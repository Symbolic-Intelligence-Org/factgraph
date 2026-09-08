"""PyReason rule_ext wrong-type rejections stay ValueError at their documented boundaries.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.pyreason.rule_ext`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pytest

from factgraph.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    PyReasonRuleExt,
    resolve_pyreason_engine_ext,
)
from factgraph.adapters.pyreason.where_compile import (
    PyReasonWhereCompileError,
    compile_where_ir_to_pyreason,
)
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store.types import EngineExtBase

_WHERE = [("pred", "user:name", ["$u", "$name"])]
_SCHEMA_IR = {
    "predicates": [
        {"pred_id": "user:name", "arity": 2},
        {"pred_id": "user:popular", "arity": 2},
    ],
}
_PROFILE_VALUE_PATH = "SemanticsProfile.rule_projection.pyreason[0].value"


@dataclass(frozen=True)
class _ForeignEngineExt(EngineExtBase):
    """An EngineExtBase carrier that is not a PyReasonRuleExt."""

    knob: int = 1


@dataclass(frozen=True)
class _DuckRuleExt(EngineExtBase):
    """Duck-typed carrier read by where_compile through getattr."""

    timestep_delay: int = 0
    body_predicate_bounds: object = field(default_factory=dict)
    head_bound: object = None


def _profile(entries: list[dict[str, object]]) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.t1a.pyreason",
        engine="pyreason",
        rule_projection={"pyreason": entries},
    )


# --- PyReasonRuleExt.__post_init__: "timestep_delay must be int" ---


@pytest.mark.parametrize("delay", ["1", 1.0, True, None])
def test_rule_ext_wrong_type_timestep_delay_is_value_error(delay):
    with pytest.raises(ValueError, match=re.escape("timestep_delay must be int")) as caught:
        PyReasonRuleExt(timestep_delay=delay)
    assert type(caught.value) is ValueError


def test_rule_ext_int_timestep_delay_is_accepted():
    assert PyReasonRuleExt(timestep_delay=2).timestep_delay == 2


# --- PyReasonFactDef.__post_init__: "start must be int" / "end must be int" ---


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start": "0"}, "start must be int"),
        ({"start": True}, "start must be int"),
        ({"start": 0.0}, "start must be int"),
        ({"end": "3"}, "end must be int"),
        ({"end": False}, "end must be int"),
        ({"end": None}, "end must be int"),
    ],
)
def test_fact_def_wrong_type_start_end_is_value_error(kwargs, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        PyReasonFactDef(atom="popular(Alice)", name="alice_pop", **kwargs)
    assert type(caught.value) is ValueError


# --- PyReasonFactDef.__post_init__: "bound[0] must be numeric" / "bound[1] must be numeric" ---


@pytest.mark.parametrize(
    ("bound", "message"),
    [
        (["0.5", 1.0], "bound[0] must be numeric"),
        ([True, 1.0], "bound[0] must be numeric"),
        ([None, 1.0], "bound[0] must be numeric"),
        ([0.5, "1.0"], "bound[1] must be numeric"),
        ([0.5, False], "bound[1] must be numeric"),
    ],
)
def test_fact_def_non_numeric_bound_is_value_error(bound, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        PyReasonFactDef(atom="popular(Alice)", name="alice_pop", bound=bound)
    assert type(caught.value) is ValueError


def test_fact_def_int_times_and_numeric_bound_are_accepted():
    fact = PyReasonFactDef(atom="popular(Alice)", name="alice_pop", start=0, end=3, bound=[0.5, 1])
    assert (fact.start, fact.end) == (0, 3)
    assert tuple(fact.bound) == (0.5, 1)


# --- _normalize_pyreason_engine_ext: "PyReason engine_ext must be PyReasonRuleExt or None" ---


def test_resolver_rejects_foreign_engine_ext_as_value_error():
    expected = "PyReason engine_ext must be PyReasonRuleExt or None, got _ForeignEngineExt"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolve_pyreason_engine_ext(
            where=_WHERE,
            schema_ir=_SCHEMA_IR,
            engine_ext=_ForeignEngineExt(),
            semantics_profile=None,
        )
    assert type(caught.value) is ValueError


def test_resolver_accepts_pyreason_rule_ext_carrier():
    resolved = resolve_pyreason_engine_ext(
        where=_WHERE,
        schema_ir=_SCHEMA_IR,
        engine_ext=PyReasonRuleExt(timestep_delay=1, head_bound=(0.5, 1.0)),
        semantics_profile=None,
    )
    assert isinstance(resolved, PyReasonRuleExt)
    assert resolved.timestep_delay == 1
    assert tuple(resolved.head_bound or ()) == (0.5, 1.0)


# --- _materialize_profile_rule_ext: "semantics_profile must be SemanticsProfile or None" ---


@pytest.mark.parametrize("profile", ["pyreason", {"engine": "pyreason"}, 1])
def test_resolver_rejects_non_profile_as_value_error(profile):
    expected = f"semantics_profile must be SemanticsProfile or None, got {type(profile).__name__}"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolve_pyreason_engine_ext(
            where=_WHERE,
            schema_ir=_SCHEMA_IR,
            engine_ext=None,
            semantics_profile=profile,
        )
    assert type(caught.value) is ValueError


def test_resolver_accepts_real_pyreason_profile():
    resolved = resolve_pyreason_engine_ext(
        where=_WHERE,
        schema_ir=_SCHEMA_IR,
        engine_ext=None,
        semantics_profile=_profile([{"target": "rule", "kind": "timestep_delay", "value": 2}]),
    )
    assert isinstance(resolved, PyReasonRuleExt)
    assert resolved.timestep_delay == 2


# --- _normalize_profile_interval: "<path>.value lower/upper bound must be numeric" ---


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (["0.7", 0.9], f"{_PROFILE_VALUE_PATH} lower bound must be numeric"),
        ([True, 0.9], f"{_PROFILE_VALUE_PATH} lower bound must be numeric"),
        ([0.7, "0.9"], f"{_PROFILE_VALUE_PATH} upper bound must be numeric"),
        ([0.7, None], f"{_PROFILE_VALUE_PATH} upper bound must be numeric"),
    ],
)
def test_profile_non_numeric_interval_is_value_error(value, message):
    profile = _profile([{"target": "head:0", "kind": "interval", "value": value}])
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        resolve_pyreason_engine_ext(
            where=_WHERE,
            schema_ir=_SCHEMA_IR,
            engine_ext=None,
            semantics_profile=profile,
        )
    assert type(caught.value) is ValueError


def test_profile_numeric_interval_is_accepted():
    resolved = resolve_pyreason_engine_ext(
        where=_WHERE,
        schema_ir=_SCHEMA_IR,
        engine_ext=None,
        semantics_profile=_profile([{"target": "head:0", "kind": "interval", "value": [0.7, 0.9]}]),
    )
    assert resolved is not None
    assert tuple(resolved.head_bound or ()) == (0.7, 0.9)


# --- _normalize_body_predicate_bounds: "body_predicate_bounds must be dict[str, [float, float]]" ---


@pytest.mark.parametrize("bounds", [[("user:name", (0.5, 1.0))], "user:name", 1])
def test_rule_ext_non_dict_body_predicate_bounds_is_value_error(bounds):
    expected = "body_predicate_bounds must be dict[str, [float, float]]"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        PyReasonRuleExt(body_predicate_bounds=bounds)
    assert type(caught.value) is ValueError


# --- _normalize_branch_head_bounds: "branch_head_bounds must be dict[int, [float, float]]" ---


@pytest.mark.parametrize("bounds", [[(0, (0.5, 1.0))], "0", 1])
def test_rule_ext_non_dict_branch_head_bounds_is_value_error(bounds):
    expected = "branch_head_bounds must be dict[int, [float, float]]"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        PyReasonRuleExt(branch_head_bounds=bounds)
    assert type(caught.value) is ValueError


# --- _validate_bound_pair: "<name> lower/upper bound must be numeric" ---


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"head_bound": ("0.5", 1.0)}, "head_bound lower bound must be numeric"),
        ({"head_bound": (True, 1.0)}, "head_bound lower bound must be numeric"),
        ({"head_bound": (0.5, "1.0")}, "head_bound upper bound must be numeric"),
        (
            {"body_predicate_bounds": {"user:name": (None, 1.0)}},
            "body_predicate_bounds lower bound must be numeric",
        ),
        (
            {"body_predicate_bounds": {"user:name": (0.5, False)}},
            "body_predicate_bounds upper bound must be numeric",
        ),
        ({"branch_head_bounds": {0: ("0.5", 1.0)}}, "branch_head_bounds lower bound must be numeric"),
        ({"branch_head_bounds": {0: (0.5, [1.0])}}, "branch_head_bounds upper bound must be numeric"),
    ],
)
def test_rule_ext_non_numeric_bound_pair_is_value_error(kwargs, message):
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        PyReasonRuleExt(**kwargs)
    assert type(caught.value) is ValueError


def test_rule_ext_dict_bounds_with_numeric_pairs_are_accepted():
    ext = PyReasonRuleExt(
        head_bound=(0.5, 1),
        body_predicate_bounds={"user:name": (0, 1.0)},
        branch_head_bounds={0: (0.25, 0.75)},
    )
    assert tuple(ext.head_bound or ()) == (0.5, 1)
    assert ext.body_predicate_bounds == {"user:name": (0, 1.0)}
    assert ext.branch_head_bounds == {0: (0.25, 0.75)}


# --- where_compile boundary: the ValueError above is what gets wrapped ---


@pytest.mark.parametrize(
    ("ext", "message"),
    [
        (
            _DuckRuleExt(body_predicate_bounds=[("user:name", (0.5, 1.0))]),
            "body_predicate_bounds must be dict[str, [float, float]]",
        ),
        (
            _DuckRuleExt(body_predicate_bounds={"user:name": ("0.5", 1.0)}),
            "body_predicate_bounds lower bound must be numeric",
        ),
        (_DuckRuleExt(head_bound=(0.5, "1.0")), "head_bound upper bound must be numeric"),
    ],
)
def test_where_compile_wraps_rule_ext_value_error_into_compile_error(ext, message):
    with pytest.raises(PyReasonWhereCompileError, match=re.escape(message)) as caught:
        compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            schema_ir=_SCHEMA_IR,
            engine_ext=ext,
        )
    assert type(caught.value.__cause__) is ValueError
