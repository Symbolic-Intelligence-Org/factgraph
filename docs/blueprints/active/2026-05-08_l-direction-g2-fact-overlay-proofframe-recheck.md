# L Direction G2 — Fact Overlay + ProofFrame Recheck SDK Shell

- **Status:** draft
- **Created:** 2026-05-08
- **Last Updated:** 2026-05-08
- **Parent:** L Direction (post-A+B+G1+G4 v1-ready roadmap target)
- **Related Bundle:** [post-routemap-direction-selection-input](../../references/working/post-routemap-direction-selection-input/) — Round 8 SDK conventions audit (G2 verdict: **pending Step 0 shape decision** — protocol DTOs `SupportArtifact` + `EvaluationOverlay` are raw types and the SDK shell must decide whether to wrap them or accept them at the boundary)
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g4-why-not-frontier (archived)](../archive/2026-05-08_l-direction-g4-why-not-frontier.md)
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md)
  - [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md)
  - [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md)
- **Audit Log:** [2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.audit.md](./2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.audit.md)

## 1. Problem

G1 shipped `SDKStore.check(...)` / `SDKStore.diagnose(...)` and G4 shipped `SDKStore.why_not(...)`. SDK consumers can run Check / Diagnose / Why-not without importing `kernel.application`.

The next L group is G2: **Fact Overlay Check + ProofFrame Recheck**. Round 8 classified G2 as **pending Step 0 shape decision** — both capabilities currently surface raw application protocol DTOs (`SupportArtifact`, `EvaluationOverlay`) at their input boundary, which forces an SDK boundary question that G1 / G4 did not face.

Beyond the input-shape decision, G2 lands the **3rd and 4th SDK shell files** (after `check.py`, `diagnose.py`, `why_not.py`). The G1+G4 §5.5 forward trigger requires G2 Step 0 to evaluate `kernel/sdk/shells/` subpackage migration as G2 Phase 0 hygiene **before** any G2 implementation lands.

This blueprint starts G2 Step 0 only. It does not implement SDK methods until §5 questions are source-grounded and scope-frozen.

## 2. Goals

- Decide G2 SDK outward shape for Fact Overlay Check and ProofFrame Recheck with the same per-family Step 0 falsifier discipline used by G1 / G4.
- Reuse G1+G4 SDK shell infrastructure: `kernel.sdk._validation.validate_derivation`, SDKStore method delegation, error remap pattern.
- Resolve the inherited `kernel/sdk/shells/` migration trigger as either a G2 Phase 0 hygiene step (with `#P1` carve-out for the G1 invariant test) or an explicit defer.
- Establish a scoped implementation plan only after §5 falsifiers are resolved.

## 3. Non-Goals

- **No implementation in draft.** No `SDKStore.check_fact_overlay(...)`, `SDKStore.recheck_proof_frame(...)`, module files, docs updates, or tests ship until §5 is locked and status moves to `scoped`.
- **No README quickstart change.** Per `#6`, new SDK shell promotion does not automatically enter README quickstart.
- **No `kernel.sdk.__all__` expansion by default.** G1 + G4 set the pattern: SDKStore instance methods first; top-level exports need their own falsifier.
- **No B walker dependency.** G2 returns raw protocol DTOs; advanced traversal stays application-side.
- **No `factpy` rebrand.** Import root remains `kernel.sdk`; OpenAI-style ergonomics are recorded as post-L redesign preference.
- **No G3 / G5 decisions.** Rule overlays and round events / ProofFrame diff remain separate future blueprints.
- **No new application capability.** G2 wraps existing application capabilities; it does not modify `check_fact_overlay_binding(...)`, `recheck_proof_frame(...)`, or any of their DTOs.
- **No SDK-side `SupportArtifact` construction.** If §5 decides to wrap `SupportArtifact`, the wrapper is a thin reference object only; SDK does not own the construction path (SupportArtifact comes from prior Check runs at the application or SDK layer).

## 4. Current Context

### 4.1 L ordering and baseline

