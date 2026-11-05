"""T2. ATR-scaled Asian-range breakout (MQL5 CodeBase 75586 defaults) on XAUUSD and EURUSD, server time (NY+7h).

Range = M1 high/low 03:00-08:00 server (same window as T1). Daily ATR(14) = SMA of the true range of the 14 completed
server-time days before the trading day. Skip unless 0.15 <= range/ATR <= 0.70. Buy stop at high + 0.15*ATR, sell stop
at low - 0.15*ATR (OCO). SL = 1.2*ATR from entry; TP = 1.8R. Orders expire at 12:00 (the CodeBase EA cancels unfilled
orders 4 hours after the London window opens) or 21:00 (variant); flat at 21:00; one trade per day.
Usage: python3 -I t2_atr_breakout.py <clean_data_dir> <out_dir> [n_random_seeds]
"""
import sys, os, time, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa

data_dir, out_dir = sys.argv[1], sys.argv[2]
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
os.makedirs(os.path.join(out_dir, 'trades'), exist_ok=True)
COSTS = {'XAUUSD': {'gross': 0.0, 'spread15': 15.0, 'base42': 42.0, 'exp50': 50.0},
         'EURUSD': {'gross': 0.0, 'cheap0.8': 0.8, 'base1.2': 1.2, 'exp2.1': 2.1}}
T0 = time.time()
master, by_year, rand_rows, stats = [], [], [], {}

