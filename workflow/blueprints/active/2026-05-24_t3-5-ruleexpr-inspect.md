# Task Blueprint: T3.5 RuleExpr Inspect

- Status: draft
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: M
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/application/protocol/rule_expr_inspect.py` (new)
  - `src/factgraph/application/protocol/__init__.py`
  - `src/factgraph/sdk/__init__.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/sdk/docs/04_api_surface.en.md`
  - `tests/application/protocol/test_rule_expr.py`
  - `tests/sdk/test_ruleexpr_inspect.py` (new)
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
  - `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
  - `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
  - `workflow/blueprints/archive/2026-05-24_t3-4-join-by-ports.md`
- Audit Log:
  - [2026-05-24_t3-5-ruleexpr-inspect.audit.md](./2026-05-24_t3-5-ruleexpr-inspect.audit.md)

## 1. Problem

T3.1-T3.4 now provide the complete authoring substrate for RuleExpr values: composition, alias validation, joins, reach validation, `.join_by_ports(...)`, structural equality, and bool guards. T3.5 adds the authoring-time inspect projection required by parent C32/C49/C50/C51/C59 and D3.

Canonical drivers:

- D3 §4.1-§4.6 keeps one polymorphic `fg.rules.inspect(...)` entry point, preserves legacy SDK Rule / Inference dict output, and requires application `Rule` plus RuleExpr inputs to return `RuleExprInspect`.
- D3 §4.4-§4.5 requires `RuleExprInspect` as a frozen object DTO with at least `ast`, `occurrences`, `joins`, `unjoined_same_name_ports`, `render()`, and `render_compact()`.
- D4 §4.3 makes occurrence alias identity load-bearing. Inspect must present aliases as expression-local identity, not as incidental display labels.
- D5 §4.6 assigns RuleExpr inspect to T3.5 and allows an internal split into T3.5a/T3.5b if blueprint preflight shows scope risk.
- Stage 3 synthesis §3 T3.5 assigns core `RuleExprInspect`, rich C49-C51/C59 descriptors, and D3-deferred `templates`, `port_visibility`, and `ports` to the inspect tranche.
- Parent §4.7 and §4.10 commit C32/C49/C50/C51. Parent §5.10 commits C59 `inspect.ports`.
- T3.4 archived at `02fcaec6` with second consecutive zero-deviation feat. T3.5 must continue the preemptive scope-locking pattern, but this slice is larger and public-surface-heavy.

This slice is M-class because it adds four public DTOs, extends SDK exports, adds a new RuleExpr inspect projection module, touches SDK inspect dispatch, consumes D3/D4/D5 plus parent C32/C49/C50/C51/C59, and needs a split decision. It is not L-class because the T3 L-class Stage 1 audit, D1-D5 decisions, Stage 3 synthesis, and track-plan sync are already complete; this blueprint consumes those adopted decisions rather than reopening the cluster analysis.

M-to-L triggers:

- changing D3's public return-shape policy for legacy SDK Rule / Inference.
- replacing rather than extending `fg.rules.inspect(...)`.
- adding execution lowering, adapter behavior, evidence/proof narrative semantics, or T5 legacy hard-cut behavior.
- discovering that C32 core inspect and C49/C50/C51/C59 rich descriptors cannot fit one M-class implementation; then apply the split rule in §5.1 rather than broadening this commit.

## 2. Goals

1. Keep `fg.rules.inspect(...)` as the single public entry point and make `SDKStore.inspect_rule(...)` dispatch across three supported inputs:
   - legacy SDK Rule / Inference.
   - application protocol `Rule`.
   - RuleExpr values.

2. Preserve the legacy SDK Rule / Inference dict path unchanged: `_inspect_rule_or_inference(...)` and branch dict shape remain the source of truth for legacy inputs.

3. Add public frozen DTOs:
   - `RuleExprInspect`
   - `OccurrenceInspect`
   - `AtomDescriptor`
   - `PortInspect`

4. Add `RuleExprInspect` minimum C32 fields and helpers:
   - `ast`
   - `occurrences`
   - `joins`
   - `unjoined_same_name_ports`
   - `render(bindings=None)`
   - `render_compact()`
   - `templates`
   - `port_visibility`
   - `ports`

5. Add C49 `OccurrenceInspect` with rich occurrence data: `template_id`, `alias`, `desc_template`, `ports`, and `atoms`.

6. Add C50 `AtomDescriptor` with structured fields and display summary. Machine consumers use structured fields, never parse `summary`.

7. Add C59 `PortInspect` values for `inspect.ports`: `name`, `kind`, `entity_type`, `field`, and `value_type`.

8. Implement C51 render contract as authoring narrative, not proof narrative. Rendering is pure, touches no ledger, and follows desc interpolation rules for ports only.

9. Application `Rule` inspect follows C35 by coercing to a one-occurrence RuleExpr inspect projection. This blueprint chooses a real transient RuleExpr value through the existing `_coerce_rule_expr_operand(...)` path, not a separate inspect-only view.

## 3. Non-goals

- No T3.6 tutorial/docs/examples beyond minimal API-surface entries.
- No RuleExpr execution lowering or adapter integration.
- No evidence/proof narrative rendering.
- No T4 head/closed-head utilities such as `inspect.is_closed` or `inspect.unbound_ports`.
- No T5 legacy SDK `Rule` flip or hard-cut behavior.
- No change to legacy SDK Rule / Inference dict inspect output.
- No change to `_inspect_rule_or_inference(...)` internals except tests may assert it remains preserved.
- No changes to T1.4 `Rule`, `RuleOccurrence`, `RulePortRef`, alias regex, or port APIs.
- No changes to T3.1/T3.2/T3.3/T3.4 authoring semantics, equality/hash, join validation, or `.join_by_ports(...)`.
- No new error subclass; inspect errors reuse `RuleExprError(SDKDSLError)` for RuleExpr/application Rule inputs and preserve existing SDK error behavior for legacy unsupported inputs.

## 4. Current Context

### 4.1 Shipped SDK inspect path

- `_SDKRulesManager.inspect(...)` delegates to `SDKStore.inspect_rule(...)` in `src/factgraph/sdk/store.py:379-386`.
- `SDKStore.inspect_rule(...)` currently returns `_inspect_rule_or_inference(obj)` at `src/factgraph/sdk/store.py:2088-2089`.
- `_inspect_rule_or_inference(...)` accepts legacy SDK `Rule` / `Inference`, returns dict payloads, and rejects everything else at `src/factgraph/sdk/store.py:2907-2927`.
- `_inspect_where_branches(...)` constructs branch dicts at `src/factgraph/sdk/store.py:2930-2964`.

T3.5 must add dispatch before or around `_inspect_rule_or_inference(...)` while keeping that legacy implementation unchanged.

### 4.2 Shipped RuleExpr substrate

Current `src/factgraph/application/protocol/rule_expr.py` provides:

- `RuleJoinConstraint` and `RuleExpr` at lines 20-67.
- frozen `_RuleOperand`, `_AndGroup`, and `_OrGroup` at lines 87-131.
- operand coercion and `_combine(...)` at lines 134-179.
- expression-scope validation and operand iteration at lines 182-210.
- canonical child/join helpers at lines 213-236.
- `.join_by_ports(...)` helpers at lines 239-280.
- join validation / reach helpers at lines 283-331.
- public `__all__` at lines 342-347.

T3.5 should read these values but avoid changing authoring behavior.

### 4.3 Existing exports

- Application protocol imports `RuleExpr`, `RuleExprError`, `RuleJoinConstraint`, and `ExplicitBoolError` from `rule_expr.py` at `src/factgraph/application/protocol/__init__.py:74-75` and exports them at `:192-199`.
- Top-level SDK imports the same RuleExpr names at `src/factgraph/sdk/__init__.py:28-29` and exports them at `:88-93`.
- T3.5 adds four inspect DTO exports to both layers. It does not export helper functions or private `_RuleExpr` internals.

### 4.4 Parent and adopted-decision locks

- D3 lines 71-112 lock polymorphic inspect, legacy dict preservation, application Rule coercion to `RuleExprInspect`, RuleExpr inspect return shape, object DTO shape, and explicit unsupported-input errors.
- D3 lines 155-179 require tests for legacy preservation, application Rule input, RuleExpr input, render helpers, unsupported inputs, and docs distinction.
- D5 lines 126-138 assign T3.5 and allow internal T3.5a/T3.5b split if preflight shows scope risk.
- Stage 3 synthesis lines 168-182 map T3.5 dependencies and may-split structure.
- Track plan lines 190-195 list T3.1-T3.6 and T3.5 inspect scope.
- Parent lines 532-599 define RuleExprInspect top-level fields, OccurrenceInspect, AtomDescriptor, convenience properties, and rendering semantics.
- Parent lines 693-699 lock C32/C49/C50/C51. Parent lines 1504-1533 lock C59 PortInspect.

## 5. Proposed Shape

### 5.1 Split decision

Use a single M-class T3.5 blueprint and implementation plan, with an explicit split trigger.

T3.5 ships both:

- T3.5a core `RuleExprInspect` minimum from D3/C32.
- T3.5b rich descriptors from C49/C50/C51/C59 plus D3-deferred `templates`, `port_visibility`, and `ports`.

Split trigger: if Step 4.6 pre-impl grep or implementation planning shows the inspect projection would require touching more than the scoped files, changing legacy inspect output, or exceeding a reviewable single-feat patch, pause before code and apply an (A-fallback) scope amendment to split into T3.5a/T3.5b. Do not silently bundle an overgrown inspect scope into feat.

Rationale: C32 minimum and C49/C50/C51/C59 rich descriptors share the same traversal and DTO graph. Splitting before any evidence of scope pressure would duplicate traversal design and slow T3.6 docs. The split remains available, but the default plan is one M-class slice.

### 5.2 Module placement and exports

Add new module:

- `src/factgraph/application/protocol/rule_expr_inspect.py`

This module owns:

- `RuleExprInspect`
- `OccurrenceInspect`
- `AtomDescriptor`
- `PortInspect`
- `_inspect_application_rule(...)`
- `_inspect_rule_expr(...)`
- private traversal/render helpers

Reason: `rule_expr.py` is already the authoring value and validation module. T3.5 inspect projection is public DTO-heavy and likely exceeds 200 LOC. A sibling inspect module keeps authoring semantics isolated while still reading `_RuleExpr`, `_RuleOperand`, `_AndGroup`, `_OrGroup`, and `RuleJoinConstraint`.

Export public DTOs from:

- `factgraph.application.protocol`
- top-level `factgraph.sdk`

Expected SDK API surface count changes from 41 to about 45, adding rows for `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, and `PortInspect`.

