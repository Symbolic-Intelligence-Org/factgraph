"""The v1 effective-snapshot integrity check keeps its ValueError contract.

``assert_resolved_query_effective_snapshot_current`` is reached from
``resolve_query_effective_snapshot_v1`` and from
``assert_resolved_scenario_compatibility_current``; the SDK Store runs the
latter inside ``except (AttributeError, TypeError, ValueError)`` and reports
``SDKStoreError``.  Every case below reaches one ``raise ValueError`` site with
a wrong-type input and pins the exact message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.protocol.query_effective_snapshot import (
    QueryEffectiveSnapshotV1,
)
from factgraph.application.query_effective_snapshot_runtime import (
    ResolvedQueryEffectiveSnapshotV1,
    assert_resolved_query_effective_snapshot_current,
)


def _resolved(snapshot):
    return ResolvedQueryEffectiveSnapshotV1(
        snapshot=snapshot,
        baseline_relation={},
        effective_relation={},
        members=(),
        legacy_set_operations=(),
    )


# --- "resolved snapshot must be ResolvedQueryEffectiveSnapshotV1" ---


@pytest.mark.parametrize("resolved", ["snapshot", None, object(), {}])
def test_snapshot_guard_rejects_foreign_object_as_value_error(resolved):
    message = "resolved snapshot must be ResolvedQueryEffectiveSnapshotV1"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        assert_resolved_query_effective_snapshot_current(resolved)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- "resolved snapshot has invalid public identity" ---


@pytest.mark.parametrize("snapshot", ["snapshot", None, object(), {}])
def test_snapshot_guard_rejects_foreign_public_identity_as_value_error(snapshot):
    message = "resolved snapshot has invalid public identity"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        assert_resolved_query_effective_snapshot_current(_resolved(snapshot))
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- valid-type positive control: a correctly typed pair clears both gates ---


def test_correctly_typed_pair_passes_both_type_gates(monkeypatch):
    seen: list[object] = []

    def _record(self) -> None:
        seen.append(self)

    monkeypatch.setattr(QueryEffectiveSnapshotV1, "__post_init__", _record, raising=True)
    snapshot = QueryEffectiveSnapshotV1.__new__(QueryEffectiveSnapshotV1)
    object.__setattr__(snapshot, "dependency_predicate_ids", ("person:age",))
    resolved = _resolved(snapshot)

    with pytest.raises(ValueError) as caught:
        assert_resolved_query_effective_snapshot_current(resolved)

    assert seen == [snapshot]
    assert str(caught.value) == (
        "resolved snapshot baseline relation keyset does not match dependencies"
    )
