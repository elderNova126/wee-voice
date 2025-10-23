from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Ensure we're using a sync database URL
if hasattr(settings, 'sync_database_url'):
    db_url = settings.sync_database_url
else:
    # Convert async URL to sync URL
    db_url = settings.DATABASE_URL
    if db_url.startswith('postgresql+asyncpg://'):
        # Use psycopg2 for synchronous connections
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
    elif db_url.startswith('postgresql://'):
        # Ensure we use psycopg2 for sync connections
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://')
    elif db_url.startswith('sqlite://'):
        pass  # SQLite is always sync

# Create synchronous engine with explicit settings
if "postgresql" in db_url:
    # PostgreSQL-specific settings
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,
        connect_args={
            "connect_timeout": 10,  # psycopg2 supports connect_timeout
            "application_name": "voiceagent_saas"
        }
    )
else:
    # SQLite settings
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

