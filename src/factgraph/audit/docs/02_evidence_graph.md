# EvidenceGraph (audit)

- Scope: `src/factgraph/audit/evidence_graph.py`
- Last updated: 2026-06-08 (rewritten — old flat-DAG model removed)
- Audience: developers implementing cross-engine explainability consumers

## 1. Role

`factgraph.audit.evidence_graph` is a **thin re-export** of the canonical
paths-model types from `factgraph.application.explain`.

It exports:

```python
from factgraph.audit.evidence_graph import (
    EvidenceGraph,
    EvidenceTimeline,
    EvidenceTree,
    LAYOUT_TIMELINE,
    LAYOUT_TREE,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
```

All canonical type definitions and prober types live in
`src/factgraph/application/explain/evidence_tree.py`.
See `src/factgraph/application/explain/docs/README.md` for the full type reference.

## 2. Current data model

The v1 paths model uses a nested tree structure in place of the old flat
node/edge DAG:

```
EvidenceGraph
  paths: tuple[EvidenceTree | EvidenceTimeline, ...]
  certainty: Certainty | None
  metadata: Mapping[str, Any]

EvidenceTree
  rules: tuple[EvidenceRule, ...]
  joins: tuple[EvidenceJoin, ...]     # reserved, always () in practice
  status: str                         # "holds" | "fails" | "not_reached"
  certainty: Certainty | None

EvidenceRule
  occurrence_alias: str
  rule_id: str
  role: str                           # "head" | "body"
  status: str
  ports: Mapping[str, Any]            # {port_name: bound_value}
  atoms: tuple[EvidenceAtom, ...]

EvidenceAtom
  form: Fact | Compare | Builtin | Aggregate
  verdict: Holds | Fails | NotReached
  atom_id: str
  repr_text: str | None
```

For timeline paths (PyReason), `paths` contains `EvidenceTimeline` instances.

**Removed in S6d (2026-06-09)**: the previous flat graph shape, its node/edge
DTOs, root pointer, and node-kind / edge-kind enumeration constants. The audit
surface now exposes only the paths model shown above.

## 3. `metadata` for row-result explanations

When an `EvidenceGraph` is produced by `EvaluateRow.explain()`, its `metadata`
carries the v1 row-result audit bridge keys:

| Key | Meaning |
|---|---|
| `result_id` | owning `EvaluateResult.result_id` |
| `row_id` | explained `EvaluateRow.row_id` |
| `evidence_ref_id` | compatibility reference id derived from result, row, claim, and closed-head digests |
| `claim_digest` | row claim digest |
| `closed_head_digest` | closed-head digest |
| `expr_digest` | evaluated expression digest (from `ResultFingerprint.expr_digest`) |
| `rule_set_digest` | rule set digest |
| `view_snapshot_digest` | database/view snapshot digest |
| `config_digest` | semantics profile digest, or `None` |
| `result_digest` | full result digest |
| `engine` | engine id |
| `engine_version` | engine version, or `None` |
| `adapter_version` | adapter version, or `None` |
| `evaluated_at` | JSON-safe evaluated timestamp |

Graphs produced by adapter converters (`problog_trace_to_evidence_graph`,
`pyreason_trace_to_evidence_graph`, etc.) have adapter-specific metadata shapes.
The row-result keys above apply only to graphs returned by `EvaluateRow.explain()`.

## 4. Layout hints

| Constant | Value | Used by |
|---|---|---|
| `LAYOUT_TREE` | `"tree"` | Native, Souffle, ProbLog |
| `LAYOUT_TIMELINE` | `"timeline"` | PyReason |

## 5. Serialization

```python
evidence_graph_to_dict(graph: EvidenceGraph) -> dict[str, Any]
evidence_graph_from_dict(d: dict[str, Any]) -> EvidenceGraph
```

Round-trip helpers for durable storage. These are canonical at
`factgraph.application.explain` and re-exported here for compatibility.

## 6. Validation

`EvidenceGraph.__post_init__` performs:

- `layout_hint` must be `LAYOUT_TREE` or `LAYOUT_TIMELINE`
- `paths` must be a non-empty tuple
- `graph_id`, `engine` must be non-empty strings
- `subject_binding` and `metadata` are shallow-frozen via `MappingProxyType`

`evidence_graph_from_dict` performs structural shape validation only.

## 7. Boundaries

- `factgraph.audit.evidence_graph` is now a re-export façade only; all type
  implementations are in `factgraph.application.explain`.
- HTML rendering is outside `factgraph.audit`; delivery-specific renderers live
  in domain or service packages.
- `AuditQuery.get_candidate_evidence_graph` is a domain-layer (host application)
  API, not part of the kernel audit package.
- Engine-native provenance carriers (`SouffleProofTreeV0`, `ProbLogTraceV0`,
  `PyReasonTraceV0`) are not replaced by `EvidenceGraph`; they are converter
  inputs that produce `EvidenceGraph` output.
- Rich adapter topology population for native/Souffle Form 1 rows is deferred.
  Current baseline returns a minimal head-atom tree for these paths.

## 8. Related documents

- `src/factgraph/application/explain/docs/README.md` — full type reference
- `src/factgraph/application/protocol/docs/README.md` — `EvaluateRow.explain()` contract
- `workflow/blueprints/archive/2026-06-08_explain-layer-s3-prober.md` — S3 paths model origin
