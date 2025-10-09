#!/usr/bin/env python3
"""
Run uvicorn with explicit logging and stdout flush
"""
import sys
import uvicorn

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Starting VoiceAgent Backend Server")
    print("="*60 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
    )

