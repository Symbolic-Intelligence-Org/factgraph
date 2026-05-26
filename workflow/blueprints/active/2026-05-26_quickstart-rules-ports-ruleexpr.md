# Task Blueprint: Quickstart Rules Ports + RuleExpr Coverage

- Status: implemented
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M (predicted docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Claude
- Reviewer: Claude (self-owned; cross-flip unavailable this cycle)
- Related audit: `workflow/blueprints/active/2026-05-26_quickstart-rules-ports-ruleexpr.audit.md`
- Related modules:
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/application/protocol/rule_expr.py`
- Related docs:
  - `docs/official/kernel/quickstart/rules-and-inferences.md`
- Active design source:
  - `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md`

## 0. Scope Locks

### In scope

- Expand `docs/official/kernel/quickstart/rules-and-inferences.md` to teach the shipped `ports` mechanism and the `RuleExpr` composition surface that ports unlock.
- Cover the three-variable distinction (free var / port / non-port free var) from design §3.6.
- Cover automatic `port_types` inference (`entity_ref` vs `value`).
- Cover the **ports ≠ head** invariant.
- Cover the `head=rule` runtime requirement (rule.id must match a real predicate; head ports must match predicate arg_specs).
- Cover the canonical `RuleExpr` composition path:
  - `rule.as_("alias") -> RuleOccurrence`;
  - `RuleOccurrence.port("name") -> RulePortRef` (and `__getattr__` proxy);
  - `RulePortRef.eq(other) -> RuleJoinConstraint`;
  - `(R1 & R2).join_by_ports("name", ...)`;
  - `(R1 & R2).join(constraint)`;
  - `RuleExpr.all(...)` / `RuleExpr.any(...)` factories;
  - `R1 & R2` / `R1 | R2` operator forms.
- Cover the shipped ambiguity behavior: **same-named ports across occurrences without explicit `.join_by_ports` or `.join` raise `RuleExprError: declared port 'X' is ambiguous across occurrences`**. (This is the shipped behavior; the design-point §3.6 line 188 "independent existential" wording predates the safer shipped rule.)
- Cover the AND-spine reachable invariant in summary form: `.join(...)` only attaches to AND groups; `OR.join(...)` and `single_rule.join(...)` are rejected.
- Cover `desc="%port_name"` rendering with `render_desc(bindings)`.
- Add a "What not to do" subsection covering the two shipped foot-guns and design drifts.

### Out of scope

- Production code changes.
- New public APIs.
- Rewriting the existing Inference section beyond surface alignment.
- Teaching `Rule.projection(*names)` as an `evaluate` head — verified `WhereValidationError: target predicate not found: __factgraph_projection__...`. It is currently only a RuleExpr inspection / mocked-evaluation helper, not a user-facing eval head.
- Full enumeration of design §3.6 nine RuleExpr commitments (Path-dependent distribute, occurrence binding semantics, evidence tree alias display, etc.) — quickstart shows the minimum useful subset.
- Changes to evidence.md, persistence.md, namespace-map.md, or other quickstart pages beyond cross-link nudges.
- Production tests; G7; service-route changes.
- The pre-existing 6 M + 1 untracked dirty baseline must remain isolated and unchanged.

### M-to-L / stop-and-amend triggers

Pause and amend if implementation requires:

- production code edits;
- changing shipped behavior so examples work;
- teaching `Rule.projection(*names)` as an evaluate head (verified non-working);
- introducing new public API surface;
- rewriting unrelated quickstart pages;
- touching the dirty baseline files.

## 1. Problem

`docs/official/kernel/quickstart/rules-and-inferences.md` currently shows `ports={...}` only as a syntactic field inside a single example and tells the reader nothing about:

- what `ports` actually does (three-variable distinction, type inference, ports ≠ head);
- why a rule has ports at all (cross-rule composition via `RuleExpr`);
- how to compose two rules and bind same-named ports (`.as_`, `.join_by_ports`, `.join(constraint)`);
- how `head=rule` interacts with the rule id and predicate arg_specs.

The shipped `RuleExpr` surface (`.as_`, `&`, `|`, `.join_by_ports`, `.join`, `RuleExpr.all`/`any`) is entirely absent from quickstart, so readers can construct a single `Rule` but cannot compose two without trial-and-error.

This is a documentation-only gap covering shipped API.

## 2. Inputs

Active design source:

- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.6 ports semantics + §3.7 desc rendering + RuleExpr commitments.

Primary implementation truth:

- `src/factgraph/application/protocol/rule.py`
  - `Rule.ports`, `Rule.port_types`, `Rule.as_`, `Rule.render_desc`, `Rule.__and__`, `Rule.__or__`;
  - `PortType(kind, entity_type)`;
  - `RuleOccurrence.port` + `__getattr__` proxy;
  - `RulePortRef.eq` + `RuleJoinConstraint`.
- `src/factgraph/application/protocol/rule_expr.py`
  - `_AndGroup.join_by_ports`, `_AndGroup.join`;
  - `RuleExpr.all`, `RuleExpr.any`;
  - ambiguity / AND-spine validation.

Inventory survey commands and results are recorded in the paired audit file §5.

## 3. Proposed Shape

Insert new sections into `docs/official/kernel/quickstart/rules-and-inferences.md` after the existing **Run a Rule** section and before **Use Query for one-off projections**.

Three new sections, all teaching shipped behavior:

### §A `Understanding ports`

1. Three-variable distinction in plain English:
   - free var (anything in `where`)
   - port (free var explicitly declared in `ports={...}`)
   - non-port free var (existential witness only; cannot be joined cross-rule)
2. `port_types` is inferred automatically:
   - `Entity(var)` -> `PortType(kind="entity_ref", entity_type="<Entity>")`;
   - `Entity(var).field == value` -> port for `value` becomes `PortType(kind="value")`;
3. **ports ≠ head** invariant with one short example.
4. `head=rule` invariant: rule.id must match a real predicate; head ports must match predicate arg_specs.
5. `desc="%port_name"` and `render_desc(bindings)` — short example.
6. What rejects:
   - non-port `%` interpolation -> `RuleValidationError: desc references undeclared port`;
   - port declared but Var not in where -> `RuleValidationError: ports[...] Var must appear in where`;
   - empty ports -> `RuleValidationError: ports must be non-empty Mapping[str, Var]`.

### §B `Composing rules with RuleExpr`

Motivate by example: a `user_region` rule + an `order_region` rule. Show that a single rule cannot ask "users who placed an order in their own region" — that needs composition.

1. `rule.as_("alias")` -> `RuleOccurrence`. Note that the default alias is `rule.id`, which fails for ids containing `:` (e.g. `User:exists`). Recommend explicit aliases.
2. `R1 & R2` and `RuleExpr.all(R1, R2)`; `R1 | R2` and `RuleExpr.any(R1, R2)`.
3. **Same-named ports raise without explicit join** — show the `RuleExprError: declared port 'region' is ambiguous across occurrences: o_, u_` failure mode so readers know it is shipped behavior.
4. `(R1 & R2).join_by_ports("region")` — the common case.
5. `(R1 & R2).join(R1.region.eq(R2.region))` — when port names differ.
6. AND-spine summary:
   - `single_rule.join(...)` -> `AttributeError` (not a method);
   - `(R1 | R2).join(...)` -> `RuleExprError: RuleExpr joins must be attached to AND groups`;
   - distribute path-dependent joins manually across OR branches.
7. End-to-end runnable example with cross-rule join + `head=` selection.

### §C `Choosing the right head`

1. The simplest head: `head=rule` reuses the rule as both body and head; rule.id must match a real predicate, and `len(rule.ports) == len(predicate.arg_specs)`.
2. Use a 1-arg predicate (`Entity:exists`) when the rule has a single port; use a 2-arg field predicate (`entity:field`) when the rule has two matching ports.
3. The result claim's name equals the head rule's id (rows have `claim.name == head.id`).
4. Cross-rule composition picks one of the participating rules' underlying templates as head. Note that `head=rule` and an occurrence `rule.as_("alias")` of the same template inside the expression are valid; an unrelated head with a different content_digest raises `RuleExprError: head rule '...' matches an expression occurrence with a different content digest`.
5. Explicit non-goal: `Rule.projection(*names)` is **not** an evaluate head in v0.2 — it is reserved for inspection / advanced use. Quickstart skips it.

### Syntax checklist additions

- `rule.as_("alias")` returns a `RuleOccurrence`; pass it into `&` / `|`.
- Same-named ports must be reconciled with `.join_by_ports(...)` or `.join(...)`; the SDK rejects ambiguity at construction time.
- `desc="%port_name"` only references declared ports.
- `head=rule` requires `rule.id` to be a real predicate id with matching arg arity.

## 4. Expected Code / Docs Changes

Docs-only:

- `docs/official/kernel/quickstart/rules-and-inferences.md` (+~200 LOC; insert 3 new sections + extend syntax checklist).

No production files. No other docs files modified in this slice.

## 5. Tests / Verification

- Run every code block in the new sections as one Python program (extended end-to-end smoke).
- Verify all assertions pass.
- Verify the negative examples actually raise the stated errors (ambiguous-port, AND-spine, undeclared-port).
- `git diff --check` clean; no production files touched; dirty baseline preserved.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Same-named ports example claims "independent" per design but shipped is "ambiguous reject" | Teach shipped behavior; cite design as historical context only if needed. |
| `Rule.projection` slips in as a head | Explicitly flag as non-eval head in §C-5. |
| Cross-rule join example needs a head whose arity matches | Use `user:region` / `order:region` two-arg field predicates. |
| Section creep into Inference reorganization | Keep all edits to insertion + checklist additions; do not touch existing Inference paragraphs. |

## 7. Implementation Plan

1. (this commit) Open scoped blueprint pair with API surface inventory locked.
2. Draft the three new sections in `rules-and-inferences.md`.
3. Run extended end-to-end smoke covering every code block in the new sections.
4. Self-review (fresh-read pass) — look for stale signatures, missed assertions, off-by-one port counts.
5. Self-fix if needed.
6. Closure + archive.

## 8. Reviewer Focus

Self-review must verify:

- every code block runs end-to-end against the actual SDK;
- the same-named-port reject is documented as shipped behavior, not as theoretical;
- `Rule.projection` is explicitly NOT taught as an eval head;
- the AND-spine reachable summary is consistent with the shipped error messages;
- the `head=rule` arity rule is stated precisely;
- no production file edits leak into the diff.

## 9. Acceptance

- [ ] `rules-and-inferences.md` gains §"Understanding ports", §"Composing rules with RuleExpr", §"Choosing the right head" sections.
- [ ] All new code blocks run end-to-end (verified by single extended smoke).
- [ ] All claimed errors are demonstrably raised by the SDK.
- [ ] `Rule.projection` is documented as non-eval head, not as a recommended path.
- [ ] Syntax checklist gains 4 new bullets.
- [ ] Diff stays within `docs/official/kernel/quickstart/rules-and-inferences.md` and the blueprint pair.
- [ ] Dirty baseline preserved; no production file changes.

## 10. Outcome / Deviations

Implemented in `4cdd4e54` after blueprint pair `ee14773e` (scoped with
inventory pre-locked) and branch-label correction `10f36b6d`.

Landed documentation:

- `docs/official/kernel/quickstart/rules-and-inferences.md` +330 LOC.
- Three new top-level sections inserted between "Run a Rule" and
  "Use Query for one-off projections":
  - **Understanding ports** — three-variable distinction; `port_types`
    inference; ports ≠ head invariant; `desc="%port_name"` rendering;
    undeclared-port reject example.
  - **Composing rules with RuleExpr** — `rule.as_("alias")` with the
    default-alias-on-colon-id foot-gun; port access (method + proxy);
    `&` / `|` and `RuleExpr.all` / `.any` equivalence; shipped
    same-named-port ambiguous reject; `.join_by_ports`; `.join(eq)`;
    AND-spine reachable rejects for single-occurrence and OR-group; full
    end-to-end cross-rule example.
  - **Choosing the right head** — `head.id` must match a real predicate;
    `len(head.ports) == arg_specs` count; 1-port -> Entity:exists,
    2-port -> entity:field; cross-rule expressions select one
    in-expression template; explicit non-goal flagging that
    `Rule.projection(*names)` is not an evaluate head in v0.2.
- Syntax checklist extended with 8 new bullets covering ports,
  `port_types`, `desc`, `rule.as_`, `&` / `|`, `.join_by_ports`,
  `.join`, AND-spine reachable, and the `head=rule` arity invariant.

Verification:

- 18-assertion end-to-end smoke ran against the live SDK on the actual
  branch (`v0.2.0-t11-1-attach-view-scope-2026-05-26`):
  - positive: `port_types` shape; `render_desc` bound and unbound; cross-rule
    join_by_ports count=2 and count=3 via either head; explicit `.join(eq)`;
    1-port head; 2-port head.
  - negative (raise verified): `desc` undeclared port; default alias on
    id with `:`; same-named ports ambiguous; single-occurrence
    `.join` AttributeError; OR-group `.join` reject;
    `Rule.projection` non-eval-head reject.
- `git diff --check` clean.
- Diff stays within `docs/official/kernel/quickstart/rules-and-inferences.md`
  and the blueprint pair files.
- Pre-existing 6 M + 1 untracked dirty baseline preserved end-to-end.
- Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged
  throughout.

Deviations and notes:

- Two design vs shipped drifts were teaching points:
  - D1 (design §3.6 line 188 "independent" vs shipped "ambiguous
    reject"): doc teaches shipped behavior; the design wording is
    captured only in the audit, not in the user-facing page.
  - D2 (`Rule.projection` documented in design as projection head but
    rejected by the real evaluator): doc explicitly flags this as
    non-eval-head in §C-5; design wording is captured in the audit.
- Branch label initially mislabeled as
  `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`; corrected to
  the actual `v0.2.0-t11-1-attach-view-scope-2026-05-26` in commit
  `10f36b6d`.
- Cycle ran self-owned (Codex working other tracks). Cross-flip review
  was unavailable; self-review compensated via fresh-read pass over the
  rendered file plus the 18-assertion smoke, including 5 negative-path
  assertions specifically targeting `RuleExprError` /
  `RuleValidationError` / `AttributeError` / `WhereValidationError`.
