# Task Blueprint: Explain Conformance Batch A — native row seed model

- Status: draft
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework batch
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `src/factgraph/sdk/store.py` (primary edit target)
  - `src/factgraph/application/protocol/rule_expr_lowering.py` (metadata contract; read-only unless helper export is explicitly chosen)
  - `tests/sdk/test_rule_expr_evaluate.py` (existing evaluate→explain tests)
  - `tests/sdk/test_explain_conformance_native.py` (new native conformance battery, proposed)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-a-seed-model.audit.md](./2026-06-10_explain-conformance-batch-a-seed-model.audit.md)

---

## 1. Problem

Native row explanations are still not fully row-anchored for all supported
RuleExpr head shapes.

The previous row-anchoring bugfix fixed inline occurrence variables by seeding
`RuleExprOccurrenceBinding.port_bindings[*].alias_local_execution_var`, but the
current seed builder still only maps `plan.head.ports[*].var.name` to occurrence
`source_var.name`.

That misses two lowering-supported head cases:

1. **projection heads**: `Rule.projection(...)` head ports use
   `$__projection_*` variables. Those variables are linked to branch sources by
   materialized head-port link atoms, not by occurrence `source_var.name`.
2. **external heads**: external head body atoms are materialized with
   `$__head__*` variables. Those aliases also need row values, otherwise head
   atoms can re-enumerate independently from the result row.

The result is an explanation that can show the correct row bindings in the
`EvaluateRow`, while the EvidenceTree re-runs the prober with missing seeds and
renders facts from another row/entity.

## 2. Goals

1. Make `_initial_probe_bindings_for_row(...)` cover all RuleExpr head binding
   kinds: `inline`, `projection`, and `external`.
2. Seed row port values to every lowered variable that can constrain that port:
   occurrence alias-local vars, projection/external head vars, and
   branch-specific source aliases.
3. Derive all seed names from `RuleExprLoweringPlan` structure, not from string
   guesses.
4. Start a native evaluate→explain conformance battery with non-mock,
   row-level tests covering inline, projection, external, OR, join, and
   multi-row anchoring.
5. Preserve support for projection heads; do not reject them in this bugfix.

## 3. Non-goals

- Do not change `RuleExprLoweringPlan` DTO shape unless source preflight proves
  helper exposure is strictly cleaner than local derivation.
- Do not change `probe_native(...)` witness/backtracking semantics.
- Do not change DTOs, adapter dispatch, or EvidenceGraph schema.
- Do not address repr rendering issues from Batches B/C.
- Do not implement Batch D verdict semantics or Batch E aggregate support.

## 4. Source Preflight

Confirmed source facts:

- `RuleExprLoweringPlan` currently contains `head`, `head_binding`, `branches`,
  `occurrence_map`, and `canonical_key`. It **does not** store a
  `declared_ports` field.
- Declared head-port sources are derived by
  `_declared_port_state_for_rule_expr_plan(plan)` inside
  `rule_expr_lowering.py`.
- `_materialize_branch(...)` creates head-port link atoms for
  `plan.head_binding.kind in {"external", "projection"}`:
  - projection: link LHS is the projection head var (`$__projection_*`);
  - external: link LHS is `_head_alias_var_map(plan.head)[head_var]`
    (`$__head__*`);
  - RHS is the branch source alias-local execution var.
- `_head_var_names(plan)` already has the canonical lowering logic:
  - projection: `plan.head.ports[*].name`;
  - external: `_head_alias_var_map(plan.head)[head_var].name`;
  - inline: matched occurrence port binding alias-local execution var.
- The current `_initial_probe_bindings_for_row(...)` only builds
  `source_var.name → alias_local_execution_var.name` from `occurrence_map`, so
  it misses projection/external head aliases and branch-specific head-port link
  aliases.

Implementation must account for this `declared_ports` derivation detail. The
parent program phrase "plan.declared_ports" means "declared ports derivable from
the plan", not a literal field on `RuleExprLoweringPlan`.

## 5. Proposed Shape

Replace the seed builder with a port-centric seed-name collection:

```python
def _initial_probe_bindings_for_row(row: Any, plan: RuleExprLoweringPlan) -> dict[str, Any]:
    row_bindings = getattr(row, "bindings", None)
    if not isinstance(row_bindings, Mapping):
        return {}

    seed_names_by_port = _probe_seed_names_by_head_port(plan)

    out: dict[str, Any] = {}
    for port_name, value in row_bindings.items():
        names = seed_names_by_port.get(port_name, ())
        if not names:
            continue
        public_value = _public_term_value(value)
        for name in names:
            out[name] = public_value
    return out
```

`_probe_seed_names_by_head_port(plan)` must include:

1. **Inline occurrence variables**
   - For matched inline heads, seed the matched occurrence
     `alias_local_execution_var` for each head port.
   - Also keep existing multi-occurrence source-var behavior for joined same-name
     ports where one logical row value needs to constrain multiple occurrences.

2. **Projection / external head variables**
   - projection: seed `plan.head.ports[port].name` (`$__projection_*`).
   - external: seed the alias produced by the same logic as
     `_head_alias_var_map(plan.head)[head_var].name` (`$__head__*`).

3. **Branch source aliases**
   - For projection/external heads, derive declared ports from the plan and seed
     every `RuleExprDeclaredPortBranchSource.alias_local_execution_var.name` for
     that head port.
   - This is required for OR branch row anchoring, because each branch can have a
     different source alias-local var.

Implementation options for deriving helpers:

- **Option A (preferred if import boundary stays clean)**: import private
  lowering helpers into `sdk/store.py`:
  `_declared_port_state_for_rule_expr_plan` and `_head_alias_var_map`, or expose
  a small protocol-level helper if the private import is judged too brittle.
- **Option B**: implement a small local equivalent in `sdk/store.py` using
  `plan.branches` + `plan.occurrence_map`. This avoids broadening
  `rule_expr_lowering.py` but risks duplicating subtle declared-port logic.

Scope-review should choose Option A or B before implementation.

## 6. Boundaries And Invariants

- Projection heads remain supported; this batch does not reject them.
- Missing seed names degrade by under-seeding, never by guessing a name.
- All seeded values come from the row's public bindings and pass through
  `_public_term_value(...)`.
- Adapter engines remain unchanged; their row anchoring is row-id artifact based.
- `closed_head_false` has no row and remains outside per-row seeding.
- G1 witness backtracking semantics remain unchanged.

## 7. Acceptance

- [ ] Inline head row explanations remain row-anchored and previous Bug 1 tests
  stay green.
- [ ] Projection head (`Rule.projection(...)`) multi-row
  `.evaluate(...).row.explain()` renders each row's own projected values and
  does not leak the first/other row.
- [ ] External head multi-row `.evaluate(...).row.explain()` renders each row's
  own head/body facts and does not leak the first/other row.
- [ ] OR branch projection/external result rows are row-anchored in each branch.
- [ ] Join / multi-occurrence rows seed every alias-local variable for shared
  source variables and keep join evidence structurally present.
- [ ] Entity-ref, string, and integer public row bindings unwrap to bare values
  before seeding.
- [ ] Existing prober monotonic test remains green.
- [ ] Souffle / ProbLog / PyReason dispatch tests remain green.
- [ ] `application/explain/prober.py` has no implementation diff.
- [ ] Focused native conformance cohort and explain cohort pass.

## 8. Implementation Plan

1. Choose helper boundary: import/expose lowering helper(s) or implement a local
   seed-name derivation helper in `sdk/store.py`.
2. Add a native conformance test battery file or section with fixtures for:
   inline, projection, external, OR, join/multi-occurrence, and multi-row cases.
3. Add failing tests first for projection and external head row anchoring.
4. Replace `_initial_probe_bindings_for_row(...)` with the port-centric
   seed-name collection.
5. Run focused native conformance tests, existing `test_rule_expr_evaluate`,
   prober tests, and adapter dispatch regressions.
6. Report any seed-name derivation gaps back to the blueprint before widening
   implementation beyond `sdk/store.py`.

## 9. Docs To Update

No public docs expected for this batch. This is evidence correctness and test
coverage work. Batch final may summarize the conformance battery.

## 10. Outcome / Deviations

To be filled after implementation.
