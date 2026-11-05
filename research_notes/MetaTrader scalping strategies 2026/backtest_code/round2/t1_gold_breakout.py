"""T1. 'Gold London Range Breakout' (MQL5 blog 777540) on XAUUSD, exact rules in broker server time (NY+7h).

Rules (base): Asian range = M1 high/low 03:00-08:00 server; at 08:00 buy stop at high+buffer and sell stop at
low-buffer (OCO, first touched side fills at the level or at the bar open if gapped through, the other is cancelled);
unfilled orders expire at 21:00 (variants 12:00, 16:00); SL = far side of the range +/- buffer, capped at 0.6% of the
entry price; TP = 2.5R; stop to break-even once +1.5R is touched (M1 high/low); force-flat at 21:00; max one fill per
day; skip the day if range/price*100 < 0.30 or > 1.60.
Usage: python3 -I t1_gold_breakout.py <clean_data_dir> <out_dir> [n_random_seeds]
"""
import sys, os, time, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa

data_dir, out_dir = sys.argv[1], sys.argv[2]
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
os.makedirs(os.path.join(out_dir, 'trades'), exist_ok=True)
SYM = 'XAUUSD'
POINT = SPECS[SYM]['pip']   # 0.01 = 1 point; data resolution is 0.1 = 10 points
COSTS = {'gross': 0.0, 'spread15': 15.0, 'base42': 42.0, 'exp50': 50.0}

T0 = time.time()
data = Data(os.path.join(data_dir, f'{SYM}_M1.csv'), SYM)
sd = ServerDays(data)
days = sd.days
d1 = sd.d1.loc[days]
trend_up = (d1['close_prev'] > d1['sma50_prev']).values
trend_known = d1['sma50_prev'].notna().values
utc_days = pd.DatetimeIndex(pd.to_datetime(data.ts).normalize().unique())
utc_days = utc_days[(utc_days.dayofweek < 5) & (utc_days >= '2024-01-01')]
print(f'{SYM}: {data.n} M1 bars; {len(days)} server weekdays from {days[0].date()} to {days[-1].date()} ({time.time()-T0:.1f}s)')
h, l, o, c, n = data.h, data.l, data.o, data.c, data.n


def candidates(range_start='03:00', range_end='08:00', expiry='21:00', flat='21:00', buffer_pts=20.0, tp_mult=2.5,
               be_mult=1.5, side='both', min_rng=0.30, max_rng=1.60, sl_cap=0.006):
    a0, a1, w1, x1 = sd.idx(range_start), sd.idx(range_end), sd.idx(expiry), sd.idx(flat)
    buf = buffer_pts * POINT
    out = dict(entry_idx=[], entry_px=[], dir=[], sl=[], tp=[], be=[], tx=[], day=[], rng_pct=[], trend_up=[],
               rng=[], R=[], capped=[])
    st = dict(weekdays=len(days), range_ok=0, eligible=0, fills=0, skipped_narrow=0, skipped_wide=0, no_fill=0)
    for i in range(len(days)):
        if a1[i] - a0[i] < 200 or a1[i] >= n or x1[i] >= n or w1[i] <= a1[i]:
            continue
        st['range_ok'] += 1
        hi = h[a0[i]:a1[i]].max(); lo = l[a0[i]:a1[i]].min(); px0 = c[a1[i] - 1]
        rng = hi - lo; rp = rng / px0 * 100
        if rp < min_rng:
            st['skipped_narrow'] += 1; continue
        if rp > max_rng:
            st['skipped_wide'] += 1; continue
        st['eligible'] += 1
        buy_lvl, sell_lvl = hi + buf, lo - buf
        use_buy = side in ('both', 'long') or (side == 'trend' and trend_known[i] and trend_up[i]) \
            or (side == 'counter' and trend_known[i] and not trend_up[i])
        use_sell = side in ('both', 'short') or (side == 'trend' and trend_known[i] and not trend_up[i]) \
            or (side == 'counter' and trend_known[i] and trend_up[i])
        if not use_buy and not use_sell:
            continue
        j, d, px = first_trigger(h, l, o, a1[i], min(w1[i], n), buy_lvl if use_buy else 1e12, sell_lvl if use_sell else -1e12)
        if d == 0:
            st['no_fill'] += 1; continue
        st['fills'] += 1
        sl = sell_lvl if d == 1 else buy_lvl
        R = d * (px - sl)
        capped = False
        if R > sl_cap * px:
            R = sl_cap * px; sl = px - d * R; capped = True
        tp = px + d * tp_mult * R
        be = px + d * be_mult * R if be_mult else np.nan
        for k, v in zip(out.keys(), (j, px, d, sl, tp, be, x1[i], days[i], rp, (trend_up[i] if trend_known[i] else np.nan),
                                     rng, R, capped)):
            out[k].append(v)
    return {k: np.asarray(v) for k, v in out.items()}, st


