"""LiveT BFF Gateway entry point.

A thin BFF (~200 lines target) covering:
  1. Upstream API key proxy (LLM / ASR / TTS)
  2. Subscription verification (WeChat Pay / Apple IAP)
  3. Anonymous error log forwarding (user-toggleable)

Privacy guarantees (see CLAUDE.md philosophy bullet #3):
  - No user dialogue / PII / medical content stored or logged
  - All upstream keys held server-side only
  - No raw audio persisted
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api import asr_proxy, error_log, llm_proxy, subscription, tts_proxy
from core.routing import HealthChecker
from core.settings import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url if settings.env != "dev" else "memory://",
)
health_checker = HealthChecker()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Boot/shutdown hooks for shared resources."""
    await health_checker.start()
    yield
    await health_checker.stop()


app = FastAPI(
    title="LiveT BFF Gateway",
    description="Thin BFF for LiveT app — keys / subscription / error-log proxy.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Routers
app.include_router(llm_proxy.router, prefix="/v1/llm", tags=["llm"])
app.include_router(asr_proxy.router, prefix="/v1/asr", tags=["asr"])
app.include_router(tts_proxy.router, prefix="/v1/tts", tags=["tts"])
app.include_router(subscription.router, prefix="/v1/sub", tags=["subscription"])
app.include_router(error_log.router, prefix="/v1/error", tags=["error_log"])


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness + upstream provider health snapshot."""
    return {
        "status": "ok",
        "version": app.version,
        "env": settings.env,
        "providers": health_checker.snapshot(),
    }


@app.get("/")
async def root() -> dict:
    return {"service": "livet-gateway", "version": app.version}
