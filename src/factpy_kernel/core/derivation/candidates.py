from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.protocol.tup_v1 import canonical_bytes_tup_v1


@dataclass(frozen=True)
class CandidateSet:
    derivation_id: str
    derivation_version: str
    run_id: str
    target: str
    key_tuple_digest: str
    tup_digest: str | None
    payload: dict[str, Any]
    support_digest: str
    support_kind: str
    generated_at: int
    state: str


def compute_key_tuple_digest(key_terms: list[tuple[str, Any]]) -> str:
    canonical = canonical_bytes_tup_v1(key_terms)
    return sha256_token(canonical)


def make_candidate(
    *,
    derivation_id: str,
    derivation_version: str,
    run_id: str,
    target: str,
    key_terms: list[tuple[str, Any]],
    payload: dict[str, Any],
    support_digest: str,
    support_kind: str,
    generated_at: int,
    state: str = "generated",
    tup_digest: str | None = None,
) -> CandidateSet:
    if not isinstance(derivation_id, str) or not derivation_id:
        raise ValueError("derivation_id must be non-empty string")
    if not isinstance(derivation_version, str) or not derivation_version:
        raise ValueError("derivation_version must be non-empty string")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be non-empty string")
    if not isinstance(target, str) or not target:
        raise ValueError("target must be non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")
    if not isinstance(generated_at, int) or isinstance(generated_at, bool):
        raise ValueError("generated_at must be epoch-nanos int")

    if "e_ref" not in payload or "rest_terms" not in payload:
        raise ValueError("payload must include e_ref and rest_terms")

    key_tuple_digest = compute_key_tuple_digest(key_terms)

    return CandidateSet(
        derivation_id=derivation_id,
        derivation_version=derivation_version,
        run_id=run_id,
        target=target,
        key_tuple_digest=key_tuple_digest,
        tup_digest=tup_digest,
        payload=dict(payload),
        support_digest=support_digest,
        support_kind=support_kind,
        generated_at=generated_at,
        state=state,
    )
