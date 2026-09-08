"""Characterize serialization before lint-only expression decomposition."""

import hashlib
from types import SimpleNamespace

import pytest

from factgraph.adapters.problog.problog_export import _choice_predicate_digest
from factgraph.application.evaluation_run_bundle_runtime import _ir_from_wire
from factgraph.application.protocol.evaluation_run_bundle import _finite_hex_float
from factgraph.application.protocol.rule_expr_lowering import _query_navigation_lookup_var


def test_choice_digest_preserves_separator_and_unicode_bytes():
    choice = SimpleNamespace(choice_node_id="node:α", topology_digest="digest")
    expected = hashlib.sha256(b"node:\xce\xb1\x1fdigest\x1farm").hexdigest()[:32]
    assert _choice_predicate_digest(choice, "arm") == expected


def test_choice_digest_does_not_coerce_non_string_arm():
    choice = SimpleNamespace(choice_node_id="node", topology_digest="digest")
    with pytest.raises(TypeError, match="sequence item 2: expected str instance, int found"):
        _choice_predicate_digest(choice, 17)


def test_navigation_digest_preserves_separator_and_field_order():
    lookup = SimpleNamespace(
        branch_id="b",
        head_port_name="h",
        occurrence_alias="o",
        port_name="p",
        field_predicate_id="f",
    )
    expected = hashlib.sha256(b"b\x00h\x00o\x00p\x00f").hexdigest()[:20]
    assert _query_navigation_lookup_var(lookup).name == f"$__query_navigation__{expected}"
    lookup.port_name = None
    with pytest.raises(TypeError, match="sequence item 3: expected str instance, NoneType found"):
        _query_navigation_lookup_var(lookup)


@pytest.mark.parametrize(
    "decode", [_finite_hex_float, lambda token: _ir_from_wire({"$float64": token}, 0)]
)
@pytest.mark.parametrize(
    ("token", "expected"),
    [("0x3ff0000000000000", 1.0), ("0x0000000000000000", 0.0), ("0xbff0000000000000", -1.0)],
)
def test_float_decoders_preserve_finite_values(decode, token, expected):
    assert decode(token) == expected


@pytest.mark.parametrize(
    "decode", [_finite_hex_float, lambda token: _ir_from_wire({"$float64": token}, 0)]
)
@pytest.mark.parametrize(
    "token",
    ["0x8000000000000000", "0x7ff0000000000000", "0x7ff8000000000000", "0xzzzzzzzzzzzzzzzz", "0x1"],
)
def test_float_decoders_continue_rejecting_invalid_tokens(decode, token):
    from factgraph.application.protocol import ProtocolShapeError

    with pytest.raises(ProtocolShapeError):
        decode(token)
