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
