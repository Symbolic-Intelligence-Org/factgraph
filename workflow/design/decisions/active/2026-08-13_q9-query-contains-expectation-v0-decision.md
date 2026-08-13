# Q9 Decision: Query `contains_row` expectation v0

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: design constraint for F5B1 only.
- Inputs:
  - 2026-08-13 user authorization to complete F5B1, M0, and F5B2 in sequence.
  - [`2026-08-13_q8-unified-evaluation-query-target-v1-decision.md`](./2026-08-13_q8-unified-evaluation-query-target-v1-decision.md)
  - [`2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md`](./2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md)
  - [`2026-08-13_q7-scenario-field-substitution-v0-decision.md`](./2026-08-13_q7-scenario-field-substitution-v0-decision.md)
- Outputs / Downstream:
  - [`2026-08-13_factgraph-f5b1-query-expectation.md`](../../../blueprints/active/2026-08-13_factgraph-f5b1-query-expectation.md)
- Branch: `codex/v0.3.0-f5b1-query-expectation-2026-08-13`
- Base: `23dc25a8`

## 1. Problem

F5-Core lets callers ask a typed Rule-or-Policy Query and inspect rows, but it
does not let a caller state the narrow proposition that a projected row with
given selected values should occur.  Treating an empty row set as false would
overclaim a general closed-world or historical completeness contract.

## 2. Decision

F5B1 adds only `expect_contains(expectation_id, /, **selected_values)` to the
unified `fg.query(...)` builder.  It is a read-only observation over the exact
typed Query result: it changes neither the Policy, the Query's `query_digest`,
the lowering plan, row set, rows, nor the projection head.

The compiler resolves each expected value against an already-selected alias by
using the same schema-aware canonicalization as `bind`.  An expectation has at
least one selected alias, may constrain a subset of selections, and has a
unique identifier within one builder.  Its independently sealed compiled form
is committed by the targeted-Query wrapper seal.

The sole native evaluation pass attaches zero or more sealed
`ExpectationResultV0` values to the existing `EvaluateResult`.  The first
allowed kind is `contains_row`.  It has four explicit statuses:

| Status | Meaning |
| --- | --- |
| `satisfied` | At least one returned row matches every expected selected value. |
| `not_satisfied` | No row matches and this exact native run had complete enumeration. |
| `underdetermined` | No row matches but its evaluator completeness basis is not sufficient. |
| `unsupported` | A valid expectation cannot be evaluated under the declared execution capability. |

F5B1's public path is deliberately narrower than the DTO: native execution
has no limit, pagination, early stop, result trimming, registry, config, or
premise filters; it evaluates the stored plan against the finite projected
relation and guards artifact/view state before and after the call.  A missing
match there is therefore `not_satisfied` with the result-local basis
`complete_native_enumeration_v0`.  This says only that exact live run was fully
enumerated.  It does **not** say the world is closed, sources are authoritative
or fresh, a historical snapshot was captured, replay is possible, or another
engine would agree.

`EvaluationRunSummaryAnchorV0.completeness` remains exactly `unknown`: it is
an F4 identity/replay statement, not an execution enumerator assertion.

## 3. Non-scope

- `expect_exists`, generic `expect`, count/set/bag modes, empty-select modes,
  pagination, limits, early-stop, ordering or continuation.
- Any change to `EvaluateResult.exists()`, which remains plain `bool(rows)`.
- Expectation Explain, negative EvidenceGraphs, result-summary evidence, or
  product allow/deny/authorization decisions.
- `capture=` or `scenario=` combined with an expectation.  F4's bundle codec
  does not yet capture expectation inventory, and F5A Scenario has no
  ledger-backed evidence/anchor contract.
- Raw compiled Query expectations, non-native/config engines, premise filters,
  wire codecs, Meander, Agent, source authority, Packages, Actions, or Decide.

## 4. Consequences

The result is a useful, bounded logical verification seam for the later M0
server-owned shadow contract.  It does not yet make Meander a product verdict
engine or make a Scenario result a general What-if proof.

## 5. Acceptance Criteria

- [ ] Typed `contains_row` expectations compile only on the unified Query
  facade and are sealed with the targeted Query identity.
- [ ] Positive matches are `satisfied`; native complete non-matches are
  `not_satisfied`; pure evaluator branches preserve `underdetermined` and
  `unsupported` without conflating them with invalid requests.
- [ ] The result attachment binds the exact query/wrapper/result/anchor and
  matching row ids, while F4 summary semantics stay unchanged.
- [ ] `capture + expectation`, `scenario + expectation`, invalid aliases,
  malformed values, stale/spliced wrappers and unsupported execution profiles
  fail closed before an outcome is emitted.
- [ ] Existing Query/F4/F5A behavior and module docs remain aligned.

## 6. Decision Record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | adopted | Narrow expectation contract selected | Independent source audit confirmed native complete enumeration can be an explicitly local basis, while F4 summary and Scenario boundaries must remain unchanged. |
