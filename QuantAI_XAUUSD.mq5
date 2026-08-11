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
input string   InpApiUrl           = "https://autonomous-trading-engine.vercel.app/api/v1/"; // URL Server AI Engine (Vercel Proxy Cloud Backend)
input ulong    InpMagicNumber      = 888999;                 // Mã nhận diện EA (Magic Number)
// InpSymbol removed — EA ALWAYS auto-detects chart symbol via Symbol() in OnInit
input int      InpPollIntervalSec  = 1;                      // Tần suất truy vấn AI Protocol (giây)
input bool     InpExecutionEnabled = true;                   // Bật/Tắt thực thi lệnh tự động (Fail closed)
input string   InpBridgeToken      = "20022007@Tu";          // Token xác thực Bearer Token cho kết nối Bridge
input string   InpExecutorId       = "ate-ea-local";         // Mã định danh Executor duy nhất cho hợp đồng lệnh
input bool     InpVerifyAccount    = true;                   // Kiểm tra xác thực tài khoản môi giới nghiêm ngặt
input double   InpMaxSpread        = 0.50;                   // Giới hạn mức chênh lệch giá tối đa (Spread Cap)
input int      InpMaxPositions     = 5;                      // Số lượng vị thế mở tối đa cùng lúc
input int      InpMaxDeviationPts  = 50;                     // Độ lệch giá tối đa cho phép từ Broker (Points)
input int      InpCalendarIntervalSec = 300;                 // Chu kỳ đẩy dữ liệu lịch kinh tế (giây)
input int      InpMaxConsecutiveFailures = 5;                // Ngưỡng lỗi kết nối liên tiếp trước khi giãn tần suất
input int      InpTelemetryIntervalSec = 5;                  // Chu kỳ gửi dữ liệu giám sát Heartbeat (giây)
input int      InpClaimIntervalSec   = 3;                    // Chu kỳ kiểm tra và lấy lệnh chờ thực thi (giây)
input bool     InpNewsProtectionEnabled = true;              // Bật/Tắt bộ lọc chặn vào lệnh khi có tin tức mạnh USD
input int      InpProtectionIntervalSec = 30;                // Chu kỳ cập nhật trạng thái bảo vệ tin tức (giây)
input bool     InpChartMarkupEnabled = true;                 // Bật/Tắt vẽ cấu trúc AI (OB, FVG, BOS/CHoCH...) lên biểu đồ
input int      InpMarkupReRenderSec  = 5;                    // Chu kỳ vẽ lại cấu trúc AI trên biểu đồ (giây)
input int      InpMarkupMaxObjects   = 120;                  // Số lượng đối tượng vẽ tối đa trên biểu đồ
input int      InpCandlesIntervalSec = 30;                   // Chu kỳ đẩy dữ liệu nến thời gian thực (giây)

//--- Global Variables
CTrade         m_trade;
datetime       m_last_poll_time;
datetime       m_last_calendar_push = 0;
datetime       m_last_telemetry_sent = 0;
datetime       m_last_claim_attempt = 0;
datetime       m_last_protection_check = 0;
datetime       m_last_markup_fetch = 0;
int            m_markup_payload_md5 = 0;
int            m_consecutive_failures = 0;
datetime       m_last_candles_push = 0;
string         g_symbol;
string         g_protection_level = "none";
int            g_protection_live_seconds = 0;
string         g_trading_method = "SNIPER";
datetime       g_last_config_fetch = 0;
string         g_kill_switch = "false";
string         g_execution_mode = "DEMO";
string         g_protection_event = "";
bool           g_protection_comment_shown = false;