Q1 split locked: **G1 -> G4 -> G2 -> G3 -> G5**. G1 + G4 are implemented, archived, and published. This G2 draft is based on `v0.1-public-surface-helpers-walker-l-g1-l-g4-2026-05-08` @ `acb5a6e` (Path B combined snapshot post-G4).

Current branch for this draft: `codex/v0.1-l-g2-fact-overlay-proofframe-recheck-2026-05-08`.

### 4.2 Round 8 G2 verdict

Round 8 SDK conventions audit recorded:

> **G2 Fact Overlay + ProofFrame Recheck: pending Step 0 shape decision** — protocol DTOs (`SupportArtifact`, `EvaluationOverlay`) are currently surfaced as raw types; SDK shell must decide whether to wrap them in SDK DSL or leave them advanced-importable.

This "pending Step 0" verdict means there is at least one substantive shape decision G2 must resolve (not just a clean lift like G4). The SDK boundary precedent from G1 (§5.7 SDK `Derivation` only at input) is challenged because:

- Fact Overlay Check needs an `EvaluationOverlay` (containing `fact_actions` + `rule_actions`) at input — a structure whose canonical home is `kernel.application.protocol`.
- ProofFrame Recheck needs a `SupportArtifact` at input — produced by a prior `check_derivation_binding(...)` call's `evidence_envelope.engine_payload`. There is no obvious SDK-level alternative.

### 4.3 Existing Tier 2 / substrate surfaces

| Area | Existing surface | Layer |
|---|---|---|
| Fact Overlay request DTO | `FactOverlayCheckRequest(plan, binding, overlay, engine)` (`kernel.application.protocol.derivation_fact_overlay:282`) | `kernel.application.protocol` |
| Fact Overlay overlay DTOs | `EvaluationOverlay`, `FactOverlayAction`, `FactValueOverride`, `RuleOverlayAction` | `kernel.application.protocol.derivation_fact_overlay` |
| Fact Overlay request helper | `build_fact_value_override(...)` (Batch 2 shipped) | `kernel.application.capability_helpers` |
| Fact Overlay runtime | `check_fact_overlay_binding(request, *, store, registry=None) -> FactOverlayCheckResult` | `kernel.application.fact_overlay_runtime` |
| Fact Overlay result DTO | `FactOverlayCheckResult` | `kernel.application.protocol.derivation_fact_overlay:367` |
| ProofFrame Recheck request DTO | `ProofFrameRecheckRequest(support_artifact, overlay)` (`kernel.application.protocol.proofframe:85`) | `kernel.application.protocol` |
| ProofFrame Recheck runtime | `recheck_proof_frame(request, *, store) -> ProofFrameRecheckResult` | `kernel.application.proofframe_runtime` |
| ProofFrame Recheck result DTO | `ProofFrameRecheckResult` (with `atom_verdicts: tuple[ProofFrameAtomVerdict, ...]`) | `kernel.application.protocol.proofframe:120` |
| `SupportArtifact` (input to Recheck) | produced by `check_derivation_binding(...)` evidence envelope | `kernel.core.store._support` |

### 4.4 G1 + G4 infrastructure available to reuse

- `SDKStore.check(...)` / `SDKStore.diagnose(...)` / `SDKStore.why_not(...)` established instance-method placement.
- `kernel.sdk._validation.validate_derivation(...)` accepts SDK `Derivation` only and attaches capability-specific `SDKStoreError.path` (Round 4 Q1 extraction; reused by G4).
- G1 + G4 error mapping uses `SDKStoreError(...) from exc`, including:
  - `RuleCompileError` from registry resolution → `path="$.<cap>.dependencies"`
  - `ValueError` from `_compiled_derivation_plan_to_application(...)` engine_ext conflict → `path="$.<cap>.derivation"`
  - `CapabilityHelperError` from A helpers → `path="$.<cap>.<arg-name>"`
  - `ProtocolShapeError` from request DTO `__post_init__` → `path="$.<cap>.request"` (G4)
  - Capability-specific runtime errors (e.g., `WhyNotRuntimeError`) → `path="$.<cap>"` (G4)
