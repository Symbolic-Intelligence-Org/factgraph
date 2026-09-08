"""CandidateProvenanceTimeline helpers retain their exact ValueError shape rejections."""

from __future__ import annotations

from typing import Any

import pytest

from factgraph.core.store._candidate_provenance_timeline import (
    build_candidate_provenance_steps,
    build_candidate_provenance_timeline,
    render_candidate_provenance_timeline_narrative,
    render_candidate_provenance_timeline_nl_explain,
    summarize_candidate_provenance_timeline,
)
from tests import test_candidate_provenance_timeline as fixtures


def _trace() -> Any:
    return fixtures._StubTrace(
        timesteps=1,
        node_events=(
            fixtures._StubEvent(
                time=0,
                fixpoint_op=0,
                component="ACME",
                component_type="node",
                label="at_risk",
                old_bound=(0.0, 1.0),
                new_bound=(1.0, 1.0),
                occurred_due_to="seed_fact",
                clause_groundings=(),
            ),
        ),
        edge_events=(),
    )


def _timeline() -> dict[str, Any]:
    return build_candidate_provenance_timeline(
        candidate_id="cand-1",
        trace=_trace(),
        candidate_payload=fixtures._make_payload("vendor:at_risk", "ACME"),
    )


@pytest.mark.parametrize(
    "terms",
    [(), None, "ACME", ({"kind": "entity_ref", "value": "ACME"},), {"kind": "entity_ref"}],
)
def test_candidate_terms_rejection_preserves_exact_value_error(terms):
    with pytest.raises(ValueError, match=r"candidate_payload\.terms must be list") as caught:
        build_candidate_provenance_timeline(
            candidate_id="cand-1",
            trace=_trace(),
            candidate_payload={"pred_id": "vendor:at_risk", "terms": terms},
        )
    assert type(caught.value) is ValueError


def test_list_terms_build_timeline():
    timeline = _timeline()
    assert timeline["kind"] == "candidate_provenance_timeline"
    assert timeline["root_chain_key"] == ["node", "ACME", "at_risk"]


@pytest.mark.parametrize("chains", [(), None, "chains", {"0": {"events": []}}, 1])
def test_steps_reject_non_list_chains_with_exact_value_error(chains):
    with pytest.raises(ValueError, match=r"timeline\.chains must be list") as caught:
        build_candidate_provenance_steps({"chains": chains, "timesteps": 1})
    assert type(caught.value) is ValueError


def test_steps_accept_list_chains():
    steps = build_candidate_provenance_steps(_timeline())
    assert [step["step_kind"] for step in steps] == ["bound_seed", "convergence"]


@pytest.mark.parametrize("wrong", [None, [], "summary", 1, ("timesteps", 1)])
def test_nl_explain_rejects_non_mapping_summary_with_exact_value_error(wrong):
    narrative = render_candidate_provenance_timeline_narrative(_timeline())
    with pytest.raises(ValueError, match="summary must be object") as caught:
        render_candidate_provenance_timeline_nl_explain(wrong, narrative)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("wrong", [None, [], "narrative", 1, ("headline", "x")])
def test_nl_explain_rejects_non_mapping_narrative_with_exact_value_error(wrong):
    summary = summarize_candidate_provenance_timeline(_timeline())
    with pytest.raises(ValueError, match="narrative must be object") as caught:
        render_candidate_provenance_timeline_nl_explain(summary, wrong)
    assert type(caught.value) is ValueError


def test_nl_explain_accepts_mapping_summary_and_narrative():
    timeline = _timeline()
    summary = summarize_candidate_provenance_timeline(timeline)
    narrative = render_candidate_provenance_timeline_narrative(timeline)
    out = render_candidate_provenance_timeline_nl_explain(summary, narrative)
    assert out["headline"] == "at_risk: 1 chains, 1 timesteps across 1 timestep."
    assert out["paragraphs"][0].startswith("Overview: 1 propagation chain, 1 seeded")
