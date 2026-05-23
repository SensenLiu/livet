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


class WavFormatError(Exception):
    """WAV file is not 16kHz/16-bit/mono."""


def read_wav_pcm(path: Path) -> bytes:
    """Read a WAV file and return raw PCM bytes.

    Raises WavFormatError if the format is not 16kHz / 16-bit / mono.
    """
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        if rate != SAMPLE_RATE or channels != CHANNELS or sampwidth != SAMPLE_WIDTH:
            raise WavFormatError(
                f"need {SAMPLE_RATE}Hz / {SAMPLE_WIDTH * 8}-bit / "
                f"{CHANNELS}ch, got {rate}Hz / {sampwidth * 8}-bit / "
                f"{channels}ch ({path})"
            )
        return w.readframes(w.getnframes())


def _print_safe(label: str, msg: str) -> None:
    """Print to stderr to keep stdout clean for --report consumers."""
    print(f"[{label}] {msg}", file=sys.stderr)


async def _run_async(args: argparse.Namespace) -> int:
    env_path = Path(args.env) if args.env else DEFAULT_ENV_PATH
    try:
        env = load_env(env_path)
    except EnvMissing as e:
        _print_safe("ENV", str(e))
        return 2

    audio_path = Path(args.audio)
    transcript_path = Path(args.transcript)
    try:
        pcm = read_wav_pcm(audio_path)
    except WavFormatError as e:
        _print_safe("WAV", str(e))
        return 2

    ground_truth = transcript_path.read_text(encoding="utf-8")

    client = SAMIStreamingClient(
        app_key=env["VOLC_ASR_APP_ID"],
        access_key=env["VOLC_ASR_ACCESS_TOKEN"],
    )

    _print_safe("INFO", f"audio={audio_path} ({len(pcm)} bytes PCM)")
    _print_safe("INFO", f"endpoint={client.endpoint}")
    _print_safe("INFO", f"resource={client.resource_id}")

    final_text: str | None = None
    t_send_end: float | None = None
    t_recv_final: float | None = None
    t_start = time.monotonic()

    async def chunks_with_send_end_capture():
        nonlocal t_send_end
        async for chunk in chunks_at_realtime_pace(pcm):
            yield chunk
        t_send_end = time.monotonic()

    try:
        async for evt in client.stream(chunks_with_send_end_capture()):
            elapsed = int((time.monotonic() - t_start) * 1000)
            if evt["type"] == "partial":
                _print_safe("PARTIAL", f"+{elapsed}ms  {evt['text']}")
            elif evt["type"] == "final":
                t_recv_final = time.monotonic()
                final_text = evt["text"]
                _print_safe("FINAL", f"+{elapsed}ms  {evt['text']}")
            elif evt["type"] == "error":
                _print_safe("UPSTREAM-ERROR", json.dumps(evt["raw"], ensure_ascii=False))
    except SAMIAuthError as e:
        _print_safe("AUTH-FAIL", str(e))
        _print_safe("HINT", "Check (1) Volcengine speech console: AppID has "
                           "'volc.bigasr.sauc.duration' enabled. (2) "
                           "VOLC_ASR_ACCESS_TOKEN is the speech-console access "
                           "token (NOT the IAM AK_ID).")
        return 3
    except SAMIConnectError as e:
        _print_safe("CONNECT-FAIL", str(e))
        return 4
    except SAMITimeoutError as e:
        _print_safe("TIMEOUT", str(e))
        return 5
    except SAMIProtocolError as e:
        _print_safe("PROTOCOL-FAIL", str(e))
        return 6

    if final_text is None or t_send_end is None or t_recv_final is None:
        _print_safe("ERROR", "stream ended without a final")
        return 7

    latency_ms = final_latency_ms(t_send_end, t_recv_final)
    char_err_rate = cer(final_text, ground_truth)

    lat_ok = latency_ms < LATENCY_THRESHOLD_MS
    cer_ok = char_err_rate < CER_THRESHOLD

    report = {
        "transcript": final_text,
        "ground_truth": ground_truth,
        "final_latency_ms": latency_ms,
        "latency_threshold_ms": LATENCY_THRESHOLD_MS,
        "latency_pass": lat_ok,
        "cer": round(char_err_rate, 4),
        "cer_threshold": CER_THRESHOLD,
        "cer_pass": cer_ok,
    }

    _print_safe("RESULT", f"transcript: {final_text}")
    _print_safe("RESULT", f"final_latency: {latency_ms} ms  "
                          f"[{'PASS' if lat_ok else 'FAIL'} vs <{LATENCY_THRESHOLD_MS}ms]")
    _print_safe("RESULT", f"CER: {char_err_rate * 100:.2f}%  "
                          f"[{'PASS' if cer_ok else 'FAIL'} vs <{CER_THRESHOLD * 100:.0f}%]")

    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        _print_safe("RESULT", f"report written to {args.report}")

    return 0 if (lat_ok and cer_ok) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PoC-1 SAMI streaming ASR runner.")
    p.add_argument("--audio", required=True, help="path to 16k/16bit/mono WAV")
    p.add_argument("--transcript", required=True, help="path to UTF-8 ground truth")
    p.add_argument("--env", default=None,
                   help="path to .env (default: ../../gateway/.env)")
    p.add_argument("--report", default=None,
                   help="optional: write JSON report to this path")
    args = p.parse_args(argv)
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    sys.exit(main())