- G1 + G4 invariant test pattern: 6-class single-file mirroring (`__all__` unchanged + result types not exported / instance-method placement / flat-module-no-shells / no-internal-walker-audit-imports / thin-delegate / docstring-boundary-contract).
- G4 added explicit Frontier-defer assertions (no `kernel.core.rules.frontier` import). G2 may need similar capability-specific defer assertions.

### 4.5 G1+G4 forward trigger inherited by G2

Per G1 §5.5 (forward trigger to G2) and G4 §5.5 (re-recorded ownership), **G2 Step 0 MUST evaluate `kernel/sdk/shells/` subpackage migration before adding any G2 shell file**. The trigger is at the file-count signal: post-G1 = 2 files, post-G4 = 3 files, post-G2 (without migration) = 5 files. G2 is the natural migration point.

If migration happens, it becomes G2 Phase 0 hygiene **before any G2 implementation**, includes an explicit `#P1` carve-out for the G1 archived invariant test `test_g1_modules_are_flat_and_no_shells_package_exists`, and the G4 sibling test `test_g4_modules_are_flat_and_no_shells_package_exists`.

If migration is again deferred, G2 §5.5 must record a positive justification for keeping flat layout at 5 files (not just "convenient defer") and re-record ownership to G3 or to a dedicated hygiene blueprint.

## 5. Design — Step 0 Questions

This blueprint is at `draft` status. The questions below must be resolved before status advances to `scoped`.

### 5.1 Fact Overlay SDK input shape

**Question:** Does `SDKStore.check_fact_overlay(...)` accept:

1. SDK `Derivation` + binding mapping + SDK-friendly overlay shape (mappings / sequences),
2. SDK `Derivation` + binding mapping + raw `EvaluationOverlay` protocol DTO,
3. some other shape that hides `EvaluationOverlay` entirely (e.g., per-action-kind kwargs),
4. or no SDK method at all?

**Conservative default:** option 2 (raw `EvaluationOverlay` accepted at SDK boundary), provided it does not contradict the G1 §5.7 lock spirit.

**Falsifiers required:**

- Confirm or refute that SDK precedent permits accepting `kernel.application.protocol` DTOs as input. G1 §5.7 rejected `CompiledDerivationPlan` because it was "already-lowered application-layer entry"; `EvaluationOverlay` is **author-time intent** rather than a lowered representation, so the rejection rationale may not apply.
- Confirm whether existing application-layer Fact Overlay tests construct `EvaluationOverlay` directly, indicating it is the ergonomic intent shape.
- Reject any shape that requires SDK-side `EvaluationOverlay` reconstruction without source signal.

**Decision (2026-05-08):** Lock option 2 — `SDKStore.check_fact_overlay(derivation, binding, overlay, *, engine="native", registry=None) -> FactOverlayCheckResult`, where `derivation` is SDK `Derivation`, `binding` is a `$`-prefixed mapping validated through the shared SDK validators, and `overlay` is a raw `EvaluationOverlay` protocol DTO. G2 treats `EvaluationOverlay` as author-time intent, not a lowered application plan. It is therefore not covered by G1's rejection of `CompiledDerivationPlan`, which was rejected because it is already-lowered application-layer representation.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `EvaluationOverlay` is author-time intent, not lowered plan state | `EvaluationOverlay` is a frozen protocol DTO over `fact_actions` / `rule_actions` with validation only for action tuple shape (`derivation_fact_overlay.py:263-278`). `FactOverlayCheckRequest` accepts either legacy tuple-of-`FactValueOverride` or `EvaluationOverlay` directly (`derivation_fact_overlay.py:281-307`). It is not a compiled plan and does not contain runtime store/registry/projection/cache state. | PASS — G1 §5.7 `CompiledDerivationPlan` rejection does not apply. |
| F2 | Application tests already treat `EvaluationOverlay` as the ergonomic intent shape | Protocol tests construct `EvaluationOverlay(fact_actions=...)`, preserve legacy positional fact actions, allow empty overlay for runtime invalid-request behavior, and accept rule-action lane values (`test_application_fact_overlay_protocol.py:274-313`). Runtime tests pass `EvaluationOverlay(...)` directly to `FactOverlayCheckRequest` for rule-action rejection and other preflight paths (`test_application_fact_overlay_runtime_native.py:236-258`). | PASS — raw overlay is already the user-facing application intent object. |
| F3 | A helper surface already builds the action pieces, not a separate SDK overlay DTO | Batch 2 helpers build `FactValueOverride`, `FactRemoveAction`, and `EvaluationOverlay` from existing store/schema context (`capability_helpers/fact_overlay.py:28-178`). Creating a parallel SDK overlay wrapper would duplicate that construction path and add a new outward SDK type under `#6` without source signal. | PASS — no new SDK overlay wrapper in first slice. |
| F4 | Direct protocol validation constrains bad overlay shapes | `EvaluationOverlay.__post_init__` rejects non-tuple actions and unknown action types (`derivation_fact_overlay.py:268-278`; tests at `test_application_fact_overlay_protocol.py:300-312`). G2 will still remap request DTO `ProtocolShapeError` and runtime failures to `SDKStoreError` in §5.8. | PASS — raw DTO does not bypass validation. |

