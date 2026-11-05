"""T3 robustness: how much of the night-scalping result comes from the minutes around the 00:00 server rollover, where the
Forexite bid feed shows spike bars and a 10-15 minute gap (and where real spreads are several times wider)?
For each symbol and variant: expectancy (base costs) by entry-time bucket, the share of trades that enter and exit in the
same M1 bar, and the result after excluding entries between 23:30 and 00:30 server.
Usage: python3 -I t3_rollover_check.py <clean_data_dir> <results_dir>
"""
import sys, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from r2_engine import *   # noqa

data_dir, res = sys.argv[1], sys.argv[2]
SYMS = ['AUDNZD', 'EURCHF', 'EURGBP', 'AUDCAD', 'GBPCAD', 'NZDCAD', 'EURAUD', 'EURUSD']
VARS = ['N1_bb_sl2.0x_mintp5', 'N1_bb_sl1.5x_mintp5', 'N2_limit_tp6_sl12', 'N2_limit_tp10_sl20', 'N1_bb_sl2.0x_mintp0']
NIGHT_SPREAD = {'EURCHF': 0.8, 'AUDNZD': 1.0, 'EURGBP': 0.7, 'AUDCAD': 0.9, 'GBPCAD': 1.3, 'NZDCAD': 1.1, 'EURAUD': 1.0, 'EURUSD': 0.4}
BUCKETS = [(21 * 60, 22 * 60, '21:00-22:00'), (22 * 60, 23 * 60, '22:00-23:00'), (23 * 60, 23 * 60 + 30, '23:00-23:30'),
           (23 * 60 + 30, 24 * 60 + 30, '23:30-00:30 (rollover)'), (30, 2 * 60, '00:30-02:00')]