def simulate(cand):
    return run_trades_be(data, cand['entry_idx'], cand['entry_px'], cand['dir'], cand['sl'], cand['tp'],
                         be_trig=cand['be'], time_exit_idx=cand['tx'],
                         extra=dict(time_exit_idx=cand['tx'], day=cand['day'], rng_pct=cand['rng_pct'],
                                    trend_up=cand['trend_up'], sl_capped=cand['capped']))


master, by_year, splits, stats = [], [], [], {}


def record(name, tr, st, group, params, save=True):
    if save:
        tr.to_csv(os.path.join(out_dir, 'trades', f't1_{name}.csv.gz'), index=False)
    stats[name] = {**st, **params, 'trades': len(tr)}
    for cc, cost in COSTS.items():
        t = apply_costs(tr, SYM, cost)
        base = dict(test='T1', group=group, variant=name, cost_case=cc, cost_pips=cost, **params)
        m10 = metrics(t, SYM, all_days=utc_days, ci_R=True, start_equity=10000.0)
        m5 = metrics(t, SYM, all_days=utc_days, with_ci=False, start_equity=5000.0)
        master.append({**base, **m10, 'pnl_usd_10k': m10.get('final_equity', np.nan) - 10000.0,
                       'pnl_usd_5k': m5.get('final_equity', np.nan) - 5000.0,
                       'return_pct_5k': m5.get('return_pct_1pct_risk', np.nan), 'maxdd_pct_5k': m5.get('max_dd_pct_1pct_risk', np.nan),
                       'eligible_days': st['eligible'], 'fills': st['fills']})
        by_year.extend(by_year_rows(t, SYM, base, utc_days))
        if group in ('base', 'be', 'expiry'):
            known = t['trend_up'].notna()
            with_tr = (t['dir'] == 1) == (t['trend_up'] == 1.0)
            for lab, g in (('long', t[t['dir'] == 1]), ('short', t[t['dir'] == -1]),
                           ('with_trend', t[known & with_tr]), ('counter_trend', t[known & ~with_tr]),
                           ('sl_capped', t[t['sl_capped'] == True]), ('sl_uncapped', t[t['sl_capped'] == False])):
                splits.append({**base, 'split': lab, **metrics(g, SYM, all_days=utc_days, with_ci=True, n_boot=1000)})
    print(f'  {name:36s} elig={st["eligible"]:4d} fills={st["fills"]:4d} trades={len(tr):4d} '
          f'gross={tr.gross.mean()/POINT:+7.1f}pt  reasons={tr.reason.value_counts().to_dict()}', flush=True)
    return tr


# ----------------------------------------------------------------------------------------------------------------------
# 1. Base rule and its direct variants
# ----------------------------------------------------------------------------------------------------------------------
print('\n== base and variants')
BASE = dict(range_start='03:00', range_end='08:00', expiry='21:00', buffer_pts=20.0, tp_mult=2.5, be_mult=1.5)
cand, st = candidates(**BASE)
base_tr = record('base_buf20_tp2.5_be1.5_w03-08_x21', simulate(cand), st, 'base', BASE)

for buf in (0.0, 50.0):
    p = {**BASE, 'buffer_pts': buf}; cand, st = candidates(**p)
    record(f'buf{buf:.0f}_tp2.5_be1.5_w03-08_x21', simulate(cand), st, 'buffer', p)
for tpm in (1.5, 2.0, 3.0):
    p = {**BASE, 'tp_mult': tpm}; cand, st = candidates(**p)
    record(f'buf20_tp{tpm}_be1.5_w03-08_x21', simulate(cand), st, 'tp', p)
for tpm in (1.5, 2.0, 2.5, 3.0):
    p = {**BASE, 'tp_mult': tpm, 'be_mult': None}; cand, st = candidates(**p)
    record(f'buf20_tp{tpm}_beOFF_w03-08_x21', simulate(cand), st, 'be', {**p, 'be_mult': 0.0})
for ex in ('12:00', '16:00'):
    p = {**BASE, 'expiry': ex}; cand, st = candidates(**p)
    record(f'buf20_tp2.5_be1.5_w03-08_x{ex[:2]}', simulate(cand), st, 'expiry', p)
for rs, re in (('02:00', '07:00'), ('04:00', '09:00')):
    p = {**BASE, 'range_start': rs, 'range_end': re}; cand, st = candidates(**p)
    record(f'buf20_tp2.5_be1.5_w{rs[:2]}-{re[:2]}_x21', simulate(cand), st, 'window', p)
