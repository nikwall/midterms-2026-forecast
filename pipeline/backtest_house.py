"""How our House model would have done in 2022 and 2024.

Runs the House part of the model as of 7 days before each election, with the inputs that exist
for that year, and scores it the way the HKS contest scores us: (a) Democratic seats, (b) the
chance of a Democratic majority, (c) district probabilities (Brier score).

Inputs per year (same formulas and constants as the 2026 model)
    fundamentals   district lean + national environment + incumbency (±3 pts); race error ±6,
                   national error ±3.6 (fundamentals.py, model.py: our own House fundamentals)
                   lean 2022: FiveThirtyEight partisan lean on the 2022 lines
                   lean 2024: 2020 presidential margin on the 2024 lines (The Downballot) minus the
                              national D+4.45
                   environment: generic-ballot polls up to 7 days out, weighted as in fetch_polls.py
    polls          district polls of the actual matchup up to 7 days out, weighted as in fetch_polls.py
                   2022: FiveThirtyEight poll archive (raw_polls_538.csv, as in backtest.py)
                   2024: FiveThirtyEight polls page, Wayback Machine copy of 29 Nov 2024
    missing        market prices and DDHQ's probabilities for those years. In 2026 they carry most of
                   the weight in the contest districts, so this is a test of the model's skeleton.

Results: FiveThirtyEight election-results repository. Raw files go to data/raw/backtest/ and are
downloaded on the first run. Writes data/backtest_house.json, app/data/backtest.json and
research/backtest_house_report.md.

    python -I pipeline/backtest_house.py
"""

import csv
import json
import math
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "backtest"
OUT = ROOT / "data"
REPORT = ROOT / "research" / "backtest_house_report.md"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}

DOWNLOADS = {
    "fte_election_results_house.csv": "https://raw.githubusercontent.com/fivethirtyeight/election-results/main/election_results_house.csv",
    "fte_partisan_lean_districts.csv": "https://raw.githubusercontent.com/fivethirtyeight/data/master/partisan-lean/fivethirtyeight_partisan_lean_DISTRICTS.csv",
    "downballot_presbycd_2024lines.csv": "https://docs.google.com/spreadsheets/d/1ng1i_Dm_RMDnEvauH44pgE6JCUsapcuu8F2pCfeLWFo/export?format=csv&gid=1491069057",
    "wayback/house_polls_2024.csv": "https://web.archive.org/web/20241129175737id_/https://projects.fivethirtyeight.com/polls-page/data/house_polls.csv",
    "wayback/generic_polls_2024.csv": "https://web.archive.org/web/20241129175749id_/https://projects.fivethirtyeight.com/polls-page/data/generic_ballot_polls.csv",
}
ELECTIONS = {"2022": date(2022, 11, 8), "2024": date(2024, 11, 5)}
AS_OF_DAYS = 7
NATIONAL_2020 = 4.45  # Biden's national margin, for the 2024 lean
INCUMBENCY = model.DEFAULT_CFG["incumbency"]
NAT_SD = 3.6
FUND_SD = math.sqrt(NAT_SD ** 2 + model.DEFAULT_CFG["fund_race_sd"]["house"] ** 2)
POLL_BASE, POLL_SAMPLING = model.POLL_BASE_ERROR, model.POLL_SAMPLING_ERROR
HALF_LIFE, SAMPLE_CAP, PARTISAN_W = 14, 2400, 0.5
POP_W = {"lv": 1.0, "rv": 0.8, "v": 0.8, "a": 0.6}
N_SIMS = 20_000


def fetch_raw():
    for name, url in DOWNLOADS.items():
        path = RAW / name
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
            path.write_bytes(r.read())
        print("downloaded", name)


def rows(name):
    return list(csv.DictReader((RAW / name).open(encoding="utf-8", errors="replace")))


