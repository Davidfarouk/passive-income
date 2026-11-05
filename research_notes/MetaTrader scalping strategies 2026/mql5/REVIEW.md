# LondonRangeBreakout.mq5 - desk review log

Scope: `LondonRangeBreakout.mq5`, `README.md`, `LondonRangeBreakout_XAUUSD.set`,
`LondonRangeBreakout_EURUSD.set`. The review was done without MetaEditor; the source was read line by
line as a compiler would, every Standard Library call, enum constant, `StringFormat` specifier/argument
pair and event-handler signature was checked against the MQL5 reference from memory, and the trading
logic was traced for the day cycle (range -> window -> fill -> exit -> rollover). Line numbers below
refer to the file **after** the fixes unless marked "orig.".

## 1. Compile-level findings

No definite syntax error, undeclared identifier, wrong method name/signature, wrong enum constant,
mis-typed `StringFormat` argument or wrong handler signature was found. Specifically verified:

* Handlers: `int OnInit()`, `void OnDeinit(const int)`, `void OnTick()`,
  `void OnTradeTransaction(const MqlTradeTransaction&, const MqlTradeRequest&, const MqlTradeResult&)`.
* `CTrade`: `SetExpertMagicNumber(ulong)`, `SetDeviationInPoints(ulong)`, `SetTypeFilling`,
  `SetAsyncMode`, `LogLevel`, `BuyStop/SellStop(volume, price, symbol, sl, tp, type_time, expiration,
  comment)`, `Buy/Sell(volume, symbol, price, sl, tp, comment)`, `OrderDelete(ticket)`,
  `PositionClose(ticket, deviation)`, `PositionModify(ticket, sl, tp)`, `ResultRetcode()` (uint),
  `ResultRetcodeDescription()`, `ResultOrder()`, `ResultVolume()`, `ResultPrice()`.
* `CSymbolInfo`: `Name(string)` (bool), `Refresh`, `RefreshRates`, `Digits`, `Point`, `TickSize`,
  `TickValue`, `ContractSize`, `LotsMin/Max/Step`, `StopsLevel`, `FreezeLevel` (int), `Ask`, `Bid`.
* `CPositionInfo`/`COrderInfo`: `SelectByIndex(int)`, `Symbol`, `Magic` (long), `Ticket`, `Volume`,
  `PriceOpen`, `StopLoss`, `TakeProfit`, `Profit`, `PositionType`, `Time`, `OrderType`, `TimeSetup`.
* Enum constants: `ORDER_TYPE_BUY_STOP/SELL_STOP`, `ORDER_FILLING_FOK/IOC/RETURN`,
  `ORDER_TIME_GTC/SPECIFIED`, `DEAL_ENTRY_IN/OUT/INOUT/OUT_BY`, `DEAL_TYPE_BUY/SELL`,
  `TRADE_TRANSACTION_DEAL_ADD`, `SYMBOL_TRADE_EXECUTION_EXCHANGE`,
  `ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`, `SYMBOL_FILLING_FOK/IOC` and `SYMBOL_EXPIRATION_SPECIFIED`
  used as bit flags, `TRADE_RETCODE_DONE/PLACED/DONE_PARTIAL`, `INIT_*`, `MQL_TESTER`,
  `MQL_OPTIMIZATION`, `TERMINAL_TRADE_ALLOWED`, `ACCOUNT_TRADE_EXPERT`.
* Every function is defined before its first use (MQL5 does not strictly require it, but the order is
  clean anyway).
* All 24 `StringFormat` calls: specifier count equals argument count and every `%d` receives an `int`
  (no `long` passed to `%d`), every `%s` a `string`, every `%f` a `double`.
* `datetime`/`long`/`int` arithmetic is cast explicitly; `ORDER_TIME_SPECIFIED` is always paired with a
  non-zero expiration (`g_srvTradeEnd`); lot and price normalisation go through `NormalizeLotsDown`
  and `NormalizePrice` (tick-size rounding then `NormalizeDouble`).

One cosmetic change was made to avoid a type-conversion warning:

| Line | Change |
|---|---|
| 1268 (orig. 1176) | `datetime expiry = g_expirationSupported ? g_srvTradeEnd : 0;` -> `... : (datetime)0;` |

## 2. Logic bugs found and fixed

