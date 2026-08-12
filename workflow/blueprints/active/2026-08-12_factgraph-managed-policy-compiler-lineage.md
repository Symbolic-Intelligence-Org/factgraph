# Task Blueprint: FactGraph managed Policy compiler and lineage

- Status: implemented
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F2B only.
- Inputs:
  - [`2026-08-12_q4b-managed-policy-v0-decision.md`](../../design/decisions/active/2026-08-12_q4b-managed-policy-v0-decision.md)
  - [`2026-08-12_q4a-managed-rule-occurrence-address-decision.md`](../../design/decisions/active/2026-08-12_q4a-managed-rule-occurrence-address-decision.md)
- Outputs / Downstream:
  - Application-layer Policy values, compiler, structural lineage, focused tests and current-truth docs
- Related:
  - [`2026-08-12_factgraph-managed-policy-compiler-lineage.audit.md`](./2026-08-12_factgraph-managed-policy-compiler-lineage.audit.md)
- Related Modules:
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/`
- Related Docs:
  - `src/factgraph/application/docs/rule.md`
  - `src/factgraph/application/docs/README.md`
- Audit Log:
  - [`2026-08-12_factgraph-managed-policy-compiler-lineage.audit.md`](./2026-08-12_factgraph-managed-policy-compiler-lineage.audit.md)
- Branch: `codex/v0.3.0-f2b-policy-compiler-lineage-2026-08-12`
- Base: `9418d6dc`

## 1. Problem

Managed semantic ports and occurrence-qualified addresses now exist, but there
is no Policy value that can safely compose them. Raw RuleExpr permits a partial
join across `Any` and loses the authored alias when DNF lowering copies an
occurrence. Passing that behavior through would make Policy meaning and later
UI/Explain lineage ambiguous.

## 2. Goals

- Add the minimal `Policy`, `PolicyOccurrence`, `PolicyAll`, `PolicyAny` and
  `PolicyUnify` value surface.
- Compile only exact F2A address spaces and conservatively admitted Rules.
- Lower deterministically through the shipped RuleExpr body path.
- Reject partial constraints and static DNF overflow before engine execution.
- Produce total, bidirectional structural lineage without parsing repr or
  generated names.

## 3. Non-goals

- Compare, literal predicates or field navigation.
- Query/bind/select/expect, synthetic head, Evaluate, Explain or engine config.
- SDK/service/wire/persistence/registry/Package/Meander/Agent work.
- Not/Unless/priority/aggregate/temporal Policy semantics.
- Any change to legacy RuleExpr partial-join behavior.

## 4. Current Context

- `Rule.as_()` and `RulePortRef.eq()` own occurrence and equality mechanics.
- F2A owns exact address resolution and contract freshness.
- RuleExpr owns Boolean normalization, branch aliasing and alias-local Vars.
- Existing DNF normalization caps expansion at 32 and filters joins whose
  endpoints are missing in a branch.
- Existing lowering has no head-independent plan and no authored alias field.

## 5. Proposed Shape

```text
Policy AST + SemanticAddressSpace
  -> shape/admission/schema checks
  -> bounded DNF projection check
  -> checked Policy-to-RuleExpr adapter
  -> exact head-independent RuleExpr body lowering
  -> CompiledPolicyV0 + branch inventory + total PolicyLineage
