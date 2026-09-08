"""build_candidate_evidence_tree retains its exact ValueError shape rejections."""

from __future__ import annotations

import re
from typing import Any

import pytest

from factgraph.core.store._candidate_evidence_tree import build_candidate_evidence_tree

_DIGEST = "sha256:" + "0" * 64


def _support(**overrides: Any) -> dict[str, Any]:
    support: dict[str, Any] = {
        "binding": [["$x", "e1"]],
        "pred_witnesses": [{"pred_condition_key": "c0.c0:p", "asrt_ids": ["a1"]}],
        "non_fact_steps": [],
        "rule_refs": [],
        "rule_ref_edges": [],
        "root_result_kind": "fact",
    }
    support.update(overrides)
    return support


def _detail(**overrides: Any) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "claim": {"pred_id": "p", "e_ref": "e1"},
        "claim_args": [{"idx": 0, "tag": "entity_ref", "val": "e1"}],
    }
    detail.update(overrides)
    return detail


def _build(support: Any, detail: Any) -> dict[str, Any]:
    return build_candidate_evidence_tree(
        candidate_id="cand-1",
        support_digest=_DIGEST,
        support_kind="native_binding_v1",
        support=support,
        assertion_lookup=lambda asrt_id: detail,
        support_lookup=lambda digest: None,
    )


def test_mapping_support_and_detail_build_tree():
    tree = _build(_support(), _detail())
    assert tree["kind"] == "candidate_evidence_tree"
    section = tree["root"]["children"][0]
    assert section["node_kind"] == "support_section"
    leaf = section["children"][0]["children"][0]
    assert leaf["node_kind"] == "assertion_fact"
    assert leaf["asrt_id"] == "a1"
    assert leaf["claim_args"] == [{"idx": 0, "tag": "entity_ref", "val": "e1"}]


@pytest.mark.parametrize("support", [None, [], (), "support", [("binding", [])]])
def test_non_mapping_support_rejection_preserves_exact_value_error(support):
    with pytest.raises(ValueError, match=re.escape("support must be mapping")) as caught:
        _build(support, _detail())
    assert type(caught.value) is ValueError


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"binding": ()}, "support.binding must be list"),
        ({"binding": {"$x": "e1"}}, "support.binding must be list"),
        ({"pred_witnesses": ()}, "support.pred_witnesses must be list"),
        ({"pred_witnesses": None}, "support.pred_witnesses must be list"),
        ({"rule_ref_edges": ()}, "support.rule_ref_edges must be list"),
        ({"rule_ref_edges": [["c0.c1:r", "r", "v1"]]}, "support.rule_ref_edges[0] must be mapping"),
        ({"rule_ref_edges": [None]}, "support.rule_ref_edges[0] must be mapping"),
    ],
)
def test_support_field_shape_rejections_preserve_exact_value_error(overrides, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _build(_support(**overrides), _detail())
    assert type(caught.value) is ValueError


@pytest.mark.parametrize(
    ("detail", "message"),
    [
        (None, "assertion detail not found for asrt_id='a1'"),
        ([("claim", {"pred_id": "p", "e_ref": "e1"})], "assertion detail not found for asrt_id='a1'"),
        (_detail(claim=["p", "e1"]), "assertion detail missing claim for asrt_id='a1'"),
        (_detail(claim="p:e1"), "assertion detail missing claim for asrt_id='a1'"),
        (_detail(claim=None), "assertion detail missing claim for asrt_id='a1'"),
        (_detail(claim_args=({"idx": 0, "tag": "entity_ref", "val": "e1"},)), "a1.claim_args must be list"),
        (_detail(claim_args=[["idx", 0]]), "a1.claim_args[0] must be mapping"),
        (_detail(claim_args=[None]), "a1.claim_args[0] must be mapping"),
        (_detail(claim_args=[{"idx": "0", "tag": "entity_ref", "val": "e1"}]), "a1.claim_args[0].idx must be int"),
        (_detail(claim_args=[{"idx": 0.0, "tag": "entity_ref", "val": "e1"}]), "a1.claim_args[0].idx must be int"),
        (_detail(claim_args=[{"idx": True, "tag": "entity_ref", "val": "e1"}]), "a1.claim_args[0].idx must be int"),
    ],
)
def test_assertion_detail_shape_rejections_preserve_exact_value_error(detail, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _build(_support(), detail)
    assert type(caught.value) is ValueError
