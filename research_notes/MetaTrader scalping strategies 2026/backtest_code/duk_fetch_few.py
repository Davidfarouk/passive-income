"""Fetch a handful of Dukascopy daily candle files politely (long spacing, backoff on 429). Used only for cross-validation."""
import sys, time, urllib.request, urllib.error
out_dir = sys.argv[1]
items = sys.argv[2:]  # SYMBOL:YYYY-MM-DD
for it in items:
    sym, day = it.split(':'); y, m, d = day.split('-')
    url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{int(m)-1:02d}/{d}/BID_candles_min_1.bi5"
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                b = r.read()
            open(f"{out_dir}/{sym}_{day}.bi5", 'wb').write(b); print(it, 'OK', len(b), flush=True); break
        except urllib.error.HTTPError as e:
            print(it, 'HTTP', e.code, 'attempt', attempt, flush=True); time.sleep(20)
        except Exception as e:
            print(it, 'ERR', repr(e), flush=True); time.sleep(20)
    time.sleep(15)
