# Task Blueprint: T3.6 Docs And Examples

- Status: implemented
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Class: S
- Related Modules:
  - `src/factgraph/sdk/docs/00_user_guide.en.md`
  - `src/factgraph/sdk/docs/01_concepts.en.md`
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
  - `src/factgraph/application/docs/rule.md`
- Related Docs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
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
  - `workflow/blueprints/archive/2026-05-24_t3-5-ruleexpr-inspect.md`
- Audit Log:
  - [2026-05-24_t3-6-docs-and-examples.audit.md](./2026-05-24_t3-6-docs-and-examples.audit.md)

## 1. Problem

T3.1-T3.5 now ship the full initial RuleExpr authoring and inspect surface:
composition, bool guards, expression-scope validation, joins, reach validation,
`.join_by_ports(...)`, polymorphic inspect, and rich RuleExpr inspect DTOs.
T3.6 is the final initial T3 slice and must turn those shipped behaviors into
clear user-facing docs and examples before the later execution-lowering tranche.

Canonical drivers:

- D5 section 4.7 assigns T3.6 to docs and examples after authoring and inspect
  behavior stabilizes.
- Stage 3 synthesis section 3 T3.6 requires staged import examples, `.eq(...)`
  join syntax, `&` / `|` precedence and parentheses, bool guards, same-name port
  no-auto-join guidance, and inspect return-shape differences.
- D1 section 4.5 requires examples to use `ApplicationRule`, `RuleExpr`, and
  `build_application_rule(...)` during the T1.3 staged naming period.
- D2 section 7.3 requires docs to show `.eq(...)`, not Python `==`, for initial
  join constraint construction.
- D3 section 7.3 requires docs to distinguish legacy dict inspect from
  `RuleExprInspect` object inspect.
- Parent C24 / C27 / C32 / C35 / C49-C51 / C58 / C59 are now implemented by
  T3.1-T3.5 and need current module docs.

This slice is S-class because it is docs-only: it adds no public SDK exports,
no new DTO, no new error class, no algorithm, and no shipped behavior change.
It consumes the already adopted T3 decisions and archived T3.1-T3.5 substrate.
It is not M-class unless implementation discovers that docs cannot be made
accurate without code, API surface, or export changes; such discovery must stop
before implementation and trigger a scope amendment.

S-to-M triggers:

- touching Python source outside docs.
- changing `factgraph.sdk.__all__`, public exports, DTOs, or error classes.
- changing shipped RuleExpr, join, inspect, or legacy SDK semantics.
- adding new executable examples that require new runtime behavior instead of
  documenting shipped behavior.

## 2. Goals

1. Document staged imports and naming during T1.3/T3:
   - `factgraph.sdk.Rule` remains legacy.
   - `factgraph.sdk.ApplicationRule` is the application Rule.
   - `factgraph.application.protocol.Rule` is the same runtime type as
     `ApplicationRule`.
   - `build_application_rule(...)` is the bridge for SDK DSL authors.
   - T5 owns the final hard-cut / name flip.

2. Document explicit join syntax:
   - `a.user.eq(b.person)` constructs `RuleJoinConstraint`.
   - `.eq(...)` is used instead of `==` to preserve T1.4 `RulePortRef` value
     equality.
   - `(a & b).join(a.user.eq(b.person))` is the base authoring pattern.

3. Document `&` / `|` precedence and parentheses:
   - Python `&` binds tighter than `|`.
   - mixed AND/OR expressions should always use explicit parentheses.
   - examples must distinguish `a & b | c`, `(a & b) | c`, and `a & (b | c)`.

4. Document bool guards:
   - application `Rule` and RuleExpr truthiness raises `ExplicitBoolError`.
   - use `&` / `|`, not `and` / `or`.
   - use explicit identity checks such as `rule is None` when testing optionals.

5. Document same-name ports do not auto-join:
   - matching port names across occurrences are only discoverability hints.
   - users must write `.join(...)` or `.join_by_ports(...)`.
   - `fg.rules.inspect(expr).unjoined_same_name_ports` exposes hints using
     `port_name` and `occurrences` keys.

