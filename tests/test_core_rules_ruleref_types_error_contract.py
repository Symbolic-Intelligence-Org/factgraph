"""``NativeRuleRefResolution`` keeps one ValueError rejection family.

``factgraph.core.rules.ruleref_types`` carries the RuleRef support DTOs that
``ruleref_substrate`` builds and ``core.store._support_capture`` persists.  The
``row_supports`` shape guard sits in the same ``__post_init__`` as the sort-order
guard (``row_supports must be sorted by row_terms``), a value-domain rejection
that must stay ``ValueError``; callers catch the DTO family with a single
``except ValueError``.  These tests pin the exact types and messages.
"""

from __future__ import annotations

import re

import pytest

from factgraph.core.rules.ruleref_types import (
    NativeRuleRefResolution,
    NativeRuleRefRowSupport,
)


def _resolution(row_supports):
    return NativeRuleRefResolution(
        ruleref_condition_key="cond-1",
        rule_ref_id="child",
        rule_ref_version="1",
        row_supports=row_supports,
    )


def _support(term: str) -> NativeRuleRefRowSupport:
    return NativeRuleRefRowSupport(row_terms=(term,), child_support_digest="sha256:" + term)


@pytest.mark.parametrize("row_supports", [None, [], "rows", 1, {_support("a")}])
def test_resolution_rejects_non_tuple_row_supports_with_exact_value_error(row_supports):
    message = "row_supports must be tuple"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _resolution(row_supports)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_resolution_accepts_tuple_row_supports():
    assert _resolution(()).row_supports == ()
    supports = (_support("a"), _support("b"))
    assert _resolution(supports).row_supports == supports


def test_resolution_sort_order_guard_shares_the_value_error_family():
    with pytest.raises(ValueError, match=re.escape("row_supports must be sorted by row_terms")):
        _resolution((_support("b"), _support("a")))
