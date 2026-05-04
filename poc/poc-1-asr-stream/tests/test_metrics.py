"""Tests for metrics.py — pure functions, no IO."""
from metrics import normalize


def test_normalize_strips_chinese_punct():
    assert normalize("你好，世界！") == "你好世界"


def test_normalize_strips_ascii_punct():
    assert normalize("hello, world!") == "hello world"


def test_normalize_collapses_whitespace():
    assert normalize("  你好   世界  ") == "你好 世界"


def test_normalize_fullwidth_to_halfwidth():
    assert normalize("ＡＢＣ１２３") == "ABC123"


def test_normalize_preserves_chinese_chars():
    assert normalize("我爱北京天安门") == "我爱北京天安门"
