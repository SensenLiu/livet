# 评估集模板（Eval Set Template）

> 通用评估集结构, 用于度量 LiveT 4 个 MVP 场景包 + 通用 prompt 的质量
> 适用 prompt: scenario-S{1,2,5,8} / memory-extraction / hint-timing
> 阶段 0 Gate 阈值定义见 `10-product-design.md` 第 6 章

---

## 评估集文件命名

| 文件 | 用途 |
|---|---|
| `eval-S1.md` | S1 看病管家评估集 |
| `eval-S2.md` | S2 重要谈话评估集 |
| `eval-S5.md` | S5 情绪急救评估集 |
| `eval-S8.md` | S8 日复盘评估集 |
| `eval-memory.md` | 跨场景记忆抽取评估集（v0.2 单独建, v0.1 复用 S1-S8）|
| `eval-hint-timing.md` | "何时提示"评估集（v0.2 单独建, v0.1 复用 S2 中的 hint case）|

---

## 单条评估对结构

每条评估对是一个 YAML block:

```yaml
- id: S2-eval-001              # 唯一 ID, 格式: 场景-eval-序号
  scenario: S2                  # 场景包编号
  eval_target: hint_timing      # 评估目标: hint_timing / memory_extraction / summary / fallback
  category: 讨价博弈            # 评估子类, 见各场景的 category 列表
  difficulty: medium            # easy / medium / hard / edge

  input:                        # 完整输入 (按对应 prompt 的输入 schema)
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
        role: B 公司项目负责人
        last_topics: ["报价 80 万", "对方关注预算"]
    transcript_chunk:
      - {speaker: "对方", text: "你们这个 100 万的方案,比预期高了 20%."}
      - {speaker: "用户", text: "嗯, 这个我们再聊一下..."}

  expected:                     # 期望输出 (人工标注)
    decision: hint
    priority: high
    channel_recommendation: earphone+screen
    hint_text_one_liner_pattern: "他在试探.*别急着让步|强调价值|不要直接降价"
    extracted:                  # 如果场景结束时也评估 memory extraction
      open_loops:
        - title_pattern: "降价|报价|价值博弈"
      person_updates:
        p_zhangzong:
          关注点+: ["预算"]

  scoring_rubric:               # 评分标准 (用于自动 eval pipeline)
    decision_must_match: true       # decision 字段必须完全匹配
    priority_tolerance: 0           # priority 容差: 0=必须匹配; 1=允许 ±1 级 (high<-->mid)
    text_match_method: regex        # regex / semantic / exact
    text_match_threshold: 0.7       # 如果是 semantic, 阈值
    extraction_required_keys:       # memory extraction 必须命中的 key
      - "open_loops"
      - "person_updates"
    extraction_optional_keys: []

  notes: "经典讨价场景. 容易被误判为'低优先级背景信息', 必须捕捉到."
  added_at: "2026-05-02"
  added_by: "AI agent (initial design)"
  last_passed: null
  last_failed: null
  prompt_version_passing: []
```

---

## 评估维度详细定义

### 1. 提示准确率 (hint_accuracy)

```
准确提示数 = sum(eval where eval.expected.decision==hint AND output.decision==hint AND text_match==pass)
总提示数 = sum(eval where output.decision==hint)
准确率 = 准确提示数 / 总提示数
```

阶段 0 Gate: ≥ 70%

### 2. 提示恼人率 (annoyance_rate)

来源: 用户在真实使用中标记 "无用/烦" 的提示数 / 总提示数

```
annoyance_rate = thumbs_down_count / total_hint_count
```

阶段 0 Gate: ≤ 15%

注意: 这个指标**不来自 eval set**, 来自真实用户反馈. 但可以用 eval set 中标记 `expected.decision=skip` 而 prompt 输出 `decision=hint` 的 case 模拟"误打扰".

### 3. 提示召回率 (hint_recall)

```
应提示但漏 = sum(eval where eval.expected.decision==hint AND output.decision==skip)
漏报率 = 应提示但漏 / sum(eval.expected.decision==hint)
```

阶段 0 Gate: 漏报率 ≤ 30%（即召回率 ≥ 70%）

### 4. 记忆抽取覆盖率 (memory_coverage)

```
命中关键实体数 = sum(eval where extraction_required_keys 全部命中)
应抽取关键实体总数 = sum(eval.expected.extracted)
覆盖率 = 命中 / 应抽取
```

阶段 0 Gate: ≥ 75%

### 5. 记忆抽取错误率 (memory_error_rate)

```
错误实体数 = sum(eval where extraction has hallucinated keys not in expected)
总抽取数 = sum(all extracted keys)
错误率 = 错误数 / 总数
```

阶段 0 Gate: ≤ 10%

### 6. 跨场景检索召回率 (rag_recall)

(v0.1 不评估, v0.2 引入. 需要先有跨场景的 eval set)

---

## eval pipeline (本地脚本)

```
[ load all eval-*.md ]
       ↓
[ 解析 YAML block ]
       ↓
[ 对每个 eval, 调用对应 prompt + LLM ]
       ↓
[ 对比 output vs expected ]
       ↓
[ 计算各维度指标 ]
       ↓
[ 输出: eval-report-{date}.md ]
       ↓
[ Diff 上次结果, 标 regression / improvement ]
```

期望脚本路径（V1 实现）: `scripts/eval-runner.py`

---

## 失败 case 处理流程

```
1. eval pipeline 跑出失败 case
   ↓
2. 周一 review meeting (创始人自己跟自己开)
   ↓
3. 判断: prompt 改 / eval 改 / 两者都改
   ↓
4. 改 prompt → 版本号 +0.1 → 重跑 eval
   ↓
5. 如果是真实用户反馈触发的, 把这条 case 加到 eval set
```

---

## 真实用户 case → 评估集的转化模板

```
用户反馈: "今天那个提示太烦了, 我都已经在说话了它还提示"
           ↓
[ 找到原始 transcript chunk + memory context ]
           ↓
[ 写成 eval YAML block ]
- id: S2-eval-NNN
  category: user_speaking_protection   # 边界 case
  difficulty: edge
  input: { ...还原原始上下文... }
  expected:
    decision: skip
    reason: "用户在说话, 此时打扰会打断思路"
  notes: "来自真实用户反馈 2026-05-15"
```

---

## eval 文件规模目标

| 阶段 | 每场景评估对数 | 总数 |
|---|---|---|
| v0.1（设计期）| 4-6 | 20+ |
| v0.2（alpha 后）| 10-15 | 50+ |
| v0.5（beta 后）| 20-30 | 100+ |
| v1.0（上线 6 月）| 50+ | 250+ |

**评估对的"质量"远比"数量"重要**: 每条都应该来自真实场景或精心设计的边界 case.
