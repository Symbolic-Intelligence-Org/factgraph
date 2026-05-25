# Task Blueprint: T5.3 Explanation Envelope + Live Row Resolver

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-3-explanation-envelope-live-row-resolver.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- Predecessor slices:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.

## 0. Scope Locks

### In scope

- Add public application-protocol `Explanation` DTO per D20 section 4.1.
- Re-export `Explanation` from `factgraph.application.protocol` and `factgraph.sdk`.
- Add live `EvaluateRow.explain()` using the existing T5.1/T5.2 row `_result_resolver`.
- Keep detached row behavior as `DetachedRowError`; detached rows must not return `Explanation(status="invalid_request")`.
- Implement the row-sourced explain path:
  - verify row membership in the owning `EvaluateResult`;
  - verify D19 row/result/evidence anchors;
  - copy D19 replay anchors and D25 semantics scope into `checked_scope` and `EvidenceGraph.metadata`;
  - build or resolve a passed `EvidenceGraph` for supported scoped rows;
  - validate the graph before returning `Explanation(status="passed")`.
- Reuse shipped `factgraph.audit.evidence_graph.EvidenceGraph` as the public evidence object inside `Explanation`.
- Use existing `ErrorDTO` and `WarningDTO` from `factgraph.application.protocol.common`.
- Preserve D20 status/evidence matrix:
  - `status="passed"` iff `evidence is not None`;
  - failed / unsupported / invalid_request states have no evidence graph.
- Implement D25 row-sourced semantics behavior:
  - `row.explain()` accepts no alternate `semantics=`;
  - row-sourced explain reuses the original result `semantics_digest`;
  - `checked_scope` contains the D25 five-key semantics subset.
- Add focused tests for `Explanation` validation, live row explain, detached row explain, graph validation, checked-scope metadata, raw_kind/bound copying, and forbidden future methods.

### Out of scope

- `row.close()`; T5.4 owns it.
- Manual `fg.eval.explain(expr, head=closed_head, ...)`; T5.4 owns it unless a reviewed amendment explicitly combines T5.3 and T5.4.
- Public `.eval.why_not(...)`; D22/T5.5 locks no new public why-not surface.
- Final SDK top-level `Rule` naming flip; T5.6/D24 owns that.
- Legacy hard-cut, service routes, OpenAPI, broad docs migration, and old Check/Diagnose/WhyNot shell removal; T5.7/D23 owns those.
- C73-C78 semantics implementation or adapter production edits; T5.8/D26 or a post-T5 cycle owns adapter-touching work.
- New renderer product contract, `Explanation.render()`, SDK HTML helpers, or public renderer convenience API.
- New SDK-specific graph DTO; D20 requires reuse of shipped `EvidenceGraph`.
- Public exposure of engine-specific `EvidenceNode.engine_meta` / `EvidenceEdge.engine_meta` key contracts.
- New public evidence trace, support, or WhyNot DTO beyond `Explanation`.

### M-to-L triggers

Pause and amend/split if implementation requires:

- broad evidence runtime redesign or new internal evidence graph schema;
- adapter production edits;
- service route/OpenAPI migration;
- public manual explain entrypoint;
- `row.close()`;
- public why-not or renderer surface;
- changing T5.1 `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` field contracts;
- changing T5.2 evaluate return-shape behavior;
- changing D25 semantics mismatch policy;
- changing `Rule.content_digest` or D19 digest formulas.

## 1. Inputs

T5.3 consumes the completed design layer and the first two implementation slices:

