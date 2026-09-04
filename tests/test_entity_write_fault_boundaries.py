"""Fault-injection contract for the broad boundaries in ``application.entity_write``.

Every ``except Exception`` in that module is an *executor* boundary: a fault in
the store / write-protocol / Database layer must be turned into a **typed failed
outcome** (``status="failed"`` plus an ``ErrorDTO``), never into a silent success
and never into an escaping exception. These tests inject a custom ``Exception``
subclass (and a ``LookupError``) at each such site and pin that contract, plus
the fact that ``KeyboardInterrupt`` is *not* swallowed by any of them.

The line references are to the ``# noqa: BLE001`` sites carried by the module.
"""

from __future__ import annotations

import pytest

from factgraph.application import (
    apply_write_plan,
    build_schema_index,
    plan_write_command,
    resolve_selector,
)
from factgraph.application import entity_write as ew
from factgraph.application.protocol import (
    EntityCreateCommand,
    EntityDeleteCommand,
    EntitySelector,
    EntityWriteCommand,
    FieldMutation,
    FieldPath,
)
from factgraph.core.store import Database, Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    name: str = Identity()
    locale: str = Identity()
    lives_in: Country = Field()
    tag: list[str] = Field()


class AdapterFault(Exception):
    """A store/adapter fault class the executors have no special knowledge of."""


def _schema_ir():
    return compile_schema_from_classes([Country, User])


def _store_only():
    schema_ir = _schema_ir()
    return Store(schema_ir), build_schema_index(schema_ir)


def _store_with_database():
    schema_ir = _schema_ir()
    database = Database.create(schema_ir=schema_ir)
    store = Store(schema_ir=schema_ir, ledger=database._ledger_for_attach())
    return store, build_schema_index(schema_ir), database


def _write_command() -> EntityWriteCommand:
    return EntityWriteCommand(
        target=EntitySelector(entity_type="User", identity={"name": "alice", "locale": "en"}),
        mutations=(
            FieldMutation(
                op="add",
                field=FieldPath(entity_type="User", field_name="tag"),
                value="admin",
            ),
        ),
        create_if_missing=True,
    )


def _create_command() -> EntityCreateCommand:
    return EntityCreateCommand(
        target=EntitySelector(entity_type="User", identity={"name": "bob", "locale": "en"})
    )


def _raiser(exc: BaseException):
    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


def _assert_typed_failure(result, *, message_fragment: str) -> None:
    """A fault must be a typed failure, never a success and never an empty pass."""
    assert result.errors, "boundary must surface an ErrorDTO, not an empty result"
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.code == "WRITE_APPLY_FAILED"
    assert message_fragment in error.message, "the original fault detail must be preserved"
    assert result.applied, "a failed op must still be reported"
    assert all(row.status != "applied" for row in result.applied)
    assert any(row.status == "failed" for row in result.applied)


# --------------------------------------------------------------------------
# apply_write_plan store route (entity_write.py:290)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("ledger handle vanished"), LookupError("ledger handle vanished")],
)
def test_apply_write_plan_store_route_reports_typed_failure(monkeypatch, fault) -> None:
    store, index = _store_only()
    plan = plan_write_command(_write_command(), store=store, index=index)
    assert plan.can_apply

    monkeypatch.setattr(ew, "_apply_op", _raiser(fault))
    result = apply_write_plan(plan, store=store, index=index)

    _assert_typed_failure(result, message_fragment="ledger handle vanished")
    assert result.resolved_target == plan.resolved_target
    assert result.warnings == plan.warnings


def test_apply_write_plan_store_route_does_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    store, index = _store_only()
    plan = plan_write_command(_write_command(), store=store, index=index)
    monkeypatch.setattr(ew, "_apply_op", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        apply_write_plan(plan, store=store, index=index)


# --------------------------------------------------------------------------
# apply_write_plans batch transaction route (entity_write.py:366)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("commit_changes rejected tx"), LookupError("commit_changes rejected tx")],
)
def test_apply_write_plans_batch_route_reports_typed_failure_per_plan(monkeypatch, fault) -> None:
    store, index, database = _store_with_database()
    plan = plan_write_command(_write_command(), store=store, index=index)
    assert plan.can_apply
    head_before = database.head()

    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(fault))
    results = ew.apply_write_plans((plan, plan), store=store, index=index, database=database)

    assert len(results) == 2
    for result in results:
        _assert_typed_failure(result, message_fragment="commit_changes rejected tx")
    assert database.head() == head_before, "a failed batch must not advance the head"