6. Document inspect return-shape differences:
   - legacy SDK Rule / Inference inputs return the preserved dict shape.
   - application Rule inputs return `RuleExprInspect` through C35 one-rule
     coercion.
   - RuleExpr inputs return `RuleExprInspect`.
   - explain that the dual shape is intentional until a future T5 hard-cut.

7. Provide compact examples for the shipped RuleExpr surface:
   - single application Rule inspect.
   - AND/OR composition with explicit parentheses.
   - `.join(...)` and `.join_by_ports(...)`.
   - same-occurrence and OR-branch join rejection examples as diagnostics, not
     new semantics.
   - inspect render and `unjoined_same_name_ports` examples.

## 3. Non-goals

- No RuleExpr execution lowering, adapter integration, or proof evaluation.
- No T5 legacy SDK `Rule` hard-cut.
- No Python source changes outside docs.
- No changes to `factgraph.sdk.__all__`, `04_api_surface.en.md`, or API export
  counts; T3.5 already corrected runtime `__all__` count to 53.
- No new public DTOs, helper functions, or error classes.
- No changes to T1.4 `Rule`, `RuleOccurrence`, `RulePortRef`, alias regex, or
  port APIs.
- No changes to T3.1-T3.5 RuleExpr / inspect implementations.
- No cross-type equality such as `application_rule == rule_expr`.
- No replacement of the duck-typed legacy SDK Rule detector.
- No durable docs index additions unless implementation chooses a new permanent
  docs entry; the default plan edits existing docs files only.

## 4. Current Context

### 4.1 Current docs surface

Existing docs available for T3.6:

- `src/factgraph/sdk/docs/00_user_guide.en.md` is the introductory tour and
  table of contents.
- `src/factgraph/sdk/docs/01_concepts.en.md` explains declarations,
  candidates, assertions, proof traces, and SDK/application boundaries.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` owns SDK rules,
  where syntax, bridge examples, and rule/inference authoring guidance.
- `src/factgraph/sdk/docs/04_api_surface.en.md` is the API index and was
  updated by T3.5 for RuleExprInspect DTO rows and runtime export count.
- `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` owns what-if/proof
  examples and may host inspect examples only if they are naturally
  counterfactual/proof adjacent.
- `src/factgraph/application/docs/rule.md` is the application Rule DTO current
  truth and already contains T1.4/T3.1 language, but it still says joins,
  inspect output, and full examples are deferred.

T3.6 should remove stale "deferred" language where T3.1-T3.5 have now shipped
and add user-facing RuleExpr guidance near the current rule docs.

### 4.2 Shipped behavior to document

The docs must present behavior as shipped, not as parent-final aspiration:

- `factgraph.sdk.Rule` is still legacy during T1.3/T3.
- `ApplicationRule` / `build_application_rule(...)` are the staged application
  Rule paths.
- `_RuleExpr`, `_AndGroup`, and `_OrGroup` remain internal.
- `RulePortRef.__eq__` remains value equality. `.eq(...)` builds joins.
- `.join(...)` is AND-only and validates reach.
- `.join_by_ports(...)` is explicit-name pairwise expansion over AND groups.
- same-name ports never auto-join.
- `fg.rules.inspect(...)` is polymorphic and intentionally has two return
  families: legacy dict and `RuleExprInspect`.
- `RuleExprInspect.ports` uses `PortInspect` descriptors; value ports may show
  `value_type="unknown"` because T1.4 `PortType` does not carry concrete value
  type metadata.

### 4.3 Existing test baseline

T3.5 closure recorded:

- G7 baseline: 63 OK for `tests.application.protocol.test_rule` and
  `tests.application.protocol.test_rule_expr`.
- core + T3.5 inspect gate: 76 OK.
- focused cross-slice gate: 99 OK.
- `tests.test_public_inference_factgraph_create` has unrelated pre-existing
  failures at the T3.5 G7 baseline.
- pytest remains deferred due the known environment SIGSEGV; unittest is the
  T3 cadence runner.

T3.6 should use docs grep and unittest preservation gates, not introduce a new
pytest dependency.

## 5. Proposed Shape

### 5.1 Docs-only file placement

Default touched files:

- `src/factgraph/sdk/docs/00_user_guide.en.md`
- `src/factgraph/sdk/docs/01_concepts.en.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/application/docs/rule.md`

Explicitly untouched:

- `src/factgraph/sdk/docs/04_api_surface.en.md`; T3.5 already updated API rows
  and runtime export count.
- `src/factgraph/sdk/docs/06_what_if_and_proof.en.md`; T3.6 keeps inspect
  render docs in rules/application docs, not proof-adjacent docs. Any later
  proof-facing cross-reference requires a scoped amendment.
- all Python source files.
- all tests, unless a later review explicitly asks for docs-grep fixtures. The
  default T3.6 implementation is docs-only.

No new docs file is planned. If implementation discovers that a dedicated
`08_ruleexpr.en.md` is required, pause before editing and record a scoped
amendment because that would add a durable docs entry and likely require
`src/factgraph/sdk/docs/README.md` updates.

### 5.2 Staged import examples

Docs must use this staged import pattern:

```python
from factgraph.sdk import ApplicationRule, RuleExpr, build_application_rule, vars
```

and bridge examples such as:

```python
from factgraph.sdk import build_application_rule, vars

