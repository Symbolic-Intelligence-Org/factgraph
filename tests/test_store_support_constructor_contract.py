"""Two adopted constructor exceptions, distinct from the Mapping decoder contract."""

from __future__ import annotations

from collections import UserDict
from types import MappingProxyType

import pytest

from factgraph.core.store import _support as support


class _TupleValues(tuple):
    pass


class _DictPayload(dict):
    pass


@pytest.mark.parametrize("value", [None, [], "tuple", 1, False, {"x": 1}])
def test_projected_fact_rejects_non_tuple_with_exact_value_error(value):
    with pytest.raises(ValueError) as caught:
        support.ProjectedFact("a1", value)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "ProjectedFact.fact_tuple must be tuple"


@pytest.mark.parametrize("value", [None, [], "dict", 1, False, (("x", 1),)])
def test_envelope_rejects_non_dict_with_exact_value_error(value):
    with pytest.raises(ValueError) as caught:
        support.ProvenanceEnvelope("c1", "problog", "trace", value)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "ProvenanceEnvelope.payload must be dict"


@pytest.mark.parametrize("values", [(), ("alice", 1, None), _TupleValues(("alice",))])
def test_projected_fact_preserves_valid_tuple_and_subclass(values):
    fact = support.ProjectedFact("a1", values)
    assert fact.asrt_id == "a1"
    assert fact.fact_tuple is values
    assert fact.witness_kind == "unknown"
    assert fact == support.ProjectedFact("a1", tuple(values), witness_kind="assertion")


@pytest.mark.parametrize("payload", [{}, {"events": []}, _DictPayload(events=[])])
def test_envelope_preserves_valid_dict_and_subclass(payload):
    envelope = support.ProvenanceEnvelope("c1", "problog", "trace", payload)
    assert envelope.payload is payload
    assert envelope.candidate_id == "c1"
    assert envelope.engine == "problog"
    assert envelope.payload_type == "trace"


@pytest.mark.parametrize(
    ("asrt_id", "values", "witness_kind", "message"),
    [
        ("", [], "invalid", "ProjectedFact.asrt_id must be non-empty string"),
        (None, [], "invalid", "ProjectedFact.asrt_id must be non-empty string"),
        ("a1", [], "invalid", "ProjectedFact.fact_tuple must be tuple"),
        ("a1", (), "invalid", "invalid projected witness kind"),
    ],
    ids=["empty-id-first", "wrong-id-first", "tuple-before-kind", "kind-after-tuple"],
)
def test_projected_fact_preserves_first_invalid_field(asrt_id, values, witness_kind, message):
    with pytest.raises(ValueError) as caught:
        support.ProjectedFact(asrt_id, values, witness_kind)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("candidate_id", "engine", "payload_type", "message"),
    [
        ("", "", "", "ProvenanceEnvelope.candidate_id must be non-empty string"),
        (None, None, None, "ProvenanceEnvelope.candidate_id must be non-empty string"),
        ("c1", "", "", "ProvenanceEnvelope.engine must be non-empty string"),
        ("c1", "problog", "", "ProvenanceEnvelope.payload_type must be non-empty string"),
        ("c1", "problog", "trace", "ProvenanceEnvelope.payload must be dict"),
    ],
    ids=["empty-id-first", "wrong-id-first", "engine-before-type", "type-before-payload", "payload-last"],
)
def test_envelope_preserves_first_invalid_field(candidate_id, engine, payload_type, message):
    with pytest.raises(ValueError) as caught:
        support.ProvenanceEnvelope(candidate_id, engine, payload_type, [])
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize("mapping_type", [MappingProxyType, UserDict])
def test_decoder_normalizes_non_dict_mapping_rejected_by_direct_constructor(mapping_type):
    payload = mapping_type({"events": []})
    with pytest.raises(ValueError) as caught:
        support.ProvenanceEnvelope("c1", "problog", "trace", payload)
    assert type(caught.value) is ValueError
    assert str(caught.value) == "ProvenanceEnvelope.payload must be dict"

    row = mapping_type({
        "candidate_id": "c1", "engine": "problog", "payload_type": "trace", "payload": payload,
    })
    envelope = support.provenance_envelope_from_dict(row)
    assert type(envelope.payload) is dict
    assert envelope.payload == {"events": []}
    assert envelope.payload is not payload
    assert payload == {"events": []}


@pytest.mark.parametrize("payload", [None, [], "invalid"])
def test_decoder_bad_payload_is_rejected_before_constructor(payload, monkeypatch):
    def forbidden_constructor(*args, **kwargs):
        raise AssertionError("invalid decoder input reached the constructor")

    monkeypatch.setattr(support, "ProvenanceEnvelope", forbidden_constructor)
    with pytest.raises(ValueError) as caught:
        support.provenance_envelope_from_dict({"payload": payload})
    assert type(caught.value) is ValueError
    assert str(caught.value) == "row.payload must be Mapping[str, Any]"


@pytest.mark.parametrize(
    ("payload", "expected_bytes", "expected_digest"),
    [
        (
            {},
            b'{"candidate_id":"c1","engine":"problog","payload":{},"payload_type":"trace"}',
            "sha256:2254e0720bfecc8104cc356dd5d3713bbb2a48d3a81bd6e56fa43096d4abb419",
        ),
        (
            {"labels": ["é", "alice"], "events": [{"weight": 0.75, "term": "Alice"}]},
            (
                b'{"candidate_id":"c1","engine":"problog","payload":{"events":'
                b'[{"term":"Alice","weight":0.75}],"labels":["\xc3\xa9","alice"]},"payload_type":"trace"}'
            ),
            "sha256:9b01399ac8e8cfbbe2bac0b2ff5f32f46eb3cce3a9c7363f74cb0676c094dcf1",
        ),
    ],
    ids=["empty-payload", "nested-unicode-and-float"],
)
def test_valid_provenance_bytes_digest_and_roundtrip_are_fixed(payload, expected_bytes, expected_digest):
    envelope = support.ProvenanceEnvelope("c1", "problog", "trace", payload)
    assert support.provenance_envelope_bytes(envelope) == expected_bytes
    assert support.compute_provenance_digest(envelope) == expected_digest
    decoded = support.provenance_envelope_from_dict(support.provenance_envelope_to_dict(envelope))
    assert decoded == envelope
    assert support.provenance_envelope_bytes(decoded) == expected_bytes
    assert support.compute_provenance_digest(decoded) == expected_digest
