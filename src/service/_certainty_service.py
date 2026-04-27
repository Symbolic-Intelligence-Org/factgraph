"""Service-layer certainty helpers.

Extracted from runtime_v1.py to isolate certainty derivation from session
lifecycle orchestration. This module depends on:
  - core (Store, _certainty_materializer)
  - authoring (FileAuthoringRegistry)
It does NOT import runtime_v1 — the callable-based API prevents reverse
dependency.
"""

from __future__ import annotations

from typing import Any, Callable

from kernel.authoring.registry_fs import FileAuthoringRegistry
from kernel.core.store._certainty_materializer import materialize_certainty_summary
from kernel.core.store._confidence_kind_resolver import check_certainty_artifact_eligibility
from kernel.core.store.runtime import Store


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

    payload = FileAuthoringRegistry(registry_root).read_rule_spec(
        edge.rule_ref_id,
        edge.rule_ref_version,
    )
    if not isinstance(payload, dict):
        return None
    raw_condition_weights = payload.get("condition_weights")
    if raw_condition_weights is None:
        return {}
    if not isinstance(raw_condition_weights, dict):
        return None
    condition_weights: dict[str, float] = {}
    for key, value in raw_condition_weights.items():
        if (
            not isinstance(key, str)
            or not key
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            return None
        condition_weights[key] = float(value)
    return condition_weights


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
