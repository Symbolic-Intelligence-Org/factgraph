"""Certainty derivation prototype.

Consumes ``confidence_kind="certainty"`` + ``condition_weights`` + evidence
tree dict to produce a per-condition weighted impact breakdown and an
aggregate certainty (bottleneck = minimum weighted impact).

This module is an internal prototype. It is not part of the public
``Store.evaluate()`` contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ConditionImpact:
    atom_key: str
    node_kind: str
    weight: float | None
    impact: float | None


@dataclass(frozen=True)
class CertaintySummary:
    confidence_kind: str
    condition_count: int
    weighted_condition_count: int
    conditions: tuple[ConditionImpact, ...]
    aggregate_certainty: float | None


_CONDITION_NODE_KINDS = frozenset({"predicate_witness_group", "non_fact_check"})


def derive_certainty_summary(
    tree_dict: Mapping[str, Any],
    condition_weights: Mapping[str, Any],
    confidence_kind: str,
) -> CertaintySummary | None:
    if confidence_kind != "certainty":
        return None
    if not isinstance(tree_dict, Mapping):
        raise ValueError("tree_dict must be mapping")
    if not isinstance(condition_weights, Mapping):
        raise ValueError("condition_weights must be mapping")

    root = tree_dict.get("root")
    if not isinstance(root, Mapping):
        return CertaintySummary(
            confidence_kind="certainty",
            condition_count=0,
            weighted_condition_count=0,
            conditions=(),
            aggregate_certainty=None,
        )

    conditions: list[ConditionImpact] = []
    weighted_impacts: list[float] = []
    for node in _collect_condition_nodes(root):
        atom_key = _condition_key_for_node(node)
        if atom_key is None:
            continue

        node_kind = str(node.get("node_kind") or "")
        weight = _condition_weight(condition_weights, atom_key)
        confidence = _condition_confidence(node)
        impact: float | None = None
        if weight is not None:
            impact = round(weight * confidence, 6) if confidence is not None else weight
            weighted_impacts.append(impact)

        conditions.append(
            ConditionImpact(
                atom_key=atom_key,
                node_kind=node_kind,
                weight=weight,
                impact=impact,
            )
        )

    aggregate = min(weighted_impacts) if weighted_impacts else None
    return CertaintySummary(
        confidence_kind="certainty",
        condition_count=len(conditions),
        weighted_condition_count=len(weighted_impacts),
        conditions=tuple(conditions),
        aggregate_certainty=aggregate,
    )


def _collect_condition_nodes(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    if node.get("node_kind") in _CONDITION_NODE_KINDS:
        out.append(node)
    children = node.get("children", [])
    if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
        for child in children:
            if isinstance(child, Mapping):
                out.extend(_collect_condition_nodes(child))
    return out


def _condition_key_for_node(node: Mapping[str, Any]) -> str | None:
    node_kind = node.get("node_kind")
    if node_kind == "predicate_witness_group":
        return _extract_condition_key(node.get("pred_atom_key"))
    if node_kind == "non_fact_check":
        return _extract_condition_key(node.get("step_key"))
    return None


def _extract_condition_key(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.split(":", 1)[0]


def _condition_weight(condition_weights: Mapping[str, Any], atom_key: str) -> float | None:
    raw = condition_weights.get(atom_key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f'condition_weights["{atom_key}"] must be numeric')
    weight = float(raw)
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError(f'condition_weights["{atom_key}"] must be positive finite number')
    return round(weight, 6)


def _condition_confidence(node: Mapping[str, Any]) -> float | None:
    raw = node.get("condition_confidence", node.get("confidence"))
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    confidence = float(raw)
    if not math.isfinite(confidence) or confidence < 0:
        return None
    return round(confidence, 6)


@dataclass(frozen=True)
class RankedCondition:
    atom_key: str
    node_kind: str
    weight: float | None
    impact: float | None
    is_bottleneck: bool


def rank_certainty_conditions(
    conditions: Sequence[ConditionImpact],
    aggregate_certainty: float | None,
) -> list[RankedCondition]:
    """Sort conditions by impact ascending; mark bottleneck(s)."""
    weighted: list[ConditionImpact] = []
    unweighted: list[ConditionImpact] = []
    for condition in conditions:
        if condition.impact is not None:
            weighted.append(condition)
        else:
            unweighted.append(condition)

    weighted.sort(key=lambda condition: (condition.impact, condition.atom_key))
    unweighted.sort(key=lambda condition: condition.atom_key)

    result: list[RankedCondition] = []
    for condition in weighted:
        result.append(
            RankedCondition(
                atom_key=condition.atom_key,
                node_kind=condition.node_kind,
                weight=condition.weight,
                impact=condition.impact,
                is_bottleneck=(
                    aggregate_certainty is not None and condition.impact == aggregate_certainty
                ),
            )
        )
    for condition in unweighted:
        result.append(
            RankedCondition(
                atom_key=condition.atom_key,
                node_kind=condition.node_kind,
                weight=condition.weight,
                impact=condition.impact,
                is_bottleneck=False,
            )
        )
    return result


__all__ = [
    "CertaintySummary",
    "ConditionImpact",
    "RankedCondition",
    "derive_certainty_summary",
    "rank_certainty_conditions",
]
