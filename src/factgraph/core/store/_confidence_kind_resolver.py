"""Confidence-kind resolver protocol and certainty implementation.

This module defines the protocol for determining ``confidence_kind`` at
candidate creation time, plus a shared eligibility helper that is consumed
by both the resolver and the certainty service lookup.

All types are core-internal: no authoring/service imports.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from factgraph.core.store._support import ProofReceipt, RuleRefEdge


class RuleSpecReader(Protocol):
    """Minimal interface for reading rule payload metadata."""

    def read_rule_spec(self, rule_id: str, version: str) -> dict[str, Any] | None: ...


class ConfidenceKindResolver(Protocol):
    """Determines ``confidence_kind`` for a candidate based on its support."""

    def resolve(
        self,
        support_digest: str,
        support_kind: str,
        artifact_lookup: Callable[[str], ProofReceipt | None],
    ) -> str: ...


def check_certainty_artifact_eligibility(
    artifact: ProofReceipt,
    child_artifact_lookup: Callable[[str], ProofReceipt | None],
) -> RuleRefEdge | None:
    """Check if a support artifact is eligible for certainty routing.

    Returns the single resolved ``RuleRefEdge`` if eligible, or ``None``.
    """

    if len(artifact.rule_ref_edges) != 1:
        return None
    edge = artifact.rule_ref_edges[0]
    if edge.child_support_digest is None:
        return None
    child = child_artifact_lookup(edge.child_support_digest)
    if child is None:
        return None
    if len(child.rule_ref_edges) > 0:
        return None
    return edge


class CertaintyConfidenceKindResolver:
    """Marks candidates as ``confidence_kind="certainty"`` when eligible."""

    def __init__(self, rule_spec_reader: RuleSpecReader) -> None:
        self._reader = rule_spec_reader

    def resolve(
        self,
        support_digest: str,
        support_kind: str,
        artifact_lookup: Callable[[str], ProofReceipt | None],
    ) -> str:
        artifact = artifact_lookup(support_digest)
        if artifact is None:
            return "none"  # F-CORE-4: support artifact not found
        edge = check_certainty_artifact_eligibility(artifact, artifact_lookup)
        if edge is None:
            return "none"  # F-CORE-4: eligibility check failed
        payload = self._reader.read_rule_spec(edge.rule_ref_id, edge.rule_ref_version)
        if not isinstance(payload, dict):
            return "none"  # F-CORE-4: rule_spec not found or not dict
        condition_weights = payload.get("condition_weights")
        if not isinstance(condition_weights, dict) or not condition_weights:
            return "none"  # F-CORE-4: no condition_weights in rule_spec
        return "certainty"
