"""Output variables are not values; only a zero query variant means no answer."""

from __future__ import annotations

import pytest

from factgraph.adapters.problog.problog_import import ProbLogImportError, _parse_rows


@pytest.mark.parametrize(
    "args,query_vars",
    [
        ("X3,X4", ["$person", "$tag"]),
        ("_A,_B", ["$person", "$tag"]),
        ("X3,X3", ["$person", "$person"]),
        ("_,_", ["$person", "$tag"]),
    ],
)
def test_zero_variable_renaming_is_empty(args, query_vars):
    assert _parse_rows(f"answer({args}): 0", query_pred="answer", query_vars=query_vars) == []


@pytest.mark.parametrize(
    "args,prob",
    [
        ("X3,X4", "0.82"),
        ("'alice',X4", "0"),
        ("X3,'tag'", "0"),
        ("f(X3),'tag'", "0"),
        ("[a,X3],'tag'", "0.8"),
        ("X3,X3", "0"),  # Not a renaming of distinct submitted variables.
        ("'alice','tag'", "nan"),
        ("'alice','tag'", "inf"),
        ("'alice','tag'", "1e999"),
        ("'alice','tag'", "-0.1"),
        ("'alice','tag'", "1.1"),
        ("'unterminated,tag", "0.2"),
        ("f(a],'tag'", "0.2"),
        (",'tag'", "0.2"),
    ],
)
def test_malformed_or_non_ground_output_fails_closed(args, prob):
    with pytest.raises(ProbLogImportError):
        _parse_rows(f"answer({args}): {prob}", query_pred="answer", query_vars=["$person", "$tag"])


@pytest.mark.parametrize("args", ["X3,X4", "_,_"])
def test_zero_variant_preserves_repeated_query_variable_pattern(args):
    with pytest.raises(ProbLogImportError):
        _parse_rows(f"answer({args}): 0", query_pred="answer", query_vars=["$x", "$x"])


@pytest.mark.parametrize(
    "args,expected",
    [
        ("'X3','_'", ("X3", "_")),
        ('"X3","_"', ("X3", "_")),
        ("'Alice''s X3','tag'", ("Alice's X3", "tag")),
        ('\'{"name":"X3"}\',tag', ('{"name":"X3"}', "tag")),
        ("1e-3,true", (0.001, True)),
        ("f('X3'),false", ("f('X3')", False)),
    ],
)
def test_ground_values_including_zero_keep_existing_decoding(args, expected):
    assert _parse_rows(
        f"answer({args}): 0",
        query_pred="answer",
        query_vars=["$x", "$y"],
    ) == [({"$x": expected[0], "$y": expected[1]}, 0.0)]


def test_late_invalid_row_cannot_return_partial_results():
    with pytest.raises(ProbLogImportError):
        _parse_rows(
            "answer('alice','tag'): 0.82\nanswer(X3,X4): 0.5",
            query_pred="answer",
            query_vars=["$x", "$y"],
        )


def test_escaped_quote_and_nested_variable_are_inspected_before_decoding():
    assert _parse_rows(
        r"answer('Alice\'s, X3','_'): 0",
        query_pred="answer",
        query_vars=["$x", "$y"],
    ) == [({"$x": r"Alice\'s, X3", "$y": "_"}, 0.0)]
    with pytest.raises(ProbLogImportError):
        _parse_rows(
            r"answer(f('Alice\'s, X3',X4),'_'): 0",
            query_pred="answer",
            query_vars=["$x", "$y"],
        )


@pytest.mark.parametrize(
    "term", ["f(a,,b)", "foo bar", "'quoted'trailing", "[a,]", "f()", "a)garbage("]
)
def test_invalid_ground_syntax_is_not_a_string_value(term):
    with pytest.raises(ProbLogImportError):
        _parse_rows(f"answer({term}): 0.3", query_pred="answer", query_vars=["$value"])
