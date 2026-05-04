"""LLM proxy with dual-provider fallback (DeepSeek primary, 豆包 backup).

Endpoints:
  POST /v1/llm/chat            — non-streaming
  POST /v1/llm/chat/stream     — SSE streaming

Privacy: we forward request bodies as-is to upstream, never persist them.
Logging: only timing + success/failure + provider name.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.auth import auth_dep
from core.rate_limit import limit
from core.settings import settings

router = APIRouter()


def _provider_payload(provider: str, body: dict[str, Any]) -> dict[str, Any]:
    """Adapt our internal request to provider-specific OpenAI-compatible schema."""
    if provider == "deepseek":
        return {**body, "model": body.get("model", "deepseek-chat")}
    elif provider == "doubao":
        return {**body, "model": body.get("model", settings.doubao_endpoint_id)}
    raise ValueError(f"unknown provider {provider}")


def _provider_url(provider: str) -> str:
    if provider == "deepseek":
        return f"{settings.deepseek_base_url}/chat/completions"
    elif provider == "doubao":
        return f"{settings.doubao_base_url}/chat/completions"
    raise ValueError(f"unknown provider {provider}")


def _provider_key(provider: str) -> str:
    return {
        "deepseek": settings.deepseek_api_key,
        "doubao": settings.doubao_api_key,
    }[provider]


async def _call_one(
    provider: str, body: dict[str, Any], stream: bool, timeout: float = 15.0
) -> httpx.Response:
    url = _provider_url(provider)
    payload = _provider_payload(provider, {**body, "stream": stream})
    headers = {
        "Authorization": f"Bearer {_provider_key(provider)}",
        "Content-Type": "application/json",
    }
    client = httpx.AsyncClient(timeout=timeout)
    return await client.send(
        client.build_request("POST", url, json=payload, headers=headers),
        stream=stream,
    )


@router.post("/chat")
@limit("60/minute")
async def chat(
    request: Request,
    body: dict[str, Any],
    user: dict = Depends(auth_dep),
) -> dict[str, Any]:
    """Non-streaming chat completion with auto-fallback."""
    # TODO(W4): wire HealthChecker via app.state + record per-call latency/success

    candidates = ["deepseek", "doubao"]
    last_err: Exception | None = None
    for provider in candidates:
        try:
            resp = await _call_one(provider, body, stream=False)
            resp.raise_for_status()
            data = resp.json()
            return {"provider": provider, **data}
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise HTTPException(status_code=502, detail=f"all providers failed: {last_err}")


@router.post("/chat/stream")
@limit("60/minute")
async def chat_stream(
    request: Request,
    body: dict[str, Any],
    user: dict = Depends(auth_dep),
) -> StreamingResponse:
    """SSE streaming with auto-fallback on first chunk failure."""
    candidates = ["deepseek", "doubao"]
    for provider in candidates:
        try:
            resp = await _call_one(provider, body, stream=True)

            # Bind resp via default argument to avoid late-binding closure
            # bug if we ever extend the loop with multiple in-flight responses.
            async def event_stream(_resp: httpx.Response = resp):
                async for chunk in _resp.aiter_bytes():
                    yield chunk

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        except Exception:  # noqa: BLE001, S112  # spike: log once HealthChecker is wired (W4)
            continue
    raise HTTPException(status_code=502, detail="all providers unavailable")


# TODO(W4): wire HealthChecker properly + record per-call latency/success
# TODO(W4): support hint-timing low-latency endpoint with stricter timeout (<800ms)
