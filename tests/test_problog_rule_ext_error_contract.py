"""ProbLog rule-extension carriers keep their ValueError rejection contract.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.problog.rule_ext`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
"""

from __future__ import annotations

import re

import pytest

from factgraph.adapters.problog.rule_ext import ProbLogRuleExt, resolve_problog_engine_ext
from factgraph.core.semantics import SemanticsProfile

_WHERE = [
    [("pred", "user:tag_seed", ["$u", "vip"])],
    [("pred", "user:tag_seed", ["$u", "trial"])],
]


def _profile(entries: list[dict[str, object]]) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.c.problog",
        engine="problog",
        rule_projection={"problog": entries},
    )


# --- normalize_problog_case_probabilities: "<field>[<idx>] must be float in (0,1]" ---


@pytest.mark.parametrize(
    ("case_probabilities", "message"),
    [
        (("0.5",), "case_probabilities[0] must be float in (0,1]"),
        ((True,), "case_probabilities[0] must be float in (0,1]"),
        ((None,), "case_probabilities[0] must be float in (0,1]"),
        ([0.5, "0.6"], "case_probabilities[1] must be float in (0,1]"),
    ],
)
def test_rule_ext_rejects_non_numeric_case_probability_as_value_error(case_probabilities, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        ProbLogRuleExt(case_probabilities=case_probabilities)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("legacy", "message"),
    [
        (["0.7"], "body_confidences[0] must be float in (0,1]"),
        ([True], "body_confidences[0] must be float in (0,1]"),
        ([0.7, None], "body_confidences[1] must be float in (0,1]"),
    ],
)
def test_resolver_rejects_non_numeric_legacy_body_confidence_as_value_error(legacy, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        resolve_problog_engine_ext(where=_WHERE, engine_ext=None, legacy_body_confidences=legacy)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_rule_ext_and_resolver_accept_numeric_probabilities():
    assert ProbLogRuleExt(case_probabilities=[0.5, 1]).case_probabilities == (0.5, 1.0)
    resolved = resolve_problog_engine_ext(
        where=_WHERE, engine_ext=None, legacy_body_confidences=[0.7, 0.9]
    )
    assert isinstance(resolved, ProbLogRuleExt)
    assert resolved.case_probabilities == (0.7, 0.9)


# --- _materialize_profile_case_probabilities: "semantics_profile must be SemanticsProfile or None" ---


@pytest.mark.parametrize("profile", ["problog", {"engine": "problog"}, 1])
def test_resolver_rejects_non_profile_as_value_error(profile):
    expected = f"semantics_profile must be SemanticsProfile or None, got {type(profile).__name__}"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolve_problog_engine_ext(where=_WHERE, engine_ext=None, semantics_profile=profile)
    assert type(caught.value) is ValueError
    assert str(caught.value) == expected


# --- _normalize_profile_probability: "rule_projection.problog[<idx>].value must be float" ---


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            [{"target": "branch:0", "kind": "branch_probability", "value": "0.4"}],
            "rule_projection.problog[0].value must be float in (0,1]",
        ),
        (
            [{"target": "branch:0", "kind": "branch_probability", "value": True}],
            "rule_projection.problog[0].value must be float in (0,1]",
        ),
        (
            [{"target": "branch:0", "kind": "branch_probability"}],
            "rule_projection.problog[0].value must be float in (0,1]",
        ),
        (
            [
                {"target": "branch:0", "kind": "branch_probability", "value": 0.4},
                {"target": "branch:1", "kind": "branch_probability", "value": [0.6]},
            ],
            "rule_projection.problog[1].value must be float in (0,1]",
        ),
    ],
)
def test_resolver_rejects_non_numeric_profile_value_as_value_error(entries, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        resolve_problog_engine_ext(
            where=_WHERE, engine_ext=None, semantics_profile=_profile(entries)
        )
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_resolver_accepts_real_problog_profile():
    resolved = resolve_problog_engine_ext(
        where=_WHERE,
        engine_ext=None,
        semantics_profile=_profile(
            [{"target": "branch:0", "kind": "branch_probability", "value": 0.4}]
        ),
    )
    assert isinstance(resolved, ProbLogRuleExt)
    assert resolved.case_probabilities == (0.4, 1.0)
