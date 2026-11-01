# From the course's Part 3 model to our final model

Each step changes one thing. Seats are Democratic seats over 20,000 simulations (same random draws in every step).

DDHQ's probabilities add up to 235.6 expected Democratic seats. In competitive races (10–90%) DDHQ's own blend weights are polls 4%, markets 25%, fundamentals 71%.

| Step | Change | Mean | Median | 80% range | P(majority) | NC-01 | NC-11 | O07 | PA-08 | NY-17 | TX-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Part 2: DDHQ probabilities, independent coin flips | 235.6 | 236 | 230–242 | 1.00 | 0.59 | 0.52 | 0.47 | 0.54 | 0.59 | 0.45 |
| B | Part 3: regional waves (Option 1), alpha = 0.4 | 235.4 | 234 | 223–249 | 0.96 | 0.59 | 0.51 | 0.47 | 0.54 | 0.59 | 0.46 |
| C | Our correlation (national ±3.6, division, state, race); Hill not a Democrat | 234.9 | 233 | 211–262 | 0.82 | 0.59 | 0.52 | 0.48 | 0.53 | 0.59 | 0.45 |
| D | + prediction markets, weighted by information | 239.2 | 237 | 219–263 | 0.91 | 0.85 | 0.82 | 0.81 | 0.85 | 0.65 | 0.82 |
| E | + polls = our final model | 240.2 | 238 | 219–265 | 0.91 | 0.87 | 0.88 | 0.83 | 0.85 | 0.65 | 0.86 |
| R1 | For reference: final model with our own uniform-swing fundamentals instead of DDHQ | 241.0 | 240 | 219–264 | 0.91 | 0.86 | 0.88 | 0.74 | 0.81 | 0.76 | 0.70 |
| R2 | For reference: model v1 (own fundamentals, error sizes before the backtest) | 240.8 | 240 | 223–259 | 0.95 | 0.87 | 0.90 | 0.72 | 0.80 | 0.80 | 0.67 |
