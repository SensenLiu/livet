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


def cer(hypothesis: str, reference: str) -> float:
    """Character Error Rate, normalized.

    CER = edit_distance(hyp, ref) / max(len(ref), 1)

    Both inputs are run through normalize() first. Edit distance is
    computed at character level (Levenshtein, S=I=D=1).

    Edge case: if normalized reference is empty:
        - empty hyp → 0.0
        - non-empty hyp → 1.0
    """
    hyp = normalize(hypothesis)
    ref = normalize(reference)

    if not ref:
        return 0.0 if not hyp else 1.0

    # Levenshtein DP. O(len(hyp) * len(ref)) time, O(len(ref)) space.
    prev = list(range(len(ref) + 1))
    for i, ch_h in enumerate(hyp, start=1):
        curr = [i] + [0] * len(ref)
        for j, ch_r in enumerate(ref, start=1):
            cost = 0 if ch_h == ch_r else 1
            curr[j] = min(
                curr[j - 1] + 1,        # insertion
                prev[j] + 1,            # deletion
                prev[j - 1] + cost,     # substitution
            )
        prev = curr
    return prev[-1] / len(ref)