for SYM in ('XAUUSD', 'EURUSD'):
    data = Data(os.path.join(data_dir, f'{SYM}_M1.csv'), SYM)
    sd = ServerDays(data)
    days = sd.days
    d1 = sd.d1.loc[days]
    atr = d1['atr14_prev'].values
    utc_days = pd.DatetimeIndex(pd.to_datetime(data.ts).normalize().unique())
    utc_days = utc_days[(utc_days.dayofweek < 5) & (utc_days >= '2024-01-01')]
    pip = SPECS[SYM]['pip']
    h, l, o, c, n = data.h, data.l, data.o, data.c, data.n
    print(f'\n{SYM}: {data.n} bars, {len(days)} server weekdays; median daily ATR(14) = {np.nanmedian(atr)/pip:.0f} {SPECS[SYM]["unit"]}s')

    def candidates(range_start='03:00', range_end='08:00', expiry='12:00', flat='21:00', min_ratio=0.15, max_ratio=0.70,
                   buf_atr=0.15, sl_atr=1.2, tp_mult=1.8, side='both'):
        a0, a1, w1, x1 = sd.idx(range_start), sd.idx(range_end), sd.idx(expiry), sd.idx(flat)
        out = dict(entry_idx=[], entry_px=[], dir=[], sl=[], tp=[], tx=[], day=[], ratio=[], atr=[])
        st = dict(weekdays=len(days), range_ok=0, eligible=0, fills=0, skipped_narrow=0, skipped_wide=0, no_fill=0)
        for i in range(len(days)):
            if a1[i] - a0[i] < 200 or a1[i] >= n or x1[i] >= n or w1[i] <= a1[i] or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            st['range_ok'] += 1
            hi = h[a0[i]:a1[i]].max(); lo = l[a0[i]:a1[i]].min(); rng = hi - lo
            ratio = rng / atr[i]
            if ratio < min_ratio:
                st['skipped_narrow'] += 1; continue
            if ratio > max_ratio:
                st['skipped_wide'] += 1; continue
            st['eligible'] += 1
            buf = buf_atr * atr[i]
            buy_lvl = hi + buf if side in ('both', 'long') else 1e12
            sell_lvl = lo - buf if side in ('both', 'short') else -1e12
            j, d, px = first_trigger(h, l, o, a1[i], min(w1[i], n), buy_lvl, sell_lvl)
            if d == 0:
                st['no_fill'] += 1; continue
            st['fills'] += 1
            R = sl_atr * atr[i]
            sl = px - d * R; tp = px + d * tp_mult * R
            for k, v in zip(out.keys(), (j, px, d, sl, tp, x1[i], days[i], ratio, atr[i])):
                out[k].append(v)
        return {k: np.asarray(v) for k, v in out.items()}, st

    def simulate(cand):
        return run_trades_be(data, cand['entry_idx'], cand['entry_px'], cand['dir'], cand['sl'], cand['tp'],
                             be_trig=None, time_exit_idx=cand['tx'],
                             extra=dict(time_exit_idx=cand['tx'], day=cand['day'], ratio=cand['ratio'], atr=cand['atr']))

    def record(name, tr, st, params):
        tr.to_csv(os.path.join(out_dir, 'trades', f't2_{SYM}_{name}.csv.gz'), index=False)
        stats[f'{SYM}_{name}'] = {**st, **params, 'trades': len(tr)}
        for cc, cost in COSTS[SYM].items():
            t = apply_costs(tr, SYM, cost)
            base = dict(test='T2', symbol=SYM, variant=name, cost_case=cc, cost_pips=cost, **params)
            master.append({**base, **metrics(t, SYM, all_days=utc_days, ci_R=True), 'eligible_days': st['eligible'], 'fills': st['fills']})
            by_year.extend(by_year_rows(t, SYM, base, utc_days))
        print(f'  {name:28s} elig={st["eligible"]:4d} fills={st["fills"]:4d} trades={len(tr):4d} gross={tr.gross.mean()/pip:+8.2f} '
              f'avgR={tr.risk.mean()/pip:.1f} reasons={tr.reason.value_counts().to_dict()}', flush=True)
        return tr

    BASE = dict(expiry='12:00', tp_mult=1.8, sl_atr=1.2, buf_atr=0.15)
    cand, st = candidates(**BASE)
    base_tr = record('atr_x12_tp1.8', simulate(cand), st, BASE)
    p = {**BASE, 'expiry': '21:00'}; cand, st = candidates(**p); record('atr_x21_tp1.8', simulate(cand), st, p)
    for tpm in (1.0, 2.5):
        p = {**BASE, 'tp_mult': tpm}; cand, st = candidates(**p); record(f'atr_x12_tp{tpm}', simulate(cand), st, p)
    p = {**BASE, 'min_ratio': 0.0, 'max_ratio': 1e9}; cand, st = candidates(**p); record('atr_x12_tp1.8_noFilter', simulate(cand), st, p)
    for side in ('long', 'short'):
        p = {**BASE, 'side': side}; cand, st = candidates(**p); record(f'atr_x12_tp1.8_{side}_only', simulate(cand), st, p)

    # random direction benchmark on the base trades
    for seed in range(N_SEEDS):
        rt = randomize_direction(data, base_tr, seed, tp_mult=1.8)
        for cc, cost in COSTS[SYM].items():
            t = apply_costs(rt, SYM, cost)
            m = metrics(t, SYM, all_days=utc_days, with_ci=False)
            rand_rows.append(dict(test='T2', symbol=SYM, variant='random_dir_base', seed=seed, cost_case=cc, cost_pips=cost, **m))
    r = pd.DataFrame(rand_rows); r = r[r.symbol == SYM]
    print(r.groupby('cost_case').agg(mean_exp=('exp_pips', 'mean'), p05=('exp_pips', lambda x: pctl(x, 5)),
                                     p95=('exp_pips', lambda x: pctl(x, 95)), frac_pos=('exp_pips', lambda x: (x > 0).mean())).to_string())

pd.DataFrame(master).to_csv(os.path.join(out_dir, 't2_master.csv'), index=False)
pd.DataFrame(by_year).to_csv(os.path.join(out_dir, 't2_by_year.csv'), index=False)
pd.DataFrame(rand_rows).to_csv(os.path.join(out_dir, 't2_random.csv'), index=False)
json.dump(stats, open(os.path.join(out_dir, 't2_stats.json'), 'w'), indent=1, default=str)
print(f'\nDONE T2 in {time.time()-T0:.1f}s')
