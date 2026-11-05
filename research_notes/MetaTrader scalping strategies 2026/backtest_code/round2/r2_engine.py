"""Round-2 extensions to bt_engine: broker 'server time' (New York + 7h), break-even-aware trade simulator,
per-trade (array) costs, server-day daily bars, extra symbols, random-direction benchmark helper.

Server-time convention
----------------------
Many MT5 brokers (IC Markets, Pepperstone, ...) run server time = New York local time + 7 hours, so that 00:00 server
is 17:00 New York (the FX daily rollover) and the week has exactly five daily candles. That is GMT+2 while the US is on
standard time and GMT+3 while the US is on daylight time. US DST: second Sunday in March 02:00 local (07:00 UTC) to
first Sunday in November 02:00 local (06:00 UTC).
"""
import sys, os
import numpy as np
import pandas as pd
import numba
import datetime as _dt

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ../ = round-one code dir
if CODE not in sys.path:
    sys.path.insert(0, CODE)
import bt_engine as E
from bt_engine import Data, bootstrap_ci, longest_losing_streak, max_drawdown, max_drawdown_pct

# Price levels are sums of decimals (e.g. 2726.7 + 0.2 = 2726.8999999999996); a quote that prints exactly at the level
# must count as a touch, so every level comparison uses a tolerance far below one tick.
EPS = 1e-7

# ----------------------------------------------------------------------------------------------------------------------
# Extra symbols (Forexite: 4-digit crosses). pip_value_per_lot is an approximate USD value of one pip for one standard
# lot (quote-currency pip value x 2024-26 average USD rate); it only affects the $-based 1%-risk equity curve, not pips.
# ----------------------------------------------------------------------------------------------------------------------
EXTRA_SPECS = {
    'AUDNZD': dict(pip=0.0001, unit='pip', pip_value_per_lot=6.0, tick=0.0001),    # 10 NZD ~ $6.0
    'EURCHF': dict(pip=0.0001, unit='pip', pip_value_per_lot=11.5, tick=0.0001),   # 10 CHF ~ $11.5
    'EURGBP': dict(pip=0.0001, unit='pip', pip_value_per_lot=12.8, tick=0.0001),   # 10 GBP ~ $12.8
    'AUDCAD': dict(pip=0.0001, unit='pip', pip_value_per_lot=7.3, tick=0.0001),    # 10 CAD ~ $7.3
    'GBPCAD': dict(pip=0.0001, unit='pip', pip_value_per_lot=7.3, tick=0.0001),
    'NZDCAD': dict(pip=0.0001, unit='pip', pip_value_per_lot=7.3, tick=0.0001),
    'EURAUD': dict(pip=0.0001, unit='pip', pip_value_per_lot=6.6, tick=0.0001),    # 10 AUD ~ $6.6
}
for s, v in EXTRA_SPECS.items():
    E.SPECS.setdefault(s, v)
    E.MAX_LEVERAGE.setdefault(s, 30.0)
    E.CONTRACT_UNITS.setdefault(s, 100000.0)
SPECS = E.SPECS

# ----------------------------------------------------------------------------------------------------------------------
# Server time (NY + 7h)
# ----------------------------------------------------------------------------------------------------------------------
H = np.timedelta64(1, 'h')


def _nth_sunday(year, month, n):
    d = _dt.date(year, month, 1)
    first = d + _dt.timedelta(days=(6 - d.weekday()) % 7)
    return first + _dt.timedelta(days=7 * (n - 1))


def us_dst_bounds_utc(year):
    """UTC instants at which US DST starts (2nd Sunday March 02:00 EST = 07:00 UTC) and ends (1st Sunday Nov 02:00 EDT
    = 06:00 UTC)."""
    s = np.datetime64(f'{_nth_sunday(year, 3, 2).isoformat()}T07:00:00', 'ns')
    e = np.datetime64(f'{_nth_sunday(year, 11, 1).isoformat()}T06:00:00', 'ns')
    return s, e


def utc_offset_hours(utc):
    """Server-time offset (2 or 3 hours) for each UTC instant."""
    utc = np.asarray(utc).astype('datetime64[ns]')
    years = utc.astype('datetime64[Y]').astype(int) + 1970
    off = np.full(len(utc), 2, dtype=np.int64)
    for y in np.unique(years):
        s, e = us_dst_bounds_utc(int(y))
        off[(utc >= s) & (utc < e)] = 3
    return off


def utc_to_server(utc):
    utc = np.asarray(utc).astype('datetime64[ns]')
    return utc + utc_offset_hours(utc) * H