# no range filter (author says it fails)
p = {**BASE, 'min_rng': 0.0, 'max_rng': 1e9}; cand, st = candidates(**p)
record('buf20_tp2.5_be1.5_w03-08_x21_noRangeFilter', simulate(cand), st, 'filter', {**BASE})

# ----------------------------------------------------------------------------------------------------------------------
# 2. Benchmarks: long-only, short-only, trend-filtered (50-day SMA of server-day closes), counter-trend
# ----------------------------------------------------------------------------------------------------------------------
print('\n== one-sided / trend-filtered versions')
for side in ('long', 'short', 'trend', 'counter'):
    p = {**BASE, 'side': side}; cand, st = candidates(**p)
    record(f'base_{side}_only', simulate(cand), st, 'side', p)

# ----------------------------------------------------------------------------------------------------------------------
# 3. Random-direction benchmark on the base trades (same entry bar, fill price, R, 2.5R target, 1.5R BE, 21:00 flat)
# ----------------------------------------------------------------------------------------------------------------------
print('\n== random direction (%d seeds)' % N_SEEDS)
rand_rows = []
for seed in range(N_SEEDS):
    rt = randomize_direction(data, base_tr, seed, be_mult=1.5, tp_mult=2.5)
    for cc, cost in COSTS.items():
        t = apply_costs(rt, SYM, cost)
        m = metrics(t, SYM, all_days=utc_days, with_ci=False)
        rand_rows.append(dict(test='T1', variant='random_dir_base', seed=seed, cost_case=cc, cost_pips=cost, **m))
        et = pd.to_datetime(t['entry_time'])
        for yr, g in t.groupby(et.dt.year):
            my = metrics(g, SYM, with_ci=False)
            rand_rows.append(dict(test='T1', variant='random_dir_base', seed=seed, cost_case=cc, cost_pips=cost, year=int(yr),
                                  trades=my['trades'], exp_pips=my['exp_pips'], exp_R=my['exp_R'], profit_factor=my['profit_factor']))
rand = pd.DataFrame(rand_rows)
rand.to_csv(os.path.join(out_dir, 't1_random.csv'), index=False)
rs = rand[rand['year'].isna()].groupby('cost_case').agg(mean_exp=('exp_pips', 'mean'), p05=('exp_pips', lambda x: pctl(x, 5)),
                                                        p95=('exp_pips', lambda x: pctl(x, 95)), mean_R=('exp_R', 'mean'),
                                                        mean_pf=('profit_factor', 'mean'), frac_pos=('exp_pips', lambda x: (x > 0).mean()))
print(rs.to_string())

# ----------------------------------------------------------------------------------------------------------------------
# 4. Buy-and-hold gold and intraday-long (08:00 -> 21:00 server) benchmarks
# ----------------------------------------------------------------------------------------------------------------------
print('\n== buy-and-hold / intraday long benchmarks')
bench = []
dd1 = sd.d1[(sd.d1.index >= '2024-01-01') & (sd.d1['dow'] < 5)]
yrs = sorted(set(dd1.index.year))
for label, sub in [('overall', dd1)] + [(str(y), dd1[dd1.index.year == y]) for y in yrs]:
    o0, c1 = sub['o'].iloc[0], sub['c'].iloc[-1]
    rets = sub['c'].pct_change().dropna()
    bench.append(dict(benchmark='buy_and_hold', period=label, start_px=o0, end_px=c1, pnl_points=(c1 - o0) / POINT,
                      return_pct=(c1 / o0 - 1) * 100, max_dd_pct=max_drawdown_pct(sub['c'].values),
                      sharpe=float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else np.nan, n_days=len(sub)))
# intraday long on eligible days and on all days: buy at the 08:00 bar open, sell at the 21:00 bar open (gross)
a0, a1, x1 = sd.idx('03:00'), sd.idx('08:00'), sd.idx('21:00')
rng_pct_day = np.full(len(days), np.nan)
for i in range(len(days)):
    if a1[i] - a0[i] >= 200 and a1[i] < n:
        rng_pct_day[i] = (h[a0[i]:a1[i]].max() - l[a0[i]:a1[i]].min()) / c[a1[i] - 1] * 100
elig_mask = (rng_pct_day >= 0.30) & (rng_pct_day <= 1.60)
for label, mask in (('all_days', np.ones(len(days), bool)), ('eligible_days', elig_mask)):
    ok = mask & (a1 < n) & (x1 < n) & (x1 > a1)
    pts = (o[x1[ok]] - o[a1[ok]]) / POINT
    dts = pd.DatetimeIndex(days[ok])
    for per, sel in [('overall', np.ones(len(pts), bool))] + [(str(y), np.asarray(dts.year == y)) for y in yrs]:
        x = pts[sel]
        bench.append(dict(benchmark=f'intraday_long_0800_2100_{label}', period=per, n_days=int(sel.sum()),
                          mean_points_per_day=x.mean() if len(x) else np.nan, total_points=x.sum(), win_rate=(x > 0).mean() * 100 if len(x) else np.nan,
                          ci_lo=bootstrap_ci(x)[0] if len(x) > 1 else np.nan, ci_hi=bootstrap_ci(x)[1] if len(x) > 1 else np.nan))
