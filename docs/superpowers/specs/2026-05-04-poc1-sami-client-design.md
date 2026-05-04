# PoC-1: 豆包 SAMI 流式 ASR 客户端 — 设计文档

> 状态：v1（待 user review）· 日期：2026-05-04 · 对应工程计划 §3 PoC-1（缩窄版）

## 1 目标与非目标

### 1.1 本 PoC 要回答的问题

1. 火山引擎 **SAUC bigmodel 流式 ASR**（v3 协议）能否用项目当前 `.env` 中的凭证连通？
2. 端到端"喂一段离线 PCM → 收完 final"的 **延迟** 是多少？
3. 在一段公开中文样本上的 **CER（字错率）** 能否达到工程计划 §1.3 期望的 2-4% 区间？

### 1.2 非目标（YAGNI）

- 麦克风实时输入
- 多供应商 fallback（讯飞/阿里 → V0.5+）
- WS 重连 / 退避
- 加密凭证存储
- Android 端到端链路（属于 PoC-1 完整版的下一步，不在本 PoC 范围）
- 集成进 `gateway/api/asr_proxy.py`（验证通过后另起任务，复用本 PoC 产出的 `sami_client.py`）

## 2 选定方案：v3 SAUC bigmodel

| 项 | 决策 |
|---|---|
| 端点 | `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel` |
| 协议版本 | v3（火山"大模型语音识别 - 流式版"） |
| 鉴权 | HTTP Header：`X-Api-App-Key` + `X-Api-Access-Key` + `X-Api-Resource-Id: volc.bigasr.sauc.duration` + `X-Api-Request-Id: <uuid>` |
| 取材的 .env 变量 | `VOLC_ASR_APP_ID` → App-Key；`VOLC_ASR_ACCESS_TOKEN` → Access-Key |
| 不使用 | `VOLC_ASR_CLUSTER`（仅 v2 标准版相关，本 PoC 忽略；后续清理） |
| 音频格式 | 16kHz / 16-bit / mono PCM；200ms / 帧 |

**为何选 v3 而不是 v2 streaming common**：
- v3 准确率更高，对齐工程计划 §1.3 期望（96-98%）
- v3 是火山当前主推路径，长期支持更稳
- v2 的 cluster 字段仅是 .env 历史遗留，不构成选 v2 的理由

**已知不确定性（PoC 第一次运行就会暴露的）**：
- ⚠️ `VOLC_ASR_ACCESS_TOKEN` 当前值与 `VOLC_AK_ID` 字符串相同——很可能是占位。如果鉴权返回 401/403，需到火山语音控制台拿真正的 access token 回填。run.py 必须给出明确的人话错误提示。
- ⚠️ AppID 是否在火山控制台开通了 SAUC bigmodel 资源（`volc.bigasr.sauc.duration`），未知。同上由 PoC 暴露。

## 3 验证口径（success metrics）

PoC 跑完后输出以下两个数字才算"通过"：

| 指标 | 定义 | 阈值 |
|---|---|---|
| **Final 延迟** | `t_final_recv − t_last_pcm_sent`（毫秒） | < 1500ms |
| **CER（字错率）** | `char-level Levenshtein(final_text, ground_truth) / len(ground_truth)` | < 10%（工程计划期望 2-4%，10% 给 PoC 留宽容） |

阈值未达成不代表方案否决，但要在 PoC 报告里写清原因（音频质量？协议参数？资源未开通？）。

## 4 目录结构与产物

```
poc/poc-1-asr-stream/
├── README.md                 # 怎么跑、期望输出、评估口径、已知风险
├── run.py                    # CLI 入口：file → SAMI → metrics → stdout
├── sami_client.py            # SAMIStreamingClient：纯协议封装，未来可被 gateway import
├── metrics.py                # CER（字级 Levenshtein，自实现 ~15 行 DP）+ 延迟统计；纯函数
├── requirements.txt          # 仅 `websockets>=12`；wav 用 std lib `wave`；Levenshtein 不引第三方库
├── .gitignore                # *.pyc, __pycache__/, *.report.json
└── fixtures/
    ├── README.md             # 音频来源、许可、转录格式
    ├── sample_zh.wav         # ≥10s 中文清唱（Common Voice zh-CN，CC0），16k/16bit/mono
    └── sample_zh.txt         # 对应 ground truth（UTF-8，无标点或仅必要标点，与 SAMI 输出口径对齐时在 metrics 里做归一化）
```

> `requirements.txt` 仅依赖 `websockets`：标准库 `wave` 读 WAV，不引 ffmpeg/numpy/torch；保持 PoC 启动门槛极低。

## 5 模块边界

### 5.1 `sami_client.py`

**职责**：封装 v3 SAUC bigmodel WebSocket 协议。**不感知文件、不感知评估**。

**对外接口**（草拟，writing-plans 阶段细化）：
```python
class SAMIStreamingClient:
    def __init__(self, app_key: str, access_key: str,
                 endpoint: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel",
                 resource_id: str = "volc.bigasr.sauc.duration"):
        ...

    async def stream(self, pcm_chunks: AsyncIterator[bytes]) -> AsyncIterator[Event]:
        """喂 PCM，吐 partial/final/error 事件。"""
```

**Event 形态**：`{"type": "partial"|"final"|"error", "text": str, "raw": dict, "ts_ms": int}`

