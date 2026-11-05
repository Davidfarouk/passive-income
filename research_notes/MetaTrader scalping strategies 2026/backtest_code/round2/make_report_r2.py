"""Turn the round-2 result CSVs into markdown tables. Usage: python3 -I make_report_r2.py <results_dir> <out_md>"""
import sys, os, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import apply_costs, bootstrap_ci

res, out_md = sys.argv[1], sys.argv[2]
L = []


def P(s=''):
    L.append(s)


def f(v, nd=1, plus=False, pct=False, comma=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return '-'
    if isinstance(v, (int, np.integer)) or (nd == 0 and comma):
        return f'{int(round(v)):,}' if comma else f'{v:+d}' if plus else str(int(v))
    s = f'{v:+,.{nd}f}' if plus else f'{v:,.{nd}f}'
    return s + ('%' if pct else '')


def ci(lo, hi, nd=0):
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return '-'
    mark = '*' if lo > 0 else ('(-)' if hi < 0 else '')
    return f'[{lo:+,.{nd}f}, {hi:+,.{nd}f}]{mark}'


def table(header, rows):
    P('| ' + ' | '.join(header) + ' |')
    P('|' + '---|' * len(header))
    for r in rows:
        P('| ' + ' | '.join(str(x) for x in r) + ' |')
    P()


# ======================================================================================================================
# T1
# ======================================================================================================================
m1 = pd.read_csv(os.path.join(res, 't1_master.csv'))
y1 = pd.read_csv(os.path.join(res, 't1_by_year.csv'))
s1 = pd.read_csv(os.path.join(res, 't1_splits.csv'))
r1 = pd.read_csv(os.path.join(res, 't1_random.csv'))
b1 = pd.read_csv(os.path.join(res, 't1_benchmarks.csv'))
g1 = pd.read_csv(os.path.join(res, 't1_sensitivity.csv'))
rs1 = pd.read_csv(os.path.join(res, 't1_range_stats.csv'))
st1 = json.load(open(os.path.join(res, 't1_stats.json')))
BASE = 'base_buf20_tp2.5_be1.5_w03-08_x21'
COSTLAB = {'gross': 'gross (0)', 'spread15': 'spread-only 15 pt', 'base42': 'base 42 pt', 'exp50': 'expensive 50 pt'}

P('<!-- T1 tables -->')
P('### T1-A. Base rule (buffer 20 pt, TP 2.5R, BE at 1.5R, range 03:00-08:00, orders/flat 21:00 server) by cost case')
P()
rows = []
for cc in ('gross', 'spread15', 'base42', 'exp50'):
    r = m1[(m1.variant == BASE) & (m1.cost_case == cc)].iloc[0]
    rows.append([COSTLAB[cc], f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f(r.exp_pips, 0, True), f(r.exp_R, 2, True),
                 ci(r.ci_lo, r.ci_hi), ci(r.ciR_lo, r.ciR_hi, 2), f(r.net_pips, 0, True, comma=True), f(r.max_dd_pips, 0, comma=True),
                 f(r.return_pct_1pct_risk, 1, True), f(r.max_dd_pct_1pct_risk, 1), f(r.pnl_usd_5k, 0, True, comma=True),
                 f(r.pnl_usd_10k, 0, True, comma=True), f(r.sharpe, 2), f(r.streak, 0), f(r.avg_risk_pips, 0),
                 f(r.cost_pct_of_risk, 1), f'{r.pct_SL:.0f}/{r.pct_TP:.0f}/{r.pct_BE:.0f}/{r.pct_time:.0f}',
                 f'{r.n_long:.0f} / {r.exp_long:+.0f}', f'{r.n_short:.0f} / {r.exp_short:+.0f}'])
table(['Cost case', 'Trades', 'Win %', 'PF', 'Exp (pt)', 'Exp (R)', '95% CI exp (pt)', '95% CI exp (R)', 'Net (pt/lot)', 'MaxDD (pt)',
       'Return % (1% risk)', 'MaxDD % (1% risk)', 'P&L $5k start', 'P&L $10k start', 'Sharpe', 'Max loss streak', 'Avg stop (pt)',
       'Cost % of stop', 'Exit % SL/TP/BE/time', 'Longs n / exp', 'Shorts n / exp'], rows)

P('### T1-B. Base rule by calendar year (base costs 42 pt; gross in brackets)')
P()
rows = []
for yr in (2024, 2025, 2026):
    r = y1[(y1.variant == BASE) & (y1.cost_case == 'base42') & (y1.year == yr)].iloc[0]
    g = y1[(y1.variant == BASE) & (y1.cost_case == 'gross') & (y1.year == yr)].iloc[0]
    rows.append([yr, f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f'{r.exp_pips:+.0f} ({g.exp_pips:+.0f})', f(r.exp_R, 2, True),
                 ci(r.ci_lo, r.ci_hi), f(r.net_pips, 0, True, comma=True), f(r.return_pct_1pct_risk, 1, True), f(r.max_dd_pct_1pct_risk, 1),
                 f(r.sharpe, 2), f(r.streak, 0), f(r.avg_risk_pips, 0), f'{r.n_long:.0f} / {r.exp_long:+.0f}', f'{r.n_short:.0f} / {r.exp_short:+.0f}'])
r = m1[(m1.variant == BASE) & (m1.cost_case == 'base42')].iloc[0]
rows.append(['**overall**', f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f'{r.exp_pips:+.0f} ({m1[(m1.variant == BASE) & (m1.cost_case == "gross")].iloc[0].exp_pips:+.0f})',
             f(r.exp_R, 2, True), ci(r.ci_lo, r.ci_hi), f(r.net_pips, 0, True, comma=True), f(r.return_pct_1pct_risk, 1, True),
             f(r.max_dd_pct_1pct_risk, 1), f(r.sharpe, 2), f(r.streak, 0), f(r.avg_risk_pips, 0), f'{r.n_long:.0f} / {r.exp_long:+.0f}', f'{r.n_short:.0f} / {r.exp_short:+.0f}'])
table(['Year', 'Trades', 'Win %', 'PF', 'Exp pt net (gross)', 'Exp (R)', '95% CI exp (pt)', 'Net (pt/lot)', 'Return % (1% risk)', 'MaxDD %',
       'Sharpe', 'Streak', 'Avg stop (pt)', 'Longs n / exp', 'Shorts n / exp'], rows)

P('### T1-C. Rule variants (base costs 42 pt)')
P()
order = [BASE, 'buf0_tp2.5_be1.5_w03-08_x21', 'buf50_tp2.5_be1.5_w03-08_x21', 'buf20_tp1.5_be1.5_w03-08_x21', 'buf20_tp2.0_be1.5_w03-08_x21',
         'buf20_tp3.0_be1.5_w03-08_x21', 'buf20_tp1.5_beOFF_w03-08_x21', 'buf20_tp2.0_beOFF_w03-08_x21', 'buf20_tp2.5_beOFF_w03-08_x21',
         'buf20_tp3.0_beOFF_w03-08_x21', 'buf20_tp2.5_be1.5_w03-08_x12', 'buf20_tp2.5_be1.5_w03-08_x16', 'buf20_tp2.5_be1.5_w02-07_x21',
         'buf20_tp2.5_be1.5_w04-09_x21', 'buf20_tp2.5_be1.5_w03-08_x21_noRangeFilter', 'base_long_only', 'base_short_only', 'base_trend_only', 'base_counter_only']
LAB = {BASE: '**base** buf 20 / TP 2.5R / BE 1.5R / 03-08 / exp 21:00', 'buf0_tp2.5_be1.5_w03-08_x21': 'buffer 0', 'buf50_tp2.5_be1.5_w03-08_x21': 'buffer 50 pt',
       'buf20_tp1.5_be1.5_w03-08_x21': 'TP 1.5R', 'buf20_tp2.0_be1.5_w03-08_x21': 'TP 2.0R', 'buf20_tp3.0_be1.5_w03-08_x21': 'TP 3.0R',
       'buf20_tp1.5_beOFF_w03-08_x21': 'TP 1.5R, BE off', 'buf20_tp2.0_beOFF_w03-08_x21': 'TP 2.0R, BE off', 'buf20_tp2.5_beOFF_w03-08_x21': 'TP 2.5R, BE off',
       'buf20_tp3.0_beOFF_w03-08_x21': 'TP 3.0R, BE off', 'buf20_tp2.5_be1.5_w03-08_x12': 'orders expire 12:00', 'buf20_tp2.5_be1.5_w03-08_x16': 'orders expire 16:00',
       'buf20_tp2.5_be1.5_w02-07_x21': 'range 02:00-07:00', 'buf20_tp2.5_be1.5_w04-09_x21': 'range 04:00-09:00',
       'buf20_tp2.5_be1.5_w03-08_x21_noRangeFilter': 'no 0.30-1.60% range filter', 'base_long_only': 'buy stop only (long-only)',
       'base_short_only': 'sell stop only (short-only)', 'base_trend_only': 'only in direction of 50-day SMA', 'base_counter_only': 'only against 50-day SMA'}
rows = []
for v in order:
    r = m1[(m1.variant == v) & (m1.cost_case == 'base42')].iloc[0]
    g = m1[(m1.variant == v) & (m1.cost_case == 'gross')].iloc[0]
    yy = {yr: y1[(y1.variant == v) & (y1.cost_case == 'base42') & (y1.year == yr)].iloc[0].exp_pips for yr in (2024, 2025, 2026)}
    rows.append([LAB[v], f(r.eligible_days, 0), f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f'{r.exp_pips:+.0f} ({g.exp_pips:+.0f})', f(r.exp_R, 2, True),
                 ci(r.ci_lo, r.ci_hi), f'{yy[2024]:+.0f} / {yy[2025]:+.0f} / {yy[2026]:+.0f}', f(r.return_pct_1pct_risk, 0, True), f(r.max_dd_pct_1pct_risk, 1),
                 f(r.sharpe, 2), f'{r.pct_SL:.0f}/{r.pct_TP:.0f}/{r.pct_BE:.0f}/{r.pct_time:.0f}'])
table(['Variant', 'Eligible days', 'Trades', 'Win %', 'PF', 'Exp pt net (gross)', 'Exp (R)', '95% CI exp (pt)', 'Exp by year 24/25/26', 'Return %', 'MaxDD %', 'Sharpe', 'Exit % SL/TP/BE/time'], rows)

P('### T1-D. Random-direction benchmark (50 seeds; same entry bars, fill prices, stop distance, 2.5R target, 1.5R BE, 21:00 flat)')
P()
rows = []
r0 = r1[r1.year.isna()]
for cc in ('gross', 'spread15', 'base42', 'exp50'):
    x = r0[r0.cost_case == cc]
    a = m1[(m1.variant == BASE) & (m1.cost_case == cc)].iloc[0]
    rows.append([COSTLAB[cc], f(x.exp_pips.mean(), 0, True), f(np.percentile(x.exp_pips, 5), 0, True), f(np.percentile(x.exp_pips, 95), 0, True),
                 f(x.exp_pips.max(), 0, True), f(x.profit_factor.mean(), 2), f(x.return_pct_1pct_risk.mean(), 0, True), f((x.exp_pips > 0).mean() * 100, 0),
                 f(a.exp_pips, 0, True), f((x.exp_pips >= a.exp_pips).mean() * 100, 0)])
table(['Cost case', 'Random mean exp (pt)', '5th pct', '95th pct', 'Max of 50 seeds', 'Mean PF', 'Mean return % (1% risk)', '% seeds positive', 'Actual rule exp (pt)', '% seeds >= actual'], rows)
rows = []
ry = r1[r1.year.notna()]
for yr in (2024, 2025, 2026):
    x = ry[(ry.cost_case == 'base42') & (ry.year == yr)]
    a = y1[(y1.variant == BASE) & (y1.cost_case == 'base42') & (y1.year == yr)].iloc[0]
    rows.append([yr, f(x.exp_pips.mean(), 0, True), f(np.percentile(x.exp_pips, 5), 0, True), f(np.percentile(x.exp_pips, 95), 0, True), f(a.exp_pips, 0, True),
                 f((x.exp_pips >= a.exp_pips).mean() * 100, 0)])
table(['Year (base costs)', 'Random mean exp (pt)', '5th pct', '95th pct', 'Actual rule exp (pt)', '% seeds >= actual'], rows)

P('### T1-E. Splits of the base rule\'s trades (base costs 42 pt)')
P()
rows = []
for sp, lab in (('long', 'Long trades'), ('short', 'Short trades'), ('with_trend', 'Breakout in direction of 50-day SMA'), ('counter_trend', 'Breakout against 50-day SMA'),
                ('sl_capped', 'Stop capped at 0.6% of price (range wider than 0.6%)'), ('sl_uncapped', 'Stop at far side of range (range <= 0.6%)')):
    r = s1[(s1.variant == BASE) & (s1.cost_case == 'base42') & (s1.split == sp)].iloc[0]
    rows.append([lab, f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f(r.exp_pips, 0, True), f(r.exp_R, 2, True), ci(r.ci_lo, r.ci_hi), f(r.net_pips, 0, True, comma=True), f(r.avg_risk_pips, 0)])
table(['Split', 'Trades', 'Win %', 'PF', 'Exp (pt)', 'Exp (R)', '95% CI exp (pt)', 'Net (pt/lot)', 'Avg stop (pt)'], rows)

P('### T1-F. Gold benchmarks over the same period')
P()
rows = []
for _, r in b1[b1.benchmark == 'buy_and_hold'].iterrows():
    rows.append([r.period, f(r.start_px, 1), f(r.end_px, 1), f(r.return_pct, 1, True), f(r.pnl_points, 0, True, comma=True), f(r.max_dd_pct, 1), f(r.sharpe, 2)])
table(['Buy-and-hold (server-day closes)', 'Start', 'End', 'Return %', 'Points per lot', 'MaxDD % (daily closes)', 'Sharpe (daily)'], rows)
rows = []
for bm, lab in (('intraday_long_0800_2100_all_days', 'all weekdays'), ('intraday_long_0800_2100_eligible_days', 'days passing the 0.30-1.60% range filter')):
    for _, r in b1[b1.benchmark == bm].iterrows():
        rows.append([lab, r.period, f(r.n_days, 0), f(r.mean_points_per_day, 0, True), ci(r.ci_lo, r.ci_hi), f(r.total_points, 0, True, comma=True), f(r.win_rate, 1)])
table(['Long gold 08:00 -> 21:00 server (gross)', 'Period', 'Days', 'Mean pt/day', '95% CI', 'Total pt', '% up days'], rows)
rows = []
for _, r in rs1.iterrows():
    rows.append([int(r.year), f(r.days, 0), f(r.mean_price, 0, comma=True), f(r.mean_rng_usd, 1), f(r.median_rng_pct, 2), f(r.pct_below_0_30, 1), f(r.pct_above_1_60, 1)])
table(['Year', 'Days', 'Mean price', 'Mean 03-08 range ($)', 'Median range % of price', '% days < 0.30% (skipped)', '% days > 1.60% (skipped)'], rows)

P('### T1-G. Sensitivity grid: expectancy after base costs (42 pt), TP x buffer x range window (BE 1.5R, expiry 21:00). * = 95% CI above zero')
P()
hdr = ['Window / buffer'] + [f'TP {t}R' for t in (1.5, 2.0, 2.5, 3.0)]
rows = []
for w in ('02-07', '03-08', '04-09'):
    for b in (0.0, 20.0, 50.0):
        cells = []
        for t in (1.5, 2.0, 2.5, 3.0):
            r = g1[(g1.window == w) & (g1.buffer_pts == b) & (g1.tp_mult == t)].iloc[0]
            cells.append(f'{r.base42_exp:+.0f} (PF {r.base42_pf:.2f}){"*" if r.base42_ci_lo > 0 else ""}')
        rows.append([f'{w} / {b:.0f} pt'] + cells)
table(hdr, rows)
npos = int((g1.base42_exp > 0).sum()); nci = int((g1.base42_ci_lo > 0).sum()); nneg = int((g1.base42_ci_hi < 0).sum())
P(f'Cells positive after base costs: **{npos} of {len(g1)}**; CI entirely above zero: **{nci}**; CI entirely below zero: {nneg}. '
  f'Range of expectancy across cells: {g1.base42_exp.min():+.0f} to {g1.base42_exp.max():+.0f} pt; expensive-cost (50 pt) positives: {int((g1.exp50_exp > 0).sum())}; '
  f'gross CI above zero: {int((g1.gross_ci_lo > 0).sum())}.')
P()

# extra diagnostics from the base trade list
tr = pd.read_csv(os.path.join(res, 'trades', f't1_{BASE}.csv.gz'), parse_dates=['entry_time', 'exit_time', 'day'])
t = apply_costs(tr, 'XAUUSD', 42.0)
net = t.net_pips.values; yr = t.entry_time.dt.year.values
P('### T1-H. Concentration and robustness diagnostics (base rule, base costs)')
P()
rows = []
for lab, msk in (('All trades', np.ones(len(t), bool)), ('2024-2025 only (excluding 2026)', yr < 2026), ('Excluding the 10 best trades', ~np.isin(np.arange(len(t)), np.argsort(-net)[:10])),
                 ('Excluding the best 5% (30 trades)', ~np.isin(np.arange(len(t)), np.argsort(-net)[:30]))):
    x = net[msk]; lo, hi = bootstrap_ci(x)
    rows.append([lab, len(x), f(x.mean(), 0, True), ci(lo, hi), f(x[x > 0].sum() / -x[x <= 0].sum(), 2)])
table(['Subset', 'Trades', 'Exp (pt)', '95% CI', 'PF'], rows)
mo = t.groupby(t.entry_time.dt.to_period('M')).net_pips.sum()
q = t.groupby(t.entry_time.dt.to_period('Q')).net_pips.sum()
P(f'Share of total net from the 10 best trades: {np.sort(net)[::-1][:10].sum()/net.sum()*100:.0f}%; from the best 30 (5%): {np.sort(net)[::-1][:30].sum()/net.sum()*100:.0f}%. '
  f'Months positive: {(mo > 0).sum()} of {len(mo)}; quarters positive: {(q > 0).sum()} of {len(q)}; best quarter {q.idxmax()} {q.max():+,.0f} pt, worst {q.idxmin()} {q.min():+,.0f} pt. '
  f'Median gross R {t.gross_R.median():+.2f}, mean {t.gross_R.mean():+.2f}; trades reaching +1R at some point: {(t.mfe >= t.risk).mean()*100:.0f}%.')
P()

# ======================================================================================================================
# T2
# ======================================================================================================================
m2 = pd.read_csv(os.path.join(res, 't2_master.csv')); y2 = pd.read_csv(os.path.join(res, 't2_by_year.csv')); r2 = pd.read_csv(os.path.join(res, 't2_random.csv'))
P('<!-- T2 tables -->')
LAB2 = {'atr_x12_tp1.8': '**CodeBase defaults**: buffer 0.15 ATR, SL 1.2 ATR, TP 1.8R, orders expire 12:00', 'atr_x21_tp1.8': 'orders expire 21:00', 'atr_x12_tp1.0': 'TP 1.0R',
        'atr_x12_tp2.5': 'TP 2.5R', 'atr_x12_tp1.8_noFilter': 'no 0.15-0.70 range/ATR filter', 'atr_x12_tp1.8_long_only': 'buy stop only', 'atr_x12_tp1.8_short_only': 'sell stop only'}
for sym, cc_list, unit in (('XAUUSD', ('gross', 'spread15', 'base42', 'exp50'), 'pt'), ('EURUSD', ('gross', 'cheap0.8', 'base1.2', 'exp2.1'), 'pip')):
    base_cc = cc_list[2]
    P(f'### T2-{sym}. ATR-scaled Asian-range breakout, {sym} (base costs {base_cc.replace("base", "")} {unit}; gross in brackets)')
    P()
    rows = []
    for v in LAB2:
        r = m2[(m2.symbol == sym) & (m2.variant == v) & (m2.cost_case == base_cc)].iloc[0]
        g = m2[(m2.symbol == sym) & (m2.variant == v) & (m2.cost_case == 'gross')].iloc[0]
        yy = {yr: y2[(y2.symbol == sym) & (y2.variant == v) & (y2.cost_case == base_cc) & (y2.year == yr)] for yr in (2024, 2025, 2026)}
        yy = {k: (vv.iloc[0].exp_pips if len(vv) else np.nan) for k, vv in yy.items()}
        rows.append([LAB2[v], f(r.eligible_days, 0), f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f'{r.exp_pips:+.1f} ({g.exp_pips:+.1f})', f(r.exp_R, 3, True),
                     ci(r.ci_lo, r.ci_hi, 1), f'{yy[2024]:+.0f} / {yy[2025]:+.0f} / {yy[2026]:+.0f}', f(r.return_pct_1pct_risk, 1, True), f(r.max_dd_pct_1pct_risk, 1), f(r.sharpe, 2),
                     f(r.avg_risk_pips, 0), f'{r.pct_SL:.0f}/{r.pct_TP:.0f}/{r.pct_time:.0f}', f'{r.n_long:.0f} / {r.exp_long:+.0f}', f'{r.n_short:.0f} / {r.exp_short:+.0f}'])
    table(['Variant', 'Eligible days', 'Trades', 'Win %', 'PF', f'Exp {unit} net (gross)', 'Exp (R)', f'95% CI exp ({unit})', 'Exp by year 24/25/26', 'Return %', 'MaxDD %', 'Sharpe',
           f'Avg stop ({unit})', 'Exit % SL/TP/time', 'Longs n / exp', 'Shorts n / exp'], rows)
    rows = []
    for cc in cc_list:
        r = m2[(m2.symbol == sym) & (m2.variant == 'atr_x12_tp1.8') & (m2.cost_case == cc)].iloc[0]
        x = r2[(r2.symbol == sym) & (r2.cost_case == cc)]
        rows.append([cc, f(r.trades, 0), f(r.exp_pips, 1, True), ci(r.ci_lo, r.ci_hi, 1), f(r.profit_factor, 2), f(r.return_pct_1pct_risk, 1, True),
                     f(x.exp_pips.mean(), 1, True), f(np.percentile(x.exp_pips, 5), 1, True), f(np.percentile(x.exp_pips, 95), 1, True), f((x.exp_pips >= r.exp_pips).mean() * 100, 0)])
    table(['Cost case (CodeBase defaults)', 'Trades', f'Exp ({unit})', '95% CI', 'PF', 'Return % (1% risk)', 'Random-dir mean exp', 'Random 5th pct', 'Random 95th pct', '% random seeds >= actual'], rows)

# ======================================================================================================================
# T3
# ======================================================================================================================
m3 = pd.read_csv(os.path.join(res, 't3_master.csv')); y3 = pd.read_csv(os.path.join(res, 't3_by_year.csv')); r3 = pd.read_csv(os.path.join(res, 't3_random.csv'))
st3 = json.load(open(os.path.join(res, 't3_stats.json')))
P('<!-- T3 tables -->')
SYMS = ['AUDNZD', 'EURCHF', 'EURGBP', 'AUDCAD', 'GBPCAD', 'NZDCAD', 'EURAUD', 'EURUSD', 'POOLED_CROSSES']
VARS = ['N1_bb_sl1.5x_mintp0', 'N1_bb_sl2.0x_mintp0', 'N1_bb_sl1.5x_mintp5', 'N1_bb_sl2.0x_mintp5', 'N2_limit_tp6_sl12', 'N2_limit_tp10_sl20', 'N3_rsi2_night', 'N3_rsi2_allday']
LAB3 = {'N1_bb_sl1.5x_mintp0': 'N1 Bollinger fade, SL 1.5x TP', 'N1_bb_sl2.0x_mintp0': 'N1 Bollinger fade, SL 2x TP', 'N1_bb_sl1.5x_mintp5': 'N1 Bollinger fade, SL 1.5x, TP >= 5 pips',
        'N1_bb_sl2.0x_mintp5': 'N1 Bollinger fade, SL 2x, TP >= 5 pips', 'N2_limit_tp6_sl12': 'N2 range limit fade, TP 6 / SL 12', 'N2_limit_tp10_sl20': 'N2 range limit fade, TP 10 / SL 20',
        'N3_rsi2_night': 'N3 RSI(2) < 5 / > 95, night window', 'N3_rsi2_allday': 'N3 RSI(2), all day (contrast)'}
P('### T3-A. Night scalping: expectancy per trade (pips) by symbol and variant, base costs (spread + 0.7 commission + 0.4 slippage); gross in brackets; * = 95% CI above zero, (-) = below zero')
P()
hdr = ['Variant'] + SYMS
rows = []
for v in VARS:
    cells = []
    for s in SYMS:
        r = m3[(m3.symbol == s) & (m3.variant == v) & (m3.cost_case == 'base')]
        g = m3[(m3.symbol == s) & (m3.variant == v) & (m3.cost_case == 'gross')]
        if len(r) == 0 or r.iloc[0].trades == 0:
            cells.append('-'); continue
        r = r.iloc[0]; g = g.iloc[0]
        mark = '*' if r.ci_lo > 0 else ('(-)' if r.ci_hi < 0 else '')
        cells.append(f'{r.exp_pips:+.2f} ({g.exp_pips:+.2f}){mark} n={int(r.trades)}')
    rows.append([LAB3[v]] + cells)
table(hdr, rows)
P('### T3-B. Same, "full" costs (base + 1.0 pip rollover widening for entries 23:45-00:15 server + 0.5 pip swap per rollover held, x3 Wednesday)')
P()
rows = []
for v in VARS:
    cells = []
    for s in SYMS:
        r = m3[(m3.symbol == s) & (m3.variant == v) & (m3.cost_case == 'full')]
        if len(r) == 0 or r.iloc[0].trades == 0:
            cells.append('-'); continue
        r = r.iloc[0]
        mark = '*' if r.ci_lo > 0 else ('(-)' if r.ci_hi < 0 else '')
        cells.append(f'{r.exp_pips:+.2f}{mark} PF {r.profit_factor:.2f}')
    rows.append([LAB3[v]] + cells)
table(hdr, rows)
P('### T3-C. Detail per variant, pooled over the seven crosses (base and full costs)')
P()
rows = []
for v in VARS:
    for cc in ('gross', 'base', 'full'):
        r = m3[(m3.symbol == 'POOLED_CROSSES') & (m3.variant == v) & (m3.cost_case == cc)]
        if len(r) == 0:
            continue
        r = r.iloc[0]
        yy = {yr: y3[(y3.symbol == 'POOLED_CROSSES') & (y3.variant == v) & (y3.cost_case == cc) & (y3.year == yr)] for yr in (2024, 2025, 2026)}
        yy = {k: (vv.iloc[0].exp_pips if len(vv) else np.nan) for k, vv in yy.items()}
        rows.append([LAB3[v] if cc == 'gross' else '', cc, f(r.cost_pips, 2), f(r.trades, 0), f(r.win_rate), f(r.profit_factor, 2), f(r.exp_pips, 2, True), f(r.exp_R, 3, True),
                     ci(r.ci_lo, r.ci_hi, 2), f'{yy[2024]:+.2f} / {yy[2025]:+.2f} / {yy[2026]:+.2f}', f(r.avg_risk_pips, 1), f(r.cost_pct_of_risk, 0), f(r.avg_bars, 0),
                     f'{r.pct_SL:.0f}/{r.pct_TP:.0f}/{r.pct_time:.0f}', f'{r.exp_long:+.2f} / {r.exp_short:+.2f}', f(r.streak, 0)])
table(['Variant', 'Costs', 'Avg cost (pips)', 'Trades', 'Win %', 'PF', 'Exp (pips)', 'Exp (R)', '95% CI exp', 'Exp by year 24/25/26', 'Avg stop (pips)', 'Cost % of stop', 'Avg bars (M1)',
       'Exit % SL/TP/time', 'Exp long / short', 'Streak'], rows)
P('### T3-D. Per-symbol detail at base costs, best-looking variant per family (N1 SL 2x TP >= 5 pips; N2 TP 6 / SL 12; N3 night)')
P()
rows = []
for v in ('N1_bb_sl2.0x_mintp5', 'N2_limit_tp6_sl12', 'N3_rsi2_night'):
    for s in SYMS[:-1]:
        r = m3[(m3.symbol == s) & (m3.variant == v) & (m3.cost_case == 'base')]
        if len(r) == 0 or r.iloc[0].trades == 0:
            continue
        r = r.iloc[0]
        fu = m3[(m3.symbol == s) & (m3.variant == v) & (m3.cost_case == 'full')].iloc[0]
        x = r3[(r3.symbol == s) & (r3.variant == v) & (r3.cost_case == 'base')]
        yy = {yr: y3[(y3.symbol == s) & (y3.variant == v) & (y3.cost_case == 'base') & (y3.year == yr)] for yr in (2024, 2025, 2026)}
        yy = {k: (vv.iloc[0].exp_pips if len(vv) else np.nan) for k, vv in yy.items()}
        rows.append([LAB3[v], s, f(r.cost_pips, 1), f(r.trades, 0), f(r.trades_per_night, 2), f(r.win_rate), f(r.profit_factor, 2), f(r.exp_pips, 2, True), ci(r.ci_lo, r.ci_hi, 2),
                     f'{yy[2024]:+.1f} / {yy[2025]:+.1f} / {yy[2026]:+.1f}', f(fu.exp_pips, 2, True), f(r.return_pct_1pct_risk, 0, True), f(r.max_dd_pct_1pct_risk, 1), f(r.sharpe, 2),
                     f(x.exp_pips.mean(), 2, True) if len(x) else '-', f(np.percentile(x.exp_pips, 95), 2, True) if len(x) else '-', f((x.exp_pips >= r.exp_pips).mean() * 100, 0) if len(x) else '-'])
table(['Variant', 'Symbol', 'Base cost', 'Trades', 'Trades / night', 'Win %', 'PF', 'Exp base (pips)', '95% CI', 'Exp by year 24/25/26', 'Exp full costs', 'Return % (1% risk)', 'MaxDD %', 'Sharpe',
       'Random-dir mean', 'Random 95th pct', '% random >= actual'], rows)
# cost-assumption summary
P('### T3-E. Night-cost assumptions actually applied (share of trades hit by the rollover add-on and by swap)')
P()
rows = []
for k, v in st3.items():
    if 'N2_limit_tp6' in k or 'N1_bb_sl2.0x_mintp5' in k:
        rows.append([k, f(v.get('base', np.nan), 1), f(v.get('pct_rollover', np.nan), 1), f(v.get('pct_swap', np.nan), 1), v.get('trades', '-')])
table(['Symbol_variant', 'Base cost (pips RT)', '% entries 23:45-00:15 (+1.0 pip)', '% positions held across 00:00 (swap)', 'Trades'], rows)

# ======================================================================================================================
# T4
# ======================================================================================================================
m4 = pd.read_csv(os.path.join(res, 't4_master.csv')); y4 = pd.read_csv(os.path.join(res, 't4_by_year.csv')); r4 = pd.read_csv(os.path.join(res, 't4_random.csv'))
P('<!-- T4 tables -->')
P('### T4-A. Breedon-Ranaldo EURUSD time-of-day pattern (short 07-13 UTC, long 13-21 UTC)')
P()
rows = []
LAB4 = {'short_07_13': 'Short 07:00-13:00 UTC', 'long_13_21': 'Long 13:00-21:00 UTC', 'combined': 'Both legs', 'reverse_combined': 'Reverse of both legs (contrast)'}
for v in LAB4:
    for cc in ('gross', 'cheap0.8', 'base1.2'):
        r = m4[(m4.variant == v) & (m4.cost_case == cc)].iloc[0]
        yy = {yr: y4[(y4.variant == v) & (y4.cost_case == cc) & (y4.year == yr)].iloc[0] for yr in (2024, 2025, 2026)}
        rows.append([LAB4[v] if cc == 'gross' else '', cc, f(r.trades, 0), f(r.win_rate), f(r.exp_pips, 2, True), ci(r.ci_lo, r.ci_hi, 2), f(r.total_pips, 0, True, comma=True), f(r.sharpe, 2), f(r.profit_factor, 2),
                     ' / '.join(f'{yy[y].total_pips:+,.0f}' for y in (2024, 2025, 2026)), ' / '.join(f'{yy[y].exp_pips:+.2f}' for y in (2024, 2025, 2026)), ' / '.join(f'{yy[y].sharpe:+.2f}' for y in (2024, 2025, 2026))])
table(['Leg', 'Costs (pips RT)', 'Trades', 'Win %', 'Exp (pips)', '95% CI exp', 'Total pips', 'Sharpe', 'PF', 'Total pips 24/25/26', 'Exp 24/25/26', 'Sharpe 24/25/26'], rows)
x = r4[r4.cost_case == 'gross']
P(f'Random-direction baseline on the same 1,394 legs (gross): mean {x.exp_pips.mean():+.2f} pips, 5th-95th pct [{np.percentile(x.exp_pips, 5):+.2f}, {np.percentile(x.exp_pips, 95):+.2f}]; '
  f'the pattern\'s gross {m4[(m4.variant == "combined") & (m4.cost_case == "gross")].iloc[0].exp_pips:+.2f} is inside that band.')
P()

open(out_md, 'w').write('\n'.join(L))
print('wrote', out_md, len(L), 'lines')
