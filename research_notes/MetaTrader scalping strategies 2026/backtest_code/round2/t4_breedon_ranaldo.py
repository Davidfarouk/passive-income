"""T4. Breedon-Ranaldo time-of-day pattern on EURUSD (academic benchmark, UTC clock, not a scalp).

Short EURUSD at the open of the first M1 bar at/after 07:00 UTC, close at 13:00 UTC; long at 13:00 UTC, close at
21:00 UTC; every weekday. No stop, no target. Costs 0 / 0.8 / 1.2 pips per round trip.
Usage: python3 -I t4_breedon_ranaldo.py <clean_data_dir> <out_dir> [n_random_seeds]
"""
import sys, os, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa

data_dir, out_dir = sys.argv[1], sys.argv[2]
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
os.makedirs(os.path.join(out_dir, 'trades'), exist_ok=True)
SYM = 'EURUSD'
COSTS = {'gross': 0.0, 'cheap0.8': 0.8, 'base1.2': 1.2}
T0 = time.time()
data = Data(os.path.join(data_dir, f'{SYM}_M1.csv'), SYM)
pip = SPECS[SYM]['pip']
ts = pd.to_datetime(data.ts)
utc_days = pd.DatetimeIndex(ts.normalize().unique())
utc_days = utc_days[(utc_days.dayofweek < 5) & (utc_days >= '2024-01-01')]
n = data.n


def leg(clock_in, clock_out, direction, label):
    i0 = data.idx_at_or_after((utc_days + pd.Timedelta(clock_in + ':00')).values)
    i1 = data.idx_at_or_after((utc_days + pd.Timedelta(clock_out + ':00')).values)
    ok = (i0 < n) & (i1 < n) & (i1 > i0)
    # require the fill bar to be within 15 minutes of the intended time (skip holidays / gaps)
    ok &= (data.ts[np.minimum(i0, n - 1)] - (utc_days + pd.Timedelta(clock_in + ':00')).values.astype('datetime64[ns]')) <= np.timedelta64(15, 'm')
    ok &= (data.ts[np.minimum(i1, n - 1)] - (utc_days + pd.Timedelta(clock_out + ':00')).values.astype('datetime64[ns]')) <= np.timedelta64(15, 'm')
    i0, i1 = i0[ok], i1[ok]
    ep = data.o[i0]
    d = np.full(len(i0), direction, dtype=np.int64)
    sl = ep - d * 1.0          # 10,000 pips away: never hit (no stop in the published rule)
    tr = run_trades_be(data, i0, ep, d, sl, np.full(len(i0), np.nan), time_exit_idx=i1, extra=dict(time_exit_idx=i1))
    tr['leg'] = label
    return tr


legs = {'short_07_13': leg('07:00', '13:00', -1, 'short_07_13'), 'long_13_21': leg('13:00', '21:00', 1, 'long_13_21')}
legs['combined'] = pd.concat([legs['short_07_13'], legs['long_13_21']], ignore_index=True).sort_values('entry_idx').reset_index(drop=True)
# contrast: the opposite pattern and a 'long all the time 07-21' exposure
legs['reverse_combined'] = legs['combined'].copy(); legs['reverse_combined']['dir'] *= -1; legs['reverse_combined']['gross'] *= -1
master, by_year, rand_rows = [], [], []
for name, tr in legs.items():
    tr.to_csv(os.path.join(out_dir, 'trades', f't4_{name}.csv.gz'), index=False)
    for cc, cost in COSTS.items():
        t = apply_costs(tr, SYM, cost)
        # risk is undefined (no stop): report pips only; put a nominal 1 pip risk so the R columns are finite
        t['risk_pips'] = 1.0; t['net_R'] = np.nan
        base = dict(test='T4', symbol=SYM, variant=name, cost_case=cc, cost_pips=cost)
        m = metrics(t, SYM, all_days=utc_days, ci_R=False)
        m['total_pips'] = t['net_pips'].sum()
        master.append({**base, **m})
        et = pd.to_datetime(t['entry_time'])
        for yr, g in t.groupby(et.dt.year):
            yd = utc_days[utc_days.year == yr]
            my = metrics(g, SYM, all_days=yd, with_ci=True, n_boot=1000); my['total_pips'] = g['net_pips'].sum()
            by_year.append({**base, 'year': int(yr), **my})
    print(f'  {name:18s} n={len(tr):4d} gross mean={tr.gross.mean()/pip:+.3f} pips  total={tr.gross.sum()/pip:+.0f} pips')

# random-direction baseline on the combined legs (same entry/exit times, coin-flip direction)
comb = legs['combined']
for seed in range(N_SEEDS):
    rng = np.random.default_rng(seed)
    d = rng.choice(np.array([-1, 1]), size=len(comb))
    g = d * (comb['exit_px'].values - comb['entry_px'].values) / pip
    for cc, cost in COSTS.items():
        net = g - cost
        rand_rows.append(dict(test='T4', variant='random_dir_combined', seed=seed, cost_case=cc, trades=len(net), exp_pips=net.mean(),
                              total_pips=net.sum(), win_rate=(net > 0).mean() * 100))
pd.DataFrame(master).to_csv(os.path.join(out_dir, 't4_master.csv'), index=False)
pd.DataFrame(by_year).to_csv(os.path.join(out_dir, 't4_by_year.csv'), index=False)
pd.DataFrame(rand_rows).to_csv(os.path.join(out_dir, 't4_random.csv'), index=False)
print(pd.DataFrame(master)[['variant', 'cost_case', 'trades', 'exp_pips', 'ci_lo', 'ci_hi', 'total_pips', 'sharpe', 'win_rate', 'profit_factor']].to_string())
print(f'\nDONE T4 in {time.time()-T0:.1f}s')
