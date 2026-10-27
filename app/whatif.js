"use strict";

// "Try your own weights": re-runs the House part of the model in the browser with the
// viewer's settings. Same steps as pipeline/model.py: each race's inputs (margin and sd) are
// combined with precision weights (times the viewer's multipliers), then all districts are
// simulated together with a shared national error (t, 5 df), Census-division, state and race
// errors. Uses helpers from app.js ($, html, pct, pct1, app, raceForecast).

const WI_SIMS = 10000;
const WI_SEED = 2026;
const WI_DEFAULT = { base: "ddhq", polls: 1, market: 1, fundamentals: 1 };
const wi = { settings: { ...WI_DEFAULT }, timer: null, baseline: null };

// Seeded random numbers, so every run uses the same draws and differences come from the settings.
function mulberry32(seed) {
  return function () {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normalSource(rand) {
  let spare = null;
  return () => {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u, v, s;
    do { u = rand() * 2 - 1; v = rand() * 2 - 1; s = u * u + v * v; } while (s >= 1 || s === 0);
    const k = Math.sqrt((-2 * Math.log(s)) / s);
    spare = v * k;
    return u * k;
  };
}

// Inverse of the standard normal distribution (Acklam's approximation).
function invNorm(p) {
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const lo = 0.02425;
  if (p < lo) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > 1 - lo) return -invNorm(1 - p);
  const q = p - 0.5, r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

// One district: combine the inputs the settings keep, weighted by precision times multiplier.
function combineInputs(id, s, params) {
  const rf = raceForecast(id);
  // The final model's House fundamentals are DDHQ's; "ours" swaps in our uniform-swing version.
  const fund = s.base === "ours" && rf.inputs.fundamentals_own ? rf.inputs.fundamentals_own : rf.inputs.fundamentals;
  const used = [];
  if (rf.inputs.polls && s.polls > 0) used.push(["polls", rf.inputs.polls, s.polls]);
  if (rf.inputs.market && s.market > 0) used.push(["market", rf.inputs.market, s.market]);
  if (s.fundamentals > 0) used.push(["fundamentals", fund, s.fundamentals]);
  if (!used.length) used.push(["fundamentals", fund, 1]);  // nothing left: fall back to fundamentals
  let total = 0, sum = 0;
  for (const [, x, mult] of used) { const prec = mult / (x.sd * x.sd); total += prec; sum += prec * x.margin; }
  const weights = {};
  for (const [k, x, mult] of used) weights[k] = mult / (x.sd * x.sd) / total;
  return { mean: sum / total, sd: Math.max(params.floor_sd, Math.sqrt(1 / total)), weights };
}

function simulateHouse(s) {
  const f = app.forecast, params = f.meta.sim_params;
  const house = app.seats.house;
  const divNames = [...new Set(app.seats.states.map((st) => st.division))].sort();
  const stateNames = app.seats.states.map((st) => st.abbr).sort();
  const n = house.length;
  const mu = new Float64Array(n), rest = new Float64Array(n), div = new Int32Array(n), st = new Int32Array(n);
  const dem = new Uint8Array(n);
  const contest = f.contest.districts.map((d) => d.race_id);
  const contestIdx = contest.map((id) => house.findIndex((h) => h.id === id));
  const contestWeights = {};
  house.forEach((h, i) => {
    const c = combineInputs(h.id, s, params);
    mu[i] = c.mean;
    rest[i] = Math.sqrt(Math.max(c.sd * c.sd - params.nat_sd * params.nat_sd, 0));
    div[i] = divNames.indexOf(app.stateByAbbr[h.state].division);
    st[i] = stateNames.indexOf(h.state);
    dem[i] = (raceForecast(h.id).side ?? "D") === "D" ? 1 : 0;
    if (contest.includes(h.id)) contestWeights[h.id] = c.weights;
  });
  const sh = params.rest_shares, sd = Math.sqrt(sh.division), ss = Math.sqrt(sh.state), sr = Math.sqrt(sh.race);
  const tScale = Math.sqrt((params.t_df - 2) / params.t_df);
  const rand = mulberry32(WI_SEED), norm = normalSource(rand);
  const seats = new Int32Array(WI_SIMS);
  const contestPos = new Int32Array(n).fill(-1);
  contestIdx.forEach((i, j) => { contestPos[i] = j; });
  const contestWins = new Int32Array(contest.length);
  const dShock = new Float64Array(divNames.length), sShock = new Float64Array(stateNames.length);
  for (let k = 0; k < WI_SIMS; k++) {
    let chi = 0;
    for (let j = 0; j < params.t_df; j++) { const z = norm(); chi += z * z; }
    const national = params.nat_sd * tScale * norm() / Math.sqrt(chi / params.t_df);
    for (let j = 0; j < dShock.length; j++) dShock[j] = norm();
    for (let j = 0; j < sShock.length; j++) sShock[j] = norm();
    let count = 0;
    for (let i = 0; i < n; i++) {
      const m = mu[i] + national + rest[i] * (sd * dShock[div[i]] + ss * sShock[st[i]] + sr * norm());
      if (m > 0) {
        if (dem[i]) count++;
        if (contestPos[i] >= 0) contestWins[contestPos[i]]++;
      }
    }
    seats[k] = count;
  }
  const sorted = Array.from(seats).sort((a, b) => a - b);
  const q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  const districts = {};
  contest.forEach((id, j) => { districts[id] = contestWins[j] / WI_SIMS; });
  return {
    median: q(0.5), p10: q(0.1), p90: q(0.9),
    pMajority: sorted.filter((x) => x >= 218).length / WI_SIMS,
    districts, contestWeights,
  };
}

// ---------- panel ----------

function readSettings() {
  return {
    base: document.querySelector('input[name="wi-base"]:checked')?.value ?? "ddhq",
    polls: +$("#wi-polls").value, market: +$("#wi-market").value, fundamentals: +$("#wi-fund").value,
  };
}

function writeSettings(s) {
  document.querySelector(`input[name="wi-base"][value="${s.base}"]`).checked = true;
  $("#wi-polls").value = s.polls; $("#wi-market").value = s.market; $("#wi-fund").value = s.fundamentals;
  updateSliderLabels();
}

function updateSliderLabels() {
  for (const id of ["wi-polls", "wi-market", "wi-fund"]) {
    const v = +$("#" + id).value;
    $("#" + id + "-out").textContent = v === 0 ? "left out" : `×${v.toFixed(2).replace(/\.?0+$/, "")}`;
  }
}

function isDefault(s) {
  return s.base === WI_DEFAULT.base && s.polls === 1 && s.market === 1 && s.fundamentals === 1;
}

function renderWhatIf(res) {
  const base = wi.baseline;
  const body = $("#wi-body");
  const f = app.forecast;
  const rows = [
    ["(a) Democratic seats (median)", String(res.median), String(base.median)],
    ["80% range", `${res.p10}–${res.p90}`, `${base.p10}–${base.p90}`],
    ["(b) P(majority)", res.pMajority.toFixed(2), base.pMajority.toFixed(2)],
    ...f.contest.districts.map((d) => [app.byId[d.race_id].label, res.districts[d.race_id].toFixed(2), base.districts[d.race_id].toFixed(2)]),
  ];
  body.replaceChildren(...rows.map(([k, a, b]) => html("tr", a !== b ? { class: "changed" } : {}, [
    html("td", { text: k }), html("td", { class: "num", text: a }), html("td", { class: "num", text: b }),
  ])));
  const w = { polls: 0, market: 0, fundamentals: 0 };
  const ids = Object.keys(res.contestWeights);
  for (const id of ids) for (const k in w) w[k] += (res.contestWeights[id][k] ?? 0) / ids.length;
  $("#wi-weights").textContent = `Average weights in the five contest districts: polls ${pct(w.polls)}, markets ${pct(w.market)}, fundamentals ${pct(w.fundamentals)}.`;
  $("#wi-status").textContent = isDefault(wi.settings) ? "Showing our final model." : "Your settings differ from our final model. Changed rows are marked.";
}

function scheduleRun() {
  wi.settings = readSettings();
  updateSliderLabels();
  $("#wi-status").textContent = "Computing…";
  clearTimeout(wi.timer);
  wi.timer = setTimeout(() => renderWhatIf(simulateHouse(wi.settings)), 120);
}

function initWhatIf() {
  if (!app.forecast?.meta?.sim_params) return;
  $("#whatif").hidden = false;
  wi.baseline = simulateHouse(WI_DEFAULT);
  writeSettings(WI_DEFAULT);
  renderWhatIf(wi.baseline);
  for (const el of document.querySelectorAll("#whatif input")) el.addEventListener("input", scheduleRun);
  $("#wi-reset").addEventListener("click", () => { writeSettings(WI_DEFAULT); scheduleRun(); });
}
