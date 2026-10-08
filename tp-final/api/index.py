"""Vercel entry point: the whole FastAPI app runs as a single serverless function (see vercel.json)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))

from pulso.asgi import app  # noqa: E402,F401
