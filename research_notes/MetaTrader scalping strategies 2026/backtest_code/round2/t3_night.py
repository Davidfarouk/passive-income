"""T3. Night-scalping mean reversion on low-volatility crosses (+ EURUSD), server time (NY+7h).

Window: entries only when the signal bar closes (or the limit order is touched) between 21:00 and 02:00 server time;
every position is force-closed at 06:00 server at the latest. Friday evenings are skipped (the market closes at 24:00
server on Friday, so a Friday-night position could not be flat by 06:00 without carrying it over the weekend).
Variants
  N1 Bollinger fade (M5): BB(20,2); long when bar t-1 closed below the lower band and bar t closed back inside (and
     below the middle band); TP = middle band at signal time; SL = 1.5x (or 2x) the TP distance from the fill.
  N2 Asian-range limit fade: at 21:00 server take the range of 17:00-21:00 server; sell limit at the high, buy limit at
     the low, valid until 02:00; TP 6 / SL 12 pips (Fenrir-style defaults) and TP 10 / SL 20; one position at a time,
     the other limit stays armed after the first position closes.
  N3 RSI(2) extreme (M5): long when RSI(2) < 5 and close > EMA(200); exit when RSI(2) > 60, after 12 bars, at
     SL = 2 x ATR(14) or at 06:00; mirror for shorts (RSI(2) > 95, exit < 40). Also run all-day (no window, no 06:00).
Costs (round trip, pips): night spread + 0.7 commission + 0.4 slippage; 'full' adds +1.0 pip for entries 23:45-00:15
server (rollover widening) and 0.5 pip swap per position held across 00:00 server (x3 when that rollover is the
Wednesday-to-Thursday one).
Usage: python3 -I t3_night.py <clean_data_dir> <out_dir> [n_random_seeds] [SYM1,SYM2,...]
"""
import sys, os, time, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa
from bt_engine import ema, atr, rsi, bollinger

data_dir, out_dir = sys.argv[1], sys.argv[2]
N_SEEDS = int(sys.argv[3]) if len(sys.argv) > 3 else 50
SYMBOLS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['AUDNZD', 'EURCHF', 'EURGBP', 'AUDCAD', 'GBPCAD', 'NZDCAD', 'EURAUD', 'EURUSD']
os.makedirs(os.path.join(out_dir, 'trades'), exist_ok=True)

NIGHT_SPREAD = {'EURCHF': 0.8, 'AUDNZD': 1.0, 'EURGBP': 0.7, 'AUDCAD': 0.9, 'GBPCAD': 1.3, 'NZDCAD': 1.1, 'EURAUD': 1.0, 'EURUSD': 0.4}
COMMISSION, SLIPPAGE, ROLLOVER_ADD, SWAP_PIP = 0.7, 0.4, 1.0, 0.5
WIN_START, WIN_END, FLAT = 21 * 60, 2 * 60, '06:00'      # server minutes of day


def cost_cases(tr, symbol, sd):
    """Return dict cost_case -> per-trade round-trip cost (pips)."""
    base = NIGHT_SPREAD[symbol] + COMMISSION + SLIPPAGE
    s_in = sd.srv[tr['entry_idx'].values]
    s_out = sd.srv[tr['exit_idx'].values]
    m_in = server_minute_of_day(s_in)
    roll = np.where((m_in >= 23 * 60 + 45) | (m_in < 15), ROLLOVER_ADD, 0.0)
    crossed = (s_out.astype('datetime64[D]') != s_in.astype('datetime64[D]')).astype(float)
    thursday = server_dow(s_out) == 3
    swap = SWAP_PIP * crossed * np.where(thursday, 3.0, 1.0)
    return {'gross': np.zeros(len(tr)), 'spread_only': np.full(len(tr), NIGHT_SPREAD[symbol]),
            'base': np.full(len(tr), base), 'full': base + roll + swap}, dict(base=base, pct_rollover=roll.mean() * 100 / ROLLOVER_ADD if len(tr) else 0,
                                                                              pct_swap=crossed.mean() * 100 if len(tr) else 0)


