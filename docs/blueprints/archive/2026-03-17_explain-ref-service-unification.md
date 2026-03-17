# Task Blueprint: Explain Ref Service Unification

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/queries.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_durable-artifact-storage.md](./2026-03-17_durable-artifact-storage.md)
  - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
  - [2026-03-17_candidate-id-support-backref.md](../archive/2026-03-17_candidate-id-support-backref.md)
  - [2026-03-17_artifact-sidecar-store.md](../archive/2026-03-17_artifact-sidecar-store.md)
  - [2026-03-17_sidecar-retention-gc.md](../archive/2026-03-17_sidecar-retention-gc.md)
- Audit Log:
  - [2026-03-17_explain-ref-service-unification.audit.md](./2026-03-17_explain-ref-service-unification.audit.md)

## 1. Problem

traceability / explainability 的底层 carrier 现在已经不再缺位，但 service 层仍然暴露为一组彼此分离的 explain handle 和 endpoint。

当前已经存在的 handle 包括：

- `support_digest`
  - 对应 native derivation 的 `SupportArtifact`
- `rule_run_id`
  - 对应 `RuleTraceArtifact`
- `candidate_id`
  - 第一跳：session-scoped in-memory backref（`_candidate_support_index`，不跨 session）
  - 第二跳：委托到 `support_digest` deref，此跳受 sidecar durability 覆盖
- `asrt_id`
  - 当前是 assertion identity，但 explain 入口仍然是 `(pred_id, e_ref, *val_atoms)` 风格

这些能力分别可用，但 service contract 仍然碎片化：

- `POST /queries/explain-support`
- `POST /queries/explain-rule-trace`
- `POST /queries/explain-fact`
- `/rules/run` 在 `capture_trace=true` 时返回 `rule_run_id`
- `/derivations/evaluate` 返回 `candidate_id` 与 `support_digest`

这会带来三个具体问题：

1. 调用方必须自己知道“哪种结果对应哪种 explain endpoint / handle 形状”，缺少统一入口。
2. `candidate` / `assertion` / `rule_run` 三类结果的 identity 已经存在，但 service 层没有一个统一的 explain handle 协议把它们串起来。
3. durable readback 现在已经稳定，但 service 层还不能以统一 contract 暴露“这个 handle 是否可跨 session / sidecar root 解引用”。

换句话说，explainability 的底层运行链路已经成型，但 service-facing explain protocol 还没有收口。

## 2. Goals

- 为 service 层定义统一的 `explain_ref` 协议，覆盖至少：
  - `candidate`
  - `assertion`
  - `rule_run`
- 明确现有 service explain endpoints 与统一 `explain_ref` 的映射关系，而不是立即假定必须只保留一个 endpoint。
- 明确统一协议中的最小字段集合、错误语义、以及 durable handle 语义边界。
- 比较“新增统一 explain endpoint”与“保留分端点但统一 handle contract”两类 service shape。
- 为后续实现型切片准备可收口的方向，但当前阶段先不预设最终一定是单一 explain endpoint、单一 payload schema 或 proof-tree-first。

## 3. Non-goals

- 本蓝图不重新设计 core `SupportArtifact` / `RuleTraceArtifact` carrier。
- 不在本轮扩张 `CandidateSet` schema，也不新增 core-level `proof_entry_id` 字段。
- 不在本轮定义完整 proof-tree / support-graph payload schema。
- 不在本轮解决 engine witness parity（如 `souffle` / `problog` explain witness）。
- 不在本轮实现 NL explain、shareable UI、或 graph visualization。
- 不把 service explain unification 与 audit artifact / package contract 混成一个任务。
- 不在本轮把 `judgment` / deontic result 等未来 kind 提前写进实现承诺。

## 4. Current Context

- 当前 service explain surface 已落地但分裂：
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-fact`
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-support`
  - `POST /v1/runtime/sessions/{session_id}/queries/explain-rule-trace`
  - `POST /v1/runtime/sessions/{session_id}/rules/run` + `capture_trace=true`
  - `POST /v1/runtime/sessions/{session_id}/derivations/evaluate`
- 当前 runtime/session explain DTO 现状：
  - `evaluate` 已返回 `candidate_id` / `candidate_key` / `support_digest`
  - `rules/run` 在 traced 模式下返回 `rule_run_id`
  - `explain-fact` 仍以 `pred_id` + `e_ref` (+ optional `val_atoms`) 为入口，不是 `asrt_id`
