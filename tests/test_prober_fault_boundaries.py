"""Fault-injection contract for the broad boundaries in ``application.explain.prober``.

The prober is a *rendering / diagnosis* surface. Every ``except Exception`` there
is a display boundary: a fault in a foreign renderer, in schema entity-repr
rendering, in identity recovery from view facts, in float64 decoding, or in
where-AST parsing must degrade to the documented fallback string (or to an empty
bound-var set) — it must never produce a wrong-but-confident repr and must never
escape into the caller's explain result.

These tests inject a custom ``Exception`` subclass (and a ``LookupError``) at
each ``# noqa: BLE001`` / ``# noqa: ... S110`` site and pin the exact fallback,
plus the fact that ``KeyboardInterrupt`` is never swallowed.
"""

from __future__ import annotations

import pytest

from factgraph.application.explain import prober
from factgraph.application.explain.evidence_tree import Const, Fact
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.core.protocol.tup_v1 import ENTITY_REF_PREFIX
from factgraph.core.rules.where_ast import AggregateAtom


class RenderFault(Exception):
    """A renderer fault class the prober has no special knowledge of."""


_SENTINEL_INDEX = object()
_REF = EntityRef(entity_type="User", identity={"name": "alice"}, encoded_ref="idref_v1:User:alice")
_ENCODED = f"{ENTITY_REF_PREFIX}User:alice"
_FAULTS = [RenderFault("repr template exploded"), LookupError("repr template exploded")]


def _raiser(exc: BaseException):
    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


# --------------------------------------------------------------------------
# _render_rule_repr — foreign render_repr callable (prober.py:537)
# --------------------------------------------------------------------------


class _Rule:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def render_repr(self, _bindings):
        raise self._exc


@pytest.mark.parametrize("fault", _FAULTS)
def test_render_rule_repr_degrades_to_none_on_renderer_fault(fault) -> None:
    assert prober._render_rule_repr(_Rule(fault), {"$u": "alice"}) is None


def test_render_rule_repr_does_not_swallow_keyboard_interrupt() -> None:
    with pytest.raises(KeyboardInterrupt):
        prober._render_rule_repr(_Rule(KeyboardInterrupt()), {"$u": "alice"})


# --------------------------------------------------------------------------
# _entity_repr_for_fact — prober.py:852 / 860 / 868
# --------------------------------------------------------------------------


def _fact(value) -> Fact:
    return Fact(predicate="User:name", terms=(Const(value),))


@pytest.mark.parametrize("fault", _FAULTS)
@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        (_REF, "idref_v1:User:alice"),
        ({"entity_type": "User", "identity": {"name": "alice"}}, None),
        (_ENCODED, _ENCODED),
    ],
    ids=["entity-ref-852", "mapping-ref-860", "encoded-ref-868"],
)
def test_entity_repr_for_fact_degrades_to_raw_term_rendering(
    monkeypatch, fault, subject, expected
) -> None:
    monkeypatch.setattr(prober.schema_runtime, "render_entity_repr", _raiser(fault))
    monkeypatch.setattr(prober, "_recover_identity_from_predicates", _raiser(fault))

    rendered = prober._entity_repr_for_fact(
        _SENTINEL_INDEX, "User", _fact(subject), view_facts={}
    )

    fallback = prober._render_term_value(
        Const(subject), schema_index=_SENTINEL_INDEX, view_facts={}
    )
    assert rendered == fallback
    assert "repr template exploded" not in rendered
    if expected is not None:
        assert rendered == expected


