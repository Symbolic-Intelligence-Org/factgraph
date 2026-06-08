# Application Protocol — EvaluateResult & Explain Surface

- Scope: `src/factgraph/application/protocol/evaluate_result.py` + `explanation_render.py`
- Last updated: 2026-06-08
- Audience: SDK layer maintainers, adapter writers, and test authors

This document covers the evaluate-result / explain slice of `protocol/`.
Other protocol files (`derivation.py`, `entity_read.py`, etc.) are covered by the
application overview doc at `src/factgraph/application/docs/01_overview_en.md`.

---

## 1. Scope

`evaluate_result.py` owns:

- `EvaluateRow` — one result row from a derivation evaluation run
- `EvaluateResult` — the full evaluation envelope (rows + head + fingerprint)
- `ResultFingerprint` — immutable digest bundle for reproducibility
- `Explanation` — the output of `EvaluateRow.explain()`
- `explain_row(row, result)` dispatch logic (internal entry point `_explain_live_row`)
- Evidence builder dispatch: minimal placeholder → ProbLog/PyReason rich adapter graph

`explanation_render.py` owns:

- `walk_evidence(graph, ...)` — deterministic text rendering over `EvidenceGraph(paths=...)`

---

## 2. Responsibilities

### 2.1 `EvaluateRow`

A single row from a derivation evaluation. Carries the bound head values
and row-level digests.

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, Any]               # {port_name: term_value}
    kind: ClaimKind                           # "fact_triple" | "rule_head" | "aggregate_result" | "projection"
    digest: str                               # sha256 claim digest
    closed_head_digest: str                   # sha256 closed-head digest
    raw_kind: RawKind | None                  # "probabilistic" | "possibilistic" | None
    bound: tuple[float, float] | None         # probability/possibility interval
```

The `explain()` method returns an `Explanation` via `_explain_live_row(self, result)`.
The `close()` method returns a closed `Rule` from the row bindings.

`EvaluateRow` is live (attached to a result resolver) or detached. Calling
`explain()` on a detached row raises `DetachedRowError`.

---

### 2.2 `ResultFingerprint`

Immutable digest bundle stamped at evaluation time:

```python
@dataclass(frozen=True)
class ResultFingerprint:
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    config_digest: str | None
    result_digest: str
    run_id: str
```

All digests are SHA-256 tokens. `config_digest` is `None` when no
`SemanticsProfile` was used (native default semantics).

---

### 2.3 `EvaluateResult`

The full evaluation envelope:

```python
@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    rows: tuple[EvaluateRow, ...]
    head: Rule
    engine: str
    evaluated_at: object
    fingerprint: ResultFingerprint
    engine_meta: Mapping[str, Any]
```

Private fields (not compared / not repr'd):
- `_schema_index` — `ApplicationSchemaIndex` for explain repr baking
- `_row_close_builder` — injected by SDK for entity-ref aware row closing
- `_row_support_artifacts` — `{row_id: ProofReceipt}` for native/souffle Form 1 rows
- `_row_provenance_envelopes` — `{row_id: ProvenanceEnvelope}` for ProbLog/PyReason rows

Iteration / indexing:
- `result[i]` → `EvaluateRow`
- `for row in result:` iterates rows
- `result.first()` → `EvaluateRow | None`
- `result.exists()` → `bool`
- `result.count()` → `int`

**Deprecated flat properties** (emit `DeprecationWarning`; use `fingerprint.*` or `engine_meta.*` instead):

| Deprecated property | Replacement |
|---|---|
| `result.run_id` | `result.fingerprint.run_id` |
| `result.engine_version` | `result.engine_meta["engine_version"]` |
| `result.adapter_version` | `result.engine_meta["adapter_version"]` |
| `result.rule_set_digest` | `result.fingerprint.rule_set_digest` |
| `result.view_snapshot_digest` | `result.fingerprint.view_snapshot_digest` |
| `result.config_digest` | `result.fingerprint.config_digest` |
| `result.result_digest` | `result.fingerprint.result_digest` |

`result.expr_digest` was removed entirely in Cleanup-β (2026-06-08) — use `result.fingerprint.expr_digest`.

---

### 2.4 `Explanation`

The output of `EvaluateRow.explain()`:

```python
@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus                    # "passed" | "failed" | "unsupported" | "invalid_request"
    evidence: EvidenceGraph | None
    row: EvaluateRow | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None
    checked_scope: Mapping[str, Any] | None
    suggested_next_steps: tuple[str, ...]
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

**S5 evidence invariant** (locked 2026-06-08):

```
status in {"passed", "failed"}  ↔  evidence is not None
status in {"unsupported", "invalid_request"}  ↔  evidence is None
```

`Explanation.__post_init__` enforces this invariant via `ProtocolShapeError`.

Status semantics:

| Status | Meaning |
|---|---|
| `"passed"` | Row passed; `evidence` is a complete `EvidenceGraph(paths=...)` |
| `"failed"` | Row failed or could not be probed; `evidence` is a probe-result `EvidenceGraph` |
| `"unsupported"` | Request context is invalid (stale row, protocol error); `evidence=None` |
| `"invalid_request"` | Malformed input; `evidence=None` |

