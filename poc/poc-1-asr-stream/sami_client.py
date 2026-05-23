"""Volcengine SAUC bigmodel streaming ASR (v3) WebSocket client.

Protocol reference: https://www.volcengine.com/docs/6561/1354869

This module is intentionally ignorant of files, audio capture, and metrics.
It eats async-iterated PCM frames and emits an async-iterated event stream.

PoC scratch only. Not part of user-data path. Do not reuse for production audio
capture without re-reviewing privacy guarantees.
"""
from __future__ import annotations

import enum


# === Protocol constants (v3 binary framing) ===

class MessageType(enum.IntEnum):
    """Upper 4 bits of header byte 1."""
    FULL_CLIENT_REQUEST = 0x1
    AUDIO_ONLY_REQUEST = 0x2
    FULL_SERVER_RESPONSE = 0x9
    SERVER_ACK = 0xB
    SERVER_ERROR = 0xF


class Serialization(enum.IntEnum):
    """Upper 4 bits of header byte 2."""
    RAW = 0x0
    JSON = 0x1


class Compression(enum.IntEnum):
    """Lower 4 bits of header byte 2."""
    NONE = 0x0
    GZIP = 0x1


class MessageFlags(enum.IntFlag):
    """Lower 4 bits of header byte 1."""
    NONE = 0x0
    POS_SEQUENCE = 0x1       # message carries a positive sequence number
    LAST_NO_SEQ = 0x2        # last message, no sequence
    LAST_POS_SEQ = 0x3       # last message, positive sequence


# === Exceptions ===

class SAMIError(Exception):
    """Base for all SAMI client errors."""


class SAMIAuthError(SAMIError):
    """401/403 from upstream. Check app_key / access_token / resource enablement."""


class SAMIConnectError(SAMIError):
    """Network-level failure connecting to upstream."""


class SAMIProtocolError(SAMIError):
    """Upstream sent something we couldn't parse, or returned SERVER_ERROR."""


class SAMITimeoutError(SAMIError):
    """Did not receive a final response within the timeout window."""


PROTOCOL_VERSION = 0x1
HEADER_SIZE_UNITS = 0x1  # header is 1 * 4 = 4 bytes


def build_header(
    msg_type: MessageType,
    flags: MessageFlags,
    serialization: Serialization,
    compression: Compression,
) -> bytes:
    """Build the 4-byte v3 binary frame header.

    Layout:
        byte 0:  [version: 4 bits][header_size: 4 bits]
        byte 1:  [msg_type: 4 bits][flags: 4 bits]
        byte 2:  [serialization: 4 bits][compression: 4 bits]
        byte 3:  reserved (0)
    """
    return bytes([
        (PROTOCOL_VERSION << 4) | HEADER_SIZE_UNITS,
        (int(msg_type) << 4) | int(flags),
        (int(serialization) << 4) | int(compression),
        0x00,
    ])


import json
import struct


def build_full_client_request(
    config: dict,
    sequence: int = 1,
) -> bytes:
    """Build a FULL_CLIENT_REQUEST frame with JSON payload.

    Layout: header (4) + sequence (4 BE int32) + size (4 BE uint32) + JSON payload.
    """
    header = build_header(
        msg_type=MessageType.FULL_CLIENT_REQUEST,
        flags=MessageFlags.POS_SEQUENCE,
        serialization=Serialization.JSON,
        compression=Compression.NONE,
    )
    payload = json.dumps(config, ensure_ascii=False).encode("utf-8")
    return (
        header
        + struct.pack(">i", sequence)
        + struct.pack(">I", len(payload))
        + payload
    )


def build_audio_frame(
    pcm: bytes,
    sequence: int,
    is_last: bool,
) -> bytes:
    """Build an AUDIO_ONLY_REQUEST frame.

    is_last=True signals end of stream by:
      - flags = LAST_POS_SEQ (0x3)
      - sequence number is negated (SAMI convention)
    """
    flags = MessageFlags.LAST_POS_SEQ if is_last else MessageFlags.POS_SEQUENCE
    header = build_header(
        msg_type=MessageType.AUDIO_ONLY_REQUEST,
        flags=flags,
        serialization=Serialization.RAW,
        compression=Compression.NONE,
    )
    seq_value = -sequence if is_last else sequence
    return (
        header
        + struct.pack(">i", seq_value)
        + struct.pack(">I", len(pcm))
        + pcm
    )


