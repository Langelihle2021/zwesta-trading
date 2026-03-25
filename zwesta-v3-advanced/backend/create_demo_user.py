#!/bin/bash

# Demo user creation script
import sys
import hashlib
from database import SessionLocal, User
from security import hash_password

def create_demo_user():
    db = SessionLocal()
    
    # Check if demo user exists
    existing = db.query(User).filter(User.username == "demo").first()
    if existing:
        print("✅ Demo user already exists")
        return
    
    # Create demo user
    demo_user = User(
        username="demo",
        email="demo@trading.com",
        password_hash=hash_password("demo123"),
        full_name="Demo User",
        phone="+1234567890",
        whatsapp_number="+1234567890",
        is_active=True
    )
    
    db.add(demo_user)
    db.commit()
    print("✅ Demo user created successfully!")
    print("   Username: demo")
    print("   Password: demo123")
    print("   Email: demo@trading.com")

if __name__ == "__main__":
    create_demo_user()
