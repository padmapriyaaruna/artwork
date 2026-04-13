"""
Application configuration — reads from environment variables.
All secrets (DB URL, etc.) should be in a .env file locally
and set as environment variables in Render.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent          # Art_Work/
TEMPLATES_DIR = BASE_DIR / "templates"                # Art_Work/templates/
ASSETS_DIR    = BASE_DIR / "assets"                   # Art_Work/assets/

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/artwork_db"  # local fallback
)

# ── App ────────────────────────────────────────────────────────────────────
APP_NAME    = "Artwork Automation Engine"
APP_VERSION = "1.0.0"
DEBUG       = os.getenv("DEBUG", "true").lower() == "true"

# ── CORS ───────────────────────────────────────────────────────────────────
# Build origin list — strips whitespace from each entry
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,"
    "http://localhost:3000,"
    "https://artwork-engine-frontend.onrender.com,"
    "https://artwork-engine.onrender.com"
)

ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# If wildcard is in the list, FastAPI needs allow_origins=["*"]
_ALLOW_ALL_ORIGINS: bool = "*" in ALLOWED_ORIGINS


# ── App Settings ──────────────────────────────────────────────
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
RENDER_DPI: int = int(os.getenv("RENDER_DPI", "600"))   # 300 for production
