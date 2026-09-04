"""``narrate_structure`` keeps its ValueError rejection contract.

``RuleStructure.narrate()`` delegates to ``narrate_structure``, which is the
static sibling of the Explain renderers in
``factgraph.application.protocol.explanation_render``.  A non-RuleStructure
argument is rejected as ``ValueError`` with this exact message.  The case below
reaches the ``raise ValueError`` site with a wrong-type input and pins it.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.protocol.rule_structure import RuleStructure
from factgraph.application.protocol.structure_render import narrate_structure

_MESSAGE = "structure must be RuleStructure"


def _structure() -> RuleStructure:
    return RuleStructure(
        structure_id="structure-1",
        source_kind="rule",
        head_rule_id="person_age",
        head_binding_kind="external",
        ast=(),
        branches=(),
    )


@pytest.mark.parametrize("structure", ["structure", None, object(), {}, ()])
def test_narrate_structure_rejects_non_rule_structure_as_value_error(structure):
    with pytest.raises(ValueError, match=re.escape(_MESSAGE)) as caught:
        narrate_structure(structure)
    assert type(caught.value) is ValueError
    assert str(caught.value) == _MESSAGE


def test_narrate_structure_accepts_a_rule_structure():
    assert narrate_structure(_structure()) == ()
