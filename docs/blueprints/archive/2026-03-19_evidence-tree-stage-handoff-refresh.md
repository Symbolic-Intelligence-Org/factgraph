# Task Blueprint: Evidence Tree Stage Handoff Refresh

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `docs/session_handoff_2026-03-19.md`
  - `docs/README.md`
  - `HANDOUT.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_runtime-traceability-evidence-tree-realignment.md](./2026-03-18_runtime-traceability-evidence-tree-realignment.md)
  - [2026-03-18_native-candidate-evidence-tree-v1.md](./2026-03-18_native-candidate-evidence-tree-v1.md)
  - [2026-03-19_native-candidate-evidence-tree-v2.md](./2026-03-19_native-candidate-evidence-tree-v2.md)
  - [session_handoff_2026-03-18.md](../../../session_handoff_2026-03-18.md)
- Audit Log:
  - [2026-03-19_evidence-tree-stage-handoff-refresh.audit.md](./2026-03-19_evidence-tree-stage-handoff-refresh.audit.md)

## 1. Problem

当前仓库已经从 cross-domain validation 阶段推进到了 `native candidate evidence tree v2`，但 handoff 入口已经失配：

- `docs/README.md` 仍指向一个不存在的 `docs/session_handoff_2026-03-18.md`
- 根目录 `HANDOUT.md` 也仍指向同一个失效路径
- 仓库里现存的长 handoff 文档是根目录的 `session_handoff_2026-03-18.md`，内容仍停在 74 tests 的 cross-domain validation stopping point，没有覆盖：
  - `native candidate evidence tree v1`
  - `native candidate evidence tree v2`
  - 当前“下一步应是 capability decision”的位置

这意味着新 agent 目前没有一个正确、单一、可发现的入口来恢复当前状态。

## 2. Goals

- 产出一份新的 canonical session handoff 文档，能让新 agent 直接从 evidence tree v2 之后的位置继续工作。
- 刷新 handoff 内容，使其准确反映：
  - 当前 capability 基线
  - 当前已完成的 evidence tree v1/v2 进度
  - 当前仍 deferred 的能力线
  - 下一步 capability decision 的候选方向与 reopening 条件
- 修正 `docs/README.md` 和根目录 `HANDOUT.md` 的 handoff 入口，使仓库只有一个可发现的 canonical handoff 目标。

## 3. Non-goals

- 不修改任何 runtime / audit / service / core contract。
- 不新增新的 capability 结论。
- 不把 handoff 文档写成新的 module truth 或 umbrella blueprint。
- 不在本轮决定 evidence tree 之后的下一条 capability line。

## 4. Current Context

- `native candidate evidence tree v1` 已归档并落地：
  - runtime `POST /queries/explain-tree`
  - audit `get_candidate_evidence_tree(candidate_id)`
  - static candidate evidence page
- `native candidate evidence tree v2` 已归档并落地：
  - sectioned tree shape
  - optional `rule_ref_section`
  - node-kind-aware nested static rendering
- 当前最近验证基线是：
  - `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`
  - `77 tests` 全通过
- 当前 active 只剩 parent blueprints；
  `candidate evidence tree v2` 完成后，下一步已经被明确收敛为新的 capability decision，而不是继续当前实现线。

## 5. Proposed Shape

- 新建 `docs/session_handoff_2026-03-19.md` 作为新的 canonical handoff。
- 文档内容至少收口这些块：
  1. 当前阶段结论
  2. 当前已完成的 evidence tree capability 基线
  3. 关键 truth 入口（parent blueprint、module docs、archive blueprints）
  4. 当前仍 deferred 的 capability lines
  5. reopening / next-decision triggers
  6. 下一位 agent 的推荐起手顺序
- `docs/README.md`
  - handoff 入口切到 `docs/session_handoff_2026-03-19.md`
- `HANDOUT.md`
  - 继续保持 thin pointer
  - 但目标切到新的 canonical handoff

## 6. Boundaries And Invariants

- handoff 文档是 session restart/reference，不替代 module docs 或 blueprint。
- 不应保留多个长期并行的 canonical handoff 入口。
- 新 handoff 必须明确说明：
  - evidence tree v2 已完成
  - 下一步是 capability decision
  - 当前尚未决定下一条 capability line
- 根目录旧 handoff 文本若继续保留，不应被重新升级为 canonical summary。

## 7. Acceptance

- [x] `docs/session_handoff_2026-03-19.md` 已写出，且能让新 agent 直接续接 evidence-tree 之后的工作
- [x] handoff 已准确反映 evidence tree v1/v2 的当前落地状态
- [x] handoff 已明确列出当前 deferred capability lines 与 reopening triggers
- [x] `docs/README.md` 已指向新的 canonical handoff
- [x] `HANDOUT.md` 已指向新的 canonical handoff，且不与其并行漂移

## 8. Implementation Plan

1. 新建本轮 doc-only blueprint 与 audit，锁定范围在 handoff refresh 与入口修正。
2. 写 `docs/session_handoff_2026-03-19.md`，把当前位置从 cross-domain validation 更新到 evidence tree v2 stopping point。
3. 更新 `docs/README.md` 和 `HANDOUT.md` 的 handoff 入口。
4. 完成 outcome，归档本蓝图。

## 9. Docs To Update

- `docs/session_handoff_2026-03-19.md`
- `docs/README.md`
- `HANDOUT.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增了 [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md) 作为新的 canonical session handoff，内容从 cross-domain validation stable stopping point 更新到了 `native candidate evidence tree v2` 之后的位置。
  - `docs/README.md` 已修正到新的 handoff 入口，不再指向缺失的 `docs/session_handoff_2026-03-18.md`。
  - 根目录 `HANDOUT.md` 仍可作为本地 thin pointer 使用，但仓库中的 durable canonical 入口现在是 `docs/session_handoff_2026-03-19.md` 与 `docs/README.md`。
- 与 blueprint 不同的地方：
  - 无实质偏差。
- 为什么会有这些调整：
  - 不适用；本切片按既定 doc-only 范围完成。
- 归档说明：
  - 本切片不涉及代码、模块真相或测试基线变更，仅用于收口新的 canonical handoff 与入口修正，因此直接归档。
  - `HANDOUT.md` 属于本地薄指针，不是本轮 durable docs 交付的判断依据。
