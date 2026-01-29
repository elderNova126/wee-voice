#!/usr/bin/env python3
"""
Quick diagnostic script to check if API keys are being loaded correctly.
Run this from the backend directory: python check_api_keys.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Get the backend directory
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

print("=" * 60)
print("API Keys Diagnostic Tool")
print("=" * 60)
print(f"\nLooking for .env file at: {ENV_FILE}")
print(f"File exists: {ENV_FILE.exists()}\n")

if ENV_FILE.exists():
    # Load .env file
    load_dotenv(ENV_FILE)
    print("✓ .env file loaded\n")
else:
    print("❌ .env file NOT FOUND!\n")
    print("Please create a .env file in the backend/ directory with:")
    print("  ANTHROPIC_API_KEY=your-key-here")
    print("  OPENAI_API_KEY=your-key-here")
    sys.exit(1)

# Check environment variables
print("Checking environment variables:")
print("-" * 60)

# Check Anthropic
anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
if anthropic_key:
    print(f"✓ ANTHROPIC_API_KEY: SET (length: {len(anthropic_key)}, starts with: {anthropic_key[:10]}...)")
else:
    print("❌ ANTHROPIC_API_KEY: NOT SET")

# Check OpenAI
openai_key = os.getenv("OPENAI_API_KEY", "")
if openai_key:
    print(f"✓ OPENAI_API_KEY: SET (length: {len(openai_key)}, starts with: {openai_key[:10]}...)")
else:
    print("❌ OPENAI_API_KEY: NOT SET")

print("\n" + "=" * 60)
print("Testing Settings import:")
print("-" * 60)

try:
    # Try to import settings
    sys.path.insert(0, str(BASE_DIR))
    from app.core.config import settings
    
    print(f"✓ Settings imported successfully")
    print(f"\nSettings values:")
    print(f"  - ANTHROPIC_API_KEY: {'SET' if settings.ANTHROPIC_API_KEY else 'NOT SET'}")
    if settings.ANTHROPIC_API_KEY:
        print(f"    Length: {len(settings.ANTHROPIC_API_KEY)}")
        print(f"    Starts with: {settings.ANTHROPIC_API_KEY[:10]}...")
    
    print(f"  - OPENAI_API_KEY: {'SET' if settings.OPENAI_API_KEY else 'NOT SET'}")
    if settings.OPENAI_API_KEY:
        print(f"    Length: {len(settings.OPENAI_API_KEY)}")
        print(f"    Starts with: {settings.OPENAI_API_KEY[:10]}...")
    
    print(f"  - ANTHROPIC_MODEL: {settings.ANTHROPIC_MODEL}")
    print(f"  - OPENAI_CHAT_MODEL: {settings.OPENAI_CHAT_MODEL}")
    
    # Test client initialization
    print("\n" + "=" * 60)
    print("Testing Client Initialization:")
    print("-" * 60)
    
    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            
            # Try simple initialization first
            try:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                print("✓ OpenAI client initialized successfully")
            except TypeError as e:
                # If proxies error, try with explicit http_client
                if 'proxies' in str(e):
                    print("⚠ Proxies parameter issue detected, trying alternative method...")
                    import httpx
                    http_client = httpx.AsyncClient(timeout=30.0)
                    client = AsyncOpenAI(
                        api_key=settings.OPENAI_API_KEY,
                        http_client=http_client
                    )
                    print("✓ OpenAI client initialized successfully (with custom http_client)")
                else:
                    raise
        except Exception as e:
            print(f"❌ OpenAI client initialization FAILED: {e}")
            import traceback
            print(traceback.format_exc())
    else:
        print("⚠ Skipping OpenAI test (no API key)")
    
    if settings.ANTHROPIC_API_KEY:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            print("✓ Anthropic client initialized successfully")
        except Exception as e:
            print(f"❌ Anthropic client initialization FAILED: {e}")
            import traceback
            print(traceback.format_exc())
    else:
        print("⚠ Skipping Anthropic test (no API key)")
    
except Exception as e:
    print(f"❌ Error importing settings: {e}")
    import traceback
    print(traceback.format_exc())

print("\n" + "=" * 60)
print("Diagnostic complete!")
print("=" * 60)

