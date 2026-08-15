# Task Blueprint Audit: FactGraph public SDK docstrings

- Blueprint: [2026-08-15_factgraph-sdk-docstrings.md](./2026-08-15_factgraph-sdk-docstrings.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | audit | Public docstring inventory started | Product and namespace entry points mix terse, legacy and implementation-facing styles. |
| 2026-08-15 | scoped | Google-style plus FactGraph contract sections adopted | User approved direct implementation across the public SDK facade. |
| 2026-08-15 | implementing | Public SDK docstrings and contract tests added | Covered lifecycle/writes, Product authoring, Query, Scenario/profile, Result/Explain and replay without signature changes. |
| 2026-08-15 | implemented | Verification completed | 2 docstring tests + 38 subtests; integrated application/SDK cohort 779 + 220 subtests; Ruff, mypy and diff-check clean. |
| 2026-08-15 | superseded | Representative coverage was not complete-surface coverage | User review identified Query/builder-facing documentation gaps. A full `factgraph.sdk.__all__` and reachable namespace census continues in the complete-surface blueprint. |

## Decision Notes

- “OpenAI-style” is treated as a clarity goal, not a separate parser format;
  Google-style supplies the stable Python structure.
- Full tutorials remain in `docs/quickstart`; docstrings provide one local
  example and link/concept guidance rather than duplicating chapters.
