"""The public evidence renderers keep their ValueError rejection contract.

``walk_evidence`` and ``narrate_evidence`` are exported from
``factgraph.application.protocol`` and back ``Explanation.repr`` /
``Explanation.narrate``.  They share the codec family already pinned for
``evidence_graph_to_dict`` in
``tests/application/explain/test_evidence_codec_errors.py``: a non-EvidenceGraph
argument is a ``ValueError`` with this exact message.  Every case below reaches
the ``raise ValueError`` site with a wrong-type input and pins that message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.explain.evidence_tree import LAYOUT_TREE, EvidenceGraph
from factgraph.application.protocol.explanation_render import (
    narrate_evidence,
    walk_evidence,
)

_MESSAGE = "graph must be EvidenceGraph"


def _graph() -> EvidenceGraph:
    return EvidenceGraph(
        graph_id="graph-1",
        engine="native",
        layout_hint=LAYOUT_TREE,
        subject_binding={},
        paths=(),
    )


@pytest.mark.parametrize("renderer", [walk_evidence, narrate_evidence])
@pytest.mark.parametrize("graph", ["graph", None, object(), {}, ()])
def test_renderers_reject_non_evidence_graph_as_value_error(renderer, graph):
    with pytest.raises(ValueError, match=re.escape(_MESSAGE)) as caught:
        renderer(graph)
    assert type(caught.value) is ValueError
    assert str(caught.value) == _MESSAGE


@pytest.mark.parametrize("renderer", [walk_evidence, narrate_evidence])
def test_renderers_accept_an_evidence_graph(renderer):
    assert isinstance(renderer(_graph()), tuple)
