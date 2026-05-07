# 41 — Application Builders Design Sketch (Direction A)

> See [README.md](README.md) for context. Cross-references: [10_implicit-gaps.md Gap 3](10_implicit-gaps.md), [20_candidates.md Candidate A](20_candidates.md), [30_recommendation.md "Direction A — Input shape lock" + Principles](30_recommendation.md), [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) (parallel sketch for B).

---

## Status framing (READ FIRST)

This document is **not** an implementation specification.

This document is the **scoping artifact for Direction A**: extending the Batch 2 ergonomic-helpers pattern (already shipped 2026-05-04 in `kernel.application/capability_helpers.py`) to cover the remaining capability areas surfaced as [Gap 3](10_implicit-gaps.md). A is **Tier 2 application-layer ergonomic foundation**; not Tier 1 SDK product surface (per [Direction A — Input shape lock](30_recommendation.md)).

What this sketch does:

1. Locates the 3 already-shipped Batch 2 helpers as the prior-art anchor (§1)
2. Maps the 8-helper coverage target: 3 shipped + 5 new families (§2)
3. Provides per-family scope, signatures, convenience adapters, and failure modes (§3)
4. Locks invariants per principles `#1`, `#5`, `#6`, `#9`, plus Batch 2 §6 helper-layer constraints (§4)
5. Previews consumer migration (formal migration path is Gap δ; this section is preview only) (§5)
6. Sketches contract test themes for A builders (§6)
7. Lists decisions deferred to A blueprint Step 0 (§7)
8. Lists what this sketch does NOT cover (§8)

The actual implementation blueprint (`docs/blueprints/active/2026-05-08_application-ergonomic-helpers-extension.md` — not yet drafted) is what owns implementation decisions.

---

## 1. Prior art alignment — Batch 2 helpers

[src/kernel/application/capability_helpers.py](../../../../src/kernel/application/capability_helpers.py) shipped 2026-05-04 contains the existing precedent:

```python
build_fact_value_override(
    store, index, *, e_ref, field, new_value, note=None,
) -> FactValueOverride

build_why_not_candidate_universe(plan, candidates) -> tuple[BindingItems, ...]

build_frontier_view_facts(store) -> dict[str, list[tuple[Any, ...]]]
```

**Conventions to align with:**

- **Module location:** `kernel.application.capability_helpers` (single module today; possibly split per family in §7 decision)
- **Naming:** `build_<noun>_<thing>(...) -> <protocol DTO>` — verb-first prefix, returns canonical application protocol DTO
- **Inputs:** application canonical types only (`FieldPath`, `e_ref: str`, `CompiledDerivationPlan`, `Store`, etc.); never SDK-exclusive objects (per [Gap β resolution](30_recommendation.md))
- **Errors:** typed `CapabilityHelperError(ValueError)` for ergonomic mistakes (missing active fact, mismatched entity type, unsupported field arity, incomplete candidate row); raised early before DTO construction
- **Layer isolation invariants enforced** (per Batch 2 §6, adopted verbatim by A):
  - Helpers do **not** import `kernel.sdk` (per `#5`)
  - Helpers do **not** call sibling runtime functions (`build_fact_value_override` does NOT call `check_fact_overlay_binding`)
  - Helpers do **not** import `kernel.core.rules.frontier` (drift gate)
  - Helpers do **not** write the ledger and do **not** mutate the store
- **Tests:** flat under `src/kernel/tests/test_application_capability_helpers.py`; fixture in same file or `_helpers_fixtures.py` per `#19` flat-fixture convention
- **Module docs:** `kernel.application.docs.01_overview.md` mentions the module + new helpers as advanced importable additions (not advertised as SDK API)

**The 5 new families inherit ALL of these conventions verbatim. No new module pattern. No outward compat commitment (per `#6`).**

---

## 2. Scope — 8-helper coverage target

3 shipped (Batch 2) + 5 new families = 8 capability areas. No new builder for Batch 7 (`AuditQuery.diff_proof_frames(...)` is already a method, no builder needed).

