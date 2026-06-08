# Blueprint: explain-layer-s6-adapter-wiring

| Field | Value |
|---|---|
| **ID** | explain-layer-s6-adapter-wiring |
| **Date** | 2026-06-08 |
| **Status** | scoped |
| **Parent** | `workflow/blueprints/active/2026-06-08_explain-layer.md` (S6 child) |
| **Branch** | `v0.2.0-blueprint-explain-layer-2026-06-08` (blueprint文档) |
| **Impl branch** | `v0.2.0-impl-adapter-provenance-wiring-2026-06-08` (从S5 impl HEAD fork) |
| **Depends on** | S5 (`9ba5f526`) — Explanation invariant + adapters 迁移到 paths model |

---

## 1. Goal

将 `evaluate_result.py` 中残留的旧 `EvidenceNode`/`EvidenceEdge` dead code 全部删除，并接通 ProbLog / PyReason 的 rich provenance 路径，使 `explain()` 对这两种 engine 的 `passed` row 能返回完整的 `EvidenceGraph(paths=...)`（而非最小占位 tree）。

**不在范围**:
- Native / Souffle Form 1（`ProofReceipt` 不含 atom expression 详情，继续使用最小 placeholder）
- Souffle raw proof tree 接通（Souffle 使用 Form 1 ProofReceipt 路径）
- 新增公共 API 或修改 `EvidenceGraph` / `EvidenceTree` 数据结构
- Docs slice（S5 impl docs 更新推迟到 S6 落地后合并）

---

## 2. Preflight Findings

### 2.1 adapters（S5 `9ba5f526`）— 已就绪

| 模块 | 函数 | 返回值 |
|---|---|---|
| `adapters/problog/provenance.py` | `problog_trace_to_evidence_graph(trace, *, candidate_id, candidate_payload, support_kind)` | `EvidenceGraph(paths=(EvidenceTree,), ...)` |
| `adapters/pyreason/provenance.py` | `pyreason_trace_to_evidence_graph(trace, *, candidate_id, candidate_payload, support_kind)` | `EvidenceGraph(paths=(EvidenceTimeline,), ...)` |
| `adapters/souffle/provenance.py` | `souffle_proof_tree_to_evidence_graph(tree, schema_index)` | `EvidenceGraph(paths=(EvidenceTree,), ...)` |

三个 adapter 函数均已更新为 paths model（S5 中完成），本 slice 仅接线，不修改 adapters。

### 2.2 evaluate_result.py dead code（S5 `9ba5f526`）

以下函数在 S5 中完全未被调用（dead code），且引用了未定义的符号（`EvidenceNode`、`EvidenceEdge`、`NODE_*`、`EDGE_*`——均未导入），在运行时会触发 `NameError`：

| 函数 | 问题 | 行号（approximate） |
|---|---|---|
| `_layered_shell_ids` | 仅由以下 dead 函数使用 | ~956 |
| `_row_conclusion_node` | 使用未导入的 `EvidenceNode`、`NODE_CONCLUSION` | ~963 |
| `_row_rule_expr_node` | 使用未导入的 `EvidenceNode`、`NODE_RULE_EXPR` | ~999 |
| `_row_rule_node` | 使用未导入的 `EvidenceNode`、`NODE_RULE` | ~1011 |
| `_row_shell_nodes` | 使用 `EvidenceNode`、`NODE_ATOM` | ~1028 |
| `_row_shell_edges` | 使用 `EvidenceEdge`、`EDGE_DERIVED_BY`、`EDGE_USES` | ~1036 |
| `_build_problog_provenance_row_evidence_graph` | 使用 `.nodes`/`.edges` 旧 API + `EvidenceNode`/`EvidenceEdge` | ~1101 |
| `_problog_trace_summary` | 使用旧 `candidate_graph.metadata` shape | ~1195 |
| `_problog_uncertainty_projection_meta` | 仅由上函数调用 | ~1212 |
| `_problog_node_engine_meta` | 仅由上函数调用 | ~1231 |
| `_build_form1_evidence_graph` | 使用 `EvidenceNode`/`EvidenceEdge`/`NODE_ATOM`/`NODE_SEED` etc. | ~1245 |

