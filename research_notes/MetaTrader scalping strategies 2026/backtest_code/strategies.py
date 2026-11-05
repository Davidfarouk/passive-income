"""Retail scalping strategy definitions. Each function returns a trades DataFrame (gross, pre-cost) via bt_engine.run_trades.

All signals are evaluated on CLOSED bars of the signal timeframe; market entries fill at the open of the next bar
(for M5 signals: the first M1 bar at/after the M5 bar's close). Stop-order strategies (C, D) fill intrabar at the stop
level (or at the bar open if it gaps through). Exits are managed on M1 bars.
"""
import numpy as np
import pandas as pd
from bt_engine import Data, ema, sma, atr, rsi, bollinger, stochastic, run_trades, first_trigger


# ----------------------------------------------------------------------------------------------------------------------
def _finalize(data: Data, entry_idx, direction, sl_dist=None, tp_dist=None, sl_lvl=None, tp_lvl=None,
              time_exit_idx=None, entry_px=None, start_time='2024-01-01'):
    entry_idx = np.asarray(entry_idx, dtype=np.int64)
    direction = np.asarray(direction, dtype=np.int64)
    m = len(entry_idx)
    valid = entry_idx < data.n
    if entry_px is None:
        ep = np.full(m, np.nan)
        ep[valid] = data.o[entry_idx[valid]]
    else:
        ep = np.asarray(entry_px, dtype=np.float64)
    if sl_lvl is None:
        sl_lvl = ep - direction * np.asarray(sl_dist, dtype=np.float64)
    if tp_lvl is None:
        tp_lvl = np.full(m, np.nan) if tp_dist is None else ep + direction * np.asarray(tp_dist, dtype=np.float64)
    sl_lvl = np.asarray(sl_lvl, dtype=np.float64).copy()
    tp_lvl = np.asarray(tp_lvl, dtype=np.float64)
    if time_exit_idx is None:
        time_exit_idx = np.full(m, data.n + 1, dtype=np.int64)
    time_exit_idx = np.asarray(time_exit_idx, dtype=np.int64)
    # minimum stop distance = one price tick of the data (1 pip EURUSD, $0.10 XAUUSD): a stop closer than that is
    # not placeable in practice and would make R-multiples meaningless. Widen such stops to one tick and flag them.
    tick = data.spec['tick']
    dist = direction * (ep - sl_lvl)
    floored = np.isfinite(dist) & (dist < tick)
    sl_lvl[floored] = ep[floored] - direction[floored] * tick
    # drop trades whose stop is not adverse or whose target is not favourable at the fill price
    ok = valid & (direction * (ep - sl_lvl) > 0)
    ok &= np.isnan(tp_lvl) | (direction * (tp_lvl - ep) > 0)
    ok &= np.isfinite(sl_lvl)
    tr = run_trades(data, entry_idx[ok], ep[ok], direction[ok], sl_lvl[ok], tp_lvl[ok], time_exit_idx[ok],
                    start_time=start_time, flags=floored[ok])
    return tr


def _sig_to_entries(bars, long_sig, short_sig):
    long_sig = long_sig.fillna(False).values
    short_sig = short_sig.fillna(False).values
    k_long = np.where(long_sig)[0]
    k_short = np.where(short_sig)[0]
    k = np.concatenate([k_long, k_short])
    d = np.concatenate([np.ones(len(k_long), dtype=np.int64), -np.ones(len(k_short), dtype=np.int64)])
    order = np.argsort(k, kind='stable')
    return k[order], d[order]


