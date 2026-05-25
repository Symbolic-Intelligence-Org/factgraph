# Task Blueprint: T5.2 Public Evaluate Return-Shape Flip

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: L (predicted; may split into adjacent M-class local slices after Step 4.6)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-2-public-evaluate-return-shape-flip.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- Predecessor slice: T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.

## 0. Scope Locks

### In scope

- Flip public SDK `evaluate(...)` success output from `list[CandidateSet]` to `EvaluateResult` per D18 section 4.1.
- Apply the return-shape flip to all public evaluate input paths in one coherent local milestone:
  - application `Rule` / `RuleExpr` with `head=` application head `Rule`;
  - legacy SDK `Inference`;
  - structured derivation dicts;
  - direct store-style evaluate fallback paths that are still part of public `SDKStore.evaluate(...)`;
  - public `fg.eval.evaluate(...)` alias path if it shares `SDKStore.evaluate(...)`.
- Reject public `engine_options=` and `registry=` at the public `evaluate(...)` boundary with `SDKStoreError`, not silent ignore.
- Populate T5.1 `EvaluateResult`, `EvaluateRow`, `Claim`, and `EvidenceRef` for every public evaluate success path.
- Populate D19 digest fields for every returned `EvaluateResult`:
  - `result_id`;
  - `run_id`;
  - `row_id`;
  - `expr_digest`;
  - `rule_set_digest`;
  - `view_snapshot_digest`;
  - `semantics_digest`;
  - `result_digest`;
  - row `Claim.digest`;
  - row `EvidenceRef.ref_id`;
  - row `EvidenceRef.closed_head_digest`.
- Decide and implement the in-memory SDK-store `view_snapshot_digest` source required by T5.1 Outcome follow-up, without placeholders.
- Keep `CandidateSet` as the internal runtime artifact and use T5.1 private conversion helpers or equivalent internal helpers only behind the new public result envelope.
- Update focused public SDK evaluate tests and any minimum docs/test expectations required to keep the hard-cut coherent locally.
- Run D23 service-route/docs/examples blast-radius inventory before feat; classify each hit.

### Out of scope

- `row.explain()` and public `Explanation`; T5.3 owns those.
- `row.close()` and manual `fg.eval.explain(expr, head=closed_head, ...)`; T5.4 owns those.
- Public `.eval.why_not(...)`; D22/T5.5 lock no new public why-not surface.
- SDK top-level `Rule` naming flip; T5.6/D24 owns that.
- Removing `accept`, `accept_many`, `check`, `diagnose`, `why_not`, or `what_if.*` shells unless Step 4.6 proves they must move in the same L-class local slice and reviewer approves an explicit scope amendment.
- Full service route/OpenAPI/docs hard-cut migration; T5.7/D23 owns final public cleanup. T5.2 may only update narrow tests/docs needed to avoid a milestone-incoherent public evaluate shape.
- C73-C78 semantics implementation and adapter production edits; T5.8/D26 or a post-T5 cycle owns adapter-touching work.
- New public CandidateSet compatibility surface:
  - no `evaluate_v2`;
  - no `evaluate_result`;
  - no `result_shape=`;
  - no `return_candidates=`;
  - no `as_candidates=`;
  - no `evaluate_candidates`.
- New public evidence graph, support, renderer, trace, or explanation DTOs beyond the T5.1 result DTOs.

### L-class split rules

T5.2 is L-class by default. It may split into adjacent local M-class slices only if the split preserves a coherent private/local state:

1. **T5.2a internal envelope conversion**:
   - introduces private conversion and digest population behind existing public return shape;
   - no push / no archive as public milestone if public evaluate still returns `list[CandidateSet]`.
2. **T5.2b public return-shape flip**:
   - flips all public evaluate paths together;
   - rejects `engine_options=` / `registry=`;
   - updates tests and minimum docs/service references needed for local consistency.

Any split must be documented by a blueprint amend before scoped. Mixed public return shapes by input type are not allowed in a public milestone.

### Escalation triggers

Pause and amend/split if implementation requires:

- adapter production edits;
- service route/OpenAPI migration larger than narrow return-shape alignment;
- final SDK `Rule` namespace changes;
- public `Explanation`, `row.explain()`, or `row.close()`;
- public CandidateSet compatibility flags;
- database migration or persistent schema changes;
- changing existing `Rule.content_digest` format or formula;
- changing T5.1 DTO field contracts;
- C73-C78 semantics implementation.

## 1. Inputs

T5.2 consumes the completed T5 design layer and T5.1 substrate:

- D17 defines `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, CandidateSet internal classification, row lineage via `EvidenceRef` / future `EvidenceGraph`, and live/detached boundary.
- D18 locks the hard-cut transition:
  - public `evaluate(...) -> EvaluateResult`;
  - all public evaluate input paths flip together;
  - no parallel v2 or return-shape flag;
  - public `engine_options=` / `registry=` are rejected with the return-shape flip;
  - CandidateSet remains internal.
- D19 locks digest formats and source-of-truth helpers; T5.1 implemented the initial helper path at `a3e96eb6`.
- D20/D21 reserve explanation and close behavior. T5.2 may bind live row resolvers but must not expose explanation/close behavior.
- D22 folds why-not into future failed `Explanation`; T5.2 must not add a public why-not path.
- D23 requires blast-radius inventory across SDK, service routes, OpenAPI, docs, examples, and tests before hard-cut implementation.
- D24 reserves final SDK `Rule` naming; T5.2 uses application head `Rule` terminology without changing SDK top-level `Rule`.
- D25 requires semantics consistency by `semantics_digest`; T5.2 must populate `semantics_digest` but not implement explanation replay mismatch policy.
- D26 keeps adapter-touching semantics work out of T5 Core by default.
- T5.1 archive provides DTOs, digest helpers, private CandidateSet conversion harness, SDK DTO re-exports, and a documented T5.2 follow-up for in-memory view snapshot source.

Pre-draft shipped source reads found:

- `src/factgraph/sdk/store.py:2211-2384` is the main public evaluate dispatcher and still returns `list[CandidateSet]`.
- `src/factgraph/application/derivation_runtime.py:69-142` still returns raw `list[CandidateSet]`.
- `src/service/runtime_v1.py:971-987` uses `session.store.evaluate(...)` and serializes candidates into a service response.
- `docs/api/openapi.yaml:606-621` still describes runtime inference evaluate as returning CandidateSet v2.
- SDK docs, examples, and tests still contain broad CandidateSet / `engine_options` / accept assumptions.

## 2. Plan

### 2.1 Pre-implementation inventory before code

Before feat, run and record Step 4.6 inventory for:

1. public SDK evaluate callers and tests;
2. application runtime CandidateSet passthrough;
3. service routes and OpenAPI;
4. docs/examples/notebooks;
5. `engine_options=` and `registry=` call sites;
6. `accept` / `accept_many` dependencies that assume CandidateSet output;
7. T5.1 DTO/digest helper consumers;
8. adapter and semantics guard words.

Classify every hit as:

- **T5.2 hard-cut update**: must change in this slice.
- **Internal preservation**: remains CandidateSet internally.
- **T5.7 deferred hard-cut**: documented service/docs/legacy shell cleanup.
- **Unrelated / historical**: archive, working reference, or agent-layer unrelated surface.

If service route/OpenAPI hits must be updated to keep local public shape coherent, the blueprint should be amended before scoped to declare whether T5.2 remains one L-class slice or splits.

Step 4.6 outcome: T5.2 remains one SDK-focused L-class slice. The SDK public `evaluate(...)` boundary, direct SDK fallback behavior, digest population, and `engine_options=` / `registry=` rejection are in scope. Service routes, OpenAPI, agent workflows, broad docs, examples, and CandidateSet/accept handshake migration are explicitly classified as T5.7 deferred hard-cut territory because they are coupled to `/inferences/accept`, `candidate_id`, and documented CandidateSet workflows. T5.2 must not update those service/docs surfaces except for a narrow deferral note if implementation needs one for local coherence.

### 2.2 Public SDK evaluate boundary

Update `SDKStore.evaluate(...)` so success returns `EvaluateResult` for every public input path:

- application `Rule` / `RuleExpr`:
  - requires `head=` application head `Rule`;
  - returns `EvaluateResult`;
  - no public CandidateSet compatibility.
- legacy SDK `Inference`:
  - compiles via existing derivation pipeline;
  - returns `EvaluateResult`.
- structured derivation dict:
  - compiles via existing path;
  - returns `EvaluateResult`.
- direct store-style evaluate fallback:
  - if still public, wrap results into `EvaluateResult` rather than returning raw store CandidateSet values;
  - if unsupported for public result conversion, reject with `SDKStoreError` and document why in audit before feat.

Public kwargs:

- `engine_options=`: reject at public evaluate boundary with `SDKStoreError`;
- `registry=`: reject at public evaluate boundary with `SDKStoreError`;
- `semantics=` remains accepted and lowered through existing `_resolve_public_engine_and_semantics(...)`;
- `engine=` remains accepted where D18 permits and resolves with semantics consistency checks.

Internal runtime functions may continue to accept registry-like state or plan-level engine options. The hard-cut is at the public SDK/service call boundary, not every private helper.

### 2.3 Internal conversion from CandidateSet to EvaluateResult

Keep `CandidateSet` as the internal runtime artifact.

Introduce an internal conversion layer that:

1. evaluates existing runtime plans to `list[CandidateSet]`;
2. maps each candidate through the T5.1 row conversion logic or equivalent internal helper;
3. enforces duplicate public `row_id` rejection before returning;
4. computes result-level digest fields after row conversion;
5. binds rows to the returned `EvaluateResult`.

Conversion rules:

- CandidateSet payload/bindings become public row `bindings`.
- CandidateSet target becomes `Claim.name` unless a head-specific mapper provides a better name.
- CandidateSet confidence carriers become `raw_kind` / `bound` only when already present in CandidateSet.
- CandidateSet ids, candidate keys, support digests, support kinds, and state remain internal.
- Row lineage is not added directly to `EvaluateRow`; D20 owns EvidenceGraph lineage.

### 2.4 Digest population

Every `EvaluateResult` must populate final D19 fields:

- `run_id`: generated once per public evaluate call and shared across rows;
- `result_id`: computed from run id, context digests, engine, and head id/content digest;
- `expr_digest`: from lowered RuleExpr structure or normalized compiled derivation plan shape;
- `rule_set_digest`: from source rules / compiled plans; `Rule.version` does not enter;
- `view_snapshot_digest`: real digest over the view visible to evaluation;
- `semantics_digest`: from normalized `SemanticsProfile` or `None`;
- `result_digest`: acyclic digest of result envelope and row digests;
- row ids and evidence refs: through T5.1 helpers.

The T5.2 implementation must close the T5.1 follow-up:

- database-backed views may use `view_digest_for(...)`;
- in-memory SDK stores must compute a deterministic digest over visible facts and schema context, or raise `SDKStoreError` before returning an `EvaluateResult`;
- no placeholder, empty, wall-clock-derived, schema-only, or "TODO" digest is allowed.

### 2.5 Application runtime boundary

`evaluate_derivation_plans(...)` may remain an internal CandidateSet-returning helper if the SDK wraps it.

Allowed options:

1. Keep `evaluate_derivation_plans(...) -> list[CandidateSet]` and add a new private SDK/application wrapper that builds `EvaluateResult`.
2. Add a sibling internal helper for `EvaluateResult` while preserving the existing CandidateSet helper for adapters/check/diagnose until T5.7.
3. Flip `evaluate_derivation_plans(...)` itself only if Step 4.6 proves all internal callers can move safely and no Check/Diagnose/WhyNot substrate breaks.

Public outcome must be `EvaluateResult`; internal helper shape is implementation-owned.

### 2.6 Service route / OpenAPI posture

D23 requires service-route blast-radius inventory. T5.2 draft does not assume final service hard-cut.

Step 4.6 selected the narrow SDK-only public flip posture:

- SDK public shape changes in T5.2.
- Service runtime evaluate response, OpenAPI, service docs, agent workflows, examples, and the CandidateSet/accept handshake remain T5.7 deferred hard-cut territory.
- Service-aligned work may only enter T5.2 after a reviewed blueprint amendment.
- No T5.2a/T5.2b split is required before scoped; implementation remains one L-class SDK public flip unless feature work proves a split is necessary.

The implementation must not leave a final milestone where SDK docs claim `EvaluateResult` but the same public service route is documented as the primary CandidateSet evaluate/accept handshake without a T5.7 deferral note.

### 2.7 Error boundaries

- Public `engine_options=` -> `SDKStoreError`.
- Public `registry=` -> `SDKStoreError`.
- Missing digest source -> `SDKStoreError` at SDK/runtime boundary.
- Duplicate row ids -> `SDKStoreError` or `ProtocolShapeError` before public return; implementation should prefer SDKStoreError at public boundary and keep ProtocolShapeError internal.
- Malformed DTO construction remains `ProtocolShapeError`.
- No new public error subclass in T5.2.

### 2.8 Implementation ordering

Recommended local ordering:

1. Add internal result-conversion helper over T5.1 DTOs.
2. Add deterministic view snapshot digest source for current SDK store evaluation view.
3. Wrap RuleExpr public evaluate path and update tests.
4. Wrap legacy `Inference` / structured dict paths and update tests.
5. Reject `engine_options=` / `registry=` at public evaluate boundary and update tests.
6. Decide direct store-style evaluate fallback behavior.
7. Run Step 4.6 service/docs/examples inventory and apply only scoped updates.
8. Run focused and G7 gates.

## 3. Code Changes

Likely production files:

- `src/factgraph/sdk/store.py`
  - public evaluate return shape;
  - `engine_options=` / `registry=` rejection;
  - result conversion helper and digest population;
  - view snapshot digest source or adapter.
- `src/factgraph/application/derivation_runtime.py`
  - only if the application runtime helper itself must expose an EvaluateResult sibling or change return shape.
- `src/factgraph/application/protocol/evaluate_result.py`
  - only narrow helper amendments if T5.1 helpers need public-boundary adaptation; do not change DTO field contracts.
- service files remain deferred to T5.7 unless a later reviewed amendment brings them into T5.2:
  - `src/service/runtime_v1.py`;
  - `docs/api/openapi.yaml`;
  - service docs.

Likely test files:

- `tests/sdk/test_rule_expr_evaluate.py`;
- tests covering legacy `Inference` / structured derivation dict evaluate;
- `tests/application/protocol/test_evaluate_result_*` if helper behavior is extended;
- service route tests if service is in this slice;
- docs/example checks only if T5.2 updates them.

Files explicitly out of target scope unless blueprint is amended:

- adapter production modules;
- `row.explain` / `row.close` implementation files;
- final SDK Rule namespace files beyond unaffected imports;
- broad final docs migration;
- legacy shell deletion files.

## 4. Tests

Minimum focused tests:

1. `fg.eval.evaluate(application_rule_or_ruleexpr, head=...)` returns `EvaluateResult`.
2. RuleExpr result rows have `EvaluateRow` items with public `bindings`, `Claim`, `EvidenceRef`, and live resolver plumbing.
3. `fg.eval.evaluate(legacy_inference)` returns `EvaluateResult`.
4. `fg.eval.evaluate(structured_derivation_dict)` returns `EvaluateResult`.
5. All public evaluate input paths reject `engine_options=` with `SDKStoreError`.
6. All public evaluate input paths reject `registry=` with `SDKStoreError`.
7. Native path populates all D19 digest fields and `result_digest` is deterministic for stable inputs.
8. Semantics lowering populates `semantics_digest`; `semantics=None` yields `None`.
9. `view_snapshot_digest` is real and deterministic for the visible SDK store view.
10. CandidateSet identifiers/support/state do not appear as public row fields.
11. Internal CandidateSet runtime tests remain green where CandidateSet is still internal.
12. No `evaluate_v2`, `result_shape=`, `return_candidates=`, or public candidate compatibility flag exists.
13. Public `row.explain()` / `row.close()` remain absent until T5.3/T5.4.
14. Service route tests remain deferred to T5.7 unless a reviewed amendment brings service route migration into T5.2.
15. Existing G7 suite preserves T4/T5.1 behavior except for intentional evaluate return-shape test updates.

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

Expected inherited baseline: 163 tests OK from T5.1 archive.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Service route / OpenAPI blast radius is larger than SDK flip. | Step 4.6 inventory before scoped; split or amend if needed. |
| Mixed public return shapes by input type. | T5.2 scope requires all public evaluate paths to flip together. |
| `view_snapshot_digest` substrate for in-memory SDK store is ambiguous. | Implement deterministic visible-fact/schema digest or raise; no placeholder allowed. |
| CandidateSet compatibility leaks into public API. | Explicitly forbid compatibility flags and public conversion helpers; tests assert no candidate ids/support/state on rows. |
| `engine_options=` / `registry=` remain accepted accidentally. | Add rejection tests for every public evaluate path. |
| D20/D21 behavior leaks early through row resolver. | Keep row resolver private; no public row methods. |
| Adapter edits become necessary for result envelope. | Pause and amend; adapter production edits are out of T5.2. |
| Broad docs migration drifts into T5.2. | Keep docs updates minimal unless service-aligned L slice is explicitly chosen after Step 4.6. |
| Digest helper duplication appears. | Use T5.1 helpers as the only result/digest path; no duplicate formula in SDK store. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates L-class default and split policy.
- Reviewer validates service-route blast-radius inventory is mandatory before scoped.
- Reviewer validates T5.2 does not absorb T5.3/T5.4/T5.6/T5.7/T5.8 without amendment.

### Step 4.6 grep gate

Before scoped:

- execute D18/D23 blast-radius grep;
- classify hits;
- record results in paired audit;
- amend blueprint if service/docs/OpenAPI scope must change.

### G7 baseline gate

After scoped:

- run inherited G7 preservation command;
- expected baseline is 163 tests OK;
- record pytest deferred and `tests.test_public_inference_factgraph_create` exclusion.

### Feature gate

Run:

- focused T5.2 evaluate return-shape tests;
- updated G7 preservation suite;
- service route tests if service is in scope;
- touched-file ruff for production and tests.

Pytest remains deferred per existing SIGSEGV environment lock unless environment constraints change.

## 7. Rollback

T5.2 rollback must restore public evaluate coherence:

- If feat fails before public flip, revert conversion/helper changes without altering T5.1 DTO foundation.
- If feat flips public evaluate, rollback must revert all public paths together; do not leave RuleExpr returning `EvaluateResult` while legacy inference returns `list[CandidateSet]`.
- If service route is included, rollback SDK and service route changes together or split only behind a reviewed local milestone.
- Do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.2 may update narrow docs/tests that are directly tied to the public evaluate return shape.

Deferred to T5.7:

- final docs migration;
- OpenAPI/service docs full cleanup;
- accept/accept_many/check/diagnose/why_not/what_if hard-cut docs;
- examples rewrite away from CandidateSet accept workflows.

Deferred to T5.6:

- final SDK `Rule` naming docs.

## 9. Reviewer Focus

- Is T5.2 scoped as one L slice or should it split before scoped?
- Is service route/OpenAPI handling precise enough before Step 4.6?
- Does the plan keep CandidateSet internal without adding compatibility flags?
- Does every public evaluate path flip together?
- Are `engine_options=` and `registry=` rejected at the public boundary?
- Is `view_snapshot_digest` source realistic for the current SDK store?
- Does the plan avoid row explanation/close and final Rule flip?
- Are digest helpers centralized on T5.1 instead of duplicated?

## 10. Outcome

### Commit References

- Feature implementation: `7dfadd4e` (`feat(sdk): flip evaluate to T5 result envelope`).
- Step 4.7 review: clean, 0 P0 / 0 P1.
- No Step 4.7 fix commit was required.

### Final Landed Code

Production:

1. `src/factgraph/sdk/store.py` flipped the SDK public `evaluate(...)` return shape to `EvaluateResult`.
2. The RuleExpr / application `Rule` path, legacy SDK `Inference` path, and structured derivation dict path now evaluate through existing internal `CandidateSet` runtime and wrap success into the T5.1 result envelope.
3. Direct store-style SDK evaluate fallback is rejected with `SDKStoreError` instead of returning raw store `CandidateSet` values.
4. Public `engine_options=` and `registry=` are rejected at the SDK evaluate boundary with `SDKStoreError`.
5. `_candidate_sets_to_evaluate_result(...)` populates T5.1 DTOs and D19 digest fields by reusing the T5.1 helper path.
6. `_view_snapshot_digest(...)` closes the T5.1 follow-up with a deterministic in-memory SDK-store view snapshot source and still delegates final formatting through `view_snapshot_digest_for_parts(...)`.

Tests:

1. `tests/sdk/test_rule_expr_evaluate.py` was updated for the public result envelope.
2. The focused tests now cover RuleExpr/application `Rule`, legacy `Inference`, structured derivation dict, public `engine_options=` / `registry=` rejection, direct fallback rejection, digest population, projection-head lowering preservation, and absence of early `row.explain()` / `row.close()` methods.

### Delivered Behavior

1. `fg.eval.evaluate(...)` now returns `EvaluateResult` for all scoped SDK public success paths.
2. Public rows expose `EvaluateRow` data (`bindings`, `Claim`, `EvidenceRef`, `raw_kind`, `bound`) rather than `CandidateSet` identifiers or support internals.
3. CandidateSet remains the internal runtime artifact; `_evaluate_compiled_derivation_plans(...)` and application runtime helpers continue to return internal `list[CandidateSet]` where needed by Check/Diagnose/WhyNot and future T5.7 work.
4. Public `engine_options=` and `registry=` are hard rejected instead of forwarded, matching D18 section 4.4.
5. The direct SDK fallback no longer exposes underlying store-style candidate output; callers must use application `Rule` / `RuleExpr` with `head=`, legacy `Inference`, or a structured derivation dict.
6. Every returned result receives `run_id`, `result_id`, row ids, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, row `Claim.digest`, row `EvidenceRef.ref_id`, and row `EvidenceRef.closed_head_digest`.
7. Service route, OpenAPI, agent workflows, examples, and broad docs remain intentionally deferred to T5.7 per the scoped Step 4.6 decision.

### Test Gates

| Gate | Result |
|---|---|
| G7 baseline | `ca18f856`: 163 tests OK. |
| Feature preservation | `7dfadd4e`: 166 tests OK. |
| Focused T5.2 tests | `tests.sdk.test_rule_expr_evaluate`: 18 tests OK. |
| T5.1 substrate focused tests | DTO/digest/export focused suite: 13 tests OK. |
| Ruff | Touched `src/factgraph/sdk/store.py` and `tests/sdk/test_rule_expr_evaluate.py` clean. |
| Diff hygiene | `git diff --check` clean. |
| Pytest | Deferred per existing SIGSEGV environment lock. |
| Excluded test | `tests.test_public_inference_factgraph_create` remains outside the G7 command. |

### Deviations And Follow-Ups

- 0 P0 / 0 P1 in Step 4.7 review.
- Optional Nit N1: `_head_rule_for_compiled_plans(...)` builds a synthetic application head `Rule` for legacy `Inference` / structured dict paths. It is an internal bridge and user-invisible.
- Optional Nit N2: in-memory `db_id` / `base_tx_id` derivation can collide across stores with identical schema and data. That is acceptable because it represents the same visible view.
- Optional Nit N3: one test compares two evaluate calls for digest repeatability; the minor extra runtime is acceptable.
- T5.7 must explicitly handle the deferred public surfaces: `src/service/runtime_v1.py`, `docs/api/openapi.yaml`, `src/agent/*`, SDK docs/examples, `accept` / `accept_many`, `check`, `diagnose`, `why_not`, and `what_if.*`.
- T5.3 and T5.4 remain responsible for `row.explain()`, `Explanation`, `row.close()`, and manual closed-head replay.
- T5.6 remains responsible for the final SDK `Rule` namespace flip.
- T5.8 or a post-T5 cycle remains responsible for C73-C78 semantics implementation and adapter-touching work.
