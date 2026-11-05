//+------------------------------------------------------------------+
//|                                          LondonRangeBreakout.mq5 |
//|        Asian-range / London-open breakout research EA for MT5    |
//+------------------------------------------------------------------+
/*
   STRATEGY SOURCE AND DISCLAIMER
   ------------------------------
   This Expert Advisor is a RESEARCH TOOL. It mechanises the "Asian range /
   London-open breakout" rule set as described in public MQL5 blog write-ups
   of the gold (XAUUSD) London-range breakout published in 2025-2026
   (Asian-session high/low box, stop orders or close-beyond entries at the
   London open, stop at the opposite side of the range or an ATR multiple,
   fixed-R target, break-even step, range-width filter, hard time cutoff).

   NO PERFORMANCE IS IMPLIED. No win rate, profit factor, return or drawdown
   is claimed for this code. Published results for this family of strategies
   are vendor-run, mostly without stated spread/commission, and the only
   independent forex test found was a net loser. Whatever you read elsewhere,
   the only numbers that matter are the ones YOU produce on YOUR broker's
   data, with real ticks, realistic spread, commission and slippage, and a
   genuine out-of-sample (forward) period.

   You must:
     * test on your own broker's symbol with "Every tick based on real ticks",
     * include the broker's real spread (or a conservative custom spread) and
       commission in the tester,
     * align every hour input to your broker's server time zone (see README),
     * treat fewer than ~300 trades as inconclusive,
     * never run this on a live account without weeks of forward testing.

   The author of this file makes no warranty of any kind. Use at your own risk.

   Technical notes:
     * No DLLs, no file I/O, no network calls.
     * Single-position logic; works on hedging and netting accounts.
     * Fill detection by OnTradeTransaction plus polling in OnTick (polling is
       the authoritative path and is robust in the Strategy Tester).
*/
#property copyright   "Research tool - no warranty, no performance claim"
#property link        "research-only build, no distribution link"
#property version     "1.00"
#property description "Asian-range / London-open breakout with ATR-based risk."
#property description "Research tool for the MT5 Strategy Tester. Not a profit guarantee."

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Trade\AccountInfo.mqh>

//+------------------------------------------------------------------+
//| Enumerations                                                     |
//+------------------------------------------------------------------+
enum ENUM_ENTRY_MODE
  {
   ENTRY_STOP_ORDERS  = 0,   // Stop orders at range edges (OCO)
   ENTRY_CLOSE_BEYOND = 1    // Market entry on bar close beyond range + k*ATR
  };

enum ENUM_SL_MODE
  {
   SL_OPPOSITE_RANGE = 0,    // Opposite side of the range (capped by MaxSLPctOfPrice)
   SL_ATR            = 1     // SLATRMult x ATR(ATRPeriod)
  };

enum ENUM_RANGE_SOURCE
  {
   RANGE_M1       = 0,       // Completed M1 bars
   RANGE_CHART_TF = 1        // Completed bars of the chart timeframe
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Range definition (broker server time unless UseServerTime=false) ==="
input int               RangeStartHour          = 0;      // Range start hour (0-23)
input int               RangeStartMinute        = 0;      // Range start minute (0-59)
input int               RangeEndHour            = 7;      // Range end hour (0-23)
input int               RangeEndMinute          = 0;      // Range end minute (0-59)
input ENUM_RANGE_SOURCE RangeSource             = RANGE_M1; // Bars used to build the range
input int               MinRangeBars            = 30;     // Minimum bars inside the range (data sanity check)
input bool              UseServerTime           = true;   // true: hour inputs are server time (recommended)
input int               ServerToUTCOffsetHours  = 2;      // Server minus UTC, hours (for logs; conversion only if UseServerTime=false)

input group "=== Trading window ==="
input int               TradeStartHour          = 7;      // Entries allowed from this hour
input int               TradeEndHour            = 10;     // Entries allowed before this hour (exclusive)
input int               ForceCloseHour          = 12;     // Close positions and delete pendings at this hour
input bool              OneTradePerDay          = true;   // Max one fill per day
input int               MaxTradesPerDay         = 2;      // Used only when OneTradePerDay=false

input group "=== Entry ==="
input ENUM_ENTRY_MODE   EntryMode               = ENTRY_STOP_ORDERS; // Entry mode
input int               BufferPoints            = 20;     // Stop-order buffer beyond range, points (XAUUSD 2-digit: 20 = $0.20; EURUSD 5-digit: 20 = 2 pips)
input bool              CancelOppositeOnFill    = true;   // OCO: delete the other stop when one fills
input double            BreakoutATRMult         = 0.15;   // CLOSE_BEYOND: close must exceed range by k*ATR
input int               ATRPeriod               = 14;     // ATR period (chart timeframe)

input group "=== Range filters (0 = disabled) ==="
input double            MinRangePctOfPrice      = 0.30;   // Skip day if range < this % of price
input double            MaxRangePctOfPrice      = 1.60;   // Skip day if range > this % of price
input int               MinRangePoints          = 0;      // Skip day if range < this many points
input int               MaxRangePoints          = 0;      // Skip day if range > this many points

input group "=== Stop loss / take profit / management ==="
input ENUM_SL_MODE      SLMode                  = SL_OPPOSITE_RANGE; // Stop-loss mode
input double            MaxSLPctOfPrice         = 0.60;   // Cap on SL distance, % of price (0 = no cap)
input double            SLATRMult               = 0.8;    // SL_ATR: SL distance = k*ATR
input double            TakeProfitR             = 1.5;    // Take profit in R multiples (0 = no TP)
input double            MoveToBreakevenAtR      = 1.0;    // Move SL to entry at this R (0 = off)
input int               BreakevenOffsetPoints   = 0;      // Break-even SL offset beyond entry, points
input double            TrailATRMult            = 0.0;    // ATR trailing stop multiple (0 = off)

input group "=== Filters ==="
input int               MaxSpreadPoints         = 80;     // Skip entries if spread > this (points)
input string            NewsBlackoutWindows     = "";     // e.g. "13:25-13:35;14:55-15:05" (schedule time, HH:MM-HH:MM;...)

input group "=== Risk sizing ==="
input double            RiskPercent             = 1.0;    // Risk per trade, % of balance
input double            FixedLots               = 0.0;    // >0 overrides RiskPercent
input bool              SkipIfStopsLevelViolated= true;   // true: skip if SL < stops level; false: widen SL

input group "=== Execution ==="
input long              MagicNumber             = 20261105; // Magic number
input int               DeviationPoints         = 30;     // Max slippage, points
input string            TradeComment            = "LRB";  // Order comment
input bool              PrintVerbose            = true;   // Verbose logging

//+------------------------------------------------------------------+
//| Constants                                                        |
//+------------------------------------------------------------------+
#define MAX_PLACE_ATTEMPTS   10
#define MAX_ENTRY_ATTEMPTS   10
#define MAX_RANGE_ATTEMPTS   3
#define LOG_PREFIX           "[LRB] "

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade          g_trade;
CSymbolInfo     g_symbol;
CPositionInfo   g_position;
COrderInfo      g_order;
CAccountInfo    g_account;

int             g_atrHandle          = INVALID_HANDLE;
long            g_shiftSec           = 0;        // server time = schedule time + g_shiftSec

// schedule, seconds since midnight of the schedule day
int             g_rangeStartSec      = 0;
int             g_rangeEndSec        = 0;
int             g_tradeStartSec      = 0;
int             g_tradeEndSec        = 0;
int             g_forceCloseSec      = 0;
bool            g_rangeOvernight     = false;

// per-day state
long            g_dayIndex           = -1;
datetime        g_dayStartLogical    = 0;
datetime        g_srvRangeStart      = 0;
datetime        g_srvRangeEnd        = 0;
datetime        g_srvTradeStart      = 0;
datetime        g_srvTradeEnd        = 0;
datetime        g_srvForceClose      = 0;
bool            g_rangeReady         = false;
int             g_rangeAttempts      = 0;
double          g_rangeHigh          = 0.0;
double          g_rangeLow           = 0.0;
bool            g_dayValid           = false;
bool            g_dayDone            = false;    // no more entries today
bool            g_tradedToday        = false;
int             g_tradesToday        = 0;
bool            g_posOpenSeen        = false;
bool            g_buySideDone        = false;
bool            g_sellSideDone       = false;
bool            g_entryPlaced        = false;
int             g_placeAttempts      = 0;
int             g_entryAttempts      = 0;
bool            g_cancelPendingRequested = false;
bool            g_forceCloseLogged   = false;
bool            g_tradeEndLogged     = false;
double          g_dayProfit          = 0.0;
double          g_lastRiskDistance   = 0.0;
datetime        g_lastBarTime        = 0;
datetime        g_lastSpreadLog      = 0;
datetime        g_lastNewsLog        = 0;
string          g_dayVerdict         = "";

// news blackout windows (minutes since midnight, schedule time)
int             g_nbStart[];
int             g_nbEnd[];
int             g_nbCount            = 0;

// symbol / account properties
bool            g_expirationSupported = false;
ENUM_ORDER_TYPE_FILLING g_filling    = ORDER_FILLING_FOK;
int             g_volDigits          = 2;
bool            g_isHedging          = false;

//+------------------------------------------------------------------+
//| Logging helpers                                                  |
//+------------------------------------------------------------------+
void LogMsg(const string msg)
  {
   Print(LOG_PREFIX, TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS), " ", msg);
  }

