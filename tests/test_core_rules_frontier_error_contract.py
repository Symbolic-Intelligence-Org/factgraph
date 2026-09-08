"""``NativeWhereFrontierEvaluation`` keeps a single ValueError rejection family.

``factgraph.core.rules.frontier`` is a documented core evaluator DTO
(``core/docs/01_architecture.en.md`` §rules.frontier).  Its ``__post_init__``
mixes shape guards with value-domain guards (``atoms_satisfied must equal
failed_atom_index``, ``empty_input frontier rows must have frontier_count=0``)
that can never become ``TypeError``.  Splitting only the ``isinstance`` guards
would break callers that catch the DTO family with a single ``except
ValueError``.  These tests pin the exact types and messages.
"""

from __future__ import annotations

import re

import pytest

from factgraph.core.rules.frontier import (
    NativeWhereFrontierEvaluation,
    NativeWhereFrontierRow,
)


@pytest.mark.parametrize("bindings", [None, (), ({"$x": "e1"},), "bindings", 1, {"$x": "e1"}])
def test_frontier_evaluation_rejects_non_list_bindings_with_exact_value_error(bindings):
    message = "bindings must be list"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        NativeWhereFrontierEvaluation(bindings=bindings)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize("row", [None, "row", 1, [("$x", "e1")], (("$x", "e1"),)])
def test_frontier_evaluation_rejects_non_dict_binding_rows_with_exact_value_error(row):
    message = "bindings must contain dict rows"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        NativeWhereFrontierEvaluation(bindings=[{"$x": "e1"}, row])
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_frontier_evaluation_accepts_list_of_dict_bindings():
    evaluation = NativeWhereFrontierEvaluation(bindings=[{"$x": "e1"}])
    assert evaluation.bindings == [{"$x": "e1"}]
    assert evaluation.rule_refs == ()
    assert evaluation.rule_ref_resolutions == ()
    assert evaluation.frontier_rows == ()
    assert NativeWhereFrontierEvaluation(bindings=[]).bindings == []


def test_frontier_value_domain_guard_shares_the_value_error_family():
    with pytest.raises(ValueError, match=re.escape("atoms_satisfied must equal failed_atom_index")):
        NativeWhereFrontierRow(
            case_index=0,
            failed_atom_index=1,
            atoms_satisfied=0,
            frontier_count=1,
            failure_kind="atom_filter_empty",
        )
