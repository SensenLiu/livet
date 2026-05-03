# Eval Set: S2 重要谈话（v0.1）

> 配套 prompt: `scenario-S2-conversation-v0.1.md`
> 评估目标: 主要评估 `decision (hint/skip)` + `priority` + `hint_text` + `meeting_summary`
> 共 6 条 eval, 覆盖: 讨价 / 走神 / 重复关注点 / 上下文调取 / 纪要生成 / 用户在说话(边界)

---

## eval-S2-001: 讨价博弈（关键时刻）

```yaml
- id: S2-eval-001
  scenario: S2
  eval_target: hint_timing
  category: 讨价博弈
  difficulty: medium

  input:
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
        role: B 公司项目负责人
        last_topics: ["报价 80 万", "对方关注预算"]
        person_traits:
          关注点: ["预算", "ROI", "交付周期"]
          避雷点: ["不喜欢被催促", "对画饼很警觉"]
          互动风格: "直接, 不套话"
        open_loops: ["周五前给报价单"]
      user_goal_today: "推进合作签约, 争取预算从 80 涨到 100"
    transcript_chunk:
      - {speaker: "对方", text: "你们这个 100 万的方案, 比我们预期高了 20%."}
      - {speaker: "用户", text: "嗯, 这个我们再聊一下..."}
    recent_hints_in_30s:
      - {at: "T-15s", text: "他第二次提到'预算'", priority: "low"}

  expected:
    decision: hint
    priority: high
    channel_recommendation: earphone+screen
    hint_text_pattern: "(他在试探|别急着让步|强调价值|不直接降价).{0,15}"
    hint_text_max_chars: 25
    rationale_brief_should_mention: ["试探", "议价"]

  scoring_rubric:
    decision_must_match: true
    priority_tolerance: 0
    text_match_method: regex
    text_must_NOT_contain: ["?", "！", "建议你"]

  notes: "经典讨价场景. 对方明示预期+用户回答模糊, 是关键议价节点."
```

---

## eval-S2-002: 对方走神（low priority, 耳机轻提示）

```yaml
- id: S2-eval-002
  scenario: S2
  eval_target: hint_timing
  category: 节奏信号
  difficulty: hard

  input:
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
      user_goal_today: "推进合作签约"
    transcript_chunk:
      - {speaker: "用户", text: "...所以这个方案我们预计能在 Q3 之前交付, 这块团队的能力我们有过去 3 个项目的实绩可以分享..."}
      - {speaker: "对方", text: "嗯嗯."}
    paralinguistic_signal:
      对方_看表次数_最近1分: 2
      对方_嗯嗯式回应_最近30s: 4
    recent_hints_in_30s: []

  expected:
    decision: hint
    priority: low
    channel_recommendation: earphone_only
    hint_text_pattern: "(他可能走神|快收尾|节奏可能.{0,5}过长)"

  scoring_rubric:
    decision_must_match: true
    priority_tolerance: 1
    text_match_method: regex

  notes: "用户讲太长, 对方明显走神. 应给低优先级提示, 但**不打开屏幕**(用户在说话)."
```

---

## eval-S2-003: 重复关注点（mid priority, 字幕）

```yaml
- id: S2-eval-003
  scenario: S2
  eval_target: hint_timing
  category: 重复信号
  difficulty: easy

  input:
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
        person_traits:
          关注点: ["预算", "ROI"]
    transcript_chunk:
      - {speaker: "对方", text: "我们再确认下, 这块的成本能不能再压压?"}
      - {speaker: "用户", text: "可以再聊聊."}
    recent_hints_in_30s: []
    cross_chunk_signals:
      对方_提及"预算/成本"次数_本场: 4

  expected:
    decision: hint
    priority: mid
    channel_recommendation: screen_only
    hint_text_pattern: "(第\\d+次|多次).*(预算|成本|核心|关切)"

  scoring_rubric:
    decision_must_match: true
    priority_tolerance: 0

  notes: "对方第 4 次提及预算 = 核心关切信号. 应字幕提示用户'重视'."
```

---

## eval-S2-004: 用户在说话（必须 skip）

```yaml
- id: S2-eval-004
  scenario: S2
  eval_target: hint_timing
  category: 用户保护
  difficulty: edge

  input:
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
    transcript_chunk:
      - {speaker: "用户", text: "我觉得这个事情我们还是要从用户价值的角度看, 因为如果我们..."}
    user_currently_speaking: true
    recent_hints_in_30s: []

  expected:
    decision: skip
    reason_pattern: "用户在说话|不打断"

  scoring_rubric:
    decision_must_match: true
    must_NOT_provide_hint: true

  notes: "用户在自己讲述时, 任何 hint 都是打扰. 这是硬约束."
```

---

## eval-S2-005: 上下文调取（场景启动时, 不是 hint, 是 startup info）

```yaml
- id: S2-eval-005
  scenario: S2
  eval_target: startup_context
  category: 上下文调取
  difficulty: easy

  input:
    user_action: "started_scenario_S2"
    memory_context:
      person:
        id: p_zhangzong
        name: 张总
        last_topics: ["报价 80 万", "ROI"]
        open_loops: ["周五前给报价单"]
        last_meeting: "2026-04-25"

  expected:
    startup_card_must_show:
      - "上次与张总: 2026-04-25"
      - "上次聊到: 报价 80 万 / ROI"
      - "未决: 周五前给报价单"
    startup_card_must_NOT_ask_user:
      - "你和他什么关系?"
      - "请描述一下..."
      - "你能告诉我..."

  scoring_rubric:
    must_use_memory_context: true
    must_NOT_request_user_input: true

  notes: "铁律 1 的硬验证: 启动页必须直接展示已知信息, 永不让用户重述."
```

---

## eval-S2-006: 谈话结束生成纪要

```yaml
- id: S2-eval-006
  scenario: S2
  eval_target: meeting_summary
  category: 纪要生成
  difficulty: medium

  input:
    scenario_id: sc_001
    transcript_full: |
      [09:12] 对方: 这次见面主要想了解你们的方案细节.
      [09:15] 用户: 我们这次准备的是 100 万方案, 包含...
      [09:20] 对方: 100 万比我们预期高 20%, 能不能压一下?
      [09:25] 用户: 我们可以提供更详细的 ROI 计算.
      [09:35] 对方: 好, 那我下周一给你反馈.
      [09:50] 对方: 关于交付周期, 你们能保证 Q3 完成吗?
      [09:53] 用户: 可以承诺. 我们周五前先给你详细 ROI.
    hints_history: [...]

  expected:
    key_points_count_min: 3
    key_points_must_mention_all: ["100 万", "ROI", "Q3", "周五前"]
    action_items_count_min: 2
    action_items_must_have_due: true
    action_items_must_include_pattern: "(周五.*ROI|Q3.*交付)"
    person_traits_update_should_include: "关注 ROI"
    next_meeting_hint_present: true

  scoring_rubric:
    key_points_coverage: 0.8  # 至少命中 80% 期望关键词
    action_items_have_due_required: true

  notes: "纪要必须捕捉关键时间承诺. 漏掉 due date = 实用性大打折扣."
```

---

## 失败 case 添加规范

参见 `eval-set-template.md`. 重点关注:
- 用户标记"无用/烦"的提示 → 加为 eval, expected.decision=skip
- 用户标记"应该提示但没有" → 加为 eval, expected.decision=hint
