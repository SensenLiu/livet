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