with vars("u") as (u,):
    active_user = build_application_rule(
        id="active_user",
        where=[User(u).status == "active"],
        ports={"user": u},
        desc="active user %user",
    )
```

Docs must not teach:

```python
from factgraph.sdk import Rule
```

as the application Rule import during T3. The only allowed mention of
top-level `Rule` is to explain that it remains the legacy SDK Rule until T5.

### 5.3 Join syntax examples

Docs should teach:

```python
a = active_user.as_("a")
b = assigned_owner.as_("b")

expr = (a & b).join(a.user.eq(b.user))
```

Key wording:

- `.eq(...)` constructs `RuleJoinConstraint`.
- `a.user == b.user` remains value equality / bool semantics for
  `RulePortRef`, not join construction.
- `.join(...)` is available on AND groups.
- OR groups and single Rules do not accept `.join(...)`.
- same-occurrence joins are rejected.

### 5.4 Precedence and bool guard examples

Docs must explicitly state:

- Python evaluates `a & b | c` as `(a & b) | c`.
- Write parentheses for mixed AND/OR even when Python precedence would produce
  the intended tree.
- Use `&` / `|` for RuleExpr construction. Do not use Python `and` / `or`.
- Python truthiness of application `Rule` and RuleExpr raises
  `ExplicitBoolError`.

Example wording:

```python
expr = (a & b) | c      # explicit OR of an AND group and c
expr = a & (b | c)      # explicit AND with an OR branch
```

Anti-example:

```python
expr = a and b          # raises ExplicitBoolError because Python evaluates bool(a) for short-circuit
if expr:                # raises ExplicitBoolError
    ...
