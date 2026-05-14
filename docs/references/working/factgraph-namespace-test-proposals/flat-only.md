# Flat-Only Namespace Proposals

These paths have behavior coverage through flat `SDKStore` methods, but no
direct namespace-form test. The proposal goal is a light smoke lock on the
public namespace path, not duplication of full flat contract suites.

## `fg.schema.ingest(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.schema.ingest(...)`.
- `src/factgraph/sdk/store.py:267`
  - `_SDKSchemaManager.ingest(...)`.
- Existing flat coverage:
  - `tests/test_sdk_ingest_application_delegate.py`

### Proposed Intent

Add a delegation smoke test. Keep deep ingest behavior in the existing flat
application-delegate suite.

### Proposed Test Code

```python
from __future__ import annotations

import unittest
from unittest.mock import patch

from factgraph.audit.proof_frame_diff import ProofFrameDiff
from factgraph.audit.round_events import (
    RoundEvent,
    make_round_finalized_event,
    make_round_started_event,
)
from factgraph.sdk import Branch, Entity, FactGraph, Field, Identity, Inference, Pred
from factgraph.sdk import vars as sdk_vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


class FactGraphSchemaIngestNamespaceTests(unittest.TestCase):
    def test_schema_ingest_delegates_to_flat_ingest(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with patch.object(fg, "ingest", return_value="ingested") as ingest:
            result = fg.schema.ingest([{"row": 1}], source="fixture")

        ingest.assert_called_once_with([{"row": 1}], source="fixture")
        self.assertEqual(result, "ingested")
```

### Release Gate Classification

Smoke.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.write.retract(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.write.retract(asrt_id, meta=None)`.
- `src/factgraph/sdk/store.py:344`
  - `_SDKWriteManager.retract(...)`.
- Existing flat coverage:
  - `test_sdk_batch_primary_identity`
  - `test_sdk_frozen_assertion_view`
  - `test_sdk_assertion_record_set`
  - `test_sdk_set_add_application_delegate`

### Proposed Intent

Use a real public write/read flow to prove namespace retraction hides a prior
assertion.

### Proposed Test Code

```python
class FactGraphWriteRetractNamespaceTests(unittest.TestCase):
    def test_write_retract_hides_retracted_assertion(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        asrt_id = fg.write.set(User.age, ref, 30)

        fg.write.retract(asrt_id, meta={"source": "review"})

        self.assertIsNone(fg.read.get(User, user_id="u-1").age)
```

### Release Gate Classification

Release-gate useful.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.eval.accept(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.eval.accept(candidate)`.
- `src/factgraph/sdk/store.py:489`
  - `_SDKEvalManager.accept(...)`.
- Existing flat coverage:
  - `test_pyreason_e2e` flat `sdk.accept(...)`

### Proposed Intent

Use a real native candidate flow to prove `evaluate -> accept -> read` through
the public namespace.

### Proposed Test Code

```python
def age_inference() -> Inference:
    with sdk_vars("u", "age") as (u, age):
        return Inference(
            id="inf.namespace.accept",
            version="v1",
            where=[Branch([Pred("user:age", u, age)], id="age_path")],
            target="user:age",
            head_vars=[u, age],
        )


class FactGraphEvalAcceptNamespaceTests(unittest.TestCase):
    def test_eval_accept_commits_one_candidate(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.age, ref, 30)

        candidate = fg.eval.evaluate(age_inference())[0]
        result = fg.eval.accept(candidate)

        self.assertGreaterEqual(len(result.accepted_asrt_ids), 1)
```

### Release Gate Classification

Release-gate useful.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.what_if.diagnose(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.what_if.diagnose(...)`.
- `src/factgraph/sdk/store.py:569`
  - `_SDKWhatIfManager.diagnose(...)`.
- Existing flat coverage:
  - `tests/test_sdk_diagnose.py`

### Proposed Intent

Add a one-row real namespace call for the public manager path.

### Proposed Test Code

```python
class FactGraphWhatIfDiagnoseNamespaceTests(unittest.TestCase):
    def test_what_if_diagnose_returns_raw_diagnose_result(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.age, ref, 30)

        result = fg.what_if.diagnose(age_inference(), {"$u": ref, "$age": 99})

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.diagnostic_payload)
```

### Release Gate Classification

Smoke.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.what_if.why_not(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.what_if.why_not(...)`.
- `src/factgraph/sdk/store.py:573`
  - `_SDKWhatIfManager.why_not(...)`.
- Existing flat coverage:
  - `tests/test_sdk_why_not.py`

### Proposed Intent

Add a real namespace call with one present candidate and one missing candidate.

### Proposed Test Code

```python
class FactGraphWhatIfWhyNotNamespaceTests(unittest.TestCase):
    def test_what_if_why_not_returns_green_and_red_candidates(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.age, ref, 30)

        result = fg.what_if.why_not(
            age_inference(),
            [
                {"$u": ref, "$age": 30},
                {"$u": "idref_v1:User:user_id:missing", "$age": 30},
            ],
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(tuple(dict(row)["$u"] for row in result.green), (ref,))
        self.assertEqual(len(result.red), 1)
```

### Release Gate Classification

Smoke.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:

## `fg.audit.diff_proof_frames(...)`

### Source Refs

- `docs/official/kernel/quickstart/namespace-map.md`
  - lists `fg.audit.diff_proof_frames(...)`.
- `src/factgraph/sdk/store.py:609`
  - `_SDKAuditManager.diff_proof_frames(...)`.
- Existing flat coverage:
  - `test_audit_proof_frame_diff`
  - `test_sdk_g5_invariants`
  - `test_sdk_proof_frame_diff`
  - `test_sdk_redesign_invariants`

### Proposed Intent

Add one namespace-form call over minimal empty rounds. Keep detailed validation
in the existing flat and audit-layer suites.

### Proposed Test Code

```python
def empty_round(round_id: str) -> tuple[RoundEvent, ...]:
    started = make_round_started_event(round_id, event_ts=100)
    finalized = make_round_finalized_event(
        round_id,
        sequence=1,
        events=(started,),
        event_ts=200,
    )
    return (started, finalized)


class FactGraphAuditDiffNamespaceTests(unittest.TestCase):
    def test_audit_diff_proof_frames_namespace_returns_diff(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        diff = fg.audit.diff_proof_frames(
            "round-a",
            "round-b",
            empty_round("round-a"),
            empty_round("round-b"),
        )

        self.assertIsInstance(diff, ProofFrameDiff)
        self.assertEqual(diff.frame_deltas, ())
```

### Release Gate Classification

Smoke.

### Review Checklist

- [ ] Accept as written
- [ ] Accept with modifications
- [ ] Reject
- [ ] Defer

Notes:
