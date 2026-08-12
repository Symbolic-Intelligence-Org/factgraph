# Task Blueprint: FactGraph EvaluationQuery projection

- Status: implemented
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
- Added production Python is capped at 650 lines; the final 150 lines are
  reserved for review-required integrity and collision guards, not new features.

## 3. Implementation Plan

1. Add compact EvaluationQuery protocol values and typed errors.
2. Extend private RuleExpr plans with explicit constant bindings and head links while preserving empty/default legacy behavior.
3. Compile/query-pin Policy, address space and schema; normalize values and emit total per-branch sources.
4. Add focused adversarial and legacy-compatibility tests plus minimal application docs.
5. Run focused suite, Ruff, targeted mypy, diff/cap checks and internal adversarial review.
6. Hand a bounded read-only review packet to the user's independent Agent before lifecycle closure.

## 4. Acceptance

- [x] Protocol shape, duplicate and ordering behavior is tested.
- [x] Policy/address/schema/staleness checks are fail-closed.
- [x] Identity encoding ignores caller-supplied encoded refs; scalar values are canonical.
- [x] DNF copies receive exact bind and projection sources; partial sources reject.
- [x] Explicit alias projection and query-aware probe seeds are tested.
- [x] Query materialization is inspectable but performs no engine call.
- [x] F1/F2A/F2B and legacy RuleExpr/evaluate/Explain tests remain green.
- [x] Static checks and 650-line production cap pass.

## 5. Outcome / Deviations

- Implementation `a8d91871` and current-truth docs `c0d2face` add the typed
  `EvaluationQuery` protocol, deterministic compiler and exact branch-local
  bind/projection metadata without entering engine execution.
- Production Python is 649 gross additions relative to `afdd9e7e`, within the
  amended 650-line stop. The 500-to-650 amendment `7f68d5e8` was consumed only
  by review-required artifact-integrity, generated-variable-collision and
  projection-namespace guards; no wider product surface was added.
- The final internal focused cohort is 310 tests passing. Ruff, targeted mypy
  and `git diff --check` pass. Broad discovery retains the unchanged
  `service.static_ui` import of absent `render_evidence_graph_html`; it is
  outside this slice and was present at the base commit.
- Three internal adversarial reviews returned CLEAR. The user's independent
  read-only review repeated a 251-test project cohort and static checks, added
  32 passing adversarial probes, and returned CLEAR with zero P0/P1 and one
  non-blocking P2 boundary note.
- That P2 does not identify an inconsistent splice: compiler-issued digests
  detect inconsistent in-process artifacts but are not authentication or a
  MAC. Current-truth docs now state that any future cross-trust codec must
  recompile authenticated source inputs or add explicit authentication.
- No contract deviation remains. Existing Query surfaces, engine execution,
  config/snapshot, rows, expectations, What-if, SDK and Meander remain
  explicitly deferred.
- Archive intent: move this blueprint and its paired audit together after this
  closure commit.
