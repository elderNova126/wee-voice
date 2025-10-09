#!/usr/bin/env python3
"""
Quick API test script to diagnose connectivity issues
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, data=None, description=""):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Method: {method}")
    print(f"URL: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.ok:
            print("✅ SUCCESS")
        else:
            print("❌ FAILED")
        
        return response
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to backend")
        print("   Is the backend running on http://localhost:8000?")
        return None
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timeout")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


def main():
    print("🔍 VoiceAgent API Diagnostics")
    print("="*60)
    
    # Test 1: Root endpoint
    test_endpoint("GET", "/", description="Root endpoint")
    
    # Test 2: Health check
    test_endpoint("GET", "/health", description="Health check")
    
    # Test 3: API docs
    test_endpoint("GET", "/api/docs", description="API documentation")
    
    # Test 4: Registration endpoint (POST)
    test_data = {
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User"
    }
    test_endpoint("POST", "/api/v1/auth/register", data=test_data, 
                  description="Registration endpoint")
    
    # Test 5: Demo agent
    test_endpoint("GET", "/api/v1/agents/public/demo", 
                  description="Demo agent endpoint")
    
    print("\n" + "="*60)
    print("Diagnostics complete!")
    print("\nIf you see connection errors, make sure:")
    print("1. Backend is running: python -m uvicorn app.main:app --reload")
    print("2. Running on port 8000")
    print("3. No firewall blocking localhost:8000")


if __name__ == "__main__":
    main()