void LogV(const string msg)
  {
   if(PrintVerbose)
      LogMsg(msg);
  }

string PriceStr(const double price)
  {
   return DoubleToString(price, g_symbol.Digits());
  }

string LotsStr(const double lots)
  {
   return DoubleToString(lots, g_volDigits);
  }

string HHMM(const int secOfDay)
  {
   int s = secOfDay;
   while(s < 0) s += 86400;
   s = s % 86400;
   return StringFormat("%02d:%02d", s / 3600, (s % 3600) / 60);
  }

//+------------------------------------------------------------------+
//| Time helpers: "schedule" time is server time unless               |
//| UseServerTime=false, in which case inputs are UTC and converted   |
//| with ServerToUTCOffsetHours.                                      |
//+------------------------------------------------------------------+
datetime ServerToLogical(const datetime srv)
  {
   return (datetime)((long)srv - g_shiftSec);
  }

datetime LogicalToServer(const datetime lg)
  {
   return (datetime)((long)lg + g_shiftSec);
  }

bool InTradeWindow(const int secOfDay)
  {
   return (secOfDay >= g_tradeStartSec && secOfDay < g_tradeEndSec);
  }

//+------------------------------------------------------------------+
//| Volume / price normalisation                                     |
//+------------------------------------------------------------------+
int VolumeDigits(const double step)
  {
   int d = 0;
   double s = step;
   while(d < 8 && MathAbs(s - MathRound(s)) > 1e-9)
     {
      s *= 10.0;
      d++;
     }
   return d;
  }

double NormalizePrice(const double price)
  {
   double p  = price;
   double ts = g_symbol.TickSize();
   if(ts > 0.0)
      p = MathRound(p / ts) * ts;
   return NormalizeDouble(p, g_symbol.Digits());
  }

double NormalizeLotsDown(const double lots)
  {
   double step = g_symbol.LotsStep();
   double maxV = g_symbol.LotsMax();
   if(step <= 0.0)
      step = 0.01;
   double n = MathFloor(lots / step + 1e-8);
   double v = NormalizeDouble(n * step, g_volDigits);
   if(maxV > 0.0 && v > maxV)
      v = maxV;
   return v;
  }

//+------------------------------------------------------------------+
//| Input validation                                                 |
//+------------------------------------------------------------------+
bool ValidateInputs()
  {
   bool ok = true;
   if(RangeStartHour < 0 || RangeStartHour > 23 || RangeEndHour < 0 || RangeEndHour > 23)
     { Print(LOG_PREFIX, "Range hours must be 0-23"); ok = false; }
   if(RangeStartMinute < 0 || RangeStartMinute > 59 || RangeEndMinute < 0 || RangeEndMinute > 59)
     { Print(LOG_PREFIX, "Range minutes must be 0-59"); ok = false; }
   if(TradeStartHour < 0 || TradeStartHour > 23 || TradeEndHour < 0 || TradeEndHour > 23 || ForceCloseHour < 0 || ForceCloseHour > 23)
     { Print(LOG_PREFIX, "TradeStartHour/TradeEndHour/ForceCloseHour must be 0-23"); ok = false; }
   if(TradeStartHour >= TradeEndHour)
     { Print(LOG_PREFIX, "TradeStartHour must be < TradeEndHour"); ok = false; }
   if(TradeEndHour > ForceCloseHour)
     { Print(LOG_PREFIX, "ForceCloseHour must be >= TradeEndHour"); ok = false; }
   int rEnd = RangeEndHour * 3600 + RangeEndMinute * 60;
   if(rEnd > TradeStartHour * 3600)
     { Print(LOG_PREFIX, "Range must end at or before TradeStartHour"); ok = false; }
   if(ATRPeriod < 1)
     { Print(LOG_PREFIX, "ATRPeriod must be >= 1"); ok = false; }
   if(BufferPoints < 0)
     { Print(LOG_PREFIX, "BufferPoints must be >= 0"); ok = false; }
   if(RiskPercent <= 0.0 && FixedLots <= 0.0)
     { Print(LOG_PREFIX, "Either RiskPercent > 0 or FixedLots > 0 is required"); ok = false; }
   if(RiskPercent > 20.0)
     { Print(LOG_PREFIX, "RiskPercent > 20 refused (sanity limit)"); ok = false; }
   if(MaxTradesPerDay < 1)
     { Print(LOG_PREFIX, "MaxTradesPerDay must be >= 1"); ok = false; }
   if(TakeProfitR < 0.0 || MoveToBreakevenAtR < 0.0 || TrailATRMult < 0.0 || SLATRMult <= 0.0 || BreakoutATRMult < 0.0)
     { Print(LOG_PREFIX, "R / ATR multipliers must be non-negative (SLATRMult > 0)"); ok = false; }
   if(MinRangeBars < 1)
     { Print(LOG_PREFIX, "MinRangeBars must be >= 1"); ok = false; }
   if(ServerToUTCOffsetHours < -12 || ServerToUTCOffsetHours > 14)
     { Print(LOG_PREFIX, "ServerToUTCOffsetHours out of range"); ok = false; }
   if(MinRangePctOfPrice > 0.0 && MaxRangePctOfPrice > 0.0 && MinRangePctOfPrice >= MaxRangePctOfPrice)
     { Print(LOG_PREFIX, "MinRangePctOfPrice must be < MaxRangePctOfPrice"); ok = false; }
   return ok;
  }

//+------------------------------------------------------------------+
//| Filling mode detection                                           |
//+------------------------------------------------------------------+
void DetectFillingMode()
  {
   int flags = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   ENUM_SYMBOL_TRADE_EXECUTION exe = (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE);
   if(exe == SYMBOL_TRADE_EXECUTION_EXCHANGE)
      g_filling = ORDER_FILLING_RETURN;        // exchange execution: pendings require RETURN
   else if((flags & SYMBOL_FILLING_FOK) != 0)
      g_filling = ORDER_FILLING_FOK;
   else if((flags & SYMBOL_FILLING_IOC) != 0)
      g_filling = ORDER_FILLING_IOC;
   else
      g_filling = ORDER_FILLING_RETURN;
   LogV("Execution mode " + EnumToString(exe) + ", filling flags " + IntegerToString(flags) + " -> using " + EnumToString(g_filling));
  }

