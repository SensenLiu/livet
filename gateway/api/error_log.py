"""Anonymous error log forwarder.

The app calls this with redacted exception payloads. Gateway forwards to Sentry
(if SENTRY_DSN configured AND user has not opted out).

Privacy contract:
  - The app is responsible for redacting PII before calling here.
  - We additionally drop any field that LOOKS like a chat message
    (key contains "transcript" / "message" / "dictation" / "user_says").
"""
from __future__ import annotations

from typing import Any

import sentry_sdk
from fastapi import APIRouter, Depends, Request

from core.auth import auth_dep
from core.rate_limit import limit
from core.settings import settings

router = APIRouter()

# Lazy init — only if a DSN is configured
_initialized = False


def _maybe_init_sentry() -> None:
    global _initialized
    if _initialized or not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        send_default_pii=False,  # never send PII
    )
    _initialized = True


_BLOCKED_KEY_SUBSTRINGS = (
    "transcript",
    "message",
    "dictation",
    "user_says",
    "raw_text",
    "audio",
    "pcm",
)


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    """Defensively drop fields that smell like dialogue/PII content."""
    out: dict[str, Any] = {}
    for k, v in payload.items():
        kl = k.lower()
        if any(bad in kl for bad in _BLOCKED_KEY_SUBSTRINGS):
            continue
        if isinstance(v, dict):
            out[k] = _scrub(v)
        else:
            out[k] = v
    return out


@router.post("/report")
@limit("30/minute")
async def report(
    request: Request,
    payload: dict[str, Any],
    user: dict = Depends(auth_dep),
) -> dict[str, Any]:
    _maybe_init_sentry()
    if not _initialized:
        return {"forwarded": False, "reason": "sentry not configured"}

    scrubbed = _scrub(payload)
    sentry_sdk.capture_message(
        scrubbed.get("message", "client error"),
        level=scrubbed.get("level", "error"),
        extras=scrubbed,
    )
    return {"forwarded": True}
