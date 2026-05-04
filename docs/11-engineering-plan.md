# LiveT — 开发方案 v0.1

> 基于 React Native + Android 优先（兼容跨平台设计）
> 编写日期: 2026-05-02
> 适用阶段: 阶段 0 MVP（0-12 周）
> 约束: 1 个全栈工程师 + AI 编程工具 + ¥10 万预算（弹性 ±30%） + 12 周
> 配套: 产品设计方案 `docs/10-product-design.md` + `docs/prompts/*.md`

---

## 0  引言

### 0.1 已对齐的关键决策

| # | 项 | 结果 |
|---|---|---|
| 1 | 创始人技术背景 | 全栈（前后端都能上手）|
| 2 | 前端框架 | React Native |
| 3 | MVP 节奏 | 4 场景全做但浅 |
| 4 | 资源约束 | 参考，可弹性 ±30% |

### 0.2 设计原则（贯穿本文档）

1. **今天就能开始做**——不依赖未发布库或未确认的 SDK；所有选型在 2026-05 都已稳定可用
2. **AI 编程友好**——Cursor/Claude Code 生态成熟（避开冷门库导致 AI 编程低效）
3. **隐私可证伪**——CI 强制 grep 检查，任何 PR 写入音频文件的 PR 直接拒
4. **降级路径默认就绪**——每个关键技术点都有备选方案 + 切换触发条件
5. **与产品设计方案逐章对应**——本文档每章末尾标"对应产品设计 §X.Y"

### 0.3 与产品设计方案的对应关系

| 本文档章节 | 对应产品设计方案 |
|---|---|
| §1.6 SQLite + sqlite-vec | §7.1 记忆引擎 schema |
| §1.2 Silero VAD | §1.2 被动提示 + §3.2 续航 |
| §1.5 双供应商 LLM | §0.2 端为主架构 |
| §3 PoC-6 前台服务 | §11.1 Android 特色 |
| §6.2 隐私 grep CI | §8.1 永不保留原声 |
| §4 12 周计划 | §13 验证与迭代计划 |

---

## 1  技术栈最终决策（brief 2.1）

### 1.1 前端：React Native 0.7x + TypeScript + New Architecture

| 项 | 决定 | 备选 | 关键理由 |
|---|---|---|---|
| 框架 | React Native 0.74+ | RN 0.6x / Flutter / Kotlin Native | 最新稳定版 + Fabric/TurboModules + AI 编程生态最成熟 |
| 架构 | New Architecture（Fabric + TurboModules）| 旧 Bridge 架构 | 性能 + 未来主流；2026 年 RN 默认 |
| 语言 | TypeScript 5.x | JavaScript | 类型安全 + AI 编程更准确 |
| UI 库 | React Native Paper（Material 3）| NativeBase / Tamagui / 自定义 | 与产品设计 §0.2 兼容 + 维护成本最低 |
| 导航 | React Navigation 7.x | Expo Router | RN 生态主流 + 跨平台一致 |
| 状态管理 | Zustand 5.x | Redux Toolkit / Jotai | 学习成本低 + 全栈背景友好 + RN 友好 |
| 表单 | React Hook Form 7.x | Formik | 性能 + RN 兼容 |
| 网络 | Tanstack Query 5.x + axios | Apollo / SWR | REST 友好 + 自带 cache + 重试 |
| 国际化 | i18next + react-i18next | react-intl | 为 Q7 海外路线预留 |
| 测试 | Jest + React Native Testing Library | Detox | 单元 + 组件优先；E2E 等 V0.5 |

**为什么不用 Expo**：Expo 限制了 native module 的灵活性。LiveT 需要深度接 native（VAD ONNX + 前台服务 + Media Button），bare RN 控制力更强。Expo 模块按需引入即可。

**已知坑**：
- 〔需验证〕RN 0.74+ 在 Android 14+ 的前台服务 API 适配（部分库未跟上）
- 〔需验证〕Material 3 RN Paper 的字体 fallback 在 ROM 上的稳定性

→ 对应产品设计 §0.2 / §3

---

### 1.2 端侧 VAD：Silero VAD ONNX（主）+ WebRTC VAD（降级）

| 项 | 决定 |
|---|---|
| 主选 | Silero VAD v4 ONNX（精度 0.95+，1.6MB 模型）|
| 降级 | WebRTC VAD（精度 ~0.85，但极轻量）|
| 接入 | `onnxruntime-react-native` + 自写 native module（从 PCM 流喂入）|
| 推理频率 | 每 32ms 一帧 |
| 决策窗 | 滑动 500ms 平均值 → 触发"说话"事件 |

**触发降级条件**：Silero ONNX 在某些 SoC 上推理 > 80ms（高通 480/天玑 700 等中低端芯片）→ 降级为 WebRTC VAD。

**已知坑**：
- 〔需验证〕onnxruntime-react-native 在 Android 14+ + JNI 的稳定性
- 〔需验证〕国产 SoC（联发科/麒麟/紫光展锐）的 ONNX 推理性能基线

**Day-1 spike 建议**：花 2 天做 PoC-2 验证 Silero VAD 在荣耀 / 红米 / OPPO 三款主流千元机上的功耗。

→ 对应产品设计 §1.2 / §3.2

---

### 1.3 ASR：豆包/火山引擎单供应商（SAMI 实时语音识别）

> **v0.2 简化（2026-05-03）**：原计划讯飞 + 阿里 + 火山三供应商兜底，
> 但 MVP 阶段过度设计。已合并为单供应商（豆包/火山引擎）：
> 同一个控制台、同一套 AK/SK、与备用 LLM（豆包 Pro）共享 vendor。
> 故障兜底等 V0.5+ 真实数据出来再决定加哪家。

| 项 | 决定 | 关键理由 |
|---|---|---|
| 主选 | 豆包 / 火山引擎 SAMI 流式 ASR | 中文准确率 ~96-98%；与 LLM 同 vendor |
| 控制台 | https://console.volcengine.com/speech/ | AK/SK 签名（与 LLM bearer token 不同）|
| 计费 | 约 ¥3/小时 | 阶段 0 月成本约 ¥150-300 |
| 弱网降级 | 客户端 buffer + 重试 ≤ 3 次 | 见 §5 R8 |
| 二供应商 | 推迟到 V0.5+ | 仅当生产成功率 < 95% 才加讯飞 |

**为什么不用端侧 ASR (Whisper Tiny ONNX)**：
- Whisper Tiny 中文准确率 < 70%（生产不可用）
- 端侧 ASR 推理在 Android 中低端机延迟过高
- 模型尺寸 ~150MB，App 包变胖
- → V1.5 再评估（届时可能有更小更准的中文 ASR）

