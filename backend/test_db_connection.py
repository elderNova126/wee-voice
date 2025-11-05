#!/usr/bin/env python3
"""
Test database connection to identify the issue
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.models.database import engine, SessionLocal
from sqlalchemy import text

def test_database_connection():
    """Test the database connection"""
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Database type: {'SQLite' if 'sqlite' in settings.DATABASE_URL else 'PostgreSQL'}")
    
    try:
        # Test engine creation
        print("Testing engine creation...")
        test_engine = engine
        print("✅ Engine created successfully")
        
        # Test connection
        print("Testing database connection...")
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            print(f"Test query result: {result.fetchone()}")
        
        # Test session
        print("Testing database session...")
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT 1"))
            print("✅ Database session successful")
            print(f"Session test result: {result.fetchone()}")
        finally:
            db.close()
            
        print("\n🎉 All database tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_database_connection()