def surname(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", s)
    tokens = [t for t in re.sub(r"[^a-z ]", " ", s).split() if t not in ("jr", "sr", "ii", "iii", "iv")]
    return tokens[-1] if tokens else ""


def did(st, n):
    return f"H-{st}-AL" if n in (0, "AL") else f"H-{st}-{int(n):02d}"


def mdy(s):
    return datetime.strptime(s, "%m/%d/%y").date()


# ---------- results and incumbents ----------

def party_of(ballot_parties):
    if ballot_parties & {"DEM", "DFL"}:
        return "D"
    if "REP" in ballot_parties:
        return "R"
    return "O"


def results(year, all_rows, at_large):
    """District -> winner party, Democratic margin (pts), general-election candidates."""
    out = {}
    by_d = defaultdict(list)
    for r in all_rows:
        if r["cycle"] == year and r["special"] == "false" and r["stage"] in ("general", "jungle primary"):
            n = int(re.sub(r"\D", "", r["office_seat_name"]) or 0)
            by_d[did(r["state_abbrev"], "AL" if r["state_abbrev"] in at_large else n)].append(r)
    for d, rs in by_d.items():
        final_round = max((int(r["ranked_choice_round"]) for r in rs if r["ranked_choice_round"]), default=None)
        if final_round:
            rs_votes = [r for r in rs if r["ranked_choice_round"] in ("", str(final_round))]
        else:
            rs_votes = rs
        cand = defaultdict(lambda: {"votes": 0, "parties": set(), "name": "", "pid": "", "winner": False})
        for r in rs:
            c = cand[r["candidate_id"]]
            c["parties"].add(r["ballot_party"])
            c["name"], c["pid"] = r["candidate_name"], r["politician_id"]
            c["winner"] |= r["winner"] == "true"
        for r in rs_votes:
            cand[r["candidate_id"]]["votes"] += int(float(r["votes"] or 0))
        winners = [c for c in cand.values() if c["winner"]]
        if not winners:
            continue
        total = sum(c["votes"] for c in cand.values()) or 1
        dv = max((c["votes"] for c in cand.values() if party_of(c["parties"]) == "D"), default=0)
        rv = max((c["votes"] for c in cand.values() if party_of(c["parties"]) == "R"), default=0)
        out[d] = {"winner": party_of(winners[0]["parties"]), "margin": round(100 * (dv - rv) / total, 1),
                  "cands": [{"name": c["name"], "pid": c["pid"], "party": party_of(c["parties"])} for c in cand.values()]}
    return out


def incumbents(year, all_rows):
    """Politician ids of House members elected in the previous cycle or in a special since."""
    prev = str(int(year) - 2)
    ids = set()
    for r in all_rows:
        if r["winner"] == "true" and (r["cycle"] == prev and r["special"] == "false"
                                      or r["special"] == "true" and prev <= r["cycle"] <= year):
            ids.add(r["politician_id"])
    return ids


# ---------- polls ----------

def poll_average(polls, as_of):
    """Weighted average with fetch_polls.py's rules; returns margin, sd, n_polls, n_eff."""
    ps = [dict(p) for p in polls if p["end"] <= as_of]
    if not ps:
        return None
    for p in ps:
        age = (as_of - p["end"]).days
        p["w"] = (0.5 ** (age / HALF_LIFE) * math.sqrt(min(p["n"] or 600, SAMPLE_CAP) / 600)
                  * POP_W.get(p["pop"], 0.6) * (PARTISAN_W if p["partisan"] else 1.0))
    by_pollster = defaultdict(list)
    for p in ps:
        by_pollster[p["pollster"]].append(p)
    for group in by_pollster.values():
        group.sort(key=lambda p: p["end"], reverse=True)
        for k, p in enumerate(group):
            p["w"] *= 0.5 ** k
    w = sum(p["w"] for p in ps)
    avg = sum(p["w"] * p["m"] for p in ps) / w
    n_eff = w ** 2 / sum(p["w"] ** 2 for p in ps)
    return {"margin": avg, "sd": math.sqrt(POLL_BASE ** 2 + POLL_SAMPLING ** 2 / n_eff), "n_polls": len(ps), "n_eff": n_eff}


def polls_2022(at_large):
    out = defaultdict(list)
    generic = []
    for r in rows("raw_polls_538.csv"):
        if r["cycle"] != "2022" or {r["cand1_party"], r["cand2_party"]} != {"DEM", "REP"}:
            continue
        sign = 1 if r["cand1_party"] == "DEM" else -1
        p = {"pollster": r["pollster"], "end": date.fromisoformat(r["polldate"]), "n": float(r["samplesize"] or 600),
             "pop": "lv", "partisan": r["partisan"] in ("DEM", "REP"), "m": sign * float(r["margin_poll"]),
             "names": {surname(r["cand1_name"]), surname(r["cand2_name"])}}
        if r["type_simple"] == "House-G-US":
            generic.append(p)
        elif r["type_simple"] == "House-G":
            st, n = r["location"].split("-")
            out[did(st, "AL" if st in at_large else n)].append(p)
    return out, generic


def polls_2024(at_large, abbr):
    by_q = defaultdict(list)
    for r in rows("wayback/house_polls_2024.csv"):
        if r["cycle"] == "2024" and r["stage"] == "general" and r["hypothetical"] != "true" and r["state"] in abbr:
            by_q[r["question_id"]].append(r)
    best = {}  # one question per poll and district, likely voters first
    for qid, rs in by_q.items():
        parties = Counter(r["party"] for r in rs)
        if parties["DEM"] != 1 or parties["REP"] != 1:
            continue
        r0 = rs[0]
        st = abbr[r0["state"]]
        d = did(st, "AL" if st in at_large else r0["seat_number"])
        dem = next(r for r in rs if r["party"] == "DEM")
        rep = next(r for r in rs if r["party"] == "REP")
        p = {"pollster": r0["pollster"], "end": mdy(r0["end_date"]), "n": float(r0["sample_size"] or 600),
             "pop": r0["population"], "partisan": bool(r0["partisan"] or r0["internal"] == "true"),
             "m": float(dem["pct"]) - float(rep["pct"]), "names": {surname(dem["candidate_name"]), surname(rep["candidate_name"])}}
        key = (r0["poll_id"], d)
        rank = {"lv": 0, "rv": 1, "v": 1}.get(p["pop"], 2)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, d, p)
    out = defaultdict(list)
    for _, d, p in best.values():
        out[d].append(p)
    generic = []
    for r in rows("wayback/generic_polls_2024.csv"):
        if r["cycle"] == "2024" and r["dem"] and r["rep"]:
            generic.append({"pollster": r["pollster"], "end": mdy(r["end_date"]), "n": float(r["sample_size"] or 600),
                            "pop": r["population"], "partisan": bool(r["partisan"] or r["internal"] == "true"),
                            "m": float(r["dem"]) - float(r["rep"])})
    return out, generic


