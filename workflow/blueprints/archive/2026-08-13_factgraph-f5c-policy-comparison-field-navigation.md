# Task Blueprint: FactGraph F5C Policy comparison and field navigation

- Status: archived
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Decision: [Q12](../../design/decisions/active/2026-08-13_q12-policy-comparison-field-navigation-v0-decision.md)
- Audit log: [paired audit](./2026-08-13_factgraph-f5c-policy-comparison-field-navigation.audit.md)

## 1. Goal

Implement the narrow Policy-owned comparison contract from Q12 end to end:
AST, compiler/lowering, native Query execution, lineage, live Explain, captured
bundle evidence and Policy projection.

## 2. Boundaries

- The public Query API remains direct-port-only.
- No new evaluator, policy registry, Scenario evidence path or Agent API.
- Native ordering is `int`/`time` only.
- Existing persisted Policy/Run DTO shapes must remain decodable and sealed.

## 3. Implementation sequence

1. Add the structured AST and independent persisted compare/condition DTOs.
2. Compile branch-total conditions and thread trusted schema resolution through
   the direct-Policy Query target path.
3. Extend lowering traces, the native prober and the EvidenceTree without
   changing ordinary RuleExpr behavior.
4. Project compare evidence through Policy lineage and reconstruct it from a
   captured EvaluationRun bundle.
5. Add focused compiler, API, Explain, codec and replay regression tests.

## 4. Acceptance / outcome

- [x] Q12 acceptance criteria pass.
- [x] Focused test cohorts, lint, type checks and a clean diff check pass.
- [x] Independent adversarial review confirms no Rule-evidence contamination,
  partial-branch lowering or bundle partition shift.

## 5. Scope freeze

No syntax sugar that parses dotted paths is required for this slice.  The
canonical structured DTO is deliberately the first implementation surface;
ergonomic Policy-authoring helpers can be evaluated separately without changing
the compiler contract.

## 6. Outcome / Deviations

- The complete Q12 path is implemented: structured `PolicyCompare` and
  `PolicyFieldNavigation` values, schema-checked branch-total lowering, native
  direct-Policy Query execution, condition lineage, live Explain, captured
  bundle codec and detached Policy evidence projection.
- Public Query `bind` and `select` remain deliberately direct-port-only.  The
  slice does not add dotted-string syntax, multi-hop navigation, literals,
  external operators, registry persistence, Scenario/What-if or Agent APIs.
- Focused regressions passed (59 tests), as did application discovery (124)
  and SDK discovery (180). Ruff, targeted mypy and `git diff --check` passed.
- Two independent fixed-state adversarial reviews returned CLEAR. One review
  initially noted that decoded bundle evidence needed an explicit round-trip
  test; that test was added before closure, so the final review state has no
  P0/P1/P2 findings.
- Current implementation truth is in the synchronized application, protocol,
  explain and SDK docs. This blueprint and its paired audit are archived
  together; archival neither implements the broader Query ergonomics nor starts
  any downstream What-if or Meander work.
