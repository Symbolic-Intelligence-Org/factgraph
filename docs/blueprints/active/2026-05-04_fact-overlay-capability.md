# Task Blueprint: Fact Overlay Capability

- Status: draft
- Created: 2026-05-04
- Last Updated: 2026-05-04
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

This blueprint is opened in `draft` for Step 0 only. No implementation may start until Step 0 freezes an application DTO shape and the ledger-write boundary.

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

- No code implementation while status is `draft`.
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

Step 0.A is source-pass-only. The current working shape is deliberately not frozen.

### Candidate capability shapes

1. **Overlay Check:** `FactOverlayCheckRequest(plan, binding, overlay, engine)` returning Check-like before/after status and a compact diff. This is the leading candidate because it composes the already-shipped Check operation with the missing `FactValueOverride` scenario.
2. **Overlay Evaluate:** `FactOverlayEvaluateRequest(plans, overlay, engine)` returning after-candidates and maybe before/after comparison metadata. This is broader and may collapse into a variant of `evaluate_derivation_plans(...)` unless the result DTO is carefully application-owned.
3. **Source-pass fallback:** if Step 0.A cannot select a ledger boundary anchor, Fact Overlay is not scoped; the next candidate is Why-not, then Explain.

### Ledger boundary anchors to decide in Step 0

1. **DTO-carried override list.** The request carries a normalized tuple of fact override actions. Each engine path receives and applies overrides explicitly. This keeps the DTO honest but pushes overlay mechanics into all four engine paths.
2. **DTO override list + narrow projection-merge shim.** The request carries explicit overrides; the runtime projects current facts, merges overrides into the projected `ProjectedFact` set, and feeds the result directly to native evaluation. This is narrower than a Store proxy and may be the correct Overlay Check anchor.
3. **Overlay-aware Store proxy.** The runtime builds an application-local read-intercept wrapper around the store so existing evaluate paths read projected overlay facts without mutating the ledger. This may be useful for broader Overlay Evaluate, but Step 0 must prove it is an application primitive and not a new general substrate.
4. **Pre-compile patch.** The runtime derives a patched plan or compiled payload. This looks thin at the DTO layer, but fact values live in ledger/view projection, not the plan. It risks pushing data override semantics into compiler / derivation runtime and may be out of scope for fact override.

### Preliminary boundary stance

- Fact overrides are simultaneous and declarative, not an ordered script.
- Overlay action target semantics must distinguish old witness `asrt_id`, active projected `(pred_id, e_ref)` value, and multi-cardinality add/replace behavior before the DTO freezes.
- A fact overlay must not call `append_assertion`, `append_revocation`, `accept_*`, or write scenario metadata.
- Step 0.B must decide whether support/provenance artifacts produced during an overlay run may be remembered in the live store's in-memory artifact caches, or whether overlay runs need isolated artifact capture.
- Step 0.B must separately decide whether overlay-derived support/provenance artifacts are exposed to callers at all, and if so through a capability-owned field rather than `EvidenceEnvelope.engine_payload` unless §6.5 is explicitly re-opened.
- Native overlay should start from the narrow seam between `project_view_facts_with_witness(...)` and `evaluate_native_where(...)`, not from Store mutation or plan mutation.
- Non-native engines are presumed `unsupported` for MVP unless Step 0.B finds a source-backed uniform injection point.

### Step 0.B proposal (draft for review)

This section proposes the Step 0.B freeze. It remains draft until accepted in the audit.

#### 5.1 Capability shape

The first Fact Overlay capability is **Overlay Check**:

`FactOverlayCheckRequest(plan, binding, overlay, engine) -> FactOverlayCheckResult`

Overlay Evaluate remains out of scope. The capability answers "under these temporary fact overrides, does this requested binding pass, and how does that differ from the current committed-fact baseline?"

#### 5.2 Ledger anchor and runtime composition

Chosen anchor: **DTO override list + narrow projection-merge shim**.

Runtime composition: **Sibling**, with narrow reuse/extraction of Check-private pure helpers allowed. Overlay Check does not call `check_derivation_binding(...)`. It owns its request/result DTOs, projection merge, baseline/overlay evaluation flow, and unsupported semantics. Shared helper extraction is allowed only for overlay-agnostic binding matching and body-var preflight.

Helper extraction destination: new application-internal shared module, expected shape `kernel.application._derivation_match_helpers`. Check and Overlay Check may import only the extracted binding-match and body-var preflight helpers from that module. Overlay Check must not import `derivation_check_runtime.py` or Check protocol result/envelope DTOs. Deterministic primary selection is not extracted; Overlay Check may import existing core helpers (`find_winning_branch_index` and `normalize_binding_items`) and compose its local sort key. This helper extraction is a prerequisite refactor before Overlay Check implementation, not part of the Overlay runtime itself.

`_derivation_match_helpers` remains a pure-helper module: no `Store`, `Registry`, global state access, evaluator dispatch, or cross-capability runtime composition. If future work needs meta-runtime behavior there, it must trigger the same class of architecture review as §6.6/§6.7 rather than silently expanding the helper module.

Hybrid via `check_derivation_binding(...)` is rejected because Check's per-engine paths can write evaluation artifacts into live `Store` caches through `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`. Overlay Check runs under hypothetical facts, so delegating through Check would risk leaving hypothetical artifacts in live caches and would launder ledger-grounded evidence behavior into an overlay result.

The native seam is:

`project_view_facts_with_witness(...) -> apply_fact_overlay_projection(...) -> evaluate_native_where(...)`

No Store proxy and no pre-compile plan patch are used in MVP.

#### 5.3 Overlay action DTO

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

#### 5.4 Artifact and evidence policy

Overlay execution must not write the ledger and must not leave hypothetical artifacts or indexes in live `Store` caches. The live-store banned write surface is: `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`.

MVP does not expose overlay-derived engine-native artifacts to callers. `FactOverlayCheckResult` carries lightweight phase summaries, not `EvidenceEnvelope`. Therefore §6.5 is not re-opened. A future decision to expose overlay-derived `SupportArtifact` / `ProvenanceEnvelope` through `EvidenceEnvelope.engine_payload` is a §6.5 trigger.

#### 5.5 Result DTO policy

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

#### 5.6 Engine support gate

MVP support is native-only:

| Engine | Overlay Check support | Result |
|---|---|---|
| `native` | supported via projection merge | `passed` / `failed` / `invalid_request` |
| `souffle` | unsupported; requires regenerated exported facts and adapter pipeline changes | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |
| `problog` | unsupported; requires rebuilt weighted-fact program | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |
| `pyreason` | unsupported; requires graph-state / temporal input patching | `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` |

This gate is self-contained and capability-owned; §6.6 still stands. No §6.7 declarative capability round is required before MVP implementation.

#### 5.7 Step 0.C anti-regression inventory

Step 0.C must map these gates to tests before implementation:

- no ledger write or append/retract/accept call;
- no hypothetical artifact or index left in live `Store` caches; explicitly ban `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`;
- no `EvidenceEnvelope.engine_payload` use for overlay-derived artifacts;
- no `check_derivation_binding(...)` delegation or Check runtime laundering;
- AST/static Sibling guard: Overlay Check runtime must not import `derivation_check_runtime`, `check_derivation_binding`, Check result/envelope DTOs, or Check private helpers directly; only the shared `_derivation_match_helpers` module's binding-match/body-var helpers are allowed. Allowed non-Check core utility imports include `kernel.core.store._support_capture.find_winning_branch_index` and `kernel.core.store._support.normalize_binding_items`;
- non-native engines always return `ENGINE_OVERLAY_NOT_SUPPORTED`;
- stale `old_fact_tuple` or non-active/non-visible `asrt_id` returns `invalid_request`;
- empty overlay returns `invalid_request` with `EMPTY_OVERLAY_NOT_PERMITTED`;
- tuple arity/entity guard violations return `invalid_request`;
- group-key position changes return `invalid_request`;
- request DTO remains intent-only: no store, registry, precomputed projections, or caches.

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
- [ ] Step 0.B freezes request / overlay action / result DTO shape
- [ ] Step 0.B freezes the ledger-write boundary anchor
- [ ] Step 0.C freezes algorithm and engine representability boundaries
- [ ] Step 0.D lifts Step 0 decisions into this blueprint and moves status to `scoped`, or records abandonment / fallback

### 7.2 Implementation acceptance (placeholder; not active while draft)

- [ ] Protocol DTOs live under `kernel.application.protocol/`
- [ ] Runtime entry lives under `kernel.application/`
- [ ] Runtime dependencies flow through side-channel kwargs, not DTO fields
- [ ] Tests prove the original ledger is unchanged after overlay execution
- [ ] Tests cover supported, unsupported, and invalid overlay paths
- [ ] Tests cover local engine gates and any §6.6 migration decision
- [ ] Affected module docs are updated

## 8. Implementation Plan

**Step 0 only while draft:**

1. **Step 0.A — Source pass + structural pressure inventory.** Read Check/Diagnose archives, old FactValueOverride material, current `evaluate_derivation_plans(...)`, `evaluate_store(...)`, projector, Store, and ledger surfaces. Record the four ledger boundary anchors and fallback order.
2. **Step 0.B — DTO + ledger boundary freeze.** Decide the leading capability shape, overlay action fields, result vocabulary, artifact side-effect policy, and whether §6.6 still holds locally.
3. **Step 0.C — Algorithm + drift-prevention freeze.** Decide per-engine support, runtime flow, and anti-regression gates.
4. **Step 0.D — Lift or fallback.** Move to `scoped` only if DTO and ledger boundary are stable. Otherwise record fallback to Why-not, then Explain.

No code implementation steps are authorized until Step 0.D.

Step 0.B should freeze in this order:

1. Ledger anchor and artifact cache policy.
2. Implied runtime composition: Sibling, Hybrid via Check, or narrow reuse of Check-private projection/match helpers. This must be frozen alongside the ledger anchor.
3. Leading shape: Overlay Check vs Overlay Evaluate.
4. Result DTO before/after policy and a per-status nullable matrix.
5. Engine-native artifact exposure channel: no exposure, capability-owned hypothetical artifact field, or explicit §6.5 re-open before using `EvidenceEnvelope.engine_payload`.
6. `FactValueOverride` fields, including target semantics and whether `old_value` / old tuple is a defensive concurrency guard.
7. Per-engine support gate and exact unsupported semantics.
8. §6.6 judgment using the self-contained-gate test: if the local gate can be described in blueprint §5 in no more than a short paragraph/table without cross-adapter detail, the working hypothesis still stands; otherwise open §6.7 before implementation.
9. Step 0.C anti-regression gate inventory, including no ledger write, no live artifact-cache contamination if isolated capture is chosen, no `EvidenceEnvelope.engine_payload` misuse, no accidental non-native support, and no Check-delegation laundering.

## 9. Docs To Update

Expected only if implementation proceeds:

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `src/kernel/application/docs/README.md` if a new durable module doc entry is introduced
- `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` if §6.6 escalates into §6.7

## 10. Outcome / Deviations

Task completion will fill:

- Final landed result:
- With / without implementation:
- Deviations from Step 0:
- Archive or fallback note:
