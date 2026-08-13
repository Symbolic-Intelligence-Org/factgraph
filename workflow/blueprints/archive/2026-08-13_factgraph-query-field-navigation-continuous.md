# Task Blueprint: FactGraph Query field-navigation continuous delivery

- Status: implemented
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

- [x] Compiler and SDK contract cover valid and rejected source shapes.
- [x] Query digest/sealing, native execution, value recovery and expectations
  cover mixed direct/navigation selection.
- [x] Live Explain and detached F4 evidence partition navigation outside Policy
  lineage, and old direct-only capture remains valid.
- [x] Scenario replacement of the navigated field works through detached
  explain/diff/verify with the correct source role.
- [x] Focused, concentrated and application/SDK regression checks are clean;
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

Delivered the bounded Query projection extension
`EvaluationQueryFieldNavigationV0` and its parallel navigation-selection
unions. `fg.query(...).select(...)` can now project exactly one field from an
identity port when the field belongs to the same entity, is single-valued,
scalar, and non-identity. `bind(...)` remains direct-port-only. The compiler
adds a Query-owned lookup after direct binds and before joins; it seals the
typed intent and branch map into the Query digest while leaving the Policy
digest, structure, and lineage unchanged.

The same selection flows through native result recovery, `expect_contains`,
live Explain, the EvaluationRun anchor/bundle codec/detached evidence and the
captured ScenarioRun path. Live Explain obtains the navigation base only from
the exact native `ProofReceipt`; it fails closed rather than inferring an
identity from a scalar. Missing field evidence produces a valid zero-row result
whose Run summary remains `not_asserted`, never a nullable or false result.

Verification: focused Query tests `36 passed`; full application discovery
`129 passed`; full SDK discovery `190 passed`; targeted `ruff --no-cache` and
`git diff --check` passed. Three independent read-only reviews found no P0/P1
issue. They led to permanent coverage for direct Policy navigation, an
identity-only Rule whose selected field is absent from its authored body, and
the zero-row missing-field case. Targeted mypy is not a clean repository gate:
it reports 571 pre-existing errors across 74 files, none introduced or isolated
by Q14.

Deliberate carry-forward: navigation remains select-only and native-only; no
relationship/multi-hop traversal, navigation binding, general QueryPlan,
operator/action, authorization, Agent/Meander, persistence, or broader
What-if grammar is introduced.
