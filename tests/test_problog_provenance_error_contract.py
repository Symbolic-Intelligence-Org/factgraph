"""Provenance decoding retains its existing exact rejection and wire shape."""

import re

import pytest

from factgraph.adapters.problog import provenance
from tests import test_problog_provenance_v0 as fixtures


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "row must be Mapping[str, Any]"),
        ({"events": (), "answers": []}, "row.events must be list"),
        ({"events": [], "answers": ()}, "row.answers must be list"),
        ({"events": [None], "answers": []}, "trace event row must be Mapping[str, Any]"),
        ({"events": [{"result_terms": ()}], "answers": []}, "trace event result_terms must be list"),
        ({"events": [], "answers": [None]}, "answer row must be Mapping[str, Any]"),
    ],
)
def test_trace_shape_rejections_preserve_exact_value_error(payload, message):
    if isinstance(payload, dict):
        payload = {"engine": "problog", "trace_type": "proof_trace", **payload}
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        provenance.problog_trace_from_dict(payload)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize(
    "decode", [provenance._resolve_candidate_info, provenance._candidate_binding_from_payload]
)
def test_candidate_terms_rejection_preserves_exact_value_error(decode):
    with pytest.raises(ValueError, match=r"candidate_payload\.terms must be list") as caught:
        decode({"pred_id": "c", "terms": ()})
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("raw", [fixtures._SUCCESS_TRACE, fixtures._FAIL_TRACE])
def test_existing_success_and_failure_traces_roundtrip_without_format_change(raw):
    trace = provenance.parse_problog_trace(raw)
    payload = provenance.problog_trace_to_dict(trace)
    restored = provenance.problog_trace_from_dict(payload)
    assert restored == trace
    assert provenance.problog_trace_to_dict(restored) == payload
