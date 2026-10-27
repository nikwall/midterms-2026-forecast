"""Run the whole forecast pipeline, in order, with one command.

    python run_all.py            refresh data, rebuild the forecast and the dashboard data
    python run_all.py --full     also the sensitivity analysis (about 2 minutes more)

Steps: seat list, market prices (Kalshi, Polymarket), polls (VoteHub), poll-market gaps,
fundamentals, model. The bridge from the course model (pipeline/bridge.py) runs only if the
course workbook is present at data/raw/course/assignment3_election2026.xlsx; it is course
material and not part of the repository.
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
    for script in STEPS:
        run(script)
    if "--full" in sys.argv:
        run("sensitivity.py")
    if (ROOT / "data" / "raw" / "course" / "assignment3_election2026.xlsx").exists():
        run("bridge.py")
    else:
        print("\n=== bridge.py skipped: course workbook not found (app/data/bridge.json keeps its last version)")
    print("\nDone. Serve the dashboard with: python -m http.server 8770 --directory app")


if __name__ == "__main__":
    main()
