"""Premise-filter configuration rejections stay ValueError at their documented boundary.

Every case below reaches one ``raise ValueError`` site in
``factgraph.core.store.premise_filter`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
The normalizers already fold ``TypeError`` into ``ValueError`` for
non-iterable configuration, and ``SDKStore.set_premise_*`` re-raises exactly
``ValueError`` as ``SDKStoreError``. Each site has a valid-type positive control.
"""

from __future__ import annotations

import pytest

from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    normalize_premise_allowances,
    normalize_premise_blocks,
    normalize_premise_exclusions,
)


def test_string_exclusion_values_is_value_error() -> None:
    with pytest.raises(
        ValueError,
        match="MetaExclusion.values must be an iterable of strings, not a single string",
    ):
        MetaExclusion(key="status", values="retracted")


def test_iterable_exclusion_values_is_accepted() -> None:
    exclusion = MetaExclusion(key="status", values=frozenset({"retracted"}))
    assert exclusion.values == frozenset({"retracted"})


@pytest.mark.parametrize("absent_ok", ["yes", 1, None])
def test_non_bool_allowance_absent_ok_is_value_error(absent_ok: object) -> None:
    with pytest.raises(ValueError, match="PredicatePremiseAllowance.absent_ok must be bool"):
        PredicatePremiseAllowance(
            pred_id="user:name",
            key="status",
            allowed_values=frozenset({"ok"}),
            absent_ok=absent_ok,
        )


def test_string_allowance_allowed_values_is_value_error() -> None:
    with pytest.raises(
        ValueError,
        match="PredicatePremiseAllowance.allowed_values must be an iterable of strings, "
        "not a single string",
    ):
        PredicatePremiseAllowance(pred_id="user:name", key="status", allowed_values="ok")


def test_valid_allowance_configuration_is_accepted() -> None:
    allowance = PredicatePremiseAllowance(
        pred_id="user:name",
        key="status",
        allowed_values=frozenset({"ok"}),
        absent_ok=True,
    )
    assert allowance.allowed_values == frozenset({"ok"})
    assert allowance.absent_ok is True


def test_string_block_blocked_values_is_value_error() -> None:
    with pytest.raises(
        ValueError,
        match="PredicatePremiseBlock.blocked_values must be an iterable of strings, "
        "not a single string",
    ):
        PredicatePremiseBlock(pred_id="user:name", key="status", blocked_values="bad")


def test_valid_block_configuration_is_accepted() -> None:
    block = PredicatePremiseBlock(
        pred_id="user:name", key="status", blocked_values=frozenset({"bad"})
    )
    assert block.blocked_values == frozenset({"bad"})


@pytest.mark.parametrize("item", [object(), "status", 7])
def test_foreign_exclusion_entry_is_value_error(item: object) -> None:
    with pytest.raises(ValueError, match="premise_exclusions entries must be MetaExclusion"):
        normalize_premise_exclusions([item])


@pytest.mark.parametrize("item", [object(), "status", 7])
def test_foreign_allowance_entry_is_value_error(item: object) -> None:
    with pytest.raises(
        ValueError, match="premise_allowances entries must be PredicatePremiseAllowance"
    ):
        normalize_premise_allowances([item])


@pytest.mark.parametrize("item", [object(), "status", 7])
def test_foreign_block_entry_is_value_error(item: object) -> None:
    with pytest.raises(ValueError, match="premise_blocks entries must be PredicatePremiseBlock"):
        normalize_premise_blocks([item])


def test_normalizers_accept_their_own_configuration_types() -> None:
    exclusion = MetaExclusion(key="status", values=frozenset({"retracted"}))
    allowance = PredicatePremiseAllowance(
        pred_id="user:name", key="status", allowed_values=frozenset({"ok"})
    )
    block = PredicatePremiseBlock(
        pred_id="user:name", key="status", blocked_values=frozenset({"bad"})
    )
    assert normalize_premise_exclusions([exclusion]) == (exclusion,)
    assert normalize_premise_allowances([allowance]) == (allowance,)
    assert normalize_premise_blocks([block]) == (block,)
