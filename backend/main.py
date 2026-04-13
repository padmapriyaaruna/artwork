"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import APP_NAME, APP_VERSION, ALLOWED_ORIGINS, _ALLOW_ALL_ORIGINS
from backend.database import create_tables, apply_migrations, AsyncSessionLocal
from backend.engine.template_registry import seed_default_templates
from backend.api import orders, artwork, approvals


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup: create tables, apply migrations, seed templates."""
    print("[Startup] Creating tables...")
    await create_tables()

    print("[Startup] Applying DB migrations...")
    await apply_migrations()

    print("[Startup] Seeding default templates...")
    async with AsyncSessionLocal() as db:
        await seed_default_templates(db)

    print(f"[Startup] {APP_NAME} v{APP_VERSION} ready.")
    yield
    print("[Shutdown] Goodbye.")


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
    allow_origins     = ["*"] if _ALLOW_ALL_ORIGINS else ALLOWED_ORIGINS,
    allow_credentials = not _ALLOW_ALL_ORIGINS,   # credentials not allowed with wildcard
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    expose_headers    = ["Content-Disposition"],   # needed for PDF/PNG downloads
)


# ── Global exception handler — returns JSON, never plain text ─────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"[ERROR] Unhandled exception on {request.method} {request.url}:\n{tb}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url),
        },
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
