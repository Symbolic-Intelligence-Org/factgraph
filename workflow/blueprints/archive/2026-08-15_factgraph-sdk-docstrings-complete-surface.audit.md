# Task Blueprint Audit: FactGraph complete public SDK docstring surface

- Blueprint: [2026-08-15_factgraph-sdk-docstrings-complete-surface.md](./2026-08-15_factgraph-sdk-docstrings-complete-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | audit | Complete public census started | 208 exported names; 312 exported-class public members; 155 missing member docstrings and 46 terse members before remediation. |
| 2026-08-15 | implementing | Scope expanded from representative to exhaustive | Coverage is defined mechanically from `factgraph.sdk.__all__` plus concrete `FactGraph` namespaces. |
| 2026-08-15 | implemented | Complete public census closed | 208 exports, 312 exported-class members and 52 namespace members now report zero missing docstrings. Query construction and all Query terminals are explicitly pinned. |
| 2026-08-15 | verification | Full regression and hygiene completed | 782 tests + 816 subtests passed; Ruff check, focused mypy and diff-check passed. Existing formatter debt and two dynamic-metaclass diagnostics in `sdk/schema.py` remain unchanged. |
| 2026-08-15 | corrective audit | User review reopened the slice | Presence-only coverage missed the non-exported V2 invocation returned by `query.plan(...)`, and the complete Product example used only an in-memory fixture instead of teaching Database ownership. |
| 2026-08-15 | implementing | Workflow-level contract added | Direct/staged Rule/Function/Policy builders, Scenario/profile builds, all Query terminals, V2 `run`, row-explicit Explain, and Database create/load/attach/close/head are explicitly pinned. |
| 2026-08-15 | example verification | Complete Product notebook executed | 15/15 code cells executed under the real `factpy` kernel. Durable create/load retained facts; caller-owned attach advanced the Database and remained open after facade close. |
| 2026-08-15 | final verification | Corrective scope closed | 783 tests + 838 subtests passed; focused docstring/quickstart cohort 7 + 656 subtests; Ruff, focused mypy/formatter and diff-check passed. |
| 2026-08-15 | hover audit | Fluent return types corrected | `fg.*_builder`, `fg.build_*`, `fg.scenario`, and `fg.query` no longer return `Any`; Query planning exposes its V1/V2 invocation types, preserving hover/completion through `.build()` and `.run()`. |
| 2026-08-15 | re-verification | Hover correction green | 784 tests + 853 subtests passed; the docstring contract includes 15 concrete-return-type subtests. |
| 2026-08-15 | archived | Blueprint pair archived | Complete-surface census, concrete fluent types and IDE-facing documentation were reverified before integration. |

## Classification

- Behavioral callables receive applicable Google-style `Args`, `Returns`,
  `Raises`, `Examples` and `Notes` sections.
- Immutable fields/properties receive a concise semantic description.
- Wire helpers state whether they validate, serialize or reconstruct sealed
  data; they do not imply business authority.
- Compatibility APIs state their V0/V1/V2 boundary rather than being silently
  described as the recommended Product path.

## Verification

- `tests/sdk/test_public_sdk_docstrings.py` plus executable Product quickstart:
  7 passed, 656 subtests.
- Application + SDK compatibility cohort: 784 passed, 853 subtests.
- Final runtime census: 0 missing exports, 0 missing exported-class members,
  0 missing namespace members.
- Ruff check passed over every module changed for the docstring remediation.
- Focused mypy passed over the typed SDK authoring/query/docstring-test slice.
- `git diff --check` passed.

The Product notebook was also executed in-place with the real `factpy`
kernel: all 15 code cells completed without error outputs.