**已知坑**：
- 〔需验证〕豆包 SAMI WebSocket 在 4G 弱网下的稳定性
- 〔需验证〕"严格匿名"模式（不存音频）是否所有套餐都支持

→ 对应产品设计 §8.1（云端 ASR 的隐私边界）

---

### 1.4 TTS：豆包/火山引擎单供应商（语音合成大模型）

> **v0.2 简化**：原计划阿里 CosyVoice。合并到豆包 = 1 个 vendor 统一管 ASR + TTS。

| 项 | 决定 |
|---|---|
| 主选 | 豆包/火山引擎 语音合成大模型（CosyVoice 风格）|
| 默认音色 | `zh_female_qingxin_v2_mars_bigtts`（温柔不打鸡血风格）|
| 用途 | 主动询问回复（🟢 模式）+ S5 引导语音 + S8 复盘语音播报 |
| 不用 TTS 的场景 | 🟡 被动提示（永不发声朗读，只播提示音；铁律 2）|
| 提示音 | 5 个预制 .ogg 音色文件（不走 TTS）打包进 App |

**已知坑**：
- 〔需验证〕首字节延迟（< 500ms 是要求）
- 〔需验证〕"温柔不打鸡血"音色是否在豆包默认库中

→ 对应产品设计 §1.1 / §4.3 / §9.1

---

### 1.5 大模型：DeepSeek-V3（主）+ 豆包 Pro-32k（兜底）

| 模型 | 角色 | 用途 | 单价（约）|
|---|---|---|---|
| **DeepSeek-V3** | 主力 | 所有场景 prompt + memory-extraction + hint-timing | ¥0.5/百万 input tokens, ¥1.5/百万 output |
| **豆包 Pro-32k** | 兜底 | DeepSeek 不可用时切换；S1 看病用药冲突检测（豆包对中文医疗稍优）| ¥0.8/百万 input, ¥2/百万 output |
| Qwen2.5-3B 端侧 | V1.5 候选 | 端侧 hint-timing 减成本 | 端侧, 一次性 |

**路由策略（双供应商兜底）**:
```python
# gateway/llm-router.py 伪代码
async def route_llm(prompt, context):
    primary = "deepseek-v3"
    fallback = "doubao-pro-32k"
    
    # 健康检查 (10s 内 success rate)
    if health_check(primary).success_rate < 0.9:
        primary, fallback = fallback, primary
    
    try:
        return await call(primary, prompt, context, timeout=15)
    except (TimeoutError, RateLimitError, ServerError):
        return await call(fallback, prompt, context, timeout=15)
```

**成本估算**（按 Day-90 100 用户算）：
- 平均启用 5 次/月/用户 × 4 场景 = 20 次启用/用户/月
- 每次启用平均 5 分钟 = 100 分钟/月
- 每分钟约 1k input + 0.3k output token = 100k input + 30k output / 用户 / 月
- 单用户月成本 = 100k × 0.5 + 30k × 1.5 = ¥0.5 + ¥0.45 ≈ **¥1/用户/月（仅 LLM）**
- 加上 ASR/TTS：约 **¥3-4/用户/月**

100 用户阶段总成本 ~ ¥300-400/月 + ¥99 服务器 + ¥1500 AI 编程订阅 = 月度 ~¥2k；阶段 0 总 API 成本可控。

**已知坑**：
- 〔需验证〕DeepSeek-V3 在 hint-timing 这种高频低延迟场景的实际响应（要 < 800ms）
- 〔需验证〕豆包 32k context 在长场景（S2 持续 1 小时谈话）的衰减
- API 成本超预期降级（见 §5 R3）

→ 对应产品设计 §0.2 / §5（prompt 工程依赖此栈）

---

### 1.6 本地数据库：SQLite + sqlite-vec + react-native-sqlite-storage

| 项 | 决定 |
|---|---|
| 数据库 | SQLite 3.45+（系统自带）|
| 向量扩展 | sqlite-vec（轻量, 单文件, ~500KB） |
| RN 接入 | react-native-sqlite-storage（成熟）+ 自写 native module 加载 sqlite-vec |
| 路径 | `/data/data/io.livet.app/databases/livet.db`（Android 私有目录）|
| 备份策略 | 用户手动导出 JSON（设置页"导出我的数据"）|

**为什么 sqlite-vec 而不是 ObjectBox / Qdrant**：
- sqlite-vec 与 SQLite 同生命周期（一份文件管全部）
- 单文件便于"一键删除全部数据"实现（铁律 3 工程化）
- 备份/导出/迁移简单
- 无独立向量库带来的额外内存

**已知坑**：
- 〔需验证〕sqlite-vec 的 react-native native module 接入复杂度（GitHub 上未看到现成 wrapper, 可能需要自己写一个 ~200 行 C++ binding）
- 〔需验证〕sqlite-vec 在 Android 各 ABI 上的稳定性（armv7, arm64, x86_64）
- 数据库膨胀触发清理（产品设计 §7.4）

**Day-1 spike 建议**：花 1 天做 PoC-4 spike 验证 sqlite-vec 在 RN 0.74 + Android 14 上能跑通（如果不通则改用 ObjectBox 备选）。

→ 对应产品设计 §7（记忆引擎）

---

### 1.7 端侧 embedding：BGE-small-zh ONNX（384 维）

| 项 | 决定 |
|---|---|
| 模型 | BGE-small-zh-v1.5（ONNX 格式，~24MB）|
| 维度 | 384 维（不用 768 维）|
| 推理 | onnxruntime-react-native（与 Silero VAD 共用） |
| 用途 | 记忆引擎写入时的实体 embedding + RAG 检索 |
| 加载 | 首启异步加载，缓存到 cache 目录 |

**为什么 384 而不是 768**：
- 节省数据库膨胀 50%（384 个 float ≈ 1.5KB/条 vs 3KB/条）
- 384 维在中文 RAG 场景的召回率与 768 维差距 < 5%
- 端侧推理速度快 2x

**备选**：如果 BGE-small-zh ONNX 推理 > 200ms → 降级为 m3e-small（也 384 维）。

→ 对应产品设计 §7.1（记忆引擎 schema 中的 embedding 字段）

---

### 1.8 音频流处理：纯 WebSocket（不用 LiveKit）

```
[ Android 麦克风 PCM 16kHz/16bit ]
        ↓ react-native-audio-recorder-player (or 自写)
[ 端侧 VAD 过滤 ]
        ↓ 检测到人声
[ 缓冲滑动窗 (≤ 5s ring buffer) ]
        ↓ 200ms 一个 chunk
[ WebSocket → BFF → ASR 供应商 ]
        ↓ ASR 流式返回文字
[ buffer 清零 + 释放 ]
        ↓
[ 文字进入 hint-timing pipeline ]
```

