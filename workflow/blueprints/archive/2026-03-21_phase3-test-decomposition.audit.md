# Task Blueprint Audit: Phase3 Test Decomposition

- Blueprint: [2026-03-21_phase3-test-decomposition.md](./2026-03-21_phase3-test-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | scoped | Blueprint created | 3-phase staged refactor: Phase 1 certainty (9 migrate + 6 new), Phase 2 evidence-tree (15 migrate), Phase 3 walkthrough/ECSS/sidecar/winning-branch (43 migrate across 4 files). Target: 10K→≤2.5K residual. |
| 2026-03-21 | scoped | Phase 1 implemented | Added `_test_helpers.py` + `test_certainty_explain_contracts.py`; migrated 9 certainty/confidence tests; added 6 new coverage tests; full suite now `206` tests green. |
| 2026-03-21 | scoped | Scope adjustment | `Account` fixture was intentionally left in `test_phase3_contracts_v1.py` because it is only consumed by the residual core/entity docstring tests; not promoted into shared helpers. |
| 2026-03-21 | scoped | Phase 2 implemented | Added `test_evidence_tree_explain_contracts.py`; migrated 15 evidence-tree / rule-trace / explain-route tests; `test_phase3_contracts_v1.py` reduced to `7,857` lines; full suite remains `206` tests green. |
| 2026-03-21 | scoped | Order-dependence fix | Phase 2 changed unittest discover order and exposed that fake Souffle evaluator tests were resetting the global engine registry to `None`; cleanup now restores the real `evaluate_store_engine` instead, keeping engine parity tests order-independent. |
| 2026-03-21 | implemented | Phase 3 implemented | Added `test_domain_walkthrough_contracts.py`, `test_ecss_compliance_contracts.py`, `test_winning_branch_rule_trace_contracts.py`, and `test_artifact_sidecar_contracts.py`; migrated all remaining capability-line tests and helper functions; `test_phase3_contracts_v1.py` reduced to `1,166` lines / `28` residual tests; full suite remains `206` tests green. |
| 2026-03-21 | implemented | Scope adjustment | Phase 3 actual extraction counts differed from the planning estimate because the contiguous capability blocks also contained adjacent support/rule-trace and legacy-package tests that belong with the same files; they were migrated with their owning capability line instead of being split again. |
| 2026-03-21 | implemented | Constant relocation fix | Walkthrough-specific predicate-id constants were initially carried into `test_artifact_sidecar_contracts.py` by the raw block move; they were then relocated into `test_domain_walkthrough_contracts.py` so walkthrough helpers and tests own their full module-level fixture surface. |

## Decision Notes

- Phase 1 合并了 P1 coverage gap（ValueError + tri-state explicit tests），因为在抽出 certainty tests 时成本最低
- helper module 用 `_test_helpers.py` 前缀 `_` 避免 unittest discover，不引入 pytest conftest
- 不消除 private API 调用——那是另一个独立治理任务
- Phase 3 拆成 4 个子文件而非 1 个"其他"桶，保持每文件单一 capability line 原则
- Fake engine evaluator tests must restore global engine state after each test; clearing to `None` is not stable once files are split and discover order changes
- Raw line-range extraction is acceptable for this task only because each moved block stayed within a single capability line and was immediately verified by full-suite execution
