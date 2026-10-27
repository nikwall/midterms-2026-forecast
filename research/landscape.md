# The 2026 race landscape

Research snapshot, 26 October 2026. Election Day is Tuesday, 3 November 2026.

## What is at stake

| Chamber | Seats on the ballot | Current split | Majority line | Notes |
|---|---|---|---|---|
| House | all 435 | Republican majority | 218 | 9 states use new maps in 2026 (see below) |
| Senate | 35 (33 Class II + specials in OH and FL) | 53 R – 47 D (incl. 2 independents caucusing with D) | 51 for Democrats; 50 for Republicans, because VP Vance breaks ties | Democrats need a net gain of 4 |

Of the 35 Senate seats, 22 are held by Republicans and 13 by Democrats. Democrats hold 34 seats that are not up this year, so they need 17 of the 35 to reach 51.

Senate seats up in 2026 (holder party):
- **R (22):** AK, AL, AR, FL (special), IA, ID, KS, KY, LA, ME, MS, MT, NC, NE, OH (special), OK, SC, SD, TN, TX, WV, WY
- **D (13):** CO, DE, GA, IL, MA, MI, MN, NH, NJ, NM, OR, RI, VA

## Competitive races (expert ratings)

**Senate, Cook Political Report, 20 October.** Seven races are Toss Up: Alaska (Sullivan), Iowa (open), Kansas (Marshall), Maine (Collins), Michigan (open), Ohio (Husted) and Texas (open). On 6 October Cook moved New Hampshire to Lean D and North Carolina to Likely D. Cook sees a Democratic gain of 2 to 6 seats. Bloomberg counts 14 races that could be competitive. [Cook](https://www.cookpolitical.com/ratings/senate-race-ratings), [Cook analysis](https://www.cookpolitical.com/analysis/senate/senate-overview/senate-majority-squarely-democrats-sights-kansas-moves-toss-two), [Washington Post](https://www.washingtonpost.com/politics/2026/10/06/three-senate-races-shift-toward-democrats-cook-ratings/)

Special cases the model must handle:
- **Nebraska.** The challenger to Ricketts is an independent, so "D seat" has to be defined for NE. This needs a decision.
- **Maine.** Elections there use ranked-choice voting.
- **Georgia and Louisiana.** Runoffs or later general elections are possible. Louisiana moved its House primary to 3 November, so some LA House seats are decided later. Check how the tournament resolves such races.

**House, Cook, 9 October.** 21 seats are Toss Up (15 R-held, 6 D-held). Counting Toss Up or worse for the holder, 23 R-held and 11 D-held seats are at risk ([Newsweek](https://www.newsweek.com/midterm-map-shift-2026-democrats-house-ratings-12209741)). Between January and mid-July, forecasters made 113 House rating changes, 92 of them toward Democrats.

## Mid-decade redistricting (2026 lines)

Source: [Wikipedia, 2025–2026 redistricting](https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting), cross-checked with [Ballotpedia](https://ballotpedia.org/Redistricting_ahead_of_the_2026_elections). Seat effects are estimates "on paper", using past presidential results.

| State | New map in effect for 2026? | Estimated effect |
|---|---|---|
| Texas | yes (SCOTUS stay, 4 Dec 2025) | +5 R |
| California | yes (Prop 50; SCOTUS denied review) | +5 D |
| Florida | yes (May 2026) | +4 R |
| Ohio | yes (commission map) | +2 R |
| North Carolina | yes | +1 R |
| Tennessee | yes (May 2026, after *Louisiana v. Callais*) | +1 R |
| Louisiana | yes (May 2026, after *Callais*) | +1 R |
| Alabama | yes (June 2026, after *Callais*) | +1 R |
| Utah | yes (court-selected map) | +1 D |
| Missouri | **no**, the 2022 map stays; Prop A on the ballot decides 2028 | (+1 R if used) |
| Virginia | **no**, the amendment was voided by the state Supreme Court | (+4 D if used) |

Net effect on paper is about +9 R, which matches Wikipedia's overview figure. Democrats therefore need a larger national margin to win the House than on the 2024 lines.

**Consequence for our work:** 2024 district results on 2024 lines are wrong for 9 states. We need 2024 presidential results recomputed on the 2026 lines (see [sources.md](sources.md)).

## Where the forecasters stand (headline numbers as reported)

| Source | P(Dem House) | P(Dem Senate) | As of | Note |
|---|---|---|---|---|
| Decision Desk HQ | 79% | 56% | 25 Oct | median 237 D House seats, 51 D Senate; D/D 54%, D-House/R-Senate 24%, R/R 21% |
| Silver Bulletin (FLIPR) | ~93% | ~75% | 12 Oct / 26 Oct | via Newsweek and The Conversation |
| Poliwave | 88% | 57% | 25 Oct | 100k simulations |
| Kalshi (market) | 91% | 64% | 26 Oct | |
| Split Ticket | 90% | n/a | Oct | via comparison article |
| The Economist | ~90% | ~49% | unclear | via Substack; verify |
| VoteHub | 72% | n/a | unclear | verify |
| ElectIt (Ebanks, Katz, King) | n/a (page loads by JS) | n/a | live | scenario table: "polls largely correct" gives a median of 239 D House seats and 52 D Senate seats |

The forecasters agree on the House: Democrats are clear favourites at 72–93%. They disagree on the Senate, at 49–75%. The Senate is where a careful forecast can add the most.

Context indicators:
- **Generic ballot.** About D+7 to D+9: RCP D+8.3 (8–23 Oct); FiftyPlusOne 52.2–43.0 (25 Oct); PollsMax D+8.1.
- **Youth vote.** The Harvard IOP Youth Poll (Fall 2026) has 18–29 likely voters at D 63 – R 26.

Sources: [DDHQ](https://votes.decisiondeskhq.com/forecast/2026), [Silver Bulletin](https://www.natesilver.net/p/nate-silver-2026-midterm-election-polls-model), [Poliwave](https://www.poliwave.com/us/fed/projection), [Kalshi](https://kalshi.com/category/elections/midterms), [The Conversation](https://theconversation.com/democrats-remain-clear-favourites-to-gain-control-of-congress-at-midterms-as-trumps-ratings-slide-again-295134), [ElectIt](https://gking.harvard.edu/electit/), [RCP generic ballot](https://www.realclearpolling.com/polls/state-of-the-union/generic-congressional-vote), [FiftyPlusOne](https://fiftyplusone.news/polls/generic-ballot/generic-ballot), [Harvard Youth Poll](https://iop.harvard.edu/youth-poll/53rd-edition-fall-2026)
