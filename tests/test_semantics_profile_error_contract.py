"""Public profile shape errors remain ValueError, not a lint-induced ABI change."""

import re

import pytest

from factgraph.sdk import SemanticsProfile


@pytest.mark.parametrize("kwargs,message", [
    ({"iteration_count": "3"}, "iteration_count must be int or None"),
    ({"iteration_count": True}, "iteration_count must be int or None"),
    ({"rule_projection": {"problog": 1}}, "rule_projection.problog must be list"),
    ({"rule_projection": {"problog": [1]}}, "rule_projection.problog[0] must be object"),
    ({"uncertainty_projection": {"probabilistic": 1}}, "uncertainty_projection.probabilistic must be object"),
    ({"engine_options": 1}, "engine_options must be object"),
])
def test_profile_shape_errors_preserve_exact_public_exception(kwargs, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        SemanticsProfile(name="test", engine="native", **kwargs)
    assert type(caught.value) is ValueError


def test_valid_profile_still_normalizes_without_rejecting_legal_buckets():
    profile = SemanticsProfile(
        name="test", engine="native", iteration_count=3,
        engine_options={"option": "value"},
        uncertainty_projection={"probabilistic": {"policy": "identity_probability"}},
        rule_projection={"problog": [{"target": "rule", "kind": "probability"}]},
    )
    assert profile.iteration_count == 3
    assert profile.engine_options == {"option": "value"}
    assert profile.rule_projection == {"problog": [{"target": "rule", "kind": "probability"}]}
