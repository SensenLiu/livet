# PoC-1 SAMI Streaming ASR Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写一个独立的 Python CLI（`poc/poc-1-asr-stream/run.py`），把一段本地 16kHz/16-bit/mono PCM WAV 喂给火山引擎 SAUC bigmodel v3 流式 ASR，拿到转录文本，打印 final 延迟和 CER 两个验证数字。

**Architecture:** 三个模块、单向依赖：`metrics.py`（纯函数，无 IO）← `run.py`（编排）→ `sami_client.py`（协议封装，纯协议、无文件 IO）。`sami_client.py` 设计成将来 `gateway/api/asr_proxy.py` 可直接 import。

**Tech Stack:** Python 3.10+；`websockets>=12`（唯一运行时依赖）；标准库 `wave` 读 WAV；标准库 `unicodedata` 做归一化；测试用 `pytest` + `pytest-asyncio`，本地 `websockets.serve` 起 fake 服务器测协议。

**关键参考资料**（实施时必须打开浏览器对照）：
- 火山引擎《大模型流式语音识别（流式版）》官方文档：https://www.volcengine.com/docs/6561/1354869
- 火山官方 Python demo：https://github.com/volcengine/volcengine-speech-demo（找 `sauc/bigmodel/streaming` 目录）
- 设计文档（spec）：`docs/superpowers/specs/2026-05-04-poc1-sami-client-design.md`

> ⚠️ **本计划描述的二进制协议字段（header bits、message type、flags）是基于公开文档的最佳记忆**。实施时必须以**官方 Python demo 实际代码**为准。如果 fake WS server 测试通过但真实 SAMI 返回 SERVER_ERROR，第一反应是去对照官方 demo 的 framer，不要怀疑测试本身。

---

## Phase 0：脚手架

### Task 1：建目录、依赖文件、.gitignore

**Files:**
- Create: `poc/poc-1-asr-stream/requirements.txt`
- Create: `poc/poc-1-asr-stream/requirements-dev.txt`
- Create: `poc/poc-1-asr-stream/.gitignore`
- Create: `poc/poc-1-asr-stream/__init__.py`（空文件，让 `tests/` 可 import）
- Create: `poc/poc-1-asr-stream/tests/__init__.py`（空文件）
- Create: `poc/poc-1-asr-stream/fixtures/.gitkeep`（占位）

- [ ] **Step 1.1：创建目录**

```bash
cd poc/poc-1-asr-stream
mkdir -p tests fixtures
touch __init__.py tests/__init__.py fixtures/.gitkeep
```

- [ ] **Step 1.2：写 requirements.txt**

```
websockets>=12,<14
```

- [ ] **Step 1.3：写 requirements-dev.txt**

```
-r requirements.txt
pytest>=7.4,<9
pytest-asyncio>=0.23,<1
```

- [ ] **Step 1.4：写 .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
*.report.json
.env
```

- [ ] **Step 1.5：装依赖、验证 import**

```bash
cd poc/poc-1-asr-stream
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -c "import websockets, pytest; print(websockets.__version__, pytest.__version__)"
```
Expected: 打印两个版本号，无错误。

- [ ] **Step 1.6：commit**

```bash
git add poc/poc-1-asr-stream/
git commit -m "chore(poc-1): scaffold dirs, deps, gitignore"
```

> 注：`.venv/` 不需要 ignore（Step 1.4 只 ignore 常见噪音）。如果 `.venv/` 被 Git 误识别，单独 `git rm` 后再加 `.venv/` 到 .gitignore。

---

## Phase 1：metrics.py（纯函数，TDD）

### Task 2：normalize() — 文本归一化

> 用途：CER 计算前，把 SAMI 输出和 GT 都归一化到同一形态（去标点、繁简、全半角），避免"。"vs""或"，"vs ","导致虚假错误率。

**Files:**
- Create: `poc/poc-1-asr-stream/tests/test_metrics.py`
- Create: `poc/poc-1-asr-stream/metrics.py`

- [ ] **Step 2.1：写失败测试**

`tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2.2：跑测试，确认 fail**

```bash
cd poc/poc-1-asr-stream
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 5 个 test fail，错误是 `ModuleNotFoundError: No module named 'metrics'`。

- [ ] **Step 2.3：实现 normalize()**

`metrics.py`:

```python
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
```

- [ ] **Step 2.4：跑测试，确认 pass**

```bash
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 5/5 pass。

- [ ] **Step 2.5：commit**

```bash
git add poc/poc-1-asr-stream/metrics.py poc/poc-1-asr-stream/tests/test_metrics.py
git commit -m "feat(poc-1): metrics.normalize for CER preprocessing"
```

### Task 3：cer() — 字级编辑距离错误率

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_metrics.py`
- Modify: `poc/poc-1-asr-stream/metrics.py`

- [ ] **Step 3.1：追加失败测试**

在 `tests/test_metrics.py` 末尾追加：

```python
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
```

- [ ] **Step 3.2：跑测试，确认 fail**

```bash
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 7 个新测试 fail（`ImportError: cannot import name 'cer'`）。

- [ ] **Step 3.3：实现 cer()**

在 `metrics.py` 末尾追加：

```python
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
```

- [ ] **Step 3.4：跑测试，确认 pass**

```bash
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 12/12 pass（5 个 normalize + 7 个 cer）。

- [ ] **Step 3.5：commit**

```bash
git add poc/poc-1-asr-stream/metrics.py poc/poc-1-asr-stream/tests/test_metrics.py
git commit -m "feat(poc-1): metrics.cer with char-level Levenshtein"
```

### Task 4：final_latency_ms() — 延迟计算

> 极简，但单独写以保持纯函数边界 + 单元测覆盖。

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_metrics.py`
- Modify: `poc/poc-1-asr-stream/metrics.py`

- [ ] **Step 4.1：追加测试**

在 `tests/test_metrics.py` 末尾追加：

```python
from metrics import final_latency_ms


def test_final_latency_basic():
    assert final_latency_ms(t_send_end=100.0, t_recv_final=101.234) == 1234


def test_final_latency_rounds_down():
    assert final_latency_ms(t_send_end=0.0, t_recv_final=0.0009) == 0


def test_final_latency_negative_clamps_to_zero():
    # Defensive: clock skew shouldn't produce negative latencies
    assert final_latency_ms(t_send_end=10.0, t_recv_final=9.5) == 0
```

- [ ] **Step 4.2：跑测试，确认 fail**

```bash
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 3 个新测试 fail。

- [ ] **Step 4.3：实现**

在 `metrics.py` 末尾追加：

```python
def final_latency_ms(t_send_end: float, t_recv_final: float) -> int:
    """Latency from sending the last PCM frame to receiving the final transcript.

    Inputs are time.monotonic()-style seconds. Returns whole milliseconds.
    Clamps negative deltas (clock skew, buggy callers) to 0.
    """
    delta = t_recv_final - t_send_end
    return max(0, int(delta * 1000))
```

- [ ] **Step 4.4：跑测试，确认 pass**

```bash
PYTHONPATH=. pytest tests/test_metrics.py -v
```
Expected: 15/15 pass。

- [ ] **Step 4.5：commit**

```bash
git add poc/poc-1-asr-stream/metrics.py poc/poc-1-asr-stream/tests/test_metrics.py
git commit -m "feat(poc-1): metrics.final_latency_ms"
```

---

## Phase 2：fixtures（音频 + GT）

### Task 5：下载并预处理 Common Voice 中文样本

> 这是手工任务，但每步要清晰可重现。如果你（agent）在没有外网或 ffmpeg 的环境中跑，先停下来问用户。

**Files:**
- Create: `poc/poc-1-asr-stream/fixtures/sample_zh.wav`
- Create: `poc/poc-1-asr-stream/fixtures/sample_zh.txt`
- Create: `poc/poc-1-asr-stream/fixtures/README.md`
- Delete: `poc/poc-1-asr-stream/fixtures/.gitkeep`

- [ ] **Step 5.1：检查工具**

```bash
which ffmpeg && ffmpeg -version | head -1
```
Expected：找到 ffmpeg。如果没有，在 Ubuntu 上 `sudo apt-get install ffmpeg`。

- [ ] **Step 5.2：从 Common Voice 拿一段 zh-CN 样本**

去 https://commonvoice.mozilla.org/zh-CN/datasets ，下载最新 zh-CN delta（最小那个，几百 MB）。解压后从 `clips/` 目录里挑一条满足条件的：
- 单条时长 ≥ 8s（命令行：`ffprobe -v error -show_entries format=duration filename.mp3`），或拼接同说话人 2-3 条到 ≥10s
- 在 `validated.tsv` 里能找到对应转录
- 只挑 up_votes ≥ 2 且 down_votes = 0 的条目（质量高）

如果一时拿不到完整 dataset，**fallback 路径**：去 https://commonvoice.mozilla.org/zh-CN/listen 用浏览器 DevTools 录一条 listen 页面播放的 mp3 + 复制对应文本，并在 fixtures/README.md 里如实记录该 clip 的 sentence_id。

记下选中条目的：
- `client_id`（说话人匿名 ID）
- `path`（clip 文件名）
- `sentence`（GT 文本）

- [ ] **Step 5.3：转码到 16kHz/16-bit/mono PCM WAV**

```bash
cd poc/poc-1-asr-stream
ffmpeg -i /path/to/source.mp3 -ar 16000 -ac 1 -sample_fmt s16 fixtures/sample_zh.wav
```

如果是拼接多条：

```bash
ffmpeg -i "concat:clip_a.mp3|clip_b.mp3" -ar 16000 -ac 1 -sample_fmt s16 fixtures/sample_zh.wav
```

验证：

```bash
ffprobe -v error -show_entries stream=sample_rate,channels,sample_fmt,duration -of default=noprint_wrappers=1 fixtures/sample_zh.wav
```
Expected: `sample_rate=16000`, `channels=1`, `sample_fmt=s16`, `duration` ≥ 10。

文件大小应 ≤ 500KB（30s @ 16k mono s16 = 960KB；建议 ≤15s）：

```bash
ls -lh fixtures/sample_zh.wav
```

- [ ] **Step 5.4：写 GT 文本**

把 Step 5.2 拿到的 `sentence` 字段（如果是拼接，按拼接顺序 concat，**不加分隔符**）写到 `fixtures/sample_zh.txt`：

```bash
echo -n "今天天气真好我们一起去公园散步好吗" > fixtures/sample_zh.txt   # 示例，替换为真实文本
```

> 注意：UTF-8、不带 BOM、末尾无换行（`echo -n`），便于和 SAMI 输出按字面比较。

- [ ] **Step 5.5：写 fixtures/README.md**

```markdown
# PoC-1 fixtures

## sample_zh.wav

| 字段 | 值 |
|---|---|
| 来源 | Mozilla Common Voice zh-CN |
| 许可 | CC0 1.0 (public domain) |
| 原 clip 文件名 | <填: e.g. common_voice_zh-CN_18524963.mp3> |
| 说话人 client_id | <填> |
| Common Voice sentence_id | <填，如有> |
| 上传 votes | <up=N, down=0> |
| 处理后格式 | 16kHz / 16-bit / mono PCM WAV |
| 处理后时长 | <填, 秒> |
| 处理命令 | `ffmpeg -i <src> -ar 16000 -ac 1 -sample_fmt s16 sample_zh.wav` |

如需更换 fixture，更新本表后 commit。

## sample_zh.txt

对应 `sample_zh.wav` 的 ground truth 转录文本。UTF-8、无 BOM、无尾换行。
拼接 clip 时按拼接顺序 concat，不加分隔符。
```

- [ ] **Step 5.6：清理占位、commit**

```bash
git rm poc/poc-1-asr-stream/fixtures/.gitkeep
git add poc/poc-1-asr-stream/fixtures/
git commit -m "chore(poc-1): add Common Voice zh-CN fixture (CC0)"
```

---

## Phase 3：sami_client.py（v3 SAUC bigmodel 协议）

> ⚠️ 实施前打开两个东西：
> 1. https://www.volcengine.com/docs/6561/1354869（协议文档）
> 2. 火山官方 demo（GitHub）的 framer 源码
>
> 本 Phase 描述的二进制布局是基于公开资料的最佳记忆，**以官方代码为准**。

### Task 6：异常类型与协议常量

**Files:**
- Create: `poc/poc-1-asr-stream/tests/test_sami_client.py`
- Create: `poc/poc-1-asr-stream/sami_client.py`

- [ ] **Step 6.1：写失败测试**

`tests/test_sami_client.py`:

```python
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
```

- [ ] **Step 6.2：跑测试，fail**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: ImportError。

- [ ] **Step 6.3：实现常量与异常**

`sami_client.py`:

```python
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
```

- [ ] **Step 6.4：测试 pass**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: 4/4 pass。

- [ ] **Step 6.5：commit**

```bash
git add poc/poc-1-asr-stream/sami_client.py poc/poc-1-asr-stream/tests/test_sami_client.py
git commit -m "feat(poc-1): SAMI client constants and exception hierarchy"
```

### Task 7：build_header() — 4 字节协议头

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_sami_client.py`
- Modify: `poc/poc-1-asr-stream/sami_client.py`

- [ ] **Step 7.1：追加测试**

在 `tests/test_sami_client.py` 末尾追加：

```python
from sami_client import build_header, MessageFlags


def test_build_header_full_client_request_json():
    # version=1, header_size=1 (in 4-byte units), msg=FULL_CLIENT_REQUEST,
    # flags=POS_SEQUENCE, ser=JSON, comp=NONE, reserved=0
    h = build_header(
        msg_type=MessageType.FULL_CLIENT_REQUEST,
        flags=MessageFlags.POS_SEQUENCE,
        serialization=Serialization.JSON,
        compression=Compression.NONE,
    )
    assert len(h) == 4
    # byte 0: 0001_0001 = 0x11
    assert h[0] == 0x11
    # byte 1: 0001_0001 = 0x11
    assert h[1] == 0x11
    # byte 2: 0001_0000 = 0x10
    assert h[2] == 0x10
    # byte 3: reserved
    assert h[3] == 0x00


def test_build_header_audio_last_frame():
    h = build_header(
        msg_type=MessageType.AUDIO_ONLY_REQUEST,
        flags=MessageFlags.LAST_POS_SEQ,
        serialization=Serialization.RAW,
        compression=Compression.NONE,
    )
    # byte 1: 0010_0011 = 0x23
    assert h[1] == 0x23
    # byte 2: 0000_0000
    assert h[2] == 0x00
```

- [ ] **Step 7.2：fail**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: 2 个新测试 fail（ImportError build_header）。

- [ ] **Step 7.3：实现 build_header**

在 `sami_client.py` 末尾追加：

```python
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
```

- [ ] **Step 7.4：pass**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: 6/6 pass。

- [ ] **Step 7.5：commit**

```bash
git add poc/poc-1-asr-stream/sami_client.py poc/poc-1-asr-stream/tests/test_sami_client.py
git commit -m "feat(poc-1): SAMI build_header (4-byte v3 framing)"
```

### Task 8：build_full_client_request() 与 build_audio_frame()

> 这两个 builder 把 header + sequence + payload-size + payload 拼成完整的一帧。

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_sami_client.py`
- Modify: `poc/poc-1-asr-stream/sami_client.py`

- [ ] **Step 8.1：追加测试**

```python
import json
import struct

from sami_client import build_full_client_request, build_audio_frame


def test_build_full_client_request_layout():
    config = {"audio": {"format": "pcm", "rate": 16000}}
    frame = build_full_client_request(config, sequence=1)

    # First 4 bytes: header (msg=1, flags=POS_SEQUENCE, ser=JSON)
    assert frame[0] == 0x11
    assert frame[1] == 0x11
    assert frame[2] == 0x10
    assert frame[3] == 0x00

    # Next 4 bytes: sequence (big-endian int32)
    seq = struct.unpack(">i", frame[4:8])[0]
    assert seq == 1

    # Next 4 bytes: payload size (big-endian uint32)
    size = struct.unpack(">I", frame[8:12])[0]

    # Payload: JSON bytes of config
    payload = frame[12:]
    assert size == len(payload)
    assert json.loads(payload.decode("utf-8")) == config


def test_build_audio_frame_not_last():
    pcm = b"\x00\x01" * 100  # 200 bytes of fake PCM
    frame = build_audio_frame(pcm, sequence=2, is_last=False)

    # byte 1 = msg_type AUDIO (2) << 4 | flags POS_SEQUENCE (1) = 0x21
    assert frame[1] == 0x21
    # byte 2 = ser RAW (0) << 4 | comp NONE (0) = 0x00
    assert frame[2] == 0x00

    seq = struct.unpack(">i", frame[4:8])[0]
    size = struct.unpack(">I", frame[8:12])[0]
    assert seq == 2
    assert size == len(pcm)
    assert frame[12:] == pcm


