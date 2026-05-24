# D10 — T3 Later Evaluation Result / Evidence Boundary

Status: proposed

Inputs:

- Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md` Q8, F8, F9, F10, and §10 D10 mapping.
- D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`.
- D7 `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`.
- D8 `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`.
- D9 `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`.
- D5 `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.8 execution-lowering deferral.
- Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §4.9, §5.1-§5.4, and T5 result/evidence commitments.
- Shipped `src/factgraph/core/derivation/candidates.py:13-30`.
- Shipped `src/factgraph/application/derivation_runtime.py:69-89`.
- Shipped `src/factgraph/sdk/store.py:2197-2298`.
- Shipped `src/factgraph/core/store/_support.py:96-104`, `:201-226`.
- Shipped `src/factgraph/core/store/_support_capture.py:29-62`.
- Shipped `src/factgraph/application/protocol/derivation_check.py:62-81`.

Outputs:

- D10 locks the public result shape for T3 later RuleExpr execution.
- D10 locks the private provenance/evidence preservation floor required by D7/D8/D9.
- D10 defines the boundary between T3 later and future T5 EvaluateResult / WhyNot redesign.

Related modules:

- `src/factgraph/sdk/store.py`
- `src/factgraph/application/derivation_runtime.py`
- `src/factgraph/core/derivation/candidates.py`
- `src/factgraph/core/store/_support.py`
- `src/factgraph/core/store/_support_capture.py`
- future T3 later lowering implementation modules chosen by Stage 3 synthesis

Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`

Depends on:

- D6 reviewed entrypoint/head boundary.
- D7 reviewed lowering plan shape.
- D8 reviewed join lowering semantics.
- D9 reviewed adapter matrix and rejection policy.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

Lifecycle:

- `proposed`: this draft records the intended decision.
- `reviewed`: Claude Step 4.2 review has passed.
- `adopted`: Stage 3 synthesis / first dependent implementation blueprint adopts it as binding.
- `superseded`: later T5 EvaluateResult / WhyNot design replaces this boundary.

## 1. Decision Driver

Stage 1 audit Q8 asks whether T3 later preserves alias, occurrence, join, and OR-branch identity in support artifacts, or only returns existing `CandidateSet` rows.

D10 answers with a two-layer boundary:

1. Public T3 later evaluation returns existing `list[CandidateSet]` values.
2. T3 later lowering preserves RuleExpr provenance through private trace metadata that can be consumed by future T5 EvaluateResult / WhyNot work.

This keeps T3 later executable without forcing the T5 public result redesign into the current tranche.

## 2. Scope

D10 decides:

- public success return shape for `fg.eval.evaluate(application_rule_or_rule_expr, head=...)`;
- whether a public RuleExpr-specific result wrapper exists in T3 later;
- minimum internal trace/provenance categories that must survive lowering and adapter execution;
- how D7 branch ids align with shipped runtime branch indexes and support artifact atom keys;
- how D8 explicit-join materialization metadata remains available for future evidence;
- how D9 preflight rejections relate to success results;
- what remains explicitly T5 scope.

## 3. Non-Scope

D10 does not decide:

- T5 `EvaluateResult` public DTO shape;
- T5 `fg.eval.why_not(...)` public API;
- proof-frame / WhyNot narrative format;
- public lower/debug APIs;
- adapter grammar support; D9 owns it;
- join lowering semantics; D8 owns it;
- head / closed-head semantics beyond D6 minimal head subset.

## 4. Decision

### 4.1 Public T3 later success result remains `list[CandidateSet]`

`fg.eval.evaluate(application_rule_or_rule_expr, head=...)` returns the same public success shape as existing derivation evaluation: `list[CandidateSet]`.

D10 does not introduce:

- `RuleExprEvaluateResult`;
- `EvaluateResult`;
- a public result wrapper around `CandidateSet`;
- public tuple/dict wrapping of candidates plus provenance;
- SDK `__all__` exports for RuleExpr execution results.

Rationale:

- shipped `_SDKEvalManager.evaluate(...)` already returns `list[CandidateSet]`;
- shipped `evaluate_derivation_plans(...)` returns flattened `CandidateSet` objects with no application-side wrapper;
- T5 owns the durable public result redesign and WhyNot surface;
- T3 later is execution-enabling, not the final explanation API.

### 4.2 `CandidateSet` is not extended for RuleExpr provenance

T3 later must not add RuleExpr-specific fields to `CandidateSet`.

Existing `CandidateSet` fields remain the public contract:

- derivation/run identity;
- target/key/payload;
- `support_digest` / `support_kind`;
- confidence fields;
- candidate id/key/kind.

RuleExpr alias, occurrence, branch path, and join materialization metadata must not be stuffed into `CandidateSet.payload` as a public side channel.

If future T5 needs public provenance, it must introduce or adopt a result/evidence surface explicitly rather than retrofitting T3 later `CandidateSet` rows.

### 4.3 Existing support artifacts remain engine-facing, not RuleExpr-facing

D10 does not mutate shipped `SupportArtifact` / `ProvenanceEnvelope` public shapes.

Existing support objects already carry:

- binding items;
- support kind/digest;
- predicate witnesses;
- non-fact steps;
- rule-ref edges;
- engine provenance envelopes for non-native adapters.

T3 later may rely on these support artifacts for branch/atom evidence, but must not add RuleExpr-specific public fields to them in this tranche.

This preserves support digest stability and avoids making T3 later alias terminology part of the support artifact public schema before T5.

### 4.4 Runtime branch indexes align with D7 branch ids

D9 locks one branch-list body per supported engine. D10 locks that runtime branch indexes preserve D7 branch order.

For a successful candidate:

- the runtime selected branch index corresponds to the D7 branch id/order;
- shipped support keys such as `b{branch_index}.a{atom_index}:...` remain valid;
- D8 `materialized_atom_index` can be interpreted against the selected branch body.

This is the minimum bridge between existing WhereIR support artifacts and future RuleExpr-aware evidence.

### 4.5 T3 later preserves a private RuleExpr evaluation trace sidecar

T3 later implementations must preserve private trace metadata sufficient for future T5 evidence mapping.

Minimum internal categories:

```python
@dataclass(frozen=True)
class RuleExprEvaluationTrace:
    canonical_key: tuple[object, ...]
    engine: str
    branch_id: str
    runtime_branch_index: int
    occurrence_aliases: tuple[str, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    join_materializations: tuple[RuleExprJoinMaterialization, ...]
    head_binding: RuleExprHeadBinding
    support_digest: str
    support_kind: str
```

Concrete helper names may differ, but the referenced minimum categories come from D7 §4.2 (`RuleExprOccurrenceBinding`, `RuleExprHeadBinding`) and D8 §4.8 (`RuleExprJoinMaterialization`). Exact storage location and lookup key are implementation details for Stage 3.

Minimum storage/lifetime invariants:

- the trace sidecar must be correlateable with the selected `CandidateSet`, the evaluation invocation, and the runtime branch index;
- the trace sidecar must live at least until the originating `fg.eval.evaluate(...)` invocation finishes;
- persistence beyond the invocation is not required by D10.

Required semantics:

- `canonical_key` comes from D7 `RuleExprLoweringPlan`;
- `branch_id` / `runtime_branch_index` map D7 branch identity to D9 runtime branch order;
- `occurrence_map` preserves alias-to-rule identity from D7;
- `join_materializations` preserve D8 `RuleExprJoinMaterialization` rows;
- `head_binding` preserves D6/D7 head category and projection target if present;
- `support_digest` / `support_kind` link to the existing `CandidateSet` and support artifact.

The sidecar is private and not exported from `factgraph.sdk`.

### 4.6 D8 join materialization metadata remains internal but durable

D8 §4.8 `RuleExprJoinMaterialization` metadata must survive through evaluation planning at least until a candidate/support link can be associated with a selected branch.

Future T5 must be able to identify:

- which equality atoms came from explicit RuleExpr joins;
- the original join key;
- left/right occurrence aliases and port names;
- the materialized equality atom's index in the branch body.

D10 does not expose this metadata publicly in T3 later. It only locks that implementation must not discard it before future evidence consumers can use it.

### 4.7 D9 preflight rejections do not return `CandidateSet`

D9 adapter matrix rejections raise `SDKStoreError` before adapter invocation.

They do not return:

- empty candidate lists as a substitute for unsupported;
- unsupported result objects;
- partial `CandidateSet` rows;
- T5-style structured result wrappers.

This keeps success path and unsupported-engine path distinct:

- success returns `list[CandidateSet]`;
- public call-shape / engine rejection errors raise `SDKStoreError`;
- RuleExpr semantic/lowering errors raise `RuleExprError` per D6-D8.

### 4.8 Existing Check / WhyNot evidence DTOs are not expanded in T3 later

Existing `EvidenceEnvelope` currently allows `branch_atom_projection=None` only. D10 does not change that MVP boundary.

T3 later may make internal trace metadata available for future Check/WhyNot integration, but does not:

- add public `branch_atom_projection`;
- add RuleExpr occurrence aliases to `EvidenceEnvelope`;
- update `WhyNotUniverseResult`;
- add proof-frame narrative fields.

Those are T5/T4-facing decisions.

### 4.9 Candidate ordering follows existing runtime ordering

D10 does not add RuleExpr-specific candidate sorting semantics.

Candidate order remains whatever the existing runtime/adapter evaluation path produces after D7/D9 deterministic branch ordering and shipped support capture sorting.

Future T5 may define presentation ordering for `EvaluateResult`; T3 later does not.

### 4.10 No public evidence loss through silent downgrade

T3 later must not silently drop RuleExpr provenance to satisfy the existing public result shape.

Specifically, implementations must not:

- drop D7 branch id/path metadata;
- drop occurrence aliases;
- drop D8 join materialization rows;
- rewrite support keys so branch/atom indexes no longer align with D7/D8 metadata;
- hide D9 adapter rejection behind an empty success result.

Public result stays simple, but internal evidence preservation remains mandatory.

## 5. Rejected Alternatives

### Option A: Introduce public `RuleExprEvaluateResult`

