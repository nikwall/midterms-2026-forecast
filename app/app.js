"use strict";

// Dashboard for the API-232 midterms forecast. Reads data/seats.json (the seats on the
// ballot) and data/forecast.json (the model output written by pipeline/model.py).

const SVGNS = "http://www.w3.org/2000/svg";
const MAJORITY = { house: 218, senate: 51 };

// Same probability bands as pipeline/model.py.
const BANDS = [
  { cut: 0.95, label: "Safe D", key: "d3", range: "95%+" },
  { cut: 0.65, label: "Likely D", key: "d2", range: "65–95%" },
  { cut: 0.55, label: "Lean D", key: "d1", range: "55–65%" },
  { cut: 0.45, label: "Toss-up", key: "mid", range: "45–55%" },
  { cut: 0.35, label: "Lean R", key: "r1", range: "55–65%" },
  { cut: 0.05, label: "Likely R", key: "r2", range: "65–95%" },
  { cut: 0.0, label: "Safe R", key: "r3", range: "95%+" },
];
const JOINT = [
  { key: "dem_house_dem_senate", label: "Democrats win both", color: "var(--d3)" },
  { key: "dem_house_rep_senate", label: "Dem House, GOP Senate", color: "var(--d1)" },
  { key: "rep_house_dem_senate", label: "GOP House, Dem Senate", color: "var(--r1)" },
  { key: "rep_house_rep_senate", label: "Republicans win both", color: "var(--r3)" },
];

const app = { seats: null, forecast: null, stateFilter: null, byId: {}, stateByAbbr: {}, cands: {}, news: null };
const $ = (sel) => document.querySelector(sel);
const TABS = ["contest", "congress", "maps", "weights", "record", "method"];
// Source icons (sprite in index.html): polls ring a phone, markets pay in bills, DDHQ rings the desk bell.
const ICON = { polls: "i-phone", market: "i-bill", fundamentals: "i-bell", crowd: "i-crowd", us: "i-team" };

// ---------- helpers ----------

function svg(tag, attrs = {}, parent) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function html(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "text") node.textContent = v;
    else if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
}

function icon(kind, cls = "ico") {
  const node = svg("svg", { class: cls, "aria-hidden": "true" });
  svg("use", { href: "#" + ICON[kind] }, node);
  return node;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function pct(p) {
  if (p == null) return "–";
  if (p >= 0.995) return ">99%";
  if (p <= 0.005) return "<1%";
  return Math.round(p * 100) + "%";
}

function pct1(p) {
  return (p * 100).toFixed(1) + "%";
}

// side: "D", or "I" where the non-Republican side is an independent (Nebraska).
function margin(m, side = "D") {
  if (m == null) return "–";
  if (Math.abs(m) < 0.05) return "Even";
  return (m > 0 ? side + "+" : "R+") + Math.abs(m).toFixed(1);
}

function money(v) {
  return v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}k`;
}

function band(p) {
  return BANDS.find((b) => p >= b.cut);
}

function raceForecast(id) {
  return app.forecast.races?.[id] ?? null;
}

function raceName(id) {
  const s = app.byId[id];
  if (!s) return id;
  return id.startsWith("S-") ? `${app.stateByAbbr[s.state].name} Senate` : s.label;
}

// ---------- tooltip ----------

const tip = $("#tooltip");

function placeTip(evt) {
  let x, y;
  if (evt.clientX != null && evt.type.startsWith("pointer")) {
    x = evt.clientX; y = evt.clientY;
  } else {
    const r = evt.currentTarget.getBoundingClientRect();
    x = r.right; y = r.top;
  }
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let left = x + 14, top = y + 14;
  if (left + w > innerWidth - 8) left = x - w - 14;
  if (top + h > innerHeight - 8) top = y - h - 14;
  tip.style.left = Math.max(8, left) + "px";
  tip.style.top = Math.max(8, top) + "px";
}

function bindTip(node, content) {
  const show = (e) => { tip.innerHTML = content(); tip.hidden = false; placeTip(e); };
  node.addEventListener("pointerenter", show);
  node.addEventListener("pointermove", placeTip);
  node.addEventListener("pointerleave", () => { tip.hidden = true; });
  node.addEventListener("focus", show);
  node.addEventListener("blur", () => { tip.hidden = true; });
}

function tipRows(title, rows) {
  return `<strong>${esc(title)}</strong>` +
    rows.map(([k, v]) => `<div class="row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("");
}

function raceTip(seat, chamber) {
  const rf = raceForecast(seat.id);
  const title = chamber === "senate" ? `${app.stateByAbbr[seat.state].name} Senate${seat.special ? " (special)" : ""}` : seat.label;
  const rows = [];
  if (chamber === "senate") rows.push(["Held by", seat.holder === "D" ? "Democrats" : "Republicans"]);
  if (chamber === "house" && matchup(seat.id)) rows.push(["Candidates", matchup(seat.id)]);
  if (chamber === "house" && seat.new_map_2026) rows.push(["Lines", "new in 2026"]);
  if (rf) {
    const side = rf.side ?? "D";
    rows.push([side === "I" ? `Chance ${rf.side_name ?? "independent"} wins` : "Chance Dem wins", pct(rf.p_dem)]);
    rows.push([side === "I" ? "Margin" : "Dem margin", margin(rf.margin?.mean, side)]);
    if (rf.margin?.ci80) rows.push(["80% range", `${margin(rf.margin.ci80[0], side)} to ${margin(rf.margin.ci80[1], side)}`]);
    rows.push(["Rating", rf.rating ?? band(rf.p_dem).label]);
    const inp = rf.inputs ?? {}, w = rf.weights ?? {};
    if (inp.polls) rows.push(["Polls", `${pct(inp.polls.p)} · ${inp.polls.n_polls_45d} in 45 days · weight ${pct(w.polls)}`]);
    if (inp.market) rows.push(["Markets", `${pct(inp.market.p)} · ${money(inp.market.volume)} · weight ${pct(w.market)}`]);
    if (inp.fundamentals) rows.push(["Fundamentals", `${pct(inp.fundamentals.p)} · weight ${pct(w.fundamentals)}`]);
  } else {
    rows.push(["Forecast", "not yet"]);
  }
  return tipRows(title, rows);
}

// ---------- header and tabs ----------

