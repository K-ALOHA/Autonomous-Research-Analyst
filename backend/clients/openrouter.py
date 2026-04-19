from __future__ import annotations

from typing import Optional

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_client(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    site_url: Optional[str] = None,
    app_name: Optional[str] = None,
):
    """
    OpenAI-compatible client for OpenRouter (not api.openai.com).

    - ``base_url`` defaults to ``https://openrouter.ai/api/v1``
    - ``api_key`` must be your OpenRouter key (``OPENROUTER_API_KEY``), typically ``sk-or-v1-...``
    - Sends OpenRouter-required attribution headers on every request

    Lazily imports ``openai`` so importing the backend package does not load the SDK.
    """
    from openai import OpenAI

    from utils.config import get_settings

    settings = get_settings()

    url = (base_url or settings.openrouter_base_url or DEFAULT_OPENROUTER_BASE_URL).strip().rstrip("/")
    key = (api_key if api_key is not None else settings.openrouter_api_key) or ""
    key = key.strip()
    if not key:
        raise RuntimeError("openrouter_api_key_missing: set OPENROUTER_API_KEY")

    referer = (site_url if site_url is not None else settings.openrouter_site_url).strip() or "http://localhost"
    title = (app_name if app_name is not None else settings.openrouter_app_name).strip() or "autonomous-research-analyst"

    # OpenRouter docs: HTTP-Referer + title for rankings; newer samples also use X-OpenRouter-Title.
    default_headers = {
        "HTTP-Referer": referer,
        "X-Title": title,
        "X-OpenRouter-Title": title,
    }

    return OpenAI(
        api_key=key,
        base_url=url,
        default_headers=default_headers,
    )
