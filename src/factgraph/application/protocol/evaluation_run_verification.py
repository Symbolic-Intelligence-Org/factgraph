from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import ProtocolShapeError
from .evaluation_run import _seal, _sha_token, _text, _token


@dataclass(frozen=True)
class EvaluationRunVerificationV0:
    """Content-sealed result of isolated execution over one captured bundle."""

    source_bundle_digest: str
    source_anchor_digest: str
    source_authenticity: Literal["unverified"]
    verification_scope: Literal["isolated_native_semantic_and_support_v0"]
    verifier_engine: Literal["native"]
    verifier_engine_version: str
    verifier_adapter_version: str
    runtime_compatibility: Literal["declared_match", "source_unpinned", "declared_mismatch"]
    execution_status: Literal["completed", "not_run", "failed"]
    semantic_comparison: Literal["match", "mismatch", "not_compared"]
    support_comparison: Literal["match", "mismatch", "not_compared"]
    expected_row_count: int
    observed_row_count: int | None
    expected_semantic_multiset_digest: str
    observed_semantic_multiset_digest: str | None
    expected_support_multiset_digest: str
    observed_support_multiset_digest: str | None
    estimated_work: int
    work_limit: int
    verdict: Literal[
        "matched_declared_runtime",
        "matched_unpinned_runtime",
        "semantic_mismatch",
        "support_mismatch",
        "runtime_incompatible",
        "resource_rejected",
        "execution_failed",
    ]
    reason_codes: tuple[str, ...]
    identity_semantics: Literal["verification_record_not_source_run"]
    verification_digest: str

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_digest",
            "source_anchor_digest",
            "expected_semantic_multiset_digest",
            "expected_support_multiset_digest",
        ):
            _sha_token(getattr(self, name), name)
        for name in ("observed_semantic_multiset_digest", "observed_support_multiset_digest"):
            value = getattr(self, name)
            if value is not None:
                _sha_token(value, name)
        for name in ("verifier_engine_version", "verifier_adapter_version"):
            _text(getattr(self, name), name)
        if (
            self.source_authenticity != "unverified"
            or self.verification_scope != "isolated_native_semantic_and_support_v0"
            or self.verifier_engine != "native"
            or self.identity_semantics != "verification_record_not_source_run"
        ):
            raise ProtocolShapeError("EvaluationRun verification semantics are outside v0")
        if self.runtime_compatibility not in {
            "declared_match",
            "source_unpinned",
            "declared_mismatch",
        }:
            raise ProtocolShapeError("EvaluationRun verification runtime compatibility is invalid")
        if self.execution_status not in {"completed", "not_run", "failed"}:
            raise ProtocolShapeError("EvaluationRun verification execution status is invalid")
        if self.semantic_comparison not in {"match", "mismatch", "not_compared"} or (
            self.support_comparison not in {"match", "mismatch", "not_compared"}
        ):
            raise ProtocolShapeError("EvaluationRun verification comparison status is invalid")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.expected_row_count, self.estimated_work)
        ) or (
            isinstance(self.work_limit, bool)
            or not isinstance(self.work_limit, int)
            or self.work_limit <= 0
        ):
            raise ProtocolShapeError("EvaluationRun verification counts are invalid")
        if self.observed_row_count is not None and (
            isinstance(self.observed_row_count, bool)
            or not isinstance(self.observed_row_count, int)
            or self.observed_row_count < 0
        ):
            raise ProtocolShapeError("EvaluationRun verification observed row count is invalid")
        observed = (
            self.observed_row_count,
            self.observed_semantic_multiset_digest,
            self.observed_support_multiset_digest,
        )
        if self.execution_status == "completed":
            if any(value is None for value in observed) or "not_compared" in (
                self.semantic_comparison,
                self.support_comparison,
            ):
                raise ProtocolShapeError("completed verification requires observed comparisons")
        elif any(value is not None for value in observed) or (
            self.semantic_comparison,
            self.support_comparison,
        ) != ("not_compared", "not_compared"):
            raise ProtocolShapeError("non-completed verification cannot carry observed results")
        if (
            not isinstance(self.reason_codes, tuple)
            or tuple(sorted(set(self.reason_codes))) != self.reason_codes
            or any(not isinstance(code, str) or not code for code in self.reason_codes)
        ):
            raise ProtocolShapeError("EvaluationRun verification reason codes are malformed")
        expected_status = {
            "matched_declared_runtime": "completed",
            "matched_unpinned_runtime": "completed",
            "semantic_mismatch": "completed",
            "support_mismatch": "completed",
            "runtime_incompatible": "not_run",
            "resource_rejected": "not_run",
            "execution_failed": "failed",
        }.get(self.verdict)
        if expected_status != self.execution_status:
            raise ProtocolShapeError("EvaluationRun verification verdict and execution disagree")
        expected_comparisons = {
            "matched_declared_runtime": ("match", "match"),
            "matched_unpinned_runtime": ("match", "match"),
            "semantic_mismatch": ("mismatch", "mismatch"),
            "support_mismatch": ("match", "mismatch"),
            "runtime_incompatible": ("not_compared", "not_compared"),
            "resource_rejected": ("not_compared", "not_compared"),
            "execution_failed": ("not_compared", "not_compared"),
        }.get(self.verdict)
        if expected_comparisons != (self.semantic_comparison, self.support_comparison):
            raise ProtocolShapeError("EvaluationRun verification verdict and comparisons disagree")
        for comparison, expected, actual in (
            (
                self.semantic_comparison,
                self.expected_semantic_multiset_digest,
                self.observed_semantic_multiset_digest,
            ),
            (
                self.support_comparison,
                self.expected_support_multiset_digest,
                self.observed_support_multiset_digest,
            ),
        ):
            if comparison == "match" and expected != actual:
                raise ProtocolShapeError("matching verification digests disagree")
            if comparison == "mismatch" and expected == actual:
                raise ProtocolShapeError("mismatching verification digests are equal")
        expected_reasons = {
            "matched_declared_runtime": (),
            "matched_unpinned_runtime": ("SOURCE_RUNTIME_UNPINNED",),
            "semantic_mismatch": ("SEMANTIC_MULTISET_MISMATCH",),
            "support_mismatch": ("SUPPORT_MULTISET_MISMATCH",),
            "resource_rejected": ("WORK_LIMIT_EXCEEDED",),
            "execution_failed": ("NATIVE_EXECUTION_FAILED",),
        }.get(self.verdict)
        runtime_reasons = {
            "ADAPTER_VERSION_MISMATCH",
            "CONFIG_PROFILE_MISMATCH",
            "ENGINE_PROFILE_MISMATCH",
            "ENGINE_VERSION_MISMATCH",
            "WHERE_AST_GATE_MISMATCH",
        }
        if expected_reasons is not None and self.reason_codes != expected_reasons:
            raise ProtocolShapeError("EvaluationRun verification reason codes disagree")
        if self.verdict == "runtime_incompatible" and (
            not self.reason_codes or set(self.reason_codes) - runtime_reasons
        ):
            raise ProtocolShapeError("runtime-incompatible reason codes are invalid")
        if self.runtime_compatibility == "declared_mismatch" and (
            self.verdict != "runtime_incompatible"
        ):
            raise ProtocolShapeError("declared runtime mismatch must stop verification")
        if self.verdict == "runtime_incompatible" and (
            self.runtime_compatibility != "declared_mismatch"
            and self.reason_codes != ("WHERE_AST_GATE_MISMATCH",)
        ):
            raise ProtocolShapeError("runtime incompatibility does not match its source")
        if (self.verdict == "resource_rejected") != (self.estimated_work > self.work_limit):
            raise ProtocolShapeError("resource verdict does not match the work estimate")
        if (
            self.verdict == "matched_declared_runtime"
            and self.runtime_compatibility != "declared_match"
        ):
            raise ProtocolShapeError("declared-runtime match requires complete matching pins")
        if (
            self.verdict == "matched_unpinned_runtime"
            and self.runtime_compatibility != "source_unpinned"
        ):
            raise ProtocolShapeError("unpinned-runtime match requires incomplete source pins")
        if (
            self.verdict.startswith("matched_")
            and self.observed_row_count != self.expected_row_count
        ):
            raise ProtocolShapeError("matching verification row counts disagree")
        values = tuple(
            getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "verification_digest"
        )
        _seal(
            self.verification_digest,
            _token("evaluation_run_verification_v0", values),
            "verification_digest",
        )


__all__ = ["EvaluationRunVerificationV0"]
