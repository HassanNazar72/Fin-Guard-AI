"""Central configuration for FinGuard AI.

Every limit that protects the Gemini bill or the API surface lives here so it
can be audited in one place and overridden through environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader for local development (no extra dependency).

    Real environment variables always win, so Vercel / CI settings are never
    overridden by a stray local file.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv(ROOT_DIR / ".env")

SAMPLE_CSV_PATH = ROOT_DIR / "public" / "sample_uk_statement.csv"
CACHED_DEMOS_PATH = BACKEND_DIR / "cached_demos.json"

# --- LLM -------------------------------------------------------------------
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_OUTPUT_TOKENS = 400
TEMPERATURE = 0.1
MAX_TOOL_ROUNDS = 3

# --- Input guards ----------------------------------------------------------
MAX_ROWS = 200
MAX_PROMPT_CHARS = 250
MAX_CSV_CHARS = 100_000

# --- Zero-bill protection --------------------------------------------------
LIVE_QUERIES_PER_IP_PER_DAY = _env_int("LIVE_QUERIES_PER_IP_PER_DAY", 10)
GLOBAL_LIVE_QUERIES_PER_DAY = _env_int("GLOBAL_LIVE_QUERIES_PER_DAY", 500)
RATE_LIMIT_WINDOW_SECONDS = 24 * 60 * 60

# --- Security --------------------------------------------------------------
# Salt for the one-way PII tokens. Tokens let the agent see that two rows
# reference the *same* account without ever seeing the account itself.
PII_HASH_SALT = os.environ.get("PII_HASH_SALT", "finguard-ai-default-salt")

# --- Analytics -------------------------------------------------------------
DUPLICATE_WINDOW_HOURS = 48
OUTLIER_Z_THRESHOLD = 2.5
SUBSCRIPTION_MIN_GAP_DAYS = 25
SUBSCRIPTION_MAX_GAP_DAYS = 35
SUBSCRIPTION_CREEP_MIN_PCT = 2.0
# Fixed housing costs (rent / mortgage) are excluded from outlier statistics:
# a rent payment is large but it is not anomalous.
OUTLIER_EXCLUDED_CATEGORIES = frozenset({"Housing"})

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
