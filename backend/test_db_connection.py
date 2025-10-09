#!/usr/bin/env python3
"""
Test database connection to Supabase
Run this to verify your DATABASE_URL is correct
"""

import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def test_connection():
    """Test database connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in .env file")
        print("\nPlease add to backend/.env:")
        print("DATABASE_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres")
        return False
    
    print("📊 Testing Database Connection...")
    print(f"URL: {database_url[:50]}...")
    
    try:
        # Create engine
        engine = create_engine(database_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"\n✅ Connection successful!")
            print(f"PostgreSQL version: {version[:50]}...")
            
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result]
            
            if tables:
                print(f"\n✅ Found {len(tables)} tables:")
                for table in tables:
                    print(f"   - {table}")
            else:
                print("\n⚠️  No tables found!")
                print("Run the SQL schema in Supabase SQL Editor:")
                print("   database/supabase_schema_simple.sql")
            
            # Check for demo user
            if 'users' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                count = result.fetchone()[0]
                print(f"\n✅ Users table has {count} records")
                
                if count > 0:
                    result = conn.execute(text("SELECT email FROM users LIMIT 1"))
                    email = result.fetchone()[0]
                    print(f"   Demo user: {email}")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Connection failed!")
        print(f"Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your DATABASE_URL in backend/.env")
        print("2. Verify password is correct")
        print("3. Make sure you replaced [YOUR-PASSWORD]")
        print("4. Test connection: psql \"your-connection-string\"")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

