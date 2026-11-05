"""Sanity checks on the engine: fills at next open, SL/TP hit logic, mapping M5 signal -> M1 fill, no look-ahead."""
import sys, time
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/-home-user-passive-income/4bda35b9-7742-59fc-9e40-0940cd75c46d/scratchpad/backtest/code')
from bt_engine import *
from strategies import *
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 30)
path, symbol = sys.argv[1], sys.argv[2]
t0 = time.time(); data = Data(path, symbol); print(symbol, 'M1 bars', data.n, 'load', round(time.time()-t0,1), 's')
b5 = data.resample('M5'); print('M5 bars', len(b5)); print(b5.head(3).to_string())
# check m1_next mapping: the M1 bar at m1_next must start >= M5 close time
ok = (data.ts[np.minimum(b5.m1_next.values, data.n-1)] >= (b5.datetime + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]'))
print('m1_next >= m5 close time for all bars:', ok[:-1].all())
# check M5 OHLC aggregation vs M1 for one bar
k = 1000; s, e = b5.m1_start[k], b5.m1_next[k]
print('M5 bar', b5.datetime[k], 'ohlc', b5.loc[k, ['open','high','low','close']].values, ' from M1 bars', data.ts[s], '..', data.ts[e-1],
      'o/h/l/c=', data.o[s], data.h[s:e].max(), data.l[s:e].min(), data.c[e-1])

for name, fn, kw in [('A M5', strat_A_ema_pullback, dict(tf='M5')), ('B M1', strat_B_bollinger, dict(tf='M1')),
                     ('C', strat_C_asian_breakout, {}), ('E M5', strat_E_rsi2, dict(tf='M5'))]:
    t0 = time.time(); tr = fn(data, **kw); dt = time.time()-t0
    print(f'\n##### {name}: {len(tr)} trades in {dt:.1f}s; reasons: {tr.reason.value_counts().to_dict()}; mean gross pips {tr.gross.mean()/data.spec["pip"]:.2f}')
    for _, r in tr.iloc[[0, len(tr)//2]].iterrows():
        i = np.searchsorted(data.ts, np.datetime64(r.entry_time)); j = np.searchsorted(data.ts, np.datetime64(r.exit_time))
        print(r.to_dict())
        print(data.m1.iloc[max(i-2,0):i+1][['datetime','open','high','low','close']].to_string(index=False))
        print('  ...exit bar:'); print(data.m1.iloc[j:j+1][['datetime','open','high','low','close']].to_string(index=False))
        # verify no earlier bar between entry and exit hit SL/TP
        seg_h = data.h[i:j]; seg_l = data.l[i:j]
        if r.dir == 1: early = (seg_l <= r.sl).any() or (not np.isnan(r.tp) and (seg_h >= r.tp).any())
        else: early = (seg_h >= r.sl).any() or (not np.isnan(r.tp) and (seg_l <= r.tp).any())
        print('  earlier bar hit SL/TP before recorded exit?', early)
    # overlap check: entries strictly after previous exits
    print('  overlap violations:', (tr.entry_time.values[1:] <= tr.exit_time.values[:-1]).sum())
    print('  entry px == open of entry bar (market strategies):', np.allclose(tr.entry_px.values, data.o[np.searchsorted(data.ts, tr.entry_time.values)]) if name != 'C' else 'n/a (stop orders)')
