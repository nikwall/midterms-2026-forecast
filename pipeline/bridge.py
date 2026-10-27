"""From the course's Part 3 model to ours, one change at a time.

Starts from the assignment's setup (Decision Desk HQ district probabilities of 22 Oct, from the
course workbook) and changes one thing per step until it reaches our model:

    A  Part 2: DDHQ probabilities, every district an independent coin flip
    B  Part 3: DDHQ probabilities, regional waves (Appendix B, Option 1), alpha = 0.4 as preset in the workbook
    C  DDHQ probabilities with our correlation (national, division, state and race errors);
       Alaska's Bill Hill no longer counts as a Democrat (contest rule)
    D  our fundamentals instead of DDHQ's probabilities
    E  + prediction markets, weighted by information
    F  + polls = our model
    G  alternative ("course path"): DDHQ in place of our fundamentals, + markets + polls

The course workbook is course material and is not part of the repository. Put it at
data/raw/course/assignment3_election2026.xlsx to run this script; without it the script stops.

Writes data/bridge.csv, app/data/bridge.json and research/bridge_report.md.

    python -I pipeline/bridge.py
"""

import copy
import csv
import json
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "data" / "raw" / "course" / "assignment3_election2026.xlsx"
N = NormalDist()
CONTEST = [rid for rid, _ in model.CONTEST_DISTRICTS]
CHECK = ["H-TX-15"]   # the assignment's check district (DDHQ: 45%)
ALPHA_COURSE = 0.4    # preset in the workbook's Part 3 tab
DDHQ_SD = 6.7         # margin scale used to place DDHQ's probabilities into our simulation (step C)


def ddhq(seats):
    import openpyxl
    wb = openpyxl.load_workbook(WORKBOOK, data_only=True, read_only=True)
    rows = list(wb["DDHQ Data"].iter_rows(min_row=8, values_only=True))
    hdr = {h: i for i, h in enumerate(rows[0]) if h}
    at_large = {h["state"] for h in seats["house"] if h["district"] == 0}
    out = {}
    for r in rows[1:]:
        if not r or not r[0] or not isinstance(r[1], (int, float)):
            continue
        st, d = r[0], int(r[1])
        rid = f"H-{st}-AL" if st in at_large else f"H-{st}-{d:02d}"
        out[rid] = {"p": float(r[hdr["P(Democrat wins)"]]), "rating": r[hdr["DDHQ rating"]],
                    "w_polls": r[hdr["Weight: polls"]], "w_markets": r[hdr["Weight: markets"]],
                    "w_fund": r[hdr["Weight: fundamentals"]]}
    assert len(out) == 435, len(out)
    return out


def coin_flips(house, p, division, alpha, seed, n=model.N_SIMS):
    """Parts 2 and 3 of the assignment: independent flips (alpha = 0) or regional waves (Option 1)."""
    rng = np.random.default_rng(seed)
    divs = sorted(set(division.values()))
    d_idx = np.array([divs.index(division[h["state"]]) for h in house])
    own = rng.random((n, len(house)))
    shared = rng.random((n, len(divs)))[:, d_idx]
    wave = (rng.random((n, len(divs))) < alpha)[:, d_idx]
    u = np.where(wave, shared, own)
    return u < p


def summarise(name, what, wins, house_ids, counts_as_dem):
    seats = wins[:, counts_as_dem].sum(axis=1)
    col = {rid: i for i, rid in enumerate(house_ids)}
    q10, q50, q90 = np.percentile(seats, [10, 50, 90])
    return {"step": name, "change": what, "mean": round(float(seats.mean()), 1), "median": int(q50),
            "p10": int(q10), "p90": int(q90), "p_majority": round(float((seats >= 218).mean()), 3),
            **{rid: round(float(wins[:, col[rid]].mean()), 2) for rid in CONTEST + CHECK}}


