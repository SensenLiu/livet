"""Tests for sami_client.py — protocol framing + WS round-trip via fake server."""
import pytest

from sami_client import (
    SAMIAuthError,
    SAMIConnectError,
    SAMIProtocolError,
    SAMITimeoutError,
    MessageType,
    Serialization,
    Compression,
)


def test_exceptions_are_distinct_classes():
    assert SAMIAuthError is not SAMIConnectError
    assert issubclass(SAMIAuthError, Exception)
    assert issubclass(SAMIConnectError, Exception)
    assert issubclass(SAMIProtocolError, Exception)
    assert issubclass(SAMITimeoutError, Exception)


def test_message_type_constants():
    assert MessageType.FULL_CLIENT_REQUEST == 0x1
    assert MessageType.AUDIO_ONLY_REQUEST == 0x2
    assert MessageType.FULL_SERVER_RESPONSE == 0x9
    assert MessageType.SERVER_ACK == 0xB
    assert MessageType.SERVER_ERROR == 0xF


def test_serialization_constants():
    assert Serialization.RAW == 0x0
    assert Serialization.JSON == 0x1


def test_compression_constants():
    assert Compression.NONE == 0x0
    assert Compression.GZIP == 0x1


from sami_client import build_header, MessageFlags


def test_build_header_full_client_request_json():
    # version=1, header_size=1 (in 4-byte units), msg=FULL_CLIENT_REQUEST,
    # flags=POS_SEQUENCE, ser=JSON, comp=NONE, reserved=0
    h = build_header(
        msg_type=MessageType.FULL_CLIENT_REQUEST,
        flags=MessageFlags.POS_SEQUENCE,
        serialization=Serialization.JSON,
        compression=Compression.NONE,
    )
    assert len(h) == 4
    # byte 0: 0001_0001 = 0x11
    assert h[0] == 0x11
    # byte 1: 0001_0001 = 0x11
    assert h[1] == 0x11
    # byte 2: 0001_0000 = 0x10
    assert h[2] == 0x10
    # byte 3: reserved
    assert h[3] == 0x00


def test_build_header_audio_last_frame():
    h = build_header(
        msg_type=MessageType.AUDIO_ONLY_REQUEST,
        flags=MessageFlags.LAST_POS_SEQ,
        serialization=Serialization.RAW,
        compression=Compression.NONE,
    )
    # byte 1: 0010_0011 = 0x23
    assert h[1] == 0x23
    # byte 2: 0000_0000
    assert h[2] == 0x00


import json
import struct

from sami_client import build_full_client_request, build_audio_frame


def test_build_full_client_request_layout():
    config = {"audio": {"format": "pcm", "rate": 16000}}
    frame = build_full_client_request(config, sequence=1)

    # First 4 bytes: header (msg=1, flags=POS_SEQUENCE, ser=JSON)
    assert frame[0] == 0x11
    assert frame[1] == 0x11
    assert frame[2] == 0x10
    assert frame[3] == 0x00

    # Next 4 bytes: sequence (big-endian int32)
    seq = struct.unpack(">i", frame[4:8])[0]
    assert seq == 1

    # Next 4 bytes: payload size (big-endian uint32)
    size = struct.unpack(">I", frame[8:12])[0]

    # Payload: JSON bytes of config
    payload = frame[12:]
    assert size == len(payload)
    assert json.loads(payload.decode("utf-8")) == config


def test_build_audio_frame_not_last():
    pcm = b"\x00\x01" * 100  # 200 bytes of fake PCM
    frame = build_audio_frame(pcm, sequence=2, is_last=False)

    # byte 1 = msg_type AUDIO (2) << 4 | flags POS_SEQUENCE (1) = 0x21
    assert frame[1] == 0x21
    # byte 2 = ser RAW (0) << 4 | comp NONE (0) = 0x00
    assert frame[2] == 0x00

    seq = struct.unpack(">i", frame[4:8])[0]
    size = struct.unpack(">I", frame[8:12])[0]
    assert seq == 2
    assert size == len(pcm)
    assert frame[12:] == pcm


def test_build_audio_frame_last():
    pcm = b"\xff" * 50
    frame = build_audio_frame(pcm, sequence=3, is_last=True)

    # byte 1 = msg AUDIO (2) << 4 | flags LAST_POS_SEQ (3) = 0x23
    assert frame[1] == 0x23
    # Convention: SAMI signals "last" with negative sequence number.
    # We flip sign on is_last=True.
    seq = struct.unpack(">i", frame[4:8])[0]
    assert seq == -3


from sami_client import parse_server_frame


