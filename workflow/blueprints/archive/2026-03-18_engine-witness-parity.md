# Task Blueprint: Engine Witness Parity

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/adapters/souffle/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/__init__.py`
  - `src/factpy_kernel/adapters/problog/problog_import.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)
  - [2026-03-17_rule-run-trace-schema-contract.md](../archive/2026-03-17_rule-run-trace-schema-contract.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-18_engine-witness-parity.audit.md](./2026-03-18_engine-witness-parity.audit.md)

## 1. Problem

native derivation 路径现在已经能在 evaluate 时生成真实 `SupportArtifact`，并通过 `support_digest` / `support_kind="native_binding_v1"` 打通 explainability。

engine 路径（`souffle` / `problog`）则处于完全不同的状态：

1. 它们都能产生 `CandidateSet` 结果，但在本切片之前这些 candidate 的 `support_digest` 仍是哑占位符（`sha256:000...0`），`support_kind="none"`。
2. 这意味着 `explain_ref(kind="candidate")` 对 engine candidate 的第二跳 `support_digest -> SupportArtifact` 永远无效。
3. service 层当前对 native candidate 和 engine candidate 的返回形态几乎一样，但 explain quality 实际上完全不同，且没有统一、显式的降级语义。
4. `souffle` 在执行 query 时实际上知道“哪些 tuple 命中了哪些中间结果”，但 TSV binding 输出把这些信息全部丢掉了。
5. `problog` 当前返回的是概率结果，而不是 derivation witness；现有 adapter 也没有任何 provenance 捕获或 explain contract。

因此，这个切片的首要问题不是“立刻让所有 engine 拥有原生级 witness”，而是先把 **engine candidate 在 explain surface 上的真实状态收口清楚**：

- 哪些 engine 当前完全没有 witness；
- 何处发生了零 witness 降级；
- 调用方应如何显式感知这种降级，而不是静默拿到一个不可解释的 `support_digest` 哑值。

## 2. Goals

- 审计 `souffle` / `problog` evaluate 路径，明确 engine candidate 从 evaluator 到 `CandidateSet` 的 explainability 降级链路。
- 明确 `_coerce_binding_rows(bindings=...)` 这一已知零 witness 降级点在整体架构中的角色。
- 收口第一轮 engine witness parity 的最小目标：
  - 优先实现“显式降级（explicit degraded explain）”
  - 而不是承诺立即补齐真实 witness output
- 比较并冻结 engine candidate 的最小 explain contract：
  - `support_kind="none"` 是否继续存在
  - 是否需要 engine-specific degraded marker
  - service/SDK 是否需要显式暴露“该 candidate 无 witness”
- 为后续更强目标预留入口，但与本轮分离：
  - `souffle` 是否可能输出可回映到 `asrt_id` 的 witness
  - `problog` 是否可能输出 derivation/proof tree

## 3. Non-goals

- 本蓝图不要求 `souffle` 第一轮就输出真实 `asrt_id` 级 witness。
- 不要求 `problog` 第一轮输出完整 derivation tree、proof tree 或 node-level explanation。
- 不在本轮重新设计 native `SupportArtifact` schema。
- 不把 engine witness parity 与 `rule_run` trace、proof-tree UI、或 audit export contract 混成一个任务。
- 不在本轮承诺让 engine explain quality 与 native 完全等价；第一轮最低目标是显式降级，不是语义对齐。
- 不在本轮改变 `explain_ref` 的 kind vocabulary。

## 4. Current Context

- 当前 explainability 基座已经存在：
  - native evaluate 路径会生成真实 `SupportArtifact`
  - `candidate_id -> support_digest` backref 已存在
  - service `explain_ref(kind="candidate")` 已存在
  - sidecar / durable readback / retention 已落地
- 当前 engine 路径的核心现实：
  - `souffle`
    - `evaluate_store_engine(...) -> _run_query_and_read_bindings(...) -> _read_query_bindings(...)`
    - 最终只返回 `list[dict[str, Any]]` binding rows
    - 没有任何 witness/provenance payload
  - `problog`
    - `evaluate_problog(...)` 调用 CLI，读取 raw stdout
    - `parse_problog_output(...)` 解析概率结果并重建 `CandidateSet`
    - 没有 derivation witness capture
