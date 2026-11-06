"""Collect the election results of 3 November 2026 and match them to our 470 races.

Sources (public JSON behind their results pages, re-read every 3 hours by update-results.yml):
    CNN    politics.api.cnn.io/results/national-races/2026-HG.json and 2026-SG.json
    NYT    static01.nyt.com/elections-assets/pages/data/2026-11-03/results-house.json and -senate.json
           (race calls by the Associated Press)

A race counts as called once either source names a winner; if they name different parties it is
"disputed" and counts as not called. A top-two race whose finalists share a party (California) also
counts as called for that party, with no candidate named: the seat is decided, as in the NYT seat
tally, though the person is not. Votes come from whichever source has counted more.
Not-yet-called races keep the current leader, except where a runoff decides (Louisiana's open
races without a majority).

Writes app/data/results.json. The file is rewritten only when something changed, so an unchanged
count makes no commit. If one source is down the other is used and earlier calls are kept.

    python -I pipeline/fetch_results.py
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "data"
OUT = APP / "results.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; api232-midterms-forecast/0.1; course project)"}

CNN = "https://politics.api.cnn.io/results/national-races/2026-{}.json"
NYT = "https://static01.nyt.com/elections-assets/pages/data/2026-11-03/results-{}.json"
CNN_PARTY = {"D": "D", "R": "R"}
NYT_PARTY = {"DEM": "D", "GOP": "R"}
RUNOFF_STATES = {"LA"}  # open races: without a majority the top two go to a runoff


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
        return json.load(r)


def race_id(chamber, state, number, at_large):
    if chamber == "senate":
        return f"S-{state}"
    return f"H-{state}-AL" if state in at_large else f"H-{state}-{int(number):02d}"


def cnn_races(chamber, at_large):
    out = {}
    for x in get(CNN.format("HG" if chamber == "house" else "SG")):
        # Senate specials are "2026-SP-OH"; "HQ" is a House special election, which we do not forecast.
        m = re.fullmatch(r"2026-(HG|SG|SP)-([A-Z]{2})(?:-(\d+))?", x["ecKey"])
        if not m:
            continue
        cands = [{"name": c["fullName"], "party": CNN_PARTY.get(c["candidatePartyCode"], "O"), "votes": c["voteNum"],
                  "incumbent": bool(c.get("isIncumbent"))} for c in x["candidates"]]
        won = next((c for c, raw in zip(cands, x["candidates"]) if raw.get("winner")), None)
        out[race_id(chamber, m.group(2), m.group(3), at_large)] = {
            "source": "CNN", "winner": won and won["party"], "winner_name": won and won["name"], "runoff": x["status"] == "V",
            "reporting": x["percentReporting"], "cands": cands, "time": x.get("voteTimestamp")}
    return out


def nyt_races(chamber, at_large):
    data = get(NYT.format(chamber))
    out, national = {}, None
    for r in data["races"]:
        unit = r["top_reporting_unit"] or {}
        meta = r["candidate_metadata"]
        cands = []
        for c in unit.get("candidates", []):
            m = meta[c["nyt_id"]]
            cands.append({"name": " ".join(x for x in (m["first_name"], m["last_name"]) if x), "party": NYT_PARTY.get(m["party"]["nyt_id"], "O"),
                          "votes": c["votes"]["total"], "incumbent": bool(m.get("incumbent"))})
        if r["nyt_id"].startswith("US-"):  # the national House vote
            national = {"dem": cands[0]["votes"], "rep": cands[1]["votes"], "total": unit["total_votes"], "share_counted": unit["eevp"]}
            continue
        won = r["outcome"]["won"]
        winner = meta[won[0]] if won else None
        rid = race_id(chamber, r["nyt_id"].split("-")[0], r["seat_number"] or 1, at_large)
        out[rid] = {"source": "NYT", "winner": winner and NYT_PARTY.get(winner["party"]["nyt_id"], "O"),
                    "winner_name": winner and " ".join(x for x in (winner["first_name"], winner["last_name"]) if x),
                    "runoff": r["race_call_status"] == "runoff", "reporting": unit.get("eevp"), "cands": cands, "time": r.get("updated_at")}
    control = data["partyControlData"]["results"][0]["offices"]["H" if chamber == "house" else "S"]["party_balance"]
    called_at = {k: v.get("controlled_at") for k, v in control.items() if v.get("winner")}
    return out, national, called_at


def merge(rid, recs):
    """One record per race from the sources that have it."""
    winners = {r["winner"] for r in recs if r["winner"]}
    best = max(recs, key=lambda r: sum(c["votes"] for c in r["cands"]))
    cands = sorted(best["cands"], key=lambda c: -c["votes"])
    total = sum(c["votes"] for c in cands)
    rep = next((c for c in cands if c["party"] == "R"), None)
    non_rep = next((c for c in cands if c["party"] != "R"), None)
    top_share = 100 * cands[0]["votes"] / total if total else 0
    state = rid.split("-")[1]
    one_party = len(cands) > 1 and total and len({c["party"] for c in cands}) == 1 and cands[0]["party"] != "O"
    status = "disputed" if len(winners) > 1 else "called" if winners or one_party else "counting"
    if status == "counting" and (any(r["runoff"] for r in recs) or (state in RUNOFF_STATES and total and top_share < 50)):
        status = "runoff"
    called = next((r for r in recs if r["winner"]), None)
    return {
        "status": status,
        "winner": (called["winner"] if called else cands[0]["party"]) if status == "called" else None,
        "winner_name": called["winner_name"] if status == "called" and called else None,
        "called_by": [r["source"] for r in recs if r["winner"]],
        "leader": cands[0]["party"] if status == "counting" and total else None,
        "leader_name": cands[0]["name"] if status == "counting" and total else None,
        # Non-Republican side minus Republican, in points of all votes; none without both sides.
        "margin": round(100 * (non_rep["votes"] - rep["votes"]) / total, 2) if total and rep and non_rep else None,
        "lead_votes": cands[0]["votes"] - cands[1]["votes"] if len(cands) > 1 else None,
        "reporting": round(best["reporting"] or 0),
        "top": [{"name": c["name"], "party": c["party"], "pct": round(100 * c["votes"] / total, 1) if total else None,
                 "incumbent": c["incumbent"]} for c in cands[:2]],
    }


def tally(races, ids):
    """Seats by party: called, and still counting with the party ahead."""
    out = {"called": {"D": 0, "R": 0, "O": 0}, "leading": {"D": 0, "R": 0, "O": 0}, "runoff": 0, "disputed": 0}
    for rid in ids:
        r = races.get(rid)
        if not r:
            continue
        if r["status"] == "called":
            out["called"][r["winner"]] += 1
        elif r["status"] == "counting":
            out["leading"][r["leader"] or "O"] += 1
        else:
            out[r["status"]] += 1
    out["not_called"] = len(ids) - sum(out["called"].values())
    return out


def main():
    seats = json.loads((APP / "seats.json").read_text(encoding="utf-8"))
    at_large = {h["state"] for h in seats["house"] if h["district"] == 0}
    ids = {"house": [h["id"] for h in seats["house"]], "senate": [s["id"] for s in seats["senate"]]}
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

    by_race, failed = {}, []
    national, control = old.get("national"), old.get("control", {})
    for chamber in ("house", "senate"):
        try:
            for rid, rec in cnn_races(chamber, at_large).items():
                by_race.setdefault(rid, []).append(rec)
        except Exception as e:  # one source down should not stop the update
            print(f"CNN {chamber}: skipped ({e})")
            failed.append(f"CNN {chamber}")
        try:
            recs, nat, called_at = nyt_races(chamber, at_large)
            for rid, rec in recs.items():
                by_race.setdefault(rid, []).append(rec)
            national = nat or national
            control[chamber] = called_at
        except Exception as e:
            print(f"NYT {chamber}: skipped ({e})")
            failed.append(f"NYT {chamber}")
    if len(failed) == 4:
        sys.exit("No source could be read; results.json stays as it is.")

    races = {rid: merge(rid, recs) for rid, recs in by_race.items() if rid in ids["house"] or rid in ids["senate"]}
    if failed:  # a call only one source had must not vanish while that source is down
        for rid, r in (old.get("races") or {}).items():
            if r["status"] == "called" and races.get(rid, {}).get("status") != "called":
                races[rid] = r
    missing = [rid for rid in ids["house"] + ids["senate"] if rid not in races]
    if missing:
        print("not in the feeds:", missing)
    disputed = [rid for rid, r in races.items() if r["status"] == "disputed"]
    if disputed:
        print("sources disagree:", disputed)

    if national:
        national["margin"] = round(100 * (national["dem"] - national["rep"]) / national["total"], 1)
    new = {"house": tally(races, ids["house"]), "senate": tally(races, ids["senate"]), "national": national, "control": control,
           "not_up": seats["chambers"]["senate"]["not_up"], "races": races,
           "sources": [{"name": "CNN election results", "url": "https://www.cnn.com/election/2026/results/house"},
                       {"name": "The New York Times (calls by the Associated Press)", "url": "https://www.nytimes.com/interactive/2026/11/03/us/elections/results-house.html"}]}
    if {k: v for k, v in old.items() if k != "updated"} == new:
        print("no change")
        return
    new["updated"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    OUT.write_text(json.dumps(new, indent=1, ensure_ascii=False), encoding="utf-8")
    h, s = new["house"], new["senate"]
    print(f"House: D {h['called']['D']} (+{h['leading']['D']} leading), R {h['called']['R']} (+{h['leading']['R']}), "
          f"other {h['called']['O']} (+{h['leading']['O']}), not called {h['not_called']}, runoff {h['runoff']}")
    print(f"Senate: D {s['called']['D']} (+{s['leading']['D']}), R {s['called']['R']} (+{s['leading']['R']}), not called {s['not_called']}")
    print("national House vote:", national)


if __name__ == "__main__":
    main()
