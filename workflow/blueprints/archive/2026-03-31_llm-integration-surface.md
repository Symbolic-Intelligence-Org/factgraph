# llm-integration-surface

- Status: implemented
- Created: 2026-03-31
- Parent: (none; top-level)

## 1. Problem

Explain surface（`explain_runtime_steps` / `explain_runtime_narrative` / `explain_runtime_nl`）和 rule authoring surface（`compile_authoring_rule_v1` / `rules_v1`）已经有完整基础，但距离 LLM 模块可用的状态还有四个缺口：

| ID | 缺口 | 影响集成模式 |
|----|------|------------|
| G1 | `rule_apply` 步骤缺少规则标签 | explain-only + agentic |
| G2 | 无 `asrt_id → candidate_id` 反向查找 | explain-only（对话增强） |
| G3 | 无 why-not（失败候选反事实解释） | 高级分析，延后 |
| G4 | LLM 无法在 session 内动态注册规则 | agentic |

没有上层文档管理这四个缺口的优先级、依赖关系和完成标准，子蓝图会各自为战，整体"LLM-ready"状态无人把关。

## 2. Goal

定义并追踪两个集成里程碑：

**Milestone A — explain-only LLM ready**

LLM 可以消费 explain-steps 并产出有意义的自然语言解释，包含：
- 规则名称（`rule_apply.detail.rule_ref_ids`）
- 条件满足链（`fact_check` → `rule_apply` → `conclusion` 序列）
- 数据来源（`fact_check.detail.fact_meta.source`）

**Milestone B — agentic LLM ready**

LLM 可以完成"生成规则 → 注册 → 评估 → 观察 explain → 迭代"闭环，包含：
- Milestone A 的全部能力
- Session 内 ephemeral rule 注册和清除
- `POST /sessions/{id}/ephemeral-rules` → evaluate → explain-steps 端到端可用

G2（反向查找）是 Milestone B 的可选增强：提升对话问答体验，但不是 agentic 闭环的硬依赖。

## 3. Non-Goals

- **G3（why-not）不在当前迭代**：需要评估侧 partial-binding carrier，风险/收益比最差。等 LLM NL 合成层建立后再评估价值。
- 不定义 LLM 模块本身的实现（提示词工程、对话管理等）
- 不实现跨 session 的 ephemeral rule 持久化
- 不改变现有 FS rule 注册/版本控制机制

## 4. Current Context

### 四缺口代码调研结论（2026-03-31）

**G1 — rule_apply 缺少规则标签**
- 根因：`rule_ref_section` 在 `_candidate_evidence_tree_steps.py` 被标记为 `_TRANSPARENT_KINDS`，`rule_ref_id` 在 steps 构建阶段被丢弃
- 修复路径：在树构建阶段（`_candidate_evidence_tree.py`）把 `rule_ref_ids` 注入到 `support_section` 节点，steps traversal 直接读取
- 可行性：高；风险：低；变更 ~55 LOC / 3 文件

**G2 — 反向查找 asrt_id → candidates**
- 根因：Store 只有 `candidate_id → support_digest` 正向索引，无反向路径
- 修复路径（Option A）：在 `_remember_support_artifact()` 注入点维护内存字典 `_asrt_witness_to_candidates`
- 限定：仅 session 内有效（当前架构 SupportArtifact sidecar readback，但 candidate_id → support_digest 跳不进 sidecar）
- 可行性：高；风险：低-中；变更 ~70 LOC / 2 文件

**G3 — why-not**
- 根因：评估器只返回成功 candidates，无 partial-binding carrier；`non_fact_check` 节点已有 schema 定义但未连通
- 修复成本：~250 LOC / 5 文件，需改评估核心
- **结论：延后**

