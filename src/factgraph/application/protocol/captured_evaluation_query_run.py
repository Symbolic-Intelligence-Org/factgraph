"""Detached captured targeted-Query observations.

This deliberately composes the F4 run bundle rather than extending it.  F4
captures a complete native evaluation; this outer artifact preserves the
targeted Query's ordered ``contains_row`` inventory and the observations made
over that exact capture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError
from .evaluation_expectation import (
    CompiledContainsRowExpectationV0,
    ExpectationResultV0,
)
from .evaluation_run import _plain, _sha_token, _token
from .evaluation_run_bundle import EvaluationRunBundleV0
from .evaluation_run_verification import EvaluationRunVerificationV0
from .policy_explanation import PolicyExplanationViewV0


MAX_CAPTURED_EVALUATION_QUERY_EXPECTATIONS_V0 = 64


@dataclass(frozen=True, repr=False)
class CapturedEvaluationQueryRunV0:
    """A sealed F4 bundle plus an ordered targeted-Query observation ledger.

    The artifact is integrity sealed, not authenticated.  Its outcomes say
    only what the captured native enumeration contained; they are neither
    ledger truth claims nor negative evidence.
    """

    bundle: EvaluationRunBundleV0
    targeted_query_wrapper_digest: str
    expectations: tuple[CompiledContainsRowExpectationV0, ...]
    expectation_results: tuple[ExpectationResultV0, ...]
    integrity: Literal["digest_sealed_not_authenticated"] = "digest_sealed_not_authenticated"
    authenticity: Literal["unverified"] = "unverified"
    privacy: Literal["contains_captured_typed_values"] = "contains_captured_typed_values"
    custody: Literal["caller_managed"] = "caller_managed"
    explain_availability: Literal["detached_receipt_playback_available"] = (
        "detached_receipt_playback_available"
    )
    verification_availability: Literal["isolated_native_semantic_and_support_available"] = (
        "isolated_native_semantic_and_support_available"
    )
    captured_query_run_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.bundle, EvaluationRunBundleV0):
            raise ProtocolShapeError("Captured Query run requires EvaluationRunBundleV0")
        _sha_token(
            self.targeted_query_wrapper_digest,
            "Captured Query run targeted_query_wrapper_digest",
        )
        if (
            not isinstance(self.expectations, tuple)
            or len(self.expectations) > MAX_CAPTURED_EVALUATION_QUERY_EXPECTATIONS_V0
            or not all(isinstance(item, CompiledContainsRowExpectationV0) for item in self.expectations)
        ):
            raise ProtocolShapeError("Captured Query run expectation inventory is malformed")
        expectation_ids = tuple(item.expectation_id for item in self.expectations)
        if len(set(expectation_ids)) != len(expectation_ids):
            raise ProtocolShapeError("Captured Query run expectation ids are duplicated")
        if any(item.query_digest != self.bundle.query_digest for item in self.expectations):
            raise ProtocolShapeError("Captured Query run expectation does not match its bundle Query")
        if (
            not isinstance(self.expectation_results, tuple)
            or len(self.expectation_results) != len(self.expectations)
            or not all(isinstance(item, ExpectationResultV0) for item in self.expectation_results)
        ):
            raise ProtocolShapeError("Captured Query run expectation outcomes are malformed")
        if tuple(item.expectation_id for item in self.expectation_results) != expectation_ids:
            raise ProtocolShapeError("Captured Query run expectation outcome order does not match inventory")
        if (
            self.integrity,
            self.authenticity,
            self.privacy,
            self.custody,
            self.explain_availability,
            self.verification_availability,
        ) != (
            "digest_sealed_not_authenticated",
            "unverified",
            "contains_captured_typed_values",
            "caller_managed",
            "detached_receipt_playback_available",
            "isolated_native_semantic_and_support_available",
        ):
            raise ProtocolShapeError("Captured Query run availability semantics are outside v0")
        expected = _token(
            "captured_evaluation_query_run_v0",
            _plain(
                (
                    self.bundle.bundle_digest,
                    self.targeted_query_wrapper_digest,
                    tuple(item.expectation_digest for item in self.expectations),
                    tuple(item.outcome_digest for item in self.expectation_results),
                    self.integrity,
                    self.authenticity,
                    self.privacy,
                    self.custody,
                    self.explain_availability,
                    self.verification_availability,
                )
            ),
        )
        object.__setattr__(self, "captured_query_run_digest", expected)

    def verify(self) -> "CapturedEvaluationQueryRunVerificationV0":
        """Isolated verification of the exact captured F4 bundle."""

        from factgraph.application.captured_evaluation_query_run_runtime import (
            verify_captured_evaluation_query_run_v0,
        )

        return verify_captured_evaluation_query_run_v0(self)

    def explain(self, *, row_capture_digest: str) -> "CapturedEvaluationQueryRunExplanationV0":
        """Play a positive captured row; negative observations have no graph."""

        from factgraph.application.captured_evaluation_query_run_runtime import (
            explain_captured_evaluation_query_run_v0,
        )

        return explain_captured_evaluation_query_run_v0(
            self,
            row_capture_digest=row_capture_digest,
        )

    def to_bytes(self) -> bytes:
        from factgraph.application.captured_evaluation_query_run_runtime import (
            captured_evaluation_query_run_bytes,
        )

        return captured_evaluation_query_run_bytes(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CapturedEvaluationQueryRunV0":
        from factgraph.application.captured_evaluation_query_run_runtime import (
            captured_evaluation_query_run_from_bytes,
        )

        value = captured_evaluation_query_run_from_bytes(raw)
        if not isinstance(value, cls):  # pragma: no cover - defensive import boundary
            raise ProtocolShapeError("Captured Query run codec returned unexpected value")
        return value

    def __repr__(self) -> str:
        return (
            "CapturedEvaluationQueryRunV0("
            f"captured_query_run_digest={self.captured_query_run_digest!r}, "
            "captured_values=<redacted>)"
        )


@dataclass(frozen=True)
class CapturedEvaluationQueryRunExplanationV0:
    """Detached positive-row evidence projected onto the authored Policy."""

    captured_query_run_digest: str
    row_capture_digest: str
    evidence: Any
    policy_projection: PolicyExplanationViewV0
    explanation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha_token(
            self.captured_query_run_digest,
            "Captured Query explanation captured_query_run_digest",
        )
        _sha_token(self.row_capture_digest, "Captured Query explanation row_capture_digest")
        if not isinstance(self.policy_projection, PolicyExplanationViewV0):
            raise ProtocolShapeError("Captured Query explanation policy projection is invalid")
        raw = (
            "captured_evaluation_query_run_explanation_v0\0"
            f"{self.captured_query_run_digest}\0{self.row_capture_digest}\0"
            f"{self.policy_projection.projection_digest}"
        ).encode()
        object.__setattr__(self, "explanation_digest", f"sha256:{sha256_hex(raw)}")


@dataclass(frozen=True)
class CapturedEvaluationQueryRunVerificationV0:
    """F4 verification kept explicitly separate from captured observations."""

    captured_query_run_digest: str
    bundle_verification: EvaluationRunVerificationV0
    observation_reverified: Literal[False] = False
    observation_truth_verified: Literal[False] = False
    verification_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha_token(
            self.captured_query_run_digest,
            "Captured Query verification captured_query_run_digest",
        )
        if not isinstance(self.bundle_verification, EvaluationRunVerificationV0):
            raise ProtocolShapeError("Captured Query verification bundle record is invalid")
        if (self.observation_reverified, self.observation_truth_verified) != (False, False):
            raise ProtocolShapeError("Captured Query verification semantics are outside v0")
        raw = (
            "captured_evaluation_query_run_verification_v0\0"
            f"{self.captured_query_run_digest}\0{self.bundle_verification.verification_digest}\0"
            "false\0false"
        ).encode()
        object.__setattr__(self, "verification_digest", f"sha256:{sha256_hex(raw)}")

    @property
    def matched(self) -> bool:
        return self.bundle_verification.verdict in {
            "matched_declared_runtime",
            "matched_unpinned_runtime",
        }


__all__ = [
    "CapturedEvaluationQueryRunExplanationV0",
    "CapturedEvaluationQueryRunV0",
    "CapturedEvaluationQueryRunVerificationV0",
    "MAX_CAPTURED_EVALUATION_QUERY_EXPECTATIONS_V0",
]
