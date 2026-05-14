# Stale-Conflict Proposals

These proposals handle places where `namespace-map.md` and the manager
implementation say a namespace method exists, while an existing test asserts an
older boundary.

## `fg.assertions.active()` / `fg.assertions.all()`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - documents `fg.assertions.active()` and `fg.assertions.all()`.
- `src/factgraph/sdk/store.py:216`
  - `_SDKAssertionsManager.active(...)`
- `src/factgraph/sdk/store.py:221`
  - `_SDKAssertionsManager.all(...)`
- `tests/test_sdk_fg_assertions_namespace.py:61`
  - `test_no_graph_wide_assertion_query_methods_ship`
- `tests/test_sdk_fg_assertions_namespace.py:64`
  - asserts `"active"` is absent.

### Current Evidence

The manager currently implements `active()` and `all()`, and `namespace-map.md`
documents both. The existing assertion test predates that expansion and still
expects no graph-wide assertion query methods. It also checks `history`,
`where`, `at`, and `version` as absent; those should probably remain absent.

### Proposed Intent

Replace the stale absence assertion for `active` with behavior coverage:

- `fg.assertions.all()` returns all assertion records.
- `fg.assertions.active()` returns only active records after a retraction.
- chain-level query helpers such as `history`, `where`, `at`, and `version`
  remain absent directly on `fg.assertions`.

### Proposed Test Code

```python
from __future__ import annotations

import unittest

from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_graph() -> tuple[FactGraph, dict[str, str]]:
    fg = FactGraph.create(schema_classes=[User])
    ref = fg.read.ref(User, user_id="u-1")
    ids = {
        "name": fg.write.set(User.name, ref, "Alice", meta={"source": "seed"}),
        "tag": fg.write.add(User.tag, ref, "vip", meta={"source": "seed"}),
    }
    return fg, ids


class FactGraphAssertionsReadbackTests(unittest.TestCase):
    def test_assertions_all_and_active_are_graph_scoped_record_sets(self) -> None:
        fg, ids = _seed_graph()
        fg.write.retract(ids["tag"], meta={"source": "review"})

        all_records = fg.assertions.all()
        active_records = fg.assertions.active()

        self.assertEqual(
            {record.asrt_id for record in all_records},
            {ids["name"], ids["tag"]},
        )
        self.assertEqual(
            {record.asrt_id for record in active_records},
            {ids["name"]},
        )

    def test_assertions_namespace_still_has_no_chain_helpers_directly(self) -> None:
        fg, _ = _seed_graph()

        for name in ("history", "where", "at", "version"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg.assertions, name))
```

### Release Gate Classification

Release-gate necessary. This resolves a direct contradiction between docs,
implementation, and tests.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.assertions.field(Field)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - documents `fg.assertions.field(Field)`.
- `src/factgraph/sdk/store.py:230`
  - `_SDKAssertionsManager.field(...)`
- `tests/test_sdk_fg_assertions_namespace.py`
  - covers `by_id` / `by_ids`, but not direct `field(Field)`.

### Current Evidence

Field-level assertion record flows exist, but there is no direct namespace-form
coverage for `fg.assertions.field(User.name)`.

### Proposed Intent

Add a small direct test proving that `field(Field)` returns a field-scoped
object with records for that field and rejects ambiguous string inputs.

### Proposed Test Code

```python
class FactGraphAssertionsFieldTests(unittest.TestCase):
    def test_assertions_field_returns_field_scoped_records(self) -> None:
        fg, ids = _seed_graph()

        records = fg.assertions.field(User.name).all()

        self.assertEqual([record.asrt_id for record in records], [ids["name"]])
        self.assertEqual(records.one().value, "Alice")

    def test_assertions_field_rejects_string_field_names(self) -> None:
        fg, _ = _seed_graph()

        with self.assertRaisesRegex(Exception, "Field descriptor"):
            fg.assertions.field("user:name")  # type: ignore[arg-type]
```

### Release Gate Classification

Release-gate useful. The method is documented and implemented, and the proposed
test is low cost.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