**为什么不用 LiveKit**：
- LiveKit 是 WebRTC 流媒体框架，主要用于多人实时通信
- LiveT 是单向音频流（Android → 服务器），WebSocket 完全够
- LiveKit 增加部署复杂度 + 月度成本（自建或云服务）
- 完全自控更符合"端为主"哲学

**已知坑**：
- WebSocket 重连策略（弱网下断流处理）
- BFF 层是否需要做音频缓冲（避免 ASR 供应商瞬时连接抖动）

→ 对应产品设计 §8.1

---

### 1.9 BFF 网关：FastAPI ~200 行 + Redis 限流

| 项 | 决定 |
|---|---|
| 框架 | FastAPI 0.110+ |
| 部署 | 阿里云轻量服 ¥99/月（2C2G 80GB 5Mbps）|
| 进程管理 | uvicorn + systemd（不用 docker，省内存）|
| 反代 | Caddy 2.x（自动 HTTPS）|
| 限流 | Redis + slowapi |
| 监控 | 自带 /healthz + Sentry |
| 域名 | TBD（计划 livet.io 或 livet.cn）|

**模块（每个 ~30-50 行）**:

```
gateway/
├── main.py                  # FastAPI 入口
├── api/
│   ├── llm_proxy.py         # 大模型 API key 代理 + 双供应商路由
│   ├── asr_proxy.py         # ASR API 代理 (豆包/火山 单供应商)
│   ├── tts_proxy.py         # TTS API 代理 (豆包/火山 单供应商)
│   ├── subscription.py      # 微信支付/订阅校验
│   └── error_log.py         # Sentry 转发(可关)
├── core/
│   ├── rate_limit.py        # Redis 限流
│   ├── auth.py              # 设备 ID + 短期 token
│   └── routing.py           # 双供应商健康检查 + 路由
├── pyproject.toml
└── Caddyfile
```

总代码量约 200 行（不含 deps）。

**已知坑**：
- 〔需验证〕阿里云轻量服 ¥99/月套餐的网络抖动（如不稳定升级 ECS 共享通用型 ~¥160/月）
- HTTPS 证书自动续期（Caddy 自动处理）
- 流量超 100GB/月（按 100 用户估算约 50GB/月，应该够）

→ 对应产品设计 §0.2

---

### 1.10 UI / 状态 / 导航 综合

详见 §2.2 目录结构。补充：

| 维度 | 选型 |
|---|---|
| 主题 | 自定义 Material 3 主题（青蓝 + 暖灰，对应产品设计 §0.2）|
| 字体 | 系统默认（PingFang/Roboto fallback）|
| 暗色模式 | 跟随系统 |
| 动效 | 默认开（用户可关）|
| 日期/时间 | dayjs（轻量）|
| 图表 | victory-native（情绪曲线 / 复盘视图）|

---

### 1.11 监控

| 工具 | 用途 | 默认 |
|---|---|---|
| Sentry | 崩溃 + 错误日志 | 默认开（用户可关）|
| PostHog 自建 | 产品分析（场景启用次数 / 留存 / 漏斗）| 默认关，用户主动开启 |
| 网关 metrics | 自建 Prometheus + Grafana（V0.5）| 网关侧, 不涉及用户数据 |

**严格隐私约束**：
- Sentry 报错日志中**禁止**出现用户对话内容、人物姓名、医疗信息
- PostHog 默认关，开启时弹窗明示"匿名行为统计"
- 任何上传的字段都需经过 `redact_pii()` 函数

→ 对应产品设计 §8.2

---

## 2  模块划分与目录结构（brief 2.2）

### 2.1 Monorepo 根目录

```
life_crutch/
├── CLAUDE.md
├── README.md
├── docs/                              # 已有
│   ├── 00-product-strategy.md
│   ├── 01-philosophy.md
│   ├── 02-decisions-log.md
│   ├── 03-open-questions.md
│   ├── 04-next-step-brief.md
│   ├── 10-product-design.md
│   ├── 11-engineering-plan.md         # 本文档
│   ├── prompts/                       # 已有
│   └── user-research/
│
├── app/                               # RN 前端
│   ├── android/                       # Android native 工程
│   ├── ios/                           # iOS 工程（V1 不做但保留）
│   ├── src/
│   ├── e2e/
│   ├── package.json
│   └── tsconfig.json
│
├── gateway/                           # FastAPI BFF
│   ├── main.py
│   ├── api/
│   ├── core/
│   └── pyproject.toml
│
├── scripts/                           # 工具脚本
│   ├── eval-runner.py                 # 跑 prompts/eval-* 评估集
│   ├── privacy-grep-check.sh          # CI 用（隐私 grep）
│   └── android-rom-test.md            # 6 大 ROM 测试 checklist
│
├── poc/                               # 6 个 PoC 独立目录
│   ├── poc-1-asr-stream/
│   ├── poc-2-vad/
│   ├── poc-3-dual-channel-hint/
│   ├── poc-4-memory-engine/
│   ├── poc-5-bluetooth-button/
│   └── poc-6-foreground-service/
│
└── .github/                           # CI
    └── workflows/
        ├── ci.yml                     # lint + test + 隐私 grep
        └── release.yml                # apk 构建 + 上传 alpha
```

### 2.2 app/src 内部结构（细到文件级）

