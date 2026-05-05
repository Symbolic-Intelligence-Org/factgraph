# Task Blueprint: Fact Overlay Capability

- Status: implemented
- Created: 2026-05-04
- Last Updated: 2026-05-05
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/view/`
  - `src/kernel/core/store/`
  - `src/kernel/sdk/` (optional thin shell only; no substrate)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md](../../references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md)
  - [docs/references/working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md](../../references/working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md)
  - [docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../archive/2026-05-03_check-operation.md)
  - [docs/blueprints/archive/2026-05-04_diagnose-operation.md](../archive/2026-05-04_diagnose-operation.md)
- Audit Log:
  - [2026-05-04_fact-overlay-capability.audit.md](./2026-05-04_fact-overlay-capability.audit.md)

## 1. Problem

Check and Diagnose established two application-first capabilities on the redesign line. The engine-extension topic then resolved capability declarations as a working hypothesis: local per-capability engine gates are allowed until a concrete migration trigger appears.

Fact Overlay is the third application capability candidate. It should test that working hypothesis while addressing the known missing half of the old workflow: users can evaluate committed facts and now Check a binding, but they still cannot ask "under this temporary fact correction, would this binding or derivation outcome change?" without writing to the ledger.

This blueprint completed Step 0 and is now scoped for implementation. Implementation must follow the frozen application DTO shape, ledger boundary, algorithm, and anti-regression gates below.

## 2. Goals

- Run a source-backed Step 0 for an application-first Fact Overlay capability.
- Decide whether the first capability shape is overlay-check, overlay-evaluate, or a narrower source-pass result that should fall back to Why-not.
- Freeze, before implementation:
  - request DTO shape;
  - overlay action DTO shape;
  - result/status vocabulary;
  - ledger-write boundary;
  - engine representability gates;
  - error and warning policy.
- Explicitly evaluate the four ledger boundary anchors:
  - DTO-carried override list;
  - DTO override list plus narrow projection-merge shim;
  - overlay-aware Store proxy;
  - pre-compile patch.
- Use the third capability to test engine-extension §6.6 without prematurely introducing a shared capability schema.

## 3. Non-goals

- No code implementation outside the scoped plan below.
- No ledger write, retract, set/add, accept, audit commit, or persisted scenario state.
- No mutable evidence tree API.
- No ProofFrameRechecker or local proof-path recheck in MVP unless Step 0 proves overlay evaluation cannot stand without it.
- No RuleDisable, RuleParameterOverride, ConditionOverride, add-condition, or rule rewrite in the first fact-overlay scope.
- No broad Why-not / candidate-universe search.
- No Explain renderer or natural-language narrative.
- No SDK substrate. Any SDK shell, if ever added, must be a thin delegate after application runtime exists.
- No release-base, `v0.1-oss-prep`, `master`, publish, or projection action.

## 4. Current Context

### Application-first baseline

- New runtime capabilities must start in `kernel.application.protocol` and `kernel.application`.
- Existing derivation runtime has `evaluate_derivation_plans(request, *, store, registry=None)`.
- Check and Diagnose established the current template:
  - intent-only request DTO;
  - runtime side-channel `store` / `registry`;
  - capability-owned status vocabulary;
  - locally hardcoded per-engine support gates;
  - no SDK shell by default.

### Source anchors

- Current `CheckRequest` / `CheckResult` have no overlay fields and Check's native runtime directly projects view facts before calling `evaluate_native_where(...)`.
- Current `DerivationEvaluateRequest` has no overlay fields.
- `evaluate_store(...)` has no `overlay`, `fact_override`, or `disabled_locators` argument after the reset.
- Native evaluation projects facts from `store.ledger` through `project_view_facts_with_witness(...)`.
- Non-native evaluation calls `store.evaluate_engine(...)`, which passes the concrete store to the registered adapter.
- B'' design material defines `EvaluationOverlay` as a non-persistent scenario and `FactValueOverride` as "assume a different assertion value under overlay; do not write ledger."
- The design material also warns against pre-rewrite store / sandbox-fork semantics and against plan-time patch as the default answer.

### Engine-extension anchors

- §6.6 says a third capability is the first migration trigger for re-opening capability declaration.
- Fact Overlay will likely add a third local support gate. Step 0 must decide whether that is still clear enough locally or whether §6.7 should be opened before implementation.

## 5. Proposed Shape

### 5.1 Capability shape

The first Fact Overlay capability is **Overlay Check**:

`FactOverlayCheckRequest(plan, binding, overlay, engine) -> FactOverlayCheckResult`

Overlay Evaluate remains out of scope. The capability answers "under these temporary fact overrides, does this requested binding pass, and how does that differ from the current committed-fact baseline?"

### 5.2 Ledger anchor and runtime composition

Chosen anchor: **DTO override list + narrow projection-merge shim**.

Runtime composition: **Sibling**, with narrow reuse/extraction of Check-private pure helpers allowed. Overlay Check does not call `check_derivation_binding(...)`. It owns its request/result DTOs, projection merge, baseline/overlay evaluation flow, and unsupported semantics. Shared helper extraction is allowed only for overlay-agnostic binding matching and body-var preflight.

Helper extraction destination: new application-internal shared module, expected shape `kernel.application._derivation_match_helpers`. Check and Overlay Check may import only the extracted binding-match and body-var preflight helpers from that module. Overlay Check must not import `derivation_check_runtime.py` or Check protocol result/envelope DTOs. Deterministic primary selection is not extracted; Overlay Check may import existing core helpers (`find_winning_branch_index` and `normalize_binding_items`) and compose its local sort key. This helper extraction is a prerequisite refactor before Overlay Check implementation, not part of the Overlay runtime itself.

`_derivation_match_helpers` remains a pure-helper module: no `Store`, `Registry`, global state access, evaluator dispatch, or cross-capability runtime composition. If future work needs meta-runtime behavior there, it must trigger the same class of architecture review as §6.6/§6.7 rather than silently expanding the helper module.

Hybrid via `check_derivation_binding(...)` is rejected because Check's per-engine paths can write evaluation artifacts into live `Store` caches through `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`. Overlay Check runs under hypothetical facts, so delegating through Check would risk leaving hypothetical artifacts in live caches and would launder ledger-grounded evidence behavior into an overlay result.

The native seam is:

`project_view_facts_with_witness(...) -> _apply_fact_overlay_projection(...) -> evaluate_native_where(...)`

No Store proxy and no pre-compile plan patch are used in MVP.

### 5.3 Overlay action DTO

MVP supports only `FactValueOverride`.

Proposed fields:

| Field | Purpose |
|---|---|
| `asrt_id: str` | The active visible projected assertion row being overridden for this evaluation |
| `pred_id: str` | Defensive predicate guard |
| `e_ref: str` | Defensive entity guard |
| `old_fact_tuple: tuple[Any, ...]` | Defensive stale-snapshot guard; must equal the current projected fact tuple |
| `new_fact_tuple: tuple[Any, ...]` | Replacement projected fact tuple for this evaluation |
| `note: str | None` | Optional caller context; not persisted |

Request overlay field: `overlay: tuple[FactValueOverride, ...]`. Empty overlay is rejected with `invalid_request` and `ErrorDTO(code="EMPTY_OVERLAY_NOT_PERMITTED")`; callers with no override should use Check.

Target semantics: **active visible projected-row replacement only**. The target `asrt_id` must be active and visible in current view projection. The override replaces that projected row after chosen projection for this evaluation only; it does **not** mean "pretend the ledger assertion changed before chosen policy ran." It does not support non-visible stale witnesses, predicate-wide replacement, `replace_all`, `add_alongside`, or add-fact semantics in MVP.

Tuple semantics: `old_fact_tuple` and `new_fact_tuple` are full projected predicate argument tuples matching `ProjectedFact.fact_tuple`; `kernel.core.view.projector.build_args_for_claim(...)` builds this as `(claim.e_ref, *val_atoms)`, so `e_ref == fact_tuple[0]`. They must preserve arity. `pred_id` and `e_ref` are defensive guards; `e_ref` must match position 0 of both old and new tuples. Overlay Check cannot use `new_fact_tuple` to migrate the fact to a different entity binding or predicate shape.

Chosen-policy guard: `new_fact_tuple` must preserve all schema `group_key_indexes` positions from `old_fact_tuple`. Because overlay applies after projection, changing group-key terms would bypass chosen-policy regrouping and is invalid in MVP.

Multiple overrides are simultaneous. Duplicate `asrt_id` overrides or conflicting replacement tuples are invalid.

### 5.4 Artifact and evidence policy

Overlay execution must not write the ledger and must not leave hypothetical artifacts or indexes in live `Store` caches. The live-store banned write surface is: `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`.

MVP does not expose overlay-derived engine-native artifacts to callers. `FactOverlayCheckResult` carries lightweight phase summaries, not `EvidenceEnvelope`. Therefore §6.5 is not re-opened. A future decision to expose overlay-derived `SupportArtifact` / `ProvenanceEnvelope` through `EvidenceEnvelope.engine_payload` is a §6.5 trigger.

### 5.5 Result DTO policy

Overlay Check uses encapsulated before/after semantics. It runs the current committed-fact baseline and the overlay-applied check in one capability call. Both phases return lightweight Check-like summaries without evidence payloads.

Proposed result shape:

| Field | Type / meaning |
|---|---|
| `status` | `Literal["passed", "failed", "unsupported", "invalid_request"]`; for completed native runs, equals `after.status` |
| `requested_binding` | normalized `BindingItems` echo |
| `before` | `OverlayCheckPhase | None` |
| `after` | `OverlayCheckPhase | None` |
| `diff` | `OverlayCheckDiff | None` |
| `errors` | `tuple[ErrorDTO, ...]` |
| `warnings` | `tuple[WarningDTO, ...]` |

`OverlayCheckPhase` carries only `status`, `matched_count`, and `matched_binding`; `matched_binding` is normalized `BindingItems` (`tuple[tuple[str, JSONValue], ...]`). `OverlayCheckDiff` carries status/match deltas only; it does not carry engine-native proof artifacts. Neither structure may reference `EvidenceEnvelope`, `SupportArtifact`, `ProvenanceEnvelope`, or any §6.5 typed Union member. `OverlayCheckDiff` field schema is pinned in Step 0.C; Step 0.B constrains it to status and match-count/binding deltas only.

Nullable matrix:

| result status | before | after | diff | errors |
|---|---|---|---|---|
| `passed` | populated | populated, status=`passed` | populated | empty |
| `failed` | populated | populated, status=`failed` | populated | empty |
| `unsupported` | None | None | None | required |
| `invalid_request` | None | None | None | required |

Preflight invalid/unsupported cases occur before baseline execution, so they do not return a partial `before` phase.

### 5.6 Engine support gate

MVP support is native-only:

| Engine | Overlay Check support | Result |
|---|---|---|
| `native` | supported via projection merge | `passed` / `failed` / `invalid_request` |
| `souffle` | unsupported; requires regenerated exported facts and adapter pipeline changes | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |
| `problog` | unsupported; requires rebuilt weighted-fact program | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |
| `pyreason` | unsupported; requires graph-state / temporal input patching | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |

This gate is self-contained and capability-owned; §6.6 still stands. No §6.7 declarative capability round is required before MVP implementation.

### 5.7 Algorithm freeze

Dispatcher entry ordering:

1. Normalize request-level fields and reject `overlay=()` first with `invalid_request` / `EMPTY_OVERLAY_NOT_PERMITTED`.
2. Run Overlay Check's own RuleRef preflight before any engine dispatch. RuleRef failures return `invalid_request`.
3. Apply the capability-owned engine support gate. Non-native engines short-circuit at dispatcher entry with `unsupported` / `ENGINE_OVERLAY_NOT_SUPPORTED`; no adapter is invoked and no baseline phase is returned.
4. For native only, project current visible facts with witnesses using `project_view_facts_with_witness(store.ledger, store.schema_ir)`.
5. Validate each `FactValueOverride` against that projected witness set: `asrt_id` active and visible, `old_fact_tuple` matches, tuple arity and `e_ref == fact_tuple[0]` hold, schema `group_key_indexes` positions are preserved, and there are no duplicate or conflicting overrides.
6. Assemble `invalid_request` if any validation error was recorded; otherwise run baseline and overlay phases.

Native phase sequence:

1. Build the baseline phase from the unmodified projected witness facts.
2. Build an overlay projected witness copy with `_apply_fact_overlay_projection(overrides, projected_witness_facts)`.
3. Convert each phase's projected witnesses to the `pred_id -> list[fact_tuple]` shape required by `evaluate_native_where(...)`.
4. Run `evaluate_native_where(...)` separately for baseline and overlay phases using identical plan body, requested binding, RuleRef resolutions, and `remember_support_artifact=None`.
5. Apply `_binding_matches`-style subset matching to each phase's final bindings and build lightweight `OverlayCheckPhase` summaries.
6. Compute `OverlayCheckDiff` only from the two phase summaries: status delta, match-count delta, and binding deltas. It never reads engine-native artifacts.

Execution is sequential for MVP: baseline first, overlay second. The two phases may share the immutable original projection snapshot, but the overlay projection must be a derived copy. No phase may write into live `Store` caches or reuse mutable capture state.

Overlay does not capture support artifacts in either phase, consistent with D5 no-exposure. The `remember_support_artifact` callback is explicitly `None` to prevent indirect live-cache writes through `evaluate_native_where(...)` RuleRef support capture.

Phase-execution runtime errors propagate through the `errors` channel, not through partial phase population. If either baseline or overlay phase raises a runtime error, `before`, `after`, and `diff` are all `None`, even if the baseline phase had already completed.

Status assembly:

1. Request-shape and RuleRef invalids return `invalid_request` before engine support is considered.
2. Unsupported engines return `unsupported` before native projection-dependent override validation.
3. Native projection or override validation errors return `invalid_request`.
4. Completed native runs set top-level `status` to `after.status`, either `passed` or `failed`.

Runtime helper decomposition is frozen at name/role altitude only:

- `check_fact_overlay_binding(...)`: application entry point.
- `_overlay_engine_support_preflight(...)`: dispatcher-level engine gate.
- `_overlay_ruleref_preflight(...)`: Overlay-owned RuleRef preflight, not imported from Check.
- `_apply_fact_overlay_projection(...)`: pure projection-copy merger for `FactValueOverride`.
- `_validate_fact_value_overrides(...)`: native projected-row defensive validation.
- `_run_native_overlay_phase(...)`: native phase evaluator that returns `OverlayCheckPhase` and calls `evaluate_native_where(..., remember_support_artifact=None)`.
- `_build_overlay_diff(...)`: phase-summary-only diff builder.

### 5.8 Engine-extension conformance

D8 (§6.6 working hypothesis still stands) is a documentation-discipline judgment, not a unit-testable gate. The local support gate is self-contained: native is supported through projection merge, while all non-native engines return the same `ENGINE_OVERLAY_NOT_SUPPORTED` result without adapter dispatch. This remains short enough to describe locally without a cross-adapter support matrix, so §6.7 is not opened before MVP implementation.

## 6. Boundaries And Invariants

- **Application-first:** protocol DTOs live under `kernel.application.protocol`; runtime lives under `kernel.application`.
- **No hidden overlay:** the what-if facts must be explicit in the request DTO, not hidden in mutable store state.
- **No ledger write:** the original `store.ledger` must be unchanged by the runtime.
- **No SDK substrate:** no new runtime concepts under `kernel.sdk`.
- **Intent-only request DTO:** no `store`, no `registry`, no precomputed projections, no caches.
- **Engine support is capability-owned until proven otherwise:** local gates are allowed under §6.6, but Step 0 must record whether the third capability makes them too hard to reason about.
- **Evidence remains read-only:** overlay may compare or derive new results, but must not mutate old evidence trees.
- **Runtime errors:** unexpected engine/runtime failures propagate through the runtime error channel, not through unsupported/invalid statuses.

## 7. Acceptance

### 7.1 Step 0 closure

- [x] Step 0.A source pass recorded in the audit log
- [x] Step 0.B freezes request / overlay action / result DTO shape
- [x] Step 0.B freezes the ledger-write boundary anchor
- [x] Step 0.C freezes algorithm and engine representability boundaries
- [x] Step 0.D lifts Step 0 decisions into this blueprint and moves status to `scoped`

### 7.2 §7-Overlay-N anti-regression gates

Each gate maps to a Step 0 decision and must become focused test coverage before implementation close-out:

- [x] **§7-Overlay-1** (Sibling no-Check-call invariant): static AST/import check that Overlay Check runtime never imports `check_derivation_binding`, `derivation_check_runtime`, Check result/envelope DTOs, or Check private helpers. The allow-list is `_derivation_match_helpers` binding-match/body-var helpers plus `kernel.core.store._support_capture.find_winning_branch_index` and `kernel.core.store._support.normalize_binding_items`.
- [x] **§7-Overlay-2** (intent-only request DTO): type/field test that `FactOverlayCheckRequest` dataclass fields are exactly `plan`, `binding`, `overlay`, and `engine`; no `store`, `registry`, precomputed projection, or cache fields appear as DTO fields. `store` and optional `registry` remain runtime side-channel kwargs to `check_fact_overlay_binding(...)`, not DTO members.
- [x] **§7-Overlay-3** (no ledger write): runtime test that overlay execution leaves `store.ledger` byte-identical and never calls `append_assertion`, `append_revocation`, `accept_*`, or any other ledger-write entry.
- [x] **§7-Overlay-4** (no live cache contamination): runtime spy/monkeypatch test that overlay execution does not call `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, or `_remember_rule_trace_artifact`; spy/argument inspection also confirms each `_run_native_overlay_phase(...)` call to `evaluate_native_where(...)` passes `remember_support_artifact=None`.
- [x] **§7-Overlay-5** (non-native dispatcher short-circuit): souffle, problog, and pyreason return `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED`; adapters are not invoked and `before` / `after` / `diff` are `None`.
- [x] **§7-Overlay-6** (empty overlay rejected): `overlay=()` returns `invalid_request` with `EMPTY_OVERLAY_NOT_PERMITTED`.
- [x] **§7-Overlay-7** (projected-row stale/visibility guards): stale `old_fact_tuple`, inactive `asrt_id`, and non-visible `asrt_id` each return `invalid_request`.
- [x] **§7-Overlay-8** (tuple shape guards): tuple arity violations and `e_ref != fact_tuple[0]` return `invalid_request`.
- [x] **§7-Overlay-9** (chosen-policy group-key guard): any `new_fact_tuple` change to schema `group_key_indexes` positions returns `invalid_request`.
- [x] **§7-Overlay-10** (§6.5 non-expansion): type-level test that `OverlayCheckPhase` and `OverlayCheckDiff` fields do not reference `EvidenceEnvelope`, `SupportArtifact`, `ProvenanceEnvelope`, or any §6.5 typed Union member.
- [x] **§7-Overlay-11** (no engine payload field): result DTO field absence test that `FactOverlayCheckResult` has no `evidence_envelope`, `engine_payload`, support-artifact, or provenance-envelope field.
- [x] **§7-Overlay-12** (status and nullable matrix): type/runtime test that result status contains exactly `passed`, `failed`, `unsupported`, and `invalid_request`, and that unsupported / invalid results have `before=None`, `after=None`, and `diff=None`.

