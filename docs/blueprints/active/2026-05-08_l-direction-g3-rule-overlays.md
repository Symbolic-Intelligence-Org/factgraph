# L Direction G3 — Rule Overlay SDK Shells

- **Status:** scoped
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

**Decision (2026-05-08):** Lock 1:1 mirror of A signatures (with §5.2's `rule` substitution for `rule_spec`). All three SDK methods accept raw `RuleLiteralPath` / `RuleAddedAtom` per the G2 §5.1+§5.2 cross-cutting precedent (frozen application-canonical + no SDK alternative without inventing surface). `overlay=None` and `note=None` are exposed at SDK boundary, forwarded to A. A's existing `_request_overlay(...)` contract is preserved: `None` or empty `EvaluationOverlay()` accepted; non-empty overlay raises `CapabilityHelperError("non-empty overlay not supported")` which §5.8 maps to `$.<method>.overlay` → `SDKStoreError`. Final signatures:

```python
SDKStore.check_rule_disable(
    rule, support, *,
    branch_index, atom_index,
    overlay=None, note=None,
) -> RuleDisableResult

SDKStore.check_rule_literal_replace(
    rule, support, *,
    branch_index, atom_index,
    literal_path, old_literal, new_literal,
    overlay=None, note=None,
) -> RuleLiteralReplaceResult

SDKStore.check_rule_add_condition(
    rule, support, *,
    branch_index, added_atom,
    overlay=None, note=None,
) -> RuleAddConditionResult
```

**Falsifier outcomes (5/5 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `RuleLiteralPath` and `RuleAddedAtom` are frozen application-canonical DTOs comparable to G2's raw DTO precedent | `RuleLiteralPath` at `kernel/application/protocol/derivation_fact_overlay.py:159-176` is `@dataclass(frozen=True)` with `kind: RuleLiteralPathKind` (literal-typed `"pred_term" / "lhs" / "rhs" / "in_value" / "const_operand"`) + `index: int | None`, with strict `__post_init__` validation enforcing kind/index pairing rules. `RuleAddedAtom` at `:201-209` is `@dataclass(frozen=True)` with single `atom: tuple[Any, ...]` field, validating non-empty tuple + first element is atom-kind string. Both live in `kernel.application.protocol` (same layer as `EvaluationOverlay` / `SupportArtifact`). They satisfy the G2 §5.1+§5.2 cross-cutting precedent: (a) frozen application-canonical, (b) no SDK alternative — wrapping would force a new outward DTO under `#6` without consumer signal. | PASS — raw exposure aligned with G2 precedent. |
| F2 | SDK-friendly alternatives are obvious and source-grounded | No source signal for SDK-side wrappers around `RuleLiteralPath` (the kind+index pairing is application-protocol concept, not SDK ergonomics) or `RuleAddedAtom` (the tuple form is `kernel.core.rules.rule_ir` IR convention, used directly by the runtime). `old_literal: Any` / `new_literal: Any` are by design — literal values may be `int`, `str`, `float`, `bool`, etc. depending on which literal position is being replaced; tightening the type at SDK boundary would be either incorrect (rejecting valid literals) or a no-op (`Any` is already permissive). Inventing SDK-side per-action wrappers (e.g., `class SDKLiteralReplace`, `class SDKAddedAtom`) would expand SDK surface without ergonomic gain. | PASS reject SDK wrappers. |
| F3 | A helper behavior around `overlay=None`, empty overlay, and non-empty overlay rejection | `kernel/application/capability_helpers/rule_overlays.py:_request_overlay(action, *, overlay)` (`:150-163`): if `overlay is None` → returns `EvaluationOverlay(rule_actions=(action,))` (single-action overlay built internally); elif overlay is `EvaluationOverlay` and empty (`not overlay.fact_actions and not overlay.rule_actions`) → returns `EvaluationOverlay(rule_actions=(action,))`; elif overlay is `EvaluationOverlay` non-empty → raises `CapabilityHelperError("non-empty overlay not supported; use overlay=None or EvaluationOverlay()")`; elif overlay is non-`EvaluationOverlay` → raises `CapabilityHelperError("overlay must be EvaluationOverlay or None")`. SDK contract therefore: caller passes `None` or empty `EvaluationOverlay`; A enforces emptiness; SDK remaps non-`EvaluationOverlay` and non-empty `EvaluationOverlay` errors via `CapabilityHelperError` path mapping in §5.8. | PASS — A contract preserved verbatim. |
| F4 | `note=None` remains a SDK convenience parameter (vs. omitted) | A helpers already accept `note: str | None = None` (rule_overlays.py `:33`, `:67`, `:103`). `note` is forwarded into the rule-action DTO and used as audit/observability metadata. Omitting `note` at the SDK boundary would force callers who want to attach notes to drop to advanced-importable layer (against the L Direction spirit of full-coverage SDK). Forwarding `note` is a zero-cost continuation of an already-shipped A surface; it does not add a new outward commitment under `#6`. | PASS — note exposed. |
| F5 | `branch_index` / `atom_index` / `added_atom` / `literal_path` / `old_literal` / `new_literal` action arguments are passed positionally? Or keyword-only? | A helpers use keyword-only after `*` (verified in `rule_overlays.py` builder signatures). SDK mirrors keyword-only to (a) avoid positional-argument drift if A reorders, (b) make call sites self-documenting (`branch_index=0, atom_index=2, ...`), (c) align with G1+G4+G2 SDK methods which all have `*` before any non-required arg (e.g., G2's `check_fact_overlay(derivation, binding, overlay, *, engine, registry)`). | PASS — keyword-only. |

**Forward implications:**

- §5.8 (error mapping) covers the per-method `$.<method>.overlay` path for non-`EvaluationOverlay` and non-empty `EvaluationOverlay` rejection (both via A's `CapabilityHelperError`); `validate_evaluation_overlay` from G2 cannot be reused as-is because it rejects `None`. §5.8 lock will decide between (a) extend `_validation.py` with `validate_optional_evaluation_overlay(value, *, path)` that allows `None`, or (b) inline the type check in each shell, or (c) skip pre-check and let A's `CapabilityHelperError` fire. Conservative default: extend shared validator with optional variant.
- The locked signatures preserve A's positional vs keyword-only convention exactly, so SDK delegate body remains a thin wrapper passing all kwargs through to the A helper.
- `RuleLiteralPath` / `RuleAddedAtom` are NOT exported from `kernel.sdk.__all__` (per §5.5 lock + §5.6 invariants); SDK callers either import them from `kernel.application.protocol` or construct them inline at call sites.

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

**Decision (2026-05-08):** Lock per-method 6-path remap with shared validator extraction:

**Phase 0 hygiene (preceding G3 implementation):**

1. Extend `kernel/sdk/shells/_validation.py` with three new shared validators:
   - `validate_rule(value, *, path)` — rejects non-`Rule` inputs. Mirrors `validate_derivation` from G1 Round 4 Q1 extraction.
   - `validate_support_artifact(value, *, path)` — rejects non-`SupportArtifact` inputs. Promotes the local `_validate_support_artifact` from G2 `proof_frame.py`. **G2 §5.2 deferred trigger fires now** ("until G3/G5 also need them").
   - `validate_optional_evaluation_overlay(value, *, path)` — rejects non-`EvaluationOverlay` non-None inputs **AND** rejects non-empty `EvaluationOverlay`. Sibling to G2's `validate_evaluation_overlay` but allows `None` (which is required by all three G3 methods because A's `_request_overlay` constructs the rule-action overlay internally).
2. Update `kernel/sdk/shells/proof_frame.py` to import and use shared `validate_support_artifact` instead of the local helper. Remove the local `_validate_support_artifact` function. This is a behavior-preserving refactor — the validator semantics are identical; only the import path changes.

**Per-method 6-path remap (each of the three G3 methods):**

| Source | Exception | Where | SDK Path | Notes |
|---|---|---|---|---|
| `validate_rule(rule, path="$.<method>.rule")` | `SDKStoreError` (direct raise) | SDK shell pre-validation | `$.<method>.rule` | non-`Rule` SDK input |
| `sdk._compile_rule_input(rule)` + `RuleSpec(rule_id=..., version=..., ...)` construction | `RuleCompileError` from compile chain or `RuleSpec.__post_init__` | SDK shell during lowering | `$.<method>.rule` | invalid SDK Rule shape after lowering (rule_id/version/select_vars/where shape errors) |
| `validate_support_artifact(support, path="$.<method>.support")` | `SDKStoreError` (direct raise) | SDK shell pre-validation | `$.<method>.support` | non-`SupportArtifact` SDK input |
| `validate_optional_evaluation_overlay(overlay, path="$.<method>.overlay")` | `SDKStoreError` (direct raise) | SDK shell pre-validation | `$.<method>.overlay` | non-`EvaluationOverlay` non-None OR non-empty `EvaluationOverlay` (A's `_request_overlay` non-empty rejection becomes defensive / unreachable from SDK after this) |
| `sdk._resolve_runtime_registry(rule, explicit_registry=registry)` | `RuleCompileError` from `_register_rule_dependencies` | SDK shell try/except | `$.<method>.dependencies` | duplicate rule registration / RuleRef cycle / similar |
| `build_rule_<x>_request(rule_spec, support, *, ...)` (A helper) | `CapabilityHelperError` (e.g., `_reject_sdk_origin` if SDK object slips through) OR `ProtocolShapeError` from action / request DTO `__post_init__` | SDK shell try/except around helper call | `$.<method>.request` | invalid action argument shape (branch_index/atom_index out-of-range, literal_path kind/index pairing wrong, added_atom shape wrong, etc.); also any `RuleSpec` / `SupportArtifact` shape errors that slipped past SDK pre-validation (defensive) |
| `check_rule_<x>_action(request, store, registry)` (A runtime) | unexpected `Exception` | SDK shell try/except defensive | `$.<method>` (base) | runtime ordinarily catches its own `RuleCompileError` / `ValueError` / `KeyError` / `TypeError` / `WhereValidationError` and returns a `Rule<X>Result` (no raise); base path covers any forward-compat unexpected raise |

All non-SDK exceptions remap to `SDKStoreError(message, path=...) from exc` with `__cause__` chain preserved.

**Sibling discipline at 8-shell scope:**

After G3 lands, `kernel/sdk/shells/` contains 8 shell modules:

```
shells/check.py             (G1)
shells/diagnose.py          (G1)
shells/why_not.py           (G4)
shells/fact_overlay.py      (G2)
shells/proof_frame.py       (G2)
shells/rule_disable.py      (G3 NEW)
shells/rule_literal_replace.py (G3 NEW)
shells/rule_add_condition.py   (G3 NEW)
```

Each G3 shell's Sibling discipline test (runtime patch + static source scan) must verify NO call/import to ANY of the other 7 shells. The G3 invariant `test_g3_modules_do_not_import_internal_or_walker_layers` extends `FORBIDDEN_PRODUCTION_IMPORT_TEXT` with sibling-shell import patterns where applicable; static scans inside the per-method test files iterate the 7 sibling SDK function names (`sdk_check`, `sdk_diagnose`, `sdk_why_not`, `sdk_fact_overlay_check`, `sdk_proof_frame_recheck`, plus the two other G3 shells per-test).

**Falsifier outcomes (5/5 PASS):**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Runtime `RuleCompileError` does not leak past A | `kernel/application/rule_disable_runtime.py:129`, `rule_literal_replace_runtime.py:144`, `rule_add_condition_runtime.py:133` all wrap `(KeyError, RuleCompileError, TypeError, ValueError, WhereValidationError)` and convert to `Rule<X>Result(status="invalid_request", errors=...)`. SDK never sees `RuleCompileError` from runtime; the only `RuleCompileError` source from SDK perspective is the lowering / registry path before runtime. | PASS — `$.<method>.rule` and `$.<method>.dependencies` paths are the only `RuleCompileError` boundaries. |
| F2 | Shared validator extraction is sound for ProofFrame | `kernel/sdk/shells/proof_frame.py` `_validate_support_artifact` is byte-identical to the proposed shared `validate_support_artifact` semantics: `if not isinstance(value, SupportArtifact): raise SDKStoreError("support_artifact must be SupportArtifact", path=...)`. The only difference is the path constant is now passed by caller. ProofFrame Recheck call site updates to `validate_support_artifact(support, path="$.recheck_proof_frame.support_artifact")` — single line change. No behavior drift; existing G2 tests pass without modification. | PASS — extraction is behavior-preserving. |
| F3 | `validate_optional_evaluation_overlay` cleanly distinguishes the overlay path from the request path | The function pre-validates: (a) `None` → pass; (b) non-`EvaluationOverlay` → SDKStoreError at `$.<method>.overlay`; (c) empty `EvaluationOverlay` → pass; (d) non-empty `EvaluationOverlay` → SDKStoreError at `$.<method>.overlay`. After this pre-validation, A's `_request_overlay(...)` only sees `None` or empty `EvaluationOverlay` — its non-empty `CapabilityHelperError` path becomes defensive / unreachable from SDK. Any remaining `CapabilityHelperError` from `build_rule_<x>_request(...)` (e.g., `_reject_sdk_origin` if user passes an SDK DSL object as `branch_index` by mistake — extremely unlikely but defensive) maps to `$.<method>.request`. The two paths (`overlay` vs `request`) are now cleanly separated. | PASS — overlay/request path separation clean. |
| F4 | `RuleCompileError` source separation between `$.<method>.rule` and `$.<method>.dependencies` | Two distinct call sites: (1) `sdk._compile_rule_input(rule)` + `RuleSpec(...)` construction during SDK Rule lowering — `RuleCompileError` here means the user's SDK `Rule` itself has an invalid shape after `compile_authoring_rule_v1` (rule_id/version/select_vars/where validation in `RuleSpec.__post_init__` at `kernel/core/rules/rule_ir.py:35-46`); (2) `sdk._resolve_runtime_registry(...)` for dependency rules — `RuleCompileError` here means duplicate dependency registration, RuleRef cycle, or unknown RuleRef from `kernel/core/rules/rule_ir.py:55-78` and `:175`. Distinguishing these two paths matches G1 B.1 fix pattern (`$.check.dependencies` for registry, `$.check.derivation` for compile). For G3, the analogous mapping is `$.<method>.rule` ↔ `$.<method>.dependencies`. | PASS — same B.1 pattern as G1, semantically separated. |
| F5 | Sibling discipline at 8-shell scope is testable | G2 invariant `test_g2_modules_do_not_import_internal_or_walker_layers` already iterates per-module via `G2_MODULES` constant. G3 invariant follows the same pattern with `G3_MODULES = ("kernel.sdk.shells.rule_disable", "kernel.sdk.shells.rule_literal_replace", "kernel.sdk.shells.rule_add_condition")` and identical `FORBIDDEN_PRODUCTION_IMPORT_TEXT` set. Per-method runtime patches the 7 sibling shells (G1's `sdk_check` / `sdk_diagnose`, G4's `sdk_why_not`, G2's `sdk_fact_overlay_check` / `sdk_proof_frame_recheck`, plus the two other G3 shells), asserts none invoked. Static source scans use the same `assertNotIn("from kernel.sdk.shells.<x>", source)` and `assertNotIn("sdk_<x>(", source)` patterns established by G2. | PASS — testable at scale. |

**Forward implications:**

- Phase 0 hygiene commit (preceding G3 implementation Phases 1/2/3) lands the three new validators + `proof_frame.py` migration in a single atomic refactor. Behavior-preserving; full kernel suite must pass without test modifications beyond the G2 ProofFrame `_validate_support_artifact` import path update.
- §5.9 contract test files use the locked path strings (`$.check_rule_disable.{rule,support,overlay,dependencies,request,}` etc.) for assertion exact-match.
- G3 invariant `test_store_method_docstrings_record_boundary_contracts` asserts each `SDKStore.check_rule_<x>` docstring includes all six locked paths.
- G2 ProofFrame's existing `validate_optional_evaluation_overlay` is NOT introduced for ProofFrame — it stays on `validate_evaluation_overlay` (rejects `None`) because §5.2 ProofFrame contract requires `EvaluationOverlay` at the SDK boundary (no None default). Only G3 needs the optional-allowing variant.
- Implementation phase plan: Phase 0 = validator extraction + proof_frame migration; Phase 1 = `sdk_rule_disable` impl + tests; Phase 2 = `sdk_rule_literal_replace` impl + tests; Phase 3 = `sdk_rule_add_condition` impl + tests; Phase 4 = G3 invariants + docs + cumulative audit; Phase 5 = close-out + archive + publish. (5-impl-phase plan reflects 3-method scope; G2 was 4-phase for 2-method scope.)

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

Scoped-stage acceptance:

- [x] §5.1 locked — three explicit `SDKStore` instance methods (commit `e648384`).
- [x] §5.2 locked — SDK `Rule` object as target rule input (commit `8b36110`).
- [x] §5.3 locked — raw `SupportArtifact` (batch commit `ce4ab49`).
- [x] §5.4 locked — action arg shapes mirror A; raw `RuleLiteralPath` / `RuleAddedAtom`; `overlay=None` or empty only; `note=None` exposed (commit `476e311`).
- [x] §5.5 locked — documented passthrough of raw result DTOs (batch commit `ce4ab49`).
- [x] §5.6 locked — three sibling shell modules under `kernel/sdk/shells/` (batch commit `ce4ab49`, overrides conservative default).
- [x] §5.7 locked — `check_rule_disable` / `check_rule_literal_replace` / `check_rule_add_condition` (Group A; commit `660e61d`).
- [x] §5.8 locked — per-method 6-path remap + Phase 0 shared validator extraction (commit `cd3a5f0`).
- [x] §5.9 locked — three per-method test files + one G3 invariant file (batch commit `ce4ab49`).
- [x] §8 implementation plan filled with six phases (Phase 0 shared validators, Phase 1-3 three rule-overlay methods, Phase 4 invariants/docs/cumulative audit, Phase 5 close-out/archive/publish).
- [x] Status moves from `draft` to `scoped`.

Implementation-stage acceptance (per phase, gated by phase-end audit):

- [x] Phase 0 lands `validate_rule` / `validate_support_artifact` / `validate_optional_evaluation_overlay` in `kernel/sdk/shells/_validation.py`; G2 `proof_frame.py` migrates to shared `validate_support_artifact`; full kernel suite passes without test-file modifications beyond ProofFrame import-path update. (commit `5437cd6`; full kernel 1593 OK / 1 skipped; +19 new validator unit tests)
- [x] Phase 1 lands `kernel/sdk/shells/rule_disable.py` (real `sdk_rule_disable` implementation), `SDKStore.check_rule_disable(...)` thin delegate in `store.py`, `test_sdk_rule_disable.py` with full §5.4 + §5.8 contract coverage. (full kernel 1609 OK / 1 skipped; +16 G3 contract tests; `#P1` retrofit on pre-G3 `test_no_sdk_rule_disable_surface` boundary test)
- [ ] Phase 2 lands `kernel/sdk/shells/rule_literal_replace.py`, `SDKStore.check_rule_literal_replace(...)` thin delegate, `test_sdk_rule_literal_replace.py`.
- [ ] Phase 3 lands `kernel/sdk/shells/rule_add_condition.py`, `SDKStore.check_rule_add_condition(...)` thin delegate, `test_sdk_rule_add_condition.py`.
- [ ] Phase 4 lands `test_sdk_g3_invariants.py` (6-class mirror), updates SDK API docs (`04_api_surface.md` + `.en.md`) and application overview docs (`01_overview.md` + `_en.md`); cumulative G3 strict audit gates the close-out.
- [ ] Phase 5 fills §10 Outcome / Deviations, marks status `implemented`, archives blueprint + audit log under `docs/blueprints/archive/`, updates archive inventory, and publishes `v0.1-l-g3-rule-overlays-2026-05-08` (G3-only) + `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-2026-05-08` (Path B combined snapshot per the post-G2 strategy) to origin pending user authorization.

## 8. Implementation Plan

### Phase 0 — Shared validator extraction (no behavior change)

Scope:

- Add `validate_rule(value, *, path)` to `kernel/sdk/shells/_validation.py` (mirror `validate_derivation` shape).
- Add `validate_support_artifact(value, *, path)` to `kernel/sdk/shells/_validation.py` (promotes G2 ProofFrame's local `_validate_support_artifact`).
- Add `validate_optional_evaluation_overlay(value, *, path)` to `kernel/sdk/shells/_validation.py` (None-allowed sibling of G2's `validate_evaluation_overlay`; rejects non-`EvaluationOverlay` non-None AND non-empty `EvaluationOverlay`).
- Update `kernel/sdk/shells/proof_frame.py` to import shared `validate_support_artifact` and remove the local helper (G2 §5.2 deferred trigger fires now).
- Update `kernel/sdk/shells/_validation.py` `__all__` to export the three new validators.

Audit gate:

- All G2 ProofFrame contract tests pass without source modifications.
- G2 G2 invariants test_g2_modules_live_in_shells_subpackage continues to pass (shells/_validation.py still in shells/).
- Full kernel suite: 1573 OK / 1 skipped (no count change since validators are pure additions + a behavior-preserving migration).
- ruff clean across `_validation.py` and `proof_frame.py`.

### Phase 1 — `sdk_rule_disable` implementation

Scope:

- New `src/kernel/sdk/shells/rule_disable.py` implementing `sdk_rule_disable(sdk, rule, support, *, branch_index, atom_index, overlay=None, note=None) -> RuleDisableResult` per locked §5.1 / §5.2 / §5.4 / §5.7 signatures.
- Implementation calls (in order): `validate_rule` → `validate_support_artifact` → `validate_optional_evaluation_overlay` → `sdk._compile_rule_input(rule)` + `RuleSpec(...)` lowering (B.2 ValueError remap + B.1 RuleCompileError remap) → `sdk._resolve_runtime_registry(...)` (RuleCompileError remap) → `build_rule_disable_request(rule_spec, support, *, branch_index, atom_index, overlay, note)` (CapabilityHelperError + ProtocolShapeError remap) → `check_rule_disable_action(request, store, registry)` (defensive base path remap).
- Add `SDKStore.check_rule_disable(...)` thin delegate in `store.py` between `recheck_proof_frame` and `ref` methods. Extend TYPE_CHECKING to import `RuleDisableResult`.
- New `src/kernel/tests/test_sdk_rule_disable.py` with ~14 contract tests covering: happy path with seeded store + real Rule + real SupportArtifact; non-Rule rejection (raw RuleSpec / Derivation / dict); non-SupportArtifact rejection; non-EvaluationOverlay overlay rejection; non-empty overlay rejection at `$.check_rule_disable.overlay`; ProtocolShapeError from action / request DTO; engine_ext-style RuleCompileError remap from `_compile_rule_input`; RuleCompileError dependency from `_resolve_runtime_registry`; CapabilityHelperError from helper; runtime exception base path; result DTO not in `__all__`; Sibling discipline runtime patch (7 sibling shells) + static source scan.

Audit gate: strict per-phase audit on locked §5.x / `#5` / `#6` invariants; phase-end test count and ruff verification.

### Phase 2 — `sdk_rule_literal_replace` implementation

Scope: same shape as Phase 1 with rule-literal-replace specifics (`literal_path`, `old_literal`, `new_literal` action args). New `kernel/sdk/shells/rule_literal_replace.py` + `SDKStore.check_rule_literal_replace(...)` + `test_sdk_rule_literal_replace.py` (~15 contract tests; one extra for `literal_path` shape validation propagating through `RuleLiteralPath.__post_init__` to `$.check_rule_literal_replace.request`).

Audit gate: strict per-phase audit; G3 SDK shell file count after this phase = 2; SDKStore method count = 38.

### Phase 3 — `sdk_rule_add_condition` implementation

Scope: same shape as Phase 1 with rule-add-condition specifics (`added_atom` action arg). New `kernel/sdk/shells/rule_add_condition.py` + `SDKStore.check_rule_add_condition(...)` + `test_sdk_rule_add_condition.py` (~14 contract tests; one extra for `added_atom: RuleAddedAtom` shape validation propagating through `RuleAddedAtom.__post_init__` to `$.check_rule_add_condition.request`).

Audit gate: strict per-phase audit; G3 SDK shell file count after this phase = 3; SDKStore method count = 39.

### Phase 4 — Invariants + docs + cumulative audit

Scope:

- New `src/kernel/tests/test_sdk_g3_invariants.py` with 6 invariant classes mirroring G1 + G4 + G2 1:1: (1) `test_sdk_all_unchanged_and_g3_result_types_not_exported` — `__all__` length still 34, G3 result DTOs and SDK function names not exported; (2) `test_g3_methods_are_instance_methods_and_no_scenario_method_shipped` — three SDKStore methods callable, no scenario name; (3) `test_g3_modules_live_in_shells_subpackage` — three shell files at `kernel/sdk/shells/` flat-layout files do not; (4) `test_g3_modules_do_not_import_internal_or_walker_layers` — same `FORBIDDEN_PRODUCTION_IMPORT_TEXT` set as G1+G4+G2; (5) `test_store_methods_remain_thin_delegate_methods` — assertion-pattern style matching call/instantiation patterns (no false-trigger from docstring references); (6) `test_store_method_docstrings_record_boundary_contracts` — each docstring includes required type names + all six locked `$.<method>.<arg>` paths.
- Update SDK API docs `kernel/sdk/docs/04_api_surface.md` + `.en.md` with G3 method list + per-method shape/error-path descriptions; preamble paragraph notes G3 shells under `kernel/sdk/shells/` and the §5.1+§5.2 cross-cutting precedent extension.
- Update application overview `kernel/application/docs/01_overview.md` + `_en.md` test inventory and G3 SDK shell paragraph.
- Cumulative G3 strict audit gate (5 dimensions: §5.x locks honored / §6 invariants verified / shells/ + retrofit holding / `kernel.sdk.__all__` length still 34 / G1+G4+G2 published snapshot branches untouched).

Audit gate: cumulative G3 strict audit before close-out; all findings either fixed or recorded as explicit deferred minors.

### Phase 5 — Close-out / archive / publish

Scope:

- Fill §10 Outcome / Deviations.
- Mark status `implemented`.
- Archive blueprint + audit log under `docs/blueprints/archive/`.
- Update `docs/blueprints/archive/README.md` with G3 row.
- Publish `v0.1-l-g3-rule-overlays-2026-05-08` (G3-only) + `v0.1-public-surface-helpers-walker-l-g1-l-g4-l-g2-l-g3-2026-05-08` (Path B combined snapshot per post-G2 strategy) to origin pending user authorization.
- Update memory: create `project_g3_published.md`; update `MEMORY.md` index.

Sacred branches `master` and `v0.1-oss-prep` remain untouched throughout. G1 + G4 + G2 published snapshot branches NOT modified by Phase 0 hygiene (extraction only adds new validator names; G2 ProofFrame's import-path update is on G3 topic forward).

## 9. Outcome / Deviations

To be filled at close-out.