```
app/src/
├── App.tsx                            # 入口
├── i18n/
│   ├── zh-CN.json
│   └── en-US.json                     # Q7 海外预留
│
├── modes/                             # 三种交互模式（产品设计 §1）
│   ├── active.ts                      # 🟢 主动询问
│   ├── passive-hint.ts                # 🟡 被动提示（V1 核心）
│   └── guardian.ts                    # 🔴 守护监听（V2 占位）
│
├── scenarios/                         # 场景包（产品设计 §4）
│   ├── _base/
│   │   ├── scenario-pack.types.ts
│   │   └── scenario-runtime.ts        # 场景生命周期统一
│   ├── medical-care/                  # S1
│   │   ├── index.ts
│   │   ├── workflow.ts
│   │   └── prompts.ts                 # 引用 docs/prompts/scenario-S1...
│   ├── conversation/                  # S2
│   ├── emotion/                       # S5
│   └── daily-recap/                   # S8
│
├── core/                              # 核心引擎
│   ├── audio/
│   │   ├── recorder.ts                # 麦克风录入
│   │   ├── vad.ts                     # 端侧 VAD
│   │   ├── ring-buffer.ts             # PCM 滑动 buffer
│   │   └── shred.ts                   # 销毁原声 (隐私核心)
│   ├── asr/
│   │   ├── client.ts                  # WebSocket → BFF
│   │   └── stream-handler.ts          # 流式解码
│   ├── tts/
│   │   └── client.ts
│   ├── llm/
│   │   ├── client.ts
│   │   └── streaming.ts
│   ├── memory/                        # ⭐ 长期记忆引擎
│   │   ├── schema.sql                 # SQLite DDL
│   │   ├── db.ts                      # SQLite + sqlite-vec
│   │   ├── extractor.ts               # 调用 memory-extraction prompt
│   │   ├── retriever.ts               # 多策略 RAG
│   │   ├── embedding.ts               # BGE-small-zh ONNX
│   │   └── ttl.ts                     # 数据增长管理
│   ├── hint-timing/                   # ⭐ "何时被动提示" 算法
│   │   ├── decider.ts                 # 调用 hint-timing prompt
│   │   ├── threshold.ts               # 三级阈值 + 用户学习
│   │   └── feedback.ts                # ignore/engage 反馈
│   └── bluetooth/
│       ├── media-button.ts            # 蓝牙按键事件
│       └── connection.ts
│
├── privacy/                           # 隐私引擎
│   ├── local-store.ts                 # 端侧 SQLite 入口
│   ├── audio-shred.ts                 # 转写后销毁
│   ├── pii-redact.ts                  # 上送字段脱敏
│   └── data-controls.ts               # 用户控制面板逻辑
│
├── ui/
│   ├── screens/
│   │   ├── HomeScreen.tsx
│   │   ├── ScenarioStartScreen.tsx
│   │   ├── ScenarioActiveScreen.tsx
│   │   ├── RecapScreen.tsx
│   │   ├── SettingsScreen.tsx
│   │   ├── BluetoothPairingScreen.tsx
│   │   └── OnboardingScreen.tsx       # 60 秒引导
│   ├── components/
│   │   ├── HintBubble.tsx
│   │   ├── TranscriptCard.tsx
│   │   ├── MemoryDrawer.tsx
│   │   ├── PrivacyStatusBar.tsx
│   │   └── ScenarioCard.tsx
│   └── theme/
│       └── material3.ts
│
├── stores/                            # Zustand
│   ├── scenario.store.ts
│   ├── memory.store.ts
│   ├── settings.store.ts
│   └── privacy.store.ts
│
├── android-native/                    # Android 特色
│   ├── ForegroundService.kt           # 前台服务
│   ├── BatteryOptimizationHelper.kt   # 电池白名单引导
│   ├── RomAdapter.kt                  # 6 大 ROM 适配
│   └── MediaButtonReceiver.kt         # 蓝牙按键
│
└── utils/
    ├── time.ts
    ├── logger.ts
    └── constants.ts
```

### 2.3 gateway/ 内部

见 §1.9 已展开。

### 2.4 模块依赖关系图

```mermaid
graph LR
    UI[UI Layer<br/>screens + components] --> Stores[Zustand Stores]
    UI --> Modes[Modes<br/>active/passive/guardian]
    Modes --> Scenarios[Scenario Packs<br/>S1/S2/S5/S8]
    Scenarios --> Core[Core Engines]
    
    Core --> Audio[audio: recorder/vad/buffer/shred]
    Core --> ASR[asr]
    Core --> LLM[llm]
    Core --> Memory[memory: db/extractor/retriever]
    Core --> HintTiming[hint-timing]
    
    Memory --> Privacy[privacy/local-store]
    Audio --> Privacy
    ASR --> Gateway[BFF Gateway]
    LLM --> Gateway
    
    Gateway -.-> External[DeepSeek + 豆包/火山 (LLM/ASR/TTS)]
    Gateway --> Sentry
    
    AndroidNative[Android Native:<br/>ForegroundService<br/>BatteryHelper<br/>MediaButton] --> Audio
    AndroidNative --> Modes
```

### 2.5 关键 TypeScript 类型定义

```typescript
// app/src/scenarios/_base/scenario-pack.types.ts
export type ScenarioPackId = 'S1' | 'S2' | 'S5' | 'S8';
export type Mode = 'active' | 'passive_hint' | 'guardian';

export interface ScenarioPack {
  id: ScenarioPackId;
  name: string;
  emoji: string;
  startConditions: StartCondition[];
  listenRules: ListenRules;
  hintRules: HintRules;
  memoryExtraction: MemoryExtractionConfig;
  recapTemplate: RecapTemplate;
}

export interface StartCondition {
  type: 'manual_button' | 'bluetooth_long_press' | 'geo_fence';
  config?: Record<string, unknown>;
}

export interface ListenRules {
  audio: boolean;
  imageCapture: boolean;
  voiceInput: boolean;
}

export interface HintRules {
  promptFile: string;  // 'prompts/scenario-S1-medical-care-v0.1.md'
  hintPriorityThreshold: number;  // 0.65
}

// app/src/core/memory/types.ts
export interface MemoryEntry {
  id: string;
  scenarioId?: string;
  type: 'event' | 'person' | 'emotion' | 'open_loop' | 'preference';
  data: Record<string, unknown>;
  embedding?: Float32Array;  // 384-dim
  importance: 'high' | 'mid' | 'low';
  createdAt: Date;
  ttlAt?: Date;  // null = 永久
}

export interface RagResult {
  entries: MemoryEntry[];
  scoreBreakdown: { keyword: number; vector: number; recency: number };
}

// app/src/core/hint-timing/types.ts
export interface HintDecision {
  decision: 'hint' | 'skip';
  priority?: 'high' | 'mid' | 'low';
  channel?: 'earphone+screen' | 'screen_only' | 'earphone_only';
  text?: string;
  rationale?: string;
  internalScore: number;
}

// app/src/privacy/types.ts
export type PrivacyState = 'safe' | 'recording' | 'processing' | 'error';

export interface PrivacyControls {
  exportAll: () => Promise<string>;  // returns JSON path
  deleteAll: () => Promise<void>;
  selectiveForget: (filter: ForgetFilter) => Promise<void>;
  getDataStats: () => Promise<DataStats>;
}
```

→ 对应产品设计 §3 / §4 / §7 / §8

---

## 3  6 个关键 PoC 路径（brief 2.3）

每个 PoC 独立目录（`poc/poc-N-*/`），不进主仓直到验证完成。

### PoC-1: Android 流式音频 → 云端 ASR → 文本