### 7.3 Layer placement

- [x] Protocol DTOs live under `kernel.application.protocol/`
- [x] Runtime entry lives under `kernel.application/`
- [x] Runtime dependencies flow through side-channel kwargs, not DTO fields
- [x] No SDK substrate; any SDK shell must be separately scoped after application runtime exists

### 7.4 Code health

- [x] Tests cover protocol shape, status semantics, nullable matrix, native overlay pass/fail paths, unsupported non-native paths, invalid overlay paths, and all §7-Overlay gates.
- [x] Existing Check tests remain green after helper extraction.
- [x] `python -m ruff check src/kernel` clean.
- [x] Kernel test suite green.

### 7.5 Cross-doc updates

- [x] Application module docs (`src/kernel/application/docs/01_overview.md` + `_en.md`) updated to list Overlay Check.
- [x] Engine-extension topic doc updated only if implementation reopens §6.6 / §6.7; otherwise leave topic doc untouched per Step 0.
- [x] Conformance audit confirms implementation aligns with §5 frozen contract before status moves `scoped -> implemented`.

## 8. Implementation Plan

**Step 0 phases (complete; lifted into §5 / §7 above and audit Decision Notes):**

1. **Step 0.A — Source pass + structural pressure inventory** (complete; audit dated `2026-05-04`)
2. **Step 0.B — DTO + ledger boundary freeze** (complete; audit D1-D9)
3. **Step 0.C — Algorithm + drift-prevention freeze** (complete; audit C1-C7)
4. **Step 0.D — Lift to blueprint + scoped** (this lift)

