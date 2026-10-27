# Data sources, from most micro to most macro

Catalogue as of 26 October 2026.

**Access** column:
- **verified**: we called the API ourselves and it answered.
- **listed**: the source says it offers the data, but we have not pulled it yet.
- **web**: browser only, would need scraping.

## 1. Seat-level forecasts from other models (one probability per race)

| Source | Coverage | Access | Notes |
|---|---|---|---|
| [ElectIt](https://gking.harvard.edu/electit/) (Ebanks, Katz, King) | all 435 House + 35 Senate | listed ("Save this year (CSV)" buttons; data loads by JS) | Harvard-based. Three versions: no polls, + generic ballot, + all polls. Explicit scenario table. Paper: [gking.harvard.edu/10k](https://gking.harvard.edu/10k/) |
| [Decision Desk HQ / The Hill](https://votes.decisiondeskhq.com/forecast/2026) | House, Senate, Governor | web (rate-limited, HTTP 429) | also publishes joint control scenarios |
| [Silver Bulletin FLIPR](https://www.natesilver.net/p/nate-silver-2026-midterm-election-house-model) | House, Senate, Governor | web, seat-level partly paywalled | four error layers; polls from the NYT poll database |
| [Split Ticket](https://www.270towin.com/content/split-ticket-2026-midterm-election-forecast-model) (now at The Argument) | all races | web; mirrored as ratings on [270toWin](https://www.270towin.com/2026-house-election/split-ticket-2026-house-ratings) | categories map to probability bands: Lean ≥60%, Likely ≥80%, Safe ≥95% |
| [Race to the WH](https://www.racetothewh.com) | all 435 | web | 10,000 simulations |
| [Poliwave](https://www.poliwave.com/us/fed/projection) | House, Senate | web | 100,000 simulations |
| The Economist | House, Senate | web, paywalled | |
| FiftyPlusOne / VoteHub forecasts | House, Senate | web | |

## 2. Prediction markets (seat-level prices)

| Source | Coverage | Access | Notes |
|---|---|---|---|
| [Kalshi](https://kalshi.com/category/elections/midterms) | control markets + many individual districts and Senate races | **verified**: public REST `https://api.elections.kalshi.com/trade-api/v2/events` (no key for market data) | regulated in the US; good liquidity on headline markets |
| [Polymarket](https://polymarket.com) | control + many races | **verified**: public `https://gamma-api.polymarket.com/events` | thinner down-ballot. A Barnard study found weak down-ballot accuracy in 2024 |
| PredictIt | selected races | web/API | small position limits |
| [270toWin Kalshi page](https://270towin.com/prediction-markets/kalshi-2026-house-elections/) | competitive House races | web | handy cross-check |

## 3. Expert ratings (seat-level, categorical)

| Source | Access | Notes |
|---|---|---|
| [Cook Political Report](https://www.cookpolitical.com/ratings) | web | Senate 20 Oct, House 9 Oct |
| Sabato's Crystal Ball | web | |
| Inside Elections | web | |
| [270toWin consensus table](https://270towin.com/2026-house-election/table/consensus-2026-house-forecast) | web | aggregates all raters in one table, the easiest to scrape |

## 4. Polls

| Source | Level | Access | Notes |
|---|---|---|---|
| **VoteHub polls API** (used) | Senate, House district, generic ballot, approval | **verified**: `https://api.votehub.com/polls`, no key; 5,958 polls, current to 23 Oct; fields include pollster, LV/RV/adults, sponsor, partisan flag | CC BY 4.0 (per its reusers), so attribute VoteHub in the app |
| [FiftyPlusOne](https://fiftyplusone.news/readme) (former 538 journalists) | House district, Senate state, generic ballot, approval | needs an API key, even for the free files (HTTP 401 without one) | candidate for a cross-check if you create an account |
| NYT poll database | all | web | the main poll input for Silver Bulletin |
| [RealClearPolling](https://www.realclearpolling.com/latest-polls/senate) | Senate, House, generic | web | simple averages |
| Wikipedia race pages | per race | web | poll tables with sample size, LV/RV and sponsor |
| [Economist/YouGov](https://yougov.com/en-us/articles/55701-democrats-lead-double-digits-two-new-ways-yougov-defines-likely-voters-october-25-2026-economist-yougov-poll) | national | web | publishes both RV and two LV definitions, useful for the LV adjustment |
| FiveThirtyEight archive (`projects.fivethirtyeight.com/polls`) | all | web | from background knowledge: ABC shut 538 down in 2025, so treat the archive as frozen |

District-level House polls are sparse and often internal (campaign-sponsored). For most House seats the forecast has to come from fundamentals, ratings and markets, not polls.

## 5. Fundamentals

| Input | Source | Access | Notes |
|---|---|---|---|
| District partisan lean (2024 president by CD, **2026 lines**) | [The Downballot](https://www.the-downballot.com/p/the-downballot-releases-presidential), published 9 Jul 2026 | **verified, used**: public Google Sheet exported as CSV; all 435 districts; Missouri on its old map | no stated license; credit The Downballot (calculations: Daniel Donner) |
| Current members of Congress | [unitedstates/congress-legislators](https://unitedstates.github.io/congress-legislators/legislators-current.json) | **verified, used** | public domain; for Senate incumbents |
| Redistricting status | [Wikipedia](https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting), [Ballotpedia](https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections) | web | see [landscape.md](landscape.md) |
| National environment | generic ballot averages (RCP, FiftyPlusOne, PollsMax), presidential approval | web/CSV | D+7 to D+9 now |
| Special-election swing | The Downballot tracker; [Inside Elections](https://www.insideelections.com/news/article/special-elections-point-to-house-flip-in-november/ie17) | web | D about +13 vs Harris 2024 margin across 104 specials since 2025 |
| Candidate money | FEC OpenFEC API (`api.open.fec.gov`) | API key (free) | receipts and cash on hand by candidate |
| Historical results | MIT Election Data + Science Lab (House/Senate returns since 1976) | download | for calibrating error sizes |
| Incumbency, retirements | Ballotpedia, Wikipedia | web | |

## 6. Academic and other forecasts

- [PS: Political Science & Politics special issue](https://politicalsciencenow.com/forecasting-the-2026-us-midterms/): 17 forecasts. All of them have Democrats winning the House; they split on the Senate.
- [LSE citizen forecasting](https://blogs.lse.ac.uk/usappblog/2026/10/23/citizen-forecasting-us-midterm-elections/): Democrats win both chambers.
- FutureSearch (AI forecasting service, connected in this workspace): an optional extra ensemble member if AI is allowed.

## Proposed priority for the pipeline

1. **Kalshi + Polymarket API**: seat-level prices, automatable, verified.
2. **ElectIt CSV + 270toWin consensus ratings**: full seat coverage from non-market sources.
3. **FiftyPlusOne poll CSVs**: Senate and the few House polls; house effects and LV/RV.
4. **District lean on 2026 lines + generic ballot**: our own fundamentals baseline.
5. **DDHQ / Silver / Split Ticket toplines**: benchmarks for the dashboard comparison panel.
