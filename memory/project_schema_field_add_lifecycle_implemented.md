# Schema Field Add Lifecycle Implemented

Date: 2026-05-13

Source commit: `925354c6`

Milestone branch:

- `origin/milestone/schema-field-add-lifecycle-2026-05-13 = 925354c6`

## Summary

The schema field-add lifecycle slice is implemented, archived, and published.
It is the second post-rc.3 schema mutation slice after additive entity-class
schema mutation.

## Landed Behavior

- `fg.schema.add(...)` accepts same-entity replacement classes that add
  non-identity fields.
- `SchemaAddResult` now includes `added_fields` alongside `added_entities`.
- Existing entity declarations must preserve identity fields, existing
  predicates, field type domains, cardinality, and relationship targets.
- Identity-field addition, field rewrite, field removal, predicate collision,
  and relationship schema changes remain rejected.
- After field-add, the replacement class object becomes active; superseded
  entity classes and descriptors raise `SDKStoreError`.
- Existing assertions are not backfilled. Missing added single-cardinality
  fields read as `None`; missing added multi-cardinality fields read as `()`.
- Re-adding an equivalent replacement class is an idempotent no-op with empty
  `added_entities` and `added_fields`.
- Ledger and registry schema digest anchors reuse the schema mutation lifecycle
  behavior.
- Workspace manifests remain save-time state: `fg.schema.add(...)` does not
  rewrite the manifest until explicit `fg.save(...)`.
- Existing saved rules/inferences remain loadable; new saved assets may
  reference added fields.

## Validation

- `test_schema_field_add_lifecycle.py`: 33/33 OK.
- Combined schema/lifecycle preservation + SDK invariant stack: 217/217 OK.
- `git diff --check`: clean.
- Post-publish verification confirmed `origin/master`, the milestone branch,
  release branch, and rc tags.

## Remaining Schema Work

- Relationship schema extension.
- Identity changes.
- Field defaults / nullability semantics / backfill.
- `fg.schema.delete(...)`, `fg.schema.deprecate(...)`, `fg.schema.update(...)`,
  and migration planning.
- Class-less dynamic `FactGraph.load(...)`.