**失败模式**：连接 4xx/5xx → `SAMIAuthError` / `SAMIConnectError`；JSON 解析错 → `SAMIProtocolError`；30s 无 final → `SAMITimeoutError`。**不吞错**。

**为何独立模块**：将来 `gateway/api/asr_proxy.py` 直接 `from sami_client import SAMIStreamingClient`，PoC 投入不浪费。

### 5.2 `run.py`

**职责**：编排（file IO + 节拍控制 + 调用 client + 算 metrics + 打印报告）。

**CLI**：
```
python run.py --audio fixtures/sample_zh.wav --transcript fixtures/sample_zh.txt [--report out.json]
```

**节拍**：以 wall clock 200ms 为周期送一帧（模拟实时麦克风），不一次性灌完——避免 SAMI 把它当离线请求处理。

### 5.3 `metrics.py`

**纯函数，无 IO**：
- `cer(hypothesis: str, reference: str) -> float`
- `final_latency_ms(t_send_end: float, t_recv_final: float) -> int`
- `normalize(text: str) -> str`（去标点、繁简、全半角；CER 之前调）

## 6 数据流时序

```
run.py                                           SAMI v3
  │
  ├── 读 wav → 校验 16k/16bit/mono ───────────── 不符则 abort
  │
  ├── 建 WS（带鉴权 headers, X-Api-Request-Id=uuid4）
  │  ────────────────── connect ───────────────▶
  │  ◀───── 101 / 4xx 鉴权失败时立即报错并 exit 1
  │
  ├── 发 full_client_request（JSON，声明音频格式 + 高级参数）
  │  ──────────────────────────────────────────▶
  │
  ├── 循环：
  │   每 200ms 发一帧 audio_only_request（binary，含 sequence num）
  │   ──────────────────────────────────────▶
  │   ◀── partial events（打印 t-since-start + text）
  │
  ├── 最后一帧带 is_last=true（t_send_end = now）
  │  ──────────────────────────────────────────▶
  │   ◀── final event（t_recv_final = now）
  │
  ├── 算 final_latency = t_recv_final - t_send_end
  ├── 算 CER = cer(final_text, ground_truth)
  ├── 打印报告：
  │     transcript: "..."
  │     final latency: 1234 ms   [PASS / FAIL vs <1500ms]
  │     CER:           3.2%      [PASS / FAIL vs <10%]
  └── 可选写 out.json
```

## 7 错误处理

| 触发 | run.py 行为 |
|---|---|
| 缺 .env 字段 | fail-fast，明确指出缺哪个变量名 |
| 401/403 | 打印「鉴权失败：检查 (1) 火山语音控制台是否给该 AppID 开通 `volc.bigasr.sauc.duration` 资源 (2) `VOLC_ASR_ACCESS_TOKEN` 是否填了真实 access token（不是 IAM AK_ID）」+ exit 1 |
| WS 中途断开 | 不重连，原样报错 + 已收到的 partial 一并打印（便于事后 debug） + exit 1 |
| 超时（30s 无 final） | 报告 timeout + exit 1 |
| 音频格式不符 | abort 前直接说"需要 16kHz/16bit/mono，当前 X/Y/Z" |

## 8 隐私边界（对齐铁律 #3「数据本地优先，永不保留原声」）

PoC 是开发脚手架，但仍要践行铁律：
- run.py 默认 **不写任何音频** 到磁盘（fixtures/ 是输入，不是产出）
- 转录文本仅 stdout；`--report out.json` 写文件需用户显式开启
- run.py 文件头 docstring 写明：`# PoC scratch only. Not part of user-data path. Do not reuse for production audio capture.`
- 鉴权 headers 中的 access token 不能 print 到 stdout/log

## 9 fixtures 来源与许可

- 来源：[Common Voice zh-CN](https://commonvoice.mozilla.org/zh-CN/datasets)（Mozilla, **CC0**）
- 选样标准：清唱、≥10s（必要时把同一说话人的 2-3 条短 clip **直接 concat**，不插空白；GT 文本同步 concat，不加分隔符）、转录文本可获得、说话人匿名 ID 可记录
- 预处理：本地用 ffmpeg/sox 把 mp3 → 16kHz/16bit/mono PCM WAV，**只 commit 处理后的 wav**（≤500KB），不引入 mp3 解码依赖
- `fixtures/README.md` 记录：原始 clip 的 Common Voice ID、URL、许可证、预处理命令行

## 10 待办与开放点

| # | 项 | 何时回答 |
|---|---|---|
| O1 | `VOLC_ASR_ACCESS_TOKEN` 是否需要换成真正的 speech-console token | 第一次跑 run.py 时由 401/403 暴露 |
| O2 | AppID 是否开通 SAUC bigmodel 资源 | 同上 |
| O3 | SAMI v3 的具体 JSON header 字段（语种、是否启用标点、热词等）按官方最新文档对齐 | writing-plans 阶段查官方 SDK demo |
| O4 | 拿不到 zh-CN 数据集时，回退用火山官方 demo 音频（如有公开授权） | 仅当 O3 后 fixtures 失败再考虑 |

## 11 后续（不在本 PoC）

PoC 验证通过后的下一步（另起任务）：
1. 把 `sami_client.py` 移植到 `gateway/api/asr_proxy.py`，去掉 stub
2. 端到端：Android RN 客户端 + gateway WS bridge + SAMI（这是工程计划 §3 PoC-1 的完整目标）
3. 真实弱网/4G 稳定性测（§1.3 待验证项）