//+------------------------------------------------------------------+
//| News blackout parsing: "HH:MM-HH:MM;HH:MM-HH:MM"                 |
//+------------------------------------------------------------------+
int ParseHHMM(string t)
  {
   StringTrimLeft(t);
   StringTrimRight(t);
   string hm[];
   if(StringSplit(t, ':', hm) != 2)
      return -1;
   string hs = hm[0];
   string ms = hm[1];
   StringTrimLeft(hs);
   StringTrimRight(hs);
   StringTrimLeft(ms);
   StringTrimRight(ms);
   if(StringLen(hs) == 0 || StringLen(ms) == 0)
      return -1;
   long h = StringToInteger(hs);
   long m = StringToInteger(ms);
   if(h < 0 || h > 23 || m < 0 || m > 59)
      return -1;
   return (int)(h * 60 + m);
  }

void ParseNewsBlackout()
  {
   g_nbCount = 0;
   ArrayResize(g_nbStart, 0);
   ArrayResize(g_nbEnd, 0);
   string s = NewsBlackoutWindows;
   StringTrimLeft(s);
   StringTrimRight(s);
   if(StringLen(s) == 0)
     {
      LogV("No news blackout windows configured");
      return;
     }
   string parts[];
   int n = StringSplit(s, ';', parts);
   for(int i = 0; i < n; i++)
     {
      string w = parts[i];
      StringTrimLeft(w);
      StringTrimRight(w);
      if(StringLen(w) == 0)
         continue;
      string ends[];
      if(StringSplit(w, '-', ends) != 2)
        {
         LogMsg("Ignoring malformed news window '" + w + "' (expected HH:MM-HH:MM)");
         continue;
        }
      int a = ParseHHMM(ends[0]);
      int b = ParseHHMM(ends[1]);
      if(a < 0 || b < 0)
        {
         LogMsg("Ignoring malformed news window '" + w + "' (bad time)");
         continue;
        }
      int k = ArraySize(g_nbStart);
      ArrayResize(g_nbStart, k + 1);
      ArrayResize(g_nbEnd, k + 1);
      g_nbStart[k] = a;
      g_nbEnd[k]   = b;
      g_nbCount    = k + 1;
      LogV("News blackout window #" + IntegerToString(k + 1) + ": " + HHMM(a * 60) + "-" + HHMM(b * 60) + (a > b ? " (wraps midnight)" : ""));
     }
  }

bool InNewsBlackout(const int secOfDay)
  {
   int m = secOfDay / 60;
   for(int i = 0; i < g_nbCount; i++)
     {
      int a = g_nbStart[i];
      int b = g_nbEnd[i];
      bool inside = (a <= b) ? (m >= a && m < b) : (m >= a || m < b);
      if(inside)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;

   if(!g_symbol.Name(_Symbol))
     {
      Print(LOG_PREFIX, "CSymbolInfo::Name failed for ", _Symbol);
      return INIT_FAILED;
     }
   g_symbol.Refresh();
   g_symbol.RefreshRates();

   g_shiftSec       = UseServerTime ? 0 : (long)ServerToUTCOffsetHours * 3600;
   g_rangeStartSec  = RangeStartHour * 3600 + RangeStartMinute * 60;
   g_rangeEndSec    = RangeEndHour * 3600 + RangeEndMinute * 60;
   g_rangeOvernight = (g_rangeStartSec >= g_rangeEndSec);
   g_tradeStartSec  = TradeStartHour * 3600;
   g_tradeEndSec    = TradeEndHour * 3600;
   g_forceCloseSec  = ForceCloseHour * 3600;

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, ATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print(LOG_PREFIX, "iATR handle creation failed, error ", GetLastError());
      return INIT_FAILED;
     }

   DetectFillingMode();
   int expMode = (int)SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE);
   g_expirationSupported = ((expMode & SYMBOL_EXPIRATION_SPECIFIED) != 0);

   g_volDigits = VolumeDigits(g_symbol.LotsStep());

   g_trade.SetExpertMagicNumber((ulong)MagicNumber);
   g_trade.SetDeviationInPoints((ulong)DeviationPoints);
   g_trade.SetTypeFilling(g_filling);
   g_trade.SetAsyncMode(false);
   g_trade.LogLevel(LOG_LEVEL_ERRORS);

   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   g_isHedging = (mm == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);

   ParseNewsBlackout();

   // reset per-day state so the first tick starts a fresh day
   g_dayIndex = -1;

   //--- setup log
   LogMsg("=== LondonRangeBreakout v1.00 initialised on " + _Symbol + " " + EnumToString((ENUM_TIMEFRAMES)Period()) + " ===");
   LogMsg("Account: " + g_account.Currency() + ", leverage 1:" + IntegerToString(g_account.Leverage()) + ", balance " +
          DoubleToString(g_account.Balance(), 2) + ", margin mode " + EnumToString(mm) +
          (g_isHedging ? " (hedging)" : " (netting/exchange: keep this EA alone on the symbol)"));
   LogMsg(StringFormat("Symbol: digits=%d point=%s tick size=%s tick value=%s contract=%s lots min/max/step=%s/%s/%s stops level=%d freeze level=%d",
                       g_symbol.Digits(), DoubleToString(g_symbol.Point(), g_symbol.Digits()),
                       DoubleToString(g_symbol.TickSize(), g_symbol.Digits()), DoubleToString(g_symbol.TickValue(), 4),
                       DoubleToString(g_symbol.ContractSize(), 2), LotsStr(g_symbol.LotsMin()), LotsStr(g_symbol.LotsMax()),
                       LotsStr(g_symbol.LotsStep()), g_symbol.StopsLevel(), g_symbol.FreezeLevel()));
   LogMsg("Pending-order expiration " + (g_expirationSupported ? "SPECIFIED supported: stops expire at TradeEndHour" : "SPECIFIED not supported: EA deletes stops manually at TradeEndHour"));

   string frame = UseServerTime ? "SERVER time" : "UTC (converted to server with offset " + IntegerToString(ServerToUTCOffsetHours) + "h)";
   LogMsg("Schedule frame: " + frame);
   LogMsg("Range " + HHMM(g_rangeStartSec) + "-" + HHMM(g_rangeEndSec) + (g_rangeOvernight ? " (starts previous day)" : "") +
          ", entries " + HHMM(g_tradeStartSec) + "-" + HHMM(g_tradeEndSec) + ", force close " + HHMM(g_forceCloseSec) +
          ", one trade/day=" + (OneTradePerDay ? "true" : "false"));
   if(UseServerTime)
     {
      int off = ServerToUTCOffsetHours * 3600;
      LogMsg("If your server is UTC" + (ServerToUTCOffsetHours >= 0 ? "+" : "") + IntegerToString(ServerToUTCOffsetHours) +
             ", that is range " + HHMM(g_rangeStartSec - off) + "-" + HHMM(g_rangeEndSec - off) + " UTC, entries " +
             HHMM(g_tradeStartSec - off) + "-" + HHMM(g_tradeEndSec - off) + " UTC. VERIFY against your broker's GMT offset and DST.");
     }
   if(!MQLInfoInteger(MQL_TESTER))
     {
      long srvOff = ((long)TimeCurrent() - (long)TimeGMT());
      LogMsg("Live check: server time minus GMT is about " + DoubleToString(srvOff / 3600.0, 1) + " hours right now (ServerToUTCOffsetHours=" +
             IntegerToString(ServerToUTCOffsetHours) + ")");
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
         LogMsg("WARNING: algo trading is not allowed in the terminal/program settings");
      if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
         LogMsg("WARNING: the account does not allow expert trading");
     }
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_FULL)
      LogMsg("WARNING: symbol trade mode is " + EnumToString((ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE)));
   if(OneTradePerDay && !CancelOppositeOnFill)
      LogMsg("NOTE: OneTradePerDay=true forces deletion of the remaining stop order after the first fill (CancelOppositeOnFill is ignored)");
   if(EntryMode == ENTRY_CLOSE_BEYOND && PeriodSeconds() > 3600)
      LogMsg("WARNING: CLOSE_BEYOND mode on a timeframe above H1 will rarely produce an entry inside a " +
             IntegerToString(TradeEndHour - TradeStartHour) + "-hour window");
   LogMsg(StringFormat("Entry=%s SL=%s TP=%.2fR BE@%.2fR trail=%.2fATR buffer=%d pts spread cap=%d pts risk=%.2f%% fixed lots=%s",
                       EnumToString(EntryMode), EnumToString(SLMode), TakeProfitR, MoveToBreakevenAtR, TrailATRMult,
                       BufferPoints, MaxSpreadPoints, RiskPercent, LotsStr(FixedLots)));
   LogMsg("REMINDER: research tool only; no performance implied. Test with real ticks, real spread and commission on your own broker.");

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
     {
      IndicatorRelease(g_atrHandle);
      g_atrHandle = INVALID_HANDLE;
     }
   Comment("");
   LogV("Deinitialised, reason " + IntegerToString(reason));
  }

