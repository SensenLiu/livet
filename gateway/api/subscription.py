"""Subscription receipt verification + device token issue.

Endpoints:
  POST /v1/sub/token              — issue device-bound JWT (free tier or paid)
  POST /v1/sub/verify/wechat      — verify WeChat Pay receipt (V1)
  POST /v1/sub/verify/apple       — verify Apple IAP receipt (V1.5, iOS not yet)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.auth import issue_token

router = APIRouter()


class TokenIssueRequest(BaseModel):
    device_id: str
    receipt: str | None = None  # optional subscription receipt


class TokenIssueResponse(BaseModel):
    token: str
    tier: str
    expires_in: int = 86400  # seconds


@router.post("/token", response_model=TokenIssueResponse)
async def issue(req: TokenIssueRequest) -> TokenIssueResponse:
    """Issue a 24h JWT for the given device. If receipt is provided and valid,
    bump the tier to 'paid'.
    """
    tier = "free"
    if req.receipt:
        # TODO(W11): verify receipt with WeChat / Apple
        # tier = "paid" if verify_ok else "free"
        pass
    return TokenIssueResponse(
        token=issue_token(req.device_id, tier=tier),
        tier=tier,
    )


@router.post("/verify/wechat")
async def verify_wechat(body: dict) -> dict:
    # TODO(W11): WeChat Pay v3 callback verification
    raise HTTPException(status_code=501, detail="WeChat verify not implemented (W11)")


@router.post("/verify/apple")
async def verify_apple(body: dict) -> dict:
    # TODO(V1.5): Apple IAP receipt verification
    raise HTTPException(status_code=501, detail="Apple IAP not in V1")