# ---------- leans ----------

def lean_2022():
    out = {}
    for r in rows("fte_partisan_lean_districts.csv"):
        st, n = r["district"].split("-")
        out[(st, int(n))] = float(r["2022"])
    return out


def lean_2024():
    out = {}
    lines = list(csv.reader((RAW / "downballot_presbycd_2024lines.csv").open(encoding="utf-8")))
    for r in lines[3:]:
        m = re.fullmatch(r"([A-Z]{2})-(\d+|AL)", r[0].strip())
        if m and r[15].strip():
            out[(m.group(1), 0 if m.group(2) == "AL" else int(m.group(2)))] = float(r[15].strip().rstrip("%")) - NATIONAL_2020
    return out


# ---------- run one year ----------

def brier(ps, ys):
    return float(np.mean([(p - y) ** 2 for p, y in zip(ps, ys)])) if ps else float("nan")


def run_year(year, seats_meta, all_rows):
    election = ELECTIONS[year]
    as_of = election - timedelta(days=AS_OF_DAYS)
    abbr = {s["name"]: s["abbr"] for s in seats_meta["states"]}
    division = {s["abbr"]: s["division"] for s in seats_meta["states"]}
    at_large = {"AK", "DE", "ND", "SD", "VT", "WY"}
    res = results(year, all_rows, at_large)
    inc = incumbents(year, all_rows)
    if year == "2022":
        district_polls, generic = polls_2022(at_large)
        leans = lean_2022()
        lean_source = "FiveThirtyEight partisan lean, 2022 lines"
    else:
        district_polls, generic = polls_2024(at_large, abbr)
        leans = lean_2024()
        lean_source = "2020 presidential margin on the 2024 lines (The Downballot) minus D+4.45"
    env = poll_average(generic, as_of)
    environment = env["margin"]

    races, missing = [], []
    for d, r in sorted(res.items()):
        st = d.split("-")[1]
        n = 0 if d.endswith("-AL") else int(d.split("-")[2])
        lean = leans.get((st, n), leans.get((st, 1)) if n == 0 else None)
        if lean is None:
            missing.append(d)
            continue
        inc_party = {c["party"] for c in r["cands"] if c["pid"] in inc and c["party"] in ("D", "R")}
        inc_adj = INCUMBENCY if inc_party == {"D"} else -INCUMBENCY if inc_party == {"R"} else 0.0
        fund = {"margin": lean + environment + inc_adj, "sd": FUND_SD}
        names = {surname(c["name"]) for c in r["cands"]}
        actual_polls = [p for p in district_polls.get(d, []) if p["names"] <= names]  # the real matchup only
        pav = poll_average(actual_polls, as_of)
        inputs = {"fundamentals": fund}
        if pav:
            inputs["polls"] = pav
        races.append({"id": d, "state": st, "chamber": "house", "side": "D", "inputs": inputs,
                      "won": 1 if r["winner"] == "D" else 0, "actual_margin": r["margin"], "incumbent": "".join(sorted(inc_party))})

    data = {"division": division, "env": {"sd": NAT_SD}, "not_up_d": 0}
    cfg = {"nat_sd": NAT_SD, "rest_shares": model.REST_SHARES}
    variants = {}
    for vname, keys in (("model", ("fundamentals", "polls")), ("fundamentals_only", ("fundamentals",))):
        for r in races:
            used = {k: v for k, v in r["inputs"].items() if k in keys}
            r["mean"], r["sd"], _ = model.combine(used, model.FLOOR_SD)
        _, margins, wins, house_d, _ = model.simulate(races, data, cfg, model.SEED, N_SIMS)
        p = wins.mean(axis=0)
        variants[vname] = {"p": p, "house_d": house_d}

    actual_d = sum(r["won"] for r in races)
    out = {"year": year, "election": election.isoformat(), "as_of": as_of.isoformat(), "lean_source": lean_source,
           "environment": round(environment, 1), "generic_polls": env["n_polls"],
           "districts": len(races), "districts_missing_lean": missing,
           "districts_with_polls": sum("polls" in r["inputs"] for r in races),
           "district_polls": sum(r["inputs"]["polls"]["n_polls"] for r in races if "polls" in r["inputs"]),
           "actual_d_seats": actual_d, "actual_majority": actual_d >= 218, "variants": {}}
    for vname, v in variants.items():
        p, hd = v["p"], v["house_d"]
        q = np.percentile(hd, [10, 50, 90])
        ys = [r["won"] for r in races]
        comp = [i for i, x in enumerate(p) if 0.05 <= x <= 0.95]
        polled = [i for i, r in enumerate(races) if "polls" in r["inputs"]]
        closest = sorted(range(len(races)), key=lambda i: abs(p[i] - 0.5))[:5]
        p_maj = float((hd >= 218).mean())
        bins = []
        for lo, hi, label in ((0, 0.05, "Safe R (<5%)"), (0.05, 0.35, "Likely R (5–35%)"), (0.35, 0.65, "Toss-up and lean (35–65%)"),
                              (0.65, 0.95, "Likely D (65–95%)"), (0.95, 1.01, "Safe D (95%+)")):
            idx = [i for i, x in enumerate(p) if lo <= x < hi]
            if idx:
                bins.append({"bin": label, "n": len(idx), "mean_p": round(float(np.mean(p[idx])), 3),
                             "d_won": round(float(np.mean([ys[i] for i in idx])), 3)})
        out["variants"][vname] = {
            "median": int(q[1]), "mean": round(float(hd.mean()), 1), "ci80": [int(q[0]), int(q[2])],
            "seat_error": int(q[1]) - actual_d, "p_majority": round(p_maj, 3),
            "brier_majority": round((p_maj - (1 if actual_d >= 218 else 0)) ** 2, 3),
            "brier_all": round(brier(list(p), ys), 4),
            "brier_competitive": round(brier([p[i] for i in comp], [ys[i] for i in comp]), 4), "n_competitive": len(comp),
            "brier_polled": round(brier([p[i] for i in polled], [ys[i] for i in polled]), 4), "n_polled": len(polled),
            "favourites_won": round(float(np.mean([(p[i] > 0.5) == (ys[i] == 1) for i in comp])), 3) if comp else None,
            "calls_wrong": int(sum((p[i] > 0.5) != (ys[i] == 1) for i in range(len(races)))),
            "closest_five": [{"race_id": races[i]["id"], "p": round(float(p[i]), 2), "won": ys[i],
                              "actual_margin": races[i]["actual_margin"]} for i in closest],
            "brier_closest_five": round(brier([p[i] for i in closest], [ys[i] for i in closest]), 4),
            "calibration": bins,
        }
        if vname == "model":
            out["misses"] = sorted([{"race_id": races[i]["id"], "p": round(float(p[i]), 2), "won": ys[i],
                                     "actual_margin": races[i]["actual_margin"], "polls": "polls" in races[i]["inputs"]}
                                    for i in range(len(races)) if (p[i] > 0.5) != (ys[i] == 1)],
                                   key=lambda m: -abs(m["p"] - 0.5))
    return out