//+------------------------------------------------------------------+
//| Market data helpers                                              |
//+------------------------------------------------------------------+
double GetATR()
  {
   if(g_atrHandle == INVALID_HANDLE)
      return 0.0;
   double buf[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, buf) != 1)   // last completed bar
      return 0.0;
   if(buf[0] <= 0.0 || buf[0] == EMPTY_VALUE)
      return 0.0;
   return buf[0];
  }

int CurrentSpreadPoints()
  {
   double pt = g_symbol.Point();
   if(pt <= 0.0)
      return 0;
   return (int)MathRound((g_symbol.Ask() - g_symbol.Bid()) / pt);
  }

bool SpreadOK()
  {
   if(MaxSpreadPoints <= 0)
      return true;
   int sp = CurrentSpreadPoints();
   if(sp > MaxSpreadPoints)
     {
      if((long)TimeCurrent() - (long)g_lastSpreadLog >= 60)
        {
         LogMsg("Spread filter: " + IntegerToString(sp) + " pts > MaxSpreadPoints " + IntegerToString(MaxSpreadPoints) + ", no entry");
         g_lastSpreadLog = TimeCurrent();
        }
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Position / order enumeration (filtered by symbol + magic)        |
//+------------------------------------------------------------------+
bool IsOurPosition()
  {
   return (g_position.Symbol() == _Symbol && g_position.Magic() == MagicNumber);
  }

bool IsOurOrder()
  {
   return (g_order.Symbol() == _Symbol && g_order.Magic() == MagicNumber);
  }

int CountOurPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_position.SelectByIndex(i))
         continue;
      if(IsOurPosition())
         n++;
     }
   return n;
  }

int CountOurPendingOrders()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!g_order.SelectByIndex(i))
         continue;
      if(IsOurOrder())
         n++;
     }
   return n;
  }

bool HasOurPending(const ENUM_ORDER_TYPE type)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!g_order.SelectByIndex(i))
         continue;
      if(IsOurOrder() && g_order.OrderType() == type)
         return true;
     }
   return false;
  }

// Returns true when no pending orders of ours remain afterwards.
bool DeleteOurPendingOrders(const string reason)
  {
   bool all = true;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!g_order.SelectByIndex(i))
         continue;
      if(!IsOurOrder())
         continue;
      ulong tk = g_order.Ticket();
      string desc = EnumToString(g_order.OrderType()) + " #" + IntegerToString((long)tk) + " @ " + PriceStr(g_order.PriceOpen());
      if(g_trade.OrderDelete(tk))
         LogMsg("Deleted " + desc + " (" + reason + ")");
      else
        {
         all = false;
         LogMsg("OrderDelete failed for " + desc + ": " + IntegerToString((long)g_trade.ResultRetcode()) + " " +
                g_trade.ResultRetcodeDescription() + " (will retry)");
        }
     }
   return all;
  }

// Closes one position of ours with a descriptive log line.
void ClosePositionWithLog(const ulong ticket, const string reason)
  {
   string desc = EnumToString(g_position.PositionType()) + " #" + IntegerToString((long)ticket) + " " + LotsStr(g_position.Volume()) +
                 " lots, open " + PriceStr(g_position.PriceOpen()) + ", floating " + DoubleToString(g_position.Profit(), 2);
   if(g_trade.PositionClose(ticket, (ulong)DeviationPoints))
      LogMsg("Closed " + desc + " (" + reason + ")");
   else
      LogMsg("PositionClose failed for " + desc + ": " + IntegerToString((long)g_trade.ResultRetcode()) + " " +
             g_trade.ResultRetcodeDescription() + " (will retry next tick)");
  }

//+------------------------------------------------------------------+
//| Lot sizing                                                       |
//+------------------------------------------------------------------+
double CalcLots(const bool isBuy, const double entry, const double sl, string &why)
  {
   why = "";
   double minV = g_symbol.LotsMin();
   if(FixedLots > 0.0)
     {
      double fl = NormalizeLotsDown(FixedLots);
      if(fl < minV)
         fl = minV;
      return fl;
     }

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * RiskPercent / 100.0;
   double dist      = MathAbs(entry - sl);
   if(dist <= 0.0)
     {
      why = "zero SL distance";
      return 0.0;
     }
   if(riskMoney <= 0.0)
     {
      why = "non-positive risk amount (balance " + DoubleToString(balance, 2) + ")";
      return 0.0;
     }

   // Primary: broker-side profit calculation for 1 lot, entry -> SL (handles
   // currency conversion and contract size). Fallback: tick value / tick size.
   ENUM_ORDER_TYPE calcType = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double lossPerLot = 0.0;
   double p = 0.0;
   if(OrderCalcProfit(calcType, _Symbol, 1.0, entry, sl, p) && p < 0.0)
      lossPerLot = -p;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0.0)
      tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0)
      tickSize = g_symbol.Point();
   double lossPerLotTV = (tickSize > 0.0 && tickValue > 0.0) ? (dist / tickSize) * tickValue : 0.0;

   if(lossPerLot <= 0.0)
      lossPerLot = lossPerLotTV;
   else if(lossPerLotTV > 0.0 && MathAbs(lossPerLot - lossPerLotTV) / lossPerLot > 0.20)
      LogMsg(StringFormat("WARNING: lot-size cross-check mismatch: OrderCalcProfit says %.2f per lot, tick-value method says %.2f per lot. Check symbol specification.",
                          lossPerLot, lossPerLotTV));
   if(lossPerLot <= 0.0)
     {
      why = "cannot compute money-per-lot (tick value/size unavailable)";
      return 0.0;
     }

   double lots = NormalizeLotsDown(riskMoney / lossPerLot);
   if(lots < minV)
     {
      double actualRisk = minV * lossPerLot;
      LogMsg(StringFormat("WARNING: computed %s lots < min lot %s; using min lot, actual risk %.2f = %.2f%% of balance (target %.2f%%)",
                          LotsStr(lots), LotsStr(minV), actualRisk, (balance > 0.0 ? actualRisk / balance * 100.0 : 0.0), RiskPercent));
      lots = minV;
     }

   // margin check
   double margin = 0.0;
   if(OrderCalcMargin(calcType, _Symbol, lots, entry, margin) && margin > 0.0)
     {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95;
      if(margin > freeMargin)
        {
         double reduced = NormalizeLotsDown(lots * freeMargin / margin);
         if(reduced < minV)
           {
            why = StringFormat("insufficient free margin (need %.2f for %s lots, have %.2f)", margin, LotsStr(lots), freeMargin);
            return 0.0;
           }
         LogMsg("Lots reduced from " + LotsStr(lots) + " to " + LotsStr(reduced) + " to fit free margin");
         lots = reduced;
        }
     }

   LogV(StringFormat("Sizing: balance %.2f, risk %.2f (%0.2f%%), SL distance %s (%d pts), loss/lot %.2f -> %s lots",
                     balance, riskMoney, RiskPercent, PriceStr(dist), (int)MathRound(dist / g_symbol.Point()), lossPerLot, LotsStr(lots)));
   return lots;
  }