bench = pd.DataFrame(bench)
bench.to_csv(os.path.join(out_dir, 't1_benchmarks.csv'), index=False)
print(bench.to_string())

# range statistics by year (why days are skipped)
rng_rows = []
a0, a1 = sd.idx('03:00'), sd.idx('08:00')
for i in range(len(days)):
    if a1[i] - a0[i] >= 200 and a1[i] < n:
        hi = h[a0[i]:a1[i]].max(); lo = l[a0[i]:a1[i]].min(); px0 = c[a1[i] - 1]
        rng_rows.append(dict(day=days[i], rng_pct=(hi - lo) / px0 * 100, rng_usd=hi - lo, price=px0))
rng_df = pd.DataFrame(rng_rows)
rng_df['year'] = pd.to_datetime(rng_df['day']).dt.year
rsum = rng_df.groupby('year').agg(days=('rng_pct', 'size'), median_rng_pct=('rng_pct', 'median'), mean_rng_usd=('rng_usd', 'mean'),
                                  pct_below_0_30=('rng_pct', lambda x: (x < 0.30).mean() * 100),
                                  pct_above_1_60=('rng_pct', lambda x: (x > 1.60).mean() * 100), mean_price=('price', 'mean'))
rsum.to_csv(os.path.join(out_dir, 't1_range_stats.csv'))
print(rsum.to_string())

# ----------------------------------------------------------------------------------------------------------------------
# 5. Sensitivity grid: TP x buffer x window (BE 1.5R on, expiry/flat 21:00) = 36 cells
# ----------------------------------------------------------------------------------------------------------------------
print('\n== sensitivity grid')
sens = []
for (rs_, re_) in (('02:00', '07:00'), ('03:00', '08:00'), ('04:00', '09:00')):
    for buf in (0.0, 20.0, 50.0):
        for tpm in (1.5, 2.0, 2.5, 3.0):
            p = {**BASE, 'range_start': rs_, 'range_end': re_, 'buffer_pts': buf, 'tp_mult': tpm}
            cnd, st = candidates(**p)
            tr = simulate(cnd)
            row = dict(window=f'{rs_[:2]}-{re_[:2]}', buffer_pts=buf, tp_mult=tpm, eligible=st['eligible'], trades=len(tr))
            for cc, cost in COSTS.items():
                t = apply_costs(tr, SYM, cost)
                m = metrics(t, SYM, all_days=utc_days, with_ci=True, ci_R=True, n_boot=1000)
                row.update({f'{cc}_exp': m['exp_pips'], f'{cc}_expR': m['exp_R'], f'{cc}_pf': m['profit_factor'],
                            f'{cc}_ci_lo': m['ci_lo'], f'{cc}_ci_hi': m['ci_hi'], f'{cc}_net': m['net_pips'],
                            f'{cc}_ret_pct': m['return_pct_1pct_risk'], f'{cc}_dd_pct': m['max_dd_pct_1pct_risk']})
            sens.append(row)
            print(f'  w{row["window"]} buf{buf:.0f} tp{tpm}: n={len(tr)} base42 exp={row["base42_exp"]:+.1f} CI[{row["base42_ci_lo"]:+.0f},{row["base42_ci_hi"]:+.0f}] PF={row["base42_pf"]:.2f}', flush=True)
sens = pd.DataFrame(sens)
sens.to_csv(os.path.join(out_dir, 't1_sensitivity.csv'), index=False)
print('cells positive after base costs:', int((sens['base42_exp'] > 0).sum()), 'of', len(sens),
      '; CI excludes zero (positive):', int((sens['base42_ci_lo'] > 0).sum()), '; CI entirely negative:', int((sens['base42_ci_hi'] < 0).sum()))

pd.DataFrame(master).to_csv(os.path.join(out_dir, 't1_master.csv'), index=False)
pd.DataFrame(by_year).to_csv(os.path.join(out_dir, 't1_by_year.csv'), index=False)
pd.DataFrame(splits).to_csv(os.path.join(out_dir, 't1_splits.csv'), index=False)
json.dump(stats, open(os.path.join(out_dir, 't1_stats.json'), 'w'), indent=1, default=str)
print(f'\nDONE T1 in {time.time()-T0:.1f}s')