```

### 5.5 Same-name port and join_by_ports examples

Docs must make "same-name ports do not auto-join" load-bearing:

```python
expr = a & b
fg.rules.inspect(expr).unjoined_same_name_ports
```

Then show the two explicit join paths:

```python
expr = (a & b).join(a.user.eq(b.user))
expr = (a & b).join_by_ports("user")
```

`.join_by_ports("user")` should be documented as explicit-name pairwise
expansion over reachable AND operands. It is not silent auto-join.

### 5.6 Inspect return-shape examples

Docs must show the three-way split:

```python
legacy_payload = fg.rules.inspect(legacy_rule)      # dict
rule_view = fg.rules.inspect(application_rule)      # RuleExprInspect
expr_view = fg.rules.inspect(rule_expr)             # RuleExprInspect
```

The docs should call out:

- legacy SDK Rule / Inference dict output is preserved.
- `RuleExprInspect` exposes `ast`, `occurrences`, `joins`,
  `unjoined_same_name_ports`, `templates`, `port_visibility`, `ports`,
  `render()`, and `render_compact()`.
- `RuleExprInspect.ports` returns `PortInspect` descriptors.
- `OccurrenceInspect.ports` is a tuple of port name strings.
- value port `value_type="unknown"` means the current T1.4 substrate does not
  carry a concrete value type.

### 5.7 Preemptive scope lock

T3.6 applies the T3.3/T3.4/T3.5 zero-deviation pattern:

- Do not change shipped Python source.
- Do not change SDK exports or `__all__`.
- Do not add a new public DTO or error class.
- Do not touch T1.4/T1.3/T2.3/T3.1-T3.5 substrate files.
- Do not change RuleExpr equality/hash, join validation, inspect dispatch, or
  legacy inspect dict output.
- Do not introduce cross-type equality.
- Do not replace `_is_legacy_sdk_rule`.
- Do not edit `src/factgraph/sdk/docs/04_api_surface.en.md` unless Step 4.2
  review explicitly scopes it.
- If a new docs entry is needed, pause for scope amendment before adding it.

### 5.8 Docs wording constraints

Docs must be current-truth and user-facing:

- Prefer shipped syntax over parent-final syntax.
- Explain staged naming without implying T5 has happened.
- Treat inspect as authoring projection, not proof narrative.
- Keep examples concise and runnable against current public imports.
- Do not over-teach internal `_RuleExpr`, `_AndGroup`, `_OrGroup`, or private
  helpers.

## 6. Invariants

- T3.6 is docs-only.
- T1.1 Rule DTO behavior and atom id schema remain unchanged.
- T1.2 DSL bridge behavior remains unchanged.
- T1.3 staged naming remains unchanged; top-level `factgraph.sdk.Rule` remains
  legacy.
- T1.4 alias/port substrate remains unchanged.
- T2.3 aggregate substrate and adapters remain unchanged.
- T3.1 RuleExpr composition, bool guards, exports, and negative-action gates
  remain unchanged.
- T3.2 expression-scope validation remains unchanged.
- T3.3 joins, reach validation, equality/hash, and negative-action gates remain
  unchanged.
- T3.4 `.join_by_ports(...)` behavior and no-export lock remain unchanged.
- T3.5 RuleExpr inspect dispatch, DTOs, and API surface count remain unchanged.
- Legacy SDK Rule / Inference inspect dict output remains unchanged.
- `RuleExprInspect` object return shape remains unchanged.
- No direct `application_rule == rule_expr` or `RuleExprInspect == rule_expr`
  cross-type equality is introduced.

## 7. Acceptance

- [ ] Docs use staged imports with `ApplicationRule`, `RuleExpr`, and
  `build_application_rule(...)`, and do not present top-level SDK `Rule` as the
  application Rule before T5.
- [ ] Docs explain `.eq(...)` as the join-constraint constructor and explicitly
  state why `==` is not the T3 join syntax.
- [ ] Docs include `.join(...)` examples and diagnostics boundaries: AND-only,
  no single Rule `.join(...)`, no OR group `.join(...)`, same-occurrence joins
  rejected.
- [ ] Docs include `.join_by_ports(...)` examples and explain explicit-name
  pairwise expansion.
- [ ] Docs explain Python `&` / `|` precedence and require parentheses for mixed
  AND/OR examples.
- [ ] Docs explain bool guards and use `&` / `|`, not `and` / `or`.
- [ ] Docs explain same-name ports do not auto-join and show
  `unjoined_same_name_ports`.
- [ ] Docs explain inspect return-shape differences: legacy dict vs
  `RuleExprInspect`.
- [ ] Docs mention `RuleExprInspect.ports` / `OccurrenceInspect.ports` shape
  distinction and `value_type="unknown"` for value ports.
- [ ] Application Rule docs no longer say joins / inspect / examples are
  deferred after T3.1 where T3.3-T3.5 have now shipped.
- [ ] `src/factgraph/sdk/docs/04_api_surface.en.md` remains untouched unless a
  scoped amendment says otherwise.
- [ ] No Python source files are modified.
- [ ] Baseline RuleExpr tests still pass.
- [ ] Focused cross-slice tests still pass, excluding known pre-existing
  `tests.test_public_inference_factgraph_create` failures.
- [ ] Markdown grep checks per §8 step 8 pass: required terms are present,
  forbidden final-state `Rule` imports are absent from new RuleExpr examples,
  and stale "deferred" language in application Rule docs is updated.

## 8. Implementation Plan

1. Record G7 baseline before docs edits:

   ```bash
   PYTHONPATH=src python -m unittest \
     tests.application.protocol.test_rule \
     tests.application.protocol.test_rule_expr \
     tests.sdk.test_ruleexpr_inspect \
     -v
   ```

   Expected after T3.5: 76 tests OK.

2. Pre-impl grep:
   - search SDK/application docs for stale "joins deferred" and "inspect
     deferred" language.
   - search docs for final-state `from factgraph.sdk import Rule` examples near
     application Rule / RuleExpr teaching.
   - search docs for `a.user == b.user` join examples.
   - search docs for missing `join_by_ports`, `ExplicitBoolError`, and
     `unjoined_same_name_ports` teaching.
   - confirm `04_api_surface.en.md` does not need edits.

3. Update `application/docs/rule.md` to replace stale T3.1 deferral language
   with current RuleExpr / join / inspect summaries.

4. Update `sdk/docs/03_rules_and_inferences.en.md` with the main RuleExpr
   authoring section and compact examples.

5. Update `sdk/docs/01_concepts.en.md` with the staged RuleExpr / inspect mental
   model if needed.

6. Update `sdk/docs/00_user_guide.en.md` with navigation/cross-link only if
   the RuleExpr docs become a durable user-guide destination.

7. Keep `sdk/docs/06_what_if_and_proof.en.md` untouched. T3.6 documents inspect
   render as authoring narrative in rules/application docs; a proof-facing
   cross-reference requires a scoped amendment.

8. Run docs grep gates:
   - required terms are present.
   - forbidden final-state imports are absent in new RuleExpr examples.
   - stale "joins deferred" / "inspect deferred" language is gone or clearly
     historical.

9. Run preservation tests:

   ```bash
   PYTHONPATH=src python -m unittest \
     tests.application.protocol.test_rule \
     tests.application.protocol.test_rule_expr \
     tests.sdk.test_ruleexpr_inspect \
     tests.sdk.test_rule_naming \
     tests.application.protocol.test_rule_aggregate \
     tests.test_branch_identity_rule_inspect \
     -v
   ```

   Expected preservation after T3.5: 99 tests OK.

10. Run ruff only if any Python file is unexpectedly touched. The expected path
    has no Python edits.

11. Complete Step 4.7 self-review before closure: docs obligations, no-code
    scope, source chain, and cross-slice preservation.

## 9. Docs

This slice is docs itself. The implementation should update existing current
module docs rather than add a new durable docs entry by default.

Expected docs changes:

- `src/factgraph/application/docs/rule.md`: current application Rule and
  RuleExpr substrate truth.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`: main user-facing
  RuleExpr authoring examples.
