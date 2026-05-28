# D20 Decision: T5 Explanation Envelope and EvidenceGraph Integration

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks public `Explanation` envelope, row explain resolution, manual explain entrypoint, EvidenceGraph boundary, and Check/Diagnose integration policy.
- Implementation Anchors: T5.3 explanation envelope feat `53551cb6`, T5.4 manual explain feat `c820f102`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q6, Q8, F4, F6, F7, and section 6 C66-C67 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.6, 4.7, and 4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.1, 4.5, 4.8, and 7.3.
  - D18 `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md` sections 4.1-4.8.
  - D19 `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md` sections 4.2-4.8.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` sections 5.8.3, 5.8.5, C66-C68, C69, and C72.
  - Sibling future-design note `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md:1285-1415`, `:1542-1596`, `:1620-1690`, `:2282-2338`, and `:2349-2392`.
  - Shipped `src/factgraph/application/protocol/derivation_check.py:62-160`, `src/factgraph/application/protocol/derivation_diagnose.py:1-220`, and `src/factgraph/audit/evidence_graph.py:24-160`.
- Outputs / Downstream:
  - D21 `row.close()` and closed-head construction.
  - D22 why-not disposition.
  - D23 legacy SDK hard-cut plan.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and explanation implementation blueprint(s).
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16, D17, D18, and D19 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C67 wants a public `Explanation` envelope with four states and an optional `EvidenceGraph`. Stage 1 audit found three shipped ingredients but no unified public envelope:

- `CheckResult` has the same four-state vocabulary and an `EvidenceEnvelope`, but it does not carry result lineage, claim, row id, evidence ref id, checked scope, or suggested next steps.
- `DiagnoseResult` has a failure-focused atom locator, but evidence-tree v1 explicitly marks that style as lossy and unsuitable for public failed explanations.
- `audit.evidence_graph.EvidenceGraph` exists with nodes, edges, support kind, metadata, serialization, rendering, and cycle checks, but it is not wrapped in a row-centric `Explanation`.

D17 reserves `Explanation` as a public application-protocol DTO with SDK re-export. D19 locks the replay anchors and digest sources. D20 decides the public envelope and integration behavior.

Evidence-tree v1 remains non-authoritative sibling input, but D20 deliberately adopts a small subset that affects the public T5 envelope:

- two explain entries: live row and manual closed-head replay;
- `DetachedRowError` for detached rows;
- `status="passed"` iff `evidence is not None`;
- failed / unsupported / invalid request explanations never return partial evidence graphs;
- evidence graph metadata is copied from one evaluated context source, not recomputed independently;
- graph validation failure maps to `unsupported`, not a corrupted partial graph.

D20 does not adopt evidence-tree v1 internal `engine_meta` schema, audit channel, renderer product contract, or deferred topology internals.

## 2. Scope

This decision locks:

- public `Explanation` DTO ownership and field surface;
- `row.explain()` / `result[i].explain()` behavior for live and detached rows;
- advanced `fg.eval.explain(expr, head=closed_head, ...)` output shape and minimum context policy;
- relationship between `Explanation.status`, `Explanation.evidence`, `failure_class`, `errors`, and `warnings`;
- how shipped Check / Diagnose substrates feed or do not feed `Explanation`;
- whether `EvidenceGraph` is the public evidence object and what part of it is stable;
- metadata source-of-truth copying from `EvaluateResult` / manual context into `EvidenceGraph.metadata`.

## 3. Non-Scope

This decision does not lock:

- `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, or `DetachedRowError` field surfaces; D17 owns them;
- digest formulas and source fields; D19 owns them;
- `row.close()` construction of closed-head Rules; D21 owns it;
- why-not public surface disposition; D22 owns it;
- old API hard-cut mechanics and service-route update plan; D23 owns them;
- final SDK `Rule` naming; D24 owns it;
- evaluate/explain semantics mismatch policy; D25 owns it;
- C73-C78 semantics implementation; D26 owns it;
- full EvidenceNode / EvidenceEdge internal schema implementation; a later evidence-tree cycle owns it;
- rendering API convenience wrappers; D20 only permits reuse of existing audit rendering helpers as advanced utilities.

## 4. Decision

### 4.1 `Explanation` is a public application-protocol DTO with SDK re-export

The authoritative `Explanation` definition lives in `factgraph.application.protocol`, with SDK re-export:

```python
from factgraph.application.protocol import Explanation
from factgraph.sdk import Explanation
```

D20 adopts this public field surface:

```python
@dataclass(frozen=True)
class Explanation:
    status: Literal["passed", "failed", "unsupported", "invalid_request"]
    evidence: EvidenceGraph | None
    claim: Claim | None
    result_id: str | None
    row_id: str | None
    evidence_ref_id: str | None
    raw_kind: Literal["probabilistic", "possibilistic"] | None = None
    bound: tuple[float, float] | None = None
    failure_class: Literal[
        "no_matching_row",
        "closed_head_false",
        "stale_row",
        "row_not_in_result",
        "insufficient_closed_bindings",
    ] | None = None
    checked_scope: Mapping[str, object] | None = None
    suggested_next_steps: tuple[str, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
```

`claim` is nullable only for invalid requests that fail before a claim can be resolved. Row-sourced and successful manual explanations must carry a `Claim`.

`evidence_ref_id` is the row's `EvidenceRef.ref_id`, not the full `EvidenceRef` object. D17 keeps `EvidenceRef` row-local and not an explain entrypoint. D20 avoids duplicating row metadata inside `Explanation`.

`raw_kind` and `bound` are copied from the evaluated row or manual context when available. D20 does not decide semantics consistency or carrier projection; D25/D26 own that.

### 4.2 Status matrix is strict

D20 locks the status matrix:

| status | evidence | failure_class | errors | claim / lineage |
|---|---|---|---|---|
| `passed` | `EvidenceGraph` required | `None` | empty unless non-fatal warnings exist | claim required; result/row refs present for row path, nullable for manual path |
| `failed` | `None` | one of the 5 business failure classes | empty | claim present when resolvable; `checked_scope` and `suggested_next_steps` expected |
| `unsupported` | `None` | `None` | non-empty | claim optional |
| `invalid_request` | `None` | `None` | non-empty | claim optional |

`status="passed"` if and only if `evidence is not None`. No failed, unsupported, or invalid request `Explanation` may return a placeholder, partial, or corrupted `EvidenceGraph`.

`failure_class` is exclusively for business semantic failures:

- `no_matching_row`;
- `closed_head_false`;
- `stale_row`;
- `row_not_in_result`;
- `insufficient_closed_bindings`.

Engine witness gaps, unsupported adapters, graph validation failures, malformed manual contexts, and call-shape problems do not enter `failure_class`; they go to `errors` with `status="unsupported"` or `status="invalid_request"`.

### 4.3 Live row explain is the primary path; detached row is an exception

`EvaluateRow.explain()` and `EvaluateResult.__getitem__(...).explain()` are the primary explanation path.

For a live row, `_result_resolver` returns the owning `EvaluateResult`. The explanation resolver then:

1. verifies the row belongs to that result;
2. verifies D19 anchors such as `result_id`, `row_id`, `claim.digest`, `EvidenceRef.ref_id`, `closed_head_digest`, `view_snapshot_digest`, `rule_set_digest`, and `semantics_digest`;
3. prepares the evidence context;
4. builds or resolves an `EvidenceGraph`;
5. returns `Explanation`.

For a detached row, `row.explain()` raises `DetachedRowError`. It must not return `Explanation(status="invalid_request")`, because D17 classifies detached resolver use as a programming error, not a business failure or explain pipeline outcome.

### 4.4 Manual `fg.eval.explain(expr, head=closed_head, ...)` is advanced replay

D20 adopts an advanced manual replay entry:

```python
fg.eval.explain(expr, head=closed_head, engine=..., semantics=..., ...) -> Explanation
```

The `head` argument is a closed application head Rule. D21 owns `row.close()` and exact closed-head construction. D20 only locks that manual explain consumes a closed head and returns `Explanation`.

Manual replay has no row back-reference. Therefore:

- `row_id` is `None`;
- `evidence_ref_id` is `None`;
- `result_id` may be a temporary manual-context id or `None`, depending on implementation;
- stale-row checks degrade to closed-head / context checks rather than row membership checks.

Manual replay must carry or derive the minimum D19 context needed to build `EvidenceGraph.metadata`: engine, semantics, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `evaluated_at`, and closed-head digest input. Missing minimum context returns `Explanation(status="invalid_request", errors=(...))`, not a partially populated passed explanation.

### 4.5 `EvidenceGraph` is public inside `Explanation`, but internal metadata is audit-facing

D20 uses shipped `factgraph.audit.evidence_graph.EvidenceGraph` as the type of `Explanation.evidence`.

Stable public contract:

- `Explanation.evidence` is either an `EvidenceGraph` or `None`;
- `EvidenceGraph` remains immutable and serializable through existing audit helpers;
- graph construction must respect shipped node / edge uniqueness, endpoint, and cycle validation;
- `EvidenceGraph.metadata` contains durable replay context copied from the evaluated context.

