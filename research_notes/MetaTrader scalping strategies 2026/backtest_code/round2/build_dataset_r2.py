"""Extract additional symbols from the already-downloaded Forexite daily zips into clean UTC M1 CSVs.

Same conventions as ../build_dataset.py: Forexite rows are BID quotes, stamps are bar CLOSE times in Europe/Berlin local
time; output = bar OPEN time in UTC (stamp - 1 min, converted). Also lists which instruments exist in the archive.
Usage: python3 -I build_dataset_r2.py <zip_dir> <out_dir> SYM1,SYM2,...
"""
import sys, os, io, zipfile, glob, collections
import numpy as np, pandas as pd

zip_dir, out_dir = sys.argv[1], sys.argv[2]
TICKERS = [s.encode() for s in sys.argv[3].split(',')]
os.makedirs(out_dir, exist_ok=True)
chunks = {t: [] for t in TICKERS}
files = sorted(glob.glob(os.path.join(zip_dir, '*.zip')))
print('zip files:', len(files), os.path.basename(files[0]), '->', os.path.basename(files[-1]))
bad = []
inventory = collections.Counter()   # instrument -> number of daily files in which it appears
for f in files:
    try:
        z = zipfile.ZipFile(f)
        raw = z.read(z.namelist()[0])
    except Exception as e:
        bad.append((f, repr(e))); continue
    lines = raw.split(b'\n')
    seen = set()
    for l in lines:
        k = l.split(b',', 1)[0]
        if k and k != b'<TICKER>':
            seen.add(k)
    inventory.update(seen)
    for t in TICKERS:
        pref = t + b','
        ls = [l for l in lines if l.startswith(pref)]
        if ls:
            chunks[t].append(b'\n'.join(ls))
print('unreadable zips:', len(bad), bad[:3])
print('\nINSTRUMENT INVENTORY (instrument: number of daily files containing it, of %d):' % len(files))
for k, v in sorted(inventory.items()):
    print(f'  {k.decode():8s} {v}')

for t in TICKERS:
    name = t.decode()
    if not chunks[t]:
        print(f'\n=== {name}: NOT FOUND'); continue
    df = pd.read_csv(io.BytesIO(b'\n'.join(chunks[t])), header=None,
                     names=['ticker', 'date', 'time', 'open', 'high', 'low', 'close'], dtype={'date': str, 'time': str})
    local = pd.to_datetime(df['date'] + df['time'].str.zfill(6), format='%Y%m%d%H%M%S')
    loc = local.dt.tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='NaT')
    df['datetime'] = loc.dt.tz_convert('UTC').dt.tz_localize(None) - pd.Timedelta(minutes=1)
    n0 = len(df)
    df = df.dropna(subset=['datetime']).sort_values('datetime')
    ndup = df.duplicated('datetime').sum()
    df = df.drop_duplicates('datetime', keep='last')
    bad_ohlc = ((df.high < df[['open', 'close']].max(axis=1)) | (df.low > df[['open', 'close']].min(axis=1))).sum()
    df['volume'] = 0
    out = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    out.to_csv(os.path.join(out_dir, f'{name}_M1.csv'), index=False, date_format='%Y-%m-%d %H:%M:%S')
    # decimals actually used
    dec = out['close'].astype(str).str.split('.').str[1].str.len().max()
    dow = out.datetime.dt.dayofweek
    gaps = out.datetime.diff().dt.total_seconds().div(60)
    print(f'\n=== {name}: rows={len(out)} (raw {n0}, DST-NaT dropped {n0-len(df)-ndup}, dups {ndup}, bad OHLC {bad_ohlc}); '
          f'range {out.datetime.iloc[0]} -> {out.datetime.iloc[-1]}; price min/max {out.low.min()}/{out.high.max()}; '
          f'max decimals {dec}; bars by weekday {dow.value_counts().sort_index().to_dict()}; '
          f'weekday gaps>60min {((gaps > 60) & (dow != 6) & (dow != 0)).sum()}')