- 当前架构上的明确降级点：
  - `src/factpy_kernel/core/store/_builders.py` 的 `_coerce_binding_rows(bindings=...)`
  - 该分支在本切片前把纯 binding dict 包装成：
    - `support_digest = sha256:000...0`
    - `support_kind = "none"`
  - 这正是 engine 路径 explainability 退化成哑占位符的位置
- 当前已知 gap：
  - `E1`: `_coerce_binding_rows(bindings=...)` 产生零 digest；engine candidate 的 explainability 在这里显式降级
  - `E2`: `souffle` TSV output 只包含 binding tuples，不包含可回映到 `asrt_id` 的 provenance
  - `E3`: `problog` 输出只有概率层结果，没有 derivation 路径
  - `E4`: service 层对 `support_kind="none"` 尚无统一降级语义；当前只是静默返回一个 explainability 空壳
  - `E5`: `BindingSupportCapture` 已预留 `support_kind`，但尚未定义 engine-specific degraded kind 或 future witness kind
- 当前相关历史蓝图：
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
    - 只覆盖 native witness capture，不覆盖 engine parity
  - [2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)
    - 已让 `candidate` 进入统一 explain surface，但没有定义 engine-no-witness 的显式 service semantics
  - [2026-03-17_rule-run-trace-schema-contract.md](../archive/2026-03-17_rule-run-trace-schema-contract.md)
    - 已收口 `rule_run` trace schema；当前剩余 engine explain gap 主要落在 derivation candidate 路径
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
    - 已把 engine witness output 作为仍未拆解的剩余方向

## 5. Proposed Shape

### 5.1 First-round Goal: Explicit Degraded Explain

第一轮 engine witness parity 明确选择 **显式降级优先**，而不承诺立即补齐 native 级 witness。

换句话说，本轮的最低正确目标不是：

- `souffle` 立刻输出真实 `asrt_id` witness
- `problog` 立刻输出 derivation / proof tree

而是：

- engine candidate 不再静默伪装成“看起来和 native 一样，只是 support 读不出来”
- 调用方能够明确知道“这是有效 candidate，但当前无 witness”

### 5.2 `support_kind` Contract

第一轮收口如下：

- 新 writer 不再产生 `support_kind="none"`
- engine 路径的零 witness 降级显式写为：
  - `support_kind="engine_no_witness_v1"`
- `support_digest` 继续保留当前零 digest：
  - `sha256:000...0`
  - 其角色是兼容占位符，不再承担语义判定职责

这样做的原因：

- `support_kind` 本来就是区分 support 来源/质量层级的正确字段
- 零 digest 只能说明“没有真实 artifact digest”，不应承担 service contract 级别的判定语义
- 若继续把零 digest 当成 degrade 判据，会把 explain contract 绑死在 magic constant 上

兼容性立场：

- 新 writer 只写 `engine_no_witness_v1`
- 旧路径中已经存在的 `"none"` 应被视为 legacy degraded kind
- 第一轮不要求回写或迁移历史 candidate 数据，但 service / Store 在解释 candidate explainability 状态时必须把：
  - `"none"`
  - `"engine_no_witness_v1"`
  都视为“engine/no-witness degraded”

### 5.3 `Store` Candidate Support Kind Index

为避免在 service 层依赖零 digest 这种脆弱判定，本轮选择 **Option X**：

- 在现有 `_candidate_support_index` 旁边新增：
  - `_candidate_support_kind_index: dict[str, str]`
- 在 candidate support backref 登记时同时记录：
  - `candidate_id -> support_digest`
  - `candidate_id -> support_kind`
- 新增 public read helper：

```python
Store.get_candidate_support_kind(candidate_id) -> str | None
```

选择这一方案的原因：

