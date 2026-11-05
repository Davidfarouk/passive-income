# Round 2 backtest code

Targeted second round on the same Forexite M1 data and engine as `../` (see `../README.md` for the data format and
engine conventions). Results are written up in `../../independent_backtest_round2.md`.

| File | Purpose |
|---|---|
| `build_dataset_r2.py` | Extracts further symbols (the seven crosses) from the already-downloaded Forexite daily zips; prints the instrument inventory. |
| `r2_engine.py` | Broker server time (New York + 7h, US DST rules), server-day daily bars/ATR/SMA, break-even-aware numba simulator, tolerant stop/limit trigger scan, per-trade costs, metrics with long/short split, random-direction benchmark helper. Imports `../bt_engine.py`. |
| `t1_gold_breakout.py` | T1: exact MQL5 blog 777540 gold London-range breakout, variants, sensitivity grid, random-direction / one-sided / trend-filtered / buy-and-hold benchmarks. |
| `t2_atr_breakout.py` | T2: ATR-scaled Asian-range breakout (CodeBase 75586 defaults) on XAUUSD and EURUSD. |
| `t3_night.py` | T3: night-scalping fades (Bollinger, range limit, RSI(2)) on seven crosses and EURUSD with night-specific costs. |
| `t3_rollover_check.py` | T3 robustness: results by entry-time bucket, with and without the 23:30-00:30 server rollover hour. |
| `t4_breedon_ranaldo.py` | T4: EURUSD time-of-day pattern (short 07-13 UTC, long 13-21 UTC). |
| `t5_sanity.py` | Independent re-derivation of fills, OCO, break-even, look-ahead and timing from the raw M1 arrays. |
| `make_report_r2.py` | Builds the markdown tables (`results/tables_r2.md`) from the result CSVs. |
| `run_all_r2.sh` | Runs everything: `bash run_all_r2.sh <clean_csv_dir> <results_dir> [n_random_seeds]`. |

Runtime for the whole battery on 9 symbols x ~1.07M M1 bars: about 5 minutes on 4 cores (T3 is the slow part).
Data files are treated as untrusted downloads: every script is run with `python3 -I` and takes the data directory as an
argument.