def test_build_audio_frame_last():
    pcm = b"\xff" * 50
    frame = build_audio_frame(pcm, sequence=3, is_last=True)

    # byte 1 = msg AUDIO (2) << 4 | flags LAST_POS_SEQ (3) = 0x23
    assert frame[1] == 0x23
    # Convention: SAMI signals "last" with negative sequence number.
    # We flip sign on is_last=True.
    seq = struct.unpack(">i", frame[4:8])[0]
    assert seq == -3
```

- [ ] **Step 8.2：fail**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```

- [ ] **Step 8.3：实现**

在 `sami_client.py` 末尾追加：

```python
import json
import struct


def build_full_client_request(
    config: dict,
    sequence: int = 1,
) -> bytes:
    """Build a FULL_CLIENT_REQUEST frame with JSON payload.

    Layout: header (4) + sequence (4 BE int32) + size (4 BE uint32) + JSON payload.
    """
    header = build_header(
        msg_type=MessageType.FULL_CLIENT_REQUEST,
        flags=MessageFlags.POS_SEQUENCE,
        serialization=Serialization.JSON,
        compression=Compression.NONE,
    )
    payload = json.dumps(config, ensure_ascii=False).encode("utf-8")
    return (
        header
        + struct.pack(">i", sequence)
        + struct.pack(">I", len(payload))
        + payload
    )


def build_audio_frame(
    pcm: bytes,
    sequence: int,
    is_last: bool,
) -> bytes:
    """Build an AUDIO_ONLY_REQUEST frame.

    is_last=True signals end of stream by:
      - flags = LAST_POS_SEQ (0x3)
      - sequence number is negated (SAMI convention)
    """
    flags = MessageFlags.LAST_POS_SEQ if is_last else MessageFlags.POS_SEQUENCE
    header = build_header(
        msg_type=MessageType.AUDIO_ONLY_REQUEST,
        flags=flags,
        serialization=Serialization.RAW,
        compression=Compression.NONE,
    )
    seq_value = -sequence if is_last else sequence
    return (
        header
        + struct.pack(">i", seq_value)
        + struct.pack(">I", len(pcm))
        + pcm
    )
```

- [ ] **Step 8.4：pass**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: 9/9 pass。

- [ ] **Step 8.5：commit**

```bash
git add poc/poc-1-asr-stream/sami_client.py poc/poc-1-asr-stream/tests/test_sami_client.py
git commit -m "feat(poc-1): SAMI frame builders (full_client_request, audio_frame)"
```

### Task 9：parse_server_frame() — 反向解码

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_sami_client.py`
- Modify: `poc/poc-1-asr-stream/sami_client.py`

- [ ] **Step 9.1：追加测试**

```python
from sami_client import parse_server_frame


def _make_server_frame(msg_type: int, flags: int, ser: int, comp: int,
                      sequence: int | None, payload: bytes) -> bytes:
    """Helper: hand-craft a server frame for parser tests."""
    header = bytes([
        (0x1 << 4) | 0x1,
        (msg_type << 4) | flags,
        (ser << 4) | comp,
        0x00,
    ])
    body = b""
    if sequence is not None:
        body += struct.pack(">i", sequence)
    body += struct.pack(">I", len(payload)) + payload
    return header + body