**顶层导入中没有 `EvidenceNode`/`EvidenceEdge`/`NODE_*`/`EDGE_*`**——这些符号从未被正确导入，dead code 能在语法层通过 `compileall` 只因 Python 延迟名称解析。

### 2.3 当前 dispatch 路径（S5 实际行为）

```python
# evaluate_result.py ~line 763
builder = _build_passed_row_evidence_graph if graph_builder is None else graph_builder
evidence = builder(row, result, metadata)
```

`_build_passed_row_evidence_graph` 完全忽略 `result._row_provenance_envelopes` 和 `result._row_support_artifacts`，所有 engine 的 passed row 均走最小 head-atom placeholder。

### 2.4 Provenance envelope 收集缺口（`sdk/store.py`）

`_row_provenance_envelopes_for_candidates` 当前只收集 `PROBLOG_PROVENANCE_KIND` 候选，PyReason 候选（`PYREASON_PROVENANCE_KIND`）被跳过：

```python
# sdk/store.py ~line 2868
if candidate.support_kind != PROBLOG_PROVENANCE_KIND:
    continue
```

`_PROVENANCE_BEARING_SUPPORT_KINDS = frozenset({PYREASON_PROVENANCE_KIND, PROBLOG_PROVENANCE_KIND})` 在 `_support.py` 中已有定义（且在 `__all__` 中）。

### 2.5 `_legacy_candidate_payload_for_row_result` — 可用，需重命名

当前被 dead code `_build_problog_provenance_row_evidence_graph` 引用。删除 dead code 后，新 ProbLog 富接线函数仍需相同的 `{"pred_id": ..., "terms": [...]}` payload，可直接重命名后复用。

---

## 3. Proposed Changes

### 3.1 evaluate_result.py

#### 3.1.1 删除 dead code

删除以下全部函数：
- `_layered_shell_ids`
- `_row_conclusion_node`, `_row_rule_expr_node`, `_row_rule_node`
- `_row_shell_nodes`, `_row_shell_edges`
- `_build_problog_provenance_row_evidence_graph`, `_problog_trace_summary`, `_problog_uncertainty_projection_meta`, `_problog_node_engine_meta`
- `_build_form1_evidence_graph`

#### 3.1.2 重命名候选 payload helper

```python
# before
def _legacy_candidate_payload_for_row_result(row, result) -> Mapping[str, Any]: ...

# after
def _candidate_payload_for_row_result(row, result) -> Mapping[str, Any]: ...
```

#### 3.1.3 提取最小 placeholder

将 `_build_passed_row_evidence_graph` 现有函数体提取为 `_build_minimal_passed_evidence_graph`：

```python
def _build_minimal_passed_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
) -> EvidenceGraph:
    """Build a minimal head-atom EvidenceGraph for passed rows (no provenance available)."""
    _validate_evidence_metadata_for_row_result(metadata, row, result)
    atom = EvidenceAtom(
        form=Fact(
            predicate=_claim_name_for_row_result(row, result),
            terms=tuple(EvidenceConst(_public_term_value(term)) for term in row.bindings.values()),
        ),
        verdict=Holds(BOOLEAN_CERTAINTY),
        atom_id=f"{row.row_id}:head",
        repr_text=_claim_repr_for_row_result(row, result),
    )
    rule = EvidenceRule(
        occurrence_alias="head",
        rule_id=result.head.id,
        role="head",
        status="holds",
        ports={port_name: _public_term_value(term) for port_name, term in row.bindings.items()},
        atoms=(atom,),
    )
    tree = EvidenceTree(
        tree_id=f"path:{row.row_id}:passed",
        status="holds",
        rules=(rule,),
        joins=(),
        certainty=BOOLEAN_CERTAINTY,
    )
    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        layout_hint=LAYOUT_TREE,
        subject_binding={
            "result_id": result.result_id,
            "row_id": row.row_id,
            "bindings": {port_name: _public_term_value(term) for port_name, term in row.bindings.items()},
        },
        paths=(tree,),
        certainty=BOOLEAN_CERTAINTY,
        metadata=metadata,
    )
```