| Family | Status | Builder(s) | Application canonical input | Output |
|---|---|---|---|---|
| Q3 Fact Overlay | shipped | `build_fact_value_override(...)` | `FieldPath` + `e_ref: str` + `new_value` | `FactValueOverride` |
| Q4 Why-not | shipped | `build_why_not_candidate_universe(...)` | `CompiledDerivationPlan` + candidates seq | `tuple[BindingItems, ...]` |
| Q5 Frontier | shipped | `build_frontier_view_facts(...)` | `Store` | `dict[str, list[tuple[Any, ...]]]` |
| **Q1 Check** | new | `build_check_request(...)` | `CompiledDerivationPlan` + binding | `CheckRequest` |
| **Q2 Diagnose** | new | `build_diagnose_request(...)` | `CompiledDerivationPlan` + binding | `DiagnoseRequest` |
| **Batch 4 ProofFrame Recheck** | new | `build_proof_frame_recheck_request(...)` | `SupportArtifact` + `EvaluationOverlay` | `ProofFrameRecheckRequest` |
| **Batch 5 Rule overlay family** | new | `build_rule_disable_request(...)` / `build_rule_literal_replace_request(...)` / `build_rule_add_condition_request(...)` | `RuleSpec` + `SupportArtifact` + branch / atom indices | `RuleDisableRequest` / `RuleLiteralReplaceRequest` / `RuleAddConditionRequest` |
| **Batch 6 Round event payload** | new | `build_round_event_payload(...)` | `kind` literal + capability request + result pair | event payload `dict[str, Any]` (already in `audit/round_events.jsonl` row shape) |

**Total new functions: 7** (Q1 + Q2 + Batch 4 + Batch 5 family with 3 sub-builders + Batch 6 = 5 family signatures, 7 actual functions).

Each new builder follows §1 conventions verbatim. Each new builder accepts only application canonical types and application-internal convenience adapters; never SDK-exclusive DSL / facade / store / batch / editor / snapshot objects (per [Direction A — Input shape lock](30_recommendation.md)).

---

## 3. Per-family design sketch

### 3.1 Check + Diagnose

**Functions:**

```python
build_check_request(
    plan: CompiledDerivationPlan,
    binding: BindingItems | Mapping[str, Any],
    *,
    engine: str = "native",
) -> CheckRequest

build_diagnose_request(
    plan: CompiledDerivationPlan,
    binding: BindingItems | Mapping[str, Any],
    *,
    engine: str = "native",
) -> DiagnoseRequest
```

**Convenience adapters (application-internal):**

- `binding: Mapping[str, Any]` accepted; normalized to canonical sorted `BindingItems` tuple-of-tuples internally
- Plan is required and pre-compiled; no `rule_id` lookup convenience (rule resolution is registry's concern, not A's)

**Failure modes (raise `CapabilityHelperError` early):**

- `binding` keys do not match `plan.heads[0].head_var_names` (incomplete or extra)
- `engine` not in supported set (e.g., not `"native"`)
- Other type-level mismatches detected statically

**Rationale for separate Check + Diagnose builders:**

Both take same input shape, but downstream `check_derivation_binding(...)` vs `diagnose_derivation_binding(...)` are distinct application capabilities with distinct semantics (Check = pass/fail; Diagnose = locate failed atom). Separate builders match `#3` heterogeneity and avoid false unification — same lesson as Batch 8 §5.4 verdict #3.

### 3.2 ProofFrame Recheck

**Function:**

```python
build_proof_frame_recheck_request(
    support: SupportArtifact,
    overlay: EvaluationOverlay | None = None,
) -> ProofFrameRecheckRequest
```

**Convenience adapters:**

- `overlay` defaults to empty `EvaluationOverlay()` (baseline recheck — no overlay applied)

**Failure modes:**

- `support` is empty or has malformed `pred_witnesses` / `non_fact_steps`
- `overlay.fact_actions` references `asrt_id` / `pred_id` / `e_ref` not consistent with `support`
- `overlay.rule_actions` references rule not used by `support`