- 当前 core explain lookup 现状：
  - `Store.explain_support(support_digest)`
  - `Store.explain_rule_trace(rule_run_id)`
  - `Store.get_candidate_support_digest(candidate_id)`
  - `Store.explain_fact(pred_id, e_ref, *val_atoms)`
- 当前 durability 前置条件已经满足：
  - audit/export completeness 已完成
  - sidecar durable readback 已完成
  - sidecar retention / GC 已完成
  - 因此 `support_digest` / `rule_run_id` 不再只是短生命周期 session handle
- 当前已知 service-level gap：
  - 没有 `candidate_id -> explain` 的 service entry
  - 没有 `asrt_id -> explain` 的 direct service entry
  - 没有统一 `explain_ref` DTO
  - 没有统一 not-found / kind-mismatch / unsupported-kind 语义
- 当前相关历史蓝图：
  - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - 已证明分端点 explain surface 可以工作，但刻意没有统一协议。
  - [2026-03-17_candidate-id-support-backref.md](../archive/2026-03-17_candidate-id-support-backref.md)
    - 已在 core 层补齐 `candidate_id -> support_digest`，但尚未上到 service contract。
  - [2026-03-17_artifact-sidecar-store.md](../archive/2026-03-17_artifact-sidecar-store.md)
    - 已让 `support_digest` / `rule_run_id` 支持跨 session / shared sidecar root readback。
  - [2026-03-17_sidecar-retention-gc.md](../archive/2026-03-17_sidecar-retention-gc.md)
    - 已给 rule trace handle 补齐第一轮 retention / GC 边界，durable semantics 现在足够稳定。

## 5. Proposed Shape

本节与 §7 已一起收口到首轮可实现规格；蓝图现已进入 `scoped`。

### 5.1 Explain Ref Vocabulary

第一轮 `explain_ref` kind 集合明确收口为：

- `candidate`
- `assertion`
- `rule_run`

其中：

- `candidate`
  - 是 **session-scoped weak-durable convenience kind**
  - 第一跳解引用路径：
    - `Store.get_candidate_support_digest(candidate_id)`
    - 该映射只存在于 `_candidate_support_index`
    - 不写 sidecar，不跨 session
  - 若第一跳命中，再转发到第二跳 `support_digest` deref
    - 第二跳可受 sidecar durability 覆盖
  - 若第一跳 miss：
    - 直接视为 `not_found`
    - 不尝试 sidecar fallback，也不重跑 evaluate
- `assertion`
  - 是 **narrow single-`asrt_id` deref**
  - 第一轮不复用宽 `explain_fact(pred_id, e_ref, *val_atoms)` 语义
  - 解引用路径应为：
    - `ledger.get_claim(asrt_id)` 取得 `Claim(pred_id, e_ref, rest_terms)`
    - service-layer bridge 再结合：
      - `find_claim_args(asrt_id=...)`
      - `find_meta(asrt_id=...)`
      - `has_active_revocation(asrt_id)`
      - `find_revoker(asrt_id)`
    - 组装 narrow assertion explain payload
- `rule_run`
  - 继续以 `rule_run_id` direct deref
  - 底层委托现有 `Store.explain_rule_trace(rule_run_id)`

本轮明确 **不把 `explain-fact` 纳入 `explain_ref`**：

- `explain-fact`
  - 仍是 `(pred_id, e_ref, optional val_atoms)` 风格的 predicate/entity query
  - 不是 identity/artifact deref
  - 保持独立 endpoint，不纳入本蓝图的统一 kind 集合

最小字段集合暂按下列方向冻结：

- `kind`
- `id`

以下字段继续作为可选待比较项，而不是首轮强制字段：

- `run_id`
- `stable_key`

### 5.2 Service Shape Candidates

首轮选择 **新增统一 explain endpoint**：

```text
POST /v1/runtime/sessions/{session_id}/queries/explain
```

请求形状第一轮收口为：

```json
{
  "kind": "candidate" | "assertion" | "rule_run",
  "id": "<candidate_id | asrt_id | rule_run_id>"
}
```

约束：

- `kind` 是 load-bearing discriminator
  - 不能只靠 `id` 形状推断 kind
  - `rule_run_id` 与 `asrt_id` 都可能是 `uuid4().hex` 风格，format-identical
- 现有分端点保留为兼容 wrapper：
  - `explain-support`
  - `explain-rule-trace`
