# Application Protocol — EvaluateResult & Explain Surface

- Scope: `src/factgraph/application/protocol/evaluate_result.py` + `explanation_render.py`
- Last updated: 2026-08-13
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
- Evidence builder dispatch: SDK prober graph builder → protocol fallback paths-model graph

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
    certainty: Certainty | None               # boolean/probabilistic/possibilistic interval
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
    run_anchor: EvaluationRunAnchorV0 | None = None
    run_bundle: EvaluationRunBundleV0 | None = None
    scenario: ScenarioResolutionV0 | ScenarioFieldSubstitutionSetResolutionV0 | None = None
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

Compiled native `EvaluationQuery` execution always attaches the identity-only
`run_anchor`. With the explicit `capture="run_bundle_v0"` option it also
attaches `run_bundle`, a strict canonical and size-bounded detached audit
artifact. The bundle captures sensitive typed values, exact plan/schema,
effective dependency relations, rows and ProofReceipts. It is integrity-sealed
but not authenticated, has caller-managed custody, and exposes neither replay
nor detached Explain. Ordinary evaluation leaves `run_bundle=None`; capture
cannot be added post hoc.

The only exception is a Scenario compiled Query result. It has either the
single-field `ScenarioResolutionV0` or the atomic multi-field
`ScenarioFieldSubstitutionSetResolutionV0` in `scenario`, but it **must not**
carry a run anchor or run bundle. Its fingerprint's view-identity position is
the sealed run-local effective-relation identity, not a claim of a ledger
snapshot. `EvaluateResult` also privately pins the attached Scenario-resolution
digest, so a later `dataclasses.replace()` cannot attach metadata that describes
a different hypothetical result. Scenario rows deliberately reject `close()`
and return an unsupported result from `explain()`: the existing
live-EvidenceGraph contract refers to asserted ledger facts and is not valid
evidence for a hypothetical replacement. See
`src/factgraph/application/docs/rule.md` for the replacement-only scope.

The separate F4C `PolicyExplanationViewV0` is intentionally not an
`Explanation` field and is not produced by `EvaluateRow.explain()`. Its normal
composition projects detached F4B3 evidence through a matching
`EvaluationRunAnchorV0`; as a pure value projector, it may also consume another
`EvidenceGraph` that satisfies the same anchor and lineage checks. It does not
create, attach, or change live-Explain lifecycle semantics. See
`src/factgraph/application/docs/rule.md` for that readonly, total-or-error
composition contract. This preserves the existing lazy live-Explain behavior.

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

**S5 evidence invariant** (locked 2026-06-09):

```
status in {"passed", "failed"}  ↔  evidence is not None
status in {"unsupported", "invalid_request"}  ↔  evidence is None
```

`Explanation.__post_init__` enforces this invariant via `ProtocolShapeError`.

Status semantics:

| Status | Meaning |
|---|---|
| `"passed"` | Row passed; `evidence` is a complete `EvidenceGraph(paths=...)` |
| `"failed"` | Logical failure with probe evidence; `evidence` is a probe-result `EvidenceGraph` |
| `"unsupported"` | Request context is invalid (stale row, protocol error); `evidence=None` |
| `"invalid_request"` | Malformed input; `evidence=None` |

`failure_class` is set only when `status == "failed"`:

| Value | Trigger |
|---|---|
| `"closed_head_false"` | Derivation head does not hold; `probe_native` result attached |

Stale rows and rows that no longer belong to their result are protocol/request
problems, not logical failures. They return `status="unsupported"`,
`evidence=None`, and an `ErrorDTO` (`STALE_ROW` or `ROW_NOT_IN_RESULT`).

`Explanation.repr` property returns text lines from `walk_evidence(...)` for
`passed`/`failed` status; returns `None` for `unsupported`/`invalid_request`.

---

### 2.5 Evidence builder dispatch

`_explain_live_row` is protocol-only. It does not import the store or the native
prober directly. The SDK attaches a private row graph builder to native
`EvaluateResult` objects; that builder closes over the lowering plan and
projected view facts and calls `probe_native(...)`.

1. **Native passed row**:
   - `EvaluateRow.explain()` uses the SDK-attached graph builder.
   - The builder returns the prober's paths-model `EvidenceGraph`, including
     head/body rules, atom verdicts, joins, and baked `repr_text`.

2. **Native closed-head false**:
   - `fg.eval.explain(..., head=closed_head)` calls `probe_native(...)` even
     when no result row matches.
   - Returns `status="failed"` with `failure_class="closed_head_false"` and
     non-empty probe evidence.

3. **Protocol fallback**:
   - If no SDK graph builder is attached, protocol builds a minimal paths-model
     `EvidenceGraph` with a single head rule.
   - This fallback preserves the evidence invariant without resurrecting the
     removed flat-DAG model.

4. **Adapter rich rows**:
   - Souffle, ProbLog, and PyReason rows use SDK-attached builders over
     `_row_support_artifacts` / `_row_provenance_envelopes`.
   - Those builders return the same paths-model evidence graph shape as native
     explain paths.

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
- `evaluate_result.py` does not own the prober (`probe_native`); SDK graph builders call it
- `evaluate_result.py` does not own the SDK `EvaluateResult` → `fg.eval.evaluate()` wrapper
- `explanation_render.py` does not produce HTML; it produces plain text
- Adapter converters are outside this module; SDK graph builders dispatch to
  them and pass paths-model graphs back through the protocol surface.

---

## 4. Limitations & Compatibility

- The `expr_digest` flat property was **permanently removed** in Cleanup-β (2026-06-08).  
  All callers must migrate to `result.fingerprint.expr_digest`.
- Other deprecated flat properties (`run_id`, `engine_version`, etc.) still exist but emit `DeprecationWarning`. They will be removed in a future slice.
- Native passed rows and native closed-head-false failures are backed by the
  prober. Souffle, ProbLog, and PyReason rich evidence is wired through
  adapter-specific SDK builders.
- `_row_provenance_envelopes` and `_row_support_artifacts` are private fields and are not part of the stable contract for external callers.

---

## 5. Test Entry Points

```bash
# Core DTO shape + explain invariant + Cleanup-β
python -m pytest tests/application/protocol/test_evaluate_result_dtos.py

# walk_evidence renderer
python -m pytest tests/application/protocol/test_explanation_render.py

# Adapter dispatch (Souffle / ProbLog / PyReason rich provenance)
python -m pytest tests/test_souffle_evidence_graph.py
python -m pytest tests/test_problog_provenance_v0.py
python -m pytest tests/test_pyreason_provenance_v0.py

# SDK exports / fingerprint
python -m pytest tests/sdk/test_evaluate_result_exports.py
```

---

## 6. Related Blueprints

- `workflow/blueprints/active/2026-06-09_explain-layer-s5-native-path.md` — S5 invariant + closed_head_false wiring + stale_row/row_not_in_result → unsupported
- `workflow/blueprints/active/2026-06-09_explain-layer-v2.md` — parent program
