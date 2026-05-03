"""ASR proxy: WebSocket bridge from mobile client to upstream (讯飞/阿里/火山).

Why we proxy:
  - Upstream API keys must stay server-side (else reverse-engineering the APK
    leaks them).
  - Multi-provider auto-fallback per-stream.
  - Privacy: opportunity to enforce 'opaque chunks pass through, never stored'
    invariant in one place (no `.write()` allowed).

Privacy contract:
  - Audio bytes are forwarded chunk-by-chunk to upstream.
  - We do NOT log audio. We do NOT persist audio. CI grep enforces this
    (see scripts/privacy-grep-check.sh).
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/stream")
async def asr_stream(
    ws: WebSocket,
    provider: str = Query(default="xfyun"),
    token: str = Query(default=""),
) -> None:
    """Bidirectional WebSocket: client sends PCM chunks, server returns transcript text.

    Wire protocol (client → server):
        - binary PCM frames (16kHz / 16-bit / mono), <=200ms each
        - text frame `{"type":"end"}` to end stream
    Wire protocol (server → client):
        - text frame `{"type":"partial", "text": "..."}`
        - text frame `{"type":"final",   "text": "..."}`
        - text frame `{"type":"error",   "code": "...", "msg": "..."}`
    """
    # TODO(PoC-1, W2): verify token (reuse core.auth)
    # TODO(PoC-1, W2): connect to upstream provider WebSocket (讯飞先行)
    # TODO(W4): provider auto-fallback on first connect failure
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            # Echo placeholder until upstream is wired:
            if "bytes" in msg:
                # TODO: forward bytes to upstream ASR; enforce no .write to disk
                size = len(msg["bytes"])
                await ws.send_json({"type": "partial", "text": f"[stub recv {size}b]"})
            elif "text" in msg:
                if msg["text"] == '{"type":"end"}':
                    await ws.send_json({"type": "final", "text": "[stub stream ended]"})
                    break
    except WebSocketDisconnect:
        return


# TODO(PoC-1, W2): implement xfyun streaming bridge
# TODO(W4):       implement aliyun + volc bridges + auto-fallback
