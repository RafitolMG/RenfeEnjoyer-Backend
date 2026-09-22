import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = Path(os.getenv("RENFE_DB_PATH", BASE_DIR / "renfe_enjoyer.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Vite dev server; in production the SPA is served from the same origin.
CORS_ORIGINS = os.getenv("RENFE_CORS_ORIGINS", "http://localhost:5173").split(",")

HEADLESS = os.getenv("RENFE_HEADLESS", "").lower() in {"1", "true", "yes"}

# Renfe's pages are slow and the results table is polled, so waits are generous.
SELENIUM_TIMEOUT = int(os.getenv("RENFE_SELENIUM_TIMEOUT", "100"))
