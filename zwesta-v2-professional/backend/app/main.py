"""
Zwesta Trading System - FastAPI Backend
Production-grade trading platform with bot integration
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import routes
from app.api import auth, trading, accounts, alerts, reports, admin

# Config
from app.config import settings

# Database initialization flag
startup_complete = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown"""
    print("[STARTUP] Initializing Zwesta Trading System v2...")
    
    # Startup
    from app.database import init_db
    from app.bot.engine import TradingBotEngine
    
    init_db()
    print("[STARTUP] ✓ Database initialized")
    
    # Start trading bot in background
    bot = TradingBotEngine()
    await bot.start()
    print("[STARTUP] ✓ Trading bot started")
    
    print("[STARTUP] ✓ System ready!")
    
    yield
    
    # Shutdown
    await bot.stop()
    print("[SHUTDOWN] System offline")

# Initialize FastAPI app
app = FastAPI(
    title="Zwesta Trading API",
    description="Professional trading platform API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "Zwesta Trading API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.DEBUG,
        log_level="info"
    )
