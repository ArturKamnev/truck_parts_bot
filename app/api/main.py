from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health, customer, manager, owner, ai
from app.config import get_settings
from app.utils.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Mini App API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

# CORS configurations
allow_origins = []
if settings.miniapp_origin:
    allow_origins.append(settings.miniapp_origin.rstrip("/"))

if settings.app_env != "production" and settings.miniapp_url:
    from urllib.parse import urlparse
    parsed = urlparse(settings.miniapp_url)
    if parsed.scheme and parsed.netloc:
        url_origin = f"{parsed.scheme}://{parsed.netloc}"
        if url_origin not in allow_origins:
            allow_origins.append(url_origin)

if settings.app_env != "production":
    # In development, also allow standard local development origins
    dev_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    for o in dev_origins:
        if o not in allow_origins:
            allow_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(customer.router, prefix="/api")
app.include_router(manager.router, prefix="/api")
app.include_router(owner.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