#### 3.1.4 新 ProbLog 富接线函数

```python
def _build_problog_passed_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
    envelope: ProvenanceEnvelope,
) -> EvidenceGraph:
    """Build ProbLog rich EvidenceGraph from ProvenanceEnvelope.

    Falls back to minimal placeholder if adapter conversion fails.
    """
    try:
        from factgraph.adapters.problog.provenance import (
            problog_trace_from_dict,
            problog_trace_to_evidence_graph,
        )
        trace = problog_trace_from_dict(envelope.payload)
        candidate_payload = _candidate_payload_for_row_result(row, result)
        adapter_graph = problog_trace_to_evidence_graph(
            trace,
            candidate_id=envelope.candidate_id,
            candidate_payload=candidate_payload,
            support_kind=PROBLOG_PROVENANCE_KIND,
        )
    except Exception:
        return _build_minimal_passed_evidence_graph(row, result, metadata)

    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        layout_hint=adapter_graph.layout_hint,
        subject_binding={
            "result_id": result.result_id,
            "row_id": row.row_id,
            "bindings": {port_name: _public_term_value(term) for port_name, term in row.bindings.items()},
        },
        paths=adapter_graph.paths,
        certainty=adapter_graph.certainty,
        metadata=metadata,
    )
```

#### 3.1.5 新 PyReason 富接线函数

```python
def _build_pyreason_passed_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
    envelope: ProvenanceEnvelope,
) -> EvidenceGraph:
    """Build PyReason rich EvidenceGraph from ProvenanceEnvelope.

    Falls back to minimal placeholder if adapter conversion fails.
    """
    try:
        from factgraph.adapters.pyreason.provenance import (
            pyreason_trace_from_dict,
            pyreason_trace_to_evidence_graph,
        )
        from factgraph.core.store._support import PYREASON_PROVENANCE_KIND
        trace = pyreason_trace_from_dict(envelope.payload)
        candidate_payload = _candidate_payload_for_row_result(row, result)
        adapter_graph = pyreason_trace_to_evidence_graph(
            trace,
            candidate_id=envelope.candidate_id,
            candidate_payload=candidate_payload,
            support_kind=PYREASON_PROVENANCE_KIND,
        )
    except Exception:
        return _build_minimal_passed_evidence_graph(row, result, metadata)

    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        layout_hint=adapter_graph.layout_hint,
        subject_binding={
            "result_id": result.result_id,
            "row_id": row.row_id,
            "bindings": {port_name: _public_term_value(term) for port_name, term in row.bindings.items()},
        },
        paths=adapter_graph.paths,
        certainty=adapter_graph.certainty,
        metadata=metadata,
    )
```

#### 3.1.6 更新 dispatch（`_build_passed_row_evidence_graph`）

```python
def _build_passed_row_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
) -> EvidenceGraph:
    """Dispatch to engine-specific rich builder or fall back to minimal placeholder."""
    _validate_evidence_metadata_for_row_result(metadata, row, result)
    if result._row_provenance_envelopes:
        envelope = result._row_provenance_envelopes.get(row.row_id)
        if envelope is not None:
            if envelope.engine == "problog":
                return _build_problog_passed_evidence_graph(row, result, metadata, envelope)
            if envelope.engine == "pyreason":
                return _build_pyreason_passed_evidence_graph(row, result, metadata, envelope)
    return _build_minimal_passed_evidence_graph(row, result, metadata)
```

**注意**: `_validate_evidence_metadata_for_row_result` 在 dispatcher 中调用一次，子函数内部不需要重复调用（现有 `_build_minimal_passed_evidence_graph` 中的调用可移除）。

### 3.2 sdk/store.py

#### 3.2.1 扩展 import

```python
# before
from factgraph.core.store._support import PROBLOG_PROVENANCE_KIND, ProvenanceEnvelope, ProofReceipt

# after
from factgraph.core.store._support import (
    PROBLOG_PROVENANCE_KIND,
    PYREASON_PROVENANCE_KIND,
    ProvenanceEnvelope,
    ProofReceipt,
)
```

