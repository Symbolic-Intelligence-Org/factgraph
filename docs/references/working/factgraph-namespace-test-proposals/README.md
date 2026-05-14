# factgraph Namespace Test Proposals

Status: review packet, not active test suite.

This directory contains proposed test changes for the scoped blueprint:

- `docs/blueprints/active/2026-05-14_factgraph-namespace-test-coverage.md`
- `docs/blueprints/active/2026-05-14_factgraph-namespace-test-coverage.audit.md`

The complete namespace inventory comes from:

- `docs/official/kernel/quickstart/namespace-map.md`

## Review Rule

Files in this directory are working reference material. They are not part of
root `tests/`, are not discovered by unittest, and are not release-gate truth.

After review, accepted proposals can be migrated into root `tests/` as focused
test files or edits. Rejected or deferred proposals should stay here with review
notes or be removed in the implementation slice.

## Packet Contents

- `stale-conflict.md`
  - `fg.assertions.active()`
  - `fg.assertions.all()`
  - direct `fg.assertions.field(Field)` coverage
- `test_sdk_fg_assertions_namespace.py`
  - review-only proposed replacement/update for root
    `tests/test_sdk_fg_assertions_namespace.py`
- `missing.md`
  - `fg.schema.validate_provenance(...)`
  - `fg.write.edit(...)`
  - `fg.eval.accept_many(...)`
  - `fg.audit.explain_fact(...)`
  - `fg.audit.conflicts(...)`
  - `fg.package.run_package(...)`
- `test_factgraph_namespace_missing.py`
  - review-only proposed new root test file for Missing surfaces
- `flat-only.md`
  - `fg.schema.ingest(...)`
  - `fg.write.retract(...)`
  - `fg.eval.accept(...)`
  - `fg.what_if.diagnose(...)`
  - `fg.what_if.why_not(...)`
  - `fg.audit.diff_proof_frames(...)`
- `test_factgraph_namespace_flat_only.py`
  - review-only proposed new root test file for Flat-only namespace smoke
    coverage

The `.md` files explain evidence, scope, and review decisions. The `.py` files
are concrete migration candidates for reviewers who want to inspect the actual
test code shape.

## Sanity Check

The proposed Python files can be run in place before migration:

```bash
PYTHONPATH=src python -m unittest discover -s docs/references/working/factgraph-namespace-test-proposals -p 'test_*.py'
```

Expected result in this scoped packet: `Ran 21 tests ... OK`.

## Deferred

The scoped blueprint defers:

- NS-shape-only gaps, because alias parity and flat behavior tests already
  cover behavior.
- Light-NS coverage expansion, because those paths already have at least one
  namespace-form exerciser.

## Related Note

`namespace-map.md` still contains legacy `kernel.*` wording on this branch.
This packet treats that file as the method-inventory authority only. Package
wording cleanup should be handled by a separate docs hygiene task.
