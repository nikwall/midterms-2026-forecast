"""Pull prediction-market prices for every 2026 House and Senate race.

Sources: Kalshi (public market-data API) and Polymarket (public gamma API).
Writes
    data/raw/kalshi_events_<stamp>.json      raw snapshot, for the record
    data/raw/polymarket_events_<stamp>.json  raw snapshot
    data/markets_races.csv                   one row per race and venue, D/R probabilities
    data/markets_control.csv                 chamber-control markets

Run from the tournament folder:
    python -I pipeline/fetch_markets.py
"""

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"
SEATS = ROOT / "app" / "data" / "seats.json"

KALSHI = "https://api.elections.kalshi.com/trade-api/v2/events"
POLYMARKET = "https://gamma-api.polymarket.com/events"
HEADERS = {"User-Agent": "api232-midterms-forecast/0.1 (course project)"}

# Kalshi tags each outcome with a party id; the rules text says the same in words.
KALSHI_PARTY = {
    "57fa2293-3102-463b-9087-68cd9f6da0a6": "D",
    "9244ed4c-9dfd-45cc-8211-996dc902f315": "R",
}
# A wide quote says little about the price; fall back to the last trade then.
MAX_SPREAD = 0.10


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


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------- race ids ----------

def load_names():
    seats = json.loads(SEATS.read_text(encoding="utf-8"))
    name_to_abbr = {s["name"].lower(): s["abbr"] for s in seats["states"]}
    ids = {s["id"] for s in seats["house"]} | {s["id"] for s in seats["senate"]}
    at_large = {s["state"] for s in seats["house"] if s["district"] == 0}
    return name_to_abbr, ids, at_large


def house_id(state, district, at_large):
    if state in at_large:
        return f"H-{state}-AL"
    return f"H-{state}-{int(district):02d}"


DISTRICT_RX = re.compile(r"\b([A-Z]{2})-(\d{1,2}|AL)\b")
HOUSE_WINNER_RX = re.compile(r"^([A-Z]{2})-(\d{1,2}|AL) House winner\?$")


# ---------- Kalshi ----------