Audit-facing / advanced contract:

- `EvidenceNode.engine_meta` and `EvidenceEdge.engine_meta` may carry engine-specific details;
- evidence-tree v1 internal key names are not promoted to narrow SDK public API by D20;
- user docs may describe high-level evidence behavior, but must not promise stable engine-specific `engine_meta` keys unless a later evidence-tree cycle adopts them.

D20 does not add a new SDK-specific graph type. It rejects per-engine `EvidenceGraph` classes and a separate `ExplanationTree` DTO.

### 4.6 EvidenceGraph metadata is copied from one evaluated context

D20 adopts the evidence-tree v1 single-source metadata invariant.

For row-sourced explanations, `EvaluateResult` plus the row and `EvidenceRef` form the evaluated context. For manual explanations, the caller-supplied / derived manual context forms the evaluated context.

The orchestrator copies metadata from that context into `EvidenceGraph.metadata`; it must not independently recompute metadata fields in a second path. Required metadata includes the D19 replay anchors needed by D20/D25:

- `schema_version`;
- `evaluated_at`;
- `engine`;
- `engine_version`;
- `adapter_version`;
- `expr_digest`;
- `rule_set_digest`;
- `view_snapshot_digest`;
- `semantics_digest`;
- `result_id`;
- `row_id`;
- `claim_digest`;
- `evidence_ref_id`;
- closed-head digest information.

D20 does not require the exact 15-field evidence-tree v1 metadata list to be public SDK API. It requires implementation to keep the metadata sufficient for replay, drift checks, and D25 semantics consistency.

### 4.7 Check and Diagnose become internal substrates for Explanation, not parallel public answers

`CheckResult` may be used internally to validate whether a closed head / binding holds and to obtain a support envelope. It is not returned from `row.explain()` or `fg.eval.explain(...)`.

`DiagnoseResult` and `DiagnoseAtomLocator` are not embedded in `Explanation(status="failed")`. The failed envelope uses `failure_class`, `checked_scope`, and `suggested_next_steps`, because the shipped atom locator is lossy and evidence-tree v1 explicitly rejects atom-level failed evidence for v1.

D23 owns whether old public check / diagnose shells remain temporarily, are hidden, or are hard-cut. D20 only locks that the T5 explanation target is `Explanation`, not public `CheckResult` / `DiagnoseResult`.

### 4.8 Graph validation gate is mandatory

Before returning `Explanation(status="passed")`, the implementation must validate the `EvidenceGraph`.

At minimum, validation includes shipped `EvidenceGraph` invariants:

- unique node ids;
- unique edge ids;
- root node present;
- all edge endpoints present;
- no cycles.

T5 may add private validator checks for metadata sufficiency and required context fields. If graph validation fails, the output is:

```python
Explanation(
    status="unsupported",
    evidence=None,
    errors=(ErrorDTO(code="GRAPH_VALIDATION_FAILED", ...),),
    ...
)
```

It must not return a partial graph with warnings.

### 4.9 Rendering remains an audit utility, not an Explanation method

Existing `render_evidence_graph_html(...)`, `evidence_graph_to_dict(...)`, and `evidence_graph_from_dict(...)` remain audit helpers. D20 does not add:

- `Explanation.render()`;
- `row.render_explanation()`;
- SDK-specific HTML rendering helpers;
- a new public renderer surface.

Implementation docs may point advanced users to audit rendering helpers, but the T5 public API remains row / manual explain returning `Explanation`.

## 5. Rejected Alternatives

### Option A: Return `CheckResult` from `row.explain()`

Rejected. `CheckResult` lacks claim, row lineage, failure envelope, checked scope, and `EvidenceGraph`.

### Option B: Return `DiagnoseResult` for failed explanations

Rejected. `DiagnoseAtomLocator` is intentionally not the v1 failed explanation model. It is lossy and can mislead users into thinking one atom is the definitive cause.

### Option C: Put full `EvidenceRef` on `Explanation`

Rejected. D17 defines `EvidenceRef` as row-local metadata and not an explain entrypoint. `Explanation` carries `evidence_ref_id` as lineage, avoiding duplicate row metadata.

### Option D: Always construct EvidenceGraph, including failed states

Rejected. Parent C67 and evidence-tree v1 C81/C132 require evidence only for `passed`; failed / unsupported / invalid request states use envelope fields and errors, not placeholder graphs.

### Option E: Expose engine-specific `engine_meta` keys as SDK public contract

Rejected. D20 uses `EvidenceGraph` publicly but keeps engine metadata audit-facing. Full evidence-tree schema adoption belongs to a later evidence-tree cycle.