def test_parse_server_full_response_json():
    payload = json.dumps({"result": {"text": "你好世界"}}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0x9, flags=0x1, ser=0x1, comp=0x0,
        sequence=10, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["msg_type"] == MessageType.FULL_SERVER_RESPONSE
    assert evt["sequence"] == 10
    assert evt["payload"] == {"result": {"text": "你好世界"}}
    assert evt["is_last"] is False


def test_parse_server_full_response_last():
    payload = json.dumps({"result": {"text": "完整文本"}}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0x9, flags=0x3, ser=0x1, comp=0x0,
        sequence=20, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["is_last"] is True


def test_parse_server_error_frame():
    payload = json.dumps({"error": "bad token", "code": 1003}).encode("utf-8")
    raw = _make_server_frame(
        msg_type=0xF, flags=0x0, ser=0x1, comp=0x0,
        sequence=None, payload=payload,
    )
    evt = parse_server_frame(raw)
    assert evt["msg_type"] == MessageType.SERVER_ERROR
    assert evt["payload"]["code"] == 1003


def test_parse_server_truncated_raises_protocol_error():
    with pytest.raises(SAMIProtocolError):
        parse_server_frame(b"\x11\x91")  # too short for header
```

- [ ] **Step 9.2：fail**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```

- [ ] **Step 9.3：实现**

```python
def parse_server_frame(raw: bytes) -> dict:
    """Parse a server frame.

    Returns:
        {
            "msg_type": MessageType,
            "is_last": bool,
            "sequence": int | None,
            "payload": dict | bytes,   # dict if JSON, bytes otherwise
        }

    Raises SAMIProtocolError on malformed input.
    """
    if len(raw) < 4:
        raise SAMIProtocolError(f"frame too short: {len(raw)} bytes")

    msg_type_int = (raw[1] >> 4) & 0x0F
    flags = raw[1] & 0x0F
    ser = (raw[2] >> 4) & 0x0F

    try:
        msg_type = MessageType(msg_type_int)
    except ValueError as e:
        raise SAMIProtocolError(f"unknown msg_type {msg_type_int:#x}") from e

    is_last = (flags & int(MessageFlags.LAST_NO_SEQ)) != 0  # 0x2 bit set

    cursor = 4
    sequence: int | None = None
    if (flags & int(MessageFlags.POS_SEQUENCE)) != 0:  # 0x1 bit set
        if len(raw) < cursor + 4:
            raise SAMIProtocolError("truncated sequence field")
        sequence = struct.unpack(">i", raw[cursor:cursor + 4])[0]
        cursor += 4

    if len(raw) < cursor + 4:
        raise SAMIProtocolError("truncated payload size field")
    size = struct.unpack(">I", raw[cursor:cursor + 4])[0]
    cursor += 4

    if len(raw) < cursor + size:
        raise SAMIProtocolError(
            f"declared payload {size}B but only {len(raw) - cursor}B available"
        )

    body = raw[cursor:cursor + size]
    payload: dict | bytes
    if ser == int(Serialization.JSON):
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SAMIProtocolError(f"invalid JSON payload: {e}") from e
    else:
        payload = body

    return {
        "msg_type": msg_type,
        "is_last": is_last,
        "sequence": sequence,
        "payload": payload,
    }
```

- [ ] **Step 9.4：pass**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py -v
```
Expected: 13/13 pass。

- [ ] **Step 9.5：commit**

```bash
git add poc/poc-1-asr-stream/sami_client.py poc/poc-1-asr-stream/tests/test_sami_client.py
git commit -m "feat(poc-1): SAMI server frame parser"
```

### Task 10：SAMIStreamingClient.stream() — 整合 + fake WS server 测试

> 这是 Phase 2 的核心集成测试。开一个本地 `websockets.serve` 假装是 SAMI server，验证 client 能正确发包/收包。

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_sami_client.py`
- Modify: `poc/poc-1-asr-stream/sami_client.py`

- [ ] **Step 10.1：追加 conftest 和集成测试**

Create: `poc/poc-1-asr-stream/tests/conftest.py`

```python
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

在 `tests/test_sami_client.py` 末尾追加：

```python
import asyncio
import websockets
from sami_client import SAMIStreamingClient


class FakeSAMIServer:
    """Minimal fake server: accepts headers, replies with a partial then a final."""

    def __init__(self):
        self.received_frames: list[bytes] = []
        self.received_headers: dict[str, str] = {}
        self.port: int | None = None
        self._server = None
        self._stop = asyncio.Event()

    async def _handler(self, ws):
        # websockets v12 puts request headers on ws.request.headers
        try:
            self.received_headers = dict(ws.request.headers)
        except AttributeError:
            self.received_headers = dict(ws.request_headers)

        # Read full_client_request
        first = await ws.recv()
        self.received_frames.append(first)

        # Receive audio frames until we see one with LAST_POS_SEQ flag
        while True:
            frame = await ws.recv()
            self.received_frames.append(frame)
            flags = frame[1] & 0x0F
            if flags == 0x3:  # LAST_POS_SEQ
                break

        # Send a partial then a final
        partial = _make_server_frame(
            msg_type=0x9, flags=0x1, ser=0x1, comp=0x0,
            sequence=1,
            payload=json.dumps({"result": {"text": "你好"}}).encode("utf-8"),
        )
        await ws.send(partial)

        final = _make_server_frame(
            msg_type=0x9, flags=0x3, ser=0x1, comp=0x0,
            sequence=2,
            payload=json.dumps({"result": {"text": "你好世界"}}).encode("utf-8"),
        )
        await ws.send(final)

    async def __aenter__(self):
        self._server = await websockets.serve(self._handler, "127.0.0.1", 0)
        # websockets v12 socket discovery
        sock = next(iter(self._server.sockets))
        self.port = sock.getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()


@pytest.mark.asyncio
async def test_stream_round_trip():
    async with FakeSAMIServer() as srv:
        client = SAMIStreamingClient(
            app_key="fake-app",
            access_key="fake-token",
            endpoint=f"ws://127.0.0.1:{srv.port}",
            resource_id="volc.bigasr.sauc.duration",
        )

        async def chunks():
            yield b"\x00\x01" * 100
            yield b"\x02\x03" * 100
            yield b"\x04\x05" * 100

        events = []
        async for evt in client.stream(chunks()):
            events.append(evt)

        # 1 partial + 1 final
        assert len(events) == 2
        assert events[0]["type"] == "partial"
        assert events[0]["text"] == "你好"
        assert events[1]["type"] == "final"
        assert events[1]["text"] == "你好世界"

    # Verify auth headers landed
    assert srv.received_headers.get("x-api-app-key") == "fake-app"
    assert srv.received_headers.get("x-api-access-key") == "fake-token"
    assert srv.received_headers.get("x-api-resource-id") == "volc.bigasr.sauc.duration"
    assert "x-api-request-id" in srv.received_headers

    # Verify framing: 1 full_client_request + 3 audio frames (last is "is_last")
    assert len(srv.received_frames) == 4
    assert srv.received_frames[0][1] >> 4 == 0x1  # FULL_CLIENT_REQUEST
    for f in srv.received_frames[1:]:
        assert f[1] >> 4 == 0x2  # AUDIO_ONLY_REQUEST
    assert srv.received_frames[-1][1] & 0x0F == 0x3  # LAST_POS_SEQ on final audio
```

- [ ] **Step 10.2：fail**

```bash
PYTHONPATH=. pytest tests/test_sami_client.py::test_stream_round_trip -v
```
Expected: ImportError 或 AttributeError on `SAMIStreamingClient.stream`.

- [ ] **Step 10.3：实现 SAMIStreamingClient**

在 `sami_client.py` 末尾追加：

```python
import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import TypedDict

import websockets


class StreamEvent(TypedDict):
    type: str         # "partial" | "final" | "error"
    text: str
    raw: dict
    ts_ms: int        # monotonic ms when received (caller uses for latency math)


class SAMIStreamingClient:
    """Volcengine SAUC bigmodel v3 streaming ASR client.

    Usage:
        client = SAMIStreamingClient(app_key=..., access_key=...)
        async for event in client.stream(pcm_chunks):
            ...
    """

    DEFAULT_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
    DEFAULT_RESOURCE = "volc.bigasr.sauc.duration"

    def __init__(
        self,
        app_key: str,
        access_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        resource_id: str = DEFAULT_RESOURCE,
        idle_timeout_s: float = 30.0,
    ):
        if not app_key:
            raise ValueError("app_key required")
        if not access_key:
            raise ValueError("access_key required")
        self.app_key = app_key
        self.access_key = access_key
        self.endpoint = endpoint
        self.resource_id = resource_id
        self.idle_timeout_s = idle_timeout_s

    def _config_payload(self) -> dict:
        """Initial JSON config sent in FULL_CLIENT_REQUEST."""
        return {
            "user": {"uid": "poc-1"},
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                "result_type": "single",   # progressive partial; replace with "incremental" if docs disagree
            },
        }

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-App-Key": self.app_key,
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

    async def stream(
        self,
        pcm_chunks: AsyncIterator[bytes],
    ) -> AsyncIterator[StreamEvent]:
        """Open WS, send config + PCM, yield partial/final events."""
        try:
            ws = await websockets.connect(
                self.endpoint,
                additional_headers=self._headers(),
                max_size=2 ** 24,
            )
        except websockets.exceptions.InvalidStatus as e:
            status = e.response.status_code
            if status in (401, 403):
                raise SAMIAuthError(f"upstream rejected auth ({status})") from e
            raise SAMIConnectError(f"upstream returned {status}") from e
        except OSError as e:
            raise SAMIConnectError(f"cannot reach {self.endpoint}: {e}") from e

        async with ws:
            # 1. send config
            await ws.send(build_full_client_request(self._config_payload(), sequence=1))

            # 2. spawn audio sender + receiver concurrently
            seq = 2

            async def send_audio():
                nonlocal seq
                last: bytes | None = None
                async for chunk in pcm_chunks:
                    if last is not None:
                        await ws.send(build_audio_frame(last, seq, is_last=False))
                        seq += 1
                    last = chunk
                # send the final chunk (or empty if no chunks at all) with is_last=True
                await ws.send(build_audio_frame(last or b"", seq, is_last=True))

            send_task = asyncio.create_task(send_audio())

            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=self.idle_timeout_s)
                    except websockets.exceptions.ConnectionClosed as e:
                        raise SAMIConnectError(
                            f"connection closed mid-stream: {e}"
                        ) from e
                    evt = parse_server_frame(raw)
                    ts_ms = int(asyncio.get_event_loop().time() * 1000)

                    if evt["msg_type"] == MessageType.SERVER_ERROR:
                        yield StreamEvent(
                            type="error",
                            text="",
                            raw=evt["payload"] if isinstance(evt["payload"], dict) else {},
                            ts_ms=ts_ms,
                        )
                        raise SAMIProtocolError(f"upstream error: {evt['payload']}")

                    if evt["msg_type"] == MessageType.FULL_SERVER_RESPONSE:
                        text = ""
                        if isinstance(evt["payload"], dict):
                            text = (
                                evt["payload"]
                                .get("result", {})
                                .get("text", "")
                            )
                        yield StreamEvent(
                            type="final" if evt["is_last"] else "partial",
                            text=text,
                            raw=evt["payload"] if isinstance(evt["payload"], dict) else {},
                            ts_ms=ts_ms,
                        )
                        if evt["is_last"]:
                            break
                    # SERVER_ACK: ignore
            except asyncio.TimeoutError as e:
                raise SAMITimeoutError(f"no final within {self.idle_timeout_s}s") from e
            finally:
                if not send_task.done():
                    send_task.cancel()
                try:
                    await send_task
                except (asyncio.CancelledError, Exception):
                    pass
