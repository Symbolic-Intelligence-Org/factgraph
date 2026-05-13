# Task Blueprint Audit: Official Kernel Docstrings And Tutorials

- Blueprint: [2026-05-13_official-kernel-docstrings-and-tutorials.md](./2026-05-13_official-kernel-docstrings-and-tutorials.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Initial draft for official kernel documentation slice: public SDK docstrings first, then canonical Markdown tutorial tree under `docs/official/kernel/`. |
| 2026-05-13 | draft | Draft clarified | Added explicit selected-method docstring checklist, docstring gate scope, initial coverage snapshot, Diátaxis section boundaries, and deferred Markdown doctest harness. |
| 2026-05-13 | draft | Per-document cadence added | Added D15/D16, G1 gate specifics, Page Brief template, per-document commit cadence, and multi-session completion boundary. |

## Decision Notes

- 2026-05-13: Old public docs are not compatibility constraints because the
  product has not shipped yet. They may inform style, but current code and
  module docs are the source of truth.
- 2026-05-13: The release artifact is kernel-only. Official tutorial docs
  should not teach service, agent, extraction, domains, or HTTP routes as part
  of the `factpy-kernel` public release surface.
- 2026-05-13: Public API docstrings are treated as part of the user
  documentation layer because IDE hover text is a first-contact learning path.