No helper functions, private `_RuleExpr` internals, or traversal helpers are exported.

### 5.3 SDK inspect dispatch

Update `SDKStore.inspect_rule(obj)` to preserve legacy behavior and add two new branches:

1. Legacy SDK Rule / Inference:
   - delegate to `_inspect_rule_or_inference(obj)`.
   - preserve dict return shape exactly.

2. Application protocol `Rule`:
   - lazy import `Rule` and `_inspect_application_rule`.
   - return `RuleExprInspect` by coercing the Rule into a one-occurrence RuleExpr projection through existing RuleExpr coercion semantics.

3. RuleExpr values:
   - lazy import `_RuleExpr` and `_inspect_rule_expr`.
   - return `RuleExprInspect`.

Unsupported inputs continue to raise explicit SDK-style errors. For inspect input dispatch, use the current SDK store error style unless the value has already entered the RuleExpr inspect helper, where `RuleExprError(SDKDSLError)` is used.

The public manager `fg.rules.inspect(...)` remains unchanged and continues to delegate through `_SDKRulesManager.inspect(...)`. `SDKStore.inspect_rule(obj)` keeps its method name and call shape; its return annotation may widen because D3 makes the output shape intentionally polymorphic (`dict` for legacy SDK Rule / Inference, `RuleExprInspect` for application Rule / RuleExpr).

