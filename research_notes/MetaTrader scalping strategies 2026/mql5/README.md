# LondonRangeBreakout — MT5 research EA for the Asian-range / London-open breakout

**This is a research tool, not a trading product and not a profit guarantee.** It exists so you can
test the most-circulated 2025-2026 "gold London breakout" rule set on *your* broker's data, with real
ticks, real spread and commission, before risking a cent. No win rate, profit factor, return or
drawdown is claimed for it anywhere in this folder. The published numbers for this strategy family
(see `../session_breakout_news_scalping.md` and `../gold_xauusd_scalping.md`) are vendor-run, mostly
without stated costs, and the one independent EUR/USD test found was a net loser.

Files in this folder:

| File | Purpose |
|---|---|
| `LondonRangeBreakout.mq5` | The Expert Advisor source (compile in MetaEditor, MT5 only). |
| `LondonRangeBreakout_XAUUSD.set` | Example input preset for gold (2-digit XAUUSD). |
| `LondonRangeBreakout_EURUSD.set` | Example input preset for a 5-digit forex major. |
| `README.md` | This file. |

No DLLs, no file I/O, no network calls. Single-position logic; runs on hedging and netting accounts.

---

## 1. What the EA does

Every trading day (server time, see section 4 for the time-zone caveat):

1. **Range.** From `RangeStartHour:RangeStartMinute` to `RangeEndHour:RangeEndMinute` it collects the
   completed M1 bars (or chart-timeframe bars) and records the highest high and lowest low.
   The range can start on the previous calendar day (e.g. 22:00-07:00).
2. **Range filters.** The day is skipped if the range width is below `MinRangePctOfPrice` or above
   `MaxRangePctOfPrice` percent of price (default 0.30 % / 1.60 %), or outside `MinRangePoints` /
   `MaxRangePoints` if those are set. Weekend "days" and days with too few bars are skipped.
3. **Entry** (only between `TradeStartHour` and `TradeEndHour`, not during a news blackout, not when
   the spread exceeds `MaxSpreadPoints`):
   * `ENTRY_STOP_ORDERS` (default): at the start of the window it places a **Buy Stop** at
     `rangeHigh + BufferPoints` and a **Sell Stop** at `rangeLow - BufferPoints`, each with SL and TP
     attached. When one fills, the other is deleted (OCO). Unfilled stops are deleted at
     `TradeEndHour` (and carry a server-side expiration at that time when the broker supports it).
   * `ENTRY_CLOSE_BEYOND`: on each new bar of the chart timeframe it checks whether the bar that just
     closed finished at least `BreakoutATRMult x ATR(ATRPeriod)` beyond the range; if so it enters at
     market in that direction.
4. **Stop loss.** `SL_OPPOSITE_RANGE` (default) puts the stop at the far side of the range;
   `SL_ATR` uses `SLATRMult x ATR`. In both modes the distance is capped at `MaxSLPctOfPrice` percent
   of price. If the resulting distance is below the broker's stops level the trade is skipped
   (`SkipIfStopsLevelViolated=true`) or the stop is widened (`false`).
5. **Take profit** at `TakeProfitR` times the stop distance (0 = none).
6. **Management.** At `MoveToBreakevenAtR` R of open profit the stop goes to entry
   (+ `BreakevenOffsetPoints`). Optional ATR trailing stop (`TrailATRMult`, off by default).
7. **Hard cutoff.** At `ForceCloseHour` every open position is closed and every pending order deleted.
   Positions that somehow survive into the next day are closed on the next tick.
8. **One fill per day** by default (`OneTradePerDay=true`). With `false`, the EA re-arms after an exit
   up to `MaxTradesPerDay` fills while still inside the window.
9. **Position size.** `RiskPercent` of current balance divided by the money lost between entry and stop
   for one lot (computed with `OrderCalcProfit`, cross-checked against tick value / tick size, and a
   warning is logged if the two disagree by more than 20 %). Rounded *down* to the volume step, clamped
   to min/max volume, reduced if free margin is insufficient. `FixedLots > 0` overrides all of this.

Everything above is logged to the Experts/Journal tab: the range and its verdict, every order, fill,
modification and exit, and a one-line summary per day.

---

## 2. Inputs

