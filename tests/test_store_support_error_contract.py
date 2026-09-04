"""Support and provenance decoders retain their exact ValueError shape rejections."""

from __future__ import annotations

import re

import pytest

from factgraph.core.store._support import (
    ProofReceipt,
    ProvenanceEnvelope,
    provenance_envelope_from_dict,
    provenance_envelope_to_dict,
    support_artifact_from_dict,
    support_artifact_to_dict,
)


@pytest.mark.parametrize("row", [None, [], "row", 1, [("kind", "native_binding_v1")]])
def test_support_artifact_row_rejection_preserves_exact_value_error(row):
    with pytest.raises(ValueError, match=re.escape("row must be Mapping[str, Any]")) as caught:
        support_artifact_from_dict(row)
    assert type(caught.value) is ValueError


def test_support_artifact_mapping_row_roundtrips():
    receipt = ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="fact",
        binding_items=(("$x", "e1"),),
        pred_witnesses=(),
    )
    assert support_artifact_from_dict(support_artifact_to_dict(receipt)) == receipt


@pytest.mark.parametrize("row", [None, [], "row", 1, [("candidate_id", "cand-1")]])
def test_provenance_envelope_row_rejection_preserves_exact_value_error(row):
    with pytest.raises(ValueError, match=re.escape("row must be Mapping[str, Any]")) as caught:
        provenance_envelope_from_dict(row)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("payload", [None, [], "payload", 1, [("events", [])]])
def test_provenance_envelope_payload_rejection_preserves_exact_value_error(payload):
    row = {
        "candidate_id": "cand-1",
        "engine": "pyreason",
        "payload_type": "event_log",
        "payload": payload,
    }
    message = "row.payload must be Mapping[str, Any]"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        provenance_envelope_from_dict(row)
    assert type(caught.value) is ValueError


def test_provenance_envelope_mapping_row_roundtrips():
    envelope = ProvenanceEnvelope(
        candidate_id="cand-1",
        engine="pyreason",
        payload_type="event_log",
        payload={"events": [1, 2], "timesteps": 1},
    )
    assert provenance_envelope_from_dict(provenance_envelope_to_dict(envelope)) == envelope