```

- [ ] **Step 10.4：跑全量测试**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: 14/14 pass。

> 如果 fake server 测试失败、报 `request_headers` 相关 AttributeError，根据本地 websockets 版本调整 fixture 里的属性名（v12: `ws.request.headers`，v11: `ws.request_headers`）。

- [ ] **Step 10.5：commit**

```bash
git add poc/poc-1-asr-stream/sami_client.py poc/poc-1-asr-stream/tests/
git commit -m "feat(poc-1): SAMIStreamingClient.stream + fake WS server integration test"
```

---

## Phase 4：run.py（CLI orchestration）

### Task 11：load_env() — 从 ../../gateway/.env 读凭证

**Files:**
- Create: `poc/poc-1-asr-stream/tests/test_run.py`
- Create: `poc/poc-1-asr-stream/run.py`

- [ ] **Step 11.1：写测试**

`tests/test_run.py`:

```python
"""Tests for run.py — only the pure helper functions. Main flow tested manually."""
import pytest

from run import load_env, EnvMissing, chunks_at_realtime_pace


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
```

- [ ] **Step 11.2：fail**

```bash
PYTHONPATH=. pytest tests/test_run.py -v
```

- [ ] **Step 11.3：实现 load_env**

`run.py`:

```python
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
```

- [ ] **Step 11.4：pass (subset)**

```bash
PYTHONPATH=. pytest tests/test_run.py::test_load_env_reads_required tests/test_run.py::test_load_env_strips_quotes_and_comments tests/test_run.py::test_load_env_missing_required_raises tests/test_run.py::test_load_env_file_not_found -v
```
Expected: 4/4 pass.

- [ ] **Step 11.5：commit**

```bash
git add poc/poc-1-asr-stream/run.py poc/poc-1-asr-stream/tests/test_run.py
git commit -m "feat(poc-1): run.load_env reads ../../gateway/.env"
```

### Task 12：chunks_at_realtime_pace() — 200ms 节拍 PCM 生成器

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_run.py`
- Modify: `poc/poc-1-asr-stream/run.py`

