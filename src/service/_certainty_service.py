"""Service-layer certainty helpers.

Extracted from runtime_v1.py to isolate certainty derivation from session
lifecycle orchestration. This module depends on:
  - core (Store, _certainty_materializer)
It does NOT import runtime_v1 — the callable-based API prevents reverse
dependency.

Q8 Phase 2 (Slice 6) note:
  The registry-backed `condition_weights` lookup via
  ``FileAuthoringRegistry.read_rule_spec(...)`` was removed alongside the
  SavedRule persistence layer. ``_lookup_condition_weights_for_candidate``
  now always returns ``None`` because no FS-backed source for
  ``condition_weights`` survives Phase 2. Eligibility-check structure is
  preserved as documentation of the dead path; the function returns at the
  same logical step where the registry read used to occur. Per blueprint
  §5.10.3 + N-1 family minimum-change scope, no core/store refactor.
"""

from __future__ import annotations

from typing import Any, Callable

from factgraph.core.store._certainty_materializer import materialize_certainty_summary
from factgraph.core.store._confidence_kind_resolver import check_certainty_artifact_eligibility
from factgraph.core.store.runtime import Store


def _lookup_condition_weights_for_candidate(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    registry_root: str | None,
) -> dict[str, float] | None:
    if registry_root is None:
        return None
    support_digest = store.get_candidate_support_digest(candidate_id)
    if support_digest is None:
        return None
    artifact = store._lookup_support_artifact(support_digest)
    if artifact is None:
        return None
    edge = check_certainty_artifact_eligibility(
        artifact,
        store._lookup_support_artifact,
    )
    if edge is None:
        return None

    # Q8 Phase 2 (Slice 6): FileAuthoringRegistry.read_rule_spec(...) was
    # removed. No FS-backed source for `condition_weights` exists post-Phase-2,
    # so the lookup returns None at this point.
    return None


def _compute_certainty_summary_from_tree(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    registry_root: str | None,
    aggregation: str = "bottleneck",
) -> dict[str, Any] | None:
    condition_weights = _lookup_condition_weights_for_candidate(
        store,
        candidate_id,
        tree_dict,
        registry_root=registry_root,
    )
    return materialize_certainty_summary(
        store,
        candidate_id,
        tree_dict,
        condition_weights=condition_weights,
        aggregation=aggregation,
    )


def _compute_all_certainty_summaries(
    store: Store,
    *,
    registry_root: str | None,
    get_candidate_tree: Callable[[str], dict[str, Any] | None],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate_id in store.list_candidate_ids():
        try:
            tree = get_candidate_tree(candidate_id)
        except Exception:
            continue
        if tree is None:
            continue
        certainty_summary = _compute_certainty_summary_from_tree(
            store,
            candidate_id,
            tree,
            registry_root=registry_root,
        )
        if certainty_summary is not None:
            result[candidate_id] = certainty_summary
    return result
