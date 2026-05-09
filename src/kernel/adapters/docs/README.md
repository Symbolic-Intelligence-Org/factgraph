# FactPy Adapters Docs

This directory records the current implementation contract for
`src/kernel/adapters`, targeting developers who need to understand
the boundary between core and external execution / export engines.

## Current documents

- `src/kernel/adapters/docs/01_souffle_adapter.md`
  - Souffle adapter responsibilities, module breakdown, export /
    run path, and the boundary with core.
- `src/kernel/adapters/docs/02_problog_adapter.md`
  - ProbLog adapter responsibilities, export / execution / parse
    path, and the boundary with core.
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
  - PyReason adapter spike boundary, event-log trace shape, and
    comparative conclusions versus Souffle provenance.

## Conventions

- The `adapters` directory currently holds the `souffle`, `problog`,
  and `pyreason` (spike) adapters.
- When new engine adapters are added, follow the same convention
  and add a separate doc rather than merging all adapters into a
  single page.