def fetch_kalshi():
    events, cursor = [], ""
    while True:
        params = {"status": "open", "limit": 200, "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        page = get_json(KALSHI, params)
        events += page.get("events", [])
        cursor = page.get("cursor")
        if not cursor:
            return events
        time.sleep(0.15)


def kalshi_price(m):
    bid, ask, last = num(m.get("yes_bid_dollars")), num(m.get("yes_ask_dollars")), num(m.get("last_price_dollars"))
    if bid is not None and ask is not None and 0 < ask and ask - bid <= MAX_SPREAD:
        return (bid + ask) / 2, ask - bid
    return last, (ask - bid) if bid is not None and ask is not None else None


def kalshi_party(m):
    party = KALSHI_PARTY.get((m.get("custom_strike") or {}).get("political_party"))
    if party:
        return party
    rules = m.get("rules_primary") or ""
    if "Democratic" in rules:
        return "D"
    if "Republican" in rules:
        return "R"
    return "O"


def kalshi_rows(events, at_large, ids):
    rows, control = [], []
    for e in events:
        t, series = e["event_ticker"], e.get("series_ticker", "")
        if t in ("CONTROLH-2026", "CONTROLS-2026"):
            for m in e.get("markets", []):
                p, spread = kalshi_price(m)
                control.append({"venue": "kalshi", "chamber": "house" if t.startswith("CONTROLH") else "senate",
                                "outcome": m.get("yes_sub_title"), "price": p, "spread": spread,
                                "volume": num(m.get("volume_fp")), "volume_24h": num(m.get("volume_24h_fp"))})
            continue
        if not t.endswith("-26"):
            continue
        race = None
        sen = re.fullmatch(r"SENATE([A-Z]{2})S?-26", t)
        # House winner markets come under several series names (KXHOUSERACE, HOUSEVA1, KXHOUSENC11),
        # so they are recognised by their title, e.g. "NC-11 House winner?".
        house = HOUSE_WINNER_RX.match(e.get("title", ""))
        if sen and series.startswith("SENATE"):
            race = f"S-{sen.group(1)}"
        elif house:
            race = house_id(house.group(1), 0 if house.group(2) == "AL" else house.group(2), at_large)
        if race is None or race not in ids:
            continue
        rows.append(race_row("kalshi", race, t, e.get("title"), [
            {"party": kalshi_party(m), "name": m.get("yes_sub_title"), "price": kalshi_price(m)[0],
             "spread": kalshi_price(m)[1], "volume": num(m.get("volume_fp")) or 0.0,
             "volume_24h": num(m.get("volume_24h_fp")) or 0.0}
            for m in e.get("markets", [])
        ]))
    return rows, control


# ---------- Polymarket ----------

def fetch_polymarket():
    events = {}
    for tag in ("midterms", "senate", "house", "us-elections", "congress"):
        offset = 0
        while True:
            page = get_json(POLYMARKET, {"closed": "false", "limit": 500, "offset": offset, "tag_slug": tag})
            if not page:
                break
            new = [e for e in page if e["id"] not in events]
            for e in page:
                events[e["id"]] = e
            if not new or len(page) < 500:
                break
            offset += 500
            time.sleep(0.15)
    return list(events.values())


# Polymarket lists some candidates without a party tag (e.g. Alaska's top-four
# system). Exact labels only, checked by hand against the race.
POLY_PARTY_BY_NAME = {"Sen. Dan Sullivan": "R", "Mary Peltola": "D"}


def poly_party(label):
    label = (label or "").strip()
    if re.search(r"\(D\)|^Democrat", label):
        return "D"
    if re.search(r"\(R\)|^Republican", label):
        return "R"
    return POLY_PARTY_BY_NAME.get(label, "O")


def poly_rows(events, name_to_abbr, at_large, ids):
    rows, control = [], []
    for e in events:
        title = e.get("title", "")
        if e.get("slug") in ("which-party-will-win-the-house-in-2026", "which-party-will-win-the-senate-in-2026"):
            for m in e.get("markets", []):
                prices = json.loads(m.get("outcomePrices") or "[]")
                if not prices:
                    continue  # placeholder outcomes ("Party A", "Other") without a price
                control.append({"venue": "polymarket", "chamber": "house" if "house" in e["slug"] else "senate",
                                "outcome": m.get("groupItemTitle"), "price": num(prices[0]) if prices else None,
                                "spread": num(m.get("spread")), "volume": num(m.get("volume")),
                                "volume_24h": num(m.get("volume24hr"))})
            continue
        race = None
        sen = re.match(r"(.+?) Senate (Special )?Election Winner", title)
        if sen and sen.group(1).lower() in name_to_abbr:
            race = f"S-{name_to_abbr[sen.group(1).lower()]}"
        else:
            d = DISTRICT_RX.search(title)
            if d and "House" in title:
                race = house_id(d.group(1), 0 if d.group(2) == "AL" else d.group(2), at_large)
        if race is None or race not in ids:
            continue
        outcomes = []
        for m in e.get("markets", []):
            if m.get("closed"):
                continue
            prices = json.loads(m.get("outcomePrices") or "[]")
            bid, ask = num(m.get("bestBid")), num(m.get("bestAsk"))
            mid = (bid + ask) / 2 if bid is not None and ask and ask - bid <= MAX_SPREAD else (num(prices[0]) if prices else None)
            outcomes.append({"party": poly_party(m.get("groupItemTitle")), "name": m.get("groupItemTitle"),
                             "price": mid, "spread": (ask - bid) if bid is not None and ask else None,
                             "volume": num(m.get("volume")) or 0.0, "volume_24h": num(m.get("volume24hr")) or 0.0})
        rows.append(race_row("polymarket", race, e.get("slug"), title, outcomes))
    return rows, control


# ---------- shared ----------

def race_row(venue, race, ticker, title, outcomes):
    """Collapse candidate outcomes to party probabilities, normalised to sum to 1."""
    total = sum(o["price"] for o in outcomes if o["price"] is not None) or None
    by_party = {"D": 0.0, "R": 0.0, "O": 0.0}
    for o in outcomes:
        if o["price"] is not None:
            by_party[o["party"]] += o["price"]
    spreads = [o["spread"] for o in outcomes if o["spread"] is not None and o["party"] in ("D", "R")]
    return {
        "race_id": race, "venue": venue, "ticker": ticker, "title": title,
        "p_dem": round(by_party["D"] / total, 4) if total else None,
        "p_rep": round(by_party["R"] / total, 4) if total else None,
        "p_other": round(by_party["O"] / total, 4) if total else None,
        "overround": round(total, 4) if total else None,
        "max_spread": round(max(spreads), 4) if spreads else None,
        "volume_usd": round(sum(o["volume"] for o in outcomes), 2),
        "volume_24h_usd": round(sum(o["volume_24h"] for o in outcomes), 2),
        "candidates": "; ".join(f"{o['name']} [{o['party']}] {o['price']}" for o in outcomes),
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    RAW.mkdir(parents=True, exist_ok=True)
    name_to_abbr, ids, at_large = load_names()

    kalshi = fetch_kalshi()
    (RAW / f"kalshi_events_{stamp}.json").write_text(json.dumps(kalshi), encoding="utf-8")
    poly = fetch_polymarket()
    (RAW / f"polymarket_events_{stamp}.json").write_text(json.dumps(poly), encoding="utf-8")

    k_rows, k_ctrl = kalshi_rows(kalshi, at_large, ids)
    p_rows, p_ctrl = poly_rows(poly, name_to_abbr, at_large, ids)
    rows = sorted(k_rows + p_rows, key=lambda r: (r["race_id"], r["venue"], -r["volume_usd"]))
    for r in rows:
        r["fetched_utc"] = stamp
    control = [dict(c, fetched_utc=stamp) for c in k_ctrl + p_ctrl]
    write_csv(OUT / "markets_races.csv", rows)
    write_csv(OUT / "markets_control.csv", control)

    covered = {r["race_id"] for r in rows}
    senate = sorted(i for i in covered if i.startswith("S-"))
    house = [i for i in covered if i.startswith("H-")]
    print(f"Kalshi events: {len(kalshi)}, Polymarket events: {len(poly)}")
    print(f"race rows: {len(rows)} (Kalshi {len(k_rows)}, Polymarket {len(p_rows)})")
    print(f"races covered: Senate {len(senate)}/35, House {len(house)}/435")
    missing = sorted(i for i in ids if i.startswith("S-") and i not in covered)
    print("Senate races without a market:", ", ".join(missing) or "none")


if __name__ == "__main__":
    main()
