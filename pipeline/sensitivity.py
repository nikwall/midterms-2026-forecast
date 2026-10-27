"""Sensitivity of the forecast to the model's assumptions.

Re-runs model v1 (model.py) with one assumption changed at a time and records the chance of a
Democratic House and Senate and the median seats. All variants use the same random draws
(common random numbers), so differences come from the assumption, not from simulation noise.

Writes data/sensitivity.csv and research/sensitivity_report.md.

    python -I pipeline/sensitivity.py
"""

import copy
import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
B = model.DEFAULT_CFG


def cfg(**changes):
    c = copy.deepcopy(B)
    for k, v in changes.items():
        c[k] = v
    return c


# (group, name, description, config)
VARIANTS = [
    ("Baseline", "Model v1", "Polls, markets and fundamentals, weighted by information", cfg()),
    ("Which sources", "Without markets", "Polls and fundamentals only", cfg(inputs=("polls", "fundamentals"))),
    ("Which sources", "Without polls", "Markets and fundamentals only", cfg(inputs=("market", "fundamentals"))),
    ("Which sources", "Without fundamentals", "Polls and markets only (fundamentals where neither exists)", cfg(inputs=("polls", "market"))),
    ("Which sources", "Polls alone", "Fundamentals only where a race has no polls", cfg(inputs=("polls",))),
    ("Which sources", "Markets alone", "Fundamentals only where a race has no market", cfg(inputs=("market",))),
    ("Which sources", "Fundamentals alone", "No polls, no markets", cfg(inputs=("fundamentals",))),
    ("How to weight", "Equal weights", "Plain average of the available inputs, ignoring information", cfg(equal=True)),
    ("How to weight", "Markets count double", "Market precision x2", cfg(mult={"polls": 1, "market": 2, "fundamentals": 1})),
    ("How to weight", "Polls count double", "Poll precision x2", cfg(mult={"polls": 2, "market": 1, "fundamentals": 1})),
    ("How to weight", "Markets worth at most 3 polls", "Cap of poll-equivalents 3 instead of 10", cfg(market_max_polls=3)),
    ("How to weight", "Markets worth up to 30 polls", "Cap of poll-equivalents 30 instead of 10", cfg(market_max_polls=30)),
    ("Uncertainty", "National error ±2", "Shared national error 2 points instead of 3", cfg(nat_sd=2.0)),
    ("Uncertainty", "National error ±4", "Shared national error 4 points instead of 3", cfg(nat_sd=4.0)),
    ("Uncertainty", "Race floor ±3", "No race more certain than ±3 instead of ±4", cfg(floor_sd=3.0)),
    ("Uncertainty", "Race floor ±5", "No race more certain than ±5 instead of ±4", cfg(floor_sd=5.0)),
    ("Uncertainty", "More regional correlation", "Rest split 40% division / 30% state / 30% race", cfg(rest_shares={"division": 0.4, "state": 0.3, "race": 0.3})),
    ("Uncertainty", "Less regional correlation", "Rest split 10% division / 20% state / 70% race", cfg(rest_shares={"division": 0.1, "state": 0.2, "race": 0.7})),
    ("Uncertainty", "Poll error floor 3.5", "Irreducible poll error 3.5 instead of 4.5", cfg(poll_base=3.5)),
    ("Uncertainty", "Poll error floor 5.5", "Irreducible poll error 5.5 instead of 4.5", cfg(poll_base=5.5)),
    ("Fundamentals", "Environment 2 pts more Republican", "National environment D+5.9 instead of D+7.9", cfg(env_shift=-2.0)),
    ("Fundamentals", "Environment 2 pts more Democratic", "National environment D+9.9 instead of D+7.9", cfg(env_shift=2.0)),
    ("Fundamentals", "No incumbency bonus", "0 instead of 3 points", cfg(incumbency=0.0)),
    ("Fundamentals", "Incumbency bonus 5", "5 instead of 3 points", cfg(incumbency=5.0)),
    ("Fundamentals", "Fundamentals 50% less certain", "Race error 9 (House) / 13.5 (Senate)", cfg(fund_race_sd={"house": 9.0, "senate": 13.5})),
]


def main():
    data = model.load_data()
    rows = []
    for group, name, desc, c in VARIANTS:
        races = model.build_races(data, c)
        _, _, _, h, s = model.simulate(races, data, c, model.SEED)
        rows.append({"group": group, "variant": name, "description": desc,
                     "p_dem_house": round(float((h >= 218).mean()), 4), "p_dem_senate": round(float((s >= 51).mean()), 4),
                     "house_median": int(np.median(h)), "senate_median": int(np.median(s)),
                     "house_ci80": f"{int(np.percentile(h, 10))}-{int(np.percentile(h, 90))}",
                     "senate_ci80": f"{int(np.percentile(s, 10))}-{int(np.percentile(s, 90))}"})
        print(f"{name:34} House {rows[-1]['p_dem_house']:.3f} ({rows[-1]['house_median']})  Senate {rows[-1]['p_dem_senate']:.3f} ({rows[-1]['senate_median']})")

    with (ROOT / "data" / "sensitivity.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    base = rows[0]
    lines = [
        "# Sensitivity of the forecast",
        "",
        f"Generated by `pipeline/sensitivity.py` on {date.today().isoformat()}.",
        "",
        "Each row changes one assumption of model v1 and keeps everything else. All rows use the same random draws, "
        "so the differences come from the assumption alone. Δ is the change in percentage points against the baseline.",
        "",
        "| Group | Variant | What changes | Dem House | Δ | Median House | Dem Senate | Δ | Median Senate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        dh = (r["p_dem_house"] - base["p_dem_house"]) * 100
        ds = (r["p_dem_senate"] - base["p_dem_senate"]) * 100
        lines.append(f"| {r['group']} | {r['variant']} | {r['description']} | {r['p_dem_house']:.1%} | {dh:+.1f} | {r['house_median']} | "
                     f"{r['p_dem_senate']:.1%} | {ds:+.1f} | {r['senate_median']} |")
    (ROOT / "research" / "sensitivity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
