"""Run the whole forecast pipeline, in order, with one command.

    python run_all.py            refresh data, rebuild the forecast and the dashboard data
    python run_all.py --full     also the sensitivity analysis (about 2 minutes more)

Steps: DDHQ import (only if the course workbook is present), seat list, market prices
(Kalshi, Polymarket), polls (VoteHub), poll-market gaps, fundamentals, model, bridge from
the course model. The House fundamentals come from data/ddhq_house_2026-10-22.csv.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPE = ROOT / "pipeline"
STEPS = ["build_seats.py", "fetch_markets.py", "fetch_polls.py", "gaps.py", "fundamentals.py", "model.py"]


def run(script):
    print(f"\n=== {script}")
    subprocess.run([sys.executable, "-I", str(PIPE / script)], cwd=ROOT, check=True)


def main():
    if (ROOT / "data" / "raw" / "course" / "assignment3_election2026.xlsx").exists():
        run("ddhq_import.py")  # otherwise the committed data/ddhq_house_2026-10-22.csv is used
    for script in STEPS:
        run(script)
    if "--full" in sys.argv:
        run("sensitivity.py")
    run("bridge.py")
    print("\nDone. Serve the dashboard with: python -m http.server 8770 --directory app")


if __name__ == "__main__":
    main()