- `explain-fact` 不进入该兼容层，继续保持独立

新的统一 handler 第一轮应作为单独入口存在，例如：

- `explain_runtime_ref(...)`

旧端点若继续保留，应在内部尽量复用该统一 resolution path，而不是继续各自维护分裂逻辑。

### 5.3 Explain Payload Boundary

首轮响应形状选择 **envelope + top-level `kind` + `explain`**：

```json
{
  "ok": true,
  "meta": { ... },
  "kind": "candidate" | "assertion" | "rule_run",
  "explain": { ... }
}
```

这样做的原因是：

- 顶层 `kind` 可作为 SDK / client 的 discriminator
- 不要求消费方先深入 `explain` payload 再判断类型
- 相比 pass-through，更容易为统一错误语义和后续扩展保留稳定 envelope

per-kind `explain` payload 第一轮收口为：

- `candidate`
  - 以 `candidate_id` 为输入
  - 首先解析到 `support_digest`
  - payload 应至少包含：
    - `candidate_id`
    - `support_digest`
  - 若第一跳命中且 `support_digest` 可继续解引用，则其 explain detail 继续委托到 support explain 路径
- `assertion`
  - narrow payload
  - 应至少包含：
    - `asrt_id`
    - `pred_id`
    - `e_ref`
    - `is_active`
    - `revoker_asrt_id`（若存在）
  - 第一轮不返回宽 `active_claims[]` 风格结构
- `rule_run`
  - 继续直接返回现有 `RuleTraceArtifact` render
  - 目标是与当前 `explain-rule-trace` payload 尽量兼容

`not_found` / `kind_mismatch` / `unsupported_kind` 的错误语义留待下一轮收进 §7，但本节已明确 payload 不采用 raw pass-through，也不采用 summary/detail 双层设计。

## 6. Boundaries And Invariants

- `explain_ref` 应在 service 层定义，不反向侵入 core candidate schema。
- 当前已存在的 `support_digest` / `rule_run_id` durable semantics 必须被保留，而不是重新发明第二套 handle。
- `candidate_id` 若进入 service explain，应复用现有 backref 与 support artifact，而不是重跑 evaluate。
- `assertion` 路径若统一到 `asrt_id`，应是 service-side bridge，不是强行改写现有 core explain_fact 语义。
- 在没有单独 scope freeze 之前，不预设 proof-tree / support-graph 是首轮 payload。

## 7. Acceptance

- [x] `POST /v1/runtime/sessions/{session_id}/queries/explain` 路由已注册成功；对 `candidate` / `assertion` / `rule_run` 三种合法 kind 的请求都返回 `HTTP 200` envelope，且只允许 `ok=true` 或 `ok=false`，不得返回 `HTTP 4xx/5xx`。
- [x] `candidate` kind 的两跳行为已锁定并可验证：
  - session 内 `candidate_id` 命中 `_candidate_support_index` 时，返回 `ok=true`、顶层 `kind="candidate"`，且 `explain` 至少包含 `candidate_id` 与 `support_digest`
  - session 内 miss 时返回 `ok=false` + `runtime_explain_not_found`
  - 新 session 中对旧 `candidate_id` 的请求同样返回 `runtime_explain_not_found`，验证第一跳仍是 session-scoped
- [x] `assertion` kind 已实现 narrow single-`asrt_id` deref：
  - 有效未撤销 `asrt_id` 返回 `asrt_id` / `pred_id` / `e_ref` / `is_active=true`
  - 已撤销 `asrt_id` 返回 `is_active=false` 且带 `revoker_asrt_id`
  - 不存在的 `asrt_id` 返回 `runtime_explain_not_found`
  - 第一轮不返回宽 `active_claims[]` 风格结构
- [x] `rule_run` kind 已直接桥接到现有 `rule_run_id` explain 路径：
  - 命中时 payload 与现有 `explain-rule-trace` render 保持兼容
  - miss 时返回 `runtime_explain_not_found`
- [x] 所有统一 explain 成功响应都采用一致 envelope：
  - 顶层包含 `ok` / `meta` / `kind` / `explain`
  - 顶层 `kind` 与请求中的 `kind` 一致
- [x] `kind` 缺失或非法值走统一 shape-error 语义：
  - `kind` 缺失或值不在 `{candidate, assertion, rule_run}` 中时，返回 `HTTP 200` + `ok=false`
  - `errors[0].kind="shape"`
  - `kind="fact"` 等不支持值不得触发 `500`