def report(results_by_year):
    lines = [
        "# Backtest: our House model in 2022 and 2024", "",
        f"Generated by `pipeline/backtest_house.py` on {date.today().isoformat()}. Each year is run as of 7 days before Election Day, "
        "with the formulas and error sizes of the 2026 model. The inputs are polls and our own fundamentals; market prices and "
        "DDHQ's probabilities are not available for those years, so in 2026 terms this is the model without two of its three inputs "
        "in most districts.", "",
        "| | 2022 | 2024 |", "|---|---|---|",
    ]
    y22, y24 = results_by_year["2022"], results_by_year["2024"]
    m22, m24 = y22["variants"]["model"], y24["variants"]["model"]
    f22, f24 = y22["variants"]["fundamentals_only"], y24["variants"]["fundamentals_only"]
    rows_ = [
        ("National environment (generic-ballot polls)", f"D{y22['environment']:+.1f}", f"D{y24['environment']:+.1f}"),
        ("District polls used (districts)", f"{y22['district_polls']} ({y22['districts_with_polls']})", f"{y24['district_polls']} ({y24['districts_with_polls']})"),
        ("**(a) Democratic seats: our median**", f"**{m22['median']}** (80%: {m22['ci80'][0]}–{m22['ci80'][1]})", f"**{m24['median']}** (80%: {m24['ci80'][0]}–{m24['ci80'][1]})"),
        ("Actual Democratic seats", str(y22["actual_d_seats"]), str(y24["actual_d_seats"])),
        ("Seats off by", f"{m22['seat_error']:+d}", f"{m24['seat_error']:+d}"),
        ("**(b) P(Democratic majority)**", f"**{m22['p_majority']:.2f}** (Republicans won)", f"**{m24['p_majority']:.2f}** (Republicans won)"),
        ("Brier score of (b)", f"{m22['brier_majority']:.3f}", f"{m24['brier_majority']:.3f}"),
        ("**(c) Brier, five closest districts**", f"**{m22['brier_closest_five']:.3f}**", f"**{m24['brier_closest_five']:.3f}**"),
        ("Brier, all districts 5–95%", f"{m22['brier_competitive']:.3f} ({m22['n_competitive']})", f"{m24['brier_competitive']:.3f} ({m24['n_competitive']})"),
        ("Brier, all 435 districts", f"{m22['brier_all']:.4f}", f"{m24['brier_all']:.4f}"),
        ("Districts called wrong", str(m22["calls_wrong"]), str(m24["calls_wrong"])),
        ("Fundamentals only: median seats / P(majority)", f"{f22['median']} / {f22['p_majority']:.2f}", f"{f24['median']} / {f24['p_majority']:.2f}"),
    ]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows_]
    for y in (y22, y24):
        m = y["variants"]["model"]
        lines += ["", f"## {y['year']}", "",
                  f"Lean: {y['lean_source']}. {y['generic_polls']} generic-ballot polls, {y['district_polls']} district polls in {y['districts_with_polls']} districts.", "",
                  "Five closest districts in the model (a stand-in for the contest's part c):", "",
                  "| District | P(D) | Winner | D margin |", "|---|---|---|---|"]
        lines += [f"| {c['race_id'][2:]} | {c['p']:.2f} | {'D' if c['won'] else 'R'} | {c['actual_margin']:+.1f} |" for c in m["closest_five"]]
        lines += ["", "Calibration:", "", "| Band | Districts | Mean P(D) | Share D won |", "|---|---|---|---|"]
        lines += [f"| {b['bin']} | {b['n']} | {b['mean_p']:.2f} | {b['d_won']:.2f} |" for b in m["calibration"]]
        lines += ["", "Districts called wrong (most confident first):", "",
                  ", ".join(f"{x['race_id'][2:]} ({x['p']:.2f}, {'D' if x['won'] else 'R'} won by {abs(x['actual_margin']):.1f})" for x in y["misses"]) or "none"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    fetch_raw()
    seats_meta = json.loads((ROOT / "app" / "data" / "seats.json").read_text(encoding="utf-8"))
    all_rows = rows("fte_election_results_house.csv")
    out = {y: run_year(y, seats_meta, all_rows) for y in ELECTIONS}
    (OUT / "backtest_house.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (ROOT / "app" / "data" / "backtest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    report(out)
    for y, r in out.items():
        m = r["variants"]["model"]
        print(f"{y}: env D{r['environment']:+.1f}; districts {r['districts']} (missing lean {r['districts_missing_lean']}); "
              f"polled {r['districts_with_polls']}; median {m['median']} {m['ci80']} vs actual {r['actual_d_seats']}; "
              f"P(maj) {m['p_majority']}; Brier comp {m['brier_competitive']} ({m['n_competitive']}); closest5 {m['brier_closest_five']}; wrong {m['calls_wrong']}")


if __name__ == "__main__":
    main()
