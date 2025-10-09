from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Ensure we're using a sync database URL
db_url = settings.sync_database_url if hasattr(settings, 'sync_database_url') else settings.DATABASE_URL

# Create synchronous engine with explicit settings
engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
    connect_args={"connect_timeout": 10} if "sqlite" not in db_url else {}
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