- [x] 旧端点兼容性保持不变：
  - `explain-support` / `explain-rule-trace` 继续可达，并保持 `HTTP 200` envelope
  - 旧端点响应 shape 与重构前兼容，不在响应顶层新增 `kind` 字段
  - 内部可复用统一 resolution path，但响应序列化仍按旧 schema 输出
  - `explain-fact` 不受影响，DTO 和返回语义保持独立
- [x] `explain-fact` 与 `explain_ref` 的语义边界保持清晰：
  - `explain-fact` 不属于 `explain_ref` kind 集合
  - `POST /queries/explain` 不支持 `kind="fact"`，并走 shape-error 路径
  - `explain-fact` endpoint 继续使用 `pred_id + e_ref + val_atoms` DTO 与既有返回语义
  - 内部 helper 共享不受此条限制
- [x] service-layer bridge 边界已保持：
  - `assertion` 解引用通过 service/core bridge 组合 `ledger.get_claim(...)`、`find_claim_args(...)`、`find_meta(...)`、revocation lookup，而不是扩张新的 ledger 存储能力
  - `candidate` 解引用复用 `Store.get_candidate_support_digest(...)`，不得重跑 evaluate
- [x] 受影响 docs 的同步范围已明确；至少包括 [03_runtime_queries_views.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/03_runtime_queries_views.md)，并在需要时补 core architecture 中的 service-level handle mapping note。

## 8. Implementation Plan

1. 在 `runtime_v1.py` 落统一 `explain_runtime_ref(...)` handler、kind dispatch、`candidate`/`assertion`/`rule_run` resolution path，以及兼容 wrapper 的内部复用。
2. 在 `app_v1.py` 注册新的 `POST /queries/explain` 路由，并保持旧 explain routes 的 outward schema 不变。
3. 用 focused service/runtime tests 锁定三种 kind、shape errors、旧端点兼容、`candidate` 的 session-scoped first hop，以及 `assertion` narrow payload。
4. 实现完成后同步 `service/docs/03_runtime_queries_views.md`，并在需要时补 core architecture 对 service-level handle mapping 的说明。

## 9. Docs To Update

- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（若需要补 service-level handle mapping note）
- `src/factpy_kernel/core/docs/01_architecture.en.md`（若需要补 service-level handle mapping note）
- `docs/README.md`（仅当新增稳定文档入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增统一 service endpoint `POST /v1/runtime/sessions/{session_id}/queries/explain`，第一轮支持 `candidate` / `assertion` / `rule_run` 三种 `explain_ref` kind。
  - `candidate` 走 session-scoped first hop `candidate_id -> support_digest`，并在命中时返回统一顶层 `{ok, errors, meta, kind, explain}` envelope。
  - `assertion` 走 narrow single-`asrt_id` deref，返回 `asrt_id` / `pred_id` / `e_ref` / `is_active` / optional `revoker_asrt_id`。
  - `rule_run` 直接桥接既有 `rule_run_id -> RuleTraceArtifact` explain readback。
  - 旧 `explain-support` / `explain-rule-trace` surface 保持兼容，不新增顶层 `kind`；`explain-fact` 继续独立。
  - `service/docs/03_runtime_queries_views.md` 已同步统一 endpoint、兼容 wrapper 约束与 `explain-fact` 的语义隔离。
  - `src.factpy_kernel.tests.test_phase3_contracts_v1` 已扩展 unified explain 合同测试，`41 tests` 全通过。
- 与 blueprint 不同的地方：
  - `assertion` 第一轮只使用 `ledger.get_claim(...)`、`has_active_revocation(...)`、`find_revoker(...)` 组装 narrow payload，没有额外下沉 `find_claim_args(...)` / `find_meta(...)`，因为当前验收 shape 不需要更宽的 claim detail。
  - 旧 `explain-support` / `explain-rule-trace` endpoint 保持原有 facade 代码路径，只在行为和文档层面对齐统一 explain contract，没有机械性改写成直接转发统一 handler。
- 为什么会有这些调整：
  - 这两个调整都不改变已冻结的 service contract；它们只是把第一轮实现收敛到最小必要行为，避免在兼容 surface 上引入无收益的 DTO 扰动。
- 归档说明：
  - Blueprint 与 audit 已在实现完成、测试通过、service docs 对齐后归档到 `docs/blueprints/archive/`。