//+------------------------------------------------------------------+
//| Build SL / TP for an entry at 'entry'. Returns false to skip.     |
//+------------------------------------------------------------------+
bool BuildTradeLevels(const bool isBuy, const double entry, const double atr, double &sl, double &tp, string &err)
  {
   err = "";
   sl = 0.0;
   tp = 0.0;
   double point     = g_symbol.Point();
   double stopsDist = (double)g_symbol.StopsLevel() * point;
   double dist      = 0.0;

   if(SLMode == SL_OPPOSITE_RANGE)
     {
      double opp = isBuy ? g_rangeLow : g_rangeHigh;
      dist = MathAbs(entry - opp);
     }
   else
     {
      if(atr <= 0.0)
        {
         err = "ATR not available for SL_ATR";
         return false;
        }
      dist = SLATRMult * atr;
     }

   if(MaxSLPctOfPrice > 0.0)
     {
      double maxDist = entry * MaxSLPctOfPrice / 100.0;
      if(dist > maxDist)
        {
         LogV("SL distance " + PriceStr(dist) + " capped to " + PriceStr(maxDist) + " (" + DoubleToString(MaxSLPctOfPrice, 2) + "% of price)");
         dist = maxDist;
        }
     }
   if(dist <= 0.0)
     {
      err = "non-positive SL distance";
      return false;
     }
   if(stopsDist > 0.0 && dist < stopsDist)
     {
      if(SkipIfStopsLevelViolated)
        {
         err = "SL distance " + PriceStr(dist) + " below stops level " + PriceStr(stopsDist) + " (SkipIfStopsLevelViolated=true)";
         return false;
        }
      LogMsg("SL distance " + PriceStr(dist) + " widened to stops level " + PriceStr(stopsDist + point));
      dist = stopsDist + point;
     }

   sl   = NormalizePrice(isBuy ? entry - dist : entry + dist);
   dist = MathAbs(entry - sl);
   if(TakeProfitR > 0.0)
     {
      double tdist = TakeProfitR * dist;
      if(stopsDist > 0.0 && tdist < stopsDist)
         tdist = stopsDist + point;
      tp = NormalizePrice(isBuy ? entry + tdist : entry - tdist);
     }
   g_lastRiskDistance = dist;
   return true;
  }

//+------------------------------------------------------------------+
//| Day management                                                   |
//+------------------------------------------------------------------+
void RecoverDayStateFromHistory()
  {
   datetime from = LogicalToServer(g_dayStartLogical);
   datetime to   = (datetime)((long)TimeCurrent() + 86400);
   if(HistorySelect(from, to))
     {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0)
            continue;
         if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)
            continue;
         if(HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber)
            continue;
         ENUM_DEAL_TYPE dtype = (ENUM_DEAL_TYPE)HistoryDealGetInteger(d, DEAL_TYPE);
         if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL)
            continue;
         ENUM_DEAL_ENTRY e = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY);
         if(e == DEAL_ENTRY_IN || e == DEAL_ENTRY_INOUT)
           {
            g_tradesToday++;
            g_tradedToday = true;
           }
         if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_INOUT || e == DEAL_ENTRY_OUT_BY)
            g_dayProfit += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
        }
     }
   if(CountOurPositions() > 0)
     {
      g_posOpenSeen = true;
      g_tradedToday = true;
      if(g_tradesToday == 0)
         g_tradesToday = 1;
     }
   if(HasOurPending(ORDER_TYPE_BUY_STOP))
      g_buySideDone = true;
   if(HasOurPending(ORDER_TYPE_SELL_STOP))
      g_sellSideDone = true;
   if(g_buySideDone && g_sellSideDone)
      g_entryPlaced = true;
   if(g_tradesToday > 0 || g_buySideDone || g_sellSideDone)
      LogMsg(StringFormat("Recovered day state: %d fill(s) today, net %.2f, pending buy=%s sell=%s, open positions=%d",
                          g_tradesToday, g_dayProfit, (g_buySideDone ? "yes" : "no"), (g_sellSideDone ? "yes" : "no"), CountOurPositions()));
   if(OneTradePerDay && g_tradedToday)
      g_dayDone = true;
  }

