# Independent scalping backtest — code

Pure Python (pandas / numpy / numba). No broker, no MetaTrader, no proprietary data. Everything runs from a
clean M1 CSV per symbol.

## Files

| File | Purpose |
|---|---|
| `fxite_download.py` | Downloads Forexite daily M1 archives (all instruments, bid, Europe/Berlin time) for a date range. |
| `build_dataset.py` | Extracts EURUSD and XAUUSD from the daily zips, converts to UTC bar-open timestamps, dedups, validates, writes `<SYMBOL>_M1.csv`. |
| `decode_bi5.py`, `duk_fetch_few.py`, `compare_fxite_duk.py` | Dukascopy `.bi5` decoder and the cross-check used to establish Forexite's timezone (CET/CEST, bar-close stamps) and that its quotes are bid. |
| `bt_engine.py` | Data container, resampling (M1 -> M5), MT5-style indicators, numba trade simulator, cost model, metrics, bootstrap CI. |
| `strategies.py` | Strategies A-H (EMA pullback, Bollinger MR, Asian-range London breakout, NY ORB, RSI(2), Stochastic+EMA50, random baseline, session (T)WAP fade). |
| `run_all.py` | Runs every strategy x symbol x timeframe x cost case; writes `master.csv`, `by_year.csv`, `by_session.csv`, `by_half.csv`, `random.csv`, per-variant trade lists (`trades/*.csv.gz`) and `run_info.json`. |
| `make_report.py` | Turns the CSVs into the markdown tables used in the results report. |
| `sanity_check.py` | Prints sample trades with the surrounding M1 bars to verify fill logic (next-open fills, intrabar SL/TP, no overlap). |

## Running it on your own data (e.g. an MT5 export)

1. Export M1 bars from MT5 (`Tools > History Center` or a script) and convert to a CSV with this exact header and
   format, timestamps in **UTC**, one row per M1 bar, **bar open time**:

   ```
   datetime,open,high,low,close,volume
   2024-01-01 22:00:00,1.1037,1.1043,1.1037,1.1043,0
   ```

   `volume` is read but not used by any strategy. Name the files `EURUSD_M1.csv` and `XAUUSD_M1.csv` and put them in
   one directory. MT5 server time is usually UTC+2/UTC+3 (EET), so shift it to UTC first; the session and
   breakout strategies use UTC clock times.

2. Run:

   ```
   python3 -I run_all.py /path/to/csv_dir /path/to/results_dir 50
   python3 -I make_report.py /path/to/results_dir /path/to/results_dir/tables.md
   ```

   Runtime for ~1M M1 bars per symbol: a few minutes for the strategies, ~10-20 minutes in total because of the
   bootstrap confidence intervals (reduce `n_boot` in `bt_engine.bootstrap_ci` to speed up).

3. Change the cost assumptions in `bt_engine.COST_CASES` (round-trip cost in pips for EURUSD / points for gold).
   Add a symbol by extending `SPECS`, `COST_CASES`, `MAX_LEVERAGE` and `CONTRACT_UNITS`.

## Engine conventions (what the numbers mean)

* Signals use **closed bars only**. Market entries fill at the **open of the next bar** (for M5 signals: the first M1 bar
  at/after the M5 bar's close). Stop-order strategies fill at the stop level, or at the bar open if the bar gaps through it.
* Stops/targets are checked **intrabar on M1 high/low** from the entry bar onward. If both are touched in the same M1 bar
  the trade is counted as a **loss**. A bar that opens beyond the stop fills at the open (gap slippage).
* One position at a time per strategy variant. Signals arriving while a position is open are ignored.
* Minimum stop distance = one price tick of the data (1 pip EURUSD, $0.10 XAUUSD); tighter ATR-based stops are widened to
  one tick and flagged (`sl_floored`), because R-multiples are meaningless with a near-zero stop.
* Costs (spread + commission + slippage) are deducted once per round trip, after the fact, from the gross result.
* `exp_R` divides the net result by the initial stop distance. The 1%-risk equity curve compounds a $10,000 account
  risking 1% of equity per trade with position size capped at 30:1 (FX) / 20:1 (gold) leverage.
* Sharpe = mean/std of daily net P&L (pips, fixed 1 lot) x sqrt(252), with zero on days without a trade.
* 95% CI = percentile bootstrap (2,000 resamples of the trade list) of the mean net result per trade.
