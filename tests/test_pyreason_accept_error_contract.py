"""PyReason accept helpers keep their ValueError argument and schema-shape rejection contract.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.pyreason.accept`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from factgraph.adapters.pyreason.accept import (
    AcceptResult,
    accept_pyreason_session,
    persist_pyreason_annotations,
)
from factgraph.adapters.pyreason.session import PyReasonSession
from factgraph.core.store.ledger import Ledger

_ENTITY_SPEC = {"name": "user", "type_domain": "entity_ref"}
_TO_REF_SPEC = {"name": "to_ref", "type_domain": "entity_ref"}
_NAME_SPEC = {"name": "name", "type_domain": "string"}
_STRENGTH_SPEC = {"name": "strength", "type_domain": "string"}


def _node_pred(arg_specs: list[object]) -> dict[str, object]:
    return {"pred_id": "user:name", "arity": 2, "owner_type": "User", "arg_specs": arg_specs}


def _edge_pred(arg_specs: list[object]) -> dict[str, object]:
    return {
        "pred_id": "friends:strength",
        "arity": 3,
        "arg_specs": arg_specs,
        "relationship_type": "Friends",
        "from_entity_type": "User",
        "to_entity_type": "User",
    }


def _schema_ir(*preds: dict[str, object]) -> dict[str, object]:
    return {"predicates": list(preds)}


def _valid_schema_ir() -> dict[str, object]:
    return _schema_ir(
        _node_pred([_ENTITY_SPEC, _NAME_SPEC]),
        _edge_pred([_ENTITY_SPEC, _TO_REF_SPEC, _STRENGTH_SPEC]),
    )


# --- accept_pyreason_session: "ledger must be a Ledger instance" ---


@pytest.mark.parametrize("ledger", ["not_a_ledger", None, {}])
def test_accept_rejects_non_ledger_as_value_error(ledger):
    session = PyReasonSession(_valid_schema_ir())
    with pytest.raises(ValueError, match=re.escape("ledger must be a Ledger instance")) as caught:
        accept_pyreason_session(ledger, session)
    assert type(caught.value) is ValueError


# --- accept_pyreason_session: "session must be a PyReasonSession instance" ---


@pytest.mark.parametrize("session", ["not_a_session", None, {"predicates": []}])
def test_accept_rejects_non_session_as_value_error(session):
    expected = "session must be a PyReasonSession instance"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        accept_pyreason_session(Ledger(), session)
    assert type(caught.value) is ValueError


def test_accept_with_valid_arguments_round_trips_node_and_edge_facts():
    ledger = Ledger()
    session = PyReasonSession(_valid_schema_ir())
    session._write_node_fact_internal("user:name", "Alice", "Alice")
    session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")

    result = accept_pyreason_session(ledger, session)

    assert isinstance(result, AcceptResult)
    assert ledger.get_claim(result.node_asrt_ids[0]).rest_terms == [("string", "Alice")]
    assert ledger.get_claim(result.edge_asrt_ids[0]).rest_terms == [
        ("entity_ref", "idref_v1:User:Bob"),
        ("string", "0.9"),
    ]


# --- _predicate_specs_by_id: "session schema_ir.predicates must be list" ---


@pytest.mark.parametrize(
    "predicates",
    [
        tuple(_valid_schema_ir()["predicates"]),
        {"user:name": _node_pred([_ENTITY_SPEC, _NAME_SPEC])},
    ],
)
def test_accept_rejects_non_list_schema_predicates_as_value_error(predicates):
    session = PyReasonSession(_valid_schema_ir())
    session._schema_ir = {"predicates": predicates}
    expected = "session schema_ir.predicates must be list"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        accept_pyreason_session(Ledger(), session)
    assert type(caught.value) is ValueError


# --- _node_rest_terms: "node value arg_spec invalid for <pred_id>" ---


@pytest.mark.parametrize("value_spec", ["string", ("name", "string"), None])
def test_accept_rejects_non_mapping_node_value_arg_spec_as_value_error(value_spec):
    session = PyReasonSession(_schema_ir(_node_pred([_ENTITY_SPEC, value_spec])))
    session._write_node_fact_internal("user:name", "Alice", "Alice")
    expected = "node value arg_spec invalid for user:name"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        accept_pyreason_session(Ledger(), session)
    assert type(caught.value) is ValueError


# --- _edge_rest_terms: "edge arg_specs invalid for <pred_id>" ---


@pytest.mark.parametrize(
    "arg_specs",
    [
        [_ENTITY_SPEC, "entity_ref", _STRENGTH_SPEC],
        [_ENTITY_SPEC, _TO_REF_SPEC, ["strength", "string"]],
        [_ENTITY_SPEC, None, _STRENGTH_SPEC],
    ],
)
def test_accept_rejects_non_mapping_edge_arg_specs_as_value_error(arg_specs):
    session = PyReasonSession(_schema_ir(_edge_pred(arg_specs)))
    session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
    expected = "edge arg_specs invalid for friends:strength"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        accept_pyreason_session(Ledger(), session)
    assert type(caught.value) is ValueError


# --- persist_pyreason_annotations: "ledger must be a Ledger instance" ---


@pytest.mark.parametrize("ledger", ["not_a_ledger", None, object()])
def test_persist_rejects_non_ledger_as_value_error(ledger):
    with pytest.raises(ValueError, match=re.escape("ledger must be a Ledger instance")) as caught:
        persist_pyreason_annotations(ledger, "run-1", SimpleNamespace(), SimpleNamespace())
    assert type(caught.value) is ValueError


def test_persist_with_real_ledger_binds_pending_template_to_written_assertion():
    ledger = Ledger()
    session = PyReasonSession(_valid_schema_ir())
    session._write_node_fact_internal("user:name", "Alice", "Alice")
    asrt_id = accept_pyreason_session(ledger, session).node_asrt_ids[0]
    store = SimpleNamespace(
        _engine_pending_annotations={
            "run-1": [
                {
                    "asrt_id": "",
                    "fact_index": 0,
                    "fact_kind": "node",
                    "namespace": "pyreason",
                    "category": "semantic",
                    "key": "post_accept_lower",
                    "kind": "float",
                    "value": 0.5,
                    "origin": "observed",
                    "derivation": None,
                }
            ]
        }
    )
    accept_result = SimpleNamespace(written_assertions=[{"asrt_id": asrt_id, "pred_id": "user:name"}])

    assert persist_pyreason_annotations(ledger, "run-1", store, accept_result) == 1

    keys = {row.key for row in ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")}
    assert "post_accept_lower" in keys
