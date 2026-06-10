# FactPy Authoring Docs

This directory records the current implementation contract for
`src/factgraph/authoring`, targeting developers who need to understand
authoring preflight, publish, and registry workflows.

## Current documents

- `src/factgraph/authoring/docs/01_overview.md`
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
- The persisted declarative metadata contract is schema `version / tags`
  plus rule/derivation `version / description / tags` and rule-scoped
  `condition_weights`; schema `repr` templates are validated for
  explain-layer use, stored in Schema IR, and excluded from schema identity:
  - schema DSL goes through `Entity.Meta`
  - rule / derivation DSL goes through top-level constructor
    parameters
  - `condition_weights` is certainty/explain projection input keyed by
    `c{case}.c{condition}`. It is not an engine adapter parameter and
    does not enter `where` execution semantics. Future runtime
    configuration for this lane belongs in
    `SemanticsProfile.certainty_projection`.
- Public derivation authoring payloads reject engine-specific branch
  probability shortcuts such as `body_confidences`.
  - Public derivation authoring payloads also reject `engine_ext`.
  - Adapter-local extension types remain internal compiled bridges only.
  - Future SemanticsProfile rule projection owns the durable public
    shape.
