"""Score the frozen forecast against the results: calibration, regions, contest answers.

Predictions are the contest entry of 2 Nov (Git tag contest-entry): app/data/forecast.json and
data/model_races.csv. They must never be refreshed after the election, because market prices now
contain the results, so the script stops if forecast.json is not that version.
Results come from app/data/results.json (fetch_results.py).

The outcome of a race is "the non-Republican side won", which is what every probability in the
forecast refers to (the Democrat, or the independent in AK-AL, NE, MT, ID, SD).

What it computes, for all races / House / Senate and for called races / called plus current leaders:
    brackets    races grouped by our chance, against the share the non-Republican side won.
                band: the 5th to 95th percentile of that share across our own 20,000 simulations.
                Races are not independent, so this is much wider than a coin-flip interval: one
                shared national error moves every bracket the same way.
                wave: the same share in the simulations whose total comes closest to the actual
                total. If the dots sit on this line, the miss is the size of the wave and not the
                ordering of the races.
    favourites  where we favoured each party: the chance we gave against how often they won
    regions     the same by Census region, with coarser brackets
    divisions   how far actual margins ended above our expected margin, in non-safe races
    series      the same brackets and Brier scores for each source alone, and for the best mixes
    mix         what the best mix of the sources looks like, and how each fit holds up

The sources, as they stood in the frozen entry: markets (Kalshi and Polymarket together, weighted by
volume), polls, our own fundamentals, and DDHQ's House probabilities (22 Oct). DDHQ blends polls and
markets itself, so it counts as a source of its own and not as fundamentals.

The best mixes use the results, so they are hindsight and never forecasts. The forecast stays frozen.
    best mix         the weights on the sources' log-odds with the lowest Brier score on these races
    knowing the wave those weights plus a shift and a sharpening of the log-odds
    lookup table     each race takes the result of the race with the most similar source chances. It
                     finds itself, so its fit is perfect by construction; it only shows in the test.
Two tests: each state predicted by a fit on the other states (same election, so the wave stays
known), and the fit applied to the 2024 Senate races, a different election, with Polymarket prices
one week out (data/backtest_markets_2024.csv).
Writes app/data/calibration.json.

    python -I pipeline/calibration.py
"""

import csv
import json
import sys
from functools import lru_cache
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "data"
DATA = ROOT / "data"
FROZEN = "2026-11-02T21:02+00:00"  # meta.updated of the contest entry

BRACKETS = [(0, .02), (.02, .05), (.05, .10), (.10, .20), (.20, .35), (.35, .65), (.65, .80), (.80, .90), (.90, .95), (.95, .98), (.98, 1.01)]
COARSE = [(0, .05), (.05, .35), (.35, .65), (.65, .95), (.95, 1.01)]
SAFE = 0.05  # below this, or above 1 - this, a race counts as safe (the rating bands)
WAVE_SIMS = 400
MIN_COUNTED = 90  # percent of the vote counted before a margin is compared
SOURCES = ("market", "polls", "fundamentals", "ddhq")
CLIP = 0.001  # chances are held inside 0.1-99.9% before they become log-odds
MIX_STEP, TEST_STEP = 0.02, 0.05  # grid of weights: for the fit, and for the many refits of the state test
REGION = {"New England": "Northeast", "Middle Atlantic": "Northeast", "East North Central": "Midwest", "West North Central": "Midwest",
          "South Atlantic": "South", "East South Central": "South", "West South Central": "South", "Mountain": "West", "Pacific": "West"}
REGIONS = ["Northeast", "Midwest", "South", "West"]


def label(lo, hi):
    return f"{round(lo * 100)}–{min(round(hi * 100), 100)}%"


def load():
    forecast = json.loads((APP / "forecast.json").read_text(encoding="utf-8"))
    if forecast["meta"]["updated"] != FROZEN:
        sys.exit(f"forecast.json is not the contest entry ({forecast['meta']['updated']}); restore it from the tag contest-entry.")
    seats = json.loads((APP / "seats.json").read_text(encoding="utf-8"))
    frozen = {r["race_id"]: r for r in csv.DictReader((DATA / "model_races.csv").open(encoding="utf-8"))}
    # Same order as model.build_races, so the same seed gives the same simulations as on 2 Nov.
    races = [dict(s, chamber="senate") for s in seats["senate"]] + [dict(h, chamber="house") for h in seats["house"]]
    for r in races:
        f = frozen[r["id"]]
        r.update(mean=float(f["mean_margin"]), sd=float(f["sd"]), side=f["side"], p=forecast["races"][r["id"]]["p_dem"])
    division = {s["abbr"]: s["division"] for s in seats["states"]}
    env = json.loads((DATA / "national_environment.json").read_text(encoding="utf-8"))
    data = {"division": division, "env": env, "not_up_d": seats["chambers"]["senate"]["not_up"]["D"]}
    _, _, wins, _, _ = model.simulate(races, data, model.DEFAULT_CFG, model.SEED)
    drift = float(np.abs(wins.mean(axis=0) - np.array([r["p"] for r in races])).max())
    if drift > 0.01:
        sys.exit(f"The simulation does not reproduce the frozen chances (largest gap {drift:.3f}).")
    return forecast, seats, races, division, env, wins