def server_to_utc(srv):
    srv = np.asarray(srv).astype('datetime64[ns]')
    guess = srv - 2 * H
    off = utc_offset_hours(guess)
    utc = srv - off * H
    off2 = utc_offset_hours(utc)          # settle the hour around the transitions (weekends; no trades there)
    return srv - off2 * H


def server_minute_of_day(srv):
    srv = np.asarray(srv).astype('datetime64[ns]')
    return ((srv - srv.astype('datetime64[D]').astype('datetime64[ns]')) // np.timedelta64(1, 'm')).astype(np.int64)


def server_dow(srv):
    """0=Monday ... 6=Sunday of the server-time date."""
    d = np.asarray(srv).astype('datetime64[D]').astype(np.int64)
    return (d + 3) % 7      # 1970-01-01 was a Thursday


# ----------------------------------------------------------------------------------------------------------------------
# Server-day daily bars and day index tables
# ----------------------------------------------------------------------------------------------------------------------
class ServerDays:
    """Per-server-day table: UTC M1 indices for arbitrary server clock times, D1 OHLC, ATR(14), SMA(50)."""

    def __init__(self, data: Data, start='2024-01-01', min_bars=600):
        self.data = data
        srv = utc_to_server(data.ts)
        self.srv = srv
        day = srv.astype('datetime64[D]')
        self.m1_day = day
        df = pd.DataFrame({'day': day, 'o': data.o, 'h': data.h, 'l': data.l, 'c': data.c})
        g = df.groupby('day', sort=True)
        d1 = g.agg(o=('o', 'first'), h=('h', 'max'), l=('l', 'min'), c=('c', 'last'), bars=('c', 'size'))
        d1.index = pd.DatetimeIndex(d1.index)
        d1['dow'] = d1.index.dayofweek
        pc = d1['c'].shift(1)
        tr = pd.concat([d1['h'] - d1['l'], (d1['h'] - pc).abs(), (d1['l'] - pc).abs()], axis=1).max(axis=1)
        d1['atr14_prev'] = tr.rolling(14).mean().shift(1)     # ATR of the 14 completed days before this day
        d1['sma50_prev'] = d1['c'].rolling(50).mean().shift(1)
        d1['close_prev'] = pc
        d1['ret_pct'] = (d1['c'] / pc - 1) * 100
        self.d1 = d1
        ok = (d1['dow'] < 5) & (d1.index >= pd.Timestamp(start)) & (d1['bars'] >= min_bars)
        self.days = d1.index[ok]      # server dates used for trading

    def idx(self, clock, days=None, day_offset=0):
        """M1 index of the first bar at/after <server date + clock> (clock 'HH:MM'); day_offset shifts the date."""
        days = self.days if days is None else days
        srv = (pd.DatetimeIndex(days) + pd.Timedelta(days=day_offset) + pd.Timedelta(clock + ':00')).values
        utc = server_to_utc(srv.astype('datetime64[ns]'))
        return np.searchsorted(self.data.ts, utc, side='left')

    def next_clock_idx(self, m1_idx, clock):
        """For each M1 index: index of the first bar at/after the next occurrence of <clock> server time (strictly
        after the bar's own server time)."""
        s = self.srv[np.minimum(m1_idx, self.data.n - 1)]
        day = s.astype('datetime64[D]').astype('datetime64[ns]')
        target = day + pd.Timedelta(clock + ':00').to_timedelta64()
        target = np.where(target <= s, target + np.timedelta64(1, 'D'), target)
        utc = server_to_utc(target.astype('datetime64[ns]'))
        return np.searchsorted(self.data.ts, utc, side='left')


# ----------------------------------------------------------------------------------------------------------------------
# Simulator with break-even stop
# ----------------------------------------------------------------------------------------------------------------------
@numba.njit(cache=True)
def _simulate_be(o, h, l, c, entry_idx, entry_px, direction, sl, tp, be_trig, time_exit_idx, n, eps):
    """Like bt_engine._simulate, plus an optional break-even rule: when the M1 high/low touches be_trig the stop moves
    to the entry price. Conservative conventions: SL checked before TP; once BE is active the BE stop is checked
    before TP (both touched in one bar = BE exit); a bar that touches be_trig and then returns to the entry price in
    the same bar (bar after the entry bar) counts as a BE exit. On the entry bar itself the low (for a long) is
    necessarily below the stop-order fill, so the 'returned to entry' test is not applied there.
    reason: 0=SL, 1=TP, 2=time, 3=end of data, 4=break-even."""
    m = len(entry_idx)
    taken = np.zeros(m, dtype=np.int8)
    exit_idx = np.full(m, -1, dtype=np.int64)
    exit_px = np.full(m, np.nan)
    reason = np.full(m, -1, dtype=np.int8)
    be_hit = np.zeros(m, dtype=np.int8)
    mfe = np.zeros(m)
    mae = np.zeros(m)
    last_exit = -1
    for t in range(m):
        i = entry_idx[t]
        if i >= n or i <= last_exit:
            continue
        d = direction[t]
        e = entry_px[t]
        s = sl[t]
        p = tp[t]
        b = be_trig[t]
        has_tp = not np.isnan(p)
        has_be = not np.isnan(b)
        tx = time_exit_idx[t]
        taken[t] = 1
        be_on = False
        j = i
        done = False
        fav = 0.0
        adv = 0.0
        while j < n:
            if j >= tx and j > i:
                exit_idx[t] = j; exit_px[t] = o[j]; reason[t] = 2; done = True; break
            if d == 1:
                fv = h[j] - e; av = e - l[j]
            else:
                fv = e - l[j]; av = h[j] - e
            if fv > fav:
                fav = fv
            if av > adv:
                adv = av
            if d == 1:
                if be_on:
                    if j > i and o[j] <= e + eps:
                        exit_idx[t] = j; exit_px[t] = o[j]; reason[t] = 4; done = True; break
                    if l[j] <= e + eps:
                        exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
                    if has_tp and h[j] >= p - eps:
                        exit_idx[t] = j; exit_px[t] = max(p, o[j]) if j > i else p; reason[t] = 1; done = True; break
                else:
                    if l[j] <= s + eps:
                        exit_idx[t] = j; exit_px[t] = min(s, o[j]) if j > i else s; reason[t] = 0; done = True; break
                    if has_tp and h[j] >= p - eps:
                        if has_be and j > i and l[j] <= e + eps:
                            be_hit[t] = 1
                            exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
                        exit_idx[t] = j; exit_px[t] = max(p, o[j]) if j > i else p; reason[t] = 1; done = True; break
                    if has_be and h[j] >= b - eps:
                        be_on = True; be_hit[t] = 1
                        if j > i and l[j] <= e + eps:
                            exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
            else:
                if be_on:
                    if j > i and o[j] >= e - eps:
                        exit_idx[t] = j; exit_px[t] = o[j]; reason[t] = 4; done = True; break
                    if h[j] >= e - eps:
                        exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
                    if has_tp and l[j] <= p + eps:
                        exit_idx[t] = j; exit_px[t] = min(p, o[j]) if j > i else p; reason[t] = 1; done = True; break
                else:
                    if h[j] >= s - eps:
                        exit_idx[t] = j; exit_px[t] = max(s, o[j]) if j > i else s; reason[t] = 0; done = True; break
                    if has_tp and l[j] <= p + eps:
                        if has_be and j > i and h[j] >= e - eps:
                            be_hit[t] = 1
                            exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
                        exit_idx[t] = j; exit_px[t] = min(p, o[j]) if j > i else p; reason[t] = 1; done = True; break
                    if has_be and l[j] <= b + eps:
                        be_on = True; be_hit[t] = 1
                        if j > i and h[j] >= e - eps:
                            exit_idx[t] = j; exit_px[t] = e; reason[t] = 4; done = True; break
            j += 1
        if not done:
            exit_idx[t] = n - 1; exit_px[t] = c[n - 1]; reason[t] = 3
        last_exit = exit_idx[t]
        mfe[t] = fav
        mae[t] = adv
    return taken, exit_idx, exit_px, reason, be_hit, mfe, mae


@numba.njit(cache=True)
def first_trigger(h, l, o, start, end, buy_lvl, sell_lvl, eps=EPS):
    """Scan M1 bars [start, end) for the first bar that touches buy_lvl (high >= buy) or sell_lvl (low <= sell); used both
    for stop orders (buy at buy_lvl) and, with the direction flipped by the caller, for limit orders. Returns
    (idx, direction, fill_px); direction 0 if nothing triggered. Fill at the level, or at the bar open if the bar opens
    beyond it. If both are touched in the same bar, the side closer to the bar's open is assumed to have triggered first.
    Same logic as bt_engine.first_trigger plus the tolerance eps."""
    for j in range(start, end):
        hb = h[j] >= buy_lvl - eps
        ls = l[j] <= sell_lvl + eps
        if hb and ls:
            if (buy_lvl - o[j]) <= (o[j] - sell_lvl):
                return j, 1, max(buy_lvl, o[j])
            else:
                return j, -1, min(sell_lvl, o[j])
        if hb:
            return j, 1, max(buy_lvl, o[j])
        if ls:
            return j, -1, min(sell_lvl, o[j])
    return -1, 0, np.nan


REASONS = {0: 'SL', 1: 'TP', 2: 'time', 3: 'end', 4: 'BE'}


def run_trades_be(data: Data, entry_idx, entry_px, direction, sl, tp, be_trig=None, time_exit_idx=None,
                  start_time='2024-01-01', extra=None):
    """Simulate candidate trades (one position at a time) and return a gross trades DataFrame.
    entry_px nan = market fill at the bar open. extra: dict of per-candidate arrays to carry into the output."""
    entry_idx = np.asarray(entry_idx, dtype=np.int64)
    m = len(entry_idx)
    order = np.argsort(entry_idx, kind='stable')
    ep = np.asarray(entry_px, dtype=np.float64)[order]
    entry_idx = entry_idx[order]
    direction = np.asarray(direction, dtype=np.int64)[order]
    sl = np.asarray(sl, dtype=np.float64)[order]
    tp = np.asarray(tp, dtype=np.float64)[order]
    be = (np.full(m, np.nan) if be_trig is None else np.asarray(be_trig, dtype=np.float64))[order]
    tx = (np.full(m, data.n + 1, dtype=np.int64) if time_exit_idx is None else np.asarray(time_exit_idx, dtype=np.int64))[order]
    extra = {k: np.asarray(v)[order] for k, v in (extra or {}).items()}
    valid = entry_idx < data.n
    nanmask = np.isnan(ep) & valid
    ep[nanmask] = data.o[entry_idx[nanmask]]
    # tradeable geometry: stop adverse, target favourable, stop at least one tick away
    tick = data.spec['tick']
    ok = valid & (direction * (ep - sl) >= tick - 1e-12) & (np.isnan(tp) | (direction * (tp - ep) > 0))
    if start_time is not None:
        ok &= data.ts[np.minimum(entry_idx, data.n - 1)] >= np.datetime64(start_time, 'ns')
    entry_idx, ep, direction, sl, tp, be, tx = (a[ok] for a in (entry_idx, ep, direction, sl, tp, be, tx))
    extra = {k: v[ok] for k, v in extra.items()}
    taken, exit_idx, exit_px, reason, be_hit, mfe, mae = _simulate_be(
        data.o, data.h, data.l, data.c, entry_idx, ep, direction, sl, tp, be, tx, data.n, EPS)
    k = taken == 1
    tr = pd.DataFrame({
        'entry_time': data.ts[entry_idx[k]], 'exit_time': data.ts[exit_idx[k]], 'entry_idx': entry_idx[k],
        'exit_idx': exit_idx[k], 'dir': direction[k], 'entry_px': ep[k], 'exit_px': exit_px[k], 'sl': sl[k],
        'tp': tp[k], 'be_trig': be[k], 'reason': [REASONS[r] for r in reason[k]], 'bars': exit_idx[k] - entry_idx[k],
        'be_hit': be_hit[k].astype(bool), 'mfe': mfe[k], 'mae': mae[k],
    })
    for kk, v in extra.items():
        tr[kk] = v[k]
    tr['gross'] = tr['dir'] * (tr['exit_px'] - tr['entry_px'])
    tr['risk'] = (tr['entry_px'] - tr['sl']).abs()
    return tr


# ----------------------------------------------------------------------------------------------------------------------
# Costs (scalar or per-trade array) and metrics
# ----------------------------------------------------------------------------------------------------------------------
def apply_costs(tr, symbol, cost_pips):
    """cost_pips: scalar or array (per trade) of round-trip cost in pips/points."""
    pip = SPECS[symbol]['pip']
    t = tr.copy()
    t['gross_pips'] = t['gross'] / pip
    t['cost_pips'] = np.broadcast_to(np.asarray(cost_pips, dtype=np.float64), (len(t),)).copy()
    t['net_pips'] = t['gross_pips'] - t['cost_pips']
    t['risk_pips'] = t['risk'] / pip
    t['net_R'] = t['net_pips'] / t['risk_pips']
    t['gross_R'] = t['gross_pips'] / t['risk_pips']
    return t


def metrics(t, symbol, all_days=None, with_ci=True, ci_R=False, start_equity=10000.0, n_boot=2000):
    """Summary metrics of a costed trade list (see bt_engine.metrics), plus long/short split, BE share and the
    1%-risk compounding curve from start_equity."""
    n = len(t)
    out = {'trades': n}
    if n == 0:
        return out
    net = t['net_pips'].values
    netR = t['net_R'].values
    wins = net[net > 0]
    losses = net[net <= 0]
    out['win_rate'] = len(wins) / n * 100
    out['exp_pips'] = net.mean()
    out['exp_R'] = netR.mean()
    out['gross_exp_pips'] = t['gross_pips'].mean()
    out['avg_win_pips'] = wins.mean() if len(wins) else 0.0
    out['avg_loss_pips'] = losses.mean() if len(losses) else 0.0
    gp, gl = wins.sum(), -losses.sum()
    out['profit_factor'] = gp / gl if gl > 0 else np.inf
    out['net_pips'] = net.sum()
    out['max_dd_pips'] = max_drawdown(np.concatenate([[0.0], np.cumsum(net)]))
    eq, capped = E.equity_1pct(net, t['risk_pips'].values, t['entry_px'].values, symbol, start=start_equity)
    out['start_equity'] = start_equity
    out['final_equity'] = eq[-1]
    out['return_pct_1pct_risk'] = (eq[-1] / start_equity - 1) * 100
    out['max_dd_pct_1pct_risk'] = max_drawdown_pct(np.concatenate([[start_equity], eq]))
    out['pct_trades_leverage_capped'] = capped / n * 100
    out['avg_risk_pips'] = t['risk_pips'].mean()
    out['cost_pct_of_risk'] = t['cost_pips'].mean() / t['risk_pips'].mean() * 100
    out['avg_cost_pips'] = t['cost_pips'].mean()
    out['avg_bars'] = t['bars'].mean()
    out['streak'] = longest_losing_streak(net)
    d = pd.Series(net, index=pd.to_datetime(t['exit_time']).dt.normalize()).groupby(level=0).sum()
    if all_days is not None:
        d = d.reindex(pd.DatetimeIndex(all_days), fill_value=0.0)
    out['sharpe'] = float(d.mean() / d.std() * np.sqrt(252)) if d.std() > 0 else np.nan
    if with_ci:
        out['ci_lo'], out['ci_hi'] = bootstrap_ci(net, n_boot=n_boot)
        if ci_R:
            out['ciR_lo'], out['ciR_hi'] = bootstrap_ci(netR, n_boot=n_boot, seed=1)
    for r in ('SL', 'TP', 'time', 'BE'):
        out[f'pct_{r}'] = (t['reason'] == r).mean() * 100
    lg, sh = t[t['dir'] == 1], t[t['dir'] == -1]
    out['n_long'] = len(lg); out['n_short'] = len(sh)
    out['exp_long'] = lg['net_pips'].mean() if len(lg) else np.nan
    out['exp_short'] = sh['net_pips'].mean() if len(sh) else np.nan
    out['net_long'] = lg['net_pips'].sum(); out['net_short'] = sh['net_pips'].sum()
    out['expR_long'] = lg['net_R'].mean() if len(lg) else np.nan
    out['expR_short'] = sh['net_R'].mean() if len(sh) else np.nan
    return out


def by_year_rows(t, symbol, base, days):
    rows = []
    et = pd.to_datetime(t['entry_time'])
    for yr, g in t.groupby(et.dt.year):
        yd = days[pd.DatetimeIndex(days).year == yr]
        rows.append({**base, 'year': int(yr), **metrics(g, symbol, all_days=yd, with_ci=True, n_boot=1000)})
    return rows


def randomize_direction(data: Data, tr, seed, time_exit_idx=None, be_mult=None, tp_mult=None):
    """Random-direction benchmark: same entry bars and fill prices, same stop distance, same target distance (or
    tp_mult x stop), same break-even multiple (be_mult x stop) and the same time exit, coin-flip direction."""
    rng = np.random.default_rng(seed)
    d = rng.choice(np.array([-1, 1]), size=len(tr))
    ep = tr['entry_px'].values
    R = tr['risk'].values
    sl = ep - d * R
    if tp_mult is None:
        tpd = (tr['tp'].values - ep) * tr['dir'].values
        tp = np.where(np.isnan(tpd), np.nan, ep + d * tpd)
    else:
        tp = ep + d * tp_mult * R
    be = None if be_mult is None else ep + d * be_mult * R
    tx = tr['time_exit_idx'].values if time_exit_idx is None else time_exit_idx
    return run_trades_be(data, tr['entry_idx'].values, ep, d, sl, tp, be_trig=be, time_exit_idx=tx)


def pctl(x, q):
    return float(np.percentile(np.asarray(x, dtype=float), q)) if len(x) else np.nan
