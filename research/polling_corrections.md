# Polling corrections: what the evidence says

Research notes as of 26 October 2026, focused on midterms and the recent past.

## In plain language

Polls are not wrong in a predictable direction. Some years they miss toward Republicans, some years toward Democrats. The direction has not been stable from one cycle to the next. Three things follow:

- Do not shift the polls by a fixed "the polls always miss X" amount.
- Do assume that misses are **shared across races**: when polls are off in Ohio, they tend to be off in Iowa too.
- Fix the **known, mechanical** distortions: pollster leans, registered vs. likely voters, and stale polls.

## 1. How large and in which direction past misses were

| Cycle | Direction of race-level poll bias | Source |
|---|---|---|
| 2014 (midterm) | overstated D by 2.6 pts | 538 data, via [Dave Manuel](https://www.davemanuel.com/2026/10/14/the-biggest-polling-misses-in-midterm-election-history/) |
| 2018 (midterm) | overstated R by 0.5 pts | same |
| 2022 (midterm) | overstated D by 0.8 pts | same |
| 2016/2020/2024 (presidential) | overstated D by 3.8 pts on average | [Silver Bulletin](https://www.natesilver.net/p/what-if-the-polls-are-wrong-again) |
| Trump-era off-year / special elections | biased toward R by 1.3 pts on average | same |
| 2025 New Jersey governor | R+9 bias, average error about 9 pts, the worst since 2000 | [Silver](https://www.natesilver.net/p/actually-sometimes-polls-underestimate) |
| 2025 Virginia | average error 5.9 pts; D underestimated in all three statewide races | Silver; [Sabato](https://centerforpolitics.org/crystalball/polling-accuracy-in-the-2025-elections-virginia-new-jersey-and-new-york-city/) |

Takeaways:
- The 2018 and 2022 midterm averages were nearly unbiased overall, but had sizeable *regional* errors (Silver).
- Over nine cycles the bias ran against D once, against R four times, and was about zero four times. Silver notes this could still be chance.
- Midterm Senate polling error is larger than in presidential years ([Sam Wang, Princeton Election Consortium](https://election.princeton.edu/?p=1012)).
- ElectIt's scenario table puts 0.07–0.10 probability on each "historic" polling error ([ElectIt](https://gking.harvard.edu/electit/)).

## 2. The structure of the error matters more than its sign

The FLIPR model (Silver Bulletin) splits error into four layers:
1. a uniform national error,
2. demographically or geographically correlated error,
3. state-level error,
4. race-specific error.

In presidential years most of the error sits in layer 1. In midterms it is spread more evenly across all four. **This is why race probabilities must not be summed as if they were independent.** Independent races give far too narrow seat intervals.

## 3. Mechanical corrections (apply these)

| Correction | What it fixes | 2026 evidence |
|---|---|---|
| **House effects** | Each pollster leans systematically. Estimate each pollster's average deviation from consensus and subtract it. | standard in FLIPR, 538 and FiftyPlusOne |
| **Likely vs. registered voters** | Midterm electorates differ from all registered voters. | **This cycle LV screens favour D.** Economist/YouGov had RV D+8 with larger LV leads (25 Oct); in September YouGov ranged from D+6 (RV) to D+16 (one LV screen) ([YouGov](https://yougov.com/en-us/articles/55690-likely-voters-and-the-blue-wave)). One estimate puts the 2026 LV bonus for D at about 4 pts ([plusminus4](https://plusminus4.substack.com/p/blue-wave-polls), lower-quality source). Historically LV screens moved midterm polls toward R; the education realignment reversed that. |
| **Recalled-vote weighting** | Pollsters weight to the 2024 result using respondents' recalled vote. | Some 2024 Trump voters no longer admit it, so weighting to Trump's actual share over-weights his most loyal voters ([G. Elliott Morris, 22 Oct](https://www.gelliottmorris.com/p/2026-10-22-trump-voters-rewriting-2024-vote)). In Morris's simulation, removing the anchor moved the margin from D+7.1 to D+10.0 ([Morris, July](https://www.gelliottmorris.com/p/2026-07-23-lab-npors-pid5-weighting)). In Virginia 2025, pollsters weighting to a 2021/2024 electorate were less accurate (Silver). |
| **Timeline adjustment** | Old polls in races with few polls are stale. | Shift old race polls by the change in the generic ballot since they were fielded (FLIPR does this). |
| **Partisan / sponsor flag** | Campaign internals are released selectively. | down-weight; FiftyPlusOne `sponsors.csv` flags sponsor type |
| **Poll quality weighting** | Pollsters differ in historical accuracy. | weight by pollster rating and sample size |

## 4. Fundamentals that pull polls toward reality

| Signal | Value now | Use |
|---|---|---|
| Midterm penalty | From background knowledge, to verify: the president's party lost House seats in 18 of 20 post-war midterms. Silver: the typical swing is 7–8 pts vs. the previous presidential result; current models imply 10–11 pts toward D. | prior for the national swing |
| Generic ballot | D+7 to D+9 (RCP, FiftyPlusOne, PollsMax) | sets the national environment |
| Special-election swing | D +12.9 pts vs. Harris margin across 104 specials since 2025 (Downballot); about +11 in 2026; DDHQ: about +20 in 2025 House specials | directional signal. In 2018, early specials ran hot and then faded: the May–Oct median was only D+2.0 ([MultiState](https://www.multistate.us/insider/2026/4/13/what-democratic-special-election-wins-mean-for-state-legislative-elections-in-2026)) |
| Presidential approval | about 37% (lower-quality aggregator; verify) | midterm-penalty driver |
| District lean | 2024 president on **2026 lines** | baseline for every House seat |
| Incumbency, candidate quality, money | per race | small adjustments; ElectIt estimates "candidate effects" |
| Polls ↔ fundamentals blend | Silver example: SC polls R+2.6 → forecast R+5.3 after fundamentals | fundamentals matter most where polls are thin or out of line with the state's lean |

## 5. What we propose to do with this

1. Apply the mechanical corrections (section 3) to the raw polls.
2. Do **not** add a directional "unskew". The evidence for a 2026-specific direction is mixed: Democrats outran their polls in 2025 and in the specials, but in 2016/2020/2024 the polls overstated Democrats. Instead, keep the error symmetric and **fat-tailed**, with correlated layers.
3. Report scenarios like ElectIt: polls right, normal miss each way, historic miss each way.
4. Open question for us: since the tournament scores outcomes, should we tilt slightly toward the 2025/special-election evidence? Our proposal is to give it a small weight in the national-environment prior, not in the polls themselves.