| 维度 | 内容 |
|---|---|
| 目标 | 验证 Android 麦克风 PCM → WebSocket → 豆包 ASR → 文字 完整链路 |
| 不验证 | LLM、提示、UI 美观 |
| 依赖库 | react-native-audio-recorder-player + 豆包 SAMI 流式 ASR (火山引擎) |
| 关键代码片段 | 见下 |
| 验证标准 | ① 流式延迟 < 500ms；② 中文准确率 > 90%；③ 无音频文件落盘 |
| 预估耗时 | 3 人日 |
| 失败 fallback | V0.5+ 加讯飞作为第二供应商；spike 阶段失败先 debug 豆包 SAMI 接入 |

```typescript
// poc-1 关键片段
const recorder = new AudioRecorderPlayer();
const ws = new WebSocket('wss://gateway.livet.io/asr/stream');

await recorder.startRecorder('memory://buffer', {
  AudioEncodingAndroid: AudioEncoder.AAC_LC,
  AudioSourceAndroid: AudioSource.MIC,
  SampleRate: 16000,
});

recorder.addRecordBackListener((e) => {
  const pcmChunk = e.recordSecs;  // 实际中拿 PCM bytes
  ws.send(pcmChunk);
});

ws.onmessage = (e) => {
  const transcript = JSON.parse(e.data).text;
  console.log('ASR:', transcript);
};
```

---

### PoC-2: 端侧 VAD（Silero ONNX）+ 智能唤醒

| 维度 | 内容 |
|---|---|
| 目标 | Silero VAD 在 Android 千元机的功耗实测 + 误激活率 |
| 依赖库 | onnxruntime-react-native + 自写 native module |
| 验证标准 | ① 推理延迟 < 80ms；② 1 小时纯 VAD 功耗 < 5%；③ 误激活率 < 5% |
| 测试机型 | 红米 Note 12（联发科）/ 荣耀 X40（高通）/ OPPO A1（联发科）|
| 预估耗时 | 5 人日（包含 native module 集成）|
| 失败 fallback | 降级 WebRTC VAD；最差情况：MVP 不做 VAD，全部靠用户主动按按钮 |

**关键挑战**：onnxruntime-react-native 没有现成 VAD wrapper，需要自己写 ~150 行 TS + native module 桥接。

---

### PoC-3: 双通道被动提示（耳机声 + 浮窗字幕同步）

| 维度 | 内容 |
|---|---|
| 目标 | 验证耳机短"叮"声 + 浮窗字幕同时触发，延迟 < 100ms |
| 依赖库 | react-native-sound + react-native-floating-bubble + react-native-permissions |
| 验证标准 | ① 提示音播放延迟 < 50ms；② 浮窗显示延迟 < 100ms；③ 双通道同步差 < 100ms |
| Android 权限 | SYSTEM_ALERT_WINDOW（浮窗，需用户在系统设置开）|
| 预估耗时 | 3 人日 |
| 失败 fallback | 降级为通知栏字幕（不需 SYSTEM_ALERT_WINDOW）|

---

### PoC-4: Memory Engine 最小闭环（S5 场景）

| 维度 | 内容 |
|---|---|
| 目标 | sqlite-vec 在 RN 跑通 + 写入 + 检索完整闭环 |
| 依赖库 | react-native-sqlite-storage + sqlite-vec native module（自写）+ BGE-small-zh ONNX |
| 验证标准 | ① 写入 1000 条耗时 < 1s；② 向量检索 top-5 耗时 < 50ms；③ 端侧 embedding 推理 < 100ms |
| 预估耗时 | 6 人日（最大 PoC，含 native module）|
| 失败 fallback | sqlite-vec 不通 → 改 ObjectBox（4 人日切换）|

**Day-1 spike 优先做 PoC-4**：因为 sqlite-vec 是最大未知数，先 spike 1 天看是否可行；不通早降级到 ObjectBox。

---

### PoC-5: Android 蓝牙耳机 Media Button + 三种按键映射

| 维度 | 内容 |
|---|---|
| 目标 | 蓝牙耳机短按 / 长按 / 双击事件接入 + 触发不同模式 |
| 依赖库 | react-native-music-control / 自写 Media Button Receiver |
| 验证标准 | ① 主流耳机（AirPods / 华为 / 小米 / 索尼）都能识别；② 长按 1s 区别于短按 |
| 测试耳机 | 至少 4 款（不同品牌）|
| 预估耗时 | 2 人日 |
| 失败 fallback | 仅识别短按（双击/长按延后）|

---

### PoC-6: Android 前台服务 + 通知栏字幕

| 维度 | 内容 |
|---|---|
| 目标 | Foreground Service 持续运行 12 小时不被 6 大 ROM 杀掉 |
| 依赖库 | 自写 Kotlin（不用 RN 库）+ 通知栏 RemoteViews |
| 验证标准 | ① 红米 / 荣耀 / OPPO / vivo / 魅族 / 原生 Android 都能稳定运行 12h；② 用户引导后白名单率 > 90% |
| 预估耗时 | 7 人日（最复杂 PoC，含 6 ROM 适配）|
| 失败 fallback | 部分 ROM 用 WorkManager 周期唤醒（间断模式）；最差：用户必须保持 App 前台 |

**这是最关键的 PoC**——做不通就违反"被动提示"灵魂。**Day-1 第二个 spike 的优先级**。

---

## 4  阶段 0 - 12 周开发计划（brief 2.4）

按"4 场景全做但浅"节奏。每周表格：目标 / 交付物 / 风险 / 降级 / 验证 gate。

### W1-W2 基建周（2 weeks）

| 项 | 内容 |
|---|---|
| 目标 | 项目骨架跑通 + 主动询问 demo + 关键 PoC（PoC-6 + PoC-1） |
| 交付物 | ① RN 0.74 + Android 14 工程跑通 hello world ② BFF FastAPI 部署 ③ DeepSeek API 主动询问 demo（一句话问一句话答）④ PoC-6 前台服务在 3 个 ROM 上活 12h ⑤ PoC-1 流式 ASR demo |
| 风险 | RN New Architecture 在 Android 14+ 的 native module 兼容问题 |
| 降级 | 退回 RN Bridge 旧架构（损失性能但稳定）|
| 验证 gate | 主动询问 demo 能在 3 款机型上正常工作 |

### W3-W4 核心引擎周（2 weeks）

| 项 | 内容 |
|---|---|
| 目标 | Memory Engine + Privacy Engine 完整可用（PoC-4 升级为生产代码）|
| 交付物 | ① SQLite + sqlite-vec 接入 ② BGE-small-zh embedding 端侧推理 ③ memory-extraction 通用 prompt 闭环 ④ 流式 PCM → 销毁的隐私实现 ⑤ 隐私控制面板 UI（导出/删除）|
| 风险 | sqlite-vec 在 RN 不稳定 |
| 降级 | 切 ObjectBox（4 人日）|
| 验证 gate | 写 100 条记忆 + RAG 检索召回率 > 75% |

