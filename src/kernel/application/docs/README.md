# FactPy Application Docs

This directory records the current implementation contract for
`src/kernel/application`. `application` is the canonical Python
runtime authority on top of `core`; `sdk` is responsible for the
Python product surface, DSL authoring, and outward facade
compatibility.

> **Audience note**
>
> If you are writing ordinary Python product code and want to use
> `Entity` / `Field` / `Identity` classes, the Query DSL, snapshots,
> batches, or user-facing exceptions, read `src/kernel/sdk/docs/`
> first and start from `kernel.sdk`.
>
> This directory targets integration / automation / pipeline / RPC
> bridge authors: callers who may only hold JSON-like payloads,
> schema identity strings, field paths, and error DTOs, and who
> should not depend on SDK descriptors or Python DSL objects. What
> this directory records is the Layer 2 runtime contract beneath
> the SDK.

## Current documents

- `src/kernel/application/docs/01_overview_en.md`
  - English overview of the application module.
- `src/kernel/application/walker/docs/README.md`
  - Current implementation contract for the application-layer walker
    module.
- `src/kernel/application/schema_mutation_runtime.py`
  - Additive schema-extension validation and transition planning used by
    `fg.schema.add(...)`; application-first runtime module, documented in
    the application overview.

## Conventions

- Documents in this directory reflect current implementation
  behavior, not standalone design drafts.
- When adding or adjusting public `application` entry points, update
  the corresponding doc and tests in the same change.
- The application protocol does not accept SDK facade objects, SDK
  `Field` descriptors, or SDK DSL objects; SDK is responsible for
  lowering / adapting ergonomic inputs into application runtime DTOs.