**Implementation steps (ordered for incremental commits):**

5. **Step 1 — Helper extraction prerequisite refactor.** Move `_binding_matches` and `_all_body_vars` from `derivation_check_runtime.py` to new application-internal module `kernel.application._derivation_match_helpers`. Update Check to import those helpers. Verify the Check test slice stays green before adding Overlay code.

6. **Step 2 — Protocol DTOs.** Add `FactOverlayCheckRequest`, `FactValueOverride`, `FactOverlayCheckResult`, `OverlayCheckPhase`, and `OverlayCheckDiff` under `kernel.application.protocol/derivation_fact_overlay.py`. Add protocol tests for field shape, status literal, nullable matrix, empty-overlay rejection, intent-only DTO fields, and no §6.5 typed Union references.

7. **Step 3 — Native MVP scaffolding.** Add `check_fact_overlay_binding(...)`, dispatcher preflight ordering, `_overlay_ruleref_preflight(...)`, `_overlay_engine_support_preflight(...)`, native support, and non-native `ENGINE_OVERLAY_NOT_SUPPORTED` short-circuit. Land an end-to-end native path before full override hardening.

8. **Step 4 — Native double-run + override hardening.** Implement `_apply_fact_overlay_projection(...)`, `_validate_fact_value_overrides(...)`, `_run_native_overlay_phase(...)`, and `_build_overlay_diff(...)`. Cover baseline + overlay sequencing, callback pin `remember_support_artifact=None`, `asrt_id` active/visible validation, stale `old_fact_tuple`, arity/entity guards, group-key guard, duplicate/conflicting override rejection, and phase-runtime-error nullability.