def outcomes(races, results, basis):
    """1 if the non-Republican side won, 0 if not, None if not known on this basis."""
    y = []
    for r in races:
        x = results["races"].get(r["id"], {})
        side = x.get("winner") if x.get("status") == "called" else x.get("leader") if basis == "leaders" and x.get("status") == "counting" else None
        y.append(None if side is None else int(side != "R"))
    return y


def rows(idx, edges, p, y, wins, wave):
    out = []
    for lo, hi in edges:
        m = [i for i in idx if lo <= p[i] < hi]
        if not m:
            continue
        sims = wins[:, m].mean(axis=1)
        out.append({"bracket": label(lo, hi), "lo": lo, "hi": min(hi, 1), "n": len(m), "mean_p": round(float(p[m].mean()), 4),
                    "wins": int(y[m].sum()), "freq": round(float(y[m].mean()), 4),
                    "band": [round(float(q), 4) for q in np.percentile(sims, [5, 95])],
                    "wave": round(float(wins[wave][:, m].mean()), 4)})
    return out


def favourites(idx, p, y):
    out = []
    for scope, keep in (("all", lambda x: True), ("non-safe", lambda x: SAFE <= x <= 1 - SAFE)):
        for party in ("D", "R"):
            m = [i for i in idx if keep(p[i]) and (p[i] >= 0.5) == (party == "D")]
            if not m:
                continue
            chance = p[m] if party == "D" else 1 - p[m]
            won = y[m] if party == "D" else 1 - y[m]
            out.append({"scope": scope, "party": party, "n": len(m), "chance": round(float(chance.mean()), 4), "won": round(float(won.mean()), 4),
                        "expected": round(float(chance.sum()), 1), "actual": int(won.sum())})
    return out


def brier(p, y):
    return round(float(np.mean((p - y) ** 2)), 4)


def source_chances(forecast, races):
    """Each source's chance per race from the frozen entry, nan where it has none."""
    q = np.full((len(races), len(SOURCES)), np.nan)
    for i, r in enumerate(races):
        x = forecast["races"][r["id"]]["inputs"]
        f = x["fundamentals"]  # in the House this is DDHQ, and our own sit in fundamentals_own
        q[i] = [x.get("market", {}).get("p", np.nan), x.get("polls", {}).get("p", np.nan),
                x.get("fundamentals_own", f)["p"], f["p"] if f["source"] == "ddhq" else np.nan]
    return q


def logit(p):
    p = np.clip(p, CLIP, 1 - CLIP)
    return np.log(p / (1 - p))


def expit(z):
    return 1 / (1 + np.exp(-z))


@lru_cache(maxsize=None)
def simplex(parts, step):
    """Every way to split 100% over this many sources, in steps of this size."""
    n = round(1 / step)
    return np.array([(*c, n - sum(c)) for c in product(range(n + 1), repeat=parts - 1) if sum(c) <= n]) / n


def blend(w, z, have):
    """Weighted log-odds of the sources a race has, for one set of weights or a stack of them.
    z holds 0 where a source is missing. A race without any weighted source takes the plain average."""
    den = w @ have.T
    return np.where(den > 0, (w @ (z * have).T) / np.where(den > 0, den, 1), z.sum(axis=1) / have.sum(axis=1))


def fit_weights(z, have, y, step, shift=0.0, slope=1.0):
    """The weights with the lowest Brier score; a source with no race in this set stays at 0."""
    used = have.any(axis=0)
    grid = np.zeros((len(simplex(int(used.sum()), step)), z.shape[1]))
    grid[:, used] = simplex(int(used.sum()), step)
    return grid[((expit(shift + slope * blend(grid, z, have)) - y) ** 2).mean(axis=1).argmin()]


def fit_shift(score, y):
    """Shift and slope of the log-odds with the lowest Brier score: a coarse grid, then zooming in."""
    shifts, slopes = np.arange(-4, 4.01, .25), np.arange(.25, 5.01, .25)
    d = .25
    for _ in range(4):
        e = ((expit(shifts[:, None, None] + slopes[None, :, None] * score) - y) ** 2).mean(axis=2)
        i, j = np.unravel_index(e.argmin(), e.shape)
        a, b = float(shifts[i]), float(slopes[j])
        shifts, slopes, d = a + np.linspace(-d, d, 9), b + np.linspace(-d, d, 9), d / 4
    return a, b


def fit_hindsight(z, have, y, step):
    """Weights, shift and slope together, in turns."""
    w = fit_weights(z, have, y, step)
    for _ in range(3):
        a, b = fit_shift(blend(w, z, have), y)
        w = fit_weights(z, have, y, step, a, b)
    return (w, *fit_shift(blend(w, z, have), y))


def state_test(idx, states, q, z, have, y):
    """Brier scores when every state is predicted by fits on the other states of this election."""
    idx = np.array(idx)
    used = have[idx].any(axis=0)
    filled = np.where(have[:, used] > 0, q[:, used], np.nanmean(q[idx][:, used], axis=0))
    mix, hindsight, lookup = np.empty(len(y)), np.empty(len(y)), np.empty(len(y))
    for s in sorted(set(states[idx])):
        tr, te = idx[states[idx] != s], idx[states[idx] == s]
        mix[te] = expit(blend(fit_weights(z[tr], have[tr], y[tr], TEST_STEP), z[te], have[te]))
        w, a, b = fit_hindsight(z[tr], have[tr], y[tr], TEST_STEP)
        hindsight[te] = expit(a + b * blend(w, z[te], have[te]))
        lookup[te] = y[tr][((filled[te][:, None, :] - filled[tr][None, :, :]) ** 2).sum(axis=2).argmin(axis=1)]
    return {"mix": brier(mix[idx], y[idx]), "hindsight": brier(hindsight[idx], y[idx]), "lookup": brier(lookup[idx], y[idx])}


def senate_2024(shift, slope):
    """A different election: plain Polymarket prices one week out, then with this year's correction."""
    rows_2024 = list(csv.DictReader((DATA / "backtest_markets_2024.csv").open(encoding="utf-8")))
    p = np.array([float(r["p_nonrep"]) for r in rows_2024])
    won = np.array([r["won"] == "True" for r in rows_2024], float)
    return {"n": len(rows_2024), "market": brier(p, won), "hindsight": brier(expit(shift + slope * logit(p)), won)}


def plain_rows(idx, p, y):
    """Brackets for a source: what it said and what happened, without simulations."""
    out = []
    for lo, hi in BRACKETS:
        m = [i for i in idx if lo <= p[i] < hi]
        if m:
            out.append({"bracket": label(lo, hi), "n": len(m), "mean_p": round(float(p[m].mean()), 4), "wins": int(y[m].sum()), "freq": round(float(y[m].mean()), 4)})
    return out


def compare(idx, p, y, q, wins, wave, states):
    """Every source and fit on these races: on its own races, and on those with both polls and markets."""
    z, have = np.nan_to_num(logit(q)), (~np.isnan(q)).astype(float)
    ix = np.array(idx)
    w = fit_weights(z[ix], have[ix], y[ix], MIX_STEP)
    wh, shift, slope = fit_hindsight(z[ix], have[ix], y[ix], MIX_STEP)
    chance = {"us": p, **{k: q[:, j] for j, k in enumerate(SOURCES)}, "mix": expit(blend(w, z, have)), "hindsight": expit(shift + slope * blend(wh, z, have))}
    shared = [i for i in idx if have[i, 0] and have[i, 1]]
    series = {}
    for key, c in chance.items():
        m = [i for i in idx if not np.isnan(c[i])]
        if not m:
            continue
        covers = bool(shared) and not np.isnan(c[shared]).any()
        series[key] = {"n": len(m), "brier": brier(c[m], y[m]), "us": brier(p[m], y[m]), "brackets": plain_rows(m, c, y),
                       "shared": brier(c[shared], y[shared]) if covers else None,
                       "shared_brackets": (rows(shared, BRACKETS, c, y, wins, wave) if key == "us" else plain_rows(shared, c, y)) if covers else None}
    named = lambda v: dict(zip(SOURCES, (round(float(x), 2) for x in v)))
    market_or_fundamentals = np.where(have[:, 0] > 0, q[:, 0], q[:, 2])
    mix = {"weights": named(w), "hindsight": {"weights": named(wh), "shift": round(shift, 2), "slope": round(slope, 2), "tossup": round(float(expit(shift)), 3)},
           "market": brier(market_or_fundamentals[ix], y[ix]), "states": state_test(idx, states, q, z, have, y), "senate_2024": senate_2024(shift, slope)}
    return series, len(shared), mix


def groups(idx_all, chamber, region_of, q, y):
    """The best mix again on parts of the races: how much do the weights depend on the sample?"""
    z, have = np.nan_to_num(logit(q)), (~np.isnan(q)).astype(float)
    parts = [("All races", idx_all), ("House", [i for i in idx_all if chamber[i] == "house"]), ("Senate", [i for i in idx_all if chamber[i] == "senate"])]
    parts += [(name, [i for i in idx_all if region_of[i] == name]) for name in REGIONS]
    out = []
    for name, m in parts:
        if m:
            ix = np.array(m)
            w = fit_weights(z[ix], have[ix], y[ix], MIX_STEP)
            out.append({"name": name, "n": len(m), "weights": dict(zip(SOURCES, (round(float(x), 2) for x in w))), "brier": brier(expit(blend(w, z[ix], have[ix])), y[ix])})
    return out


def view(idx, races, p, y, wins, results, q, states):
    total = int(y[idx].sum())
    sims = wins[:, idx].sum(axis=1)
    wave = np.argsort(np.abs(sims - total), kind="stable")[:WAVE_SIMS]
    non_safe = [i for i in idx if SAFE <= p[i] <= 1 - SAFE]
    region_of = [REGION[r["division"]] for r in races]

    regions = []
    for name in REGIONS:
        m = [i for i in idx if region_of[i] == name]
        ns = [i for i in m if SAFE <= p[i] <= 1 - SAFE]
        if m:
            regions.append({"region": name, "n": len(m), "expected": round(float(p[m].sum()), 1), "actual": int(y[m].sum()), "brier": brier(p[m], y[m]),
                            "n_non_safe": len(ns), "expected_non_safe": round(float(p[ns].sum()), 1), "actual_non_safe": int(y[ns].sum()),
                            "upsets_d": sum(1 for i in m if p[i] < .5 and y[i] == 1), "upsets_r": sum(1 for i in m if p[i] >= .5 and y[i] == 0),
                            "brackets": rows(m, COARSE, p, y, wins, wave)})

    misses = {}
    for i in non_safe:
        x = results["races"][races[i]["id"]]
        if x["margin"] is not None and (x["reporting"] or 0) >= MIN_COUNTED:
            misses.setdefault(races[i]["division"], []).append(x["margin"] - races[i]["mean"])
    divisions = [{"division": k, "region": REGION[k], "n": len(v), "miss": round(float(np.mean(v)), 1),
                  "se": round(float(np.std(v, ddof=1) / np.sqrt(len(v))), 1) if len(v) > 1 else None} for k, v in misses.items()]
    every = [m for v in misses.values() for m in v]

    surprises = []
    for i in sorted(idx, key=lambda i: -abs(y[i] - p[i]))[:12]:
        r = races[i]
        x = results["races"][r["id"]]
        surprises.append({"race_id": r["id"], "p": round(float(p[i]), 3), "won": int(y[i]), "status": x["status"], "margin": x["margin"],
                          "lead_votes": x["lead_votes"], "reporting": x["reporting"], "top": x["top"]})

    series, n_shared, mix = compare(idx, p, y, q, wins, wave, states)
    return {
        "n": len(idx), "actual": total, "expected": round(float(p[idx].sum()), 1), "share_sims_below": round(float((sims < total).mean()), 4),
        "brier": brier(p[idx], y[idx]), "n_non_safe": len(non_safe), "brier_non_safe": brier(p[non_safe], y[non_safe]) if non_safe else None,
        "favourite_won": round(float(np.mean((p[idx] >= .5) == (y[idx] == 1))), 4),
        "wrong": [races[i]["id"] for i in idx if (p[i] >= .5) != (y[i] == 1)],
        "brackets": rows(idx, BRACKETS, p, y, wins, wave), "favourites": favourites(idx, p, y), "regions": regions,
        "divisions": sorted(divisions, key=lambda d: -d["miss"]),
        "mean_miss": round(float(np.mean(every)), 1) if every else None, "n_miss": len(every),
        "surprises": surprises,
        "series": series, "n_shared": n_shared, "mix": mix,
    }


