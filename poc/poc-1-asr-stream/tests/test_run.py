"""Tests for run.py — only the pure helper functions. Main flow tested manually."""
import pytest

from run import load_env, EnvMissing


def test_load_env_reads_required(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "VOLC_ASR_APP_ID=app123\n"
        "VOLC_ASR_ACCESS_TOKEN=tok456\n"
        "OTHER_KEY=ignored\n"
    )
    cfg = load_env(env_path=env)
    assert cfg["VOLC_ASR_APP_ID"] == "app123"
    assert cfg["VOLC_ASR_ACCESS_TOKEN"] == "tok456"


def test_load_env_strips_quotes_and_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        '# comment\n'
        'VOLC_ASR_APP_ID="app123"   # inline comment\n'
        "VOLC_ASR_ACCESS_TOKEN='tok456'\n"
    )
    cfg = load_env(env_path=env)
    assert cfg["VOLC_ASR_APP_ID"] == "app123"
    assert cfg["VOLC_ASR_ACCESS_TOKEN"] == "tok456"


def test_load_env_missing_required_raises(tmp_path):
    env = tmp_path / ".env"
    env.write_text("VOLC_ASR_APP_ID=app123\n")  # missing access token
    with pytest.raises(EnvMissing) as exc:
        load_env(env_path=env)
    assert "VOLC_ASR_ACCESS_TOKEN" in str(exc.value)


def test_load_env_file_not_found(tmp_path):
    with pytest.raises(EnvMissing) as exc:
        load_env(env_path=tmp_path / "nope.env")
    assert "not found" in str(exc.value).lower()


import asyncio
from run import chunks_at_realtime_pace


@pytest.mark.asyncio
async def test_chunks_at_realtime_pace_yields_correct_size():
    # 16kHz, 16-bit, mono, 200ms -> 16000 * 0.2 * 2 = 6400 bytes
    pcm = b"\x00\x01" * (16000 * 1)  # 1 second of PCM
    chunks = []
    async for c in chunks_at_realtime_pace(pcm, chunk_ms=200, sleep=False):
        chunks.append(c)
    assert len(chunks) == 5  # 1s / 200ms
    assert all(len(c) == 6400 for c in chunks)


@pytest.mark.asyncio
async def test_chunks_at_realtime_pace_handles_partial_last_chunk():
    # 1.05s of PCM -> 5 full + 1 partial of 1600 bytes (50ms)
    pcm = b"\x00\x01" * int(16000 * 1.05)
    chunks = []
    async for c in chunks_at_realtime_pace(pcm, chunk_ms=200, sleep=False):
        chunks.append(c)
    assert len(chunks) == 6
    assert len(chunks[-1]) == 1600


@pytest.mark.asyncio
async def test_chunks_at_realtime_pace_paces(monkeypatch):
    # When sleep=True, each yield except first should ~await chunk_ms
    sleeps: list[float] = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    pcm = b"\x00\x01" * 16000  # 1s
    async for _ in chunks_at_realtime_pace(pcm, chunk_ms=200, sleep=True):
        pass

    # 5 chunks → 4 inter-chunk sleeps (no sleep before first)
    assert len(sleeps) == 4
    # Each sleep should be non-negative. Cannot bound upper tightly when
    # asyncio.sleep is mocked (real time keeps advancing while virtual time
    # doesn't), so we only verify the pacing function attempts sleeps at all.
    assert all(s >= 0 for s in sleeps)
