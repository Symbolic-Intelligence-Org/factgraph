"""Certainty-summary wrong-type rejections stay ValueError at their documented boundary.

Every case below reaches one ``raise ValueError`` site in
``factgraph.core.annotation._certainty`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
Each site is paired with a valid-type positive control.
"""

from __future__ import annotations

import pytest

from factgraph.core.annotation._certainty import (
    _condition_weight,
    derive_certainty_summary,
)


def test_tree_dict_wrong_type_is_value_error() -> None:
    with pytest.raises(ValueError, match="tree_dict must be mapping"):
        derive_certainty_summary(["not-a-mapping"], {}, "certainty")


def test_condition_weights_wrong_type_is_value_error() -> None:
    with pytest.raises(ValueError, match="condition_weights must be mapping"):
        derive_certainty_summary({"root": {}}, ["not-a-mapping"], "certainty")


def test_mapping_inputs_are_accepted() -> None:
    assert derive_certainty_summary({"root": {}}, {}, "certainty") is not None
    assert derive_certainty_summary({"root": {}}, {}, "probability") is None


@pytest.mark.parametrize("raw", ["0.5", True, [0.5]])
def test_non_numeric_condition_weight_is_value_error(raw: object) -> None:
    with pytest.raises(ValueError, match=r'condition_weights\["cond"\] must be numeric'):
        _condition_weight({"cond": raw}, "cond")


def test_numeric_condition_weight_is_accepted() -> None:
    assert _condition_weight({"cond": 2}, "cond") == 2.0
    assert _condition_weight({"cond": 0.25}, "cond") == 0.25
    assert _condition_weight({}, "cond") is None
