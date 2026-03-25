"""
Database configuration and initialization
PostgreSQL with SQLAlchemy ORM
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
import os

from app.config import settings

# Database engine
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Test connections before using
    echo=settings.DEBUG
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all models
Base = declarative_base()

def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database - create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("[DB] ✓ All tables created/verified")
    except Exception as e:
        print(f"[DB] ✗ Initialization error: {e}")
        raise

def drop_db():
    """Drop all tables - for testing/reset only"""
    Base.metadata.drop_all(bind=engine)
    print("[DB] ✓ All tables dropped")