All times are **broker server time** unless `UseServerTime=false` (see section 4).

### Range definition
| Input | Default | Meaning |
|---|---|---|
| `RangeStartHour`, `RangeStartMinute` | 0, 0 | Start of the box. If start >= end the box begins on the previous day. |
| `RangeEndHour`, `RangeEndMinute` | 7, 0 | End of the box (exclusive). Must be <= `TradeStartHour`. |
| `RangeSource` | `RANGE_M1` | Build the range from completed M1 bars (recommended) or from the chart timeframe. |
| `MinRangeBars` | 30 | Skip the day if fewer bars than this fall inside the box (missing data / holiday guard). |
| `UseServerTime` | true | `true`: all hour inputs are server time. `false`: hour inputs are UTC and are shifted by `ServerToUTCOffsetHours` (fixed offset, no DST handling). Keep `true` unless you know what you are doing. |
| `ServerToUTCOffsetHours` | 2 | Server minus UTC, in hours. Used for the UTC equivalents printed in the log, and for conversion only when `UseServerTime=false`. |

### Trading window
| Input | Default | Meaning |
|---|---|---|
| `TradeStartHour` | 7 | Entries (stop placement or market entries) allowed from this hour. |
| `TradeEndHour` | 10 | Entries allowed *before* this hour; unfilled stops are deleted at this hour. |
| `ForceCloseHour` | 12 | Close positions and delete pendings at this hour. Must be >= `TradeEndHour`. |
| `OneTradePerDay` | true | Max one fill per day. When true, the remaining stop is always deleted after a fill. |
| `MaxTradesPerDay` | 2 | Only used when `OneTradePerDay=false`. |