- `src/factgraph/sdk/docs/01_concepts.en.md`: mental model / return-shape
  distinction if needed.
- `src/factgraph/sdk/docs/00_user_guide.en.md`: navigation pointer if needed.
- `src/factgraph/sdk/docs/06_what_if_and_proof.en.md`: explicitly untouched;
  proof-facing inspect cross-references are deferred unless a scoped amendment
  says otherwise.

Out of default scope:

- `src/factgraph/sdk/docs/04_api_surface.en.md`; T3.5 already updated API rows.
- `src/factgraph/sdk/docs/README.md`; only update if a new docs file is added.
- repository-level `docs/README.md`; no new repository-level durable entry is
  expected.

## 10. Outcome / Deviations

### Final Landed Code

- `src/factgraph/application/docs/rule.md` — replaced stale T3.1-era deferral
  language with current T3.1-T3.5 truth: composition, bool guards, explicit
  `.eq(...)` joins, `.join(...)`, `.join_by_ports(...)`, same-name port
  discoverability, and RuleExpr inspect return shape.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — added the main
  user-facing "RuleExpr Authoring Surface" section covering staged imports,
  `ApplicationRule` / `build_application_rule(...)`, occurrence aliases,
  `&` / `|` precedence and parentheses, `ExplicitBoolError` bool guards,
  `.eq(...)` joins, `.join_by_ports(...)`, `unjoined_same_name_ports`, inspect
  return-shape differences, `value_type="unknown"`, and render helpers as
  authoring narrative.
