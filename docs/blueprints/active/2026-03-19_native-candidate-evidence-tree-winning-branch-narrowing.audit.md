# Task Blueprint Audit: Native Candidate Evidence Tree Winning-Branch Narrowing

- Blueprint: [2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened an implementation-facing draft for winning-branch narrowing after the semantics blueprint reached `scoped`, with scope limited to support-capture narrowing, deterministic tie handling, and targeted tests. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after settling capture-local narrowing ownership, `source-order wins`, fail-fast behavior when no branch satisfies a final binding, and the targeted regression matrix for atom-kind re-checks and legacy fallback. |
| 2026-03-19 | implemented | Winning-branch narrowing landed | Implemented capture-local branch selection in `_support_capture`, narrowed `SupportArtifact` emission to the selected branch, updated `_evaluate.py` and `ruleref_substrate.py` to compute `selected_branch_index` before artifact capture, and validated the narrowed contract with targeted regressions plus existing recursive-proof/runtime tests. |
| 2026-03-19 | implemented | Docs synced | Updated core/service module docs so current truth now states that native candidate proof uses winning-branch narrowing with `source-order wins`, rather than deferred conservative all-branch capture. |

## Decision Notes

- 2026-03-19
  - Scope rule: this blueprint implements an already-frozen capability contract. It must not reopen winning-branch semantics, execution substrate DTOs, or tree taxonomy.
- 2026-03-19
  - Owner rule: winning-branch narrowing belongs in `core.store._support_capture`, not in tree readback, `_evaluate.py` orchestration, or candidate builders.
- 2026-03-19
  - Tie rule: if multiple branches satisfy the same final binding, first-round implementation must deterministically choose source-order first (`lowest branch_index wins`) rather than erroring or preserving multiple proofs.
- 2026-03-19
  - Test rule: implementation is not complete without direct regression coverage for single-branch no-op, multi-branch overlap, pred exclusion, `not`, ungroundable `ruleref`, arith mismatch, legacy fallback, and digest stability.
- 2026-03-19
  - Failure rule: a final binding with no satisfying branch is a capture contract violation, including the degenerate single-branch AND case after normalization. This should fail fast rather than be treated as an ordinary “no match”.
- 2026-03-19
  - Outcome rule: once narrowing lands, `derive_rule_ref_edges_for_binding(...)` no longer keeps the pre-narrowing `0-match => skip` behavior for the selected branch. A selected branch without an exact `row_support` match is treated as a contract violation and fails fast.