### 5.4 DTO shapes

Public DTOs are frozen dataclasses or equivalent immutable structures.

```python
RuleExprInspect(
    ast: tuple[object, ...],
    occurrences: tuple[OccurrenceInspect, ...],
    joins: tuple[RuleJoinConstraint, ...],
    unjoined_same_name_ports: tuple[dict[str, object], ...],
)
```

`RuleExprInspect` also provides:

- `templates` property: tuple of unique `template_id` values in stable occurrence order.
- `port_visibility` property: mapping from occurrence alias to tuple of port names.
- `ports` property: tuple of `PortInspect` values.
- `render(bindings: Mapping[str, object] | None = None) -> str`.
- `render_compact() -> str`.

```python
OccurrenceInspect(
    template_id: str,
    alias: str,
    desc_template: str | None,
    ports: tuple[str, ...],
    atoms: tuple[AtomDescriptor, ...],
)
```

```python
AtomDescriptor(
    atom_id: str,
    kind: str,
    subject: str | None,
    entity_type: str | None,
    field: str | None,
    op: str | None,
    value: object,
    summary: str,
)
```

```python
PortInspect(
    name: str,
    kind: Literal["entity_ref", "value"],
    entity_type: str | None,
    field: str | None,
    value_type: str | None,
)
```

DTO `__post_init__` validation is defense-in-depth only: type/shape validation, tuple normalization for collections, and no graph traversal. Semantic source-consistency validation lives in traversal helpers.

