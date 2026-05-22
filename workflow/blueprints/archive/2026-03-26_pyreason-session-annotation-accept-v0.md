# Task Blueprint: PyReason Session Annotation Accept v0

- Status: implemented
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/session.py`
  - `src/factpy_kernel/adapters/pyreason/accept.py` (new)
  - `src/factpy_kernel/core/evidence/write_protocol.py`
  - `src/factpy_kernel/core/store/ledger.py`
- Audit Log:
  - [2026-03-26_pyreason-session-annotation-accept-v0.audit.md](./2026-03-26_pyreason-session-annotation-accept-v0.audit.md)

## 1. Problem

`PyReasonSession` 已能产出 `annotation_templates`，`Ledger` 已能持久化 `AnnotationRow`，但两者之间没有消费桥。annotation templates 里 `asrt_id=""` 是占位符，需要真正的 assertion accept 路径来绑定。

## 2. Goals

- 新增 adapter-local accept helper：`accept_pyreason_session(ledger, session)`
- 复用现有 `set_field()` 共享写入路径获取 `asrt_id`
- 只 materialize `pyreason/*` annotation templates（`shared/*` 已由 `set_field()` 自动写入）
- 绑定键冻结为 `(fact_kind, fact_index)`
- 跑通最小 round-trip：session → accept → ledger → verify annotations persisted

## 3. Non-goals

- 不碰 evaluate dispatch
- 不碰 rule builder / `engine_ext`
- 不碰 provenance pipeline
- 不碰 UI / audit consumer 切换
- 不修改 `write_protocol.py`
- 不修改 `accept.py`（Souffle candidate 专用）

## 4. Current Context

- `set_field(ledger, pred_id, e_ref, rest_terms, meta)` 已同时写 `meta_rows` + `shared/*` annotation_rows
- `set_field()` 对 edge facts 兼容（`rest_terms` 接受任意 tuple 对）
- `session.annotation_templates` 已标记 `fact_kind` + `fact_index`
- `ledger.append_annotations()` 已可用

## 5. Proposed Shape

### 5.1 Accept Helper

```python
# adapters/pyreason/accept.py

def accept_pyreason_session(
    ledger: Ledger,
    session: PyReasonSession,
) -> AcceptResult:
    """Accept all buffered facts from a PyReasonSession into the Ledger.

    1. Node facts → set_field() → asrt_id
    2. Edge facts → set_field() → asrt_id
    3. pyreason/* annotation templates → fill asrt_id → append_annotations()
    """
```

### 5.2 Edge Fact Mapping

Edge fact `{pred_id, from_ref, to_ref, value}` → `set_field()` call:
- `e_ref = from_ref`
- `rest_terms = [("to_ref", to_ref), ("value", value)]` if value non-empty, else `[("to_ref", to_ref)]`

### 5.3 Annotation Materialization

- 从 `session.annotation_templates` 中过滤 `namespace == "pyreason"` 的条目
- 用 `(fact_kind, fact_index) → asrt_id` map 填充 `asrt_id`
- 构造 `AnnotationRow` 并调用 `ledger.append_annotations()`
- **不重复写 `shared/*`**——已由 `set_field()` 内的 `_annotation_rows_for_claim()` 处理

### 5.4 Return Type

```python
@dataclass
class AcceptResult:
    node_asrt_ids: list[str]      # asrt_id per node fact, in order
    edge_asrt_ids: list[str]      # asrt_id per edge fact, in order
    annotation_count: int          # pyreason/* annotations written
```

## 6. Boundaries And Invariants

- accept helper 在 `adapters/pyreason/` 下，不在 `core/`
- 只调用 `set_field()` 和 `ledger.append_annotations()`，不直接写 SQLite
- `(fact_kind, fact_index)` 是模板到 assertion 的唯一绑定键
- `shared/*` annotations 永远不由 accept helper 写入

## 7. Acceptance

- [x] `accept_pyreason_session()` 可将 session 中的 facts 持久化到 Ledger
- [x] 每条 fact 获得真正的 `asrt_id`
- [x] `pyreason/semantic/*` annotations 持久化到 `annotation_rows` 并可通过 `find_annotations()` 查回
- [x] `shared/*` annotations 不重复写入
- [x] Round-trip 测试通过

## 8. Implementation Plan

1. 新建 `adapters/pyreason/accept.py`：`accept_pyreason_session()` + `AcceptResult`
2. 新建 `tests/test_pyreason_accept.py`：round-trip 测试
3. 更新蓝图 audit log

## 9. Docs To Update

- 本蓝图 audit log
- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `adapters/pyreason/accept.py`，提供 `accept_pyreason_session(ledger, session)`
  - `session.annotation_templates` 中的 `pyreason/*` 现在可 materialize 到 `Ledger.annotation_rows`
  - round-trip 测试覆盖了 session → accept → ledger → annotation readback
- 与 blueprint 不同的地方：
  - 最终没有把裸 graph id 直接送进 `set_field()`；accept helper 会先把 PyReason raw refs materialize 为 synthetic `entity_ref`
- 为什么会有这些调整：
  - shared write path 的 ingest key 计算强制 `e_ref` / `entity_ref` 走 canonical entity_ref encoding，裸 `Alice` / `Bob` 不能直接复用 `set_field()`
  - 为了继续复用 shared write path，同时不扩 scope 到完整 identity 对齐，这一版采用最小 adapter-local `idref_v1:<EntityType>:<raw>` materialization
- 归档说明：
  - 代码、测试、模块 docs 对齐后归档