### Entry
| Input | Default | Meaning |
|---|---|---|
| `EntryMode` | `ENTRY_STOP_ORDERS` | `ENTRY_STOP_ORDERS` = OCO stop orders at the range edges; `ENTRY_CLOSE_BEYOND` = market entry on a bar close beyond the range by `BreakoutATRMult x ATR`. |
| `BufferPoints` | 20 | Distance beyond the range for stop orders, in **points** (the symbol's smallest price increment). XAUUSD quoted to 2 decimals: 20 points = $0.20. EURUSD quoted to 5 decimals: 20 points = 2.0 pips. On a 3-decimal gold feed 20 points would be $0.02, so check your symbol's digits. |
| `CancelOppositeOnFill` | true | OCO behaviour. Ignored (forced on) while `OneTradePerDay=true`. |
| `BreakoutATRMult` | 0.15 | `ENTRY_CLOSE_BEYOND` only: required close distance beyond the range, in ATRs. |
| `ATRPeriod` | 14 | ATR period, calculated on the **chart timeframe** (so M5 and M15 charts give different ATRs). |

### Range filters (0 disables a filter)
| Input | Default | Meaning |
|---|---|---|
| `MinRangePctOfPrice` | 0.30 | Skip the day if range / mid-price x 100 is below this. |
| `MaxRangePctOfPrice` | 1.60 | Skip the day if above this. |
| `MinRangePoints`, `MaxRangePoints` | 0, 0 | Absolute alternatives in points. |

For EURUSD at ~1.08 a 30-pip Asian range is about 0.28 %, so the gold defaults (0.30 %-1.60 %) would
skip most forex days; the EURUSD preset uses 0.10 %-0.60 %.

### Stop loss / take profit / management
| Input | Default | Meaning |
|---|---|---|
| `SLMode` | `SL_OPPOSITE_RANGE` | `SL_OPPOSITE_RANGE` or `SL_ATR`. The published close-beyond variant used an ATR stop; the stop-order variant used the far side of the range. |
| `MaxSLPctOfPrice` | 0.60 | Cap on the stop distance as % of price (applied in both SL modes; 0 = no cap). |
| `SLATRMult` | 0.8 | `SL_ATR` only: stop distance in ATRs. |
| `TakeProfitR` | 1.5 | TP as a multiple of the stop distance; 0 = no TP (exit only by stop, trail or `ForceCloseHour`). |
| `MoveToBreakevenAtR` | 1.0 | Move SL to entry when open profit reaches this many R; 0 = off. |
| `BreakevenOffsetPoints` | 0 | Points beyond entry for the break-even stop (e.g. to cover commission). |
| `TrailATRMult` | 0.0 | ATR trailing stop multiple; 0 = off. Only ever tightens the stop. |

### Filters
| Input | Default | Meaning |
|---|---|---|
| `MaxSpreadPoints` | 80 | No new entries / stop placement while the spread is above this (points). Stop placement is retried on later ticks inside the window. 80 points = $0.80 on 2-digit gold = 8 pips on 5-digit EURUSD, so lower it for forex (the EURUSD preset uses 15). |
| `NewsBlackoutWindows` | "" | Semicolon-separated `HH:MM-HH:MM` windows in schedule time during which no new entries are placed, e.g. `13:25-13:35;14:55-15:05`. Windows may wrap midnight (`23:50-00:10`). Malformed pieces are ignored with a log line. Pending orders already placed are **not** removed during a blackout. |

### Risk sizing
| Input | Default | Meaning |
|---|---|---|
| `RiskPercent` | 1.0 | Percent of **balance** risked between entry and initial stop. Refused above 20. |
| `FixedLots` | 0.0 | If > 0, overrides `RiskPercent`. |
| `SkipIfStopsLevelViolated` | true | When the stop distance is below `SYMBOL_TRADE_STOPS_LEVEL`: skip (true) or widen the stop to the minimum (false). |

If the computed volume is below the symbol's minimum lot the EA trades the minimum lot and logs the
real risk percentage, so small accounts on gold will risk more than `RiskPercent`. Watch for that line.

### Execution
| Input | Default | Meaning |
|---|---|---|
| `MagicNumber` | 20261105 | Identifies this EA's orders and positions. Use a different magic per chart. |
| `DeviationPoints` | 30 | Max slippage for market orders and closes, in points. |
| `TradeComment` | "LRB" | Order comment. |
| `PrintVerbose` | true | Extra log lines (sizing details, trailing modifications, new-day lines). |

Filling policy is detected from `SYMBOL_FILLING_MODE` / execution mode automatically. Pending-order
expiration uses `ORDER_TIME_SPECIFIED` when the symbol allows it, otherwise the EA deletes the orders
itself at `TradeEndHour`.

---

## 3. Running it in the Strategy Tester

1. Copy `LondonRangeBreakout.mq5` to `MQL5\Experts\` (File > Open Data Folder in MT5), open it in
   MetaEditor and press **Compile** (F7). Fix any error the compiler reports before continuing; this
   source was written without access to a compiler and has not been compiled by its author.
2. In MT5 open **View > Strategy Tester** (Ctrl+R). Settings tab:

| Setting | Recommended |
|---|---|
| Expert | `LondonRangeBreakout` |
| Symbol | Your broker's gold symbol (`XAUUSD`, `GOLD`, `XAUUSD.m`...) or `EURUSD`/`GBPUSD`. The symbol must be visible in Market Watch and have tick history. |
| Timeframe | **M5** or **M15**. The range is built from M1 regardless; the timeframe sets the ATR and, in `ENTRY_CLOSE_BEYOND` mode, the breakout bar. Test both. |
| Date | **Custom period**, `2023.01.01` to today. Then also run shorter sub-periods (each calendar year separately). |
| Forward | `No` for the first run; see section 5. |
| Delays | Not "zero latency". Use a realistic value for your broker (e.g. 50-200 ms) or "Random delay". |
| Modelling | **Every tick based on real ticks**. Anything else invents intrabar paths and will fill stop orders at prices that never traded. The first run downloads the tick history and can take a long time. |
| Deposit | The amount you would actually trade, in your account currency (e.g. 10 000 USD). Because the EA sizes from balance the equity curve compounds; use `FixedLots` for a non-compounding, fixed-R comparison. |
| Leverage | Your real account leverage (e.g. 1:100 or 1:30). |
| Optimization | Disabled for single runs. |
| Visualization | Off (much faster). Turn on briefly to watch the range and orders being placed. |

3. **Spread.** With real ticks, leaving the tester spread at **Current** replays the broker's *recorded*
   bid/ask at each tick, which is the most honest option. If you want a pessimistic run, set a fixed
   spread in the tester's spread box (e.g. 25-35 points on 2-digit gold, 8-12 points on EURUSD) and
   check the result still holds.
4. **Commission.** The tester applies whatever commission is stored in the symbol specification. Many
   brokers show 0 there even on commission accounts. Two ways to include it:
   * Create a **Custom symbol** copy (Market Watch > right-click > Symbols > select symbol > *Custom
     Symbol*), set the commission in the "Commission" section of the custom symbol, download/import the
     ticks for it, and test on that symbol; or
   * Run on the real symbol and subtract manually: `trades x lots per trade x round-turn commission`
     (e.g. 715 trades x 0.10 lot x $7 = $500). Compare with the net profit.
   If the strategy is not clearly profitable *after* that subtraction, it is not profitable.
5. Open the **Inputs** tab, load a `.set` file (right-click > Load, or the Load button) or set values by
   hand, and press **Start**. (MT5 saves `.set` files as UTF-16; the presets here are plain text, which
   the terminal normally reads fine. If a load fails, open the file in Notepad and save it as UTF-16 LE,
   or just type the values in.)
6. Read the **Journal** tab at least once: the init block prints the symbol specification, the UTC
   equivalents of your schedule, and warnings. Then read a few days of RANGE/FILL/EXIT lines to confirm
   the EA is doing what you think it is doing.

---

## 4. Time zone: the input that breaks everything if wrong

All hour inputs are **broker server time**. The strategy depends on the range ending at the London
open, so the right numbers differ by broker:

* Find your server offset: attach the EA to any chart on a demo account and read the log line
  `Live check: server time minus GMT is about X hours` (the Strategy Tester cannot tell you this because
  there `TimeGMT()` equals server time). Alternatively compare the time of the latest M1 bar with a UTC
  clock.
* Most retail MT5 servers run UTC+2 in winter and UTC+3 in summer (so the New York close is 00:00).
  On such a server **London open (08:00 UK) is 10:00 server time almost all year**, so an "Asian range
  until London open" would be `RangeEndHour=10`, `TradeStartHour=10`, `TradeEndHour=13`,
  `ForceCloseHour=15` or later. A UTC+0 server would use 8/8/11/13.
* The defaults in this EA (range 00:00-07:00, entries 07:00-10:00, close 12:00) follow the task
  specification and correspond to one of the published variants (00:00-07:00 GMT) only on a UTC+0
  server. The published gold variant that reported a multi-year real-tick test used 03:00-08:00 server
  time with entries at 08:00 and a 21:00 close. There is no agreed "correct" window; test several and be
  suspicious if only one of them works.
* `UseServerTime=false` lets you type UTC hours and have them shifted by `ServerToUTCOffsetHours`.
  It is a fixed offset; it does **not** follow daylight-saving changes, so on a UTC+2/+3 server it is
  wrong for half the year unless you update it. Server-time inputs are the safer choice.

---

## 5. Walk-forward (out-of-sample) testing

Any parameter you tune on the full 2023-today history is, by construction, fitted to that history.
MT5 has a built-in walk-forward:

1. In the Settings tab enable **Optimization** (`Slow complete algorithm` for a handful of
   parameters, `Fast genetic based algorithm` for many) and choose an **Optimization criterion** such
   as *Balance max* or *Custom max*; prefer *Balance + max Profit factor* or *Recovery factor* over raw
   balance.
2. In the Inputs tab tick the parameters to optimize and set Start/Step/Stop. Keep it to 2-4
   parameters with coarse steps (the presets pre-flag `BufferPoints`, `TakeProfitR`,
   `MinRangePctOfPrice`, `MaxRangePctOfPrice` and `MoveToBreakevenAtR`; the flags are ignored in a
   single test). Thousands of combinations on a strategy with ~250 trades per year guarantee a lucky
   winner.
3. Set **Forward** to `1/3` (or `1/4`, or `Custom` with a date such as `2026.01.01`). The tester
   optimizes on the first part only, then re-runs *every* pass unchanged on the forward part and shows
   them in the **Forward Results** tab next to **Optimization Results**.
4. Compare. For the passes that were best in-sample, look at their forward profit factor and drawdown.
   If the forward numbers collapse towards PF 1.0 or below while the back-test looked great, the edge
   was the optimizer, not the market. Look for a *plateau* (neighbouring parameter values all decent)
   rather than a single spike, and pick a value from the middle of the plateau.
5. Manual rolling variant: optimize on 2023-2024, run a single test on 2025 with the chosen values;
   then optimize 2024-2025 and test on 2026. Note each out-of-sample result. The concatenated
   out-of-sample periods are the only numbers worth quoting.
6. After that, forward-test on a demo account for weeks. Live spread, slippage and server time are the
   usual places where a tester result dies.

---

## 6. Reading the results

Open the **Backtest** (report) tab after a run. The numbers that matter:

* **Total trades.** At one fill per day on one symbol you get roughly 150-250 trades per year.
  **Fewer than ~300 trades is not conclusive** about anything: a 40 %-win-rate, 1.5R strategy can show
  a profit factor anywhere from about 0.8 to 1.6 over 100 trades purely by chance. Treat any
  sub-300-trade result, good or bad, as "no information yet".
* **Profit factor** (gross profit / gross loss). After real spread and commission, a PF below about
  1.15 over a few hundred trades is indistinguishable from zero edge. Do not quote a PF without also
  quoting the trade count and the costs used.
* **Maximal / relative equity drawdown.** This is what you will live through. Published gold tests of
  this strategy family showed 15-19 % drawdowns at 1 % risk per trade; expect worse live. If you plan
  to run it on a prop-firm account with a 10 % limit, re-run at 0.25-0.4 % risk and check the drawdown
  again.
* **Expected payoff** (average profit per trade in money). Divide by the average money risked per
  trade (balance x `RiskPercent`) to get the expectancy in R; +0.1R to +0.2R per trade after costs is
  what a working breakout system typically looks like, not +1R.
* **Win rate** by itself means nothing; with a 1.5R target the break-even win rate is 40 % before
  costs. The EA does not claim, and you should not expect, any particular win rate.
* **Recovery factor** (net profit / max drawdown) and **Sharpe ratio** are useful for comparing runs.
* **Consecutive losses / long flat periods.** Breakout systems lose for weeks at a time. Check the
  equity curve for the longest flat stretch and ask whether you would keep running it through that.
* **Year by year.** Run each calendar year separately. A system that made all its money in one
  trending year (gold in 2025, for example) and bled in the others is a bet on that year repeating.
* **Robustness checks:** rerun with 1.5-2x the spread, with `Delays` increased, on M5 vs M15, with
  `BufferPoints` +/-50 %, and with `RangeEndHour`/`TradeStartHour` shifted by one hour. If the result
  flips sign under any of these, you have a curve fit, not a strategy.
* **Journal warnings.** Search the Journal for `WARNING: lot-size cross-check mismatch`. A published
  version of this strategy once opened positions ~10x too large on one broker because of a tick-value
  mismatch; the EA sizes with `OrderCalcProfit` and cross-checks, but you must still verify the first
  few position sizes by hand (position volume x contract size x stop distance should equal
  balance x RiskPercent).

---

## 7. Known limitations

* Not compiled by the author (no MetaEditor in the authoring environment). Compile and fix before use.
* Server-time inputs; no automatic DST handling (see section 4).
* On netting accounts the EA cannot separate its position from manual trades on the same symbol;
  run it alone on the symbol.
* The news filter is a static time list; it does not read the economic calendar. Update it for
  NFP/CPI/FOMC days yourself or leave it empty and accept the news risk.
* Stop orders are placed at the start of the window at the current price; if price has already left the
  range before `TradeStartHour`, that side is skipped and logged (the EA does not chase).
* Range filters use the mid-price of the range for the percent calculation.
* `MaxSLPctOfPrice` is applied in both SL modes (the specification only required it for the
  opposite-range mode); set it to 0 to disable.

---

## 8. Warning

This EA, its presets and this README are research material. They are **not** financial advice, not a
recommendation to trade, and carry **no claim of profitability, win rate or drawdown**. Backtests,
including walk-forward backtests, routinely overstate live results because of spread widening at the
session open, slippage on stop orders, requotes, server-time mistakes and plain over-fitting. If you
trade this, do it first on a demo account, then with money you can afford to lose entirely, and keep
your own records. Nobody in the sources this was built from has published an audited multi-year live
track record for a London-range breakout.
