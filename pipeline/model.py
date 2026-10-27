"""Model v1: combine the inputs per race and simulate all races jointly.

Inputs per race (each as a margin for the non-Republican side, with its own error sd):
    polls          data/polls_races.csv          corrected poll average
    markets        data/markets_races.csv        volume-weighted Kalshi/Polymarket price, turned into a margin
    fundamentals   data/fundamentals_races.csv   lean on the 2026 lines + national environment + incumbency
Other forecasters' models are not inputs; they appear as benchmarks only (PROCESS.md, C8).

Combining is agnostic about source type: inverse-variance weights from each input's own
error in that race (C5). The simulation draws every race from shared national, regional
(Census division) and state errors plus its own error, so seat totals have realistic spread.

Writes app/data/forecast.json (the dashboard contract, see build_seats.py) and data/model_races.csv.

    python -I pipeline/model.py
"""

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
APP = ROOT / "app" / "data"

N_SIMS = 20_000
SEED = 2026
ROBUSTNESS_SEEDS = (1, 2, 3, 4)  # the same model re-run with other random draws
FLOOR_SD = 4.0  # inputs overlap (markets read polls), so a race is never more certain than this
# Error layers (C20). The national layer is the uncertainty of the national environment
# (sd from national_environment.json, 3 points) and hits every race in full. The rest of each
# race's variance is split between Census division, state and the race itself.
REST_SHARES = {"division": 0.25, "state": 0.25, "race": 0.50}
T_DF = 5  # fat tails for the national layer
# Markets and polls on one scale (C19): a market's error is that of a poll average with n_equiv
# polls, where $20k traded counts as 1 poll and $1M as 10 polls (log scale), capped at 10.
# The poll error formula and constants are those of fetch_polls.py.
POLL_BASE_ERROR, POLL_SAMPLING_ERROR = 4.5, 7.0
MARKET_VOL_ONE_POLL, MARKET_VOL_TEN_POLLS, MARKET_MAX_POLLS = 20_000, 1_000_000, 10
WIDE_SPREAD, WIDE_SPREAD_PENALTY = 0.05, 1.0

# Rating bands (C28): toss-up 45-55%, lean 55-65%, likely 65-95%, safe 95%+, for either party.
BANDS = [(0.95, "Safe D"), (0.65, "Likely D"), (0.55, "Lean D"), (0.45, "Toss-up"),
         (0.35, "Lean R"), (0.05, "Likely R"), (0.0, "Safe R")]
NORM = NormalDist()


