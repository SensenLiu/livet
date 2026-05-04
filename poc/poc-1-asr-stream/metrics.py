"""Metrics for PoC-1: text normalization, CER, latency.

Pure functions only. No IO, no globals, no logging.
"""
from __future__ import annotations

import re
import unicodedata

# Strip Chinese + ASCII punctuation. Whitespace handled separately.
_PUNCT_RE = re.compile(
    r"[，。！？、；：「」『』（）《》【】〈〉〔〕,.\!?;:\"'`()\[\]{}<>—–\-…]"
)
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalize transcript for CER comparison.

    Steps:
        1. Unicode NFKC: 全角 → 半角, 兼容字符 → 标准形
        2. Strip Chinese + ASCII punctuation
        3. Collapse runs of whitespace to single space
        4. Strip leading/trailing whitespace
    """
    text = unicodedata.normalize("NFKC", text)
    text = _PUNCT_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()
