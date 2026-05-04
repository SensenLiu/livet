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


from metrics import cer


def test_cer_perfect_match():
    assert cer("你好世界", "你好世界") == 0.0


def test_cer_single_substitution():
    # 1 substitution / 4 chars = 0.25
    assert cer("你好时界", "你好世界") == 0.25


def test_cer_single_deletion():
    # 1 deletion / 4 chars = 0.25
    assert cer("你好世", "你好世界") == 0.25


def test_cer_single_insertion():
    # 1 insertion / 4 chars = 0.25
    assert cer("你好世界界", "你好世界") == 0.25


def test_cer_empty_reference_returns_zero_when_hyp_also_empty():
    assert cer("", "") == 0.0


def test_cer_empty_reference_with_nonempty_hyp_returns_one():
    # No reference chars to match against, but hyp has content → 100% error
    assert cer("hello", "") == 1.0


def test_cer_normalizes_inputs():
    # Punct difference should not count as error
    assert cer("你好，世界", "你好世界") == 0.0
