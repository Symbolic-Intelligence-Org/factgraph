"""The Q7/Q11 Scenario compatibility check keeps its ValueError contract.

``assert_resolved_scenario_compatibility_current`` guards the parallel
public/private halves of the old Scenario adapters.  ``factgraph.sdk.store``
calls it inside ``except (AttributeError, TypeError, ValueError)`` and reports
``SDKStoreError("Scenario effective snapshot failed its execution-time
integrity check")``, so the whole rejection family must stay inside that tuple.
Every case below reaches one ``raise ValueError`` site with a wrong-type input
and pins the exact message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.evaluation_scenario_runtime import (
    ResolvedScenarioFieldSubstitutionSetV0,
    ResolvedScenarioFieldSubstitutionV0,
    assert_resolved_scenario_compatibility_current,
)
from factgraph.application.protocol.query_effective_snapshot import (
    QueryEffectiveSnapshotV1,
)
from factgraph.application.query_effective_snapshot_runtime import (
    ResolvedQueryEffectiveSnapshotV1,
)


def _runtime(snapshot=None):
    return ResolvedQueryEffectiveSnapshotV1(
        snapshot=snapshot,
        baseline_relation={},
        effective_relation={},
        members=(),
        legacy_set_operations=(),
    )


def _resolved(cls, *, runtime, effective_snapshot):
    return cls(
        resolution=None,
        baseline_relation={},
        effective_relation={},
        premise_bindings=(),
        effective_snapshot=effective_snapshot,
        _effective_snapshot_runtime=runtime,
    )


_ADAPTERS = (ResolvedScenarioFieldSubstitutionV0, ResolvedScenarioFieldSubstitutionSetV0)


# --- "resolved Scenario must be one of the Q7/Q11 compatibility adapters" ---


@pytest.mark.parametrize("resolved", ["scenario", None, object(), {}, _runtime()])
def test_scenario_guard_rejects_foreign_object_as_value_error(resolved):
    message = "resolved Scenario must be one of the Q7/Q11 compatibility adapters"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        assert_resolved_scenario_compatibility_current(resolved)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- "resolved Scenario has invalid private v1 runtime state" ---


@pytest.mark.parametrize("cls", _ADAPTERS)
@pytest.mark.parametrize("runtime", ["runtime", None, object()])
def test_scenario_guard_rejects_foreign_private_runtime_as_value_error(cls, runtime):
    message = "resolved Scenario has invalid private v1 runtime state"
    resolved = _resolved(cls, runtime=runtime, effective_snapshot=None)
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        assert_resolved_scenario_compatibility_current(resolved)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- "resolved Scenario has invalid public v1 snapshot" ---


@pytest.mark.parametrize("cls", _ADAPTERS)
@pytest.mark.parametrize("effective_snapshot", ["snapshot", None, object()])
def test_scenario_guard_rejects_foreign_public_snapshot_as_value_error(cls, effective_snapshot):
    message = "resolved Scenario has invalid public v1 snapshot"
    resolved = _resolved(cls, runtime=_runtime(), effective_snapshot=effective_snapshot)
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        assert_resolved_scenario_compatibility_current(resolved)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- valid-type positive control: correctly typed halves clear all three gates ---


@pytest.mark.parametrize("cls", _ADAPTERS)
def test_correctly_typed_adapter_passes_every_type_gate(cls, monkeypatch):
    monkeypatch.setattr(
        QueryEffectiveSnapshotV1, "__post_init__", lambda self: None, raising=True
    )
    snapshot = QueryEffectiveSnapshotV1.__new__(QueryEffectiveSnapshotV1)
    object.__setattr__(snapshot, "dependency_predicate_ids", ("person:age",))
    resolved = _resolved(cls, runtime=_runtime(snapshot), effective_snapshot=snapshot)

    with pytest.raises(ValueError) as caught:
        assert_resolved_scenario_compatibility_current(resolved)

    assert str(caught.value) == (
        "resolved snapshot baseline relation keyset does not match dependencies"
    )
