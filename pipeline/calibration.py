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
    sources     Brier scores of our forecast, the markets, the fundamentals and the polls
Writes app/data/calibration.json.

    python -I pipeline/calibration.py
"""

import csv
import json
import sys
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


def view(idx, races, p, y, wins, results, forecast):
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

    fr = forecast["races"]
    have_m = [i for i in idx if "market" in fr[races[i]["id"]]["inputs"]]
    have_p = [i for i in idx if "polls" in fr[races[i]["id"]]["inputs"]]
    q = lambda m, k: np.array([fr[races[i]["id"]]["inputs"][k]["p"] for i in m])
    return {
        "n": len(idx), "actual": total, "expected": round(float(p[idx].sum()), 1), "share_sims_below": round(float((sims < total).mean()), 4),
        "brier": brier(p[idx], y[idx]), "n_non_safe": len(non_safe), "brier_non_safe": brier(p[non_safe], y[non_safe]) if non_safe else None,
        "favourite_won": round(float(np.mean((p[idx] >= .5) == (y[idx] == 1))), 4),
        "wrong": [races[i]["id"] for i in idx if (p[i] >= .5) != (y[i] == 1)],
        "brackets": rows(idx, BRACKETS, p, y, wins, wave), "favourites": favourites(idx, p, y), "regions": regions,
        "divisions": sorted(divisions, key=lambda d: -d["miss"]),
        "mean_miss": round(float(np.mean(every)), 1) if every else None, "n_miss": len(every),
        "surprises": surprises,
        "sources": {"market_set": {"n": len(have_m), "us": brier(p[have_m], y[have_m]), "markets": brier(q(have_m, "market"), y[have_m]),
                                   "fundamentals": brier(q(have_m, "fundamentals"), y[have_m])} if have_m else None,
                    "poll_set": {"n": len(have_p), "us": brier(p[have_p], y[have_p]), "polls": brier(q(have_p, "polls"), y[have_p])} if have_p else None},
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

    views = {}
    for basis in ("leaders", "called"):
        known = outcomes(races, results, basis)
        y = np.array([-1 if v is None else v for v in known])
        for name, keep in (("all", np.ones(len(races), bool)), ("house", chamber == "house"), ("senate", chamber == "senate")):
            idx = [i for i in range(len(races)) if keep[i] and known[i] is not None]
            views[f"{name}|{basis}"] = view(idx, races, p, y, wins, results, forecast)

    s = results["senate"]
    out = {"updated": results["updated"], "frozen": FROZEN, "views": views, "contest": contest(forecast, results),
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
    print(" ", v["sources"])
    print(json.dumps(out["contest"], ensure_ascii=False)[:900])


if __name__ == "__main__":
    main()
