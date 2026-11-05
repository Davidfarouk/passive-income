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
#property link        ""
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
