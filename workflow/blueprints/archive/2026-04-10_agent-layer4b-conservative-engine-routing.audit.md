# Audit Log: Agent Layer 4B — Conservative Engine Routing

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §5.5 (Layer 4 拆分) + 用户指导（metadata-first, conservative）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4B-01 | Advisor 只给建议，不自动执行 | 用户 2026-04-10 指导 |
| L4B-02 | 显式 metadata/hint 优先，缺失时才 heuristics | 用户 2026-04-10 指导 |
| L4B-03 | 需要定义最小 routing metadata carrier | 用户 2026-04-10 指导：当前 rule inventory 无 engine 信息 |
| L4B-04 | 不碰文档提取，不碰多引擎执行闭环 | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4B-05 | EngineRoutingHint 是 agent 层数据结构，不改 kernel | 零 kernel 改动原则 |
| L4B-06 | 利用 RuleSpec.tags 的 "engine:<name>" 约定做零改动路由 | tags 存在于 agent 层 RuleSpec；注意：runtime session rule inventory（`include_spec=true`）不返回 tags，所以 tag-based routing 只覆盖调用方手里的 RuleSpec，不覆盖 list_rules() 回来的现有 inventory |
| L4B-07 | support_kind → engine 映射用于一致性检查 | 四个 support_kind 值已有稳定映射 |
| L4B-08 | register_and_evaluate_rule_with_routing 不替换 Layer 4A 方法 | 增量而非替换；Layer 4A 方法用于确定性 native 场景 |
| L4B-09 | 非 native engine + ephemeral rule → EvaluateOutcome(status="skipped") | ephemeral 仅 native 可消费；不假装可执行 |
| L4B-10 | NL 语言线索分析留给 Layer 5+ | v1 蓝图 §12 的 CUES 词表不在 Layer 4B 范围 |

## 2026-04-10 — 实现前收口修订 (5 处)

### 修订来源

用户 code review 发现 4 处 P1 + 1 处 P2。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4B-11 | **冻结** 非 native route 下不注册 ephemeral | ephemeral 仅 native 可消费；注册后返回 skipped 是无用状态污染 |
| L4B-12 | 修正 support_kind 映射到真实值 (native_binding_v1 等) + engine_no_witness_v1 → None | 旧值不存在于当前 runtime；会导致 check_consistency 全量误判 |
| L4B-13 | 删除 condition_weights → problog heuristic | condition_weights 是 certainty metadata，不是概率语义；会系统性误导 |
| L4B-14 | recommend_for_evaluate v1 收窄为：显式 mode / ruleref→native / 默认 native | temporal/probabilistic 结构分析缺少稳定的 where IR tag 定义，不可实现 |
| L4B-15 | 明确 tag-based routing 只覆盖 agent-side RuleSpec，不覆盖 runtime inventory | runtime include_spec=true 不返回 tags；audit 旧表述高估了覆盖面 |
| L4B-16 | 返回合同统一：`tuple[RegisterResult|RegisterError|None, EvaluateOutcome, EngineRoutingHint]`；non-native 分支第一项为 None，不返回 preview | 消除 3-tuple 类型不一致和 preview 承诺冲突 |
| L4B-17 | 验收标准第 7 条追加"不注册 ephemeral / session state 不污染 / list_ephemeral 不含" | 防止实现回退到旧语义 |

### 合同对齐验证

确认以下已实现合同在 Layer 4B 中正确引用：
- `RuleSpec.tags: list[str] | None` (rules.py) ✓
- `RuleSpec.condition_weights: dict | None` (rules.py) ✓
- `EvaluateResult.mode: str` (evaluate.py) ✓
- `CandidateSummary.support_kind: str` (kg_read.py) ✓
- `EvaluateOutcome(status="skipped")` (rules.py) ✓
- `RegisterResult / RegisterError` (rules.py) ✓
- `ReadReviewOrchestrator.register_and_evaluate_rule()` (orchestrator.py) ✓

### Engine metadata 现状审计

| 数据点 | 当前状态 | Layer 4B 方案 |
|--------|---------|-------------|
| Rule inventory engine 字段 | 不存在 | agent 层 EngineRoutingHint carrier |
| RuleSpec engine hint | 不存在 | +routing_hint optional field |
| Derivation mode | 内嵌 derivation dict | advisor 从 dict 提取/推断 |
| Tag-based routing | 无约定 | 新增 "engine:<name>" tag 约定 |
| support_kind → engine | 已有映射 | 复用做一致性检查 |
