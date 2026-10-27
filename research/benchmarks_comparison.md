# How our contest answers compare with other forecasters

Collected 27 October 2026. Other models are shown for comparison only, not as inputs (C8). Note that the course's own basic model starts from Decision Desk HQ's district probabilities (see the assignment).

## House totals

| Source | Dem seats | P(majority) | As of |
|---|---|---|---|
| **Our model (v1)** | **238** (median; 80%: 221–257) | **0.94** | 27 Oct |
| Decision Desk HQ | 238 (projected) | 0.79 | 26 Oct |
| Kalshi seat-count market | 238.3 (average) | 0.91 (control market) | Oct |
| ElectIt (Ebanks, Katz, King) | 239 (median) | n/a | Oct |
| Poliwave | 230 (80%: 216–247) | 0.87 | 25 Oct |
| Cook Political Report (implied by its ratings) | 227–237 | n/a | Oct |

Sources: [DDHQ](https://votes.decisiondeskhq.com/forecast/2026/house), [Kalshi](https://news.kalshi.com/p/2026-midterm-odds-democrats-forecast-win-house-238-seats), [ElectIt](https://gking.harvard.edu/electit/), [Poliwave](https://www.poliwave.com/us/fed/projection), [NewsOn6 / Cook](https://www.newson6.com/national-politics-oklahoma/one-week-away-the-stakes-if-the-midterm-elections-loom-large).

**Reading.**
- Our seat count matches DDHQ, Kalshi's seat market and ElectIt.
- Our majority probability (0.94) is higher than DDHQ's (0.79) and close to Kalshi's (0.91), so our seat distribution is narrower than DDHQ's.

## The five contest districts

| District | Our answer | Markets | Polls | Expert consensus (270toWin, 23 Oct) | Other models |
|---|---|---|---|---|---|
| NC-01 | 0.89 | 0.83 | 0.89 (1 poll) | Toss-up | |
| NC-11 | 0.92 | 0.86 | 0.94 (Emerson, 14 Oct: Ager +13) | Leans R (Cook moved it to Lean D on 27 Oct) | DDHQ 0.51; smarter.vote 0.63 |
| OH-07 | 0.82 | 0.85 | 0.89 (last poll Aug) | Toss-up | |
| PA-08 | 0.77 | 0.85 | 0.68 | Toss-up | |
| NY-17 | 0.79 | 0.58 | 0.58 | Toss-up | |

Sources: [270toWin consensus](https://www.270towin.com/2026-house-election/table/consensus-2026-house-forecast), [DDHQ NC-11](https://votes.decisiondeskhq.com/races/2026-11-03/north-carolina-us-house-11-general-election/forecast), [Kalshi NC-11](https://kalshi.com/markets/kxhousenc11/house-nc-11/kxhousenc11-26), [smarter.vote](https://smarter.vote/races/nc-house-11-2026/).

**Reading.**
- The experts call four of the five races toss-ups. Markets and polls lean clearly Democratic.
- The assignment's own data point shows the same gap: DDHQ gave TX-15 45% on 22 Oct, while the market pays about 82%.
- For the Brier tiebreaker this is the key risk. If the experts are right, numbers around 0.8–0.9 cost us. If markets and polls are right, they pay off.

## Data fixes found while comparing (27 Oct)

- **NC-11 and ten other districts had markets my fetcher missed.** Kalshi lists them under different ticker names. Coverage is now 425 of 435 districts.
- **NC-11 had a poll we dropped** (Emerson, Ager +13). It also had a wrong incumbency assumption: Edwards is not on the ballot. Its answer moved from 0.32 to 0.92.
- **Alaska at-large:**
  - 10 polls were dropped because no market names Hill and Begich. They now count.
  - Hill (nonpartisan, endorsed by Democrats) is now counted as "not Republican" but not as a Democratic seat, as the contest instructions require.
