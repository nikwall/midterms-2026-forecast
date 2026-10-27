"""Why do the fundamentals disagree with polls and markets? And what happens to the contest
answers if we change how fundamentals enter?

Compares, for every House district with a market, the fundamentals' expected margin with the
margin the market price implies (on the fundamentals' own error scale). Then fits what the
markets implicitly assume: margin = a + b * (2024 presidential margin) + c * incumbency.
Finally re-runs the model with alternative treatments of fundamentals.

Writes research/fundamentals_diagnosis.md.

    python -I pipeline/diagnose_fundamentals.py
"""

import copy
import csv
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N = NormalDist()
CONTEST = [rid for rid, _ in model.CONTEST_DISTRICTS]
BINS = [(-99, -20), (-20, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 20), (20, 99)]


def main():
    data = model.load_data()
    races = model.build_races(data)
    funda = data["funda"]
    rows = []
    for r in races:
        if r["chamber"] != "house" or "market" not in r["inputs"]:
            continue
        f, m = r["inputs"]["fundamentals"], r["inputs"]["market"]
        if not 0.05 <= m["p"] <= 0.95:
            continue  # prices near 0 or 1 say little about the margin
        implied = f["sd"] * N.inv_cdf(m["p"])  # market price as a margin on the fundamentals' scale
        fr = funda[r["id"]]
        inc = float(fr["incumbency_adj"])
        rows.append({"id": r["id"], "pres": float(fr["pres_margin_2024"]), "inc": (inc > 0) - (inc < 0),
                     "fund": f["margin"], "market": implied, "diff": implied - f["margin"]})

    lines = ["# Diagnosis: fundamentals vs. markets in the House", "",
             f"Districts with a market priced between 5% and 95%: {len(rows)}. Market prices are turned into margins on the fundamentals' own error scale "
             f"(±{races[-1]['inputs']['fundamentals']['sd']:.1f} points), so the two can be compared in points.", "",
             "## Where the gap sits, by the district's 2024 presidential margin", "",
             "| 2024 presidential margin | Districts | Fundamentals (avg) | Market-implied (avg) | Market minus fundamentals |",
             "|---|---|---|---|---|"]
    for lo, hi in BINS:
        b = [x for x in rows if lo <= x["pres"] < hi]
        if not b:
            continue
        label = f"{'D' if lo >= 0 else 'R'}+{min(abs(lo), abs(hi))}–{max(abs(lo), abs(hi))}".replace("99", "∞")
        lines.append(f"| {label} | {len(b)} | {np.mean([x['fund'] for x in b]):+.1f} | {np.mean([x['market'] for x in b]):+.1f} | {np.mean([x['diff'] for x in b]):+.1f} |")
    lines += ["", "## By incumbency", "", "| Incumbent on the ballot | Districts | Market minus fundamentals |", "|---|---|---|"]
    for v, name in ((1, "Democrat"), (-1, "Republican"), (0, "none (open seat)")):
        b = [x for x in rows if x["inc"] == v]
        if b:
            lines.append(f"| {name} | {len(b)} | {np.mean([x['diff'] for x in b]):+.1f} |")

    # What do markets implicitly assume?  market margin = a + b * pres2024 + c * incumbency
    X = np.column_stack([np.ones(len(rows)), [x["pres"] for x in rows], [x["inc"] for x in rows]])
    y = np.array([x["market"] for x in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    env = float(data["env"]["mean"]) - float(data["env"]["national_pres_margin_2024"])
    lines += ["", "## What the markets implicitly assume", "",
              "Regression of the market-implied margin on the 2024 presidential margin and incumbency (+1 Democratic incumbent, −1 Republican, 0 open):", "",
              "| | Markets imply | Our fundamentals assume |", "|---|---|---|",
              f"| Swing in a district Trump won by 0 points (a) | {coef[0]:+.1f} | {env:+.1f} (national environment D+{float(data['env']['mean']):.1f} minus the national 2024 margin) |",
              f"| How much of the 2024 margin carries over (b) | {coef[1]:.2f} | 1.00 (uniform swing) |",
              f"| Incumbency bonus (c) | {coef[2]:+.1f} | ±3.0 |",
              f"| Scatter around the fit (sd) | {resid.std(ddof=3):.1f} | 6.7 |", "",
              "Reading: b < 1 means the swing toward Democrats is larger in Republican-leaning districts than uniform swing assumes; a negative c would mean incumbents gain less than we assume.", ""]

    # Contest answers under alternative treatments of fundamentals.
    def run(cfg):
        rs = model.build_races(data, cfg)
        _, _, wins, h, _ = model.simulate(rs, data, cfg, model.SEED)
        idx = {r["id"]: i for i, r in enumerate(rs)}
        return {"seats": int(np.median(h)), "p_maj": float((h >= 218).mean()),
                **{rid: float(wins[:, idx[rid]].mean()) for rid in CONTEST}}

    def cfg(**kw):
        c = copy.deepcopy(model.DEFAULT_CFG)
        c.update(kw)
        return c
    variants = [
        ("Model v1: polls + markets + fundamentals", cfg()),
        ("Fundamentals at half weight", cfg(mult={"polls": 1, "market": 1, "fundamentals": 0.5})),
        ("Fundamentals only where no poll and no market", cfg(inputs=("polls", "market"))),
    ]
    lines += ["## Contest answers under alternative treatments of fundamentals", "",
              "| Variant | Seats (median) | P(majority) | " + " | ".join(r.replace("H-", "") for r in CONTEST) + " |",
              "|---|---|---|" + "---|" * len(CONTEST)]
    for name, c in variants:
        res = run(c)
        lines.append(f"| {name} | {res['seats']} | {res['p_maj']:.2f} | " + " | ".join(f"{res[r]:.2f}" for r in CONTEST) + " |")
        print(name, res)
    (ROOT / "research" / "fundamentals_diagnosis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("regression a, b, c:", np.round(coef, 2), "resid sd", round(float(resid.std(ddof=3)), 2), "n", len(rows))


if __name__ == "__main__":
    main()