void StartNewDay(const long dayIdx)
  {
   if(g_dayIndex >= 0)
      LogMsg(StringFormat("Day summary %s: fills=%d net P/L=%.2f range=%s",
                          TimeToString(g_dayStartLogical, TIME_DATE), g_tradesToday, g_dayProfit,
                          (g_rangeReady ? (PriceStr(g_rangeLow) + "-" + PriceStr(g_rangeHigh) + " " + g_dayVerdict) : "n/a")));

   g_dayIndex        = dayIdx;
   g_dayStartLogical = (datetime)(dayIdx * 86400);
   long ds = (long)g_dayStartLogical;
   long rs = ds + g_rangeStartSec;
   if(g_rangeOvernight)
      rs -= 86400;
   g_srvRangeStart = (datetime)(rs + g_shiftSec);
   g_srvRangeEnd   = (datetime)(ds + g_rangeEndSec + g_shiftSec);
   g_srvTradeStart = (datetime)(ds + g_tradeStartSec + g_shiftSec);
   g_srvTradeEnd   = (datetime)(ds + g_tradeEndSec + g_shiftSec);
   g_srvForceClose = (datetime)(ds + g_forceCloseSec + g_shiftSec);

   g_rangeReady      = false;
   g_rangeAttempts   = 0;
   g_rangeHigh       = 0.0;
   g_rangeLow        = 0.0;
   g_dayValid        = false;
   g_dayDone         = false;
   g_tradedToday     = false;
   g_tradesToday     = 0;
   g_posOpenSeen     = false;
   g_buySideDone     = false;
   g_sellSideDone    = false;
   g_entryPlaced     = false;
   g_placeAttempts   = 0;
   g_entryAttempts   = 0;
   g_cancelPendingRequested = false;
   g_forceCloseLogged = false;
   g_tradeEndLogged  = false;
   g_dayProfit       = 0.0;
   g_lastRiskDistance = 0.0;
   g_lastBarTime     = 0;
   g_dayVerdict      = "";

   MqlDateTime dt;
   TimeToStruct(g_dayStartLogical, dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
     {
      g_dayDone    = true;
      g_dayVerdict = "weekend";
      LogV("New day " + TimeToString(g_dayStartLogical, TIME_DATE) + " is a weekend day: no trading");
     }
   else
      LogV("New day " + TimeToString(g_dayStartLogical, TIME_DATE) + ": range window " +
           TimeToString(g_srvRangeStart, TIME_DATE|TIME_MINUTES) + " .. " + TimeToString(g_srvRangeEnd, TIME_MINUTES) +
           " server, entries " + TimeToString(g_srvTradeStart, TIME_MINUTES) + "-" + TimeToString(g_srvTradeEnd, TIME_MINUTES) +
           ", force close " + TimeToString(g_srvForceClose, TIME_MINUTES));

   RecoverDayStateFromHistory();
  }

//+------------------------------------------------------------------+
//| Range computation and filters                                    |
//+------------------------------------------------------------------+
void ComputeRange()
  {
   if(g_rangeAttempts >= MAX_RANGE_ATTEMPTS)
     {
      g_dayDone    = true;
      g_dayVerdict = "range unavailable";
      LogMsg("Range could not be computed after " + IntegerToString(MAX_RANGE_ATTEMPTS) + " attempts: skipping the day");
      return;
     }
   g_rangeAttempts++;

   ENUM_TIMEFRAMES tf = (RangeSource == RANGE_M1) ? PERIOD_M1 : (ENUM_TIMEFRAMES)Period();
   datetime to = (datetime)((long)g_srvRangeEnd - 1);
   MqlRates rates[];
   int n = CopyRates(_Symbol, tf, g_srvRangeStart, to, rates);
   if(n <= 0)
     {
      LogMsg("CopyRates for range returned " + IntegerToString(n) + ", error " + IntegerToString(GetLastError()) + " (attempt " + IntegerToString(g_rangeAttempts) + ")");
      return;
     }

   double hi = -DBL_MAX;
   double lo = DBL_MAX;
   int used = 0;
   for(int i = 0; i < n; i++)
     {
      if(rates[i].time < g_srvRangeStart || rates[i].time >= g_srvRangeEnd)
         continue;
      if(rates[i].high > hi)
         hi = rates[i].high;
      if(rates[i].low < lo)
         lo = rates[i].low;
      used++;
     }
   if(used < MinRangeBars)
     {
      LogMsg("Only " + IntegerToString(used) + " bars inside the range window (MinRangeBars=" + IntegerToString(MinRangeBars) + "), attempt " + IntegerToString(g_rangeAttempts));
      return;
     }

   g_rangeHigh  = hi;
   g_rangeLow   = lo;
   g_rangeReady = true;

   double range = hi - lo;
   double mid   = (hi + lo) / 2.0;
   double pct   = (mid > 0.0) ? range / mid * 100.0 : 0.0;
   double pts   = (g_symbol.Point() > 0.0) ? range / g_symbol.Point() : 0.0;

   g_dayValid   = true;
   g_dayVerdict = "OK";
   if(range <= 0.0)
     { g_dayValid = false; g_dayVerdict = "zero range"; }
   else if(MinRangePctOfPrice > 0.0 && pct < MinRangePctOfPrice)
     { g_dayValid = false; g_dayVerdict = StringFormat("range %.3f%% < min %.2f%%", pct, MinRangePctOfPrice); }
   else if(MaxRangePctOfPrice > 0.0 && pct > MaxRangePctOfPrice)
     { g_dayValid = false; g_dayVerdict = StringFormat("range %.3f%% > max %.2f%%", pct, MaxRangePctOfPrice); }
   else if(MinRangePoints > 0 && pts < (double)MinRangePoints)
     { g_dayValid = false; g_dayVerdict = StringFormat("range %d pts < min %d pts", (int)MathRound(pts), MinRangePoints); }
   else if(MaxRangePoints > 0 && pts > (double)MaxRangePoints)
     { g_dayValid = false; g_dayVerdict = StringFormat("range %d pts > max %d pts", (int)MathRound(pts), MaxRangePoints); }

   LogMsg(StringFormat("RANGE %s..%s (%s bars=%d): high %s low %s width %d pts (%.3f%% of price) -> %s",
                       TimeToString(g_srvRangeStart, TIME_MINUTES), TimeToString(g_srvRangeEnd, TIME_MINUTES), EnumToString(tf), used,
                       PriceStr(hi), PriceStr(lo), (int)MathRound(pts), pct, (g_dayValid ? "VALID, trading allowed" : "SKIP: " + g_dayVerdict)));
   if(!g_dayValid)
      g_dayDone = true;
  }

//+------------------------------------------------------------------+
//| Fill / exit handlers (idempotent)                                |
//+------------------------------------------------------------------+
void OnFillDetected(const string source)
  {
   if(g_posOpenSeen)
      return;
   g_posOpenSeen = true;
   g_tradedToday = true;
   g_tradesToday++;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_position.SelectByIndex(i))
         continue;
      if(!IsOurPosition())
         continue;
      double risk = (g_position.StopLoss() > 0.0) ? MathAbs(g_position.PriceOpen() - g_position.StopLoss()) : g_lastRiskDistance;
      LogMsg(StringFormat("FILL (%s): %s #%s %s lots @ %s SL %s TP %s risk %d pts, spread now %d pts, trade %d of the day",
                          source, EnumToString(g_position.PositionType()), IntegerToString((long)g_position.Ticket()),
                          LotsStr(g_position.Volume()), PriceStr(g_position.PriceOpen()), PriceStr(g_position.StopLoss()),
                          PriceStr(g_position.TakeProfit()), (int)MathRound(risk / g_symbol.Point()), CurrentSpreadPoints(), g_tradesToday));
     }

   if(OneTradePerDay || CancelOppositeOnFill)
     {
      g_cancelPendingRequested = true;
      if(DeleteOurPendingOrders(OneTradePerDay ? "one trade per day" : "OCO"))
         g_cancelPendingRequested = false;
     }
  }

void OnPositionClosed(const string source)
  {
   if(!g_posOpenSeen)
      return;
   g_posOpenSeen = false;
   LogMsg(StringFormat("Position closed (%s). Day net P/L so far %.2f", source, g_dayProfit));

   if(OneTradePerDay || g_tradesToday >= MaxTradesPerDay)
     {
      g_dayDone = true;
      if(CountOurPendingOrders() > 0)
        {
         g_cancelPendingRequested = true;
         if(DeleteOurPendingOrders("day complete"))
            g_cancelPendingRequested = false;
        }
     }
   else
     {
      // re-arm for another entry inside the window
      g_entryPlaced   = false;
      g_buySideDone   = false;
      g_sellSideDone  = false;
      g_placeAttempts = 0;
      LogV("Re-armed for another entry (trade " + IntegerToString(g_tradesToday) + " of max " + IntegerToString(MaxTradesPerDay) + ")");
     }
  }

void PollPositions()
  {
   int n = CountOurPositions();
   if(n > 0 && !g_posOpenSeen)
      OnFillDetected("poll");
   else if(n == 0 && g_posOpenSeen)
      OnPositionClosed("poll");
  }

//+------------------------------------------------------------------+
//| Entry: stop orders                                               |
//+------------------------------------------------------------------+
// Returns true when the side is finished (placed, already exists, or
// permanently skipped today); false when it should be retried.
bool PlaceStopSide(const bool isBuy, const double atr, const ENUM_ORDER_TYPE_TIME tt, const datetime expiry)
  {
   ENUM_ORDER_TYPE otype = isBuy ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
   if(HasOurPending(otype))
      return true;

   string side      = isBuy ? "BUY STOP" : "SELL STOP";
   double point     = g_symbol.Point();
   double stopsDist = (double)g_symbol.StopsLevel() * point;
   double ask       = g_symbol.Ask();
   double bid       = g_symbol.Bid();
   double price     = NormalizePrice(isBuy ? g_rangeHigh + BufferPoints * point : g_rangeLow - BufferPoints * point);

   if(isBuy)
     {
      if(ask >= price)
        {
         LogMsg(side + " skipped: Ask " + PriceStr(ask) + " is already at/above the trigger " + PriceStr(price) + " (breakout happened before the window)");
         return true;
        }
      if(stopsDist > 0.0 && price - ask < stopsDist)
        {
         double adj = NormalizePrice(ask + stopsDist + point);
         LogMsg(side + " trigger " + PriceStr(price) + " too close to Ask " + PriceStr(ask) + " (stops level), moved to " + PriceStr(adj));
         price = adj;
        }
     }
   else
     {
      if(bid <= price)
        {
         LogMsg(side + " skipped: Bid " + PriceStr(bid) + " is already at/below the trigger " + PriceStr(price) + " (breakout happened before the window)");
         return true;
        }
      if(stopsDist > 0.0 && bid - price < stopsDist)
        {
         double adj = NormalizePrice(bid - stopsDist - point);
         LogMsg(side + " trigger " + PriceStr(price) + " too close to Bid " + PriceStr(bid) + " (stops level), moved to " + PriceStr(adj));
         price = adj;
        }
     }

   double sl = 0.0, tp = 0.0;
   string err = "";
   if(!BuildTradeLevels(isBuy, price, atr, sl, tp, err))
     {
      LogMsg(side + " skipped: " + err);
      return true;
     }
   string why = "";
   double lots = CalcLots(isBuy, price, sl, why);
   if(lots <= 0.0)
     {
      LogMsg(side + " skipped: " + why);
      return true;
     }

   bool sent = isBuy ? g_trade.BuyStop(lots, price, _Symbol, sl, tp, tt, expiry, TradeComment)
                     : g_trade.SellStop(lots, price, _Symbol, sl, tp, tt, expiry, TradeComment);
   uint rc = g_trade.ResultRetcode();
   if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))
     {
      LogMsg(StringFormat("%s #%s placed: %s lots @ %s SL %s TP %s (risk %d pts, R:R 1:%.2f, expires %s)",
                          side, IntegerToString((long)g_trade.ResultOrder()), LotsStr(lots), PriceStr(price), PriceStr(sl), PriceStr(tp),
                          (int)MathRound(MathAbs(price - sl) / point), TakeProfitR,
                          (expiry > 0 ? TimeToString(expiry, TIME_DATE|TIME_MINUTES) : "GTC, deleted by EA at TradeEndHour")));
      return true;
     }
   LogMsg(side + " failed: retcode " + IntegerToString((long)rc) + " " + g_trade.ResultRetcodeDescription() + " (will retry, attempt " +
          IntegerToString(g_placeAttempts) + "/" + IntegerToString(MAX_PLACE_ATTEMPTS) + ")");
   return false;
  }

