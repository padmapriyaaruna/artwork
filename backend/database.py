"""
SQLAlchemy async database setup for Neon PostgreSQL.
Neon is serverless — connections auto-pause, so we use
NullPool to avoid keeping idle connections alive.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import DATABASE_URL

# asyncpg driver — convert postgresql:// → postgresql+asyncpg://
ASYNC_DB_URL = DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    ASYNC_DB_URL,
    poolclass=NullPool,   # Required for Neon serverless
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """Create all tables on startup (safe to call repeatedly)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
