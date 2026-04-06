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
# In production set this to your Render static site URL
ALLOWED_ORIGINS: list[str] = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

# ── App Settings ──────────────────────────────────────────────
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
RENDER_DPI: int = int(os.getenv("RENDER_DPI", "600"))   # 300 for production
