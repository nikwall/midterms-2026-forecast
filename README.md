# 2026 Midterms Forecast

A forecast of the 2026 US House (and Senate) elections, built for the HKS forecasting contest in API-232: Computational Policy Analysis. Election Day is Tuesday, 3 November 2026.

**Dashboard:** https://nikwall.github.io/midterms-2026-forecast/

## What is here

| Path | Contents |
|---|---|
| [app/](app/) | the dashboard (static HTML/JS), published on GitHub Pages |
| [pipeline/](pipeline/) | the Python scripts: data, model, checks |
| [run_all.py](run_all.py) | runs the whole pipeline with one command |
| [PROCESS.md](PROCESS.md) | dated log of every step and choice, with reasons |
| [MODEL_PROPOSAL.md](MODEL_PROPOSAL.md) | the model design |
| [research/](research/) | sources, polling corrections, backtests (Senate 1998–2022; House 2022 and 2024), sensitivity, bridge from the course model, comparisons |
| [data/polls_manual.csv](data/polls_manual.csv) | polls from the news check that VoteHub lacks, with sources |

## How the model works, in one paragraph

Final model (v2). Every race gets three pieces of evidence:
- polls (VoteHub),
- prediction-market prices (Kalshi, Polymarket),
- fundamentals:
  - House: Decision Desk HQ's district probabilities of 22 Oct, the course's starting point;
  - Senate: the 2024 presidential result in the state, shifted by the national environment, plus incumbency.

Polls VoteHub lacks are added by hand after a news check of the contest districts. Crowd forecasts (Metaculus, Manifold, PredictIt) are shown for comparison, not used.

Each piece becomes an expected margin with an uncertainty. The uncertainties are calibrated on the midterms 1998–2022. The pieces are averaged with weights inversely proportional to their variance. All races are then simulated together 20,000 times, with a shared national error (±3.6), division and state errors, and a race-specific error. Every assumption is listed with its source on the dashboard ("Our assumptions").

Details: [research/model_explained.md](research/model_explained.md). The step-by-step path from the course's Part 3 model to ours: [research/bridge_report.md](research/bridge_report.md).

## Run it yourself

You need Python 3.11 or newer. Install the two packages once:

```bash
pip install -r requirements.txt
```

Fetch fresh data and rebuild the forecast (about one minute):

```bash
python run_all.py
```

Add `--full` to also run the sensitivity analysis and the 2022/2024 House backtest (downloads about 10 MB on the first run). Then open the dashboard:

```bash
python -m http.server 8770 --directory app
```

and go to http://localhost:8770.

**On GitHub, without installing anything:** under **Actions → Update forecast → Run workflow**. Anyone with write access to the repository can start it. GitHub then fetches the data, re-runs the model, commits the new forecast and republishes the dashboard.

**Data that is not in the repository:**
- Raw downloads in `data/raw/`: the pipeline fetches them again.
- The course workbook: course material, so not published. Its Decision Desk HQ district probabilities, which the model uses, are in `data/ddhq_house_2026-10-22.csv` (source: Decision Desk HQ, accessed 22 Oct 2026).
- `pipeline/backtest.py` needs the FiveThirtyEight poll archive and MIT Election Lab results in `data/raw/backtest/` (sources listed in the script). `pipeline/backtest_house.py` downloads its own files on the first run.
- Candidate photos are linked from Wikipedia, not copied.

## Contest rules (summary)

- **Scope:** the House only, entries due 7:00 AM ET on 3 Nov 2026.
- **(a)** The number of Democratic seats; teams are ranked by closeness.
- **(b)** The probability of a Democratic majority (218+).
- **(c)** The probability the Democrat wins NC-01, NC-11, OH-07, PA-08 and NY-17.
- **Tiebreaker:** the Brier score over the six probabilities.
- Alaska's Bill Hill (independent) does not count as a Democrat.

## Licences of the data

- VoteHub polls: CC BY 4.0.
- Kalshi and Polymarket: public market data.
- The Downballot: credit The Downballot.
- MIT Election Data + Science Lab and FiveThirtyEight: as published by them.
