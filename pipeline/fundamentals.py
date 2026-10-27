"""Fundamentals input: district and state lean on the 2026 lines plus the national environment.

For every race:  expected non-R margin = lean + national environment + incumbency
    lean          2024 presidential margin in the district (2026 lines) or state, minus the national 2024 margin
    environment   expected national House margin in 2026 (D minus R, points), see national_environment()
    incumbency    +/- INCUMBENCY points for the party of an incumbent who is on the ballot

Sources (downloaded to data/raw/ on first run, or with --refresh):
    The Downballot, 2024 presidential results by congressional district on the 2026 lines (Google Sheet)
    unitedstates/congress-legislators, current members of Congress (for Senate incumbents)
Also reads data/polls_races.csv (generic ballot), data/markets_races.csv (who is on the ballot)
and the latest Kalshi snapshot in data/raw/ (House popular-vote market). Run the other fetchers first.

Writes
    data/national_environment.json
    data/fundamentals_races.csv
    research/fundamentals_report.md   comparison with polls and markets

    python -I pipeline/fundamentals.py [--refresh]
"""

import csv
import glob
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
SEATS = ROOT / "app" / "data" / "seats.json"
REPORT = ROOT / "research" / "fundamentals_report.md"

DOWNBALLOT = ("https://docs.google.com/spreadsheets/d/1eZfaFI-c-PFOoKx1-zZA2MP0_dxRq_LVK0re3BOQqy0"
              "/export?format=csv&gid=1491069057")
DOWNBALLOT_FILE = RAW / "downballot" / "presbycd_2026_gid1491069057.csv"
LEGISLATORS = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
LEGISLATORS_FILE = RAW / "legislators" / "legislators-current.json"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}

# Provisional constants, to be calibrated on 2018 and 2022 results (see PROCESS.md, C15-C18).
INCUMBENCY = 3.0                         # margin points for an incumbent on the ballot
# Race-level error around the uniform-swing estimate. Senate results stray much further from
# presidential partisanship than House results (strong or weak nominees, e.g. Collins 2020).
RACE_SD = {"house": 6.0, "senate": 9.0}
POLL_ENV_SD = 3.0                        # error of the final generic-ballot average vs the House vote
# Kalshi's open-ended brackets need a representative value: "Republicans win" and "16% and above".
BRACKET_TAILS = {(-100, 0): -3.0, (16, 100): 17.5}

N = NormalDist()


def fetch(url, path, refresh):
    if path.exists() and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        path.write_bytes(r.read())


def surname(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)  # Polymarket appends "(D)" / "(R)"
    tokens = [t for t in re.sub(r"[^a-z ]", " ", s).split() if t not in ("jr", "sr", "ii", "iii", "iv", "sen", "rep")]
    return tokens[-1] if tokens else ""


def num(s):
    return float(str(s).replace(",", "").replace("%", "").strip() or "nan")


# ---------- inputs ----------

def read_districts():
    rows = {}
    for r in csv.reader(DOWNBALLOT_FILE.open(encoding="utf-8")):
        if re.fullmatch(r"[A-Z]{2}-(\d{2}|AL)", r[0] or ""):
            rows[f"H-{r[0]}"] = {
                "state": r[0][:2], "incumbent": r[1].strip(), "incumbent_party": r[2].strip("() "),
                "harris": num(r[4]), "trump": num(r[5]), "total": num(r[6]),
            }
    assert len(rows) == 435, len(rows)
    return rows


# Outcome labels that name a party or a placeholder rather than a person.
NOT_A_NAME = re.compile(r"^(democratic|republican) party$|^(democrat|republican|independent|other)$|"
                        r"^(person|candidate|party) [a-z]$|^[a-z]$", re.I)


def market_candidates():
    """race id -> set of candidate surnames listed by either market (races listing only parties are left out)."""
    out = defaultdict(set)
    for r in csv.DictReader((DATA / "markets_races.csv").open(encoding="utf-8")):
        for part in r["candidates"].split("; "):
            m = re.match(r"(.+?) \[([DRO])\] ", part + " ")
            if m and not NOT_A_NAME.match(m.group(1).strip()):
                out[r["race_id"]].add(surname(m.group(1)))
    return out