- D17 defines the result row envelope, live/detached row boundary, row lineage through `EvidenceRef` / future `EvidenceGraph`, and `DetachedRowError`.
- D19 defines replay anchors and digest source-of-truth. T5.3 must consume those anchors, not recompute them in a second path.
- D20 defines the `Explanation` DTO, status/evidence matrix, live row explain path, `EvidenceGraph` reuse boundary, metadata copying rule, Check/Diagnose substrate policy, graph validation gate, and renderer exclusion.
- D21 owns `row.close()` and manual closed-head explain. T5.3 must not implement either unless the blueprint is amended.
- D22 defines failed Explanation as the v1 why-not envelope and forbids a public `.eval.why_not(...)` in T5 Core.
- D23 owns legacy hard-cut and old Check/Diagnose shell disposition. T5.3 may use Check/Diagnose internally but must not remove or redesign public shells.
- D25 defines row-sourced semantics reuse and the minimum `checked_scope` semantics keys.
- D26 keeps adapter-touching semantics out of T5 Core by default and forbids D25 policy changes.
- T5.1 added `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, digest helpers, and private CandidateSet conversion.
- T5.2 flips public SDK evaluate to `EvaluateResult` and binds live row resolvers through result construction.

Pre-draft shipped-source reads found:

- `src/factgraph/application/protocol/evaluate_result.py` has `EvaluateRow._require_live_result()` but no public `row.explain()` and no `Explanation` DTO.
- `src/factgraph/application/protocol/common.py` already provides `ErrorDTO` and `WarningDTO`.
- `src/factgraph/audit/evidence_graph.py` already provides `EvidenceGraph`, `EvidenceNode`, `EvidenceEdge`, serialization helpers, rendering helpers, and constructor validation for node/edge uniqueness, root presence, edge endpoints, and cycles.
- `src/factgraph/application/protocol/derivation_check.py` and `derivation_diagnose.py` provide legacy Check/Diagnose DTOs that D20 allows as private substrate, not public result type.
- `src/factgraph/sdk/__init__.py` and `src/factgraph/application/protocol/__init__.py` already re-export T5.1 DTOs and are the natural export points for `Explanation`.

## 2. Plan

### 2.1 Add `Explanation` DTO

Add `Explanation` in the application protocol layer, preferably in the existing result DTO module unless Step 4.6 shows a cleaner module boundary.

Required fields:

```python
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

Validation rules:

- `status` must be one of the four D20 states.
- `status="passed"` iff `evidence is not None`.
- `passed` requires `claim`; row-sourced passed explanations require `result_id`, `row_id`, and `evidence_ref_id`.
- `failed` requires one of the five D20 business `failure_class` values and `evidence is None`.
- `unsupported` and `invalid_request` require non-empty `errors` and `evidence is None`.
- `failure_class` must be `None` except on `status="failed"`.
- `raw_kind` / `bound` follow the existing T5.1 carrier invariant: `raw_kind is None` iff `bound is None`.
- `errors` and `warnings` are tuples of existing `ErrorDTO` / `WarningDTO`.
- `checked_scope`, when present, is frozen to prevent caller mutation.

### 2.2 Export `Explanation`

Add application protocol and SDK re-exports:

```python
from factgraph.application.protocol import Explanation
from factgraph.sdk import Explanation
```

Do not change the SDK `Rule` / `LegacyRule` / `ApplicationRule` namespace.

### 2.3 Add live `EvaluateRow.explain()`

Add a public no-argument method:

```python
def explain(self) -> Explanation: ...
```

Behavior:

- calls `_require_live_result()`;
- raises `DetachedRowError` for detached rows;
- does not accept `semantics=`, `engine=`, `head=`, or other replay kwargs;
- delegates to a private row explanation helper using the owning `EvaluateResult`.

The method must not add `row.close()` and must not expose a manual explain entrypoint.

### 2.4 Row membership and anchor validation

The row explanation helper verifies:

- the row belongs to the owning result by `row_id`;
- `row.evidence_ref.result_id == result.result_id`;
- `row.evidence_ref.row_id == row.row_id`;
- `row.evidence_ref.fact_digest == row.claim.digest`;
- `row.claim.digest` is present and stable;
- `row.evidence_ref.ref_id` is present;
- `row.evidence_ref.closed_head_digest` is present;
- result anchors are present:
  - `expr_digest`;
  - `rule_set_digest`;
  - `view_snapshot_digest`;
  - `semantics_digest`;
  - `result_digest`;
  - `engine`;
  - `engine_version`;
  - `adapter_version`;
  - `evaluated_at`.

If membership fails, return `Explanation(status="failed", failure_class="row_not_in_result", ...)` for a live but mismatched row/result context. Detached rows still raise `DetachedRowError`.

If required anchor data is malformed or missing because of an implementation/runtime gap, return `Explanation(status="invalid_request", errors=(...))` unless DTO construction already raises a protocol error earlier.

### 2.5 Build passed row-sourced `EvidenceGraph`

T5.3 must reuse shipped `factgraph.audit.evidence_graph.EvidenceGraph`.

