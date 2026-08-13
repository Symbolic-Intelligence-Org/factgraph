# Task Blueprint: FactGraph Query field-navigation continuous delivery

- Status: scoped
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Branch: `codex/v0.3.0-factgraph-whatif-v1-continuous-2026-08-13`
- Decision: [Q14](../../design/decisions/active/2026-08-13_q14-evaluation-query-field-navigation-v0-decision.md)
- Audit Log: [paired audit](./2026-08-13_factgraph-query-field-navigation-continuous.audit.md)

## 1. Problem

Direct-port Query selection leaves a read-only one-hop entity-field projection
outside the unified Query path. Q12 deliberately did not solve this because
Policy-owned navigation and Query-owned navigation have different identity and
evidence semantics.

## 2. Goals

- Add a typed, one-hop Query `select` navigation source without a string DSL.
- Compile it branch-totally into the existing native Query plan.
- Carry it faithfully through live Explain, F4 anchor/bundle/evidence/verify,
  expectations and Q13 ScenarioRun.
- Preserve direct-only public DTO and wire compatibility.

## 3. Non-goals

- No navigation in `bind`, no authored Policy change, no generic What-if,
  operator, authorization, Agent/Meander or non-native work.
- No relationship/multi-hop/multi-value/identity-field projection, null result
  semantics, complete-result semantics or schema-validity-as-authorization.

## 4. Proposed shape

Introduce a Query-owned navigation value and companion selection DTOs. Resolve
the base and field against the trusted address space/schema during Query
compilation, then insert a compiler-private field predicate lookup after Query
binds and before joins. Treat the atom as Query-owned evidence throughout the
live and detached paths.

## 5. Boundaries and invariants

- Existing direct DTO fields, legacy anchor/bundle shapes and Policy identity
  remain untouched.
- A navigation source must be branch-total and resolves only identity -> same
  entity, single scalar field.
- Missing field facts result in zero rows; they do not materialize `null` or
  `false`.
- Lowering, capture offsets, codec sealing and evidence reconstruction use one
  fixed atom order.
- Scenario inherits the identical plan; the effective side never masquerades
  as a captured ledger witness.

## 6. Acceptance

- [ ] Compiler and SDK contract cover valid and rejected source shapes.
- [ ] Query digest/sealing, native execution, value recovery and expectations
  cover mixed direct/navigation selection.
- [ ] Live Explain and detached F4 evidence partition navigation outside Policy
  lineage, and old direct-only capture remains valid.
- [ ] Scenario replacement of the navigated field works through detached
  explain/diff/verify with the correct source role.
- [ ] Focused, concentrated and application/SDK regression checks are clean;
  affected module docs describe only shipped v0 behavior.

## 7. Implementation plan

1. Add sealed protocol/compiled selection unions and exact compiler admission.
2. Extend lowering and live trace partitioning with Query-owned lookup atoms.
3. Extend anchor/bundle/codec/evidence/verification and expectation projection.
4. Add focused tests for direct Policy, Rule lift, branch failure, tamper,
   evidence, codec and Scenario inheritance; update docs.
5. Run concentrated checks and independent adversarial review, then record the
   outcome and archive the pair.

## 8. Docs to update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/protocol/docs/README.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 9. Outcome / deviations

To be completed after implementation and independent review.
