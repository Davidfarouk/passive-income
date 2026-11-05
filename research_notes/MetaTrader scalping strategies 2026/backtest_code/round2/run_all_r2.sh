#!/bin/bash
# Run the whole round-2 battery. Usage: bash run_all_r2.sh <clean_data_dir> <results_dir> [n_random_seeds]
# (data files are untrusted downloads: every script is run with python3 -I and takes the data path as an argument)
set -u
CODE="$(cd "$(dirname "$0")" && pwd)"
DATA="$1"; OUT="$2"; SEEDS="${3:-50}"
mkdir -p "$OUT"
python3 -I "$CODE/t1_gold_breakout.py" "$DATA" "$OUT" "$SEEDS" > "$OUT/t1_log.txt" 2>&1 &
python3 -I "$CODE/t2_atr_breakout.py" "$DATA" "$OUT" "$SEEDS" > "$OUT/t2_log.txt" 2>&1 &
python3 -I "$CODE/t4_breedon_ranaldo.py" "$DATA" "$OUT" "$SEEDS" > "$OUT/t4_log.txt" 2>&1 &
python3 -I "$CODE/t3_night.py" "$DATA" "$OUT" "$SEEDS" > "$OUT/t3_log.txt" 2>&1
wait
python3 -I "$CODE/t3_rollover_check.py" "$DATA" "$OUT" > "$OUT/t3_rollover_log.txt" 2>&1 &
python3 -I "$CODE/t5_sanity.py" "$DATA" "$OUT" > "$OUT/t5_sanity_log.txt" 2>&1
wait
python3 -I "$CODE/make_report_r2.py" "$OUT" "$OUT/tables_r2.md" > "$OUT/make_report_log.txt" 2>&1
echo "ALL DONE" >> "$OUT/make_report_log.txt"
