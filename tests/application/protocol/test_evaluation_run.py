from __future__ import annotations

from dataclasses import replace

import pytest

from factgraph.application.protocol import (
    EvaluationRunSummaryAnchorV0,
    ProtocolShapeError,
)
from factgraph.application.protocol.evaluation_run import _token


def _summary(row_digests: tuple[str, ...]) -> EvaluationRunSummaryAnchorV0:
    values = ("b" * 64, len(row_digests), row_digests, "not_asserted", "unknown", "unspecified")
    return EvaluationRunSummaryAnchorV0(
        *values, _token("evaluation_run_summary_anchor_v0", values),
    )


def test_summary_preserves_duplicate_semantic_rows_without_claiming_truth() -> None:
    digest = "sha256:" + "a" * 64
    summary = _summary((digest, digest))

    assert summary.row_count == 2
    assert summary.row_anchor_digests == (digest, digest)
    assert summary.truth_interpretation == "not_asserted"
    with pytest.raises(ProtocolShapeError):
        replace(summary, truth_interpretation="false")


def test_zero_row_summary_is_an_anchor_not_a_truth_result() -> None:
    summary = _summary(())

    assert summary.summary_anchor_digest.startswith("sha256:")
    assert summary.completeness == "unknown"
    assert summary.ordering == "unspecified"
