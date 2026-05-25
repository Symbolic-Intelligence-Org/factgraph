# Task Blueprint: T5.7 Legacy Hard-Cut + Service/Docs Migration

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: L (scoped; implement as three adjacent M-class local sub-slices)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-7-legacy-hard-cut-service-docs-migration.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition-strategy.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope-evidencegraph-integration.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
- Predecessor slices:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.
  - T5.3 Explanation Envelope + Live Row Resolver archived at `ba5e5c26`; feature anchor `53551cb6`.
  - T5.4 Row Close + Manual Explain Closed-Head Gate archived at `7464c3e3`; feature anchor `c820f102`.
  - T5.5 Why-Not Fold + Legacy Evidence Quarantine archived at `ec45f12f`; feature anchor `5113e13d`.
  - T5.6 Final SDK Rule Flip archived at `7aa1c6a3`; feature anchor `ad810f4d`.

## 0. Scope Locks

### In scope

- Complete the D23 public hard-cut for legacy evaluation/evidence shells:
  - `fg.eval.accept`;
  - `fg.eval.accept_many`;
  - `fg.eval.run`;
  - `SDKStore.accept`;
  - `SDKStore.accept_many`;
  - direct `SDKStore.check`;
  - direct `SDKStore.diagnose`;
  - direct `SDKStore.why_not`;
  - `fg.what_if.check`;
  - `fg.what_if.diagnose`;
  - `fg.what_if.why_not`;
  - `fg.what_if.fact_overlay.*`;
  - `fg.what_if.rule.*`.
- Synchronize service routes and OpenAPI with the T5 public EvaluateResult model:
  - `/runtime/inferences/evaluate` must stop documenting or returning public CandidateSet payloads;
  - `/runtime/inferences/accept` must be removed, rejected, or redesigned so the service no longer exposes CandidateSet accept round-trips;
  - `docs/api/openapi.yaml` must stop describing CandidateSet as the public evaluate result.
- Perform final docs and examples migration after T5.6 final SDK `Rule` naming:
  - public docs prefer `from factgraph.sdk import Rule`;
  - docs do not teach `ApplicationRule`, top-level `LegacyRule`, CandidateSet, accept, check, diagnose, why-not, or what-if shells as T5 evidence paths;
  - examples and notebooks are updated or archived if they teach removed workflows.
- Decide final disposition of legacy DSL `Rule`:
  - no final user-facing `factgraph.sdk.dsl.Rule` path is allowed unless Step 4.6 records an explicit future-track exception;
  - any preserved legacy class must be internal-only and not appear in public docs/examples.
- Decide final disposition of shipped why-not DTOs/runtime/shells after T5.5 quarantine:
  - delete if no internal runtime requires them;
  - otherwise keep them internal-only and unexported with tests proving no T5 public evidence dependency.
- Preserve internal CandidateSet runtime behavior where still needed by private evaluation engines or tests.
- Add hard-cut and docs-grep tests that prove the final milestone is coherent across SDK, service, OpenAPI, and docs.

### Out of scope

- C73-C78 adapter or Semantics Lite implementation.
- Parent section 6 task split.
- Parent section 9 RuleExpr x evidence-join expansion.
- New public CandidateSet compatibility routes, flags, or DTOs.
- New public why-not replacement API.
- T5.1-T5.6 DTO/evaluate/explain/close/Rule contracts.
- Rule content digest, closed-head construction, or EvidenceGraph schema changes.
- Evidence-tree internal node/edge schema implementation.
- Adapter production edits.

### L-class split rules

T5.7 is L-class by default. Step 4.6 may split it into M-class implementation slices only if the split preserves coherent public milestones.

Allowed split candidates:

- T5.7a Service + OpenAPI migration.
- T5.7b Final docs, examples, and notebooks migration.
- T5.7c Legacy shell deletion, legacy DSL Rule final disposition, and why-not final disposition.

Any split must be recorded before scoped status. Intermediate mixed states are local-only and must not be pushed as a public milestone when SDK, service, OpenAPI, and docs disagree about return shape or public surfaces.

Step 4.6 decision:

- T5.7 remains one L-class blueprint and one archive unit.
- Implementation is split into three adjacent M-class local sub-slices:
  - T5.7a: service routes, agent/runtime candidate workflow alignment, and OpenAPI.
  - T5.7b: final SDK/service/official docs, examples, and notebook migration.
  - T5.7c: legacy SDK shell deletion/rejection, legacy DSL Rule final disposition, and why-not final disposition.
- No T5.7 sub-slice may be treated as push-ready until the full T5.7 public story is coherent.
- The blueprint stays active until T5.7a, T5.7b, and T5.7c are complete, verified, and closed.

### M-to-L / stop-and-amend triggers

Pause and amend if implementation requires:

- adapter production edits;
- persistent database migrations;
- a new public compatibility surface;
- service auth/session redesign beyond route payload migration;
- deleting internal DTOs that still support private runtime behavior;
- changing T5.1-T5.6 public contracts;
- changing application protocol `Rule` semantics or content digest;
- adding evidence-tree failed-node schema;
- broad example/notebook rewrites that cannot be validated in this slice;
- preserving a public legacy path as a final T5 milestone without an explicit future-track decision.

## 1. Inputs

D23 is the primary source for T5.7. It locks:

- hard-cut targets for legacy SDK shells;
- service-route blast-radius inventory before implementation;
- service/OpenAPI CandidateSet round-trip removal or redesign;
- local-only intermediate mixed states;
- final docs migration after D24 naming.

D18 provides the public evaluate return-shape hard-cut. T5.2 already flipped SDK `evaluate(...) -> EvaluateResult`, rejected `engine_options=` and `registry=`, and deferred service/OpenAPI/docs migration to T5.7.

D22 provides why-not disposition. T5.5 quarantined shipped why-not DTOs and shells; T5.7 owns the final internal-preserve or delete decision.

D24 provides final SDK naming. T5.6 made SDK top-level `Rule` the application protocol `Rule`, kept `ApplicationRule` as a transition alias, and removed top-level `LegacyRule`; T5.7 consumes that naming for broad docs and legacy cleanup.

Pre-draft shipped-source reads found:

- `src/service/runtime_v1.py` still serializes evaluate output as CandidateSet payloads and caches candidates for accept.
- `src/service/app_v1.py` still registers evaluate and accept runtime inference routes.
- `docs/api/openapi.yaml` still documents `/runtime/inferences/evaluate` as CandidateSet v2 and `/runtime/inferences/accept` as the accept handshake.
- `src/factgraph/sdk/store.py` still contains legacy `accept`, `accept_many`, direct `check`, direct `diagnose`, direct `why_not`, and `what_if.*` manager paths.
- `src/factgraph/sdk/docs/*.en.md`, `docs/official`, examples, and notebooks still contain broad CandidateSet/accept/check/diagnose/why-not/what-if teaching.
- `factgraph.sdk.dsl.Rule` remains the explicit legacy DSL path after T5.6 and needs final disposition.

## 2. Plan

### 2.1 Run D23 blast-radius inventory first

Before scoped status, run and record a broad inventory across:

- `src/factgraph/sdk`;
- `src/factgraph/application`;
- `src/service`;
- `src/agent`;
- `docs/api/openapi.yaml`;
- service docs;
- SDK docs;
- `docs/official`;
- examples;
- tests.

Classify each hit as:

- T5.7 hard-cut update;
- internal runtime preservation;
- explicit future-track deferral;
- unrelated or historical reference.

### 2.2 Implement through three local M-class sub-slices

Step 4.6 found 99 files across service, agent, OpenAPI, docs, examples, and tests that still reference CandidateSet, candidate ids, accept workflows, what-if, why-not, `ApplicationRule`, or legacy DSL Rule. A single feat commit would be too broad and would make review less precise.

T5.7 therefore uses one active L-class blueprint with three local sub-slices:

- T5.7a service routes, agent/runtime candidate workflow alignment, and OpenAPI.
- T5.7b final SDK/service/official docs, examples, and notebook migration.
- T5.7c legacy SDK shell deletion/rejection, legacy DSL Rule final disposition, and why-not final disposition.