def main():
    if not WORKBOOK.exists():
        sys.exit(f"Course workbook not found at {WORKBOOK}. It is course material and not in the repository.")
    data = model.load_data()
    seats = data["seats"]
    house = seats["house"]
    ids = [h["id"] for h in house]
    division = data["division"]
    dd = ddhq(seats)
    p_dd = np.array([dd[i]["p"] for i in ids])
    all_dem = np.ones(len(ids), dtype=bool)  # assignment Parts 2-3: Hill counted as a Democrat
    steps = []

    steps.append(summarise("A", "Part 2: DDHQ probabilities, independent coin flips",
                           coin_flips(house, p_dd, division, 0.0, model.SEED), ids, all_dem))
    steps.append(summarise("B", f"Part 3: regional waves (Option 1), alpha = {ALPHA_COURSE}",
                           coin_flips(house, p_dd, division, ALPHA_COURSE, model.SEED), ids, all_dem))

    # C: DDHQ probabilities placed on a margin scale and run through our correlated simulation.
    races = model.build_races(data)
    hidx = [i for i, r in enumerate(races) if r["chamber"] == "house"]
    ddhq_races = copy.deepcopy(races)
    for r in ddhq_races:
        if r["chamber"] == "house":
            p = min(max(dd[r["id"]]["p"], 0.001), 0.999)
            r["mean"], r["sd"] = DDHQ_SD * N.inv_cdf(p), DDHQ_SD
    dem_side = np.array([races[i]["side"] == "D" for i in hidx])

    def ours(rs, cfg):
        _, _, wins, _, _ = model.simulate(rs, data, cfg, model.SEED)
        return wins[:, hidx]

    steps.append(summarise("C", "Our correlation (national ±3, division, state, race); Hill not a Democrat",
                           ours(ddhq_races, model.DEFAULT_CFG), ids, dem_side))
    for name, what, inputs in [("D", "Our fundamentals instead of DDHQ's probabilities", ("fundamentals",)),
                               ("E", "+ prediction markets, weighted by information", ("market", "fundamentals")),
                               ("F", "+ polls = our model", ("polls", "market", "fundamentals"))]:
        cfg = copy.deepcopy(model.DEFAULT_CFG)
        cfg["inputs"] = inputs
        steps.append(summarise(name, what, ours(model.build_races(data, cfg), cfg), ids, dem_side))

    # G (alternative, the "course path"): DDHQ takes the place of our fundamentals; markets and polls on top.
    alt = copy.deepcopy(data)
    for rid in ids:
        p = min(max(dd[rid]["p"], 0.001), 0.999)
        alt["funda"][rid] = dict(alt["funda"][rid], expected_margin=str(DDHQ_SD * N.inv_cdf(p)), incumbency_adj="0")
    steps.append(summarise("G", "Alternative: DDHQ in place of our fundamentals, + markets + polls",
                           ours(model.build_races(alt, model.DEFAULT_CFG), model.DEFAULT_CFG), ids, dem_side))

    with (ROOT / "data" / "bridge.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(steps[0]))
        w.writeheader()
        w.writerows(steps)
    comp = [i for i in ids if 0.1 < dd[i]["p"] < 0.9]
    ddhq_weights = {k: round(float(np.mean([dd[i][k] for i in comp])), 3) for k in ("w_polls", "w_markets", "w_fund")}
    # DDHQ district probabilities for the dashboard's fundamentals switch. Course material: kept
    # out of the repository (.gitignore) unless we decide to publish it.
    (ROOT / "app" / "data" / "ddhq.json").write_text(json.dumps({
        "source": "Decision Desk HQ, accessed 22 Oct 2026, via the API-232 course workbook",
        "p": {i: dd[i]["p"] for i in ids}}), encoding="utf-8")
    (ROOT / "app" / "data" / "bridge.json").write_text(json.dumps({
        "steps": steps, "contest": CONTEST, "check": CHECK, "ddhq_sum_p": round(float(p_dd.sum()), 1),
        "ddhq_weights_competitive": ddhq_weights, "ddhq_contest": {i: dd[i]["p"] for i in CONTEST + CHECK},
    }, indent=1), encoding="utf-8")

    cols = CONTEST + CHECK
    lines = ["# From the course's Part 3 model to ours", "",
             "Each step changes one thing. Seats are Democratic seats over 20,000 simulations (same random draws in every step).", "",
             f"DDHQ's probabilities add up to {p_dd.sum():.1f} expected Democratic seats. In competitive races (10–90%) DDHQ's own blend weights are "
             f"polls {ddhq_weights['w_polls']:.0%}, markets {ddhq_weights['w_markets']:.0%}, fundamentals {ddhq_weights['w_fund']:.0%}.", "",
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