def senate_incumbents():
    members = json.loads(LEGISLATORS_FILE.read_text(encoding="utf-8"))
    out = {}
    for x in members:
        t = x["terms"][-1]
        if t["type"] != "sen":
            continue
        # Class II seats are up in 2026; Ohio and Florida hold specials for their Class III seats.
        if t.get("class") == 2 or (t["state"] in ("OH", "FL") and t.get("class") == 3):
            party = {"Democrat": "D", "Republican": "R"}.get(t["party"], "I")
            out[t["state"]] = (x["name"].get("official_full") or f"{x['name']['first']} {x['name']['last']}", party)
    return out


def kalshi_popular_vote():
    """Mean and sd of the D-minus-R national House margin implied by Kalshi's bracket market."""
    snaps = sorted(glob.glob(str(RAW / "kalshi_events_*.json")))
    if not snaps:
        return None
    for e in json.loads(Path(snaps[-1]).read_text(encoding="utf-8")):
        if e["event_ticker"].startswith("KXHOUSEPOPVOTEMARGIN-"):
            brackets = []
            for m in e["markets"]:
                lo, hi = m.get("floor_strike"), m.get("cap_strike")
                bid, ask = num(m.get("yes_bid_dollars")), num(m.get("yes_ask_dollars"))
                p = (bid + ask) / 2
                mid = BRACKET_TAILS.get((lo, hi), (lo + hi) / 2)
                brackets.append((mid, p, num(m.get("volume_fp"))))
            total = sum(p for _, p, _ in brackets)
            mean = sum(x * p for x, p, _ in brackets) / total
            sd = (sum((x - mean) ** 2 * p for x, p, _ in brackets) / total) ** 0.5
            return {"mean": mean, "sd": sd, "volume": sum(v for _, _, v in brackets), "ticker": e["event_ticker"],
                    "brackets": [{"mid": x, "p": round(p / total, 4)} for x, p, _ in brackets]}
    return None


def national_environment():
    generic = next(r for r in csv.DictReader((DATA / "polls_races.csv").open(encoding="utf-8")) if r["race_id"] == "GENERIC")
    parts = [{
        "name": "Generic-ballot polls (VoteHub, weighted v1)", "mean": float(generic["margin_nonrep"]), "sd": POLL_ENV_SD,
        "detail": f"{generic['n_polls']} polls, latest ended {generic['latest_end']}; no LV adjustment yet",
    }]
    market = kalshi_popular_vote()
    if market:
        parts.append({
            "name": "Kalshi House popular-vote margin market", "mean": round(market["mean"], 2), "sd": round(market["sd"], 2),
            "detail": f"{market['ticker']}, ${market['volume']:,.0f} traded; spread of the price distribution used as sd",
            "brackets": market["brackets"],
        })
    # Agnostic between source types: inverse-variance weights from each source's own uncertainty.
    w = [1 / p["sd"] ** 2 for p in parts]
    mean = sum(wi * p["mean"] for wi, p in zip(w, parts)) / sum(w)
    for wi, p in zip(w, parts):
        p["weight"] = round(wi / sum(w), 3)
    # Markets watch polls, so the sources are not independent: combining them does not shrink the sd.
    return {"mean": round(mean, 2), "sd": min(p["sd"] for p in parts), "components": parts,
            "cross_checks": [
                "Special elections since 2025: Democrats ran about 13 points ahead of Harris's 2024 margin (The Downballot, 104 races); not converted to a national margin yet",
                "Expectation polls: Pew (28 Sep - 4 Oct) 55% expect a Democratic House, 40% a Republican one",
                "Other poll averages: RCP D+8.3 (8-23 Oct), FiftyPlusOne 52.2-43.0 (25 Oct)",
            ]}


# ---------- races ----------