**Composition note:** `support: SupportArtifact` is typically obtained from a prior `check_derivation_binding(...)` call's `evidence_envelope.engine_payload`. The builder does **not** perform a Check; it only constructs the recheck request. Multi-capability composition is the caller's responsibility (or future Direction L's, in scenario API).

### 3.3 Rule overlay builders (Batch 5 family)

**Functions:**

```python
build_rule_disable_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    atom_index: int,
    overlay: EvaluationOverlay | None = None,
) -> RuleDisableRequest

build_rule_literal_replace_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    atom_index: int,
    literal_path: RuleLiteralPath,
    old_literal: Any,
    new_literal: Any,
    overlay: EvaluationOverlay | None = None,
) -> RuleLiteralReplaceRequest

build_rule_add_condition_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    added_atom: RuleAddedAtom,
    overlay: EvaluationOverlay | None = None,
) -> RuleAddConditionRequest
```

**Convenience adapters:**

- `overlay` defaults to empty `EvaluationOverlay()` for all three sub-builders
- All three accept the same `rule_spec` + `support` + `overlay` triple plus family-specific spec arguments

**Failure modes:**

- `branch_index` / `atom_index` out of range for `rule_spec.where` body
- For `_literal_replace`: `literal_path` does not match an actual literal in target atom; or `old_literal` does not equal current literal at that position
- For `_add_condition`: `added_atom` is malformed IR — specifically, introduces a new variable binder (Batch 5c forbids; filter atoms only per §1.1 Batch 5c blueprint)

**Rationale for keeping three sub-builders separate (not unifying into `build_rule_overlay_request(kind=...)`):**

Per `#3` heterogeneity: each rule overlay action has distinct spec shape (`atom_index` only vs. `literal_path + old + new` vs. `added_atom`). Unifying would require a discriminated union type that adds caller complexity without ergonomic gain. Three sub-builders mirror the three runtime functions (`check_rule_disable_action` / `check_rule_literal_replace_action` / `check_rule_add_condition_action`) 1-to-1.

This is also consistent with [Lane 3 SDK conventions audit](README.md) finding that SDK shells for rule overlays should NOT collapse into one polymorphic method — same heterogeneity reasoning applies one tier down at A.

### 3.4 Round event payload

**Function:**

```python
build_round_event_payload(
    kind: Literal[
        "check_result",
        "diagnose_result",
        "fact_overlay_result",
        "why_not_result",
        "proof_frame_result",
    ],
    request: Any,   # capability request DTO matching kind
    result: Any,    # capability result DTO matching kind
) -> dict[str, Any]   # event payload, in audit/round_events.jsonl row shape
```

**Convenience adapters:**

- `kind` is a string literal selecting which projection function to call internally; builder dispatches to `kernel.audit.round_events.project_<kind>_event_payload(...)` (these projection functions already exist)

**Failure modes:**

- `kind` not in supported set
- `request` / `result` types do not match `kind`'s expected pair (e.g., `kind="check_result"` but `request` is `DiagnoseRequest`)

**Rationale:**

Currently caller imports 5 separate projection functions (`project_check_event_payload(...)` / `project_diagnose_event_payload(...)` / etc.) and remembers which to call per event kind. Builder consolidates dispatch: caller specifies `kind` once and builder picks the right projection. Reduces import surface from 5 names to 1, with explicit `kind` literal type.

---

## 4. Cross-cutting invariants

Per principles in [30_recommendation.md](30_recommendation.md):

- **`#1` Application-first runtime authority** — A's builders construct application protocol DTOs; do not own runtime substrate; runtime call still goes through `kernel.application.<capability>_runtime` functions (or `kernel.audit.round_events` projections for Batch 6)
- **`#4a` Application input is intent-minimal** — A's intent normalization (e.g., `Mapping[str, Any]` binding → canonical `BindingItems` sorted tuple-of-tuples) is application-internal. SDK-level intent normalization (SDK Rule → `CompiledDerivationPlan`) belongs to L per [Direction A — Input shape lock](30_recommendation.md) bridging clause; A does not perform that lowering
- **`#5` Layer isolation invariants** — A's builders never import `kernel.sdk`; never call sibling runtime functions (per Batch 2 §6); never import `kernel.core.rules.frontier`; A is `kernel.application` self-contained
- **`#6` No outward compat without user signal** — A's builders are advanced importable; not added to `kernel.sdk.__all__`; not promoted as outward-stable contracts; can evolve in v0.x without compat commitment
- **`#9` Lazy traversal (where applicable)** — N/A for builders themselves (they construct DTOs synchronously); applies only to walker views (B's responsibility)
- **Batch 2 §6 helper-layer constraints adopted verbatim** — see §1 above
- **`#19` test convention** — common contract tests + behavior-specific tests; flat unittest under `src/kernel/tests/test_application_capability_helpers.py`; no Hypothesis v1; fixtures flat in `_helpers_fixtures.py` if extracted
- **`#P0` conflict resolution** — if A blueprint Step 0 surfaces a conflict between principles in this sketch, apply `#P0` boundary-first heuristic (Authority > Layer isolation > Read-only > Ergonomic walker surface > No new outward commitment); known conflicts must be added to bundle's documented conflict list before patching
- **`#P1` revision flow** — deviations from this sketch's design must follow `#P1` carve-out (principle id + reason + scope + impact + reviewer ack); single-blueprint context-specific carve-outs may stay inside A's blueprint; systemic deviations (same principle violated across multiple A builders) trigger bundle revision per `#P1` item 5

---

## 5. Consumer migration preview

Formal migration path is [Gap δ](README.md) (deferred to a future round). This section is preview only.

After A lands, the canonical demo `examples/round_story_full_demo.py` `_phase_check(...)` would change as:

```python
# Before A:
request = CheckRequest(
    plan=plan,
    binding=tuple(sorted([("$p", e_ref), ("$age", 25), ("$region", "us")])),
    engine="native",
)
result = check_derivation_binding(request, store=store)

# After A:
request = build_check_request(
    plan=plan,
    binding={"$p": e_ref, "$age": 25, "$region": "us"},
)
result = check_derivation_binding(request, store=store)
```

Lines saved per capability call: ~3-5 lines (CheckRequest construction collapses; binding normalization handled internally). Across the full round-story demo: estimate ~30-50 lines simplified, ~5-8 imports removed.

The 4 chaptered notebooks (`examples/01_*.ipynb` through `04_*.ipynb`) see proportionally similar simplification. Demo correctness behavior is unchanged; assertions remain the same.

---

## 6. Contract test sketch

Per `#19` (every helper family needs common contract tests + behavior-specific tests). This section sketches **what** the contract tests should verify; final method names + assertion structure are decided in A blueprint Step 0.

### A builder contract tests (mandatory)

Each new builder added by A must pass these contract checks:

| Test theme | Verifies | Principle |
|---|---|---|
| **Application canonical input acceptance** | Builder accepts each documented application canonical type and produces the documented protocol DTO | Gap β |
| **DTO output shape parity** | Builder output equals manually-constructed protocol DTO for the same canonical inputs (e.g., `build_check_request(plan, binding={"$p": e_ref, "$age": 25})` equals `CheckRequest(plan=plan, binding=tuple(sorted([("$p", e_ref), ("$age", 25)])), engine="native")`) | `#1` + Gap β |
| **Convenience adapter normalization** | `Mapping[str, Any]` binding input + canonical `BindingItems` input → identical resulting DTO; sort order is canonical (lexicographic on var name, per Step 0 decision) | Gap β |
| **Failure modes early raise** | Malformed input (e.g., binding keys mismatch plan head var names; wrong engine name) raises before runtime DTO is constructed; not deferred to runtime call | Batch 2 §6 |
| **Forbidden inputs** | Passing an SDK-exclusive object (any class whose origin package is `kernel.sdk`) raises a typed helper / domain error or `TypeError` per Step 0; builder MUST NOT silently coerce SDK-exclusive objects | Gap β |
| **No store writes** | Builder does not write to `Store.ledger` (verifiable: ledger byte-dump unchanged before/after builder call). Reads from store ONLY when declared by builder contract (e.g., Batch 2 `build_fact_value_override` reads to find current active fact); read-only contract documented per builder | Batch 2 §6 |
| **Heterogeneity preserved** | Each rule overlay sub-builder (`disable` / `literal_replace` / `add_condition`) has its own test class with family-specific spec arguments verified independently; no shared base test exercising "polymorphic input" | `#3` |

### Static / structural tests (blueprint acceptance candidates, not dynamic unittest)

These are **not** dynamic unittests. They are blueprint acceptance items via `grep` / import-graph review during code review:

- **Layer isolation**: `grep -r "from kernel.sdk" src/kernel/application/capability_helpers*` returns no matches (per `#5`)
- **No sibling runtime call**: `grep` for `from kernel.application.<capability>_runtime import` inside `capability_helpers*` returns no matches (per Batch 2 §6)
- **No frontier import**: `grep` for `from kernel.core.rules.frontier import` inside `capability_helpers*` returns no matches (per Batch 2 §6 drift gate)
- **No SDK export**: builders may be added to `kernel.application.__all__` (advanced importable, per `#6` allowed) but `kernel.sdk.__all__` MUST NOT include them (per `#6` + D2 acceptance gate)

These are review-time checks; A blueprint acceptance section should list them explicitly. **Lint framework is not introduced** (we don't have one yet); upgrade to lint when a recurring drift incident justifies it.

### Test fixture pattern

Per `#19`: flat unittest extending existing `src/kernel/tests/test_application_capability_helpers.py` (Batch 2 location); new test classes per family. Fixtures in same file or `_helpers_fixtures.py` if extracted. No new `tests/capability_helpers/` directory.

---

## 7. Decisions deferred to A blueprint Step 0

Items the implementation blueprint must resolve before scope-freeze:

1. **Module location:** single `kernel.application/capability_helpers.py` (current Batch 2 form, growing) or split into per-family files (`capability_helpers/check.py`, `capability_helpers/proofframe.py`, `capability_helpers/rule_overlay.py`, etc.)?
2. **Binding normalization canonical sort key:** lexicographic on var name only? Or include type tag for cross-engine determinism?
3. **`EntitySelector` resolution in builders:** built-in convenience for any builder accepting `e_ref: str`, or always require pre-resolved `e_ref`? Trade-off: ergonomics vs. helper-layer constraint "do not call sibling runtime functions" (`resolve_selector` lives in `schema_runtime`, gray area).
4. **`overlay` default vs explicit:** for ProofFrame Recheck and rule overlays, default `overlay = EvaluationOverlay()` adds ergonomics but may obscure caller intent. Required vs. optional?
5. **Test fixture pattern:** extend existing `test_application_capability_helpers.py` with new test classes (per family), or split into per-family test files?
6. **`kernel.application.__all__` exposure:** add new builders to `kernel.application.__all__` (advanced importable, per `#6` allowed), or only via submodule import path (`from kernel.application.capability_helpers import build_check_request`)?
7. **`build_round_event_payload`'s `kind` literal:** Python `Literal[...]` static type or `str` with runtime validation? Trade-off: static-checker friendliness vs. forward-compat for new kinds.

---

## 8. What this sketch does NOT cover

- **No SDK shell wrapping** — that is Direction L (post-A+B v1-ready roadmap target per [30_recommendation.md "Plausible follow-ons"](30_recommendation.md)). A's builders are reused by L's SDK shells via the strangler migration pattern, but L's outward shape and acceptance is L's responsibility, not A's.
- **No walker view return wrapping** — A's builders construct *requests*, not results. Result wrapping is Direction B's responsibility (`SupportArtifactView`, `ProofFrameView`, `ProofFrameDiffView`, etc., per [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md)).
- **No adapter evidence helpers** — ProbLog / PyReason adapter evidence builders are deferred (separate trigger, per [10_implicit-gaps.md Gap 2](10_implicit-gaps.md) and Lane 5 of the 2026-05-07 evidence-ecosystem audit).
- **No ProofFrame Diff builder** — `AuditQuery.diff_proof_frames(...)` is already a method on AuditQuery, not a builder need. The 8-helper coverage target excludes it.
- **No SDK Rule lowering** — bridging from SDK Rule to `CompiledDerivationPlan` is the SDK shell's responsibility (per [Direction A — Input shape lock](30_recommendation.md) bridging clause). A consumes already-compiled plans.
- **No formal contract test framework** — that is [Gap ε](README.md), pending separate sub-section in this sketch (added in a future round) and the parallel section in 40_.
- **No multi-capability composition (e.g., `explain` = Check + Diagnose chained)** — A is per-capability builder layer. Composition belongs to L (future SDK scenario API) per [`temp.md` library form discussion](#) (referenced in Round 8 verification log).
