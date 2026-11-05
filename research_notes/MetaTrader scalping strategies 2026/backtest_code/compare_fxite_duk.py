"""Cross-check Forexite day file vs Dukascopy bi5 day file: find the hour/minute shift that aligns them, and price offset."""
import sys, zipfile, io
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/-home-user-passive-income/4bda35b9-7742-59fc-9e40-0940cd75c46d/scratchpad/backtest/code')
from decode_bi5 import decode

fx_zip, ticker, duk_file, scale, duk_day = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
z = zipfile.ZipFile(fx_zip)
df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
df.columns = ['ticker','date','time','open','high','low','close']
df = df[df.ticker == ticker].copy()
df['ts'] = pd.to_datetime(df.date.astype(str) + df.time.astype(str).str.zfill(6), format='%Y%m%d%H%M%S')
print(ticker, 'forexite rows', len(df), 'first', df.ts.iloc[0], 'last', df.ts.iloc[-1])
print(df[['ts','open','high','low','close']].head(3).to_string()); print(df[['ts','open','high','low','close']].tail(3).to_string())
fx = df.set_index('ts').close

a = decode(duk_file, scale)
dk = pd.Series(a[:,4], index=pd.Timestamp(duk_day) + pd.to_timedelta(a[:,0], unit='s'))
dk = dk[a[:,5] > 0]  # drop zero-volume filler bars
print('dukascopy bars with volume', len(dk), dk.index[0], dk.index[-1])
best = None
for h in range(-4, 5):
    for m in (0, -1):
        shifted = fx.copy(); shifted.index = shifted.index - pd.Timedelta(hours=h, minutes=-m)  # forexite_time - h hours (+m minutes)
        j = dk.to_frame('dk').join(shifted.rename('fx'), how='inner')
        if len(j) < 100: continue
        corr = np.corrcoef(j.dk.diff().dropna(), j.fx.diff().dropna())[0,1]
        mad = (j.dk - j.fx).abs().mean(); bias = (j.fx - j.dk).mean()
        if best is None or corr > best[0]: best = (corr, h, m, len(j), mad, bias)
        print(f'shift -{h}h {m:+d}min n={len(j)} corr(returns)={corr:.4f} MAD={mad:.5f} bias(fx-dk)={bias:+.5f}')
print('BEST', best)
