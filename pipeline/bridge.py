"""From the course's Part 3 model to our final model, one change at a time.

Starts from the assignment's setup (Decision Desk HQ district probabilities of 22 Oct) and
changes one thing per step until it reaches our final model (v2, option 4):

    A  Part 2: DDHQ probabilities, every district an independent coin flip
    B  Part 3: DDHQ probabilities, regional waves (Appendix B, Option 1), alpha = 0.4 as preset in the workbook
    C  our correlation (national ±3.6, division, state, race errors); Alaska's Bill Hill no longer a Democrat
    D  + prediction markets, weighted by information
    E  + polls = our final model (v2)
For reference:
    R1 final model, but with our own uniform-swing fundamentals instead of DDHQ
    R2 model v1 (own fundamentals, uncalibrated error sizes)

Needs data/ddhq_house_2026-10-22.csv (from pipeline/ddhq_import.py).
Writes data/bridge.csv, app/data/bridge.json and research/bridge_report.md.

    python -I pipeline/bridge.py
"""

import copy
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTEST = [rid for rid, _ in model.CONTEST_DISTRICTS]
CHECK = ["H-TX-15"]   # the assignment's check district (DDHQ: 45%)
ALPHA_COURSE = 0.4    # preset in the workbook's Part 3 tab


def coin_flips(house, p, division, alpha, seed, n=model.N_SIMS):
    """Parts 2 and 3 of the assignment: independent flips (alpha = 0) or regional waves (Option 1)."""
    rng = np.random.default_rng(seed)
    divs = sorted(set(division.values()))
    d_idx = np.array([divs.index(division[h["state"]]) for h in house])
    own = rng.random((n, len(house)))
    shared = rng.random((n, len(divs)))[:, d_idx]
    wave = (rng.random((n, len(divs))) < alpha)[:, d_idx]
    return np.where(wave, shared, own) < p


def summarise(name, what, wins, house_ids, counts_as_dem):
    seats = wins[:, counts_as_dem].sum(axis=1)
    col = {rid: i for i, rid in enumerate(house_ids)}
    q10, q50, q90 = np.percentile(seats, [10, 50, 90])
    return {"step": name, "change": what, "mean": round(float(seats.mean()), 1), "median": int(q50),
            "p10": int(q10), "p90": int(q90), "p_majority": round(float((seats >= 218).mean()), 3),
            **{rid: round(float(wins[:, col[rid]].mean()), 2) for rid in CONTEST + CHECK}}


def main():
    data = model.load_data()
    if not data["ddhq"]:
        sys.exit("DDHQ probabilities missing: run pipeline/ddhq_import.py (needs the course workbook).")
    house = data["seats"]["house"]
    ids = [h["id"] for h in house]
    p_dd = np.array([data["ddhq"][i] for i in ids])
    all_dem = np.ones(len(ids), dtype=bool)  # assignment Parts 2-3: Hill counted as a Democrat
    steps = [
        summarise("A", "Part 2: DDHQ probabilities, independent coin flips",
                  coin_flips(house, p_dd, data["division"], 0.0, model.SEED), ids, all_dem),
        summarise("B", f"Part 3: regional waves (Option 1), alpha = {ALPHA_COURSE}",
                  coin_flips(house, p_dd, data["division"], ALPHA_COURSE, model.SEED), ids, all_dem),
    ]

    def ours(d, cfg):
        rs = model.build_races(d, cfg)
        hidx = [i for i, r in enumerate(rs) if r["chamber"] == "house"]
        dem_side = np.array([rs[i]["side"] == "D" for i in hidx])
        _, _, wins, _, _ = model.simulate(rs, d, cfg, model.SEED)
        return wins[:, hidx], dem_side

    def cfg(**kw):
        c = copy.deepcopy(model.DEFAULT_CFG)
        c.update(kw)
        return c

    nat = float(data["env"]["sd"])
    for name, what, c in [
        ("C", f"Our correlation (national ±{nat:.1f}, division, state, race); Hill not a Democrat", cfg(inputs=("fundamentals",))),
        ("D", "+ prediction markets, weighted by information", cfg(inputs=("market", "fundamentals"))),
        ("E", "+ polls = our final model", cfg()),
        ("R1", "For reference: final model with our own uniform-swing fundamentals instead of DDHQ", cfg(house_fundamentals="ours")),
    ]:
        wins, dem_side = ours(data, c)
        steps.append(summarise(name, what, wins, ids, dem_side))
    v1_data = copy.deepcopy(data)
    v1_data["env"]["sd"] = 3.0  # v1's national environment uncertainty
    wins, dem_side = ours(v1_data, copy.deepcopy(model.V1_CFG))
    steps.append(summarise("R2", "For reference: model v1 (own fundamentals, error sizes before the backtest)", wins, ids, dem_side))

    with (ROOT / "data" / "bridge.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(steps[0]))
        w.writeheader()
        w.writerows(steps)
    dd_rows = list(csv.DictReader(model.DDHQ_FILE.open(encoding="utf-8")))
    comp = [r for r in dd_rows if 0.1 < float(r["p_dem"]) < 0.9]
    ddhq_weights = {k: round(float(np.mean([float(r[k]) for r in comp])), 3) for k in ("w_polls", "w_markets", "w_fundamentals")}
    (ROOT / "app" / "data" / "bridge.json").write_text(json.dumps({
        "steps": steps, "contest": CONTEST, "check": CHECK, "ddhq_sum_p": round(float(p_dd.sum()), 1),
        "ddhq_weights_competitive": ddhq_weights, "final_step": "E",
    }, indent=1), encoding="utf-8")

    cols = CONTEST + CHECK
    lines = ["# From the course's Part 3 model to our final model", "",
             "Each step changes one thing. Seats are Democratic seats over 20,000 simulations (same random draws in every step).", "",
             f"DDHQ's probabilities add up to {p_dd.sum():.1f} expected Democratic seats. In competitive races (10–90%) DDHQ's own blend weights are "
             f"polls {ddhq_weights['w_polls']:.0%}, markets {ddhq_weights['w_markets']:.0%}, fundamentals {ddhq_weights['w_fundamentals']:.0%}.", "",
             "| Step | Change | Mean | Median | 80% range | P(majority) | " + " | ".join(c.replace("H-", "") for c in cols) + " |",
             "|---|---|---|---|---|---|" + "---|" * len(cols)]
    for s in steps:
        lines.append(f"| {s['step']} | {s['change']} | {s['mean']} | {s['median']} | {s['p10']}–{s['p90']} | {s['p_majority']:.2f} | "
                     + " | ".join(f"{s[c]:.2f}" for c in cols) + " |")
    (ROOT / "research" / "bridge_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s in steps:
        print(s)


if __name__ == "__main__":
    main()
