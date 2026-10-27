"""Pull 2026 House, Senate and generic-ballot polls and build race averages (v1).

Source: VoteHub polls API (public, no key; data shared under CC BY 4.0).
Candidate parties come from the market data (Kalshi tags every candidate with a
party), so run fetch_markets.py first.

Writes
    data/raw/votehub_polls_<stamp>.json   raw snapshot
    data/polls_clean.csv                  one row per poll, mapped to a race, with weights
    data/polls_races.csv                  weighted average per race (and the generic ballot)
    data/polls_unmatched.csv              poll answers whose party could not be identified

v1 corrections (see research/polling_corrections.md; house effects and the
LV/RV shift follow in v2):
    recency     weight halves every 14 days since the poll ended
    sample      weight grows with sqrt(n), capped at 2,400 respondents
    population  likely voters 1.0, registered voters 0.8, adults 0.6
    sponsor     partisan or internal polls 0.5
    repeats     each pollster's older polls in a race count half as much as its newer one

    python -I pipeline/fetch_polls.py
"""

import csv
import json
import math
import re
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"
SEATS = ROOT / "app" / "data" / "seats.json"
MARKETS = OUT / "markets_races.csv"

VOTEHUB = "https://api.votehub.com/polls"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}

CYCLE_START = "2026-01-01"
HALF_LIFE_DAYS = 14
POPULATION_WEIGHT = {"lv": 1.0, "rv": 0.8, "v": 0.8, "a": 0.6}
PARTISAN_WEIGHT = 0.5
# Poll-implied probability: race margin error = irreducible part + part that shrinks with more polls.
BASE_ERROR = 4.5      # points of margin, systematic + race-level error of final midterm polls (provisional)
SAMPLING_ERROR = 7.0  # points of margin for a single poll; divided by sqrt(effective number of polls)