No sub-slice is independently push-ready unless the reviewer explicitly marks it coherent. The default is to keep all T5.7 intermediate states local-only until the closure commit records SDK/service/OpenAPI/docs agreement.

### 2.3 Migrate service evaluate and accept routes

Target state:

- service evaluate route returns a JSON representation of `EvaluateResult`;
- rows serialize bindings, claim, raw_kind, bound, evidence reference, and row identifiers;
- result metadata serializes run/result identifiers, head metadata, engine metadata, digests, and evaluated_at;
- service route does not expose CandidateSet public fields such as candidate ids, support artifacts, or accept-state payloads;
- accept route is removed, rejected, or redesigned so it no longer accepts serialized CandidateSet payloads.

The exact JSON schema is implementation-owned but must be reflected in OpenAPI and service tests.

### 2.4 Remove or hide legacy SDK shells

T5.7 owns final public disposition for:

- `fg.eval.accept`;
- `fg.eval.accept_many`;
- `fg.eval.run`;
- `SDKStore.accept`;
- `SDKStore.accept_many`;
- `SDKStore.check`;
- `SDKStore.diagnose`;
- `SDKStore.why_not`;
- `fg.what_if.check`;
- `fg.what_if.diagnose`;
- `fg.what_if.why_not`;
- `fg.what_if.fact_overlay.*`;
- `fg.what_if.rule.*`.

Preferred final state is removal from public SDK surfaces. If a private helper remains for internal runtime tests, it must be renamed or scoped so it is not documented or exported as T5 public API.

### 2.5 Complete docs and examples migration

Update public-facing material so the post-T5 path is:

- author or receive an SDK `Rule`;
- call `fg.eval.evaluate(...)`;
- inspect `EvaluateResult` / `EvaluateRow`;
- call `row.explain()` for row evidence;
- call `row.close()` and `fg.eval.explain(expr, head=closed_head, ...)` for manual replay.

Remove or rewrite content that teaches:

- CandidateSet as public evaluate output;
- accept/accept_many workflows;
- direct check/diagnose/why_not shells;
- what-if evidence shells;
- top-level `LegacyRule`;
- `ApplicationRule` as the primary public name.

### 2.6 Decide legacy DSL Rule and Inference final disposition

After Step 4.6, choose the least broad final state consistent with D24:

- remove public/user-facing `factgraph.sdk.dsl.Rule` if tests and runtime can migrate cleanly; or
- keep only an internal/private legacy class if T5.7 needs to preserve old compilation internals.

`Inference` remains unless D23 hard-cut implementation proves the legacy input path can be deleted safely in this slice.

### 2.7 Decide why-not final disposition

After Step 4.6, choose:

- delete shipped why-not DTOs/runtime/shells if no internal runtime requires them; or
- preserve them internal-only with tests proving they are not public T5 evidence DTOs and not converted lossily into `Explanation.failure_class`.

No public `.eval.why_not(...)`, `why_not_v2`, `EvaluateResult.why_not(...)`, or atom-locator API may be added.

### 2.8 Verify final coherence

Feature completion requires:

- SDK public namespace and service route shapes agree with T5 result/evidence model;
- OpenAPI agrees with service implementation;
- public docs/examples agree with SDK and OpenAPI;
- internal CandidateSet tests remain green where private runtime still uses CandidateSet;
- no final public legacy shell remains without an explicit reviewed future-track deferral.

## 3. Code Changes

Likely touched areas:

- `src/factgraph/sdk/store.py`
- `src/factgraph/sdk/__init__.py`
- `src/factgraph/sdk/dsl/*`
- `src/factgraph/sdk/shells/*`
- `src/factgraph/application/protocol/derivation_why_not.py`
- `src/factgraph/application/why_not_runtime.py`
- `src/service/runtime_v1.py`
- `src/service/app_v1.py`
- `docs/api/openapi.yaml`
- `src/factgraph/sdk/docs/*.en.md`
- `src/factgraph/application/docs/rule.md`
- `docs/official/**`
- `examples/**/*.ipynb`
- service and SDK tests

