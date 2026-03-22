# Task Blueprint: Engine Partial Witness — Audit/Static Surface

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-20_engine-partial-witness-adapter-contract.md](./2026-03-20_engine-partial-witness-adapter-contract.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-20_engine-partial-witness-audit-static-surface.audit.md](./2026-03-20_engine-partial-witness-audit-static-surface.audit.md)

## 1. Problem

Souffle partial witness 已通过 `support_kind="souffle_witness_v1"` 落地到 runtime live surface：`explain(kind="candidate")` 和 `explain-tree(kind="candidate")` 都已经接受 witness-bearing engine support。

但 audit/static 仍停在旧 gate：

- `AuditQuery.get_candidate_evidence_tree(...)` 只接受 `support_kind == "native_binding_v1"`
- 对 degraded kind 走 `build_degraded_candidate_evidence_tree(...)`
- 对 `souffle_witness_v1` 直接抛 `AuditQueryError`

由于 `audit.dto` 和 `audit.static_ui` 都委托 `AuditQuery.get_candidate_evidence_tree(...)`，这个单点 gate 让整个 audit/static surface 继续落后于 runtime。

本蓝图只解决这一处消费层 gap：让 audit/static 与 runtime 一样接受 witness-bearing support kind。

## 2. Goals

- 放通 audit candidate evidence tree 对 witness-bearing support kind 的消费
- 保持 `audit.dto` / `audit.static_ui` 继续复用现有 query 结果，不新增平行逻辑
- 不改变现有 tree node shape、summary、narrative 或 static rendering contract
- 为 `souffle_witness_v1` 增加至少一条 audit/static 回归测试

## 3. Non-goals

- 不重开 Souffle adapter / runtime witness capture contract
- 不修改 `candidate_evidence_tree` 的 node taxonomy
- 不扩展 audit/static 到 ProbLog 或其他 degraded engine kind
- 不新增 DTO 字段
- 不修改 audit package artifact 文件格式

## 4. Current Context

- runtime 已接受 `_WITNESS_BEARING_SUPPORT_KINDS`
- `AuditQuery.get_candidate_evidence_tree(...)` 当前仍硬编码 `support_kind == "native_binding_v1"`
- `audit.dto` 的 tree/summary/narrative surface 全部委托 query
- `static_ui` 通过 dto/query 渲染 candidate evidence page，本身没有单独的 witness-bearing gate

因此当前 gap 是一个明确的 query-layer gate，而不是多处分叉实现。

## 5. Proposed Shape

### 5.1 Scope Freeze

first-round 只改一件事：

- 将 `AuditQuery.get_candidate_evidence_tree(...)` 从 `support_kind == "native_binding_v1"` 放宽为 `support_kind in _WITNESS_BEARING_SUPPORT_KINDS`

degraded kind 的分支保持不变：

- `support_kind in _DEGRADED_SUPPORT_KINDS` 继续走 `build_degraded_candidate_evidence_tree(...)`

其他非 witness-bearing / 非 degraded kind 继续报错。

### 5.2 DTO And Static Reuse

本轮不在 `audit.dto` 或 `audit.static_ui` 增加新的支路。

冻结结论：

- `dto.py` 继续只调用 `query.get_candidate_evidence_tree(...)` / summary / narrative
- `static_ui.py` 继续只消费既有 DTO / query 结果
- 放通 query gate 后，DTO/static 自动承接 `souffle_witness_v1`

### 5.3 No New Contract Surface

本轮不新增：

- 新 node kind
- 新 DTO 字段
- 新 summary / narrative shape
- 新 static template section

也就是说，`souffle_witness_v1` 在 audit/static 上继续复用既有 witness-bearing candidate tree shape，与 runtime 保持同构。

### 5.4 Docs Sync

模块 docs 需要把这条行为从“runtime-only / audit-static deferred”改成：

- runtime + audit + static 均接受 `souffle_witness_v1`
- ProbLog 和其他 degraded engine 仍保持原状

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `souffle_witness_v1` 继续复用 witness-bearing `candidate_evidence_tree`
  - degraded kind 继续复用 `degraded_support` tree shape
  - DTO/static 不新增专用 engine 分支
- 明确不做的内容：
  - 不支持 ProbLog witness parity
  - 不新增 audit NL surface
  - 不改 `support_artifacts.jsonl` 结构
- 兼容性约束：
  - native `native_binding_v1` 行为不变
  - legacy `"none"` / `engine_no_witness_v1` degraded 行为不变

## 7. Acceptance

- [x] `AuditQuery.get_candidate_evidence_tree(...)` 接受 `_WITNESS_BEARING_SUPPORT_KINDS`
- [x] `souffle_witness_v1` 在 audit DTO / static page 上无需新增支路即可工作
- [x] degraded kind 行为无回归
- [x] 受影响模块 docs 已同步
- [x] blueprint outcome 已填写并归档

## 8. Implementation Plan

1. 更新 `audit/query.py` 的 witness-bearing gate，保持 degraded fallback 不变
2. 补一条 `souffle_witness_v1` 的 audit/static targeted regression
3. 更新 `service/docs/03_runtime_queries_views.md` 与 `audit/docs/01_overview.md`
4. 回填 outcome / audit，标记 `implemented` 并归档

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/audit/docs/01_overview.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `AuditQuery.get_candidate_evidence_tree(...)` 现已与 runtime 一样接受 `_WITNESS_BEARING_SUPPORT_KINDS`
  - `souffle_witness_v1` 通过既有 query → dto → static 链路进入 audit/static surface
  - 没有新增 node kind、DTO 字段或 static template 分支
- 与 blueprint 不同的地方：
  - 无实质偏离；实现与 scoped freeze 一致
- 为什么会有这些调整：
  - 不适用
- 归档说明：
  - 本蓝图为窄 implementation slice，已完成并归档到 `docs/blueprints/archive/`
