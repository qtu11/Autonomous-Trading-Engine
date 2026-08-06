//+------------------------------------------------------------------+
//|    Autonomous Trading Engine (ATE) - By QTusdev (Nguyễn Quang Tú)|
//|                                    https://github.com/qtu11       |
//+------------------------------------------------------------------+
#property copyright "Autonomous Trading Engine (ATE) - By QTusdev (Nguyễn Quang Tú)"
#property link      "https://github.com/qtu11"
#property version   "3.00"
#property description "Pure MQL5 Execution Bridge / Protocol for Autonomous Trading Engine (ATE)"
#property description "All trading decisions & signals are driven 100% by AI Engine"

#include <Trade\Trade.mqh>

//--- Input Parameters
input string   InpApiUrl           = "https://autonomous-trading-engine.vercel.app/api/v1/"; // AI FastAPI Server URL via Vercel (public cloud proxy to backend)
input ulong    InpMagicNumber      = 888999;                 // EA Magic Number
input string   InpSymbol           = "XAUUSDm";              // Trading Symbol (Blank for auto-detect chart)
input int      InpPollIntervalSec  = 1;                      // AI Protocol Poll Interval (seconds)
input bool     InpExecutionEnabled = true;                 // Fail closed until the command protocol is upgraded
input string   InpBridgeToken      = "20022007@Tu";                    // Required Bearer token for protected bridge endpoints
input string   InpExecutorId       = "ate-ea-local";        // Unique executor identity for command leases
input bool     InpVerifyAccount    = true;                  // Strict Account Verification (DEMO + LIVE allowlist)
input string   InpExpectedCompany   = "Exness Technologies Ltd"; // Broker company allowlist
input long     InpExpectedLogin    = 0;              // DEMO account allowlist
input string   InpExpectedServer   = "";     // DEMO server allowlist
input long     InpExpectedLiveLogin = 0;                    // LIVE account allowlist (0 = not configured -> LIVE refused)
input string   InpExpectedLiveServer= "";                   // LIVE server allowlist (empty = not configured)
input double   InpMaxSpread        = 0.50;                   // XAUUSDm raw-price spread cap
input int      InpMaxPositions     = 1;                      // Matching symbol/magic position cap
input int      InpMaxDeviationPts  = 50;                     // Broker request deviation cap
input int      InpCalendarIntervalSec = 300;                 // Economic calendar push interval (seconds)
input int      InpMaxConsecutiveFailures = 5;                // Backoff threshold before slowing poll
input int      InpTelemetryIntervalSec = 5;                  // Telemetry/heartbeat interval (seconds, >=1)
input int      InpClaimIntervalSec   = 3;                    // Claim poll interval (seconds, >=1, < command TTL)
input bool     InpNewsProtectionEnabled = true;             // Block new BUY/SELL entries around High impact USD news
input int      InpProtectionIntervalSec = 30;               // News protection state poll interval (seconds)

//--- Global Variables
CTrade         m_trade;
datetime       m_last_poll_time;
datetime       m_last_calendar_push = 0;
datetime       m_last_telemetry_sent = 0;
datetime       m_last_claim_attempt = 0;
datetime       m_last_protection_check = 0;
int            m_consecutive_failures = 0;
string         g_symbol;
string         g_protection_level = "none";
int            g_protection_live_seconds = 0;
string         g_protection_event = "";
bool           g_protection_comment_shown = false;

//--- Returns InpApiUrl with trailing slashes, /api/v1 and /api trimmed to construct endpoints cleanly
string QuantAIApiBase()
{
   string u = InpApiUrl;
   while(StringLen(u) > 0 && StringGetCharacter(u, StringLen(u) - 1) == '/')
      u = StringSubstr(u, 0, StringLen(u) - 1);
   
   int len = StringLen(u);
   if(len >= 7 && StringSubstr(u, len - 7) == "/api/v1")
      u = StringSubstr(u, 0, len - 7);
   else if(len >= 4 && StringSubstr(u, len - 4) == "/api")
      u = StringSubstr(u, 0, len - 4);
      
   return u;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   g_symbol = InpSymbol;
   if(StringLen(g_symbol) == 0)
      g_symbol = Symbol();

   QuantAILog(StringFormat("INIT_BEGIN url=%s token_len=%d exec=%s verify=%s poll=%ds", InpApiUrl, StringLen(InpBridgeToken), InpExecutionEnabled ? "true" : "false", InpVerifyAccount ? "true" : "false", InpPollIntervalSec));

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpMaxDeviationPts);
   m_trade.SetAsyncMode(false);
   
   if(InpPollIntervalSec < 1 || InpMagicNumber != 888999)
   {
      QuantAILog("INIT_FAILED: poll interval or magic is invalid.");
      Print("QuantAI configuration rejected: poll interval or magic is invalid.");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(!SymbolSelect(g_symbol, true))
   {
      QuantAILog(StringFormat("INIT_FAILED: symbol %s is unavailable.", g_symbol));
      PrintFormat("QuantAI configuration rejected: symbol %s is unavailable.", g_symbol);
      return(INIT_FAILED);
   }
   if(InpExecutionEnabled && !IsAuthorizedEnvironment())
   {
      // Do NOT hard-fail here: MT5 resets the Algo Trading button OFF on every
      // terminal launch, so a hard INIT_FAILED would permanently kill the EA
      // before the operator can toggle the button. Keep the EA alive so
      // telemetry/heartbeat still flow; execution stays fail-closed because
      // PollAndExecuteAISignals() re-checks IsAuthorizedEnvironment() before
      // claiming/executing any command.
      QuantAILog(StringFormat("INIT_WARNING: execution unauthorized. trade_allowed=%d mql_trade_allowed=%d account=#%I64d@%s company=%s mode=%s (will retry at claim time)", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED), AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel()));
   }

   // Set 1-second timer for polling AI Protocol
   EventSetTimer(InpPollIntervalSec);
   
   QuantAILog(StringFormat("INIT_OK account=#%I64d@%s company=%s mode=%s trade_allowed=%d mql_trade_allowed=%d", AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel(), TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED)));
   PrintFormat("=================================================");
   PrintFormat("QuantAI MQL5 Pure Execution Protocol v3.0 Started");
   PrintFormat("Connected AI Bridge: %s | Symbol: %s", InpApiUrl, g_symbol);
   PrintFormat("Account: #%I64d @ %s (mode: %s)", AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountModeLabel());
   PrintFormat("=================================================");
   return(INIT_SUCCEEDED);
}

bool IsAuthorizedEnvironment()
{
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      return false;
   long tradeMode = SymbolInfoInteger(g_symbol, SYMBOL_TRADE_MODE);
   if(tradeMode != SYMBOL_TRADE_MODE_FULL && tradeMode != SYMBOL_TRADE_MODE_LONGONLY && tradeMode != SYMBOL_TRADE_MODE_SHORTONLY)
      return false;

   if(!InpVerifyAccount)
      return true;

   long login      = AccountInfoInteger(ACCOUNT_LOGIN);
   string server   = AccountInfoString(ACCOUNT_SERVER);
   string company  = AccountInfoString(ACCOUNT_COMPANY);
   long accountMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);

   if(accountMode == ACCOUNT_TRADE_MODE_DEMO)
   {
      if(login != InpExpectedLogin)  return false;
      if(server != InpExpectedServer) return false;
      if(company != InpExpectedCompany) return false;
      return true;
   }
   if(accountMode == ACCOUNT_TRADE_MODE_REAL)
   {
      // Fail closed: LIVE is only accepted when the operator explicitly
      // configured a LIVE login/server on this EA instance.
      if(InpExpectedLiveLogin <= 0)      return false;
      if(login != InpExpectedLiveLogin)  return false;
      if(StringLen(InpExpectedLiveServer) > 0 && server != InpExpectedLiveServer) return false;
      if(company != InpExpectedCompany)  return false;
      return true;
   }
   return false;
}

string AccountModeLabel()
{
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL)
      return "REAL";
   return "DEMO";
}

int MatchingPositionCount()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == g_symbol && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         count++;
   }
   return count;
}

bool IsValidCommand(double volume, double stopLoss, double takeProfit, string action)
{
   double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double spread = ask - bid;
   double minVolume = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double maxVolume = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);
   int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   int stopsLevel = (int)SymbolInfoInteger(g_symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freezeLevel = (int)SymbolInfoInteger(g_symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double minimumDistance = MathMax(stopsLevel, freezeLevel) * point;
   if(ask <= 0 || bid <= 0 || spread < 0 || spread > InpMaxSpread || volume < minVolume || volume > maxVolume || step <= 0)
      return false;
   double normalizedVolume = MathRound(volume / step) * step;
   if(MathAbs(normalizedVolume - volume) > step * 0.01)
      return false;
   if(action == "BUY")
      return stopLoss < bid - minimumDistance && takeProfit > ask + minimumDistance;
   if(action == "SELL")
      return stopLoss > ask + minimumDistance && takeProfit < bid - minimumDistance;
   return false;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("QuantAI MQL5 Protocol Bridge Stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert timer function (Polls AI Protocol every 1 sec)            |
//+------------------------------------------------------------------+
void OnTimer()
{
   // 0. Connection watchdog: detect terminal/broker disconnect and back off.
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
   {
      m_consecutive_failures++;
      if(m_consecutive_failures >= InpMaxConsecutiveFailures)
         PrintFormat("QuantAI reconnect watchdog: terminal offline (failures=%d). Backing off.", m_consecutive_failures);
      return; // Skip this cycle; timer fires again and retries automatically.
   }

   // 1. Send Telemetry to AI Engine (also acts as the EA heartbeat) at its own cadence.
   if(TimeLocal() - m_last_telemetry_sent >= InpTelemetryIntervalSec)
   {
      SendTelemetry();
      m_last_telemetry_sent = TimeLocal();
   }

   // 2. Push the broker's real economic calendar on its own cadence.
   if(TimeLocal() - m_last_calendar_push >= InpCalendarIntervalSec)
   {
      SendCalendar();
      m_last_calendar_push = TimeLocal();
   }

   // 2b. Refresh News Protection state (blocks new entries around High impact news).
   if(InpNewsProtectionEnabled && TimeLocal() - m_last_protection_check >= InpProtectionIntervalSec)
   {
      CheckNewsProtection();
      m_last_protection_check = TimeLocal();
   }

   // 3. Poll & Execute Signals Issued strictly by AI at its own cadence.
   //    Keeping telemetry and claim on separate, slower intervals avoids
   //    saturating the terminal's internal WebRequest stack (error 1003/1001).
   if(TimeLocal() - m_last_claim_attempt >= InpClaimIntervalSec)
   {
      PollAndExecuteAISignals();
      m_last_claim_attempt = TimeLocal();
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Pure Protocol Mode: Tick logic is handled via AI Timer polling
}

//+------------------------------------------------------------------+
//| Build authenticated headers for protected bridge endpoints       |
//+------------------------------------------------------------------+
string BridgeHeaders()
{
   return "Content-Type: application/json\r\nAuthorization: Bearer " + InpBridgeToken + "\r\n";
}

//+------------------------------------------------------------------+
//| Send Telemetry data to FastAPI Bridge                            |
//+------------------------------------------------------------------+
void SendTelemetry()
{
   if(StringLen(InpBridgeToken) == 0)
   {
      Print("QuantAI bridge token is not configured; telemetry is blocked.");
      return;
   }
   string headers = BridgeHeaders();
   string payload = StringFormat(
      "{\"symbol\":\"%s\",\"account_id\":%I64d,\"server\":\"%s\",\"broker\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"margin_free\":%.2f,\"profit\":%.2f,\"positions\":%d,\"ask\":%.2f,\"bid\":%.2f}",
      g_symbol,
      AccountInfoInteger(ACCOUNT_LOGIN),
      AccountInfoString(ACCOUNT_SERVER),
      AccountInfoString(ACCOUNT_COMPANY),
      AccountInfoDouble(ACCOUNT_BALANCE),
      AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoDouble(ACCOUNT_MARGIN),
      AccountInfoDouble(ACCOUNT_MARGIN_FREE),
      AccountInfoDouble(ACCOUNT_PROFIT),
      PositionsTotal(),
      SymbolInfoDouble(g_symbol, SYMBOL_ASK),
      SymbolInfoDouble(g_symbol, SYMBOL_BID)
   );
   
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));
   
   int res = WebRequest("POST", QuantAIApiBase() + "/api/telemetry", headers, 3000, data, result, result_headers);
   if(res != 200)
   {
      int err = GetLastError();
      QuantAILogThrottled("TELEMETRY_HTTP_" + string(res), StringFormat("Telemetry push failed (HTTP %d, err=%d). Bridge may be down, URL not allowlisted, or network blocked.", res, err));
   }
   else if(!g_telemetry_ok_logged)
   {
      g_telemetry_ok_logged = true;
      QuantAILog("TELEMETRY_OK: first successful heartbeat to " + InpApiUrl);
   }
}

//+------------------------------------------------------------------+
//| Push the broker's real economic calendar to the AI Engine         |
//+------------------------------------------------------------------+
void SendCalendar()
{
   if(StringLen(InpBridgeToken) == 0)
      return;

   MqlCalendarValue values[];
   datetime from = TimeLocal() - 86400;        // yesterday
   datetime to   = TimeLocal() + 7 * 86400;    // next 7 days
   int total = CalendarValueHistory(values, from, to);
   if(total <= 0)
      return;

   string eventsJson = "";
   int appended = 0;
   for(int i = 0; i < total && appended < 60; i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev))
         continue;
      MqlCalendarCountry country;
      string currency = "USD";
      if(CalendarCountryById(ev.country_id, country))
         currency = country.currency;
      // Focus on USD high/medium impact macro events for XAUUSD.
      if(currency != "USD")
         continue;
      if(ev.importance == CALENDAR_IMPORTANCE_NONE)
         continue;

      string impact = "LOW";
      if(ev.importance == CALENDAR_IMPORTANCE_HIGH)   impact = "HIGH";
      else if(ev.importance == CALENDAR_IMPORTANCE_MODERATE) impact = "MED";

      datetime t = (datetime)values[i].time;
      string day = TimeToString(t, TIME_DATE);
      string tm  = TimeToString(t, TIME_MINUTES);

      string actual   = DoubleToString(values[i].GetActualValue(), 2);
      string forecast = DoubleToString(values[i].GetForecastValue(), 2);
      string previous = DoubleToString(values[i].GetPreviousValue(), 2);

      if(appended > 0)
         eventsJson += ",";
      eventsJson += StringFormat(
         "{\"event_id\":\"%I64u\",\"day\":\"%s\",\"date\":\"%s\",\"time\":\"%s\",\"currency\":\"%s\",\"title\":\"%s\",\"impact\":\"%s\",\"actual\":\"%s\",\"forecast\":\"%s\",\"previous\":\"%s\",\"status\":\"UPCOMING\"}",
         values[i].event_id,
         day, day, tm,
         EscapeJson(currency),
         EscapeJson(ev.name),
         impact,
         actual, forecast, previous
      );
      appended++;
   }

   if(appended == 0)
      return;

   string headers = BridgeHeaders();
   string payload = "{\"source\":\"MT5_CALENDAR\",\"events\":[" + eventsJson + "]}";
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));
   WebRequest("POST", QuantAIApiBase() + "/api/v1/bridge/calendar", headers, 1000, data, result, result_headers);
}

//+------------------------------------------------------------------+
//| Pull News Protection state from the bridge and enforce locally   |
//+------------------------------------------------------------------+
void CheckNewsProtection()
{
   if(StringLen(InpBridgeToken) == 0 || StringLen(InpApiUrl) == 0)
      return;

   string headers = "Authorization: Bearer " + InpBridgeToken + "\r\n";
   char result[];
   string result_headers;
   char empty[];
   int res = WebRequest("GET", QuantAIApiBase() + "/api/economic-calendar/protection", headers, 3000, empty, result, result_headers);
   if(res != 200 || ArraySize(result) == 0)
   {
      if(g_protection_level != "unknown")
      {
         g_protection_level = "unknown";
         QuantAILogThrottled("PROTECTION_UNREACHABLE", StringFormat("News protection state unreachable (HTTP %d, err=%d). Falling back to: allow entries.", res, GetLastError()));
      }
      return;
   }

   string response = CharArrayToString(result);
   string level = ExtractJsonString(response, "\"level\":");
   int liveSeconds = (int)ExtractDouble(response, "\"live_remaining_seconds\":", 0.0);
   string eventTitle = ExtractJsonString(response, "\"title\":");
   if(StringLen(level) == 0)
      level = "none";

   bool changed = (level != g_protection_level);
   g_protection_level = level;
   g_protection_live_seconds = liveSeconds;
   g_protection_event = eventTitle;

   if(changed)
   {
      QuantAILog(StringFormat("NEWS_PROTECTION_STATE level=%s event='%s' live_remaining=%ds", level, eventTitle, liveSeconds));
      if(level == "lockdown" || level == "approaching")
         QuantAILog("NEWS_PROTECTION: new BUY/SELL entries are BLOCKED until the news window passes (CLOSE/MODIFY still allowed).");
      else if(level == "watch")
         QuantAILog("NEWS_PROTECTION: watch mode - High impact news approaching, entries still allowed.");
   }

   UpdateProtectionComment();
}

//+------------------------------------------------------------------+
//| Chart comment showing current News Protection state              |
//+------------------------------------------------------------------+
void UpdateProtectionComment()
{
   if(!InpNewsProtectionEnabled || g_protection_level == "none" || g_protection_level == "unknown")
   {
      if(g_protection_comment_shown)
      {
         Comment("");
         g_protection_comment_shown = false;
      }
      return;
   }

   string statusText = "";
   if(g_protection_level == "lockdown")
      statusText = StringFormat("LOCKDOWN - block entries (%d min remaining)", (g_protection_live_seconds + 59) / 60);
   else if(g_protection_level == "approaching")
      statusText = "APPROACHING - block entries (news < 1h)";
   else if(g_protection_level == "watch")
      statusText = "WATCH - High impact news in 1-5h";

   Comment("NEWS PROTECTION: " + statusText + "\nEvent: " + g_protection_event);
   g_protection_comment_shown = true;
}

//+------------------------------------------------------------------+
//| Structured EA file logging (written to MQL5\Files\)              |
//+------------------------------------------------------------------+
string g_ea_log_file = "";
string g_ea_last_msg  = "";
bool  g_telemetry_ok_logged = false;

string QuantAILogFileName()
{
   if(StringLen(g_ea_log_file) == 0)
      g_ea_log_file = "quantai_ea_" + TimeToString(TimeCurrent(), TIME_DATE) + ".log";
   return g_ea_log_file;
}

void QuantAILog(const string message)
{
   string line = StringFormat("[%s] %s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), message);
   Print(line);
   int handle = FileOpen(QuantAILogFileName(), FILE_READ|FILE_WRITE|FILE_TXT|FILE_UNICODE);
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);
      FileWrite(handle, line);
      FileClose(handle);
   }
}

void QuantAILogThrottled(const string key, string message)
{
   if(key == g_ea_last_msg)
      return;
   g_ea_last_msg = key;
   QuantAILog(message);
}

//+------------------------------------------------------------------+
//| Poll AI Engine for Pending Execution Commands                     |
//+------------------------------------------------------------------+
void PollAndExecuteAISignals()
{
   if(!InpExecutionEnabled || StringLen(InpBridgeToken) == 0)
      return;

   // IMPORTANT: only the identity guard returns here. The position-count guard
   // lives inside the BUY/SELL branch so that CLOSE_POSITION, CLOSE_ALL and
   // MODIFY_SLTP are still claimable while a position is open.
   if(!IsAuthorizedEnvironment())
   {
      QuantAILogThrottled("UNAUTH", StringFormat("Blocked poll: trade_allowed=%d mql_trade_allowed=%d account=#%I64d@%s company=%s mode=%s (allowlist: login=%I64d server=%s company=%s)", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED), AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel(), InpExpectedLogin, InpExpectedServer, InpExpectedCompany));
      return;
   }

   string tradeModeStr = AccountModeLabel();
   string headers = BridgeHeaders();
   string payload = StringFormat("{\"executor_id\":\"%s\",\"symbol\":\"%s\",\"magic\":%I64u,\"account_login\":%I64d,\"account_server\":\"%s\",\"broker_company\":\"%s\",\"trade_mode\":\"%s\"}", EscapeJson(InpExecutorId), EscapeJson(g_symbol), InpMagicNumber, AccountInfoInteger(ACCOUNT_LOGIN), EscapeJson(AccountInfoString(ACCOUNT_SERVER)), EscapeJson(AccountInfoString(ACCOUNT_COMPANY)), tradeModeStr);
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));

   int res = WebRequest("POST", QuantAIApiBase() + "/api/v1/bridge/commands/claim", headers, 3000, data, result, result_headers);
   if(res != 200 || ArraySize(result) == 0)
   {
      int err = GetLastError();
      QuantAILogThrottled("CLAIM_HTTP_" + string(res), StringFormat("Claim request failed (HTTP %d, err=%d). Verify the bridge is up and '" + InpApiUrl + "' is in the MT5 WebRequest allowlist (use hostname/IP, not 127.0.0.1).", res, err));
      return;
   }

   string response = CharArrayToString(result);
   if(StringFind(response, "\"status\":\"CLAIMED\"") < 0)
      return;

   int commandStart = StringFind(response, "\"command\":");
   if(commandStart < 0)
      return;
   string commandJson = StringSubstr(response, commandStart);
   string commandId = ExtractJsonString(commandJson, "\"command_id\":");
   string action = ExtractJsonString(commandJson, "\"action\":");
   string commandSymbol = ExtractJsonString(commandJson, "\"symbol\":");
   long commandMagic = (long)ExtractDouble(commandJson, "\"magic\":", 0.0);
   double volume = ExtractDouble(commandJson, "\"volume\":", 0.0);
   double stopLoss = ExtractDouble(commandJson, "\"stop_loss\":", 0.0);
   double takeProfit = ExtractDouble(commandJson, "\"take_profit\":", 0.0);
   string reason = ExtractJsonString(commandJson, "\"reason\":");
   if(StringLen(commandId) == 0 || commandSymbol != g_symbol || commandMagic != (long)InpMagicNumber)
   {
      QuantAILog(StringFormat("REJECT_INVALID_COMMAND command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_INVALID_COMMAND");
      return;
   }
   if(!IsAuthorizedEnvironment())
   {
      QuantAILog(StringFormat("REJECT_EXECUTION_GUARD command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_EXECUTION_GUARD");
      return;
   }

   QuantAILog(StringFormat("CLAIMED command=%s action=%s volume=%.2f sl=%.2f tp=%.2f reason=%s", commandId, action, volume, stopLoss, takeProfit, reason));

   int symbolDigits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   m_trade.SetTypeFillingBySymbol(g_symbol);
   bool requestAccepted = false;
   ulong resultTicket = 0;

   if(action == "BUY" || action == "SELL")
   {
      // News Protection: fail-closed on new entries only; CLOSE/MODIFY stay claimable.
      if(InpNewsProtectionEnabled && (g_protection_level == "lockdown" || g_protection_level == "approaching"))
      {
         QuantAILog(StringFormat("REJECT_NEWS_PROTECTION command=%s action=%s level=%s event='%s' live_remaining=%ds", commandId, action, g_protection_level, g_protection_event, g_protection_live_seconds));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_NEWS_PROTECTION");
         return;
      }
      if(MatchingPositionCount() >= InpMaxPositions || !IsValidCommand(volume, stopLoss, takeProfit, action))
      {
         QuantAILog(StringFormat("REJECT_EXECUTION_GUARD command=%s action=%s positions=%d reason=%s", commandId, action, MatchingPositionCount(), reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_EXECUTION_GUARD");
         return;
      }
      if(action == "BUY")
         requestAccepted = m_trade.Buy(volume, g_symbol, SymbolInfoDouble(g_symbol, SYMBOL_ASK), NormalizeDouble(stopLoss, symbolDigits), NormalizeDouble(takeProfit, symbolDigits), "QuantAI v1 BUY");
      else
         requestAccepted = m_trade.Sell(volume, g_symbol, SymbolInfoDouble(g_symbol, SYMBOL_BID), NormalizeDouble(stopLoss, symbolDigits), NormalizeDouble(takeProfit, symbolDigits), "QuantAI v1 SELL");
      resultTicket = m_trade.ResultOrder();
   }
   else if(action == "MODIFY_SLTP")
   {
      ulong ticket = ExtractTicketFromReason(reason);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
      {
         QuantAILog(StringFormat("REJECT_TICKET_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_TICKET_NOT_FOUND");
         return;
      }
      requestAccepted = m_trade.PositionModify(ticket, NormalizeDouble(stopLoss, symbolDigits), NormalizeDouble(takeProfit, symbolDigits));
      resultTicket = ticket;
   }
   else if(action == "CLOSE_POSITION")
   {
      ulong ticket = ExtractTicketFromReason(reason);
      if(ticket == 0)
      {
         QuantAILog(StringFormat("REJECT_TICKET_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_TICKET_NOT_FOUND");
         return;
      }
      requestAccepted = m_trade.PositionClose(ticket);
      resultTicket = ticket;
   }
   else if(action == "CLOSE_ALL")
   {
      int closed = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == g_symbol && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            if(m_trade.PositionClose(ticket))
               closed++;
         }
      }
      requestAccepted = true;
      resultTicket = (ulong)closed;
   }
   else if(action == "CANCEL_PENDING")
   {
      ulong orderTicket = ExtractOrderFromReason(reason);
      if(orderTicket == 0)
      {
         QuantAILog(StringFormat("REJECT_ORDER_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_ORDER_NOT_FOUND");
         return;
      }
      requestAccepted = m_trade.OrderDelete(orderTicket);
      resultTicket = orderTicket;
   }
   else
   {
      QuantAILog(StringFormat("REJECT_UNSUPPORTED_ACTION command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_UNSUPPORTED_ACTION");
      return;
   }

   uint retcode = m_trade.ResultRetcode();
   bool executed = requestAccepted && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_DONE_PARTIAL || retcode == TRADE_RETCODE_PLACED);
   if(executed)
   {
      m_consecutive_failures = 0;
      QuantAILog(StringFormat("EXECUTED command=%s action=%s ticket=%I64u retcode=%u (%s) reason=%s", commandId, action, resultTicket, retcode, m_trade.ResultRetcodeDescription(), reason));
      SendCommandReceipt(commandId, "EXECUTED", resultTicket, retcode, m_trade.ResultRetcodeDescription());
   }
   else
   {
      QuantAILog(StringFormat("FAILED command=%s action=%s retcode=%u (%s) reason=%s", commandId, action, retcode, m_trade.ResultRetcodeDescription(), reason));
      SendCommandReceipt(commandId, "FAILED", 0, retcode, m_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Extract a position/order ticket embedded in the command reason    |
//+------------------------------------------------------------------+
ulong ExtractTicketFromReason(string reason)
{
   int pos = StringFind(reason, "ticket=");
   if(pos < 0)
      return 0;
   return (ulong)StringToInteger(StringSubstr(reason, pos + 7));
}

ulong ExtractOrderFromReason(string reason)
{
   int pos = StringFind(reason, "order=");
   if(pos < 0)
      return 0;
   return (ulong)StringToInteger(StringSubstr(reason, pos + 6));
}

string ExtractJsonString(string json, string key)
{
   int start = StringFind(json, key);
   if(start < 0)
      return "";
   start += StringLen(key);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '"'))
      start++;
   int end = StringFind(json, "\"", start);
   if(end <= start)
      return "";
   return StringSubstr(json, start, end - start);
}

string EscapeJson(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   return value;
}

void SendCommandReceipt(string commandId, string receiptStatus, ulong orderTicket, uint retcode, string resultMessage)
{
   if(StringLen(commandId) == 0)
      return;
   string receiptId = StringFormat("%s-%I64d-%u", InpExecutorId, TimeLocal(), GetTickCount());
   string headers = BridgeHeaders();
   string payload = StringFormat("{\"executor_id\":\"%s\",\"receipt_id\":\"%s\",\"status\":\"%s\",\"retcode\":%u,\"result_message\":\"%s\",\"order_ticket\":%I64u}", EscapeJson(InpExecutorId), EscapeJson(receiptId), EscapeJson(receiptStatus), retcode, EscapeJson(resultMessage), orderTicket);
   char data[];
   char result[];
   string resultHeaders;
   StringToCharArray(payload, data, 0, StringLen(payload));
   WebRequest("POST", QuantAIApiBase() + "/api/v1/bridge/commands/" + commandId + "/receipt", headers, 1000, data, result, resultHeaders);
}

//+------------------------------------------------------------------+
//| Helper JSON Double Extractor                                     |
//+------------------------------------------------------------------+
double ExtractDouble(string json, string key, double defaultValue)
{
   int pos = StringFind(json, key);
   if(pos < 0) return defaultValue;
   
   pos += StringLen(key);
   string sub = StringSubstr(json, pos, 30);
   int comma = StringFind(sub, ",");
   int brace = StringFind(sub, "}");
   int endPos = (comma >= 0 && (brace < 0 || comma < brace)) ? comma : brace;
   if(endPos > 0) sub = StringSubstr(sub, 0, endPos);
   
   double val = StringToDouble(sub);
   return (val > 0) ? val : defaultValue;
}
//+------------------------------------------------------------------+
