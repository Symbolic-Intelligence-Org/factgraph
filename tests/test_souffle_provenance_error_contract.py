"""Souffle audit-package proof-tree decoding keeps its exact ValueError contract.

``souffle_proof_tree_from_dict`` reconstructs ``SouffleProofTreeV0`` from the
``provenance_tree`` dict shape written into audit packages (``query`` /
``root`` / ``rules``).  Every case below reaches one ``raise ValueError`` site
with a wrong-type input (the input a ``TypeError`` rewrite would re-classify)
and pins the exact message, so the exception class is part of the contract.
"""

from __future__ import annotations

import re

import pytest

from factgraph.adapters.souffle import provenance
from factgraph.adapters.souffle.provenance import (
    SouffleProofNodeV0,
    SouffleProofTreeV0,
    parse_souffle_proof_json,
    souffle_proof_tree_from_dict,
)
from tests import test_souffle_provenance_v0 as fixtures

_VALID_ROOT: dict[str, object] = {
    "node_type": "axiom",
    "relation": "disposal_probability",
    "args": ["sentinel_7", "920000"],
    "rule_number": None,
    "children": [],
}


def _node_to_dict(node: SouffleProofNodeV0) -> dict[str, object]:
    return {
        "node_type": node.node_type,
        "relation": node.relation,
        "args": list(node.args),
        "rule_number": node.rule_number,
        "children": [_node_to_dict(child) for child in node.children],
    }


def _tree_to_dict(tree: SouffleProofTreeV0) -> dict[str, object]:
    return {"query": tree.query, "root": _node_to_dict(tree.root), "rules": dict(tree.rules)}


# --- souffle_proof_tree_from_dict: "row must be dict" / "row.root ..." / "row.rules ..." ---


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (None, "row must be dict"),
        ([("root", _VALID_ROOT)], "row must be dict"),
        ("row", "row must be dict"),
        ({"root": None, "rules": {}}, "row.root must be dict"),
        ({"root": [_VALID_ROOT], "rules": {}}, "row.root must be dict"),
        ({"rules": {}}, "row.root must be dict"),
        ({"root": _VALID_ROOT, "rules": None}, "row.rules must be dict"),
        ({"root": _VALID_ROOT, "rules": [("(R1)", "rule")]}, "row.rules must be dict"),
    ],
)
def test_tree_row_shape_rejections_preserve_exact_value_error(row, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        souffle_proof_tree_from_dict(row)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- _souffle_proof_node_from_dict: "proof node args/children must be list" ---


@pytest.mark.parametrize(
    ("root", "message"),
    [
        ({**_VALID_ROOT, "args": ("sentinel_7",)}, "proof node args must be list"),
        ({**_VALID_ROOT, "args": None}, "proof node args must be list"),
        ({**_VALID_ROOT, "children": ()}, "proof node children must be list"),
        ({**_VALID_ROOT, "children": None}, "proof node children must be list"),
        (
            {**_VALID_ROOT, "children": [{**_VALID_ROOT, "args": "sentinel_7"}]},
            "proof node args must be list",
        ),
    ],
)
def test_nested_node_shape_rejections_preserve_exact_value_error(root, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        souffle_proof_tree_from_dict({"query": "q", "root": root, "rules": {}})
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


# --- _souffle_proof_node_from_dict: "proof node row must be dict" ---


@pytest.mark.parametrize("row", [None, ["node"], "node"])
def test_node_decoder_rejects_non_dict_row_as_value_error(row):
    with pytest.raises(ValueError, match=re.escape("proof node row must be dict")) as caught:
        provenance._souffle_proof_node_from_dict(row)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "proof node row must be dict"


@pytest.mark.parametrize(
    "raw", [fixtures.DISPOSAL_JSON, fixtures.PASSIVATION_JSON], ids=["disposal", "passivation"]
)
def test_parsed_proof_tree_roundtrips_through_the_dict_shape(raw):
    trees = parse_souffle_proof_json(raw)
    assert len(trees) == 1
    decoded = souffle_proof_tree_from_dict(_tree_to_dict(trees[0]))
    assert decoded == trees[0]
    assert decoded.root.node_type == "derived"
    assert decoded.root.children[0].node_type == "axiom"