| # | Where (new lines) | Problem | Fix |
|---|---|---|---|
| L1 | `RecoverDayStateFromHistory`, 869-888 (orig. 857-863) | Any open position of ours at the start of a new day was counted as *today's* fill (`g_tradedToday=true`, `g_tradesToday=1`). A position left over from the previous day (EA offline at `ForceCloseHour`, e.g. Friday evening) therefore set `g_dayDone` under `OneTradePerDay` and the whole day was lost. | The loop now checks the position's open day (`PositionInfo.Time()` converted to the schedule day); only a position opened today counts. A stale one is logged, `g_posOpenSeen` is still set so its close is detected, and `ManagePositions` closes it as before. |
| L2 | `OnPositionClosed`, 1134-1137 (orig. 1046) | Follow-on from L1: when the stale position was closed, `OneTradePerDay` set `g_dayDone=true`, still losing the day. | `dayComplete` now requires `g_tradesToday > 0`; a close with zero fills today re-arms instead of finishing the day. |
| L3 | `RecoverDayStateFromHistory`, 889-911 (new) | Pending stop orders set up on a previous day (EA offline at `TradeEndHour` and the broker ignored the expiration) were seen by `HasOurPending()` and marked that side as already placed, so no stop order was placed for today on that side, and the stale order sat at yesterday's range edge until today's `TradeEndHour`. | Orders whose `TimeSetup()` falls on an earlier schedule day are deleted at day start (description captured before deletion; on failure `g_cancelPendingRequested` is set so `OnTick` retries). |
| L4 | `ComputeRange`, 998 and 1013-1015 (orig. 964-965) | The bar filter only required `time < g_srvRangeEnd`, so with `RangeSource=RANGE_CHART_TF` and a range end that is not on a bar boundary (e.g. M15 chart, `RangeEndMinute=5`) the still-forming bar that straddles the range end was included with its partial high/low. (With `RANGE_M1` and minute-aligned inputs the result was already correct.) | Bars must now also satisfy `time + PeriodSeconds(tf) <= g_srvRangeEnd`, i.e. be complete by the window end, matching the "completed bars" wording of the enum and README. |
| L5 | `OnPositionClosed` / new `CountTodayEntryDeals`, 1089-1131 | With `OneTradePerDay=false` and `CancelOppositeOnFill=false` on a hedging account both stops can fill. The second fill was (correctly) not double-handled by the `g_posOpenSeen` guard, but it was also never counted, so `g_tradesToday` under-counted and `MaxTradesPerDay` could be exceeded after the pair closed. | When the last position closes, today's `DEAL_ENTRY_IN`/`INOUT` deals with our magic are recounted from history and `g_tradesToday` is raised if the history shows more fills. |
| L6 | `OnPositionClosed`, 1154 (orig. 1059-1063) | On re-arm for another entry (`OneTradePerDay=false`) `g_entryAttempts` was not reset, so in `ENTRY_CLOSE_BEYOND` mode failed attempts from the first trade ate into the second trade's `MAX_ENTRY_ATTEMPTS`. | `g_entryAttempts = 0` added to the re-arm block; log text adjusted. |
| L7 | `OnInit`, 525-534 (new) | `MinRangeBars=30` (default) with `RangeSource=RANGE_CHART_TF` on M15 or slower silently skips every day (a 7-hour box holds 28 M15 bars), with only a per-day "Only 28 bars..." line to explain it. | Start-up warning computed from the window length and `PeriodSeconds()`; README note added. Code behaviour otherwise unchanged. |
| L8 | `ValidateInputs`, 322-323 (new) | `DeviationPoints` is cast to `ulong` for `SetDeviationInPoints`/`PositionClose`; a negative input would become a huge deviation. | Rejected at init with the other range checks. |

