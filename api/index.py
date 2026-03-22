"""Vercel serverless function entry point.

Vercel's Python runtime looks for an `app` object in api/index.py.
We simply re-export the FastAPI app from our main server module.
"""

from app.server import app  # noqa: F401
