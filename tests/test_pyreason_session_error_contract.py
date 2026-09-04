"""PyReason session write API keeps its ValueError argument and schema-shape rejection contract.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.pyreason.session`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
The session constructor, ``write_node_fact`` / ``write_edge_fact``, and the
``tx.relationship(...)`` batch API are the documented adapter-local write
surface (adapter docs sections 5A / 5A.1).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from factgraph.adapters.pyreason.session import (
    PyReasonEntityHandle,
    PyReasonSession,
    _resolve_shared_meta,
)
from factgraph.sdk.schema import Entity, Field, Identity, Relationship


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field()


def _schema_ir() -> dict[str, Any]:
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
        ],
    }


# --- PyReasonSession.__init__: "schema_ir must be dict" / "schema_ir.predicates must be list" ---


@pytest.mark.parametrize(
    ("schema_ir", "message"),
    [
        (None, "schema_ir must be dict"),
        ([("predicates", [])], "schema_ir must be dict"),
        ({"predicates": ({"pred_id": "user:name", "arity": 2},)}, "schema_ir.predicates must be list"),
        ({"predicates": "user:name"}, "schema_ir.predicates must be list"),
    ],
)
def test_constructor_schema_shape_rejections_preserve_exact_value_error(schema_ir, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        PyReasonSession(schema_ir)
    assert type(caught.value) is ValueError


def test_constructor_accepts_dict_schema_ir_positive_control():
    session = PyReasonSession(_schema_ir())
    assert session._pred_ids == {"user:name", "friends:strength"}
    assert session._relationship_preds == {"friends:strength"}


# --- PyReasonBatchTx.relationship: "from_entity must be a PyReasonEntityHandle" / "to_entity ..." ---


@pytest.mark.parametrize("handle_kwarg", ["from_entity", "to_entity"])
def test_relationship_handle_type_rejections_preserve_exact_value_error(handle_kwarg):
    session = PyReasonSession(_schema_ir())
    with session.batch() as tx:
        alice = tx.entity(User, user_id="Alice")
        bob = tx.entity(User, user_id="Bob")
        handles: dict[str, Any] = {"from_entity": alice, "to_entity": bob}
        handles[handle_kwarg] = "Alice"  # a bare node_ref string where a handle is required
        expected = f"{handle_kwarg} must be a PyReasonEntityHandle"
        with pytest.raises(ValueError, match=re.escape(expected)) as caught:
            tx.relationship(Friends, strength="0.9", **handles)
        assert type(caught.value) is ValueError
    assert session.edge_facts == []


def test_relationship_accepts_entity_handles_positive_control():
    session = PyReasonSession(_schema_ir())
    with session.batch() as tx:
        alice = tx.entity(User, user_id="Alice")
        bob = tx.entity(User, user_id="Bob")
        assert isinstance(alice, PyReasonEntityHandle)
        tx.relationship(Friends, from_entity=alice, to_entity=bob, strength="0.9")
    assert [(f["pred_id"], f["from_ref"], f["to_ref"], f["value"]) for f in session.edge_facts] == [
        ("friends:strength", "Alice", "Bob", "0.9")
    ]


# --- write_node_fact / write_edge_fact: "value must be string" ---


@pytest.mark.parametrize("value", [1, 0.9, b"Alice", ["Alice"]])
def test_write_node_fact_value_type_rejection_preserves_exact_value_error(value):
    session = PyReasonSession(_schema_ir())
    with pytest.raises(ValueError, match=re.escape("value must be string")) as caught:
        session.write_node_fact("user:name", "Alice", value)
    assert type(caught.value) is ValueError
    assert session.node_facts == []


@pytest.mark.parametrize("value", [1, 0.9, b"0.9", ["0.9"]])
def test_write_edge_fact_value_type_rejection_preserves_exact_value_error(value):
    session = PyReasonSession(_schema_ir())
    with pytest.raises(ValueError, match=re.escape("value must be string")) as caught:
        session.write_edge_fact("friends:strength", "Alice", "Bob", value)
    assert type(caught.value) is ValueError
    assert session.edge_facts == []


def test_write_fact_string_values_positive_control():
    session = PyReasonSession(_schema_ir())
    session.write_node_fact("user:name", "Alice", "Alice")
    session.write_edge_fact("friends:strength", "Alice", "Bob", "0.9")
    assert session.node_facts[0]["value"] == "Alice"
    assert session.edge_facts[0]["value"] == "0.9"


# --- _resolve_shared_meta: "meta must be dict when provided" ---


@pytest.mark.parametrize("meta", [[("source", "test")], "source=test", {"source", "test"}])
def test_meta_type_rejection_preserves_exact_value_error(meta):
    session = PyReasonSession(_schema_ir())
    with pytest.raises(ValueError, match=re.escape("meta must be dict when provided")) as caught:
        session.write_node_fact("user:name", "Alice", "Alice", meta=meta)
    assert type(caught.value) is ValueError
    with pytest.raises(ValueError, match=re.escape("meta must be dict when provided")) as direct:
        _resolve_shared_meta(meta, lower_bound=1.0)
    assert type(direct.value) is ValueError
    assert session.node_facts == []


def test_meta_dict_or_none_positive_control():
    assert _resolve_shared_meta(None, lower_bound=1.0) == {}
    assert _resolve_shared_meta({"source": "test"}, lower_bound=1.0) == {"source": "test"}
    session = PyReasonSession(_schema_ir())
    session.write_node_fact("user:name", "Alice", "Alice", meta={"source": "test"})
    assert session.node_facts[0]["meta"] == {"source": "test"}
