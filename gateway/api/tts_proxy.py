"""TTS proxy (豆包/火山引擎 voice synthesis large model).

Used for:
  - 🟢 Active mode replies (S5 grounding voice + S8 voice playback opt-in)
  - NOT used for 🟡 passive hints (those play preset .ogg files; product rule #2)

Stage-0 design: single vendor (豆包/火山).
Originally planned 阿里 CosyVoice; consolidated to 豆包 to keep one voice
vendor for both ASR and TTS. Same console, same AK/SK.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.auth import auth_dep
from core.rate_limit import limit

router = APIRouter()


@router.post("/synth")
@limit("30/minute")
async def synth(
    request: Request,
    body: dict,
    user: dict = Depends(auth_dep),
) -> StreamingResponse:
    """POST {text, voice?, speed?, pitch?} -> audio/mpeg stream."""
    # TODO(W6): wire 豆包/火山 voice synthesis large model streaming TTS
    # AK/SK signing; voice id from settings.volc_tts_voice
    raise HTTPException(status_code=501, detail="TTS not implemented yet (W6)")