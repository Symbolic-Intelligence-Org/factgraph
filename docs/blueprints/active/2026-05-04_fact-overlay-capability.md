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
- Overlay action targets should be assertion-scoped first (`asrt_id`) because the old material and current projector both identify selected facts by assertion rows.
- A fact overlay must not call `append_assertion`, `append_revocation`, `accept_*`, or write scenario metadata.
- Step 0.B must decide whether support/provenance artifacts produced during an overlay run may be remembered in the live store's in-memory artifact caches, or whether overlay runs need isolated artifact capture.
- Step 0.B must separately decide whether overlay-derived support/provenance artifacts are exposed to callers at all, and if so through a capability-owned field rather than `EvidenceEnvelope.engine_payload` unless §6.5 is explicitly re-opened.
- Native overlay should start from the narrow seam between `project_view_facts_with_witness(...)` and `evaluate_native_where(...)`, not from Store mutation or plan mutation.
- Non-native engines are presumed `unsupported` for MVP unless Step 0.B finds a source-backed uniform injection point.

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
2. Leading shape: Overlay Check vs Overlay Evaluate.
3. Result DTO before/after policy: internally run baseline+overlay and return diff, or return overlay-after only.
4. Engine-native artifact exposure channel: no exposure, capability-owned hypothetical artifact field, or explicit §6.5 re-open before using `EvidenceEnvelope.engine_payload`.
5. `FactValueOverride` fields, including whether `old_value` / old tuple is a defensive concurrency guard.
6. Per-engine support gate and exact unsupported semantics.
7. §6.6 judgment using the self-contained-gate test: if the local gate can be described in blueprint §5 in no more than a short paragraph/table without cross-adapter detail, the working hypothesis still stands; otherwise open §6.7 before implementation.

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
