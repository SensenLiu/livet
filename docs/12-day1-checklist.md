# Day-1 Onboarding Checklist（B 线）

> 这份文档说明**接下来 72 小时你（创始人）需要亲自做的事**。
>
> 我（AI agent）已完成的"A 线"工作见 README 顶部 "Repo state" 段落 +
> `docs/11-engineering-plan.md §7`。所有代码已 commit 到本地 git。
>
> 下面 6 件事按优先级排列。**前 3 件是阻塞**（不做后面的 PoC 跑不了）；
> 后 3 件可以并行。

---

## 1. 申请 API key（约 0.5–1 天）

### 必须（V1 上线前）

| 服务 | 注册入口 | 用途 | 备注 |
|---|---|---|---|
| **DeepSeek** | https://platform.deepseek.com | 主 LLM | 充值 ¥50 即可 |
| **火山方舟（豆包）** | https://console.volcengine.com/ark | 兜底 LLM | 注意 endpoint_id 与 api_key 是两个东西 |
| **讯飞实时语音转写** | https://console.xfyun.cn | 主 ASR | 实时语音转写 SDK，注意是按时长计费 |
| **阿里云 CosyVoice** | https://help.aliyun.com/zh/dashscope/ | 主 TTS | DashScope 平台，开通"语音合成-CosyVoice" |
| **Sentry**（可选） | https://sentry.io | 错误监控 | 免费层够阶段 0 用 |

### 备用（V1 中后期）

| 服务 | 注册入口 |
|---|---|
| 阿里云智能语音交互 | https://nls-portal.console.aliyun.com |
| 火山引擎 ASR | https://www.volcengine.com/product/voice-tech |

### 申请到 key 后

把所有 key 填到 `gateway/.env`（**不要**提交到 git，`.gitignore` 已忽略）：

```bash
cd gateway
cp .env.example .env
$EDITOR .env  # 填 DEEPSEEK_API_KEY 等
```

### Startup credit（可选，如有时间）

DeepSeek + 豆包都有面向初创团队的额度返还计划（参考开发方案 §8.3 *待拍板*）。
准备一份「项目简介 200 字 + 预估月用量」的资料，1-2 天能搞定。

---

## 2. 决定 Android 开发环境方案

你这台 Linux ThinkStation 上**还没装** Android SDK / Android Studio / adb。
三个选项，按推荐度排序：

### 选项 A：本机装 Android Studio（推荐）

- 装 [Android Studio Iguana 2023.2.1+](https://developer.android.com/studio)
- 自动装 Android SDK（target 34）
- 升级 JDK 到 17（`sudo apt install openjdk-17-jdk` 或下载 OpenJDK 17 archive）
- 优点：本仓库 + 真机调试一站式
- 耗时：2-3 小时（含下载）

### 选项 B：另外一台带 Android Studio 的机器（如 Mac）

- 把这个仓库 push 到一个 GitHub 私仓
- 在 Mac 上 clone + 用 Android Studio 打开 `poc/poc-6-foreground-service`
- 优点：不动你 Linux 机器
- 缺点：双机切换

### 选项 C：先用 Android 模拟器跑 PoC-6（不推荐做 12h 测试）

- Linux 上可以用 KVM-accelerated Android emulator
- 但**模拟器无法验证 ROM 杀进程行为** —— 这正是 PoC-6 要测的
- 只能用作 smoke test（"代码能编译能跑起来"）

→ **强烈建议选项 A**。

---

## 3. PoC-6 真机测试（关键路径）

PoC-6 是 6 个 PoC 中**风险最高**的（30-50% 失败概率）。完整指南在
`poc/poc-6-foreground-service/README.md`。

### 最少要测的 ROM × 手机

| 优先级 | ROM | 至少几台 |
|---|---|---|
| P0 | MIUI / HyperOS（小米/红米）| 2 |
| P0 | MagicOS（荣耀）/ HarmonyOS（华为）| 2 |
| P0 | ColorOS（OPPO/Realme）| 1 |
| P0 | OriginOS（vivo/iQOO）| 1 |
| P1 | AOSP / Pixel（控制组）| 1 if available |

最少 6 台手机（你 + 朋友拼凑都行）。共创群里如有 Android 用户可以拉来当测试机。

### 流程

每台机器上：

1. 装 LiveT-PoC6（Android Studio 一键 Run，或 `./gradlew installDebug`）
2. 打开 App → 按"打开电池白名单设置"→ 按 OEM 提示完成
3. 按"启动前台服务"
4. 屏幕关闭 + 不充电（充电状态某些 ROM 不会激进杀进程，结果会偏乐观）
5. 12+ 小时后回收手机
6. `adb pull /sdcard/Android/data/io.livet.poc6/files/heartbeat.csv`
7. `python3 poc/poc-6-foreground-service/analyze_heartbeat.py heartbeat.csv`
8. 把结果加到 `poc/poc-6-foreground-service/results.md`

### 如果某台 ROM 失败

不用慌。开发方案 §5 R2 有 3 级降级方案（电池白名单引导加强 → WorkManager
间断模式 → 牺牲被动特性）。但**先试**：

- 重做电池白名单（不同 ROM 路径见 `BatteryWhitelistHelper.kt#oemAdditionalHint`）
- 关闭其他后台清理工具（如某些 ROM 的"省电卫士"）
- 重装一次

如果三次都挂，记到 results.md 的"Notes"列。

---

## 4. 4 个待拍板项（plan §8.3）

每个 1-2 句话决定即可。这些不阻塞 Day-1 执行，但 W4 之前要拍。

### Q-A: 商业 OCR 预算（S1 看病用）
- 默认假设：可花 ¥1-2k/月买专业医疗 OCR（处方笔迹）
- 不花：用免费 Tesseract，准确率约 60%（S1 体验受影响但能用）
- 你的决定：______

### Q-B: 律师 review 隐私协议预算
- 默认假设：愿意花 ¥3-5k 一次性
- 不花：自己用 ChatGPT 起草，上线风险增加（应用商店审核可能因隐私协议条款被卡）
- 你的决定：______

### Q-C: 海外（Google Play）阶段 0 是否同步
- 默认假设：阶段 0 不上，仅 i18n 友好（代码上预留）
- 上：分散精力但海外审核更宽松，可作为国内被拒的备选渠道
- 你的决定：______

### Q-D: 12 周硬目标 vs 16 周弹性
- 默认假设：按 12 周推进但允许 ±30% 弹性 → 实际 12-16 周
- 硬 12 周：更紧迫但也容易牺牲质量
- 你的决定：______

---

## 5. 环境升级（可选但推荐）

| 项 | 当前 | 推荐 | 影响 |
|---|---|---|---|
| Python | 3.8.10 | 3.11+ | gateway 提速 30%，避免 PEP 604 兼容问题 |
| JDK | 11 | 17 | RN 0.74+ 推荐版本，AGP 8 要求 |
| yarn | （未装）| corepack 启用 | RN 项目首选包管理 |
| poetry | （未装）| 可装可不装 | 已用 requirements.txt 兜底 |

**升级命令**（Ubuntu 20.04）：

```bash
# Python 3.11
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv python3.11-dev

# JDK 17
sudo apt install openjdk-17-jdk
sudo update-alternatives --config java   # 选 java 17

# yarn (via corepack)
corepack enable
corepack prepare yarn@stable --activate
```

---

## 6. GitHub 仓库（如果要）

我已经 `git init` 但还没 commit（等你 review 后决定要不要先 commit）。
如果决定建私仓：

```bash
gh repo create life-crutch --private --source=/home/lss/life_crutch --remote=origin
git add .
git commit -m "initial: docs + gateway + poc-4 + poc-6 + scripts"
git push -u origin main
```

**别忘了**：`.env` / `*.db` / `node_modules` 都已在 `.gitignore`。但每次
推送前手动 `git status` 一眼，避免 secrets 漏出。

---

## 我做完后的下一步建议

按下面顺序推进会最高效：

1. **今晚**：申请 DeepSeek key + 豆包 key（最快 30 分钟到账，决定后续 LLM 是否能跑通）
2. **明天上午**：装 Android Studio + JDK 17 + Python 3.11
3. **明天下午**：把 PoC-6 装到你自己的手机上，跑起来看 1 小时（验证代码 OK）
4. **明天晚上 → 后天上午**：发动共创群，让有 6 大 ROM 之一的朋友帮你装一台 12h 跑 PoC-6
5. **后天**：拿到至少 1-2 台机器的 12h 结果 → 决定走 sqlite-vec 路径继续 / 还是触发 §5 R2 降级

如果到 Day-3 末（72 小时后）你拿到了：
- ✅ 至少 2 个 LLM key + 1 个 ASR key
- ✅ Android Studio 跑通本仓库
- ✅ 至少 1 台真机的 PoC-6 12h 数据

那就可以正式启动 W1-W2 基建周（开发方案 §4）。

---

**最后**：如果任一环节卡住超过 4 小时，告诉我 + 我们一起 debug。不要硬扛。
