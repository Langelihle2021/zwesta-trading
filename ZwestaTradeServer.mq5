//+------------------------------------------------------------------+
//| ZwestaTradeServer.mq5                                            |
//| Zwesta Trader - Self-Hosted MT5 Socket Trade Server              |
//| Listens on TCP for JSON trade commands from Python backend       |
//+------------------------------------------------------------------+
#property copyright "Zwesta Trader"
#property link      "https://zwesta.com"
#property version   "1.00"
#property description "TCP socket trade server for Zwesta backend"

#include <Trade\Trade.mqh>

// ==================== INPUT PARAMETERS ====================
input int      ServerPort     = 8001;     // TCP port to listen on (8001, 8002, etc.)
input int      MaxClients     = 5;        // Max simultaneous connections
input int      HeartbeatSec   = 10;       // Heartbeat interval in seconds
input string   AuthToken      = "zwesta"; // Simple auth token for security

// ==================== GLOBALS ====================
int            server_socket = INVALID_HANDLE;
int            client_sockets[];
CTrade         trade;
datetime       last_heartbeat = 0;
bool           server_running = false;
string         recv_buffer;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
    // Allow live trading
    if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
    {
        Print("ERROR: Algo trading not allowed. Enable in Tools > Options > Expert Advisors");
        return INIT_FAILED;
    }
    
    // Create server socket
    server_socket = SocketCreate();
    if(server_socket == INVALID_HANDLE)
    {
        Print("ERROR: Failed to create socket: ", GetLastError());
        return INIT_FAILED;
    }
    
    // Bind and listen
    if(!SocketBind(server_socket, "127.0.0.1", ServerPort))
    {
        Print("ERROR: Failed to bind to port ", ServerPort, ": ", GetLastError());
        SocketClose(server_socket);
        return INIT_FAILED;
    }
    
    if(!SocketListen(server_socket, MaxClients))
    {
        Print("ERROR: Failed to listen on port ", ServerPort, ": ", GetLastError());
        SocketClose(server_socket);
        return INIT_FAILED;
    }
    
    server_running = true;
    trade.SetExpertMagicNumber(20260326); // Zwesta magic number
    
    Print("=== Zwesta Trade Server STARTED on port ", ServerPort, " ===");
    Print("Account: ", AccountInfoInteger(ACCOUNT_LOGIN));
    Print("Server: ", AccountInfoString(ACCOUNT_SERVER));
    Print("Balance: $", DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
    
    // Set timer for heartbeat and client checking
    EventSetMillisecondTimer(100); // 100ms polling
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    server_running = false;
    
    // Close all client connections
    for(int i = ArraySize(client_sockets) - 1; i >= 0; i--)
    {
        if(client_sockets[i] != INVALID_HANDLE)
            SocketClose(client_sockets[i]);
    }
    ArrayResize(client_sockets, 0);
    
    // Close server socket
    if(server_socket != INVALID_HANDLE)
    {
        SocketClose(server_socket);
        server_socket = INVALID_HANDLE;
    }
    
    Print("=== Zwesta Trade Server STOPPED ===");
}

//+------------------------------------------------------------------+
//| Timer function - polls for connections and data                   |
//+------------------------------------------------------------------+
void OnTimer()
{
    if(!server_running) return;
    
    // Accept new connections
    AcceptNewClients();
    
    // Process data from connected clients
    ProcessClients();
    
    // Heartbeat logging
    if(TimeCurrent() - last_heartbeat >= HeartbeatSec)
    {
        last_heartbeat = TimeCurrent();
        // Silent heartbeat - only log if debug needed
    }
}

//+------------------------------------------------------------------+
//| Accept incoming client connections                                |
//+------------------------------------------------------------------+
void AcceptNewClients()
{
    int new_client = SocketAccept(server_socket, 0); // Non-blocking (0ms timeout)
    if(new_client != INVALID_HANDLE)
    {
        int size = ArraySize(client_sockets);
        ArrayResize(client_sockets, size + 1);
        client_sockets[size] = new_client;
        Print("Client connected (socket ", new_client, "), total: ", size + 1);
    }
}