T5.7 must not touch `src/factgraph/adapters/` unless the blueprint is amended.

## 4. Tests

Minimum tests:

- SDK `fg.eval.evaluate(...)` still returns `EvaluateResult`.
- No public `fg.eval.accept`, `fg.eval.accept_many`, or `fg.eval.run`.
- Direct `SDKStore.check`, `SDKStore.diagnose`, and `SDKStore.why_not` are removed or rejected according to final implementation.
- No public `fg.what_if.*` evidence shell remains unless Step 4.6 records a future-track deferral.
- Service evaluate route returns EvaluateResult representation, not CandidateSet.
- Service accept route is removed, rejected, or redesigned without CandidateSet payload dependency.
- OpenAPI no longer documents CandidateSet evaluate output or accept handshake.
- Public docs/examples grep clean for removed teaching paths.
- SDK docs use `Rule` as final public name.
- `ApplicationRule` appears only as transition alias material, not primary docs.
- Top-level `LegacyRule` remains absent; legacy DSL Rule final disposition is tested.
- Why-not DTO final disposition is tested.
- Internal CandidateSet runtime tests remain green.
- No public CandidateSet compatibility flags are introduced.
- No public why-not replacement API is introduced.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Service route migration is broader than expected | Use Step 4.6 split policy and keep intermediate states local-only. |
| OpenAPI and runtime drift | Update route implementation and OpenAPI in the same public milestone. |
| Docs/examples still teach removed shells | Add grep-based docs guards and list any intentionally historical/archive exceptions. |
| Legacy shell deletion breaks private runtime tests | Rename or internalize helpers rather than deleting private runtime behavior prematurely. |
| Why-not DTO deletion breaks internal diagnostics | Preserve internal-only DTOs if needed; do not re-export or document them. |
| Legacy DSL Rule deletion breaks broad tests | Split final DSL cleanup or preserve internal-only class with explicit review. |
| Dirty notebooks complicate migration | Do not overwrite unrelated dirty notebook baseline; inspect and work with existing changes. |
| Public clients lose route without clear replacement | OpenAPI and docs must point to EvaluateResult, row explain, row close, and manual explain paths. |
| Scope creeps into Semantics Lite | Guard `src/factgraph/adapters/` and C73-C78 terms in Step 4.6. |

## 6. Verification Gates

### Draft review

- Step 4.2 review confirms D23/D18/D22/D24 scope mapping.
- No production changes before review.

### Step 4.6 inventory gate

- Run the broad inventory in the paired audit.
- Record split decision before scoped status.
- Amend if public coherence cannot be maintained in one L slice.

### G7 baseline

Expected inherited baseline: 171 tests OK from T5.6 archive.

Command:

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

### Feature gate

- G7 preservation.
- Focused SDK hard-cut tests.
- Focused service route tests.
- OpenAPI/schema tests or static validation.
- Docs grep guards.
- Internal CandidateSet preservation tests.
- Touched-file ruff.
- `git diff --check`.

## 7. Rollback

Rollback must be atomic by public surface:

- Do not revert service without OpenAPI if they changed together.
- Do not restore CandidateSet public compatibility flags.
- Do not restore top-level legacy SDK aliases as a hidden compatibility lane.
- Do not alter unrelated dirty baseline files unless T5.7 explicitly owns them.
- If split is required, each pushed slice must preserve a coherent public story.

## 8. Documentation Handoff

T5.7 is the final T5 Core docs migration slice. Closure must list:

- service route changes;
- OpenAPI changes;
- SDK docs changes;
- official docs changes;
- examples/notebooks changed or intentionally deferred;
- any historical/archive references that still mention legacy APIs.

## 9. Reviewer Focus

Review should focus on:

- no public CandidateSet compatibility reintroduced;
- no public why-not replacement introduced;
- service/OpenAPI/docs agreement;
- final SDK naming consistency after T5.6;
- legacy shell deletion not breaking private runtime;
- dirty baseline preserved;
- no adapter or Semantics Lite drift.

## 10. Outcome

Pending implementation.