rows, pooled = [], {}
for SYM in SYMS:
    data = Data(os.path.join(data_dir, f'{SYM}_M1.csv'), SYM); sd = ServerDays(data)
    base = NIGHT_SPREAD[SYM] + 0.7 + 0.4
    # size of the rollover gap and spike in this feed: median |open - previous close| for the first bar after 00:00 server vs other bars
    srv_m = server_minute_of_day(sd.srv)
    jump = np.abs(data.o[1:] - data.c[:-1]) / SPECS[SYM]['pip']
    first_after = (srv_m[1:] >= 0) & (srv_m[1:] < 30) & (srv_m[:-1] >= 23 * 60)
    gapmin = ((data.ts[1:] - data.ts[:-1]) / np.timedelta64(1, 'm')).astype(float)
    print(f'{SYM}: median gap length at the 00:00 rollover {np.median(gapmin[first_after]):.0f} min; median |open-prev close| at the rollover bar '
          f'{np.median(jump[first_after]):.1f} pips vs {np.median(jump[~first_after]):.1f} pips elsewhere; 95th pct {np.percentile(jump[first_after], 95):.1f} vs {np.percentile(jump[~first_after], 95):.1f}')
    for v in VARS:
        p = os.path.join(res, 'trades', f't3_{SYM}_{v}.csv.gz')
        if not os.path.exists(p):
            continue
        tr = pd.read_csv(p)
        t = apply_costs(tr, SYM, base)
        m = server_minute_of_day(sd.srv[t['entry_idx'].values]); m2 = np.where(m < 12 * 60, m + 24 * 60, m)   # 00:30 -> 1470
        same_bar = (t['bars'] == 0)
        for lo, hi, lab in BUCKETS:
            lo2, hi2 = (lo, hi) if lo >= 12 * 60 else (lo + 24 * 60, hi + 24 * 60)
            sel = (m2 >= lo2) & (m2 < hi2)
            x = t.net_pips.values[sel]
            rows.append(dict(symbol=SYM, variant=v, bucket=lab, trades=int(sel.sum()), exp=x.mean() if len(x) else np.nan, net=x.sum(),
                             share_of_net_pct=x.sum() / t.net_pips.sum() * 100 if t.net_pips.sum() != 0 else np.nan, same_bar_pct=same_bar[sel].mean() * 100 if sel.any() else np.nan))
        excl = ~((m2 >= 23 * 60 + 30) & (m2 < 24 * 60 + 30))
        x = t.net_pips.values[excl]; lo_, hi_ = bootstrap_ci(x)
        rows.append(dict(symbol=SYM, variant=v, bucket='ALL', trades=len(t), exp=t.net_pips.mean(), net=t.net_pips.sum(), share_of_net_pct=100.0, same_bar_pct=same_bar.mean() * 100,
                         ci_lo=t.net_pips.quantile(0) * 0 + bootstrap_ci(t.net_pips.values)[0], ci_hi=bootstrap_ci(t.net_pips.values)[1]))
        rows.append(dict(symbol=SYM, variant=v, bucket='EXCL 23:30-00:30', trades=int(excl.sum()), exp=x.mean(), net=x.sum(), share_of_net_pct=x.sum() / t.net_pips.sum() * 100 if t.net_pips.sum() != 0 else np.nan,
                         same_bar_pct=same_bar[excl].mean() * 100, ci_lo=lo_, ci_hi=hi_))
        # same-bar (entry and exit within one M1 bar) trades: how much do they contribute?
        xs = t.net_pips.values[same_bar.values]
        rows.append(dict(symbol=SYM, variant=v, bucket='SAME-BAR trades only', trades=int(same_bar.sum()), exp=xs.mean() if len(xs) else np.nan, net=xs.sum(),
                         share_of_net_pct=xs.sum() / t.net_pips.sum() * 100 if t.net_pips.sum() != 0 else np.nan, same_bar_pct=100.0))
        xn = t.net_pips.values[~same_bar.values]; lo_, hi_ = bootstrap_ci(xn)
        rows.append(dict(symbol=SYM, variant=v, bucket='EXCL same-bar trades', trades=int((~same_bar).sum()), exp=xn.mean(), net=xn.sum(),
                         share_of_net_pct=xn.sum() / t.net_pips.sum() * 100 if t.net_pips.sum() != 0 else np.nan, same_bar_pct=0.0, ci_lo=lo_, ci_hi=hi_))
        if SYM != 'EURUSD':
            pooled.setdefault(v, []).append(t.assign(m2=m2, same_bar=same_bar.values))
for v, lst in pooled.items():
    t = pd.concat(lst, ignore_index=True)
    for lab, sel in (('ALL', np.ones(len(t), bool)), ('EXCL 23:30-00:30', ~((t.m2 >= 23 * 60 + 30) & (t.m2 < 24 * 60 + 30)).values),
                     ('SAME-BAR trades only', t.same_bar.values), ('EXCL same-bar trades', ~t.same_bar.values), ('rollover bucket only', ((t.m2 >= 23 * 60 + 30) & (t.m2 < 24 * 60 + 30)).values)):
        x = t.net_pips.values[sel]; lo_, hi_ = bootstrap_ci(x) if len(x) > 1 else (np.nan, np.nan)
        rows.append(dict(symbol='POOLED_CROSSES', variant=v, bucket=lab, trades=int(sel.sum()), exp=x.mean() if len(x) else np.nan, net=x.sum(),
                         share_of_net_pct=x.sum() / t.net_pips.sum() * 100 if t.net_pips.sum() != 0 else np.nan, same_bar_pct=t.same_bar.values[sel].mean() * 100 if sel.any() else np.nan, ci_lo=lo_, ci_hi=hi_))
df = pd.DataFrame(rows)
df.to_csv(os.path.join(res, 't3_rollover_check.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
print(df[df.symbol == 'POOLED_CROSSES'].round(2).to_string())
print(df[(df.symbol.isin(['AUDNZD', 'EURCHF', 'EURAUD'])) & (df.variant.isin(['N2_limit_tp10_sl20', 'N1_bb_sl2.0x_mintp5']))].round(2).to_string())
