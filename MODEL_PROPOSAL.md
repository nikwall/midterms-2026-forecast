# Forecasting model: proposal for agreement

Status: **proposal, 26 October 2026**. Nothing is computed until we agree on it.

## The question: forecast every seat, assign confidence, then build scenarios?

Yes, with one essential change: **the seats must be simulated jointly, not one by one.**

In plain language: suppose you give each of 470 races a win probability and add them up as if they were coin flips. The seat total then comes out far too certain, because the luck evens out across hundreds of races. Real elections do not work like that. If the polls underestimate Democrats in Michigan, they usually also do in Ohio, Iowa and a few dozen House seats. The national wave moves everything together. So we keep the per-race probabilities, but draw the errors from shared national, regional and state layers. This leaves each race's probability unchanged and makes the seat distribution realistically wide.

Rigorously: race *i*'s Democratic margin is

margin_i = μ_i + N + R_region(i) + S_state(i) + ε_i

Each term has a mean of zero, apart from μ_i. They have variances σ_N², σ_R², σ_S² and σ_εi², which sum to σ_i², the total uncertainty of race *i*. The terms are drawn from t-distributions with about 5 degrees of freedom, which gives fat tails. P(D wins *i*) = P(margin_i > 0). Adding a common N to all races does not change any single probability, but it does produce a positive correlation between races.

## Pipeline

*Revised 26 Oct after your feedback: we start agnostic between source types, add neighbour polls, single out poll–market gaps, and use other models only to learn from.*

**1. Inputs per race.** Each input is converted to a D win probability. Only these four count as data:

| Input | Coverage | How it becomes a probability |
|---|---|---|
| **Polls** (vote intention), corrected | Senate races, some House seats, generic ballot | corrected average margin → probability, using the historical poll error |
| **Neighbour polls** ("how will your neighbours / friends vote?", "who will win here?") | mostly national and state level | expected vote share → margin → probability |
| **Prediction markets** (Kalshi, Polymarket) | control + many races | mid price, normalised so P(D) + P(R) = 1; thin markets get less weight |
| **Fundamentals** | all seats | district lean (2024 president, **2026 lines**) + national environment + incumbency |

Other models (ElectIt, DDHQ, Silver Bulletin, Split Ticket, The Economist) and expert ratings (Cook, Sabato, Inside Elections) are **not inputs**. We read them to learn how they treat polls, errors and special cases, and show them as benchmarks next to our forecast. Ratings are forecasts too, so the same rule applies to them.

**2. Combining, agnostic about source type.** No source type gets a higher weight a priori. Each input is weighted only by how much information it carries in *that* race:
- the number and recency of polls,
- the trading volume of the market,
- how well the fundamentals have predicted similar seats historically.

Technically this is inverse-variance weighting on the margin scale. A race with ten fresh polls leans on polls; a district with no polls but a liquid market leans on the market. The weights are reported per race.

**2b. Poll–market gaps get their own review.** For every race with both a poll average and a market price, we compare the two probabilities. A gap of 15 percentage points or more (or 0.6 on the log-odds scale) is flagged. We then check the likely reasons by hand: few or old polls, partisan sponsors, candidate news after the polls were fielded, a thin market. The finding goes into PROCESS.md. The dashboard gets a "Where polls and markets disagree" view.

**3. Back to margins.** μ_i = σ_i · Φ⁻¹(p_i). The σ_i is larger for House seats without polls (about 6–7 pts) than for well-polled Senate races (about 4–5 pts).

**4. Correlated simulation.** 50,000 draws. Proposed error split, on the margin in points:
- national: 3.0
- region (Census division): 2.0
- state: 1.5, shared by the Senate race and all House seats in the state
- race-specific: the remainder

We will check these against midterm errors from 2014, 2018 and 2022.

**5. Outputs (what fills the dashboard):**
- P(D House), P(D Senate) and the four joint outcomes (D/D, D-House/R-Senate, R-House/D-Senate, R/R)
- seat distributions with median and 80% / 95% intervals
- the tipping-point seat in each chamber
- per race: P(D), margin with 80% interval, and an **agreement score** (how far apart the inputs are). This is the "confidence" beyond the probability itself.
- scenarios: results conditional on the national error at −2σ, −1σ, 0, +1σ and +2σ, i.e. "polls right", "normal miss" and "historic miss" each way.

**6. Polling corrections** are applied inside our own model, as described in [research/polling_corrections.md](research/polling_corrections.md): house effects, LV/RV, recency, sponsor flag and quality weights, with no directional "unskew".

## Senate specifics

- Democrats need 51 seats, because Vice President Vance breaks ties.
- 34 D-caucus seats are not up, so Democrats need 17 of the 35 races.
- **Nebraska** has an independent challenger. How we count that seat depends on the tournament's resolution rule.
- **Maine** uses ranked-choice voting. **Georgia and Louisiana** can go to runoffs or later elections.

## Decisions

Decided on 26 Oct:
- **Weights:** agnostic between source types; markets are not weighted above polls.
- **Neighbour polls:** included as an input.
- **Poll–market gaps:** flagged and reviewed by hand.
- **Other models and ratings:** used to learn from and shown as benchmarks, not used as data.

Still open:
1. **Directional tilt.** Should the 2025 elections and special elections, where Democrats outran their polls, get a small weight in the national prior, or none?
2. **Nebraska.** Count an independent win as "not R", or as its own category?
3. **FutureSearch.** It is itself a forecasting model, so under the rule above it would be a benchmark only.
4. **Sharing.** The dashboard can be published as a private claude.ai link that you share yourself.

## Timeline (tournament deadline still unknown)

| Day | Work |
|---|---|
| Mon 26 Oct | research, scaffold (done) |
| Tue 27 Oct | data pipeline: markets, ratings, ElectIt, polls, district lean |
| Wed 28 Oct | model v1, simulation, dashboard filled |
| Thu 29 Oct | checks, sensitivity runs, documentation |
| Fri 30 Oct – Mon 2 Nov | daily refresh; final freeze before the submission deadline |
| Tue 3 Nov | Election Day |
