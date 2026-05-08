# L Direction G3 — Rule Overlay SDK Shells

- **Status:** draft
- **Created:** 2026-05-08
- **Last Updated:** 2026-05-08
- **Parent:** L Direction (post-A+B+G1+G4+G2 v1-ready roadmap target)
- **Related Bundle:** [post-routemap-direction-selection-input](../../references/working/post-routemap-direction-selection-input/) — Round 8 SDK conventions audit (G3 verdict: **pending Step 0 shape decision** — three-sister naming has no SDK precedent and raw `RuleSpec` exposure breaks the DSL abstraction)
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck (archived)](../archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md)
  - [2026-05-08_l-direction-g4-why-not-frontier (archived)](../archive/2026-05-08_l-direction-g4-why-not-frontier.md)
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md)
  - [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md)
  - [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md)
- **Audit Log:** [2026-05-08_l-direction-g3-rule-overlays.audit.md](./2026-05-08_l-direction-g3-rule-overlays.audit.md)

## 1. Problem

G1 shipped Check / Diagnose SDK shells, G4 shipped Why-not, and G2 shipped Fact Overlay Check + ProofFrame Recheck. SDK consumers can now run the first three L groups without importing `kernel.application`.

The next L group is G3: **rule overlays**. This is the hardest remaining SDK-shape decision before G5 because it combines two tensions:

- The application layer intentionally preserves **three heterogeneous rule-overlay families**: rule disable, literal replace, and add condition. A's builders and runtimes are three separate functions because their argument shapes differ.
- The SDK layer should not simply expose raw `RuleSpec` or blindly copy application helper names. Round 8 explicitly flagged G3 as a mismatch: "three-sister naming has no SDK precedent; raw `RuleSpec` exposure breaks DSL abstraction."

This blueprint starts G3 Step 0 only. It does not implement SDK methods until the §5 questions are source-grounded and scope-frozen.

## 2. Goals

- Decide the G3 SDK outward shape for rule overlays with the same per-family Step 0 falsifier discipline used by G1 / G4 / G2.
- Preserve `#3` heterogeneity unless a source-grounded SDK shape proves a unification is clearer than the three runtime families.
- Avoid exposing raw `RuleSpec` at the SDK boundary unless Step 0 explicitly proves there is no safer SDK-facing alternative.
- Reuse shipped L infrastructure:
  - `kernel/sdk/shells/` package from G2.
  - `SDKStore` instance-method delegation.
  - `SDKStoreError(...) from exc` remap discipline.
  - Shared validators in `kernel.sdk.shells._validation` where they match G3 inputs.
- Establish a scoped implementation plan only after §5 falsifiers are resolved.

## 3. Non-Goals

- **No implementation before scoped.** No `SDKStore.*rule*` methods, shell files, docs updates, tests, or exports ship before §5 is locked and status moves to `scoped`.
- **No README quickstart change.** Per `#6`, new SDK shell promotion does not automatically enter README quickstart.
- **No `kernel.sdk.__all__` expansion by default.** G1 / G4 / G2 set the pattern: SDKStore instance methods first; top-level exports need their own falsifier.
- **No `factpy` rebrand.** Import root remains `kernel.sdk`; OpenAI-style ergonomics are recorded as post-L redesign preference, not G3 scope.
- **No G5 decisions.** Round events and ProofFrame diff remain a separate future blueprint.
- **No new application runtime or protocol shape.** G3 wraps existing application rule-overlay runtimes and builders; it does not modify `RuleDisableRequest`, `RuleLiteralReplaceRequest`, `RuleAddConditionRequest`, or their runtimes.
- **No SDK mutation of the store / ledger.** Rule overlays are temporary what-if checks. They do not register rules, mutate ledger state, or persist overlays.
- **No B walker dependency.** G3 returns application result DTOs unless Step 0 explicitly proves a SDK wrapper is necessary.
- **No Frontier or round-event behavior.** G3 does not reopen G4's Frontier defer or G5's recorder / payload decisions.

## 4. Current Context

### 4.1 L ordering and baseline

Q1 split locked: **G1 -> G4 -> G2 -> G3 -> G5**. G1, G4, and G2 are implemented, archived, and published. This G3 blueprint is based on `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-2026-05-08` @ `d658390`.

Current branch for this draft work: `codex/v0.1-l-g3-rule-overlays-2026-05-08`.

### 4.2 Round 8 G3 verdict

Round 8 SDK conventions audit recorded:

> **G3 Rule overlays: pending Step 0 shape decision** — three-sister naming has no SDK precedent; raw `RuleSpec` exposure breaks DSL abstraction. Step 0 must choose namespace (`sdk.rule.*`), polymorphic `sdk.mutate_rule(kind=...)`, or three sister methods with explicit justification.

This verdict means G3 cannot copy the application helper surface blindly. It must first decide:

- whether SDK exposes three separate methods, one polymorphic method, or a nested namespace;
- how SDK callers identify the target rule without raw `RuleSpec`;
- which raw application DTO inputs are acceptable after the G2 precedent;
- how much action-specific shape the SDK should expose directly.

### 4.3 Existing Tier 2 / application surfaces

