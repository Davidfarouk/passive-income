# Validating a scalping strategy / EA before risking money in MetaTrader 5 (2025–2026)

Scope note for the writer: 16 web searches were run and roughly 37 pages were read in full (official MetaQuotes help, MQL5 articles/blogs 2011–2026, vendor docs, broker execution pages, the Bailey/López de Prado papers via local PDF text extraction). The shared web-search budget was exhausted after the 16th search, so a few items (QuantStart, SSRN, Admiral Markets, Robot Wealth) could not be fetched and are listed as gaps. Dates are given so the writer can mark older material; everything from MetaQuotes help pages is the current online version as of Nov 2026.

---

## KQ1. What do MetaQuotes docs and MQL5 articles say about MT5 Strategy Tester tick modeling, modeling quality, spread, real-tick availability and limitations for M1 scalping backtests?

### Takeaway
MT5 has four price-modeling modes; only "Every tick based on real ticks" replays broker-recorded ticks with their real intra-minute spread, while the three generated modes build at most 11 synthetic ticks per M1 bar and apply one fixed spread per minute bar. Real-tick history is filled with generated ticks wherever the broker's tick archive has holes, and the tester's "History Quality" figure measures M1-bar consistency, not tick fidelity, so a high quality number does not by itself validate a scalping backtest.

### Cited Findings

