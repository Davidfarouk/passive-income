"""Core backtest engine: data loading, resampling, indicators, trade simulator, cost model, metrics.

Conventions
-----------
* Input CSV: datetime,open,high,low,close,volume  (UTC, bar OPEN time, M1, BID quotes).
* Signals are computed on CLOSED bars; entries happen at the OPEN of the next bar (market orders) or at the
  stop level intrabar (stop orders). Stops/targets are checked intrabar on M1 high/low from the entry bar onward.
  If both SL and TP are touched in the same M1 bar, the trade is counted as a loss (SL).
  If a bar opens through the SL (gap), the fill is at the open (worse than SL).
* One position at a time per strategy variant.
* Costs are applied after the fact per round trip (spread + commission + slippage) in price units.
"""
import numpy as np
import pandas as pd
import numba

# ----------------------------------------------------------------------------------------------------------------------
# Symbol specs and cost cases
# ----------------------------------------------------------------------------------------------------------------------
SPECS = {
    # pip_size: the unit in which results are reported (EURUSD pip = 0.0001; XAUUSD point = 0.01 = 1 cent)
    'EURUSD': dict(pip=0.0001, unit='pip', pip_value_per_lot=10.0, tick=0.0001),
    'XAUUSD': dict(pip=0.01, unit='point', pip_value_per_lot=1.0, tick=0.1),  # 1 lot = 100 oz; 0.01 move = $1
}
# 'tick' = price resolution of the Forexite data (4-digit EURUSD, 1-decimal gold); also used as the minimum stop distance
# round-trip cost in pips/points: cheap / base / expensive
COST_CASES = {
    'EURUSD': {
        'cheap':     0.8,   # 0.1 raw spread + 0.7 commission ($7/lot RT), no slippage
        'base':      1.2,   # + 0.2 slippage per side
        'expensive': 2.1,   # 1.5 pip spread standard account, 0 commission, 0.3 slippage per side
    },
    'XAUUSD': {
        'cheap':     25.0,  # 10 pt raw spread + 7 pt commission + 4 pt slippage per side (optimistic ECN)
        'base':      42.0,  # 15 pt raw spread + 7 pt commission + 10 pt slippage per side
        'expensive': 50.0,  # 30 pt spread standard account, 0 commission, 10 pt slippage per side
    },
}
SESSIONS = {'Asia': (22, 7), 'London': (7, 13), 'NY': (13, 22)}  # UTC hour ranges [start, end)


def session_of(hours):
    h = np.asarray(hours)
    out = np.where((h >= 7) & (h < 13), 'London', np.where((h >= 13) & (h < 22), 'NY', 'Asia'))
    return out


