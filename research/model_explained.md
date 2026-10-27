# What model we use, and how sure we can be about it

Written 27 October 2026, for model v1. The numbers come from `pipeline/model.py` and `pipeline/sensitivity.py`.

> **Update, final model v2 (27 Oct, PROCESS.md C49):** the structure below is unchanged. What changed:
> - The error sizes are now calibrated in the backtest: poll errors ±2.4 / ±9.7, national error ±3.6, Senate fundamentals ±16.
> - The House fundamentals are Decision Desk HQ's district probabilities instead of our uniform swing.
>
> The current assumptions are listed on the dashboard, and the current sensitivity table is in [sensitivity_report.md](sensitivity_report.md).

## In plain language

There is no machine learning in the model: no trees, no forests, no neural network. There is also no regression fitted to past elections. The model has three steps:

1. **Measure.** Each source is turned into the same kind of statement: "the Democrat (or the non-Republican side) wins this race by X points, give or take Y."
   - Polls give X as a weighted poll average.
   - Markets give X by translating the price into a margin.
   - Fundamentals give X from a fixed rule: the 2024 result, plus the national swing, plus the incumbency bonus.
2. **Combine.** The three statements are averaged per race. A statement with a small "give or take" counts more. This is the textbook way to pool estimates of the same quantity. A meta-analysis does the same, and so does a Bayesian update with normal errors.
3. **Simulate.** 20,000 times, every race gets a random error. Part of that error is shared nationally, part regionally, part by state, and part is the race's own. Then we count the seats.

The model is simple in structure and transparent. Its weakness is that the **sizes of the errors (the "give or take") are assumptions**, informed by the literature but not estimated from data. The weights follow from those assumptions. So the honest description is: a judgement-calibrated evidence synthesis with a correlated Monte Carlo, not an estimated statistical model.

## Rigorous version

For race *i* and source *k* ∈ {polls, market, fundamentals}:

- Each source gives an estimated margin *m_ik* with error *σ_ik*.
- Combined margin: μ_i = Σ_k w_ik · m_ik, with weights w_ik = (1/σ_ik²) / Σ_j (1/σ_ij²).
- Combined error: σ_i = max(4, (Σ_k 1/σ_ik²)^(-1/2)).
- Simulation: margin_i = μ_i + 3·T + r_i · (√0.25·D_div(i) + √0.25·S_state(i) + √0.5·E_i), with r_i = √(σ_i² − 3²).
  - T ~ t₅, rescaled to variance 1, is shared by all races.
  - D, S and E are independent standard normal draws.
- A race is won if margin_i > 0. Control: House ≥ 218 Democratic seats; Senate ≥ 51, counting the 34 Democratic seats not up.

**Where each σ comes from**

| Source | σ (margin points) | From data | Assumed |
|---|---|---|---|
| Polls | √(4.5² + 7² / n_eff) | n_eff, the effective number of polls (Kish), after weighting by recency, sample size, population and sponsor | 4.5 = error no number of polls removes; 7 = noise of one poll incl. pollster lean |
| Markets | √(4.5² + 7² / n_equiv) | trading volume | the exchange rate: $20k traded = 1 poll, $1M = 10 polls (log scale), never more than 10 |
| Fundamentals | √(3² + 6²) = 6.7 House; √(3² + 9²) = 9.5 Senate | – | 3 = uncertainty of the national environment; 6 / 9 = how far races stray from uniform swing |

**Where the weights are applied:** `combine()` in `pipeline/model.py`, called by `build_races()` for each race. Its output (μ_i, σ_i) is the only thing the simulation (`simulate()`) sees.

**Example, Texas Senate.**

| Source | Margin | σ | Weight |
|---|---|---|---|
| Polls (44 polls, n_eff 13.7) | D+2.1 | 4.9 | 45% |
| Market (64.5%, $50M traded) | D+1.9 | 5.1 | 43% |
| Fundamentals | R+4.2 | 9.5 | 12% |

The market counts as 10 polls (the cap) and its margin is σ × the probit of 64.5%. Combined: D+1.2 ± 4, which gives a 62–63% chance.