### 5.5 Traversal and AST projection

`_inspect_rule_expr(expr)` walks the RuleExpr tree and produces:

- `ast`: nested tuple structure using `("rule", alias, rule_id)`, `("and", children, joins)`, and `("or", children)`.
- `occurrences`: one `OccurrenceInspect` per `_RuleOperand`, stable sorted by `(alias, rule_id)` for presentation.
- `joins`: normalized join constraints collected from `_AndGroup.joins`.
- `unjoined_same_name_ports`: discoverability hints for same-name ports that appear on two or more direct reachable AND operands but are not joined by that port name.

Inspect presentation order is not equality/hash order. D4 §7.3 permits inspect rendering to choose stable presentation order that differs from equality/hash.

### 5.6 AtomDescriptor derivation

T3.5 supports descriptors for the atom kinds already stored in application `Rule.where`.

Minimum mapping:

- `PredAtom`: use parent C50 vocabulary such as `entity_existence` or `field_predicate` when entity / field structure is discoverable; otherwise fall back to kind `pred`, summary from predicate and terms.
- `CmpAtom`: use `field_eq` / `field_compare` when subject and field structure are discoverable; otherwise fall back to kind `cmp` with structured `op`, `field` when discoverable, and value.
- `InAtom`: kind `in`.
- `BuiltinAtom`: kind `builtin`.
- `NotAtom`: kind `not`.

Descriptors are best-effort structural authoring projections. They are not adapter execution IR and not evidence proof nodes. `atom_id` uses a stable inspect-local form such as `<alias>:atom_<index>`; this aligns with parent C50's shared authoring schema intent without claiming execution proof identity.

### 5.7 Render contract

`render()` and `render_compact()` are authoring narrative helpers.

Rules:

- Pure functions: no ledger access, no evaluation, no store reads.
- Single application Rule inspect renders as the single occurrence.
- AND and OR render with explicit grouping.
- joins render as authoring constraints.
- desc interpolation follows parent §3.7.1 / C5: declared port placeholders may use `%port` or `<port>`.
- bindings replace port placeholders by port name; unbound ports render as `<port>`.
- non-port variables are not interpolated.
- `render_compact()` may use symbolic tokens and aliases, but must remain deterministic.

Exact prose is not a proof narrative and should not be used as an execution explanation.

### 5.8 D3 §4.4 deferred items decision