9. **Step 5 — Drift-prevention named gates.** Land focused tests for §7-Overlay-1 through §7-Overlay-12 under `src/kernel/tests/test_application_fact_overlay_*.py`, with each gate represented by a named test class or clearly named test group.

10. **Step 6 — Close-out.** Update application docs, run the scoped verification set, record conformance audit findings in this blueprint audit, fill §10 Outcome / Deviations, then move status `scoped -> implemented` if implementation matches §5 and all §7 gates pass.

## 9. Docs To Update

Expected during implementation close-out:

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `src/kernel/application/docs/README.md` if a new durable module doc entry is introduced
- `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` if §6.6 escalates into §6.7

## 10. Outcome / Deviations

Final landed result:

- Fact Overlay Check shipped as the third application-first capability on `v0.1-fact-overlay-2026-05-04`.
- Runtime surface:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`
  - `src/kernel/application/fact_overlay_runtime.py`
  - public application export `check_fact_overlay_binding(...)`
- Capability behavior:
  - native engine supported through baseline + overlay-applied double run over projected facts;
  - result returns `before`, `after`, and phase-summary-only `diff`;
  - overlay is assertion-scoped active visible projected-row replacement;
  - no ledger write, no Store proxy, no SDK substrate, no Check delegation;
  - souffle/problog/pyreason short-circuit with `ENGINE_OVERLAY_NOT_SUPPORTED`.
- Implementation chain:
  - Step 1 helper extraction: `8d7d7bc`
  - Step 2 protocol DTOs: `96aea6f`
  - Step 2 review fix: `96a8982`
  - Step 3 native MVP scaffolding: `a7a8955`
  - Step 4 native double-run hardening: `009efac`
  - Step 5 drift gates: `d992cbd`
- Verification at close-out:
  - focused Overlay tests: 72 OK (`42` protocol + `27` runtime + `3` sibling invariant)
  - full kernel suite: 944 OK / 1 skipped
  - `python -m ruff check src/kernel`: clean

With implementation.

Deviations and implementation-surfaced refinements:

- **R1 — empty overlay rejection layer.** Initial Step 2 DTO code rejected `overlay=()` in `FactOverlayCheckRequest.__post_init__`, which made the frozen runtime `invalid_request` path mechanically unreachable. Fix `96a8982` moved the rejection to runtime as `status="invalid_request"` / `EMPTY_OVERLAY_NOT_PERMITTED` while allowing DTO construction. This refines the Step 0 contract by making "rejected" explicitly runtime-level, not protocol-shape-level.
- **R2 — phase status narrowing.** Initial Step 2 DTO code allowed `OverlayCheckPhase.status` to use the top-level four-value status literal, permitting impossible phase states such as `unsupported` / `invalid_request`. Fix `96a8982` introduced `OverlayCheckPhaseStatus = Literal["passed", "failed"]` and enforced phase consistency (`passed` requires match; `failed` requires no match). This makes explicit an invariant implied by the Step 0 nullable matrix.
- **R3 — planned Step 3 scaffolding.** Step 3 intentionally used a degenerate `before == after` native result to land the dispatcher and callback pin path before full hardening. Step 4 replaced it with the real double-run algorithm; this was planned sequencing, not a contract deviation.

Archive note:

- Blueprint and audit are ready to move from `docs/blueprints/active/` to `docs/blueprints/archive/`.
