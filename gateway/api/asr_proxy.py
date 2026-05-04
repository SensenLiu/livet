"""ASR proxy: WebSocket bridge from mobile client to upstream ASR.

Stage-0 design: single vendor (豆包/火山引擎 SAMI streaming).
Multi-vendor fallback was originally planned (讯飞 + 阿里 + 火山) but trimmed
to one vendor per the user's scope-simplification call: voice stack stays on
豆包/火山, since the same vendor already provides our backup LLM (豆包 Pro)
and gives us one console / one bill / one SDK.

Why we still proxy (instead of letting the app talk to 火山 directly):
  - Upstream AK/SK must stay server-side (else reverse-engineering the APK
    leaks them).
  - Privacy: opportunity to enforce 'opaque chunks pass through, never
    persisted' invariant in one place. CI grep enforces this.

Privacy contract:
  - Audio bytes are forwarded chunk-by-chunk to upstream.
  - We do NOT log audio. We do NOT persist audio. CI grep enforces this
    (see scripts/privacy-grep-check.sh).

Future fallback (V0.5+): if 豆包 ASR success rate drops below threshold in
production, add 讯飞 as a second provider. Until then keep this single-vendor
to minimize complexity.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/stream")
async def asr_stream(
    ws: WebSocket,
    token: str = Query(default=""),
) -> None:
    """Bidirectional WebSocket: client sends PCM chunks, server returns transcript.

    Wire protocol (client → server):
        - binary PCM frames (16kHz / 16-bit / mono), <=200ms each
        - text frame `{"type":"end"}` to end stream
    Wire protocol (server → client):
        - text frame `{"type":"partial", "text": "..."}`
        - text frame `{"type":"final",   "text": "..."}`
        - text frame `{"type":"error",   "code": "...", "msg": "..."}`
    """
    # TODO(PoC-1, W2): verify token (reuse core.auth)
    # TODO(PoC-1, W2): connect to 豆包/火山 SAMI streaming WebSocket
    #                  (signing: AK/SK; protocol: binary frames)
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            # Stub until upstream is wired:
            if "bytes" in msg:
                # TODO: forward bytes to 火山 ASR; enforce no .write to disk
                size = len(msg["bytes"])
                await ws.send_json({"type": "partial", "text": f"[stub recv {size}b]"})
            elif "text" in msg:
                if msg["text"] == '{"type":"end"}':
                    await ws.send_json({"type": "final", "text": "[stub stream ended]"})
                    break
    except WebSocketDisconnect:
        return


# TODO(PoC-1, W2): implement 豆包/火山 SAMI streaming bridge
# TODO(V0.5+):     add 讯飞 secondary provider only if 豆包 production success rate < 0.95