- `src/factgraph/sdk/docs/01_concepts.en.md` — added a concise RuleExpr mental
  model under the SDK/application split and added RuleExpr DTOs to the frozen
  DTO boundary table.
- `src/factgraph/sdk/docs/00_user_guide.en.md` — added navigation pointers from
  the eval section and "Where to go next" list to the RuleExpr authoring docs.

Strict scope result: T3.6 landed in four docs files. `04_api_surface.en.md`,
`06_what_if_and_proof.en.md`, all Python source files, and all tests remained
untouched.

### Test Gates

- G7 baseline `24e55668`: `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect -v` -> 76 OK.
- Post-impl preservation gate: `tests.application.protocol.test_rule`, `tests.application.protocol.test_rule_expr`, `tests.sdk.test_ruleexpr_inspect`, `tests.sdk.test_rule_naming`, `tests.application.protocol.test_rule_aggregate`, and `tests.test_branch_identity_rule_inspect` -> 99 OK.
- Markdown grep gates passed: stale "deferred to later T3" language removed; required RuleExpr teaching terms present; no new final-state `from factgraph.sdk import Rule` application-Rule teaching added.
- Ruff not run because T3.6 touched no Python files.

### Deviations / Follow-Ups

T3.6 closed with **zero deviations** from blueprint scope. This is the
**fourth consecutive T3 feat commit** to land with 0 P0/P1/P2/P3 findings at
Step 4.7 review, and the final feat slice of the initial T3 authoring/inspect
cycle.

T3 cycle six-slice summary:

| Slice | Class | Feat | Deviation |
|---|---|---|---|
| T3.1 | M | `e049c93e` | A-fallback `8de03372` mid-impl reactive. |
| T3.2 | S | `2a16dd98` | T-1 `RuleOccurrence.__and__/__or__` deviation bundled into feat. |
| T3.3 | M | `0b80fe9b` | **0 deviation** — first preemptive scope-locking success. |
| T3.4 | S | `8f248212` | **0 deviation** — second consecutive zero-deviation feat. |
| T3.5 | M | `55d9e67b` | **0 deviation** — third consecutive feat plus first proactive Step 4.6 A-fallback catch. |
| T3.6 | S | `f8abaad1` | **0 deviation** — fourth consecutive feat and final initial T3 slice. |

Cadence discipline pattern validated across T3:

- preemptive scope locks with explicit "do not" lists.
- algorithm / validation / diagnostics specifications before implementation.
- sibling-module isolation for public-surface-heavy work.
- Step 4.6 proactive catch and pre-feat A-fallback amendment in T3.5.
- docs-only scope discipline in T3.6: strict four-file docs scope, no Python,
  no tests, no API-surface count churn.

The pattern spans M/S/M/S/M/S slices, including the largest T3 M-class slice
(T3.5) and the final docs-only S-class slice (T3.6). The zero-deviation tail is
repeatable rather than slice-specific.

Out-of-scope notes preserved:

- `tests.test_public_inference_factgraph_create` still has pre-existing
  failures unrelated to RuleExpr work at the T3.5 G7 baseline.
- pytest remains deferred due the known environment SIGSEGV; unittest fallback
  was used throughout the T3 cycle.
- T3.5-F6 `value_type="unknown"` for value ports is now documented in T3.6.
  A future substrate slice may add concrete value-type metadata if needed.

No T3.6 follow-up blocks the later RuleExpr execution-lowering tranche.

### Stage 1-3 Traceability

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Adopted D1: `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md` §4.5.
- Adopted D2: `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md` §4.1-§4.5 and §7.3.
- Adopted D3: `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md` §4.1-§4.6 and §7.3.
- Adopted D4: `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md` §4.1-§4.7 and §7.3.
- Adopted D5: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.7.
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.6.
- Track plan sync: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` synced at `9c857d0c`.
- Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.6 / §3.7.1 C5-C6 / §4 C23-C35+C49-C51 / §5.9 C58 / §5.10 C59.
- Substrate archives: T1.4 plus T3.1, T3.2, T3.3, T3.4, and T3.5 archive pairs.

### Archive Readiness

Yes.
