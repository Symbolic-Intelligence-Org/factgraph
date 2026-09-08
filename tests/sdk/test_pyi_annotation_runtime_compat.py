"""Pin the approved annotation delta without changing Python protocol behaviour."""

from __future__ import annotations

import inspect
import operator
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from factgraph.adapters.pyreason.session import PyReasonBatchTx, PyReasonSession
from factgraph.core.store.database import Database, _suppress_os_error
from factgraph.sdk import Entity, FactGraph, Field, Identity, compile_schema_from_classes
from factgraph.sdk.batch import SDKBatchTx, _IdentityWriteGuard
from factgraph.sdk.dsl.expr import AttrRef, BinaryExpr, CompareExpr, LogicVar, _AggregateRef
from factgraph.sdk.facade import AssertionRecordSet, EntityEditor, IdentityEditor
from factgraph.sdk.schema import _UnsetFieldValue
from factgraph.sdk.store import SDKStore


class AnnotationUser(Entity):
    user_id: str = Identity()
    name: str = Field()


_EXIT_PARAMETERS = {
    "exc_type": type[BaseException] | None,
    "exc": BaseException | None,
    "tb": object,
}
_EXIT_SIGNATURE = (
    "(self, exc_type: 'type[BaseException] | None', "
    "exc: 'BaseException | None', tb: 'object')"
)
_METHOD_CONTRACTS = (
    *(
        (method, "(self, other: 'object') -> 'CompareExpr'",
         {"other": object, "return": CompareExpr})
        for method in (
            LogicVar.__eq__, LogicVar.__ne__, AttrRef.__eq__, AttrRef.__ne__,
            BinaryExpr.__eq__, BinaryExpr.__ne__, _AggregateRef.__eq__, _AggregateRef.__ne__,
        )
    ),
    *(
        (method, "(self, other: 'object') -> 'bool'", {"other": object, "return": bool})
        for method in (_IdentityWriteGuard.__eq__, IdentityEditor.__eq__, _UnsetFieldValue.__eq__)
    ),
    (PyReasonBatchTx.__enter__, "(self) -> 'PyReasonBatchTx'", {"return": PyReasonBatchTx}),
    (Database.__enter__, "(self) -> 'Database'", {"return": Database}),
    (SDKBatchTx.__enter__, "(self) -> 'SDKBatchTx'", {"return": SDKBatchTx}),
    (EntityEditor.__enter__, "(self) -> 'EntityEditor'", {"return": EntityEditor}),
    (SDKStore.__enter__, "(self) -> 'SDKStore'", {"return": SDKStore}),
    (AssertionRecordSet.__new__, "(cls, records: 'Any' = ()) -> 'AssertionRecordSet'",
     {"records": Any, "return": AssertionRecordSet}),
    (PyReasonBatchTx.__exit__, "(self, *exc_info: 'object') -> 'None'",
     {"exc_info": object, "return": type(None)}),
    (Database.__exit__, _EXIT_SIGNATURE + " -> 'None'", {**_EXIT_PARAMETERS, "return": type(None)}),
    (_suppress_os_error.__exit__, _EXIT_SIGNATURE + " -> 'bool'", {**_EXIT_PARAMETERS, "return": bool}),
    (SDKStore.__exit__, _EXIT_SIGNATURE + " -> 'None'", {**_EXIT_PARAMETERS, "return": type(None)}),
    # These two neighbours are deliberately not given new parameter annotations.
    (SDKBatchTx.__exit__, "(self, exc_type, exc, tb) -> 'None'", {"return": type(None)}),
    (EntityEditor.__exit__, "(self, exc_type, exc_val, exc_tb) -> 'bool'", {"return": bool}),
)


@pytest.mark.parametrize(
    ("method", "signature", "hints"),
    _METHOD_CONTRACTS,
    ids=[method.__qualname__ for method, _, _ in _METHOD_CONTRACTS],
)
def test_protocol_introspection_contract(method, signature, hints) -> None:
    """Resolve every hint on 3.10/3.11 and pin names, kinds and defaults too."""
    assert get_type_hints(method) == hints
    assert str(inspect.signature(method)) == signature


@pytest.mark.parametrize("kind", ["variable", "attribute", "binary", "aggregate"])
@pytest.mark.parametrize(("compare", "op"), [(operator.eq, "eq"), (operator.ne, "ne")])
def test_behaviour_dsl_comparison_retains_arbitrary_operand(kind, compare, op) -> None:
    variable = LogicVar("annotation")
    term = {
        "variable": variable,
        "attribute": AttrRef(variable, "name"),
        "binary": BinaryExpr("add", variable, 1),
        "aggregate": _AggregateRef("count", variable, ()),
    }[kind]
    operand = object()
    result = compare(term, operand)
    assert isinstance(result, CompareExpr)
    assert result.op == op
    assert result.left is term
    assert result.right is operand


