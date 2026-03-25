"""
Configuration management
Pydantic settings for environment variables
"""
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings - reads from environment variables"""
    
    # App
    APP_NAME: str = "Zwesta Trading System"
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost/zwesta_db"
    )
    
    # JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # Trading
    BOT_SCAN_INTERVAL_SECONDS: int = int(os.getenv("BOT_SCAN_INTERVAL", "5"))
    POSITION_SIZE_PERCENT: float = float(os.getenv("POSITION_SIZE_PERCENT", "2"))
    STOP_LOSS_POINTS: float = float(os.getenv("STOP_LOSS_POINTS", "50"))
    TAKE_PROFIT_PERCENT: float = float(os.getenv("TAKE_PROFIT_PERCENT", "1.5"))
    CONSECUTIVE_LOSS_LIMIT: int = int(os.getenv("CONSECUTIVE_LOSS_LIMIT", "3"))
    DAILY_LOSS_LIMIT: float = float(os.getenv("DAILY_LOSS_LIMIT", "500"))
    
    # MT5
    MT5_ACCOUNT: str = os.getenv("MT5_ACCOUNT", "103672035")
    MT5_PASSWORD: str = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER: str = os.getenv("MT5_SERVER", "MetaQuotes-Demo")
    
    # Binance
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    
    # WhatsApp (Twilio)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+1234567890")
    
    # Binance Additional
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "True") == "True"
    BINANCE_REQUEST_TIMEOUT: int = 30
    
    # MT5 Additional
    MT5_TIMEOUT: int = 30
    
    # PDF Reports
    PDF_REPORT_DIR: str = os.getenv("PDF_REPORT_DIR", "./reports")
    PDF_GENERATED_FILES_KEEP_DAYS: int = 30
    
    # Trading Bot
    BOT_ENABLED: bool = os.getenv("BOT_ENABLED", "True") == "True"
    BOT_TRADING_SYMBOLS: List[str] = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"
    ]
    
    # Risk Management
    MAX_POSITION_SIZE: float = float(os.getenv("POSITION_SIZE_PERCENT", "2"))
    MAX_DAILY_LOSS_PERCENT: float = 5.0
    MIN_RR_RATIO: float = float(os.getenv("TAKE_PROFIT_PERCENT", "1.5"))
    
    # Application Server
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    TIMEZONE: str = os.getenv("TIMEZONE", "UTC")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
