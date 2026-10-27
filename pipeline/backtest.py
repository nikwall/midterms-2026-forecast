"""Backtest: calibrate the model's assumed error sizes on past elections and judge the source weights.

Data (in data/raw/backtest/; the Polymarket file is fetched here on first run):
    raw_polls_538.csv              FiveThirtyEight poll archive: polls from the final three weeks with the
                                   actual result, 1998-2022 (Senate, House districts, generic ballot)
    medsl_senate_1976_2024.tab     MIT Election Data + Science Lab, Senate results by state
    medsl_president_1976_2024.csv  MIT Election Data + Science Lab, presidential results by state
    polymarket_senate_2024.json    Polymarket 2024 Senate prices one week before Election Day

Everything is evaluated "as of 7 days before Election Day", which is where we stand on 27 Oct 2026.
Poll averages use the same rules as fetch_polls.py; fundamentals the same formula as fundamentals.py.

Writes data/backtest_polls.csv, data/backtest_senate_fundamentals.csv, data/backtest_markets_2024.csv
and research/backtest_report.md.

    python -I pipeline/backtest.py
"""

import csv
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "backtest"
OUT = ROOT / "data"
REPORT = ROOT / "research" / "backtest_report.md"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}
N = NormalDist()

AS_OF_DAYS = 7
MIDTERMS = ["1998", "2002", "2006", "2010", "2014", "2018", "2022"]
# Poll weighting rules of fetch_polls.py (population is not in the archive, so it is left out).
HALF_LIFE_DAYS, SAMPLE_CAP, PARTISAN_WEIGHT = 14, 2400, 0.5
# Model v1 constants being tested.
V1 = {"poll_base": 4.5, "poll_sampling": 7.0, "nat_sd": 3.0, "incumbency": 3.0, "fund_sd_senate": 9.0}
POLYMARKET_TARGET_TS = 1730203200  # 29 Oct 2024 12:00 UTC, one week before 5 Nov 2024


