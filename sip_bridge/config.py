"""
SIP Bridge Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# SIP Server Configuration
SIP_HOST = os.getenv("SIP_HOST", "0.0.0.0")
SIP_PORT = int(os.getenv("SIP_PORT", "5060"))
SIP_USERNAME = os.getenv("SIP_USERNAME", "agent")
SIP_PASSWORD = os.getenv("SIP_PASSWORD", "")
SIP_DOMAIN = os.getenv("SIP_DOMAIN", "sip.example.com")

# RTP Configuration
RTP_PORT_MIN = int(os.getenv("RTP_PORT_MIN", "10000"))
RTP_PORT_MAX = int(os.getenv("RTP_PORT_MAX", "20000"))

# Railway Backend WebSocket URL
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "wss://your-app.railway.app/api/v1/ws/voice")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

# Audio Configuration
INPUT_SAMPLE_RATE = 16000  # Sample rate for audio sent to backend
OUTPUT_SAMPLE_RATE = 24000  # Sample rate for audio from backend

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Security - Zadarma IPs to whitelist
ZADARMA_ALLOWED_IPS = os.getenv("ZADARMA_ALLOWED_IPS", "")