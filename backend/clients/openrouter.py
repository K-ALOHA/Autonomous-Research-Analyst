from __future__ import annotations

import os
from typing import Optional

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_client(*, api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    Build an OpenAI-compatible client for OpenRouter.

    Lazily imports ``openai`` so importing the backend package does not load the SDK.
    """
    from openai import OpenAI

    url = (base_url or os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL).rstrip("/")
    key = (api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("openrouter_api_key_missing: set OPENROUTER_API_KEY")

    return OpenAI(
        api_key=key,
        base_url=url,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "autonomous-research-analyst"),
        },
    )
