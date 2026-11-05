"""Download Forexite daily M1 archives (all instruments, bid, GMT+1) for a date range. Polite: sequential, ~0.7s spacing, skip existing."""
import sys, time, os, urllib.request, urllib.error, datetime as dt
out_dir, start, end = sys.argv[1], dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
os.makedirs(out_dir, exist_ok=True)
d = start; ok = miss = err = 0
while d <= end:
    name = d.strftime('%d%m%y') + '.zip'
    path = os.path.join(out_dir, d.strftime('%Y%m%d') + '.zip')
    if os.path.exists(path):
        d += dt.timedelta(days=1); continue
    url = f"https://www.forexite.com/free_forex_quotes/{d.year}/{d.month:02d}/{name}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                b = r.read()
            if b[:2] == b'PK':
                open(path, 'wb').write(b); ok += 1
            else:
                print(d, 'not a zip', len(b), flush=True); err += 1
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                miss += 1; print(d, '404', flush=True); break
            print(d, 'HTTP', e.code, 'attempt', attempt, flush=True); time.sleep(5 * (attempt + 1))
        except Exception as e:
            print(d, 'ERR', repr(e), 'attempt', attempt, flush=True); time.sleep(5 * (attempt + 1))
    else:
        err += 1
    if (ok + miss + err) % 50 == 0:
        print(f'progress {d} ok={ok} miss={miss} err={err}', flush=True)
    time.sleep(0.7)
    d += dt.timedelta(days=1)
print(f'DONE ok={ok} miss={miss} err={err}', flush=True)
