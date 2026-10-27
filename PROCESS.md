# Process and choices

This is the running record of how the forecast was made, which choices we took and why. Entries are dated and the newest come last.

## 26 October 2026: setup and research

**Tournament.** The tournament is HKS-internal. According to Cas it has been open since midnight on 26 Oct. Credit is for the procedure, prizes are for the outcome; our aim is the outcome. Rules, questions and the submission format are not yet known. A web search found no public page for it (searched Harvard/HKS news, Metaculus and the Gazette); the nearest hits were public Metaculus midterm tournaments and Harvard's [ElectIt](https://gking.harvard.edu/electit/) forecast. **To do:** get the announcement from Cas, Canvas or Slack.

**Research done:**
- [research/landscape.md](research/landscape.md): seats at stake, ratings, the 2025–26 redistricting, where the forecasters stand
- [research/sources.md](research/sources.md): data catalogue from seat level to national, with access status
- [research/polling_corrections.md](research/polling_corrections.md): what is known about midterm polling error and corrections

**Choices made:**

| # | Choice | Why |
|---|---|---|
| C1 | Forecast every seat (435 House + 35 Senate) and aggregate by correlated simulation | Seat-level forecasts are the most detailed and verifiable. Correlated errors are needed for honest seat intervals (see [MODEL_PROPOSAL.md](MODEL_PROPOSAL.md)). |
| C2 | Dashboard maps are **tile grids**, not geographic maps | 9 states use new district lines in 2026, so standard district shapefiles are wrong. Tiles also keep small states (RI, DE, NH) visible and render well on phones. |
| C3 | Dashboard is a static page (HTML + JS) that reads `app/data/*.json`, written by a Python pipeline | The model and the display stay separate. The page can be shared as a single link and needs no server. |
| C4 | No directional "unskewing" of polls by default | Past bias has flipped sign between cycles. We use symmetric, fat-tailed, correlated errors instead. Still open, see the proposal. |

**Dashboard scaffold built** ([app/](app/)):
- Sections: control odds per chamber, joint control, seat distributions, Senate and House tile maps, polling-miss scenarios, a table of all 470 races, other forecasts, and sources.
- The page reads `app/data/seats.json` and `app/data/forecast.json`. The forecast file is empty for now, so every number shows "–" and the maps show "No forecast yet".
- A "Demo data" switch loads `forecast_demo.json`. It holds synthetic numbers from `pipeline/demo_forecast.py`, which uses the proposed correlated error layers, so it shows what the real outputs will look like. It is labelled as not a forecast.
- Checked in the browser: desktop and phone width, light and dark theme, no console errors, no horizontal scroll.

**Pending agreement:** the model in [MODEL_PROPOSAL.md](MODEL_PROPOSAL.md).

## 26 October 2026 (evening): your decisions on the model

| # | Choice | Why |
|---|---|---|
| C5 | Source types weighted agnostically. The weights follow the information in each race (inverse variance), not a ranking of source types. | We have no prior reason to trust markets over polls or the reverse. Information content per race is measurable. |
| C6 | Neighbour / social-circle polls added as an input | Asking people how their neighbours or friends will vote captures views that respondents are reluctant to state as their own, and it reaches people outside the sample. |
| C7 | Poll–market gaps of 15 points or more flagged and reviewed by hand | A large gap means one of the two knows something the other does not. Understanding it is where the forecast can gain most. |
| C8 | Other models and expert ratings not used as data, only as benchmarks and to learn from | Avoids double-counting the same polls and herding toward the consensus. Our forecast stays an independent judgement that can be compared with the others. |

The dashboard was opened for your design review. Design feedback is pending.

## 26 October 2026 (night): pipeline v1, markets, polls, gaps

**Neighbour polls.** No public 2026 survey asks the social-circle question ("how will your friends and neighbours vote?"). There are national expectation questions (Pew, Verasight). So this input works at the national level only for now. Details: [research/neighbour_polls.md](research/neighbour_polls.md).

**Scripts.** Run in this order (each with `python -I`):

| Step | Script | Output | Coverage on 26 Oct |
|---|---|---|---|
| 1 | `pipeline/fetch_markets.py` | `data/markets_races.csv`, `data/markets_control.csv`, raw snapshots in `data/raw/` | Senate 35/35 (Kalshi 34, Polymarket 35); House 415/435 (Kalshi 414, Polymarket 22) |
| 2 | `pipeline/fetch_polls.py` | `data/polls_clean.csv`, `data/polls_races.csv`, `data/polls_unmatched.csv` | 744 polls of real matchups; Senate 26/35, House 68/435; generic ballot D+7.4 |
| 3 | `pipeline/gaps.py` | `data/gaps.csv`, [research/gaps_report.md](research/gaps_report.md) | 94 races compared; 34 flagged, 17 watch |