- **Rejected**.
- **Why rejected**: this would duplicate or preempt T5 `EvaluateResult` work. T3 later needs execution capability, not the final result/explanation API.

### Option B: Extend `CandidateSet` with RuleExpr provenance fields

- **Rejected**.
- **Why rejected**: `CandidateSet` is a core derivation result type used by legacy derivation evaluation and accept paths. Adding RuleExpr-specific fields would broaden the public blast radius and risk stale semantics before T5.

### Option C: Store RuleExpr provenance in `CandidateSet.payload`

- **Rejected**.
- **Why rejected**: `payload` describes the candidate fact/entity payload. Using it as a provenance side channel makes public rows ambiguous and complicates accept/ingest semantics.

### Option D: Extend `SupportArtifact` / `EvidenceEnvelope` publicly in T3 later

- **Rejected**.
- **Why rejected**: support artifacts are digest-bearing evidence shapes. Public mutation belongs with T5 proof/evidence design, not the T3 later execution tranche.

### Option E: Drop RuleExpr provenance entirely and rely on raw WhereIR support

- **Rejected**.
- **Why rejected**: raw support branch/atom keys alone cannot recover occurrence aliases, explicit join origins, or head projection categories. This would block T5 WhyNot / EvaluateResult mapping.

### Option F: Represent adapter rejection as a returned unsupported result

- **Rejected**.
- **Why rejected**: D9 already locks public adapter preflight rejection to `SDKStoreError`. Returning unsupported objects would require a public result wrapper, which D10 rejects for T3 later.

## 6. Supporting Evidence

- Shipped `CandidateSet` already carries support digest/kind and candidate identity, but no RuleExpr-specific fields.
- Shipped `_SDKEvalManager.evaluate(...)` returns `list[CandidateSet]` and delegates current derivation paths to compiled derivation plan evaluation.
- Shipped `evaluate_derivation_plans(...)` explicitly returns flattened `CandidateSet` objects with no application-side wrapper.
- Shipped support artifacts encode selected runtime branch/atom identity through `b{branch_index}.a{atom_index}:...` keys.
- Shipped support capture builds support artifacts for the selected branch, enumerating atoms in branch order.
- Existing `EvidenceEnvelope` keeps `branch_atom_projection=None` in MVP, which confirms that public branch/atom projection is not yet a stable public evidence surface.
- Stage 1 audit F8 warns that T3 later must avoid silently discarding alias/occurrence/join/OR structure needed by T5.

## 7. Consequences

Downstream implementation blueprints can:

- implement RuleExpr execution without public result wrapper churn;
- reuse existing accept flow for returned `CandidateSet` objects;
- preserve internal trace metadata for later T5 without committing its public schema;
- test D7/D8/D9 provenance alignment through private helpers.

D10 constrains Stage 3 synthesis:

- no T3 later slice may add public result DTO exports without a scope/class amendment;
- no T3 later slice may modify `CandidateSet` public shape for RuleExpr;
- Stage 3 must allocate a trace-preservation step before any adapter execution slice claims evidence-readiness;
- D10 reviewed status will complete Stage 2 decision coverage and unblock Stage 3 synthesis.

Still deferred:

- final T5 `EvaluateResult` / WhyNot public surface;
- public evidence projection from RuleExpr occurrences/joins to proof frames;
- structured SDKStoreError payload objects beyond D9's message contract;
- T4 Head / closed-head evidence semantics.

## 8. Acceptance Criteria

- [ ] Stage 3 synthesis cites D10 for result/evidence boundaries.
- [ ] Future implementation blueprints keep `fg.eval.evaluate(rule_expr, head=...)` success return shape as `list[CandidateSet]`.
- [ ] Future implementation blueprints do not add public RuleExpr evaluation result DTOs or SDK exports in T3 later.
- [ ] Future implementation blueprints do not extend `CandidateSet` or use `CandidateSet.payload` for RuleExpr provenance.
- [ ] Future implementation blueprints preserve private trace metadata covering D7 canonical key, branch id/runtime index, occurrence map, D8 join materializations, head binding, and support digest/kind.
- [ ] Future implementation blueprints keep D9 preflight rejections as `SDKStoreError`, not unsupported result objects or empty candidate lists.
- [ ] Future implementation blueprints preserve support branch/atom key alignment with D7/D8 metadata.
- [ ] Future implementation blueprints do not expand `EvidenceEnvelope`, `WhyNotUniverseResult`, or proof-frame public DTOs without a T5/T4 decision.
- [ ] No new public error subclass or result wrapper is introduced by D10.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | D10 keeps public RuleExpr evaluation success results as `list[CandidateSet]`, rejects public result wrappers / `CandidateSet` extensions, and requires private trace preservation for future T5 evidence mapping. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Added ADR lifecycle blockquote, typed trace sidecar fields against D7/D8 minimum categories, and locked minimum sidecar storage/lifetime invariants. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1-WC3 and N2 addressed; public `list[CandidateSet]` boundary, private trace sidecar typing, and T5 evidence deferral reviewed clean; Stage 3 synthesis unblocked. |
