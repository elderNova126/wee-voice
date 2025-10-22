from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "VoiceAgent SaaS"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./voiceagent.db"  # SQLite fallback for development
    )
    
    @property
    def sync_database_url(self) -> str:
        """Ensure database URL uses synchronous driver"""
        url = self.DATABASE_URL
        # Replace async drivers with sync ones
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "")
        if "+aiomysql" in url:
            url = url.replace("+aiomysql", "")
        return url
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Google Cloud
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    # OpenAI (for OCR and optional fallback)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_OCR_MODEL: str = "gpt-4o"  # gpt-4o has vision capabilities
    
    # Gemini Configuration
    GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-09-2025"
    DEFAULT_LANGUAGE: str = "fr-FR"  # French
    
    # Audio Configuration
    AUDIO_FORMAT: str = "audio/pcm"
    SEND_SAMPLE_RATE: int = 16000
    RECEIVE_SAMPLE_RATE: int = 24000
    CHUNK_SIZE: int = 2048
    
    # Stripe (for billing)
    STRIPE_API_KEY: Optional[str] = os.getenv("STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Usage Limits
    FREE_TIER_MINUTES: int = 30
    BASIC_TIER_MINUTES: int = 1000
    PRO_TIER_MINUTES: int = 10000
    
    # Storage
    CALL_RECORDINGS_PATH: str = "./data/recordings"
    TRANSCRIPTS_PATH: str = "./data/transcripts"
    
    # Supabase Storage
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "voice-agent-documents")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"  # Ignore extra fields from .env
    )


settings = Settings()