def surname(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", s)
    tokens = [t for t in re.sub(r"[^a-z ]", " ", s).split() if t not in ("jr", "sr", "ii", "iii", "iv")]
    return tokens[-1] if tokens else ""


def num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else float("nan")


# ---------- A. polls ----------

def poll_averages(rows, type_simple):
    """Weighted poll average per race as of AS_OF_DAYS before the election, with the actual result."""
    by_race = defaultdict(list)
    for r in rows:
        if r["type_simple"] != type_simple or {r["cand1_party"], r["cand2_party"]} != {"DEM", "REP"}:
            continue
        tte = int(r["time_to_election"])
        if tte < AS_OF_DAYS:
            continue
        sign = 1 if r["cand1_party"] == "DEM" else -1
        n = num(r["samplesize"], 600.0) or 600.0
        w = (0.5 ** ((tte - AS_OF_DAYS) / HALF_LIFE_DAYS) * math.sqrt(min(n, SAMPLE_CAP) / 600)
             * (PARTISAN_WEIGHT if r["partisan"] in ("DEM", "REP") else 1.0))
        by_race[(r["cycle"], r["race"])].append({"pollster": r["pollster"], "tte": tte, "w": w,
                                                 "m": sign * float(r["margin_poll"]), "a": sign * float(r["margin_actual"])})
    out = []
    for (cycle, race), ps in by_race.items():
        by_pollster = defaultdict(list)
        for p in ps:
            by_pollster[p["pollster"]].append(p)
        for group in by_pollster.values():
            group.sort(key=lambda p: p["tte"])  # newest first
            for k, p in enumerate(group):
                p["w"] *= 0.5 ** k
        W = sum(p["w"] for p in ps)
        avg = sum(p["w"] * p["m"] for p in ps) / W
        out.append({"cycle": cycle, "race": race, "type": type_simple, "avg": avg, "actual": ps[0]["a"],
                    "error": avg - ps[0]["a"], "n_polls": len(ps), "n_eff": W ** 2 / sum(p["w"] ** 2 for p in ps)})
    return out


def fit_poll_error(races):
    """Error of race i = cycle-wide bias + race part with variance base^2 + s^2 / n_eff.
    The bias is the mean error of the cycle; base^2 and s^2 come from regressing the squared
    race part on 1 / n_eff."""
    by_cycle = defaultdict(list)
    for r in races:
        by_cycle[r["cycle"]].append(r)
    bias = {c: float(np.mean([r["error"] for r in rs])) for c, rs in by_cycle.items()}
    x = np.array([1 / r["n_eff"] for r in races])
    y = np.array([(r["error"] - bias[r["cycle"]]) ** 2 for r in races])
    slope, intercept = np.polyfit(x, y, 1)
    base = math.sqrt(max(intercept, 0.0))
    sampling = math.sqrt(max(slope, 0.0))
    return {"bias": bias, "base": base, "sampling": sampling,
            "rms_total": rms([r["error"] for r in races]),
            "rms_within": rms([r["error"] - bias[r["cycle"]] for r in races]),
            "rms_bias": rms(list(bias.values())), "n": len(races)}


# ---------- B. Senate fundamentals ----------

def read_tab(path):
    return list(csv.DictReader(path.open(encoding="utf-8", errors="replace"), delimiter="\t"))


def senate_results():
    """(year, state, special) -> margins and candidates from MEDSL, general elections only."""
    races = defaultdict(list)
    for r in read_tab(RAW / "medsl_senate_1976_2024.tab"):
        if r["stage"].strip('"').lower() != "gen" or r["writein"].strip('"') == "True":
            continue
        key = (int(r["year"]), r["state_po"].strip('"'), r["special"].strip('"') == "True")
        races[key].append(r)
    out = {}
    for key, rs in races.items():
        modes = {x.get("mode", "").strip('"').lower() for x in rs}
        if "total" in modes and len(modes) > 1:
            rs = [x for x in rs if x.get("mode", "").strip('"').lower() == "total"]
        total = max(num(x["totalvotes"], 0) for x in rs)
        votes = defaultdict(float)
        for x in rs:
            votes[(x["candidate"].strip('"'), x["party_simplified"].strip('"'))] += num(x["candidatevotes"], 0)
        d = sum(v for (c, p), v in votes.items() if p == "DEMOCRAT")
        rep = sum(v for (c, p), v in votes.items() if p == "REPUBLICAN")
        top_other = max([v for (c, p), v in votes.items() if p not in ("DEMOCRAT", "REPUBLICAN")] or [0])
        if total <= 0 or rep == 0 or max(d, top_other) == 0:
            continue  # uncontested by one side, or two candidates of the same party
        winner = max(votes.items(), key=lambda kv: kv[1])[0]
        out[key] = {"margin": 100 * (max(d, top_other) - rep) / total, "winner": winner,
                    "cands": {surname(c): {"DEMOCRAT": "D", "REPUBLICAN": "R"}.get(p, "O") for (c, p) in votes}}
    return out


def president_margins():
    """year -> (state margins D-R, national margin), from MEDSL."""
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
    for r in csv.DictReader((RAW / "medsl_president_1976_2024.csv").open(encoding="utf-8", errors="replace")):
        if r["writein"] == "TRUE":
            continue
        a = acc[int(r["year"])][r["state_po"]]
        v = num(r["candidatevotes"], 0)
        if r["party_simplified"] == "DEMOCRAT":
            a[0] += v
        elif r["party_simplified"] == "REPUBLICAN":
            a[1] += v
        a[2] = max(a[2], num(r["totalvotes"], 0))
    out = {}
    for y, states in acc.items():
        nat = [sum(s[i] for s in states.values()) for i in range(3)]
        out[y] = ({st: 100 * (s[0] - s[1]) / s[2] for st, s in states.items() if s[2]}, 100 * (nat[0] - nat[1]) / nat[2])
    return out


def senate_fundamentals(results, pres, env_actual, env_polls):
    """Lean (last presidential result vs the nation), environment and incumbency for every Senate race."""
    winners = defaultdict(set)  # (year, state) -> winner surnames
    for (y, st, sp), r in results.items():
        winners[(y, st)].add(surname(r["winner"][0]))
    rows = []
    for (y, st, sp), r in sorted(results.items()):
        if y % 2 or y < 1998:
            continue
        p_year = y - 2 if y % 4 == 2 else y - 4
        if p_year not in pres or st not in pres[p_year][0]:
            continue
        lean = pres[p_year][0][st] - pres[p_year][1]
        incumbents = set().union(*(winners.get((yy, st), set()) for yy in range(y - 6, y)))
        inc = [s for s, party in r["cands"].items() if s in incumbents and party in ("D", "R")]
        inc_sign = (1 if r["cands"][inc[0]] == "D" else -1) if inc else 0
        rows.append({"year": y, "state": st, "special": sp, "margin": r["margin"], "lean": lean, "inc_sign": inc_sign,
                     "env_actual": env_actual.get(str(y)), "env_polls": env_polls.get(str(y))})
    return rows


def fit_fundamentals(rows):
    """margin - (lean + actual national House margin) = beta * incumbency + race error."""
    rs = [r for r in rows if r["env_actual"] is not None]
    x = np.array([r["inc_sign"] for r in rs], dtype=float)
    y = np.array([r["margin"] - (r["lean"] + r["env_actual"]) for r in rs])
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    close = [i for i, r in enumerate(rs) if abs(r["lean"] + r["env_actual"] + coef[1] * r["inc_sign"]) < 20]
    return {"intercept": float(coef[0]), "incumbency": float(coef[1]), "race_sd": float(np.std(resid, ddof=2)),
            "race_sd_close": float(np.std(resid[close], ddof=2)) if len(close) > 3 else float("nan"),
            "n": len(rs), "n_close": len(close)}


# ---------- C. markets, 2024 Senate ----------

def get_json(url, params):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


STATE_NAMES = {
    "AZ": "Arizona", "CA": "California", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "HI": "Hawaii",
    "IN": "Indiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "ND": "North Dakota", "OH": "Ohio", "PA": "Pennsylvania", "RI": "Rhode Island",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def fetch_polymarket_2024():
    path = RAW / "polymarket_senate_2024.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    out = []
    for abbr, name in STATE_NAMES.items():
        slug = name.lower().replace(" ", "-") + "-us-senate-election-winner"
        events = get_json("https://gamma-api.polymarket.com/events", {"slug": slug})
        if not events:
            continue
        outcomes = []
        for m in events[0].get("markets", []):
            tokens = json.loads(m.get("clobTokenIds") or "[]")
            if not tokens:
                continue
            hist = get_json("https://clob.polymarket.com/prices-history",
                            {"market": tokens[0], "startTs": POLYMARKET_TARGET_TS - 43200,
                             "endTs": POLYMARKET_TARGET_TS + 43200, "fidelity": 60}).get("history", [])
            price = min(hist, key=lambda h: abs(h["t"] - POLYMARKET_TARGET_TS))["p"] if hist else None
            outcomes.append({"label": m.get("groupItemTitle"), "price": price, "volume": num(m.get("volume"), 0.0)})
            time.sleep(0.1)
        out.append({"state": abbr, "slug": slug, "outcomes": outcomes})
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def market_rows(pm, results):
    rows = []
    for e in pm:
        res = results.get((2024, e["state"], False))
        if not res:
            continue
        p = {"D": 0.0, "R": 0.0, "O": 0.0}
        for o in e["outcomes"]:
            if o["price"] is None:
                continue
            party = res["cands"].get(surname(o["label"]), "O")
            p[party] += o["price"]
        total = sum(p.values())
        if not total or not p["R"]:
            continue
        rows.append({"state": e["state"], "p_nonrep": 1 - p["R"] / total, "margin": res["margin"],
                     "won": res["margin"] > 0, "volume": sum(o["volume"] for o in e["outcomes"])})
    return rows


def brier(ps, ys):
    return float(np.mean([(p - y) ** 2 for p, y in zip(ps, ys)]))


def logloss(ps, ys):
    return float(np.mean([-math.log(min(max(p if y else 1 - p, 1e-4), 1)) for p, y in zip(ps, ys)]))


# ---------- D. weights: polls vs fundamentals on past Senate midterms ----------

def weight_check(poll_rows, fund_rows, poll_fit, fund_fit, nat_sd):
    """For Senate midterm races with polls, compare fixed poll weights with the inverse-variance rule."""
    fund = {(str(r["year"]), r["state"]): r for r in fund_rows if r["env_polls"] is not None and not r["special"]}
    pairs = []
    for p in poll_rows:
        st = p["race"].split("_")[-1]
        f = fund.get((p["cycle"], st))
        if p["cycle"] not in MIDTERMS or not f:
            continue
        f_margin = f["lean"] + f["env_polls"] + fund_fit["incumbency"] * f["inc_sign"]
        p_sd = math.sqrt(poll_fit["base"] ** 2 + poll_fit["sampling"] ** 2 / p["n_eff"] + poll_fit["rms_bias"] ** 2)
        f_sd = math.sqrt(nat_sd ** 2 + fund_fit["race_sd"] ** 2)
        pairs.append({"poll": p["avg"], "fund": f_margin, "actual": p["actual"], "p_sd": p_sd, "f_sd": f_sd})
    grid = []
    for w in [i / 10 for i in range(11)]:
        errs = [w * x["poll"] + (1 - w) * x["fund"] - x["actual"] for x in pairs]
        grid.append({"w_polls": w, "rmse": rms(errs)})
    iv = []
    for x in pairs:
        wp = (1 / x["p_sd"] ** 2) / (1 / x["p_sd"] ** 2 + 1 / x["f_sd"] ** 2)
        iv.append((wp, wp * x["poll"] + (1 - wp) * x["fund"] - x["actual"]))
    return {"n": len(pairs), "grid": grid, "iv_mean_w": float(np.mean([w for w, _ in iv])), "iv_rmse": rms([e for _, e in iv])}


# ---------- report ----------

def main():
    polls = list(csv.DictReader((RAW / "raw_polls_538.csv").open(encoding="utf-8", errors="replace")))

    sen = poll_averages(polls, "Sen-G")
    house = poll_averages(polls, "House-G")
    generic = poll_averages(polls, "House-G-US")
    sen_mid = [r for r in sen if r["cycle"] in MIDTERMS]
    house_mid = [r for r in house if r["cycle"] in MIDTERMS]
    gen_mid = [r for r in generic if r["cycle"] in MIDTERMS]
    fit_sen, fit_house, fit_all_sen = fit_poll_error(sen_mid), fit_poll_error(house_mid), fit_poll_error(sen)
    gen_err = {r["cycle"]: r["error"] for r in gen_mid}
    nat_sd = rms(list(gen_err.values()))

    env_actual = {r["cycle"]: r["actual"] for r in generic}
    env_polls = {r["cycle"]: r["avg"] for r in generic}
    results = senate_results()
    pres = president_margins()
    env_actual["2024"] = pres[2024][1]  # proxy: no national House result for 2024 in the archive
    fund_rows = senate_fundamentals(results, pres, env_actual, env_polls)
    fund_mid = [r for r in fund_rows if str(r["year"]) in MIDTERMS]
    fit_fund, fit_fund_all = fit_fundamentals(fund_mid), fit_fundamentals(fund_rows)

    pm = fetch_polymarket_2024()
    mkt = market_rows(pm, results)
    close_mkt = [r for r in mkt if 0.05 <= r["p_nonrep"] <= 0.95]

    # Poll-based probabilities for Senate midterms, with calibrated and with v1 error sizes.
    def poll_p(r, base, sampling, nat):
        return N.cdf(r["avg"] / math.sqrt(base ** 2 + sampling ** 2 / r["n_eff"] + nat ** 2))
    ys = [r["actual"] > 0 for r in sen_mid]
    p_cal = [poll_p(r, fit_sen["base"], fit_sen["sampling"], fit_sen["rms_bias"]) for r in sen_mid]
    p_v1 = [poll_p(r, V1["poll_base"], V1["poll_sampling"], 0.0) for r in sen_mid]
    close_poll = [r for r in sen_mid if abs(r["avg"]) < 10]

    # Market-implied margins on the calibrated scale of a well-polled race, to compare error sizes.
    ref_sd = math.sqrt(fit_sen["base"] ** 2 + fit_sen["sampling"] ** 2 / 10 + fit_sen["rms_bias"] ** 2)
    mkt_err = [ref_sd * N.inv_cdf(min(max(r["p_nonrep"], 0.01), 0.99)) - r["margin"] for r in close_mkt]
    w = weight_check(sen, fund_rows, fit_sen, fit_fund, nat_sd)

    # Files
    def write(name, rows):
        with (OUT / name).open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    write("backtest_polls.csv", sen + house + generic)
    write("backtest_senate_fundamentals.csv", fund_rows)
    write("backtest_markets_2024.csv", mkt)

    rec = {
        "poll_base": round(fit_sen["base"], 1), "poll_sampling": round(fit_sen["sampling"], 1),
        "nat_sd": round(max(nat_sd, fit_sen["rms_bias"]), 1),
        "incumbency": round(fit_fund["incumbency"], 1), "fund_sd_senate": round(fit_fund["race_sd"], 1),
    }
    (OUT / "backtest_calibration.json").write_text(json.dumps({"recommended": rec, "v1": V1}, indent=1), encoding="utf-8")

    f1 = lambda x: f"{x:.1f}"
    lines = [
        "# Backtest: calibrating the model on past elections",
        "",
        f"Generated by `pipeline/backtest.py` on {date.today().isoformat()}. Everything is evaluated as of {AS_OF_DAYS} days before Election Day.",
        "",
        "## Data",
        "",
        f"- Poll archive (FiveThirtyEight, 1998–2022): {len(sen_mid)} Senate, {len(house_mid)} House-district and {len(gen_mid)} generic-ballot poll averages in the midterms {', '.join(MIDTERMS)}.",
        f"- Senate results and presidential results by state, 1976–2024 (MIT Election Data + Science Lab): {len(fund_mid)} contested Senate midterm races with a lean.",
        f"- Polymarket 2024 Senate prices on 29 Oct 2024: {len(mkt)} races ({len(close_mkt)} not safe, priced 5–95%).",
        "- Limits: no market prices for 2022 and no poll archive for 2024, so polls and markets are never compared in the same races. The House results file needs a registration form, so House fundamentals are not calibrated.",
        "",
        "## A. How large are polling errors?",
        "",
        "Error = poll average minus result, in points of margin. It is split into a part shared by all races of a cycle (the cycle bias) and a race part.",
        "",
        "| Cycle | Senate bias | House-district bias | Generic-ballot error |",
        "|---|---|---|---|",
    ]
    for c in MIDTERMS:
        lines.append(f"| {c} | {fit_sen['bias'].get(c, float('nan')):+.1f} | {fit_house['bias'].get(c, float('nan')):+.1f} | {gen_err.get(c, float('nan')):+.1f} |")
    lines += [
        f"| **Typical size (RMS)** | **{f1(fit_sen['rms_bias'])}** | **{f1(fit_house['rms_bias'])}** | **{f1(nat_sd)}** |",
        "",
        "Positive = polls too Democratic.",
        "",
        "| Race part | Senate midterms | House districts | Model v1 |",
        "|---|---|---|---|",
        f"| Irreducible error (base) | {f1(fit_sen['base'])} | {f1(fit_house['base'])} | {V1['poll_base']} |",
        f"| Noise of one poll (sampling) | {f1(fit_sen['sampling'])} | {f1(fit_house['sampling'])} | {V1['poll_sampling']} |",
        f"| Total error, all races (RMS) | {f1(fit_sen['rms_total'])} | {f1(fit_house['rms_total'])} | |",
        f"| Races | {fit_sen['n']} | {fit_house['n']} | |",
        "",
        f"For comparison, all Senate cycles 1998–2022 including presidential years: base {f1(fit_all_sen['base'])}, sampling {f1(fit_all_sen['sampling'])}, typical cycle bias {f1(fit_all_sen['rms_bias'])}.",
        "",
        "## B. How far do Senate races stray from the fundamentals?",
        "",
        "Regression of (result − lean − actual national House margin) on incumbency, contested Senate races.",
        "",
        "| | Midterms only | All cycles 1998–2024 | Model v1 |",
        "|---|---|---|---|",
        f"| Incumbency bonus (points of margin) | {f1(fit_fund['incumbency'])} | {f1(fit_fund_all['incumbency'])} | {V1['incumbency']} |",
        f"| Race error, all races | {f1(fit_fund['race_sd'])} | {f1(fit_fund_all['race_sd'])} | {V1['fund_sd_senate']} |",
        f"| Race error, races within 20 points | {f1(fit_fund['race_sd_close'])} | {f1(fit_fund_all['race_sd_close'])} | |",
        f"| Races | {fit_fund['n']} | {fit_fund_all['n']} | |",
        "",
        f"National environment error (generic-ballot average vs. national House vote, midterms): RMS {f1(nat_sd)} points (model v1: {V1['nat_sd']}).",
        "",
        "## C. Polls and markets: accuracy",
        "",
        "| | Senate polls, midterms 1998–2022 | Polymarket, Senate 2024 |",
        "|---|---|---|",
        f"| Races | {len(sen_mid)} | {len(mkt)} |",
        f"| Brier score (lower is better) | {brier(p_cal, ys):.3f} (calibrated) / {brier(p_v1, ys):.3f} (v1 errors) | {brier([r['p_nonrep'] for r in mkt], [r['won'] for r in mkt]):.3f} |",
        f"| Log loss | {logloss(p_cal, ys):.3f} / {logloss(p_v1, ys):.3f} | {logloss([r['p_nonrep'] for r in mkt], [r['won'] for r in mkt]):.3f} |",
        f"| Margin error in close races (RMS) | {f1(rms([r['error'] for r in close_poll]))} ({len(close_poll)} races with a poll margin under 10) | {f1(rms(mkt_err))} ({len(close_mkt)} races priced 5–95%, price turned into a margin on the scale of a well-polled race) |",
        "",
        "Brier scores from different years are only roughly comparable: 2024 had few upsets, and its close races are a small sample.",
        "",
        "Polymarket 2024, races priced between 5% and 95% one week out (chance of the non-Republican side):",
        "",
        "| State | Market | Result (margin) | Non-Republican won |",
        "|---|---|---|---|",
    ]
    for r in sorted(close_mkt, key=lambda r: -r["p_nonrep"]):
        lines.append(f"| {r['state']} | {r['p_nonrep']:.0%} | {r['margin']:+.1f} | {'yes' if r['won'] else 'no'} |")
    lines += [
        "",
        "## D. Polls vs. fundamentals: which weighting would have worked?",
        "",
        f"{w['n']} Senate midterm races with polls (1998–2022). The fundamentals use the pre-election generic-ballot average as the national environment, as the live model does.",
        "",
        "| Poll weight | " + " | ".join(f"{g['w_polls']:.1f}" for g in w["grid"]) + " |",
        "|---|" + "---|" * len(w["grid"]),
        "| Margin error (RMS) | " + " | ".join(f1(g["rmse"]) for g in w["grid"]) + " |",
        "",
        f"Inverse-variance rule with the calibrated errors: average poll weight {w['iv_mean_w']:.2f}, margin error {f1(w['iv_rmse'])}.",
        "",
        "## Recommended constants",
        "",
        "| Constant | Model v1 | Backtest |",
        "|---|---|---|",
    ] + [f"| {k} | {V1[k]} | {rec[k]} |" for k in rec] + [""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"recommended": rec, "v1": V1}, indent=1))
    print("weights grid:", [(g["w_polls"], round(g["rmse"], 2)) for g in w["grid"]], "iv:", round(w["iv_mean_w"], 2), round(w["iv_rmse"], 2))
    print("markets:", len(mkt), "close:", len(close_mkt), "brier", round(brier([r['p_nonrep'] for r in mkt], [r['won'] for r in mkt]), 3))


if __name__ == "__main__":
    main()
