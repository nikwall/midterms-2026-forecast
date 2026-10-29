"""Candidates and their photos for the House races the dashboard puts first.

Races: the five contest districts and the 30 districts that most often decide the majority
(tipping-point shares from app/data/forecast.json, so run model.py first). Names and parties come
from the Kalshi listing (data/markets_races.csv), incumbents from data/fundamentals_races.csv.
Photos are Wikipedia page images (mostly official portraits, public domain or free licences),
linked to their page; a candidate without a Wikipedia page gets initials on the dashboard.

Writes app/data/candidates.json.

    python -I pipeline/fetch_candidates.py
"""

import csv
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
APP = ROOT / "app" / "data"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project; https://github.com/nikwall/midterms-2026-forecast)"}
WIKI = "https://en.wikipedia.org/w/api.php"
N_TIPPING = 30
# A page counts as the candidate's only if its short description says what a candidate would be.
ROLE_WORDS = re.compile(r"politician|representative|congress|mayor|senator|legislat|official|candidate|commissioner", re.I)


STATE_NAMES = []  # filled from seats.json


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    return [t for t in re.sub(r"[^a-z ]", " ", s).split() if t not in ("jr", "sr", "ii", "iii")]


def wiki_photo(name, state):
    """The candidate's Wikipedia page and image. A page about a namesake is skipped: one whose
    qualifier names another state ("Tom Barrett (Wisconsin politician)") or who has died."""
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{name} {state} politician",
              "gsrlimit": 5, "prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": 160, "redirects": 1}
    req = urllib.request.Request(WIKI + "?" + urllib.parse.urlencode(params), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        pages = sorted(json.load(r).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    want = norm(name)
    for p in pages:
        title = norm(p["title"])
        same = title == want or (want and title and title[0] == want[0] and title[-1] == want[-1])
        qualifier = re.search(r"\(([^)]*)\)", p["title"])
        other_state = qualifier and any(s in qualifier.group(1) for s in STATE_NAMES if s != state)
        dead = re.search(r"\d{4}\s*[–-]\s*\d{4}", p.get("description", ""))
        if same and not other_state and not dead and ROLE_WORDS.search(p.get("description", "")):
            return {"wiki": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                    "photo": p.get("thumbnail", {}).get("source"), "description": p.get("description")}
    return {"wiki": None, "photo": None, "description": None}


def main():
    forecast = json.loads((APP / "forecast.json").read_text(encoding="utf-8"))
    seats = json.loads((APP / "seats.json").read_text(encoding="utf-8"))
    state_name = {s["abbr"]: s["name"] for s in seats["states"]}
    STATE_NAMES.extend(state_name.values())
    races = [d["race_id"] for d in forecast["contest"]["districts"]]
    for t in forecast["house"]["tipping_shares"][:N_TIPPING]:
        if t["race_id"] not in races:
            races.append(t["race_id"])
    listing = {}
    for r in csv.DictReader((DATA / "markets_races.csv").open(encoding="utf-8")):
        if r["venue"] == "kalshi" or r["race_id"] not in listing:
            listing[r["race_id"]] = r["candidates"]
    incumbents = {r["race_id"]: (r["incumbent"], r["incumbent_party"]) for r in csv.DictReader((DATA / "fundamentals_races.csv").open(encoding="utf-8"))}
    cache = {}
    old = APP / "candidates.json"
    if old.exists():  # keep earlier lookups; Wikipedia rarely changes within a week
        for race in json.loads(old.read_text(encoding="utf-8"))["races"].values():
            for c in race.values():
                cache[c["name"]] = {k: c.get(k) for k in ("wiki", "photo", "description")}

    out = {}
    for rid in races:
        best = {}
        for part in listing.get(rid, "").split("; "):
            m = re.match(r"(.+?) \[([DR])\] (\S+)", part)
            if not m or re.match(r"(Candidate|Person|Party) [A-Z]$", m.group(1)):
                continue
            price = float(m.group(3)) if m.group(3) != "None" else 0.0
            if price >= best.get(m.group(2), ("", -1))[1]:
                best[m.group(2)] = (m.group(1).strip(), price)
        inc_name, inc_party = incumbents.get(rid, ("", ""))
        race = {}
        for party, key in (("D", "dem"), ("R", "rep")):
            if party not in best:
                continue
            name = best[party][0]
            if name not in cache:
                cache[name] = wiki_photo(name, state_name[rid.split("-")[1]])
                time.sleep(0.2)
            race[key] = {"name": name, "party": party,
                         "incumbent": bool(inc_name) and inc_party == party and norm(inc_name)[-1:] == norm(name)[-1:],
                         **cache[name]}
        out[rid] = race
    (APP / "candidates.json").write_text(json.dumps({"source": "Kalshi listing; photos from Wikipedia", "races": out}, indent=1),
                                         encoding="utf-8")
    found = sum(bool(c.get("photo")) for r in out.values() for c in r.values())
    total = sum(len(r) for r in out.values())
    print(f"{len(out)} races, {total} candidates, {found} with a Wikipedia photo")
    for rid, r in out.items():
        print(rid, " vs ".join(f"{c['name']}{' (inc)' if c['incumbent'] else ''}{' [photo]' if c.get('photo') else ''}" for c in r.values()))


if __name__ == "__main__":
    main()
