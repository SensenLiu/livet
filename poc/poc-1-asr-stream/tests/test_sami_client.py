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