function renderHeader(f) {
  $("#updated").textContent = f.meta.updated
    ? "Updated " + new Date(f.meta.updated).toLocaleString("en-US", { timeZone: "America/New_York", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) + " ET"
    : "No model run yet";
  $("#sims-note").textContent = f.meta.n_sims ? `Share of ${f.meta.n_sims.toLocaleString("en-US")} simulated elections with each number of Democratic seats` : "";
  $("#method-version").textContent = f.meta.model_version ? `Model ${f.meta.model_version}` : "";
}

function showTab(name) {
  if (!TABS.includes(name)) name = "contest";
  for (const p of document.querySelectorAll("[data-panel]")) p.hidden = p.dataset.panel !== name;
  for (const a of document.querySelectorAll("[data-tab]")) a.setAttribute("aria-selected", String(a.dataset.tab === name));
  tip.hidden = true;
}

// ---------- faces ----------

function initials(name) {
  return name.split(/\s+/).filter((t) => /^[A-Z]/.test(t) && !/^(Jr|Sr|II|III)\.?$/.test(t)).map((t) => t[0]).slice(0, 2).join("");
}

// A candidate's Wikipedia photo, or their initials; the ring shows the party.
function face(c, size = "") {
  const cls = `face ${c.party === "D" ? "dem" : "rep"} ${size}`;
  const inner = c.photo
    ? html("img", { src: c.photo, alt: c.name, loading: "lazy", referrerpolicy: "no-referrer" })
    : html("span", { class: "ini", text: initials(c.name) });
  return c.wiki ? html("a", { class: cls, href: c.wiki, target: "_blank", rel: "noopener", title: `${c.name} on Wikipedia` }, inner)
    : html("span", { class: cls, title: c.name }, inner);
}

// Everything after the first name, without initials and suffixes: "De La Cruz", "Gluesenkamp Perez".
function surname(name) {
  const t = name.replace(/,?\s+(Jr|Sr|II|III)\.?$/, "").trim().split(/\s+/).slice(1).filter((x) => !/^[A-Z]\.$/.test(x));
  return t.join(" ") || name;
}

// "Davis (D, inc.) vs Buckhout (R)"
function matchup(id) {
  const r = app.cands[id];
  if (!r) return null;
  const one = (c) => c ? `${surname(c.name)} (${c.party}${c.incumbent ? ", inc." : ""})` : "";
  return [one(r.dem), one(r.rep)].filter(Boolean).join(" vs ");
}

function faces(id, size) {
  const r = app.cands[id];
  if (!r) return html("span", { class: "faces" });
  return html("span", { class: "faces" }, [r.dem ? face(r.dem, size) : null, r.rep ? face(r.rep, size) : null]);
}

// ---------- contest entry ----------

function prob2(p) {
  return p == null ? "–" : p.toFixed(2);
}

// The icons on a 0–1 track. Evidence sits above the line, in up to three lanes so that icons
// close together do not cover each other; our answer sits below the line with a tick.
const LANE = 17, LANE_GAP = 0.055;

function iconTrack(evidence, ours) {
  const lanes = [];
  const placed = evidence.filter((e) => e.p != null).sort((a, b) => a.p - b.p).map((e) => {
    let lane = 0;
    while (lanes[lane] != null && e.p - lanes[lane] < LANE_GAP) lane++;
    lanes[lane] = e.p;
    return { ...e, lane };
  });
  const nLanes = Math.max(1, lanes.length);
  const axis = nLanes * LANE + 3;
  const ps = placed.map((e) => e.p).concat(ours.p);
  const lo = Math.min(...ps), hi = Math.max(...ps);
  const track = html("div", { class: "icon-track", style: `height:${axis + 24}px;--axis:${axis}px` }, [
    html("span", { class: "spread", style: `left:${lo * 100}%;width:${(hi - lo) * 100}%` }),
  ]);
  for (const e of placed) {
    const node = html("span", { class: "pin", style: `left:${e.p * 100}%;top:${axis - 2 - (e.lane + 1) * LANE}px` }, icon(e.kind));
    bindTip(node, () => tipRows(e.title, e.rows));
    track.append(node);
  }
  const us = html("span", { class: "pin us", style: `left:${ours.p * 100}%;top:${axis}px` }, [html("span", { class: "tick" }), icon("us")]);
  bindTip(us, () => tipRows(ours.title, ours.rows));
  track.append(us);
  return track;
}

function renderContest(f) {
  const c = f.contest;
  const rowsBox = $("#contest-rows");
  rowsBox.replaceChildren();
  if (!c) return;
  $("#contest-due").textContent = c.deadline;
  $("#ans-seats").textContent = c.seats.answer;
  $("#ans-seats-sub").textContent = `80% range ${c.seats.ci80[0]}–${c.seats.ci80[1]}`;
  $("#ans-majority").textContent = prob2(c.p_majority);
  $("#ans-majority-sub").textContent = `218+ in ${pct1(c.p_majority)} of runs`;
  const crowdRows = (f.benchmarks ?? []).filter((b) => b.crowd && b.p_dem_house != null);
  $("#contest-crowds").textContent = crowdRows.length
    ? "Crowds on (b): " + crowdRows.map((b) => `${b.source.split(" (")[0]} ${prob2(b.p_dem_house)}`).join(" · ") : "";

  const wt = (x) => `${Math.round((x ?? 0) * 100)}%`;
  for (const d of c.districts) {
    const rf = raceForecast(d.race_id);
    const inp = rf.inputs ?? {}, w = rf.weights ?? {};
    const crowds = (d.crowds ?? []).filter((x) => x.p != null);
    const crowdP = crowds.length ? crowds.reduce((s, x) => s + x.p, 0) / crowds.length : null;
    const evidence = [
      inp.polls && { kind: "polls", p: inp.polls.p, title: "Polls", rows: [["P(D)", prob2(inp.polls.p)], ["Polls", `${inp.polls.n_polls}, latest ${inp.polls.latest}`], ["Weight", wt(w.polls)]] },
      inp.market && { kind: "market", p: inp.market.p, title: "Markets", rows: [["P(D)", prob2(inp.market.p)], ["Traded", money(inp.market.volume)], ["Weight", wt(w.market)]] },
      { kind: "fundamentals", p: inp.fundamentals.p, title: inp.fundamentals.source === "ddhq" ? "DDHQ, 22 Oct" : "Fundamentals", rows: [["P(D)", prob2(inp.fundamentals.p)], ["Weight", wt(w.fundamentals)]] },
      crowdP != null && { kind: "crowd", p: crowdP, title: "Crowds (not used)", rows: crowds.map((x) => [x.source, prob2(x.p)]) },
    ].filter(Boolean);
    const track = iconTrack(evidence, { p: d.p, title: "Our answer", rows: [["P(D)", prob2(d.p)], ["Expected margin", margin(rf.margin.mean)],
      ["80% range", `${margin(rf.margin.ci80[0])} to ${margin(rf.margin.ci80[1])}`]] });

    const parts = [];
    parts.push(inp.polls ? `polls ${prob2(inp.polls.p)} (${inp.polls.n_polls} ${inp.polls.n_polls === 1 ? "poll" : "polls"}, latest ${inp.polls.latest}, weight ${wt(w.polls)})` : "no polls");
    parts.push(inp.market ? `markets ${prob2(inp.market.p)} (${money(inp.market.volume)} traded, weight ${wt(w.market)})` : "no market");
    parts.push(`${inp.fundamentals.source === "ddhq" ? "DDHQ" : "fundamentals"} ${prob2(inp.fundamentals.p)} (weight ${wt(w.fundamentals)})`);
    const crowdText = (d.crowds ?? []).map((x) => `${x.source} ${x.p != null ? prob2(x.p) : "–"}${x.note && x.p == null ? ` (${x.note})` : ""}`).join(" · ");
    const b = band(d.p);
    const seat = app.byId[d.race_id];
    const row = html("div", { class: "c-row" }, [
      html("div", { class: "c-main" }, [
        faces(d.race_id),
        html("div", { class: "c-name" }, [html("strong", { text: seat.label }), html("span", { text: matchup(d.race_id) ?? d.name })]),
        html("span", { class: "c-p", style: `color:var(--${d.p >= 0.65 ? "d3" : d.p <= 0.35 ? "r3" : "ink"})`, text: prob2(d.p) }),
        track,
      ]),
      html("details", { class: "c-detail" }, [
        html("summary", { text: `${b.label} · inputs${d.hints.length ? " and checks" : ""}` }),
        html("div", {}, [
          html("p", { text: `Inputs: ${parts.join(" · ")}. Expected margin ${margin(rf.margin.mean)} (80% range ${margin(rf.margin.ci80[0])} to ${margin(rf.margin.ci80[1])}).` }),
          crowdText ? html("p", { class: "muted", text: `Crowds, not used: ${crowdText}.` }) : null,
          ...d.hints.map((h) => html("p", { class: "check", text: `Check: ${h}` })),
        ]),
      ]),
    ]);
    rowsBox.append(row);
  }

  const ex = $("#explain-median");
  ex.replaceChildren(
    html("p", { text: "The contest ranks teams by how close their seat number is to the actual count. For that kind of scoring the median is the best single number: half of our simulations end above it and half below, which keeps the expected distance to the true result smallest." }),
    html("p", { text: `The mean (${c.seats.mean}) would be best if large misses were punished more than proportionally. The most frequent count (${c.seats.mode}) is a poor choice: with the simulations spread over many seat counts, even the most common one occurs in only about ${pct1(Math.max(...f.house.distribution.map((x) => x.p)))} of them.` }),
  );
}

// ---------- the races that decide the majority ----------

const MORE_DECIDERS = 17;

function renderDeciders(f) {
  const shares = f.house?.tipping_shares ?? [];
  const box = $("#deciders"), more = $("#deciders-more");
  box.replaceChildren();
  more.replaceChildren();
  if (!shares.length) return;
  const { set, cum } = halfSet(shares);
  const contest = new Set(f.contest.districts.map((d) => d.race_id));
  const nContest = [...set].filter((id) => contest.has(id)).length;
  $("#deciders-note").textContent = `${set.size} districts deliver the 218th seat in ${pct(cum)} of simulations` +
    (nContest ? `; ${nContest} of them are contest districts` : "");
  for (const id of set) {
    const t = shares.find((s) => s.race_id === id);
    const rf = raceForecast(id), b = band(rf.p_dem), r = app.cands[id] ?? {};
    const person = (c) => c ? html("span", { class: "who" }, [face(c),
      html("span", { class: "who-name", text: c.name }), html("span", { class: "muted", text: c.incumbent ? `${c.party}, inc.` : c.party })]) : null;
    const card = html("article", { class: "decider" + (contest.has(id) ? " in-contest" : ""), tabindex: 0 }, [
      html("div", { class: "decider-head" }, [
        html("strong", { text: app.byId[id].label }),
        contest.has(id) ? html("span", { class: "badge", text: "contest" }) : null,
        html("span", { class: "decider-p", style: `background:var(--${b.key});color:var(--on-${b.key})`, text: pct(rf.p_dem) }),
      ]),
      html("div", { class: "decider-people" }, [person(r.dem), person(r.rep)]),
      html("div", { class: "decider-foot muted", text: `${b.label} · decides control in ${pct1(t.share)} of simulations` }),
    ]);
    bindTip(card, () => raceTip(app.byId[id], "house"));
    card.addEventListener("click", (e) => { if (!e.target.closest("a")) setStateFilter(app.byId[id].state, id); });
    box.append(card);
  }
  const next = shares.filter((s) => !set.has(s.race_id)).slice(0, MORE_DECIDERS);
  const nextCum = next.reduce((s, t) => s + t.share, 0);
  $("#deciders-more-label").textContent = `The next ${next.length} districts (together another ${pct(nextCum)} of simulations)`;
  for (const t of next) {
    const rf = raceForecast(t.race_id), b = band(rf.p_dem);
    const row = html("div", { class: "decider-row", tabindex: 0 }, [
      faces(t.race_id, "sm"),
      html("strong", { text: app.byId[t.race_id].label }),
      html("span", { class: "muted", text: matchup(t.race_id) ?? "" }),
      html("span", { class: "num", text: `${pct(rf.p_dem)} D` }),
      html("span", { class: "chip" }, [html("span", { class: "swatch", style: `background:var(--${b.key})` }), b.label]),
      html("span", { class: "num muted", text: pct1(t.share) }),
    ]);
    bindTip(row, () => raceTip(app.byId[t.race_id], "house"));
    row.addEventListener("click", (e) => { if (!e.target.closest("a")) setStateFilter(app.byId[t.race_id].state, t.race_id); });
    more.append(row);
  }
}

// ---------- us and the crowds ----------

function renderCompare(f) {
  const body = $("#compare-body");
  body.replaceChildren();
  const c = f.contest;
  if (!c) return;
  body.append(html("tr", { class: "us" }, [
    html("td", {}, [icon("us"), html("strong", { text: " Us (model v2)" })]),
    html("td", { class: "num", text: c.seats.answer }), html("td", { class: "num", text: prob2(c.p_majority) }),
    html("td", { text: f.meta.updated.slice(0, 10) }),
  ]));
  for (const b of f.benchmarks ?? []) {
    if (b.p_dem_house == null) continue;
    body.append(html("tr", {}, [
      html("td", {}, [b.crowd ? icon("crowd") : /market/.test(b.source) ? icon("market") : null, " ",
        b.url ? html("a", { href: b.url, target: "_blank", rel: "noopener", text: b.source }) : b.source]),
      html("td", { class: "num", text: b.dem_seats ?? "–" }),
      html("td", { class: "num", text: prob2(b.p_dem_house) }),
      html("td", { text: b.as_of ?? "–" }),
    ]));
  }
}

function renderNews(n) {
  const box = $("#news-check");
  box.replaceChildren();
  if (!n) return;
  box.append(html("p", { text: `As of ${n.date}. ${n.summary}` }));
  for (const d of n.districts) {
    box.append(html("div", { class: "news-district" }, [
      html("strong", { text: `${app.byId[d.race_id]?.label ?? d.race_id}${matchup(d.race_id) ? " · " + matchup(d.race_id) : ""}` }),
      html("ul", {}, d.items.map((t) => html("li", { text: t }))),
      html("p", { class: "small" }, ["Sources: ", ...d.links.flatMap(([name, url], i) => [i ? " · " : "", html("a", { href: url, target: "_blank", rel: "noopener", text: name })])]),
    ]));
  }
}

// ---------- track record: the House model in 2022 and 2024 ----------

function renderBacktest(bt) {
  const intro = $("#record-intro"), box = $("#record-years");
  box.replaceChildren();
  if (!bt) { intro.textContent = "The backtest appears after pipeline/backtest_house.py has run."; return; }
  const years = Object.values(bt);
  const both = years.map((y) => y.variants.model);
  intro.textContent = `What our House model would have entered one week before Election Day in ${years.map((y) => y.year).join(" and ")}, ` +
    `with the polls and fundamentals available then. Both times it made Republicans the favourites for the majority ` +
    `(P(Democratic majority) ${both.map((m) => prob2(m.p_majority)).join(" and ")}), and Republicans won. ` +
    `The seat count was off by ${both.map((m) => Math.abs(m.seat_error)).join(" and ")} seats.`;
  for (const y of years) {
    const m = y.variants.model, fo = y.variants.fundamentals_only;
    const won = y.actual_majority ? "Democrats won" : "Republicans won";
    const card = html("article", { class: "card record" }, [
      html("div", { class: "record-head" }, [html("h3", { text: y.year }),
        html("span", { class: "muted small", text: `as of ${y.as_of} · ${y.district_polls} district polls in ${y.districts_with_polls} districts · generic ballot D${y.environment >= 0 ? "+" : ""}${y.environment}` })]),
      html("div", { class: "answers mini" }, [
        html("div", { class: "answer" }, [html("span", { class: "q", text: "(a) Dem seats" }), html("span", { class: "a", text: m.median }),
          html("span", { class: "sub", text: `actual ${y.actual_d_seats} · off by ${Math.abs(m.seat_error)}` })]),
        html("div", { class: "answer" }, [html("span", { class: "q", text: "(b) P(majority)" }), html("span", { class: "a", text: prob2(m.p_majority) }),
          html("span", { class: "sub", text: `${won} · Brier ${m.brier_majority.toFixed(3)}` })]),
        html("div", { class: "answer" }, [html("span", { class: "q", text: "(c) Brier, 5 closest" }), html("span", { class: "a", text: m.brier_closest_five.toFixed(2) }),
          html("span", { class: "sub", text: "0.25 = a coin flip" })]),
      ]),
      html("table", { class: "small-table" }, [
        html("thead", {}, html("tr", {}, [html("th", { text: "Five closest districts" }), html("th", { class: "num", text: "P(D)" }), html("th", { text: "Winner" }), html("th", { class: "num", text: "D margin" })])),
        html("tbody", {}, m.closest_five.map((d) => html("tr", {}, [
          html("td", { text: d.race_id.slice(2) }), html("td", { class: "num", text: prob2(d.p) }),
          html("td", { text: d.won ? "D" : "R" }), html("td", { class: "num", text: margin(d.actual_margin) }),
        ]))),
      ]),
      html("table", { class: "small-table" }, [
        html("thead", {}, html("tr", {}, [html("th", { text: "Calibration" }), html("th", { class: "num", text: "Districts" }), html("th", { class: "num", text: "Our mean P(D)" }), html("th", { class: "num", text: "D won" })])),
        html("tbody", {}, m.calibration.map((c) => html("tr", {}, [
          html("td", { text: c.bin }), html("td", { class: "num", text: c.n }), html("td", { class: "num", text: prob2(c.mean_p) }), html("td", { class: "num", text: prob2(c.d_won) }),
        ]))),
      ]),
      html("p", { class: "small", text: `Brier over the ${m.n_competitive} districts we gave 5–95%: ${m.brier_competitive.toFixed(3)}. Districts called wrong: ${m.calls_wrong} of ${y.districts}. ` +
        `Fundamentals alone would have said ${fo.median} seats and ${prob2(fo.p_majority)}.` }),
      html("details", { class: "more" }, [html("summary", { text: `The ${y.misses.length} districts we called wrong` }),
        html("p", { class: "small", text: y.misses.map((x) => `${x.race_id.slice(2)} (${prob2(x.p)}; ${x.won ? "D" : "R"} won by ${Math.abs(x.actual_margin).toFixed(1)})`).join(", ") })]),
    ]);
    box.append(card);
  }
  $("#record-method").replaceChildren(
    html("p", { text: "Each year is run with the 2026 model's formulas and error sizes: poll errors ±2.4 and ±9.7, a shared national error of ±3.6 with fat tails, the same weighting of polls and the same simulation with 20,000 runs." }),
    html("p", { text: `Inputs: district polls of the actual matchup and our own fundamentals (district lean + generic-ballot average + 3 points for an incumbent). Lean: ${years.map((y) => `${y.year}: ${y.lean_source}`).join("; ")}.` }),
    html("p", { text: "Left out: prediction markets and DDHQ's district probabilities, which carry most of the weight in our 2026 contest districts but have no archive for those years. So this tests the skeleton of the model, not the full 2026 version." }),
    html("p", { text: "The contest's part (c) names five districts in advance. As a stand-in we score the five districts our model rated closest to 50%; races that close are near coin flips for any model, so a Brier score near 0.25 is expected." }),
    html("p", { class: "small" }, ["Data: ", html("a", { href: "https://github.com/fivethirtyeight/election-results", target: "_blank", rel: "noopener", text: "FiveThirtyEight election results" }),
      ", FiveThirtyEight poll archive and polls page (", html("a", { href: "https://web.archive.org/web/20241129175737/https://projects.fivethirtyeight.com/polls-page/data/house_polls.csv", target: "_blank", rel: "noopener", text: "Wayback copy" }),
      "), ", html("a", { href: "https://the-db.co/presbycd", target: "_blank", rel: "noopener", text: "The Downballot" }), ". Code: pipeline/backtest_house.py."]),
  );
}

function renderChamber(name, c) {
  const card = $("#card-" + name);
  const field = (k) => card.querySelector(`[data-field="${k}"]`);
  const p = c?.p_dem_control ?? null;
  field("p-d").textContent = pct(p);
  field("p-r").textContent = p == null ? "–" : pct(1 - p);
  const [d, r] = card.querySelectorAll(".split-bar span");
  d.style.flex = p == null ? "0 0 0" : `${p} 1 0`;
  r.style.flex = p == null ? "0 0 0" : `${1 - p} 1 0`;
  const s = c?.dem_seats ?? {};
  field("median").textContent = s.median ?? "–";
  field("ci80").textContent = s.ci80 ? `${s.ci80[0]}–${s.ci80[1]}` : "–";
  field("ci95").textContent = s.ci95 ? `${s.ci95[0]}–${s.ci95[1]}` : "–";
}

function renderExplainers(f) {
  const rb = f.meta.robustness;
  const sims = $("#explain-sims");
  sims.replaceChildren();
  if (rb) {
    const runsH = rb.reruns.map((r) => r.p_house), runsS = rb.reruns.map((r) => r.p_senate);
    const lo = (xs, x) => Math.min(...xs, x), hi = (xs, x) => Math.max(...xs, x);
    sims.append(
      html("p", { text: "Each simulation is one possible election night: every race gets a result, and we count the seats. The chances shown are the share of simulations each party wins. More simulations make the count more precise, but they do not reduce the real uncertainty. That comes from the inputs." }),
      html("p", { text: `With ${rb.n_sims.toLocaleString("en-US")} simulations, the random noise of the simulation itself is small: about ±${(1.96 * rb.mc_se_house * 100).toFixed(1)} points for the House chance and ±${(1.96 * rb.mc_se_senate * 100).toFixed(1)} points for the Senate chance (95% range).` }),
      html("p", { text: `As a check we re-ran the model with four other random seeds. The House chance stayed between ${pct1(lo(runsH, f.house.p_dem_control))} and ${pct1(hi(runsH, f.house.p_dem_control))}, the Senate chance between ${pct1(lo(runsS, f.senate.p_dem_control))} and ${pct1(hi(runsS, f.senate.p_dem_control))}. Median seats stayed at ${rb.median_range_house[0] === rb.median_range_house[1] ? rb.median_range_house[0] : rb.median_range_house.join("–")} for the House and ${rb.median_range_senate.join("–")} for the Senate. Running more simulations would not change the picture.` }),
    );
  }
  const tipBox = $("#explain-tipping");
  tipBox.replaceChildren();
  tipBox.append(
    html("p", { text: "In each simulation, line up all races from the most to the least Democratic result. The race that gives Democrats their 218th House seat, or their 51st Senate seat, decides control: it is the tipping point of that simulation. Across 20,000 simulations, different races take that role. The charts show how often each one does." }),
    html("p", { text: "The darker bars mark the smallest group of races that together decide control in at least half of all simulations. In the House this group is spread over many districts, so no single district matters much on its own. In the Senate a handful of states carry most of the weight." }),
    html("p", { text: `Because Democrats are expected to win about ${f.house.dem_seats.median} House seats, the 218th seat is usually one they win comfortably. Such a seat only decides control in the simulations where the national result is close.` }),
  );
}

// ---------- which races decide control ----------

// Senate seats by state name ("Alaska"), House seats by district ("NC-01").
function shortName(id) {
  return id.startsWith("S-") ? app.stateByAbbr[app.byId[id].state].name : app.byId[id].label;
}

// The smallest set of races, by share, that together cover at least half of all tipping points.
function halfSet(shares) {
  const set = new Set();
  let cum = 0;
  for (const t of shares) {
    if (cum >= 0.5) break;
    set.add(t.race_id);
    cum += t.share;
  }
  return { set, cum };
}

function renderTipping(chamber) {
  const shares = app.forecast[chamber]?.tipping_shares ?? [];
  const root = $("#tip-" + chamber);
  const sum = $("#tip-sum-" + chamber);
  root.replaceChildren();
  if (!shares.length) { sum.textContent = "Appears after the first model run."; return; }
  const { set, cum } = halfSet(shares);
  const named = [...set].map(shortName);
  const list = named.length > 6 ? `${named.slice(0, 6).join(", ")} and ${named.length - 6} more` : named.join(", ").replace(/, ([^,]*)$/, " or $1");
  sum.textContent = `${set.size} ${chamber === "senate" ? "states" : "districts"} decide control in ${pct(cum)} of simulations: ${list}.`;

  // Order by our expected margin, most Democratic first.
  const rows = shares.map((t) => ({ ...t, m: raceForecast(t.race_id)?.margin?.mean ?? 0 })).sort((a, b) => b.m - a.m);
  const W = 560, H = 210, m = { l: 40, r: 8, t: 12, b: chamber === "senate" ? 44 : 30 };
  root.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const bw = (W - m.l - m.r) / rows.length;
  const yMax = niceCeil(Math.max(...rows.map((r) => r.share)));
  const y = (p) => m.t + (H - m.t - m.b) * (1 - p / yMax);
  for (const v of [0, yMax / 2, yMax]) {
    svg("line", { class: v === 0 ? "axis" : "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, root);
    svg("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, root).textContent = (v * 100).toFixed((v * 100) % 1 ? 1 : 0) + "%";
  }
  rows.forEach((r, i) => {
    const x = m.l + i * bw;
    const w = Math.max(1, bw - (bw > 6 ? 2 : 1));
    const inSet = set.has(r.race_id);
    const rf = raceForecast(r.race_id);
    svg("path", { d: barPath(x + (bw - w) / 2, y(r.share), w, y(0), Math.min(2, w / 2)),
      fill: inSet ? `var(--${band(rf.p_dem).key})` : "var(--mid)" }, root);
    if (chamber === "senate") {
      svg("text", { class: "tip-axis", x: x + bw / 2, y: y(0) + 14, "text-anchor": "middle", fill: inSet ? "var(--ink)" : null }, root)
        .textContent = app.byId[r.race_id].state;
    }
    const hit = svg("rect", { x, y: m.t, width: bw, height: y(0) - m.t, fill: "transparent" }, root);
    bindTip(hit, () => tipRows(shortName(r.race_id), [
      ["Decides control in", pct1(r.share) + " of simulations"],
      ["Chance Dem wins", pct(rf.p_dem)],
      ["Expected margin", margin(rf.margin.mean, rf.side)],
    ]));
    hit.addEventListener("click", () => setStateFilter(app.byId[r.race_id].state, r.race_id));
  });
  const yb = H - 8;
  svg("text", { class: "tip-axis", x: m.l, y: yb }, root).textContent = "← more Democratic";
  svg("text", { class: "tip-axis", x: W - m.r, y: yb, "text-anchor": "end" }, root).textContent = "more Republican →";
}

// ---------- races to watch ----------

function renderWatch(chamber) {
  const box = $("#watch-" + chamber);
  box.replaceChildren();
  const seats = chamber === "senate" ? app.seats.senate : app.seats.house;
  const rows = seats.map((s) => ({ seat: s, rf: raceForecast(s.id) }))
    .filter((r) => r.rf && r.rf.p_dem >= 0.05 && r.rf.p_dem < 0.95)
    .sort((a, b) => b.rf.p_dem - a.rf.p_dem);
  const title = $("#watch-title-" + chamber);
  title.replaceChildren(chamber === "senate" ? "Senate " : "House ",
    html("span", { class: "muted", text: `· ${rows.length} ${chamber === "senate" ? "races" : "districts"} not safe, from most Democratic to most Republican` }));
  for (const b of BANDS.filter((b) => !b.label.startsWith("Safe"))) {
    const group = rows.filter((r) => band(r.rf.p_dem) === b);
    if (!group.length) continue;
    box.append(html("div", { class: "watch-group" }, [
      html("span", { class: "watch-group-label", text: `${b.label} · ${group.length}` }),
      html("div", { class: "chips" }, group.map(({ seat, rf }) => {
        const label = chamber === "senate" ? seat.state : seat.label;
        const chip = html("button", { type: "button", class: "race-chip", style: `background:var(--${b.key});color:var(--on-${b.key})` }, [
          label, html("span", { class: "p", text: pct(rf.p_dem) + (rf.side === "I" ? " I" : "") }),
        ]);
        bindTip(chip, () => raceTip(seat, chamber));
        chip.addEventListener("click", () => setStateFilter(seat.state, seat.id));
        return chip;
      })),
    ]));
  }
}

// ---------- model summary ----------

function renderModelSummary(f) {
  const m = f.meta.inputs;
  if (!m) return;
  const set = (k, text) => { const el = document.querySelector(`[data-m="${k}"]`); if (el) el.textContent = text; };
  set("flow-inputs", `Polls (${m.race_polls} polls in ${m.senate_with_polls + m.house_with_polls} races), prediction markets (Kalshi and Polymarket, ${m.senate_with_market + m.house_with_market} races, ${money(m.market_volume_usd)} traded) and fundamentals (House: Decision Desk HQ's district probabilities of 22 Oct; Senate: the 2024 result in the state plus a national environment of ${margin(m.environment)}).`);
  const ws = m.weights_senate_polled, wu = m.weights_house_unpolled;
  set("flow-weights", ws && wu
    ? `No source is favoured in advance; each counts by how much it knows about that race. In polled Senate races the average weights are polls ${pct(ws.polls)}, markets ${pct(ws.market)} and fundamentals ${pct(ws.fundamentals)}. In House districts without polls, fundamentals carry ${pct(wu.fundamentals)} and markets ${pct(wu.market)}.`
    : "No source is favoured in advance; each counts by how much it knows about that race.");
  set("flow-sims", `Races move together: a shared national error of ±${m.environment_sd.toFixed(0)} points hits all of them, plus regional, state and race-specific errors. Democrats need 218 House seats and 51 Senate seats.`);
}

function renderJoint(joint) {
  const bar = $("#joint-bar");
  const legend = $("#joint-legend");
  bar.replaceChildren();
  legend.replaceChildren();
  for (const j of JOINT) {
    const p = joint?.[j.key] ?? null;
    if (p != null) {
      const seg = html("span", { style: `flex:${p} 1 0;background:${j.color}` });
      bindTip(seg, () => tipRows(j.label, [["Chance", pct(p)]]));
      bar.append(seg);
    }
    legend.append(html("span", { class: "legend-item" }, [
      html("span", { class: "swatch", style: `background:${j.color}` }),
      html("span", { text: `${j.label} ` }),
      html("span", { class: "num", text: pct(p) }),
    ]));
  }
}

// ---------- seat distributions ----------

function niceCeil(v) {
  const steps = [0.01, 0.02, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1];
  return steps.find((s) => s >= v * 1.08) ?? 1;
}

function barPath(x, yTop, w, yBase, r) {
  r = Math.max(0, Math.min(r, w / 2, yBase - yTop));
  return `M${x},${yBase}V${yTop + r}Q${x},${yTop} ${x + r},${yTop}H${x + w - r}Q${x + w},${yTop} ${x + w},${yTop + r}V${yBase}Z`;
}

function renderDist(id, c, majority, fallback, unit) {
  const root = $("#" + id);
  root.replaceChildren();
  const W = 560, H = 230, m = { l: 44, r: 12, t: 24, b: 32 };
  root.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const dist = (c?.distribution ?? []).filter((d) => d.p >= 0.0005);
  let [lo, hi] = fallback;
  if (dist.length) {
    lo = Math.min(...dist.map((d) => d.seats), majority - 3);
    hi = Math.max(...dist.map((d) => d.seats), majority + 3);
    if (unit > 1) { lo = Math.floor(lo / unit) * unit; hi = Math.ceil(hi / unit) * unit; }
  }
  const n = hi - lo + 1;
  const bw = (W - m.l - m.r) / n;
  const x = (s) => m.l + (s - lo) * bw;
  const yMax = niceCeil(dist.length ? Math.max(...dist.map((d) => d.p)) : 0.05);
  const y = (p) => m.t + (H - m.t - m.b) * (1 - p / yMax);

  for (const v of [0, yMax / 2, yMax]) {
    svg("line", { class: v === 0 ? "axis" : "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, root);
    const label = svg("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, root);
    label.textContent = (v * 100).toFixed((v * 100) % 1 ? 1 : 0) + "%";
  }
  const tickStep = n > 50 ? 10 : n > 24 ? 5 : n > 12 ? 2 : 1;
  for (let s = Math.ceil(lo / tickStep) * tickStep; s <= hi; s += tickStep) {
    const t = svg("text", { x: x(s) + bw / 2, y: H - m.b + 16, "text-anchor": "middle" }, root);
    t.textContent = s;
  }

  const bars = svg("g", {}, root);
  const byCount = new Map(dist.map((d) => [d.seats, d.p]));
  for (const d of dist) {
    if (d.seats < lo || d.seats > hi) continue;
    const w = Math.max(1, bw - 2);
    svg("path", {
      d: barPath(x(d.seats) + (bw - w) / 2, y(d.p), w, y(0), 2),
      fill: d.seats >= majority ? "var(--d2)" : "var(--r2)",
    }, bars);
  }

  const mx = x(majority);
  svg("line", { class: "majority", x1: mx, x2: mx, y1: m.t - 6, y2: y(0) }, root);
  const ml = svg("text", { class: "majority-label", x: mx + 5, y: m.t - 10 }, root);
  ml.textContent = `${majority} = majority`;

  if (!dist.length) {
    const note = svg("text", { class: "empty-note", x: (m.l + W - m.r) / 2, y: (m.t + H - m.b) / 2, "text-anchor": "middle" }, root);
    note.textContent = "Distribution appears after the first model run";
    return;
  }
  for (let s = lo; s <= hi; s++) {
    const p = byCount.get(s) ?? 0;
    const hit = svg("rect", { x: x(s), y: m.t, width: bw, height: y(0) - m.t, fill: "transparent" }, root);
    bindTip(hit, () => tipRows(`${s} Democratic seats`, [
      ["Share of simulations", p < 0.001 && p > 0 ? "<0.1%" : (p * 100).toFixed(1) + "%"],
      ["Control", s >= majority ? "Democrats" : "Republicans"],
    ]));
  }
}

// ---------- tile maps ----------

function seatFill(id) {
  const rf = raceForecast(id);
  return rf ? `var(--${band(rf.p_dem).key})` : null;
}

function seatInk(id) {
  const rf = raceForecast(id);
  return rf ? `var(--on-${band(rf.p_dem).key})` : "var(--pending-ink)";
}

function stateTile(root, st, label) {
  const g = svg("g", { class: "state-tile", tabindex: 0, role: "button", "aria-label": label }, root);
  const pick = () => setStateFilter(st.abbr);
  g.addEventListener("click", pick);
  g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  return g;
}

function renderSenateMap() {
  const root = $("#map-senate");
  root.replaceChildren();
  const T = 58, S = T + 4;
  root.setAttribute("viewBox", `0 0 ${11 * S - 4} ${8 * S - 4}`);
  const races = Object.fromEntries(app.seats.senate.map((s) => [s.state, s]));
  for (const st of app.seats.states) {
    const x = st.col * S, y = st.row * S;
    const race = races[st.abbr];
    const g = stateTile(root, st, race ? `${st.name} Senate race` : `${st.name}, no Senate race`);
    if (race) {
      const fill = seatFill(race.id);
      svg("rect", {
        class: "tile-bg", x, y, width: T, height: T, rx: 3,
        fill: fill ?? "var(--pending)", stroke: fill ? "var(--bg)" : "var(--pending-ink)",
        "stroke-dasharray": fill ? null : "3 2", "stroke-width": 1,
      }, g);
      const ink = seatInk(race.id);
      svg("text", { class: "tile-label", x: x + T / 2, y: y + T / 2 + 1, "text-anchor": "middle", fill: ink }, g).textContent = st.abbr;
      const rf = raceForecast(race.id);
      svg("text", { class: "tile-sub", x: x + T / 2, y: y + T / 2 + 16, "text-anchor": "middle", fill: ink }, g)
        .textContent = rf ? pct(rf.p_dem) + (rf.side === "I" ? " I" : "") : `${race.holder} seat`;
      bindTip(g, () => raceTip(race, "senate"));
    } else {
      svg("rect", { class: "tile-bg", x, y, width: T, height: T, rx: 3, fill: "var(--norace)", stroke: "var(--line)", "stroke-dasharray": "3 2" }, g);
      svg("text", { class: "tile-label", x: x + T / 2, y: y + T / 2 + 6, "text-anchor": "middle", fill: "var(--muted)" }, g).textContent = st.abbr;
      bindTip(g, () => tipRows(st.name, [["Senate", "no race in 2026"]]));
    }
  }
}

function renderHouseMap() {
  const root = $("#map-house");
  root.replaceChildren();
  const T = 74, S = T + 4, sq = 7, step = 8, head = 16;
  root.setAttribute("viewBox", `0 0 ${11 * S - 4} ${8 * S - 4}`);
  const byState = {};
  for (const h of app.seats.house) (byState[h.state] ??= []).push(h);
  for (const st of app.seats.states) {
    const x = st.col * S, y = st.row * S;
    const seats = byState[st.abbr];
    const g = stateTile(root, st, `${st.name}, ${seats.length} House ${seats.length === 1 ? "seat" : "seats"}`);
    svg("rect", {
      class: "tile-bg", x: x + 0.75, y: y + 0.75, width: T - 1.5, height: T - 1.5, rx: 3, fill: "var(--bg)",
      stroke: st.new_map_2026 ? "var(--ink-2)" : "var(--line)", "stroke-width": st.new_map_2026 ? 1.2 : 1,
      "stroke-dasharray": st.new_map_2026 ? "4 2.5" : null,
    }, g);
    svg("text", { class: "house-label", x: x + 6, y: y + 12 }, g).textContent = st.abbr;
    svg("text", { class: "house-label", x: x + T - 6, y: y + 12, "text-anchor": "end", fill: "var(--muted)" }, g).textContent = seats.length;
    const cols = Math.min(8, Math.ceil(Math.sqrt(seats.length)));
    const rows = Math.ceil(seats.length / cols);
    const x0 = x + (T - (cols * step - 1)) / 2;
    const y0 = y + head + (T - head - 3 - (rows * step - 1)) / 2;
    seats.forEach((seat, i) => {
      const fill = seatFill(seat.id);
      const r = svg("rect", {
        class: "seat", "data-id": seat.id, x: x0 + (i % cols) * step, y: y0 + Math.floor(i / cols) * step,
        width: sq, height: sq, rx: 1, fill: fill ?? "var(--pending-ink)", "fill-opacity": fill ? null : 0.3,
      }, g);
      bindTip(r, () => raceTip(seat, "house"));
      r.addEventListener("click", (e) => { e.stopPropagation(); setStateFilter(st.abbr, seat.id); });
    });
  }
}

function renderMapLegend() {
  const legend = $("#map-legend");
  legend.replaceChildren();
  for (const b of BANDS) {
    legend.append(html("span", { class: "legend-item" }, [
      html("span", { class: "swatch", style: `background:var(--${b.key})` }),
      html("span", { text: `${b.label} ` }), html("span", { class: "muted", text: b.range }),
    ]));
  }
  legend.append(
    html("span", { class: "legend-item" }, [html("span", { class: "swatch norace" }), "No Senate race"]),
    html("span", { class: "legend-item" }, [html("span", { class: "swatch newmap" }), "New House lines in 2026"]),
  );
}

// ---------- polls vs markets, national environment ----------

const GAP_PREVIEW = 14;

function renderGaps(list, showAll) {
  const box = $("#gap-rows");
  const more = $("#gap-more");
  box.replaceChildren();
  if (!list?.length) {
    box.append(html("p", { class: "muted", text: "Appears once polls and market prices are loaded." }));
    more.hidden = true;
    return;
  }
  const shown = showAll ? list : list.slice(0, GAP_PREVIEW);
  for (const g of shown) {
    const lo = Math.min(g.p_polls, g.p_market), hi = Math.max(g.p_polls, g.p_market);
    const track = html("div", { class: "gap-track" }, [
      html("span", { class: "span", style: `left:${lo * 100}%;width:${(hi - lo) * 100}%` }),
      html("span", { class: "mark mark-model", style: `left:${g.p_model * 100}%` }),
      html("span", { class: "gap-icon", style: `left:${g.p_polls * 100}%` }, icon("polls")),
      html("span", { class: "gap-icon", style: `left:${g.p_market * 100}%` }, icon("market")),
    ]);
    const short = g.race_id.startsWith("S-") ? `${app.byId[g.race_id].state} Senate` : app.byId[g.race_id].label;
    const row = html("div", { class: "gap-row", tabindex: 0 }, [
      html("span", { class: "gap-label" }, [short,
        html("span", { class: "gap-flag" + (g.status === "FLAG" ? "" : " watch"), text: g.status === "FLAG" ? "flag" : "watch" })]),
      track,
      html("span", { class: "gap-value", text: `${g.gap > 0 ? "+" : "−"}${Math.round(Math.abs(g.gap) * 100)}` }),
    ]);
    bindTip(row, () => tipRows(raceName(g.race_id), [
      ["Polls", `${pct(g.p_polls)} · ${g.n_polls_45d} in 45 days · latest ${g.latest_poll}`],
      ["Markets", pct(g.p_market)],
      ["Our forecast", pct(g.p_model)],
      ["Why it may differ", g.hints || "no obvious data issue"],
    ]));
    row.addEventListener("click", () => setStateFilter(app.byId[g.race_id].state, g.race_id));
    box.append(row);
  }
  more.hidden = list.length <= GAP_PREVIEW;
  more.textContent = showAll ? "Show fewer" : `Show all ${list.length} races`;
  more.onclick = () => renderGaps(list, !showAll);
}

function renderNational(n) {
  const env = $("#nat-env");
  const sig = $("#nat-signals");
  env.replaceChildren();
  sig.replaceChildren();
  if (!n) {
    env.append(html("p", { class: "muted", text: "Appears after the first model run." }));
    return;
  }
  env.append(
    html("h3", { text: "Expected national House margin" }),
    html("div", { class: "env-big", text: `${margin(n.environment)} ± ${n.environment_sd.toFixed(0)}` }),
    html("p", { class: "muted", text: `Trump won the 435 districts by ${Math.abs(n.pres_margin_2024).toFixed(1)} points in 2024. Each seat's fundamentals shift from there.` }),
    html("ul", { class: "kv" }, n.components.map((c) => html("li", {}, [
      html("span", { class: "k", text: `${c.name} · weight ${pct(c.weight)}` }),
      html("span", { class: "v", text: `${margin(c.mean)} (sd ${c.sd.toFixed(1)})` }),
    ]))),
  );
  sig.append(
    html("h3", { text: "Other national signals (cross-checks)" }),
    html("ul", { class: "kv" }, n.signals.map((s) => html("li", {}, [
      html("a", { class: "k", href: s.url, target: "_blank", rel: "noopener", text: s.name }),
      html("span", { class: "v", text: s.value }),
    ]))),
  );
}

// ---------- tables ----------

function emptyRow(cols, text) {
  return html("tr", { class: "empty-row" }, html("td", { colspan: cols, text }));
}

function renderScenarios(list) {
  const body = $("#scenario-body");
  body.replaceChildren();
  if (!list?.length) {
    body.append(emptyRow(6, "Appears after the first model run."));
    return;
  }
  for (const s of list) {
    body.append(html("tr", {}, [
      html("td", { text: s.name }),
      html("td", { class: "num", text: pct(s.p) }),
      html("td", { class: "num", text: pct(s.p_dem_house) }),
      html("td", { class: "num", text: pct(s.p_dem_senate) }),
      html("td", { class: "num", text: s.house_median }),
      html("td", { class: "num", text: s.senate_median }),
    ]));
  }
}

function allRaces() {
  const senate = app.seats.senate.map((s) => ({ seat: s, chamber: "senate" }));
  const house = app.seats.house.map((s) => ({ seat: s, chamber: "house" }));
  return senate.concat(house);
}

function renderRaces(focusId) {
  const body = $("#race-body");
  body.replaceChildren();
  const hasForecast = Object.keys(app.forecast.races ?? {}).length > 0;
  const closeBox = $("#f-close");
  closeBox.disabled = !hasForecast;
  if (!hasForecast) closeBox.checked = false;
  const chamber = $("#f-chamber").value;
  const q = $("#f-search").value.trim().toLowerCase();
  const sort = $("#f-sort").value;
  const gapOf = (id) => {
    const inp = raceForecast(id)?.inputs;
    return inp?.polls && inp?.market ? inp.polls.p - inp.market.p : null;
  };
  const rows = allRaces().filter(({ seat, chamber: c }) => {
    if (chamber !== "all" && c !== chamber) return false;
    if (app.stateFilter && seat.state !== app.stateFilter) return false;
    if (q) {
      const name = app.stateByAbbr[seat.state].name.toLowerCase();
      if (!seat.label.toLowerCase().includes(q) && !name.includes(q)) return false;
    }
    if (closeBox.checked) {
      const rf = raceForecast(seat.id);
      if (!rf || rf.p_dem < 0.05 || rf.p_dem >= 0.95) return false;
    }
    return true;
  });
  if (hasForecast && sort === "close") {
    rows.sort((a, b) => Math.abs(raceForecast(a.seat.id).p_dem - 0.5) - Math.abs(raceForecast(b.seat.id).p_dem - 0.5));
  } else if (hasForecast && sort === "gap") {
    rows.sort((a, b) => Math.abs(gapOf(b.seat.id) ?? -1) - Math.abs(gapOf(a.seat.id) ?? -1));
  }
  const frag = document.createDocumentFragment();
  for (const { seat, chamber: c } of rows) {
    const rf = raceForecast(seat.id);
    const b = rf ? band(rf.p_dem) : null;
    const side = rf?.side ?? "D";
    const name = c === "senate" ? `${app.stateByAbbr[seat.state].name} Senate${seat.special ? " (special)" : ""}` : seat.label;
    const holder = c === "senate" ? (seat.holder === "D" ? "Dem" : "GOP") : seat.new_map_2026 ? "new lines" : "–";
    const prob = rf
      ? html("div", { class: "prob-cell" }, [
          html("span", { class: "prob-track", "aria-hidden": "true" }, html("span", { style: `width:${rf.p_dem * 100}%` })),
          html("span", { text: pct(rf.p_dem) + (side === "I" ? " (I)" : "") }),
        ])
      : "–";
    const inp = rf?.inputs ?? {};
    const gap = gapOf(seat.id);
    const marketCell = html("td", { class: "num input-cell" }, [inp.market ? pct(inp.market.p) : "–",
      gap != null && Math.abs(gap) >= 0.15 ? html("span", { class: "gap-badge", title: "Polls and markets differ by 15 points or more", text: "gap" }) : null]);
    const range = rf?.margin ? `${margin(rf.margin.mean, side)}  (${margin(rf.margin.ci80[0], side)} to ${margin(rf.margin.ci80[1], side)})` : "–";
    const chip = b
      ? html("span", { class: "chip" }, [html("span", { class: "swatch", style: `background:var(--${b.key})` }), rf.rating ?? b.label])
      : html("span", { class: "chip muted" }, [html("span", { class: "swatch pending" }), "No forecast yet"]);
    const tr = html("tr", { id: "row-" + seat.id }, [
      html("td", { text: name }), html("td", { text: holder }),
      html("td", { class: "num" }, prob),
      html("td", { class: "num input-cell", text: inp.polls ? pct(inp.polls.p) : "–" }),
      marketCell,
      html("td", { class: "num input-cell", text: inp.fundamentals ? pct(inp.fundamentals.p) : "–" }),
      html("td", { class: "num", text: range }), html("td", {}, chip),
    ]);
    if (rf) bindTip(tr, () => raceTip(seat, c));
    frag.append(tr);
  }
  if (!rows.length) frag.append(emptyRow(8, "No races match these filters."));
  body.append(frag);
  $("#race-count").textContent = `${rows.length} of 470 races`;
  const clear = $("#f-clear");
  clear.hidden = !app.stateFilter;
  if (app.stateFilter) clear.textContent = `Show all states (now: ${app.stateByAbbr[app.stateFilter].name})`;
  if (focusId) {
    const row = document.getElementById("row-" + focusId);
    if (row) { row.classList.add("highlight"); row.scrollIntoView({ block: "nearest" }); }
  }
}

function setStateFilter(abbr, focusId) {
  tip.hidden = true;
  app.stateFilter = abbr;
  if (location.hash !== "#maps") history.pushState(null, "", "#maps");
  showTab("maps");
  renderRaces(focusId);
  const smooth = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("#race-title").scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
}

function renderBenchmarks(f) {
  const body = $("#bench-body");
  body.replaceChildren();
  if (f.house?.p_dem_control != null) {
    body.append(html("tr", {}, [
      html("td", {}, html("strong", { text: "This forecast" })),
      html("td", { class: "num", text: pct(f.house.p_dem_control) }),
      html("td", { class: "num", text: pct(f.senate.p_dem_control) }),
      html("td", { text: f.meta.updated ? f.meta.updated.slice(0, 10) : "–" }),
    ]));
  }
  for (const b of f.benchmarks ?? []) {
    body.append(html("tr", {}, [
      html("td", {}, b.url ? html("a", { href: b.url, target: "_blank", rel: "noopener", text: b.source }) : b.source),
      html("td", { class: "num", text: pct(b.p_dem_house) }),
      html("td", { class: "num", text: pct(b.p_dem_senate) }),
      html("td", { text: b.as_of ?? "–" }),
    ]));
  }
  if (!body.children.length) body.append(emptyRow(4, "Appears after the first model run."));
}

// ---------- assumptions ----------

function renderAssumptions(list) {
  const body = $("#assump-body");
  body.replaceChildren();
  if (!list?.length) { $("#assumptions").hidden = true; return; }
  let group = null;
  for (const a of list) {
    if (a.group !== group) {
      group = a.group;
      body.append(html("tr", { class: "group-row" }, html("td", { colspan: 4, text: group })));
    }
    body.append(html("tr", {}, [
      html("td", { text: a.name }), html("td", { class: "value", text: a.value }),
      html("td", { text: a.where }), html("td", { class: "muted", text: a.how }),
    ]));
  }
}

// ---------- bridge from the course model ----------

function renderBridge(b) {
  if (!b?.steps?.length) return;
  $("#bridge").hidden = false;
  const w = b.ddhq_weights_competitive;
  $("#bridge-intro").textContent =
    `The course starts from Decision Desk HQ's district probabilities of 22 October (expected ${b.ddhq_sum_p} Democratic seats). ` +
    `In competitive races DDHQ weighs fundamentals ${pct(w.w_fundamentals)}, markets ${pct(w.w_markets)} and polls ${pct(w.w_polls)}. ` +
    `Steps A and B are Parts 2 and 3 of the assignment; each later step changes one thing on the way to our final model (${b.final_step}). ` +
    "The last two rows are for reference: our own fundamentals instead of DDHQ, and model v1 before the backtest.";
  const cols = b.contest.concat(b.check);
  const label = (id) => app.byId[id]?.label ?? id;
  $("#bridge-head").replaceChildren(html("tr", {}, [
    html("th", { text: "Step" }), html("th", { text: "Change" }), html("th", { class: "num", text: "Median" }),
    html("th", { class: "num", text: "80% range" }), html("th", { class: "num", text: "P(majority)" }),
    ...cols.map((c) => html("th", { class: "num", text: label(c) })),
  ]));
  const body = $("#bridge-body");
  body.replaceChildren();
  for (const s of b.steps) {
    const tr = html("tr", s.step === b.final_step ? { class: "final" } : s.step.startsWith("R") ? { class: "reference" } : {}, [
      html("td", { text: s.step }), html("td", { text: s.change }),
      html("td", { class: "num", text: s.median }), html("td", { class: "num", text: `${s.p10}–${s.p90}` }),
      html("td", { class: "num", text: s.p_majority.toFixed(2) }),
      ...cols.map((c) => html("td", { class: "num", text: s[c].toFixed(2) })),
    ]);
    body.append(tr);
  }
}

// ---------- method and sources ----------

function renderMethod(f) {
  const m = f.meta.inputs;
  if (!m) return;
  const set = (k, text) => { const el = document.querySelector(`[data-m="${k}"]`); if (el) el.textContent = text; };
  set("polls", `${m.race_polls} polls of the actual matchups in ${m.senate_with_polls} Senate races and ${m.house_with_polls} House districts, plus ${m.generic_polls} national generic-ballot polls (VoteHub; latest fieldwork ${m.latest_poll}).`);
  set("markets", `Kalshi and Polymarket prices for all ${m.senate_with_market} Senate races and ${m.house_with_market} of 435 House districts, with ${money(m.market_volume_usd)} traded.`);
  set("env", `${margin(m.environment)} ± ${m.environment_sd.toFixed(0)}`);
}

function renderSources(list) {
  const box = $("#source-groups");
  box.replaceChildren();
  const groups = new Map();
  for (const s of list ?? []) {
    if (!groups.has(s.group)) groups.set(s.group, []);
    groups.get(s.group).push(s);
  }
  for (const [name, items] of groups) {
    box.append(html("div", { class: "source-group" }, [
      html("h3", { text: name }),
      html("ul", {}, items.map((s) => html("li", {}, [
        html("a", { href: s.url, target: "_blank", rel: "noopener", text: s.name }),
        html("span", { text: s.role }),
      ]))),
    ]));
  }
}

// ---------- wiring ----------

function render() {
  const f = app.forecast;
  renderHeader(f);
  renderContest(f);
  renderDeciders(f);
  renderCompare(f);
  renderNews(app.news);
  renderAssumptions(f.meta.assumptions);
  renderChamber("house", f.house);
  renderChamber("senate", f.senate);
  renderModelSummary(f);
  renderExplainers(f);
  renderJoint(f.joint);
  renderTipping("senate");
  renderTipping("house");
  renderWatch("senate");
  renderWatch("house");
  renderDist("dist-house", f.house, MAJORITY.house, [190, 260], 10);
  renderDist("dist-senate", f.senate, MAJORITY.senate, [44, 58], 1);
  renderMapLegend();
  renderSenateMap();
  renderHouseMap();
  renderGaps(f.gaps, false);
  renderNational(f.national);
  renderScenarios(f.scenarios);
  renderRaces();
  renderBenchmarks(f);
  renderMethod(f);
  renderSources(f.sources);
}

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

async function init() {
  try {
    app.seats = await loadJSON("data/seats.json");
    app.forecast = await loadJSON("data/forecast.json");
  } catch (err) {
    $(".page").replaceChildren(html("p", { class: "notice", text:
      `The data files could not be loaded (${err.message}). Serve the app folder over HTTP, for example: python -m http.server 8770 --directory app` }));
    return;
  }
  for (const s of app.seats.senate.concat(app.seats.house)) app.byId[s.id] = s;
  for (const st of app.seats.states) app.stateByAbbr[st.abbr] = st;
  try { renderBridge(await loadJSON("data/bridge.json")); } catch { /* bridge is optional (needs the course workbook) */ }
  // Optional extras: candidates and photos, the news check, the 2022/2024 backtest.
  const [cands, news, backtest] = await Promise.all(["data/candidates.json", "data/news.json", "data/backtest.json"]
    .map((p) => loadJSON(p).catch(() => null)));
  app.cands = cands?.races ?? {};
  app.news = news;
  renderBacktest(backtest);

  for (const id of ["f-chamber", "f-close", "f-sort"]) $("#" + id).addEventListener("change", () => renderRaces());
  $("#f-search").addEventListener("input", () => renderRaces());
  $("#f-clear").addEventListener("click", () => { app.stateFilter = null; renderRaces(); });
  addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
  addEventListener("hashchange", () => { showTab(location.hash.slice(1)); if (!app.stateFilter) scrollTo(0, 0); });
  for (const a of document.querySelectorAll("[data-tab]")) a.addEventListener("click", () => { app.stateFilter = null; renderRaces(); });
  showTab(location.hash.slice(1));
  render();
  if (typeof initWhatIf === "function") initWhatIf();  // whatif.js: the weights panel
}

init();