**The four modes (official help, current)**
- MetaQuotes lists the modes as: "Every tick — the most accurate but the slowest mode" (all ticks simulated); "Every tick based on real ticks" using broker-collected ticks where "No simulation is performed" and "downloading them from a broker's server during the first testing run may take a long time"; "1 minute OHLC" where "only 4 prices (Open, High, Low and Close) of each minute bar are emulated"; "Open prices only" where "only the open price is used for testing/optimization"; plus "Math calculations" (no ticks, no history; "margin control is not performed in this mode. You should only use it for quick and rough strategy estimation"). — [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- A "Pips" profit-calculation mode speeds testing but "Swap and commission calculations are eliminated in this mode." — [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)

**How generated ticks are built (official help, current)**
- Generated ticks come from cached M1 records: tick volume 1 → one tick at Close; tick volume 2 → Open then Close; tick volume ≥3 → ticks built from reference points whose count "cannot exceed the tick volume or 11 (Open is excluded)", split between opening shadow, body range and closing shadow (an "ideal" 3-5-3 distribution). Intermediate ticks form a sawtooth or linear sequence. — [MetaTrader 5 Help: Real and Generated Ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)
- Spread in generated modes: "Generated ticks use a fixed spread from the minute bar"; Ask = Bid + that fixed spread; bars are built from Bid, trades execute at Bid/Ask. With real ticks, "The spread can change within a minute bar." — [MetaTrader 5 Help: Real and Generated Ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)
- Real-tick fallback: "Missing minute data is filled in by generating ticks in 'Every tick' mode. Ticks for a minute with no minute bar are ignored, because minute data is considered more reliable." Tick data is stored monthly in TKC files under `bases\[server]\ticks\[symbol]\`. — [MetaTrader 5 Help: Real and Generated Ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)
- "Open prices only" limitations: Random Delay cannot be used; the EA cannot access timeframes below the test timeframe; stops/pending orders "may trigger at prices different from the specified ones, especially on higher timeframes"; W1/MN1 bars generated once a day. — [MetaTrader 5 Help: Real and Generated Ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)
- MQL5 Book: if real ticks are selected but the broker lacks them for the instrument, the tester silently uses the "All ticks" (generated) mode; if an M1 bar exists but has no ticks for that minute, ticks are generated for that minute. The tester report shows the tick-generation mode "graphically and as a percentage, where '100% means all ticks are real.'" The tick cache holds at most 128,000 ticks. The book warns that "1 minute OHLC" can create a "Testing Grail" that doesn't hold up online. — [MQL5 Book: Generating ticks in tester](https://www.mql5.com/en/book/automation/tester/tester_ticks)

**Spread is taken from history, not modeled**
- MetaQuotes (2011, still accurate for generated modes): "The spread is not modeled. It is taken from historical data"; if the historical spread is zero/negative the agent uses the spread at the time of the requested data; spread is "always considered floating" and `SYMBOL_SPREAD_FLOAT` always returns true in the tester. 1-minute OHLC "removes intrabar price movement, which can produce an unrealistically smooth equity curve"; recommends re-checking any promising result in "Every tick". — [MQL5 Article 239: The Fundamentals of Testing in MetaTrader 5 (18 May 2011)](https://www.mql5.com/en/articles/239)
- Forum (2017–2026, mql5.com): moderator Alain Verleyen (2017): "Historical data are used you can't change it." Thi Thu Ha Hoang (2022) edited the spread column of >5 million Tickstory rows yet the spread still floated in the backtest. Peter Mueller (26 Apr 2026): in "every tick based on real ticks" the symbol panel cannot set spread because "spreads are essentially contained in the real ticks themselves"; in 1-minute-OHLC mode the panel spread does apply, and on his broker tests at 100 vs 1000 points gave "very significant" differences. — [MQL5 Forum 212322: MT5 backtesting spread](https://www.mql5.com/en/forum/212322)
- Same thread p.2: sentinelquantlabs (26 Apr 2026) found an EA profitable with a fixed 10-point spread lost money with variable spread because widening at news/session opens/rollover ate trades that barely reached TP; treats a large fixed-vs-variable gap as a spread-sensitivity red flag. Ryan L Johnson recommends backtesting OHLC with the "maximum spread for your trading times". — [MQL5 Forum 212322 page 2](https://www.mql5.com/en/forum/212322/page2)
- (Search snippet only, not fetched) a separate MQL5 thread reports that with real ticks changing the custom spread setting "seems to have no effect; it only seems to work on virtual ticks." — [MQL5 Forum 427613](https://mql5.com/en/forum/427613/40419568)

**How much the mode changes results (MetaQuotes experiment)**
- MetaQuotes tested one breakout EA (EURUSD H1, 1 Jan–30 Jun 2016) in three modes: 1-min OHLC → 731,466 ticks, net +169.46, 96 trades, 1.6 s; Every tick → 18,983,485 ticks, net −466.81, 158 trades, DD 9.29%, 36.7 s; Real ticks → 34,099,141 ticks, net −97.24, 156 trades, DD 6.07%, 74 s. Real-tick mode had ~1.8× the ticks of "Every tick" and took ~2× longer; the author notes tick count and order change entries, exits and skipped trades. A reader comment claims "1 minute OHLC" samples at roughly 0/20/40/59 s rather than true OHLC (unverified). — [MQL5 Article 2612: Testing trading strategies on real ticks (4 Aug 2016)](https://www.mql5.com/en/articles/2612)

**Execution delay (latency) settings**
- Official: "delays work only for trades performed by an EA"; for pending orders "delays are only applied to order placing but not to order execution". Modes: "No Delay" ("all orders are executed at requested prices without requotes"), "Random Delay" ("the possibility of a delay for 0-8 seconds is 90%, possibility of a 9-18 second delay is 10%" — quoted as the help page renders it), and "Fixed Delay" where "The platform measures the ping to the trade server" and lets you use it. Requotes are possible in instant-execution mode if price moves beyond the deviation. — [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- Practitioners describe Random Delay as a "crude tool" and recommend running the same strategy with several slippage/spread assumptions; a 2021 beta bug report said Random Delay wrongly triggered requote errors (may be fixed). — [MQL5 Forum 430831](https://www.mql5.com/en/forum/430831/41433018), [MQL5 Forum 445072](https://www.mql5.com/en/forum/445072)

**"Modeling quality" / "History Quality"**
- Official definition: History Quality is "the percentage ratio of correct to incorrect one-minute data"; bars with volume 1 and differing OHLC and history gaps count as incorrect; the test period is split into 1–199 intervals, each scored, with intervals below 50% shown in red. The "Ticks" field is just "the number of ticks modeled during testing." — [MetaTrader 5 Help: Testing Report](https://www.metatrader5.com/en/terminal/help/algotrading/testing_report)
- (Search snippet only; MT4-era) an MQL5 user found the same tick file could show 25% quality and concluded the "99%" number is "just a number embedded in the tick data file (FXT)". — [MQL5 Forum 11241](https://mql5.com/en/forum/11241/469904)
- Vendors selling pre-built MT5 custom symbols say selecting "Every tick based on real ticks" is required to "achieve 100% modeling quality, the highest possible accuracy in MetaTrader 5" (vendor claim). — [MQL5 Blog 771687: MT5 Tick Data (22 Jun 2026)](https://www.mql5.com/en/blogs/post/771687)

**Community critique and correction (Dec 2025)**
- Blog post argues even real-tick tests omit live latency, queueing and slippage, that real latency is "about 5 ms to 300 ms during volatile moments", and that "99.9% model quality can create false confidence". Stanislav Korotky (17 Dec 2025) pushed back that with real ticks the claims about smoothed gaps and fixed spreads are wrong, tester spreads follow real dynamics and delay can be random; the author conceded his points applied to generated ticks. — [MQL5 Blog 765944 (6 Dec 2025)](https://www.mql5.com/es/blogs/post/765944)

**Importing your own ticks (official)**
- Custom symbols accept tick files with columns Date, Time, Bid, Ask, Last, Volume (chronological; flags computed on import), bar files with Date, Time, O, H, L, C, TickVolume, Volume, Spread; a "Shift" option offsets hours for timezone; "During import, the time interval is completely replaced by data from the specified file." Custom symbols cannot use the MQL5 Cloud Network for optimization and names must not match broker symbols (connecting to a server with the same name deletes the custom symbol). — [MetaTrader 5 Help: Custom Financial Instruments](https://www.metatrader5.com/en/terminal/help/trading_advanced/custom_instruments)

### Inferences
- For a 5–10 pip scalper, only "Every tick based on real ticks" on a broker with deep tick history is defensible; a generated-tick test applies one spread per minute and a synthetic intrabar path, which is exactly where a scalper's SL/TP decisions happen.
- Because the tester silently falls back to generated ticks per minute where ticks are missing, the real-tick percentage shown in the report (not History Quality) is the figure to check, and it should be checked per broker/symbol since tick depth differs by server.
- The practical way to run fixed-spread stress tests in MT5 is in 1-minute-OHLC/Every-tick mode via the custom-symbol spread setting (or by editing the Spread column in an imported M1 file), while real-tick mode is used to see actual spread dynamics; both runs together bracket spread sensitivity.
- Use "Fixed Delay" set to measured ping (plus margin) rather than Random Delay, since the latter's distribution (as documented) is far wider than typical VPS latency.

### Gaps
- No official statement was found on how many months/years of real tick history major brokers keep, or a list of brokers with full tick archives; this must be checked per server (the tester journal reports downloaded tick months).
- The exact algorithm by which the report computes "% real ticks" for mixed real/generated periods is not documented.
- The Random Delay text ("0-8 seconds") was quoted via a fetch summary; the unit should be double-checked against the live help page before publication.

---

## KQ2. Where to obtain free high-quality historical M1/tick data (EURUSD/XAUUSD) and what are the known quality issues (gaps, GMT offsets, bid-only vs bid/ask)?

### Takeaway
Dukascopy (direct, via Tickstory or StrategyQuant's QuantDataManager) is the default free bid/ask tick source from ~2007; TrueFX offers free institutional top-of-book ticks with registration; HistData gives free M1/tick CSV but in fixed EST without DST, bid-based bars, and ask only in its tick ASCII files. All free sources have holes and timezone pitfalls, and each MT5 import route has its own spread limitation.

### Cited Findings

**Dukascopy**
- Dukascopy's Historical Data Export is free, CSV, "from tick-by-tick to monthly", covering "Forex, Commodities and Indices"; it points to a Trading Breaks Calendar in GMT because holidays and DST shift trading hours. The page does not state bid/ask availability, start dates or export timezones. — [Dukascopy Historical Data Feed](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- (Search snippets, not fetched) a trader reports Dukascopy "offers free tick data spanning from April 2007 (for most currencies)"; another that Dukascopy "do not have weekend GMT tick data to download, apart from the last couple of hours on Sunday"; a Dukascopy forum user found daily OHLC built from downloaded ticks did not match JForex OHLC on some days. — [EliteTrader: Free tick data back to 2007](https://elitetrader.com/et/threads/free-tick-data-back-to-2007.328629/), [MQL5 Forum 156020](https://mql5.com/en/forum/156020/3801630), [Dukascopy forum](https://www.dukascopy.com/swiss/english/forex/jforex/forum/viewtopic.php?p=89906)

**QuantDataManager (StrategyQuant) – free downloader**
- Lists Dukascopy, Yahoo, Darwinex, Binance, Bitfinex, Coinbase, Poloniex and file import; forex/CFD tick data "provided for free by Dukascopy (available directly in app)"; "Commodity data are paid, there is no free source available." Downloads tick and minute data; can clone a dataset "recomputed into a different timezone"; exports MT4 FXT/HST and has an MT5 import guide; quality tools "review gaps, spikes and incorrect candles"; Pro "Verified downloads" prevent connection-caused gaps "but not gaps already present in the source data." Free tier (ads) or Pro $49 lifetime. — [StrategyQuant QuantDataManager](https://strategyquant.com/quantdatamanager)

**Tickstory**
- Tickstory support (2017–2018): MT5 custom-symbol import from Dukascopy works and a user achieved 100% quality after selecting "Every tick based on real ticks"; but "The File Export function has no field for exporting spread, so they use a fixed spread that users can change" and the tester's USD/EUR cross-rate lookup caused "no prices for symbol USDEUR_BASKET" errors with no documented fix. — [Tickstory MT5 Support thread](https://support.tickstory.com/viewtopic.php?p=7101)
- (Search snippet) Tickstory "sources its free data from Dukascopy" and describes it as updated daily. — [Tickstory](https://tickstory.com/)

**Tick Data Suite (eareview.net) – paid, MT4**
- "The Tick Data Suite only integrates with MT4"; "Tick Data Suite for MT5 is currently in beta". Features: recorded variable spread adjustable to a broker, slippage simulation with several generation methods, commission/leverage overrides, backtest timezone change, nine download sources including Dukascopy, TrueFX, Darwinex, FxOpen. Pricing $37.9/month, $200.9/year, $579 lifetime, 14-day trial. Markets "99% modeling quality in your MT4 backtests." — [Tick Data Suite product page](https://eareview.net/tick-data-suite)
- TDS support: do not set spread to "Current" (variable-spread brokers make each run different); enable "Reproducible slippage" or every run gets different slippage; TDS removes duplicate consecutive identical bid/ask ticks by default; mismatched GMT/DST settings between runs and between the main symbol and any `iClose` cross-symbol data cause divergent results; "Grid and martingale EAs are especially sensitive. A single trade closing at a different time or price can cascade into large differences." — [Tick Data Suite: Different backtest results](https://eareview.freshdesk.com/support/solutions/articles/19000063735-different-backtest-results)

**HistData.com**
- "The timezone of all data is: Eastern Standard Time (EST) time-zone WITHOUT Day Light Savings adjustments." Bar OHLC "derived from the Bid"; "Ask prices appear only in Tick data in the Generic ASCII format, so you can calculate spread only from that format." Offers Tick and M1 only; volume removed because "volume data is broker-specific"; per-file status reports max gap (ms), gaps >1 minute and average tick interval, noting average gaps above 90 s in low-volume periods. Free CSV; Automatic Updates $7/month per format (MT4/5, Generic ASCII, Excel, NinjaTrader, MetaStock). No warranty: use "at your own will and risk." — [HistData.com FAQ](https://www.histdata.com/f-a-q/)
- Conflict: a third-party guide (search snippet) says HistData is "derived from Dukascopy" and "GMT"; HistData's own FAQ names no source and specifies EST. Prefer the FAQ. — [hw.online guide](https://hw.online/faq/metatrader-4-historical-data-for-backtesting/) vs [HistData FAQ](https://www.histdata.com/f-a-q/)

**TrueFX**
- "Top-of-book, tick-by-tick market data, with fractional pip spreads in millisecond detail", sourced from Integral OCX ("over 250 banks, brokers, and asset managers"), "at zero cost to you", registration required. Pairs, start year, format and timezone are not stated on the page. — [TrueFX Historical Downloads](https://www.truefx.com/truefx-historical-downloads/)
- Older secondary sources (2012–2016): history from 2009, 15 major pairs, monthly zip files, timestamps GMT. — [Forex Strategy Builder wiki: TrueFX data](https://forexsb.com/wiki/fsb/manual/truefx_data), [TFX R package](https://rdrr.io/cran/TFX)

**Pre-built MT5 custom symbols (vendor)**
- FEA Trading's installer delivers custom symbols per spread profile (Low = raw+commission, Medium = standard, High = retail standard), e.g. `EURUSD_SPREAD_MEDIUM`; data in UTC+02:00 with DST; 26 symbols; updated around the 10th monthly; custom symbols are tester-only. — [MQL5 Blog 771687 (22 Jun 2026)](https://www.mql5.com/en/blogs/post/771687)

**Broker ticks (built-in)**
- The tester downloads the broker's own ticks on first run; sizes are large; stored as monthly TKC files. — [MetaTrader 5 Help: Real and Generated Ticks](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation)

**General data-quality warnings**
- Forum consensus (snippets): "the quality aspect of data is more about missing data, Fridays that end at different times and Sundays that start at different times, H1 data not matching M1 data"; public archives default to GMT/UTC while most retail MT servers run GMT+2/GMT+3, "so timezone misalignment is the most common problem." — [MQL5 Forum 131188](https://www.mql5.com/en/forum/131188), [hw.online guide](https://hw.online/faq/metatrader-4-historical-data-for-backtesting/)

### Inferences
- For EURUSD, the realistic free stack is Dukascopy ticks (via QuantDataManager or Tickstory) imported into an MT5 custom symbol with bid+ask preserved, time-shifted to the target broker's server offset; HistData is adequate for M1 OHLC sanity checks but not for spread-sensitive scalping because bars are bid-only and the timezone is fixed EST.
- XAUUSD is weaker: Dukascopy covers it as a CFD and QuantDataManager says commodity data are paid "no free source", so gold scalping validation will likely rely on the broker's own tick history or paid data.
- Any imported data that replaces the Spread column with a constant (as Tickstory's exporter did) reintroduces the fixed-spread problem even in "real ticks" mode; verify the Ask column survives import.

### Gaps
- No fetched source gives Dukascopy's or TrueFX's current pair list, exact start dates or export timezone options; the Tickstory homepage/FAQ could not be read (truncated). Session-open/close and weekend-gap behaviour of each feed was not quantified.
- No independent 2024–2026 audit comparing Dukascopy vs broker ticks for EURUSD/XAUUSD spread or gap statistics was found.

---

## KQ3. Evidence-based guidelines on sample size (trades), out-of-sample share, walk-forward windows and parameter robustness for short-term strategies

### Takeaway
Required trade count scales with the inverse square of the per-trade edge-to-noise ratio (n ≈ (t/SR_per_trade)²; a noisy scalper can need ~500+ trades before biases, then ×2), while the Bailey/López de Prado results show that the number of configurations tried matters as much as sample length: five years of daily data support no more than ~45 trials before the best result is expected to be a fluke. Walk-forward guidance (Pardo via secondary sources): 3:1 IS:OOS, ≥5 (ideally 8–12) windows, ≥30 trades per OOS window, WFE ≥50%.

### Cited Findings

**Multiple testing and backtest overfitting (primary papers)**
- Bailey & López de Prado (JPM 2014): "The Deflated Sharpe Ratio (DSR) corrects for two leading sources of performance inflation: Selection bias under multiple testing and non-Normally distributed returns." The expected maximum Sharpe ratio after N independent trials with zero true skill is approximately sqrt(V[SR]) × ((1−γ)·Z⁻¹[1−1/N] + γ·Z⁻¹[1−1/(N·e)]), γ ≈ 0.5772 (the paper's Python `getExpMaxSR` implements exactly this). DSR = PSR evaluated at that threshold, i.e. Z[(SR − SR*)·√(T−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²)], using skewness γ₃, kurtosis γ₄ and sample length T. — [Bailey & López de Prado, The Deflated Sharpe Ratio (SSRN 2460551; PDF at davidhbailey.com)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- Worked example in the paper: a strategist finds "many combinations yield an annualized SR of 2, with a particular one yielding a SR of 2.5 over a daily sample of 5 years" (T = 1250). After deflating for the number of trials and non-normal returns, "there is only a 90% chance that the true SR associated with this strategy is greater than zero", so the investor declines at 95% confidence; "Should the strategist have made his discovery after running only N=46 independent trials ... DSR would have been 0.9505"; with Normal returns the strategy would have passed up to N=88 trials. The paper's "when should we stop testing" answer is the 1/e optimal-stopping rule. — [Bailey & López de Prado, DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- Bailey, Borwein, Salehipour, López de Prado & Zhu (2016): "if only five years of daily stock market data are available as a backtest, then no more than 45 variations of a strategy should be tried on this data, or the resulting strategy will be overfit" (citing Bailey et al., Notices of the AMS 61(5), 2014, pp. 458–471, "Pseudo-Mathematics and Financial Charlatanism"). Their demonstration tool found an optimal in-sample SR of 1.59 that produced an out-of-sample SR of −0.18; a sample DSR of in-sample data was 0.3744. The Minimum Backtest Length (MinBTL) is proposed "as a metric to avoid selecting a strategy with a high SR on IS" data. — [Bailey et al., Backtest overfitting demonstration tools (PDF)](https://www.davidhbailey.com/dhbpapers/overfit-tools-at.pdf); summary at [CXO Advisory](https://www.cxoadvisory.com/big-ideas/backtest-overfitting-the-movies/)
- CXO's summary of DSR: holdout testing "doesn't eliminate this bias when multiple strategies are tested against the same holdout data"; the paper suggests estimating N by randomly testing ~37% (1/e) of justifiable alternatives then continuing until one beats all prior tests. Caveat: "theoretically justifiable" is ill-defined and researchers rarely document every alternative. — [CXO Advisory: Sharper Sharpe Ratio](https://cxoadvisory.com/big-ideas/sharper-sharpe-ratio)

**Trade-count rules of thumb**
- EliteTrader (globalarbtrader, 3 Mar 2021): required trades N = 4 × (s/m)² where m = mean trade, s = SD of trades (assumes t-stat 2); worked example of a series alternating +$300/−$250 → mean $25, SD ≈ $275 → N ≈ 484, "almost 500 trades"; multiply "by at least a factor of 2, if not more" for overfitting, survivorship, data snooping, vanishing edges and cost underestimation. Same Lazy Element: "t-stat = sqrt(n) * sharpe, so n = (t-stat / sharpe)^2". — [EliteTrader thread 356588 p.2](https://www.elitetrader.com/et/threads/minimum-number-of-trades-required-for-backtesting-results-to-be-trusted.356588/page-2)
- MQL5 blog (15 May 2025) tiers: 30–50 trades = proof of concept; 100–200 basic validation; 200–300 intermediate; 300–500 "confident performance metrics"; 1,000+ "robust optimization"; 2,000–5,000+ for "multi-phase validation (e.g., walk-forward)"; "The rarer your trades, the more years of data you need"; don't trust a one-year backtest with <50 trades; keep parameters "well below the number of trades". No formulas given. — [MQL5 Blog 762390: How Many Trades Do You Really Need?](https://www.mql5.com/en/blogs/post/762390)
- MQL5 article (12 Feb 2025): "at least 10 years and thousands of trades" for non-HF strategies; keep tunable parameters below five; prefer larger optimization steps and a "smooth, concave performance curve around the best value rather than a sharp spike"; hold back recent data at 7:3, 8:2 or 9:1; profit factor 1.2–1.5 is reasonable, above 1.5 "may indicate too small a sample or ignored costs"; LR correlation of equity >0.9; walk-forward "optional for most rule-based EAs" but necessary for ML strategies. — [MQL5 Article 16957: Robustness Testing on Expert Advisors](https://www.mql5.com/en/articles/16957)

**Walk-forward (Pardo-derived, secondary)**
- Backtrex (vendor blog citing Pardo 2008): WFE = Net OOS / Net IS × 100; thresholds <30% severe overfit, 30–50% marginal, 50–70% acceptable ("Pardo threshold"), 70–100% good, >100% "investigate period selection and regime mismatch"; split 3:1 (75/25) as "Pardo's recommended standard", 4:1 for scarce data, 2:1 conservative; minimum OOS window ≥30 trades; e.g. 2-year IS / 6-month OOS needs 5–6 years of data; at least 5 iterations, 8–12 more stable; rolling windows preferred for FX; rule of thumb "if optimized parameters exceed the square root of the IS trade count, overfitting risk becomes significant." Backtrex does not quote Pardo directly. — [Backtrex: Walk Forward Efficiency Ratio thresholds](https://backtrex.com/en/blog/walk-forward-efficiency-ratio-thresholds)
- quantammsim docs attribute WFE > 0.5 to Pardo (2008) as robust, ~1.0 ideal. — [quantammsim Walk-Forward Analysis](https://quantammsim.readthedocs.io/en/latest/tutorials/walk_forward_analysis.html)
- StrategyQuant Walk-Forward Matrix: runs several WF optimizations across a grid (example 5–15 runs × 20/30/40% OOS = 18 cells); a WF run "passes" when ≥80% of user-defined robustness components pass (example: 4/6 = 66% failed); a strategy is robust if a ≥3×3 cluster of neighbouring cells has more passes than fails (example rule 7 of 9); the reoptimization period at the cluster centre is chosen. — [StrategyQuant: Walk-Forward Matrix](https://strategyquant.com/doc/strategyquant/walk-forward-matrix/)

**MT5's built-in forward test (not rolling walk-forward)**
- MT5 "Forward" options: No, 1/2, 1/3, 1/4, Custom; "Always the second (latest) part of the total period is taken for the forward testing"; after optimization, the top 10% (full search) or 25% (genetic) of runs are re-run on the forward segment, "If the number of best runs is less than 256, the additional best runs are used for forward testing until their number reaches 256"; results in Back/Forward tabs. Stated purpose: "in an effort to avoid overfitting", "The better the results coincide, the more likely it is that the Expert Advisor will show good results in real trading." No rolling re-optimization is offered. — [MetaTrader 5 Help: Strategy Optimization](https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization), [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- A multi-part MQL5 series implements "Continuous Walk-Forward Optimization" on top of the tester by rebuilding reports in MQL5 (adding custom commission/slippage per symbol via CCCM) and scoring with profit factor, recovery factor, win rate, Sharpe-style ratio, Altman Z-score and historical VaR. — [MQL5 Article 7452 (18 Feb 2020)](https://www.mql5.com/en/articles/7452)
- Third-party guides claiming MT5 "runs successive cycles automatically" were not confirmed by the official help. — [Backtrex MT5 tutorial](https://backtrex.com/en/blog/metatrader-5-strategy-tester-backtesting-tutorial)

**Tester statistics definitions (for reading reports)**
- Sharpe in the tester assumes zero risk-free rate; LR Correlation near 1 = smooth equity, near 0 = random; Z-score >3 or <−3 indicates serial dependence of wins/losses; AHPR vs GHPR; Recovery Factor = profit / max drawdown. — [MetaTrader 5 Help: Testing Report](https://www.metatrader5.com/en/terminal/help/algotrading/testing_report)

### Inferences
- A scalper with, e.g., 55% win rate and 1:1 R:R has per-trade SR ≈ 0.10, so by n = (2/0.10)² it needs ~400 trades for t ≈ 2 before any multiplier; the EliteTrader "×2 for biases" rule pushes this to ~800–1,000, consistent with the MQL5 blog's 1,000+ tier for optimization.
- The DSR logic implies every optimizer pass counts as a trial: a genetic run over thousands of combinations on 2–3 years of M1 data is in the regime where the top result is expected to be a fluke unless the strategy class has very few justifiable configurations.
- Because MT5's native forward test is a single holdout (not rolling), a real walk-forward requires either manual re-optimization per window, the MQL5 CWFO code, or StrategyQuant; the Backtrex/Pardo-style numbers (≥5 windows, ≥30 trades each) translate for an M1 scalper into many months of real-tick data per window.

### Gaps
- Pardo's thresholds (WFE 50%, 3:1 split, √trades parameter rule) are all secondhand; the book itself was not consulted.
- In the DSR paper's worked example the values of N, V[SR], skewness and kurtosis were lost in PDF text extraction; only T = 1250, SR 2.5, the 90% result and the N = 46 / N = 88 thresholds are legible.
- QuantStart's backtesting-bias articles (503) and Robot Wealth/Quantpedia pieces could not be fetched; no FX-scalping-specific published PBO/CSCV case study was found.

---

## KQ4. Published data on how much scalping EA performance degrades from backtest to live (slippage, spread variability, latency, requotes), 2022–2026

### Takeaway
No controlled study quantifying typical backtest-to-live degradation for retail scalping EAs was found; the only quantified 2026 case (48 matched trades) showed a 20% profit shortfall of which ~75% came from entry/exit fill prices and 0% from commission, and a 2026 gold tick-scalping study found the only surviving edge died above ~50 ms latency. Practitioners consistently report that divergence is largest for tick scalpers and near zero for H4 open-price EAs.

### Cited Findings
- 48-trade matched comparison (Oct 2026): backtest €726.58 vs live €580.96 (gap −€145.62, i.e. −20%); attribution: entry prices −€77.77 (53%), exit prices −€32.23 (22%), timing (two trades opened at different moments) −€18.76 (13%), one backtest trade with no live counterpart −€16.59 (11%), commission −€0.27 (0%), swap/conversion €0.00. "EAs targeting small moves are hit hardest, since a fraction of a pip is a large share of their profit per trade." The author's method: match trades not totals, normalize lot size, separate prices from costs, count missing/extra trades, verify the tester/server clock offset; then stress-test with measured slippage or "2× STRESS". (Promotes the author's Strategy Ledger Pro; single account.) — [MQL5 Blog 777157: Why Your EA Does Worse Live Than in the Backtest (9 Oct 2026)](https://www.mql5.com/en/blogs/post/777157)
- Gold tick scalping research EA (Oct 2026): typical broker spread ~10–11 points on XAUUSD; "Nearly all of these micro edges were smaller than the spread"; only post-spike continuation survived, and only with tester delay ≤~50 ms; author's ping 52 ms; recommends comparing 0 ms vs real-ping runs: "A strategy that only works at 0 ms is not viable." — [MQL5 Blog 777925: I Tested Tick-Level Scalping on Gold (17 Oct 2026)](https://www.mql5.com/en/blogs/post/777925)
- Dec 2025 blog: real latency "ranging from about 5 ms to 300 ms during volatile moments" as a random sum of VPS, network, broker queueing and slippage; recommends checking entries still work "with 2-3 pips of worse execution" and forward-testing "months, not days". — [MQL5 Blog 765944 (6 Dec 2025)](https://www.mql5.com/es/blogs/post/765944)
- MQL5 forum "EA backtesting vs real life" (2013–2016): Alexey Volchanskiy: tester results for scalping EAs differ greatly from a real account while H4 open-price EAs match; Ndumiso Mavuso: a scalper "may enter many trades on large spikes in the tester, while live it may fill none during the same spike"; Drazen Penic: live execution delay "anywhere from a third of the second upwards" (2016 figure); Stuart Browne: treat the tester as a "logic tester". No numbers. — [MQL5 Forum 10911](https://www.mql5.com/en/forum/10911)
- MetaQuotes' own mode comparison shows the same EA flipping from +169 to −467 to −97 purely by tick-model choice (see KQ1), which is a lower bound on how fragile short-term results are to price-path assumptions. — [MQL5 Article 2612](https://www.mql5.com/en/articles/2612)
- r/algotrading (2025–2026 threads via mirror; snippets): posters model slippage as "a distribution tied to spread, volatility, and queue position, then assume the tails will be worse live"; one adds "1-7 bps random but seeded slippage ... based on what I was seeing in my live trades"; another adds a fixed 1–2 tick penalty; swing FX traders report "virtually no slippage"; the fetched thread (late Aug 2025) contains no quantified FX scalping live-vs-backtest figures. — [r/algotrading mirror thread 1s9kbip](https://reddit.sentinel-team.org/posts/1s9kbip/snapshots/2026-04-03T17%3A02%3A31.736953Z), [r/algotrading mirror timeline](https://reddit.sentinel-team.org/subreddits/algotrading/snapshots/2026-03-05T08%3A50%3A14.201339Z)
- Vendor red-flag anecdote: "the backtest showed a 90% win rate. The live account shows 40%." — [MQL5 Blog 766446 / search snippet](https://www.mql5.com/en/blogs/post/766446)

### Inferences
- The one quantified case implies a rule of thumb that fills (spread+slippage+price mismatch) rather than commissions explain most of the gap; for a 5–10 pip target, a 0.3–0.5 pip average fill shortfall per side is a 6–20% haircut on gross profit per trade, consistent with the observed −20%.
- The ~50 ms viability threshold from the gold study and the 5–300 ms latency range imply that tick-level scalps are viable only from a VPS co-located near the broker, and that the tester's 0 ms default is the single most optimistic assumption in any scalping backtest.

### Gaps
- No peer-reviewed or multi-account dataset quantifying backtest-vs-live degradation for MT5 scalping EAs (2022–2026) was found; Myfxbook-style aggregate comparisons could not be searched after the budget ran out.
- No data on requote frequency on MT5 market-execution accounts was found (FXCM's and FxPro's reports cover slippage, not requotes, except FxPro's older "re-quote rates").

---

## KQ5. How to model costs realistically for a 5–10 pip scalp (variable spread by hour, commission per lot, slippage distribution, swap) and what brokers' execution statistics imply

### Takeaway
Build a per-trade "cost budget" in points (spread at the hour you trade + commission converted to points + a slippage allowance), run real-tick tests across a spread-gate matrix and at 0 ms vs measured ping, and treat broker-published slippage (e.g. FXCM 2024: 54.5% none / 30.8% positive / 14.6% negative, but 57% of stop orders negative) as the optimistic bound because stops and news-time fills skew negative.

### Cited Findings
- Spread budget method (Aug 2026): compute `spread_points = round((ask − bid)/point)` from the latest tick immediately before sending the order; gate new entries only (not exits); log every blocked signal because "a filter that removes 2% of entries differs greatly from one that removes 40%"; budget = average trade (points) − realized bid-ask cost − commission in point-equivalents − slippage allowance, using one price convention so spread isn't double counted; stress matrix of five runs: real ticks at intended gate, tighter gate, wider gate, higher commission + slippage allowance, and a report of signals/blocked/executed/avg trade/PF/DD; "If only one exact value works, the filter may be fitting noise"; "A spread filter cannot create an edge." — [MQL5 Blog 774963: How to Build a Spread Budget for an M1 Expert Advisor (29 Aug 2026)](https://www.mql5.com/en/blogs/post/774963)
- Costs in the MT5 tester are set via the custom-symbol (money-sign) settings; example broker comparison for EURUSD: B-book ~1 pip spread no commission vs ECN ~$7 per lot round-trip plus ~0.1 pip spread; a 10-pip TP with ~1 pip total cost gives up ~10% per trade; simulation with 55% win rate, 1:1 R:R shows how 10% cost per trade erodes the curve. Author argues slippage matters most for news/high-volatility entries because positive and negative slippage otherwise tend to offset. — [MQL5 Article 16957 (12 Feb 2025)](https://www.mql5.com/en/articles/16957)
- Variable spread effect: an EA profitable at fixed 10 points lost with variable spread due to widening at news, session opens and rollover. — [MQL5 Forum 212322 p.2 (Apr 2026)](https://www.mql5.com/en/forum/212322/page2)
- Gold: typical 10–11 point spread; edges smaller than spread; latency threshold ~50 ms. — [MQL5 Blog 777925](https://www.mql5.com/en/blogs/post/777925)
- Latency in tester: use "Fixed Delay" equal to measured ping (terminal shows ping bottom-right), compare with 0 ms. — [MQL5 Blog 777925](https://www.mql5.com/en/blogs/post/777925), [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- Pips profit mode drops swap and commission entirely — do not use it for cost-sensitive tests. — [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- MT4/TDS specifics: enable "Reproducible slippage"; never leave spread on "Current"; use quote currency as backtest currency to avoid conversion drift. — [Tick Data Suite support](https://eareview.freshdesk.com/support/solutions/articles/19000063735-different-backtest-results)
- Broker execution statistics, FXCM 2024 (self-reported): no slippage 54.53%, positive 30.83%, negative 14.64%; limit/limit-entry orders 74.58% positive slippage; stop/stop-entry orders 57.42% negative slippage; average execution speed 0.017 s (Jan–Sep 2025, CFDs), measured from order receipt to execution excluding internet latency. — [FXCM Execution Transparency](https://www.fxcm.com/eu/execution/transparency/)
- FXCM July 2018: 63.91% none / 25.86% positive / 10.24% negative. — [Finance Magnates, FXCM July 2018](https://www.financemagnates.com/forex/brokers/fxcm-reports-spreads-execution-quality-metrics-for-july-2018/)
- FxPro 2016 (old, search snippet): full-year positive 37.43%, at quote 39.11%, negative 23.46%; Q1 2016 positive 46.93%, at quote 31.81%, negative 21.26%. — [FxPro Q4/year-end 2016 execution statistics](https://www.fxpro.com/press-release/fxpro-announces-q4-and-year-end-execution-statistics-for-2016)
- Reddit practitioners: slippage as a seeded distribution of 1–7 bps or a fixed 1–2 tick penalty per trade. — [r/algotrading mirror timeline](https://reddit.sentinel-team.org/subreddits/algotrading/snapshots/2026-03-05T08%3A50%3A14.201339Z)
- Monte Carlo retests can randomize spread and slippage as "properties that can be changed in retests" (StrategyQuant). — [StrategyQuant: Types of robustness tests](https://strategyquant.com/doc/strategyquant/types-of-robustness-tests-in-sqx/)

### Inferences
- Broker stats are dominated by limit orders receiving positive slippage; a scalper's stop-loss exits sit in the category that is net negative (57% of FXCM stop orders), so a realistic model should apply asymmetric slippage: ~0 or slightly positive on limit entries, negative on stop exits and market entries during news.
- A defensible MT5 protocol: (1) real ticks on the target broker server with its real spread history; (2) commission entered in custom symbol settings per the live account type; (3) Fixed Delay = measured ping × 1.5–2; (4) a second run with spread gate wider by the broker's news-time spread; (5) a hand-applied per-trade slippage penalty (e.g. 0.3–0.5 pip on EURUSD, more on gold) since MT5 has no explicit slippage distribution setting; the strategy must survive all of these, not just the default run.
- Because MT5's only slippage mechanism is price movement during the delay, strategies with limit entries will show almost no slippage in the tester even with delays — a separate penalty or Monte Carlo cost perturbation (StrategyQuant or spreadsheet) is required.

### Gaps
- No fetched source gives hour-by-hour spread tables for EURUSD/XAUUSD at specific brokers in 2025–2026; the user must record them from their own terminal or tick history.
- Admiral Markets' execution statistics page (404) and IC Markets/Pepperstone/Darwinex execution reports could not be retrieved; FXCM is the only current (2024–2025) primary dataset found.
- Swap modeling for scalpers (overnight holds) was not covered by any fetched source beyond MT5's note that swaps are applied unless Pips mode is used.

---

## KQ6. A sound forward-testing protocol (demo duration, micro-live, metrics, stopping rules)

### Takeaway
No single authoritative protocol with numeric durations was found; the consistent practitioner guidance is: backtest is a filter → demo on the intended broker for months (not days) → small live → compare at the trade level (matched trades, not totals) and extend until the live sample is statistically meaningful, with a pre-set stop rule based on backtested drawdown.

### Cited Findings
- "Use backtests as an initial filter only"; "Forward test on a live demo with your intended broker ... months, not days"; "Test slippage tolerance ... 2-3 pips of worse execution"; "If it only works on a perfect feed, it doesn't work." — [MQL5 Blog 765944 (Dec 2025)](https://www.mql5.com/es/blogs/post/765944)
- Seven-check workflow ends with "Forward validation: Demo → small live → stability sample size"; no durations given. — [MQL5 Blog 766453 (7 Jan 2026)](https://www.mql5.com/en/blogs/post/766453)
- "Live or paper trading with small size to test slippage, spreads, and execution delays" after OOS and outlier checks; monitor profit factor, max equity drawdown, LR correlation, long/short win rates; monthly-return table to detect time outliers. — [MQL5 Article 16957 (Feb 2025)](https://www.mql5.com/en/articles/16957)
- Trade-level reconciliation method for the live phase: match each live trade to its backtest twin, normalize lot size, separate price effects from costs, count missing/extra trades, verify clock offset. — [MQL5 Blog 777157 (Oct 2026)](https://www.mql5.com/en/blogs/post/777157)
- Tickstory support also recommends comparing "each live trade with its simulated counterpart" and notes a strategy "may be too sensitive to some settings (such as spread) which could be different in your live environment." — [Tickstory support: Inaccurate Results](https://support.tickstory.com/viewtopic.php?p=12359)
- Repeat tester and demo checks "in the environment you plan to use" since digits, point size, spread, commission and execution differ by broker/account type. — [MQL5 Blog 774963](https://www.mql5.com/en/blogs/post/774963)
- Sample-size tiers applicable to a forward sample: 100–200 trades for basic validation, 300–500 for confident metrics. — [MQL5 Blog 762390](https://www.mql5.com/en/blogs/post/762390)
- Titan FX's forward-testing page describes only MT5's Forward 1/2 split and manual demo testing; it gives no durations or go-live criteria. — [Titan FX Research: Forward testing](https://research.titanfx.com/auto-trading/forward-testing)
- Backtrex: do not re-tune parameters after a poor forward result, since that turns the forward period into in-sample data. — [Backtrex MT5 tutorial](https://backtrex.com/en/blog/metatrader-5-strategy-tester-backtesting-tutorial)

### Inferences
- Combining the sources: for a scalper producing ~5–20 trades/day, a 100–200-trade demo sample is reachable in 2–6 weeks, but the "months" guidance exists because spread/latency regimes (news weeks, holidays, rollover) need to be sampled; a minimum of ~3 months demo then ~3 months micro-live (smallest lot) is the smallest program consistent with the cited advice.
- Stop rules should be fixed before starting: e.g. halt if live drawdown exceeds the backtest's maximal drawdown, if matched-trade fill shortfall exceeds the slippage allowance used in the backtest, or if live/backtest trade counts diverge materially (missing-trade rate), since each of these is a diagnosed cause in the 48-trade study.

### Gaps
- No experienced-quant or prop-firm source with explicit numbers (weeks on demo, trades before live, kill thresholds) was retrievable; quantifiedstrategies.com (bot wall) and QuantStart (503) failed. This section is a synthesis of qualitative guidance.

---

## KQ7. Red flags of a curve-fit or misleading scalping backtest / vendor claim

### Takeaway
The repeatable red flags are: generated-tick or MT4 "99% quality" tests presented as proof, fixed or zero spread and no commission, results reported on the same period that was optimized, 0 ms execution, tiny targets with very high win rates and large hidden stops, 20–100+ inputs, equity curves that climb without drawdown (grid/martingale/"recovery mode"), and vendors risking far less live than they charge.

### Cited Findings
- Buying red flags: huge stop losses relative to take profits "which can hide frequent large losses behind a high win rate"; sellers "who risk only $10-$100 in their signal while selling the EA for $1,000 or more"; "new accounts with few trades and a 100% win rate"; martingale/hedging/averaging/grid as high risk; EA without an ONNX file but >~1 MB may hide hard-coded model parameters; profit factor >1.5 "may indicate too small a sample or ignored costs". — [MQL5 Article 16957 (Feb 2025)](https://www.mql5.com/en/articles/16957)
- Marketing red flags: "90% win rate", "Never loses", "Guaranteed monthly income", "$200 into $20,000"; grid tells: "recovery mode"/"smart averaging", many stacked same-direction trades, floating drawdown that "grows quietly for weeks", "equity curve that looks too smooth for too long"; martingale tells: "double lot after loss", high win rate with rare large losses; over-optimization tells: "100+ inputs", near-zero drawdown, "breaks when spread or slippage changes slightly", "depends on one broker's exact conditions". (Author sells EAs; affiliate links.) — [MQL5 Blog 766446 (25 Dec 2025)](https://www.mql5.com/en/blogs/post/766446)
- Seven robustness checks: spread increases (collapse = no edge), slippage (esp. breakouts, XAUUSD), market regimes, parameter sensitivity ("sweet spot" settings), multiple time windows ("consistent logic, not just consistent profit"), no recovery mechanics, forward validation. — [MQL5 Blog 766453 (7 Jan 2026)](https://www.mql5.com/en/blogs/post/766453)
- (Search snippets, vendor blogs) grid/martingale curves "climb steadily with almost no visible drawdown, then collapse vertically"; vendors "run all combinations through Strategy Tester ... select the combination with the smoothest equity curve"; "overfitted EAs ... many (20+) [parameters] without clear logical reason"; one blog's rule of thumb that an OOS drop >40% vs IS is likely curve-fit (heuristic, unverified). — [MQL5 Blog 767446](https://www.mql5.com/en/blogs/post/767446), [MQL5 Blog 761635](https://www.mql5.com/en/blogs/post/761635)
- Mode-specific tells from official docs: "1 minute OHLC" produces "an unrealistically smooth equity curve" and a "Testing Grail"; "Open prices only" lets stops trigger at unrealistic prices; Pips mode removes swap and commission; "No Delay" means ideal fills without requotes. — [MQL5 Article 239](https://www.mql5.com/en/articles/239), [MQL5 Book](https://www.mql5.com/en/book/automation/tester/tester_ticks), [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing)
- Statistical tells: an in-sample SR of 1.59 turning into −0.18 OOS; a 2.5 Sharpe over 5 years being rejected once the number of trials is disclosed; "Academic articles and investment proposals almost never disclose the number of trials involved" — the same applies to EA vendors. — [Bailey et al. overfit tools](https://www.davidhbailey.com/dhbpapers/overfit-tools-at.pdf), [Bailey & López de Prado DSR](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- Statistical tells from the tester report: Z-score beyond ±3 indicates non-random win/loss streaks (typical of grid/martingale sequencing); LR correlation ≈1 with no drawdown is suspicious for a scalper. — [MetaTrader 5 Help: Testing Report](https://www.metatrader5.com/en/terminal/help/algotrading/testing_report)
- Grid/martingale fragility: "A single trade closing at a different time or price can cascade into large differences by the end of the test." — [Tick Data Suite support](https://eareview.freshdesk.com/support/solutions/articles/19000063735-different-backtest-results)
- Monte Carlo acceptance example: original net profit $6,990 vs $3,943 at 95% confidence ("a 5% chance the strategy would earn less than $3,943"); filter rejecting strategies whose MC net profit < 80% of original. Trade-order shuffling keeps net profit but changes drawdown; skip-trades simulates missed fills. — [StrategyQuant: Monte Carlo tests](https://strategyquant.com/doc/monte-carlo-tests/)

### Inferences
- A vendor-proof checklist derived from the above: (1) Which mode? Demand "Every tick based on real ticks" with the broker/server named and the real-tick percentage visible; (2) Which spread/commission? Demand variable spread with commission matching the account type, or reject; (3) Delay? 0 ms = reject for scalpers; (4) Period? Demand the optimization window and a separate forward window, and the number of optimization passes; (5) Trades? ≥ several hundred per regime; (6) Shape? Reject curves with no drawdown, growing floating loss, or lot escalation; (7) Live proof? A verified live account on the same broker whose per-trade results reconcile to the backtest.
- Vendor backtest screenshots on MQL5 Market are typically produced on the vendor's broker; the official docs make clear that real-tick depth and spread history are server-specific, so the same EA must be re-tested on the buyer's server before any inference.

### Gaps
- The ">40% OOS drop" and "20+ parameters" thresholds come from vendor blog snippets and were not independently validated.
- No regulator or marketplace (MQL5 Market) rule text on backtest disclosure was found.

---

## KQ8 (tools). Free/open tools and what each can and cannot model

### Takeaway
MT5's built-in tester is the only free tool that replays broker ticks with real spread and an execution delay; StrategyQuant adds Monte Carlo/walk-forward matrices (paid, free QuantDataManager); Forex Tester sells 23 years of ticks but does not run MT4/MT5 EAs; Python libraries model costs as flat fractions and treat each bar as a black box, which is inadequate for intrabar scalping logic unless fed tick data.

### Cited Findings
- MT5 Strategy Tester: modes, real ticks, Fixed/Random delay, forward segment, custom symbols with spread/commission overrides; Cloud Network unavailable for custom symbols. — [MetaTrader 5 Help: Testing](https://www.metatrader5.com/en/terminal/help/algotrading/testing), [Custom Instruments](https://www.metatrader5.com/en/terminal/help/trading_advanced/custom_instruments)
- StrategyQuant X: Monte Carlo trade manipulation (resampling/exact shuffle, random skip), retests (randomize history by % of ATR, parameters by % with example 60 ±10% → 54–66, starting bar), confidence levels 50–100, ~0.5 s per backtest → 100 sims ≈ 50 s; IS/OOS, OOS/IS ratios, multi-market, Walk-Forward Matrix. — [StrategyQuant: Monte Carlo](https://strategyquant.com/doc/monte-carlo-tests/), [Types of robustness tests](https://strategyquant.com/doc/strategyquant/types-of-robustness-tests-in-sqx/), [Walk-Forward Matrix](https://strategyquant.com/doc/strategyquant/walk-forward-matrix/)
- QuantDataManager: free Dukascopy tick/M1 downloader with gap/spike review, timezone clones, MT4 FXT/HST and MT5 export. — [QuantDataManager](https://strategyquant.com/quantdatamanager)
- Forex Tester: "Up to 23y of ticks", EURUSD and XAUUSD history from 6 May 2003, lowest timeframe 1 minute (second-based planned), 283 symbols, $139–$299/year promos, 30-day refund; mentions swaps/spreads/commissions but no explicit variable-spread or slippage model; MT4/MT5 EA execution not stated (own "Trading robots"). Vendor claims "highly accurate" without methodology. — [Forex Tester](https://forextester.com/)
- Tick Data Suite: MT4 only (MT5 beta), variable spread, slippage, commission, from $37.9/month. — [Tick Data Suite](https://eareview.net/tick-data-suite)
- backtesting.py: `commission` (rate, (fixed, relative) tuple, or callable), `spread` (constant relative bid-ask, docs suggest 0.0002 for commission-free forex), `margin`, `trade_on_close`, `hedging`, `exclusive_orders`; market orders fill at next bar's open; the docs do not specify intrabar order of SL/TP evaluation. — [backtesting.py API](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)
- vectorbt: `fees` (fraction of order value), `fixed_fees` (cash per order), `slippage` (fraction of price), `sl_stop`/`tp_stop` as fractions (0.01 = 1%), stop signals have priority within a bar, high/low used only for stops, "Each bar is effectively a black box, so only the open and close are reliable"; benchmark ignores fees/slippage. — [vectorbt Portfolio API](https://vectorbt.dev/api/portfolio/base/)
- Python helper patterns from MQL5: monthly-return tables and symbol pie charts from the saved Excel tester report (pandas/seaborn). — [MQL5 Article 16957](https://www.mql5.com/en/articles/16957)

### Inferences
- For a scalper, Python OHLC backtesters on M1 bars cannot resolve which of SL/TP was hit first inside a bar; either run them on tick data (vectorbt/backtesting.py accept any bar series, so 1-second or tick-aggregated bars can be used) or use them only for portfolio-level Monte Carlo on the MT5 trade list.
- The cheapest rigorous stack in 2026: MT5 real-tick tester on the target broker (free) + QuantDataManager/Dukascopy ticks for a second-feed check (free) + a spreadsheet or Python Monte Carlo on the exported deal list (free); StrategyQuant or TDS only if automated walk-forward matrices or MT4 variable spread are required.

### Gaps
- Backtrader documentation was not fetched; Forex Tester's handling of variable spread/slippage and its data vendor are not disclosed on its page; the vectorbt `StopExitPrice` enum and intrabar check order were not in the fetched excerpt.