def norm_name(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\((d|r|i)\)|\b(sen|rep|gov|dr|jr|sr|iii|ii)\b\.?", " ", s)
    return re.sub(r"[^a-z ]", " ", s).split()


def candidate_parties():
    """race id -> list of (name tokens, party) from the market snapshot."""
    out = defaultdict(list)
    for r in csv.DictReader(MARKETS.open(encoding="utf-8")):
        for part in r["candidates"].split("; "):
            m = re.match(r"(.+?) \[([DRO])\] ", part + " ")
            if m and not re.match(r"(Candidate|Person|Party) [A-Z]$|Other$", m.group(1)):
                out[r["race_id"]].append((norm_name(m.group(1)), m.group(2)))
    return out


# Candidates no market lists by name, checked by hand. Alaska: Bill Hill is a nonpartisan
# independent endorsed by Democrats; the contest does not count him as a Democrat.
MANUAL_PARTY = {"H-AK-AL": {"hill": "O", "begich": "R"}}


def party_of(choice, race, cands):
    manual = MANUAL_PARTY.get(race, {})
    tokens0 = norm_name(choice)
    if tokens0 and tokens0[-1] in manual:
        return manual[tokens0[-1]]
    # Party labels first: norm_name strips "Rep." as a title.
    word = (choice or "").strip().lower()
    if word in ("dem", "democrat", "democratic", "democrats"):
        return "D"
    if word in ("rep", "republican", "republicans", "gop"):
        return "R"
    tokens = norm_name(choice)
    if not tokens:
        return None
    exact = {p for t, p in cands.get(race, []) if t == tokens}
    if len(exact) == 1:
        return exact.pop()
    last = {p for t, p in cands.get(race, []) if t and t[-1] == tokens[-1]}
    return last.pop() if len(last) == 1 else None


def race_id(poll, name_to_abbr, at_large):
    subject = (poll.get("subject") or "").replace("2026 ", "", 1).strip()
    if poll["poll_type"] == "us-senator":
        abbr = name_to_abbr.get(subject.lower())
        return f"S-{abbr}" if abbr else None
    if poll["poll_type"] == "us-representative":
        m = re.fullmatch(r"([A-Z]{2})-(\d{1,2}|AL)", poll.get("seat_name") or subject)
        if not m:
            return None
        st = m.group(1)
        return f"H-{st}-AL" if st in at_large else f"H-{st}-{int(m.group(2)):02d}"
    if poll["poll_type"] == "generic-ballot":
        return "GENERIC"
    return None


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    today = date.today()
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(VOTEHUB, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        polls = json.load(r)
    (RAW / f"votehub_polls_{stamp}.json").write_text(json.dumps(polls), encoding="utf-8")

    seats = json.loads(SEATS.read_text(encoding="utf-8"))
    name_to_abbr = {s["name"].lower(): s["abbr"] for s in seats["states"]}
    at_large = {h["state"] for h in seats["house"] if h["district"] == 0}
    valid = {s["id"] for s in seats["senate"] + seats["house"]} | {"GENERIC"}
    cands = candidate_parties()

    clean, unmatched = [], []
    for p in polls:
        race = race_id(p, name_to_abbr, at_large)
        if race not in valid or p["end_date"] < CYCLE_START:
            continue
        shares = defaultdict(float)
        named = []
        for a in p["answers"]:
            party = party_of(a["choice"], race, cands)
            if party is None:
                unmatched.append({"race_id": race, "poll_id": p["id"], "choice": a["choice"], "pct": a["pct"]})
                party = "?"
            named.append(f"{a['choice']} [{party}] {a['pct']}")
            if party in ("D", "R"):
                shares[party] += a["pct"]
            elif party == "O":
                shares["O"] = max(shares["O"], a["pct"])
        # Keep only polls of the actual matchup: both sides must be candidates the markets list
        # today. This drops hypothetical pairings with people who lost their primary. Unmatched
        # answers ("?") are minor candidates or non-nominees and stay out of the margin.
        if "R" not in shares or ("D" not in shares and "O" not in shares):
            continue
        # The non-Republican side is the Democrat, or the strongest other candidate where no
        # Democrat is competitive (Nebraska: independent Dan Osborn).
        non_r = max(shares.get("D", 0.0), shares.get("O", 0.0))
        age = (today - date.fromisoformat(p["end_date"])).days
        weight = (0.5 ** (age / HALF_LIFE_DAYS)
                  * math.sqrt(min(p.get("sample_size") or 600, 2400) / 600)
                  * POPULATION_WEIGHT.get(p.get("population"), 0.6)
                  * (PARTISAN_WEIGHT if p.get("partisan") or p.get("internal") else 1.0))
        clean.append({
            "race_id": race, "poll_id": p["id"], "pollster": p["pollster"], "sponsors": "; ".join(p.get("sponsors") or []),
            "partisan": p.get("partisan") or "", "internal": p.get("internal"), "population": p.get("population"),
            "sample_size": p.get("sample_size"), "start_date": p["start_date"], "end_date": p["end_date"], "age_days": age,
            "dem_pct": shares.get("D"), "rep_pct": shares["R"], "nonrep_pct": non_r,
            "margin_nonrep": round(non_r - shares["R"], 2), "weight": weight, "answers": "; ".join(named), "url": p.get("url"),
        })

    # Older polls by the same pollster in the same race count half as much each step back.
    by_key = defaultdict(list)
    for row in clean:
        by_key[(row["race_id"], row["pollster"])].append(row)
    for rows in by_key.values():
        rows.sort(key=lambda r: r["end_date"], reverse=True)
        for k, row in enumerate(rows):
            row["weight"] = round(row["weight"] * 0.5 ** k, 5)

    races = []
    by_race = defaultdict(list)
    for row in clean:
        by_race[row["race_id"]].append(row)
    for race, rows in sorted(by_race.items()):
        w = sum(r["weight"] for r in rows)
        if w <= 0:
            continue
        avg = sum(r["weight"] * r["margin_nonrep"] for r in rows) / w
        n_eff = w ** 2 / sum(r["weight"] ** 2 for r in rows)  # Kish effective number of polls
        recent = [r for r in rows if r["age_days"] <= 45]
        sd = math.sqrt(BASE_ERROR ** 2 + SAMPLING_ERROR ** 2 / max(n_eff, 1e-9))
        p_nonrep = 0.5 * (1 + math.erf(avg / (sd * math.sqrt(2))))
        races.append({
            "race_id": race, "margin_nonrep": round(avg, 2), "sd": round(sd, 2), "p_nonrep": round(p_nonrep, 4),
            "n_polls": len(rows), "n_polls_45d": len(recent), "n_pollsters": len({r["pollster"] for r in rows}),
            "n_eff": round(n_eff, 2), "total_weight": round(w, 4), "latest_end": max(r["end_date"] for r in rows),
            "share_partisan_weight": round(sum(r["weight"] for r in rows if r["partisan"] or r["internal"]) / w, 3),
        })

    def write(path, rows):
        with path.open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)

    write(OUT / "polls_clean.csv", sorted(clean, key=lambda r: (r["race_id"], r["end_date"]), reverse=False))
    write(OUT / "polls_races.csv", races)
    if unmatched:
        write(OUT / "polls_unmatched.csv", unmatched)
    senate = [r for r in races if r["race_id"].startswith("S-")]
    house = [r for r in races if r["race_id"].startswith("H-")]
    generic = next((r for r in races if r["race_id"] == "GENERIC"), None)
    print(f"VoteHub polls: {len(polls)}; usable 2026 race polls: {len(clean)}")
    print(f"races with polls: Senate {len(senate)}/35, House {len(house)}/435")
    if generic:
        print(f"generic ballot (weighted): D margin {generic['margin_nonrep']:+.1f} from {generic['n_polls']} polls")
    print(f"answers without an identified party: {len(unmatched)} (see data/polls_unmatched.csv)")


if __name__ == "__main__":
    main()
