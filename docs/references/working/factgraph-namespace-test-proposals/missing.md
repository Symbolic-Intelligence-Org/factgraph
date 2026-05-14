# Missing-Surface Proposals

These entries had no observed namespace-form coverage and no obvious flat
counterpart coverage in root `tests/` during the audit.

## Shared Fixture Sketch

Several proposed snippets can share a tiny public graph fixture:

```python
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from factgraph.audit.proof_frame_diff import ProofFrameDiff
from factgraph.audit.round_events import (
    RoundEvent,
    make_round_finalized_event,
    make_round_started_event,
)
from factgraph.sdk import Branch, Entity, FactGraph, Field, Identity
from factgraph.sdk import Inference, Pred, vars as sdk_vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def seed_user(fg: FactGraph) -> str:
    ref = fg.read.ref(User, user_id="u-1")
    fg.write.set(User.name, ref, "Alice", meta={"source": "seed"})
    fg.write.set(User.tag_seed, ref, "vip", meta={"source": "seed"})
    return ref
```

Review can decide whether these become one shared helper in a new test file or
private helpers repeated in narrower files.

## `fg.schema.validate_provenance(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `validate_provenance(obj, *, standard="derivation_v1")`.
- `src/factgraph/sdk/store.py:270`
  - `_SDKSchemaManager.validate_provenance(...)`.

### Current Evidence

No direct namespace or flat coverage was observed in root `tests/`.

### Proposed Intent

Use `patch.object` to lock the namespace delegation without needing a large
provenance object fixture.

### Proposed Test Code

```python
class FactGraphSchemaNamespaceTests(unittest.TestCase):
    def test_schema_validate_provenance_delegates_to_flat_method(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        payload = {"standard": "derivation_v1", "data": {}}

        with patch.object(fg, "validate_provenance", return_value="ok") as validate:
            result = fg.schema.validate_provenance(payload, standard="derivation_v1")

        validate.assert_called_once_with(payload, standard="derivation_v1")
        self.assertEqual(result, "ok")
```

### Release Gate Classification

Smoke. Behavior fixture can be added later if provenance validation becomes a
public quickstart path.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.write.edit(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.write.edit(...)`.
- `src/factgraph/sdk/store.py:353`
  - `_SDKWriteManager.edit(...)`.
- `src/factgraph/sdk/store.py:1059`
  - flat `SDKStore.edit(...)`.

### Current Evidence

No namespace or flat `.edit(` instance call was observed in root `tests/`.

### Proposed Intent

Lock the namespace path to the flat editor entrypoint. A deeper behavior test
can be added separately if editor session semantics become part of quickstart
teaching.

### Proposed Test Code

```python
class FactGraphWriteNamespaceTests(unittest.TestCase):
    def test_write_edit_delegates_to_flat_edit(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with patch.object(fg, "edit", return_value="editor") as edit:
            result = fg.write.edit(User, user_id="u-1")

        edit.assert_called_once_with(User, user_id="u-1")
        self.assertEqual(result, "editor")
```

### Release Gate Classification

Smoke.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.eval.accept_many(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `accept_many(candidates)`.
- `src/factgraph/sdk/store.py:498`
  - `_SDKEvalManager.accept_many(...)`.
- `src/factgraph/sdk/store.py:2367`
  - flat `SDKStore.accept_many(...)`.

### Current Evidence

No namespace or flat exerciser observed.

### Proposed Intent

Use a real inference candidate flow to prove `evaluate -> accept_many -> read`
works through the public namespace.

### Proposed Test Code

```python
def tag_inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.namespace.accept_many",
            version="v1",
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed")],
            target="user:tag",
            head_vars=[u, tag],
        )


class FactGraphEvalNamespaceTests(unittest.TestCase):
    def test_eval_accept_many_accepts_evaluated_candidates(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        seed_user(fg)

        candidates = fg.eval.evaluate(tag_inference())
        results = fg.eval.accept_many(candidates)

        self.assertEqual(len(results), 1)
        self.assertEqual(tuple(fg.read.get(User, user_id="u-1").tag), ("vip",))
```

### Release Gate Classification

Release-gate necessary. This is a documented public lifecycle path.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.audit.explain_fact(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - calls this the user-facing bridge into evidence.
- `src/factgraph/sdk/store.py:601`
  - `_SDKAuditManager.explain_fact(...)`.
- `src/factgraph/sdk/store.py:2380`
  - flat `SDKStore.explain_fact(...)`.

### Current Evidence

No root test reaches `explain_fact(...)` through namespace or flat API.

### Proposed Intent

Seed one fact and assert that explanation returns active claim rows for the
requested predicate/ref/value.

### Proposed Test Code

```python
class FactGraphAuditNamespaceTests(unittest.TestCase):
    def test_audit_explain_fact_returns_active_claims_for_fact(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = seed_user(fg)

        explanation = fg.audit.explain_fact("user:name", ref, "Alice")

        self.assertEqual(explanation["pred_id"], "user:name")
        self.assertEqual(explanation["e_ref"], ref)
        self.assertEqual(len(explanation["active_claims"]), 1)
        self.assertEqual(explanation["active_claims"][0]["args"][1:], ["Alice"])
```

### Release Gate Classification

Release-gate necessary. Highest-signal public gap.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.audit.conflicts(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `conflicts(pred_id, e_ref)`.
- `src/factgraph/sdk/store.py:605`
  - `_SDKAuditManager.conflicts(...)`.
- `src/factgraph/sdk/store.py:2383`
  - flat `SDKStore.conflicts(...)`.

### Current Evidence

No namespace or flat exerciser observed.

### Proposed Intent

Seed two single-cardinality writes for the same field/ref and assert that the
conflict payload sees both active assertion ids and one chosen id.

### Proposed Test Code

```python
class FactGraphAuditConflictTests(unittest.TestCase):
    def test_audit_conflicts_reports_active_ids_and_chosen_id(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        first = fg.write.set(User.name, ref, "Alice", meta={"source": "a"})
        second = fg.write.set(User.name, ref, "Alicia", meta={"source": "b"})

        result = fg.audit.conflicts("user:name", ref)

        self.assertEqual(set(result["active_asrt_ids"]), {first, second})
        self.assertIn(result["chosen_asrt_id"], {first, second})
```

### Release Gate Classification

Release-gate useful.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.package.run_package(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `run_package(package_dir, entrypoints=[...], engine="souffle")`.
- `src/factgraph/sdk/store.py:631`
  - `_SDKPackageManager.run_package(...)`.
- `src/factgraph/sdk/store.py:2389`
  - flat `SDKStore.run_package(...)`.

### Current Evidence

No root test reaches `run_package(...)` through namespace or flat API.

### Proposed Intent

Lock namespace delegation without requiring a real Souffle package execution in
this coverage slice.

### Proposed Test Code

```python
class FactGraphPackageNamespaceTests(unittest.TestCase):
    def test_package_run_package_delegates_to_flat_method(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with patch.object(fg, "run_package", return_value={"ok": True}) as run_package:
            result = fg.package.run_package(
                Path("/tmp/package"),
                entrypoints=["main"],
                engine="souffle",
            )

        run_package.assert_called_once_with(
            Path("/tmp/package"),
            entrypoints=["main"],
            engine="souffle",
        )
        self.assertEqual(result, {"ok": True})
```

### Release Gate Classification

Smoke. Full package execution belongs to package/export integration tests.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:
