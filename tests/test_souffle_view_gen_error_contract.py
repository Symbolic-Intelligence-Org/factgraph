"""Souffle view generation keeps its schema_ir shape rejection contract.

``generate_view_dl`` distinguishes a non-dict ``schema_ir`` argument
(``TypeError``) from malformed schema_ir content (``ValueError``).  Every
case below reaches one ``raise ValueError`` site with a wrong-type input (the
input a ``TypeError`` rewrite would re-classify) and pins the exact message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.adapters.souffle.souffle_view_gen import generate_view_dl
from tests import test_souffle_witness_view_gen_v1 as fixtures

# --- generate_view_dl: "schema_ir.predicates must be list" ---


@pytest.mark.parametrize(
    "schema_ir",
    [{"predicates": ("user:name",)}, {"predicates": None}, {"predicates": "user:name"}, {}],
)
def test_view_gen_rejects_non_list_predicates_as_value_error(schema_ir):
    with pytest.raises(ValueError, match=re.escape("schema_ir.predicates must be list")) as caught:
        generate_view_dl(schema_ir)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "schema_ir.predicates must be list"


# --- generate_view_dl: "schema predicate must be dict" ---


@pytest.mark.parametrize(
    "predicates",
    [
        ["user:name"],
        [None],
        [("pred_id", "user:name")],
        [fixtures._schema_ir()["predicates"][0], []],
    ],
)
def test_view_gen_rejects_non_dict_predicate_as_value_error(predicates):
    with pytest.raises(ValueError, match=re.escape("schema predicate must be dict")) as caught:
        generate_view_dl({"predicates": predicates})
    assert type(caught.value) is ValueError
    assert str(caught.value) == "schema predicate must be dict"


def test_view_gen_keeps_type_error_for_non_dict_schema_ir_argument():
    with pytest.raises(TypeError, match=re.escape("schema_ir must be dict")):
        generate_view_dl(["predicates"])


def test_view_gen_accepts_well_formed_schema_ir():
    dl = generate_view_dl(fixtures._schema_ir())
    assert ".decl p_user_name(E:symbol, V0:symbol)" in dl
    assert ".decl p_user_status(E:symbol, V0:symbol)" in dl
