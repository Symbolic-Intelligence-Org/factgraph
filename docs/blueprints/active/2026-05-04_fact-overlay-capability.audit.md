# Task Blueprint Audit: Fact Overlay Capability

- Blueprint: [2026-05-04_fact-overlay-capability.md](./2026-05-04_fact-overlay-capability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-04 | draft | Blueprint created | Opened as the third application capability candidate after Check and Diagnose. Purpose is Step 0 only: decide whether Fact Overlay has a stable application DTO and ledger-write boundary before implementation. |
| 2026-05-04 | draft | Step 0.A source pass complete | Source anchors read from Check and Diagnose archives, B'' FactValueOverride material, current derivation runtime, store evaluator, projector, Store, and ledger surfaces. Four ledger boundary anchors recorded. Fallback order recorded as Overlay → Why-not → Explain. |
| 2026-05-04 | draft | Step 0.A addendum recorded | Review added a fourth narrow projection-merge anchor, sharpened native/non-native boundaries, and set the Step 0.B freeze order plus §6.6 falsifiability test. |
| 2026-05-04 | draft | Step 0.A artifact exposure addendum recorded | Review split internal artifact cache side effects from caller-visible overlay artifact exposure. Step 0.B must choose no exposure, capability-owned exposure, or explicit §6.5 re-open before using `EvidenceEnvelope.engine_payload`. |
| 2026-05-04 | draft | Round 1 review addendum recorded | Three read-only reviewers reported PASS on engine-extension triggers, and missing Step 0.B freeze coverage for Check runtime anchors, Hybrid/Sibling composition, nullable matrix, drift-prevention gates, and active projected fact semantics. |
| 2026-05-04 | draft | Step 0.B proposal drafted | Complete nine-part freeze proposal drafted for review: projection-merge anchor, Sibling composition, Overlay Check shape, before/after result DTO, no artifact exposure, active-visible fact override semantics, native-only support gate, §6.6 still standing, and Step 0.C anti-regression inventory. |
| 2026-05-04 | draft | Step 0.B proposal hardening recorded | Review tightened helper extraction destination, Sibling static guard, concrete overlay field type, empty-overlay policy, and full projected tuple semantics. |
| 2026-05-05 | draft | Step 0.B grounding pass recorded | Grounding corrected helper extraction scope (primary selection stays local), enumerated the four live `Store._remember_*` cache/index write methods, and pinned projected fact tuple position 0 to `e_ref`. |
| 2026-05-05 | draft | Step 0.B review blocker resolved | Review identified chosen-policy regrouping risk in post-projection replacement. Proposal now defines projected-row replacement semantics and rejects changes to schema `group_key_indexes` positions. |
| 2026-05-05 | draft | Step 0.B Round 1 precision findings resolved | Review tightened the Sibling parity mechanism, AST allow-list, no-§6.5 DTO field claim, and `_derivation_match_helpers` pure-helper governance. |
| 2026-05-05 | draft | Step 0.C proposal drafted | C1-C7 drafted: dispatcher preflight/status ordering, native projection-copy algorithm, unsupported short-circuit, result assembly, helper decomposition, §7-Overlay-1 through §7-Overlay-12 drift gates, and Step 0.D lift entry point. |
| 2026-05-05 | draft | Step 0.C review precision findings resolved | Review pinned phase-runtime-error nullability, made projection merge helper private, tightened intent-only DTO wording, and made the no-ledger-write gate API-specific. |
| 2026-05-05 | draft | Step 0.C Round 1 findings resolved | Review found `evaluate_native_where(...)` RuleRef support capture as an indirect live-cache path. Native phases now pin `remember_support_artifact=None`; D8 §6.6 is recorded as Step 0.D review discipline, not a unit-test gate. |
| 2026-05-05 | draft → scoped | Step 0.D lift complete | Step 0.B D1-D9 and Step 0.C C1-C7 lifted into blueprint §5 / §7 / §8. Blueprint status moved `draft → scoped`; implementation authorized only through the six ordered steps and §7-Overlay-1 through §7-Overlay-12 gates. |
| 2026-05-05 | scoped | Step 1 helper extraction complete | Moved Check's `_binding_matches` and `_all_body_vars` into `kernel.application._derivation_match_helpers`, updated Check imports, added focused helper tests, and verified helper tests, Check 73 tests, full kernel unittest discover, and ruff. |
| 2026-05-05 | scoped | Step 2 protocol DTOs complete | Added Fact Overlay protocol DTOs and package exports, plus focused protocol tests covering DTO shape, nullable matrix, intent-only request fields, no §6.5 typed Union expansion, no engine payload field, exact status/engine literals, full kernel unittest discover, and ruff. |
| 2026-05-05 | scoped | Step 2 protocol review fixes complete | Review found two DTO drifts: empty overlay was incorrectly rejected at DTO construction, and `OverlayCheckPhase` allowed impossible / result-level states. DTOs and tests now align with runtime invalid-request handling and phase-only `passed` / `failed` semantics. |
| 2026-05-05 | scoped | Step 3 native MVP scaffolding complete | Added `check_fact_overlay_binding(...)`, dispatcher preflights, non-native unsupported short-circuit, native single-phase evaluation, degenerate before/after no-change result assembly, callback pin coverage, focused runtime tests, full kernel unittest discover, and ruff. |
| 2026-05-05 | scoped | Step 4 native double-run + override hardening complete | Replaced Step 3 degenerate result assembly with baseline + overlay-applied native phases, projection-copy overlay merge, collect-all override validation, phase-summary diff construction, phase runtime-error nullability, expanded focused runtime tests, full kernel unittest discover, and ruff. |

## Decision Notes

- 2026-05-04: Fact Overlay starts as a `draft` blueprint because the DTO shape and ledger boundary are not frozen. Per application-first hard constraint, implementation cannot begin until Step 0 answers "what is the application DTO shape?"

- 2026-05-04: Branch context is `v0.1-fact-overlay-2026-05-04`, cut from `v0.1-engine-capability-declaration-2026-05-04` at `8dac105`. This intentionally inherits §6.6, which makes the third application capability the first migration trigger for capability-declaration re-evaluation.

- 2026-05-04: Step 0.A source-pass file coverage:
  - `docs/blueprints/archive/2026-05-03_check-operation.md` — Check's binding-only, no-fact-overlay boundary and application runtime template.
  - `docs/blueprints/archive/2026-05-04_diagnose-operation.md` / `.audit.md` — four-sub-round Step 0 pattern, local support gates, and Sibling capability discipline.
  - `docs/references/working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md` §6.4 / §6.6 / §7 — `FactValueOverride`, simultaneous `EvaluationOverlay`, no ledger write, and older execution-model warnings.
  - `docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md` §1.3 / §1.4 — "FactValueOverride + Check" identified as the missing pair.
  - `docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md` §P0-1 / §P0-3 / P1 skeleton — no-overlay baseline and current fact read path anchors.
  - `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` §6.6 — third capability trigger and local-gate discipline.
  - `src/kernel/application/protocol/derivation_check.py` — `CheckRequest` / `CheckResult` have no overlay field and Check result nullable semantics are the closest lineage pattern.
  - `src/kernel/application/derivation_check_runtime.py` — current native Check does not call `evaluate_store(...)`; it directly runs `project_view_facts(...)`, `project_view_facts_with_witness(...)`, and `evaluate_native_where(...)`.
  - `src/kernel/application/protocol/derivation.py` — current `DerivationEvaluateRequest` fields (`plans`, `run_id`, `engine`) and no overlay field.
  - `src/kernel/application/derivation_runtime.py` — `evaluate_derivation_plans(request, *, store, registry=None)` pass-through executor.
  - `src/kernel/core/store/_evaluate.py` — `evaluate_store(...)` engine dispatch; native path projects `store.ledger`, non-native path calls adapters through `store.evaluate_engine`.
  - `src/kernel/core/view/projector.py` — `project_view_facts(...)` and `project_view_facts_with_witness(...)` visible-row projection.
  - `src/kernel/core/store/runtime.py` — `Store` owns the concrete `ledger`, engine evaluator dispatch, and in-memory support/provenance artifact caches.
  - `src/kernel/core/store/ledger.py` — append-only ledger with explicit write sessions and append/revocation APIs.

- 2026-05-04 (Step 0.A) — **Candidate ordering.** Primary candidate is Fact Overlay. If Step 0.A / 0.B cannot select a ledger boundary anchor, fallback order is **Why-not → Explain**, not direct Explain. Rationale: Why-not avoids ledger-write semantics and may still pressure capability support meaningfully; Explain is last because it risks being only a projection over existing Check / evidence payloads.

- 2026-05-04 (Step 0.A) — **Leading capability shape.** The leading shape is **Overlay Check**, not broad Overlay Evaluate, because old design material explicitly names the missing pair as `FactValueOverride + Check`. A Check-shaped question (`plan + binding + overlay + engine`) can test the fact-overlay boundary while keeping result semantics narrower than a new evaluate variant. This is a preliminary Step 0.A stance, not a frozen DTO.

- 2026-05-04 (Step 0.A) — **Ledger-write boundary is the DTO stress test.** "Overlay does not write ledger" is insufficient as a contract statement. The implementation anchor determines the DTO and support-boundary shape:
  1. **DTO-carried override list:** request carries override actions; runtime/engine paths apply them directly. Thin request, explicit intent, but complexity spreads across native + souffle + problog + pyreason dispatch.
  2. **DTO override list + narrow projection-merge shim:** request carries override actions; runtime projects current witness facts, merges override effects into that projected `ProjectedFact` set, and feeds the merged projection directly into native evaluation. This is the likely Overlay Check seam because it is not a Store wrapper and not a compiler patch.
  3. **Overlay-aware Store proxy:** request carries override actions; runtime builds an application-local read-intercept store/projection wrapper. Potentially cohesive for broader Overlay Evaluate, but Step 0.B must prove it is a private application primitive rather than a new general substrate.
  4. **Pre-compile patch:** request carries override actions; runtime derives a patched plan/compiled payload. Fact values live in ledger projection, not plan IR, so this is likely ill-fitting for fact override and risks pushing data semantics into compiler / derivation runtime.

- 2026-05-04 (Step 0.A) — **Current evaluator surface pressure.**
  - Native `evaluate_store(...)` calls `project_view_facts_with_witness(store.ledger, store.schema_ir)` then `evaluate_native_where(...)`. Fact overlay must therefore affect projection or supply an alternate witness/view fact set.
  - Non-native `evaluate_store(...)` calls `engine_evaluate(**engine_kwargs)` through `store.evaluate_engine`, and `Store.evaluate_engine(...)` passes the concrete `Store` into registered adapters. Fact overlay cannot transparently affect non-native engines unless the adapter reads through an overlay-aware store or receives explicit overlay/projection input.
  - Current application `evaluate_derivation_plans(...)` returns raw `CandidateSet` and has no application response DTO. Overlay likely needs its own application-owned result DTO because it must report before/after and no-write guarantees, not just raw candidates.

- 2026-05-04 (Step 0.A addendum) — **Native seam sharpened.** Native Fact Overlay does not need Store-time mutation or plan-time mutation. The natural seam is:

  `project_view_facts_with_witness(...) -> projection merge -> evaluate_native_where(...)`

  Step 0.B should treat "native overlay = projection-time merge" as the default hypothesis for Overlay Check. Store proxy remains a broader candidate, not the native default.

- 2026-05-04 (Round 1 addendum) — **Current Check runtime anchor correction.** Overlay Check must account for Check's current native path, not just `evaluate_store(...)`. `check_derivation_binding(...)` dispatches native Check to `_native_check`, which directly projects `view_facts` / `witness_facts` and calls `evaluate_native_where(...)`. Therefore a projection-merge shim scoped only to `evaluate_store(...)` would not affect Overlay Check. Step 0.B must decide whether Overlay Check:
  - is a **Sibling** runtime that owns its own projection merge + matching;
  - is a **Hybrid** runtime that wraps/proxies store then delegates to `check_derivation_binding(...)`;
  - or narrowly reuses/extracts Check-private projection / matching helpers under an explicitly scoped helper contract.

  This is the Overlay counterpart to Diagnose's Q1 Hybrid/Sibling decision. If Hybrid is chosen, Step 0.B must inspect whether Check's behavior would launder any non-overlay semantics into Overlay Check; the known risk is hypothetical artifact/cache contamination rather than Diagnose's lookup-miss laundering.

- 2026-05-04 (Step 0.A addendum) — **Non-native asymmetry sharpened.** Non-native engines have no uniform overlay injection point:
  - Souffle overlay means regenerating `.facts` / exported input and rerunning the Souffle pipeline.
  - ProbLog overlay means rebuilding the weighted-fact program.
  - PyReason overlay means patching graph state / temporal input.

  MVP default is therefore **non-native `unsupported`**, not "maybe unsupported." Step 0.B must decide the exact error semantics, likely a representability-style code such as `ENGINE_OVERLAY_NOT_SUPPORTED`, while preserving the four-value status pattern established by Check / Diagnose unless a stronger reason appears.

- 2026-05-04 (Step 0.A) — **Artifact side-effect open question.** Even without ledger writes, current evaluation may remember `SupportArtifact` / `ProvenanceEnvelope` in the live `Store`'s in-memory artifact caches. Step 0.B must decide whether overlay evaluation may leave hypothetical support artifacts in those caches, or whether overlay evaluation needs isolated artifact capture. This is separate from ledger-write immutability.

- 2026-05-04 (Step 0.A addendum) — **Overlay artifact exposure channel.** Internal artifact cache side effects and caller-visible artifact exposure are separate decisions. Step 0.B must answer:
  1. Does `OverlayCheckResult` expose support/provenance produced under the overlay assumption?
  2. If yes, does it expose through a capability-owned hypothetical field, or through `EvidenceEnvelope.engine_payload`?

  Default hypothesis: **capability-owned or no exposure**. Overlay-derived evidence is hypothetical and should not be silently mixed into Check's ledger-grounded `EvidenceEnvelope.engine_payload` channel. If Step 0.B chooses to expose native engine artifacts through `EvidenceEnvelope.engine_payload`, that is an explicit §6.5 pressure point and should re-open the engine-native payload working hypothesis before implementation.

- 2026-05-04 (Step 0.A) — **Fact override action target.** Old material points at `asrt_id`, and current `project_view_facts_with_witness(...)` emits `ProjectedFact(asrt_id, fact_tuple)`. Step 0.B should start with assertion-scoped `FactValueOverride`, not predicate-wide replacement. Open fields include whether to carry `old_value` / old tuple for defensive validation, and whether `new_value` means one rest term or the full projected fact tuple.

- 2026-05-04 (Round 1 addendum) — **Fact override target semantics.** Assertion-scoped `asrt_id` is a starting point, not the full semantic answer. B'' §5.6.5 and design discussion H1/H2 distinguish:
  - old witness `asrt_id` override;
  - active projected value override for `(pred_id, e_ref)`;
  - multi-cardinality predicate behavior (`replace_all` vs `add_alongside`-style effects).

  Current projection first filters active claims, then applies single-cardinality chosen policy, then emits `ProjectedFact(asrt_id, fact_tuple)`. Step 0.B must freeze whether Fact Overlay modifies only the old witness row for this evaluation, the active projected value for the entity/predicate, or a constrained subset such as active visible projected row only. This decision must happen before `FactValueOverride` fields freeze.

- 2026-05-04 (Step 0.A addendum) — **`old_value` defensive field pressure.** Step 0.B must explicitly decide whether `FactValueOverride` carries an expected old value / old tuple. Carrying it would reject stale caller-side scenarios when the ledger changed between read and overlay request. Omitting it would keep the DTO thinner but treats caller-side concept drift as out of scope. This is a DTO-freeze decision, not implementation detail.

- 2026-05-04 (Step 0.A addendum) — **Before/after result policy.** Step 0.B must choose between:
  - **Encapsulated before/after:** Overlay Check internally runs baseline Check plus overlay-applied Check, returning `before`, `after`, and diff fields. This makes the capability meaningfully third-capability-like, at the cost of two evaluations.
  - **After-only composition:** Overlay Check returns only the overlay-applied result; callers run baseline Check and diff themselves. This is narrower but risks becoming "Check plus overlay arg" rather than a self-contained application capability.

  The two result shapes are incompatible enough that this cannot be deferred to Step 0.C.

- 2026-05-04 (Step 0.A) — **Non-native support likely becomes the §6.6 pressure point.** Native can plausibly be supported by applying overrides at view/witness projection time. Souffle / ProbLog / PyReason may require adapter-specific projection/export changes or may be `unsupported` for MVP. A third local gate is allowed by §6.6, but if the gate becomes "native only because overlay injection cannot be expressed uniformly," Step 0.B should explicitly decide whether to keep the local gate or open engine-extension §6.7.

- 2026-05-04 (Step 0.A addendum) — **§6.6 falsifiability test.** Step 0.B must judge the local-gate working hypothesis using a concrete writing test:
  - If the per-engine support gate can be described in blueprint §5 as a short self-contained paragraph/table, without requiring reader cross-navigation into adapter internals, §6.6 still stands and local gates remain acceptable.
  - If the gate requires a multi-column matrix with adapter-internal details or cross-engine dimensions that are hard to reason about locally, that is a concrete §6.7 trigger before implementation.

- 2026-05-04 (Step 0.A) — **Preliminary non-goal boundary.** RuleDisable is not part of the first Fact Overlay capability even though the old `EvaluationOverlay` container allowed it. Including RuleDisable would re-enter RuleRef substrate semantics and old v0.1.3 disable-condition history; first scope stays fact override only unless Step 0.B proves rule-disable is necessary to make the DTO coherent.

- 2026-05-04 (Step 0.A) — **Step 0.B entry point.** Step 0.B must freeze in this order:
  1. ledger boundary anchor from the four options above, plus artifact cache side-effect policy;
  2. implied runtime composition: Sibling, Hybrid via Check, or narrow reuse / extraction of Check projection + match helpers;
  3. leading request shape: Overlay Check vs Overlay Evaluate;
  4. result DTO policy: encapsulated `before/after/diff` vs `after`-only, plus a per-status nullable matrix;
  5. engine-native artifact exposure channel: no exposure, capability-owned hypothetical field, or explicit §6.5 re-open before using `EvidenceEnvelope.engine_payload`;
  6. `FactValueOverride` fields and validation rules, including active-projection target semantics and old-value / stale-snapshot guard;
  7. per-engine support table, local gate names, and unsupported error semantics;
  8. §6.6 judgment: local gate still readable vs open §6.7 before implementation;
  9. Step 0.C anti-regression gate inventory: no ledger write, artifact isolation/cache policy, no `EvidenceEnvelope.engine_payload` misuse, no accidental non-native support, no Check-delegation laundering, and request DTO side-channel discipline.

Blueprint remains `draft` until Step 0.D lifts decisions into §5 / §7 / §8 and moves status to `scoped`, or records fallback to Why-not.

- 2026-05-04 (Step 0.B proposal) — **D1 Ledger anchor and artifact cache policy.** Choose **DTO override list + narrow projection-merge shim**. The request carries fact override actions; the runtime projects current witness facts, applies a projection-level merge, and feeds the merged projection to native evaluation. No Store proxy and no pre-compile plan patch in MVP. Overlay execution must not write the ledger and must not leave hypothetical artifacts or indexes in the live `Store` caches. If Step 0.C needs support capture internally, use isolated local capture, not live-store write methods.

  Grounding pass enumerated the live-store banned write surface: `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`.

- 2026-05-04 (Step 0.B proposal) — **D2 Runtime composition.** Choose **Sibling**. Overlay Check does not call `check_derivation_binding(...)`. It owns its runtime flow and result DTO. Narrow reuse/extraction of Check-private pure helpers is allowed only for overlay-agnostic binding matching and body-var preflight.

  Helper extraction destination is a new application-internal shared module, expected shape `kernel.application._derivation_match_helpers`. Check and Overlay Check may import only the extracted binding-match and body-var preflight helpers from that module. Overlay Check must not import `derivation_check_runtime.py` or Check protocol result/envelope DTOs. Deterministic primary selection is not extracted; Overlay Check may import existing core helpers (`find_winning_branch_index` and `normalize_binding_items`) and compose its local sort key. This small Check-internal refactor is a prerequisite before Overlay Check implementation, not part of the Overlay runtime itself.

  `_derivation_match_helpers` must remain a pure-helper module: no `Store`, `Registry`, global state access, evaluator dispatch, or cross-capability runtime composition. If future work needs meta-runtime behavior there, it must trigger the same class of architecture review as §6.6/§6.7 rather than silently expanding the helper module.

  The Sibling choice avoids Hybrid cache contamination and avoids laundering Check's ledger-grounded evidence behavior into a hypothetical overlay result. Mechanism: Hybrid via `check_derivation_binding(...)` dispatches into Check's per-engine paths, and those paths can write evaluation artifacts into live `Store` caches through `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`. Overlay Check runs under hypothetical facts, so those live-cache writes would violate D1/D5 artifact isolation. This is the Overlay counterpart to Diagnose's Q1 rejection of Hybrid laundering.

- 2026-05-04 (Step 0.B proposal) — **D3 Leading capability shape.** Choose **Overlay Check**. Overlay Evaluate stays out of scope. The request shape is `FactOverlayCheckRequest(plan, binding, overlay, engine)` with `overlay: tuple[FactValueOverride, ...]`. Empty overlay is rejected with `status="invalid_request"` and `ErrorDTO(code="EMPTY_OVERLAY_NOT_PERMITTED")`; callers with no override should use Check. The runtime side-channel remains `store` and optional `registry`; neither appears on the DTO.

- 2026-05-04 (Step 0.B proposal) — **D4 Result DTO and nullable matrix.** Choose encapsulated before/after. The runtime runs baseline and overlay-applied checks in one call and returns lightweight summaries, not Check `EvidenceEnvelope`s. Top-level `status` uses Check's four values; for completed native runs it equals `after.status`. Nullable matrix:

  | result status | before | after | diff | errors |
  |---|---|---|---|---|
  | `passed` | populated | populated, status=`passed` | populated | empty |
  | `failed` | populated | populated, status=`failed` | populated | empty |
  | `unsupported` | None | None | None | required |
  | `invalid_request` | None | None | None | required |

  Unsupported / invalid preflight happens before baseline execution, so there is no partial `before` phase. `OverlayCheckPhase` carries only `status`, `matched_count`, and `matched_binding`; `matched_binding` is normalized `BindingItems` (`tuple[tuple[str, JSONValue], ...]`). `OverlayCheckDiff` field schema is pinned in Step 0.C; Step 0.B constrains it to status and match-count/binding deltas only, never engine-native proof artifacts.

- 2026-05-04 (Step 0.B proposal) — **D5 Artifact exposure channel.** MVP exposes no overlay-derived engine-native artifacts to callers. `FactOverlayCheckResult` carries `OverlayCheckPhase` and `OverlayCheckDiff` only. `EvidenceEnvelope.engine_payload` is not used. §6.5 remains untouched; a future decision to expose overlay-derived `SupportArtifact` / `ProvenanceEnvelope` through `EvidenceEnvelope` is a §6.5 trigger.

  No result DTO field may reference `EvidenceEnvelope`, `SupportArtifact`, `ProvenanceEnvelope`, or any §6.5 typed Union member. This keeps `OverlayCheckPhase` and `OverlayCheckDiff` capability-owned rather than silently expanding the engine-native artifact channel.

- 2026-05-04 (Step 0.B proposal) — **D6 `FactValueOverride` fields and target semantics.** MVP supports `FactValueOverride(asrt_id, pred_id, e_ref, old_fact_tuple, new_fact_tuple, note=None)`. Semantics: **active visible projected-row replacement only**. The target `asrt_id` must be active and visible in current view projection, `old_fact_tuple` must match the current projected tuple, and `new_fact_tuple` replaces that projected row after chosen projection for this evaluation only. It does **not** mean "pretend the ledger assertion changed before chosen policy ran."

  `old_fact_tuple` and `new_fact_tuple` are full projected predicate argument tuples matching `ProjectedFact.fact_tuple`; `kernel.core.view.projector.build_args_for_claim(...)` builds this as `(claim.e_ref, *val_atoms)`, so `e_ref == fact_tuple[0]`. They must preserve arity. `pred_id` and `e_ref` are defensive guards; `e_ref` must match position 0 of both old and new tuples. Overlay Check cannot use `new_fact_tuple` to migrate the fact to a different entity binding or predicate shape. `new_fact_tuple` must also preserve every schema `group_key_indexes` position from `old_fact_tuple`, because this capability replaces a projected row after chosen policy and does not rerun chosen regrouping. No non-visible stale witness override, predicate-wide replacement, `replace_all`, `add_alongside`, add-fact, RuleDisable, parameter override, or condition override.

- 2026-05-04 (Step 0.B proposal) — **D7 Engine support gate and unsupported semantics.** MVP is native-only. `souffle`, `problog`, and `pyreason` return `status="unsupported"` with `ErrorDTO(code="ENGINE_OVERLAY_NOT_SUPPORTED")`. Rationale is source-backed and engine-specific: Souffle needs regenerated facts/export pipeline, ProbLog needs rebuilt weighted-fact program, and PyReason needs graph-state / temporal input patching. No adapter is invoked for unsupported engines.

- 2026-05-04 (Step 0.B proposal) — **D8 §6.6 judgment.** The local support gate is self-contained: native supported through projection merge; all non-native engines unsupported with one error code. This is short enough to describe locally without cross-adapter support matrix. §6.6 working hypothesis still stands; do not open §6.7 before MVP implementation.

- 2026-05-04 (Step 0.B proposal) — **D9 Step 0.C anti-regression inventory.** Step 0.C must turn these into named acceptance gates before implementation:
  - no ledger write, append, retract, accept, or scenario persistence;
  - no hypothetical artifact or index in live `Store` caches; explicitly ban `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, and `_remember_rule_trace_artifact`;
  - no `EvidenceEnvelope.engine_payload` use for overlay-derived artifacts;
  - no `check_derivation_binding(...)` delegation;
  - AST/static Sibling guard: Overlay Check runtime must not import `derivation_check_runtime`, `check_derivation_binding`, Check result/envelope DTOs, or Check private helpers directly; only the shared `_derivation_match_helpers` module's binding-match/body-var helpers are allowed. Allowed non-Check core utility imports include `kernel.core.store._support_capture.find_winning_branch_index` and `kernel.core.store._support.normalize_binding_items`;
  - non-native engines never dispatch and always return `ENGINE_OVERLAY_NOT_SUPPORTED`;
  - stale `old_fact_tuple` / inactive / non-visible `asrt_id` returns `invalid_request`;
  - empty overlay returns `invalid_request` with `EMPTY_OVERLAY_NOT_PERMITTED`;
  - tuple arity/entity guard violations return `invalid_request`;
  - group-key position changes return `invalid_request`;
  - request DTO remains intent-only: no `store`, `registry`, precomputed projection, or cache fields.

- 2026-05-05 (Step 0.C proposal) — **C1 Dispatcher ordering and status precedence.** Overlay Check dispatcher runs request-level invalid preflights before engine support:
  1. normalize request-level fields and reject `overlay=()` as `invalid_request` / `EMPTY_OVERLAY_NOT_PERMITTED`;
  2. run Overlay Check's own RuleRef preflight; failures return `invalid_request`;
  3. apply the capability-owned engine support gate; non-native engines short-circuit at dispatcher entry with `unsupported` / `ENGINE_OVERLAY_NOT_SUPPORTED`, with no adapter invocation and no baseline phase;
  4. for native only, project current visible facts with witnesses;
  5. validate each `FactValueOverride` against the projected witness set;
  6. run baseline and overlay phases only after validation succeeds.

  Status assembly follows this order: request-shape / RuleRef invalids before unsupported; unsupported before native projection-dependent override validation; native projection / override validation errors as `invalid_request`; completed native runs set top-level `status = after.status`.

- 2026-05-05 (Step 0.C proposal) — **C2 Native algorithm.** Native Overlay Check uses the frozen seam:

  `project_view_facts_with_witness(...) -> _apply_fact_overlay_projection(...) -> evaluate_native_where(...) -> binding match`

  Runtime first builds the baseline phase from unmodified projected witness facts. It then builds an overlay projected witness copy with `_apply_fact_overlay_projection(overrides, projected_witness_facts)`. Each phase converts projected witnesses to the `pred_id -> list[fact_tuple]` shape required by `evaluate_native_where(...)`, evaluates the same plan body / requested binding / RuleRef resolutions with `remember_support_artifact=None`, and applies `_binding_matches`-style subset matching to final bindings.

  Execution is sequential for MVP: baseline first, overlay second. The phases may share the immutable original projection snapshot, but the overlay projection must be a derived copy. No phase may write into live `Store` caches or reuse mutable capture state.

  Overlay does not capture support artifacts in either phase, consistent with D5 no-exposure. The `remember_support_artifact` callback is explicitly `None` to prevent indirect live-cache writes through `evaluate_native_where(...)` RuleRef support capture.

  Phase-execution runtime errors propagate through the `errors` channel, not through partial phase population. If either baseline or overlay phase raises a runtime error, `before`, `after`, and `diff` are all `None`, even if the baseline phase had already completed.

- 2026-05-05 (Step 0.C proposal) — **C3 Result assembly and diff source.** `OverlayCheckPhase` is built from phase-local status, matched count, and normalized matched binding only. `OverlayCheckDiff` is computed only from the two `OverlayCheckPhase` summaries: status delta, match-count delta, and binding deltas. It never reads support/provenance artifacts or any engine-native payload channel.

- 2026-05-05 (Step 0.C proposal) — **C4 Non-native short-circuit.** Souffle, ProbLog, and PyReason return `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED` at dispatcher entry. This short-circuit happens before any adapter dispatch and before any baseline result is assembled, so `before`, `after`, and `diff` are all `None`.

- 2026-05-05 (Step 0.C proposal) — **C5 Function decomposition shape.** Step 0.C freezes names and roles only, not full signatures:
  - `check_fact_overlay_binding(...)`: application entry point;
  - `_overlay_engine_support_preflight(...)`: dispatcher-level engine gate;
  - `_overlay_ruleref_preflight(...)`: Overlay-owned RuleRef preflight, not imported from Check;
  - `_apply_fact_overlay_projection(...)`: pure projection-copy merger for `FactValueOverride`;
  - `_validate_fact_value_overrides(...)`: native projected-row defensive validation;
  - `_run_native_overlay_phase(...)`: native phase evaluator returning `OverlayCheckPhase` and calling `evaluate_native_where(..., remember_support_artifact=None)`;
  - `_build_overlay_diff(...)`: phase-summary-only diff builder.

- 2026-05-05 (Step 0.C proposal) — **C6 Drift prevention §7-Overlay mapping.** Step 0.D must lift these named gates into §7 Acceptance before implementation:
  - **§7-Overlay-1** (Sibling no-Check-call invariant): static AST/import check that Overlay Check runtime never imports `check_derivation_binding`, `derivation_check_runtime`, Check result/envelope DTOs, or Check private helpers. Allow-list: `_derivation_match_helpers` binding-match/body-var helpers plus `kernel.core.store._support_capture.find_winning_branch_index` and `kernel.core.store._support.normalize_binding_items`.
  - **§7-Overlay-2** (intent-only request DTO): type/field test that `FactOverlayCheckRequest` dataclass fields are exactly `plan`, `binding`, `overlay`, and `engine`; no `store`, `registry`, precomputed projection, or cache fields appear as DTO fields. `store` and optional `registry` remain runtime side-channel kwargs to `check_fact_overlay_binding(...)`, not DTO members.
  - **§7-Overlay-3** (no ledger write): runtime test that overlay execution leaves `store.ledger` byte-identical and never calls `append_assertion`, `append_revocation`, `accept_*`, or any other ledger-write entry.
  - **§7-Overlay-4** (no live cache contamination): runtime spy/monkeypatch test that overlay execution does not call `_remember_support_artifact`, `_remember_provenance_envelope`, `_remember_candidate_support`, or `_remember_rule_trace_artifact`; spy/argument inspection also confirms each `_run_native_overlay_phase(...)` call to `evaluate_native_where(...)` passes `remember_support_artifact=None`.
  - **§7-Overlay-5** (non-native dispatcher short-circuit): souffle, problog, and pyreason return `unsupported` with `ENGINE_OVERLAY_NOT_SUPPORTED`; adapters are not invoked and `before` / `after` / `diff` are `None`.
  - **§7-Overlay-6** (empty overlay rejected): `overlay=()` returns `invalid_request` with `EMPTY_OVERLAY_NOT_PERMITTED`.
  - **§7-Overlay-7** (projected-row stale/visibility guards): stale `old_fact_tuple`, inactive `asrt_id`, and non-visible `asrt_id` each return `invalid_request`.
  - **§7-Overlay-8** (tuple shape guards): tuple arity violations and `e_ref != fact_tuple[0]` return `invalid_request`.
  - **§7-Overlay-9** (chosen-policy group-key guard): any `new_fact_tuple` change to schema `group_key_indexes` positions returns `invalid_request`.
  - **§7-Overlay-10** (§6.5 non-expansion): type-level test that `OverlayCheckPhase` and `OverlayCheckDiff` fields do not reference `EvidenceEnvelope`, `SupportArtifact`, `ProvenanceEnvelope`, or any §6.5 typed Union member.
  - **§7-Overlay-11** (no engine payload field): result DTO field absence test that `FactOverlayCheckResult` has no `evidence_envelope`, `engine_payload`, support-artifact, or provenance-envelope field.
  - **§7-Overlay-12** (status and nullable matrix): type/runtime test that result status contains exactly `passed`, `failed`, `unsupported`, and `invalid_request`, and that unsupported / invalid results have `before=None`, `after=None`, and `diff=None`.

- 2026-05-05 (Step 0.C proposal) — **C7 Step 0.D entry point.** Step 0.D should lift Step 0.B D1-D9 and Step 0.C C1-C6 into blueprint §5, §7, and §8, mark Step 0.C complete if review closes without material changes, and move blueprint status `draft -> scoped`. Implementation remains unauthorized until that lift.

  D8 (§6.6 working hypothesis still stands) is a documentation-discipline judgment, not a unit-testable gate. It is verified at Step 0.D blueprint review and re-verified at any future blueprint amendment of the §5.6 engine support table. This mirrors Diagnose's §6.6 handling: local-gate readability is editorial, not regression-tested.

- 2026-05-05 (Step 0.D) — **Step 0.D lift complete; status `draft -> scoped`.** Step 0.B and Step 0.C decisions were lifted into the canonical blueprint sections:
  - **§5 Proposed Shape** now contains the authoritative Overlay Check contract: capability shape, ledger anchor/runtime composition, `FactValueOverride` DTO, artifact/evidence policy, result DTO policy, engine support gate, algorithm freeze, and engine-extension conformance note.
  - **§7 Acceptance** now contains Step 0 closure, §7-Overlay-1 through §7-Overlay-12 anti-regression gates, layer placement, code health, and cross-doc acceptance.
  - **§8 Implementation Plan** now contains complete Step 0 history plus six ordered implementation steps: helper extraction prerequisite refactor, protocol DTOs, native MVP scaffolding, native double-run + override hardening, drift-prevention named gates, and close-out.

  Cross-consistency check: every D1-D9 and C1-C7 decision has a home in §5, §7, or §8. D8 remains review-discipline only and is recorded in §5.8 rather than forced into a unit-test gate. Implementation may start, but any future change to §5 contract, §7 acceptance gates, or §8 plan requires a new audit entry before code changes.

- 2026-05-05 (Implementation Step 1) — **Helper extraction prerequisite refactor complete.** Created `src/kernel/application/_derivation_match_helpers.py` and moved Check's pure `_binding_matches(...)` and `_all_body_vars(...)` helpers there without renaming. `derivation_check_runtime.py` now imports those helpers from the shared application-internal module. Added direct unit coverage in `test_application_derivation_match_helpers.py` for subset matching, mismatch, empty requested binding, plain body vars, `not` body vars, and `ruleref` term vars.

  Verification:
  - `python -m unittest src.kernel.tests.test_application_derivation_match_helpers` — 6 tests OK
  - `python -m unittest src.kernel.tests.test_application_check_runtime src.kernel.tests.test_application_check_protocol` — 73 tests OK
  - `python -m unittest discover -s src/kernel/tests` — 872 tests OK, 1 skipped
  - `python -m ruff check src/kernel` — clean

- 2026-05-05 (Implementation Step 2) — **Fact Overlay protocol DTOs complete.** Added `src/kernel/application/protocol/derivation_fact_overlay.py` with local Sibling protocol types: `OverlayCheckStatus`, `OverlayCheckEngine`, `FactValueOverride`, `FactOverlayCheckRequest`, `OverlayCheckPhase`, `OverlayCheckDiff`, and `FactOverlayCheckResult`. Exported the DTOs from `kernel.application.protocol`.

  Protocol behavior landed:
  - `FactOverlayCheckRequest` remains intent-only (`plan`, `binding`, `overlay`, `engine`) and allows empty overlay so the runtime can classify it as `invalid_request` / `EMPTY_OVERLAY_NOT_PERMITTED`.
  - `OverlayCheckPhase.matched_count` is a non-null non-negative `int`.
  - `OverlayCheckDiff` is delta-only: `status_changed`, signed `matched_count_delta`, `bindings_added`, and `bindings_removed`.
  - `FactOverlayCheckResult` enforces the frozen nullable matrix for `passed`, `failed`, `unsupported`, and `invalid_request`.
  - DTO module does not import `EvidenceEnvelope`, `SupportArtifact`, or `ProvenanceEnvelope`, and result DTO has no engine payload / evidence field.

  Verification:
  - `python -m unittest src.kernel.tests.test_application_fact_overlay_protocol` — 38 tests OK
  - `python -m unittest discover -s src/kernel/tests` — 910 tests OK, 1 skipped
  - `python -m ruff check src/kernel` — clean

- 2026-05-05 (Implementation Step 2 review fix) — **Protocol DTO drift corrected before Step 3.** Code review found two P1 mismatches with the frozen blueprint:
  1. `FactOverlayCheckRequest` rejected `overlay=()` during DTO construction, making the §7-Overlay-6 runtime `invalid_request` path unreachable.
  2. `OverlayCheckPhase` used the full result status literal and accepted impossible phase states such as `passed` with zero matches or `unsupported` as a populated phase.

  Fixes:
  - `FactOverlayCheckRequest` now accepts empty `overlay`; Step 3 dispatcher remains responsible for returning `invalid_request` / `EMPTY_OVERLAY_NOT_PERMITTED`.
  - Added `OverlayCheckPhaseStatus = Literal["passed", "failed"]`; `OverlayCheckPhase` now rejects result-level statuses and enforces `passed => matched_count >= 1 + matched_binding`, `failed => matched_count == 0 + matched_binding=None`.
  - Protocol package exports `OverlayCheckPhaseStatus`.

  Verification:
  - `python -m unittest src.kernel.tests.test_application_fact_overlay_protocol` — 42 tests OK
  - `python -m unittest discover -s src/kernel/tests` — 914 tests OK, 1 skipped
  - `python -m ruff check src/kernel` — clean

- 2026-05-05 (Implementation Step 3) — **Native MVP scaffolding complete.** Added `src/kernel/application/fact_overlay_runtime.py` with the public entry `check_fact_overlay_binding(...)`, Overlay-owned RuleRef preflight, native-only support gate, non-native `ENGINE_OVERLAY_NOT_SUPPORTED` short-circuit, and `_run_native_overlay_phase(...)`.

  Step 3 native result shape is intentionally **degenerate scaffolding**: the runtime executes one native phase against current committed facts, then returns `before == after` and `OverlayCheckDiff(status_changed=False, matched_count_delta=0, bindings_added=(), bindings_removed=())`. Step 4 replaces this with real baseline + overlay-applied double-run, `_apply_fact_overlay_projection(...)`, override validation, and true diff construction.

- 2026-05-05 (Implementation Step 4) — **Native double-run + override validation hardening complete.** Step 4 replaced the Step 3 degenerate result path with the frozen native sequence:

  `project_view_facts_with_witness(...) -> baseline phase -> _apply_fact_overlay_projection(...) -> overlay phase -> _build_overlay_diff(...)`

  Override validation now runs after projection and before any native phase. It collects all detected override errors and returns `invalid_request` without calling `evaluate_native_where(...)` when validation fails. Covered validation codes are `OVERLAY_DUPLICATE_ASRT_ID`, `OVERLAY_ASRT_ID_NOT_VISIBLE`, `OVERLAY_STALE_OLD_FACT_TUPLE`, `OVERLAY_TUPLE_ARITY_MISMATCH`, `OVERLAY_E_REF_POSITION_MISMATCH`, and `OVERLAY_GROUP_KEY_CHANGED`.

  `_apply_fact_overlay_projection(...)` is a pure projection-copy merger over `ProjectedFact` rows and does not mutate the baseline projected witness. `_build_overlay_diff(...)` computes status, count, added-binding, and removed-binding deltas only from `OverlayCheckPhase` summaries. Native phases still call `evaluate_native_where(..., remember_support_artifact=None)`; focused tests now assert both baseline and overlay phase calls keep the callback pinned to `None`.

  Phase execution errors return `invalid_request` with `OVERLAY_PHASE_RUNTIME_ERROR` and no partial `before` / `after` / `diff`, matching C2's no-partial-phase policy. Step 5 still needs to lift the hardening coverage into the named §7-Overlay-1 through §7-Overlay-12 drift gate files/classes.

  Guardrails landed now:
  - `overlay=()` returns `invalid_request` / `EMPTY_OVERLAY_NOT_PERMITTED`.
  - RuleRef preflight is Overlay-owned and does not import Check runtime helpers.
  - Non-native engines short-circuit before adapter dispatch.
  - Native phase calls `evaluate_native_where(..., remember_support_artifact=None)`.

  Verification:
  - `python -m unittest src.kernel.tests.test_application_fact_overlay_runtime_native` — 8 tests OK
  - `python -m unittest src.kernel.tests.test_application_fact_overlay_protocol` — 42 tests OK
  - `python -m unittest discover -s src/kernel/tests` — 922 tests OK, 1 skipped
  - `python -m ruff check src/kernel` — clean
