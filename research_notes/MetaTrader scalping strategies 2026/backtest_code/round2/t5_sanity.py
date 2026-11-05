"""T5. Sanity checks on the round-2 trade lists against the raw M1 data (independent re-derivation, no engine code):
look-ahead (range built from bars before 08:00 server only; M5 signals fill at the next M1 open), stop-order fills
(at the level, or at the open if gapped through), OCO (first touched level wins, the other never filled), one fill per
day, no earlier SL/TP/BE touch than the recorded exit, break-even logic, limit-order fills (N2), T4 timing.
Usage: python3 -I t5_sanity.py <clean_data_dir> <results_dir>
"""
import sys, os, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
data_dir, res = sys.argv[1], sys.argv[2]
POINT = 0.01


def bars_around(data, i, before=2, after=1, srv=None):
    seg = data.m1.iloc[max(i - before, 0):i + after + 1][['datetime', 'open', 'high', 'low', 'close']].copy()
    if srv is not None:
        seg.insert(1, 'server_time', pd.to_datetime(srv[max(i - before, 0):i + after + 1]))
    return seg.to_string(index=False)


# ----------------------------------------------------------------------------------------------------------------------
print('=' * 110 + '\nT1 base variant (buffer 20 pts, TP 2.5R, BE 1.5R, window 03:00-08:00, expiry/flat 21:00) vs raw XAUUSD M1\n' + '=' * 110)
data = Data(os.path.join(data_dir, 'XAUUSD_M1.csv'), 'XAUUSD')
sd = ServerDays(data)
h, l, o, c, n = data.h, data.l, data.o, data.c, data.n
tr = pd.read_csv(os.path.join(res, 'trades', 't1_base_buf20_tp2.5_be1.5_w03-08_x21.csv.gz'), parse_dates=['entry_time', 'exit_time', 'day'])
print('trades:', len(trade := tr), '| distinct days:', tr['day'].nunique(), '| max fills on one day:', tr.groupby('day').size().max())
days = pd.DatetimeIndex(tr['day'])
a0 = sd.idx('03:00', days); a1 = sd.idx('08:00', days); w1 = sd.idx('21:00', days)
viol = dict(fill_level=0, not_first_touch=0, other_side_first=0, early_exit=0, be_logic=0, range_lookahead=0, exit_after_flat=0, filter=0)
for t, r in tr.iterrows():
    i, j = int(r['entry_idx']), int(r['exit_idx'])
    hi = h[a0[t]:a1[t]].max(); lo = l[a0[t]:a1[t]].min(); px0 = c[a1[t] - 1]
    buy, sell = hi + 20 * POINT, lo - 20 * POINT
    rp = (hi - lo) / px0 * 100
    if not (0.30 <= rp <= 1.60):
        viol['filter'] += 1
    # range bars all before 08:00 server; entry bar at/after 08:00
    if not (sd.srv[a1[t] - 1] < np.datetime64(str(r['day'].date()) + 'T08:00:00') <= sd.srv[i]):
        viol['range_lookahead'] += 1
    lvl = buy if r['dir'] == 1 else sell
    expect = max(lvl, o[i]) if r['dir'] == 1 else min(lvl, o[i])
    touched = h[i] >= lvl - EPS if r['dir'] == 1 else l[i] <= lvl + EPS
    if not touched or abs(r['entry_px'] - expect) > 1e-9:
        viol['fill_level'] += 1
    # no touch of either level between 08:00 and the entry bar
    if i > a1[t] and ((h[a1[t]:i] >= buy - EPS).any() or (l[a1[t]:i] <= sell + EPS).any()):
        viol['not_first_touch'] += 1
    # same bar: if both touched, the closer-to-open side must have been chosen
    if h[i] >= buy - EPS and l[i] <= sell + EPS:
        closer_buy = (buy - o[i]) <= (o[i] - sell)
        if (r['dir'] == 1) != closer_buy:
            viol['other_side_first'] += 1
    # exits: no earlier SL/TP/BE touch between entry+1 and exit-1
    e, s, p, b = r['entry_px'], r['sl'], r['tp'], r['be_trig']
    seg_h, seg_l = h[i + 1:j], l[i + 1:j]
    if r['dir'] == 1:
        early = (seg_l <= s + EPS).any() or (seg_h >= p - EPS).any()
        be_touch_before = (h[i:j + 1] >= b - EPS).any()   # the exit bar itself may be the trigger bar (same-bar BE exit)
        if (h[i:j] >= b - EPS).any():  # once BE is active, a later low <= entry would have exited
            k = i + int(np.argmax(h[i:j] >= b - EPS))
            early |= (l[k + 1:j] <= e + EPS).any()
    else:
        early = (seg_h >= s - EPS).any() or (seg_l <= p + EPS).any()
        be_touch_before = (l[i:j + 1] <= b + EPS).any()
        if (l[i:j] <= b + EPS).any():
            k = i + int(np.argmax(l[i:j] <= b + EPS))
            early |= (h[k + 1:j] >= e - EPS).any()
    if early:
        viol['early_exit'] += 1
    if r['reason'] == 'BE':
        ok = be_touch_before and (abs(r['exit_px'] - e) < 1e-9 or (r['dir'] == 1 and o[j] <= e) or (r['dir'] == -1 and o[j] >= e))
        if not ok:
            viol['be_logic'] += 1
    if j > w1[t] or (r['reason'] == 'time' and j != w1[t]):
        viol['exit_after_flat'] += 1
    if early or (r['reason'] == 'BE' and not ok):
        print(f'  flagged trade #{t}: day {r["day"].date()} dir {r["dir"]} entry {r["entry_px"]} sl {s} tp {p} be {b} exit {r["exit_px"]} {r["reason"]} '
              f'(entry bar {i}, exit bar {j}); bars entry..exit:')
        print(bars_around(data, i, 0, j - i, sd.srv).replace('\n', '\n    '))
print('violations:', viol)
print('fill price == level (not gapped):', int((np.isclose(tr['entry_px'], np.where(tr['dir'] == 1, (h[a0] if False else 0), 0)) == False).sum()) if False else '', end='')
gap = []
for t, r in tr.iterrows():
    i = int(r['entry_idx']); hi = h[a0[t]:a1[t]].max(); lo = l[a0[t]:a1[t]].min()
    lvl = hi + 20 * POINT if r['dir'] == 1 else lo - 20 * POINT
    gap.append(abs(r['entry_px'] - lvl) > 1e-9)
print(f'fills at the open because the bar gapped through the level: {int(np.sum(gap))} of {len(tr)} ({np.mean(gap)*100:.1f}%), '
      f'mean gap slippage on those: {np.mean([abs(r.entry_px - ((h[a0[t]:a1[t]].max() + 0.2) if r.dir == 1 else (l[a0[t]:a1[t]].min() - 0.2))) for t, r in tr.iterrows() if gap[t]])/POINT if any(gap) else 0:.0f} points')
print('exit reasons:', tr['reason'].value_counts().to_dict(), '| BE triggered (incl. later TP):', int(tr['be_hit'].sum()))
print('entry server time distribution (hour):', pd.Series(server_minute_of_day(sd.srv[tr['entry_idx'].values]) // 60).value_counts().sort_index().to_dict())
print('trades per eligible day: see t1_stats.json (eligible vs fills); trades per month:',
      tr.groupby(tr['entry_time'].dt.to_period('M')).size().describe()[['mean', 'min', 'max']].round(1).to_dict())
for reason in ('SL', 'TP', 'BE', 'time'):
    r = tr[tr['reason'] == reason].iloc[len(tr[tr['reason'] == reason]) // 2]
    t = r.name; i, j = int(r['entry_idx']), int(r['exit_idx'])
    hi = h[a0[t]:a1[t]].max(); lo = l[a0[t]:a1[t]].min()
    print(f'\n--- sample {reason} trade: day {r["day"].date()} range {lo}-{hi} ({(hi-lo)/c[a1[t]-1]*100:.2f}%), levels buy {hi+0.2:.1f} / sell {lo-0.2:.1f}; '
          f'dir {r["dir"]} entry {r["entry_px"]} sl {r["sl"]:.1f} tp {r["tp"]:.1f} be {r["be_trig"]:.1f} exit {r["exit_px"]:.1f} ({r["reason"]}) gross {r["gross"]/POINT:+.0f} pts')
    print('last range bar / first order bar (UTC + server):'); print(bars_around(data, a1[t], 1, 0, sd.srv))
    print('entry bar:'); print(bars_around(data, i, 1, 0, sd.srv))
    print('exit bar:'); print(bars_around(data, j, 1, 0, sd.srv))

# ----------------------------------------------------------------------------------------------------------------------
print('\n' + '=' * 110 + '\nT2 (ATR-scaled) XAUUSD: fill and OCO checks\n' + '=' * 110)
t2 = pd.read_csv(os.path.join(res, 'trades', 't2_XAUUSD_atr_x12_tp1.8.csv.gz'), parse_dates=['entry_time', 'exit_time', 'day'])
days2 = pd.DatetimeIndex(t2['day']); a0 = sd.idx('03:00', days2); a1 = sd.idx('08:00', days2); w1 = sd.idx('12:00', days2)
v = dict(fill=0, first_touch=0, after_expiry=0, one_per_day=int((t2.groupby('day').size() > 1).sum()))
for t, r in t2.iterrows():
    i = int(r['entry_idx']); hi = h[a0[t]:a1[t]].max(); lo = l[a0[t]:a1[t]].min(); buf = 0.15 * r['atr']
    buy, sell = hi + buf, lo - buf
    lvl = buy if r['dir'] == 1 else sell
    expect = max(lvl, o[i]) if r['dir'] == 1 else min(lvl, o[i])
    if abs(r['entry_px'] - expect) > 1e-9: v['fill'] += 1
    if i > a1[t] and ((h[a1[t]:i] >= buy - EPS).any() or (l[a1[t]:i] <= sell + EPS).any()): v['first_touch'] += 1
    if i >= w1[t]: v['after_expiry'] += 1
print('trades', len(t2), 'violations', v, '| SL/ATR =', round((t2['risk'] / t2['atr']).mean(), 3), '| TP/SL =', round(((t2['tp'] - t2['entry_px']).abs() / t2['risk']).mean(), 3))

# ----------------------------------------------------------------------------------------------------------------------
print('\n' + '=' * 110 + '\nT3 N2 limit fade AUDNZD (TP 6 / SL 12): limit fills at the 17:00-21:00 range extremes\n' + '=' * 110)
dA = Data(os.path.join(data_dir, 'AUDNZD_M1.csv'), 'AUDNZD'); sdA = ServerDays(dA)
t3 = pd.read_csv(os.path.join(res, 'trades', 't3_AUDNZD_N2_limit_tp6_sl12.csv.gz'), parse_dates=['entry_time', 'exit_time'])
srv_in = sdA.srv[t3['entry_idx'].values]; mins = server_minute_of_day(srv_in)
srv_out = sdA.srv[t3['exit_idx'].values]
deadline = (srv_in.astype('datetime64[D]') + np.where(mins >= 21 * 60, 1, 0) * np.timedelta64(1, 'D')).astype('datetime64[ns]') + np.timedelta64(6, 'h')
print('trades', len(t3), '| legs:', t3['leg'].value_counts().to_dict(), '| entries inside 21:00-02:00 server:',
      int((((mins >= 21 * 60) | (mins < 2 * 60))).sum()), '| exits at/before the 06:00 server deadline:', int((srv_out <= deadline).sum()),
      '| entries on Friday server date (= Thursday-night session after midnight):', int((server_dow(srv_in) == 4).sum()),
      '| Friday-evening entries (>= 21:00 Fri):', int(((server_dow(srv_in) == 4) & (mins >= 21 * 60)).sum()))
v = dict(fill=0, not_extreme=0)
for t, r in t3.head(400).iterrows():
    i = int(r['entry_idx'])
    day = np.datetime64(srv_in[t], 'D') if mins[t] >= 21 * 60 else np.datetime64(srv_in[t], 'D') - np.timedelta64(1, 'D')
    r0 = sdA.idx('17:00', pd.DatetimeIndex([day]))[0]; r1 = sdA.idx('21:00', pd.DatetimeIndex([day]))[0]
    hi = dA.h[r0:r1].max(); lo = dA.l[r0:r1].min()
    lvl = hi if r['dir'] == -1 else lo
    expect = max(lvl, dA.o[i]) if r['dir'] == -1 else min(lvl, dA.o[i])
    if abs(r['entry_px'] - expect) > 1e-9: v['fill'] += 1
    touched = dA.h[i] >= lvl - EPS if r['dir'] == -1 else dA.l[i] <= lvl + EPS
    if not touched: v['not_extreme'] += 1
print('first 400 trades re-derived: violations', v)
r = t3.iloc[len(t3) // 3]; i, j = int(r['entry_idx']), int(r['exit_idx'])
print(f'sample: dir {r["dir"]} entry {r["entry_px"]} sl {r["sl"]} tp {r["tp"]} exit {r["exit_px"]} {r["reason"]} gross {r["gross"]/0.0001:+.1f} pips')
print(bars_around(dA, i, 2, 0, sdA.srv)); print('exit bar:'); print(bars_around(dA, j, 0, 0, sdA.srv))

print('\n' + '=' * 110 + '\nT3 N1 Bollinger fade AUDNZD: signal bar closes before the fill bar opens (no look-ahead)\n' + '=' * 110)
t3b = pd.read_csv(os.path.join(res, 'trades', 't3_AUDNZD_N1_bb_sl1.5x_mintp0.csv.gz'), parse_dates=['entry_time', 'exit_time'])
et = pd.to_datetime(t3b['entry_time'])
print('trades', len(t3b), '| entry minute % 5 == 0 (first M1 bar after an M5 close):', int((et.dt.minute % 5 == 0).sum()),
      '| entry px == open of entry bar:', int(np.isclose(t3b['entry_px'], dA.o[t3b['entry_idx'].values]).sum()))
r = t3b.iloc[len(t3b) // 2]; i = int(r['entry_idx'])
b5 = dA.resample('M5'); kk = np.searchsorted(b5['m1_next'].values, i)
print('signal M5 bar (closed):', b5.iloc[kk - 1][['datetime', 'open', 'high', 'low', 'close']].to_dict() if b5['m1_next'].values[kk] == i else b5.iloc[kk][['datetime', 'open', 'high', 'low', 'close']].to_dict())
print('fill bar:'); print(bars_around(dA, i, 0, 0, sdA.srv))

print('\n' + '=' * 110 + '\nT4 timing\n' + '=' * 110)
t4 = pd.read_csv(os.path.join(res, 'trades', 't4_combined.csv.gz'), parse_dates=['entry_time', 'exit_time'])
print('entry hours:', t4['entry_time'].dt.hour.value_counts().sort_index().to_dict(), '| exit hours:', t4['exit_time'].dt.hour.value_counts().sort_index().to_dict(),
      '| entry minute == 0:', int((t4['entry_time'].dt.minute == 0).sum()), 'of', len(t4))

print('\n' + '=' * 110 + '\nServer-time helper spot checks\n' + '=' * 110)
for u in ('2025-01-15T12:00', '2025-07-15T12:00', '2025-03-09T06:59', '2025-03-09T07:00', '2025-11-02T05:59', '2025-11-02T06:00', '2026-03-08T07:00', '2026-11-01T06:00'):
    s = utc_to_server(np.array([np.datetime64(u)]))[0]
    back = server_to_utc(np.array([s]))[0]
    print(f'  UTC {u} -> server {str(s)[:16]} -> back {str(back)[:16]}')
