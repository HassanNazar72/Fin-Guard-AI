"""Vercel Python Serverless Function entrypoint.

``vercel.json`` rewrites every ``/api/*`` request here; FastAPI then routes on
the original path (``/api/chat``, ``/api/analyze``, ...).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import app  # noqa: E402

__all__ = ["app"]
