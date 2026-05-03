# Eval Set: S8 日复盘（v0.1）

> 配套 prompt: `scenario-S8-daily-recap-v0.1.md`
> 评估目标: `one_liner` / `highlights` / `open_loops` / `emotion_curve` / `soft_suggestion`
> 共 4 条 eval, 覆盖: 一句话总结 / 高光抽取 / 未决事项 / 情绪曲线

---

## eval-S8-001: 一句话总结（不评价好坏）

```yaml
- id: S8-eval-001
  scenario: S8
  eval_target: one_liner
  category: 一句话总结
  difficulty: easy

  input:
    date: "2026-05-02"
    scenarios_today:
      - id: sc_001
        scenario_pack: S2
        summary: "与张总会议, 100 万方案有阻力"
        emotion_during: [{label: "anxious", intensity_avg: 6}]
      - id: sc_002
        scenario_pack: S5
        summary: "情绪急救, 工作压力, 改善 8→5"
        emotion_during: [{label: "anxious", intensity_before: 8, intensity_after: 5}]
      - id: sc_003
        scenario_pack: S1
        summary: "妈妈心内科复诊, 新增房颤"
    open_loops_existing: []

  expected:
    one_liner_max_chars: 30
    one_liner_must_mention_2_dimensions: true
    one_liner_must_NOT_contain:
      - "你今天表现"
      - "辛苦了"
      - "加油"
      - "真棒"
      - "失败"
    one_liner_should_capture: ["谈判|张总|工作", "压力|焦虑"]

  scoring_rubric:
    char_count_max: 30
    must_be_factual_not_evaluative: true
    must_capture_main_event: true
    must_capture_emotion_state: true

  notes: "一句话必须客观+包含'今日重点+状态'. 评价性词汇=失败."
```

---

## eval-S8-002: 高光抽取（不一定开心, 但重要）

```yaml
- id: S8-eval-002
  scenario: S8
  eval_target: highlights
  category: 高光时刻
  difficulty: medium

  input:
    date: "2026-05-02"
    scenarios_today:
      - id: sc_001
        scenario_pack: S2
        importance: high
        key_points: ["100 万方案有阻力", "对方要 ROI 详细计算"]
      - id: sc_002
        scenario_pack: S5
        importance: mid
        key_points: ["grounding 改善 8→5"]
      - id: sc_003
        scenario_pack: S1
        importance: high
        key_points: ["妈妈房颤新增", "6月2日复查"]
      - id: sc_004
        scenario_pack: S2
        importance: low
        key_points: ["与小李闲聊"]

  expected:
    highlights_count: 3
    highlights_should_select_importance_high_first: true
    highlights_must_include_scenarios: ["sc_001", "sc_003"]  # 两个 high
    highlights_should_include_one_of: ["sc_002"]  # 第三个填充
    highlights_must_NOT_include: ["sc_004"]  # importance=low

  scoring_rubric:
    high_importance_must_appear: true
    low_importance_must_NOT_appear: true
    count_exact: 3

  notes: "高光不一定是'开心', 也可以是'重要进展'. 优先 importance=high."
```

---

## eval-S8-003: 未决事项排序

```yaml
- id: S8-eval-003
  scenario: S8
  eval_target: open_loops
  category: 未决事项
  difficulty: medium

  input:
    date: "2026-05-02"
    scenarios_today:
      - {id: sc_001, action_items: [{what: "周五前发详细 ROI", due: "2026-05-09"}]}
      - {id: sc_003, action_items: [{what: "6月2日带妈妈复查", due: "2026-06-02"}]}
    open_loops_existing:
      - {title: "本周末回复李姐饭局", due: "2026-05-04"}
      - {title: "下个月旅行机票", due: "2026-06-15"}
      - {title: "电费账单", due: "2026-05-15"}

  expected:
    open_loops_count_min: 3
    open_loops_count_max: 5
    open_loops_first_due_within_days: 7  # due 临近的优先
    open_loops_must_include_pattern: "李姐|周末"  # due 最近
    open_loops_should_include: ["ROI", "复查"]  # 今天新产生的且重要
    open_loops_each_must_have_due: true

  scoring_rubric:
    must_sort_by_due_proximity: true
    each_must_have_due: true

  notes: "排序规则: 临近 due > 重要性. 用户最关心的是'下周要做什么'."
```

---

## eval-S8-004: 全天高负面 + soft_suggestion

```yaml
- id: S8-eval-004
  scenario: S8
  eval_target: soft_suggestion
  category: 软建议
  difficulty: medium

  input:
    date: "2026-05-02"
    scenarios_today:
      - {scenario_pack: S5, emotion_during: [{label: "anxious", intensity_avg: 7}]}
      - {scenario_pack: S5, emotion_during: [{label: "anxious", intensity_avg: 8}]}
      - {scenario_pack: S2, emotion_during: [{label: "frustrated", intensity_avg: 6}]}
    user_recent_pattern:
      this_week_S5_count: 3
      this_week_S5_avg_intensity: 7

  expected:
    soft_suggestion_present: true
    soft_suggestion_max_chars: 40
    soft_suggestion_text_must_use_softener: ["考虑", "或许", "可以", "也许"]
    soft_suggestion_must_NOT_contain: ["必须", "应该", "需要立即", "你要"]
    soft_suggestion_type: "self_care"

  scoring_rubric:
    must_use_softening_language: true
    must_NOT_command: true
    char_count_max: 40

  notes: "本周 3 次情绪急救 = 长期压力信号, 应温柔建议. '必须减压'=失败."
```

---

## 失败 case 添加规范

S8 是用户每天能看到的报告, 文案质量直接影响用户体验. 重点关注:
- 用户标记"复盘没用"的内容 → 加为 eval, 找出 prompt 哪里没抓住重点
- 用户标记"复盘说我表现得很好" → 加为 eval, 强化"不评价"约束
- 长期负面情绪未识别 → 加为 eval, 强化 soft_suggestion 触发

特别注意: S8 的 prompt 不应"鼓励"也不应"安慰", 是中性的数据视图.
