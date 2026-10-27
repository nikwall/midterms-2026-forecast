"""Import Decision Desk HQ's House district probabilities (22 Oct 2026) from the course workbook.

Since model v2 (option 4, PROCESS.md C49) these probabilities are the House fundamentals input:
the course's starting point, and better than our own uniform-swing fundamentals (bridge, C42).

Reads  data/raw/course/assignment3_election2026.xlsx   (course material, not in the repository)
Writes data/ddhq_house_2026-10-22.csv                   (state, district, race id, probability, rating, DDHQ's blend weights)

    python -I pipeline/ddhq_import.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "data" / "raw" / "course" / "assignment3_election2026.xlsx"
OUT = ROOT / "data" / "ddhq_house_2026-10-22.csv"
SEATS = ROOT / "app" / "data" / "seats.json"


def main():
    import openpyxl
    seats = json.loads(SEATS.read_text(encoding="utf-8"))
    at_large = {h["state"] for h in seats["house"] if h["district"] == 0}
    wb = openpyxl.load_workbook(WORKBOOK, data_only=True, read_only=True)
    rows = list(wb["DDHQ Data"].iter_rows(min_row=8, values_only=True))
    hdr = {h: i for i, h in enumerate(rows[0]) if h}
    out = []
    for r in rows[1:]:
        if not r or not r[0] or not isinstance(r[1], (int, float)):
            continue
        st, d = r[0], int(r[1])
        out.append({
            "race_id": f"H-{st}-AL" if st in at_large else f"H-{st}-{d:02d}", "state": st, "district": d,
            "p_dem": r[hdr["P(Democrat wins)"]], "rating": r[hdr["DDHQ rating"]],
            "w_polls": r[hdr["Weight: polls"]], "w_markets": r[hdr["Weight: markets"]], "w_fundamentals": r[hdr["Weight: fundamentals"]],
        })
    assert len(out) == 435, len(out)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{OUT.name}: {len(out)} districts, expected Democratic seats {sum(x['p_dem'] for x in out):.1f}")


if __name__ == "__main__":
    main()
