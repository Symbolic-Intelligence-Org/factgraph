# Task Blueprint: Why-not Universe Diagnose Capability

- Status: scoped
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
  - `src/kernel/adapters/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md](../../references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
  - [docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../archive/2026-05-03_check-operation.md)
  - [docs/blueprints/archive/2026-05-04_diagnose-operation.md](../archive/2026-05-04_diagnose-operation.md)
  - [docs/blueprints/archive/2026-05-04_fact-overlay-capability.md](../archive/2026-05-04_fact-overlay-capability.md)
- Audit Log:
  - [2026-05-05_why-not-universe-diagnose-capability.audit.md](./2026-05-05_why-not-universe-diagnose-capability.audit.md)

## 1. Problem

Check, Diagnose, and Fact Overlay have shipped as application-first capabilities. They validate the DTO + runtime pattern and keep engine-extension §6.6's locally hardcoded capability gate working hypothesis standing.

The next high-signal pressure point is Why-not: users eventually want to ask what almost matched, what was excluded, and why. Unlike Check / Diagnose / Fact Overlay, true Why-not appears to require either an explicit candidate universe or evaluator/adapter near-miss traces. This blueprint exists only to run Step 0 and decide whether a crisp application DTO exists. If it does not, the valid output is abandonment or reclassification as evaluator architecture work.

## 2. Goals

- Run a source-backed Step 0 for Why-not before any code implementation.
- Decide whether the capability has a crisp application DTO shape.
- Separate three possible shapes that old references often conflate:
  - lazy candidate-universe red/green carriers;
  - lazy candidate-universe carriers with inline bounded Diagnose;
  - true evaluator near-miss / exclusion-reason Why-not.
- Determine whether Why-not keeps §6.6 local gates readable or triggers §6.7 declarative capability work.
- Record a valid abandonment path if the DTO shape depends on a new evaluator hook.

## 3. Non-goals

- No implementation before Step 0 moves this blueprint to `scoped`.
- No evaluator hook, trace callback, adapter change, carrier persistence, audit package write, SDK shell, UI, or release-base action in this scoped capability.
- No broad Explain renderer.
- No red/green completeness claim without an explicit finite candidate universe.
- No `search_budget` / `limit` field as a substitute for a bounded algorithm.
- No new substrate in `kernel.sdk`.
- No changes to `v0.1-oss-prep` or `master`.

## 4. Current Context

### Shipped capability pattern

The three shipped application capabilities share these properties:

- Request DTOs are intent-only and live under `kernel.application.protocol`.
- Runtime functions take `store` and optional `registry` through side-channel kwargs.
- Status vocabularies and payloads are capability-owned.
- Local engine gates are acceptable when they can be described clearly and tested locally.
- Sibling composition is preferred when delegation would launder another capability's behavior.

### Source-backed Why-not anchors

- L6 is documented as "Lazy why-not / candidate-universe board" and explicitly deferred because it needs a new evaluator hook to capture near-misses.
- B'' material says lazy red traces require an explicit, finite candidate universe aligned with the rule head/select identity.
- Existing `evaluate_native_where(...)` returns `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`; it does not expose failed branches, rejected environments, exclusion reasons, or near-miss state.
- Diagnose's native atom localization is a bounded post-failure localizer for one requested binding. It is not a candidate-universe or near-miss trace API.
- Souffle, ProbLog, and PyReason adapters return derived candidates plus success support/provenance. They do not expose failed candidate traces through the current application contract.

## 5. Proposed Shape

This contract is frozen by Step 0 (0.A source pass / 0.B DTO crispness decision / 0.C algorithm and gate freeze). Implementation may begin only within this shape.

### 5.1 Capability Shape

The selected capability is **Why-not Universe Diagnose**:

`WhyNotUniverseRequest(plan, candidate_universe, engine) -> WhyNotUniverseResult`

It answers: "For this explicit finite universe of possible head bindings, which bindings are derived, which are not, and what bounded Diagnose result is available for each red binding?"

This is intentionally not full evaluator near-miss Why-not. It is a bounded red/green universe board with row-level diagnostics.

Rejected alternatives:

- **Pure carrier board:** crisp but lower signal because row-level "why" is deferred to caller-side per-row calls.
- **True near-miss / exclusion-reason Why-not:** outside this scope because current evaluators and adapters do not expose failed-frontier / near-miss trace data without new architecture work.

### 5.2 Request DTO

Frozen request fields:

| Field | Meaning |
|---|---|
| `plan: CompiledDerivationPlan` | Single derivation plan; exactly one head |
| `candidate_universe: tuple[BindingItems, ...]` | Explicit finite universe of complete head bindings |
| `engine: Literal["native", "souffle", "problog", "pyreason"]` | Required engine; no default |

Request invariants:

- `candidate_universe` is a tuple of normalized `BindingItems`.
- Each universe binding must use exactly the plan head variable names. Body-only variables are invalid in the universe.
- Duplicate universe bindings are invalid; the board is set-like.
- Empty universe is allowed and returns a completed empty board.
- No `store`, `registry`, `search_budget`, `limit`, `mode`, `diagnostic_mode`, `engine_options`, `run_id`, query handle, precomputed candidates, or precomputed green set appears on the request DTO.
- Runtime dependencies remain side-channel kwargs: `check_why_not_universe(request, *, store, registry=None)`.

### 5.3 Result DTO

Frozen result fields:

| Field | Meaning |
|---|---|
| `status: Literal["completed", "unsupported", "invalid_request"]` | Batch-level status |
| `requested_universe: tuple[BindingItems, ...]` | Normalized universe echo |
| `green: tuple[BindingItems, ...]` | Universe bindings derived by evaluate |
| `red: tuple[WhyNotRedRow, ...]` | Universe bindings not derived, with row-level diagnostic summaries |
| `errors: tuple[ErrorDTO, ...]` | Batch-level errors |
| `warnings: tuple[WarningDTO, ...]` | Batch-level warnings |

Top-level nullable / population matrix:

| status | green | red | errors |
|---|---|---|---|
| `completed` | populated or empty | populated or empty | empty |
| `unsupported` | empty | empty | required |
| `invalid_request` | empty | empty | required |

Row-level unsupported diagnostics do not make the top-level result `unsupported`; they live on the corresponding red row. Row-level `invalid_request` is not a normal Why-not result after request preflight and maps to a runtime invariant error per §5.12. Top-level non-completed statuses are reserved for request-wide failures before the board can be assembled.

### 5.4 Red Row DTO

Frozen row shape:

| Field | Meaning |
|---|---|
| `binding: BindingItems` | Red universe binding |
| `diagnostic: WhyNotRowDiagnostic` | Why-not-owned copy of the bounded Diagnose outcome for this binding |

`WhyNotRowDiagnostic` is a capability-owned DTO. It copies Diagnose's stable row semantics but does **not** nest `DiagnoseResult`. Step 0.C narrows the row shape to fields meaningful for red rows only.

| Field | Meaning |
|---|---|
| `status: Literal["failed", "unsupported"]` | Per-row diagnostic status; `passed` is impossible for a red row |
| `failure_kind: Literal["no_candidate", "atom_localized"] | None` | Diagnose-compatible failure kind |
| `diagnostic_granularity: Literal["atom_localized", "coarse", "unavailable"]` | Row diagnostic richness |
| `atom_locator: WhyNotAtomLocator | None` | Why-not-owned locator copy for native atom-localized rows |
| `errors: tuple[ErrorDTO, ...]` | Per-row diagnostic errors |
| `warnings: tuple[WarningDTO, ...]` | Per-row diagnostic warnings |

`WhyNotAtomLocator(branch_index, failed_atom_index, attempted_binding)` copies `DiagnoseAtomLocator` semantics into the Why-not protocol. This keeps the result contract capability-owned while allowing runtime implementation to call Diagnose and map its result.

### 5.5 Runtime Composition

Chosen composition: **Sibling-with-Diagnose mapping**.

Why-not may call `diagnose_derivation_binding(...)` for each red binding, because Shape A-prime's value is precisely bounded row-level diagnosis. However, the Why-not protocol must not expose nested `DiagnoseResult`. The runtime maps `DiagnoseResult` into `WhyNotRowDiagnostic` and maps `DiagnoseAtomLocator` into `WhyNotAtomLocator`.

Why-not does not call Check. It does not import Check runtime or Check protocol DTOs. It does not add a new evaluator hook.

### 5.6 Engine Support Gate

The selected shape keeps §6.6 local-gate discipline:

- The green/red board can be computed for engines that can evaluate the plan and expose candidate bindings compatible with the explicit universe.
- Red-row diagnostics inherit Diagnose semantics through mapping:
  - native can return `failed.atom_localized`;
  - souffle / problog / pyreason can return coarse `failed.no_candidate` or `unsupported` according to Diagnose's current representability and evidence lookup rules.
- A row-level `unsupported` result does not invalidate the whole board.
- If a plan / engine pair cannot produce comparable candidate bindings for the supplied universe, the top-level result is `unsupported` with a batch-level error.

This remains short enough to describe locally. §6.7 is not opened by this blueprint.

### 5.7 Algorithm Freeze

Dispatcher order:

1. Validate the request DTO shape and universe semantics before any evaluation:
   - plan has exactly one head;
   - every universe binding is a complete head binding using exactly the head variable names;
   - no duplicate bindings;
   - no body-only variables;
   - empty universe is valid.
2. Run Why-not's own RuleRef preflight before engine dispatch. Request-wide RuleRef failures return top-level `invalid_request`.
3. Evaluate the single plan once through the selected engine to compute derived candidate bindings.
4. Extract comparable head bindings from the engine candidates. If the selected engine / plan shape cannot expose comparable head bindings, return top-level `unsupported`.
5. Compute `green` and `red` by set intersection / difference against `candidate_universe`, preserving the request universe order in both outputs.
6. For each red binding, call `diagnose_derivation_binding(...)` with the same plan, binding, engine, store, and registry.
7. Map each Diagnose result into `WhyNotRowDiagnostic`.
8. Assemble `WhyNotUniverseResult`.

Green extraction uses the same head-binding semantics as Check / Diagnose:

- fact targets align plan head variables to candidate payload terms;
- entity targets are supported only when the engine candidate payload can expose the requested head binding;
- body-only variables are never part of the universe;
- candidate payloads that cannot represent a complete head binding make the request unsupported for that engine / plan shape.

### 5.8 Status And Mapping Freeze

Top-level status:

| Status | Meaning |
|---|---|
| `completed` | The board was assembled; `green` / `red` partition the requested universe |
| `unsupported` | The engine / plan cannot produce comparable candidate bindings for this board |
| `invalid_request` | Request-wide shape, universe, or RuleRef preflight failed |

Row diagnostic mapping from Diagnose:

| Diagnose result | Why-not handling |
|---|---|
| `failed.no_candidate` | row `status="failed"`, `failure_kind="no_candidate"`, `diagnostic_granularity="coarse"`, `atom_locator=None` |
| `failed.atom_localized` | row `status="failed"`, `failure_kind="atom_localized"`, `diagnostic_granularity="atom_localized"`, `atom_locator` populated |
| `unsupported` | row `status="unsupported"`, `failure_kind=None`, `diagnostic_granularity="unavailable"`, errors copied |
| `invalid_request` | runtime invariant error; Why-not already validated this binding and RuleRef shape |
| `passed` | runtime invariant error; green extraction and Diagnose disagree |

Invariant errors surface as `WhyNotRuntimeError` (name frozen at role altitude only) rather than a normal DTO result. They indicate implementation drift or inconsistent engine extraction, not user-facing unsupported semantics.

## 6. Boundaries And Invariants

- **Application-first:** any scoped capability must begin with protocol DTOs and application runtime.
- **No hidden universe:** red/green completeness requires an explicit finite candidate universe in the request or a separate source-backed universe provider.
- **No algorithmic paper-over:** `search_budget`, `limit`, or `max_candidates` cannot make an unbounded search crisp unless Step 0 defines the natural bounded search space.
- **No evaluator architecture by accident:** if near-miss reasons require modifying `evaluate_native_where(...)`, `where_eval`, or adapters to expose failed traces, this blueprint must stop before implementation and open a different architecture-facing task.
- **Capability gates stay local only while readable:** if Why-not requires a cross-engine support matrix with adapter-internal details, engine-extension §6.7 is triggered.
- **Capability-owned protocol:** Why-not may use Diagnose at runtime, but it must expose Why-not-owned result and locator DTOs rather than nested `DiagnoseResult`.
- **No SDK substrate:** SDK may only become a future thin shell after an application runtime exists.

## 7. Acceptance

### 7.1 Step 0 closure

- [x] Step 0.A source pass records the current evaluator / adapter surface.
- [x] Step 0.B decides whether the DTO is crisp, not crisp, or crisp only after reframing to carrier board / carrier plus Diagnose.
- [x] Step 0.C freezes either a scoped algorithm and drift gates, or records why no algorithm can be frozen.
- [x] Step 0.D lifts Step 0 decisions into canonical §5 / §7 / §8 and moves status to `scoped`.

### 7.2 §7-WhyNot-N anti-regression gates

Each gate maps to Step 0.C and must become focused test coverage before implementation close-out:

- [ ] **§7-WhyNot-1** (intent-only request DTO): `WhyNotUniverseRequest` fields are exactly `plan`, `candidate_universe`, and `engine`.
- [ ] **§7-WhyNot-2** (no algorithmic budget escape): request DTO has no `search_budget`, `limit`, `max_candidates`, `mode`, or `diagnostic_mode`.
- [ ] **§7-WhyNot-3** (explicit finite universe): universe bindings must be complete head bindings; body-only variables and missing/extra head variables are invalid.
- [ ] **§7-WhyNot-4** (duplicate universe guard): duplicate normalized universe bindings return `invalid_request`.
- [ ] **§7-WhyNot-5** (empty universe allowed): `candidate_universe=()` returns `completed` with empty `green` and `red`.
- [ ] **§7-WhyNot-6** (top-level status matrix): top-level statuses are exactly `completed`, `unsupported`, and `invalid_request`; unsupported / invalid results have empty `green` and `red` with required errors.
- [ ] **§7-WhyNot-7** (green/red partition): completed results preserve requested universe order; `green` and `red` are disjoint and their union equals `requested_universe`.
- [ ] **§7-WhyNot-8** (protocol owns row DTOs): Why-not protocol does not import or annotate fields with `DiagnoseResult`, `DiagnoseAtomLocator`, Check DTOs, `EvidenceEnvelope`, `SupportArtifact`, or `ProvenanceEnvelope`.
- [ ] **§7-WhyNot-9** (runtime composition boundary): runtime may call Diagnose and construct Diagnose requests internally, but output mapping must produce Why-not-owned row DTOs; runtime must not call Check.
- [ ] **§7-WhyNot-10** (row diagnostic status): row diagnostic statuses are exactly `failed` and `unsupported`; row-level `passed` / `invalid_request` Diagnose results raise a runtime invariant error.
- [ ] **§7-WhyNot-11** (diagnostic richness): native atom-localized rows map to `diagnostic_granularity="atom_localized"` with a populated `WhyNotAtomLocator`; coarse rows use `coarse`; unsupported rows use `unavailable`.
- [ ] **§7-WhyNot-12** (engine support gate): non-native engines can produce completed boards with coarse or unavailable red-row diagnostics when candidate binding extraction is representable; unsupported is top-level only when the board cannot be assembled.
- [ ] **§7-WhyNot-13** (no evaluator hook): implementation does not modify or depend on new `evaluate_native_where(...)` trace / callback output.
- [ ] **§7-WhyNot-14** (no ledger write): running Why-not does not append, revoke, accept, or persist facts / scenario state.

### 7.3 Layer Placement

- [x] Protocol DTOs live under `kernel.application.protocol/`.
- [x] Runtime entry lives under `kernel.application/`.
- [x] Runtime dependencies flow through side-channel kwargs, not DTO fields.
- [x] No SDK substrate; any SDK shell must be separately scoped after application runtime exists.

### 7.4 Code Health

- [ ] Focused protocol and runtime tests cover request shape, universe validation, top-level statuses, row mapping, all §7-WhyNot gates, and engine support behavior.
- [ ] Existing Check / Diagnose / Fact Overlay tests remain green.
- [ ] `python -m ruff check src/kernel` clean.
- [ ] Kernel test suite green.

### 7.5 Cross-doc Updates

- [ ] Application module docs (`src/kernel/application/docs/01_overview.md` + `_en.md`) updated to list Why-not Universe Diagnose.
- [ ] Engine-extension topic doc updated only if implementation reopens §6.6 / §6.7; otherwise leave topic doc untouched per Step 0.
- [ ] Conformance audit confirms implementation aligns with §5 frozen contract before status moves `scoped -> implemented`.

## 8. Implementation Plan

**Step 0 phases (complete; lifted into §5 / §7 above and audit Decision Notes):**

1. **Step 0.A — Source pass + shape split** (complete): read shipped capability archives, L6 / lazy why-not references, current native evaluator surface, current adapter output surfaces, and engine-extension §6.6. Recorded that the old "Why-not" label hides pure carrier, carrier + inline Diagnose, and true near-miss shapes.
2. **Step 0.B — DTO crispness decision** (complete): chose Shape A-prime as Why-not Universe Diagnose; froze request/result/red-row DTO shape; rejected nested `DiagnoseResult` in favor of Why-not-owned row DTOs; left Shape B as evaluator-architecture work.
3. **Step 0.C — Algorithm / gate freeze** (complete): froze dispatcher order, green/red computation, row Diagnose mapping, top-level status matrix, row diagnostic taxonomy, engine support gate, and §7-WhyNot drift gates.
4. **Step 0.D — Lift to scoped** (complete): renamed the blueprint to capability scope, lifted Step 0 decisions into canonical sections, and moved status `draft -> scoped`.

**Implementation steps (ordered for incremental commits):**

5. **Step 1 — Protocol DTOs** (complete). Add `WhyNotUniverseRequest`, `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, and `WhyNotAtomLocator` under `kernel.application.protocol/derivation_why_not.py`. Add protocol tests for DTO field shape, universe validation, status literals, nullable matrix, row diagnostic consistency, no budget escape fields, no nested Diagnose / Check / evidence payload DTOs, and empty-universe result construction.

6. **Step 2 — Runtime MVP board assembly** (complete). Add `check_why_not_universe(...)`, dispatcher preflight, RuleRef preflight, single-plan evaluation, comparable head-binding extraction for native and representable non-native candidates, green/red partitioning, empty-universe path, unsupported top-level path, and partition/order tests.

7. **Step 3 — Sibling-with-Diagnose row diagnostics.** Integrate `diagnose_derivation_binding(...)` for red rows and map Diagnose outputs into Why-not-owned row DTOs. Cover native atom-localized rows, coarse failed rows, row-level unsupported/unavailable rows, and runtime invariant errors for Diagnose `passed` / `invalid_request`.

8. **Step 4 — Drift-prevention named gates.** Land focused tests for §7-WhyNot-1 through §7-WhyNot-14, including static AST checks for protocol ownership and runtime composition boundaries.

9. **Step 5 — Close-out.** Update application docs, run the scoped verification set, record conformance audit findings, fill §10 Outcome / Deviations, and move status `scoped -> implemented` if implementation matches §5 and all §7 gates pass.

## 9. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` only if implementation reopens §6.6 / §6.7.

## 10. Outcome / Deviations

Task completion pending.

- Final Step 0 result:
- Deviations:
- Archive / abandonment / supersession notes:
