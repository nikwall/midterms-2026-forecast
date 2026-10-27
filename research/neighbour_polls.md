# Neighbour polls: asking about others instead of oneself

Research notes, 26 October 2026.

## The idea

There are two kinds of "about others" questions:

1. **Social-circle question.** "What share of your friends, family and neighbours will vote for each party?" Respondents report on a network much larger than the sample. They also reveal views they might not admit as their own. Galesic, Bruine de Bruin and colleagues found that this question predicted the 2016 US and 2017 French presidential elections better than the usual own-vote question ([Galesic et al. 2018](https://pac.org/wp-content/uploads/Galesic1803.pdf)). A follow-up found the advantage holds in elections with many parties ([Bruine de Bruin et al. 2022](https://www.sumsar.net/papers/bruine_de_bruin_social_circles_many_parties_2022.pdf)). In 2018 the same team forecast the House popular vote through USC's Understanding America Study. Their new methods showed a smaller Democratic lead than the traditional questions ([Galesic, Psychology Today](https://www.psychologytoday.com/us/blog/our-networks-our-selves/201811/how-social-science-tools-can-better-predict-election-results)).
2. **Expectation question ("citizen forecasting").** "Who do you think will win?" The American National Election Studies have asked it since 1956. Aggregated expectations predict winners with considerable accuracy ([LSE USAPP, 23 Oct 2026](https://blogs.lse.ac.uk/usappblog/2026/10/23/citizen-forecasting-us-midterm-elections/)). Answers are strongly partisan, though, so the raw shares are not probabilities.

## What exists for 2026

| Survey | Question | Field dates, sample | Result |
|---|---|---|---|
| [Pew Research Center](https://www.pewresearch.org/short-reads/2026/10/15/majority-of-americans-expect-democrats-to-win-control-of-house-public-is-split-on-senate/) | which party will control the House / Senate | 28 Sep – 4 Oct, 5,062 adults | House: D 55, R 40. Senate: R 48, D 46. Partisans expect their own side to win (75% of Republicans expect an R Senate, 71% of Democrats a D Senate). |
| [Verasight Omnibus via LSE](https://blogs.lse.ac.uk/usappblog/2026/10/23/citizen-forecasting-us-midterm-elections/) | which party wins House and Senate | Sep 2026, about 1,000 adults | D both 39, R both 27, D House + R Senate 22, R House + D Senate 12. A year earlier R both led with 37. |
| [Verasight data page](https://data.verasight.io/politics/how-americans-see-the-2026-midterms-shaping-up) | expectations, turnout intent | 2026 | expectations tilt narrowly D; about a quarter unsure |

**Not found:** a 2026 survey with the social-circle question (vote shares among friends and neighbours), and any state- or district-level expectation data. USC's Understanding America Study ran social-circle questions in earlier cycles. Its 2026 pages did not appear in search, so we need to check them directly (USC Dornsife / CESR).

## What it means for the model

- Neighbour and expectation data exist only at the **national** level. In the model they inform the national environment and chamber control, not single seats.
- Raw expectation shares must be calibrated: correct for partisan composition and compare against past cycles. A simple first version uses the **change** over time, which removes much of the partisan baseline. Verasight's sweep expectation for Democrats rose from 27% to 39% in a year.
- **A gap to note.** The public is split on the Senate (Pew: D 46 vs R 48). Markets have Democrats at about 64%. The Pew field dates are three weeks older than the market prices, so part of the gap may be timing.
- **Next steps:**
  1. Look for the social-circle question in the UAS 2026 data.
  2. Check whether state polls (e.g. university polls in Maine, Iowa, Texas) ask "who will win the Senate race here?"
  3. Read the field dates and wording of each source carefully, because expectation answers move with news coverage.