For the first implementation slice, a minimal passed graph is acceptable if it is valid and uses only stable public row/result data:

- one conclusion/root node representing the explained row claim;
- zero or more premise/support nodes only if existing runtime support substrate is readily available without redesign;
- metadata copied from the evaluated context;
- `support_kind` set to a stable T5 row-explain support label.

Graph validation relies on the shipped `EvidenceGraph` constructor and may add private metadata sufficiency checks. If graph construction or validation fails, T5.3 must return:

- `Explanation(status="unsupported", evidence=None, errors=(ErrorDTO(code="GRAPH_VALIDATION_FAILED", ...),))`

It must not return a partial `EvidenceGraph`.

### 2.6 Metadata and checked scope

`EvidenceGraph.metadata` must copy from a single row/result context. At minimum include:

- `result_id`;
- `row_id`;
- `evidence_ref_id`;
- `claim_digest`;
- `closed_head_digest`;
- `expr_digest`;
- `rule_set_digest`;
- `view_snapshot_digest`;
- `semantics_digest`;
- `result_digest`;
- `engine`;
- `engine_version`;
- `adapter_version`;
- `evaluated_at`.

`Explanation.checked_scope` must include the D25 semantics subset for row-sourced explanations:

```python
{
    "semantics_digest": result.semantics_digest,
    "semantics_source": "row_result",
    "evaluate_semantics_digest": result.semantics_digest,
    "explain_semantics_digest": result.semantics_digest,
    "semantics_match": True,
}
```

It may also include the D19 anchors listed above. It must not set `semantics_match=False` in a returned `Explanation`.

### 2.7 Carrier copying

For row-sourced explanations:

- copy `raw_kind` from the row;
- copy `bound` from the row;
- do not recompute quantitative carriers;
- do not use raw_kind/bound as a semantics consistency proof.

### 2.8 Check/Diagnose substrate boundary

T5.3 may call existing Check/Diagnose internals if useful, but:

- `row.explain()` returns `Explanation`, not `CheckResult` or `DiagnoseResult`;
- `DiagnoseResult`, atom locators, and old why-not DTOs must not be embedded in `Explanation`;
- public Check/Diagnose/WhyNot shell disposition remains T5.7.

### 2.9 Implementation ordering

Recommended local order:

1. Add `Explanation` DTO and validation tests.
2. Add protocol/SDK re-exports.
3. Add row explain helper and `EvaluateRow.explain()`.
4. Add minimal valid EvidenceGraph builder for row-sourced passed explanations.
5. Add metadata / checked_scope copying.
6. Add graph validation failure and detached-row tests.
7. Run focused tests, G7 preservation, and ruff.

## 3. Code Changes

Likely production files:

- `src/factgraph/application/protocol/evaluate_result.py`
  - `Explanation` DTO;
  - `EvaluateRow.explain()`;
  - private row explanation helper;
  - private metadata / checked_scope helper;
  - minimal row EvidenceGraph builder.
- `src/factgraph/application/protocol/__init__.py`
  - `Explanation` export.
- `src/factgraph/sdk/__init__.py`
  - `Explanation` re-export.

Possible but not required:

- a new `src/factgraph/application/protocol/explanation.py` module if Step 4.6 or implementation complexity favors separation.

Files explicitly out of target scope unless amended:

- `src/factgraph/sdk/store.py` public evaluate behavior;
- service route / OpenAPI / agent files;
- adapter production files;
- old Check/Diagnose/WhyNot shells;
- SDK final `Rule` namespace files;
- docs final migration.

## 4. Tests

Minimum focused tests:

1. `Explanation(status="passed", evidence=EvidenceGraph(...))` validates.
2. `Explanation(status="passed", evidence=None)` is rejected.
3. `Explanation(status="failed", evidence=...)` is rejected.
4. `Explanation(status="failed")` requires one of the five D20 failure classes.
5. `Explanation(status="unsupported")` and `invalid_request` require errors.
6. `Explanation.raw_kind` / `bound` preserve the T5 carrier invariant.
7. Application protocol and SDK re-export `Explanation`.
8. Live `EvaluateRow.explain()` returns `Explanation(status="passed")` for a row produced by `fg.eval.evaluate(...)`.
9. Returned passed Explanation includes an `EvidenceGraph` whose root node is present and whose metadata includes D19 anchors.
10. `checked_scope` contains the D25 row-sourced five-key semantics subset.
11. `Explanation.raw_kind` / `bound` are copied from the row.
12. Detached row `explain()` raises `DetachedRowError`.
13. Graph validation failure path returns `Explanation(status="unsupported", errors=(...))` and no evidence graph, if a private injection seam is used for testing.
14. `row.explain()` accepts no `semantics=`, `engine=`, or other kwargs.
15. `row.close()` remains absent.
16. No public `.eval.why_not(...)` is introduced.
17. Existing T5.2 evaluate return-shape tests remain green.

