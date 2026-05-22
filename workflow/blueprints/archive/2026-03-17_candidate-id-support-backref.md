# Task Blueprint: Candidate ID Support Backref

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/derivation/candidates.py`
  - `src/factpy_kernel/service/runtime_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
  - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
- Audit Log:
  - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)

## 1. Problem

当前 explainability 已经打通了：

- `candidate.support_digest`
- `Store.explain_support(support_digest)`
- service `POST /queries/explain-support`

但调用者如果手里只有 `candidate_id`，仍然缺一条稳定的反查路径去拿到对应的 `support_digest`。

这在几类场景下会形成空洞：

- 上层只缓存了 `candidate_id`，没有保留完整 `CandidateSet`
- 调用方想从 candidate handle 继续跳到 support explain，而不是自己携带 digest
- 后续若继续讨论 candidate-facing explain protocol，没有这层 backref 就只能要求调用方一直持有完整 candidate payload

当前问题不是 generic `explain_ref`，也不是 durable storage；只是要把现有 handle 之间的关系补成“按 `candidate_id` 可查找”。

## 2. Goals

- 在 `Store` 上新增 `candidate_id -> support_digest` 的内存 backref index。
- 让 native evaluate 路径在 candidate 构建后把 backref 写入 index。
- 在 `Store` 上新增公开 helper：`get_candidate_support_digest(candidate_id) -> str | None`。
- 保持现有 `Store.explain_support(...)` 语义不变，由调用者自行决定是否继续解引用 explain dict。
- 保持当前 runtime/service/core explain 分层不被揉成单一 convenience API。

## 3. Non-goals

- 不做 `candidate_key -> support_digest`。
- 不做 `candidate_id -> explain dict` 的一步式 convenience API。
- 不做 `RuleTraceArtifact` 的反查协议。
- 不改 ledger / audit package durable 结构。
- 不引入 generic `explain_ref`。
- 不改动 `CandidateSet` 公开字段形状。

## 4. Current Context

- 当前 `CandidateSet` 已经带 `candidate_id` 与 `support_digest`。
- `support_digest` 当前来自 native support capture；非 native 路径仍可能是 `support_kind="none"`。
- `Store` 已有：
  - `_support_artifacts`
  - `_lookup_support_artifact(...)`
  - `explain_support(...)`
- 当前最自然的写入点不在 `_builders.py`，因为：
  - `_builders.py` 是纯构建层，不持有 `Store`
  - `_evaluate_where_over_view_with_support(...)` 只有 `BindingSupportCapture`，还没有 `candidate_id`
- `_evaluate.py` 的 builder 外层是唯一同时拿到：
  - `store`
  - `row.support_digest`
  - `candidate.candidate_id`

## 5. Proposed Shape

### 5.1 Store-side Index

在 `Store` 上新增：

```python
_candidate_support_index: dict[str, str]
```

语义：

- key = `candidate_id`
- value = `support_digest`

第一轮刻意不做：

- `candidate_key -> support_digest`
- multi-value mapping
- accepted-only mapping

### 5.2 Write Timing

backref 在 **evaluate 时** 写入，而不是 accept 时。

原因：

- `candidate_id` 本来就是 evaluate 产物
- 调用方在 accept 之前也可能需要 explain
- 若只在 accept 时写入，会让 `candidate_id` 的 explainability 语义不完整

因此第一轮语义是：

- 所有 evaluated native candidates 都可通过 `candidate_id` 反查 `support_digest`

### 5.3 Write Location

写入点放在 `_evaluate.py` 的 builder 外层，而不是：

- `_evaluate_where_over_view_with_support(...)`
  - 因为此时还没有 `candidate_id`
- `_builders.py`
  - 因为 builder 不应为了 backref 引入 `Store`

因此第一轮实现应在：

- fact derivation path：builder 返回 `candidates` 后注册 backref
- entity derivation path：builder 返回 `entity + role fact candidates` 后注册 backref

### 5.4 Entity-path Sharing

entity derivation 下，一条 row 可能产出多个 candidates。

第一轮约束：

