# Independent backtest, round 2: gold London-range breakouts, ATR-scaled breakouts, Asian-session night scalping on crosses, and the Breedon-Ranaldo time-of-day pattern (Jan 2024 - 4 Nov 2026)

*Prepared 5 November 2026. Second, targeted round on the same Forexite minute data and the same engine as `independent_backtest_results.md`; the new code is in `backtest_code/round2/` and every table below is generated from the result CSVs in `backtest_code/round2/results/` by `make_report_r2.py`. Nothing here uses vendor backtests, signal pages or marketing figures; the vendor numbers quoted for comparison come from `round2_candidate_verification.md`.*

## 1. Data and symbol coverage actually used

Source: the 1,047 Forexite daily archives already downloaded in round one (2023-12-24 to 2026-11-04, zero missing days). Each daily zip holds all ~70 instruments, so the seven crosses were extracted from the existing zips (`build_dataset_r2.py`); nothing was re-downloaded. Same conventions as round one: bid quotes, Europe/Berlin bar-close stamps converted to UTC bar-open time, de-duplicated, OHLC-validated.

| Symbol | M1 bars | First bar (UTC) | Last bar (UTC) | Price decimals | Weekday gaps > 60 min | Used in |
|---|---|---|---|---|---|---|
| XAUUSD | 1,068,700 | 2023-12-24 22:00 | 2026-11-04 22:59 | 1 ($0.10 = 10 points) | 0 | T1, T2 |
| EURUSD | 1,074,945 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 (whole pips) | 0 | T2, T3, T4 |
| AUDNZD | 1,074,626 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| EURCHF | 1,074,558 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| EURGBP | 1,074,665 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| AUDCAD | 1,074,561 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| GBPCAD | 1,074,616 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| NZDCAD | 1,074,538 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |
| EURAUD | 1,074,724 | 2023-12-24 22:00 | 2026-11-04 22:59 | 4 | 0 | T3 |

* Trading days: 742 server-time weekdays from 2024-01-02 to 2026-11-04 (2024-01-01 has too few bars and is dropped; the last week of December 2023 is indicator warm-up only). Calendar years: 2024 = 261 days, 2025 = 261, 2026 = 220 (to 4 November).
* **Caveats that matter for this round.** (a) Bid only: stop and limit fills are simulated on the bid; the spread is charged as a cost, so a buy stop that in reality triggers on the ask is modelled as triggering on the bid at the same level. (b) Gold is quoted to $0.10, so the 20-point buffer in T1 is two data ticks and the 0-point buffer means a touch of the rounded range high. (c) The Forexite bid feed shows **spike bars at the 00:00 server rollover**: the absolute jump between the previous close and the open of the first bar after midnight has a 95th percentile of 6-15 pips on the crosses against 1 pip at other times. That turned out to be decisive for T3 (section 7.4). (d) No volume. (e) Forexite also carries index CFDs (DJIUSD, NDQUSD, SPXUSD, present in 772 of the 1,047 daily files with 1,440 bars per weekday, i.e. 24-hour dealing-desk quotes) plus USXUSD, XAGUSD, XAUEUR, WTIUSD/BRNUSD and crypto. Index tests were out of scope and were not run; the files are there if wanted.

## 2. Server-time convention

Every rule that the sources express in "server time" is run in **broker server time = New York time + 7 hours**, the convention of IC Markets, Pepperstone and most MT5 brokers: 00:00 server is 17:00 New York (the daily FX rollover), so the week has exactly five daily candles. That is **UTC+2 while the US is on standard time and UTC+3 while the US is on daylight time**; the switch follows US DST rules (second Sunday in March at 02:00 New York = 07:00 UTC, to the first Sunday in November at 02:00 New York = 06:00 UTC), *not* EU rules. The helper (`r2_engine.utc_to_server` / `server_to_utc`) was checked against the data: the Forexite week opens Sunday 22:00 UTC in winter and 21:00 UTC in summer and closes Friday 21:58 / 20:58 UTC, which is Monday 00:00 and Friday 23:59 server time in both seasons. Spot checks across the 2025 and 2026 transitions are printed in `t5_sanity_log.txt`. T4 uses UTC clock times because the academic paper does.

## 3. Cost assumptions

Costs are deducted once per round trip from the gross result. All cases are run; "base" is the headline.

