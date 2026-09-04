"""ProbLog shared runtime options keep their documented ValueError rejection contract.

Adapter docs section 6A ("Shared runtime options") pin ``engine_options``
rejections to ``ValueError``.  The wrong-type cases below reach the
``raise ValueError`` site in ``resolve_problog_timeout`` with the input a
``TypeError`` rewrite would re-classify and pin the exact message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.adapters.problog.engine_eval import resolve_problog_timeout

# --- resolve_problog_timeout: "ProbLog engine_options must be dict[str, Any] or None" ---


@pytest.mark.parametrize(
    "engine_options",
    [[("timeout", 5)], ("timeout",), "30", 30, {"timeout", 5}],
)
def test_timeout_resolver_rejects_non_dict_engine_options_as_value_error(engine_options):
    expected = (
        "ProbLog engine_options must be dict[str, Any] or None, "
        f"got {type(engine_options).__name__}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolve_problog_timeout(engine_options)
    assert type(caught.value) is ValueError
    assert str(caught.value) == expected


def test_timeout_resolver_accepts_none_and_dict_engine_options():
    assert resolve_problog_timeout(None) == 30
    assert resolve_problog_timeout({}) == 30
    assert resolve_problog_timeout({"timeout": 7}) == 7


@pytest.mark.parametrize(
    ("engine_options", "message"),
    [
        (
            {"timesteps": 5},
            "Unsupported ProbLog engine_options: timesteps. Supported keys: timeout",
        ),
        ({"timeout": "slow"}, "ProbLog engine_options.timeout must be a positive int"),
        ({"timeout": True}, "ProbLog engine_options.timeout must be a positive int"),
        ({"timeout": 0}, "ProbLog engine_options.timeout must be a positive int"),
    ],
)
def test_timeout_resolver_sibling_rejections_share_the_value_error_family(engine_options, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        resolve_problog_timeout(engine_options)
    assert type(caught.value) is ValueError