G7 preservation baseline before feat:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected inherited baseline: 166 tests OK from T5.2 archive.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Minimal EvidenceGraph could overpromise internal evidence topology. | Use only stable row/result metadata; do not expose engine_meta key contract; defer richer topology to future evidence-tree cycle. |
| `row.explain()` accidentally becomes manual replay or alternate semantics API. | No kwargs; D25 row-sourced semantics reuse only; T5.4 owns manual explain. |
| Graph validation failure blurs with business failure. | D20 says graph validation is `unsupported` with errors, not `failure_class`. |
| Old Check/Diagnose DTOs leak into public Explanation. | Keep them private substrate only; tests assert Explanation shape. |
| T5.3 reopens T5.2 evaluate behavior. | Use existing live result resolver; do not change public evaluate return shape. |
| T5.3 reopens T5.4 closed-head work. | No `row.close()` and no manual explain entrypoint. |
| Renderer product API leaks early. | No `Explanation.render()` or SDK HTML helpers; audit rendering helpers remain advanced utilities. |
| Adapter-specific evidence details become public. | Keep engine_meta key names audit-facing and non-contract. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates T5.3 scope does not absorb T5.4 manual explain / row.close.
- Reviewer validates minimal passed EvidenceGraph is acceptable for this slice.
- Reviewer validates no renderer, why-not, service, docs, adapter, or final Rule flip scope leak.

### Step 4.6 grep gate

Before scoped:

- search `Explanation`, `row.explain`, `EvidenceGraph`, `checked_scope`, `failure_class`, Check/Diagnose/WhyNot, renderer, `row.close`, manual explain, SDK exports, and service/docs guard words;
- classify all hits;
- record results in paired audit;
- amend blueprint if unexpected collisions appear.

### G7 baseline gate

After scoped:

- run inherited G7 preservation command;
- expected baseline is 166 tests OK;
- record pytest deferred and `tests.test_public_inference_factgraph_create` exclusion.

### Feature gate

Run:

- focused T5.3 Explanation / row explain tests;
- T5.2 evaluate return-shape focused tests;
- updated G7 preservation suite;
- touched-file ruff for production and tests.

Pytest remains deferred per existing SIGSEGV environment lock unless environment constraints change.

## 7. Rollback

Rollback must preserve T5.1/T5.2 substrates:

- If `Explanation` DTO validation is wrong, revert T5.3 DTO/export changes without changing `EvaluateResult`.
- If `row.explain()` fails, remove the method and private helper together; do not leave a public method returning placeholder data.
- If graph construction is too broad, keep `Explanation` DTO work and split graph resolver into a reviewed follow-up only after amendment.
- Do not revert T5.2 public evaluate hard-cut.
- Do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.3 may add narrow API docs/tests only if needed for local coherence.

Deferred:

- final docs migration and examples rewrite remain T5.7;
- renderer product docs remain out of T5 Core;
- manual explain docs remain T5.4;
- final SDK `Rule` naming docs remain T5.6/T5.7.

## 9. Reviewer Focus

- Is a minimal row-sourced passed `EvidenceGraph` enough for T5.3, or should this split before scoped?
- Does `row.explain()` stay strictly row-sourced with no kwargs?
- Are D20 status/evidence matrix and D25 checked_scope keys represented precisely?
- Does the plan avoid `row.close()` and manual explain?
- Does the plan reuse shipped `EvidenceGraph` without making engine_meta keys public contract?
- Are Check/Diagnose kept private substrate rather than parallel public answer types?
- Are service/docs/renderer/why-not/final Rule flip boundaries preserved?

## 10. Outcome

Pending implementation.