@pytest.mark.parametrize(("operand", "expected"), [(None, True), (0, False), (object(), False)])
def test_behaviour_unset_field_equality(operand, expected) -> None:
    sentinel = AnnotationUser(user_id="unset").name
    assert isinstance(sentinel, _UnsetFieldValue)
    assert operator.eq(sentinel, operand) is expected


@pytest.mark.parametrize(("operand", "expected"), [("alice", True), ("bob", False), (object(), False)])
def test_behaviour_identity_guards(operand, expected) -> None:
    with FactGraph.create(schema_classes=[AnnotationUser]) as graph:
        graph.entities.create(AnnotationUser, user_id="alice")
        with graph.batch() as batch:
            handle = batch.entity(AnnotationUser, user_id="alice")
            assert isinstance(handle.user_id, _IdentityWriteGuard)
            assert operator.eq(handle.user_id, operand) is expected
        editor = graph.entities.edit(AnnotationUser, user_id="alice")
        try:
            assert isinstance(editor.user_id, IdentityEditor)
            assert operator.eq(editor.user_id, operand) is expected
        finally:
            editor.rollback()


def test_behaviour_pyreason_batch_enter_and_exception_propagation() -> None:
    batch = PyReasonSession({"predicates": []}).batch()
    failure = LookupError("batch failure")
    with pytest.raises(LookupError) as caught, batch as entered:
        assert entered is batch
        raise failure
    assert caught.value is failure


def test_behaviour_sdk_batch_enter_and_exception_propagation() -> None:
    with FactGraph.create(schema_classes=[AnnotationUser]) as graph:
        batch = graph.batch()
        failure = LookupError("batch failure")
        with pytest.raises(LookupError) as caught, batch as entered:
            assert entered is batch
            entered.entity(AnnotationUser, user_id="staged").name.set("uncommitted")
            raise failure
        assert caught.value is failure
        assert graph.entities.get(AnnotationUser, user_id="staged") is None


def test_behaviour_database_enter_exit_releases_workspace(tmp_path: Path) -> None:
    path = tmp_path / "database"
    schema = compile_schema_from_classes([AnnotationUser])
    database = Database.create(path, schema_ir=schema)
    failure = LookupError("database failure")
    with pytest.raises(LookupError) as caught, database as entered:
        assert entered is database
        raise failure
    assert caught.value is failure
    # A real reopen checks cleanup, not a mock of the close method.
    with Database.open(path, schema_ir=schema):
        pass


def test_behaviour_store_enter_exit_releases_owned_workspace(tmp_path: Path) -> None:
    path = tmp_path / "graph"
    graph = FactGraph.create(schema_classes=[AnnotationUser], path=path)
    failure = LookupError("store failure")
    with pytest.raises(LookupError) as caught, graph as entered:
        assert entered is graph
        raise failure
    assert caught.value is failure
    with FactGraph.load_workspace(path, schema_classes=[AnnotationUser]):
        pass


@pytest.mark.parametrize("abort", [False, True])
def test_behaviour_entity_editor_commit_or_rollback(abort: bool) -> None:
    with FactGraph.create(schema_classes=[AnnotationUser]) as graph:
        ref = graph.entities.create(AnnotationUser, user_id="alice")
        graph.fields.set(AnnotationUser.name, ref, "original")
        editor = graph.entities.edit(AnnotationUser, user_id="alice")
        assert editor.__enter__() is editor
        editor.name.set("updated")
        failure = ValueError("editor failure") if abort else None
        assert editor.__exit__(ValueError if abort else None, failure, None) is False
        snapshot = graph.entities.get(AnnotationUser, user_id="alice")
        assert snapshot is not None
        assert snapshot.name == ("original" if abort else "updated")


@pytest.mark.parametrize("failure", [OSError("expected"), ValueError("not suppressed")])
def test_behaviour_suppress_os_error_is_narrow(failure: Exception) -> None:
    if isinstance(failure, OSError):
        with _suppress_os_error():
            raise failure
    else:
        with pytest.raises(ValueError) as caught, _suppress_os_error():
            raise failure
        assert caught.value is failure


def test_behaviour_assertion_record_set_new_and_slice() -> None:
    with FactGraph.create(schema_classes=[AnnotationUser]) as graph:
        ref = graph.entities.create(AnnotationUser, user_id="alice")
        graph.fields.set(AnnotationUser.name, ref, "Alice")
        snapshot = graph.entities.get(AnnotationUser, user_id="alice")
        assert snapshot is not None
        record = snapshot.field("name").active[0]
        records = AssertionRecordSet([record])
        assert type(records) is AssertionRecordSet
        assert records[0] is record
        assert type(records[:1]) is AssertionRecordSet
        assert records[:1][0] is record
        assert type(records[:0]) is AssertionRecordSet
        assert len(records[:0]) == 0
