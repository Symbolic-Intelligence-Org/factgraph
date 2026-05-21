"""Service-layer certainty helpers.

Extracted from runtime_v1.py to isolate certainty derivation from session
lifecycle orchestration. This module depends on:
  - core (Store, _certainty_materializer)
It does NOT import runtime_v1 — the callable-based API prevents reverse
dependency.

Q8 Phase 2 (Slice 6) + Slice 7C / Q6-A (a.2) note:
  The registry-backed ``condition_weights`` lookup via
  ``FileAuthoringRegistry.read_rule_spec(...)`` was removed alongside the
  SavedRule persistence layer in Slice 6. Slice 7C dropped the
  ``registry_root`` plumbing carried through these helpers (Q6-A (b.3) +
  N-2): the parameter was already a no-op (always returned None), so its
  removal is signature-only and behaviorally inert. ``condition_weights``
  remains permanently ``None`` from the certainty pipeline.
"""

from __future__ import annotations

from typing import Any, Callable

from factgraph.core.store._certainty_materializer import materialize_certainty_summary
from factgraph.core.store.runtime import Store


def _lookup_condition_weights_for_candidate(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
) -> dict[str, float] | None:
    # Q8 Phase 2 (Slice 6) + Slice 7C (Q6-A b.3): no FS-backed source for
    # `condition_weights` exists after the FileAuthoringRegistry removal.
    return None


def _compute_certainty_summary_from_tree(
    store: Store,
    candidate_id: str,
    tree_dict: dict[str, Any],
    *,
    aggregation: str = "bottleneck",
) -> dict[str, Any] | None:
    condition_weights = _lookup_condition_weights_for_candidate(
        store,
        candidate_id,
        tree_dict,
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
        )
        if certainty_summary is not None:
            result[candidate_id] = certainty_summary
    return result