- [ ] **Step 12.1：追加测试**

```python
import asyncio


def _async_run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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
    assert all(0 <= s <= 0.2 for s in sleeps)
```

- [ ] **Step 12.2：fail**

```bash
PYTHONPATH=. pytest tests/test_run.py -v
```

- [ ] **Step 12.3：实现**

在 `run.py` 末尾追加：

```python
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
```

- [ ] **Step 12.4：pass**

```bash
PYTHONPATH=. pytest tests/test_run.py -v
```
Expected: 7/7 pass.

- [ ] **Step 12.5：commit**

```bash
git add poc/poc-1-asr-stream/run.py poc/poc-1-asr-stream/tests/test_run.py
git commit -m "feat(poc-1): chunks_at_realtime_pace 200ms generator"
```

### Task 13：read_wav_pcm() — WAV 读取与格式校验

**Files:**
- Modify: `poc/poc-1-asr-stream/tests/test_run.py`
- Modify: `poc/poc-1-asr-stream/run.py`

- [ ] **Step 13.1：追加测试**

```python
from run import read_wav_pcm, WavFormatError


def _write_wav(path, *, rate, channels, sampwidth, frames):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(frames)


def test_read_wav_pcm_happy_path(tmp_path):
    wav = tmp_path / "ok.wav"
    pcm = b"\x00\x01" * 16000  # 1 second
    _write_wav(wav, rate=16000, channels=1, sampwidth=2, frames=pcm)
    out = read_wav_pcm(wav)
    assert out == pcm


def test_read_wav_pcm_wrong_rate_raises(tmp_path):
    wav = tmp_path / "bad.wav"
    _write_wav(wav, rate=44100, channels=1, sampwidth=2, frames=b"\x00\x01" * 100)
    with pytest.raises(WavFormatError) as exc:
        read_wav_pcm(wav)
    assert "16000" in str(exc.value)
    assert "44100" in str(exc.value)


def test_read_wav_pcm_wrong_channels_raises(tmp_path):
    wav = tmp_path / "bad.wav"
    _write_wav(wav, rate=16000, channels=2, sampwidth=2, frames=b"\x00\x01\x02\x03" * 100)
    with pytest.raises(WavFormatError):
        read_wav_pcm(wav)


def test_read_wav_pcm_wrong_sampwidth_raises(tmp_path):
    wav = tmp_path / "bad.wav"
    _write_wav(wav, rate=16000, channels=1, sampwidth=1, frames=b"\x00" * 100)
    with pytest.raises(WavFormatError):
        read_wav_pcm(wav)
```

- [ ] **Step 13.2：fail**

```bash
PYTHONPATH=. pytest tests/test_run.py -v
```

- [ ] **Step 13.3：实现**

在 `run.py` 末尾追加：

```python
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
```

- [ ] **Step 13.4：pass**

```bash
PYTHONPATH=. pytest tests/test_run.py -v
```
Expected: 11/11 pass.

- [ ] **Step 13.5：commit**

```bash
git add poc/poc-1-asr-stream/run.py poc/poc-1-asr-stream/tests/test_run.py
git commit -m "feat(poc-1): read_wav_pcm with format validation"
```

### Task 14：main() — 完整编排，含 metrics 输出

> 这一步没有单元测试（main 是 IO orchestration，整合所有部分）。验证靠 Phase 5 的端到端运行。

**Files:**
- Modify: `poc/poc-1-asr-stream/run.py`

- [ ] **Step 14.1：实现 main**

在 `run.py` 末尾追加：

```python
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
```

- [ ] **Step 14.2：跑全部单元测试，确认未回归**

```bash
PYTHONPATH=. pytest tests/ -v
```
Expected: 全 pass（约 40 个测试：metrics 15 + sami_client 14 + run 11）。

- [ ] **Step 14.3：commit**

```bash
git add poc/poc-1-asr-stream/run.py
git commit -m "feat(poc-1): run.main end-to-end orchestration"
```

---

## Phase 5：端到端运行 + README

### Task 15：写 README

**Files:**
- Create: `poc/poc-1-asr-stream/README.md`

- [ ] **Step 15.1：写 README**

```markdown
# PoC-1: 豆包 SAMI 流式 ASR 客户端

> Spec: [`docs/superpowers/specs/2026-05-04-poc1-sami-client-design.md`](../../docs/superpowers/specs/2026-05-04-poc1-sami-client-design.md)
> Plan: [`docs/superpowers/plans/2026-05-04-poc1-sami-client.md`](../../docs/superpowers/plans/2026-05-04-poc1-sami-client.md)

## What it does

把一段本地 16kHz/16-bit/mono PCM WAV 喂给火山引擎 SAUC bigmodel 流式 ASR
（v3 协议），打印转录、final 延迟、CER。

## Quickstart

```bash
cd poc/poc-1-asr-stream
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 跑测试
PYTHONPATH=. pytest tests/ -v

# 跑端到端（需要 ../../gateway/.env 已配置 VOLC_ASR_APP_ID + VOLC_ASR_ACCESS_TOKEN）
PYTHONPATH=. python run.py \
  --audio fixtures/sample_zh.wav \
  --transcript fixtures/sample_zh.txt \
  --report run.report.json