def race_row(race, chamber, state, d, national_2024, env, incumbent, inc_party, running):
    margin_2024 = 100 * (d["harris"] - d["trump"]) / d["total"]
    lean = margin_2024 - national_2024
    inc_adj = 0.0
    if running in ("yes", "assumed"):
        inc_adj = INCUMBENCY if inc_party == "D" else -INCUMBENCY if inc_party == "R" else 0.0
    expected = lean + env["mean"] + inc_adj
    sd = (env["sd"] ** 2 + RACE_SD[chamber] ** 2) ** 0.5
    return {
        "race_id": race, "chamber": chamber, "state": state,
        "pres_margin_2024": round(margin_2024, 2), "lean": round(lean, 2), "environment": env["mean"],
        "incumbent": incumbent, "incumbent_party": inc_party, "incumbent_running": running,
        "incumbency_adj": inc_adj, "expected_margin": round(expected, 2), "sd": round(sd, 2),
        "p_nonrep": round(N.cdf(expected / sd), 4),
    }


def main():
    refresh = "--refresh" in sys.argv
    fetch(DOWNBALLOT, DOWNBALLOT_FILE, refresh)
    fetch(LEGISLATORS, LEGISLATORS_FILE, refresh)
    seats = json.loads(SEATS.read_text(encoding="utf-8"))
    districts = read_districts()
    cands = market_candidates()
    env = national_environment()

    # National and state 2024 results from the district totals (DC is not a district, so it is excluded).
    tot = {k: sum(d[k] for d in districts.values()) for k in ("harris", "trump", "total")}
    national_2024 = 100 * (tot["harris"] - tot["trump"]) / tot["total"]
    states = defaultdict(lambda: {"harris": 0.0, "trump": 0.0, "total": 0.0})
    for d in districts.values():
        for k in ("harris", "trump", "total"):
            states[d["state"]][k] += d[k]

    rows = []
    for race, d in sorted(districts.items()):
        inc = d["incumbent"]
        if not inc or inc.lower().startswith("vacant"):
            running, party = "open", ""
        elif race not in cands:
            running, party = "assumed", d["incumbent_party"]  # no market listing to check against
        else:
            running, party = ("yes" if surname(inc) in cands[race] else "no"), d["incumbent_party"]
        rows.append(race_row(race, "house", d["state"], d, national_2024, env, inc, party, running))

    sen_inc = senate_incumbents()
    for s in seats["senate"]:
        name, party = sen_inc.get(s["state"], ("", ""))
        running = "yes" if name and surname(name) in cands.get(s["id"], set()) else "no"
        rows.append(race_row(s["id"], "senate", s["state"], states[s["state"]], national_2024, env, name, party, running))

    with (DATA / "fundamentals_races.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    env_out = dict(env, national_pres_margin_2024=round(national_2024, 2), computed=date.today().isoformat())
    (DATA / "national_environment.json").write_text(json.dumps(env_out, indent=1), encoding="utf-8")

    write_report(rows, env_out)
    house = [r for r in rows if r["chamber"] == "house"]
    print(f"national 2024 presidential margin (435 districts): {national_2024:+.2f}")
    print(f"national environment 2026: D{env['mean']:+.1f} (sd {env['sd']:.1f}) from " +
          ", ".join(f"{p['name']} {p['mean']:+.1f} (w {p['weight']})" for p in env["components"]))
    print(f"House: expected D seats from fundamentals {sum(r['p_nonrep'] for r in house):.0f}; "
          f"incumbents running: {sum(r['incumbent_running'] == 'yes' for r in house)}, "
          f"not running: {sum(r['incumbent_running'] == 'no' for r in house)}, assumed: {sum(r['incumbent_running'] == 'assumed' for r in house)}")


# ---------- report ----------

def write_report(rows, env):
    polls = {r["race_id"]: r for r in csv.DictReader((DATA / "polls_races.csv").open(encoding="utf-8"))}
    markets = defaultdict(list)
    for r in csv.DictReader((DATA / "markets_races.csv").open(encoding="utf-8")):
        if r["p_rep"]:
            markets[r["race_id"]].append((1 - float(r["p_rep"]), max(float(r["volume_usd"]), 1.0)))
    mkt = {k: sum(p * v for p, v in xs) / sum(v for _, v in xs) for k, xs in markets.items()}

    def pct(p):
        return "–" if p is None else f"{p:.0%}"

    def mg(x):
        return ("D+" if x >= 0 else "R+") + f"{abs(x):.1f}"

    house = [r for r in rows if r["chamber"] == "house"]
    senate = sorted((r for r in rows if r["chamber"] == "senate"), key=lambda r: abs(r["p_nonrep"] - 0.5))
    with_mkt = [r for r in house if r["race_id"] in mkt]
    seats_f = sum(r["p_nonrep"] for r in house)
    seats_m = sum(mkt[r["race_id"]] for r in with_mkt) + sum(r["p_nonrep"] for r in house if r["race_id"] not in mkt)
    diffs = sorted(with_mkt, key=lambda r: -abs(r["p_nonrep"] - mkt[r["race_id"]]))

    lines = [
        "# Fundamentals: district lean on the 2026 lines plus the national environment",
        "",
        f"Generated by `pipeline/fundamentals.py` on {env['computed']}.",
        "",
        "**In plain language.** Each seat starts from how it voted for president in 2024, measured against the country as a whole. "
        "The national mood for 2026 is added on top, plus a bonus for an incumbent who is on the ballot. "
        "No polls of the race and no market prices enter this input; it is what history and the national mood alone would predict.",
        "",
        f"**Formula.** expected margin = (2024 margin − national 2024 margin of {mg(env['national_pres_margin_2024'])}) + environment + incumbency (±{INCUMBENCY:.0f}). "
        f"The probability uses an error of √(environment sd² + race sd²), with race sd {RACE_SD['house']:.0f} for House and {RACE_SD['senate']:.0f} for Senate.",
        "",
        "## National environment",
        "",
        "| Component | D margin | sd | Weight | Detail |",
        "|---|---|---|---|---|",
    ]
    for p in env["components"]:
        lines.append(f"| {p['name']} | {mg(p['mean'])} | {p['sd']:.1f} | {p['weight']:.0%} | {p['detail']} |")
    lines += [f"| **Combined** | **{mg(env['mean'])}** | **{env['sd']:.1f}** | | weights from each source's own uncertainty; sd not shrunk, because the sources overlap |", "",
              "Cross-checks, not in the number:"] + [f"- {c}" for c in env["cross_checks"]] + [
        "",
        "## House",
        "",
        f"- Expected Democratic seats from fundamentals alone: **{seats_f:.0f}**. "
        f"With market prices in place of fundamentals wherever a market exists ({len(with_mkt)} districts): **{seats_m:.0f}**.",
        f"- {sum(r['p_nonrep'] >= 0.5 for r in house)} districts lean Democratic on fundamentals (218 needed).",
        "",
        "Largest differences between fundamentals and markets (House):",
        "",
        "| District | Fundamentals | Market | Expected margin | 2024 pres | Incumbent | On ballot |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in diffs[:20]:
        lines.append(f"| {r['race_id']} | {pct(r['p_nonrep'])} | {pct(mkt[r['race_id']])} | {mg(r['expected_margin'])} | "
                     f"{mg(r['pres_margin_2024'])} | {r['incumbent']} ({r['incumbent_party']}) | {r['incumbent_running']} |")
    lines += [
        "",
        "## Senate: fundamentals next to polls and markets",
        "",
        "Chance of the non-Republican side. Sorted by how close the fundamentals are to 50%.",
        "",
        "| Race | Fundamentals | Polls | Market | Expected margin | 2024 pres | Incumbent on ballot |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in senate:
        pr = polls.get(r["race_id"])
        lines.append(f"| {r['race_id']} | {pct(r['p_nonrep'])} | {pct(float(pr['p_nonrep'])) if pr else '–'} | {pct(mkt.get(r['race_id']))} | "
                     f"{mg(r['expected_margin'])} | {mg(r['pres_margin_2024'])} | "
                     f"{r['incumbent'] + ' (' + r['incumbent_party'] + ')' if r['incumbent_running'] == 'yes' else 'open'} |")
    lines += [
        "",
        "**Reading the Senate table.** Fundamentals know nothing about the candidates. Where polls and markets agree with each other but not with the fundamentals "
        "(e.g. a strong or weak nominee), the candidate effect is the likely reason. This input should then get little weight in that race.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
