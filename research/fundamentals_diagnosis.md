# Diagnosis: fundamentals vs. markets in the House

Districts with a market priced between 5% and 95%: 146. Market prices are turned into margins on the fundamentals' own error scale (±6.7 points), so the two can be compared in points.

## Where the gap sits, by the district's 2024 presidential margin

| 2024 presidential margin | Districts | Fundamentals (avg) | Market-implied (avg) | Market minus fundamentals |
|---|---|---|---|---|
| R+20–∞ | 36 | -18.4 | -9.8 | +8.6 |
| R+10–20 | 65 | -7.0 | -4.2 | +2.8 |
| R+5–10 | 14 | -0.5 | +2.5 | +3.0 |
| R+0–5 | 16 | +6.1 | +7.3 | +1.2 |
| D+0–5 | 8 | +12.4 | +7.5 | -4.9 |
| D+5–10 | 5 | +19.2 | +10.5 | -8.7 |
| D+10–20 | 1 | +18.7 | +10.6 | -8.2 |
| D+20–∞ | 1 | +30.2 | +11.0 | -19.2 |

## By incumbency

| Incumbent on the ballot | Districts | Market minus fundamentals |
|---|---|---|
| Democrat | 22 | -1.4 |
| Republican | 88 | +4.4 |
| none (open seat) | 36 | +2.2 |

## What the markets implicitly assume

Regression of the market-implied margin on the 2024 presidential margin and incumbency (+1 Democratic incumbent, −1 Republican, 0 open):

| | Markets imply | Our fundamentals assume |
|---|---|---|
| Swing in a district Trump won by 0 points (a) | +6.2 | +9.5 (national environment D+7.9 minus the national 2024 margin) |
| How much of the 2024 margin carries over (b) | 0.56 | 1.00 (uniform swing) |
| Incumbency bonus (c) | +2.3 | ±3.0 |
| Scatter around the fit (sd) | 3.6 | 6.7 |

Reading: b < 1 means the swing toward Democrats is larger in Republican-leaning districts than uniform swing assumes; a negative c would mean incumbents gain less than we assume.

## Contest answers under alternative treatments of fundamentals

| Variant | Seats (median) | P(majority) | NC-01 | NC-11 | O07 | PA-08 | NY-17 |
|---|---|---|---|---|---|---|---|
| Model v1: polls + markets + fundamentals | 238 | 0.94 | 0.89 | 0.92 | 0.82 | 0.77 | 0.79 |
| Fundamentals at half weight | 241 | 0.94 | 0.92 | 0.95 | 0.89 | 0.83 | 0.73 |
| Fundamentals only where no poll and no market | 245 | 0.90 | 0.93 | 0.96 | 0.95 | 0.87 | 0.62 |