def sig_to_entries(long_sig, short_sig):
    kl = np.where(long_sig.fillna(False).values)[0]; ks = np.where(short_sig.fillna(False).values)[0]
    k = np.concatenate([kl, ks]); d = np.concatenate([np.ones(len(kl), np.int64), -np.ones(len(ks), np.int64)])
    order = np.argsort(k, kind='stable')
    return k[order], d[order]


T0 = time.time()
master, by_year, rand_rows, stats, pooled = [], [], [], {}, {}

for SYM in SYMBOLS:
    t0 = time.time()
    data = Data(os.path.join(data_dir, f'{SYM}_M1.csv'), SYM)
    sd = ServerDays(data)
    pip, tick = SPECS[SYM]['pip'], SPECS[SYM]['tick']
    h, l, o, c, n = data.h, data.l, data.o, data.c, data.n
    utc_days = pd.DatetimeIndex(pd.to_datetime(data.ts).normalize().unique())
    utc_days = utc_days[(utc_days.dayofweek < 5) & (utc_days >= '2024-01-01')]
    b = data.resample('M5')
    close_srv = utc_to_server((b['datetime'] + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]'))
    cm = server_minute_of_day(close_srv); cdow = server_dow(close_srv)
    in_window = ((cm >= WIN_START) | (cm < WIN_END)) & ~((cdow == 4) & (cm >= WIN_START)) & (cdow < 5)
    window = pd.Series(in_window, index=b.index)
    print(f'\n===== {SYM}: {n} M1 bars, {len(b)} M5 bars, window bars {in_window.sum()} ({time.time()-t0:.1f}s)', flush=True)

    def finish(name, tr, params, tx_random=None):
        """Cost, metrics, by-year, random-direction benchmark for one variant."""
        tr.to_csv(os.path.join(out_dir, 'trades', f't3_{SYM}_{name}.csv.gz'), index=False)
        cc, cinfo = cost_cases(tr, SYM, sd)
        stats[f'{SYM}_{name}'] = {**params, 'trades': len(tr), **cinfo}
        nights = len(sd.days)
        for case, cost in cc.items():
            t = apply_costs(tr, SYM, cost)
            base = dict(test='T3', symbol=SYM, variant=name, cost_case=case, cost_pips=float(np.mean(cost)) if len(cost) else np.nan, **params)
            master.append({**base, **metrics(t, SYM, all_days=utc_days, ci_R=True), 'trades_per_night': len(t) / nights})
            by_year.extend(by_year_rows(t, SYM, base, utc_days))
            pooled.setdefault((name, case), []).append(t.assign(symbol=SYM))
        # random direction: same entries, same SL/TP distances, exit at the deadline (N3: 12 bars or 06:00, no RSI exit)
        if len(tr) > 10:
            cc_r = None
            for seed in range(N_SEEDS):
                rt = randomize_direction(data, tr, seed, time_exit_idx=tx_random)
                cc_r, _ = cost_cases(rt, SYM, sd)
                for case, cost in cc_r.items():
                    m = metrics(apply_costs(rt, SYM, cost), SYM, with_ci=False)
                    rand_rows.append(dict(test='T3', symbol=SYM, variant=name, seed=seed, cost_case=case, trades=m['trades'],
                                          exp_pips=m['exp_pips'], exp_R=m['exp_R'], profit_factor=m['profit_factor'], win_rate=m['win_rate']))
        print(f'  {name:26s} trades={len(tr):5d} gross={tr.gross.mean()/pip:+6.2f} pips  avg stop={tr.risk.mean()/pip:5.1f}  '
              f'reasons={tr.reason.value_counts().to_dict()}  bars={tr.bars.mean():.0f}', flush=True)

    # ------------------------------------------------------------------------------------------------------------------
    # N1 Bollinger fade
    # ------------------------------------------------------------------------------------------------------------------
    cl = b['close']; mid, ub, lb = bollinger(cl, 20, 2.0)
    long_sig = (cl.shift(1) < lb.shift(1)) & (cl >= lb) & (cl < mid) & window
    short_sig = (cl.shift(1) > ub.shift(1)) & (cl <= ub) & (cl > mid) & window
    k, d = sig_to_entries(long_sig, short_sig)
    entry = b['m1_next'].values[k]; valid = entry < n
    k, d, entry = k[valid], d[valid], entry[valid]
    ep = o[entry]; tp_lvl = mid.values[k]; tpd = d * (tp_lvl - ep)
    tx = sd.next_clock_idx(entry, FLAT)
    for sl_mult in (1.5, 2.0):
        for min_tp in (0, 5):
            ok = tpd >= max(tick, min_tp * pip)
            sl_lvl = ep - d * sl_mult * tpd
            tr = run_trades_be(data, entry[ok], ep[ok], d[ok], sl_lvl[ok], tp_lvl[ok], time_exit_idx=tx[ok],
                               extra=dict(time_exit_idx=tx[ok]))
            finish(f'N1_bb_sl{sl_mult}x_mintp{min_tp}', tr, dict(family='N1', sl_mult=sl_mult, min_tp_pips=min_tp, window='night'))

    # ------------------------------------------------------------------------------------------------------------------
    # N2 Asian-range limit fade (two passes: first touched level, then the other level after the first position closes)
    # ------------------------------------------------------------------------------------------------------------------
    days = sd.days[sd.days.dayofweek < 4]           # Monday..Thursday evenings
    r0, r1 = sd.idx('17:00', days), sd.idx('21:00', days)
    w1, x1 = sd.idx('02:00', days, day_offset=1), sd.idx(FLAT, days, day_offset=1)
    for tp_pips, sl_pips in ((6, 12), (10, 20)):
        E1 = dict(entry_idx=[], entry_px=[], dir=[], sl=[], tp=[], tx=[], w1=[], other=[], day=[])
        n_days = 0
        for i in range(len(days)):
            if r1[i] - r0[i] < 200 or r1[i] >= n or w1[i] >= n or w1[i] <= r1[i]:
                continue
            n_days += 1
            hi = h[r0[i]:r1[i]].max(); lo = l[r0[i]:r1[i]].min()
            if hi - lo < 2 * tick:
                continue
            j, dt, px = first_trigger(h, l, o, r1[i], min(w1[i], n), hi, lo)   # touch of the high -> sell limit fills
            if dt == 0:
                continue
            dd = -dt
            E1['entry_idx'].append(j); E1['entry_px'].append(px); E1['dir'].append(dd)
            E1['sl'].append(px - dd * sl_pips * pip); E1['tp'].append(px + dd * tp_pips * pip); E1['tx'].append(x1[i])
            E1['w1'].append(w1[i]); E1['other'].append(lo if dd == -1 else hi); E1['day'].append(days[i])
        E1 = {kk: np.asarray(v) for kk, v in E1.items()}
        tr1 = run_trades_be(data, E1['entry_idx'], E1['entry_px'], E1['dir'], E1['sl'], E1['tp'], time_exit_idx=E1['tx'],
                            extra=dict(time_exit_idx=E1['tx'], w1=E1['w1'], other=E1['other'], leg=np.ones(len(E1['dir']), int)))
        # pass 2
        E2 = dict(entry_idx=[], entry_px=[], dir=[], sl=[], tp=[], tx=[])
        for _, r in tr1.iterrows():
            if r['exit_idx'] + 1 >= r['w1']:
                continue
            lvl = r['other']
            if r['dir'] == -1:    # first leg was a sell at the high -> remaining order is the buy limit at the low
                j, dt, px = first_trigger(h, l, o, int(r['exit_idx']) + 1, int(min(r['w1'], n)), 1e12, lvl); dd = 1
            else:
                j, dt, px = first_trigger(h, l, o, int(r['exit_idx']) + 1, int(min(r['w1'], n)), lvl, -1e12); dd = -1
            if dt == 0:
                continue
            E2['entry_idx'].append(j); E2['entry_px'].append(px); E2['dir'].append(dd)
            E2['sl'].append(px - dd * sl_pips * pip); E2['tp'].append(px + dd * tp_pips * pip); E2['tx'].append(int(r['time_exit_idx']))
        E2 = {kk: np.asarray(v) for kk, v in E2.items()}
        tr2 = run_trades_be(data, E2['entry_idx'], E2['entry_px'], E2['dir'], E2['sl'], E2['tp'], time_exit_idx=E2['tx'],
                            extra=dict(time_exit_idx=E2['tx'], leg=np.full(len(E2['dir']), 2, int))) if len(E2['dir']) else tr1.iloc[0:0]
        tr = pd.concat([tr1.drop(columns=['w1', 'other']), tr2], ignore_index=True).sort_values('entry_idx').reset_index(drop=True)
        finish(f'N2_limit_tp{tp_pips}_sl{sl_pips}', tr, dict(family='N2', tp_pips=tp_pips, sl_pips=sl_pips, window='night', nights=n_days))

    # ------------------------------------------------------------------------------------------------------------------
    # N3 RSI(2) extreme with EMA(200) filter, night window and all-day
    # ------------------------------------------------------------------------------------------------------------------
    r2 = rsi(cl, 2); e200 = ema(cl, 200); a14 = atr(b, 14)
    m1_next = b['m1_next'].values
    ex_long = np.sort(m1_next[(r2 > 60).fillna(False).values]); ex_short = np.sort(m1_next[(r2 < 40).fillna(False).values])
    for mode in ('night', 'allday'):
        ls = (r2 < 5) & (cl > e200); ss = (r2 > 95) & (cl < e200)
        if mode == 'night':
            ls &= window; ss &= window
        k, d = sig_to_entries(ls, ss)
        entry = m1_next[k]; valid = (entry < n) & np.isfinite(a14.values[k])
        k, d, entry = k[valid], d[valid], entry[valid]
        sig_exit = np.where(d == 1, ex_long[np.minimum(np.searchsorted(ex_long, entry, side='right'), len(ex_long) - 1)],
                            ex_short[np.minimum(np.searchsorted(ex_short, entry, side='right'), len(ex_short) - 1)])
        bar_exit = m1_next[np.minimum(k + 12, len(b) - 1)]
        tx_hold = bar_exit.copy()
        if mode == 'night':
            tx_hold = np.minimum(tx_hold, sd.next_clock_idx(entry, FLAT))
        tx = np.minimum(sig_exit, tx_hold)
        tx = np.where(tx <= entry, n + 1, tx); tx_hold = np.where(tx_hold <= entry, n + 1, tx_hold)
        sl_dist = 2.0 * a14.values[k]
        ep = o[entry]
        tr = run_trades_be(data, entry, ep, d, ep - d * sl_dist, np.full(len(k), np.nan), time_exit_idx=tx,
                           extra=dict(time_exit_idx=tx_hold))
        finish(f'N3_rsi2_{mode}', tr, dict(family='N3', window=mode), tx_random=tx_hold)
    print(f'  {SYM} done in {time.time()-t0:.1f}s', flush=True)

# pooled crosses (all symbols except EURUSD) per variant and cost case
for (name, case), lst in pooled.items():
    tt = pd.concat([x for x in lst if x['symbol'].iloc[0] != 'EURUSD'], ignore_index=True) if any(x['symbol'].iloc[0] != 'EURUSD' for x in lst) else None
    if tt is None or len(tt) == 0:
        continue
    base = dict(test='T3', symbol='POOLED_CROSSES', variant=name, cost_case=case, cost_pips=tt['cost_pips'].mean(), family=name[:2])
    # use the first symbol's spec for pip accounting (all crosses are 4-digit, pip = 0.0001); $-curve uses AUDNZD pip value
    master.append({**base, **metrics(tt, 'AUDNZD', ci_R=True)})
    et = pd.to_datetime(tt['entry_time'])
    for yr, g in tt.groupby(et.dt.year):
        by_year.append({**base, 'year': int(yr), **metrics(g, 'AUDNZD', with_ci=True, n_boot=1000)})

pd.DataFrame(master).to_csv(os.path.join(out_dir, 't3_master.csv'), index=False)
pd.DataFrame(by_year).to_csv(os.path.join(out_dir, 't3_by_year.csv'), index=False)
pd.DataFrame(rand_rows).to_csv(os.path.join(out_dir, 't3_random.csv'), index=False)
json.dump(stats, open(os.path.join(out_dir, 't3_stats.json'), 'w'), indent=1, default=str)
print(f'\nDONE T3 in {time.time()-T0:.1f}s')
