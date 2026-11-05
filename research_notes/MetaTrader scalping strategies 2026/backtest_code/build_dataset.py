"""Build clean UTC M1 OHLC CSVs (datetime,open,high,low,close,volume) for EURUSD and XAUUSD from Forexite daily zips.

Forexite format: <TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>; BID quotes; timestamps are bar CLOSE times in
Europe/Berlin local time (GMT+1 winter / GMT+2 summer) -- verified against Dukascopy bid candles (see compare_fxite_duk.py).
Output timestamps = bar OPEN time in UTC = stamp - 1 minute, converted from Europe/Berlin to UTC.
Usage: python3 -I build_dataset.py <zip_dir> <out_dir>
"""
import sys, os, io, zipfile, glob
import numpy as np, pandas as pd

zip_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
TICKERS = [b'EURUSD', b'XAUUSD']
chunks = {t: [] for t in TICKERS}
files = sorted(glob.glob(os.path.join(zip_dir, '*.zip')))
print('zip files:', len(files), files[0] if files else None, files[-1] if files else None)
bad = []
for f in files:
    try:
        z = zipfile.ZipFile(f)
        names = z.namelist()
        raw = z.read(names[0])
    except Exception as e:
        bad.append((f, repr(e))); continue
    for t in TICKERS:
        pref = t + b','
        lines = [l for l in raw.split(b'\n') if l.startswith(pref)]
        if lines:
            chunks[t].append(b'\n'.join(lines))
print('unreadable zips:', bad[:5], len(bad))

for t in TICKERS:
    name = t.decode()
    buf = io.BytesIO(b'\n'.join(chunks[t]))
    df = pd.read_csv(buf, header=None, names=['ticker','date','time','open','high','low','close'],
                     dtype={'date': str, 'time': str})
    # local (Europe/Berlin) close timestamp -> UTC open timestamp
    local = pd.to_datetime(df['date'] + df['time'].str.zfill(6), format='%Y%m%d%H%M%S')
    loc = local.dt.tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='NaT')
    ts = loc.dt.tz_convert('UTC').dt.tz_localize(None) - pd.Timedelta(minutes=1)
    df['datetime'] = ts
    n0 = len(df)
    df = df.dropna(subset=['datetime'])
    df = df.sort_values('datetime')
    ndup = df.duplicated('datetime').sum()
    df = df.drop_duplicates('datetime', keep='last')
    # sanity: OHLC consistency
    bad_ohlc = ((df.high < df[['open','close']].max(axis=1)) | (df.low > df[['open','close']].min(axis=1))).sum()
    df['volume'] = 0
    out = df[['datetime','open','high','low','close','volume']]
    path = os.path.join(out_dir, f'{name}_M1.csv')
    out.to_csv(path, index=False, date_format='%Y-%m-%d %H:%M:%S')
    print(f'\n=== {name}: rows={len(out)} (raw {n0}, dropped DST-NaT {n0-len(df)-ndup}, dups removed {ndup}, bad OHLC rows {bad_ohlc})')
    print('range', out.datetime.iloc[0], '->', out.datetime.iloc[-1])
    print('price min/max', out.low.min(), out.high.max())
    m = out.set_index('datetime').resample('MS').agg(rows=('close','size'), lo=('low','min'), hi=('high','max'))
    print(m.to_string())
    # weekend bars check (should be ~0 on Saturday after 00:00 UTC... Friday 22:00 close -> Sunday 22:00 open)
    dow = out.datetime.dt.dayofweek
    print('bars by weekday (0=Mon):', dow.value_counts().sort_index().to_dict())
    gaps = out.datetime.diff().dt.total_seconds().div(60)
    print('gaps > 60min during weekdays (count):', ((gaps > 60) & (dow != 6) & (dow != 0)).sum())
