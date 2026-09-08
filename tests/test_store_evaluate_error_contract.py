"""Native dependency analysis retains its exact ValueError rejection of ruleref atoms."""

from __future__ import annotations

import re

import pytest

from factgraph.core.rules.where_ast import PredAtom, RuleRefAtom, Var
from factgraph.core.store import _evaluate as evaluate_module

_RULEREF_MESSAGE = "native effective relation capture requires materialized where without ruleref atoms"
_PRED_ID_MESSAGE = "native effective relation predicate id must be non-empty string"


@pytest.mark.parametrize(
    "atom",
    [
        RuleRefAtom(rule_id="rule", version=None, terms=[]),
        RuleRefAtom(rule_id="rule", version="v1", terms=[Var("$x")]),
    ],
)
def test_ruleref_atom_rejection_preserves_exact_value_error(atom):
    predicates: set[str] = set()
    with pytest.raises(ValueError, match=re.escape(_RULEREF_MESSAGE)) as caught:
        evaluate_module._collect_atom_predicates(atom, predicates)
    assert type(caught.value) is ValueError
    assert predicates == set()


@pytest.mark.parametrize(
    "where",
    [
        [("ruleref", "rule", None, [])],
        [("pred", "Person:exists", ["$x"]), ("ruleref", "rule", "v1", ["$x"])],
    ],
)
def test_dependency_scan_rejects_ruleref_where_with_exact_value_error(where):
    with pytest.raises(ValueError, match=re.escape(_RULEREF_MESSAGE)) as caught:
        evaluate_module._native_where_dependency_predicates(where)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("pred_id", [123, None, b"Person:exists", ("Person:exists",), ""])
def test_predicate_id_rejection_preserves_exact_value_error(pred_id):
    atom = PredAtom(pred_id=pred_id, terms=[Var("$x")])
    predicates: set[str] = set()
    with pytest.raises(ValueError, match=re.escape(_PRED_ID_MESSAGE)) as caught:
        evaluate_module._collect_atom_predicates(atom, predicates)
    assert type(caught.value) is ValueError
    assert predicates == set()


def test_pred_atom_is_collected_without_error():
    predicates: set[str] = set()
    evaluate_module._collect_atom_predicates(
        PredAtom(pred_id="Person:exists", terms=[Var("$x")]), predicates
    )
    assert predicates == {"Person:exists"}


def test_dependency_scan_over_materialized_where_ir_collects_predicates():
    assert evaluate_module._native_where_dependency_predicates(
        [("pred", "Person:exists", ["$x"]), ("pred", "Person:age", ["$x", "$age"])]
    ) == ("Person:age", "Person:exists")