```

## Expected output

```
[INFO] audio=fixtures/sample_zh.wav (320000 bytes PCM)
[INFO] endpoint=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
[INFO] resource=volc.bigasr.sauc.duration
[PARTIAL] +312ms  你好
[PARTIAL] +615ms  你好世界
[FINAL] +10120ms  你好世界欢迎使用语音识别
[RESULT] transcript: 你好世界欢迎使用语音识别
[RESULT] final_latency: 420 ms  [PASS vs <1500ms]
[RESULT] CER: 2.50%  [PASS vs <10%]
```

Exit codes:
- 0: both metrics PASS
- 1: at least one metric FAIL（仍然返回了 transcript）
- 2: 配置或音频格式错
- 3: 鉴权错（401/403）→ 看下方 troubleshoot
- 4: 连接错
- 5: 超时
- 6: 协议错
- 7: 流结束时没收到 final

## Troubleshoot: AUTH-FAIL

按 **AUTH-FAIL** 报错最常见的两种情况：

1. **AppID 未开通 SAUC bigmodel 资源**：去
   https://console.volcengine.com/speech/ → 大模型语音识别 → 流式版 → 点开通；
   开通后 `volc.bigasr.sauc.duration` 才有效。
2. **Access Token 不对**：火山控制台「应用管理」里每个应用有自己的
   Access Token，**和 IAM 的 AK_ID 不是一回事**。把它填进 `gateway/.env` 的
   `VOLC_ASR_ACCESS_TOKEN`。

## 隐私

PoC scratch only. 不把音频写盘，不把 access token 写日志。
不要 import 进 production 路径，相关代码（`sami_client.py`）整体迁移到
`gateway/api/asr_proxy.py` 时再走 review。
```

- [ ] **Step 15.2：commit**

```bash
git add poc/poc-1-asr-stream/README.md
git commit -m "docs(poc-1): README with quickstart + troubleshoot"
```

### Task 16：端到端跑一次，记录结果

> 这是手工任务，但产物是一个 `eval-reports/` 下的报告文件 + 一次 commit。
> **预期第一次会 AUTH-FAIL**（spec §10 风险 O1/O2 即将兑现）。这是预期内的结果，
> 不是 bug——失败本身就是 PoC 的产出之一。

**Files:**
- Create: `eval-reports/2026-05-04-poc1-run.md`

- [ ] **Step 16.1：第一次跑**

```bash
cd poc/poc-1-asr-stream
PYTHONPATH=. python run.py \
  --audio fixtures/sample_zh.wav \
  --transcript fixtures/sample_zh.txt \
  --report ../../eval-reports/2026-05-04-poc1-run.report.json 2>&1 | tee /tmp/poc1.log
```

- [ ] **Step 16.2：基于结果，分支处理**

**Case A: AUTH-FAIL** → 记录到 `eval-reports/2026-05-04-poc1-run.md`：

```markdown
# PoC-1 Run #1 — 2026-05-04

**Status:** AUTH-FAIL（预期）

**Outcome:** 火山控制台需要：
- [ ] 给 AppID 8435898292 开通 `volc.bigasr.sauc.duration` 资源
- [ ] 拿到正确的 access token，回填 `gateway/.env` 的 VOLC_ASR_ACCESS_TOKEN

**Log excerpt:**
\`\`\`
<贴 /tmp/poc1.log 关键几行>
\`\`\`

**Next step:** 到火山控制台完成上述两步，然后回到 Step 16.3 重跑。
```

提交后停下，让用户去控制台开通。

**Case B: 跑通但指标 FAIL** → 记录指标、分析 CER 高的原因（标点？数字？方言？）：

```markdown
# PoC-1 Run #1 — 2026-05-04

**Status:** RAN, metric FAIL

| 指标 | 值 | 阈值 | 结果 |
|---|---|---|---|
| Final 延迟 | 1820 ms | <1500 ms | FAIL |
| CER | 8.4% | <10% | PASS |

**Transcript:** ...
**Ground truth:** ...

**Diff highlights:** <逐字对照标错处>

**Hypothesis:** <为何 latency 偏高 / CER 偏高>

**Next step:** <调参或换 fixture>
```

**Case C: 全 PASS** → 简短记录、庆祝、关 PoC：

```markdown
# PoC-1 Run #1 — 2026-05-04

**Status:** ✅ ALL PASS

| 指标 | 值 | 阈值 |
|---|---|---|
| Final 延迟 | 420 ms | <1500 ms |
| CER | 2.5% | <10% |

PoC-1 验证通过。下一步：把 sami_client 迁移到 gateway/api/asr_proxy.py。
```

- [ ] **Step 16.3：commit 报告**

```bash
git add eval-reports/2026-05-04-poc1-run.md
# 如果有 .report.json:
git add eval-reports/2026-05-04-poc1-run.report.json
git commit -m "report(poc-1): first run result — <CASE A/B/C 一句话>"
```

- [ ] **Step 16.4（仅 Case A）：等用户操作完控制台后重跑**

确认 token 已更新，重复 Step 16.1，把结果追加到 `eval-reports/2026-05-04-poc1-run.md` 作为 "Run #2"。

---

## 完整测试清单（实施完所有 Task 后）

```bash
cd poc/poc-1-asr-stream
PYTHONPATH=. pytest tests/ -v
# Expected: 全 pass（约 40 个测试）
```

```bash
PYTHONPATH=. python run.py --audio fixtures/sample_zh.wav --transcript fixtures/sample_zh.txt
# Expected: 跑通，输出延迟与 CER；或在 AUTH-FAIL 时给出明确指引
```