void TryPlaceStopOrders()
  {
   if(g_placeAttempts >= MAX_PLACE_ATTEMPTS)
     {
      if(!g_entryPlaced)
        {
         LogMsg("Giving up on stop-order placement for today after " + IntegerToString(MAX_PLACE_ATTEMPTS) + " attempts");
         g_entryPlaced  = true;
         g_buySideDone  = true;
         g_sellSideDone = true;
        }
      return;
     }
   g_placeAttempts++;

   double atr = GetATR();
   if(SLMode == SL_ATR && atr <= 0.0)
     {
      LogMsg("ATR not available yet for SL_ATR, retrying next tick");
      return;
     }
   ENUM_ORDER_TYPE_TIME tt = g_expirationSupported ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC;
   datetime expiry = g_expirationSupported ? g_srvTradeEnd : 0;

   if(g_placeAttempts == 1)
      LogMsg(StringFormat("Placing OCO stops around range %s-%s, buffer %d pts, ATR(%d)=%s, spread %d pts",
                          PriceStr(g_rangeLow), PriceStr(g_rangeHigh), BufferPoints, ATRPeriod, PriceStr(atr), CurrentSpreadPoints()));

   if(!g_buySideDone)
      g_buySideDone = PlaceStopSide(true, atr, tt, expiry);
   if(!g_sellSideDone)
      g_sellSideDone = PlaceStopSide(false, atr, tt, expiry);
   if(g_buySideDone && g_sellSideDone)
     {
      g_entryPlaced = true;
      if(CountOurPendingOrders() == 0)
        {
         LogMsg("No stop order could be placed today: day finished");
         g_dayDone = true;
        }
     }
  }

//+------------------------------------------------------------------+
//| Entry: market order on bar close beyond the range                |
//+------------------------------------------------------------------+
void TryMarketEntry(const bool isBuy, const double atr, const double closePrice)
  {
   g_entryAttempts++;
   string side  = isBuy ? "BUY" : "SELL";
   double price = isBuy ? g_symbol.Ask() : g_symbol.Bid();
   double sl = 0.0, tp = 0.0;
   string err = "";
   if(!BuildTradeLevels(isBuy, price, atr, sl, tp, err))
     {
      LogMsg(side + " market entry skipped: " + err);
      return;
     }
   string why = "";
   double lots = CalcLots(isBuy, price, sl, why);
   if(lots <= 0.0)
     {
      LogMsg(side + " market entry skipped: " + why);
      return;
     }
   LogMsg(StringFormat("Breakout bar closed at %s beyond range %s-%s by >= %.2f*ATR(%s): %s at market, spread %d pts",
                       PriceStr(closePrice), PriceStr(g_rangeLow), PriceStr(g_rangeHigh), BreakoutATRMult, PriceStr(atr), side, CurrentSpreadPoints()));

   bool sent = isBuy ? g_trade.Buy(lots, _Symbol, price, sl, tp, TradeComment)
                     : g_trade.Sell(lots, _Symbol, price, sl, tp, TradeComment);
   uint rc = g_trade.ResultRetcode();
   if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
     {
      LogMsg(StringFormat("%s order #%s done: %s lots, fill %s (requested %s), SL %s TP %s",
                          side, IntegerToString((long)g_trade.ResultOrder()), LotsStr(g_trade.ResultVolume()), PriceStr(g_trade.ResultPrice()),
                          PriceStr(price), PriceStr(sl), PriceStr(tp)));
      if(CountOurPositions() > 0)
         OnFillDetected("market order");
     }
   else
      LogMsg(side + " market entry failed: retcode " + IntegerToString((long)rc) + " " + g_trade.ResultRetcodeDescription() +
             " (attempt " + IntegerToString(g_entryAttempts) + "/" + IntegerToString(MAX_ENTRY_ATTEMPTS) + ")");
  }

void EvaluateCloseBeyond()
  {
   MqlRates r[];
   if(CopyRates(_Symbol, PERIOD_CURRENT, 1, 1, r) != 1)
      return;
   if(r[0].time < g_srvRangeEnd)        // bar belongs to the range itself
      return;
   double atr = GetATR();
   if(atr <= 0.0)
     {
      LogV("ATR not available, skipping bar");
      return;
     }
   double thr = BreakoutATRMult * atr;
   if(r[0].close >= g_rangeHigh + thr)
      TryMarketEntry(true, atr, r[0].close);
   else if(r[0].close <= g_rangeLow - thr)
      TryMarketEntry(false, atr, r[0].close);
  }

//+------------------------------------------------------------------+
//| Entry dispatcher                                                 |
//+------------------------------------------------------------------+
void HandleEntries(const int secOfDay)
  {
   if(OneTradePerDay && g_tradedToday)
      return;
   if(!OneTradePerDay && g_tradesToday >= MaxTradesPerDay)
      return;
   if(CountOurPositions() > 0)
      return;

   if(EntryMode == ENTRY_STOP_ORDERS)
     {
      if(g_entryPlaced)
         return;
      if(InNewsBlackout(secOfDay))
        {
         if((long)TimeCurrent() - (long)g_lastNewsLog >= 60)
           {
            LogMsg("News blackout active (" + HHMM(secOfDay) + "): stop-order placement postponed");
            g_lastNewsLog = TimeCurrent();
           }
         return;
        }
      if(!SpreadOK())
         return;
      TryPlaceStopOrders();
     }
   else
     {
      datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
      if(bt == g_lastBarTime)
         return;
      g_lastBarTime = bt;
      if(g_entryAttempts >= MAX_ENTRY_ATTEMPTS)
         return;
      if(InNewsBlackout(secOfDay))
        {
         LogV("News blackout active (" + HHMM(secOfDay) + "): bar not evaluated");
         return;
        }
      if(!SpreadOK())
         return;
      EvaluateCloseBeyond();
     }
  }

//+------------------------------------------------------------------+
//| Position management: break-even and ATR trailing                 |
//+------------------------------------------------------------------+
bool IsBetterSL(const bool isBuy, const double cand, const double cur)
  {
   if(cur <= 0.0)
      return true;
   double half = g_symbol.Point() * 0.5;
   return isBuy ? (cand > cur + half) : (cand < cur - half);
  }