| Test | Symbol(s) | Case | Round-trip cost | Composition |
|---|---|---|---|---|
| T1, T2 | XAUUSD | gross | 0 | signal only |
| | | spread-only | 15 points ($0.15) | approximates an MT5 real-tick test with no commission or delay (what the vendor's test most likely included) |
| | | **base** | **42 points** | 15 spread + 7 commission ($7/lot) + 10 slippage per side |
| | | expensive | 50 points | 30 spread (standard account) + 10 slippage per side |
| T2 | EURUSD | gross / cheap / **base** / expensive | 0 / 0.8 / **1.2** / 2.1 pips | as in round one |
| T3 | crosses, EURUSD | gross | 0 | |
| | | spread-only | night spread | EURCHF 0.8, AUDNZD 1.0, EURGBP 0.7, AUDCAD 0.9, GBPCAD 1.3, NZDCAD 1.1, EURAUD 1.0, EURUSD 0.4 pips (IC Markets Raw averages and the KQ5 night estimates) |
| | | **base** | spread + 0.7 commission + 0.4 slippage | EURCHF 1.9, AUDNZD 2.1, EURGBP 1.8, AUDCAD 2.0, GBPCAD 2.4, NZDCAD 2.2, EURAUD 2.1, EURUSD 1.5 pips |
| | | full | base + rollover + swap | +1.0 pip for entries between 23:45 and 00:15 server; swap 0.5 pip per position held across 00:00 server, tripled when that rollover is the Wednesday-to-Thursday one |
| T4 | EURUSD | gross / cheap / **base** | 0 / 0.8 / **1.2** pips | |

Not modelled: variable spreads beyond the fixed add-on (the real widening at the rollover is far larger than 1 pip, see 7.4), requotes, broker stop-level rules, partial fills, and the ask-side of the quote. The $-based figures for crosses use approximate constant pip values in USD (AUDNZD $6.0, EURCHF $11.5, EURGBP $12.8, CAD crosses $7.3, EURAUD $6.6 per pip per lot); they affect only the compounding curve, not the pip results.

## 4. Engine conventions and what was verified (T5)

* Signals use closed bars; market entries fill at the open of the next M1 bar (M5 signals: the first M1 bar at or after the M5 close). Stop orders fill at the level, or at the bar open if the bar opens beyond the level (12 of 603 T1 fills, 2%, were such gap fills with an average 52 points of adverse slippage). Limit orders fill at the level, or at the open if the bar opens through it (favourably). OCO: the first level touched fills; if both are touched in one M1 bar the side closer to the bar's open is taken; the other order is cancelled.
* SL/TP are checked intrabar on M1 high/low from the entry bar on; both touched in one bar = loss. **Break-even rule (T1):** when the M1 high (long) touches entry + 1.5R the stop moves to the entry price; a bar that touches +1.5R and returns to the entry price in the same bar counts as a break-even exit; once the BE stop is active, a bar touching both the BE stop and the target counts as a BE exit; a bar opening below the BE stop exits at the open. On the entry bar itself the "returned to entry" test is not applied (the low of a stop-order entry bar is below the fill by construction).
* Price levels are sums of decimals (e.g. 2726.7 + 0.2 = 2726.8999999999996). The first run missed one exact-tick touch of a BE stop because of this; all level comparisons now carry a 1e-7 tolerance (far below a tick). The T1 results were unchanged by the fix; T3 results moved by at most 0.1 pip.
* One position per strategy variant at a time. Costs applied after the fact (scalar or per-trade array for T3).
* Statistics: expectancy per trade in points/pips and in R; profit factor; win rate; max drawdown in points and in % of a compounding 1%-risk account (20:1 leverage cap for gold, 30:1 FX; $10,000 and, for T1, $5,000 start); Sharpe = annualised mean/std of daily net P&L (fixed 1 lot, zero on no-trade days); longest losing streak; long vs short split; 95% percentile bootstrap CI (2,000 resamples) of the mean net result per trade (1,000 for per-year rows). An asterisk in the tables marks a CI entirely above zero, "(-)" one entirely below.
* **Independent re-derivation (`t5_sanity.py`), all against the raw M1 arrays without engine code:** T1 base variant, 603 trades on 603 distinct days (max one fill per day); every fill is at the recomputed level or at the gap open (0 violations); no earlier touch of either stop level between 08:00 server and the fill bar (0); same-bar tie-break correct (0); the range is built only from bars stamped before 08:00 server and the first order bar is at/after 08:00 (0); no earlier SL/TP/BE touch than the recorded exit (0); every BE exit was preceded by a +1.5R touch (0); no exit after the 21:00 flat (0); every traded day passes the 0.30-1.60% filter (0). T2: 272 trades, 0 fill/first-touch/expiry/one-per-day violations, SL/ATR = 1.200, TP/SL = 1.800. T3 N2 (AUDNZD): 669 trades, all entered inside 21:00-02:00 server, all closed by the 06:00 deadline, no Friday-evening entries, first 400 fills re-derived at the 17:00-21:00 range extremes (0 violations). T3 N1: 1,724 of 1,725 entries at an M5 boundary minute (the exception follows a missing bar), all at the open of the fill bar, the signal bar closes before the fill bar opens. T4: 742 entries at 07:00 and 652 at 13:00 UTC, exits at 13:00 and 21:00, all at minute :00.
* Trade-count sanity: T1 traded on 603 of 610 eligible days (82% of weekdays eligible; 84 days skipped for a range under 0.30%, 48 for a range over 1.60%; 7 eligible days with no fill), 17 trades per month on average (vendor: 715 trades in 45 months, 16 per month). T2 gold: 643 eligible days, 272 fills with the 12:00 expiry (orders are 0.15 ATR away and only have four hours). T3: 0.4-1.2 trades per night per symbol.

---

## 5. T1. "Gold London Range Breakout" (MQL5 blog 777540), exact rules, XAUUSD

**Rules as run.** Asian range = M1 high/low from 03:00 to 08:00 server. At 08:00 a buy stop at range high + buffer and a sell stop at range low - buffer (OCO), expiring at 21:00 if unfilled (variants 12:00, 16:00). SL at the far side of the range (long: low - buffer; short: high + buffer), capped at 0.6% of the entry price (if the range is wider, SL = entry -/+ 0.6%). TP = 2.5R. Stop to break-even at +1.5R. Force-flat at 21:00. Max one fill per day. Skip the day if range/price x 100 is below 0.30 or above 1.60 (price = close of the last range bar). Base buffer 20 points; 0 and 50 also run. 1% risk compounding at 20:1 cap on $5,000 and $10,000.

### T1-A. Base rule by cost case

| Cost case | Trades | Win % | PF | Exp (pt) | Exp (R) | 95% CI exp (pt) | 95% CI exp (R) | Net (pt/lot) | MaxDD (pt) | Return % (1% risk) | MaxDD % (1% risk) | P&L $5k start | P&L $10k start | Sharpe | Max loss streak | Avg stop (pt) | Cost % of stop | Exit % SL/TP/BE/time | Longs n / exp | Shorts n / exp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gross (0) | 603 | 44.6 | 1.39 | +325 | +0.16 | [+131, +532]* | [+0.06, +0.26]* | 196,254 | 58,603 | +147.9 | 19.2 | 7,393 | 14,785 | 1.84 | 6 | 1,891 | 0.0 | 41/12/5/42 | 330 / +298 | 273 / +359 |
| spread-only 15 pt | 603 | 44.3 | 1.37 | +310 | +0.15 | [+116, +517]* | [+0.05, +0.25]* | 187,209 | 59,458 | +134.4 | 19.7 | 6,719 | 13,437 | 1.75 | 15 | 1,891 | 0.8 | 41/12/5/42 | 330 / +283 | 273 / +344 |
| base 42 pt | 603 | 43.9 | 1.33 | +283 | +0.13 | [+89, +490]* | [+0.04, +0.23]* | 170,928 | 60,997 | +111.9 | 21.5 | 5,596 | 11,193 | 1.60 | 15 | 1,891 | 2.2 | 41/12/5/42 | 330 / +256 | 273 / +317 |
| expensive 50 pt | 603 | 43.6 | 1.32 | +275 | +0.13 | [+81, +482]* | [+0.03, +0.23]* | 166,104 | 61,453 | +105.7 | 22.0 | 5,285 | 10,570 | 1.55 | 15 | 1,891 | 2.6 | 41/12/5/42 | 330 / +248 | 273 / +309 |

The $5k and $10k accounts give identical percentages because the 20:1 cap never binds (stops are 0.3-0.6% of price, so 1% risk is 1.7-3.3x equity of notional). Points are $0.01/oz = $1 per 1-lot (100 oz) trade.

### T1-B. Base rule by calendar year (base costs; gross in brackets)

| Year | Trades | Win % | PF | Exp pt net (gross) | Exp (R) | 95% CI exp (pt) | Net (pt/lot) | Return % (1% risk) | MaxDD % | Sharpe | Streak | Avg stop (pt) | Longs n / exp | Shorts n / exp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | 194 | 46.9 | 1.29 | +146 (+188) | +0.12 | [-62, +349] | 28,273 | +25.5 | 13.8 | 1.44 | 5 | 1,176 | 111 / +201 | 83 / +72 |
| 2025 | 222 | 40.1 | 1.16 | +143 (+185) | +0.06 | [-168, +465] | 31,803 | +13.3 | 14.7 | 0.88 | 11 | 1,865 | 125 / +310 | 97 / -71 |
| 2026 | 187 | 45.5 | 1.52 | +593 (+635) | +0.22 | [+110, +1,055]* | 110,852 | +49.0 | 12.1 | 2.51 | 15 | 2,664 | 94 / +249 | 93 / +940 |
| **overall** | 603 | 43.9 | 1.33 | +283 (+325) | +0.13 | [+89, +490]* | 170,928 | +111.9 | 21.5 | 1.60 | 15 | 1,891 | 330 / +256 | 273 / +317 |

### T1-C. Rule variants (base costs)

| Variant | Eligible days | Trades | Win % | PF | Exp pt net (gross) | Exp (R) | 95% CI exp (pt) | Exp by year 24/25/26 | Return % | MaxDD % | Sharpe | Exit % SL/TP/BE/time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **base** buf 20 / TP 2.5R / BE 1.5R / 03-08 / exp 21:00 | 610 | 603 | 43.9 | 1.33 | +283 (+325) | +0.13 | [+89, +490]* | +146 / +143 / +593 | +112 | 21.5 | 1.60 | 41/12/5/42 |
| buffer 0 | 610 | 603 | 43.4 | 1.34 | +284 (+326) | +0.13 | [+94, +488]* | +152 / +154 / +575 | +113 | 20.2 | 1.61 | 41/12/6/41 |
| buffer 50 pt | 610 | 601 | 44.6 | 1.33 | +281 (+323) | +0.13 | [+78, +483]* | +143 / +155 / +572 | +110 | 21.3 | 1.57 | 40/12/4/44 |
| TP 1.5R | 610 | 603 | 48.8 | 1.23 | +198 (+240) | +0.09 | [+21, +380]* | +146 / +49 / +429 | +71 | 20.7 | 1.30 | 41/30/0/30 |
| TP 2.0R | 610 | 603 | 44.3 | 1.25 | +215 (+257) | +0.10 | [+32, +410]* | +104 / +78 / +494 | +71 | 23.2 | 1.30 | 41/18/5/36 |
| TP 3.0R | 610 | 603 | 43.8 | 1.32 | +275 (+317) | +0.13 | [+80, +487]* | +151 / +137 / +568 | +107 | 19.3 | 1.52 | 41/7/5/47 |
| TP 1.5R, BE off | 610 | 603 | 48.9 | 1.24 | +204 (+246) | +0.10 | [+27, +387]* | +146 / +49 / +448 | +74 | 20.7 | 1.33 | 41/30/0/30 |
| TP 2.0R, BE off | 610 | 603 | 46.3 | 1.26 | +227 (+269) | +0.10 | [+42, +435]* | +117 / +79 / +517 | +78 | 24.7 | 1.34 | 42/19/0/38 |
| TP 2.5R, BE off | 610 | 603 | 45.9 | 1.33 | +295 (+337) | +0.14 | [+96, +508]* | +165 / +127 / +627 | +121 | 23.8 | 1.62 | 42/13/0/44 |
| TP 3.0R, BE off | 610 | 603 | 45.8 | 1.31 | +281 (+323) | +0.13 | [+77, +507]* | +170 / +121 / +586 | +113 | 21.7 | 1.52 | 43/7/0/50 |
| orders expire 12:00 | 610 | 526 | 43.7 | 1.38 | +320 (+362) | +0.15 | [+105, +535]* | +159 / +154 / +710 | +114 | 16.0 | 1.66 | 42/14/6/39 |
| orders expire 16:00 | 610 | 578 | 43.9 | 1.36 | +308 (+350) | +0.14 | [+96, +516]* | +148 / +182 / +624 | +118 | 18.3 | 1.68 | 42/13/5/40 |
| range 02:00-07:00 | 586 | 582 | 43.3 | 1.30 | +257 (+299) | +0.13 | [+63, +481]* | +110 / +186 / +487 | +100 | 22.9 | 1.42 | 41/12/6/41 |
| range 04:00-09:00 | 620 | 608 | 44.6 | 1.20 | +171 (+213) | +0.09 | [-22, +374] | +94 / +121 / +311 | +61 | 25.5 | 1.01 | 41/11/4/44 |
| no 0.30-1.60% range filter | 742 | 722 | 42.9 | 1.33 | +270 (+312) | +0.14 | [+89, +455]* | +158 / +85 / +627 | +159 | 25.2 | 1.71 | 42/14/6/38 |
| buy stop only (long-only) | 610 | 436 | 45.2 | 1.18 | +147 (+189) | +0.10 | [-61, +350] | +60 / +264 / +90 | +51 | 13.2 | 0.79 | 38/10/4/48 |
| sell stop only (short-only) | 610 | 374 | 40.4 | 1.27 | +227 (+269) | +0.06 | [-26, +482] | -29 / -9 / +768 | +22 | 24.3 | 1.00 | 43/12/6/40 |
| only in direction of 50-day SMA | 610 | 403 | 45.9 | 1.34 | +284 (+326) | +0.14 | [+56, +526]* | +9 / +271 / +559 | +70 | 15.1 | 1.33 | 39/12/3/46 |
| only against 50-day SMA | 610 | 379 | 40.1 | 1.12 | +100 (+142) | +0.04 | [-138, +337] | +61 / +1 / +269 | +13 | 21.4 | 0.48 | 42/10/6/42 |

### T1-D. Random-direction benchmark (50 seeds; same entry bars, fill prices, stop distance, 2.5R target, 1.5R BE, 21:00 flat; only the direction is a coin flip)

| Cost case | Random mean exp (pt) | 5th pct | 95th pct | Max of 50 seeds | Mean PF | Mean return % (1% risk) | % seeds positive | Actual rule exp (pt) | % seeds >= actual |
|---|---|---|---|---|---|---|---|---|---|
| gross (0) | +1 | -143 | +98 | +170 | 1.00 | -4 | 50 | +325 | 0 |
| spread-only 15 pt | -14 | -158 | +83 | +155 | 0.99 | -10 | 44 | +310 | 0 |
| base 42 pt | -41 | -185 | +56 | +128 | 0.96 | -18 | 32 | +283 | 0 |
| expensive 50 pt | -49 | -193 | +48 | +120 | 0.95 | -21 | 22 | +275 | 0 |

| Year (base costs) | Random mean exp (pt) | 5th pct | 95th pct | Actual rule exp (pt) | % seeds >= actual |
|---|---|---|---|---|---|
| 2024 | -98 | -230 | +16 | +146 | 0 |
| 2025 | -6 | -214 | +144 | +143 | 6 |
| 2026 | -24 | -252 | +214 | +593 | 0 |

### T1-E. Splits of the base rule's trades (base costs)

| Split | Trades | Win % | PF | Exp (pt) | Exp (R) | 95% CI exp (pt) | Net (pt/lot) | Avg stop (pt) |
|---|---|---|---|---|---|---|---|---|
| Long trades | 330 | 46.1 | 1.31 | +256 | +0.16 | [+5, +497]* | 84,448 | 1,882 |
| Short trades | 273 | 41.4 | 1.36 | +317 | +0.10 | [-6, +641] | 86,480 | 1,903 |
| Breakout in direction of 50-day SMA | 309 | 46.3 | 1.44 | +377 | +0.18 | [+75, +694]* | 116,607 | 1,960 |
| Breakout against 50-day SMA | 274 | 42.0 | 1.24 | +206 | +0.10 | [-88, +505] | 56,531 | 1,887 |
| Stop capped at 0.6% of price (range wider than 0.6%) | 352 | 47.7 | 1.51 | +499 | +0.21 | [+164, +811]* | 175,540 | 2,301 |
| Stop at far side of range (range <= 0.6%) | 251 | 38.6 | 0.97 | -18 | +0.02 | [-212, +177] | -4,612 | 1,317 |

### T1-F. Gold benchmarks over the same period

| Buy-and-hold (server-day closes) | Start | End | Return % | Points per lot | MaxDD % (daily closes) | Sharpe (daily) |
|---|---|---|---|---|---|---|
| overall | 2,064.3 | 4,060.7 | +96.7 | 199,640 | 28.5 | 1.19 |
| 2024 | 2,064.3 | 2,624.3 | +27.1 | 56,000 | 8.0 | 1.65 |
| 2025 | 2,624.3 | 4,318.9 | +64.6 | 169,460 | 9.8 | 2.65 |
| 2026 | 4,318.9 | 4,060.7 | -6.0 | -25,820 | 28.5 | -0.10 |

| Long gold 08:00 -> 21:00 server (gross) | Period | Days | Mean pt/day | 95% CI | Total pt | % up days |
|---|---|---|---|---|---|---|
| all weekdays | overall | 742 | -30 | [-336, +264] | -22,410 | 53.0 |
| all weekdays | 2024 | 261 | +42 | [-187, +270] | 11,020 | 51.3 |
| all weekdays | 2025 | 261 | +193 | [-272, +602] | 50,360 | 55.2 |
| all weekdays | 2026 | 220 | -381 | [-1,262, +391] | -83,790 | 52.3 |
| days passing the 0.30-1.60% range filter | overall | 610 | -59 | [-359, +240] | -35,980 | 52.3 |
| days passing the 0.30-1.60% range filter | 2024 | 194 | +15 | [-242, +276] | 3,000 | 51.5 |
| days passing the 0.30-1.60% range filter | 2025 | 228 | +234 | [-195, +682] | 53,260 | 54.8 |
| days passing the 0.30-1.60% range filter | 2026 | 188 | -491 | [-1,226, +225] | -92,240 | 50.0 |

| Year | Days | Mean price | Mean 03-08 range ($) | Median range % of price | % days < 0.30% (skipped) | % days > 1.60% (skipped) |
|---|---|---|---|---|---|---|
| 2024 | 261 | 2,389 | 11.6 | 0.41 | 23.8 | 1.9 |
| 2025 | 261 | 3,442 | 26.1 | 0.64 | 7.7 | 5.0 |
| 2026 | 220 | 4,496 | 51.5 | 0.93 | 0.9 | 13.6 |

Additional trend diagnostics from the base trade list: correlation between a trade's net R and the same day's close-to-close gold return is 0.00; correlation with the *absolute* daily return is 0.47; the breakout direction matched the sign of the day's close-to-close move on 71% of traded days.

### T1-G. Sensitivity grid: expectancy after base costs, TP x buffer x range window (BE 1.5R, expiry 21:00); * = 95% CI above zero

| Window / buffer | TP 1.5R | TP 2.0R | TP 2.5R | TP 3.0R |
|---|---|---|---|---|
| 02-07 / 0 pt | +210 (PF 1.25)* | +246 (PF 1.29)* | +275 (PF 1.32)* | +273 (PF 1.32)* |
| 02-07 / 20 pt | +194 (PF 1.22)* | +230 (PF 1.27)* | +257 (PF 1.30)* | +261 (PF 1.30)* |
| 02-07 / 50 pt | +179 (PF 1.21) | +236 (PF 1.27)* | +247 (PF 1.28)* | +258 (PF 1.30)* |
| 03-08 / 0 pt | +209 (PF 1.25)* | +223 (PF 1.27)* | +284 (PF 1.34)* | +283 (PF 1.34)* |
| 03-08 / 20 pt | +198 (PF 1.23)* | +215 (PF 1.25)* | +283 (PF 1.33)* | +275 (PF 1.32)* |
| 03-08 / 50 pt | +173 (PF 1.20)* | +224 (PF 1.26)* | +281 (PF 1.33)* | +282 (PF 1.33)* |
| 04-09 / 0 pt | +132 (PF 1.15) | +171 (PF 1.20) | +180 (PF 1.21) | +168 (PF 1.20) |
| 04-09 / 20 pt | +110 (PF 1.13) | +155 (PF 1.18) | +171 (PF 1.20) | +156 (PF 1.18) |
| 04-09 / 50 pt | +96 (PF 1.11) | +149 (PF 1.17) | +162 (PF 1.18) | +158 (PF 1.18) |

Cells positive after base costs: **36 of 36**; CI entirely above zero: **23 of 36** (none of the twelve 04:00-09:00 cells, and 02-07 / 50 pt / TP 1.5R); CI entirely below zero: 0. Expectancy ranges from +96 to +284 points per trade. All 36 cells also stay positive at the expensive 50-point cost; 32 of 36 gross CIs are above zero.

### T1-H. Concentration and robustness (base rule, base costs)

| Subset | Trades | Exp (pt) | 95% CI | PF |
|---|---|---|---|---|
| All trades | 603 | +283 | [+89, +490]* | 1.33 |
| 2024-2025 only (excluding 2026) | 416 | +144 | [-36, +349] | 1.20 |
| Excluding the 10 best trades | 593 | +167 | [-16, +358] | 1.19 |
| Excluding the best 5% (30 trades) | 573 | -53 | [-230, +121] | 0.94 |

The 10 best trades supply 42% of the net and the best 30 (5%) supply 118%. 18 of 35 months and 9 of 12 quarters were positive; best quarter 2026Q2 +88,106 points, worst 2026Q1 -21,964 points. Median gross result -0.07R, mean +0.16R; 49% of trades were at some point +1R in profit.

### Reading T1

1. **The vendor's headline numbers replicate on independent data.** PF 1.33 against the author's 1.38, 17 trades per month against 16, +112% on $5,000 at 1% risk after base costs (+134% at the spread-only cost that an MT5 real-tick test most likely embeds) against the author's +137% over the longer Jan 2023-Sep 2026 window, max equity drawdown 21.5% against 17.3%, and 2026 PF 1.52 against the author's 2026 hold-out PF 1.61. Whatever else is said below, the published backtest is not fabricated and is not an artefact of one broker's ticks.
2. **Post-cost expectancy is distinguishable from zero over the whole sample, but only because of 2026.** Base-cost expectancy +283 points per trade (0.13R), 95% CI [+89, +490], CI in R [0.04, 0.23]. By year: 2024 +146 [-62, +349], 2025 +143 [-168, +465], 2026 +593 [+110, +1,055]. The 2024-2025 pool (416 trades) gives +144 [-36, +349], i.e. not distinguishable from zero. 2026 contributed 65% of the net points with 31% of the trades.
3. **The direction carries information: the result is far outside the random-direction distribution.** Coin-flip direction at the same entry bars, fill prices, stop distances, targets, BE and time exits averages -41 points after base costs; the 95th percentile of 50 seeds is +56 and the best seed +128, against the rule's +283. None of 50 seeds matched the rule overall; none in 2024 and 2026; in 2025 three seeds (6%) did. Gross random expectancy is +1 point, so the benchmark is unbiased.
4. **It is not long-gold beta.** Longs and shorts contributed almost identical net points (+84k vs +86k per lot). Gold rose 97% over the period but fell 6% in 2026 with a 28% drawdown, and 2026 was the rule's best year because the *shorts* made +940 points per trade; long-only was +90 per trade in 2026 (not significant) and short-only lost in 2024 and 2025 (-29, -9) and made +768 in 2026. A plain intraday long from 08:00 to 21:00 server on the same eligible days *lost* 59 points per day overall (-491 per day in 2026). Trade results have zero correlation with the day's signed return and 0.47 correlation with its absolute size. The 50-day SMA filter helps (+377* with the trend vs +206 against it) but the counter-trend half is still positive, and the filtered one-sided version does not beat the two-sided rule (+284 vs +283 per trade on fewer trades).
5. **What it is instead: an intraday trend-day capture whose pay-off scales with volatility.** The average Asian range went from $11.6 (0.41% of price) in 2024 to $26.1 (0.64%) in 2025 and $51.5 (0.93%) in 2026. The rule's profit sits entirely in the days where the range is wider than 0.6% of price and the 0.6% cap pulls the stop inside the range (352 trades, +499 points, CI [+164, +811]); on the 251 narrower days the stop is at the far side of the range and the result is -18 points (CI [-212, +177]). Those wide-range days are 2025-2026 days.
6. **Fat right tail.** 44% win rate, median trade -0.07R, mean +0.16R; the best 5% of trades are more than the entire net. Dropping the 10 best trades leaves +167 [-16, +358]; dropping the best 30 leaves -53. Only 18 of 35 months were positive. A trader would have sat through 17 losing months, a 15-trade losing streak and a 21.5% drawdown to collect this.
7. **Parameter sensitivity is benign in sign, not in significance.** All 36 TP x buffer x window cells are positive after base and after expensive costs; 23 have CIs above zero. The buffer does not matter (0, 20, 50 points give +284, +283, +281). Break-even at 1.5R does not help (TP 2.5R: +295 without BE vs +283 with). TP 2.5-3R beats 1.5-2R. Letting orders expire at 12:00 improves the per-trade result (+320 on 526 trades) and halves the drawdown (16%). Shifting the range window one hour later (04:00-09:00) cuts expectancy to +171 with a CI that includes zero, so the result does depend on where the range is drawn. Removing the 0.30-1.60% range filter changes nothing per trade (+270*) and adds 119 trades, so the filter is not the source of the edge.
8. **Costs are almost irrelevant here, execution risk is not.** The base cost is 2.2% of the average $18.9 stop; gross, spread-only, base and expensive cases differ by 50 points per trade in a +325 gross result. The genuine execution question is slippage on a gold stop order at the London open on a trend day: 2% of fills were gap fills averaging 52 points of slippage in M1 data, and real spikes (the sample BE trade on 2026-07-02 shows a single M1 bar spanning $54) would be worse on a live account than on bid M1 bars.

---

## 6. T2. ATR-scaled Asian-range breakout (MQL5 CodeBase 75586 defaults), XAUUSD and EURUSD

**Rules as run.** Range 03:00-08:00 server (as T1). Daily ATR(14) = mean true range of the 14 completed server-time days before the trading day. Skip unless 0.15 <= range/ATR <= 0.70. Buy stop at high + 0.15 ATR, sell stop at low - 0.15 ATR, OCO. SL = 1.2 ATR from entry (independent of the range), TP = 1.8R. Orders expire at 12:00 (the CodeBase EA cancels unfilled orders four hours into the London window; 21:00 also run); flat at 21:00; one trade per day. Median daily ATR(14): gold $47.6, EURUSD 63 pips.

### T2-XAUUSD (base costs 42 pt; gross in brackets)

| Variant | Eligible days | Trades | Win % | PF | Exp pt net (gross) | Exp (R) | 95% CI exp (pt) | Exp by year 24/25/26 | Return % | MaxDD % | Sharpe | Avg stop (pt) | Exit % SL/TP/time | Longs n / exp | Shorts n / exp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **CodeBase defaults**: buffer 0.15 ATR, SL 1.2 ATR, TP 1.8R, orders expire 12:00 | 643 | 272 | 52.6 | 1.52 | +470.3 (+512.3) | +0.038 | [+32.6, +980.3]* | +18 / +278 / +1596 | +10.6 | 5.4 | 1.16 | 6,762 | 3/2/96 | 139 / +57 | 133 / +902 |
| orders expire 21:00 | 643 | 561 | 53.3 | 1.36 | +303.5 (+345.5) | +0.027 | [+49.4, +578.9]* | +58 / +255 / +690 | +15.9 | 6.9 | 1.29 | 7,365 | 2/1/97 | 309 / +103 | 252 / +549 |
| TP 1.0R | 643 | 272 | 52.6 | 1.35 | +314.8 (+356.8) | +0.024 | [-58.5, +708.5] | -14 / +154 / +1166 | +6.3 | 5.4 | 0.97 | 6,762 | 3/4/93 | 139 / +66 | 133 / +575 |
| TP 2.5R | 643 | 272 | 52.6 | 1.44 | +397.4 (+439.4) | +0.034 | [-6.6, +831.4] | +17 / +293 / +1254 | +9.3 | 5.4 | 1.10 | 6,762 | 3/0/97 | 139 / +57 | 133 / +753 |
| no 0.15-0.70 range/ATR filter | 733 | 300 | 52.3 | 1.32 | +355.5 (+397.5) | +0.035 | [-143.3, +921.1] | +36 / +125 / +1184 | +10.5 | 5.4 | 0.77 | 7,012 | 4/2/93 | 155 / +20 | 145 / +714 |
| buy stop only | 643 | 139 | 51.8 | 1.07 | +57.3 (+99.3) | +0.016 | [-335.1, +441.7] | -26 / +141 / +91 | +2.1 | 3.2 | 0.17 | 6,343 | 3/0/97 | 139 / +57 | 0 / - |
| sell stop only | 643 | 133 | 53.4 | 1.94 | +902.0 (+944.0) | +0.061 | [+130.7, +1,765.8]* | +72 / +437 / +2612 | +8.3 | 3.8 | 1.20 | 7,200 | 2/4/94 | 0 / - | 133 / +902 |

| Cost case (CodeBase defaults) | Trades | Exp (pt) | 95% CI | PF | Return % (1% risk) | Random-dir mean exp | Random 5th pct | Random 95th pct | % random seeds >= actual |
|---|---|---|---|---|---|---|---|---|---|
| gross | 272 | +512.3 | [+74.6, +1,022.3]* | 1.58 | +13.1 | +90.6 | -175.8 | +382.2 | 2 |
| spread15 | 272 | +497.3 | [+59.6, +1,007.3]* | 1.56 | +12.2 | +75.6 | -190.8 | +367.2 | 2 |
| base42 | 272 | +470.3 | [+32.6, +980.3]* | 1.52 | +10.6 | +48.6 | -217.8 | +340.2 | 2 |
| exp50 | 272 | +462.3 | [+24.6, +972.3]* | 1.51 | +10.1 | +40.6 | -225.8 | +332.2 | 2 |

### T2-EURUSD (base costs 1.2 pip; gross in brackets)

| Variant | Eligible days | Trades | Win % | PF | Exp pip net (gross) | Exp (R) | 95% CI exp (pip) | Exp by year 24/25/26 | Return % | MaxDD % | Sharpe | Avg stop (pip) | Exit % SL/TP/time | Longs n / exp | Shorts n / exp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **CodeBase defaults**: buffer 0.15 ATR, SL 1.2 ATR, TP 1.8R, orders expire 12:00 | 658 | 365 | 51.5 | 1.00 | +0.0 (+1.2) | -0.005 | [-4.0, +3.8] | -1 / +5 / -5 | -2.2 | 11.6 | 0.01 | 81 | 3/1/96 | 182 / +0 | 183 / -0 |
| orders expire 21:00 | 658 | 629 | 47.5 | 0.93 | -0.9 (+0.3) | -0.016 | [-3.7, +2.0] | -3 / +3 / -4 | -10.1 | 14.7 | -0.37 | 80 | 3/0/97 | 306 / -0 | 323 / -2 |
| TP 1.0R | 658 | 365 | 51.5 | 0.95 | -0.7 (+0.5) | -0.014 | [-4.6, +2.9] | -2 / +4 / -5 | -5.3 | 11.6 | -0.20 | 81 | 3/4/93 | 182 / -1 | 183 / -1 |
| TP 2.5R | 658 | 365 | 51.5 | 1.02 | +0.2 (+1.4) | -0.002 | [-3.9, +4.1] | -1 / +5 / -5 | -1.2 | 11.6 | 0.06 | 81 | 3/0/96 | 182 / +1 | 183 / -0 |
| no 0.15-0.70 range/ATR filter | 733 | 406 | 52.2 | 0.97 | -0.5 (+0.7) | -0.005 | [-4.4, +3.3] | -1 / +3 / -4 | -2.6 | 10.4 | -0.13 | 81 | 4/0/96 | 198 / -1 | 208 / -0 |
| buy stop only | 658 | 190 | 49.5 | 1.05 | +0.7 (+1.9) | +0.002 | [-4.5, +6.3] | -3 / +6 / -3 | +0.1 | 6.9 | 0.15 | 83 | 2/1/97 | 190 / +1 | 0 / - |
| sell stop only | 658 | 185 | 55.1 | 0.99 | -0.1 (+1.1) | -0.006 | [-5.8, +5.6] | +1 / +4 / -6 | -1.3 | 7.9 | -0.03 | 78 | 5/0/95 | 0 / - | 185 / -0 |

| Cost case (CodeBase defaults) | Trades | Exp (pip) | 95% CI | PF | Return % (1% risk) | Random-dir mean exp | Random 5th pct | Random 95th pct | % random seeds >= actual |
|---|---|---|---|---|---|---|---|---|---|
| gross | 365 | +1.2 | [-2.8, +5.0] | 1.09 | +3.6 | -0.1 | -2.7 | +2.5 | 24 |
| cheap0.8 | 365 | +0.4 | [-3.6, +4.2] | 1.03 | -0.3 | -0.9 | -3.5 | +1.7 | 24 |
| base1.2 | 365 | +0.0 | [-4.0, +3.8] | 1.00 | -2.2 | -1.3 | -3.9 | +1.3 | 24 |
| exp2.1 | 365 | -0.9 | [-4.9, +2.9] | 0.94 | -6.4 | -2.2 | -4.8 | +0.4 | 24 |

### Reading T2

* **Gold:** 96% of trades end at the 21:00 flat because a 1.2-ATR stop (about $68) and a 1.8R target (about $122) are rarely reached in a day; the rule is "enter on the breakout and hold to the close" in disguise. Base-cost expectancy +470 points [+33, +980], PF 1.52, but only 0.04R per trade, so 1% risk compounding yields +10.6% in 35 months. 77% of the net comes from 2026 (+1,596 per trade), and all of it from the short side (sell-stop-only +902* vs buy-stop-only +57, not significant). 2% of random-direction seeds matched it; the random 95th percentile is +340. The range/ATR filter and the TP multiple barely matter. This is the same 2026 short-side volatility capture as T1 with a worse risk/reward geometry.
* **EURUSD:** +0.0 pips after base costs, gross +1.2 pips on an 81-pip stop, CI [-4.0, +3.8]; 24% of random seeds did as well. Nothing there, consistent with the published PF 0.87-1.03 attempts to port the gold rule to EURUSD/GBPUSD.

---

## 7. T3. Night-scalping mean reversion on crosses (AUDNZD, EURCHF, EURGBP, AUDCAD, GBPCAD, NZDCAD, EURAUD) and EURUSD

**Window.** Entries only when the M5 signal bar closes (N1, N3) or the limit order is touched (N2) between 21:00 and 02:00 server; every position is force-closed at 06:00 server at the latest. Friday evenings are skipped (the market closes at 24:00 server on Friday); Thursday-night sessions that run past midnight into Friday are kept. Monday 00:00-02:00 entries (Sunday evening New York) are allowed.

**Variants.** N1 Bollinger fade (M5): BB(20, 2); long when bar t-1 closed below the lower band and bar t closed back inside and below the middle band (mirror for shorts); TP = middle band at signal time; SL = 1.5x or 2x the TP distance from the fill; also with a minimum TP distance of 5 pips. N2 range limit fade: at 21:00 server take the 17:00-21:00 range; sell limit at the high, buy limit at the low, valid until 02:00; TP 6 / SL 12 pips (Fenrir-style 60/120 points) and TP 10 / SL 20; one position at a time, the other limit stays armed after the first position closes. N3 RSI(2) extreme (M5): long when RSI(2) < 5 and close > EMA(200), exit when RSI(2) > 60, after 12 bars, at SL = 2 x ATR(14) or at 06:00; mirror for shorts (> 95, exit < 40); also all-day. Random-direction benchmarks (50 seeds) keep entries, stop and target distances and the time exit (N3: 12 bars or 06:00, without the RSI exit).

### T3-A. Expectancy per trade (pips) by symbol and variant, base costs; gross in brackets; * = 95% CI above zero, (-) = below zero

| Variant | AUDNZD | EURCHF | EURGBP | AUDCAD | GBPCAD | NZDCAD | EURAUD | EURUSD | Pooled 7 crosses |
|---|---|---|---|---|---|---|---|---|---|
| N1 Bollinger fade, SL 1.5x TP | -0.56 (+1.54)(-) n=1725 | -0.43 (+1.47)(-) n=1372 | -0.70 (+1.10)(-) n=1235 | -0.69 (+1.31)(-) n=1448 | -0.37 (+2.03) n=1384 | -0.71 (+1.49)(-) n=1542 | -0.21 (+1.89) n=1545 | -1.01 (+0.49)(-) n=1181 | -0.52 (+1.56)(-) n=10251 |
| N1 Bollinger fade, SL 2x TP | -0.16 (+1.94) n=1641 | -0.22 (+1.68) n=1292 | -0.57 (+1.23)(-) n=1179 | -0.56 (+1.44)(-) n=1366 | -0.22 (+2.18) n=1319 | -0.70 (+1.50)(-) n=1452 | -0.12 (+1.98) n=1448 | -0.90 (+0.60)(-) n=1113 | -0.36 (+1.72)(-) n=9697 |
| N1 Bollinger fade, SL 1.5x, TP >= 5 pips | +1.73 (+3.83)* n=408 | +2.12 (+4.02)* n=279 | +0.93 (+2.73) n=132 | +0.71 (+2.71) n=460 | +0.58 (+2.98) n=840 | +0.63 (+2.83) n=514 | +0.76 (+2.86) n=910 | -0.73 (+0.77) n=503 | +0.92 (+3.07)* n=3543 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | +2.31 (+4.41)* n=401 | +2.19 (+4.09)* n=270 | +1.20 (+3.00) n=129 | +0.74 (+2.74) n=442 | +0.71 (+3.11) n=804 | +0.68 (+2.88) n=495 | +0.75 (+2.85) n=856 | -0.45 (+1.05) n=492 | +1.04 (+3.19)* n=3397 |
| N2 range limit fade, TP 6 / SL 12 | +1.45 (+3.55)* n=669 | +0.80 (+2.70)* n=473 | +0.28 (+2.08) n=432 | +0.24 (+2.24) n=467 | -0.98 (+1.42)(-) n=390 | -0.62 (+1.58) n=521 | +0.13 (+2.23) n=424 | -1.38 (+0.12)(-) n=392 | +0.28 (+2.35)* n=3376 |
| N2 range limit fade, TP 10 / SL 20 | +2.53 (+4.63)* n=658 | +1.27 (+3.17)* n=469 | +0.02 (+1.82) n=428 | -0.10 (+1.90) n=463 | -0.20 (+2.20) n=390 | -0.68 (+1.52) n=519 | +2.05 (+4.15)* n=424 | -1.82 (-0.32)(-) n=392 | +0.80 (+2.87)* n=3351 |
| N3 RSI(2) < 5 / > 95, night window | -1.66 (+0.44)(-) n=909 | -1.36 (+0.54)(-) n=1155 | -1.44 (+0.36)(-) n=1272 | -1.46 (+0.54)(-) n=1211 | -1.51 (+0.89)(-) n=1089 | -1.76 (+0.44)(-) n=1244 | -0.71 (+1.39)(-) n=1114 | -1.08 (+0.42)(-) n=1402 | -1.42 (+0.65)(-) n=7994 |
| N3 RSI(2), all day (contrast) | -1.78 (+0.32)(-) n=5212 | -1.68 (+0.22)(-) n=5952 | -1.71 (+0.09)(-) n=6232 | -1.73 (+0.27)(-) n=5990 | -1.97 (+0.43)(-) n=5449 | -2.03 (+0.17)(-) n=6162 | -1.72 (+0.38)(-) n=5325 | -1.21 (+0.29)(-) n=6367 | -1.80 (+0.26)(-) n=40322 |

### T3-B. Same, "full" costs (base + 1.0 pip rollover widening for entries 23:45-00:15 server + 0.5 pip swap per rollover held, x3 Wednesday)

| Variant | AUDNZD | EURCHF | EURGBP | AUDCAD | GBPCAD | NZDCAD | EURAUD | EURUSD | Pooled 7 crosses |
|---|---|---|---|---|---|---|---|---|---|
| N1 Bollinger fade, SL 1.5x TP | -0.80(-) PF 0.67 | -0.70(-) PF 0.67 | -0.98(-) PF 0.46 | -0.96(-) PF 0.67 | -0.67(-) PF 0.83 | -0.98(-) PF 0.65 | -0.48 PF 0.89 | -1.30(-) PF 0.65 | -0.79(-) PF 0.73 |
| N1 Bollinger fade, SL 2x TP | -0.42(-) PF 0.81 | -0.52(-) PF 0.74 | -0.87(-) PF 0.50 | -0.85(-) PF 0.71 | -0.52 PF 0.87 | -0.98(-) PF 0.66 | -0.40 PF 0.91 | -1.22(-) PF 0.68 | -0.64(-) PF 0.78 |
| N1 Bollinger fade, SL 1.5x, TP >= 5 pips | +1.47* PF 1.47 | +1.81* PF 1.66 | +0.53 PF 1.16 | +0.35 PF 1.08 | +0.22 PF 1.05 | +0.28 PF 1.07 | +0.46 PF 1.08 | -1.10 PF 0.81 | +0.59* PF 1.13 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | +2.02* PF 1.72 | +1.87* PF 1.69 | +0.78 PF 1.25 | +0.35 PF 1.08 | +0.34 PF 1.07 | +0.30 PF 1.07 | +0.43 PF 1.07 | -0.85 PF 0.85 | +0.69* PF 1.16 |
| N2 range limit fade, TP 6 / SL 12 | +0.94* PF 1.43 | +0.28 PF 1.11 | -0.32 PF 0.86 | -0.12 PF 0.96 | -1.20(-) PF 0.67 | -1.02(-) PF 0.72 | -0.09 PF 0.97 | -1.67(-) PF 0.61 | -0.14 PF 0.95 |
| N2 range limit fade, TP 10 / SL 20 | +1.88* PF 1.49 | +0.61 PF 1.19 | -0.68(-) PF 0.75 | -0.63 PF 0.88 | -0.58 PF 0.89 | -1.23(-) PF 0.79 | +1.69* PF 1.38 | -2.30(-) PF 0.63 | +0.24 PF 1.05 |
| N3 RSI(2) < 5 / > 95, night window | -1.85(-) PF 0.23 | -1.57(-) PF 0.19 | -1.65(-) PF 0.08 | -1.66(-) PF 0.23 | -1.70(-) PF 0.39 | -1.97(-) PF 0.18 | -0.95(-) PF 0.61 | -1.24(-) PF 0.32 | -1.62(-) PF 0.28 |
| N3 RSI(2), all day (contrast) | -1.82(-) PF 0.22 | -1.73(-) PF 0.20 | -1.76(-) PF 0.11 | -1.77(-) PF 0.26 | -2.01(-) PF 0.37 | -2.08(-) PF 0.17 | -1.78(-) PF 0.49 | -1.25(-) PF 0.42 | -1.85(-) PF 0.28 |

### T3-C. Detail per variant, pooled over the seven crosses

| Variant | Costs | Avg cost (pips) | Trades | Win % | PF | Exp (pips) | Exp (R) | 95% CI exp | Exp by year 24/25/26 | Avg stop (pips) | Cost % of stop | Avg bars (M1) | Exit % SL/TP/time | Exp long / short | Streak |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1 Bollinger fade, SL 1.5x TP | gross | 0.00 | 10251 | 68.9 | 1.72 | +1.56 | +0.181 | [+1.41, +1.71]* | +1.17 / +1.74 / +1.77 | 7.9 | 0 | 67 | 29/67/4 | +1.64 / +1.48 | 7 |
|  | base | 2.08 | 10251 | 59.5 | 0.82 | -0.52 | -0.261 | [-0.67, -0.37](-) | -0.91 / -0.34 / -0.30 | 7.9 | 26 | 67 | 29/67/4 | -0.44 / -0.60 | 9 |
|  | full | 2.35 | 10251 | 56.4 | 0.73 | -0.79 | -0.314 | [-0.94, -0.64](-) | -1.18 / -0.61 / -0.58 | 7.9 | 30 | 67 | 29/67/4 | -0.71 / -0.88 | 11 |
| N1 Bollinger fade, SL 2x TP | gross | 0.00 | 9697 | 74.8 | 1.78 | +1.72 | +0.163 | [+1.55, +1.88]* | +1.29 / +1.84 / +2.07 | 10.5 | 0 | 77 | 22/73/5 | +1.85 / +1.60 | 5 |
|  | base | 2.08 | 9697 | 64.1 | 0.87 | -0.36 | -0.171 | [-0.53, -0.19](-) | -0.80 / -0.23 / -0.01 | 10.5 | 20 | 77 | 22/73/5 | -0.23 / -0.48 | 8 |
|  | full | 2.37 | 9697 | 60.4 | 0.78 | -0.64 | -0.213 | [-0.82, -0.48](-) | -1.08 / -0.51 / -0.30 | 10.5 | 22 | 77 | 22/73/5 | -0.51 / -0.77 | 9 |
| N1 Bollinger fade, SL 1.5x, TP >= 5 pips | gross | 0.00 | 3543 | 70.8 | 1.83 | +3.07 | +0.214 | [+2.65, +3.48]* | +2.08 / +3.31 / +3.64 | 15.2 | 0 | 117 | 24/67/9 | +3.17 / +2.97 | 8 |
|  | base | 2.15 | 3543 | 70.0 | 1.21 | +0.92 | +0.033 | [+0.50, +1.34]* | -0.07 / +1.17 / +1.49 | 15.2 | 14 | 117 | 24/67/9 | +1.02 / +0.82 | 8 |
|  | full | 2.48 | 3543 | 69.8 | 1.13 | +0.59 | +0.005 | [+0.17, +1.01]* | -0.42 / +0.85 / +1.16 | 15.2 | 16 | 117 | 24/67/9 | +0.69 / +0.49 | 8 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | gross | 0.00 | 3397 | 74.6 | 1.84 | +3.19 | +0.171 | [+2.78, +3.65]* | +2.03 / +3.40 / +3.97 | 20.0 | 0 | 132 | 18/70/12 | +3.43 / +2.95 | 6 |
|  | base | 2.15 | 3397 | 73.7 | 1.24 | +1.04 | +0.035 | [+0.63, +1.50]* | -0.11 / +1.26 / +1.82 | 20.0 | 11 | 132 | 18/70/12 | +1.29 / +0.81 | 6 |
|  | full | 2.50 | 3397 | 73.4 | 1.16 | +0.69 | +0.013 | [+0.28, +1.16]* | -0.49 / +0.92 / +1.48 | 20.0 | 12 | 132 | 18/70/12 | +0.93 / +0.47 | 6 |
| N2 range limit fade, TP 6 / SL 12 | gross | 0.00 | 3376 | 76.8 | 2.05 | +2.35 | +0.196 | [+2.11, +2.57]* | +2.15 / +2.32 / +2.61 | 12.0 | 0 | 129 | 17/73/10 | +2.53 / +2.16 | 4 |
|  | base | 2.07 | 3376 | 75.6 | 1.10 | +0.28 | +0.023 | [+0.04, +0.50]* | +0.08 / +0.24 / +0.54 | 12.0 | 17 | 129 | 17/73/10 | +0.47 / +0.09 | 6 |
|  | full | 2.48 | 3376 | 74.6 | 0.95 | -0.14 | -0.011 | [-0.38, +0.09] | -0.32 / -0.16 / +0.09 | 12.0 | 21 | 129 | 17/73/10 | +0.06 / -0.34 | 8 |
| N2 range limit fade, TP 10 / SL 20 | gross | 0.00 | 3351 | 69.7 | 1.82 | +2.87 | +0.143 | [+2.52, +3.24]* | +2.49 / +2.87 / +3.29 | 20.0 | 0 | 239 | 13/59/28 | +3.18 / +2.55 | 7 |
|  | base | 2.07 | 3351 | 66.9 | 1.19 | +0.80 | +0.040 | [+0.45, +1.17]* | +0.42 / +0.79 / +1.22 | 20.0 | 10 | 239 | 13/59/28 | +1.11 / +0.48 | 9 |
|  | full | 2.63 | 3351 | 65.2 | 1.05 | +0.24 | +0.012 | [-0.12, +0.61] | -0.13 / +0.24 / +0.63 | 20.0 | 13 | 239 | 13/59/28 | +0.57 / -0.10 | 11 |
| N3 RSI(2) < 5 / > 95, night window | gross | 0.00 | 7994 | 58.8 | 1.63 | +0.65 | +0.159 | [+0.56, +0.74]* | +0.64 / +0.62 / +0.69 | 4.4 | 0 | 15 | 21/0/79 | +0.59 / +0.71 | 6 |
|  | base | 2.06 | 7994 | 27.5 | 0.33 | -1.42 | -0.473 | [-1.50, -1.33](-) | -1.43 / -1.44 / -1.38 | 4.4 | 47 | 15 | 21/0/79 | -1.48 / -1.35 | 36 |
|  | full | 2.27 | 7994 | 25.3 | 0.28 | -1.62 | -0.546 | [-1.71, -1.53](-) | -1.64 / -1.64 / -1.58 | 4.4 | 51 | 15 | 21/0/79 | -1.68 / -1.56 | 52 |
| N3 RSI(2), all day (contrast) | gross | 0.00 | 40322 | 56.5 | 1.18 | +0.26 | +0.062 | [+0.22, +0.31]* | +0.29 / +0.28 / +0.21 | 5.4 | 0 | 15 | 24/0/76 | +0.27 / +0.26 | 9 |
|  | base | 2.07 | 40322 | 28.8 | 0.29 | -1.80 | -0.482 | [-1.85, -1.76](-) | -1.78 / -1.78 / -1.86 | 5.4 | 39 | 15 | 24/0/76 | -1.80 / -1.81 | 44 |
|  | full | 2.11 | 40322 | 28.3 | 0.28 | -1.85 | -0.498 | [-1.89, -1.80](-) | -1.82 / -1.83 / -1.90 | 5.4 | 39 | 15 | 24/0/76 | -1.84 / -1.85 | 65 |

### T3-D. Per-symbol detail at base costs for the best-looking variant of each family, with the random-direction benchmark

| Variant | Symbol | Base cost | Trades | Trades / night | Win % | PF | Exp base (pips) | 95% CI | Exp by year 24/25/26 | Exp full costs | Return % (1% risk) | MaxDD % | Sharpe | Random-dir mean | Random 95th pct | % random >= actual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N1 Bollinger fade, SL 2x, TP >= 5 pips | AUDNZD | 2.1 | 401 | 0.54 | 81.8 | 1.85 | +2.31 | [+1.38, +3.18]* | +0.2 / +3.0 / +3.6 | +2.02 | +70 | 6.0 | 1.42 | -1.34 | -0.64 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | EURCHF | 1.9 | 270 | 0.36 | 75.9 | 1.84 | +2.19 | [+1.06, +3.38]* | +0.7 / +1.9 / +5.2 | +1.87 | +33 | 4.5 | 1.38 | -1.53 | -0.58 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | EURGBP | 1.8 | 129 | 0.17 | 69.8 | 1.40 | +1.20 | [-0.38, +2.67] | -0.7 / +1.6 / +2.0 | +0.78 | +4 | 5.6 | 0.54 | -1.79 | -0.42 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | AUDCAD | 2.0 | 442 | 0.60 | 71.3 | 1.17 | +0.74 | [-0.45, +1.86] | +0.3 / +0.1 / +1.7 | +0.35 | +2 | 8.6 | 0.15 | -1.96 | -0.82 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | GBPCAD | 2.4 | 804 | 1.08 | 70.9 | 1.15 | +0.71 | [-0.27, +1.67] | +0.0 / +1.2 / +0.6 | +0.34 | +4 | 18.0 | 0.27 | -2.14 | -1.13 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | NZDCAD | 2.2 | 495 | 0.67 | 72.9 | 1.17 | +0.68 | [-0.29, +1.61] | -0.0 / +0.5 / +1.5 | +0.30 | +7 | 13.7 | 0.12 | -2.08 | -1.43 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | EURAUD | 2.1 | 856 | 1.15 | 73.9 | 1.13 | +0.75 | [-0.39, +1.83] | -0.8 / +1.3 / +1.6 | +0.43 | +14 | 18.0 | -0.00 | -2.31 | -1.62 | 0 |
| N1 Bollinger fade, SL 2x, TP >= 5 pips | EURUSD | 1.5 | 492 | 0.66 | 60.2 | 0.92 | -0.45 | [-1.65, +0.71] | -1.7 / -0.1 / +0.2 | -0.85 | -24 | 28.2 | -0.70 | -1.55 | -0.78 | 4 |
| N2 range limit fade, TP 6 / SL 12 | AUDNZD | 2.1 | 669 | 0.90 | 84.9 | 1.69 | +1.45 | [+0.91, +1.96]* | +1.6 / +1.2 / +1.7 | +0.94 | +122 | 10.0 | 3.11 | -1.80 | -1.37 | 0 |
| N2 range limit fade, TP 6 / SL 12 | EURCHF | 1.9 | 473 | 0.64 | 75.5 | 1.35 | +0.80 | [+0.20, +1.36]* | +0.2 / +0.7 / +1.5 | +0.28 | +36 | 9.9 | 1.56 | -1.43 | -0.97 | 0 |
| N2 range limit fade, TP 6 / SL 12 | EURGBP | 1.8 | 432 | 0.58 | 60.6 | 1.14 | +0.28 | [-0.19, +0.73] | -0.1 / +0.4 / +0.6 | -0.32 | +10 | 10.6 | 0.67 | -1.36 | -0.94 | 0 |
| N2 range limit fade, TP 6 / SL 12 | AUDCAD | 2.0 | 467 | 0.63 | 77.1 | 1.08 | +0.24 | [-0.43, +0.90] | +0.2 / +0.3 / +0.2 | -0.12 | +9 | 11.9 | 0.43 | -1.36 | -0.87 | 0 |
| N2 range limit fade, TP 6 / SL 12 | GBPCAD | 2.4 | 390 | 0.53 | 73.3 | 0.73 | -0.98 | [-1.72, -0.20](-) | -1.5 / -0.3 / -1.3 | -1.20 | -28 | 28.9 | -1.44 | -2.38 | -1.81 | 0 |
| N2 range limit fade, TP 6 / SL 12 | NZDCAD | 2.2 | 521 | 0.70 | 73.9 | 0.82 | -0.62 | [-1.30, +0.01] | -0.6 / -1.2 / +0.1 | -1.02 | -24 | 32.9 | -1.07 | -1.91 | -1.51 | 0 |
| N2 range limit fade, TP 6 / SL 12 | EURAUD | 2.1 | 424 | 0.57 | 78.5 | 1.04 | +0.13 | [-0.57, +0.82] | -0.1 / +0.3 / +0.2 | -0.09 | +4 | 15.3 | 0.21 | -2.41 | -1.84 | 0 |
| N2 range limit fade, TP 6 / SL 12 | EURUSD | 1.5 | 392 | 0.53 | 63.5 | 0.67 | -1.38 | [-2.19, -0.58](-) | -1.9 / -2.3 / +0.2 | -1.67 | -37 | 39.8 | -1.98 | -1.42 | -0.88 | 44 |
| N3 RSI(2) < 5 / > 95, night window | AUDNZD | 2.1 | 909 | 1.23 | 21.9 | 0.27 | -1.66 | [-1.89, -1.43](-) | -1.9 / -1.6 / -1.5 | -1.85 | -91 | 90.9 | -7.42 | -2.07 | -2.00 | 0 |
| N3 RSI(2) < 5 / > 95, night window | EURCHF | 1.9 | 1155 | 1.56 | 31.9 | 0.24 | -1.36 | [-1.52, -1.20](-) | -1.5 / -1.3 / -1.3 | -1.57 | -99 | 99.3 | -7.77 | -1.89 | -1.84 | 0 |
| N3 RSI(2) < 5 / > 95, night window | EURGBP | 1.8 | 1272 | 1.71 | 19.3 | 0.11 | -1.44 | [-1.55, -1.34](-) | -1.3 / -1.6 / -1.5 | -1.65 | -100 | 99.9 | -11.93 | -1.79 | -1.75 | 0 |
| N3 RSI(2) < 5 / > 95, night window | AUDCAD | 2.0 | 1211 | 1.63 | 23.9 | 0.27 | -1.46 | [-1.65, -1.29](-) | -1.4 / -1.6 / -1.4 | -1.66 | -98 | 98.2 | -7.90 | -1.99 | -1.94 | 0 |
| N3 RSI(2) < 5 / > 95, night window | GBPCAD | 2.4 | 1089 | 1.47 | 37.1 | 0.44 | -1.51 | [-1.84, -1.16](-) | -1.6 / -1.7 / -1.1 | -1.70 | -84 | 84.3 | -5.61 | -2.38 | -2.29 | 0 |
| N3 RSI(2) < 5 / > 95, night window | NZDCAD | 2.2 | 1244 | 1.68 | 20.1 | 0.22 | -1.76 | [-1.95, -1.59](-) | -1.7 / -1.6 / -1.9 | -1.97 | -100 | 99.6 | -9.47 | -2.18 | -2.12 | 0 |
| N3 RSI(2) < 5 / > 95, night window | EURAUD | 2.1 | 1114 | 1.50 | 39.7 | 0.69 | -0.71 | [-1.07, -0.35](-) | -0.7 / -0.6 / -0.8 | -0.95 | -63 | 62.8 | -2.53 | -2.09 | -2.00 | 0 |
| N3 RSI(2) < 5 / > 95, night window | EURUSD | 1.5 | 1402 | 1.89 | 32.7 | 0.36 | -1.08 | [-1.26, -0.90](-) | -1.2 / -1.2 / -0.8 | -1.24 | -97 | 97.2 | -6.18 | -1.49 | -1.45 | 0 |

### T3-E. Where the night profit comes from: the 00:00 server rollover (base costs)

Entries are bucketed by server time. "Rollover" = entries between 23:30 and 00:30 server, i.e. the hour around 17:00 New York, when the Forexite bid feed shows spike bars (95th-percentile jump 6-15 pips on these crosses vs 1 pip at other times) and when real spreads are several times their normal width. Full table in `t3_rollover_check.csv`.

| Variant | Symbol | Trades | Exp all entries [95% CI] | Entries 23:30-00:30 (share) | Exp of those | Share of total net | Trades excl. 23:30-00:30 | Exp excl. 23:30-00:30 [95% CI] |
|---|---|---|---|---|---|---|---|---|
| N1 Bollinger, SL 2x, TP >= 5 | AUDNZD | 401 | +2.31 [+1.38, +3.18] | 163 (41%) | +4.44 | +78% | 238 | +0.85 [-0.44, +2.06] |
| N1 Bollinger, SL 2x, TP >= 5 | EURCHF | 270 | +2.19 [+1.06, +3.38] | 88 (33%) | +4.70 | +70% | 182 | +0.98 [-0.32, +2.28] |
| N1 Bollinger, SL 2x, TP >= 5 | EURGBP | 129 | +1.20 [-0.38, +2.67] | 46 (36%) | +3.66 | +109% | 83 | -0.17 [-2.06, +1.63] |
| N1 Bollinger, SL 2x, TP >= 5 | AUDCAD | 442 | +0.74 [-0.45, +1.86] | 115 (26%) | +3.55 | +125% | 327 | -0.25 [-1.60, +1.03] |
| N1 Bollinger, SL 2x, TP >= 5 | GBPCAD | 804 | +0.71 [-0.27, +1.67] | 225 (28%) | +4.95 | +195% | 579 | -0.94 [-2.05, +0.15] |
| N1 Bollinger, SL 2x, TP >= 5 | NZDCAD | 495 | +0.68 [-0.29, +1.61] | 151 (31%) | +3.62 | +163% | 344 | -0.61 [-1.80, +0.53] |
| N1 Bollinger, SL 2x, TP >= 5 | EURAUD | 856 | +0.75 [-0.39, +1.83] | 225 (26%) | +5.21 | +182% | 631 | -0.84 [-2.27, +0.49] |
| N1 Bollinger, SL 2x, TP >= 5 | EURUSD | 492 | -0.45 [-1.65, +0.71] | 87 (18%) | +2.58 | -101% | 405 | -1.10 [-2.41, +0.19] |
| N1 Bollinger, SL 2x, TP >= 5 | **Pooled crosses** | 3397 | +1.04 [+0.63, +1.50] | 1013 (30%) | +4.49 | +128% | 2384 | **-0.42 [-0.96, +0.10]** |
| N2 limit fade, TP 6 / SL 12 | AUDNZD | 669 | +1.45 [+0.91, +1.96] | 205 (31%) | +2.41 | +51% | 464 | +1.03 [+0.39, +1.63] |
| N2 limit fade, TP 6 / SL 12 | EURCHF | 473 | +0.80 [+0.20, +1.36] | 96 (20%) | +3.57 | +91% | 377 | +0.09 [-0.56, +0.77] |
| N2 limit fade, TP 6 / SL 12 | EURGBP | 432 | +0.28 [-0.19, +0.73] | 74 (17%) | +1.73 | +105% | 358 | -0.02 [-0.55, +0.52] |
| N2 limit fade, TP 6 / SL 12 | AUDCAD | 467 | +0.24 [-0.43, +0.90] | 67 (14%) | +3.25 | +193% | 400 | -0.26 [-0.97, +0.44] |
| N2 limit fade, TP 6 / SL 12 | GBPCAD | 390 | -0.98 [-1.72, -0.20] | 52 (13%) | +2.77 | -38% | 338 | -1.55 [-2.41, -0.71] |
| N2 limit fade, TP 6 / SL 12 | NZDCAD | 521 | -0.62 [-1.30, +0.01] | 99 (19%) | +1.75 | -54% | 422 | -1.17 [-2.00, -0.40] |
| N2 limit fade, TP 6 / SL 12 | EURAUD | 424 | +0.13 [-0.57, +0.82] | 55 (13%) | +2.77 | +285% | 369 | -0.27 [-1.08, +0.51] |
| N2 limit fade, TP 6 / SL 12 | EURUSD | 392 | -1.38 [-2.19, -0.58] | 15 (4%) | +1.43 | -4% | 377 | -1.49 [-2.32, -0.67] |
| N2 limit fade, TP 6 / SL 12 | **Pooled crosses** | 3376 | +0.28 [+0.04, +0.50] | 648 (19%) | +2.55 | +177% | 2728 | **-0.26 [-0.54, +0.00]** |
| N2 limit fade, TP 10 / SL 20 | AUDNZD | 658 | +2.53 [+1.69, +3.34] | 198 (30%) | +4.65 | +55% | 460 | +1.62 [+0.60, +2.65] |
| N2 limit fade, TP 10 / SL 20 | EURCHF | 469 | +1.27 [+0.50, +2.03] | 94 (20%) | +5.03 | +80% | 375 | +0.32 [-0.59, +1.21] |
| N2 limit fade, TP 10 / SL 20 | EURGBP | 428 | +0.02 [-0.56, +0.60] | 72 (17%) | +1.27 | n/m | 356 | -0.23 [-0.87, +0.39] |
| N2 limit fade, TP 10 / SL 20 | AUDCAD | 463 | -0.10 [-1.08, +0.92] | 64 (14%) | +5.05 | n/m | 399 | -0.93 [-2.14, +0.23] |
| N2 limit fade, TP 10 / SL 20 | GBPCAD | 390 | -0.20 [-1.43, +0.98] | 52 (13%) | +5.77 | n/m | 338 | -1.12 [-2.44, +0.16] |
| N2 limit fade, TP 10 / SL 20 | NZDCAD | 519 | -0.68 [-1.75, +0.32] | 97 (19%) | +2.66 | -73% | 422 | -1.44 [-2.68, -0.28] |
| N2 limit fade, TP 10 / SL 20 | EURAUD | 424 | +2.05 [+0.92, +3.24] | 55 (13%) | +7.30 | +46% | 369 | +1.27 [-0.01, +2.48] |
| N2 limit fade, TP 10 / SL 20 | EURUSD | 392 | -1.82 [-2.94, -0.64] | 16 (4%) | +2.12 | -5% | 376 | -1.99 [-3.23, -0.80] |
| N2 limit fade, TP 10 / SL 20 | **Pooled crosses** | 3351 | +0.80 [+0.45, +1.17] | 632 (19%) | +4.38 | +104% | 2719 | **-0.04 [-0.45, +0.38]** |

(n/m = the total net is near zero, so the share is not meaningful.) In addition, trades that enter and exit within the same M1 bar, which only happens when a limit order is filled inside a spike that reverses within the minute, are 7% of N2 TP 6 trades and supply 54% of its pooled net (+2.1 pips each); 3% of N2 TP 10 trades supply 18%.

### T3-F. Night cost assumptions actually applied

| Symbol_variant | Base cost (pips RT) | % entries 23:45-00:15 (+1.0 pip) | % positions held across 00:00 (swap) | Trades |
|---|---|---|---|---|
| AUDNZD_N1_bb_sl2.0x_mintp5 | 2.1 | 12.2 | 19.7 | 401 |
| AUDNZD_N2_limit_tp6_sl12 | 2.1 | 25.7 | 33.0 | 669 |
| EURCHF_N1_bb_sl2.0x_mintp5 | 1.9 | 9.3 | 30.4 | 270 |
| EURCHF_N2_limit_tp6_sl12 | 1.9 | 16.1 | 48.0 | 473 |
| EURGBP_N1_bb_sl2.0x_mintp5 | 1.8 | 8.5 | 37.2 | 129 |
| EURGBP_N2_limit_tp6_sl12 | 1.8 | 11.8 | 64.8 | 432 |
| AUDCAD_N1_bb_sl2.0x_mintp5 | 2.0 | 7.9 | 37.8 | 442 |
| AUDCAD_N2_limit_tp6_sl12 | 2.0 | 9.0 | 40.0 | 467 |
| GBPCAD_N1_bb_sl2.0x_mintp5 | 2.4 | 11.8 | 33.5 | 804 |
| GBPCAD_N2_limit_tp6_sl12 | 2.4 | 10.5 | 18.5 | 390 |
| NZDCAD_N1_bb_sl2.0x_mintp5 | 2.2 | 10.3 | 33.7 | 495 |
| NZDCAD_N2_limit_tp6_sl12 | 2.2 | 13.2 | 38.0 | 521 |
| EURAUD_N1_bb_sl2.0x_mintp5 | 2.1 | 10.0 | 29.4 | 856 |
| EURAUD_N2_limit_tp6_sl12 | 2.1 | 9.9 | 18.2 | 424 |
| EURUSD_N1_bb_sl2.0x_mintp5 | 1.5 | 3.5 | 46.1 | 492 |
| EURUSD_N2_limit_tp6_sl12 | 1.5 | 1.8 | 38.5 | 392 |

### Reading T3

* **N3 RSI(2) is dead on every symbol, night or day:** pooled -1.42 pips per trade at base costs (CI [-1.50, -1.33]), PF 0.33, because the 2 x ATR stop at night is 4.4 pips and the cost is 47% of it. Gross it has a small real edge (+0.65 pips, CI above zero), the same picture as round one on EURUSD and gold.
* **The plain Bollinger fade (N1 without a minimum target) loses on every cross:** pooled -0.52 pips [-0.67, -0.37] at base costs; gross +1.56 against a 2.1-pip cost.
* **The variants that look good at base costs are the filtered Bollinger fade (TP >= 5 pips) and the range limit fades:** pooled +1.04 [+0.63, +1.50] (N1, SL 2x, TP >= 5), +0.80 [+0.45, +1.17] (N2 10/20), +0.28 [+0.04, +0.50] (N2 6/12); on AUDNZD and EURCHF individually with CIs above zero; well above the random-direction 95th percentile everywhere (random is about -cost). At "full" costs the pooled N1 variant keeps a positive CI (+0.69 [+0.28, +1.16]) and the N2 variants do not (+0.24 and -0.14).
* **But the whole pooled profit comes from the hour around the 00:00 server rollover.** Entries between 23:30 and 00:30 are 19-30% of the trades and make +4.4 to +4.5 pips each, i.e. 104-177% of the pooled net; the other 70-80% of the trades, taken outside that hour, are -0.42 [-0.96, +0.10], -0.26 [-0.54, +0.00] and -0.04 [-0.45, +0.38] pips for the three variants. On the single symbols only AUDNZD keeps a positive CI outside the rollover hour (N2 6/12: +1.03 [+0.39, +1.63]; N2 10/20: +1.62 [+0.60, +2.65]; N1: +0.85 [-0.44, +2.06]), one cross of seven and before the full-cost add-ons, which took 0.5 pip off AUDNZD's N2 result overall.
* **Why the rollover profit should not be believed.** The sample N2 fill printed in `t5_sanity_log.txt` is typical: AUDNZD at 23:45 server the bid jumps from 1.1001 to 1.1012 and prints a 20-pip high within one minute; the sell limit at the range high fills at 1.1027 and the 6-pip target is hit in the same bar. The feed's 00:00 bars have a 95th-percentile open-to-previous-close jump of 10 pips (AUDNZD) against 1 pip at any other time. Those minutes are precisely when ECN spreads on crosses are 3-10 pips (round-one KQ5: EUR/GBP 0.5 -> 3.2 pips, peaks 5.5; crosses 6-12x), when liquidity is thinnest and when limit fills are routinely requoted; on bid-only data the buy side of such a trade is unknown and the +1.0 pip add-on is a token. Fading a dealing-desk bid spike and taking profit when it reverts a minute later is a backtest artefact unless the broker really fills limit orders at those prices, and the vendors' own advice ("avoid the 00:00-01:00 rollover hour") says they do not.
* **Everything else about the night fades is as expected:** win rates 70-85% with average losses 1.5-2x average wins, 0.4-1.2 trades per night per symbol, costs 10-26% of the stop, and the "edge" appearing only in 2025-2026 for N1 (2024 was -0.1 pip pooled). EURUSD is negative in every variant.

---

## 8. T4. Breedon-Ranaldo time-of-day pattern on EURUSD (academic benchmark)

Short EURUSD at 07:00 UTC, close 13:00 UTC; long at 13:00 UTC, close 21:00 UTC; every weekday, no stop, no target.

| Leg | Costs (pips RT) | Trades | Win % | Exp (pips) | 95% CI exp | Total pips | Sharpe | PF | Total pips 24/25/26 | Exp 24/25/26 | Sharpe 24/25/26 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Short 07:00-13:00 UTC | gross | 742 | 51.6 | +0.21 | [-1.79, +2.14] | 156 | 0.12 | 1.02 | +300 / -303 / +159 | +1.15 / -1.16 / +0.72 | +0.71 / -0.58 / +0.50 |
|  | cheap0.8 | 742 | 51.6 | -0.59 | [-2.59, +1.34] | -438 | -0.34 | 0.94 | +91 / -512 / -17 | +0.35 / -1.96 / -0.08 | +0.22 / -0.98 / -0.05 |
|  | base1.2 | 742 | 50.1 | -0.99 | [-2.99, +0.94] | -734 | -0.58 | 0.91 | -13 / -616 / -105 | -0.05 / -2.36 / -0.48 | -0.03 / -1.18 / -0.33 |
| Long 13:00-21:00 UTC | gross | 652 | 47.7 | +0.01 | [-2.33, +2.32] | 5 | 0.00 | 1.00 | -164 / +278 / -109 | -0.71 / +1.20 / -0.57 | -0.39 / +0.52 / -0.29 |
|  | cheap0.8 | 652 | 47.7 | -0.79 | [-3.13, +1.52] | -517 | -0.39 | 0.93 | -349 / +93 / -261 | -1.51 / +0.40 / -1.37 | -0.83 / +0.18 / -0.70 |
|  | base1.2 | 652 | 46.3 | -1.19 | [-3.53, +1.12] | -777 | -0.58 | 0.90 | -441 / +1 / -337 | -1.91 / +0.00 / -1.77 | -1.05 / +0.00 / -0.90 |
| Both legs | gross | 1394 | 49.8 | +0.12 | [-1.45, +1.61] | 161 | 0.09 | 1.01 | +136 / -25 / +50 | +0.28 / -0.05 / +0.12 | +0.22 / -0.03 / +0.10 |
|  | cheap0.8 | 1394 | 49.8 | -0.68 | [-2.25, +0.81] | -954 | -0.52 | 0.94 | -258 / -419 / -278 | -0.52 / -0.85 / -0.68 | -0.42 / -0.57 / -0.58 |
|  | base1.2 | 1394 | 48.4 | -1.08 | [-2.65, +0.41] | -1,512 | -0.82 | 0.90 | -454 / -615 / -442 | -0.92 / -1.25 / -1.08 | -0.73 / -0.84 / -0.92 |
| Reverse of both legs (contrast) | gross | 1394 | 47.7 | -0.12 | [-1.61, +1.45] | -161 | -0.09 | 0.99 | -136 / +25 / -50 | -0.28 / +0.05 / -0.12 | -0.22 / +0.03 / -0.10 |
|  | cheap0.8 | 1394 | 47.7 | -0.92 | [-2.41, +0.65] | -1,276 | -0.69 | 0.92 | -530 / -369 / -378 | -1.08 / -0.75 / -0.92 | -0.85 / -0.50 / -0.78 |
|  | base1.2 | 1394 | 46.4 | -1.32 | [-2.81, +0.25] | -1,834 | -0.99 | 0.88 | -726 / -565 / -542 | -1.48 / -1.15 / -1.32 | -1.17 / -0.77 / -1.12 |

(The long leg has 652 rather than 742 observations because the 21:00 UTC exit does not exist on summer Fridays, when the market closes at 20:58 UTC, and those days are skipped.)

**Reading T4.** The pattern is gone. Gross, the two legs make +0.21 and +0.01 pips per day, +161 pips in total over 35 months, Sharpe 0.09, CI [-1.45, +1.61]; the random-direction band on the same legs is [-1.08, +0.97], so the sign is noise. After 0.8 or 1.2 pips of cost it is -0.7 to -1.1 pips per leg. The year signs flip (short leg +1.15 / -1.16 / +0.72 pips per day). Breedon and Ranaldo's Sharpe 1.3 / 0.9 on 1997-2007 EBS data does not exist in 2024-2026 EURUSD minute data, with or without costs.

---

## 9. T5. Sanity and robustness summary

* Look-ahead: ranges are built only from bars stamped before the order time; M5 signals fill at the first M1 bar after the M5 close; daily ATR and SMA use completed days only (0 violations in the independent re-derivation, section 4).
* Pending-order fills: stop and limit orders fill only when the M1 high/low crosses the level, at the level, or at the open when the bar opens through it (0 violations across 603 T1, 272 T2 and 400 re-derived N2 fills).
* OCO: the first touched level fills, the other never does; both-in-one-bar tie-break by proximity to the open (0 violations); one fill per day (603 trades on 603 days; T2 0 duplicates).
* Trade counts: T1 trades on 99% of eligible days and 81% of all weekdays; T2 gold fills on 42% of eligible days with the 4-hour order window; night variants 0.4-1.2 trades per night.
* T1 sensitivity: 36 of 36 TP x buffer x window cells positive after base costs, 23 with CIs above zero (section 5, T1-G); the 04:00-09:00 window row is uniformly weaker and never significant.
* One engine issue found and fixed during the checks (floating-point representation of price levels, now a 1e-7 tolerance); the fix changed no T1 number and moved T3 numbers by at most 0.1 pip.

---

## 10. Findings

1. **The gold London-range breakout (blog 777540) replicates.** On independent bid M1 data, in broker server time, the exact rule gives PF 1.33, +283 points ($2.83/oz) per trade after 42 points of costs, +112% on $5,000 at 1% risk with a 21.5% maximum drawdown, 17 trades a month; the vendor reported PF 1.38, +137% and 17.3% over a longer window, and our 2026 PF 1.52 sits next to their 2026 hold-out PF 1.61. The published result is real in the sense that the rule, as described, produced those numbers in this period.
2. **Post-cost expectancy is distinguishable from zero over the full 35 months (CI [+89, +490] points, [0.04, 0.23] R) and from the random-direction baseline (0 of 50 coin-flip seeds reached it; random mean -41, 95th percentile +56).** Those are the two tests the brief asked for and the gold breakout passes both.
3. **But the significance comes from one year.** 2024 (+146, CI [-62, +349]) and 2025 (+143, [-168, +465]) are each indistinguishable from zero and so is their pool (+144, [-36, +349]); 2026 alone is +593 [+110, +1,055] and supplies 65% of the net. The best 5% of trades are 118% of the net and only 18 of 35 months were positive. A trader who started in January 2024 would have been, after two years and 416 trades, unable to tell the rule from noise.
4. **The gold breakout's return is not explained by the gold trend.** Longs and shorts earned the same net; short-only lost in 2024-2025 and made its whole profit in 2026 while gold fell 6%; long-only was never significant; a plain 08:00-21:00 long on the same days lost 59 points a day; trade results have zero correlation with the day's signed gold return. It is explained by **volatility**: results correlate 0.47 with the absolute daily move, the breakout direction matched the day's close-to-close direction 71% of the time, the Asian range quadrupled from $11.6 (2024) to $51.5 (2026), and all of the profit sits in the 352 days whose range exceeded 0.6% of price (+499*), none in the 251 narrower days (-18). This is intraday trend-day continuation in a historically volatile gold market, not a timing edge that exists in calm markets.
5. **The T1 parameter surface is robustly positive in sign but only half of it is significant**, the one-hour-later window is not, break-even management is useless (removing it improves the result), the buffer and the 0.30-1.60% range filter are irrelevant, and letting unfilled orders expire at 12:00 improves per-trade results and drawdown. Costs hardly matter (2% of the stop); real-world slippage on gold stop orders during London/New York trend days and news spikes (one sample trade sits inside a single $54 M1 bar) is the unmodelled risk.
6. **The ATR-scaled CodeBase 75586 variant on gold is the same 2026 short-side volatility capture with a worse structure:** 96% of trades end at the 21:00 flat because a 1.2-ATR stop and 1.8R target are rarely hit intraday; +470 points per trade [+33, +980] but only 0.04R and +10.6% at 1% risk; 77% of the net from 2026 and all of it from sell stops (buy-stop-only +57, not significant); 2% of random seeds matched it. **On EURUSD the same rule is exactly zero** (+0.0 pip after base costs, CI [-4.0, +3.8], 24% of random seeds as good).
7. **Night-scalping RSI(2) fades are reliably negative on all eight symbols** (-1.4 pips per trade pooled, CI [-1.50, -1.33]), costs being half the 4-pip stop; the plain Bollinger fade is negative too (-0.52 [-0.67, -0.37]). Both have a small gross edge (+0.65 and +1.56 pips) that is smaller than the cheapest realistic cost, exactly as in round one.
8. **The night variants that look profitable at base costs (filtered Bollinger fade, range limit fades on AUDNZD/EURCHF/EURAUD; pooled +0.3 to +1.0 pips with CIs above zero and far above the random baseline) owe their entire pooled profit to entries in the hour around the 00:00 server rollover**, where the bid feed prints 10-pip spike bars that revert within minutes: those 19-30% of trades make +4.4 pips each and 104-177% of the net; outside that hour the pooled results are -0.42 [-0.96, +0.10], -0.26 [-0.54, 0.00] and -0.04 [-0.45, +0.38] pips. Only AUDNZD retains a positive CI outside the rollover hour (limit fade +1.0 to +1.6 pips at base costs), one cross of seven and before the rollover/swap add-ons. We consider the rollover profit a data and execution artefact (bid-only spikes at the minute of the day with the widest spreads and the most requotes), so the honest reading is: **no night-scalping variant shows a post-cost expectancy distinguishable from zero on clean minutes, and none would survive the real rollover spread.**
9. **The "full" night cost case (rollover add-on and swap) alone turns the pooled limit fades from +0.80/+0.28 to +0.24/-0.14 pips**, which shows how thin these structures are: with 6-20-pip targets, 0.5-1.5 pips of swap and widening is the difference between a positive and a negative sample.
10. **The Breedon-Ranaldo EURUSD time-of-day pattern no longer exists:** +0.12 pips per leg gross (CI [-1.45, +1.61], inside the random band [-1.08, +0.97]), -1.08 after 1.2 pips of cost, year signs alternating, Sharpe 0.09 gross.
11. **For each candidate, the answer to "distinguishable from zero after costs?" and "distinguishable from random direction?"** is: gold London-range breakout, yes and yes over 2024-2026, no and partly in 2024-2025 alone; ATR breakout on gold, yes (barely, lower CI bound +33 points) and yes, but 2026-only and short-only; ATR breakout on EURUSD, no and no; night RSI(2) and plain Bollinger fades, significantly negative; filtered Bollinger and limit fades, yes and yes at base costs on the full sample, **no** once the rollover hour is removed (except AUDNZD limit fades, marginal); Breedon-Ranaldo, no and no.
12. **Multiple comparisons.** This round ran about 45 gold-breakout variants, 64 night cells and several benchmarks. With that many looks, a handful of CIs above zero is expected by chance; the gold result's robustness across the 36-cell grid and against random direction is what makes it more than that, and the night results' collapse outside one hour is what makes them less.
13. **Caveats that cut both ways.** Bid-only quotes (stop fills on the bid are slightly early for buys; the ask side at the rollover is unknown and would hurt the night fades further); 1-decimal gold and 4-digit crosses (touch detection rounded to the tick, conservative tie-breaks); fixed spreads except for a 1-pip rollover token; no requotes, stop-level rules or partial fills; parameters taken from the published descriptions and not optimised; and 35 months, which is enough to kill high-frequency candidates and to confirm the gold breakout over the sample as a whole but not year by year.

**Bottom line.** Of the four candidate families, one (the gold London-range breakout) has a genuine, replicable, post-cost positive expectancy over January 2024 to November 2026 that is not long-gold beta but is a volatility-regime effect concentrated in 2026 and in the fattest 5% of trades, with two of three calendar years statistically flat; one (ATR breakout) is the same effect on gold and nothing on EURUSD; one (night scalping on crosses) shows no edge outside the rollover minutes where the data cannot be trusted; and one (Breedon-Ranaldo) has disappeared.

## 11. Files

* Code: `backtest_code/round2/` (`r2_engine.py` server time, BE simulator, costs; `build_dataset_r2.py`; `t1_gold_breakout.py`; `t2_atr_breakout.py`; `t3_night.py`; `t3_rollover_check.py`; `t4_breedon_ranaldo.py`; `t5_sanity.py`; `make_report_r2.py`; `run_all_r2.sh`).
* Results: `backtest_code/round2/results/` (`t1_master.csv`, `t1_by_year.csv`, `t1_splits.csv`, `t1_random.csv`, `t1_sensitivity.csv`, `t1_benchmarks.csv`, `t1_range_stats.csv`, `t2_*.csv`, `t3_master.csv`, `t3_by_year.csv`, `t3_random.csv`, `t3_rollover_check.csv`, `t4_*.csv`, `*_stats.json`, run logs, `t5_sanity_log.txt`, `tables_r2.md`, and the per-variant trade lists in `trades/`).
