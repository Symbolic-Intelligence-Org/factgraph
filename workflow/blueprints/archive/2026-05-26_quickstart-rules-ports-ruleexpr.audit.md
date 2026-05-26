# Audit: Quickstart Rules Ports + RuleExpr Coverage

- Status: implemented
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_quickstart-rules-ports-ruleexpr.md`
- Stage: implemented
- Class: M (predicted docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved
- Ownership: self-owned (Claude as both owner and reviewer)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | scoped | `ee14773e` | Self-owned blueprint pair drafted with inventory pre-locked | Cross-flip cadence unavailable this cycle; rigorous self-review compensates. Inventory survey run before draft to surface design vs shipped drift. |
| 2026-05-26 | scoped | `10f36b6d` | Branch label corrected | Original draft labeled `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`; actual working branch is `v0.2.0-t11-1-attach-view-scope-2026-05-26`. |
| 2026-05-26 | implemented | `4cdd4e54` | Three new sections + checklist extension landed | +330 LOC docs-only; 18-assertion end-to-end smoke green (including 5 negative-path rejects). |

## 2. Source Reads

| Source | Reason |
|---|---|
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Current quickstart text shows `ports={...}` in one example only; no explanation of ports semantics, no `RuleExpr` composition coverage. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.6 (lines 160-232) | Active design source for ports semantics, three-variable distinction, RuleExpr port join, AND-spine reachable. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.7 (lines 234-259) | Active design source for `desc="%port_name"` rendering. |
| `src/factgraph/application/protocol/rule.py` | Shipped truth for `Rule`, `RuleOccurrence`, `RulePortRef`, `PortType`. |
| `src/factgraph/application/protocol/rule_expr.py` | Shipped truth for `_AndGroup`, `_OrGroup`, `.join_by_ports`, `.join`, `RuleExpr.all` / `.any`. |
| `tests/sdk/test_rule_expr_evaluate.py` (line 162-170) | Confirms `Rule.projection` evaluate head only works under mocked `evaluate_derivation_plans`. |

## 3. Initial Inventory

| Area | Finding | Treatment |
|---|---|---|
| Quickstart `ports` coverage | One example use + one prose sentence; no semantics. | Add dedicated §"Understanding ports". |
| Quickstart `RuleExpr` composition | Absent. | Add dedicated §"Composing rules with RuleExpr". |
| `head=rule` arity rule | Used in examples but never explained. | Cover in §"Choosing the right head". |
| `Rule.projection` evaluate head | Verified non-working in real evaluator (only passes under mock). | Explicit non-goal in blueprint scope and §C-5 callout in doc. |
| Same-named ports default behavior | Design says "independent existential"; shipped raises ambiguous-port error. | Teach shipped behavior; note drift in audit. |

## 4. Step 4.6 Scoped Inventory Plan

Pre-implementation inventory items to lock are recorded in §5 below (combined with draft step because this is a self-owned cycle and the survey was run before drafting).

## 5. Step 4.6 Scoped Inventory Results

| # | Item | Result | Source / evidence |
|---|---|---|---|
| 1 | `Rule.ports` field | `Rule.ports: Mapping[str, Var]`; required, non-empty; validated against where free-vars at construction. | `src/factgraph/application/protocol/rule.py:58`, `:70-91`. |
| 2 | `Rule.port_types` property | Returns `MappingProxyType[str, PortType]`; inferred at construction. | `src/factgraph/application/protocol/rule.py:102-104`, `:96`. |
| 3 | `PortType` dataclass | Fields `kind: Literal["entity_ref", "value"]` and `entity_type: str | None`. | `src/factgraph/application/protocol/rule.py:36-39`. |
| 4 | Port type inference | `Entity(var)` atom -> `PortType("entity_ref", entity_type="<Entity>")`; otherwise `PortType("value", None)`. Verified live: `{user: entity_ref/User, region: value/None}`. | `src/factgraph/application/protocol/rule.py:508-535` (`_infer_port_types`, `_find_entity_ref_type`). |
| 5 | `Rule.as_(alias=None)` | Returns `RuleOccurrence`; default alias = `rule.id`. **Default alias fails for ids with `:` etc.** because alias regex is `[A-Za-z][A-Za-z0-9_]*`. Verified: `R1.as_()` with `id="User:exists"` raises `RuleValidationError: occurrence alias must match [A-Za-z][A-Za-z0-9_]*`. | `src/factgraph/application/protocol/rule.py:130-132`, `:250-255`. |
| 6 | `RuleOccurrence.port(name)` | Returns `RulePortRef`; rejects names not in `rule.ports`. | `src/factgraph/application/protocol/rule.py:199-209`. |
| 7 | `RuleOccurrence.__getattr__` proxy | `occ.port_name` forwards to `occ.port("port_name")`; raises `AttributeError` for unknown ports. | `src/factgraph/application/protocol/rule.py:221-227`. |
| 8 | `RulePortRef` fields | `occurrence_alias`, `rule_id`, `port_name`, `var`, `port_type`. | `src/factgraph/application/protocol/rule.py:170-175`. |
| 9 | `RulePortRef.eq(other)` | Returns `RuleJoinConstraint`; rejects same-occurrence pairs; rejects non-`RulePortRef`. | `src/factgraph/application/protocol/rule.py:180-186`. |
| 10 | `Rule.__and__` / `__or__` | Both shipped; return `_AndGroup` / `_OrGroup`. `__bool__` raises `ExplicitBoolError`. | `src/factgraph/application/protocol/rule.py:153-166`. |
| 11 | `RuleExpr.all(*operands)` / `.any(*operands)` | Factory methods returning `_AndGroup` / `_OrGroup`. | `src/factgraph/application/protocol/rule_expr.py` (verified live). |
| 12 | `_AndGroup.join_by_ports(*names)` | Resolves same-named ports across the group's direct AND children. Rejects empty name list, non-string names, names not present in ≥2 occurrences. | `src/factgraph/application/protocol/rule_expr.py:113-114`, `:241-281`. |
| 13 | `_AndGroup.join(constraint)` | Takes one or more `RuleJoinConstraint`; validates against AND-spine reachable. | `src/factgraph/application/protocol/rule_expr.py` (verified live). |
| 14 | `_OrGroup.join_by_ports` / `.join` | Both raise `RuleExprError: RuleExpr joins must be attached to AND groups; distribute joins into OR branches`. | `src/factgraph/application/protocol/rule_expr.py:128-130`. |
| 15 | Single `RuleOccurrence` `.join(...)` | `AttributeError` (no `join` method on `RuleOccurrence`). | Verified live; `RuleOccurrence` defines only `port`, not `join`. |
| 16 | Same-named ports without join | Raises `RuleExprError: declared port 'X' is ambiguous across occurrences: a, b` at evaluate time. Design §3.6 line 188 said "independent"; shipped is stricter. | Verified live with `(u_occ & o_occ)` having shared `region` port. |
| 17 | `Rule.projection(*port_names)` | Constructs a synthetic `Rule` with `id=__factgraph_projection__<hash>`; **`evaluate(..., head=projection)` raises `WhereValidationError: target predicate not found: __factgraph_projection__<hash>`** in the real evaluator. Tests only exercise it under `patch("factgraph.sdk.store.evaluate_derivation_plans", ...)`. | `src/factgraph/application/protocol/rule.py:134-151`; `tests/sdk/test_rule_expr_evaluate.py:162-170`. |
| 18 | `head=rule` arity invariant | `rule.id` must match a real predicate; `len(rule.ports)` must equal that predicate's `arg_specs` count. Otherwise raises `WhereValidationError: head_vars length must match target arg_specs`. | Verified live with 1-port rule against 2-arg predicate. |
| 19 | Cross-rule head with same-id occurrence | If `head` is a Rule with the same id as an in-expr occurrence but different `content_digest`, raises `RuleExprError: head rule '<id>' matches an expression occurrence with a different content digest`. Workaround: use the exact same Rule template as head, or pick a different template whose id+arity fits. | Verified live with `(user_exists.as_("a") & user_in_region.as_("b"))` heading on either of them. |
| 20 | `desc="%port_name"` rendering | `Rule.render_desc(bindings=None)` returns unbound form like `"user <user> lives in <region>"`; with bindings returns the substituted string. Construction rejects `%non_port` with `RuleValidationError: desc references undeclared port: <name>`. | `src/factgraph/application/protocol/rule.py:115-128`, `:239-247`. Verified live. |
| 21 | Per-port type from same-name port | Same-named ports across rules with **different `PortType`** would also fail join; but our common case is same-named ports with same `port_type`, which `.join_by_ports` handles. | `src/factgraph/application/protocol/rule_expr.py:319-328`. |
| 22 | `Rule.atom_ids` | Property returning `("<rule_id>:atom_0", ...)`; used by inspect / evidence. | `src/factgraph/application/protocol/rule.py:98-100`. Not taught in quickstart this cycle. |

### Drift findings (recorded as design vs shipped)

- **D1** Design §3.6 line 188 says "同名 port 不自动 join,默认为 independent existential variables". Shipped behavior is stricter — same-named ports across occurrences raise `RuleExprError: declared port 'X' is ambiguous across occurrences`. Quickstart will teach shipped behavior; design wording is from an earlier stage of the design point.
- **D2** Design §3.7 (line 234-259) treats `Rule.projection` as an inspection / advanced helper. Shipped behavior matches: `evaluate(..., head=Rule.projection(...))` raises `WhereValidationError: target predicate not found` because the projection id is not a real predicate. Tests only cover it under mocked `evaluate_derivation_plans`. Quickstart will not teach `Rule.projection` as an eval head.

### Scoped decisions

- Teach shipped same-named-port ambiguity reject, not the design-doc "independent" wording.
- Skip `Rule.projection(*names)` as an evaluate head; mention only as explicit non-goal in §C-5.
- Examples use real 1-arg (`Entity:exists`) and 2-arg (`entity:field`) predicate ids as heads. No projection-head examples.
- Cross-rule join example uses `user:region` + `order:region` so both rules' ids match real 2-arg predicates and either rule's underlying template can be used as `head=`.
- Same-named port reject behavior is shown via a deliberate negative example.
- AND-spine reachable invariant is summarized; full RuleExpr 9-item enumeration is out of scope.

## 6. Verification Plan

- Single Python program covering every code block in the new sections; assertions must pass.
- Negative examples must raise the stated errors (ambiguous-port, OR-group `.join`, undeclared-port).
- `git diff --check` clean.
- Only `docs/official/kernel/quickstart/rules-and-inferences.md` + blueprint pair touched.
- Dirty baseline preserved at 6 modified + 1 untracked.
- Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.

## 7. Review Checklist

- [x] Step 4.6 scoped inventory recorded before implementation.
- [x] Implementation uses shipped APIs only; `Rule.projection` is not taught as eval head.
- [x] All positive examples run end-to-end; all negative examples raise the documented error.
- [x] Same-named-port shipped behavior is taught, with the design-doc "independent" wording recorded as historical drift in this audit only (not in the user-facing doc).
- [x] No production files touched; dirty baseline preserved.

## 8. Closure Notes

Implemented with `4cdd4e54`.

Self-owned cycle summary:

- This cycle ran without cross-flip because Codex was on other tracks
  (T11.1 attach-view-scope). Owner and reviewer were both Claude.
- Inventory survey was run **before** drafting the blueprint, so Step
  4.6 was pre-loaded into the scoped state from the start (the audit
  was created directly in `scoped`, not `draft -> scoped`).
- Step 4.7 self-review took the form of a fresh-read pass over the
  rendered file plus the 18-assertion end-to-end smoke, with 5 of
  those 18 assertions specifically targeting the negative-path
  rejections (`RuleExprError` ambiguous-port, `RuleExprError` OR-group
  join, `AttributeError` single-occurrence join, `RuleValidationError`
  desc undeclared port, `WhereValidationError` projection target).

Final landed scope:

- `docs/official/kernel/quickstart/rules-and-inferences.md` gained
  three new sections (~330 LOC):
  - **Understanding ports** — semantics, type inference, `desc`.
  - **Composing rules with RuleExpr** — occurrences, operators,
    joins, AND-spine rejects, end-to-end example.
  - **Choosing the right head** — arity invariants, cross-rule head
    selection, `Rule.projection` non-eval-head call-out.
- Syntax checklist gained 8 new bullets.
- No other quickstart pages, no SDK module docs, no production code.

Drift records (kept in audit only, not in user-facing doc):

- D1: design §3.6 line 188 wording "independent existential variables"
  for same-named ports is not the shipped behavior. Shipped behavior
  is `RuleExprError: declared port 'X' is ambiguous across
  occurrences: <aliases>`. The doc teaches shipped behavior.
- D2: `Rule.projection(*names)` is exported as a `Rule` factory but is
  rejected by the real evaluator with `WhereValidationError: target
  predicate not found: __factgraph_projection__<hash>`. Tests only
  exercise it under `patch("factgraph.sdk.store.evaluate_derivation_plans", ...)`.
  The doc explicitly marks it as non-eval-head in v0.2.

Verification:

- `python` smoke: 18/18 assertions green, including 5 negative-path
  rejects. Ran on `v0.2.0-t11-1-attach-view-scope-2026-05-26`.
- `git diff --check`: clean.
- Diff scope: `docs/official/kernel/quickstart/rules-and-inferences.md`
  + blueprint pair.
- Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- Pre-existing 6 modified + 1 untracked dirty baseline preserved.

Deferred / non-goals (left for future cycles):

- Full enumeration of the design §3.6 nine RuleExpr commitments
  (occurrence binding semantics, evidence tree alias display, etc.).
- Path-dependent join distribution worked example beyond the summary
  sentence.
- Lifting same-named-port behavior from "shipped reject" to design's
  "independent" (would require shipped behavior change; out of scope
  for docs).
- Rewriting the existing Inference section.
