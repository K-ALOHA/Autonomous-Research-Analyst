from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services.router import router as api_router
from backend.utils.config import get_settings
from backend.utils.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )

    allow_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    logger = logging.getLogger(__name__)
    logger.info(
        "app_initialized",
        extra={"environment": settings.environment, "log_json": settings.log_json},
    )

    return app


app = create_app()

