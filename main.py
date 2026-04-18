"""
ASGI entry for hosts that expect ``uvicorn main:app`` (e.g. Render).

Run from the repository root with PYTHONPATH including this directory (default when
cwd is the project root):

    uvicorn main:app --host 0.0.0.0 --port 10000
"""

from pathlib import Path
import sys

_BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.main import app

__all__ = ["app"]
