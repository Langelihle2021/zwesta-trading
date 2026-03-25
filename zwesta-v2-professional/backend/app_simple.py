"""
Zwesta Trading System v2 - FastAPI Backend
Simplified entry point for testing
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Zwesta Trading API v2",
    description="Professional trading platform API",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Zwesta Trading System v2 API",
        "docs": "/docs"
    }

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "service": "Zwesta Trading API",
        "version": "2.0.0"
    }

@app.post("/api/auth/login")
async def login(credentials: dict):
    """Demo login - accepts any credentials"""
    username = credentials.get("username")
    password = credentials.get("password")
    
    if username and password:
        return {
            "access_token": f"demo_token_{username}",
            "token_type": "bearer",
            "user": {
                "username": username,
                "email": f"{username}@trading.com",
                "id": 1
            }
        }
    return {"detail": "Invalid credentials"}

@app.get("/api/trading/trades")
async def get_trades():
    """Get trading history"""
    return [
        {
            "id": 1,
            "symbol": "GBPUSD",
            "trade_type": "BUY",
            "volume": 1.0,
            "entry_price": 1.2650,
            "current_price": 1.2680,
            "pnl": 30.0,
            "return_percentage": 0.24,
            "opened_at": "2024-03-01T10:00:00",
            "closed_at": "2024-03-01T12:00:00",
            "status": "closed"
        }
    ]

@app.get("/api/trading/positions")
async def get_positions():
    """Get open positions"""
    return [
        {
            "id": 1,
            "symbol": "EURUSD",
            "trade_type": "BUY",
            "volume": 0.5,
            "entry_price": 1.0950,
            "current_price": 1.0980,
            "stop_loss": 1.0920,
            "take_profit": 1.1050,
            "current_pnl": 15.0,
            "return_percentage": 0.27,
            "opened_at": "2024-03-02T09:30:00",
            "status": "open"
        }
    ]

@app.get("/api/trading/statistics")
async def get_statistics():
    """Get trading statistics"""
    return {
        "total_trades": 25,
        "winning_trades": 18,
        "losing_trades": 7,
        "win_rate": 72.0,
        "total_pnl": 1250.50,
        "avg_win": 95.32,
        "avg_loss": -42.14,
        "profit_factor": 2.41
    }

@app.get("/api/account/summary")
async def get_account():
    """Get account summary"""
    return {
        "balance": 10000.0,
        "equity": 10150.0,
        "margin": 500.0,
        "margin_level": 2030.0,
        "total_pnl": 150.0,
        "today_pnl": 45.0,
        "currency": "USD"
    }

@app.get("/api/account/list")
async def get_accounts_list():
    """Get all trading accounts"""
    return [
        {
            "id": 1,
            "account_number": "136372035",
            "broker": "XM",
            "account_type": "Demo",
            "balance": 10000.0,
            "equity": 10150.0,
            "currency": "USD",
            "status": "active",
            "created_at": "2024-01-15T10:30:00"
        }
    ]

@app.get("/api/accounts/")
async def get_accounts():
    """Get all trading accounts (plural endpoint)"""
    return [
        {
            "id": 1,
            "account_number": "136372035",
            "broker": "XM",
            "account_type": "Demo",
            "balance": 10000.0,
            "equity": 10150.0,
            "currency": "USD",
            "status": "active",
            "created_at": "2024-01-15T10:30:00"
        }
    ]

@app.get("/api/account/history")
async def get_account_history():
    """Get account balance history"""
    return [
        {"date": "2024-02-26", "balance": 9850.0},
        {"date": "2024-02-27", "balance": 9920.0},
        {"date": "2024-02-28", "balance": 10050.0},
        {"date": "2024-03-01", "balance": 10100.0},
        {"date": "2024-03-02", "balance": 10150.0}
    ]

@app.get("/api/reports/generate")
async def generate_report(report_type: str = "monthly"):
    """Generate trading report"""
    return {
        "report_type": report_type,
        "generated_at": "2024-03-02T14:00:00",
        "file_url": "/reports/trading_report_march_2024.pdf",
        "summary": {
            "total_trades": 25,
            "winning_trades": 18,
            "losing_trades": 7,
            "gross_profit": 1712.68,
            "gross_loss": -462.18,
            "net_profit": 1250.50
        }
    }

@app.get("/api/auth/me")
async def get_current_user():
    """Get current user info"""
    return {
        "id": 1,
        "username": "demo",
        "email": "demo@trading.com",
        "full_name": "Demo User"
    }

@app.get("/api/trading/symbols")
async def get_trading_symbols():
    """Get available trading symbols"""
    return [
        {"symbol": "EURUSD", "name": "Euro / US Dollar", "spread": 1.2},
        {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "spread": 1.5},
        {"symbol": "USDJPY", "name": "US Dollar / Japanese Yen", "spread": 1.0},
        {"symbol": "AUDUSD", "name": "Australian Dollar / US Dollar", "spread": 1.8},
        {"symbol": "USDCAD", "name": "US Dollar / Canadian Dollar", "spread": 1.3},
        {"symbol": "NZDUSD", "name": "New Zealand Dollar / US Dollar", "spread": 2.0},
        {"symbol": "GOLD", "name": "Gold (XAU/USD)", "spread": 0.5},
        {"symbol": "SPX500", "name": "S&P 500 Index", "spread": 1.0}
    ]

@app.get("/api/alerts/list")
async def get_alerts():
    """Get trading alerts"""
    return [
        {
            "id": 1,
            "type": "price_alert",
            "symbol": "EURUSD",
            "message": "EURUSD reached target price 1.1000",
            "severity": "info",
            "timestamp": "2024-03-02T13:30:00",
            "read": False
        },
        {
            "id": 2,
            "type": "position_alert",
            "symbol": "GBPUSD",
            "message": "GBPUSD position now in profit",
            "severity": "success",
            "timestamp": "2024-03-02T12:15:00",
            "read": False
        }
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