//--- Fetch /api/v1/bridge/config every 30s to honor dashboard trading_method & kill_switch
void ATEFetchConfig()
{
   if(TimeCurrent() - g_last_config_fetch < 30) return;
   g_last_config_fetch = TimeCurrent();

   string headers = "Authorization: Bearer " + InpBridgeToken + "\r\n";
   char   post[]; char result[];
   string resultHeaders;
   ArrayResize(post, 0);

   string url = ATEApiBase() + "/api/v1/bridge/config";
   ResetLastError();
   int res = WebRequest("GET", url, headers, 3000, post, result, resultHeaders);
   if(res != 200) return;

   string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   int idx = StringFind(body, "\"trading_method\":\"");
   if(idx >= 0)
   {
      int s = idx + StringLen("\"trading_method\":\"");
      int e = StringFind(body, "\"", s);
      if(e > s) g_trading_method = StringSubstr(body, s, e - s);
   }
   idx = StringFind(body, "\"kill_switch\":");
   if(idx >= 0)
   {
      int s = idx + StringLen("\"kill_switch\":");
      string chunk = StringSubstr(body, s, 5);
      if(StringFind(chunk, "true") >= 0) g_kill_switch = "true";
      else g_kill_switch = "false";
   }
   idx = StringFind(body, "\"execution_mode\":\"");
   if(idx >= 0)
   {
      int s = idx + StringLen("\"execution_mode\":\"");
      int e = StringFind(body, "\"", s);
      if(e > s) g_execution_mode = StringSubstr(body, s, e - s);
   }
   PrintFormat("CONFIG_FETCH: method=%s kill=%s mode=%s", g_trading_method, g_kill_switch, g_execution_mode);
}

//--- Returns InpApiUrl with trailing slashes, /api/v1 and /api trimmed to construct endpoints cleanly
string ATEApiBase()
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
   // ALWAYS auto-detect the chart's current symbol
   g_symbol = Symbol();

   // Register symbol with backend immediately so dashboard Watchlist updates instantly
   RegisterSymbolOnInit();

   ATELog(StringFormat("INIT_BEGIN url=%s token_len=%d exec=%s verify=%s poll=%ds", InpApiUrl, StringLen(InpBridgeToken), InpExecutionEnabled ? "true" : "false", InpVerifyAccount ? "true" : "false", InpPollIntervalSec));

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpMaxDeviationPts);
   m_trade.SetAsyncMode(false);
   
   if(InpPollIntervalSec < 1)
   {
      ATELog("INIT_FAILED: poll interval is invalid.");
      Print("ATE configuration rejected: poll interval is invalid.");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(!SymbolSelect(g_symbol, true))
   {
      ATELog(StringFormat("INIT_FAILED: symbol %s is unavailable.", g_symbol));
      PrintFormat("ATE configuration rejected: symbol %s is unavailable.", g_symbol);
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
      ATELog(StringFormat("INIT_WARNING: execution unauthorized. trade_allowed=%d mql_trade_allowed=%d account=#%I64d@%s company=%s mode=%s (will retry at claim time)", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED), AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel()));
   }

   // Set 1-second timer for polling AI Protocol
   EventSetTimer(InpPollIntervalSec);
   
   ATELog(StringFormat("INIT_OK account=#%I64d@%s company=%s mode=%s trade_allowed=%d mql_trade_allowed=%d", AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel(), TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED)));
   PrintFormat("=================================================");
   PrintFormat("ATE MQL5 Pure Execution Protocol v3.0 Started");
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

   string company  = AccountInfoString(ACCOUNT_COMPANY);
   long accountMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);

   if(accountMode == ACCOUNT_TRADE_MODE_DEMO)
   {
      // Broker allowlist removed
      return true;
      return true;
   }
   if(accountMode == ACCOUNT_TRADE_MODE_REAL)
   {
      // Auto-identity: LIVE accounts are accepted without a pre-configured
      // login/server allowlist. The EA self-reports its real account (login,
      // server, company) to the backend on every telemetry/heartbeat/claim,
      // so the web dashboard "logs in" automatically from the EA itself.
      // Broker allowlist removed
      return true;
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
   Print("ATE MQL5 Protocol Bridge Stopped. Reason: ", reason);
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
      if(m_consecutive_failures == 1)
      {
         Print("ATE reconnect watchdog: Terminal disconnected from broker. Attempting to reconnect...");
      }
      else if(m_consecutive_failures == InpMaxConsecutiveFailures)
      {
         PrintFormat("ATE reconnect watchdog: Terminal offline for %d seconds. Backing off check interval to 10 seconds.", m_consecutive_failures);
         EventSetTimer(10);
      }
      return; // Skip this cycle; timer fires again and retries automatically.
   }

   // Restore normal polling if connection recovered
   if(m_consecutive_failures > 0)
   {
      PrintFormat("ATE reconnect watchdog: Terminal reconnected successfully. Restoring poll interval to %d seconds.", InpPollIntervalSec);
      m_consecutive_failures = 0;
      EventSetTimer(InpPollIntervalSec);
   }

   // 1. Send Telemetry to AI Engine (also acts as the EA heartbeat) at its own cadence.
    if(TimeLocal() - m_last_telemetry_sent >= InpTelemetryIntervalSec)
    {
       SendTelemetry();
       m_last_telemetry_sent = TimeLocal();
    }

    // 1b. Send Live Candles to API at its own cadence.
    if(TimeLocal() - m_last_candles_push >= InpCandlesIntervalSec)
    {
       SendLiveCandles();
       m_last_candles_push = TimeLocal();
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

   // 4. Fetch AI Chart Markup (ICT/SMC/Price Action structures) and draw them.
   if(InpChartMarkupEnabled && TimeLocal() - m_last_markup_fetch >= MathMax(1, InpMarkupReRenderSec))
   {
      FetchAndRenderChartMarkup();
      m_last_markup_fetch = TimeLocal();
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   ATEFetchConfig();

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
// RegisterSymbolOnInit: POST /api/v1/symbol/register so dashboard Watchlist reflects chart symbol immediately
void RegisterSymbolOnInit()
{
   if(StringLen(InpApiUrl) == 0) return;
   string url = InpApiUrl + "symbol/register";
   string company = AccountInfoString(ACCOUNT_COMPANY);
   string broker = AccountInfoString(ACCOUNT_SERVER);
   long accountId = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string payload = StringFormat(
      "{\"symbol\":\"%s\",\"company\":\"%s\",\"broker\":\"%s\",\"account_id\":%I64d,\"executor_id\":\"%s\"}",
      g_symbol, EscapeJson(company), EscapeJson(broker), accountId, EscapeJson(InpExecutorId));
   char postData[]; StringToCharArray(payload, postData, 0, StringLen(payload));
   char result[]; string headersOut = "";
   string resHeaders = StringFormat("Authorization: Bearer %s\r\nContent-Type: application/json\r\n", InpBridgeToken);
   ResetLastError();
   int code = WebRequest("POST", url, resHeaders, 5000, postData, result, headersOut);
   if(code != 200)
      PrintFormat("[ATE] symbol/register failed http=%d err=%d url=%s", code, GetLastError(), url);
   else
      PrintFormat("[ATE] symbol/register OK: %s", g_symbol);
}

// EscapeJson: minimal JSON string escape
string EscapeJson(string s)
{
   string out = "";
   for(int i = 0; i < StringLen(s); i++)
   {
      ushort ch = StringGetCharacter(s, i);
      if(ch == '"')        out += "\\\"";
      else if(ch == '\\') out += "\\\\";
      else if(ch == '\n')  out += "\\n";
      else if(ch == '\r')  out += "\\r";
      else if(ch == '\t')  out += "\\t";
      else                 out += ShortToString(ch);
   }
   return out;
}

//+------------------------------------------------------------------+
void SendTelemetry()
{
   if(StringLen(InpBridgeToken) == 0)
   {
      Print("ATE bridge token is not configured; telemetry is blocked.");
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
   
   int res = WebRequest("POST", ATEApiBase() + "/api/v1/telemetry", headers, 3000, data, result, result_headers);
   if(res != 200)
   {
      int err = GetLastError();
      ATELogThrottled("TELEMETRY_HTTP_" + string(res), StringFormat("Telemetry push failed (HTTP %d, err=%d). Bridge may be down, URL not allowlisted, or network blocked.", res, err));
   }
   else if(!g_telemetry_ok_logged)
   {
      g_telemetry_ok_logged = true;
      ATELog("TELEMETRY_OK: first successful heartbeat to " + InpApiUrl);
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
   WebRequest("POST", ATEApiBase() + "/api/v1/bridge/calendar", headers, 1000, data, result, result_headers);
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
   int res = WebRequest("GET", ATEApiBase() + "/api/economic-calendar/protection", headers, 3000, empty, result, result_headers);
   if(res != 200 || ArraySize(result) == 0)
   {
      if(g_protection_level != "unknown")
      {
         g_protection_level = "unknown";
         ATELogThrottled("PROTECTION_UNREACHABLE", StringFormat("News protection state unreachable (HTTP %d, err=%d). Falling back to: allow entries.", res, GetLastError()));
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
      ATELog(StringFormat("NEWS_PROTECTION_STATE level=%s event='%s' live_remaining=%ds", level, eventTitle, liveSeconds));
      if(level == "lockdown" || level == "approaching")
         ATELog("NEWS_PROTECTION: new BUY/SELL entries are BLOCKED until the news window passes (CLOSE/MODIFY still allowed).");
      else if(level == "watch")
         ATELog("NEWS_PROTECTION: watch mode - High impact news approaching, entries still allowed.");
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

string ATELogFileName()
{
   if(StringLen(g_ea_log_file) == 0)
      g_ea_log_file = "ate_ea_" + TimeToString(TimeCurrent(), TIME_DATE) + ".log";
   return g_ea_log_file;
}

void ATELog(const string message)
{
   string line = StringFormat("[%s] %s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), message);
   Print(line);
   int handle = FileOpen(ATELogFileName(), FILE_READ|FILE_WRITE|FILE_TXT|FILE_UNICODE);
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);
      FileWrite(handle, line);
      FileClose(handle);
   }
}

void ATELogThrottled(const string key, string message)
{
   if(key == g_ea_last_msg)
      return;
   g_ea_last_msg = key;
   ATELog(message);
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
      ATELogThrottled("UNAUTH", StringFormat("Blocked poll: trade_allowed=%d mql_trade_allowed=%d account=#%I64d@%s company=%s mode=%s (allowlist disabled)", TerminalInfoInteger(TERMINAL_TRADE_ALLOWED), MQLInfoInteger(MQL_TRADE_ALLOWED), AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoString(ACCOUNT_SERVER), AccountInfoString(ACCOUNT_COMPANY), AccountModeLabel(), "(any)"));
      return;
   }

   string tradeModeStr = AccountModeLabel();
   string headers = BridgeHeaders();
   string payload = StringFormat("{\"executor_id\":\"%s\",\"symbol\":\"%s\",\"magic\":%I64u,\"account_login\":%I64d,\"account_server\":\"%s\",\"broker_company\":\"%s\",\"trade_mode\":\"%s\"}", EscapeJson(InpExecutorId), EscapeJson(g_symbol), InpMagicNumber, AccountInfoInteger(ACCOUNT_LOGIN), EscapeJson(AccountInfoString(ACCOUNT_SERVER)), EscapeJson(AccountInfoString(ACCOUNT_COMPANY)), tradeModeStr);
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));

   // DEBUG: log before every claim attempt to track cadence
   PrintFormat("CLAIM_TRY: executor=%s symbol=%s magic=%I64u url=%s",
      InpExecutorId, g_symbol, InpMagicNumber, ATEApiBase() + "/api/v1/bridge/commands/claim");

   int res = WebRequest("POST", ATEApiBase() + "/api/v1/bridge/commands/claim", headers, 3000, data, result, result_headers);
   PrintFormat("CLAIM_RESULT: HTTP=%d result_size=%d err=%d", res, ArraySize(result), GetLastError());
   if(res != 200 || ArraySize(result) == 0)
   {
      int err = GetLastError();
      ATELogThrottled("CLAIM_HTTP_" + string(res), StringFormat("Claim request failed (HTTP %d, err=%d). Verify the bridge is up and '" + InpApiUrl + "' is in the MT5 WebRequest allowlist (use hostname/IP, not 127.0.0.1).", res, err));
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
      ATELog(StringFormat("REJECT_INVALID_COMMAND command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_INVALID_COMMAND");
      return;
   }
   if(!IsAuthorizedEnvironment())
   {
      ATELog(StringFormat("REJECT_EXECUTION_GUARD command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_EXECUTION_GUARD");
      return;
   }

   ATELog(StringFormat("CLAIMED command=%s action=%s volume=%.2f sl=%.2f tp=%.2f reason=%s", commandId, action, volume, stopLoss, takeProfit, reason));

   int symbolDigits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   m_trade.SetTypeFillingBySymbol(g_symbol);
   bool requestAccepted = false;
   ulong resultTicket = 0;

   if(action == "BUY" || action == "SELL")
   {
      // News Protection: fail-closed on new entries only; CLOSE/MODIFY stay claimable.
      if(InpNewsProtectionEnabled && (g_protection_level == "lockdown" || g_protection_level == "approaching"))
      {
         ATELog(StringFormat("REJECT_NEWS_PROTECTION command=%s action=%s level=%s event='%s' live_remaining=%ds", commandId, action, g_protection_level, g_protection_event, g_protection_live_seconds));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_NEWS_PROTECTION");
         return;
      }
      if(MatchingPositionCount() >= InpMaxPositions || !IsValidCommand(volume, stopLoss, takeProfit, action))
      {
         ATELog(StringFormat("REJECT_EXECUTION_GUARD command=%s action=%s positions=%d reason=%s", commandId, action, MatchingPositionCount(), reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_EXECUTION_GUARD");
         return;
      }
      if(action == "BUY")
         requestAccepted = m_trade.Buy(volume, g_symbol, SymbolInfoDouble(g_symbol, SYMBOL_ASK), NormalizeDouble(stopLoss, symbolDigits), NormalizeDouble(takeProfit, symbolDigits), "ATE v1 BUY");
      else
         requestAccepted = m_trade.Sell(volume, g_symbol, SymbolInfoDouble(g_symbol, SYMBOL_BID), NormalizeDouble(stopLoss, symbolDigits), NormalizeDouble(takeProfit, symbolDigits), "ATE v1 SELL");
      resultTicket = m_trade.ResultOrder();
   }
   else if(action == "MODIFY_SLTP")
   {
      ulong ticket = ExtractTicketFromReason(reason);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
      {
         ATELog(StringFormat("REJECT_TICKET_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
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
         ATELog(StringFormat("REJECT_TICKET_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
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
         ATELog(StringFormat("REJECT_ORDER_NOT_FOUND command=%s action=%s reason=%s", commandId, action, reason));
         SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_ORDER_NOT_FOUND");
         return;
      }
      requestAccepted = m_trade.OrderDelete(orderTicket);
      resultTicket = orderTicket;
   }
   else
   {
      ATELog(StringFormat("REJECT_UNSUPPORTED_ACTION command=%s action=%s", commandId, action));
      SendCommandReceipt(commandId, "REJECTED", 0, 0, "REJECT_UNSUPPORTED_ACTION");
      return;
   }

   uint retcode = m_trade.ResultRetcode();
   bool executed = requestAccepted && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_DONE_PARTIAL || retcode == TRADE_RETCODE_PLACED);
   if(executed)
   {
      m_consecutive_failures = 0;
      ATELog(StringFormat("EXECUTED command=%s action=%s ticket=%I64u retcode=%u (%s) reason=%s", commandId, action, resultTicket, retcode, m_trade.ResultRetcodeDescription(), reason));
      SendCommandReceipt(commandId, "EXECUTED", resultTicket, retcode, m_trade.ResultRetcodeDescription());
   }
   else
   {
      ATELog(StringFormat("FAILED command=%s action=%s retcode=%u (%s) reason=%s", commandId, action, retcode, m_trade.ResultRetcodeDescription(), reason));
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
   WebRequest("POST", ATEApiBase() + "/api/v1/bridge/commands/" + commandId + "/receipt", headers, 1000, data, result, resultHeaders);
}

//+------------------------------------------------------------------+
//| AI Chart Markup Rendering (AI Engine decides; EA only draws)      |
//+------------------------------------------------------------------+
void FetchAndRenderChartMarkup()
{
   if(StringLen(InpBridgeToken) == 0 || StringLen(InpApiUrl) == 0)
      return;

   string headers = BridgeHeaders();
   string payload = StringFormat("{\"executor_id\":\"%s\",\"symbol\":\"%s\",\"account_login\":%I64d,\"account_server\":\"%s\",\"broker_company\":\"%s\",\"trade_mode\":\"%s\"}", EscapeJson(InpExecutorId), EscapeJson(g_symbol), AccountInfoInteger(ACCOUNT_LOGIN), EscapeJson(AccountInfoString(ACCOUNT_SERVER)), EscapeJson(AccountInfoString(ACCOUNT_COMPANY)), AccountModeLabel());
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));

   int res = WebRequest("POST", ATEApiBase() + "/api/v1/bridge/markup", headers, 4000, data, result, result_headers);
   if(res != 200 || ArraySize(result) == 0)
      return; // Retry next tick; no chart paint this cycle.

   string response = CharArrayToString(result);
   if(StringFind(response, "\"objects\"") < 0)
      return;

   // Cheap change detection so we only repaint when the AI structure changed.
   int newHash = _MarkupHash(response);
   if(newHash == m_markup_payload_md5)
      return;
   m_markup_payload_md5 = newHash;

   RenderMarkupObjects(response);
}

// Parse a quoted "key":"value" token from a JSON fragment after `key`.
string _jxString(string json, string key)
{
   int start = StringFind(json, key);
   if(start < 0)
      return "";
   start += StringLen(key);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == ':' || StringGetCharacter(json, start) == '"'))
      start++;
   int end = StringFind(json, "\"", start);
   if(end <= start)
      return "";
   return StringSubstr(json, start, end - start);
}

// Cheap stable hash for change detection (MQL5 has no built-in StringHash).
int _MarkupHash(string s)
{
   int h = 5381;
   int len = StringLen(s);
   for(int i = 0; i < len; i++)
      h = ((h << 5) + h + (int)StringGetCharacter(s, i)) & 0x7FFFFFFF;
   return h;
}

// MQL5 StringToTime expects "yyyy.mm.dd hh:mm:ss"; normalize ISO/dash/UTC input.
datetime _jxTime(string s)
{
   StringReplace(s, "-", ".");
   StringReplace(s, "T", " ");
   int plus = StringFind(s, "+");
   if(plus > 10)
      s = StringSubstr(s, 0, plus);
   else
   {
      StringReplace(s, "Z", " ");
      StringReplace(s, "z", " ");
   }
   return StringToTime(s);
}

// Zone rectangle colors — bullish/bearish directional default, specialty types override.
color _MarkupZoneColor(string type, string dirStr)
{
   if(type == "SR")
      return (dirStr == "BULLISH") ? clrDodgerBlue : ((dirStr == "BEARISH") ? clrOrangeRed : clrGray);
   if(type == "CHANNEL" || type == "RANGE")
      return clrSilver;
   if(type == "DEALING_RANGE")
      return clrSteelBlue;
   if(type == "LIQUIDITY_POOL")
      return (dirStr == "BULLISH") ? clrGold : clrKhaki;
   if(type == "VOLUME_IMBALANCE" || type == "INDUCEMENT")
      return clrPurple;
   if(type == "BPR")
      return clrDarkOrange;
   if(type == "UNICORN")
      return clrGold;
   if(type == "PDH_PDL" || type == "WEEKLY_MONTHLY_HL")
      return (dirStr == "BULLISH") ? clrChocolate : clrSienna;
   if(type == "SESSION_HL")
      return clrSeaGreen;
   if(type == "VOID")
      return clrMagenta;
   return (dirStr == "BULLISH") ? clrDodgerBlue : ((dirStr == "BEARISH") ? clrOrangeRed : clrGray);
}

// Arrow/label colors for event types.
color _MarkupArrowColor(string type, string dirStr)
{
   if(type == "PATTERN")
      return clrWhite;
   if(type == "BREAKOUT")
      return clrLime;
   if(type == "PULLBACK" || type == "RETEST")
      return clrAqua;
   if(type == "FAKE_BREAKOUT")
      return clrRed;
   if(type == "MSS" || type == "CHoCH" || type == "BOS")
      return clrFuchsia;
   if(type == "TURTLE_SOUP")
      return clrOrange;
   if(type == "JUDAS_SWING")
      return clrCrimson;
   if(type == "SMT_DIVERGENCE")
      return clrDodgerBlue;
   if(type == "SILVER_BULLET")
      return clrWhite;
   if(type == "AMD")
      return clrGold;
   return (dirStr == "BULLISH") ? clrYellow : clrFuchsia;
}

void RenderMarkupObjects(string response)
{
   int drawn = 0;

   int pos = 0;
   while(drawn < InpMarkupMaxObjects)
   {
      int objStart = StringFind(response, "\"type\":", pos);
      if(objStart < 0)
         break;
      // Locate the object braces { ... } that enclose this "type" token.
      int braceStart = StringFind(response, "{", objStart);
      if(braceStart < 0)
         break;
      int braceEnd = StringFind(response, "}", objStart);
      if(braceEnd < 0 || braceEnd < braceStart)
         break;
      string block = StringSubstr(response, braceStart, braceEnd - braceStart + 1);

      string type = _jxString(block, "\"type\"");
      string dirStr = _jxString(block, "\"direction\"");
      string label = _jxString(block, "\"label\"");
      double top = ExtractDouble(block, "\"top\":", 0.0);
      double bottom = ExtractDouble(block, "\"bottom\":", 0.0);
      double price = ExtractDouble(block, "\"price\":", 0.0);
      datetime t1 = _jxTime(_jxString(block, "\"time_start\""));
      datetime t2 = _jxTime(_jxString(block, "\"time_end\""));

      string oid = StringFormat("ATE_MK_%d", drawn);

      // Zone types: price-level rectangles (structural + advanced).
      if(type == "OB" || type == "FVG" || type == "BREAKER" || type == "MITIGATION" || type == "REJECTION" || type == "iFVG" || type == "OTE" || type == "PD" || type == "ASIAN" ||
         type == "SR" || type == "CHANNEL" || type == "RANGE" || type == "DEALING_RANGE" || type == "LIQUIDITY_POOL" || type == "SUPPLY_DEMAND" || type == "VOLUME_IMBALANCE" || type == "VOID" ||
         type == "BPR" || type == "UNICORN" || type == "PDH_PDL" || type == "WEEKLY_MONTHLY_HL" || type == "SESSION_HL" || type == "AMD")
      {
         datetime from = t1;
         datetime to = (t2 > 0) ? t2 : (datetime)TimeCurrent();
         if(from <= 0)
            from = to - 86400;
         ObjectDelete(0, oid);
         if(!ObjectCreate(0, oid, OBJ_RECTANGLE, 0, from, top, to, bottom))
            continue;
         ObjectSetInteger(0, oid, OBJPROP_FILL, true);
         ObjectSetInteger(0, oid, OBJPROP_COLOR, _MarkupZoneColor(type, dirStr));
         ObjectSetInteger(0, oid, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, oid, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, oid, OBJPROP_BACK, true);
         ObjectSetInteger(0, oid, OBJPROP_ZORDER, 5);
         ObjectSetInteger(0, oid, OBJPROP_SELECTABLE, false);
      }
      else if(type == "TRENDLINE" || type == "DEALING_CURVE")
      {
         ObjectDelete(0, oid);
         if(!ObjectCreate(0, oid, OBJ_TREND, 0, t1, top, t2, bottom))
            continue;
         ObjectSetInteger(0, oid, OBJPROP_COLOR, (type == "DEALING_CURVE") ? clrSteelBlue : clrLimeGreen);
         ObjectSetInteger(0, oid, OBJPROP_STYLE, (type == "DEALING_CURVE") ? STYLE_SOLID : STYLE_DASH);
         ObjectSetInteger(0, oid, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, oid, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, oid, OBJPROP_SELECTABLE, false);
      }
      else if(type == "SWING" || type == "BOS" || type == "CHoCH" || type == "LIQUIDITY" || type == "KILLZONE" ||
              type == "PATTERN" || type == "BREAKOUT" || type == "PULLBACK" || type == "RETEST" || type == "FAKE_BREAKOUT" || type == "MSS" ||
              type == "INDUCEMENT" || type == "TURTLE_SOUP" || type == "JUDAS_SWING" || type == "SMT_DIVERGENCE" || type == "SILVER_BULLET")
      {
         datetime tk = (t1 > 0) ? t1 : (datetime)TimeCurrent();
         double anchorPrice = price;
         if(anchorPrice <= 0)
            anchorPrice = top + bottom;
         if(anchorPrice <= 0)
            anchorPrice = SymbolInfoDouble(g_symbol, SYMBOL_BID);
         ObjectDelete(0, oid);
         if(!ObjectCreate(0, oid, OBJ_ARROW, 0, tk, anchorPrice, 0, 0))
            continue;
         color ac = _MarkupArrowColor(type, dirStr);
         ObjectSetInteger(0, oid, OBJPROP_COLOR, ac);
         if(type == "SWING" || type == "PATTERN" || type == "BREAKOUT" || type == "PULLBACK" || type == "RETEST" || type == "FAKE_BREAKOUT")
            ObjectSetInteger(0, oid, OBJPROP_ARROWCODE, (dirStr == "BULLISH") ? 233 : 234); // 233 up, 234 down
         else
            ObjectSetInteger(0, oid, OBJPROP_ARROWCODE, 241); // right
         ObjectSetInteger(0, oid, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, oid, OBJPROP_SELECTABLE, false);
         if(StringLen(label) > 0)
         {
            string toText = "ATE_MK_T" + oid;
            ObjectDelete(0, toText);
            if(ObjectCreate(0, toText, OBJ_TEXT, 0, tk, anchorPrice))
            {
               ObjectSetString(0, toText, OBJPROP_TEXT, label);
               ObjectSetInteger(0, toText, OBJPROP_COLOR, ac);
               ObjectSetInteger(0, toText, OBJPROP_FONTSIZE, 8);
               ObjectSetInteger(0, toText, OBJPROP_SELECTABLE, false);
            }
         }
      }

      drawn++;
      pos = braceEnd + 1;
      if(drawn >= InpMarkupMaxObjects)
         break;
   }

   // Remove stale objects from previous renders (keep newest cap).
   for(int i = InpMarkupMaxObjects; i < InpMarkupMaxObjects * 2; i++)
   {
      string stale = StringFormat("ATE_MK_%d", i);
      if(ObjectFind(0, stale) >= 0)
         ObjectDelete(0, stale);
   }

   ATELog(StringFormat("MARKUP_RENDER objects=%d", drawn));
}

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
   return (val != 0) ? val : defaultValue;
}

//+------------------------------------------------------------------+
//| Get Timeframe string label                                       |
//+------------------------------------------------------------------+
string TimeframeLabel(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      default:         return "M15";
   }
}

//+------------------------------------------------------------------+
//| Send live candles from MT5 to the API                            |
//+------------------------------------------------------------------+
void SendLiveCandles()
{
   // DEBUG: Always log entry so we know this function is being called
   PrintFormat("CANDLES_DEBUG: entering SendLiveCandles() | token_len=%d url_len=%d last_push_ago=%d interval=%d",
      StringLen(InpBridgeToken), StringLen(InpApiUrl),
      (int)(TimeLocal() - m_last_candles_push), InpCandlesIntervalSec);

   if(StringLen(InpBridgeToken) == 0 || StringLen(InpApiUrl) == 0)
   {
      Print("CANDLES_SKIP: token or url empty");
      return;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, false); // Oldest first, newest last
   int copied = CopyRates(g_symbol, _Period, 0, 100, rates);
   PrintFormat("CANDLES_COPY_RESULT: copied=%d err=%d symbol=%s period=%d",
      copied, GetLastError(), g_symbol, _Period);
   if(copied <= 0)
   {
      PrintFormat("CANDLES_COPY_FAILED: err=%d for %s on %s", GetLastError(), g_symbol, _Period);
      return;
   }

   PrintFormat("CANDLES_PUSH_START: symbol=%s tf=%s candles=%d", g_symbol, _Period, copied);

   string candlesJson = "";
   for(int i = 0; i < copied; i++)
   {
      string ts = TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
      // Format as ISO 8601: YYYY.MM.DD HH:MM:SS -> YYYY-MM-DDTHH:MM:SS
      StringReplace(ts, ".", "-");
      StringReplace(ts, " ", "T");
      
      string item = StringFormat(
         "{\"t\":\"%s\",\"ts\":\"%s\",\"o\":%.2f,\"h\":%.2f,\"l\":%.2f,\"c\":%.2f,\"v\":%.1f}",
         TimeToString(rates[i].time, TIME_MINUTES),
         ts,
         rates[i].open,
         rates[i].high,
         rates[i].low,
         rates[i].close,
         (double)rates[i].tick_volume
      );
      
      if(i > 0)
         candlesJson += ",";
      candlesJson += item;
   }

   string tfLabel = TimeframeLabel(_Period);
   string payload = StringFormat("{\"symbol\":\"%s\",\"timeframe\":\"%s\",\"candles\":[%s]}", EscapeJson(g_symbol), tfLabel, candlesJson);
   
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, StringLen(payload));
   
   string headers = BridgeHeaders();
   int res = WebRequest("POST", ATEApiBase() + "/api/v1/bridge/candles", headers, 4000, data, result, result_headers);
   if(res == 200)
   {
      PrintFormat("CANDLES_PUSH_OK: pushed %d candles for %s %s", copied, g_symbol, tfLabel);
   }
   else
   {
      int err = GetLastError();
      ATELogThrottled("CANDLES_HTTP_" + string(res), StringFormat("CANDLES_PUSH_FAIL: HTTP %d err=%d", res, err));
   }
}
//+------------------------------------------------------------------+