`failure_class` is set only when `status == "failed"`:

| Value | Trigger |
|---|---|
| `"closed_head_false"` | Derivation head does not hold; `probe_native` result attached |
| `"no_matching_row"` | No row in result matches the head |
| `"stale_row"` | Row anchor digest mismatch (use current result) |
| `"row_not_in_result"` | Row belongs to a different result |
| `"insufficient_closed_bindings"` | Head has unbound ports |

`Explanation.repr` property returns text lines from `walk_evidence(...)` for
`passed`/`failed` status; returns `None` for `unsupported`/`invalid_request`.

---

### 2.5 Evidence builder dispatch

`_explain_live_row` dispatches via `_build_passed_row_evidence_graph`:

1. **ProbLog row** (`result._row_provenance_envelopes[row.row_id].engine == "problog"`):
   - Calls `problog_trace_to_evidence_graph(trace, ...)` from `adapters.problog.provenance`
   - Returns full proof-tree `EvidenceGraph(paths=(EvidenceTree,), certainty=...)`
   - Failure falls back to minimal placeholder

2. **PyReason row** (`result._row_provenance_envelopes[row.row_id].engine == "pyreason"`):
   - Calls `pyreason_trace_to_evidence_graph(trace, ...)` from `adapters.pyreason.provenance`
   - Returns timeline `EvidenceGraph(paths=(EvidenceTimeline,), certainty=...)`
   - Failure falls back to minimal placeholder

3. **Native / Souffle Form 1 row** (or any row without provenance envelope):
   - Minimal placeholder: single `EvidenceRule` with head atom only
   - `EvidenceGraph(paths=(EvidenceTree(rules=(head_rule,), ...),), certainty=BOOLEAN_CERTAINTY)`

All returned graphs have `metadata` matching the v1 row-result key set:
`result_id`, `row_id`, `evidence_ref_id`, `claim_digest`, `closed_head_digest`,
`expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `config_digest`,
`result_digest`, `engine`, `engine_version`, `adapter_version`, `evaluated_at`.

---

### 2.6 `walk_evidence`

```python
def walk_evidence(
    graph: EvidenceGraph,
    *,
    row: object | None = None,
    status: str = "passed",
    failure_class: str | None = None,
) -> tuple[str, ...]:
```

Walks an `EvidenceGraph(paths=...)` and produces deterministic plain-text lines.
Used by `Explanation.repr`. Each path in `graph.paths` is rendered recursively:
- `EvidenceTree` → rule/atom lines with repr_text and verdict
- `EvidenceTimeline` → event lines

---

## 3. Non-responsibilities

- `evaluate_result.py` does not own adapter converters (`problog_trace_to_evidence_graph` etc.)
- `evaluate_result.py` does not own the prober (`probe_native`); it calls it for `closed_head_false` paths
- `evaluate_result.py` does not own the SDK `EvaluateResult` → `fg.eval.evaluate()` wrapper
- `explanation_render.py` does not produce HTML; it produces plain text
- Souffle Form 1 / native `ProofReceipt` rich wiring is deferred; current S6 baseline uses the minimal placeholder for these engine paths

---

## 4. Limitations & Compatibility

- The `expr_digest` flat property was **permanently removed** in Cleanup-β (2026-06-08).  
  All callers must migrate to `result.fingerprint.expr_digest`.
- Other deprecated flat properties (`run_id`, `engine_version`, etc.) still exist but emit `DeprecationWarning`. They will be removed in a future slice.
- Native/Souffle Form 1 rows return a minimal head-atom `EvidenceGraph` (no body atoms). Rich Form 1 wiring requires ProofReceipt → EvidenceAtom mapping, which is deferred because ProofReceipt does not store full atom expression data.
- `_row_provenance_envelopes` and `_row_support_artifacts` are private fields and are not part of the stable contract for external callers.

---

## 5. Test Entry Points

```bash
# Core DTO shape + explain invariant + Cleanup-β
python -m pytest tests/application/protocol/test_evaluate_result_dtos.py

# walk_evidence renderer
python -m pytest tests/application/protocol/test_explanation_render.py

# Adapter dispatch (ProbLog / PyReason rich provenance)
python -m pytest tests/test_problog_evidence_graph.py
python -m pytest tests/test_pyreason_evidence_graph.py

# SDK exports / fingerprint
python -m pytest tests/sdk/test_evaluate_result_exports.py
```

---

## 6. Related Historical Blueprints

- `workflow/blueprints/archive/2026-06-08_explain-layer-s5-native-path.md` — S5 invariant + closed_head_false wiring + stale_row/row_not_in_result → unsupported
- `workflow/blueprints/archive/2026-06-08_explain-layer-s6-adapter-wiring.md` — S6 ProbLog/PyReason rich dispatch + dead code removal
- `workflow/blueprints/active/2026-06-08_explain-layer.md` — parent program
