# From the course's Part 3 model to our final model

Each step changes one thing. Seats are Democratic seats over 20,000 simulations (same random draws in every step).

DDHQ's probabilities add up to 235.6 expected Democratic seats. In competitive races (10–90%) DDHQ's own blend weights are polls 4%, markets 25%, fundamentals 71%.

| Step | Change | Mean | Median | 80% range | P(majority) | NC-01 | NC-11 | O07 | PA-08 | NY-17 | TX-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Part 2: DDHQ probabilities, independent coin flips | 235.6 | 236 | 230–242 | 1.00 | 0.59 | 0.52 | 0.47 | 0.54 | 0.59 | 0.45 |
| B | Part 3: regional waves (Option 1), alpha = 0.4 | 235.4 | 234 | 223–249 | 0.96 | 0.59 | 0.51 | 0.47 | 0.54 | 0.59 | 0.46 |
| C | Our correlation (national ±3.6, division, state, race); Hill not a Democrat | 234.9 | 233 | 211–262 | 0.82 | 0.59 | 0.52 | 0.48 | 0.53 | 0.59 | 0.45 |
| D | + prediction markets, weighted by information | 237.3 | 235 | 218–260 | 0.90 | 0.83 | 0.84 | 0.82 | 0.83 | 0.63 | 0.75 |
| E | + polls = our final model | 238.5 | 236 | 218–263 | 0.91 | 0.88 | 0.90 | 0.89 | 0.84 | 0.63 | 0.80 |
| R1 | For reference: final model with our own uniform-swing fundamentals instead of DDHQ | 239.1 | 238 | 218–261 | 0.91 | 0.87 | 0.90 | 0.84 | 0.79 | 0.77 | 0.61 |
| R2 | For reference: model v1 (own fundamentals, error sizes before the backtest) | 239.1 | 238 | 221–257 | 0.94 | 0.90 | 0.92 | 0.82 | 0.78 | 0.79 | 0.58 |
