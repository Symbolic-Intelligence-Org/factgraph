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

**Falsifiers required:**

- Verify whether SDK `Rule` can lower to the exact `RuleSpec` required by application runtimes without re-registering or mutating state.
- Verify whether `(rule_id, version)` lookup through `SDKStore` is available and layer-correct.
- Verify whether `SupportArtifact` reliably identifies the single target rule for all three overlays.
- Verify whether accepting raw `RuleSpec` can be justified by G2's raw DTO precedent, or whether `RuleSpec` is different because it is substrate rule IR rather than frozen application protocol intent/evidence.

### 5.3 Support input shape

**Question:** Does each rule-overlay SDK method accept raw `SupportArtifact`, a prior `CheckResult`, or no support argument?

**Conservative default:** raw `SupportArtifact`, by G2 §5.2 precedent and Sibling discipline.

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

**Falsifiers required:**

- Verify result DTOs are frozen application protocol objects with no mutable SDK state.
- Verify they are not exported from `kernel.sdk.__all__`.
- Verify no wrapper signal exists in references or tests.

### 5.6 Module and file layout

**Question:** How many G3 shell modules should exist under `kernel/sdk/shells/`?

Options:

- one `rule_overlays.py` module containing all three functions;
- three sibling modules (`rule_disable.py`, `rule_literal_replace.py`, `rule_add_condition.py`);
- a nested `shells/rule/` package.

**Conservative default:** one `shells/rule_overlays.py` module if §5.1 selects three `SDKStore` methods, because A grouped the three builders in one helper module while preserving separate functions.

**Falsifiers required:**

- Verify whether one module makes sibling static scans harder or easier.
- Verify whether three modules overfit implementation to runtime filenames and add noise.
- Verify whether a nested package would be premature after G2 just activated `shells/`.

### 5.7 SDKStore method names

**Question:** What are the SDK method names?

Candidate names:

- `disable_rule(...)`, `replace_rule_literal(...)`, `add_rule_condition(...)`;
- `check_rule_disable(...)`, `check_rule_literal_replace(...)`, `check_rule_add_condition(...)`;
- `rule_disable(...)`, `rule_literal_replace(...)`, `rule_add_condition(...)`;
- namespace-style names if §5.1 chooses a namespace.

**Conservative default:** verb-first names that make the what-if check nature explicit without copying application runtime names wholesale.

**Falsifiers required:**

- Compare existing SDKStore method vocabulary (`check`, `diagnose`, `why_not`, `check_fact_overlay`, `recheck_proof_frame`) against candidate names.
- Decide whether "check" prefix is necessary to communicate no mutation occurs.
- Avoid method names implying persistent rule mutation.

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