# ----------------------------------------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------------------------------------
class Data:
    """Holds M1 arrays plus a resampled timeframe (M1 or M5) with indicator helpers."""

    def __init__(self, path, symbol):
        df = pd.read_csv(path, parse_dates=['datetime'])
        df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
        self.symbol = symbol
        self.spec = SPECS[symbol]
        self.m1 = df
        self.ts = df['datetime'].values.astype('datetime64[ns]')
        self.ts_i8 = self.ts.astype('int64')
        self.o = df['open'].values.astype(np.float64)
        self.h = df['high'].values.astype(np.float64)
        self.l = df['low'].values.astype(np.float64)
        self.c = df['close'].values.astype(np.float64)
        self.n = len(df)

    def resample(self, tf):
        """Return OHLC DataFrame on timeframe tf ('M1' or 'M5'), plus array m1_next: M1 index of the first bar
        at/after each tf bar's close (i.e. where a market order placed on that bar's close would be filled)."""
        if tf == 'M1':
            bars = self.m1[['datetime', 'open', 'high', 'low', 'close']].copy()
            bars['m1_next'] = np.arange(1, self.n + 1)  # fill at next M1 bar open
            bars['m1_start'] = np.arange(self.n)
        else:
            minutes = int(tf[1:])
            g = self.m1.set_index('datetime')[['open', 'high', 'low', 'close']]
            r = g.resample(f'{minutes}min', label='left', closed='left').agg(
                {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            bars = r.reset_index()
            close_time = (bars['datetime'] + pd.Timedelta(minutes=minutes)).values.astype('datetime64[ns]')
            bars['m1_next'] = np.searchsorted(self.ts, close_time, side='left')
            bars['m1_start'] = np.searchsorted(self.ts, bars['datetime'].values.astype('datetime64[ns]'), side='left')
        return bars

    def idx_at_or_after(self, times):
        """M1 index of first bar with ts >= each time (times: datetime64 array)."""
        return np.searchsorted(self.ts, np.asarray(times).astype('datetime64[ns]'), side='left')


# ----------------------------------------------------------------------------------------------------------------------
# Indicators (MT5-style definitions)
# ----------------------------------------------------------------------------------------------------------------------
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def sma(s, n):
    return s.rolling(n).mean()


def atr(df, n=14):
    """MT5 iATR: simple moving average of True Range."""
    pc = df['close'].shift(1)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - pc).abs(), (df['low'] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(s, n=14):
    """Wilder RSI (as MT5 iRSI)."""
    d = s.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    au = up.ewm(alpha=1.0 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(ad != 0, 100.0)
    return out


def bollinger(s, n=20, k=2.0):
    m = s.rolling(n).mean()
    sd = s.rolling(n).std(ddof=0)
    return m, m + k * sd, m - k * sd


def stochastic(df, k=5, slow=3, d=3):
    ll = df['low'].rolling(k).min()
    hh = df['high'].rolling(k).max()
    raw = 100 * (df['close'] - ll) / (hh - ll).replace(0, np.nan)
    K = raw.rolling(slow).mean()
    D = K.rolling(d).mean()
    return K, D


# ----------------------------------------------------------------------------------------------------------------------
# Simulator
# ----------------------------------------------------------------------------------------------------------------------
@numba.njit(cache=True)
def _simulate(o, h, l, c, entry_idx, entry_px, direction, sl, tp, time_exit_idx, n):
    """Walk each candidate trade forward on M1 bars.
    entry_idx: M1 bar index at which the position is opened (at entry_px: open of bar for market orders, or stop level).
    sl/tp: price levels (tp may be nan for 'no target'); time_exit_idx: M1 index at whose OPEN the trade is closed
    if still open (use n or larger for 'none').
    Returns arrays (taken flag, exit_idx, exit_px, reason) where reason: 0=SL, 1=TP, 2=time/signal exit, 3=end of data.
    Trades overlapping an open position are skipped (taken=0)."""
    m = len(entry_idx)
    taken = np.zeros(m, dtype=np.int8)
    exit_idx = np.full(m, -1, dtype=np.int64)
    exit_px = np.full(m, np.nan)
    reason = np.full(m, -1, dtype=np.int8)
    last_exit = -1
    for t in range(m):
        i = entry_idx[t]
        if i >= n or i <= last_exit:
            continue
        d = direction[t]
        s = sl[t]
        p = tp[t]
        has_tp = not np.isnan(p)
        tx = time_exit_idx[t]
        taken[t] = 1
        j = i
        done = False
        # entry bar: position opened at entry_px; the bar's remaining range may hit SL/TP (conservative: SL first)
        while j < n:
            if j >= tx and j > i:
                exit_idx[t] = j; exit_px[t] = o[j]; reason[t] = 2; done = True; break
            if j == i:
                # on the entry bar the open is already known; only check adverse/favourable extremes
                if d == 1:
                    if l[j] <= s:
                        exit_idx[t] = j; exit_px[t] = s; reason[t] = 0; done = True; break
                    if has_tp and h[j] >= p:
                        exit_idx[t] = j; exit_px[t] = p; reason[t] = 1; done = True; break
                else:
                    if h[j] >= s:
                        exit_idx[t] = j; exit_px[t] = s; reason[t] = 0; done = True; break
                    if has_tp and l[j] <= p:
                        exit_idx[t] = j; exit_px[t] = p; reason[t] = 1; done = True; break
            else:
                if d == 1:
                    if l[j] <= s:
                        exit_idx[t] = j; exit_px[t] = min(s, o[j]); reason[t] = 0; done = True; break
                    if has_tp and h[j] >= p:
                        exit_idx[t] = j; exit_px[t] = max(p, o[j]); reason[t] = 1; done = True; break
                else:
                    if h[j] >= s:
                        exit_idx[t] = j; exit_px[t] = max(s, o[j]); reason[t] = 0; done = True; break
                    if has_tp and l[j] <= p:
                        exit_idx[t] = j; exit_px[t] = min(p, o[j]); reason[t] = 1; done = True; break
            j += 1
        if not done:
            exit_idx[t] = n - 1; exit_px[t] = c[n - 1]; reason[t] = 3
        last_exit = exit_idx[t]
    return taken, exit_idx, exit_px, reason


@numba.njit(cache=True)
def first_trigger(h, l, o, start, end, buy_lvl, sell_lvl):
    """Scan M1 bars [start, end) for the first bar that touches buy_lvl (high >= buy) or sell_lvl (low <= sell).
    Returns (idx, direction, fill_px); direction 0 if nothing triggered. If both touched in the same bar, the side
    closer to the bar's open is assumed to have triggered first."""
    for j in range(start, end):
        hb = h[j] >= buy_lvl
        ls = l[j] <= sell_lvl
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


REASONS = {0: 'SL', 1: 'TP', 2: 'time', 3: 'end'}


def run_trades(data: Data, entry_idx, entry_px, direction, sl, tp, time_exit_idx, start_time=None, flags=None):
    """Simulate and return a trades DataFrame (gross results in price units, no costs)."""
    entry_idx = np.asarray(entry_idx, dtype=np.int64)
    order = np.argsort(entry_idx, kind='stable')
    entry_idx = entry_idx[order]
    entry_px = np.asarray(entry_px, dtype=np.float64)[order]
    direction = np.asarray(direction, dtype=np.int64)[order]
    sl = np.asarray(sl, dtype=np.float64)[order]
    tp = np.asarray(tp, dtype=np.float64)[order]
    time_exit_idx = np.asarray(time_exit_idx, dtype=np.int64)[order]
    flags = np.zeros(len(entry_idx), dtype=bool) if flags is None else np.asarray(flags, dtype=bool)[order]
    # fill market entries at the bar open when entry_px is nan
    valid = entry_idx < data.n
    ep = entry_px.copy()
    nanmask = np.isnan(ep) & valid
    ep[nanmask] = data.o[entry_idx[nanmask]]
    if start_time is not None:
        st = np.datetime64(start_time, 'ns')
        keep = valid & (data.ts[np.minimum(entry_idx, data.n - 1)] >= st)
    else:
        keep = valid
    entry_idx, ep, direction, sl, tp, time_exit_idx, flags = (entry_idx[keep], ep[keep], direction[keep], sl[keep],
                                                               tp[keep], time_exit_idx[keep], flags[keep])
    taken, exit_idx, exit_px, reason = _simulate(data.o, data.h, data.l, data.c, entry_idx, ep, direction, sl, tp,
                                                 time_exit_idx, data.n)
    k = taken == 1
    tr = pd.DataFrame({
        'entry_time': data.ts[entry_idx[k]], 'exit_time': data.ts[exit_idx[k]],
        'dir': direction[k], 'entry_px': ep[k], 'exit_px': exit_px[k], 'sl': sl[k], 'tp': tp[k],
        'reason': [REASONS[r] for r in reason[k]], 'bars': exit_idx[k] - entry_idx[k], 'sl_floored': flags[k],
    })
    tr['gross'] = tr['dir'] * (tr['exit_px'] - tr['entry_px'])
    tr['risk'] = (tr['entry_px'] - tr['sl']).abs()
    return tr


# ----------------------------------------------------------------------------------------------------------------------
# Costs and metrics
# ----------------------------------------------------------------------------------------------------------------------
def apply_costs(tr, symbol, cost_pips):
    pip = SPECS[symbol]['pip']
    t = tr.copy()
    t['gross_pips'] = t['gross'] / pip
    t['cost_pips'] = cost_pips
    t['net_pips'] = t['gross_pips'] - cost_pips
    t['risk_pips'] = t['risk'] / pip
    t['net_R'] = t['net_pips'] / t['risk_pips']
    t['gross_R'] = t['gross_pips'] / t['risk_pips']
    return t


@numba.njit(parallel=True, cache=True)
def _boot_means(x, n_boot, seed):
    # numba keeps an independent random state per thread; seeding inside prange makes the result reproducible
    n = len(x)
    out = np.empty(n_boot)
    for b in numba.prange(n_boot):
        np.random.seed(seed * 1000003 + b)
        s = 0.0
        for i in range(n):
            s += x[np.random.randint(0, n)]
        out[b] = s / n
    return out


def bootstrap_ci(x, n_boot=2000, seed=0):
    """95% percentile bootstrap CI of the mean (resampling trades with replacement)."""
    x = np.ascontiguousarray(np.asarray(x, dtype=np.float64))
    if len(x) < 2:
        return (np.nan, np.nan)
    means = _boot_means(x, n_boot, seed)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def longest_losing_streak(net):
    best = cur = 0
    for v in net:
        if v < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


MAX_LEVERAGE = {'EURUSD': 30.0, 'XAUUSD': 20.0}   # ESMA/FCA retail caps; used to stop absurd sizing on micro-stops
CONTRACT_UNITS = {'EURUSD': 100000.0, 'XAUUSD': 100.0}


def equity_1pct(net_pips, risk_pips, entry_px, symbol, risk_frac=0.01, start=10000.0):
    """Compounding equity curve risking risk_frac of current equity per trade, position size capped by max leverage.
    net_pips/risk_pips in pips (points for gold); entry_px used for the notional/leverage cap."""
    spec = SPECS[symbol]
    pv = spec['pip_value_per_lot']
    units = CONTRACT_UNITS[symbol]
    lev = MAX_LEVERAGE[symbol]
    net_pips = np.asarray(net_pips, dtype=np.float64)
    risk_pips = np.asarray(risk_pips, dtype=np.float64)
    entry_px = np.asarray(entry_px, dtype=np.float64)
    eq = np.empty(len(net_pips))
    e = start
    capped = 0
    for i in range(len(net_pips)):
        lots_risk = risk_frac * e / (risk_pips[i] * pv) if risk_pips[i] > 0 else 0.0
        lots_cap = lev * e / (units * entry_px[i])
        lots = min(lots_risk, lots_cap)
        if lots_cap < lots_risk:
            capped += 1
        e = e + lots * net_pips[i] * pv
        if e <= 0:
            e = 0.0
            eq[i:] = 0.0
            break
        eq[i] = e
    return eq, capped


def max_drawdown(curve):
    curve = np.asarray(curve, dtype=np.float64)
    if len(curve) == 0:
        return 0.0
    peak = np.maximum.accumulate(curve)
    return float((peak - curve).max())


def max_drawdown_pct(curve):
    curve = np.asarray(curve, dtype=np.float64)
    if len(curve) == 0:
        return 0.0
    peak = np.maximum.accumulate(curve)
    return float(((peak - curve) / peak).max() * 100)


def metrics(t, symbol, all_days=None, with_ci=True, ci_R=False):
    """Compute summary metrics from a costed trades DataFrame."""
    n = len(t)
    out = {'trades': n}
    if n == 0:
        return out
    net = t['net_pips'].values
    netR = t['net_R'].values
    wins = net[net > 0]
    losses = net[net <= 0]
    out['win_rate'] = len(wins) / n * 100
    out['avg_win_pips'] = wins.mean() if len(wins) else 0.0
    out['avg_loss_pips'] = losses.mean() if len(losses) else 0.0
    out['exp_pips'] = net.mean()
    out['exp_R'] = netR.mean()
    out['gross_exp_pips'] = t['gross_pips'].mean()
    gp, gl = wins.sum(), -losses.sum()
    out['profit_factor'] = gp / gl if gl > 0 else np.inf
    out['net_pips'] = net.sum()
    out['max_dd_pips'] = max_drawdown(np.concatenate([[0.0], np.cumsum(net)]))
    eq, capped = equity_1pct(net, t['risk_pips'].values, t['entry_px'].values, symbol)
    out['return_pct_1pct_risk'] = (eq[-1] / 10000.0 - 1) * 100
    out['max_dd_pct_1pct_risk'] = max_drawdown_pct(np.concatenate([[10000.0], eq]))
    out['pct_trades_leverage_capped'] = capped / n * 100
    out['avg_risk_pips'] = t['risk_pips'].mean()
    out['cost_pct_of_risk'] = t['cost_pips'].mean() / t['risk_pips'].mean() * 100
    out['avg_bars'] = t['bars'].mean()
    out['streak'] = longest_losing_streak(net)
    # daily P&L Sharpe (fixed 1 lot, pips), zero on days with no trades within the sample
    d = pd.Series(net, index=pd.to_datetime(t['exit_time']).dt.normalize()).groupby(level=0).sum()
    if all_days is not None:
        d = d.reindex(all_days, fill_value=0.0)
    out['sharpe'] = float(d.mean() / d.std() * np.sqrt(252)) if d.std() > 0 else np.nan
    if with_ci:
        out['ci_lo'], out['ci_hi'] = bootstrap_ci(net)
        if ci_R:
            out['ciR_lo'], out['ciR_hi'] = bootstrap_ci(netR, seed=1)
    out['pct_sl'] = (t['reason'] == 'SL').mean() * 100
    out['pct_tp'] = (t['reason'] == 'TP').mean() * 100
    out['pct_sl_floored'] = t['sl_floored'].mean() * 100 if 'sl_floored' in t else 0.0
    return out
