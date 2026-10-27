"""Build the static seat list for the dashboard and an empty forecast file.

Writes
    app/data/seats.json      every seat on the ballot on 3 Nov 2026 (435 House + 35 Senate)
    app/data/forecast.json   the forecast data contract with no numbers yet (only if missing)

Run from the tournament folder:
    python pipeline/build_seats.py
"""

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"

# abbr, name, House seats (2020 apportionment), tile column, tile row, Census division
STATES = [
    ("AK", "Alaska", 1, 0, 0, "Pacific"),
    ("ME", "Maine", 2, 10, 0, "New England"),
    ("WI", "Wisconsin", 8, 5, 1, "East North Central"),
    ("VT", "Vermont", 1, 9, 1, "New England"),
    ("NH", "New Hampshire", 2, 10, 1, "New England"),
    ("WA", "Washington", 10, 0, 2, "Pacific"),
    ("ID", "Idaho", 2, 1, 2, "Mountain"),
    ("MT", "Montana", 2, 2, 2, "Mountain"),
    ("ND", "North Dakota", 1, 3, 2, "West North Central"),
    ("MN", "Minnesota", 8, 4, 2, "West North Central"),
    ("IL", "Illinois", 17, 5, 2, "East North Central"),
    ("MI", "Michigan", 13, 6, 2, "East North Central"),
    ("NY", "New York", 26, 8, 2, "Middle Atlantic"),
    ("MA", "Massachusetts", 9, 9, 2, "New England"),
    ("OR", "Oregon", 6, 0, 3, "Pacific"),
    ("NV", "Nevada", 4, 1, 3, "Mountain"),
    ("WY", "Wyoming", 1, 2, 3, "Mountain"),
    ("SD", "South Dakota", 1, 3, 3, "West North Central"),
    ("IA", "Iowa", 4, 4, 3, "West North Central"),
    ("IN", "Indiana", 9, 5, 3, "East North Central"),
    ("OH", "Ohio", 15, 6, 3, "East North Central"),
    ("PA", "Pennsylvania", 17, 7, 3, "Middle Atlantic"),
    ("NJ", "New Jersey", 12, 8, 3, "Middle Atlantic"),
    ("CT", "Connecticut", 5, 9, 3, "New England"),
    ("RI", "Rhode Island", 2, 10, 3, "New England"),
    ("CA", "California", 52, 0, 4, "Pacific"),
    ("UT", "Utah", 4, 1, 4, "Mountain"),
    ("CO", "Colorado", 8, 2, 4, "Mountain"),
    ("NE", "Nebraska", 3, 3, 4, "West North Central"),
    ("MO", "Missouri", 8, 4, 4, "West North Central"),
    ("KY", "Kentucky", 6, 5, 4, "East South Central"),
    ("WV", "West Virginia", 2, 6, 4, "South Atlantic"),
    ("VA", "Virginia", 11, 7, 4, "South Atlantic"),
    ("MD", "Maryland", 8, 8, 4, "South Atlantic"),
    ("DE", "Delaware", 1, 9, 4, "South Atlantic"),
    ("AZ", "Arizona", 9, 1, 5, "Mountain"),
    ("NM", "New Mexico", 3, 2, 5, "Mountain"),
    ("KS", "Kansas", 4, 3, 5, "West North Central"),
    ("AR", "Arkansas", 4, 4, 5, "West South Central"),
    ("TN", "Tennessee", 9, 5, 5, "East South Central"),
    ("NC", "North Carolina", 14, 6, 5, "South Atlantic"),
    ("SC", "South Carolina", 7, 7, 5, "South Atlantic"),
    ("OK", "Oklahoma", 5, 3, 6, "West South Central"),
    ("LA", "Louisiana", 6, 4, 6, "West South Central"),
    ("MS", "Mississippi", 4, 5, 6, "East South Central"),
    ("AL", "Alabama", 7, 6, 6, "East South Central"),
    ("GA", "Georgia", 14, 7, 6, "South Atlantic"),
    ("HI", "Hawaii", 2, 0, 7, "Pacific"),
    ("TX", "Texas", 38, 3, 7, "West South Central"),
    ("FL", "Florida", 28, 8, 7, "South Atlantic"),
]

# Senate seats on the ballot: 33 Class II seats plus the OH and FL specials.
# Party of the current holder (D includes independents who caucus with Democrats).
SENATE = {
    "AK": "R", "AL": "R", "AR": "R", "CO": "D", "DE": "D", "FL": "R", "GA": "D",
    "IA": "R", "ID": "R", "IL": "D", "KS": "R", "KY": "R", "LA": "R", "MA": "D",
    "ME": "R", "MI": "D", "MN": "D", "MS": "R", "MT": "R", "NC": "R", "NE": "R",
    "NH": "D", "NJ": "D", "NM": "D", "OH": "R", "OK": "R", "OR": "D", "RI": "D",
    "SC": "R", "SD": "R", "TN": "R", "TX": "R", "VA": "D", "WV": "R", "WY": "R",
}
SENATE_SPECIAL = {"FL", "OH"}