# ----------------------------------------------------------------------------------------------------------------------
# A. EMA pullback trend scalp
# ----------------------------------------------------------------------------------------------------------------------
def strat_A_ema_pullback(data: Data, tf='M5', fast=9, slow=21, tp_mult=1.0, atr_mult=1.5):
    b = data.resample(tf)
    ef, es, e50 = ema(b['close'], fast), ema(b['close'], slow), ema(b['close'], 50)
    a = atr(b, 14)
    up = (ef > es) & (b['close'] > e50)
    dn = (ef < es) & (b['close'] < e50)
    long_sig = up & (b['low'] <= ef) & (b['close'] > ef) & (b['close'] > b['open'])
    short_sig = dn & (b['high'] >= ef) & (b['close'] < ef) & (b['close'] < b['open'])
    k, d = _sig_to_entries(b, long_sig, short_sig)
    sl = atr_mult * a.values[k]
    return _finalize(data, b['m1_next'].values[k], d, sl_dist=sl, tp_dist=tp_mult * sl)


# ----------------------------------------------------------------------------------------------------------------------
# B. Bollinger Band mean reversion
# ----------------------------------------------------------------------------------------------------------------------
def strat_B_bollinger(data: Data, tf='M5', rsi_filter=False, atr_mult=1.0):
    b = data.resample(tf)
    c = b['close']
    m, ub, lb = bollinger(c, 20, 2.0)
    a = atr(b, 14)
    long_sig = (c.shift(1) < lb.shift(1)) & (c > lb) & (c < m)
    short_sig = (c.shift(1) > ub.shift(1)) & (c < ub) & (c > m)
    if rsi_filter:
        r = rsi(c, 14)
        long_sig &= r.shift(1) < 30
        short_sig &= r.shift(1) > 70
    k, d = _sig_to_entries(b, long_sig, short_sig)
    sl_lvl = np.where(d == 1, lb.values[k] - atr_mult * a.values[k], ub.values[k] + atr_mult * a.values[k])
    tp_lvl = m.values[k]
    return _finalize(data, b['m1_next'].values[k], d, sl_lvl=sl_lvl, tp_lvl=tp_lvl)


# ----------------------------------------------------------------------------------------------------------------------
# Daily helpers
# ----------------------------------------------------------------------------------------------------------------------
def _trading_days(data: Data):
    days = pd.DatetimeIndex(pd.to_datetime(data.ts).normalize().unique())
    return days[(days.dayofweek < 5) & (days >= pd.Timestamp('2024-01-01'))]


def _idx(data: Data, times):
    return data.idx_at_or_after(np.asarray(times, dtype='datetime64[ns]'))


# ----------------------------------------------------------------------------------------------------------------------
# C. London open Asian-range breakout (fixed UTC clock as in the common retail spec)
# ----------------------------------------------------------------------------------------------------------------------
def strat_C_asian_breakout(data: Data, buffer=0.0002, range_start='00:00', range_end='07:00', order_end='10:00',
                           close_at='12:00', sl_cap_mult=1.5, tp_mult=1.0, min_range_bars=120):
    days = _trading_days(data)
    a0 = _idx(data, days + pd.Timedelta(range_start + ':00'))
    a1 = _idx(data, days + pd.Timedelta(range_end + ':00'))
    w1 = _idx(data, days + pd.Timedelta(order_end + ':00'))
    x1 = _idx(data, days + pd.Timedelta(close_at + ':00'))
    h, l, o = data.h, data.l, data.o
    E, P, D, SL, TP, TX = [], [], [], [], [], []
    for i in range(len(days)):
        if a1[i] - a0[i] < min_range_bars or a1[i] >= data.n:
            continue
        hi = h[a0[i]:a1[i]].max(); lo = l[a0[i]:a1[i]].min(); rng = hi - lo
        if rng <= 0:
            continue
        j, d, px = first_trigger(h, l, o, a1[i], min(w1[i], data.n), hi + buffer, lo - buffer)
        if d == 0:
            continue
        if d == 1:
            sl = max(lo, px - sl_cap_mult * rng); tp = px + tp_mult * rng
        else:
            sl = min(hi, px + sl_cap_mult * rng); tp = px - tp_mult * rng
        E.append(j); P.append(px); D.append(d); SL.append(sl); TP.append(tp); TX.append(x1[i])
    return _finalize(data, E, D, sl_lvl=SL, tp_lvl=TP, time_exit_idx=TX, entry_px=P)


# ----------------------------------------------------------------------------------------------------------------------
# D. New York opening range breakout
# ----------------------------------------------------------------------------------------------------------------------
def strat_D_ny_orb(data: Data, range_minutes=15, tp_mult=1.0, anchor='utc', order_end_minutes=150,
                   flat_minutes=210, buffer=0.0):
    """anchor='utc': range starts 13:30 UTC every day (as specified). anchor='ny': range starts 09:30 New York local
    time (DST-aware: 13:30 UTC in summer, 14:30 UTC in winter). Orders active until range_start+order_end_minutes;
    flat at range_start+flat_minutes (17:00 UTC for the 13:30 anchor)."""
    days = _trading_days(data)
    if anchor == 'utc':
        r0 = days + pd.Timedelta('13:30:00')
    else:
        local = pd.DatetimeIndex([d + pd.Timedelta('09:30:00') for d in days]).tz_localize('America/New_York')
        r0 = pd.DatetimeIndex(local.tz_convert('UTC').tz_localize(None))
    i0 = _idx(data, r0.values)
    i1 = _idx(data, (r0 + pd.Timedelta(minutes=range_minutes)).values)
    w1 = _idx(data, (r0 + pd.Timedelta(minutes=order_end_minutes)).values)
    x1 = _idx(data, (r0 + pd.Timedelta(minutes=flat_minutes)).values)
    h, l, o = data.h, data.l, data.o
    E, P, D, SL, TP, TX = [], [], [], [], [], []
    for i in range(len(days)):
        if i1[i] - i0[i] < range_minutes * 0.8 or i1[i] >= data.n:
            continue
        hi = h[i0[i]:i1[i]].max(); lo = l[i0[i]:i1[i]].min(); rng = hi - lo
        if rng <= 0:
            continue
        mid = (hi + lo) / 2
        j, d, px = first_trigger(h, l, o, i1[i], min(w1[i], data.n), hi + buffer, lo - buffer)
        if d == 0:
            continue
        tp = px + d * tp_mult * rng
        E.append(j); P.append(px); D.append(d); SL.append(mid); TP.append(tp); TX.append(x1[i])
    return _finalize(data, E, D, sl_lvl=SL, tp_lvl=TP, time_exit_idx=TX, entry_px=P)


# ----------------------------------------------------------------------------------------------------------------------
# E. RSI(2) extreme mean reversion with EMA200 filter
# ----------------------------------------------------------------------------------------------------------------------
def strat_E_rsi2(data: Data, tf='M5', max_bars=12, atr_mult=2.0):
    b = data.resample(tf)
    c = b['close']
    r2 = rsi(c, 2)
    e200 = ema(c, 200)
    a = atr(b, 14)
    long_sig = (r2 < 10) & (c > e200)
    short_sig = (r2 > 90) & (c < e200)
    k, d = _sig_to_entries(b, long_sig, short_sig)
    m1_next = b['m1_next'].values
    # signal exits: RSI2 > 60 closes longs, RSI2 < 40 closes shorts; fill at next bar open
    ex_long = np.sort(m1_next[(r2 > 60).fillna(False).values])
    ex_short = np.sort(m1_next[(r2 < 40).fillna(False).values])
    entry = m1_next[k]
    sig_exit = np.where(d == 1, ex_long[np.minimum(np.searchsorted(ex_long, entry, side='right'), len(ex_long) - 1)],
                        ex_short[np.minimum(np.searchsorted(ex_short, entry, side='right'), len(ex_short) - 1)])
    kk = np.minimum(k + max_bars, len(b) - 1)
    time_exit = np.minimum(sig_exit, m1_next[kk])
    time_exit = np.where(time_exit <= entry, data.n + 1, time_exit)
    return _finalize(data, entry, d, sl_dist=atr_mult * a.values[k], time_exit_idx=time_exit)


# ----------------------------------------------------------------------------------------------------------------------
# F. Stochastic(5,3,3) crossover + EMA(50) trend filter
# ----------------------------------------------------------------------------------------------------------------------
def strat_F_stoch(data: Data, tf='M5', sl_mult=1.0, tp_mult=1.0):
    b = data.resample(tf)
    K, D = stochastic(b, 5, 3, 3)
    e50 = ema(b['close'], 50)
    a = atr(b, 14)
    cross_up = (K.shift(1) <= D.shift(1)) & (K > D) & (K.shift(1) < 20)
    cross_dn = (K.shift(1) >= D.shift(1)) & (K < D) & (K.shift(1) > 80)
    long_sig = cross_up & (b['close'] > e50)
    short_sig = cross_dn & (b['close'] < e50)
    k, d = _sig_to_entries(b, long_sig, short_sig)
    return _finalize(data, b['m1_next'].values[k], d, sl_dist=sl_mult * a.values[k], tp_dist=tp_mult * a.values[k])


# ----------------------------------------------------------------------------------------------------------------------
# G. Random entry baseline (same SL/TP structure: 1 x ATR each side)
# ----------------------------------------------------------------------------------------------------------------------
def strat_G_random(data: Data, tf='M5', seed=0, p=None, sl_mult=1.0, tp_mult=1.0):
    b = data.resample(tf)
    a = atr(b, 14)
    if p is None:
        p = 1 / 100 if tf == 'M5' else 1 / 300
    rng = np.random.default_rng(seed)
    sig = rng.random(len(b)) < p
    dirs = rng.choice(np.array([-1, 1]), size=len(b))
    sig &= a.notna().values
    k = np.where(sig)[0]
    d = dirs[k]
    return _finalize(data, b['m1_next'].values[k], d, sl_dist=sl_mult * a.values[k], tp_dist=tp_mult * a.values[k])


# ----------------------------------------------------------------------------------------------------------------------
# H. Session (T)WAP +/- 2 sigma fade on M1 (Forexite has no volume, so this is a time-weighted VWAP proxy)
# ----------------------------------------------------------------------------------------------------------------------
def strat_H_vwap_fade(data: Data, k_sigma=2.0, atr_mult=1.0, min_bars=30):
    b = data.resample('M1')
    tp_px = (b['high'] + b['low'] + b['close']) / 3
    day = b['datetime'].dt.normalize()
    g = tp_px.groupby(day)
    n = g.cumcount() + 1
    cs = g.cumsum()
    cs2 = (tp_px ** 2).groupby(day).cumsum()
    vwap = cs / n
    var = (cs2 / n - vwap ** 2).clip(lower=0)
    sd = np.sqrt(var)
    ub, lb = vwap + k_sigma * sd, vwap - k_sigma * sd
    a = atr(b, 14)
    c = b['close']
    enough = n >= min_bars
    long_sig = enough & (c.shift(1) < lb.shift(1)) & (c > lb) & (c < vwap)
    short_sig = enough & (c.shift(1) > ub.shift(1)) & (c < ub) & (c > vwap)
    k, d = _sig_to_entries(b, long_sig, short_sig)
    sl_lvl = np.where(d == 1, lb.values[k] - atr_mult * a.values[k], ub.values[k] + atr_mult * a.values[k])
    tp_lvl = vwap.values[k]
    # flat at the end of the UTC day (session reset)
    day_end = (day.values[k] + np.timedelta64(1, 'D')).astype('datetime64[ns]')
    tx = data.idx_at_or_after(day_end)
    return _finalize(data, b['m1_next'].values[k], d, sl_lvl=sl_lvl, tp_lvl=tp_lvl, time_exit_idx=tx)