### Option F: Make graph validation best-effort

Rejected. Returning partial or corrupt evidence undermines replay and audit trust. Validation failure maps to `unsupported` with errors.

### Option G: Add `Explanation.render()` in D20

Rejected. Rendering is useful, but D20 is the envelope decision. Existing audit rendering helpers are sufficient until a future UI/rendering decision.

### Option H: Treat detached rows as invalid_request Explanation

Rejected. D17 locks detached resolver use as `DetachedRowError`, a programming error. It must not enter the explanation status matrix.

## 6. Supporting Evidence

| Evidence | Source | D20 conclusion |
|---|---|---|
| Parent `Explanation` has four statuses, evidence only on passed, claim and lineage fields, failure envelope, errors, and warnings. | `rule-expression-and-proof-attempt.zh.md:1160-1245` | D20 adopts the public envelope and makes claim nullable only for pre-claim invalid requests. |
| `CheckResult` has four-state status and `EvidenceEnvelope`, but not the T5 row-centric fields. | `src/factgraph/application/protocol/derivation_check.py:62-160` | Check can be an internal substrate, not the public explanation output. |
| `DiagnoseResult` owns `DiagnoseAtomLocator` and intentionally lacks EvidenceEnvelope. | `src/factgraph/application/protocol/derivation_diagnose.py:1-220` | Failed Explanation should not embed the atom locator. |
| Shipped `EvidenceGraph` already has nodes, edges, support kind, metadata, serialization, rendering, and validation. | `src/factgraph/audit/evidence_graph.py:24-160` | D20 reuses it rather than inventing a second graph DTO. |
| Evidence-tree v1 explains the two-entry orchestrator, DetachedRowError, validator gate, and passed/evidence iff invariant. | `evidence-tree-rainbird-style-v1.zh.md:1285-1415`, `:1542-1596` | D20 adopts those public-envelope-relevant constraints. |
| Evidence-tree v1 marks failed explanations as envelope-only with five failure classes. | `evidence-tree-rainbird-style-v1.zh.md:2282-2338` | D20 keeps failed evidence `None` and uses `failure_class`. |
| D19 locks replay anchors and digest sources. | D19 sections 4.2-4.8 | D20 consumes, not recomputes, result/row/evidence/context digests. |

## 7. Consequences

### 7.1 Downstream D-docs

- D21 must make `row.close()` produce closed heads that D20 manual explain can consume.
- D22 must decide whether why-not folds into `Explanation(status="failed")` or remains a separate public surface.
- D23 must account for old Check / Diagnose public shells after D20 makes `Explanation` the primary explain target.
- D25 must use `checked_scope` and `semantics_digest` when defining evaluate/explain semantics mismatch behavior.
- D26 must not require D20 to expose engine-specific `engine_meta` keys as SDK public contract.

### 7.2 Implementation constraints

T5 implementation needs:

- public `Explanation` DTO in application protocol and SDK exports;
- row resolver plumbing that can build a context from `EvaluateResult` and `EvaluateRow`;
- manual explain context validation;
- private conversion from support / runtime evidence into `EvidenceGraph`;
- graph validation before returning passed Explanation;
- docs that explain failed / unsupported / invalid request distinction without promising atom-level why-not trees.

### 7.3 Stage 3 synthesis

Stage 3 must not schedule row explain implementation before D17/D19 DTO and digest helpers exist. It may schedule `Explanation` DTO scaffolding before full graph building only if public evaluate does not expose row explain until the graph path and failure matrix are implemented.

## 8. Acceptance Criteria

- [ ] `Explanation` field surface is locked and re-export location follows D17.
- [ ] `status="passed"` iff `evidence is not None`; all other statuses have `evidence=None`.
- [ ] `failure_class` appears only on `status="failed"` and uses the five-class enum.
- [ ] Detached rows raise `DetachedRowError`, not invalid-request Explanation.
- [ ] D20 consumes D19 replay anchors without adding duplicate digest formulas.
- [ ] `EvidenceGraph` is reused, but `engine_meta` keys are not promoted to narrow SDK public API.
- [ ] Check / Diagnose are internal substrates or legacy shells, not public output for T5 explain.
- [ ] Graph validation failure maps to `unsupported` with no partial graph.
- [ ] Rendering remains an audit helper, not an `Explanation` method.

## 9. Decision Record

| Date | State | Reviewer / Commit | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Codex draft | Initial D20 explanation envelope decision. Locks public `Explanation` field surface, row and manual explain entrypoints, status/evidence matrix, EvidenceGraph reuse boundary, Check/Diagnose integration policy, and graph validation gate. |
