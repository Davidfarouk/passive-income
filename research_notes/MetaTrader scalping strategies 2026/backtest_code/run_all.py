"""Run every strategy variant x symbol x cost case and write result tables.
Usage: python3 -I run_all.py <clean_data_dir> <results_dir> [n_random_seeds]
"""
import sys, os, json, time
import numpy as np, pandas as pd

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
from bt_engine import Data, SPECS, COST_CASES, apply_costs, metrics, session_of
import strategies as S

data_dir, out_dir = sys.argv[1], sys.argv[2]
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
SYMBOLS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['EURUSD', 'XAUUSD']   # optional symbol filter
SUFFIX = ('_' + '_'.join(SYMBOLS)) if len(sys.argv) > 4 else ''
os.makedirs(os.path.join(out_dir, 'trades'), exist_ok=True)

SESSION_STRATS = ('A', 'B', 'E', 'F', 'H')


def variants(symbol):
    pip = SPECS[symbol]['pip']
    v = []
    for tf in ('M5', 'M1'):
        for fast, slow in ((9, 21), (5, 13)):
            for tpm in (1.0, 1.5):
                v.append((f'A_ema{fast}_{slow}_tp{tpm}', tf, S.strat_A_ema_pullback,
                          dict(tf=tf, fast=fast, slow=slow, tp_mult=tpm)))
    for tf in ('M5', 'M1'):
        v.append(('B_bb20_2', tf, S.strat_B_bollinger, dict(tf=tf, rsi_filter=False)))
        v.append(('B_bb20_2_rsi14', tf, S.strat_B_bollinger, dict(tf=tf, rsi_filter=True)))
    buf = 2 * pip if symbol == 'EURUSD' else 20 * pip
    v.append(('C_asian_range_london_bo', 'M1', S.strat_C_asian_breakout, dict(buffer=buf)))
    rm = 30 if symbol == 'EURUSD' else 15
    for tpm in (1.0, 2.0):
        v.append((f'D_ny_orb_tp{tpm:.0f}x_1330utc', 'M1', S.strat_D_ny_orb, dict(range_minutes=rm, tp_mult=tpm, anchor='utc')))
        v.append((f'D_ny_orb_tp{tpm:.0f}x_nyse0930', 'M1', S.strat_D_ny_orb, dict(range_minutes=rm, tp_mult=tpm, anchor='ny')))
    for tf in ('M5', 'M1'):
        v.append(('E_rsi2_ema200', tf, S.strat_E_rsi2, dict(tf=tf)))
    for tf in ('M5', 'M1'):
        v.append(('F_stoch533_ema50', tf, S.strat_F_stoch, dict(tf=tf)))
    v.append(('H_twap_2sigma_fade', 'M1', S.strat_H_vwap_fade, dict()))
    return v


def cost_cases(symbol):
    cc = {'gross': 0.0}
    cc.update(COST_CASES[symbol])
    return cc


master, by_year, by_session, by_half, random_rows = [], [], [], [], []
info = {}
T0 = time.time()
for symbol in SYMBOLS:
    path = os.path.join(data_dir, f'{symbol}_M1.csv')
    if not os.path.exists(path):
        print('missing', path); continue
    data = Data(path, symbol)
    ts = pd.to_datetime(data.ts)
    days = pd.DatetimeIndex(ts.normalize().unique())
    days = days[(days.dayofweek < 5) & (days >= '2024-01-01')]
    start, end = pd.Timestamp('2024-01-01'), ts[-1]
    mid = start + (end - start) / 2
    info[symbol] = dict(m1_bars=int(data.n), first=str(ts[0]), last=str(ts[-1]), trading_days=int(len(days)),
                        mid_point=str(mid))
    print(f'\n===== {symbol}: {data.n} M1 bars, {ts[0]} -> {ts[-1]}, {len(days)} weekdays, half split at {mid}')

    for name, tf, fn, kw in variants(symbol):
        t0 = time.time()
        tr = fn(data, **kw)
        dt = time.time() - t0
        tr.to_csv(os.path.join(out_dir, 'trades', f'{symbol}_{name}_{tf}.csv.gz'), index=False)
        print(f'  {name:28s} {tf:3s} trades={len(tr):6d}  gross_mean={tr.gross.mean()/SPECS[symbol]["pip"]:+.2f}  ({dt:.1f}s)', flush=True)
        for cc, cost in cost_cases(symbol).items():
            t = apply_costs(tr, symbol, cost)
            base = dict(symbol=symbol, strategy=name, tf=tf, cost_case=cc, cost_pips=cost)
            master.append({**base, **metrics(t, symbol, all_days=days, ci_R=True)})
            et = pd.to_datetime(t['entry_time'])
            for yr, g in t.groupby(et.dt.year):
                ydays = days[days.year == yr]
                by_year.append({**base, 'year': int(yr), **metrics(g, symbol, all_days=ydays, with_ci=False)})
            for half, g in (('H1', t[et < mid]), ('H2', t[et >= mid])):
                hdays = days[days < mid] if half == 'H1' else days[days >= mid]
                by_half.append({**base, 'half': half, **metrics(g, symbol, all_days=hdays, with_ci=True)})
            if name[0] in SESSION_STRATS:
                sess = session_of(et.dt.hour.values)
                for s in ('Asia', 'London', 'NY'):
                    g = t[sess == s]
                    by_session.append({**base, 'session': s, **metrics(g, symbol, all_days=days, with_ci=True)})

    # random baseline
    for tf in ('M5', 'M1'):
        t0 = time.time()
        for seed in range(N_SEEDS):
            tr = S.strat_G_random(data, tf=tf, seed=seed)
            for cc, cost in cost_cases(symbol).items():
                t = apply_costs(tr, symbol, cost)
                m = metrics(t, symbol, all_days=days, with_ci=False)
                random_rows.append(dict(symbol=symbol, strategy='G_random_1atr', tf=tf, cost_case=cc, cost_pips=cost,
                                        seed=seed, **m))
        print(f'  G_random {tf}: {N_SEEDS} seeds done ({time.time()-t0:.1f}s)', flush=True)

pd.DataFrame(master).to_csv(os.path.join(out_dir, f'master{SUFFIX}.csv'), index=False)
pd.DataFrame(by_year).to_csv(os.path.join(out_dir, f'by_year{SUFFIX}.csv'), index=False)
pd.DataFrame(by_session).to_csv(os.path.join(out_dir, f'by_session{SUFFIX}.csv'), index=False)
pd.DataFrame(by_half).to_csv(os.path.join(out_dir, f'by_half{SUFFIX}.csv'), index=False)
pd.DataFrame(random_rows).to_csv(os.path.join(out_dir, f'random{SUFFIX}.csv'), index=False)
info['runtime_sec'] = time.time() - T0
info['n_random_seeds'] = N_SEEDS
json.dump(info, open(os.path.join(out_dir, f'run_info{SUFFIX}.json'), 'w'), indent=1)
print('\nDONE in', round(time.time() - T0, 1), 's')