**Choices made while building:**

| # | Choice | Why |
|---|---|---|
| C9 | Polls from VoteHub (open API, CC BY 4.0), not FiftyPlusOne | FiftyPlusOne requires an API key, even on its free tier. VoteHub has 5,958 polls, updated to 23 Oct. |
| C10 | A candidate's party comes from the market listing (Kalshi tags each candidate with a party id). A poll counts only if both sides are today's nominees. | Polls carry candidate names only. The rule also drops hypothetical matchups with primary losers (e.g. Platner or Mills in Maine). |
| C11 | Every race is expressed as the chance of the **non-Republican side** | Nebraska's challenger is an independent (Osborn). This compares polls and markets on equal terms without deciding yet how the seat counts for control. |
| C12 | v1 poll weights: recency (14-day half-life), √sample size, LV 1.0 / RV 0.8 / adults 0.6, partisan or internal polls 0.5, older polls by the same pollster halved | Standard, transparent corrections. House effects and the LV/RV shift come in v2. |
| C13 | Poll-implied probability uses margin error √(4.5² + 7²/n_eff) | 4.5 points of error that more polls cannot remove, plus sampling and pollster noise that shrinks with the effective number of polls. Provisional; to be calibrated on past midterms. |
| C14 | Market consensus is the volume-weighted average of Kalshi and Polymarket, using the mid quote when the spread is at most 10 cents | Liquid venues and tight quotes carry more information. |

**First findings from the gap report:**
- **House gaps are mostly a polling-quality problem.** Most flagged House races have one or two polls, often partisan. A poll-only House forecast is weak; the fundamentals input is needed there.
- **Senate gaps worth a manual review:**

  | Race | Polls | Markets | Note |
  |---|---|---|---|
  | **Alaska** | 57% D | 74% D | 5 recent polls, no warning hints |
  | **Ohio** | 79% D | 68% D | 14 recent polls; polls *more* Democratic than markets |
  | **South Carolina** | 44% | 23% | stale polls |
  | **Mississippi** | 31% | 11% | one poll |
  | **Minnesota** | 72% | 84% | |
  | **Kansas** | 50% | 39% | |

## 26 October 2026 (late): fundamentals input

Script: `pipeline/fundamentals.py`. It writes `data/fundamentals_races.csv`, `data/national_environment.json` and [research/fundamentals_report.md](research/fundamentals_report.md).

**Formula.** For each race: expected margin = lean + national environment + incumbency.
- **lean** = 2024 presidential margin in the district or state minus the national margin (R+1.65 across the 435 districts).
- The probability uses an error of √(environment sd² + race sd²).

**Choices:**

| # | Choice | Why |
|---|---|---|
| C15 | District lean from The Downballot's 2024 presidential results on the **2026 lines** (published 9 Jul 2026, 435 districts). The sheet keeps Missouri's old map, which is correct because the new map is blocked. State lean is the sum of its districts. | The only complete dataset on the new lines. Hand-calculated from precinct data by a respected source. |
| C16 | National environment = generic-ballot polls (D+7.4, sd 3) and Kalshi's House popular-vote market (D+9.0, sd 4.5), weighted by inverse variance → **D+7.9**. The sd is kept at 3.0, not shrunk. | Agnostic between source types (C5). Markets watch polls, so the two are not independent evidence. Special elections and expectation polls are listed as cross-checks only, until we can calibrate how they translate into a national margin. |
| C17 | Incumbency bonus ±3 points of margin for an incumbent on the ballot. "On the ballot" means the incumbent's surname appears among the market's candidates for that district. Where a market lists only parties (Louisiana), we assume the incumbent runs. | Simple and checkable. 336 incumbents found on the ballot, 71 not, 26 assumed. The size is provisional (from background knowledge: the incumbency advantage has shrunk to a few points); to be calibrated. |
| C18 | Race-level error: 6 points for House, 7 for Senate. Uniform swing from 2024. | Provisional, to be checked against 2018 and 2022. The Senate gets more, because candidates matter more there. |

**What the comparison shows** (things to learn from, not to copy):
- **House total.** Fundamentals give 235 expected Democratic seats. Using markets where they exist gives 243.
- **Candidate effects.** The largest House differences involve strong incumbents: Fitzpatrick in PA-01 (fundamentals 85% D, market 44%), Lawler in NY-17. In the Senate, Collins in Maine, Brown in Ohio, and the open Texas and Alaska races show the same.
- **Differential swing.** South Texas (TX-15, TX-28, TX-34) and some rural seats (IA-01, OH-07) are far more Democratic in markets than in fundamentals. Uniform swing assumes every seat moves alike. Hispanic areas swung most toward Trump in 2024 and may swing back most. **Possible v2 improvement:** swing by demographic group instead of uniformly.
- **Weighting.** In candidate-driven Senate races, fundamentals should carry little weight. Inverse-variance weighting already does this, because their error (≈7.6) is larger than that of a well-polled average (≈5).

## 26 October 2026 (night): model v1 and the filled dashboard

Script: `pipeline/model.py`. It writes `app/data/forecast.json` and `data/model_races.csv`.

**Result, model v1 (26 Oct, 20,000 simulations):**

| | Chance of a Democratic majority | Median Dem seats | 80% range | 95% range | Tipping-point seat |
|---|---|---|---|---|---|
| House | 93.6% | 238 | 221–257 | 210–272 | NC-01 |
| Senate | 64.6% | 51 | 48–54 | | Alaska |

Joint control: D both 64.6%; D House + R Senate 29.0%; R both 6.4%. For comparison (not inputs): Kalshi 91% / 64%, Polymarket 92% / 65%, DDHQ 79% / 56%.

**Choices:**

| # | Choice | Why |
|---|---|---|
| C19 | Markets and polls on **one scale**. A market counts like a poll average with n polls: $20k traded = 1 poll, $1M = 10 polls (log scale), never more than 10. Its error uses the poll formula √(4.5² + 7²/n). | The first version treated every liquid market like an infinitely polled race, which gave markets about 50% of the weight vs 39% for polls in the top Senate races. That contradicted C5. Now, in the best-polled Senate races, polls and markets get about 43–45% each and fundamentals about 12%. Markets lead only where polls are thin (KS, SC, MS). |
| C20 | Simulation errors: a **national** error of ±3 points (the uncertainty of the national environment, t-distributed with 5 degrees of freedom) hits every race in full. The rest of each race's variance is split 25% Census division, 25% state, 50% the race itself. | A first version made the national part a fixed share of each race's variance. Well-polled races then carried only ±2.5 points of national error, less than the environment's own uncertainty, and gave a too-certain House (96.5%). |
| C21 | A combined race can never be more certain than ±4 points | The three inputs overlap (markets read polls; fundamentals and polls share the national environment), so their precisions cannot simply be added. |
| C22 | Senate fundamentals error widened from 7 to 9 points | Senate results stray far from presidential partisanship when candidates are strong or weak (Maine's Collins being the clearest case). |
| C23 | Nebraska: a win by the independent Osborn counts as "not Republican" in the race, but **not** as a Democratic seat for Senate control | He says he will not caucus with either party. The same applies to the independents in Montana and Idaho. |
| C24 | Tipping-point seat = the seat that most often delivers the 218th (or 51st) seat across the simulations | Standard definition. |

**Dashboard:**
- Filled with model v1. New sections: "Where polls and markets disagree" (one row per race with polls, market and our forecast on one scale) and "National environment".
- The race table now shows polls, markets and fundamentals per race, marks gaps of 15 points or more, and sorts by closeness or by gap.
- Checked in the browser at desktop and phone width, no layout overflow.

## 27 October 2026: redesign and explanations

The tournament instructions were still missing on 27 Oct.

**Design.**
- Slim, light arq look: white page, one font (Roboto 300/400), anthracite text (#2f3639).
- Blue shades for Democratic seats; arq crimson shades (#bb2649 down to a light rose) for Republican ones. Arq green marks links and markets.
- No capitals. The title sits in a slim top line with section links.

**Removed:**
- the countdown to Election Day,
- the "Live forecast" badge,
- the demo-data switch (its file and script `demo_forecast.py` were deleted),
- "Computational Policy Analysis".

**Added explanations:**
- why 20,000 simulations and how stable the results are,
- what the tipping-point seat is and why this one,
- what the intervals mean,
- what safe, likely, lean and toss-up mean (with the ranges also in the map legend),
- a "How the forecast works" section (plain-language summary, six steps, process timeline),
- a source list with links, grouped by role.

**Choices:**

| # | Choice | Why |
|---|---|---|
| C25 | Robustness check in every model run: the analytic simulation noise (±0.3 pts House, ±0.7 pts Senate, 95%) plus four re-runs with other random seeds | On 27 Oct the re-runs stayed within 0.4 pts (House) and 0.8 pts (Senate). Median seats moved by at most one. So 20,000 simulations are enough; the real uncertainty comes from the inputs. |
| C26 | Tipping-point seat reported with its share of simulations and the runners-up | The House tipping point is diffuse: NC-01 decides in only 3.7% of simulations, just ahead of MI-07, IA-01, PA-07 and AZ-01. Showing a single seat without that context would overstate its importance. In the Senate: Alaska 17%, Texas 17%, Ohio 15%. |
| C27 | Numbers in the method text (poll counts, coverage, environment) are read from the forecast file | The text stays true after every data refresh. |

**Second round of feedback, 27 Oct:**

| # | Choice | Why |
|---|---|---|
| C28 | Rating bands narrowed to **toss-up 45–55%, lean 55–65%, likely 65–95%, safe 95%+**. The common convention (Split Ticket: toss-up below 60%, lean to 80%, likely to 95%) is named in the explainer. | Your preference. Narrower bands give more races a direction. The bands are fixed probability cutoffs and are unrelated to state-level poll uncertainty. On 27 Oct: 11 Senate races and 73 House districts are not safe. |
| C29 | The single tipping-point seat is removed from the chamber cards. Instead, a chart per chamber shows each race's tipping-point share, ordered from most Democratic to most Republican, with the smallest group deciding at least half of all simulations highlighted. The model now stores the full distribution. | One seat with 3.7% says little. The distribution shows where control is decided. Senate: Alaska, Texas, Ohio or Maine decide 62% of simulations. House: 15 districts decide 51%. |
| C30 | Non-safe races listed above the map, grouped by band from most Democratic to most Republican | Makes the races that matter visible at a glance. |
| C31 | A four-step summary "How this forecast is made" placed right under the headline, with live numbers and average input weights, linking to the full method | The model was not visible enough at the bottom of the page. |

**Model explained and sensitivity analysis, 27 Oct.** You asked what kind of model this is and how to judge the weights. The answer is written up in [research/model_explained.md](research/model_explained.md).

| # | Choice | Why |
|---|---|---|
| C32 | `model.py` restructured into `load_data()`, `build_races(cfg)` and `simulate()`. Every assumption sits in one settings dict (`DEFAULT_CFG`). Model v1 results are unchanged. | Lets the same code run with other assumptions. |
| C33 | `pipeline/sensitivity.py` runs 24 variants, each changing one assumption, all with the same random draws. Output: `data/sensitivity.csv`, [research/sensitivity_report.md](research/sensitivity_report.md). | Shows which assumptions matter. **House:** 89–98% in every variant. **Senate:** 54–69% in every reasonable variant, but 38% with fundamentals alone. Senate drivers: weight on fundamentals and the floor on race uncertainty. The poll-vs-market split barely matters. |
| C34 | No ARIMA. History should instead calibrate the assumed constants (backtest on past cycles); a state-space poll average is an option. | Late-campaign poll averages behave close to a random walk, which the model already assumes. There are too few midterms for ARIMA on the national level. |

## 27 October 2026: the contest rules arrive

The entry form (see README) settles the open questions:
- **What is scored:** only the House. (a) Democratic seat count, ranked by closeness. (b) P(Democratic majority). (c) P(Democrat wins) in NC-01, NC-11, OH-07, PA-08 and NY-17. The six probabilities form a Brier-score tiebreaker.
- **Deadline:** 7:00 AM ET, Tuesday 3 Nov.

**Backtest, first run (paused for the rules discussion, not yet adopted):**
- **Poll error:** Senate-midterm poll errors fit base 2.4 and per-poll 9.7, against 4.5 and 7 in v1.
- **National error:** the generic-ballot error across midterms has an RMS of 3.6, against 3.0 in v1.
- **Poll vs fundamentals weight:** in 1998–2022 Senate midterms the best fixed poll weight was 0.8 (margin RMSE 5.8). Our inverse-variance rule averages 0.87 (RMSE 5.9), so the rule is close to the best fixed weight.
- **To fix before use:** the 2024 market check matched only 5 races (party mapping), and the Senate fundamentals regression (incumbency 11, race error 16) looks inflated.

| # | Choice | Why |
|---|---|---|
| C35 | The page now opens with "Our contest entry": (a) seats, (b) P(majority), (c) the five districts. Each district shows the inputs, weights, expected margin and automatic warnings. "Contest entry" is the first link in the top line. The model writes a `contest` block into `forecast.json`. | Your request: the tournament answers come first. |
| C36 | (a) is the **median** of the simulated seat counts | Teams are ranked by distance to the true count; the median minimises the expected absolute distance. The mean (238.5) suits squared error; the most frequent count (236) occurs in only about 3% of simulations. |
| C37 | Probabilities are shown with two decimals, as entered in the form | The Brier tiebreaker rewards honest probabilities, so no rounding toward 0 or 1. |

**Assignment instructions found (27 Oct, `Extra Credit Assignment _ Election forecasting 2026.pdf`):**
- Parts 1–4.
- **Part 1 must be done by hand, without AI.** Claude did not check the hand solution.
- Parts 2–3 build a simulation from Decision Desk HQ's district probabilities (22 Oct, course workbook), first as independent coin flips, then with a correlation parameter α.
- Part 4 is the contest entry, plus (d) the model description and (e) the AI-use description.
- Alaska's Bill Hill does not count as a Democrat in the seat total.

**Fixes after comparing with other forecasters:**

| # | Choice | Why |
|---|---|---|
| C38 | Kalshi House markets are recognised by their title ("XX-NN House winner?"), not by series name | Eleven districts, including the contest district NC-11, were listed under a series name the fetcher did not know. Coverage rose from 415 to 425 districts. NC-11 moved from 0.32 to 0.92. |
| C39 | Alaska at-large: Hill and Begich mapped to their parties by hand for the polls; a Hill win counts as "not Republican" but **not** as a Democratic seat. Only Democratic wins count toward the 218. | Assignment footnote 12. The 10 Alaska polls were previously dropped. |
| C40 | Comparison with other forecasters: [research/benchmarks_comparison.md](research/benchmarks_comparison.md). Fundamentals diagnosis: [research/fundamentals_diagnosis.md](research/fundamentals_diagnosis.md) (`pipeline/diagnose_fundamentals.py`). | Your request to see how we compare and why the fundamentals sit so far from polls and markets. |

**Bridge from the course model, packaging (27 Oct evening):**

| # | Choice | Why |
|---|---|---|
| C41 | `pipeline/bridge.py` goes from the course's Part 3 model to ours, one change per step. It starts from the course workbook (DDHQ probabilities of 22 Oct; Part 3 tab preset to regional waves with α = 0.4). Output: [research/bridge_report.md](research/bridge_report.md) and a table on the page. | Your request: start where the course starts and show how we arrive at our answers. |
| C42 | What the bridge shows: | |
| | – Part 3 (α = 0.4) gives P(majority) 0.96. Our correlation on DDHQ's probabilities gives 0.84, close to DDHQ's own 0.79. | Our error structure is in line with DDHQ's spread. |
| | – Our uniform-swing fundamentals give TX-15 0.05, against DDHQ 0.45 and the market 0.82. | Our fundamentals miss South Texas. |
| | – Markets and polls move the five districts from about 0.5 to 0.8–0.9. | |
| | – Alternative G (DDHQ in place of our fundamentals, plus markets and polls) gives 237 seats and P(majority) 0.93, with NY-17 at 0.64. | |
| | – DDHQ's own blend in competitive races: fundamentals 71%, markets 25%, polls 4%. | |
| C43 | Reproducible package: `run_all.py` (one command), `requirements.txt` (numpy, openpyxl), a GitHub Actions workflow "Update forecast" (manual button, optional daily schedule) and "Deploy dashboard" (GitHub Pages). | Your request: anyone with access can run the model. |
| | **Not published:** raw downloads, the course workbook and PDF, the contest form link. | Course material is not ours to publish; strangers should not be able to submit entries. |

| C44 | "Try your own weights" panel (`app/whatif.js`). It re-runs the House model in the browser (10,000 simulations, fixed random seed) with three sliders (polls, markets, fundamentals, ×0 to ×3 on each source's precision) and a fundamentals switch (ours / DDHQ 22 Oct). "Reset to our final model" restores the defaults. At the defaults it reproduces the official numbers (238, 0.94, districts within 0.01). With DDHQ it reproduces bridge step G. | Your request: make the fundamentals source and the weights a choice for the viewer, with a way back to our model. |
| | The DDHQ file (`app/data/ddhq.json`) is kept out of the repository for now, so on the public site the DDHQ switch is greyed out. | The 435 probabilities come from DDHQ via the course workbook; publishing them is your call. |

| C45 | Published on 27 Oct as a public repository [nikwall/midterms-2026-forecast](https://github.com/nikwall/midterms-2026-forecast) with the dashboard on GitHub Pages: https://nikwall.github.io/midterms-2026-forecast/. Commits are signed with the GitHub noreply address. | Your request to host the app on your GitHub. Free Pages requires a public repository, which you approved. |

**Discussion of fundamentals and weights (27 Oct, late):**

| # | Finding or choice | Detail |
|---|---|---|
| C46 | Backtest market check fixed | Polymarket sometimes names only the party; fusion candidates (one candidate on several party lines) are now added up across lines. Polymarket 2024 Senate, 33 races one week out: Brier 0.034, margin error in the 14 close races 3.4 points. For comparison, Senate polls in midterms 1998–2022: Brier 0.044, close-race error 5.5 points. Different years, so indicative only. |
| C47 | Evidence on fundamentals | **Senate midterms:** fundamentals alone miss by 14.3 points (RMS) and polls alone by 6.6. A blend of 80% polls and 20% fundamentals is best (5.8); our inverse-variance rule lands close to it (0.87 poll weight, 5.9). **Senate fundamentals calibration:** incumbency bonus about 11 points and race error about 16 (v1: 3 and 9), so our Senate fundamentals are overconfident. **House fundamentals:** not calibrated (no results file). |
| C48 | Candidate final settings and their answers (seats, P(majority), NC-01 / NC-11 / OH-07 / PA-08 / NY-17) | 1. v1: 238, 0.94, .89/.92/.82/.77/.79 · 2. v1 + DDHQ as fundamentals: 237, 0.93, .90/.92/.89/.83/.64 · 3. calibrated constants (poll error 2.4/9.7, national ±3.6, Senate fundamentals error 16): 238, 0.90, .87/.89/.82/.78/.77 · **4. calibrated + DDHQ as fundamentals: 236, 0.90, .88/.90/.88/.84/.63** · 5. as 4 with markets ×1.5: 236, 0.92, .88/.90/.89/.86/.63 |

## 27 October 2026 (night): final model v2 (option 4)

| # | Choice | Why |
|---|---|---|
| C49 | **Final model v2:** poll errors ±2.4 (irreducible) and ±9.7 (per poll); national error ±3.6; Senate fundamentals race error ±16; **House fundamentals = DDHQ's district probabilities (22 Oct)**, placed on the margin scale (±7.0). Incumbency stays 3 (Senate only now); the backtest's 11 is not adopted. Markets ×1. Our own House fundamentals remain available (panel switch, bridge row R1). | Your choice, option 4. **Error sizes:** from the backtest (C46–C48). **DDHQ:** the course's starting point, and better than our uniform swing in the House. **Incumbency 3:** kept as in the option you chose; the Senate is not scored. |
| C50 | The page lists every assumption ("Our assumptions"): value, where it enters, how we derived it. The list is written by the model, so it always matches the code. | Your request. |
| C51 | More compact page: base font 14 px, smaller headings, tables and explanations, tighter spacing. The contest answers stay large and are coloured. | Your request: see more at once, important numbers more prominent. |
| C52 | DDHQ's district probabilities are stored in `data/ddhq_house_2026-10-22.csv`; `pipeline/ddhq_import.py` re-creates it from the workbook. | Needed so that everyone, including GitHub Actions, can run the final model. **Publishing them needs your OK** (they come from DDHQ via the course). |

**Final model v2, contest answers on 27 Oct (fresh data):**

| Question | Answer |
|---|---|
| (a) Democratic seats | **236** (80%: 218–263) |
| (b) P(majority) | **0.91** |
| NC-01 | 0.88 |
| NC-11 | 0.90 |
| OH-07 | 0.89 |
| PA-08 | 0.84 |
| NY-17 | 0.63 |

Sensitivity (24 variants): House 0.87–0.94 for reasonable choices; v1 settings 0.94.

**Entry as of 27 Oct (model v1, before calibration and the district review):**

| Question | Answer |
|---|---|
| (a) Democratic seats | 238 |
| (b) P(majority) | 0.94 |
| NC-01 | 0.89 |
| NC-11 | 0.32 |
| OH-07 | 0.83 |
| PA-08 | 0.75 |
| NY-17 | 0.79 |