def read(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def rating(p):
    return next(label for cut, label in BANDS if p >= cut)


# Races whose non-Republican side is set by hand. Alaska at-large: Bill Hill, nonpartisan and
# endorsed by Democrats; the contest instructions say his win does not count as a Democratic seat.
SIDE_OVERRIDES = {"H-AK-AL": ("I", "Bill Hill")}

# Every assumption the sensitivity analysis (sensitivity.py) varies. The defaults are model v1.
DEFAULT_CFG = {
    "inputs": ("polls", "market", "fundamentals"),
    "mult": {"polls": 1.0, "market": 1.0, "fundamentals": 1.0},  # extra factor on each input's precision
    "floor_sd": FLOOR_SD,
    "nat_sd": None,                                   # None: the national environment's own sd (3 points)
    "incumbency": 3.0,                                # as in fundamentals.py
    "fund_race_sd": {"house": 6.0, "senate": 9.0},    # as in fundamentals.py
    "poll_base": POLL_BASE_ERROR,
    "market_max_polls": MARKET_MAX_POLLS,
    "rest_shares": REST_SHARES,
}


def market_poll_equivalents(volume, max_polls=MARKET_MAX_POLLS):
    frac = (math.log10(max(volume, 1.0)) - math.log10(MARKET_VOL_ONE_POLL)) / (
        math.log10(MARKET_VOL_TEN_POLLS) - math.log10(MARKET_VOL_ONE_POLL))
    return min(max_polls, 10 ** frac)


def market_sd(volume, spread, max_polls=MARKET_MAX_POLLS, base=POLL_BASE_ERROR):
    sd = (base ** 2 + POLL_SAMPLING_ERROR ** 2 / market_poll_equivalents(volume, max_polls)) ** 0.5
    return sd + (WIDE_SPREAD_PENALTY if spread is not None and spread > WIDE_SPREAD else 0.0)


def market_consensus():
    by_race = defaultdict(list)
    for r in read("markets_races.csv"):
        if r["p_rep"]:
            by_race[r["race_id"]].append(r)
    out = {}
    for race, rs in by_race.items():
        vol = np.array([max(float(r["volume_usd"]), 1.0) for r in rs])
        w = vol / vol.sum()
        p_rep = float(np.dot(w, [float(r["p_rep"]) for r in rs]))
        p_dem = float(np.dot(w, [float(r["p_dem"]) for r in rs]))
        p_oth = float(np.dot(w, [float(r["p_other"]) for r in rs]))
        spreads = [float(r["max_spread"]) for r in rs if r["max_spread"]]
        # Name of the leading non-Republican candidate who is not a Democrat (Nebraska: Osborn).
        other = None
        for r in rs:
            for part in r["candidates"].split("; "):
                if " [O] " in part:
                    name, price = part.split(" [O] ")
                    if price != "None" and float(price) >= 0.05:
                        other = name.strip()
        out[race] = {"p_nonrep": 1 - p_rep, "p_dem": p_dem, "p_other": p_oth, "volume": float(vol.sum()),
                     "max_spread": max(spreads) if spreads else None, "other_name": other,
                     "venues": {r["venue"]: round(1 - float(r["p_rep"]), 4) for r in rs}}
    return out


def combine(inputs, floor_sd=FLOOR_SD, mult=None):
    """Inverse-variance combination of (margin, sd) inputs; returns mean, sd and weights."""
    mult = mult or {}
    prec = {k: mult.get(k, 1.0) / v["sd"] ** 2 for k, v in inputs.items()}
    total = sum(prec.values())
    mean = sum(prec[k] * v["margin"] for k, v in inputs.items()) / total
    sd = max(floor_sd, (1 / total) ** 0.5)
    return mean, sd, {k: round(p / total, 3) for k, p in prec.items()}


def load_data():
    seats = json.loads((APP / "seats.json").read_text(encoding="utf-8"))
    return {
        "seats": seats,
        "env": json.loads((DATA / "national_environment.json").read_text(encoding="utf-8")),
        "polls": {r["race_id"]: r for r in read("polls_races.csv")},
        "funda": {r["race_id"]: r for r in read("fundamentals_races.csv")},
        "mkts": market_consensus(),
        "division": {s["abbr"]: s["division"] for s in seats["states"]},
        "not_up_d": seats["chambers"]["senate"]["not_up"]["D"],
    }


def build_races(data, cfg=DEFAULT_CFG):
    """Every race with its inputs (margin, sd, p) and the combined mean, sd and weights under cfg."""
    seats, polls, funda, mkts = data["seats"], data["polls"], data["funda"], data["mkts"]
    env_sd = float(data["env"]["sd"])
    races = [dict(s, chamber="senate") for s in seats["senate"]] + [dict(h, chamber="house") for h in seats["house"]]
    for r in races:
        rid, inputs = r["id"], {}
        f = funda[rid]
        inc_old = float(f["incumbency_adj"])
        fm = (float(f["expected_margin"]) - inc_old + (math.copysign(cfg["incumbency"], inc_old) if inc_old else 0.0)
              + cfg.get("env_shift", 0.0))
        fsd = (env_sd ** 2 + cfg["fund_race_sd"][r["chamber"]] ** 2) ** 0.5
        inputs["fundamentals"] = {"margin": fm, "sd": fsd, "p": NORM.cdf(fm / fsd)}
        if rid in polls:
            p = polls[rid]
            psd = (cfg["poll_base"] ** 2 + POLL_SAMPLING_ERROR ** 2 / float(p["n_eff"])) ** 0.5
            pm = float(p["margin_nonrep"])
            inputs["polls"] = {"margin": pm, "sd": psd, "p": NORM.cdf(pm / psd),
                               "n_polls": int(p["n_polls"]), "n_polls_45d": int(p["n_polls_45d"]), "latest": p["latest_end"]}
        if rid in mkts:
            m = mkts[rid]
            sd = market_sd(m["volume"], m["max_spread"], cfg["market_max_polls"], cfg["poll_base"])
            pm = min(max(m["p_nonrep"], 0.005), 0.995)
            inputs["market"] = {"margin": sd * NORM.inv_cdf(pm), "sd": sd, "p": m["p_nonrep"], "volume": round(m["volume"]),
                                "poll_equivalents": round(market_poll_equivalents(m["volume"], cfg["market_max_polls"]), 1),
                                "venues": m["venues"]}
        # Inputs left out by cfg still show on the dashboard; a race with none left falls back to fundamentals.
        used = {k: v for k, v in inputs.items() if k in cfg["inputs"]} or {"fundamentals": inputs["fundamentals"]}
        mean, sd, weights = combine(used, cfg["floor_sd"], cfg["mult"])
        if cfg.get("equal"):  # sensitivity only: plain average of the inputs, same uncertainty
            mean = sum(v["margin"] for v in used.values()) / len(used)
            weights = {k: round(1 / len(used), 3) for k in used}
        # The non-Republican side is the Democrat unless markets favour an independent (NE, MT, ID),
        # or the race is set by hand (SIDE_OVERRIDES).
        side = "I" if rid in mkts and mkts[rid]["p_other"] > mkts[rid]["p_dem"] else "D"
        side_name = mkts[rid]["other_name"] if side == "I" and rid in mkts else None
        if rid in SIDE_OVERRIDES:
            side, side_name = SIDE_OVERRIDES[rid]
        r.update(mean=mean, sd=sd, weights=weights, inputs=inputs, side=side, side_name=side_name)
        ps = [v["p"] for v in inputs.values()]
        r["spread"] = max(ps) - min(ps)
    return races


def simulate(races, data, cfg, seed, n_sims=N_SIMS):
    """Correlated simulation: shared national error, then division, state and race errors."""
    division = data["division"]
    divs, states = sorted(set(division.values())), sorted(division)
    div_idx = np.array([divs.index(division[r["state"]]) for r in races])
    st_idx = np.array([states.index(r["state"]) for r in races])
    mu = np.array([r["mean"] for r in races])
    sd = np.array([r["sd"] for r in races])
    nat_sd = cfg["nat_sd"] if cfg["nat_sd"] is not None else float(data["env"]["sd"])
    shares = cfg["rest_shares"]
    # Only Democratic wins count as Democratic seats (contest rule: Alaska's Bill Hill does not).
    is_house = np.array([r["chamber"] == "house" and r["side"] == "D" for r in races])
    is_sen_d = np.array([r["chamber"] == "senate" and r["side"] == "D" for r in races])
    rng = np.random.default_rng(seed)
    z_nat = rng.standard_t(T_DF, n_sims) * math.sqrt((T_DF - 2) / T_DF)
    z_div = rng.standard_normal((n_sims, len(divs)))
    z_st = rng.standard_normal((n_sims, len(states)))
    z_race = rng.standard_normal((n_sims, len(races)))
    rest_sd = np.sqrt(np.maximum(sd ** 2 - nat_sd ** 2, 0.0))
    margins = (mu + nat_sd * z_nat[:, None]
               + rest_sd * (math.sqrt(shares["division"]) * z_div[:, div_idx]
                            + math.sqrt(shares["state"]) * z_st[:, st_idx]
                            + math.sqrt(shares["race"]) * z_race))
    wins = margins > 0
    return z_nat, margins, wins, wins[:, is_house].sum(axis=1), data["not_up_d"] + wins[:, is_sen_d].sum(axis=1)


def main():
    data = load_data()
    env, not_up_d = data["env"], data["not_up_d"]
    races = build_races(data)
    model_rows = []
    nat_sd = float(env["sd"])
    is_house = np.array([r["chamber"] == "house" and r["side"] == "D" for r in races])
    is_sen_d = np.array([r["chamber"] == "senate" and r["side"] == "D" for r in races])

    z_nat, margins, wins, house_d, senate_d = simulate(races, data, DEFAULT_CFG, SEED)
    house_ctrl, senate_ctrl = house_d >= 218, senate_d >= 51

    # Robustness (C25): simulation noise of the headline numbers, and the same run with other seeds.
    reruns = []
    for seed in ROBUSTNESS_SEEDS:
        _, _, _, h, s = simulate(races, data, DEFAULT_CFG, seed)
        reruns.append({"seed": seed, "p_house": round(float((h >= 218).mean()), 4), "p_senate": round(float((s >= 51).mean()), 4),
                       "house_median": int(np.median(h)), "senate_median": int(np.median(s))})
    p_h, p_s = float(house_ctrl.mean()), float(senate_ctrl.mean())
    robustness = {
        "n_sims": N_SIMS, "seed": SEED,
        "mc_se_house": round(math.sqrt(p_h * (1 - p_h) / N_SIMS), 4),
        "mc_se_senate": round(math.sqrt(p_s * (1 - p_s) / N_SIMS), 4),
        "reruns": reruns,
        "max_diff_house": round(max(abs(r["p_house"] - p_h) for r in reruns), 4),
        "max_diff_senate": round(max(abs(r["p_senate"] - p_s) for r in reruns), 4),
        "median_range_house": [min(r["house_median"] for r in reruns), max(r["house_median"] for r in reruns)],
        "median_range_senate": [min(r["senate_median"] for r in reruns), max(r["senate_median"] for r in reruns)],
    }

    def chamber(counts, ctrl):
        c = Counter(counts.tolist())
        q = np.percentile(counts, [2.5, 10, 50, 90, 97.5])
        return {"p_dem_control": round(float(ctrl.mean()), 4),
                "dem_seats": {"median": int(q[2]), "mean": round(float(counts.mean()), 1),
                              "ci80": [int(q[1]), int(q[3])], "ci95": [int(q[0]), int(q[4])]},
                "distribution": [{"seats": k, "p": v / N_SIMS} for k, v in sorted(c.items())]}

    def tipping(mask, needed):
        """Line the seats up from most to least Democratic in each simulation; the seat at position
        `needed` decides control. Returns the seats that most often hold that position, with shares."""
        idx = np.where(mask)[0]
        order = np.argsort(-margins[:, idx], axis=1)[:, needed - 1]
        return [{"race_id": races[idx[k]]["id"], "share": round(v / N_SIMS, 5)}
                for k, v in Counter(order.tolist()).most_common() if v / N_SIMS >= 0.0005]

    house = chamber(house_d, house_ctrl)
    house["tipping_shares"] = tipping(is_house, 218)
    house["tipping_point"] = house["tipping_shares"][0]["race_id"]
    senate = chamber(senate_d, senate_ctrl)
    senate["tipping_shares"] = tipping(is_sen_d, 51 - not_up_d)
    senate["tipping_point"] = senate["tipping_shares"][0]["race_id"]
    joint = {
        "dem_house_dem_senate": round(float((house_ctrl & senate_ctrl).mean()), 4),
        "dem_house_rep_senate": round(float((house_ctrl & ~senate_ctrl).mean()), 4),
        "rep_house_dem_senate": round(float((~house_ctrl & senate_ctrl).mean()), 4),
        "rep_house_rep_senate": round(float((~house_ctrl & ~senate_ctrl).mean()), 4),
    }

    # Scenarios: group simulations by the shared national error, in standard deviations.
    pts_per_sd = nat_sd
    scenarios = []
    for name, lo, hi in [("Big shared miss toward Republicans", -99, -1.5), ("Normal miss toward Republicans", -1.5, -0.5),
                         ("Polls and markets about right", -0.5, 0.5), ("Normal miss toward Democrats", 0.5, 1.5),
                         ("Big shared miss toward Democrats", 1.5, 99)]:
        sel = (z_nat >= lo) & (z_nat < hi)
        scenarios.append({"name": name, "p": round(float(sel.mean()), 4),
                          "p_dem_house": round(float(house_ctrl[sel].mean()), 4),
                          "p_dem_senate": round(float(senate_ctrl[sel].mean()), 4),
                          "house_median": int(np.median(house_d[sel])), "senate_median": int(np.median(senate_d[sel])),
                          "shift_points": [round(max(lo, -3) * pts_per_sd, 1), round(min(hi, 3) * pts_per_sd, 1)]})

    p_win = wins.mean(axis=0)
    q10, q90 = np.percentile(margins, [10, 90], axis=0)
    out_races = {}
    for i, r in enumerate(races):
        p = float(p_win[i])
        out_races[r["id"]] = {
            "p_dem": round(p, 4), "side": r["side"], "side_name": r["side_name"],
            "margin": {"mean": round(r["mean"], 1), "ci80": [round(float(q10[i]), 1), round(float(q90[i]), 1)]},
            "rating": rating(p),
            "agreement": "high" if r["spread"] < 0.10 else "medium" if r["spread"] < 0.25 else "low",
            "input_spread": round(r["spread"], 3),
            "weights": r["weights"],
            "inputs": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in r["inputs"].items()},
        }
        model_rows.append({"race_id": r["id"], "p_nonrep": round(p, 4), "side": r["side"], "mean_margin": round(r["mean"], 2),
                           "sd": round(r["sd"], 2), **{f"w_{k}": r["weights"].get(k, 0) for k in ("polls", "market", "fundamentals")},
                           **{f"p_{k}": r["inputs"][k]["p"] if k in r["inputs"] else "" for k in ("polls", "market", "fundamentals")}})

    forecast = json.loads((APP / "forecast.json").read_text(encoding="utf-8"))
    forecast.update({
        "meta": {"status": "live", "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                 "model_version": "v1", "n_sims": N_SIMS,
                 "note": "Polls, markets and fundamentals combined per race by inverse-variance weights; correlated simulation.",
                 "robustness": robustness, "inputs": input_summary(races, env),
                 # What the dashboard needs to re-run the House model in the browser (app/whatif.js).
                 "sim_params": {"nat_sd": nat_sd, "floor_sd": FLOOR_SD, "rest_shares": REST_SHARES, "t_df": T_DF,
                                "fund_sd_house": round(math.sqrt(nat_sd ** 2 + DEFAULT_CFG["fund_race_sd"]["house"] ** 2), 3)}},
        "house": house, "senate": senate, "joint": joint, "scenarios": scenarios, "races": out_races,
        "national": national_block(env),
        "contest": contest_block(house, out_races),
        "gaps": gap_block(out_races),
        "benchmarks": benchmarks(),
        "sources": SOURCES,
    })
    (APP / "forecast.json").write_text(json.dumps(forecast, indent=1), encoding="utf-8")
    with (DATA / "model_races.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(model_rows[0]))
        w.writeheader()
        w.writerows(model_rows)

    print(f"House: P(D) {house['p_dem_control']:.3f}, median {house['dem_seats']['median']}, 80% {house['dem_seats']['ci80']}, "
          f"95% {house['dem_seats']['ci95']}, tipping {house['tipping_point']}")
    print(f"Senate: P(D) {senate['p_dem_control']:.3f}, median {senate['dem_seats']['median']}, 80% {senate['dem_seats']['ci80']}, "
          f"tipping {senate['tipping_point']}")
    print("joint:", joint)
    for r in sorted((r for r in races if r["chamber"] == "senate"), key=lambda r: abs(p_win[races.index(r)] - 0.5))[:12]:
        i = races.index(r)
        print(f"  {r['id']:6} P {p_win[i]:.2f} margin {r['mean']:+5.1f} sd {r['sd']:.1f} weights {r['weights']}")


# HKS contest entry (README): House seats, P(majority) and five districts, due 7:00 AM ET on 3 Nov.
CONTEST_DISTRICTS = [("H-NC-01", "North Carolina 1st"), ("H-NC-11", "North Carolina 11th"), ("H-OH-07", "Ohio 7th"),
                     ("H-PA-08", "Pennsylvania 8th"), ("H-NY-17", "New York 17th")]


def contest_hints(r):
    """Automatic warnings for a contest district; the manual review adds its own notes."""
    inp, hints = r["inputs"], []
    if "polls" not in inp and "market" not in inp:
        hints.append("No polls and no market found: this number rests on fundamentals alone.")
    if "polls" in inp:
        if inp["polls"]["n_polls"] == 1:
            hints.append(f"Only one poll (fielded until {inp['polls']['latest']}).")
        elif inp["polls"]["n_polls_45d"] == 0:
            hints.append(f"No poll in the last 45 days; the latest ended {inp['polls']['latest']}.")
    if "polls" in inp and "market" in inp and abs(inp["polls"]["p"] - inp["market"]["p"]) >= 0.15:
        hints.append(f"Polls and markets differ by {abs(inp['polls']['p'] - inp['market']['p']) * 100:.0f} points.")
    if "market" in inp and abs(inp["fundamentals"]["p"] - inp["market"]["p"]) >= 0.25:
        hints.append(f"Fundamentals differ from the market by {abs(inp['fundamentals']['p'] - inp['market']['p']) * 100:.0f} points, "
                     "a sign of candidate effects the fundamentals cannot see.")
    if "market" in inp and inp["market"]["volume"] < 100_000:
        hints.append("Thin market (under $100k traded).")
    return hints


def contest_block(house, out_races):
    dist = house["distribution"]
    return {
        "deadline": "Tuesday 3 Nov 2026, 7:00 AM ET",
        "seats": {"answer": house["dem_seats"]["median"], "rule": "median", "mean": house["dem_seats"]["mean"],
                  "mode": max(dist, key=lambda d: d["p"])["seats"], "ci80": house["dem_seats"]["ci80"]},
        "p_majority": house["p_dem_control"],
        "districts": [{"race_id": rid, "name": name, "p": out_races[rid]["p_dem"], "hints": contest_hints(out_races[rid])}
                      for rid, name in CONTEST_DISTRICTS],
    }


def input_summary(races, env):
    """Counts the method section of the dashboard quotes, so the text stays true after each refresh."""
    polls = [r for r in read("polls_clean.csv") if r["race_id"] != "GENERIC"]
    generic = [r for r in read("polls_clean.csv") if r["race_id"] == "GENERIC"]
    markets = read("markets_races.csv")
    with_inputs = lambda kind, ch: sum(kind in r["inputs"] and r["chamber"] == ch for r in races)

    def mean_weights(ch, need_polls):
        rs = [r for r in races if r["chamber"] == ch and ("polls" in r["inputs"]) == need_polls and "market" in r["inputs"]]
        return {k: round(float(np.mean([r["weights"].get(k, 0) for r in rs])), 3) for k in ("polls", "market", "fundamentals")} if rs else None

    return {
        "weights_senate_polled": mean_weights("senate", True), "weights_house_polled": mean_weights("house", True),
        "weights_house_unpolled": mean_weights("house", False),
        "race_polls": len(polls), "generic_polls": len(generic),
        "latest_poll": max(r["end_date"] for r in polls),
        "senate_with_polls": with_inputs("polls", "senate"), "house_with_polls": with_inputs("polls", "house"),
        "senate_with_market": with_inputs("market", "senate"), "house_with_market": with_inputs("market", "house"),
        "market_volume_usd": round(sum(float(r["volume_usd"]) for r in markets)),
        "markets_fetched": markets[0]["fetched_utc"] if markets else None,
        "environment": env["mean"], "environment_sd": env["sd"],
    }


def national_block(env):
    return {
        "environment": env["mean"], "environment_sd": env["sd"],
        "pres_margin_2024": env["national_pres_margin_2024"],
        "components": [{k: c[k] for k in ("name", "mean", "sd", "weight", "detail")} for c in env["components"]],
        "signals": [
            {"name": "Expectation poll, Pew (28 Sep – 4 Oct, 5,062 adults)", "value": "House: 55% expect D, 40% R · Senate: 46% D, 48% R",
             "url": "https://www.pewresearch.org/short-reads/2026/10/15/majority-of-americans-expect-democrats-to-win-control-of-house-public-is-split-on-senate/"},
            {"name": "Expectation poll, Verasight (Sep 2026, ~1,000 adults)", "value": "D both 39% · D House/R Senate 22% · R both 27%",
             "url": "https://blogs.lse.ac.uk/usappblog/2026/10/23/citizen-forecasting-us-midterm-elections/"},
            {"name": "Special elections since 2025 (The Downballot, 104 races)", "value": "Democrats about 13 pts ahead of Harris 2024 margin",
             "url": "https://www.insideelections.com/news/article/special-elections-point-to-house-flip-in-november/ie17"},
        ],
    }


def gap_block(out_races):
    rows = []
    for g in read("gaps.csv"):
        if g["status"] == "ok":
            continue
        rows.append({"race_id": g["race_id"], "status": g["status"], "p_polls": float(g["p_polls"]),
                     "p_market": float(g["p_market"]), "p_model": out_races[g["race_id"]]["p_dem"],
                     "gap": float(g["gap"]), "n_polls_45d": int(g["n_polls_45d"]), "latest_poll": g["latest_poll"],
                     "hints": g["hints"]})
    return sorted(rows, key=lambda r: (not r["race_id"].startswith("S-"), -abs(r["gap"])))


def benchmarks():
    rows = []
    ctrl = defaultdict(dict)
    for c in read("markets_control.csv"):
        if c["outcome"].startswith("Democratic") and c["price"]:
            ctrl[c["venue"]][c["chamber"]] = float(c["price"])
            ctrl[c["venue"]]["as_of"] = c["fetched_utc"][:8]
    for venue, url in (("kalshi", "https://kalshi.com/category/elections/midterms"), ("polymarket", "https://polymarket.com")):
        if venue in ctrl:
            d = ctrl[venue]
            rows.append({"source": f"{venue.capitalize()} (market)", "url": url, "p_dem_house": d.get("house"),
                         "p_dem_senate": d.get("senate"), "as_of": f"{d['as_of'][:4]}-{d['as_of'][4:6]}-{d['as_of'][6:]}"})
    # Other models, as reported in the press; shown to learn from, never used as inputs.
    rows += [
        {"source": "Decision Desk HQ (model)", "url": "https://votes.decisiondeskhq.com/forecast/2026", "p_dem_house": 0.79, "p_dem_senate": 0.56, "as_of": "2026-10-25"},
        {"source": "Poliwave (model)", "url": "https://www.poliwave.com/us/fed/projection", "p_dem_house": 0.88, "p_dem_senate": 0.57, "as_of": "2026-10-25"},
        {"source": "Silver Bulletin (model, as reported)", "url": "https://www.natesilver.net/p/nate-silver-2026-midterm-election-polls-model", "p_dem_house": 0.93, "p_dem_senate": 0.75, "as_of": "Oct 12 / Oct 26"},
    ]
    return rows


# Shown on the dashboard, grouped by the role each source plays.
SOURCES = [
    {"group": "Data we use", "name": "VoteHub polls API", "url": "https://votehub.com/polls/",
     "role": "Senate, House and generic-ballot polls, CC BY 4.0"},
    {"group": "Data we use", "name": "Kalshi", "url": "https://kalshi.com/category/elections/midterms",
     "role": "Prices for each race and for the national House vote"},
    {"group": "Data we use", "name": "Polymarket", "url": "https://polymarket.com",
     "role": "Prices for each race and for chamber control"},
    {"group": "Data we use", "name": "The Downballot: 2024 presidential results by district", "url": "https://www.the-downballot.com/p/the-downballot-releases-presidential",
     "role": "Calculated on the district lines used in November 2026"},
    {"group": "Data we use", "name": "unitedstates/congress-legislators", "url": "https://unitedstates.github.io/congress-legislators/legislators-current.json",
     "role": "Current members of Congress, for Senate incumbents"},
    {"group": "National signals, cross-checks only", "name": "Pew Research Center: who Americans expect to win", "url": "https://www.pewresearch.org/short-reads/2026/10/15/majority-of-americans-expect-democrats-to-win-control-of-house-public-is-split-on-senate/",
     "role": "Expectation poll, 28 Sep – 4 Oct"},
    {"group": "National signals, cross-checks only", "name": "Citizen forecasting (Verasight, LSE USAPP)", "url": "https://blogs.lse.ac.uk/usappblog/2026/10/23/citizen-forecasting-us-midterm-elections/",
     "role": "Expectation poll, September 2026"},
    {"group": "National signals, cross-checks only", "name": "Inside Elections: special elections", "url": "https://www.insideelections.com/news/article/special-elections-point-to-house-flip-in-november/ie17",
     "role": "Democratic overperformance in special elections"},
    {"group": "For comparison, not used as data", "name": "Decision Desk HQ forecast", "url": "https://votes.decisiondeskhq.com/forecast/2026", "role": "Model"},
    {"group": "For comparison, not used as data", "name": "Silver Bulletin forecast", "url": "https://www.natesilver.net/p/nate-silver-2026-midterm-election-polls-model", "role": "Model"},
    {"group": "For comparison, not used as data", "name": "Poliwave projection", "url": "https://www.poliwave.com/us/fed/projection", "role": "Model"},
    {"group": "For comparison, not used as data", "name": "ElectIt (Ebanks, Katz, King)", "url": "https://gking.harvard.edu/electit/", "role": "Model, with scenario table"},
    {"group": "For comparison, not used as data", "name": "Cook Political Report ratings", "url": "https://www.cookpolitical.com/ratings", "role": "Expert ratings"},
    {"group": "Background reading", "name": "Galesic et al. (2018): asking about social circles", "url": "https://pac.org/wp-content/uploads/Galesic1803.pdf",
     "role": "Why neighbour questions can beat own-vote questions"},
    {"group": "Background reading", "name": "Silver Bulletin: what if the polls are wrong again?", "url": "https://www.natesilver.net/p/what-if-the-polls-are-wrong-again",
     "role": "Size, direction and structure of polling errors"},
    {"group": "Background reading", "name": "Sabato's Crystal Ball: polling accuracy in 2025", "url": "https://centerforpolitics.org/crystalball/polling-accuracy-in-the-2025-elections-virginia-new-jersey-and-new-york-city/",
     "role": "Democrats underestimated in Virginia and New Jersey"},
    {"group": "Background reading", "name": "G. Elliott Morris: recalled-vote weighting", "url": "https://www.gelliottmorris.com/p/2026-10-22-trump-voters-rewriting-2024-vote",
     "role": "How weighting to the 2024 vote can tilt 2026 polls"},
    {"group": "Background reading", "name": "Wikipedia: 2025–2026 redistricting", "url": "https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting",
     "role": "Which states vote on new maps"},
]


if __name__ == "__main__":
    main()
