# Task Blueprint: FactGraph EvaluationQuery projection

- Status: scoped
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F3A only.
- Inputs:
  - [`2026-08-12_q5a-evaluation-query-projection-v0-decision.md`](../../design/decisions/active/2026-08-12_q5a-evaluation-query-projection-v0-decision.md)
  - [`2026-08-12_q4b-managed-policy-v0-decision.md`](../../design/decisions/active/2026-08-12_q4b-managed-policy-v0-decision.md)
- Outputs / Downstream:
  - Application-layer query DTO, compiler artifact, focused tests and current-truth docs
- Related:
  - [`2026-08-12_factgraph-evaluation-query-projection.audit.md`](./2026-08-12_factgraph-evaluation-query-projection.audit.md)
- Related Modules:
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/`
- Audit Log:
  - [`2026-08-12_factgraph-evaluation-query-projection.audit.md`](./2026-08-12_factgraph-evaluation-query-projection.audit.md)
- Branch: `codex/v0.3.0-f3-policy-query-projection-2026-08-12`
- Base: `afdd9e7e`

## 1. Goal

Compile exact Policy-owned direct-port `bind/select` intent into a deterministic,
engine-neutral lowering artifact without entering execution or inventing a new
result model.

## 2. Invariants

- New public name is `EvaluationQuery`; the two shipped old Query surfaces stay untouched.
- Query pins one `CompiledPolicyV0`, exact address space and exact schema.
- Bindings are typed body constraints; selections are ordered truth-neutral projections.
- Every addressed occurrence exists in every DNF branch.
- Projection aliases map explicitly to branch-local vars; no name inference.
- Legacy lowering plans with no query metadata retain their exact canonical key and behavior.
- The output has no engine, config, snapshot, rows, completeness, expectations or Explain result.
- Added production Python is capped at 500 lines; crossing the cap stops implementation.

## 3. Implementation Plan

1. Add compact EvaluationQuery protocol values and typed errors.
2. Extend private RuleExpr plans with explicit constant bindings and head links while preserving empty/default legacy behavior.
3. Compile/query-pin Policy, address space and schema; normalize values and emit total per-branch sources.
4. Add focused adversarial and legacy-compatibility tests plus minimal application docs.
5. Run focused suite, Ruff, targeted mypy, diff/cap checks and internal adversarial review.
6. Hand a bounded read-only review packet to the user's independent Agent before lifecycle closure.

## 4. Acceptance

- [ ] Protocol shape, duplicate and ordering behavior is tested.
- [ ] Policy/address/schema/staleness checks are fail-closed.
- [ ] Identity encoding ignores caller-supplied encoded refs; scalar values are canonical.
- [ ] DNF copies receive exact bind and projection sources; partial sources reject.
- [ ] Explicit alias projection and query-aware probe seeds are tested.
- [ ] Query materialization is inspectable but performs no engine call.
- [ ] F1/F2A/F2B and legacy RuleExpr/evaluate/Explain tests remain green.
- [ ] Static checks and 500-line production cap pass.

## 5. Outcome / Deviations

- Pending implementation and independent review.