def test_apply_write_plans_batch_route_does_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    store, index, database = _store_with_database()
    plan = plan_write_command(_write_command(), store=store, index=index)
    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ew.apply_write_plans((plan,), store=store, index=index, database=database)


# --------------------------------------------------------------------------
# apply_create_plan (entity_write.py:586 database route, 605 store route)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("identity emission failed"), LookupError("identity emission failed")],
)
def test_apply_create_plan_database_route_reports_typed_failure(monkeypatch, fault) -> None:
    store, index, database = _store_with_database()
    plan = ew.plan_create_command(_create_command(), store=store, index=index)
    assert plan.can_apply
    head_before = database.head()

    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(fault))
    result = ew.apply_create_plan(plan, store=store, index=index, database=database)

    _assert_typed_failure(result, message_fragment="identity emission failed")
    assert database.head() == head_before


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("set_field blew up"), LookupError("set_field blew up")],
)
def test_apply_create_plan_store_route_reports_typed_failure(monkeypatch, fault) -> None:
    store, index = _store_only()
    plan = ew.plan_create_command(_create_command(), store=store, index=index)
    assert plan.can_apply

    monkeypatch.setattr(ew, "_apply_op", _raiser(fault))
    result = ew.apply_create_plan(plan, store=store, index=index)

    _assert_typed_failure(result, message_fragment="set_field blew up")


def test_apply_create_plan_routes_do_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    store, index, database = _store_with_database()
    plan = ew.plan_create_command(_create_command(), store=store, index=index)
    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ew.apply_create_plan(plan, store=store, index=index, database=database)

    store2, index2 = _store_only()
    plan2 = ew.plan_create_command(_create_command(), store=store2, index=index2)
    monkeypatch.setattr(ew, "_apply_op", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ew.apply_create_plan(plan2, store=store2, index=index2)


# --------------------------------------------------------------------------
# apply_delete_plan (entity_write.py:749 database route, 768 store route)
# --------------------------------------------------------------------------


def _materialized_delete_plan(store, index):
    create_plan = ew.plan_create_command(_create_command(), store=store, index=index)
    created = ew.apply_create_plan(create_plan, store=store, index=index)
    assert not created.errors
    ref = resolve_selector(_create_command().target, index=index)
    command = EntityDeleteCommand(
        target=EntitySelector(
            entity_type=ref.entity_type,
            identity=dict(ref.identity),
            encoded_ref=ref.encoded_ref,
        )
    )
    plan = ew.plan_delete_command(command, store=store, index=index)
    assert plan.can_apply
    assert plan.planned_retracts
    return plan


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("retract tx aborted"), LookupError("retract tx aborted")],
)
def test_apply_delete_plan_database_route_reports_typed_failure(monkeypatch, fault) -> None:
    store, index, database = _store_with_database()
    plan = _materialized_delete_plan(store, index)

    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(fault))
    result = ew.apply_delete_plan(plan, store=store, index=index, database=database)

    _assert_typed_failure(result, message_fragment="retract tx aborted")


@pytest.mark.parametrize(
    "fault",
    [AdapterFault("retract_by_asrt failed"), LookupError("retract_by_asrt failed")],
)
def test_apply_delete_plan_store_route_reports_typed_failure(monkeypatch, fault) -> None:
    store, index = _store_only()
    plan = _materialized_delete_plan(store, index)

    monkeypatch.setattr(ew, "_apply_entity_delete_retract", _raiser(fault))
    result = ew.apply_delete_plan(plan, store=store, index=index)

    _assert_typed_failure(result, message_fragment="retract_by_asrt failed")


def test_apply_delete_plan_routes_do_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    store, index, database = _store_with_database()
    plan = _materialized_delete_plan(store, index)
    monkeypatch.setattr(ew, "_commit_planned_ops_to_database", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ew.apply_delete_plan(plan, store=store, index=index, database=database)

    store2, index2 = _store_only()
    plan2 = _materialized_delete_plan(store2, index2)
    monkeypatch.setattr(ew, "_apply_entity_delete_retract", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        ew.apply_delete_plan(plan2, store=store2, index=index2)
