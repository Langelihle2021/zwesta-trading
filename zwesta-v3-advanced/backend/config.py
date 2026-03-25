from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Zwesta Trading System v3"
    APP_ENV: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite:///./zwesta.db"
    
    # JWT
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "+14155238886"
    ADMIN_WHATSAPP_NUMBER: str = ""
    
    # Stripe
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8081"
    ]
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Bot
    BOT_ENABLED: bool = True
    BOT_CHECK_INTERVAL: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