| Area | Existing surface | Layer |
|---|---|---|
| Disable helper | `build_rule_disable_request(rule_spec, support, *, branch_index, atom_index, overlay=None, note=None)` | `kernel.application.capability_helpers` |
| Literal replace helper | `build_rule_literal_replace_request(rule_spec, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)` | `kernel.application.capability_helpers` |
| Add condition helper | `build_rule_add_condition_request(rule_spec, support, *, branch_index, added_atom, overlay=None, note=None)` | `kernel.application.capability_helpers` |
| Disable runtime | `check_rule_disable_action(request) -> RuleDisableResult` | `kernel.application.rule_disable_runtime` |
| Literal replace runtime | `check_rule_literal_replace_action(request) -> RuleLiteralReplaceResult` | `kernel.application.rule_literal_replace_runtime` |
| Add condition runtime | `check_rule_add_condition_action(request) -> RuleAddConditionResult` | `kernel.application.rule_add_condition_runtime` |
| Inputs shared by all three | `RuleSpec`, `SupportArtifact`, `EvaluationOverlay` | `kernel.core` / `kernel.application.protocol` |
| Action DTOs | `RuleDisableAction`, `RuleLiteralReplaceAction`, `RuleAddConditionAction`, `RuleLiteralPath`, `RuleAddedAtom` | `kernel.application.protocol.derivation_fact_overlay` |

### 4.4 A-layer rationale that G3 must preserve or explicitly reject

A's application builder blueprint keeps three sub-builders separate:

- `RuleDisableAction` needs `branch_index` + `atom_index`.
- `RuleLiteralReplaceAction` needs `branch_index` + `atom_index` + `literal_path` + `old_literal` + `new_literal`.
- `RuleAddConditionAction` needs `branch_index` + `added_atom`.

The A blueprint explicitly cites `#3` heterogeneity: unifying these into `build_rule_overlay_request(kind=...)` would require a discriminated union that adds caller complexity without ergonomic gain. G3 may still choose a different SDK surface, but it must explain why SDK conventions outweigh this application-layer heterogeneity.

### 4.5 G1 / G4 / G2 infrastructure available to reuse

- `kernel/sdk/shells/` is active from G2. G3 shell files must land under this package unless §5 explicitly reopens layout.
- Existing shell methods use `SDKStore.<method>(...)` instance placement with thin delegates in `store.py`.
- `kernel.sdk.shells._validation` currently provides:
  - `validate_derivation(...)`
  - `validate_binding(...)`
  - `validate_evaluation_overlay(...)`
- G2 established a cross-cutting precedent:
  - Raw application protocol DTOs may cross the SDK boundary as input when they are frozen application-canonical and no SDK alternative exists without inventing new outward surface or breaking Sibling discipline.
  - This precedent covered `EvaluationOverlay` and `SupportArtifact`.
- G1 / G4 / G2 do not expand `kernel.sdk.__all__`; result DTOs remain documented passthrough values.
- G1 / G4 / G2 use `SDKStoreError(...) from exc` for shell-boundary errors.

### 4.6 G3-specific constraints from shipped code

- Rule-overlay request DTOs require raw `RuleSpec`, `SupportArtifact`, and `EvaluationOverlay`.
- A helpers construct exactly one action into a fresh overlay, rejecting non-empty caller overlays.
- Runtimes return result DTOs with `variant_rows`, `proof_frame`, `errors`, and `warnings`; they do not mutate store or registry.
- `RuleDisableRequest`, `RuleLiteralReplaceRequest`, and `RuleAddConditionRequest` require `EvaluationOverlay`, not tuple-form overlays.
- Application docs still classify rule overlays as application-layer only until G3 ships.

## 5. Design — Step 0 Questions

This blueprint is at `draft` status. The questions below are not locked. Each must pass a source-grounded falsifier before status can move to `scoped`.

### 5.1 SDK surface shape: three methods, namespace, or polymorphic method

**Question:** Does G3 expose:

1. three `SDKStore` instance methods,
2. a nested namespace such as `store.rule.disable(...)`,
3. a single polymorphic method such as `store.mutate_rule(kind=...)`,
4. or no SDK surface yet?

**Conservative default:** three explicit `SDKStore` instance methods, because A and runtime layers already preserve three separate capability families.