## How to judge whether the market and poll weights make sense

1. **Sensitivity.** Does the answer depend on the choice? Doubling either the market or the poll weight moves the Senate by at most 1.4 points and the House by at most 1.1. Today it hardly matters, because where both sources exist they mostly agree. What does matter is how much the fundamentals count, and the size of the uncertainty (see below).
2. **Backtest.** This is the proper test. On past cycles with known results, compute each source's error race by race. Then find the weights that would have minimised the Brier or log score.
   - Data that exists: FiveThirtyEight's archive of final polls with results, closed Kalshi, Polymarket and PredictIt race markets (2022, 2024), and fundamentals for 2022 and 2024.
   - Limit: few close races per cycle, so the weights will be estimated with wide error bars.
3. **Literature as a prior.** Aggregates beat single sources (PollyVote, Graefe). Close to Election Day, poll averages and markets perform similarly. Down-ballot markets are thin and were less accurate in 2024.

## Would an ARIMA element help?

ARIMA forecasts a variable from its own history, assuming the past pattern of movement continues. There are three places "history" could enter:

- **The poll average over the campaign.** Late in a campaign, poll averages move almost like a random walk (Erikson and Wlezien). The best forecast for Election Day is then today's level with growing uncertainty, which is what ARIMA(0,1,0) says and what we already assume. Extrapolating a trend one week ahead mostly chases noise. The better tool here is a state-space model (Kalman filter) for the poll average: it weighs old against new polls properly and can pool across races. It would be the principled version of our 14-day half-life.
- **The national environment across past midterms.** There are only 20 midterms since 1946, with structural breaks, which is too short for ARIMA. The standard is a small regression, e.g. seat change on presidential approval and the generic ballot.
- **Each district's own past.** This is where history pays off most. Past results (2018, 2020, 2022) can calibrate our assumed constants: the incumbency bonus, how far races stray from uniform swing, and the size of polling errors.

**Recommendation:** no ARIMA. Use history to calibrate the constants (backtest), and optionally replace the poll weighting with a state-space average.

## Sensitivity: what moves the forecast

The full table is in [sensitivity_report.md](sensitivity_report.md). It covers 24 variants, each changing one assumption, all with the same random draws. Baseline: House 93.6%, Senate 64.6%.

| What changes | Dem House | Dem Senate |
|---|---|---|
| **Which sources** | | |
| Without markets | 91.8% | 62.4% |
| Without polls | 93.5% | 59.2% |
| Without fundamentals | 89.3% | 67.2% |
| Polls alone (fundamentals where no polls) | 95.7% | 69.1% |
| Markets alone (fundamentals where no market) | 89.1% | 61.6% |
| Fundamentals alone | 91.5% | 38.3% |
| **How to weight** | | |
| Equal weights | 93.1% | 54.2% |
| Markets count double | 94.7% | 65.3% |
| Polls count double | 93.6% | 66.0% |
| Markets worth at most 3 polls | 93.9% | 65.8% |
| **Uncertainty** | | |
| National error ±2 instead of ±3 | 97.6% | 66.3% |
| National error ±4 | 89.3% | 64.4% |
| Race floor ±3 instead of ±4 | 93.4% | 68.4% |
| Race floor ±5 | 94.0% | 61.6% |
| **Fundamentals** | | |
| Environment 2 pts more Republican | 90.4% | 61.1% |
| Environment 2 pts more Democratic | 95.6% | 67.8% |
| No incumbency bonus | 94.3% | 67.3% |

Reading:

- **House.** Democrats are favoured in every variant (89–98%). The biggest lever is the size of the national error. With ±4 instead of ±3, the chance drops to 89%.
- **Senate.** Every reasonable variant lands between 54% and 69%. Only "fundamentals alone" (38%) falls outside, because fundamentals miss the candidates: Texas, Ohio and Alaska lean Republican on 2024 results but have strong Democratic nominees.
- **The two choices that matter most for the Senate:**
  - how much the fundamentals count: equal weights give 54%, information weights 65%;
  - how certain a race can be: the floor of ±3 to ±5 moves the Senate between 62% and 68%.

  The poll-versus-market split matters least.