#### 3.2.2 修复 `_row_provenance_envelopes_for_candidates`

```python
# before
if candidate.support_kind != PROBLOG_PROVENANCE_KIND:
    continue

# after
if candidate.support_kind not in (PROBLOG_PROVENANCE_KIND, PYREASON_PROVENANCE_KIND):
    continue
```

---

## 4. Decisions

### Q-S6-A: adapter 调用失败时的回退策略 — LOCKED Option B

**背景**: `problog_trace_to_evidence_graph` / `pyreason_trace_to_evidence_graph` 在 payload 损坏或格式不兼容时会抛出 `ValueError`。

**选项**:
- **Option A**: 不捕获——让 `ValueError` 向上传播，被外层 `try/except ValueError` 捕获，返回 `status="unsupported", evidence=None`。
  - **问题**: 破坏 S5 invariant（passed row → evidence is not None）。
- **Option B（推荐）**: 在 `_build_problog_passed_evidence_graph` 和 `_build_pyreason_passed_evidence_graph` 内部用 `try/except Exception` 捕获，失败时 fall back 到 `_build_minimal_passed_evidence_graph`。
  - 维护 invariant：passed rows 永远有 evidence。
  - 与 `probe_native` 在 S5 closed_head_false 路径的回退策略一致。

**决策**: **Option B**。Rich builder 内部捕获 adapter 转换异常并回退到 `_build_minimal_passed_evidence_graph(...)`，保证 S5 锁定的 passed-row invariant（`status="passed"` 必须有 evidence）不被 adapter payload/trace 兼容问题打破。

---

## 5. Invariants

| ID | 不变量 |
|---|---|
| INV-s6-dead-code | evaluate_result.py 中不存在 `EvidenceNode`/`EvidenceEdge`/`NODE_*`/`EDGE_*` 引用 |
| INV-s6-dispatch | `passed` 行 explain：有 problog envelope → ProbLog rich graph；有 pyreason envelope → PyReason rich graph；其他 → minimal placeholder |
| INV-s6-metadata | 所有 rich builder 返回的 `EvidenceGraph.metadata` 通过 `_validate_evidence_metadata_for_row_result` |
| INV-s6-fallback | adapter 转换失败 → 回退到 minimal placeholder，不返回 unsupported |
| INV-s6-pyreason-collect | `_row_provenance_envelopes_for_candidates` 收集 ProbLog + PyReason 两种 envelope |

---

## 6. Scope Boundaries

**IN**:
- 删除 evaluate_result.py 中所有 dead `EvidenceNode`/`EvidenceEdge`-using 函数
- ProbLog 富接线：`_build_problog_passed_evidence_graph`
- PyReason 富接线：`_build_pyreason_passed_evidence_graph`
- PyReason envelope 收集修复（sdk/store.py）
- `_legacy_candidate_payload_for_row_result` 重命名（去掉 `legacy_` 前缀）

**OUT**:
- Native / Souffle Form 1 富接线（ProofReceipt 不含 atom expression）
- `_build_form1_evidence_graph` 重写（删除后不替换，仅 minimal placeholder）
- EvidenceTimeline 额外字段（PyReason path shape 已由 adapter 决定）
- 新增测试（现有 1996 通过测试已覆盖路径；富接线需要 adapter 测试数据，推迟到独立 test slice）
- Module docs 更新（推迟到 S6 + test slice 合并）
- 推送（用户显式授权后统一推）

---

## 7. File Touch List

| 文件 | 操作 | 范围 |
|---|---|---|
| `src/factgraph/application/protocol/evaluate_result.py` | 修改 | 删除 dead 函数；提取/新增/更新 4 个 evidence builder；重命名 1 个 helper |
| `src/factgraph/sdk/store.py` | 修改 | 扩展 import + 修复 `_row_provenance_envelopes_for_candidates` 1 行条件 |

---

## 8. Outcome / Deviations

_（实施完成后填写）_
