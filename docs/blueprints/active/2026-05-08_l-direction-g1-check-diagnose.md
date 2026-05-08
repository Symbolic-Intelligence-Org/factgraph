# L Direction G1 — Check + Diagnose SDK Shell

- **Status:** draft
- **Created:** 2026-05-08
- **Parent:** L Direction (post-A+B v1-ready roadmap target)
- **Related Bundle:** [post-routemap-direction-selection-input](../../references/working/post-routemap-direction-selection-input/) — Round 8 SDK conventions audit (G1 verdict: clean)
- **Predecessors (shipped):** [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md), [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md)

## 1. Problem

A+B Tier 2 application-layer surface (`kernel.application.capability_helpers` + `kernel.application.walker`) shipped 2026-05-08 on combined branch `v0.1-public-surface-helpers-walker-2026-05-08` @ `6162f1e`. SDK consumers (Tier 1) still cannot run Q1 Check or Q2 Diagnose without dropping to advanced importable layer (importing from `kernel.application.*`).

Round 8 SDK conventions audit (4 parallel lanes, 2026-05-07) verified G1 (Check + Diagnose) is the cleanest of 5 candidate L groups: naming aligns with verb-first SDK convention; SDK Rule lowering reuses existing `to_authoring_payload()` pipeline; return shape can match the `ValidationReport` typed-DTO precedent. G1 is therefore the right starting point for L's SDK-shell template — the validation pattern (lowering / dispatch / return wrap / error remap / `__all__` boundary) established here is reused by G4 → G2 → G3 → G5 in subsequent blueprints.

This blueprint covers G1 only. Each remaining group has own per-family Step 0 + own blueprint per [Batch 8 §5.5.5 reactivation rule](../archive/2026-05-06_public-surface.md).

## 2. Goal

Tier 1 SDK shell that lets a `kernel.sdk` consumer invoke Q1 Check and Q2 Diagnose without importing `kernel.application` or `kernel.application.capability_helpers`. Specifically:

- Accept SDK-canonical inputs (SDK `Rule` / DSL plan, SDK store, SDK-shaped binding) and lower internally to `CompiledDerivationPlan` via existing `to_authoring_payload()` + `compile_authoring_rule_v1()` pipeline.
- Consume A's `build_check_request` / `build_diagnose_request` after lowering — do not duplicate normalization or origin-package validation.
- Resolve return shape, error mapping, exposure pattern, module/test layout, and scenario-vs-per-method API at G1 Step 0 falsifier pass — none pre-locked here.
- Establish the SDK-shell template (lowering pipeline / dispatch contract / boundary discipline) reusable by G2–G5 blueprints.

## 3. Non-Goals

- **No scenario merge pre-lock.** `sdk.explain(...)` (Direction C scenario shape, [30_recommendation.md §"Why not start with C"](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)) is one Step 0 candidate. `#3` heterogeneity warns against false merge. Falsifier required (§5.1).
- **No return-shape pre-lock.** B-typed-wrap is the leading candidate (Round 8 `ValidationReport` precedent), but `#6` + `#P0` Tier 5 require formal Step 0 falsifier (§5.2).
- **No README quickstart change.** Per `#6` "What this principle set forbids" — adding new helpers / walker classes to README quickstart is forbidden. Quickstart change requires its own user signal beyond G1.
- **No `kernel.sdk.__all__` expansion without §5.4 Step 0 lock.** Per Batch 8 §5.5.5: outward-shape lock-in is part of G1 own Step 0; `__all__` insertion needs explicit decision.
- **No SDK Rule lowering reinvention.** G1 reuses the existing `to_authoring_payload()` + `compile_authoring_rule_v1()` lowering at [src/kernel/sdk/store.py:821-848 `_compile_rule_input(...)`](../../../src/kernel/sdk/store.py). New lowering paths are out of scope.
- **No protocol DTO field changes.** Per `#1` + `#6` "Refactoring existing protocol DTOs to fit walker shape better" forbidden. G1 wraps existing DTOs; never reshapes them.
- **No service / agent / domain integration.** G1 is `kernel.sdk` self-contained. Service routes deferred per Batch 8 §5.5.5 row 3.
- **No `factpy` rebrand or umbrella alias.** Import root continues `kernel.sdk` (Q3 lock, §4.1). Rebrand is publish-day or product-naming blueprint, not L/G1.
- **No A internals usage.** G1 imports `build_check_request`, `build_diagnose_request`, `CapabilityHelperError`, `OriginPackageError` from A's public surface only. `_binding`, `_reject_sdk_origin`, direct `CheckRequest`/`DiagnoseRequest` construction are forbidden.
- **No G2/G3/G4/G5 work.** Each gets own Step 0 + own blueprint when activated.
- **No demo / notebook migration.** Per [50_migration-path.md §3](../../references/working/post-routemap-direction-selection-input/50_migration-path.md), demo update is follow-up work post-archive.