def parse_server_frame(raw: bytes) -> dict:
    """Parse a server frame.

    Returns:
        {
            "msg_type": MessageType,
            "is_last": bool,
            "sequence": int | None,
            "payload": dict | bytes,   # dict if JSON, bytes otherwise
        }

    Raises SAMIProtocolError on malformed input.
    """
    if len(raw) < 4:
        raise SAMIProtocolError(f"frame too short: {len(raw)} bytes")

    msg_type_int = (raw[1] >> 4) & 0x0F
    flags = raw[1] & 0x0F
    ser = (raw[2] >> 4) & 0x0F

    try:
        msg_type = MessageType(msg_type_int)
    except ValueError as e:
        raise SAMIProtocolError(f"unknown msg_type {msg_type_int:#x}") from e

    is_last = (flags & int(MessageFlags.LAST_NO_SEQ)) != 0  # 0x2 bit set

    cursor = 4
    sequence: int | None = None
    if (flags & int(MessageFlags.POS_SEQUENCE)) != 0:  # 0x1 bit set
        if len(raw) < cursor + 4:
            raise SAMIProtocolError("truncated sequence field")
        sequence = struct.unpack(">i", raw[cursor:cursor + 4])[0]
        cursor += 4

    if len(raw) < cursor + 4:
        raise SAMIProtocolError("truncated payload size field")
    size = struct.unpack(">I", raw[cursor:cursor + 4])[0]
    cursor += 4

    if len(raw) < cursor + size:
        raise SAMIProtocolError(
            f"declared payload {size}B but only {len(raw) - cursor}B available"
        )

    body = raw[cursor:cursor + size]
    payload: dict | bytes
    if ser == int(Serialization.JSON):
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SAMIProtocolError(f"invalid JSON payload: {e}") from e
    else:
        payload = body

    return {
        "msg_type": msg_type,
        "is_last": is_last,
        "sequence": sequence,
        "payload": payload,
    }


import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import TypedDict

import websockets
from websockets.asyncio.client import connect as ws_connect


class StreamEvent(TypedDict):
    type: str         # "partial" | "final" | "error"
    text: str
    raw: dict
    ts_ms: int        # monotonic ms when received (caller uses for latency math)


class SAMIStreamingClient:
    """Volcengine SAUC bigmodel v3 streaming ASR client.

    Usage:
        client = SAMIStreamingClient(app_key=..., access_key=...)
        async for event in client.stream(pcm_chunks):
            ...
    """

    DEFAULT_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
    DEFAULT_RESOURCE = "volc.bigasr.sauc.duration"

    def __init__(
        self,
        app_key: str,
        access_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        resource_id: str = DEFAULT_RESOURCE,
        idle_timeout_s: float = 30.0,
    ):
        if not app_key:
            raise ValueError("app_key required")
        if not access_key:
            raise ValueError("access_key required")
        self.app_key = app_key
        self.access_key = access_key
        self.endpoint = endpoint
        self.resource_id = resource_id
        self.idle_timeout_s = idle_timeout_s

    def _config_payload(self) -> dict:
        """Initial JSON config sent in FULL_CLIENT_REQUEST."""
        return {
            "user": {"uid": "poc-1"},
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                "result_type": "single",
            },
        }

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-App-Key": self.app_key,
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

    async def stream(
        self,
        pcm_chunks: AsyncIterator[bytes],
    ) -> AsyncIterator[StreamEvent]:
        """Open WS, send config + PCM, yield partial/final events."""
        try:
            ws = await ws_connect(
                self.endpoint,
                additional_headers=self._headers(),
                max_size=2 ** 24,
            )
        except websockets.exceptions.InvalidStatus as e:
            status = e.response.status_code
            if status in (401, 403):
                raise SAMIAuthError(f"upstream rejected auth ({status})") from e
            raise SAMIConnectError(f"upstream returned {status}") from e
        except OSError as e:
            raise SAMIConnectError(f"cannot reach {self.endpoint}: {e}") from e

        async with ws:
            # 1. send config
            await ws.send(build_full_client_request(self._config_payload(), sequence=1))

            # 2. spawn audio sender + receiver concurrently
            seq = 2

            async def send_audio():
                nonlocal seq
                last: bytes | None = None
                async for chunk in pcm_chunks:
                    if last is not None:
                        await ws.send(build_audio_frame(last, seq, is_last=False))
                        seq += 1
                    last = chunk
                # send the final chunk (or empty if no chunks at all) with is_last=True
                await ws.send(build_audio_frame(last or b"", seq, is_last=True))

            send_task = asyncio.create_task(send_audio())

            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=self.idle_timeout_s)
                    except websockets.exceptions.ConnectionClosed as e:
                        raise SAMIConnectError(
                            f"connection closed mid-stream: {e}"
                        ) from e
                    evt = parse_server_frame(raw)
                    ts_ms = int(asyncio.get_event_loop().time() * 1000)

                    if evt["msg_type"] == MessageType.SERVER_ERROR:
                        yield StreamEvent(
                            type="error",
                            text="",
                            raw=evt["payload"] if isinstance(evt["payload"], dict) else {},
                            ts_ms=ts_ms,
                        )
                        raise SAMIProtocolError(f"upstream error: {evt['payload']}")

                    if evt["msg_type"] == MessageType.FULL_SERVER_RESPONSE:
                        text = ""
                        if isinstance(evt["payload"], dict):
                            text = (
                                evt["payload"]
                                .get("result", {})
                                .get("text", "")
                            )
                        yield StreamEvent(
                            type="final" if evt["is_last"] else "partial",
                            text=text,
                            raw=evt["payload"] if isinstance(evt["payload"], dict) else {},
                            ts_ms=ts_ms,
                        )
                        if evt["is_last"]:
                            break
                    # SERVER_ACK: ignore
            except asyncio.TimeoutError as e:
                raise SAMITimeoutError(f"no final within {self.idle_timeout_s}s") from e
            finally:
                if not send_task.done():
                    send_task.cancel()
                try:
                    await send_task
                except (asyncio.CancelledError, Exception):
                    pass