**Forward implications:**

- `SDKStore.check_fact_overlay(...)` does not accept application `CompiledDerivationPlan`, raw `FactOverlayCheckRequest`, SDK-owned overlay DTOs, or per-action keyword shapes in this slice.
- Implementation validates `derivation` and `binding` with the same shared SDK validators used by G1/G4, then constructs `FactOverlayCheckRequest(plan, binding, overlay, engine)`.
- `overlay` wrong-type / malformed-shape failures are handled through request DTO construction and remapped per §5.8, not through a new SDK overlay normalizer.

### 5.2 ProofFrame Recheck SDK input shape

**Question:** Does `SDKStore.recheck_proof_frame(...)` accept:

1. raw `SupportArtifact` + raw `EvaluationOverlay`,
2. an SDK wrapper around `SupportArtifact`,
3. composition: take the result of a prior `sdk.check(...)` call (a `CheckResult` whose `evidence_envelope` carries the `SupportArtifact`) plus an overlay,
4. some hybrid?

**Conservative default:** option 1 — raw `SupportArtifact` + raw `EvaluationOverlay`. ProofFrame Recheck is inherently a re-evaluation of an already-existing support, so the support must come from somewhere; SDK does not own its construction.

**Falsifiers required:**

- Confirm `SupportArtifact` is `@dataclass(frozen=True)` and contains no SDK-level state that would warrant wrapping.
- Confirm whether composition (option 3) creates a new "Q-Sibling at SDK layer" coupling that violates `#3` heterogeneity (one SDK method depending on the output of another).
- Reject SDK wrapper unless source signal demonstrates the raw `SupportArtifact` exposes harmful internals.

### 5.3 Fact Overlay return shape

**Question:** Does `SDKStore.check_fact_overlay(...)` return raw `FactOverlayCheckResult`, wrap, or simplify?

**Conservative default:** documented passthrough of `FactOverlayCheckResult`, mirroring G1 / G4.

**Falsifiers required:**

- Confirm G1 + G4 raw-passthrough precedent applies (`__all__` unchanged, no SDK wrapper).
- Confirm `FactOverlayCheckResult` has no mutable internals that warrant wrapping.

### 5.4 ProofFrame Recheck return shape

**Question:** Does `SDKStore.recheck_proof_frame(...)` return raw `ProofFrameRecheckResult`, wrap, or simplify?

**Conservative default:** documented passthrough of `ProofFrameRecheckResult`.

**Falsifiers required:**

- Same as §5.3 with `ProofFrameRecheckResult` shape inspected.

### 5.5 Module placement and `kernel/sdk/shells/` migration

**Question:** Does G2 trigger the `kernel/sdk/shells/` subpackage migration (inherited from G1+G4 §5.5), or defer again?

Options:

- Migrate `check.py`, `diagnose.py`, `why_not.py`, plus G2's two new files into `kernel/sdk/shells/`. Includes `#P1` carve-out for `test_g1_modules_are_flat_and_no_shells_package_exists` and the matching G4 invariant.
- Continue flat layout for G2 (post-G2 = 5 flat shell files), re-record trigger to G3.

**Conservative default:** **migrate**. G2 is the natural migration point per the inherited trigger; deferring twice while file count grows runs counter to the trigger's intent.

**Falsifiers required:**

- Verify migration cost: list every file/test/import that needs touching; estimate `#P1` carve-out scope for G1+G4 invariant tests.
- Confirm thin `SDKStore` delegate pattern is preserved under either option.
- Verify G2 invariants can still mirror G1+G4 patterns under shells/ layout.

### 5.6 Module file naming under chosen layout

**Question:** What are the G2 shell file names (under flat or shells/ layout)?

Options for the two G2 capabilities:

- Flat: `kernel/sdk/fact_overlay.py` (`sdk_fact_overlay_check(...)`) + `kernel/sdk/proof_frame.py` (`sdk_proof_frame_recheck(...)`).
- Subpackage: same filenames under `kernel/sdk/shells/`.

`SDKStore` method names are a separate sub-question (§5.7 below).

**Falsifiers required:**

- Confirm naming aligns with existing `check.py` / `diagnose.py` / `why_not.py` convention (single concept per file).
- Confirm no name collision with existing `kernel/sdk/` modules.

### 5.7 SDKStore method names

**Question:** What are the SDKStore method names for the two G2 capabilities?

Candidates:

- `SDKStore.check_fact_overlay(...)` + `SDKStore.recheck_proof_frame(...)` — verb-first, explicit.
- `SDKStore.fact_overlay_check(...)` + `SDKStore.proof_frame_recheck(...)` — noun-verb.
- `SDKStore.fact_overlay(...)` + `SDKStore.proof_frame(...)` — single concept (drops verb).

**Conservative default:** `SDKStore.check_fact_overlay(...)` + `SDKStore.recheck_proof_frame(...)` — preserves verb-first style of G1's `check` / `diagnose` / G4's `why_not`.

**Falsifiers required:**

- Confirm consistency with existing G1 / G4 method names.
- Reject any name that collides with or shadows an existing `SDKStore` attribute (`SDKStore.add`, `.set`, `.ref`, `.evaluate`, `.get`, `.check`, `.diagnose`, `.why_not`, `.batch`, etc.).
- Note that final renaming is out of G2 scope (post-L redesign blueprint).

### 5.8 Error mapping and Q3 / Batch-4 Sibling discipline

**Question:** Which non-A helper / runtime exceptions remap to `SDKStoreError`, and what is the per-method Sibling discipline at the SDK layer?

Known candidate exceptions:

- `validate_derivation` `SDKStoreError` (already raised, shared with G1/G4).
- `_compiled_derivation_plan_to_application(...)` `ValueError` (G1 B.2 + G4 §5.6 pattern).
- `_resolve_runtime_registry(...)` `RuleCompileError` (G1 B.1 + G4 §5.6 pattern).
- A helper `CapabilityHelperError` (Fact Overlay only — for overlay normalization if `build_fact_value_override(...)` is used).
- Request DTO `ProtocolShapeError` (both methods — Fact Overlay's `FactOverlayCheckRequest.__post_init__` and ProofFrame's `ProofFrameRecheckRequest.__post_init__`).
- Runtime errors: `FactOverlayRuntimeError` (if exists) / generic runtime exceptions.

Sibling discipline:

- Application-layer Fact Overlay vs Check: shares helpers via `_derivation_match_helpers`, **does not call** `check_derivation_binding(...)`.
- Application-layer ProofFrame Recheck: standalone; does not call Check.
- **SDK-layer question:** does `sdk_fact_overlay_check` or `sdk_proof_frame_recheck` call `sdk_check`, `sdk_diagnose`, or `sdk_why_not`? Conservative: **NO** — mirror G1/G4 Q1 Sibling lock.

