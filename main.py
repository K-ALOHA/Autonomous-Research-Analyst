"""
ASGI entry for hosts that expect ``uvicorn main:app`` (e.g. Render).

Run from the repository root with PYTHONPATH including this directory (default when
cwd is the project root):

    uvicorn main:app --host 0.0.0.0 --port 10000
"""

from backend.main import app

__all__ = ["app"]
