"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import APP_NAME, APP_VERSION, ALLOWED_ORIGINS
from backend.database import create_tables, AsyncSessionLocal
from backend.engine.template_registry import seed_default_templates
from backend.api import orders, artwork, approvals


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup: create DB tables and seed default templates."""
    print(f"[Startup] Creating tables...")
    await create_tables()

    print(f"[Startup] Seeding default templates...")
    async with AsyncSessionLocal() as db:
        await seed_default_templates(db)

    print(f"[Startup] {APP_NAME} v{APP_VERSION} ready.")
    yield
    print(f"[Shutdown] Goodbye.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = APP_NAME,
    version     = APP_VERSION,
    description = "Automated artwork generation engine for Sainmarks/Britannia. "
                  "Replaces XMPie, ESCO, and NICE Label.",
    lifespan    = lifespan,
)

# CORS — allow frontend (Render Static Site or localhost dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(orders.router,    prefix="/api")
app.include_router(artwork.router,   prefix="/api")
app.include_router(approvals.router, prefix="/api")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


@app.get("/", tags=["System"])
async def root():
    return JSONResponse({
        "message": f"Welcome to {APP_NAME}",
        "docs":    "/docs",
        "health":  "/health",
    })