@pytest.mark.parametrize("subject", [_REF, {"entity_type": "User", "identity": {"name": "a"}}])
def test_entity_repr_for_fact_does_not_swallow_keyboard_interrupt(monkeypatch, subject) -> None:
    monkeypatch.setattr(
        prober.schema_runtime, "render_entity_repr", _raiser(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        prober._entity_repr_for_fact(_SENTINEL_INDEX, "User", _fact(subject), view_facts={})


# --------------------------------------------------------------------------
# _render_term_value — prober.py:977 / 985 / 995 / 1000
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fault", _FAULTS)
def test_render_term_value_entity_ref_falls_back_to_encoded_ref(monkeypatch, fault) -> None:
    monkeypatch.setattr(prober.schema_runtime, "render_entity_repr", _raiser(fault))
    rendered = prober._render_term_value(
        Const(_REF), schema_index=_SENTINEL_INDEX, view_facts={}
    )
    assert rendered == _REF.encoded_ref


@pytest.mark.parametrize("fault", _FAULTS)
def test_render_term_value_mapping_ref_falls_through_to_str(monkeypatch, fault) -> None:
    """prober.py:985 — the swallowed fault must fall through, not fake a repr."""
    monkeypatch.setattr(prober.schema_runtime, "render_entity_repr", _raiser(fault))
    value = {"entity_type": "User", "identity": {"name": "alice"}}
    rendered = prober._render_term_value(
        Const(value), schema_index=_SENTINEL_INDEX, view_facts={}
    )
    assert rendered == str(value)
    assert "repr template exploded" not in rendered


@pytest.mark.parametrize("fault", _FAULTS)
def test_render_term_value_encoded_ref_falls_through_to_str(monkeypatch, fault) -> None:
    """prober.py:995 — identity recovery faults must not fabricate an entity label."""
    monkeypatch.setattr(prober, "_recover_identity_from_predicates", _raiser(fault))
    rendered = prober._render_term_value(
        Const(_ENCODED), schema_index=_SENTINEL_INDEX, view_facts={}
    )
    assert rendered == _ENCODED


@pytest.mark.parametrize("fault", _FAULTS)
def test_render_term_value_float64_decode_falls_through_to_str(monkeypatch, fault) -> None:
    """prober.py:1000 — an undecodable float64 payload renders as its raw string."""
    monkeypatch.setattr(prober, "display_float64_value", _raiser(fault))
    rendered = prober._render_term_value(
        Const("f64:garbage"), schema_index=None, view_facts={}, decode_float64=True
    )
    assert rendered == "f64:garbage"


def test_render_term_value_does_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    monkeypatch.setattr(
        prober.schema_runtime, "render_entity_repr", _raiser(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        prober._render_term_value(Const(_REF), schema_index=_SENTINEL_INDEX, view_facts={})

    monkeypatch.setattr(prober, "display_float64_value", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        prober._render_term_value(
            Const("f64:garbage"), schema_index=None, view_facts={}, decode_float64=True
        )


# --------------------------------------------------------------------------
# _canonical_aggregate_filter_bound_vars — prober.py:1158 / 1164
# --------------------------------------------------------------------------

_AGG_TERM = ("count", "$x", [])


@pytest.mark.parametrize("fault", _FAULTS)
def test_canonical_aggregate_bound_vars_empty_on_parse_fault(monkeypatch, fault) -> None:
    monkeypatch.setattr(prober, "_parse_term", _raiser(fault))
    assert prober._canonical_aggregate_filter_bound_vars(_AGG_TERM, {"$u": 1}) == set()


@pytest.mark.parametrize("fault", _FAULTS)
def test_canonical_aggregate_bound_vars_empty_on_analysis_fault(monkeypatch, fault) -> None:
    parsed = AggregateAtom(kind="count", target=None, filter=[])
    monkeypatch.setattr(prober, "_parse_term", lambda *a, **k: parsed)
    monkeypatch.setattr(prober, "_aggregate_filter_bound_vars", _raiser(fault))
    assert prober._canonical_aggregate_filter_bound_vars(_AGG_TERM, {"$u": 1}) == set()


def test_canonical_aggregate_bound_vars_does_not_swallow_keyboard_interrupt(monkeypatch) -> None:
    monkeypatch.setattr(prober, "_parse_term", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        prober._canonical_aggregate_filter_bound_vars(_AGG_TERM, {"$u": 1})

    parsed = AggregateAtom(kind="count", target=None, filter=[])
    monkeypatch.setattr(prober, "_parse_term", lambda *a, **k: parsed)
    monkeypatch.setattr(prober, "_aggregate_filter_bound_vars", _raiser(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        prober._canonical_aggregate_filter_bound_vars(_AGG_TERM, {"$u": 1})