### W5-W6 S5 + S8（2 weeks）

| 项 | 内容 |
|---|---|
| 目标 | 最简单两个场景跑通（不需要持续 ASR）|
| 交付物 | ① S5 情绪急救：grounding 引导 + 单次问询 + emergency 触发 ② S8 日复盘：22:00 自动触发 + 报告生成 ③ 复盘 UI（一日总结） |
| 风险 | S8 自动触发在国产 ROM 上被杀 |
| 降级 | 用户手动触发"今日复盘"按钮 |
| 验证 gate | S5 5 用户测试恼人率 < 30% / S8 自动触发存活率 > 80% |

### W7-W8 S1 + S2（2 weeks）

| 项 | 内容 |
|---|---|
| 目标 | 看病和重要谈话基础版（含 PoC-3 双通道提示）|
| 交付物 | ① S1：拍照 OCR + 口述医嘱 + 子女转发卡 ② S2：持续 ASR + hint-timing 接入 + 谈话纪要 ③ PoC-3 双通道提示融入 S2 |
| 风险 | OCR 处方笔迹准确率低 / hint-timing 误打扰多 |
| 降级 | OCR 不通用商业 OCR 改用免费 Tesseract（精度差）|
| 验证 gate | S2 提示恼人率 < 25%（5 用户内测）|

### W9 被动提示完整闭环（1 week）

| 项 | 内容 |
|---|---|
| 目标 | hint-timing 上线 + PoC-2 VAD 集成 |
| 交付物 | ① 端侧 VAD + 流式 ASR + LLM 判断 + 提示输出 完整链路 ② 三级优先级 + 阈值动态调整（user_engagement_history）③ 提示历史 + 用户反馈 UI |
| 风险 | VAD 误激活让续航暴跌 |
| 降级 | 关闭端侧 VAD，改"用户开始/暂停手动控制"模式 |
| 验证 gate | 1 小时被动提示场景续航 > 8% 电量消耗 |

### W10 评估集 + 内部 dogfooding（1 week）

| 项 | 内容 |
|---|---|
| 目标 | 创始人 + 8 人共创群 4 周 dogfooding 启动 |
| 交付物 | ① 部署 eval-runner.py 自动跑 prompts/eval-* ② 创始人内部 daily build 安装 ③ 8 人共创群发邀请 + 内测群组建 ④ 反馈收集 issue 模板 |
| 风险 | 共创群反馈不积极 |
| 降级 | 减少到 3 个核心朋友重度 dogfooding |
| 验证 gate | 8 人都成功安装 + 至少 5 人首周启用 ≥ 5 次 |

### W11 上架准备（1 week）

| 项 | 内容 |
|---|---|
| 目标 | Android 应用商店素材 + 隐私协议 + 6 大 ROM 适配测试 |
| 交付物 | ① 应用商店截图（5 张）+ 视频（30s）+ 描述（300 字）② 隐私协议 + 用户协议（律师 review）③ 6 大 ROM 实机测试报告 ④ 备案（如需）|
| 风险 | 应用商店审核拒（"持续监听"敏感）|
| 降级 | 改成"按需启动" + 加强隐私文案；或先去 Google Play 海外渠道 |
| 验证 gate | 至少 1 个商店审核通过（小米 / 华为 / OPPO 之一）|

### W12 Android 上线（1 week）

| 项 | 内容 |
|---|---|
| 目标 | 上架 + 监控部署 + 第一批 30 亲友 alpha |
| 交付物 | ① 应用商店上线（小米 / 华为 / OPPO / vivo / 应用宝）② Sentry 监控配置 ③ 30 亲友邀请发出 + 首批反馈渠道 ④ Day-90 决策表 |
| 风险 | 上架后崩溃率高 / 数据库 corrupt |
| 降级 | 紧急回滚版本 + Sentry 报警 |
| 验证 gate | 30 亲友中 ≥ 20 人成功安装 + 首日崩溃率 < 5% |

### 12 周总投入估算

| 项 | 估算 |
|---|---|
| 时间 | 12 周 × 5 天 × 8 小时 = 480 小时（个人）|
| AI 编程订阅 | Cursor Pro $20 + Claude Code $20 = ~¥300/月 × 3 = ¥900 |
| API 试用费 | DeepSeek + 豆包 startup credit + 讯飞试用包 = ~¥0-3000 |
| 服务器 | 阿里云轻量服 ¥99 × 3 + 域名 ¥55/年 = ¥352 |
| 应用商店 | 小米 ¥0 / 华为 ¥0 / OPPO ¥0 / vivo ¥0 / 苹果 $99（V1 不上）= ¥0-700 |
| 备案/法律 | 律师协议 review ¥3000-5000 + ICP 备案 0 |
| 营销试投 | ¥3-5 万 |
| **合计** | **¥4-7 万**（不含创始人时间机会成本）|

→ 资源约束 ±30% 弹性下，可控。

→ 对应产品设计 §13.1 / §13.4

---

## 5  关键风险与降级方案（brief 2.5）

### R1 端侧 VAD 误激活率太高

- **触发**：alpha 测试 VAD 误激活率 > 15%
- **降级 1**：调整 Silero 阈值 + 加"白名单声纹"（用户首启录 5s 自己声音）
- **降级 2**：关闭 VAD 改"持续 ASR + 服务器侧 VAD"（耗流量但更准）
- **降级 3**：完全关闭 VAD，改"用户主动按开始/暂停"
- **不可降级到**：违反铁律 3 把音频上传分析

### R2 Android 前台服务被 ROM 杀掉

- **触发**：6 大 ROM 测试中任一存活率 < 80%
- **降级 1**：增强电池白名单引导（动画 + 一键跳转系统设置）
- **降级 2**：用 WorkManager 周期唤醒（每 15min 一次，间断模式）
- **降级 3**：要求用户保持 App 前台（牺牲"被动"特性）
- **极端降级**：该 ROM 用户专属版（限制功能但稳定）

### R3 大模型 API 成本超预期

- **触发**：单用户月 LLM 成本 > ¥10
- **降级 1**：hint-timing 缓存 + 去重（同 transcript chunk 不重复判断）
- **降级 2**：hint-timing 改用 DeepSeek-V3 mini 版（更便宜）
- **降级 3**：S2 持续监听场景的 LLM 调用频率从每 10s 降到每 30s
- **极端降级**：每月免费启用次数从 50 改 30

### R4 hint-timing 算法做不出可用版本

- **触发**：alpha 测试恼人率 > 30%（持续 4 周不能改善）
- **诊断**：是 prompt 问题（先调）还是模型能力问题（升级到豆包/GPT-4 兜底）
- **降级 1**：降低三级阈值到只剩"high"（减少打扰量）
- **降级 2**：关闭主动提示，改"用户问 → AI 答"模式（退回主动询问，违反"被动"灵魂）
- **极端降级**：暂停被动提示模式上线，重做 prompt + 评估集（推迟 4 周）

### R5 sqlite-vec 在 RN 不稳定

- **触发**：W3 PoC-4 spike 失败 / 上线后崩溃率高
- **降级 1**：切 ObjectBox（vector index 内置，4 人日切换）
- **降级 2**：切 LanceDB-RN（更新但稳定性〔需验证〕）
- **极端降级**：放弃向量检索，纯关键词 RAG（召回率下降但能跑）

### R6 Android 应用商店审核拒了"持续监听"

- **触发**：W11 提交后被拒
- **降级 1**：删除"持续监听"措辞，改"实时识别"+ 强化"按需启用"叙事
- **降级 2**：一审被拒后人工申诉 + 提供合规说明
- **降级 3**：仅上 1-2 个比较宽松的商店（如应用宝）+ 自有渠道下载
- **极端降级**：先海外（Google Play）+ 国内自有渠道（小红书 + 微信）

### R7 创始人个人无法持续投入

- **触发**：连续 2 周进度 < 50% 计划
- **降级 1**：暂停非核心特性（如 S8 复盘），保 S1/S2/S5 上线
- **降级 2**：找 1 个外包工程师补齐 PoC-2/PoC-6（最 native 的 2 个 PoC）
- **降级 3**：12 周延后到 16 周（资源约束允许 ±30%）
- **极端降级**：上线"主动询问 + S5 + S8" 简化版，被动提示推迟到阶段 1

### R8 流式 ASR 在弱网下不可用

- **触发**：alpha 测试 4G/弱 wifi 下 ASR 中断率 > 20%
- **降级 1**：客户端缓冲 + 重连机制（最多重试 3 次）
- **降级 2**：检测到弱网自动切端侧 ASR（precision 降但能用）
- **降级 3**：弱网下提示用户"建议切到稳定网络再启动场景"
- **极端降级**：关闭流式 ASR 在弱网，仅留主动询问

→ 对应产品设计 §12（不确定项清单）

---

## 6  测试策略（brief 2.6）

### 6.1 评估集

```bash
# 复用 prompts/eval-*.md
python scripts/eval-runner.py \
  --prompt-dir docs/prompts \
  --scenarios S1,S2,S5,S8 \
  --report eval-report-$(date +%Y%m%d).md
```

每周一跑一次，diff 上次结果。

### 6.2 单元测试

| 重点 | 内容 | 覆盖率目标 |
|---|---|---|
| **隐私 grep CI** | `grep -rE "(\.wav|\.pcm|\.mp3|fs\.write.*audio|writeFileSync.*pcm)" app/src/` 必须为空 | 100%（任一命中即拒 PR）|
| 业务逻辑核心 | hint-timing decider / memory-engine extractor / scenario-runtime | ≥ 70% |
| 隐私引擎 | audio-shred / pii-redact / data-controls | ≥ 90% |
| 通用工具 | time / logger / constants | ≥ 80% |
| UI 组件 | 仅快照测试关键组件 | smoke |

### 6.3 集成测试

| 链路 | 验证 |
|---|---|
| 主动询问 | 用户问 → ASR → LLM → TTS 全链路 < 3s |
| 被动提示 | VAD → 流式 ASR → hint-timing → 双通道提示 < 1.5s |
| Memory Engine | 场景结束 → 抽取 → 写入 → 下次启动检索 |
| Privacy | PCM buffer → ASR → 销毁，CI 验证无落盘 |

### 6.4 内部 dogfooding（创始人 + 8 人共创群 4 周）

W10-W12 滚动进行：
- 创始人每天用至少 1 次（自己当用户）
- 8 人共创群每周提交 ≥ 1 个反馈
- 反馈分类：bug / 体验问题 / 哲学层异议 / 商业建议

### 6.5 Alpha（30 个亲友 2 周）

W12-W14（含上线后 2 周）:
- 招募 30 个亲友（覆盖中老年/职场/学生）
- 引导安装 + 首启 60 秒 + 自由使用 2 周
- 关键指标：首启完成率 / 30 天留存 / NPS / 恼人率
- 1v1 访谈 5-8 人收集质化反馈

### 6.6 Beta（小红书招募 100 人 2 周）

W15+:
- 小红书 + 即刻发"招内测官"，按 7 个场景类型分流
- 100 人发 30 天免费试用 + ¥0 预付占位
- 关键指标：付费转化率 / 单用户启用次数 / 单元成本

### 6.7 上线后监控指标（Day-90 决策依据）

| 指标 | Gate | 失败信号 |
|---|---|---|
| 30 天留存 | ≥ 35% | < 15% 严重失败 |
| 单用户启用次数 | ≥ 5 次/月 | < 2 次大问题 |
| 付费用户数 | ≥ 100 | < 30 大问题 |
| 恼人率 | ≤ 15% | > 30% 重做 hint-timing |
| 单用户成本 | ≤ ¥5/月 | > ¥10/月 财务不可持续 |
| 崩溃率 | ≤ 0.5% | > 2% 紧急 |
| 6 大 ROM 存活率 | ≥ 90% | < 70% 重做前台服务 |

→ 对应产品设计 §13.1 / brief 阶段 0 Gate 指标

---

## 7  Day-1 立刻做（接下来 72 小时）

### Day 1（今天）

```bash
# 1. 仓库初始化（30 min）
cd /home/lss/life_crutch
npx react-native@latest init app --template react-native-template-typescript
mv app/* /home/lss/life_crutch/app/
cd app && yarn add zustand @react-navigation/native react-native-paper

# 2. gateway 骨架（1 hour）
mkdir -p gateway && cd gateway
poetry init --name livet-gateway
poetry add fastapi uvicorn slowapi redis httpx
# 写 main.py + Caddyfile

# 3. 申请 API key（半天）
# - DeepSeek: platform.deepseek.com → API keys
# - 豆包: console.volcengine.com/ark
# - 讯飞: console.xfyun.cn → 实时语音转写
# - Sentry: sentry.io → New project (React Native)
```

### Day 2

```bash
# PoC-6 spike（最关键 PoC）
mkdir -p poc/poc-6-foreground-service
cd poc/poc-6-foreground-service
# 写 Android Kotlin 前台服务 hello-world
# 在 1 台机型（你自己的）测试 12h 存活
```

### Day 3

