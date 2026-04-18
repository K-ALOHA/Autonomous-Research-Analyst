from __future__ import annotations

import os

# Names only — never log values (secrets).
TRACKED_ENV_VAR_NAMES: tuple[str, ...] = (
    "APP_NAME",
    "ENV",
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "LOG_JSON",
    "CORS_ALLOW_ORIGINS",
    "DATABASE_URL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_SITE_URL",
    "OPENROUTER_APP_NAME",
    "PLANNER_MODEL",
    "ANALYST_MODEL",
    "OPENROUTER_MODEL",
    "TAVILY_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_BASE_URL",
)


def list_detected_config_env_names() -> list[str]:
    """Return sorted names of tracked env vars that are set to a non-empty string."""
    out: list[str] = []
    for name in TRACKED_ENV_VAR_NAMES:
        v = os.getenv(name)
        if v is not None and str(v).strip() != "":
            out.append(name)
    return sorted(out)
