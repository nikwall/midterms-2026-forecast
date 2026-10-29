"""Crowd forecasts beside our model: Metaculus, Manifold and PredictIt.

Shown on the dashboard for comparison, not used as inputs (PROCESS.md, C8 and C54): Metaculus
and Manifold are forecasting crowds that read the same polls and markets we do, and PredictIt's
district markets are capped at $850 per trader and often have no trades for days.

    PredictIt   public market-data API; the mid of the best bid and ask, only if the spread is 15 cents or less
    Manifold    public API (play money); the market probability
    Metaculus   community forecast, read by hand from metaculus.com/midterms-2026 (its API needs a login)

Writes data/crowds.json, which model.py adds to the dashboard.

    python -I pipeline/fetch_crowds.py
"""

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "crowds.json"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}
MAX_SPREAD = 0.15

# Read by hand on the date given; update before the final entry.
METACULUS = {"source": "Metaculus", "kind": "forecasting community", "url": "https://www.metaculus.com/midterms-2026/",
             "p_dem_house": 0.959, "p_dem_senate": 0.676, "dem_seats_median": 230, "as_of": "2026-10-29",
             "note": "median House seat advantage D+25, so about 230 Democratic seats"}

PREDICTIT_CONTROL = {"house": 8157, "senate": 8155}
PREDICTIT_REP_SEATS = 7589
PREDICTIT_DISTRICTS = {"H-NC-01": 8184, "H-NC-11": 8909, "H-OH-07": 8992, "H-PA-08": 8978, "H-NY-17": 8187}

MANIFOLD_HOUSE = "will-the-democrats-win-a-majority-i-ClQ6g6lntn"
MANIFOLD_SENATE = "will-democrats-or-republicans-win-a"
MANIFOLD_SEATS = "how-many-house-seats-will-the-democ"
MANIFOLD_DISTRICTS = ("will-a-democrat-win-these-us-house", {
    "H-NC-01": "North Carolina 1 ", "H-NC-11": "North Carolina 11", "H-OH-07": "Ohio 7", "H-PA-08": "Pennsylvania 8", "H-NY-17": "New York 17"})


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        return json.load(r)


def mid(contract):
    buy, sell = contract.get("bestBuyYesCost"), contract.get("bestSellYesCost")
    if buy is None or sell is None or buy - sell > MAX_SPREAD:
        return None
    return (buy + sell) / 2


def predictit():
    markets = {m["id"]: m for m in get("https://www.predictit.org/api/marketdata/all/")["markets"]}

    def dem_share(mid_id):
        m = markets.get(mid_id)
        if not m:
            return None
        d = next((mid(c) for c in m["contracts"] if c["name"].startswith("Dem")), None)
        r = next((mid(c) for c in m["contracts"] if c["name"].startswith(("Rep", "GOP"))), None)
        if d is None:
            return None
        return round(d / (d + r), 3) if r is not None else round(d, 3)

    seats = markets[PREDICTIT_REP_SEATS]["contracts"]
    # Republican seat buckets ("192 or fewer", "193 to 197", ...): median from the normalised mids.
    buckets = []
    for c in seats:
        p = mid(c) if mid(c) is not None else c["lastTradePrice"]
        nums = [int(x) for x in re.findall(r"\d+", c["name"])]
        lo = 0 if "fewer" in c["name"] else nums[0]
        hi = 435 if "more" in c["name"] else nums[-1]
        buckets.append((lo, hi, p or 0))
    buckets.sort()
    total, cum, median = sum(b[2] for b in buckets), 0.0, None
    for lo, hi, p in buckets:
        cum += p / total
        if cum >= 0.5:
            median = [435 - hi, 435 - lo]
            break
    row = {"source": "PredictIt", "kind": "real-money market, $850 cap", "url": "https://www.predictit.org/markets/5/Congress",
           "p_dem_house": dem_share(PREDICTIT_CONTROL["house"]), "p_dem_senate": dem_share(PREDICTIT_CONTROL["senate"]),
           "dem_seats_range": median, "as_of": datetime.now(timezone.utc).date().isoformat()}
    districts = {}
    for rid, mid_id in PREDICTIT_DISTRICTS.items():
        p = dem_share(mid_id)
        districts[rid] = {"source": "PredictIt", "p": p, "url": f"https://www.predictit.org/markets/detail/{mid_id}",
                          "note": None if p is not None else "no tight quote (spread over 15¢)"}
    return row, districts


def manifold():
    base = "https://api.manifold.markets/v0/slug/"
    house = get(base + MANIFOLD_HOUSE)
    senate = get(base + MANIFOLD_SENATE)
    p_sen = next((a["probability"] for a in senate.get("answers", []) if a["text"].lower().startswith("democrat")), None)
    seats = get(base + MANIFOLD_SEATS)
    # Answers are thresholds ("235+ (2018 result)"): the median is where P(at least X) crosses one half.
    pts = sorted((int(re.match(r"(\d+)\+", a["text"]).group(1)), a["probability"]) for a in seats["answers"] if re.match(r"\d+\+", a["text"]))
    median = None
    for (x0, p0), (x1, p1) in zip(pts, pts[1:]):
        if p0 >= 0.5 > p1:
            median = round(x0 + (p0 - 0.5) / (p0 - p1) * (x1 - x0))
    row = {"source": "Manifold", "kind": "play-money market", "url": house["url"], "p_dem_house": round(house["probability"], 3),
           "p_dem_senate": round(p_sen, 3) if p_sen is not None else None, "dem_seats_median": median,
           "bettors_house": house.get("uniqueBettorCount"), "as_of": datetime.now(timezone.utc).date().isoformat()}
    multi = get(base + MANIFOLD_DISTRICTS[0])
    districts = {}
    for rid, label in MANIFOLD_DISTRICTS[1].items():
        a = next((a for a in multi["answers"] if (a["text"] + " ").startswith(label)), None)
        if a:
            districts[rid] = {"source": "Manifold", "p": round(a["probability"], 3), "url": multi["url"],
                              "note": f"{multi.get('uniqueBettorCount')} traders in the market"}
    return row, districts


def main():
    out = {"fetched": datetime.now(timezone.utc).isoformat(timespec="minutes"), "control": [METACULUS], "districts": {}}
    for name, fn in (("PredictIt", predictit), ("Manifold", manifold)):
        try:
            row, districts = fn()
        except Exception as e:  # a crowd source that is down should not stop the forecast
            print(f"{name}: skipped ({e})")
            continue
        out["control"].append(row)
        for rid, d in districts.items():
            out["districts"].setdefault(rid, []).append(d)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in out["control"]:
        print(f"{r['source']}: House {r['p_dem_house']}, Senate {r['p_dem_senate']}, seats {r.get('dem_seats_median') or r.get('dem_seats_range')}")
    for rid, ds in out["districts"].items():
        print(rid, [(d["source"], d["p"]) for d in ds])


if __name__ == "__main__":
    main()