```bash
# PoC-4 spike（第二关键, 决定 sqlite-vec 是否可行）
mkdir -p poc/poc-4-memory-engine
# 验证 react-native-sqlite-storage + sqlite-vec native module 在 Android 14 跑通
# 失败则切 ObjectBox 备选
```

### Day 4-7

按 W1-W2 计划，全速推进基建周。

---

## 8  关键设计假设与不确定项

### 〔需验证〕清单（按 alpha 验证窗口排序）

#### Day-1 优先级（决定整个栈是否可行）
1. sqlite-vec 在 RN 0.74 + Android 14 的稳定性（PoC-4 spike）
2. Foreground Service 在 6 大 ROM 的存活率（PoC-6 spike）

#### Day-30 优先级
3. Silero VAD 在国产 SoC 的功耗与误激活率
4. 豆包 SAMI 流式 ASR 在 4G 弱网的稳定性
5. DeepSeek-V3 在 hint-timing 高频低延迟场景的响应时间
6. BGE-small-zh ONNX 在中低端机的推理延迟

#### Day-60 优先级（需要真实用户数据）
7. hint-timing 三级阈值能否压恼人率到 < 15%
8. Memory engine schema 是否够用（events/persons 是否需要拆得更细）
9. Android 应用商店对"持续监听"App 的审核态度

#### Day-90 优先级
10. 单用户 LLM 成本能否压到 < ¥3/月
11. 6 大 ROM 存活率能否稳定 > 90%

### 哪些技术决策建议先做 spike（独立实验, 不进主仓）

按优先级：
1. **sqlite-vec 在 RN（1 天）**：决定 memory engine 整个栈
2. **Foreground Service 在 6 ROM（2 天）**：决定被动提示是否可行
3. **Silero VAD 功耗（1 天）**：决定 VAD 路径是否走得通
4. **豆包 SAMI ASR 流式（半天）**：决定 ASR 选型

如果以上 4 个 spike 中任一失败，整个开发计划要重新评估。**强烈建议在 W1 第 1-3 天集中做完这 4 个 spike**，再正式开始 W1-W2 基建周。

### 已拍板的决策（2026-05-03）

- ✅ **商业 OCR**：不买，用免费 Tesseract（精度约 60%；S1 加"手动补全"UI 兜底）
- ✅ **律师协议**：不花钱外包，自己用 ChatGPT 起草后让朋友圈律师朋友帮看一遍
- ✅ **海外路线**：阶段 0 不出海（仅 i18n 友好），阶段 1 末再启动
- ✅ **资源弹性**：按 12 周计划推进，允许 ±30% 弹性（实际 12-16 周）
- ✅ **ASR/TTS 供应商**：合并到豆包/火山一家（v0.2 简化）

### 仍待拍板

- *待用户拍板*：是否申请 DeepSeek/豆包 startup credit（需提交资料 + 等待）

---

## 9  v0.2 触发条件 + 与下一阶段衔接

### v0.2 触发

任一发生即触发开发方案 v0.2:
- 4 个 Day-1 spike 中任一失败 → 技术栈调整 → 章节 1 + 4 重写
- W1-W2 基建周完成后真实开发体感与计划差距大 → 12 周计划重排
- alpha 30 用户后核心反馈与产品设计假设差距大 → 产品 + 开发联动 v0.2

### 与阶段 1（3-9 个月）衔接

- 阶段 0 Gate 通过（≥ 100 付费 + 30 天留存 ≥ 35% + NPS ≥ 30）
- 阶段 1 工作内容：补 S3/S4/S6 + V1.5 半自动场景识别 + 跨场景检索 + 子女联动 H5
- 阶段 1 开始前，本方案需要 v0.5 update（含阶段 0 学到的真实数据）

---

## 10  附录：成本估算明细 + Day-30 / Day-90 判断指标

### 成本估算（细化版）

#### 一次性

| 项 | 估算 |
|---|---|
| 公司主体（个体户/公司）| ¥0-2000 |
| 域名（.io 或 .cn 各注 1 个）| ¥80-300/年 |
| ICP 备案 | ¥0（自行办理）|
| 应用商店上架（小米/华为/OPPO/vivo）| ¥0 |
| 应用宝上架 | ¥0 |
| 律师审核协议（隐私 + 用户 + 数据训练承诺）| ¥3000-5000 |
| Logo / UI kit | ¥0-2000（自做或 freelance）|
| 营销试投（短视频拍摄 + 投流）| ¥30000-50000 |
| **一次性合计** | **¥3-7 万** |

#### 月度（阶段 0 期间）

| 项 | 估算 |
|---|---|
| 阿里云轻量服 | ¥99/月 |
| Sentry（free tier）| ¥0 |
| AI 编程订阅（Cursor + Claude Code）| ~¥300/月 |
| API 成本（开发 + 自测期）| ~¥500-1500/月 |
| 阶段 0 上线后用户 API 成本（100 用户）| ~¥300-500/月 |
| **月度合计** | **¥1.2-2.5k/月** |

12 周月度合计：¥3.5-7.5k

**总投入估算**：¥7-15 万（一次性 + 月度 × 3）

→ 与 brief 估算（¥8-12 万）一致, 弹性 ±30% 内可控。

### Day-30 决策表

| 维度 | Go 信号 | No-Go 信号 |
|---|---|---|
| 5 用户访谈 | ≥ 3 用户主动想要 + 至少 1 场景集中 | 无强需求, 礼貌点头多 |
| Coze 伪 MVP 测试 | 用户启用 ≥ 1 次/天 | < 1 次/天 |
| 4 个 spike 完成度 | 4/4 通过 | 任一失败 |
| 自我感知 | 创始人自己想用 | 自己都不想用 |

### Day-90 决策表

| 维度 | Go 信号 | No-Go 信号 |
|---|---|---|
| 付费用户 | ≥ 100 | < 30 |
| 30 天留存 | ≥ 35% | < 15% |
| 单场景 NPS | ≥ 1 个场景 NPS ≥ 30 | 全部 < 0 |
| 启用频次 | ≥ 5 次/月 | < 2 次 |
| 单用户成本 | ≤ ¥5/月 | > ¥10/月 |
| 恼人率 | ≤ 15% | > 30% |

阶段 0 Gate 通过 → 进入阶段 1（融种子轮 or 继续 bootstrap）
阶段 0 Gate 失败 → 复盘 + 重新评估产品 + 商业模式

---

**文档版本**：v0.1（2026-05-02）
**作者**：AI agent（Claude）
**待用户决策项**：startup credit 申请（其余已拍板：OCR=Tesseract / 律师协议=自起草 / 海外=阶段 0 不上 / 资源=±30% 弹性 / ASR+TTS=合并到豆包）
**下一版触发**：4 个 Day-1 spike 完成 或 W2 基建周结束