//+------------------------------------------------------------------+
//| Process data from all connected clients                          |
//+------------------------------------------------------------------+
void ProcessClients()
{
    for(int i = ArraySize(client_sockets) - 1; i >= 0; i--)
    {
        if(client_sockets[i] == INVALID_HANDLE) continue;
        
        // Check if socket is still connected
        if(!SocketIsConnected(client_sockets[i]))
        {
            Print("Client disconnected (socket ", client_sockets[i], ")");
            SocketClose(client_sockets[i]);
            RemoveClient(i);
            continue;
        }
        
        // Try to read data (non-blocking)
        uchar data[];
        int bytes = SocketRead(client_sockets[i], data, 8192, 0);
        
        if(bytes > 0)
        {
            string received = CharArrayToString(data, 0, bytes, CP_UTF8);
            recv_buffer += received;
            
            // Process complete JSON messages (newline-delimited)
            int nl_pos;
            while((nl_pos = StringFind(recv_buffer, "\n")) >= 0)
            {
                string message = StringSubstr(recv_buffer, 0, nl_pos);
                recv_buffer = StringSubstr(recv_buffer, nl_pos + 1);
                
                if(StringLen(message) > 0)
                {
                    string response = ProcessCommand(message);
                    SendResponse(client_sockets[i], response);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Remove disconnected client from array                            |
//+------------------------------------------------------------------+
void RemoveClient(int index)
{
    int size = ArraySize(client_sockets);
    for(int i = index; i < size - 1; i++)
        client_sockets[i] = client_sockets[i + 1];
    ArrayResize(client_sockets, size - 1);
}

//+------------------------------------------------------------------+
//| Send response back to client                                     |
//+------------------------------------------------------------------+
void SendResponse(int socket, string response)
{
    if(socket == INVALID_HANDLE) return;
    response += "\n"; // Newline delimiter
    uchar data[];
    StringToCharArray(response, data, 0, StringLen(response), CP_UTF8);
    SocketSend(socket, data, ArraySize(data));
}

//+------------------------------------------------------------------+
//| Parse and execute a JSON command                                  |
//+------------------------------------------------------------------+
string ProcessCommand(string json)
{
    // Simple JSON parser for our known commands
    string cmd = JsonGetString(json, "cmd");
    string token = JsonGetString(json, "token");
    
    // Auth check
    if(token != AuthToken)
        return "{\"success\":false,\"error\":\"invalid_token\"}";
    
    if(cmd == "ping")
        return HandlePing();
    else if(cmd == "account_info")
        return HandleAccountInfo();
    else if(cmd == "symbol_price")
        return HandleSymbolPrice(json);
    else if(cmd == "place_order")
        return HandlePlaceOrder(json);
    else if(cmd == "close_position")
        return HandleClosePosition(json);
    else if(cmd == "modify_position")
        return HandleModifyPosition(json);
    else if(cmd == "get_positions")
        return HandleGetPositions();
    else if(cmd == "symbol_info")
        return HandleSymbolInfo(json);
    else if(cmd == "candles")
        return HandleCandles(json);
    else
        return "{\"success\":false,\"error\":\"unknown_command\",\"cmd\":\"" + cmd + "\"}";
}

//+------------------------------------------------------------------+
//| Handle: ping                                                      |
//+------------------------------------------------------------------+
string HandlePing()
{
    return "{\"success\":true,\"cmd\":\"pong\",\"account\":" + 
           IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + 
           ",\"server\":\"" + AccountInfoString(ACCOUNT_SERVER) + "\"}";
}

//+------------------------------------------------------------------+
//| Handle: account_info                                              |
//+------------------------------------------------------------------+
string HandleAccountInfo()
{
    string result = "{\"success\":true";
    result += ",\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2);
    result += ",\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2);
    result += ",\"margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2);
    result += ",\"freeMargin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2);
    result += ",\"leverage\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE));
    result += ",\"currency\":\"" + AccountInfoString(ACCOUNT_CURRENCY) + "\"";
    result += ",\"login\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
    result += ",\"server\":\"" + AccountInfoString(ACCOUNT_SERVER) + "\"";
    result += ",\"name\":\"" + AccountInfoString(ACCOUNT_NAME) + "\"";
    result += "}";
    return result;
}

//+------------------------------------------------------------------+
//| Handle: symbol_price                                              |
//+------------------------------------------------------------------+
string HandleSymbolPrice(string json)
{
    string symbol = JsonGetString(json, "symbol");
    if(symbol == "") return "{\"success\":false,\"error\":\"symbol required\"}";
    
    MqlTick tick;
    if(!SymbolInfoTick(symbol, tick))
    {
        // Try to add symbol to Market Watch
        SymbolSelect(symbol, true);
        Sleep(100);
        if(!SymbolInfoTick(symbol, tick))
            return "{\"success\":false,\"error\":\"symbol_not_found\",\"symbol\":\"" + symbol + "\"}";
    }
    
    string result = "{\"success\":true";
    result += ",\"symbol\":\"" + symbol + "\"";
    result += ",\"bid\":" + DoubleToString(tick.bid, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
    result += ",\"ask\":" + DoubleToString(tick.ask, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
    result += ",\"spread\":" + DoubleToString(tick.ask - tick.bid, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
    result += ",\"time\":" + IntegerToString(tick.time);
    result += "}";
    return result;
}

//+------------------------------------------------------------------+
//| Handle: place_order                                               |
//+------------------------------------------------------------------+
string HandlePlaceOrder(string json)
{
    string symbol   = JsonGetString(json, "symbol");
    string action   = JsonGetString(json, "action");  // BUY or SELL
    double volume   = JsonGetDouble(json, "volume");
    double sl       = JsonGetDouble(json, "stop_loss");
    double tp       = JsonGetDouble(json, "take_profit");
    string comment  = JsonGetString(json, "comment");
    
    if(symbol == "" || volume <= 0)
        return "{\"success\":false,\"error\":\"symbol and volume required\"}";
    
    // Ensure symbol is in Market Watch
    SymbolSelect(symbol, true);
    
    // Get current price
    MqlTick tick;
    if(!SymbolInfoTick(symbol, tick))
        return "{\"success\":false,\"error\":\"cannot_get_price\",\"symbol\":\"" + symbol + "\"}";
    
    ENUM_ORDER_TYPE order_type;
    double price;
    
    if(action == "BUY")
    {
        order_type = ORDER_TYPE_BUY;
        price = tick.ask;
    }
    else if(action == "SELL")
    {
        order_type = ORDER_TYPE_SELL;
        price = tick.bid;
    }
    else
        return "{\"success\":false,\"error\":\"action must be BUY or SELL\"}";
    
    // Set SL/TP if provided
    if(sl > 0) trade.SetDeviationInPoints(50);
    
    // Place market order
    bool result;
    if(sl > 0 && tp > 0)
        result = trade.PositionOpen(symbol, order_type, volume, price, sl, tp, comment);
    else if(sl > 0)
        result = trade.PositionOpen(symbol, order_type, volume, price, sl, 0, comment);
    else if(tp > 0)
        result = trade.PositionOpen(symbol, order_type, volume, price, 0, tp, comment);
    else
        result = trade.PositionOpen(symbol, order_type, volume, price, 0, 0, comment);
    
    uint retcode = trade.ResultRetcode();
    ulong ticket = trade.ResultOrder();
    ulong deal = trade.ResultDeal();
    
    string resp = "{\"success\":" + (result ? "true" : "false");
    resp += ",\"retcode\":" + IntegerToString(retcode);
    resp += ",\"ticket\":" + IntegerToString(ticket);
    resp += ",\"deal\":" + IntegerToString(deal);
    resp += ",\"price\":" + DoubleToString(trade.ResultPrice(), (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));
    resp += ",\"volume\":" + DoubleToString(trade.ResultVolume(), 2);
    if(!result)
        resp += ",\"error\":\"" + trade.ResultComment() + "\"";
    resp += "}";
    
    Print("ORDER ", action, " ", DoubleToString(volume, 2), " ", symbol, 
          " -> ", (result ? "OK" : "FAIL"), " retcode=", retcode, " ticket=", ticket);
    
    return resp;
}

//+------------------------------------------------------------------+
//| Handle: close_position                                            |
//+------------------------------------------------------------------+
string HandleClosePosition(string json)
{
    long ticket = (long)JsonGetDouble(json, "ticket");
    
    if(ticket <= 0)
        return "{\"success\":false,\"error\":\"ticket required\"}";
    
    // Select position
    if(!PositionSelectByTicket(ticket))
        return "{\"success\":false,\"error\":\"position_not_found\",\"ticket\":" + IntegerToString(ticket) + "}";
    
    bool result = trade.PositionClose(ticket);
    uint retcode = trade.ResultRetcode();
    
    string resp = "{\"success\":" + (result ? "true" : "false");
    resp += ",\"retcode\":" + IntegerToString(retcode);
    resp += ",\"ticket\":" + IntegerToString(ticket);
    if(!result)
        resp += ",\"error\":\"" + trade.ResultComment() + "\"";
    resp += "}";
    
    Print("CLOSE ticket=", ticket, " -> ", (result ? "OK" : "FAIL"), " retcode=", retcode);
    
    return resp;
}

//+------------------------------------------------------------------+
//| Handle: modify_position (change SL/TP)                           |
//+------------------------------------------------------------------+
string HandleModifyPosition(string json)
{
    long ticket = (long)JsonGetDouble(json, "ticket");
    double sl = JsonGetDouble(json, "stop_loss");
    double tp = JsonGetDouble(json, "take_profit");
    
    if(ticket <= 0)
        return "{\"success\":false,\"error\":\"ticket required\"}";
    
    if(!PositionSelectByTicket(ticket))
        return "{\"success\":false,\"error\":\"position_not_found\"}";
    
    // Keep existing values if not provided
    if(sl == 0) sl = PositionGetDouble(POSITION_SL);
    if(tp == 0) tp = PositionGetDouble(POSITION_TP);
    
    bool result = trade.PositionModify(ticket, sl, tp);
    uint retcode = trade.ResultRetcode();
    
    string resp = "{\"success\":" + (result ? "true" : "false");
    resp += ",\"retcode\":" + IntegerToString(retcode);
    if(!result)
        resp += ",\"error\":\"" + trade.ResultComment() + "\"";
    resp += "}";
    
    return resp;
}

//+------------------------------------------------------------------+
//| Handle: get_positions                                             |
//+------------------------------------------------------------------+
string HandleGetPositions()
{
    int total = PositionsTotal();
    string result = "{\"success\":true,\"count\":" + IntegerToString(total) + ",\"positions\":[";
    
    for(int i = 0; i < total; i++)
    {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        
        if(i > 0) result += ",";
        
        string symbol = PositionGetString(POSITION_SYMBOL);
        double vol = PositionGetDouble(POSITION_VOLUME);
        double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
        double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
        double pnl = PositionGetDouble(POSITION_PROFIT);
        double sl = PositionGetDouble(POSITION_SL);
        double tp = PositionGetDouble(POSITION_TP);
        double swap = PositionGetDouble(POSITION_SWAP);
        double commission = 0; // Commission not directly available per position in MQL5
        long posType = PositionGetInteger(POSITION_TYPE);
        datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
        int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
        
        string typeStr = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
        
        result += "{\"ticket\":" + IntegerToString(ticket);
        result += ",\"symbol\":\"" + symbol + "\"";
        result += ",\"type\":\"" + typeStr + "\"";
        result += ",\"volume\":" + DoubleToString(vol, 2);
        result += ",\"openPrice\":" + DoubleToString(openPrice, digits);
        result += ",\"currentPrice\":" + DoubleToString(currentPrice, digits);
        result += ",\"pnl\":" + DoubleToString(pnl, 2);
        result += ",\"swap\":" + DoubleToString(swap, 2);
        result += ",\"sl\":" + DoubleToString(sl, digits);
        result += ",\"tp\":" + DoubleToString(tp, digits);
        result += ",\"openTime\":" + IntegerToString(openTime);
        result += "}";
    }
    
    result += "]}";
    return result;
}

//+------------------------------------------------------------------+
//| Handle: symbol_info                                               |
//+------------------------------------------------------------------+
string HandleSymbolInfo(string json)
{
    string symbol = JsonGetString(json, "symbol");
    if(symbol == "") return "{\"success\":false,\"error\":\"symbol required\"}";
    
    SymbolSelect(symbol, true);
    
    double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
    if(point == 0)
        return "{\"success\":false,\"error\":\"symbol_not_found\",\"symbol\":\"" + symbol + "\"}";
    
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    int spread = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
    int stops_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
    
    string result = "{\"success\":true";
    result += ",\"symbol\":\"" + symbol + "\"";
    result += ",\"point\":" + DoubleToString(point, digits + 1);
    result += ",\"digits\":" + IntegerToString(digits);
    result += ",\"minLot\":" + DoubleToString(min_lot, 2);
    result += ",\"maxLot\":" + DoubleToString(max_lot, 2);
    result += ",\"lotStep\":" + DoubleToString(lot_step, 2);
    result += ",\"spread\":" + IntegerToString(spread);
    result += ",\"stopsLevel\":" + IntegerToString(stops_level);
    result += "}";
    return result;
}

//+------------------------------------------------------------------+
//| Handle: candles (OHLCV history)                                   |
//+------------------------------------------------------------------+
string HandleCandles(string json)
{
    string symbol = JsonGetString(json, "symbol");
    string tf_str = JsonGetString(json, "timeframe");
    int count = (int)JsonGetDouble(json, "count");
    
    if(symbol == "") return "{\"success\":false,\"error\":\"symbol required\"}";
    if(count <= 0) count = 50;
    if(count > 500) count = 500;
    
    // Map timeframe string to ENUM
    ENUM_TIMEFRAMES tf = PERIOD_M5;
    if(tf_str == "1m" || tf_str == "M1") tf = PERIOD_M1;
    else if(tf_str == "5m" || tf_str == "M5") tf = PERIOD_M5;
    else if(tf_str == "15m" || tf_str == "M15") tf = PERIOD_M15;
    else if(tf_str == "30m" || tf_str == "M30") tf = PERIOD_M30;
    else if(tf_str == "1h" || tf_str == "H1") tf = PERIOD_H1;
    else if(tf_str == "4h" || tf_str == "H4") tf = PERIOD_H4;
    else if(tf_str == "1d" || tf_str == "D1") tf = PERIOD_D1;
    
    MqlRates rates[];
    int copied = CopyRates(symbol, tf, 0, count, rates);
    
    if(copied <= 0)
        return "{\"success\":false,\"error\":\"no_data\",\"symbol\":\"" + symbol + "\"}";
    
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    string result = "{\"success\":true,\"count\":" + IntegerToString(copied) + ",\"candles\":[";
    
    for(int i = 0; i < copied; i++)
    {
        if(i > 0) result += ",";
        result += "{\"time\":" + IntegerToString(rates[i].time);
        result += ",\"open\":" + DoubleToString(rates[i].open, digits);
        result += ",\"high\":" + DoubleToString(rates[i].high, digits);
        result += ",\"low\":" + DoubleToString(rates[i].low, digits);
        result += ",\"close\":" + DoubleToString(rates[i].close, digits);
        result += ",\"volume\":" + IntegerToString(rates[i].tick_volume);
        result += "}";
    }
    
    result += "]}";
    return result;
}

//+------------------------------------------------------------------+
//| Simple JSON string extractor                                      |
//+------------------------------------------------------------------+
string JsonGetString(string json, string key)
{
    string search = "\"" + key + "\":\"";
    int pos = StringFind(json, search);
    if(pos < 0) return "";
    
    int start = pos + StringLen(search);
    int end = StringFind(json, "\"", start);
    if(end < 0) return "";
    
    return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Simple JSON number extractor                                      |
//+------------------------------------------------------------------+
double JsonGetDouble(string json, string key)
{
    // Try quoted number first: "key":"value"
    string search = "\"" + key + "\":\"";
    int pos = StringFind(json, search);
    if(pos >= 0)
    {
        int start = pos + StringLen(search);
        int end = StringFind(json, "\"", start);
        if(end > start)
            return StringToDouble(StringSubstr(json, start, end - start));
    }
    
    // Try unquoted number: "key":value
    search = "\"" + key + "\":";
    pos = StringFind(json, search);
    if(pos < 0) return 0;
    
    int start = pos + StringLen(search);
    // Skip whitespace
    while(start < StringLen(json) && StringGetCharacter(json, start) == ' ')
        start++;
    
    // Find end of number (comma, }, or end of string)
    int end = start;
    while(end < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, end);
        if(ch == ',' || ch == '}' || ch == ' ' || ch == '\n')
            break;
        end++;
    }
    
    if(end > start)
        return StringToDouble(StringSubstr(json, start, end - start));
    
    return 0;
}

//+------------------------------------------------------------------+
//| Tick handler (not used - we use timer-based polling)              |
//+------------------------------------------------------------------+
void OnTick()
{
    // Not used - all processing done in OnTimer
}
//+------------------------------------------------------------------+
