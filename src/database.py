"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
import asyncpg
from loguru import logger

from src.config import settings
from src.models import Base


# Sync SQLAlchemy engine for traditional ORM operations
engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session dependency for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Get database session as context manager."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_async_connection():
    """Get async database connection for high-performance operations."""
    # Parse database URL for asyncpg
    # postgresql://user:password@host:port/database
    db_url = settings.database_url.replace("postgresql://", "").replace("postgres://", "")

    try:
        conn = await asyncpg.connect(f"postgresql://{db_url}")
        return conn
    except Exception as e:
        logger.error(f"Failed to create async database connection: {e}")
        raise


async def close_async_connection(conn):
    """Close async database connection."""
    if conn:
        await conn.close()
