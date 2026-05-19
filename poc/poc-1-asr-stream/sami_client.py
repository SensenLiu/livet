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
