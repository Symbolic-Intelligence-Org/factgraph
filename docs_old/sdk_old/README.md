# FactPy SDK Docs (v1)

This folder is the code-aligned documentation for `src/factpy_kernel/sdk`.
It is meant to be the implementation reference for SDK behavior, not a conceptual blueprint.

## Scope

- Schema declarations: `Entity`, `Identity`, `Field`
- Write paths: `sdk.batch(...)`, `sdk.set/add/retract(...)`
- Read/write facade: `sdk.get/find/edit(...)`, `EntitySnapshot`, `EntityEditor`
- External ingest + provenance tooling: `sdk.ingest(...)`, `sdk.validate_provenance(...)`
- Rule/Derivation object DSL: `Rule`, `Derivation`, `RuleRef`, `Pred`, `Not`, `vars(...)`
- Registry facade: `SDKRegistry`

## Docs in this folder

- `src/factpy_kernel/sdk/docs/01_alignment_matrix.md`
  Current implementation matrix, supported boundaries, and deferred items.
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
  Practical reference for `batch/get/find/edit/ingest/provenance`.
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
  Object DSL syntax, lowering behavior, derivation materialization flow.

## Runtime constraints to remember

- `vars()` unpack mode is not available at runtime SDK level.
  Use:
  - `with vars("p", "c") as (p, c): ...` (recommended), or
  - `with vars() as V: p, c = V("p", "c")`
- `sdk.run(...)` / `sdk.evaluate(...)` do not accept string DSL in SDK v1.
  Use object DSL (`Rule` / `Derivation`) or compiled/spec dicts.
- There is no top-level `factpy_kernel.sdk.apply_schema_classes`.
  Use instance method: `SDKRegistry.apply_schema_classes(...)`.

## Contract style

When behavior differs between design intent and current implementation, docs in this folder follow current implementation.
For future changes, update these docs in the same PR as behavior changes.
