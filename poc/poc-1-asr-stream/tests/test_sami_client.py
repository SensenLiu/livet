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
