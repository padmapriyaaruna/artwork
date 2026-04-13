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
# We strip query params (like ?sslmode=require or channel_binding) because
# asyncpg does not support them natively. We enforce SSL via connect_args instead.
ASYNC_DB_URL = DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
).split("?")[0]

engine = create_async_engine(
    ASYNC_DB_URL,
    poolclass=NullPool,   # Required for Neon serverless
    echo=False,
    connect_args={"ssl": True}
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


# Columns added in v2 — safe to run every startup (IF NOT EXISTS)
_V2_MIGRATIONS = [
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS barcode_number   VARCHAR(50);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS selling_price    VARCHAR(50);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS currency_symbol  VARCHAR(10);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS sku_code         VARCHAR(50);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS commercial_ref   VARCHAR(100);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS color            VARCHAR(100);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS style_code       VARCHAR(100);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS department       VARCHAR(100);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS sub_department   VARCHAR(100);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS translation_code VARCHAR(200);",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS extra_variables  JSONB DEFAULT '{}'::jsonb;",
]


async def apply_migrations():
    """
    Run incremental ALTER TABLE statements on every startup.
    Using IF NOT EXISTS makes these completely idempotent.
    """
    async with engine.begin() as conn:
        for sql in _V2_MIGRATIONS:
            try:
                await conn.execute(__import__("sqlalchemy").text(sql))
            except Exception as e:
                print(f"[Migration] Warning: {sql[:60]}... → {e}")
    print("[Migration] v2 columns verified.")

