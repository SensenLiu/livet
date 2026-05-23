"""PoC-1 SAMI streaming ASR runner.

PoC scratch only. Not part of user-data path. Do not reuse for production audio
capture without re-reviewing privacy guarantees (see CLAUDE.md philosophy #3).

Usage:
    python run.py --audio fixtures/sample_zh.wav --transcript fixtures/sample_zh.txt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave
from collections.abc import AsyncIterator
from pathlib import Path

from metrics import cer, final_latency_ms
from sami_client import (
    SAMIAuthError,
    SAMIConnectError,
    SAMIProtocolError,
    SAMIStreamingClient,
    SAMITimeoutError,
)


REQUIRED_ENV = ("VOLC_ASR_APP_ID", "VOLC_ASR_ACCESS_TOKEN")
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / "gateway" / ".env"

LATENCY_THRESHOLD_MS = 1500
CER_THRESHOLD = 0.10

CHUNK_MS = 200
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


class EnvMissing(Exception):
    """A required environment variable was missing or .env file unreadable."""


def load_env(env_path: Path) -> dict[str, str]:
    """Read .env file (KEY=VALUE format), return dict of REQUIRED_ENV values.

    Raises EnvMissing if file is absent or any required key is missing.
    """
    if not env_path.exists():
        raise EnvMissing(f".env not found at {env_path}")

    cfg: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip inline comment
        if "#" in value:
            value = value.split("#", 1)[0]
        value = value.strip().strip('"').strip("'")
        if key in REQUIRED_ENV:
            cfg[key] = value

    missing = [k for k in REQUIRED_ENV if not cfg.get(k)]
    if missing:
        raise EnvMissing(f"missing required env vars: {', '.join(missing)}")
    return cfg


async def chunks_at_realtime_pace(
    pcm: bytes,
    chunk_ms: int = CHUNK_MS,
    sleep: bool = True,
) -> AsyncIterator[bytes]:
    """Yield PCM chunks of `chunk_ms` duration at wall-clock pace.

    Real-time pacing simulates a microphone, which is what SAMI streaming
    expects (otherwise it may return early "final" prematurely).

    sleep=False is for tests: emit all chunks immediately.
    """
    bytes_per_chunk = int(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * chunk_ms / 1000)
    target_interval_s = chunk_ms / 1000.0

    next_send_t = time.monotonic()
    first = True
    for offset in range(0, len(pcm), bytes_per_chunk):
        chunk = pcm[offset:offset + bytes_per_chunk]
        if not chunk:
            break

        if sleep and not first:
            now = time.monotonic()
            wait = next_send_t - now
            if wait > 0:
                await asyncio.sleep(wait)
        first = False
        next_send_t += target_interval_s
        yield chunk