**G4 — ephemeral rule authoring**
- 根因：`RuntimeSession` 无规则存储，每次 evaluate 从 FS 冷建 `RuleRegistry()`
- 修复路径：`RuntimeSession.ephemeral_rules: list[RuleSpec]`，`_apply_ephemeral_rules()` 在 evaluate 时 merge
- `compile_authoring_rule_v1()` + `RuleRegistry` 已有完整基础，顺着架构做
- 可行性：高；风险：低；变更 ~165 LOC / 2 文件

### 当前已有能力（可直接接 LLM）

- ✅ `explain_runtime_steps()` — 结构化步骤列表
- ✅ `explain_runtime_narrative()` — NL 段落（source、confidence、entity）
- ✅ `explain_runtime_nl()` — 完整 NL 文本
- ✅ `compile_authoring_rule_v1()` + validate endpoint
- ✅ `rule_apply.detail.rule_ref_ids` + named rule_apply descriptions（G1 已关闭）
- ⚠️ 无 asrt → candidate 反查（G2 补后增强）
- ❌ 无 ephemeral rule（G4 补后解锁 agentic）

## 5. Child Blueprints

| ID | Blueprint | 状态 | 里程碑依赖 |
|----|-----------|------|----------|
| G1 | `2026-03-31_rule-label-in-steps.md` | implemented (archived) | Milestone A（已关闭） |
| G2 | *(待建)* | — | Milestone B（可选增强） |
| G3 | *(延后，不建)* | — | 未来迭代 |
| G4 | `2026-03-31_ephemeral-rule-authoring.md` | implemented (archived) | Milestone B（硬依赖，已关闭） |

## 6. Implementation Plan

```
Phase 1（当前迭代）
  G1 → rule-label-in-steps      实施 → archive

Phase 2（agentic LLM 集成前）
  G4 → ephemeral-rule-authoring  实施 → archive

Phase 3（可选，对话体验增强）
  G2 → (blueprint TBD)           按需决定

Phase 4（未来，高成本）
  G3 → why-not                   独立评估，不纳入当前规划
```

## 7. Acceptance Criteria

**Milestone A**
- [x] MA-1：`explain_runtime_steps()` 返回的每个 `rule_apply` 步骤中，`detail.rule_ref_ids` 非空（当 SupportArtifact 有 rule_refs 时）
- [x] MA-2：`description` 字段包含规则 ID（`"Rule expert-has-recent-pub@v1: N condition(s) met"`）
- [x] MA-3：native / souffle 路径覆盖，ProbLog / PyReason 不受影响

**Milestone B**
- [x] MB-1：`POST /sessions/{id}/ephemeral-rules` 接受合法 DTO，返回 `{"status": "registered"}`
- [x] MB-2：注册后调用 `run_runtime_rule` / `evaluate_runtime_derivation`，ephemeral rule 参与推导
- [x] MB-3：evaluate → accept → `explain_runtime_steps` 端到端产出包含 ephemeral rule 名称的步骤
- [x] MB-4：`DELETE /sessions/{id}/ephemeral-rules` 后，ephemeral rules 不再参与推导
- [x] MB-5：全量测试 green（所有现有路径零回归；`unittest discover` 731 tests）

## 8. Outcome

任务完成后填写：

- Milestone A 完成日期：2026-03-31（G1 closed）
- Milestone B 完成日期：2026-03-31（G4 closed）
- 与 blueprint 不同的地方：
  - G2 保持为可选增强，没有单独起步，不阻塞母蓝图收口
  - G4 测试落地时补了比原骨架更完整的 end-to-end 覆盖（含 `evaluate -> accept -> explain-steps`）
- 为什么会有这些调整：
  - 当前目标是判定 explain-only / agentic LLM 是否 ready，而不是把所有增强项一并做完
  - MB-3 是 agentic 闭环的关键证据，必须有真实行为测试
- 归档说明：
  - G1 / G4 子蓝图均已 implemented + archived
  - G2 保留为未来对话增强项；G3 继续延后
  - 母蓝图已完成当前定义的两个里程碑，可归档
