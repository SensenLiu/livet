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

### 必须（V1 上线前）— 简化版（v0.2 合并到 2 个 vendor）

| 服务 | 注册入口 | 用途 | 状态 |
|---|---|---|---|
| **DeepSeek** | https://platform.deepseek.com | 主 LLM | ✅ 已配 (gateway/.env.example) |
| **火山方舟 / 豆包** | https://console.volcengine.com/ark | 兜底 LLM (Pro-32k) | ✅ 已配 (gateway/.env.example) |
| **火山引擎 语音技术** | https://console.volcengine.com/speech/ | **ASR + TTS 都用它**(SAMI 流式 + 语音合成大模型) | ⏳ 待申请 AK/SK |
| **Sentry**（可选） | https://sentry.io | 错误监控 | 可后置 |

> **v0.2 决策（2026-05-03）**：原计划讯飞 + 阿里 + 火山三个供应商兜底，
> 但 MVP 阶段过度设计。已合并为豆包/火山一家：1 个控制台 / 1 套 AK/SK /
> 1 张账单 / 1 套 SDK。第二供应商（讯飞）仅当 V0.5+ 实测豆包成功率 < 95%
> 才加。

### 备用（V0.5+ 才考虑，本阶段不申请）

- 讯飞实时语音转写（如果豆包 ASR 在生产中暴露问题）

### 申请到 key 后

把所有 key 填到 `gateway/.env`（**不要**提交到 git，`.gitignore` 已忽略）：

```bash
cd gateway
cp .env.example .env
$EDITOR .env  # 填 VOLC_AK_ID / VOLC_SK / VOLC_ASR_APP_ID / VOLC_TTS_APP_ID
```

### Startup credit（可选，如有时间）

DeepSeek + 豆包都有面向初创团队的额度返还计划。
准备一份「项目简介 200 字 + 预估月用量」的资料，1-2 天能搞定。

---

## 2. Android 开发环境 — **已选 A：本机装 Android Studio**（2026-05-03）

### ✅ 选项 A：本机装 Android Studio

- 装 [Android Studio Iguana 2023.2.1+](https://developer.android.com/studio)
- 自动装 Android SDK（target 34）
- 升级 JDK 到 17（`sudo apt install openjdk-17-jdk` 或下载 OpenJDK 17 archive）
- 优点：本仓库 + 真机调试一站式
- 耗时：2-3 小时（含下载）

### 安装步骤（执行）

```bash
# JDK 17（如未装）
sudo apt update
sudo apt install -y openjdk-17-jdk
sudo update-alternatives --config java   # 选 java 17

# Android Studio (manual download)
# 1) 浏览器开 https://developer.android.com/studio
# 2) 下载 Linux 64-bit .tar.gz (~1.2GB)
# 3) 解压: tar -xzf android-studio-*.tar.gz -C ~/
# 4) 启动: ~/android-studio/bin/studio.sh
# 5) 首启走 Setup Wizard, 装 SDK 34 + Build Tools + Platform Tools (含 adb)
# 6) ~/.bashrc 加: export ANDROID_HOME=$HOME/Android/Sdk
#                  export PATH=$PATH:$ANDROID_HOME/platform-tools
```

装完后验证：

```bash
adb version       # 应该有输出
echo $ANDROID_HOME  # 应该非空
```

### 备用选项（已不选，仅留参考）

- 选项 B：另一台带 Android Studio 的机器（如 Mac）—— 不选，要双机切换
- 选项 C：Linux KVM Android emulator —— 不选，模拟器无法验证 ROM 杀进程行为

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

## 4. 4 个待拍板项 — 已拍板（2026-05-03）

| # | 项 | 决定 |
|---|---|---|
| Q-A | 商业 OCR 预算（S1 看病用）| **不花** — 用免费 Tesseract，准确率约 60%。S1 体验受影响但能用，后续如必要再升级 |
| Q-B | 律师 review 隐私协议预算 | **不花** — 自己用 ChatGPT 起草，承担应用商店审核风险（备选：找朋友圈律师朋友帮看一遍） |
| Q-C | 海外（Google Play）阶段 0 是否同步 | **不上** — 阶段 0 仅 i18n 友好（代码上预留），阶段 1 末视情况启动 |
| Q-D | 12 周硬目标 vs 16 周弹性 | **±30% 弹性** — 按 12 周推进但允许实际 12-16 周完成 |

### 这些决策的下游影响

- **Q-A 用 Tesseract**：S1 处方 OCR 加 fallback 机制（OCR 错误时引导用户手动补充关键药名/剂量）。production design 需改 §4.1 增加"手动补全"UI。
- **Q-B 自起草协议**：上架前 30 分钟读一遍隐私协议，对照 6 大 ROM 应用商店各家"隐私协议"模板要求微调。任何高风险条款（如 24h 监听）双倍小心措辞。
- **Q-C 阶段 0 不出海**：所有 prompts/scenario-* 短期内中文优先；i18n key 框架仍保留以便后期补 en-US.json。
- **Q-D ±30% 弹性**：12 周计划写死的"W12 上线"实际允许到 W14-16，但每周 gate 指标不松。

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

## 6. GitHub 仓库 — **已建立**（2026-05-03）

仓库地址：https://github.com/SensenLiu/livet
- ✅ git init + main 分支
- ✅ remote origin = git@github.com:SensenLiu/livet.git
- ✅ 已 push commit `ca82954`（67 文件 / 8829 行）
- ✅ git config user.email = `1105803409@qq.com` (local repo only)
- ✅ CI 已配置 5 个 job（push 后自动跑）

后续推送：

```bash
git status  # check
git add -p  # selective add
git commit -m "feat: ..."
git push
```

**别忘了**：`.env` / `*.db` / `node_modules` / `.venv` 都已在 `.gitignore`。
但每次推送前手动 `git status` 一眼，避免 secrets 漏出。

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