def contest(forecast, results):
    c, h = forecast["contest"], results["house"]
    called, ahead = h["called"]["D"], h["called"]["D"] + h["leading"]["D"]
    dist = forecast["house"]["distribution"]
    won_house = 1 if "DEM" in results["control"].get("house", {}) else 0 if "GOP" in results["control"].get("house", {}) else None
    districts, errors = [], []
    for d in c["districts"]:
        x = results["races"][d["race_id"]]
        side = x["winner"] or x["leader"]
        districts.append({"race_id": d["race_id"], "p": d["p"], "status": x["status"], "side": side, "margin": x["margin"], "called_by": x["called_by"],
                          "reporting": x["reporting"], "top": x["top"], "sq_error": round((d["p"] - (side != "R")) ** 2, 4) if side else None})
        if side:
            errors.append((d["p"] - (side != "R")) ** 2)
    if won_house is not None:
        errors.append((c["p_majority"] - won_house) ** 2)
    return {"seats": {"answer": c["seats"]["answer"], "ci80": c["seats"]["ci80"], "called": called, "with_leaders": ahead, "off_by": ahead - c["seats"]["answer"],
                      "share_sims_below": round(sum(x["p"] for x in dist if x["seats"] < ahead), 4)},
            "p_majority": c["p_majority"], "dem_majority": won_house, "districts": districts, "brier": round(float(np.mean(errors)), 4), "n_scored": len(errors)}


def main():
    forecast, seats, races, division, env, wins = load()
    results = json.loads((APP / "results.json").read_text(encoding="utf-8"))
    p = np.array([r["p"] for r in races])
    chamber = np.array([r["chamber"] for r in races])
    for r in races:
        r["division"] = division[r["state"]]
    q = source_chances(forecast, races)
    states = np.array([r["state"] for r in races])
    region_of = [REGION[r["division"]] for r in races]

    views, mix_groups = {}, {}
    for basis in ("leaders", "called"):
        known = outcomes(races, results, basis)
        y = np.array([-1 if v is None else v for v in known])
        for name, keep in (("all", np.ones(len(races), bool)), ("house", chamber == "house"), ("senate", chamber == "senate")):
            idx = [i for i in range(len(races)) if keep[i] and known[i] is not None]
            views[f"{name}|{basis}"] = view(idx, races, p, y, wins, results, q, states)
        mix_groups[basis] = groups([i for i in range(len(races)) if known[i] is not None], chamber, region_of, q, y)

    s = results["senate"]
    out = {"updated": results["updated"], "frozen": FROZEN, "views": views, "mix_groups": mix_groups, "contest": contest(forecast, results),
           "environment": env["mean"], "national": results["national"],
           "senate": {"p_control": forecast["senate"]["p_dem_control"], "median": forecast["senate"]["dem_seats"]["median"],
                      "called": results["not_up"]["D"] + s["called"]["D"], "with_leaders": results["not_up"]["D"] + s["called"]["D"] + s["leading"]["D"],
                      "dem_majority": 1 if "DEM" in results["control"].get("senate", {}) else 0 if "GOP" in results["control"].get("senate", {}) else None}}
    (APP / "calibration.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    v = views["all|leaders"]
    print(f"All races with a result or leader: {v['n']}; non-Republican wins {v['actual']} vs expected {v['expected']}; Brier {v['brier']}, non-safe {v['brier_non_safe']} ({v['n_non_safe']})")
    for b in v["brackets"]:
        print(f"  {b['bracket']:>8} n {b['n']:>3}  said {b['mean_p']:.3f}  won {b['freq']:.3f}  band {b['band']}  wave {b['wave']}")
    for f in v["favourites"]:
        print(" ", f)
    for r in v["regions"]:
        print(" ", {k: x for k, x in r.items() if k != "brackets"})
    print(" ", v["divisions"], v["mean_miss"], v["n_miss"])
    for k, x in v["series"].items():
        print(f"  {k:>12} n {x['n']:>3}  Brier {x['brier']:.4f}  us {x['us']:.4f}  shared ({v['n_shared']}) {x['shared']}")
    print(" ", v["mix"])
    for g in mix_groups["leaders"]:
        print(" ", g)
    print(json.dumps(out["contest"], ensure_ascii=False)[:900])


if __name__ == "__main__":
    main()
