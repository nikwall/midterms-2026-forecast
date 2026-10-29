# From the course's Part 3 model to our final model

Each step changes one thing. Seats are Democratic seats over 20,000 simulations (same random draws in every step).

DDHQ's probabilities add up to 235.6 expected Democratic seats. In competitive races (10–90%) DDHQ's own blend weights are polls 4%, markets 25%, fundamentals 71%.

| Step | Change | Mean | Median | 80% range | P(majority) | NC-01 | NC-11 | O07 | PA-08 | NY-17 | TX-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Part 2: DDHQ probabilities, independent coin flips | 235.6 | 236 | 230–242 | 1.00 | 0.59 | 0.52 | 0.47 | 0.54 | 0.59 | 0.45 |
| B | Part 3: regional waves (Option 1), alpha = 0.4 | 235.4 | 234 | 223–249 | 0.96 | 0.59 | 0.51 | 0.47 | 0.54 | 0.59 | 0.46 |
| C | Our correlation (national ±3.6, division, state, race); Hill not a Democrat | 234.9 | 233 | 211–262 | 0.82 | 0.59 | 0.52 | 0.48 | 0.53 | 0.59 | 0.45 |
| D | + prediction markets, weighted by information | 238.4 | 236 | 218–262 | 0.91 | 0.83 | 0.82 | 0.81 | 0.89 | 0.65 | 0.81 |
| E | + polls = our final model | 239.4 | 237 | 219–264 | 0.91 | 0.84 | 0.88 | 0.83 | 0.88 | 0.65 | 0.85 |
| R1 | For reference: final model with our own uniform-swing fundamentals instead of DDHQ | 240.0 | 239 | 218–262 | 0.91 | 0.84 | 0.88 | 0.74 | 0.84 | 0.76 | 0.69 |
| R2 | For reference: model v1 (own fundamentals, error sizes before the backtest) | 239.9 | 239 | 222–258 | 0.94 | 0.83 | 0.91 | 0.72 | 0.83 | 0.79 | 0.66 |