- 当前 `explain_ref(kind="candidate")` 只有 `candidate_id`，而 `Store` 并没有按 `candidate_id` 直接取 `CandidateSet`
- `_candidate_support_index` 只存 digest，不存 kind
- 若不新增 kind index，service 只能：
  - 猜测 zero digest
  - 或继续把 degraded/no-witness 与 artifact-missing 混在一起

本轮明确拒绝：

- `Option Y`
  - 把 degraded 语义编码进 `support_digest` 命名
  - 这会破坏 `support_digest` 作为 `sha256:` token 的既有 contract
- `Option Z`
  - 继续在 service 里硬编码 zero digest 模式识别
  - 这会把 explain contract 建立在 magic constant 上

### 5.4 `candidate` Explain Degraded Semantics

`candidate` explain 第一轮选择 **degraded explain** 语义，而不是 `not_found`。

service 层需要区分两种情况：

1. `support_kind` 属于 degraded kind（legacy `"none"` 或新 `"engine_no_witness_v1"`）
   - candidate 本身有效
   - 只是当前结构上没有 witness artifact
   - 响应应保持 `ok=true`
   - explain payload 至少应显式包含：
     - `witness_status="degraded"`
   - 可附带 `witness_note` / `support_kind`
2. `support_kind` 不是 degraded kind，但 `support_digest -> SupportArtifact` 读不到
   - 这是 artifact-missing / readback-miss 问题
   - 不应与 engine-no-witness 混淆
   - 第一轮保持现有 readback 语义，不把它伪装成 degraded explain

这样收口的原因：

- `not_found` 语义表示“本来应该存在，但没有找到”
- engine no-witness 的真实语义是“结构上没有 witness”
- candidate 本身仍然是有效结果，因此不应通过 `ok=false` 把它表述成错误

第一轮 payload 方向：

- `explain.support` 在 degraded 情况下可以缺失
- 但必须显式暴露：
  - `witness_status="degraded"`
- 因此实现层面允许“support 缺失 + degraded marker”并存

### 5.5 Adapter-specific Gap Boundary

在上述统一 degraded contract 之外，两个 adapter 的更强目标继续分开处理：

- `souffle`
  - 后续若要追求真正 witness parity，关键问题是 query output 如何保留可回映到 `asrt_id` 的 provenance
- `problog`
  - 后续若要追求真正 witness parity，关键问题是如何从概率结果提升到 derivation/proof 结构

这些后续问题不阻塞第一轮 explicit degraded explain contract。

## 6. Boundaries And Invariants

- 必须明确区分 native 真 witness 与 engine 当前零 witness 降级路径。
- 第一轮不得把“显式降级”偷换成“表面返回一样、实质没有 explain”的静默兼容。
- 不得把本切片扩成 `souffle` schema 改造或 `problog` proof-tree 引擎项目。

## 7. Acceptance

- [x] `_coerce_binding_rows(bindings=...)` 的新 writer 语义已生效：
  - engine 路径（`souffle` / `problog`）生成的 `BindingSupportCapture.support_kind` 为 `"engine_no_witness_v1"`
  - 新 writer 不再写 `"none"`
- [x] `Store._remember_candidate_support(...)` 已扩展为同时登记 `support_kind`：
  - 签名接受 `support_kind: str`
  - `Store` 新增 `_candidate_support_kind_index: dict[str, str]`
  - 登记时同时写入 `candidate_id -> support_digest` 与 `candidate_id -> support_kind`
- [x] `Store.get_candidate_support_kind(candidate_id) -> str | None` 已存在：
  - 命中时返回 `support_kind`
  - 未命中时返回 `None`
- [x] degraded kind 的判定不依赖 magic constant：
  - 定义 `_DEGRADED_SUPPORT_KINDS = frozenset({"none", "engine_no_witness_v1"})` 或等价常量
  - service / Store 层使用该集合判断 degraded，而不是硬编码 zero digest 模式识别
- [x] `_explain_ref_candidate(...)` 在 degraded kind 时返回显式 degraded explain：
  - `get_candidate_support_kind(candidate_id)` 命中 degraded kind 时，响应保持 `ok=true`
  - `explain.witness_status = "degraded"`
  - degraded 情况下 `explain.support` 可以缺失，且不作为错误处理