**Decision (2026-05-08):** Lock option 1 — three explicit `SDKStore` instance methods. G3 ships `SDKStore.disable_rule(...)`, `SDKStore.replace_rule_literal(...)`, and `SDKStore.add_rule_condition(...)` as three flat sibling methods (final names locked in §5.7). No nested `store.rule.*` namespace; no polymorphic `store.mutate_rule(kind=...)`; G3 does ship an SDK surface (defer-entirely rejected). The shells live at `kernel/sdk/shells/{rule_disable,rule_literal_replace,rule_add_condition}.py` per §5.6, building on the active `kernel/sdk/shells/` subpackage from G2 Phase 0.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Existing `SDKStore` method naming has any namespace precedent | One precedent exists: `SDKStore.views` exposes a `_SDKViewsManager` namespace with `create / update / delete / get / list` (see `src/kernel/sdk/store.py:195`). However: (a) `views` is a multi-operation manager over a single resource type (named `ViewSpec`) — it is not three-action-on-one-rule analog; (b) `views` predates L Direction; (c) all five L Direction methods shipped to date (`check`, `diagnose`, `why_not`, `check_fact_overlay`, `recheck_proof_frame`) are flat sibling methods on `SDKStore`. Adopting a `store.rule.*` namespace mid-L would split L surface into two patterns (flat + nested) without consumer signal. Post-L SDK ergonomics redesign blueprint (per `feedback_sdk_ergonomics_redesign_target`) is the right venue for any namespace move; G3 stays flat. | PASS — namespace is the wrong move now. |
| F2 | Polymorphic method would violate `#3` by forcing a discriminated union across three distinct argument shapes | Application layer keeps three distinct capabilities. Verified at `src/kernel/application/rule_disable_runtime.py:26` (`check_rule_disable_action`), `src/kernel/application/rule_literal_replace_runtime.py:43` (`check_rule_literal_replace_action`), `src/kernel/application/rule_add_condition_runtime.py:35` (`check_rule_add_condition_action`). Three distinct request DTOs at `kernel/application/protocol/rule_disable.py`, `rule_literal_replace.py`, and `rule_add_condition.py`. Each has incompatible spec arguments: disable needs `(branch_index, atom_index)`; literal_replace needs `(branch_index, atom_index, literal_path, old_literal, new_literal)`; add_condition needs `(branch_index, added_atom)`. A polymorphic `mutate_rule(kind=..., **kwargs)` would force a discriminated union over three disjoint kwarg sets, which is precisely the `#3` heterogeneity false-merge that G2 §5.8 already rejected for the analogous A-side rule-overlay builders ("each rule overlay action has distinct spec shape — `atom_index` only vs `literal_path + old + new` vs `added_atom`. Unifying would require a discriminated union type that adds caller complexity without ergonomic gain"). | PASS — polymorphic rejected. |
| F3 | Three explicit methods create unacceptable outward surface noise under `#6` | Current `SDKStore` exposes 36 methods; G3 adds 3 (= 39 total). The three rule-overlay methods are distinct semantic actions (disable an atom, replace a literal, add a condition), not redundant surface. Naming follows the verb-first pattern locked across G1 (`check` / `diagnose`), G4 (`why_not`), and G2 (`check_fact_overlay` / `recheck_proof_frame`). Each method maps 1:1 to an existing application runtime, so the SDK surface is a thin reflection of substrate intent — the `#6` "no outward compat without signal" gate is satisfied because the shape comes from already-shipped application capabilities, not from invented SDK ergonomics. | PASS — surface noise acceptable. |
| F4 | G3 should defer entirely because raw `RuleSpec` cannot be resolved safely in §5.2 | The §5.1 SDK shape decision is independent of §5.2 (target rule input shape). Three locked methods can use any of the §5.2 candidates (raw `RuleSpec`, SDK `Rule`, `(rule_id, version)` lookup, `SupportArtifact`-derived target, SDK-owned target handle) once §5.2 resolves. If §5.2 concludes `no SDK shell yet` (defer-entirely), the §5.1 lock becomes moot but does not conflict — three method names are claims about surface shape, not rule input shape. Round 8 SDK conventions audit explicitly listed three options ("namespace `sdk.rule.*`, polymorphic `sdk.mutate_rule(kind=…)`, or three sister methods with explicit justification") and did NOT include defer-entirely; the audit's framing already presumes G3 ships an SDK surface in some form. | PARTIAL — does not block §5.1; §5.2 still must resolve. |

**Forward implications:**

- §5.6 (module + file layout) is now constrained to three new flat shell files under `kernel/sdk/shells/` (G2 Phase 0 already activated the subpackage); no `shells/rule/` sub-subpackage and no consolidated `shells/rule_overlay.py` mega-file.
- §5.7 (SDKStore method names) inherits the three-flat-method shape; final names need to satisfy verb-first style and avoid collision with existing `SDKStore` attributes.
- §5.2 (target rule input) is the next falsifier and is the critical one — Round 8 explicitly flagged raw `RuleSpec` exposure as a mismatch; §5.2 lock determines whether G3 ultimately ships or defers.
- Post-L SDK ergonomics redesign blueprint (per `feedback_sdk_ergonomics_redesign_target`) remains the right venue for evaluating `SDKStore` → `Client.rule.*` namespace migration once all G1-G5 capabilities have shipped.

### 5.2 Target rule input shape

**Question:** How does the SDK caller identify the target rule?

Options:

- raw `RuleSpec`;
- SDK `Rule` object;
- `(rule_id, version)` lookup through `SDKStore` / registry;
- `SupportArtifact`-derived target rule;
- some SDK-owned target handle.

**Conservative default:** do not accept raw `RuleSpec` unless falsifier shows every SDK-facing alternative is worse. Round 8 explicitly flags raw `RuleSpec` exposure as a mismatch.