## 4. Current Context

### 4.1 Framing decisions absorbed (Q1 / Q2 / Q3, locked 2026-05-08)

**Q1 — G1-G5 split structure (locked):**

Each L group gets its own blueprint per Batch 8 §5.5.5. Execution order **G1 → G4 → G2 → G3 → G5**. The SDK-shell validation pattern is established in G1 and reused by subsequent groups. No mega-blueprint, no clean-vs-pending split.

**Q2 — G1 dependencies on A/B (locked):**

| Layer | Surface | Status |
|---|---|---|
| A — must use | `build_check_request(plan, binding, *, engine)` | Hard dependency |
| A — must use | `build_diagnose_request(plan, binding, *, engine)` | Hard dependency |
| A — must use | `CapabilityHelperError` (catch + remap to SDKError) | Hard dependency |
| A — must use | `OriginPackageError` (catch + remap to SDKError) | Hard dependency |
| A — forbidden | `_binding` private module direct import | Internal-only |
| A — forbidden | `_reject_sdk_origin` direct call | Internal-only |
| A — forbidden | Direct `CheckRequest` / `DiagnoseRequest` construction | Skips A defense-in-depth |
| B — conditional | `SupportArtifactView` | Active only if §5.2 selects B-typed-wrap |
| B — conditional | `AssertionView` | Active only if `lookup_assertion(...)` is exposed |
| B — conditional | `parse_atom_key` / `AtomKeyView` | Active only if Diagnose atom-key parsed surface chosen |
| B — conditional | `WalkerError` family | Active only if walker views surface to SDK |

**Q3 — Import naming (locked):**

`kernel.sdk` namespace continues. Rebrand to `factpy` or umbrella-alias is an independent publish-day or product-naming blueprint; does NOT enter L or G1. Bundle [30_recommendation.md L586](../../references/working/post-routemap-direction-selection-input/30_recommendation.md) explicitly anchors L on `kernel.sdk`: "Future L (Tier 1 SDK shell) is the home for SDK-DSL acceptance" — predicates `kernel.sdk` continuation.

### 4.2 Round 8 Lane 3 G1 verdict (cite [bundle README Round 8](../../references/working/post-routemap-direction-selection-input/README.md))

> "G1 Check + Diagnose: clean — naming aligns with verb-first SDK convention; rule lowering pattern works via existing `to_authoring_payload()` precedent; return shape can match `ValidationReport` typed-DTO precedent."

