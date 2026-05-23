# PoC-1 fixtures

## sample_zh.wav

| 字段 | 值 |
|---|---|
| 来源 | 自录（创始人本人） |
| 录音设备 | 本机麦克风（Ubuntu / ALSA arecord 直录） |
| 录音环境 | 室内 |
| 内容主题 | S2 谈话场景模拟（季度回款讨论） |
| 处理后格式 | 16kHz / 16-bit / mono PCM WAV |
| 处理后时长 | 15.000s |
| 录制命令 | `arecord -f S16_LE -r 16000 -c 1 -d 15 fixtures/sample_zh.wav` |
| Git 状态 | wav 文件被根 `.gitignore` 的 `*.wav` 规则忽略，仅 GT 文本与本 README 入库 |

如需更换 fixture，更新本表后 commit。

## sample_zh.txt

对应 `sample_zh.wav` 的 GT 转录文本（按实际朗读内容，含口误/换词若有）。UTF-8 无 BOM 无尾换行。