- 同一 row 产出的所有 candidates
- 都写入同一个 `support_digest`

这与当前 native support capture 的语义一致，因为这些 candidates 本来就共享同一个 `SupportArtifact`。

### 5.5 Public API Shape

第一轮新增：

```python
def get_candidate_support_digest(self, candidate_id: str) -> str | None:
    ...
```

并保留私有层：

```python
def _lookup_candidate_support(self, candidate_id: str) -> str | None:
    ...
```

第一轮明确不新增：

```python
def explain_support_for_candidate(self, candidate_id: str) -> dict | None:
    ...
```

调用者若需要 explain，应自行串联：

1. `digest = store.get_candidate_support_digest(candidate_id)`
2. `store.explain_support(digest)`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `CandidateSet` 公共 schema 不变
  - `Store.explain_support(...)` 语义不变
  - `_builders.py` 保持纯构建职责，不直接持有 `Store`
- 明确不做的内容：
  - 不做 `candidate_key`
  - 不做 rule-trace 反查
  - 不做 durable backref
  - 不做 service endpoint 扩张
- 兼容性约束：
  - 非 native / `support_kind="none"` 路径不应被错误登记成伪 backref
  - 若同一 `candidate_id` 被重复注册，第一轮采用 **first-write-wins**：静默保留首次登记值，后续重复注册忽略；`candidate_id` 本应是 per-evaluate-run 唯一值，不应在 index 层再引入覆盖语义或异常分支

## 7. Acceptance

- [x] `Store` 拥有 `candidate_id -> support_digest` 的内存 index
- [x] native evaluate 路径会在 candidate 构建后登记 backref
- [x] entity path 的一 row 多 candidates 都能指向同一个 `support_digest`
- [x] `Store.get_candidate_support_digest(candidate_id)` 可用
- [x] 没有引入 convenience explain API、`candidate_key` mapping 或 durable 语义

## 8. Implementation Plan

1. 在 `Store` 上增加 `_candidate_support_index` 及私有/公开 lookup helper。
2. 在 `_evaluate.py` 的 native candidate 构建外层登记 fact-path backref。
3. 在 `_evaluate.py` 的 entity-path candidate 构建外层登记共享 `support_digest` 的 backref。
4. 补充 focused tests，覆盖：
   - fact candidate path
   - entity multi-candidate sharing
   - missing candidate id returns `None`
5. 如有必要，更新相关 module docs。

## 9. Docs To Update

- `src/factpy_kernel/core/derivation/CANDIDATE_PROTOCOL_V2.md`（如需补充 candidate-facing explain handle note）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（仅在 service 层消费路径需要备注时）
- `docs/README.md`（仅在新增 durable docs 入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - `Store` 新增 `_candidate_support_index`、`_remember_candidate_support(...)`、`_lookup_candidate_support(...)` 和公开 helper `get_candidate_support_digest(candidate_id)`
  - native evaluate 路径现已在 builder 外层登记 `candidate_id -> support_digest` backref
  - 仅 `support_kind="native_binding_v1"` 的 candidates 会进入 backref index；兼容路径的 `support_kind="none"` 不会被登记
  - entity path 下同一 row 产出的 entity candidate 与 role fact candidates 会共享同一 `support_digest` backref
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记
  - `src/factpy_kernel/core/docs/01_architecture.md` / `.en.md` 与 `CANDIDATE_PROTOCOL_V2.md` 已同步补充 candidate-facing explain backref 说明
- 与 blueprint 不同的地方：
  - 写入点仍位于 `_evaluate.py` 的 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 `support_kind/support_digest`，没有继续保留额外的 binding-to-support 对齐层
- 为什么会有这些调整：
  - candidate 本身已经携带最终的 `support_kind/support_digest`，直接按 candidate 登记 backref 更稳，也避免在 index 层重复实现 binding 重建或 row/candidate 对齐推断
- 归档说明：
  - 本切片已实现并完成 targeted `unittest` 与 compile 验证；后续若继续推进 candidate-facing explainability，应在此基础上另开 convenience API 或 generic explain protocol 子蓝图，而不是在本文件中继续扩写
