"""Rule trace carriers and codecs retain their exact ValueError shape rejections.

Every guard in ``factgraph.core.rules._trace`` raises ``ValueError``: the module's
own public error ``RuleTraceSummaryError`` subclasses ``ValueError``,
``factgraph.audit.query`` wraps that family with ``except ValueError``, and the
``FileArtifactSidecar`` / ``Store._remember_rule_trace_artifact`` boundaries use
the same ``ValueError`` guards.  These tests pin the type-check guards so a
lint-driven ``TypeError`` switch cannot silently split that boundary.
"""

from __future__ import annotations

import json
import re

import pytest

from factgraph.core.rules._trace import (
    RuleRunResult,
    RuleTraceArtifact,
    RuleTraceInvocation,
    _normalize_binding_items,
    _normalize_detail_items,
    rule_trace_artifact_bytes,
    rule_trace_artifact_from_dict,
    rule_trace_artifact_to_dict,
)


def _invocation(**overrides):
    kwargs = {
        "invocation_id": "run-1:i1",
        "parent_invocation_id": None,
        "rule_id": "rule",
        "version": "v1",
        "memo_hit": False,
        "memo_source_invocation_id": None,
        "original_where": [["pred", "p", ["$x"]]],
        "rewritten_where": [["pred", "p", ["$x"]]],
        "bindings": ((("$x", "e1"),),),
        "output_rows": (("e1",),),
    }
    kwargs.update(overrides)
    return RuleTraceInvocation(**kwargs)


def _artifact() -> RuleTraceArtifact:
    return RuleTraceArtifact(
        rule_run_id="run-1",
        root_rule_id="rule",
        root_version="v1",
        select_vars=("$x",),
        invocations=(_invocation(),),
        root_rows=(("e1",),),
    )


@pytest.mark.parametrize("binding", [[("$x", "e1")], (("$x", "e1"),), "$x", None, 1])
def test_normalize_binding_items_rejects_non_dict_with_exact_value_error(binding):
    message = "binding must be dict[str, Any]"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _normalize_binding_items(binding)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_normalize_binding_items_accepts_dict_and_sorts_keys():
    assert _normalize_binding_items({"$y": 2, "$x": 1}) == (("$x", 1), ("$y", 2))


@pytest.mark.parametrize("details", [(("k", 1),), {("k", 1)}, "k", None, 1])
def test_normalize_detail_items_rejects_non_dict_non_list_with_exact_value_error(details):
    message = "details must be dict[str, Any] or list[tuple[str, Any]]"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _normalize_detail_items(details)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_normalize_detail_items_accepts_dict_and_list():
    assert _normalize_detail_items({"b": 2, "a": 1}) == (("a", 1), ("b", 2))
    assert _normalize_detail_items([("b", 2), ("a", 1)]) == (("a", 1), ("b", 2))


@pytest.mark.parametrize("memo_hit", [1, 0, "true", None])
def test_invocation_rejects_non_bool_memo_hit_with_exact_value_error(memo_hit):
    message = "memo_hit must be bool"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _invocation(memo_hit=memo_hit)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_invocation_accepts_bool_memo_hit():
    assert _invocation(memo_hit=False).memo_hit is False
    assert _invocation(memo_hit=True).memo_hit is True


def test_decoded_row_with_non_bool_memo_hit_rejects_with_exact_value_error():
    row = rule_trace_artifact_to_dict(_artifact())
    row["invocations"][0]["memo_hit"] = 1
    with pytest.raises(ValueError, match=re.escape("memo_hit must be bool")) as caught:
        rule_trace_artifact_from_dict(row)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("rows", [(), (("e1",),), None, "rows", {("e1",)}])
def test_rule_run_result_rejects_non_list_rows_with_exact_value_error(rows):
    message = "rows must be list[tuple[Any, ...]]"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        RuleRunResult(rule_run_id="run-1", rows=rows)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_rule_run_result_accepts_list_rows():
    assert RuleRunResult(rule_run_id="run-1", rows=[("e1",)]).rows == [("e1",)]
    assert RuleRunResult(rule_run_id="run-1", rows=[]).rows == []


@pytest.mark.parametrize("wrong", [None, {}, "artifact", ("run-1",), _invocation()])
def test_to_dict_rejects_non_artifact_with_exact_value_error(wrong):
    message = "artifact must be RuleTraceArtifact"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        rule_trace_artifact_to_dict(wrong)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize("row", [None, [], "row", 1, [("rule_run_id", "run-1")]])
def test_from_dict_rejects_non_mapping_row_with_exact_value_error(row):
    message = "row must be Mapping[str, Any]"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        rule_trace_artifact_from_dict(row)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_artifact_dict_and_bytes_round_trip():
    artifact = _artifact()
    assert rule_trace_artifact_from_dict(rule_trace_artifact_to_dict(artifact)) == artifact
    decoded = json.loads(rule_trace_artifact_bytes(artifact))
    assert rule_trace_artifact_from_dict(decoded) == artifact


def test_rule_trace_summary_error_is_value_error_subclass():
    from factgraph.core.rules._trace import RuleTraceSummaryError

    assert issubclass(RuleTraceSummaryError, ValueError)
    assert not issubclass(RuleTraceSummaryError, TypeError)
