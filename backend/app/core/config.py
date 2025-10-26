import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WeeVoice - Voice Agent SaaS"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./voiceagent.db")
    
    # Supabase (optional - for PostgreSQL)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "voice-agent-documents")
    
    # Google Gemini API
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-09-2025"
    
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
    
    # Email (SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@weevoice.com")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "WeeVoice")
    
    # Frontend URL (for email links)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # Zadarma Integration
    ZADARMA_API_KEY: str = os.getenv("ZADARMA_API_KEY", "")
    ZADARMA_API_SECRET: str = os.getenv("ZADARMA_API_SECRET", "")
    
    # Zadarma SIP Settings (optional, for direct SIP connection)
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
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env to prevent validation errors


settings = Settings()