**Conservative default:** every non-SDK exception crossing SDK shell boundary remaps to `SDKStoreError(...) from exc` with capability-specific path; no SDK shell calls another SDK shell internally.

## 6. Boundaries And Invariants

| Principle | G2 interpretation |
|---|---|
| `#1` Application-first authority | SDK shell lowers/wraps and delegates; does not own Fact Overlay or ProofFrame Recheck semantics. |
| `#3` Heterogeneity | Fact Overlay Check (overlay-bearing Check variant) and ProofFrame Recheck (re-evaluate prior support) are distinct capabilities; no false-merge. |
| `#4a` Intent-minimal canonical input | SDK accepts SDK-layer intent for inputs that have a clear SDK alternative (Derivation, binding mapping); for inputs without SDK alternatives (`SupportArtifact`, possibly `EvaluationOverlay`), §5.1 + §5.2 decide. |
| `#5` Layer isolation | `kernel.sdk` may import public `kernel.application` surfaces; application/core must not import SDK; G2 uses public application protocol DTOs and runtime functions only. |
| `#6` No outward compat without signal | New SDK methods are outward commitments; keep narrow. No new SDK error subclass; no new SDK-owned wrapper unless §5 decides one with source signal. |
| `#19` Testing | Flat unittest files; per-method test + invariant file pattern from G1/G4. |
| `#P0` Conflict resolution | Authority > layer isolation > read-only > ergonomics > outward commitment. |
| `#P1` Revision flow | Any deviation gets a named carve-out with reason/scope/impact. The `kernel/sdk/shells/` migration (if it happens) requires `#P1` carve-out for G1 + G4 invariant tests. |

Forbidden until scoped:

- No `kernel.sdk.__all__` addition.
- No README quickstart update.
- No `factpy` alias / rename.
- No `kernel.application` import of `kernel.sdk`.
- No SDK-side `SupportArtifact` construction.
- No new SDK error subclass.

## 7. Acceptance

Draft-stage acceptance:

- [x] G2 draft opened on the latest G1+G4 combined baseline (`acb5a6e`).
- [x] Round 8 G2 verdict ("pending Step 0 shape decision") + the inherited `kernel/sdk/shells/` migration trigger captured.
- [x] G1 + G4 infrastructure inventoried as available prior art.
- [x] Eight Step 0 questions enumerated covering input shapes (×2), return shapes (×2), shells/ migration, file naming, method naming, error mapping + Sibling discipline.
- [ ] §5.1-§5.8 falsifier passes complete.
- [ ] Status moves to `scoped` only after all Step 0 questions are resolved.

Scoped-stage acceptance will be filled once §5 is locked.

## 8. Implementation Plan

Deferred until status `scoped`.

Expected shape if Step 0 follows conservative defaults:

1. **Phase 0** — module skeleton / `SDKStore` method stubs / placeholder tests / **shells/ migration if §5.5 locks it (Phase 0 hygiene with `#P1` carve-out for G1 + G4 invariant tests)**.
2. **Phase 1** — `sdk_fact_overlay_check(...)` real implementation + contract tests.
3. **Phase 2** — `sdk_proof_frame_recheck(...)` real implementation + contract tests + Q3/Batch-4 Sibling discipline tests.
4. **Phase 3** — `test_sdk_g2_invariants.py` (6-class mirror) + docs updates + cumulative G2 strict audit.
5. **Phase 4** — close-out, archive, snapshot publish (`v0.1-l-g2-fact-overlay-proofframe-recheck-2026-05-09` or `-2026-05-08` if same day).

The 5-phase plan reflects G2's two-method scope (vs G4's single-method) and the potential shells/ migration phase.

## 9. Docs To Update

If implementation is scoped:

- `src/kernel/sdk/docs/04_api_surface.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/application/docs/01_overview.md` (G2 test inventory)
- `src/kernel/application/docs/01_overview_en.md` (G2 test inventory)
- `docs/blueprints/archive/README.md` on archive

README quickstart remains untouched unless a separate blueprint scopes it.

## 10. Outcome / Deviations

To be filled after implementation.