"Clean" means: no naming convention mismatch (unlike G3's three-sister naming), no raw protocol DTO surfaced as shell input (unlike G2's `SupportArtifact` / `EvaluationOverlay`), no lifecycle/query mixing (unlike G5's recorder vs query split). G1 is the simplest L group and the appropriate template for L's SDK-shell pattern.

### 4.3 Strangler migration pattern (Decision 1 reference)

Per [60_lessons-learned.md](../../references/working/rule-replay-line-redesign-input/60_lessons-learned.md) Decision 1: "SDK wrapper 推到第二步, 后期 strangler migration". A is the first step (Tier 2 stabilization, shipped 2026-05-07). G1 is the second step (Tier 1 SDK wrap, this blueprint). G1 does not duplicate A's substrate; G1 wraps A.

### 4.4 Prior art and infrastructure to consume

| Resource | Purpose |
|---|---|
| [src/kernel/sdk/store.py:821-848 `_compile_rule_input(...)`](../../../src/kernel/sdk/store.py) | Existing SDK Rule → `CompiledDerivationPlan` lowering pipeline; G1 reuses, does not invent |
| [src/kernel/application/capability_helpers/check.py](../../../src/kernel/application/capability_helpers/check.py) | A's `build_check_request` |
| [src/kernel/application/capability_helpers/diagnose.py](../../../src/kernel/application/capability_helpers/diagnose.py) | A's `build_diagnose_request` |
| [src/kernel/application/walker/views.py](../../../src/kernel/application/walker/views.py) | B's walker views; conditional dependency per §5.2 |
| `ValidationReport` (`kernel.sdk.protocol`) | SDK return-type precedent (typed frozen dataclass); cited by Round 8 Lane 1 as alignment reference |
| [src/kernel/sdk/errors.py](../../../src/kernel/sdk/errors.py) | `SDKError` hierarchy; G1 adds new subclasses for error remap |
| [src/kernel/sdk/__init__.py](../../../src/kernel/sdk/__init__.py) | SDK store, DSL primitives (`SDKStore`, `Entity`, `Pred`, ...) — G1 input source |

### 4.5 Branch state

- Working tree on `v0.1-public-surface-helpers-walker-2026-05-08` @ `33b6d06` (memory sync commit on top of A+B combined `6162f1e`); clean tree
- Sacred branches `master` and `v0.1-oss-prep` untouched
- G1 implementation will branch from current HEAD per [feedback_worktree_parallel_implementation pattern](../../../../.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_worktree_parallel_implementation.md): `git worktree add -b codex/v0.1-l-g1-check-diagnose-2026-05-DD /Users/zhenzhili/hnsm-backend-G1` once scope-freeze advances to `implementing`
- Snapshot branch convention on publish: `v0.1-l-g1-check-diagnose-2026-05-DD` (drop `codex/` prefix per A+B precedent)

## 5. Design — Step 0 questions to resolve in scoping round

This blueprint is at `draft` status. The seven questions below MUST be resolved with falsifier passes before status advances to `scoped`. Each question lists the tension, falsifier requirement, and conservative default if Step 0 evidence is inconclusive.

### 5.1 Scenario API vs per-method API (THE central tension)

**Question:** Does G1 ship a unified `sdk.explain(rule, binding, store)` returning a result combining Check passed/failed + Diagnose locator, OR ship `sdk.check(...)` + `sdk.diagnose(...)` as two separate methods?

**Source candidates:**

- Bundle [30_recommendation.md §"Why not start with C"](../../references/working/post-routemap-direction-selection-input/30_recommendation.md) hypothetical scenario shape:
  ```
  explain = sdk.explain(rule=eligible_rule, binding={'$p': alice}, store=store)
  explain.passed   # bool
  explain.evidence # walker view (depends on B)
  explain.failure  # FailureExplanation (Diagnose locator + friendly attempted_binding view)
  ```
- Per-method shape: `sdk.check(rule, binding, store) -> SDKCheckResult` + `sdk.diagnose(rule, binding, store) -> SDKDiagnoseResult`, mirroring application-layer pattern.

**Tension:**

- **Pro scenario:** single user-facing entry, intent-shaped ("explain why this binding holds or doesn't"); reduces caller orchestration; B walker integration natural via `explain.evidence`.
- **Pro per-method:** explicit per-capability semantics — `sdk.check()` returns status, `sdk.diagnose()` returns locator, no result-type discriminator to design; mirrors existing application-layer `check_derivation_binding` / `diagnose_derivation_binding` 1:1 split (lower learning curve, code symmetry); lower outward commitment surface — no new `FailureExplanation` hybrid type whose shape gets locked by `#6` once shipped. Backed by `#3` "Capability heterogeneity — One SDK method family would be false merge" — Check (status-only) and Diagnose (atom-localized) are structurally heterogeneous; merging creates a hybrid result type both senses must understand.

**Falsifier required (per `#3` + `#6` + `#P0`):**

1. Source-ground a user-facing workflow that needs `sdk.explain` semantics specifically (not separate Check + Diagnose calls). Without that, `#3` heterogeneity argument prevails.
2. If scenario shape is selected: document why it is NOT a false merge — discriminator must be unambiguous (e.g., `passed: bool`), failed branch must BE Diagnose's locator without invention.
3. If per-method shape is selected: document why scenario composition stays caller-side (lower outward commitment per `#6`).

**Default if Step 0 inconclusive:** per-method (lower `#6` commitment per `#P0` Tier 5).

**Decision (2026-05-08, falsifier pass complete):**

- **G1 ships two SDK entrypoints** for Check and Diagnose.
- Exact placement / naming deferred to §5.4 / §5.5; **scenario merge rejected for this blueprint**.
- `sdk.explain(...)` remains future Direction C composition work, not G1 scope.

**Falsifier evidence (read-only protocol audit):**

1. `sdk.explain(...)` is hypothetical only — [20_candidates.md §C](../../references/working/post-routemap-direction-selection-input/20_candidates.md) shows it as a sketch and explicitly notes "Adds outward-compatibility commitment: once shipped, the `sdk.explain` shape is locked".
2. A's design rationale already settles separate builders for Check + Diagnose on `#3` — [41_application-builders-design-sketch.md §3.1 "Rationale for separate Check + Diagnose builders"](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md): "Separate builders match `#3` heterogeneity and avoid false unification — same lesson as Batch 8 §5.4 verdict #3".
3. Application protocol enforces Q1 Sibling at the type level — [derivation_diagnose.py module docstring](../../../src/kernel/application/protocol/derivation_diagnose.py): "Diagnose owns its full dispatch and does NOT call `check_derivation_binding(...)`; this protocol redeclares its status / engine Literals locally rather than importing Check's, keeping the two capabilities decoupled at the protocol layer".
4. `DiagnoseResult` explicitly excludes `EvidenceEnvelope` — [derivation_diagnose.py `DiagnoseResult` docstring](../../../src/kernel/application/protocol/derivation_diagnose.py): "`DiagnoseResult` does NOT carry an `EvidenceEnvelope` (per D9 + Q1 Sibling — callers wanting Check's evidence on `passed` invoke Check separately)".
5. `CheckResult.evidence_envelope` is populated only on `passed`; `failed` enforces `None` via runtime assertion — [derivation_check.py `CheckResult.__post_init__`](../../../src/kernel/application/protocol/derivation_check.py): "passed CheckResult requires evidence_envelope" (line 138-139) / "failed CheckResult requires evidence_envelope=None" (line 147-148). This is an active `raise ProtocolShapeError`, not a passive absence — application protocol mechanically rejects evidence-on-failure construction.

**Why scenario merge is ruled out:**

A `sdk.explain(rule, binding, store) -> SDKExplainResult` (with `.passed`, `.evidence`, `.failure`) would force one of three options, none acceptable:

- **(a) Internal Check + Diagnose composition** — caller can do the same composition externally; no outward semantic gain over per-method.
- **(b) Add Check evidence to Diagnose-shaped result** — violates Q1 Sibling discipline already locked at the protocol layer (evidence 3).
- **(c) Invent hybrid result with evidence-on-failure semantics** — application layer explicitly excludes evidence-on-failure (evidence 4 + 5). Furthermore, since `CheckResult.__post_init__` actively raises `ProtocolShapeError` when `failed` carries an `evidence_envelope`, a SDK shell that tried to populate evidence on a failed branch would be **mechanically blocked at construction time** — not just an abstract `#1` layer-inversion concern. The hybrid type would have to bypass the application protocol entirely, creating both a `#1` layer-inversion (Tier 1 carrying semantics Tier 2 authoritatively rejects) AND a `#6` outward-compat commitment (`SDKExplainResult` shape locks once shipped) without source-grounded user signal.

**Falsifier outcomes (against the three requirements above):**

| Falsifier | Outcome |
|---|---|
| F1: source-ground a user workflow needing `sdk.explain` semantics specifically | **Not satisfied** — no source found. `#3` heterogeneity prevails. |
| F2: if scenario selected, document why NOT false merge | **Blocked** — evidence-on-failure semantics absent at protocol layer AND mechanically rejected at construction; cannot construct unambiguous discriminator without bypassing the application protocol. |
| F3: if per-method selected, document scenario composition stays caller-side | **Satisfied** — `sdk.check(...)` then `sdk.diagnose(...)` mirrors existing application-layer 1:1 pattern; no new outward type to lock. |

### 5.2 Return shape — B-typed-wrap vs raw passthrough vs documented passthrough

**Question:** Does G1 return `kernel.application.protocol.derivation_check.CheckResult` / `DiagnoseResult` directly (raw passthrough), wrap them in new SDK-typed result classes (B-typed-wrap), or return raw with docstring pointer to B walker views (documented passthrough)?

**Tension:**

- B-typed-wrap aligns with `ValidationReport` typed-DTO precedent (Round 8 Lane 1) — consistent with existing typed-DTO SDK pattern; isolates user from advanced-importable types.
- B-typed-wrap creates new outward types whose shape is locked by `#6` once shipped. `#P0` Tier 5 explicitly says: "Tier 5 is not 'lowest and sacrificable'; it constrains Tier 4. Ergonomic surface may be narrowed, but must not create new outward compatibility commitments."
- Raw passthrough leaks `kernel.application.protocol` types into SDK consumer-visible surface (mild `#5` cross-layer concern; arguably acceptable per Tier 2 advanced-importable).
- Documented passthrough is the conservative middle: raw return + docstring pointer to `SupportArtifactView(result.support_artifact)` for ergonomic access.

**Falsifier required (per `#6` + `#P0`):**

1. If B-typed-wrap selected: source-ground that the typed wrapper shape is durable in v0.x. Bundle Round 8 calls G1 "clean" but does not pre-commit a specific wrapper shape.
2. If documented passthrough selected: confirm SDK quickstart and user guide do NOT need wrapper-style return surface (consistent with `#6` no-README-change non-goal).
3. If raw passthrough selected: confirm cross-layer leak is bounded — only G1's signature exposes `CheckResult`; no further SDK methods consume it.

**Default if Step 0 inconclusive:** documented passthrough (lowest outward commitment per `#P0` Tier 5).

**Decision (2026-05-08, falsifier pass complete):**

- **Both methods return application protocol DTOs as documented passthrough:**
  - `sdk.check(...) -> CheckResult` (from `kernel.application.protocol.derivation_check`)
  - `sdk.diagnose(...) -> DiagnoseResult` (from `kernel.application.protocol.derivation_diagnose`)
- **`CheckResult` / `DiagnoseResult` may appear as return annotations / imports in G1 implementation, but are NOT re-exported from `kernel.sdk.__all__`** — preserves the `kernel.sdk` surface boundary at the export level.
- **B dependencies inactive for G1 v1:** no `SupportArtifactView`, no `AssertionView`, no `parse_atom_key`, no `WalkerError` remap. SDK method/module docstrings MAY mention advanced importable opt-in workflow (e.g., "use `SupportArtifactView(result.support_artifact, frozen_claim_index)` for ergonomic evidence access") but G1 itself does not import B walker types.
- **SDK-typed wrappers (`SDKCheckResult` / `SDKDiagnoseResult`) deferred** as future `#P1` revision trigger if a user-facing evidence workflow signal materializes.

**Falsifier evidence (read-only audit):**

1. **`ValidationReport` precedent does not force SDK wrapper** — [ingest.py:81-86](../../../src/kernel/sdk/ingest.py): `ValidationReport` is an SDK-owned frozen dataclass for provenance diagnostics (`ok` / `warnings` / `errors` fields), NOT a wrapping precedent over application protocol DTOs. Round 8 Lane 1 cited it as alignment reference for typed-DTO style, not as evidence that SDK must wrap protocol types.
2. **SDK has established raw-passthrough precedent** — [store.py:773 `evaluate_compiled`](../../../src/kernel/sdk/store.py): returns `list[CandidateSet]`; [store.py:776 `accept`](../../../src/kernel/sdk/store.py): returns `AcceptResult`. Both return core/application types directly. The pattern is established: SDK methods may return non-SDK types as long as those types aren't re-exported from `kernel.sdk.__all__`.
3. **`__all__` boundary is about exports, not return types** — [01_alignment_matrix.md §3 line 36](../../../src/kernel/sdk/docs/01_alignment_matrix.md): "`kernel.sdk.__all__` 只表达 SDK user-facing surface / compatibility aliases，不导出 application internals". Exporting `CheckResult` from `kernel.sdk.__all__` would be the violation; returning it as `sdk.check()` output type does not violate the boundary as long as `__all__` stays clean.
4. **B-typed-wrap for Check would force G1 to build new substrate** — [views.py:495-509 `SupportArtifactView.__init__`](../../../src/kernel/application/walker/views.py): constructor requires `support` + `frozen_claim_index: Mapping[str, Claim]` (positional, no default). G1 to wrap CheckResult would need to construct/hydrate a `frozen_claim_index` from the store — that's new substrate inside `kernel.sdk` that doesn't exist today, directly violating `#1` "no new substrate in `kernel.sdk`".
5. **B-typed-wrap for Diagnose has no input** — [derivation_diagnose.py:80-104 `DiagnoseAtomLocator`](../../../src/kernel/application/protocol/derivation_diagnose.py): fields are `branch_index: int`, `failed_atom_index: int`, `attempted_binding: BindingItems`. NO `b{branch}.a{idx}:{pred_id}` string field — `parse_atom_key` / `AtomKeyView` from B has no actual input from Diagnose to consume. Diagnose's atom-key wrap is mechanically moot.

**Why documented passthrough is the only viable option:**

| Option | Outcome |
|---|---|
| **B-typed-wrap** | Blocked by evidence 4 (Check would need new substrate inside `kernel.sdk`, `#1` violation) AND evidence 5 (Diagnose has no atom-key string input — wrapping is mechanically moot). Not technically viable for G1 today. |
| **Raw passthrough (no docstring guidance)** | Functionally equivalent to documented passthrough but loses the opt-in advanced-workflow pointer; users wanting B walker integration must discover it independently. |
| **Documented passthrough** | Returns `CheckResult` / `DiagnoseResult` directly + docstring opt-in pointer to B walker views. Zero G1 import of B; zero `__all__` expansion; preserves option to ship typed wrappers later under `#P1` if user signal materializes. |

**Falsifier outcomes (against the three requirements above):**

| Falsifier | Outcome |
|---|---|
| F1: if B-typed-wrap selected, source-ground that wrapper shape is durable in v0.x | **Blocked** — evidence 4 + 5 show B-typed-wrap is not technically viable for G1 today (would force new substrate / has no input to wrap). Cannot ship a "durable" wrapper that doesn't currently work. |
| F2: if documented passthrough selected, confirm SDK quickstart and user guide do NOT need wrapper-style return surface | **Satisfied** — quickstart unchanged per `#6` non-goal; user guide gets opt-in advanced workflow pointer (docstring only), not a new SDK type contract. |
| F3: if raw passthrough selected, confirm cross-layer leak is bounded — only G1's signature exposes `CheckResult` | **Satisfied** — `CheckResult` / `DiagnoseResult` appear ONLY as G1 method return annotations; not added to `kernel.sdk.__all__`; consistent with existing `evaluate_compiled` / `accept` precedent (evidence 2). Boundary preserved. |

### 5.3 Error mapping strategy

**Question:** How are `CapabilityHelperError`, `OriginPackageError`, `WalkerError` family (if applicable) caught and remapped into the `SDKError` hierarchy?

**Constraint:** `#12` forbids cross-layer error reuse ("Do not reuse SDK `FrozenSnapshotError` across the application/audit boundary"). G1 must NOT alias `WalkerError` to an existing SDK error type; it must define new SDK error subclasses if walker errors surface.

**Sub-questions:**

1. Does `OriginPackageError` (lowering caught an SDK object that didn't lower correctly) map to a new `SDKLoweringError` subclass, or remain visible as `OriginPackageError` propagating from A?
2. If walker views are exposed (return shape per §5.2), do walker-layer exceptions surface to SDK callers, or are they caught and remapped at the SDK boundary?
3. New SDK error subclasses needed (if any) — list them.

**Falsifier required:** confirm error hierarchy growth is minimal — only what current G1 needs (per `#6`).

### 5.4 `kernel.sdk.__all__` exposure pattern

**Question:** Are G1's new methods added to `kernel.sdk.__all__` directly (top-level), exposed only via submodule path (`from kernel.sdk.check import sdk_check_derivation_binding`), or both?

**Constraint:** Batch 8 §5.5.5 requires per-family own outward-shape lock-in. Once added to `__all__`, removal is `#6` outward-compat break.

**Default if Step 0 inconclusive:** start with submodule-only path; promote to `__all__` only if Step 0 gathers explicit signal.

### 5.5 Module location and structure

**Question:** Single file `kernel/sdk/g1.py`? Per-method files (`kernel/sdk/check.py` + `kernel/sdk/diagnose.py`)? New `kernel/sdk/shells/` package? Inject into existing `kernel/sdk/facade.py`?

**Reference:** A's Step 0 selected `capability_helpers/` package layout with per-family files. By analogy, G1 could mirror this for forward compatibility with G2-G5.

**Default if Step 0 inconclusive:** mirror A's per-family layout (`kernel/sdk/check.py` + `kernel/sdk/diagnose.py`) for forward compatibility.

### 5.6 Test layout

**Question:** Flat `src/kernel/tests/test_sdk_g1.py`, per-method test files (`test_sdk_check.py` + `test_sdk_diagnose.py`), or extend existing SDK test files?

**Constraint:** `#19` flat unittest layout; no Hypothesis; no nested `tests/sdk/` directory.

**Default if Step 0 inconclusive:** flat per-method (`test_sdk_check.py` + `test_sdk_diagnose.py`); shared fixtures in `_g1_fixtures.py` if extracted.

### 5.7 SDK-side input shape

**Question:** What SDK-side input types are accepted at G1's surface?

- Plan: SDK `Rule` instance only? `Rule | CompiledDerivationPlan` accepted? Other?
- Binding: `dict[str, Any]` only? Also accept SDK DSL `Var` references?
- Store: SDK `SDKStore` only, or also accept lower-level `Store` for advanced usage?

**Constraint:** SDK boundary should accept SDK-canonical types. `CompiledDerivationPlan` is technically `kernel.application` — should G1 accept it as a power-user escape, or strictly SDK Rule?

**Default if Step 0 inconclusive:** SDK-canonical inputs only at G1 surface; advanced importable users keep using A's `build_check_request` directly.

## 6. Boundaries-and-Invariants

Principles locked active for G1 (numbering per [30_recommendation.md](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)):

| Principle | Lock | Notes |
|---|---|---|
| `#1` Application-first | Active | G1 has no substrate; calls A and existing application runtime; no new application-layer DTOs |
| `#3` Heterogeneity | Active | Hard constraint on §5.1 scenario API decision |
| `#4a` Intent-minimal at SDK | Active | G1 accepts SDK-shaped intent; lowering is internal |
| `#5` Layer isolation | Active | G1 in `kernel.sdk` may import `kernel.application.capability_helpers` public surface and `kernel.application.derivation_check_runtime` / `derivation_diagnose_runtime`. Reverse imports forbidden. |
| `#6` No outward compat without user signal | Active | Drives §5.1 / §5.2 / §5.4 falsifier discipline. README quickstart non-goal. |
| `#11` `.underlying` escape hatch | **Inactive for G1 v1** (resolved 2026-05-08) | §5.2 locked to documented passthrough; G1 does not import B walker views, so `.underlying` is not surfaced. Reactivates only via future `#P1` revision adding typed wrapper. |
| `#12` Error boundaries naming | **Partial** (resolved 2026-05-08) | `OriginPackageError` remap (§5.3) remains unconditionally active. `WalkerError` remap is inactive for G1 v1 since walker views are not exposed (§5.2 documented passthrough). Reactivates if future `#P1` revision adds B walker imports. |
| `#19` Test contract | Active | Flat `unittest`; no Hypothesis; fixtures `_g1_fixtures.py` if extracted |
| `#P0` Conflict resolution | Active | Tier 5 (`#6`) constrains Tier 4 (ergonomic surface). Default-to-narrow heuristic informs §5.1 / §5.2 / §5.4 defaults. |
| `#P1` Carve-out flow | Active | Any deviation in scoping or implementation phases must record id / reason / scope / impact / reviewer ack |

**Forbidden (consolidated negative list per Q1/Q2/Q3 + bundle "What forbidden" L396-419):**

- New substrate in `kernel.sdk` (per `#1`); G1 wraps existing.
- A internals usage: `_binding` import, `_reject_sdk_origin` direct call, direct `CheckRequest` / `DiagnoseRequest` construction.
- Protocol DTO field changes "to fit SDK shape better" (per `#1` + `#6`).
- README quickstart change (per `#6`).
- `kernel.sdk.__all__` expansion without §5.4 Step 0 lock.
- New SDK Rule lowering pipeline (use existing `to_authoring_payload()`).
- Service / agent / domain integration.
- `factpy` rebrand or umbrella-alias.
- G2 / G3 / G4 / G5 work mixed into this blueprint.
- Demo notebook migration as part of this scope (post-archive follow-up).

## 7. Acceptance Criteria

Acceptance gates are completed at scope-freeze. At `draft` status, only Step 0 falsifier outcomes (per §5) are pending. Once scoped, this section will list per-falsifier resolution + concrete test contract obligations.

**Pre-scope-freeze acceptance (this draft round):**

- [x] Q1 / Q2 / Q3 framing decisions absorbed in §4.1
- [x] 7 Step 0 questions enumerated in §5
- [x] Principle lock set documented in §6
- [x] Non-goals enumerated in §3 (covers `factpy`, README quickstart, scenario merge pre-lock, B return-shape pre-lock, etc.)
- [x] Bundle reference and prior art cited in §4
- [x] §5.1 falsifier pass — locked 2026-05-08 (per-method API; scenario `sdk.explain` rejected, remains Direction C future composition)
- [x] §5.2 falsifier pass — locked 2026-05-08 (documented passthrough for both methods; B dependencies inactive; `CheckResult` / `DiagnoseResult` not re-exported from `kernel.sdk.__all__`)
- [ ] §5.3 through §5.7 falsifier passes — **pending scoping round**

## 8. Implementation Plan

Deferred to scoped status. At scope-freeze this section will include:

- Per-falsifier resolution (one decision per §5.x question)
- Phased implementation order (per A+B precedent: Phase 0 process correction → Phase 1 Check shell → Phase 2 Diagnose shell → Phase N close-out)
- Worktree branch creation: `git worktree add -b codex/v0.1-l-g1-check-diagnose-2026-05-DD /Users/zhenzhili/hnsm-backend-G1` (date filled at scope-freeze)
- Per-phase audit cadence (per [feedback_audit_cadence_per_phase](../../../../.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_audit_cadence_per_phase.md))
- Snapshot branch publish plan: `v0.1-l-g1-check-diagnose-2026-05-DD` on origin
- Archive sequence

## 9. Outcome

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
