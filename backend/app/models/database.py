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
    # Extract SSL mode from URL if present, or default to 'require' for cloud databases
    connect_args = {
        "connect_timeout": 10,  # psycopg2 supports connect_timeout
        "application_name": "voiceagent_saas"
    }
    
    # For Neon and other cloud databases, ensure SSL is properly configured
    # If DATABASE_URL contains sslmode, it will be in the URL itself
    # Otherwise, we'll let psycopg2 handle it based on the connection string
    # Neon requires SSL, so we ensure it's enabled
    if "neon" in db_url.lower() or "sslmode" not in db_url.lower():
        # For Neon, SSL is required - it's usually in the connection string
        # But we can add sslmode=require as a fallback if not present
        pass  # Let the connection string handle SSL
    
    engine = create_engine(
        db_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=300,  # Recycle connections after 5 minutes
        pool_size=10,  # Maintain a pool of connections
        max_overflow=20,  # Allow overflow connections
        echo=False,
        connect_args=connect_args
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
    """Get database session with proper error handling and connection recovery.
    
    The connection pool is configured with pool_pre_ping=True which automatically
    tests connections before using them, helping to recover from SSL connection issues.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Rollback on any exception
        try:
            db.rollback()
        except Exception:
            # Connection might already be closed, ignore rollback errors
            pass
        raise
    finally:
        try:
            db.close()
        except Exception:
            # Ignore errors when closing - connection might already be closed
            # This can happen with SSL connections that were unexpectedly closed
            pass