# States voting on new congressional lines in 2026 (see research/landscape.md).
NEW_MAP_2026 = {"AL", "CA", "FL", "LA", "NC", "OH", "TN", "TX", "UT"}

CHAMBERS = {
    "house": {"seats": 435, "majority": 218, "not_up": {"D": 0, "R": 0}},
    # 47 D-caucus and 53 R seats today; 13 D and 22 R seats are on the ballot.
    # Democrats need 51 because Vice President Vance breaks ties for Republicans.
    "senate": {"seats": 100, "majority": 51, "not_up": {"D": 34, "R": 31}},
}


def build_seats():
    states, house, senate = [], [], []
    for abbr, name, n_house, col, row, division in STATES:
        states.append({
            "abbr": abbr, "name": name, "col": col, "row": row,
            "division": division, "house_seats": n_house,
            "senate_race": abbr in SENATE, "new_map_2026": abbr in NEW_MAP_2026,
        })
        for d in range(1, n_house + 1):
            label = f"{abbr}-AL" if n_house == 1 else f"{abbr}-{d:02d}"
            house.append({
                "id": f"H-{label}", "label": label, "state": abbr,
                "district": 0 if n_house == 1 else d, "new_map_2026": abbr in NEW_MAP_2026,
            })
        if abbr in SENATE:
            senate.append({
                "id": f"S-{abbr}", "label": f"{abbr} Senate" + (" (special)" if abbr in SENATE_SPECIAL else ""),
                "state": abbr, "holder": SENATE[abbr], "special": abbr in SENATE_SPECIAL,
            })

    assert len(states) == 50
    assert len(house) == 435, len(house)
    assert len(senate) == 35, len(senate)
    holders = [s["holder"] for s in senate]
    assert holders.count("D") == 13 and holders.count("R") == 22
    return {
        "generated": date.today().isoformat(),
        "election_day": "2026-11-03",
        "chambers": CHAMBERS,
        "states": states,
        "senate": senate,
        "house": house,
    }


def empty_forecast():
    """The data contract the dashboard reads. Every number is null until the model runs."""
    seats = {"median": None, "mean": None, "ci80": None, "ci95": None}
    chamber = {"p_dem_control": None, "dem_seats": dict(seats), "distribution": [], "tipping_point": None}
    return {
        "meta": {
            "status": "pending",  # pending | demo | live
            "updated": None,
            "model_version": None,
            "n_sims": None,
            "note": "No forecast yet. The model is pending agreement (see MODEL_PROPOSAL.md).",
        },
        "house": chamber,
        "senate": json.loads(json.dumps(chamber)),
        "joint": {"dem_house_dem_senate": None, "dem_house_rep_senate": None,
                  "rep_house_dem_senate": None, "rep_house_rep_senate": None},
        "scenarios": [],
        # race id -> {"p_dem", "margin": {"mean", "ci80"}, "rating", "agreement", "inputs": {...}}
        "races": {},
        # other forecasters: {"source", "url", "p_dem_house", "p_dem_senate", "as_of"}
        "benchmarks": [],
        "sources": PLANNED_SOURCES,
    }


PLANNED_SOURCES = [
    {"name": "Kalshi", "url": "https://kalshi.com/category/elections/midterms",
     "level": "seat", "role": "prediction market prices", "status": "planned"},
    {"name": "Polymarket", "url": "https://polymarket.com",
     "level": "seat", "role": "prediction market prices", "status": "planned"},
    {"name": "ElectIt (Ebanks, Katz, King)", "url": "https://gking.harvard.edu/electit/",
     "level": "seat", "role": "statistical model, all seats", "status": "planned"},
    {"name": "Expert ratings via 270toWin", "url": "https://270towin.com/2026-house-election/table/consensus-2026-house-forecast",
     "level": "seat", "role": "Cook, Sabato, Inside Elections ratings", "status": "planned"},
    {"name": "FiftyPlusOne poll files", "url": "https://fiftyplusone.news/readme",
     "level": "seat", "role": "Senate and House polls, generic ballot", "status": "planned"},
    {"name": "District lean on 2026 lines", "url": "https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting",
     "level": "seat", "role": "2024 presidential margin per district", "status": "planned"},
    {"name": "Decision Desk HQ", "url": "https://votes.decisiondeskhq.com/forecast/2026",
     "level": "national", "role": "benchmark forecast", "status": "planned"},
    {"name": "Silver Bulletin", "url": "https://www.natesilver.net/p/nate-silver-2026-midterm-election-polls-model",
     "level": "national", "role": "benchmark forecast", "status": "planned"},
]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    seats = build_seats()
    (DATA / "seats.json").write_text(json.dumps(seats, indent=1), encoding="utf-8")
    print(f"seats.json: {len(seats['house'])} House + {len(seats['senate'])} Senate seats")

    forecast_path = DATA / "forecast.json"
    if forecast_path.exists():
        print("forecast.json exists, left unchanged")
    else:
        forecast_path.write_text(json.dumps(empty_forecast(), indent=1), encoding="utf-8")
        print("forecast.json: empty contract written")


if __name__ == "__main__":
    main()
