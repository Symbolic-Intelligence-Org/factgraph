"""PyReason engine evaluator keeps its ValueError contract for shared evaluate inputs.

Every case below reaches one ``raise ValueError`` site in
``factgraph.adapters.pyreason.engine_eval`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
``engine_options`` and ``semantics_profile`` rejections mirror the core
``evaluate_store`` ValueError boundary (adapter docs 5C.0 / 5C.0a), and
``valid_time_boundaries`` meta rejections share the temporal-projection
ValueError boundary.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from factgraph.adapters.pyreason.engine_eval import (
    _meta_value_for_key,
    _resolve_iteration_count,
    _resolve_temporal_projection_state,
    _valid_range_for_asrt_id,
    resolve_pyreason_run_config,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store.ledger import Ledger, MetaRow


class _ProfileLookalike:
    """Duck-typed profile exposing the attributes the adapter reads, but not a SemanticsProfile."""

    engine = "pyreason"
    iteration_count = 2
    temporal_projection: ClassVar[dict[str, str]] = {"mode": "none"}


def _profile(**kwargs: Any) -> SemanticsProfile:
    return SemanticsProfile(name="profile.t1b.pyreason", engine="pyreason", **kwargs)


# --- resolve_pyreason_run_config: "PyReason engine_options must be dict[str, Any] or None" ---


@pytest.mark.parametrize("engine_options", [[("timesteps", 3)], "timesteps=3", ("timesteps", 3)])
def test_engine_options_type_rejection_preserves_exact_value_error(engine_options):
    expected = (
        "PyReason engine_options must be dict[str, Any] or None, "
        f"got {type(engine_options).__name__}"
    )
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolve_pyreason_run_config(engine_options)
    assert type(caught.value) is ValueError


def test_engine_options_dict_or_none_positive_control():
    assert resolve_pyreason_run_config(None).timesteps == 2
    assert resolve_pyreason_run_config({"timesteps": 3}).timesteps == 3


# --- _resolve_iteration_count / _resolve_temporal_projection_state:
#     "semantics_profile must be SemanticsProfile or None" ---


def _temporal_state(profile: Any) -> Any:
    return _resolve_temporal_projection_state(
        None,
        {},
        semantics_profile=profile,
        engine_options=None,
    )


@pytest.mark.parametrize("resolver", [_resolve_iteration_count, _temporal_state])
def test_semantics_profile_type_rejection_preserves_exact_value_error(resolver):
    expected = "semantics_profile must be SemanticsProfile or None, got _ProfileLookalike"
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        resolver(_ProfileLookalike())
    assert type(caught.value) is ValueError


def test_semantics_profile_none_or_real_profile_positive_control():
    assert _resolve_iteration_count(None) is None
    assert _temporal_state(None) is None
    profile = _profile(iteration_count=2)
    assert _resolve_iteration_count(profile) == 2
    assert _temporal_state(profile) is None


# --- _meta_value_for_key: "{key} meta must be string for PyReason valid_time_boundaries" ---


def _ledger_store_with_meta(meta: dict[str, Any]) -> tuple[Any, str]:
    ledger = Ledger()
    asrt_id = set_field(
        ledger,
        pred_id="user:name",
        e_ref="idref_v1:User:Alice",
        rest_terms=[("string", "Alice")],
        meta=meta,
    )
    return SimpleNamespace(ledger=ledger), asrt_id


def _store_with_meta_rows(rows_by_key: dict[str, Any]) -> Any:
    """Store whose ledger serves real ``MetaRow`` values directly.

    ``set_field`` refuses non-string ``valid_from`` / ``valid_to`` meta at the
    write protocol, so the adapter site is only reachable through a ledger row
    whose ``MetaRow.value`` (typed ``Any``) is not a string.
    """

    def _effective_meta_rows(*, asrt_id: str, key: str) -> tuple[MetaRow, ...]:
        if key not in rows_by_key:
            return ()
        return (MetaRow(asrt_id, key, "str", rows_by_key[key]),)

    return SimpleNamespace(ledger=SimpleNamespace(effective_meta_rows=_effective_meta_rows))


@pytest.mark.parametrize(
    ("key", "value"),
    [("valid_from", 20260110), ("valid_to", 20260210), ("valid_from", ["2026-01-10"])],
)
def test_valid_time_meta_type_rejection_preserves_exact_value_error(key, value):
    expected = f"{key} meta must be string for PyReason valid_time_boundaries"
    store = _store_with_meta_rows({key: value})
    with pytest.raises(ValueError, match=re.escape(expected)) as caught:
        _valid_range_for_asrt_id(store, "asrt:alice")
    assert type(caught.value) is ValueError
    with pytest.raises(ValueError, match=re.escape(expected)) as direct:
        _meta_value_for_key(store, "asrt:alice", key)
    assert type(direct.value) is ValueError


def test_valid_time_meta_string_positive_control():
    store, asrt_id = _ledger_store_with_meta({"valid_from": "2026-01-10", "valid_to": "2026-02-10"})
    assert _valid_range_for_asrt_id(store, asrt_id) == ("2026-01-10", "2026-02-10")
    bare_store, bare_asrt_id = _ledger_store_with_meta({"source": "test"})
    assert _valid_range_for_asrt_id(bare_store, bare_asrt_id) == (None, None)
    row_store = _store_with_meta_rows({"valid_from": "2026-01-10", "valid_to": None})
    assert _valid_range_for_asrt_id(row_store, "asrt:alice") == ("2026-01-10", None)
    assert _meta_value_for_key(row_store, "asrt:alice", "valid_to") is None