Checked and found correct (no change): trade-window boundaries (`[TradeStart, TradeEnd)`,
range `[start, end)`, force close `>=`), day index from schedule time (server-time inputs are immune
to broker DST), stop-loss direction for long/short, TP sign, break-even direction and the
`beAlready` guard, trailing only tightening (`IsBetterSL` with half-point tolerance), stops-level and
freeze-level handling for new SLs, buy-stop/sell-stop trigger adjustment to the stops level, OCO
idempotency between `OnTradeTransaction` and polling (`g_posOpenSeen` guard in both directions,
`g_cancelPendingRequested` retry), lot formula `riskMoney / ((dist / tickSize) * tickValue)` with
`OrderCalcProfit` as primary and the 20 % cross-check, lot rounding down to the step with min/max
clamp, margin reduction, spread measured in `Point()` units (consistent with `MaxSpreadPoints`
whatever the symbol's digits), news windows wrapping midnight, filling-mode detection by
`SYMBOL_FILLING_MODE` bits with `RETURN` forced for exchange execution.

## 3. README / .set consistency

* All 38 `input` names appear in both `.set` files in source order, enums as numeric values
  (`RangeSource`, `EntryMode`, `SLMode` = 0/1), bools as `true||false||0||true||N`, strings without
  optimisation fields. Defaults in the XAUUSD preset equal the code defaults; the EURUSD preset's
  deliberate deviations (range 0.10-0.60 %, spread cap 15, SL cap 0.50 %, magic 20261106,
  deviation 20, comment `LRB-EU`) match the README text. No changes needed.
* README input tables: every name, default and enum literal matches the code.
* README edits made: `REVIEW.md` added to the file table; range description now says only bars that
  complete by the window end are used; `MinRangeBars` row explains the chart-timeframe trap; tester
  "Timeframe" row says the range comes from M1 *by default*; section 3 step 1 mentions this review;
  section 7 gained bullets on SL/TP being anchored to the intended entry, break-even with trailing
  active, non-re-evaluated bars in `CLOSE_BEYOND`, start-of-day cleanup, and the fill-count
  reconciliation.

## 4. Items to double-check in MetaEditor

None of these is believed to be an error; they are the places where exact header contents vary by
terminal build or broker and could not be confirmed here.

1. Line 474: `g_trade.LogLevel(LOG_LEVEL_ERRORS)`. `ENUM_LOG_LEVELS` has `LOG_LEVEL_NO`,
   `LOG_LEVEL_ERRORS`, `LOG_LEVEL_ALL` in current `Trade.mqh`; if your build lacks the method, delete
   the line (it only silences CTrade's own prints).
2. Line 898: `g_order.TimeSetup()` (`COrderInfo`), returns `datetime`. Present in current
   `OrderInfo.mqh`.
3. Line 441: `g_symbol.Name(_Symbol)` is used as a `bool`. In current `SymbolInfo.mqh`
   `CSymbolInfo::Name(const string)` returns `bool`; on a very old build it was `void` and the `if`
   would not compile. Then replace with `g_symbol.Name(_Symbol); if(!g_symbol.Refresh()) ...`.
4. Lines 1230-1231 (`BuyStop`/`SellStop`): the filling type handed to pending orders is the one detected
   for market orders (FOK preferred, else IOC, else RETURN). Some Instant/Request-execution brokers
   reject pendings with retcode 10030 "Unsupported filling mode"; if the Journal shows that, call
   `g_trade.SetTypeFilling(ORDER_FILLING_RETURN)` before the two `*Stop` calls and restore
   `g_filling` afterwards.
5. `input group` (lines 75 ff.) needs terminal build 2155 or later.
6. Line 1268: `ORDER_TIME_SPECIFIED` with expiration `g_srvTradeEnd`. A few brokers accept
   `SYMBOL_EXPIRATION_SPECIFIED` but reject expirations inside the current session; a retcode 10022
   "Invalid expiration" in the Journal means set `g_expirationSupported=false` (the EA then deletes the
   stops itself at `TradeEndHour`, which it does anyway).
7. `StringTrimLeft/StringTrimRight` return `bool` on current builds and `int` on old ones; the return
   value is ignored everywhere, so either compiles.
8. Compiler warnings to expect and ignore: "implicit conversion from 'number' to 'string'" does not
   occur (all concatenations use `IntegerToString`/`DoubleToString`); possible "possible loss of data"
   warnings on explicit `(int)` casts are intentional.

## 5. What could not be verified without a compiler

* That the file actually compiles on the user's MetaEditor build (header versions of the Standard
  Library differ slightly between builds).
* Runtime behaviour of the Strategy Tester: ordering of `OnTradeTransaction` relative to position-list
  updates (the EA relies on polling as the authoritative path precisely because of this), whether the
  tester honours `ORDER_TIME_SPECIFIED` for the broker's symbol, and real retcodes for stops-level,
  freeze-level and filling-mode rejections.
* Broker-specific symbol properties (digits, tick value, stops level, execution mode) that drive the
  spread filter, buffer and sizing; the init log prints them so they can be checked on first run.
* Any statement about profitability. None is made, none was tested.