def _make_server_frame(msg_type: int, flags: int, ser: int, comp: int,
                      sequence: int | None, payload: bytes) -> bytes:
    """Helper: hand-craft a server frame for parser tests."""
    header = bytes([
        (0x1 << 4) | 0x1,
        (msg_type << 4) | flags,
        (ser << 4) | comp,
        0x00,
    ])
    body = b""
    if sequence is not None:
        body += struct.pack(">i", sequence)
    body += struct.pack(">I", len(payload)) + payload
    return header + body


def test_parse_server_full_response_json():
    payload = json.dumps({"result": {"text": "你好世界"}}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0x9, flags=0x1, ser=0x1, comp=0x0,
        sequence=10, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["msg_type"] == MessageType.FULL_SERVER_RESPONSE
    assert evt["sequence"] == 10
    assert evt["payload"] == {"result": {"text": "你好世界"}}
    assert evt["is_last"] is False


def test_parse_server_full_response_last():
    payload = json.dumps({"result": {"text": "完整文本"}}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0x9, flags=0x3, ser=0x1, comp=0x0,
        sequence=20, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["is_last"] is True


def test_parse_server_error_frame():
    payload = json.dumps({"error": "bad token", "code": 1003}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0xF, flags=0x0, ser=0x1, comp=0x0,
        sequence=None, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["msg_type"] == MessageType.SERVER_ERROR
    assert evt["payload"]["code"] == 1003


def test_parse_server_truncated_raises_protocol_error():
    with pytest.raises(SAMIProtocolError):
        parse_server_frame(b"\x11\x91")  # too short for header


import asyncio
import websockets
from websockets.asyncio.server import serve as ws_serve
from sami_client import SAMIStreamingClient


class FakeSAMIServer:
    """Minimal fake server: accepts headers, replies with a partial then a final."""

    def __init__(self):
        self.received_frames: list[bytes] = []
        self.received_headers: dict[str, str] = {}
        self.port: int | None = None
        self._server = None
        self._stop = asyncio.Event()

    async def _handler(self, ws):
        # websockets v12+ puts request headers on ws.request.headers
        try:
            self.received_headers = dict(ws.request.headers)
        except AttributeError:
            self.received_headers = dict(ws.request_headers)

        # Read full_client_request
        first = await ws.recv()
        self.received_frames.append(first)

        # Receive audio frames until we see one with LAST_POS_SEQ flag
        while True:
            frame = await ws.recv()
            self.received_frames.append(frame)
            flags = frame[1] & 0x0F
            if flags == 0x3:  # LAST_POS_SEQ
                break

        # Send a partial then a final
        partial = _make_server_frame(
            msg_type=0x9, flags=0x1, ser=0x1, comp=0x0,
            sequence=1,
            payload=json.dumps({"result": {"text": "你好"}}).encode("utf-8"),
        )
        await ws.send(partial)

        final = _make_server_frame(
            msg_type=0x9, flags=0x3, ser=0x1, comp=0x0,
            sequence=2,
            payload=json.dumps({"result": {"text": "你好世界"}}).encode("utf-8"),
        )
        await ws.send(final)

        # Wait for client to close after consuming final, so we don't race the close frame
        # against the still-buffered final message.
        try:
            async for _ in ws:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass

    async def __aenter__(self):
        self._server = await ws_serve(self._handler, "127.0.0.1", 0)
        # websockets v13 asyncio.server socket discovery
        sock = next(iter(self._server.sockets))
        self.port = sock.getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()


@pytest.mark.asyncio
async def test_stream_round_trip():
    async with FakeSAMIServer() as srv:
        client = SAMIStreamingClient(
            api_key="fake-api-key",
            endpoint=f"ws://127.0.0.1:{srv.port}",
            resource_id="volc.seedasr.sauc.duration",
        )

        async def chunks():
            yield b"\x00\x01" * 100
            yield b"\x02\x03" * 100
            yield b"\x04\x05" * 100

        events = []
        async for evt in client.stream(chunks()):
            events.append(evt)

        # 1 partial + 1 final
        assert len(events) == 2
        assert events[0]["type"] == "partial"
        assert events[0]["text"] == "你好"
        assert events[1]["type"] == "final"
        assert events[1]["text"] == "你好世界"

    # Verify auth headers landed
    assert srv.received_headers.get("x-api-key") == "fake-api-key"
    assert srv.received_headers.get("x-api-resource-id") == "volc.seedasr.sauc.duration"
    assert "x-api-connect-id" in srv.received_headers

    # Verify framing: 1 full_client_request + 3 audio frames (last is "is_last")
    assert len(srv.received_frames) == 4
    assert srv.received_frames[0][1] >> 4 == 0x1  # FULL_CLIENT_REQUEST
    for f in srv.received_frames[1:]:
        assert f[1] >> 4 == 0x2  # AUDIO_ONLY_REQUEST
    assert srv.received_frames[-1][1] & 0x0F == 0x3  # LAST_POS_SEQ on final audio
