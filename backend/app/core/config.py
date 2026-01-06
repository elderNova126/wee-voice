import os
from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings

# Get the absolute path to the backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Go up to backend/
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WeeVoice - Voice Agent SaaS"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")  # Base URL for API endpoints
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./voiceagent.db")
    
    # Storage (for file storage service)
    STORAGE_URL: str = os.getenv("STORAGE_URL", "")
    STORAGE_KEY: str = os.getenv("STORAGE_KEY", "")
    STORAGE_BUCKET: str = os.getenv("STORAGE_BUCKET", "voice-agent-documents")
    
    # Google Gemini API
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-09-2025"
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_SUMMARY_MODEL: str = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-3.5-turbo")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-3.5-turbo")
    
    # Anthropic (for text chat - primary)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Stripe (for payments) - Optional
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_API_KEY: str = os.getenv("STRIPE_API_KEY", "")  # Alias for STRIPE_SECRET_KEY
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Email (SMTP) - Using TLS on port 587
    SMTP_HOST: str = os.getenv("SMTP_HOST", "mail.weedoo.be")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "voice@weedoo.be")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "1") == "1"  # Use TLS for port 587
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "0") == "1"  # Use SSL for port 465
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "voice@weedoo.be")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "WeeVoice")
    
    # Frontend URL (for email links)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # Zadarma Integration
    ZADARMA_API_KEY: str = os.getenv("ZADARMA_API_KEY", "")
    ZADARMA_API_SECRET: str = os.getenv("ZADARMA_API_SECRET", "")
    
    # Zadarma PBX Settings (for PBX extension management)
    ZADARMA_PBX_SERVER: str = os.getenv("ZADARMA_PBX_SERVER", "pbx.zadarma.com")
    ZADARMA_PBX_LOGIN: str = os.getenv("ZADARMA_PBX_LOGIN", "")
    ZADARMA_PBX_PASSWORD: str = os.getenv("ZADARMA_PBX_PASSWORD", "")
    ZADARMA_PBX_ID: str = os.getenv("ZADARMA_PBX_ID", "")
    
    # SIP Settings
    # Note: SIP credentials are now loaded from phone_numbers table in database
    # Each phone number can have its own SIP configuration (set via Phone Numbers page)
    SIP_ENABLED: bool = os.getenv("SIP_ENABLED", "true").lower() == "true"  # Master switch for SIP functionality
    
    # Legacy Zadarma SIP Settings (for backward compatibility)
    ZADARMA_SIP_SERVER: str = os.getenv("ZADARMA_SIP_SERVER", "sip.zadarma.com")
    ZADARMA_SIP_LOGIN: str = os.getenv("ZADARMA_SIP_LOGIN", "")
    ZADARMA_SIP_PASSWORD: str = os.getenv("ZADARMA_SIP_PASSWORD", "")
    ZADARMA_PHONE_NUMBER: str = os.getenv("ZADARMA_PHONE_NUMBER", "")
    
    # Pricing Configuration
    COST_PER_MINUTE: float = float(os.getenv("COST_PER_MINUTE", "0.05"))  # $0.05 per minute default
    PHONE_NUMBER_MONTHLY_COST: float = float(os.getenv("PHONE_NUMBER_MONTHLY_COST", "4.99"))
    
    # Audio Configuration
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2048"))
    RECEIVE_SAMPLE_RATE: int = int(os.getenv("RECEIVE_SAMPLE_RATE", "24000"))
    SEND_SAMPLE_RATE: int = int(os.getenv("SEND_SAMPLE_RATE", "16000"))
    
    # Storage Paths
    CALL_RECORDINGS_PATH: str = os.getenv("CALL_RECORDINGS_PATH", "./data/recordings")
    TRANSCRIPTS_PATH: str = os.getenv("TRANSCRIPTS_PATH", "./data/transcripts")
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env to prevent validation errors


# Explicitly load .env file with absolute path before creating settings instance
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load .env file
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
    logger.info(f"✓ Loaded .env file from: {ENV_FILE}")
else:
    logger.warning(f"⚠ .env file not found at: {ENV_FILE}")

settings = Settings()

# Debug: Log if critical keys are loaded
if settings.ANTHROPIC_API_KEY:
    logger.info(f"✓ ANTHROPIC_API_KEY loaded: {settings.ANTHROPIC_API_KEY[:20]}...")
else:
    logger.warning("⚠ ANTHROPIC_API_KEY is NOT loaded")

if settings.OPENAI_API_KEY:
    logger.info(f"✓ OPENAI_API_KEY loaded: {settings.OPENAI_API_KEY[:20]}...")
else:
    logger.warning("⚠ OPENAI_API_KEY is NOT loaded")