T3.5 ships D3-deferred `templates`, `port_visibility`, and `ports` in the first inspect slice.

Rationale:

- `templates` and `port_visibility` are convenience properties derived from `occurrences`; they do not add new traversal ownership.
- `ports` is C59 and shares occurrence/port traversal with C49.
- Deferring them would leave T3.6 docs with an incomplete inspect surface and force a small follow-up over the same DTO graph.

If the split trigger in §5.1 fires, T3.5a ships core `RuleExprInspect` without these convenience properties, and T3.5b ships them with rich descriptors.

### 5.9 Preemptive scope lock

T3.5 applies the T3.3/T3.4 zero-deviation pattern before implementation:

- Do not change `_SDKRulesManager.inspect(...)` public signature.
- Do not change legacy `_inspect_rule_or_inference(...)` dict output.
- Do not convert legacy SDK Rule / Inference inspect to `RuleExprInspect`.
- Do not add methods to T1.4 `Rule`, `RuleOccurrence`, or `RulePortRef`.
- Do not change RuleExpr equality/hash or canonicalization.
- Do not change `.join(...)`, `.join_by_ports(...)`, or reach validation.
- Do not add execution lowering or adapter integration.
- Do not add new error subclasses.
- Do not replace `_is_legacy_sdk_rule`.
- Do add explicit lazy imports in SDK dispatch to avoid import cycles.

### 5.10 Validation layers

Use three validation layers:

1. DTO layer:
   - frozen dataclasses.
   - tuple-normalize collection fields.
   - validate basic field types where cheap.

2. traversal layer:
   - ensure each occurrence comes from `_RuleOperand`.
   - ensure joins are read from `_AndGroup.joins`.
   - ensure `PortInspect` values derive from actual `Rule.ports` / `Rule.port_types`.

3. dispatch layer:
   - only legacy SDK Rule / Inference, application Rule, and RuleExpr inputs are accepted.
   - unsupported inputs raise explicit SDK-style errors.

### 5.11 Error hierarchy

RuleExpr inspect helper errors use `RuleExprError(SDKDSLError)` from T3.1. SDK dispatch errors that happen before RuleExpr helper dispatch may keep the existing `SDKStoreError` style. Do not introduce `RuleExprInspectError`.

## 6. Invariants

- Legacy SDK Rule / Inference dict inspect behavior is preserved.
- `fg.rules.inspect(...)` remains the single public entry point.
- Application `Rule` inspect returns `RuleExprInspect`, not a legacy dict.
- RuleExpr inspect returns `RuleExprInspect`.
- `RuleExprInspect` and nested DTOs are immutable.
- Inspect is read-only authoring projection, not execution/evidence/proof narrative.
- `RuleExprInspect.joins` consumes T3.3 `RuleJoinConstraint` values without redefining them.
- Occurrence aliases remain load-bearing in inspect identity and presentation.
- T1.4 alias/port substrate remains unchanged.
- T1.3 staged naming remains unchanged; top-level `factgraph.sdk.Rule` remains legacy.
- T2.3 aggregate substrate and adapters are untouched.
- T3.1/T3.2/T3.3/T3.4 acceptance and negative-action gates remain preserved.
- No direct `application_rule == rule_expr` or `RuleExprInspect == rule_expr` cross-type equality is introduced.

## 7. Acceptance

- [ ] Existing legacy SDK Rule inspect tests pass unchanged.
- [ ] Existing legacy SDK Inference inspect tests pass unchanged where present.
- [ ] `fg.rules.inspect(application_rule)` returns `RuleExprInspect`.
- [ ] `fg.rules.inspect(rule_expr)` returns `RuleExprInspect`.
- [ ] Unsupported inspect inputs raise explicit SDK-style errors.
- [ ] `RuleExprInspect` is frozen / immutable.
- [ ] `OccurrenceInspect`, `AtomDescriptor`, and `PortInspect` are frozen / immutable.
- [ ] Public DTOs export from `factgraph.application.protocol`.
- [ ] Public DTOs re-export from top-level `factgraph.sdk`.
- [ ] SDK API surface docs add four minimal rows and update export count.
- [ ] `RuleExprInspect.ast` represents rule, AND, OR, and join structure deterministically.
- [ ] `RuleExprInspect.occurrences` includes aliases, template ids, desc templates, ports, and atoms.
- [ ] `RuleExprInspect.joins` includes T3.3 join constraints and preserves symmetric/dedup normalized behavior.
- [ ] `RuleExprInspect.unjoined_same_name_ports` reports same-name direct-AND ports that are not joined.
- [ ] `templates` derives from occurrences and is stable.
- [ ] `port_visibility` derives from occurrences and is stable.
- [ ] `ports` returns `PortInspect` values with C59 fields.
- [ ] `AtomDescriptor` exposes structured fields and `summary`; tests do not parse `summary`.
- [ ] `render()` returns deterministic authoring narrative for single Rule.
- [ ] `render()` returns deterministic authoring narrative for AND/OR/join RuleExpr.
- [ ] `render(bindings=...)` substitutes only declared port placeholders.
- [ ] `render_compact()` returns deterministic compact authoring text.
- [ ] Application Rule inspect uses the same one-occurrence semantics as RuleExpr coercion.
- [ ] Legacy dict inspect and RuleExprInspect return-shape difference is intentional and tested.
- [ ] T1.4 application protocol tests pass unchanged.
- [ ] T1.3 SDK naming tests pass unchanged.
- [ ] T2.3 aggregate tests pass unchanged.
- [ ] T3.1-T3.4 RuleExpr tests pass unchanged.
- [ ] Ruff passes on touched Python files.

## 8. Implementation Plan

1. Record G7 baseline before implementation:

   ```bash
   PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v
   ```

   Expected baseline after T3.4: 63 tests OK.

2. Pre-impl grep:
   - locate all current `inspect_rule` and `_inspect_rule_or_inference` call sites.
   - confirm no existing `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, or `PortInspect` names.
   - confirm SDK `__all__` current RuleExpr export block.

3. Add `rule_expr_inspect.py` with frozen DTOs and traversal helpers.

4. Implement RuleExpr traversal over `_RuleOperand`, `_AndGroup`, and `_OrGroup`.

5. Implement atom descriptor best-effort mapping for current application Rule atom types.

6. Implement render and render_compact.

7. Update SDK inspect dispatch with lazy imports while preserving legacy `_inspect_rule_or_inference(...)`.

8. Export the four DTOs from application protocol and top-level SDK.

9. Add API surface docs rows.

10. Add focused tests for DTO shape, dispatch, render, descriptor fields, legacy preservation, and cross-slice gates.

11. Run targeted gates:

    ```bash
    PYTHONPATH=src python -m unittest \
      tests.application.protocol.test_rule \
      tests.application.protocol.test_rule_expr \
      tests.sdk.test_rule_naming \
      tests.application.protocol.test_rule_aggregate \
      tests.sdk.test_ruleexpr_inspect \
      tests.test_branch_identity_rule_inspect \
      tests.test_public_inference_factgraph_create \
      -v
    ```

12. Run ruff:

    ```bash
    python -m ruff check \
      src/factgraph/application/protocol/rule_expr.py \
      src/factgraph/application/protocol/rule_expr_inspect.py \
      src/factgraph/application/protocol/__init__.py \
      src/factgraph/sdk/__init__.py \
      src/factgraph/sdk/store.py \
      tests/application/protocol/test_rule_expr.py
    ```

## 9. Docs

Update `src/factgraph/sdk/docs/04_api_surface.en.md` with minimal API rows for:

- `RuleExprInspect`
- `OccurrenceInspect`
- `AtomDescriptor`
- `PortInspect`

T3.6 owns tutorial docs, examples, and user-facing explanation of legacy dict inspect versus RuleExprInspect object return shape. T3.5 should not add tutorial examples beyond the minimal API surface update.

## 10. Outcome / Deviations

To be completed after implementation.
