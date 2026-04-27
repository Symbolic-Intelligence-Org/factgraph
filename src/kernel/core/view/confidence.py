from __future__ import annotations

from typing import Any

from kernel.core.store.types import ConfidenceStrategy


def aggregate_confidence(
    facts: list[dict[str, Any]],
    strategy: ConfidenceStrategy,
    prefer_source: str | None = None,
) -> float | None:
    if not isinstance(facts, list):
        raise ValueError("facts must be list")
    if strategy not in {"max", "mean", "median", "prefer_source"}:
        raise ValueError("strategy must be one of: max, mean, median, prefer_source")
    if prefer_source is not None and (not isinstance(prefer_source, str) or not prefer_source):
        raise ValueError("prefer_source must be non-empty string or None")

    rows = [_read_confidence_row(item) for item in facts if isinstance(item, dict)]
    confidences = [row["confidence"] for row in rows if row["confidence"] is not None]
    if not confidences:
        return None

    if strategy == "max":
        return max(confidences)
    if strategy == "mean":
        return sum(confidences) / len(confidences)
    if strategy == "median":
        sorted_values = sorted(confidences)
        mid = len(sorted_values) // 2
        if len(sorted_values) % 2 == 1:
            return sorted_values[mid]
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0

    preferred = [
        row["confidence"]
        for row in rows
        if row["confidence"] is not None and prefer_source is not None and row["source"] == prefer_source
    ]
    if preferred:
        return max(preferred)
    return max(confidences)


def _read_confidence_row(row: dict[str, Any]) -> dict[str, float | str | None]:
    source = row.get("source")
    source_value = source if isinstance(source, str) and source else None

    confidence_raw = row.get("confidence")
    if confidence_raw is None:
        return {"source": source_value, "confidence": None}
    if isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
        return {"source": source_value, "confidence": None}

    confidence = float(confidence_raw)
    if confidence < 0.0 or confidence > 1.0:
        return {"source": source_value, "confidence": None}
    return {"source": source_value, "confidence": confidence}