- [x] `_explain_ref_candidate(...)` 能区分 “engine no-witness” 与 “artifact missing”：
  - `support_kind` 属于 degraded kind时，返回 degraded explain
  - `support_kind` 不属于 degraded kind，但 `explain_support(...)` 读不到时，保持现有非错误成功响应，不附加 `witness_status`
  - 两种情况的 payload 语义不互相污染
- [x] native candidate explain 行为保持不变：
  - `support_kind="native_binding_v1"` 的 candidate 继续走原有 support deref 路径
  - native explain payload 中不新增 `witness_status`
- [x] engine candidate 的现有序列化 surface 已反映新 `support_kind`：
  - evaluate response 中 `candidate.support_kind` 对 engine path 为 `"engine_no_witness_v1"`
  - 不再返回 `"none"`
- [x] `src/factpy_kernel/service/docs/03_runtime_queries_views.md` 已明确文档化：
  - `candidate` explain 的 `witness_status="degraded"` 出现条件
  - `support_kind="engine_no_witness_v1"` 的含义
- [x] `src/factpy_kernel/core/docs/01_architecture.md`（及必要时英文版）已补充 engine parity 当前状态：
  - engine 路径当前是显式 degraded explain
  - 不再把零 digest 当作隐式、未说明的兼容行为

## 8. Implementation Plan

1. 在 `_support.py` 冻结 degraded marker 常量与 legacy degraded-kind 兼容集合。
2. 扩展 `Store` 的 candidate explain backref，从 `candidate_id -> support_digest` 升级为 `candidate_id -> (support_digest, support_kind)`。
3. 让 engine evaluate 返回后的 candidates 也统一登记 backref，再由 service `explain_ref(kind="candidate")` 显式返回 degraded explain。
4. 补 focused tests 与 core/service/adapter docs，同步 engine parity 的当前 operator-facing 语义。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `docs/README.md`（仅当新增稳定文档入口时）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `_support.py` 新增 `ENGINE_NO_WITNESS_KIND = "engine_no_witness_v1"` 与 legacy degraded-kind 兼容集合 `_DEGRADED_SUPPORT_KINDS`。
  - engine binding fallback writer 不再产出 `support_kind="none"`；`_builders.py` 与 `Store.evaluate_dummy(...)` 现均写入 `engine_no_witness_v1`。
  - `Store` 新增 `_candidate_support_kind_index` 与 `get_candidate_support_kind(candidate_id)`，candidate explain 第一跳升级为 `candidate_id -> (support_digest, support_kind)`。
  - `evaluate_store(...)` 的 engine 分支现在也会在 evaluator 返回后登记 candidate support backrefs，使 `candidate` explain 能覆盖 engine degraded path。
  - `runtime_v1._explain_ref_candidate(...)` 对 degraded kind 返回 `ok=true` + `witness_status="degraded"` + `support_kind`，并继续把 native explain 与 artifact-miss 语义分开。
  - focused contracts 已覆盖 native explain 不变、engine degraded explain、新旧 degraded kind 兼容，以及 evaluate response 上的新 `support_kind`。
  - core / service / adapter docs 已同步到“显式 degraded explain”语义。
- 与 blueprint 不同的地方：
  - 实现时发现仅修改 `_remember_candidate_support_backrefs(...)` 的过滤逻辑还不够，因为 `evaluate_store(...)` 的 `souffle` / `problog` 分支原本直接 `return engine_evaluate(...)`，并不会调用 backref 登记。
- 为什么会有这些调整：
  - 若不补 engine evaluate 返回后的 backref 登记，engine candidate 仍然不会进入 session-scoped explain handle 索引，`explain_ref(kind="candidate")` 依旧会错误地落到 `runtime_explain_not_found`。
- 归档说明：
  - 本切片已实现并完成 focused docs/test sync，可归档到 `docs/blueprints/archive/2026-03-18_engine-witness-parity.md`。