void ManageStops(const ulong ticket, const ENUM_POSITION_TYPE ptype, const double open, const double sl, const double tp, const double atr)
  {
   bool   isBuy      = (ptype == POSITION_TYPE_BUY);
   double bid        = g_symbol.Bid();
   double ask        = g_symbol.Ask();
   double point      = g_symbol.Point();
   double stopsDist  = (double)g_symbol.StopsLevel() * point;
   double freezeDist = (double)g_symbol.FreezeLevel() * point;
   double risk       = (sl > 0.0) ? MathAbs(open - sl) : g_lastRiskDistance;
   if(risk <= 0.0)
      return;

   double cur        = isBuy ? bid : ask;                  // price the SL is measured against
   double profitDist = isBuy ? (bid - open) : (open - ask);
   double newSL      = sl;
   string why        = "";
   bool   beAlready  = (sl > 0.0) && (isBuy ? (sl >= open) : (sl <= open));

   if(MoveToBreakevenAtR > 0.0 && !beAlready && profitDist >= MoveToBreakevenAtR * risk)
     {
      double cand = isBuy ? open + BreakevenOffsetPoints * point : open - BreakevenOffsetPoints * point;
      if(IsBetterSL(isBuy, cand, newSL))
        {
         newSL = cand;
         why   = "breakeven";
        }
     }
   if(TrailATRMult > 0.0 && atr > 0.0)
     {
      double cand = isBuy ? bid - TrailATRMult * atr : ask + TrailATRMult * atr;
      if(IsBetterSL(isBuy, cand, newSL))
        {
         newSL = cand;
         why   = (why == "" ? "trail" : why + "+trail");
        }
     }
   if(why == "")
      return;

   newSL = NormalizePrice(newSL);
   if(!IsBetterSL(isBuy, newSL, sl))
      return;
   // stops level: the new SL must stay at least stopsDist away from the current price
   if(stopsDist > 0.0)
     {
      if(isBuy && (bid - newSL) < stopsDist)
         newSL = NormalizePrice(bid - stopsDist);
      if(!isBuy && (newSL - ask) < stopsDist)
         newSL = NormalizePrice(ask + stopsDist);
      if(!IsBetterSL(isBuy, newSL, sl))
         return;
     }
   // freeze level: an SL within the freeze distance of the market cannot be modified right now
   if(sl > 0.0 && freezeDist > 0.0 && MathAbs(cur - sl) <= freezeDist)
      return;

   if(g_trade.PositionModify(ticket, newSL, tp))
     {
      string msg = StringFormat("%s #%s: SL %s -> %s (%s, open %s, profit %d pts = %.2fR)",
                                EnumToString(ptype), IntegerToString((long)ticket), PriceStr(sl), PriceStr(newSL), why,
                                PriceStr(open), (int)MathRound(profitDist / point), profitDist / risk);
      if(StringFind(why, "breakeven") >= 0)
         LogMsg(msg);
      else
         LogV(msg);
     }
   else
      LogV("PositionModify failed for #" + IntegerToString((long)ticket) + ": " + IntegerToString((long)g_trade.ResultRetcode()) + " " +
           g_trade.ResultRetcodeDescription());
  }

void ManagePositions(const int secOfDay)
  {
   double atr = (TrailATRMult > 0.0) ? GetATR() : 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_position.SelectByIndex(i))
         continue;
      if(!IsOurPosition())
         continue;
      ulong  tk   = g_position.Ticket();
      long   pDay = ((long)g_position.Time() - g_shiftSec) / 86400;
      if(pDay != g_dayIndex)
        {
         ClosePositionWithLog(tk, "opened on a previous day, stale");
         continue;
        }
      if(secOfDay >= g_forceCloseSec)
        {
         if(!g_forceCloseLogged)
           {
            LogMsg("Force-close hour " + HHMM(g_forceCloseSec) + " reached");
            g_forceCloseLogged = true;
           }
         ClosePositionWithLog(tk, "force-close hour");
         continue;
        }
      ManageStops(tk, g_position.PositionType(), g_position.PriceOpen(), g_position.StopLoss(), g_position.TakeProfit(), atr);
     }
  }

//+------------------------------------------------------------------+
//| Chart status line                                                |
//+------------------------------------------------------------------+
void UpdateComment(const int secOfDay)
  {
   if(MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   string rng = g_rangeReady ? (PriceStr(g_rangeLow) + " - " + PriceStr(g_rangeHigh) + " (" +
                                IntegerToString((int)MathRound((g_rangeHigh - g_rangeLow) / g_symbol.Point())) + " pts) " + g_dayVerdict)
                             : "not yet computed";
   string phase;
   if(g_dayDone)
      phase = "day done";
   else if(secOfDay < g_rangeEndSec)
      phase = "building range";
   else if(secOfDay < g_tradeStartSec)
      phase = "waiting for window";
   else if(InTradeWindow(secOfDay))
      phase = "trade window";
   else
      phase = "managing";
   Comment("LondonRangeBreakout | research tool, no performance implied\n",
           "Schedule time ", HHMM(secOfDay), " | phase: ", phase, "\n",
           "Range: ", rng, "\n",
           "Fills today: ", IntegerToString(g_tradesToday), " | positions: ", IntegerToString(CountOurPositions()),
           " | pending: ", IntegerToString(CountOurPendingOrders()), " | day P/L: ", DoubleToString(g_dayProfit, 2), "\n",
           "Spread: ", IntegerToString(CurrentSpreadPoints()), " pts (cap ", IntegerToString(MaxSpreadPoints), ")");
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!g_symbol.RefreshRates())
      return;

   datetime srvNow = TimeCurrent();
   long lgNow      = (long)ServerToLogical(srvNow);
   long dayIdx     = lgNow / 86400;
   if(dayIdx != g_dayIndex)
      StartNewDay(dayIdx);
   int secOfDay = (int)(lgNow - (long)g_dayStartLogical);

   // 1. fill / close detection (authoritative path)
   PollPositions();

   // 2. open positions: stale close, force close, break-even, trailing
   ManagePositions(secOfDay);

   // 3. pending-order housekeeping
   if(g_cancelPendingRequested)
     {
      if(DeleteOurPendingOrders("OCO retry"))
         g_cancelPendingRequested = false;
     }
   if(secOfDay >= g_tradeEndSec)
     {
      if(CountOurPendingOrders() > 0)
         DeleteOurPendingOrders(secOfDay >= g_forceCloseSec ? "force-close hour" : "trade window ended");
      if(!g_dayDone)
        {
         g_dayDone = true;
         if(!g_tradeEndLogged)
           {
            g_tradeEndLogged = true;
            if(g_rangeReady && g_dayValid && g_tradesToday == 0)
               LogMsg("Trade window ended without a fill: no breakout today");
            else
               LogV("Trade window ended");
           }
        }
     }

   // 4. range
   if(!g_rangeReady && !g_dayDone && secOfDay >= g_rangeEndSec)
      ComputeRange();

   // 5. entries
   if(!g_dayDone && g_rangeReady && g_dayValid && InTradeWindow(secOfDay))
      HandleEntries(secOfDay);

   UpdateComment(secOfDay);
  }

//+------------------------------------------------------------------+
//| Trade transaction handler (fast path for fills and exits)        |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   ulong deal = trans.deal;
   if(deal == 0)
      return;
   if(!HistoryDealSelect(deal))
      return;
   if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol)
      return;
   if(HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicNumber)
      return;
   ENUM_DEAL_TYPE dtype = (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
   if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL)
      return;

   ENUM_DEAL_ENTRY  entry  = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
   ENUM_DEAL_REASON reason = (ENUM_DEAL_REASON)HistoryDealGetInteger(deal, DEAL_REASON);
   double price  = HistoryDealGetDouble(deal, DEAL_PRICE);
   double vol    = HistoryDealGetDouble(deal, DEAL_VOLUME);
   double net    = HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP) + HistoryDealGetDouble(deal, DEAL_COMMISSION);

   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_INOUT || entry == DEAL_ENTRY_OUT_BY)
     {
      g_dayProfit += net;
      LogMsg(StringFormat("EXIT deal #%s %s %s lots @ %s reason=%s net=%.2f (profit incl. swap+commission)",
                          IntegerToString((long)deal), EnumToString(dtype), LotsStr(vol), PriceStr(price), EnumToString(reason), net));
      if(entry != DEAL_ENTRY_INOUT && CountOurPositions() == 0)
         OnPositionClosed("transaction");
     }
   if(entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
     {
      LogV(StringFormat("ENTRY deal #%s %s %s lots @ %s reason=%s", IntegerToString((long)deal), EnumToString(dtype), LotsStr(vol), PriceStr(price), EnumToString(reason)));
      if(entry == DEAL_ENTRY_INOUT)
         g_posOpenSeen = false;     // the previous position was reversed; treat as a new fill
      OnFillDetected("transaction");
     }
  }
//+------------------------------------------------------------------+
