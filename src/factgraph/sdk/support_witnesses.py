"""Read-only classification of the witnesses in one captured support.

Kind is captured evidence; assertion availability is a read-time material check.
Neither is permission, current visibility, truth, or a shared snapshot guarantee.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_token
from factgraph.core.store._support import _to_jsonable, compute_support_digest
from factgraph.core.view.projector import build_args_for_claim

SUPPORT_WITNESS_CONTRACT_V1 = "factgraph.support-witness-report.v1"


class SupportWitnessError(ValueError):
    """Invalid input/capture is an error, never silently unavailable evidence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SupportWitnessV1:
    """One original condition/ref occurrence with independent origin and availability."""

    condition_key: str
    witness_ref: str
    kind: Literal["assertion", "virtual", "unknown"]
    availability: Literal["available", "unavailable"]
    reason: str | None
    predicate_id: str | None
    terms: tuple[Any, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible V1 item used in the report digest."""
        return {
            "condition_key": self.condition_key,
            "witness_ref": self.witness_ref,
            "kind": self.kind,
            "availability": self.availability,
            "reason": self.reason,
            "predicate_id": self.predicate_id,
            "terms": _to_jsonable(self.terms),
        }


@dataclass(frozen=True)
class SupportWitnessReportV1:
    """Versioned read report; availability may change without rewriting support."""

    support_digest: str
    capture_version: int | None
    status: Literal["available", "not_captured", "support_missing"]
    items: tuple[SupportWitnessV1, ...]

    @property
    def contract(self) -> str:
        """Return the fixed V1 report contract identifier."""
        return SUPPORT_WITNESS_CONTRACT_V1

    def to_dict(self) -> dict[str, Any]:
        """Return the complete deterministic report-digest payload."""
        return {
            "contract": self.contract,
            "support_digest": self.support_digest,
            "capture_version": self.capture_version,
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
        }

    @property
    def report_digest(self) -> str:
        """Return SHA-256 of the canonical report payload, excluding this digest."""
        return sha256_token(json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8"))


def read_support_witnesses(store: Any, support_digest: str) -> SupportWitnessReportV1:
    """Implementation behind the SDK audit seam; no ledger or sidecar writes."""
    if not isinstance(support_digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", support_digest) is None:
        raise SupportWitnessError("invalid_support_digest", "Expected a canonical support SHA-256 token")
    try:
        artifact = store._lookup_support_artifact(support_digest)
    except (ValueError, TypeError, KeyError) as exc:
        raise SupportWitnessError("invalid_support_capture", "Invalid captured support metadata") from exc
    if artifact is None:
        return SupportWitnessReportV1(support_digest, None, "support_missing", ())
    try:
        actual_digest = compute_support_digest(artifact)
    except (ValueError, TypeError) as exc:
        raise SupportWitnessError("invalid_support_capture", "Cannot encode captured support") from exc
    if actual_digest != support_digest:
        raise SupportWitnessError("support_digest_mismatch", "Captured support does not match its digest")

    items: list[SupportWitnessV1] = []
    for predicate in artifact.pred_witnesses:
        if predicate.witnesses is None:
            items.extend(
                SupportWitnessV1(predicate.pred_condition_key, ref, "unknown", "unavailable",
                                 "not_captured", None, ())
                for ref in predicate.asrt_ids
            )
            continue
        for witness in predicate.witnesses:
            reason = None
            if witness.kind == "unknown":
                reason = "unsupported_witness_kind"
            elif witness.kind == "assertion":
                claim = store.ledger.get_claim(witness.witness_ref)
                if claim is None:
                    reason = "assertion_missing"
                else:
                    try:
                        # Canonical JSON preserves bool/int distinctions that
                        # Python tuple equality alone would silently collapse.
                        same_terms = json.dumps(_to_jsonable(build_args_for_claim(store.ledger, claim))) == json.dumps(
                            _to_jsonable(witness.terms)
                        )
                    except (TypeError, ValueError):
                        same_terms = False
                    if claim.pred_id != witness.predicate_id or not same_terms:
                        reason = "assertion_mismatch"
            items.append(SupportWitnessV1(
                predicate.pred_condition_key, witness.witness_ref, witness.kind,
                "available" if reason is None else "unavailable", reason,
                witness.predicate_id, witness.terms,
            ))
    return SupportWitnessReportV1(
        support_digest, artifact.witness_capture_version,
        "available" if artifact.witness_capture_version == 1 else "not_captured",
        tuple(items),
    )


__all__ = ["SUPPORT_WITNESS_CONTRACT_V1", "SupportWitnessError", "SupportWitnessReportV1", "SupportWitnessV1"]
