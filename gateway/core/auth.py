"""Device-bound short-lived token auth.

Goal: prevent random clients from burning our upstream API quota.
Not a privacy mechanism — we still don't store user data.

Flow:
  1. App on first launch generates a stable random device_id (UUIDv4) — never PII.
  2. App calls POST /v1/sub/token with device_id (+ optional subscription receipt).
  3. Gateway issues a 24h JWT signed with DEVICE_TOKEN_SECRET.
  4. App sends JWT in Authorization header for /v1/llm /v1/asr /v1/tts calls.
"""
from __future__ import annotations

import hmac
import json
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from typing import Optional

from fastapi import Header, HTTPException, status

from core.settings import settings

TOKEN_TTL_SECONDS = 24 * 3600


def _b64u(data: bytes) -> bytes:
    return urlsafe_b64encode(data).rstrip(b"=")


def _b64u_decode(data: bytes) -> bytes:
    pad = b"=" * (-len(data) % 4)
    return urlsafe_b64decode(data + pad)


def issue_token(device_id: str, tier: str = "free") -> str:
    """Issue a short-lived signed token. Lightweight HS256-style without lib deps."""
    payload = {
        "did": device_id,
        "tier": tier,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(8),
    }
    body = _b64u(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64u(hmac.new(settings.device_token_secret.encode(), body, sha256).digest())
    return f"{body.decode()}.{sig.decode()}"


def verify_token(token: str) -> dict:
    """Verify and decode. Raises HTTPException(401) on any failure."""
    try:
        body, sig = token.split(".")
        expected_sig = _b64u(
            hmac.new(settings.device_token_secret.encode(), body.encode(), sha256).digest()
        ).decode()
        if not secrets.compare_digest(sig, expected_sig):
            raise ValueError("bad sig")
        payload = json.loads(_b64u_decode(body.encode()))
        if payload["exp"] < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
        )


async def auth_dep(authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI dependency: extract + verify Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Bearer token",
        )
    return verify_token(authorization[len("Bearer ") :])
