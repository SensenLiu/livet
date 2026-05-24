# PoC-1: 豆包流式语音识别 2.0 客户端

> Plan: [`docs/superpowers/plans/2026-05-04-poc1-sami-client.md`](../../docs/superpowers/plans/2026-05-04-poc1-sami-client.md)
> Spec: [`docs/superpowers/specs/2026-05-04-poc1-sami-client-design.md`](../../docs/superpowers/specs/2026-05-04-poc1-sami-client-design.md)

## What it does

把一段本地 16kHz/16-bit/mono PCM WAV 喂给火山引擎「豆包流式语音识别模型 2.0」
（v3 双向流式协议），打印增量 partial、final 转录、final 延迟、CER。

## Quickstart

```bash
cd poc/poc-1-asr-stream
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 跑测试（40 个）
PYTHONPATH=. pytest tests/ -v

# 跑端到端（需要 ../../gateway/.env 已配置 VOLC_API_KEY）
PYTHONPATH=. python run.py \
  --audio fixtures/sample_zh.wav \
  --transcript fixtures/sample_zh.txt \
  --report run.report.json
```

## 鉴权

走**新版控制台 API Key 鉴权**（不是旧版的 AppID + Access Token）。

`gateway/.env`：

```bash
VOLC_API_KEY=<火山新版控制台 → API Key 管理 拿到的 key>
```

请求头自动构造为：

```
X-Api-Key: <VOLC_API_KEY>
X-Api-Resource-Id: volc.seedasr.sauc.duration
X-Api-Connect-Id: <uuid>
```

## Expected output

```
[INFO] audio=fixtures/sample_zh.wav (480000 bytes PCM)
[INFO] endpoint=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
[INFO] resource=volc.seedasr.sauc.duration
[PARTIAL] +10565ms  我们这个季度的回款比预期低了大概15%。是
...
[FINAL] +15591ms  我们这个季度的回款比预期低了大概15%，是华东两个大客户的付款周期延长了，估计要拖到下个月才能到账。
[RESULT] final_latency: 704 ms  [PASS vs <1500ms]
[RESULT] CER: 13.73%  [FAIL vs <10%]
```

Exit codes:
- 0: 两项 metric 都 PASS
- 1: 至少一项 FAIL（仍然返回了 transcript）
- 2: 配置或音频格式错
- 3: 鉴权错（401/403）→ 看下方 Troubleshoot
- 4: 连接错（含 400 "resource not allowed"）
- 5: 超时
- 6: 协议错
- 7: 流结束没收到 final

## Troubleshoot

**`403 requested resource not granted`** — API Key 没有绑「豆包流式语音识别模型 2.0」。
去 [火山控制台 → 服务接入](https://console.volcengine.com/speech/) 给该 Key 绑定 `volc.seedasr.sauc.duration`。

**`400 resourceId ... is not allowed`** — Resource ID 字符串不在白名单。常见原因是误用了
1.0 的 `volc.bigasr.sauc.duration` 但订阅是 2.0（或反过来）。`sami_client.SAMIStreamingClient`
构造时显式传 `resource_id` 可覆盖默认值。

**`401`** — VOLC_API_KEY 拼错 / 过期 / 用了旧版 AppID+AccessToken。

## 已知限制

1. CER 13.73% 不达 10% 阈值——主因是 ITN（数字规范化）把"百分之十五"→"15%"，以及
   测试音频有细微听写差异（"主要是" → "是"）。架构层面已验证打通，CER 调优放到
   产品阶段（关 `enable_itn` 或在 `metrics.normalize` 加 ITN 等价规则）。
2. 单条 fixture 长度 15s，未压力测试更长音频 / 连续多 session。
3. PoC 不接 mic，只读 WAV。

## 隐私

PoC scratch only. 不把音频写盘，不把 API Key 写日志。
不要 import 进 production 路径——`sami_client.py` 后续迁移到
`gateway/api/asr_proxy.py` 时再走 review（含「不持久化原声」校验）。
