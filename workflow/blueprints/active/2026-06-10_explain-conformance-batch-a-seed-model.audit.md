# Audit Log: Explain Conformance Batch A — native row seed model

Paired with [2026-06-10_explain-conformance-batch-a-seed-model.md](./2026-06-10_explain-conformance-batch-a-seed-model.md).

---

## A. Source Preflight (2026-06-10)

Codex read these shipped anchors before drafting the child blueprint:

- `src/factgraph/sdk/store.py:4100-4117`
  `_initial_probe_bindings_for_row(...)`.
- `src/factgraph/application/protocol/rule_expr_lowering.py`
  `RuleExprLoweringPlan`, `RuleExprHeadBinding`,
  `_materialize_branch(...)`, `_declared_port_state_for_rule_expr_plan(...)`,
  `_head_var_names(...)`, and `_head_alias_var_map(...)`.
- Existing tests in `tests/sdk/test_rule_expr_evaluate.py`,
  `tests/application/protocol/test_rule_expr_head_validation.py`, and
  `tests/application/protocol/test_rule_expr_lowering.py`.

Preflight findings:

1. Current seed builder only maps occurrence `source_var.name` to occurrence
   `alias_local_execution_var.name`.
2. `RuleExprLoweringPlan` does not literally carry `declared_ports`; declared
   ports and branch sources are derived from `plan.branches` and
   `plan.occurrence_map` by `_declared_port_state_for_rule_expr_plan(plan)`.
3. Projection and external heads add head-port link atoms during
   `_materialize_branch(...)`; those link atoms introduce/compare variables not
   covered by the existing source-var seed map.
4. `_head_var_names(plan)` already captures the canonical head-var lowering
   logic for inline/projection/external, but it is private.
5. Existing public tests cover projection evaluation and head validation, but
   they do not assert row-specific EvidenceTree content for projection/external
   heads.

Verdict: Batch A is correctly scoped as a seed-model rework, not a prober
witness rework.

## B. Locked Boundaries

- Do not reject projection heads in this batch.
- Do not edit prober semantics for this batch.
- Keep adapter row anchoring unchanged.
- The implementation should prefer under-seeding over guessed seed names if a
  port cannot be mapped from plan structure.
- Add non-mock evaluate→row.explain tests for every supported head kind.

## C. Scope Question For Review

The main implementation boundary is helper placement:

- **Option A**: import private lowering helpers from
  `rule_expr_lowering.py` into `sdk/store.py`:
  `_declared_port_state_for_rule_expr_plan` and `_head_alias_var_map`, or expose
  a small public-ish protocol helper for seed-name derivation.
- **Option B**: duplicate a local minimal declared-port/source derivation helper
  in `sdk/store.py`.

Codex recommendation: prefer Option A or a tiny exported helper, because
declared-port derivation is subtle (same-name join validation, partial branches,
branch source selection). Duplicating that logic in `sdk/store.py` is riskier.

Claude scope-review locked the boundary:

- Add a single public helper in `rule_expr_lowering.py`, such as
  `probe_seed_vars_by_head_port(plan) -> Mapping[str, tuple[str, ...]]`.
- The helper combines the three authoritative seed-name sources:
  `_head_var_names(plan)`, `_declared_port_state_for_rule_expr_plan(plan)`, and
  occurrence `source_var → alias_local_execution_var` mappings.
- `sdk/store.py` becomes a thin consumer: call the helper, unwrap public row
  values through `_public_term_value(...)`, and seed all returned names.
- Rationale: the seam drift happened because SDK carried a partial copy of
  lowering variable knowledge. Seed-name derivation belongs where lowering mints
  the variables.

Decision: approved `draft → scoped`.

## D. Required Tests

Batch A implementation must include tests that fail on the current seed model:

1. Lowering helper contract tests for inline, projection, external, OR, and
   join seed-name maps.
2. Projection head, two result rows, each `row.explain()` uses its own projected
   values.
3. External head, two result rows, each `row.explain()` uses its own head/body
   values.
4. OR branch head, branch-specific source aliases seeded per row.
5. Join / multi-occurrence, shared source variables seed every alias-local var.
6. Typed public row bindings unwrap to bare values.
7. Existing monotonic and adapter dispatch tests stay green.

## E. Implementation Outcome

Pending.
