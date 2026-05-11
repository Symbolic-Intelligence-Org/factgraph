# FactPy Authoring Docs

This directory records the current implementation contract for
`src/kernel/authoring`, targeting developers who need to understand
authoring preflight, publish, and registry workflows.

## Current documents

- `src/kernel/authoring/docs/01_overview.md`
  - Authoring module responsibilities, public entry points, registry
    file layout, and boundaries with SDK / service / core.

## Conventions

- Documents in this directory reflect current implementation
  behavior, not standalone design drafts.
- When adding or adjusting public `authoring` entry points, update
  the corresponding doc and tests in the same change.
- If `authoring` continues into a second-phase consolidation, prefer
  updating the "recommended entry points" and "compatibility lane"
  sections in `01_overview.md` first.
- The declarative metadata contract is unified to `version /
  description / tags`:
  - schema DSL goes through `Entity.Meta`
  - rule / derivation DSL goes through top-level constructor
    parameters
  - These fields are authoring asset metadata; they do not
    participate in runtime semantics.
- Public derivation authoring payloads reject engine-specific branch
  probability shortcuts such as `body_confidences`.
  - Public derivation authoring payloads also reject `engine_ext`.
  - Adapter-local extension types remain internal compiled bridges only.
  - Future SemanticsProfile rule projection owns the durable public
    shape.
