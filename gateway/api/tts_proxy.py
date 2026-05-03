"""TTS proxy (Aliyun CosyVoice).

Used for:
  - 🟢 Active mode replies (S5 grounding + S8 voice playback opt-in)
  - NOT used for 🟡 passive hints (those play preset .ogg files; rule #2)
"""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.auth import auth_dep
from core.rate_limit import limit

router = APIRouter()


@router.post("/synth")
@limit("30/minute")
async def synth(
    request: Request,
    body: Dict,
    user: dict = Depends(auth_dep),
) -> StreamingResponse:
    """POST {text, voice?, speed?, pitch?} -> audio/mpeg stream."""
    # TODO(W6): wire Aliyun CosyVoice streaming TTS
    raise HTTPException(status_code=501, detail="TTS not implemented yet (W6)")
