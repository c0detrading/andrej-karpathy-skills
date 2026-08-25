//+------------------------------------------------------------------+
//|                                                NasdaqScalper.mq5 |
//|  Ultra-scalping Expert Advisor for the Nasdaq 100 index          |
//|  (US100 / NAS100 / USTEC CFD, or NQ/MNQ futures symbol).         |
//|                                                                  |
//|  Exits by specification:                                         |
//|    Take profit : +5.0 index points                               |
//|    Stop loss   : -2.5 index points                               |
//|    At +3.0 points profit the stop loss moves to break even;      |
//|    while momentum keeps gaining, SL trails behind price and TP   |
//|    is pushed ahead so winners can run (see ManagePosition()).    |
//|                                                                  |
//|  Entry signal (swappable, see GetSignal()):                      |
//|    Fast EMA / slow EMA crossover, evaluated once per closed bar. |
//|                                                                  |
//|  Recommended chart timeframe: M1.                                |
//+------------------------------------------------------------------+
#property copyright ""
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

//--- exit rules (index points, i.e. price units on US100-style quotes)
input double InpTakeProfitPts = 5.0;   // Take profit (index points)
input double InpStopLossPts   = 2.5;   // Stop loss (index points)

//--- trade management (index points)
input double InpBreakEvenTriggerPts = 3.0; // Move SL to entry after this much profit
input double InpTrailDistancePts    = 2.5; // Trailing SL distance while momentum is gaining
input double InpTrailTpExtendPts    = 5.0; // Keep TP this far ahead while momentum is gaining

//--- position sizing
input double InpLots          = 0.1;   // Lot size (contracts)

//--- entry signal
input int    InpFastEMA       = 9;     // Fast EMA period
input int    InpSlowEMA       = 21;    // Slow EMA period

//--- safety filters
input double InpMaxSpreadPts  = 1.5;   // Max allowed spread (index points), 0 = no limit
input bool   InpUseTimeFilter = true;  // Trade only during set hours (server time)
input int    InpStartHour     = 15;    // Trading start hour (server time)
input int    InpEndHour       = 21;    // Trading end hour (server time)

//--- housekeeping
input long   InpMagic         = 20260825; // Magic number