**Decision (2026-05-08):** Lock option B — **SDK `Rule` object**. G3 SDK shell methods accept a SDK `Rule` (`kernel.sdk.dsl.Rule`) as the `rule` argument, mirroring G1's `Derivation` input pattern. The shell lowers the SDK `Rule` through the existing `SDKStore._compile_rule_input(rule)` path to produce a `RuleSpec`, then passes the `RuleSpec` to A's rule-overlay helpers (`build_rule_disable_request` / `build_rule_literal_replace_request` / `build_rule_add_condition_request`). SDK rejects raw `RuleSpec` (substrate IR), `(rule_id, version)` lookup (no SDK lookup API exists today; would require new outward surface), `SupportArtifact`-derived target (SupportArtifact's `rule_refs` is multi-rule, cannot uniquely identify a single target), and any SDK-owned target handle (invents new SDK type without signal).

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | A helper depends on full `RuleSpec` (where body), not just `(rule_id, version)` | `build_rule_disable_request(rule_spec, support, *, ...)` (`kernel/application/capability_helpers/rule_overlays.py:27-54`) extracts `rule_spec.rule_id` + `rule_spec.version` for the `RuleDisableAction` but **stores the full `rule_spec` in `RuleDisableRequest(rule_spec=rule_spec, ...)`** (line 50-54). Same for `build_rule_literal_replace_request` (line 89-93) and `build_rule_add_condition_request` (line 119-123). The runtime uses `rule_spec.where` for action validation (branch / atom-index range checks, literal-position resolution, added-atom IR validation). Therefore any §5.2 option must produce a full `RuleSpec`, not just `(rule_id, version)`. | Required — full `RuleSpec` is mandatory at A boundary. |
| F2 | SDK `Rule` lowers to `RuleSpec` without re-registering or mutating state | `Rule.to_authoring_payload()` at `kernel/sdk/dsl/rule.py:73-93` produces an authoring payload dict (rule_id, version, select, where, optional expose/status/description/tags/condition_weights). `kernel.authoring.rule_compile.compile_authoring_rule_v1(...)` lowers that payload to a compiled dict (verified existing import at `kernel/sdk/store.py:25`). `SDKStore._compile_rule_input(rule)` (`store.py:1040`) is the existing internal caller that drives this lowering; `SDKStore._run_rule(...)` (`store.py:847-862`) demonstrates the chain ending in `RuleSpec(rule_id=..., version=..., select_vars=..., where=..., expose=...)` construction directly from the compiled dict. No registry registration, no store mutation — the chain is read-only and idempotent. | PASS — Option B feasible via existing infrastructure. |
| F3 | `(rule_id, version)` lookup through `SDKStore` is available and layer-correct | No SDK API exposes `(rule_id, version) → RuleSpec` lookup. `RuleRegistry` (`kernel/core/rules/rule_ir.py:49`) is a caller-instantiated container — not a global SDKStore-owned registry. `SDKStore` does not maintain a persistent rule registry; each call constructs a fresh `RuleRegistry` from the input `Rule` (and its `dependency_rules()`) at runtime. Adding a `(rule_id, version)` lookup API would: (a) introduce new outward SDK surface under `#6` without consumer signal; (b) raise layer-correctness questions about who owns the registry lifecycle, persistence, and identity collisions across schemas; (c) duplicate work that the SDK `Rule` lowering chain already does. | REJECT — Option C requires new infrastructure under `#6`. |
| F4 | `SupportArtifact` reliably identifies the single target rule for all three overlays | `SupportArtifact.rule_refs: tuple[str, ...]` (`kernel/core/store/_support.py:103`) is a **tuple of rule reference strings**, not a single rule reference. Multi-step proofs that traverse `RuleRef` atoms produce multi-rule support. A single `SupportArtifact` may reference 0..N rules. Rule-overlay actions target one specific rule (rule_id + version) at one specific branch / atom-index — they require unambiguous single-rule identification. `SupportArtifact` alone is insufficient. | REJECT — Option D cannot uniquely identify the target rule. |
| F5 | Raw `RuleSpec` is covered by the G2 §5.1 + §5.2 cross-cutting precedent | G2's precedent is "raw application protocol DTOs may cross the SDK boundary as input when (a) frozen application-canonical AND (b) no SDK alternative without inventing new outward surface or breaking Sibling discipline." `RuleSpec` lives at `kernel/core/rules/rule_ir.py:28` — `kernel.core.rules` is **substrate rule IR**, not `kernel.application.protocol`. The precedent specifically scoped to "application protocol DTOs" (e.g., `EvaluationOverlay`, `SupportArtifact`, `WhyNotUniverseResult`); substrate IR is a different layer. Round 8 SDK conventions audit independently flagged "raw `RuleSpec` exposure breaks DSL abstraction" as the dominant G3 mismatch. SDK `Rule` is the SDK-side authoring DSL counterpart that is layer-correct for SDK input. | REJECT — Option A fails the precedent test AND the Round 8 mismatch. |

**Forward implications:**

- §5.3 (Support input) inherits raw `SupportArtifact` per G2 §5.2 precedent (frozen, application-canonical, no alternative).
- §5.4 (Overlay/action argument shape) is sharpened: caller passes the SDK `Rule` plus the action-specific kwargs (`branch_index` / `atom_index` for disable; +`literal_path` / `old_literal` / `new_literal` for replace; +`added_atom` for add_condition); no SDK-owned overlay normalizer, A helper builds the `EvaluationOverlay(rule_actions=...)` internally.
- §5.5 (Module placement) needs SDK `Rule` validator. A new shared `validate_rule(value, *, path)` in `kernel/sdk/shells/_validation.py` (analogous to `validate_derivation`) can be reused across all three G3 shells. Implementation can also leverage the existing `SDKStore._compile_rule_input(rule)` for the lowering itself; the new shared validator only checks `isinstance(rule, Rule)` and raises `SDKStoreError(path="$.<method>.rule")`.
- §5.7 (Method names) — inputs are `(rule, support, *, branch_index, atom_index, ...)` for all three; final method-name lock proceeds with this signature shape in mind.
- §5.8 (Error mapping) — `_compile_rule_input(rule)` already wraps internal exceptions, returning a compiled dict; `RuleSpec(...)` construction can raise `RuleCompileError` if the compiled dict has invalid select_vars / where; SDK shell remaps to `SDKStoreError(path="$.<method>.rule") from exc`. Same `RuleCompileError`-from-registry remap pattern as G1 B.1 fix applies for any `_resolve_runtime_registry` path if registry resolution remains in scope (likely not — rule-overlay runtimes operate on a single rule_spec, not a registry of dependent rules).
- G3 ships an SDK surface (defer-entirely was rejected by §5.1 falsifier set + Round 8 framing); §5.2 lock confirms feasibility through SDK `Rule` lowering.
- Verify whether accepting raw `RuleSpec` can be justified by G2's raw DTO precedent, or whether `RuleSpec` is different because it is substrate rule IR rather than frozen application protocol intent/evidence.

### 5.3 Support input shape

**Question:** Does each rule-overlay SDK method accept raw `SupportArtifact`, a prior `CheckResult`, or no support argument?

**Conservative default:** raw `SupportArtifact`, by G2 §5.2 precedent and Sibling discipline.

**Decision (2026-05-08):** Lock raw `SupportArtifact`. All three G3 SDK methods accept a raw `SupportArtifact` (`kernel.core.store._support.SupportArtifact`) as the `support` argument, mirroring the G2 ProofFrame Recheck pattern. No SDK wrapper, no `CheckResult` extraction, no internal `sdk.check(...)` call. Falsifier outcomes (3/3 PASS, identical to G2 §5.2 reasoning):

- **F1**: `SupportArtifact` is `@dataclass(frozen=True)` with canonical sorted fields (`kernel/core/store/_support.py:96-126`); no SDK-layer state. **PASS**.
- **F2**: A helpers `build_rule_disable_request(rule_spec, support, *, ...)`, `build_rule_literal_replace_request(...)`, `build_rule_add_condition_request(...)` (`kernel/application/capability_helpers/rule_overlays.py:27 / :57 / :96`) all accept `support: SupportArtifact` directly. **PASS**.
- **F3**: Composition through `CheckResult.engine_payload` would force the SDK to inspect a `SupportArtifact | ProvenanceEnvelope` union and either reject non-native or call `sdk_check` internally — same Sibling-discipline violation G2 §5.2 already rejected. **PASS — composition rejected**.

The G2 §5.1+§5.2 cross-cutting precedent ("raw application protocol DTOs at SDK boundary when frozen application-canonical AND no SDK alternative") covers this lock cleanly — `SupportArtifact` is frozen, application-canonical, and has no SDK-side alternative.

### 5.4 Overlay / action argument shape

**Falsifiers required:**

- Confirm rule-overlay request DTOs require `support_artifact`.
- Confirm composition through `CheckResult` would repeat the G2-rejected pattern of inspecting `CheckResult.engine_payload` union or calling sibling SDK shell.
- Confirm raw `SupportArtifact` still satisfies the G2 precedent after rule overlays add `RuleSpec`.

### 5.4 Overlay / action argument shape

**Question:** Which action-specific arguments cross the SDK boundary?

Candidates:

- Disable: `branch_index`, `atom_index`.
- Literal replace: `branch_index`, `atom_index`, raw `RuleLiteralPath`, `old_literal`, `new_literal`.
- Add condition: `branch_index`, raw `RuleAddedAtom`.
- Optional `note`.
- Optional caller-provided `EvaluationOverlay`.

**Conservative default:** mirror A helper arguments, with raw `RuleLiteralPath` and raw `RuleAddedAtom` treated as application protocol DTOs only if falsifier says new SDK wrappers would add no value.

**Falsifiers required:**

- Verify whether `RuleLiteralPath` and `RuleAddedAtom` are frozen application-canonical DTOs comparable to G2's raw DTO precedent.
- Verify whether SDK-friendly alternatives are obvious and source-grounded, not invented.
- Confirm A helper behavior around `overlay=None`, empty overlay, and non-empty overlay rejection.
- Decide whether `note=None` remains a SDK convenience parameter or is omitted to keep surface minimal.

### 5.5 Return shape

**Question:** Do the three methods return raw application result DTOs or SDK wrappers?

Candidates:

- `RuleDisableResult`;
- `RuleLiteralReplaceResult`;
- `RuleAddConditionResult`;
- SDK-owned wrappers / simplified summaries.

**Conservative default:** documented passthrough of raw result DTOs, mirroring G1 / G4 / G2.

**Decision (2026-05-08):** Lock documented passthrough — each G3 method returns the raw application result DTO directly:

- `disable_rule_*(...)` → `RuleDisableResult` (`kernel/application/protocol/rule_disable.py:80`)
- `replace_rule_literal_*(...)` → `RuleLiteralReplaceResult` (`kernel/application/protocol/rule_literal_replace.py:82`)
- `add_rule_condition_*(...)` → `RuleAddConditionResult` (`kernel/application/protocol/rule_add_condition.py:82`)

(Method names are §5.7-pending; result DTO bindings are independent of method-name choice.) None of the three result DTOs is added to `kernel.sdk.__all__`; SDK callers either import them from `kernel.application.protocol` or use them via attribute access.

**Falsifier outcomes (3/3 PASS):**

- **F1**: All three result DTOs are frozen application protocol dataclasses (verified by class declarations and the established protocol pattern under `kernel/application/protocol/`); no mutable SDK state, no opaque internals. **PASS**.
- **F2**: Current `kernel.sdk.__all__` length is 34 across G1 + G4 + G2 cycles; lock requires preservation. New G3 invariant test will mirror the G1+G4+G2 pattern asserting `__all__` length unchanged and result DTOs absent. **PASS — preservation locked**.
- **F3**: No wrapper signal: G1 + G4 + G2 all ship documented passthrough (`CheckResult` / `DiagnoseResult` / `WhyNotUniverseResult` / `FactOverlayCheckResult` / `ProofFrameRecheckResult`); G3 inherits the established precedent without divergence. Adding wrappers would force a new outward compat commitment under `#6` without consumer signal. **PASS**.

### 5.6 Module and file layout

### 5.6 Module and file layout

**Question:** How many G3 shell modules should exist under `kernel/sdk/shells/`?

Options:

- one `rule_overlays.py` module containing all three functions;
- three sibling modules (`rule_disable.py`, `rule_literal_replace.py`, `rule_add_condition.py`);
- a nested `shells/rule/` package.

**Conservative default:** one `shells/rule_overlays.py` module if §5.1 selects three `SDKStore` methods, because A grouped the three builders in one helper module while preserving separate functions.

**Decision (2026-05-08):** Lock **three sibling modules** under `kernel/sdk/shells/`:

- `kernel/sdk/shells/rule_disable.py` exporting `sdk_rule_disable(...)`
- `kernel/sdk/shells/rule_literal_replace.py` exporting `sdk_rule_literal_replace(...)`
- `kernel/sdk/shells/rule_add_condition.py` exporting `sdk_rule_add_condition(...)`

File names mirror the application protocol/runtime filenames (`kernel/application/protocol/rule_{disable,literal_replace,add_condition}.py`, `kernel/application/rule_{disable,literal_replace,add_condition}_runtime.py`) so a Sibling static scan can locate substrate boundaries by filename alone. Function names mirror the file names with `sdk_` prefix, consistent with G1+G4+G2 (`sdk_check`, `sdk_diagnose`, `sdk_why_not`, `sdk_fact_overlay_check`, `sdk_proof_frame_recheck`). This decision overrides the blueprint's conservative default ("one consolidated module"), per falsifier evidence below. SDKStore *method* names are independent — locked separately at §5.7.

**Falsifier outcomes (4/4 PASS, override conservative default):**

- **F1**: Three modules make Sibling static scans **easier**, not harder. G2 invariant `test_g2_modules_do_not_import_internal_or_walker_layers` iterates per-shell-module (`G2_MODULES = ("kernel.sdk.shells.fact_overlay", "kernel.sdk.shells.proof_frame")`). G3 follows the same pattern with three module entries; one consolidated `rule_overlays.py` would force per-function source slicing inside one file, breaking the invariant test pattern. **PASS — three modules**.
- **F2**: Three modules do not overfit to runtime filenames; they reflect the `#3` heterogeneity that §5.1 already locked. G2 already shipped two modules (`fact_overlay.py` + `proof_frame.py`) for two distinct capabilities; G3 is the same pattern at three modules. Consolidation would inherit G2 §5.8 false-merge risk. **PASS — heterogeneity preserved**.
- **F3**: Nested `shells/rule/` subpackage is premature. G2 Phase 0 just activated `shells/` itself; adding a sub-subpackage would require another `__init__.py`, complicate import paths, and create a new convention before three modules prove the need. Sibling SDK consumers (G5 at minimum) may add more shell families; sub-subpackages can be reintroduced later under a separate trigger if the module count exceeds ~10. **PASS — defer subpackage**.
- **F4**: Application's grouping of three builders in one `capability_helpers/rule_overlays.py` is helper-layer coincidence, not a contract for shell-layer grouping. A's helpers share validation logic via `_validate_rule_overlay_inputs(...)` and `_request_overlay(...)` which justifies one file at the helper layer. SDK shells do NOT share a build helper — each shell calls a single A helper and dispatches to a single runtime. The shared validation that DOES apply (rule, support, overlay) lives in `kernel/sdk/shells/_validation.py`, not duplicated in shell files. **PASS — no shared helper to colocate**.

**Forward implications:**

- §5.9 inherits three test file structure: `test_sdk_rule_disable.py`, `test_sdk_rule_literal_replace.py`, `test_sdk_rule_add_condition.py`, plus `test_sdk_g3_invariants.py`.
- G3 invariant `test_g3_modules_live_in_shells_subpackage` will assert all three shell files exist; `G3_MODULES` constant lists three FQ module paths.
- Post-G3 shell file count will be 8 (G1's 2 + G4's 1 + G2's 2 + G3's 3); `kernel/sdk/shells/` subpackage activated at G2 Phase 0 holds.

### 5.7 SDKStore method names

**Question:** What are the SDK method names?

Candidate names:

- `disable_rule(...)`, `replace_rule_literal(...)`, `add_rule_condition(...)`;
- `check_rule_disable(...)`, `check_rule_literal_replace(...)`, `check_rule_add_condition(...)`;
- `rule_disable(...)`, `rule_literal_replace(...)`, `rule_add_condition(...)`;
- namespace-style names if §5.1 chooses a namespace.

**Conservative default:** verb-first names that make the what-if check nature explicit without copying application runtime names wholesale.

**Decision (2026-05-08):** Lock **Group A** — `check_rule_disable(...)`, `check_rule_literal_replace(...)`, `check_rule_add_condition(...)`. Each method is an SDKStore instance method that computes what-if rule-overlay outcomes against an existing support frame, with no ledger mutation, no rule-registry mutation, and no persistent rule state change. Method-name shape preserves the SDK what-if convention established by G1 (`check`) and G2 (`check_fact_overlay`), aligns with application runtime names (`check_rule_disable_action` / `check_rule_literal_replace_action` / `check_rule_add_condition_action` — only `_action` suffix dropped at the SDK boundary), and visibly disjoint from SDK's persistent-write vocabulary (`add` / `set` / `retract`).

**Falsifier outcomes (5/5 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Runtime semantics confirm what-if (no persistence) | All three runtimes (`kernel/application/rule_disable_runtime.py`, `rule_literal_replace_runtime.py`, `rule_add_condition_runtime.py`) take `(request, *, store, registry=None) -> Rule<X>Result`; the only ledger access is `project_view_facts(store.ledger, store.schema_ir)` — read-only projection; no `apply_write_plan`, no `registry.register`, no ledger writes. The result DTOs (`RuleDisableResult` / `RuleLiteralReplaceResult` / `RuleAddConditionResult`) describe the would-be outcome of applying the overlay; they do not represent a committed state change. | PASS — what-if semantics confirmed; method-name choice must match. |
| F2 | SDK vocabulary already separates what-if from persistent-write | SDK what-if methods: `check` (G1), `diagnose` (G1), `why_not` (G4), `check_fact_overlay` (G2), `recheck_proof_frame` (G2). SDK persistent-write methods: `add`, `set`, `retract`, `accept`, `accept_many`, `accept_compiled`, `ingest`. The `check_*` prefix is the established marker for what-if read-only on derivation-shaped capabilities (G1+G2); G4's `why_not` is a noun-form question that doesn't apply here; G2's `recheck_*` is a re-prefix for ProofFrame-specific re-evaluation under overlay. Group A's `check_rule_*` extends the established `check_*` prefix. Group B's `disable_rule` / `add_rule_condition` would mix into the persistent-write vocabulary semantic field — `add` (persistent single-fact write) sits adjacent to `add_rule_condition` (what-if rule-overlay check), creating real ambiguity. | PASS reject Group B — semantic-field collision with `add`/`set`/`retract`. |
| F3 | Application runtime names provide a stable trace | Application names are `check_rule_disable_action` / `check_rule_literal_replace_action` / `check_rule_add_condition_action`. Group A drops only `_action` suffix → SDK names trace 1:1 to runtime names. Group B drops both `check_` and `_action` and reorders tokens → trace requires mental remapping (`disable_rule` ↔ `check_rule_disable_action` is non-obvious). Group A's traceability is a developer-experience asset, especially for SDK consumers reading runtime stack traces. | PASS — Group A traceable. |
| F4 | No SDKStore method-name collision | Existing `SDKStore` has 36 methods including `add`, `set`, `retract`, `accept`, `accept_many`, `accept_compiled`, `check`, `diagnose`, `why_not`, `check_fact_overlay`, `recheck_proof_frame`, etc. Verified no method starts with `disable_`, `replace_`, or `rule_`; no method named `add_rule_condition` / `check_rule_disable` / etc. Group A and Group B both lexically collision-free. **However**, Group B `add_rule_condition` shares the `add_*` prefix family with `add` (persistent write) and could read as a persistent variant. | PASS for Group A; PASS-but-ambiguous for Group B. |
| F5 | Length cost is bounded; SDK consumer ergonomics acceptable | Group A: `check_rule_literal_replace` is the longest at 26 chars (consistent with G2's `check_fact_overlay` at 18 chars and `recheck_proof_frame` at 19 chars). The longest existing SDKStore method is `accept_compiled` at 15 chars; `validate_provenance` at 19; `compile_schema_from_classes` at 27. Group A method names are within the established length envelope. SDK consumers already import via `sdk.check_fact_overlay(...)` and `sdk.recheck_proof_frame(...)`; longer-by-7-chars `sdk.check_rule_literal_replace(...)` is consistent. | PASS — length acceptable. |

**Forward implications:**

- §5.8 (error mapping + path strings) can now lock per-method `$.check_rule_disable.<arg>` / `$.check_rule_literal_replace.<arg>` / `$.check_rule_add_condition.<arg>` paths — finalized method names are required for path string locks.
- §5.9 contract test files keep their §5.6 lock names (`test_sdk_rule_disable.py` / `test_sdk_rule_literal_replace.py` / `test_sdk_rule_add_condition.py`) — they mirror shell-file names rather than SDKStore method names, which is consistent with G2 (`test_sdk_fact_overlay.py` mirrors `shells/fact_overlay.py` even though SDKStore method is `check_fact_overlay`).
- Shell function names locked at §5.6 (`sdk_rule_disable` / `sdk_rule_literal_replace` / `sdk_rule_add_condition`) remain unchanged; SDKStore method delegates via `from .shells.<x> import sdk_<x>; return sdk_<x>(self, ...)` pattern matching G1+G4+G2.
- Post-L SDK ergonomics redesign blueprint (per `feedback_sdk_ergonomics_redesign_target`) may revisit naming under a coherent namespace-or-flat scheme; the `check_*` prefix is preserved as the L-Direction what-if convention until that redesign opens.

### 5.8 Error mapping and validation paths

**Question:** Which errors must map to `SDKStoreError`, and which path strings are locked?

Expected categories:

- target rule input validation;
- support validation;
- overlay validation;
- family-specific action argument validation;
- request construction `ProtocolShapeError`;
- runtime unexpected exceptions;
- application helper `CapabilityHelperError`;
- `RuleCompileError` only if G3 resolves target rule through registry / compilation.

**Conservative default:** all non-SDK exceptions crossing the SDK shell boundary map to `SDKStoreError(...) from exc` with method-specific paths.

**Falsifiers required:**

- Enumerate each runtime/helper exception type for all three families.
- Decide whether shared validators should be added to `kernel.sdk.shells._validation` for `SupportArtifact`, `RuleSpec`, `RuleLiteralPath`, and `RuleAddedAtom`.
- Confirm path naming for each method is stable before tests lock it.

### 5.9 Tests and invariants

**Question:** What test files and invariant coverage does G3 require?

**Conservative default:** one contract test file per method plus one G3 invariant file, unless §5.6 selects a one-module / one-file test layout.

**Decision (2026-05-08):** Lock **three per-method contract test files + one G3 invariant file**, all flat under `src/kernel/tests/`:

- `src/kernel/tests/test_sdk_rule_disable.py` (~13-15 contract tests for `sdk_rule_disable`)
- `src/kernel/tests/test_sdk_rule_literal_replace.py` (~13-15 contract tests for `sdk_rule_literal_replace`)
- `src/kernel/tests/test_sdk_rule_add_condition.py` (~13-15 contract tests for `sdk_rule_add_condition`)
- `src/kernel/tests/test_sdk_g3_invariants.py` (6 invariant classes mirroring G1+G4+G2 6-class structure)

Contract tests cover (per method): happy path with seeded store + real SupportArtifact + real RuleSpec; non-Rule input rejection (raw RuleSpec / Derivation / dict — all rejected per §5.2 lock); non-SupportArtifact rejection; non-EvaluationOverlay rejection (when `overlay` argument is non-None); invalid action arguments per family; ProtocolShapeError from request DTO; unexpected runtime exception (defensive remap pattern); engine + registry passthrough where applicable; result DTO not in `kernel.sdk.__all__`; Sibling discipline runtime patch + static source scan.

G3 invariant file mirrors G2 1:1 with G3 substitutions:

1. `test_sdk_all_unchanged_and_g3_result_types_not_exported` — `__all__` length still 34, result DTOs and SDK function names not exported.
2. `test_g3_methods_are_instance_methods_and_no_scenario_method_shipped` — three `SDKStore` methods callable; reserved scenario names absent.
3. `test_g3_modules_live_in_shells_subpackage` — three shell files exist under `kernel/sdk/shells/`; flat-layout files do not.
4. `test_g3_modules_do_not_import_internal_or_walker_layers` — same forbidden-import set as G1+G4+G2 (capability_helpers `_binding`, `_reject_sdk_origin`, walker, audit, frontier).
5. `test_store_methods_remain_thin_delegate_methods` — each method body is `from .shells.<x> import sdk_<x>; return sdk_<x>(self, ...)`; assertions check call/instantiation patterns (`RuleDisableRequest(`, etc.) so legitimate docstring references don't false-trigger.
6. `test_store_method_docstrings_record_boundary_contracts` — each docstring includes required type names + locked `$.<method>.<arg>` paths from §5.8.

**Falsifier outcomes (3/3 PASS):**

- **F1**: One contract file per method is consistent with G1 (`test_sdk_check.py` + `test_sdk_diagnose.py`), G4 (`test_sdk_why_not.py`), and G2 (`test_sdk_fact_overlay.py` + `test_sdk_proof_frame.py`). Three G3 files match the three §5.6 shells 1:1, making targeted test execution and Sibling static scans straightforward. **PASS — pattern consistent**.
- **F2**: 6-class invariant mirror is the established G1+G4+G2 cadence. Each invariant maps 1:1 to a §5.x lock dimension. The G3 invariant file replaces G3-specific module list constants (`G3_MODULES`) but keeps the structural skeleton. **PASS — mirror valid**.
- **F3**: Tests stay flat under `src/kernel/tests/`; no nested `tests/sdk/` directory. Fixtures (Person Entity, `_seed_person`, `_age_rule`, `_capture_support`, etc.) inline per test file or shared via existing fixture helpers — same approach as G2. **PASS — flat layout preserved**.

**Forward implications:**

- Total post-G3 SDK shell test count target: ~39-45 contract tests across G3's three files + 6 G3 invariants = ~45-51 G3-relevant tests.
- Estimated full kernel suite at G3 published HEAD: ~1620 OK / 1 skipped (extrapolating from G2's 1573 + ~45-50 new G3 tests).
- §5.8 must enumerate all error paths before per-method contract tests can lock specific path assertions.

**Falsifiers required:**

- Mirror G1 / G4 / G2 invariant classes:
  - `kernel.sdk.__all__` unchanged and result DTOs not exported.
  - methods are `SDKStore` instance methods, not free functions.
  - modules live under `kernel/sdk/shells/`.
  - production shell modules avoid internal A helpers, walker, audit, frontier, and sibling shell imports.
  - thin delegate pattern in `store.py`.
  - docstring boundary paths.
- Add Sibling discipline tests that prevent the three rule-overlay shells from calling each other and prevent calls to G1 / G2 / G4 shells.
- Include tests for raw DTO input decisions made in §5.2-§5.4.

## 6. Boundaries and Invariants

| Principle | G3 interpretation |
|---|---|
| `#1` application-first | G3 delegates to existing application helpers / runtimes; it does not invent new semantics. |
| `#3` heterogeneity | Three rule-overlay families are distinct unless a Step 0 falsifier proves a unified SDK surface is better. |
| `#4a` intent-minimal | SDK inputs should be author intent, not already-lowered substrate IR, unless no SDK alternative exists. |
| `#5` layer isolation | `kernel.sdk` may import public application surfaces; application must not import SDK. |
| `#6` no outward compat without signal | No `__all__` expansion, wrappers, namespaces, or README quickstart changes without explicit Step 0 lock. |
| `#11` / `#12` walker-related | Inactive unless a wrapper / evidence view enters scope; default is no B dependency. |
| `#19` testing | Flat `unittest` files, no nested test package, no Hypothesis. |
| `#P0` conflict resolution | If ergonomics and outward-compat conflict, narrow ergonomics first. |
| `#P1` carve-out flow | Any deviation from G1/G4/G2 shell precedents records id / reason / scope / impact / reviewer ack in audit before implementation. |

Forbidden unless §5 explicitly changes scope:

- `kernel.sdk.__all__` expansion for rule-overlay methods or result DTOs.
- README quickstart updates.
- SDK wrappers for rule-overlay results.
- Persistent rule mutation or ledger writes.
- Direct `kernel.sdk` import from application code.
- Private application helper imports such as `kernel.application.capability_helpers._binding`.
- B walker imports.
- Frontier / audit recorder imports.
- Sibling SDK shell calls.
- Raw `RuleSpec` exposure without explicit §5.2 lock.

## 7. Acceptance Criteria

Draft-stage acceptance:

- [x] G3 baseline and shipped predecessor context recorded.
- [x] Round 8 G3 mismatch captured as the core Step 0 driver.
- [x] All G3 Step 0 questions listed without pre-locking answers.
- [x] G1 / G4 / G2 inherited constraints recorded.
- [x] Principle locks and forbidden list recorded.

Scoped-stage acceptance (pending):

- [ ] §5.1-§5.9 falsifiers are source-grounded and locked.
- [ ] §8 implementation plan is filled with phases, audit gates, and expected test files.
- [ ] Status moves from `draft` to `scoped`.

Implementation acceptance is intentionally deferred until scope-freeze.

## 8. Implementation Plan

Deferred until `scoped` status.

Expected implementation shape, subject to §5 locks:

- Phase 0: any scaffolding / shared validator extraction needed by G3.
- Phase 1: first rule-overlay method or module slice.
- Phase 2: remaining rule-overlay methods.
- Phase 3: invariants + docs + cumulative audit.
- Phase 4: close-out / archive / publish.

The exact phase split depends on §5.1 / §5.6: one module vs three modules and one commit vs three family commits.

## 9. Outcome / Deviations

To be filled at close-out.