```

The compiler does not execute the plan. A later Query slice will add the
projection-only head and runtime intent.

## 6. Boundaries And Invariants

- Policy occurrence aliases exactly equal the supplied address-space aliases;
  each appears once in the AST.
- All contracts pin one schema digest and remain current at compile time.
- Managed Rule v0 admits only top-level `PredAtom` and non-aggregate
  `CmpAtom(eq/ne/gt/ge/lt/le)`.
- `PolicyUnify` is direct-port, cross-occurrence, exact-endpoint equality only.
- A Unify is a direct `PolicyAll` child and both endpoints occur in every local
  branch. Partial applicability is a typed compile failure.
- DNF projected count is bounded and checked against 32 before structural
  lowering; no engine exists in this slice.
- All/Any canonicalization and Policy digest are input-order independent.
- Generated aliases retain explicit authored aliases internally and never
  become public semantic addresses.
- Every authored node has lowered targets; every emitted branch, occurrence,
  body-atom and Unify reference has an authored reverse origin.
- Existing lowering canonical keys, materialization, Evaluate and Explain stay
  byte/behavior compatible for legacy callers.
- Production additions under `src/factgraph/application/**/*.py`, including
  export edits and excluding tests/docs, are capped at 700 lines relative to
  `9418d6dc`. If the implementation needs a new comparison substrate or a
  second DNF algorithm, stop and split the slice.

## 7. Acceptance

- [x] Simple occurrence, All, Any and cross-occurrence Unify compile.
- [x] Same Rule under distinct aliases remains distinct and only explicit Unify joins it.
- [x] `a & (b | c)` with `Unify(a,b)` rejects; a constraint local to an `All(a,b)` branch compiles.
- [x] Entity/field mismatch, different semantic paths and self-Unify reject.
- [x] Not/In/Builtin/aggregate/unsupported comparison Rule bodies reject at admission.
- [x] Stale contracts, schema mismatch, alias mismatch and projection namespace reject distinctly.
- [x] 1, 32 and 33 branch fixtures assign the documented capability outcome.
- [x] One-to-many alias rewrite and body-atom/Unify lineage are total in both directions.
- [x] Reordered All/Any inputs produce identical digest, branches and lineage.
- [x] F1/F2A, RuleExpr/lowering and one evaluate→row→Explain regression remain green.
- [x] Ruff, targeted mypy and production-line cap pass.

## 8. Implementation Plan

1. Add the minimal immutable Policy AST and lineage DTOs.
2. Factor a private head-independent RuleExpr body plan and retain authored aliases during DNF rewriting.
3. Add the managed compiler with fail-closed admission, total-branch Unify checks, bounded DNF count and deterministic digest.
4. Add focused positive, adversarial, lineage and legacy-compatibility tests.
5. Update application Rule/module docs and exports.
6. Run focused and full verification, then hand an exact review packet to the user's independent Agent.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/docs/README.md`

## 10. Outcome / Deviations

- Implementation stack `93102d91`, `39f55922`, `cad037b8` and `e7680d47`
  adds the managed Policy value surface, exact F2A address-space compiler,
  head-independent RuleExpr body plan and machine-checkable bidirectional
  structural lineage.
- Production Python under `src/factgraph/application/**/*.py` is 699 additions
  and 10 deletions relative to `9418d6dc`, within the 700-added-line stop.
- The final focused F1/F2A/Policy/RuleExpr/lowering/evaluate/Explain cohort is
  248 tests passing. Ruff, targeted mypy and `git diff --check` pass.
- Broad unittest discovery found two unrelated import/collection failures: the
  unchanged `service.static_ui` import of absent
  `render_evidence_graph_html`, and the environment's pandas/numpy ABI failure
  while importing the PyReason test. Excluding exactly those two paths, the
  remainder ran 2,257 tests successfully with 32 skipped.
- Internal adversarial review found and corrected aggregate-term admission,
  invalid public/runtime lineage DTO states and crossed-origin reverse
  mappings. The final internal re-review returned CLEAR.
- The user's independent read-only review returned CLEAR with zero P0/P1/P2
  after the 248-test cohort, Ruff, mypy, diff/cap checks and 29 additional
  adversarial probes all passed.
- No contract deviation remains. Raw RuleExpr partial-join filtering is
  intentionally preserved while managed Policy rejects partial-branch Unify
  before lowering. Compare, Query/head, engine execution, SDK and Meander stay
  deferred.
- Archive intent: move this blueprint and its paired audit together after this
  closure commit.