CTrade   g_trade;
int      g_fastHandle = INVALID_HANDLE;
int      g_slowHandle = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpStopLossPts <= 0 || InpTakeProfitPts <= 0)
     {
      Print("Stop loss and take profit must be positive.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpFastEMA >= InpSlowEMA)
     {
      Print("Fast EMA period must be smaller than slow EMA period.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_fastHandle = iMA(_Symbol, _Period, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   g_slowHandle = iMA(_Symbol, _Period, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(g_fastHandle == INVALID_HANDLE || g_slowHandle == INVALID_HANDLE)
     {
      Print("Failed to create EMA indicator handles.");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);

   // Warn if the broker's minimum stop distance makes a 2.5-point SL impossible.
   double stopsLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(stopsLevelPts > InpStopLossPts)
      PrintFormat("WARNING: broker minimum stop distance is %.2f index points, "
                  "larger than the %.2f point stop loss. Orders will be rejected.",
                  stopsLevelPts, InpStopLossPts);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_fastHandle != INVALID_HANDLE) IndicatorRelease(g_fastHandle);
   if(g_slowHandle != INVALID_HANDLE) IndicatorRelease(g_slowHandle);
  }

//+------------------------------------------------------------------+
//| Returns +1 (buy), -1 (sell) or 0 (no signal) on the last closed  |
//| bar. Replace this function to change the entry strategy; the     |
//| fixed 5.0 / 2.5 point exits are applied independently of it.     |
//+------------------------------------------------------------------+
int GetSignal()
  {
   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   // Series order: index 0 = last closed bar, index 1 = the bar before it.
   if(CopyBuffer(g_fastHandle, 0, 1, 2, fast) != 2 ||
      CopyBuffer(g_slowHandle, 0, 1, 2, slow) != 2)
      return(0);

   bool crossedUp   = fast[1] <= slow[1] && fast[0] > slow[0];
   bool crossedDown = fast[1] >= slow[1] && fast[0] < slow[0];

   if(crossedUp)   return(1);
   if(crossedDown) return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
//| Momentum is "gaining" when the fast/slow EMA gap in the trade    |
//| direction (dir = +1 buy, -1 sell) is positive and wider on the   |
//| last closed bar than on the bar before it.                       |
//+------------------------------------------------------------------+
bool MomentumGaining(int dir)
  {
   double fast[], slow[];
   ArraySetAsSeries(fast, true);
   ArraySetAsSeries(slow, true);
   if(CopyBuffer(g_fastHandle, 0, 1, 2, fast) != 2 ||
      CopyBuffer(g_slowHandle, 0, 1, 2, slow) != 2)
      return(false);

   double gapNow  = dir * (fast[0] - slow[0]);
   double gapPrev = dir * (fast[1] - slow[1]);
   return(gapNow > 0 && gapNow > gapPrev);
  }

//+------------------------------------------------------------------+
//| Returns the ticket of this EA's open position, or 0 if none.     |
//+------------------------------------------------------------------+
ulong FindPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return(ticket);
     }
   return(0);
  }

//+------------------------------------------------------------------+
//| Runs every tick while a position is open:                        |
//|  1. At +InpBreakEvenTriggerPts profit, move SL to the entry.     |
//|  2. While momentum keeps gaining, trail SL InpTrailDistancePts   |
//|     behind price and keep TP InpTrailTpExtendPts ahead of it.    |
//| SL and TP only ever move in the trade's favor (ratchet).         |
//+------------------------------------------------------------------+
void ManagePosition(ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return;

   int    dir   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL = PositionGetDouble(POSITION_SL);
   double curTP = PositionGetDouble(POSITION_TP);

   // Price the position would close at right now.
   double close = SymbolInfoDouble(_Symbol, dir > 0 ? SYMBOL_BID : SYMBOL_ASK);
   double profitPts = dir * (close - entry);
   if(profitPts < InpBreakEvenTriggerPts) return;

   double newSL = curSL;
   double newTP = curTP;

   // 1) Break even: SL still on the losing side of entry (or missing).
   if(curSL == 0 || dir * (entry - curSL) > 0)
      newSL = entry;

   // 2) Momentum trailing.
   if(MomentumGaining(dir))
     {
      double trailSL = NormalizeToTick(close - dir * InpTrailDistancePts);
      if(dir * (trailSL - newSL) > 0)
         newSL = trailSL;

      double trailTP = NormalizeToTick(close + dir * InpTrailTpExtendPts);
      if(dir * (trailTP - newTP) > 0)
         newTP = trailTP;
     }

   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(MathAbs(newSL - curSL) < tick && MathAbs(newTP - curTP) < tick)
      return;

   if(!g_trade.PositionModify(ticket, NormalizeToTick(newSL), newTP))
      PrintFormat("PositionModify failed: %d / %s", g_trade.ResultRetcode(),
                  g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
bool TradingHoursOk()
  {
   if(!InpUseTimeFilter) return(true);
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   if(InpStartHour <= InpEndHour)
      return(now.hour >= InpStartHour && now.hour < InpEndHour);
   // Window crosses midnight.
   return(now.hour >= InpStartHour || now.hour < InpEndHour);
  }

//+------------------------------------------------------------------+
double NormalizeToTick(double price)
  {
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) return(NormalizeDouble(price, _Digits));
   return(NormalizeDouble(MathRound(price / tick) * tick, _Digits));
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Manage the open position on every tick.
   ulong ticket = FindPosition();
   if(ticket != 0)
      ManagePosition(ticket);

   // Entries: act once per bar, on bar open.
   datetime barTime = iTime(_Symbol, _Period, 0);
   if(barTime == g_lastBarTime) return;
   g_lastBarTime = barTime;

   if(ticket != 0) return;                // one position at a time
   if(!TradingHoursOk()) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Spread filter: on US100-style symbols 1.0 of price = 1 index point.
   if(InpMaxSpreadPts > 0 && (ask - bid) > InpMaxSpreadPts) return;

   int signal = GetSignal();
   if(signal == 0) return;

   if(signal > 0)
     {
      double sl = NormalizeToTick(ask - InpStopLossPts);
      double tp = NormalizeToTick(ask + InpTakeProfitPts);
      if(!g_trade.Buy(InpLots, _Symbol, 0.0, sl, tp, "NasdaqScalper buy"))
         PrintFormat("Buy failed: %d / %s", g_trade.ResultRetcode(),
                     g_trade.ResultRetcodeDescription());
     }
   else
     {
      double sl = NormalizeToTick(bid + InpStopLossPts);
      double tp = NormalizeToTick(bid - InpTakeProfitPts);
      if(!g_trade.Sell(InpLots, _Symbol, 0.0, sl, tp, "NasdaqScalper sell"))
         PrintFormat("Sell failed: %d / %s", g_trade.ResultRetcode(),
                     g_trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
