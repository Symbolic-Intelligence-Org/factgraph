"""Derivation outputs and legacy candidate-protocol compatibility names.

``DerivationOutput`` is the canonical read-only evaluation vocabulary.  The
class remains defined in this historical module so persisted references to
``factgraph.core.derivation.candidates.CandidateSet`` can resolve through the
direct compatibility alias below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeAlias

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1

CONFIDENCE_KINDS = frozenset({"none", "probability", "certainty"})


@dataclass(frozen=True)
class DerivationOutput:
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
    confidence: float | None = None
    confidence_kind: str = "none"
    candidate_id: str = ""
    candidate_key: str = ""
    candidate_kind: str = "fact"

    def __post_init__(self) -> None:
        if self.candidate_kind not in {"fact", "entity"}:
            raise ValueError("candidate_kind must be 'fact' or 'entity'")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be object")
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("target must be non-empty string")
        if not isinstance(self.derivation_id, str) or not self.derivation_id:
            raise ValueError("derivation_id must be non-empty string")
        if not isinstance(self.derivation_version, str) or not self.derivation_version:
            raise ValueError("derivation_version must be non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be non-empty string")
        if not isinstance(self.key_tuple_digest, str) or not self.key_tuple_digest.startswith("sha256:"):
            raise ValueError("key_tuple_digest must be sha256 token")
        if self.confidence is not None and (
            isinstance(self.confidence, bool) or not isinstance(self.confidence, float)
        ):
            raise ValueError("confidence must be float or None")
        if not isinstance(self.confidence_kind, str) or self.confidence_kind not in CONFIDENCE_KINDS:
            raise ValueError("confidence_kind must be one of: none, probability, certainty")
        key = self.candidate_key or compute_candidate_key_v2(
            derivation_id=self.derivation_id,
            derivation_version=self.derivation_version,
            candidate_kind=self.candidate_kind,
            target=self.target,
            payload=self.payload,
        )
        if not isinstance(key, str) or not key.startswith("candk_v2:"):
            raise ValueError("candidate_key must start with 'candk_v2:'")
        object.__setattr__(self, "candidate_key", key)
        cand_id = self.candidate_id or compute_candidate_id_v2(
            run_id=self.run_id,
            candidate_kind=self.candidate_kind,
            target=self.target,
            candidate_key=key,
        )
        if not isinstance(cand_id, str) or not cand_id.startswith("cand_v2:"):
            raise ValueError("candidate_id must start with 'cand_v2:'")
        object.__setattr__(self, "candidate_id", cand_id)


def compute_key_tuple_digest(key_terms: list[tuple[str, Any]]) -> str:
    canonical = canonical_bytes_tup_v1(key_terms)
    return sha256_token(canonical)


def compute_candidate_key_v2(
    *,
    derivation_id: str,
    derivation_version: str,
    candidate_kind: str,
    target: str,
    payload: dict[str, Any],
) -> str:
    content = canonical_candidate_content(candidate_kind=candidate_kind, target=target, payload=payload)
    raw = b"".join(
        [
            b"factpy\x00cand_v2\x00",
            derivation_id.encode("utf-8"),
            b"\x00",
            derivation_version.encode("utf-8"),
            b"\x00",
            candidate_kind.encode("utf-8"),
            b"\x00",
            content,
            b"\x00",
        ]
    )
    return f"candk_v2:{sha256_hex(raw)}"


def compute_candidate_id_v2(
    *,
    run_id: str,
    candidate_kind: str,
    target: str,
    candidate_key: str,
) -> str:
    raw = b"".join(
        [
            b"factpy\x00cand_id_v2\x00",
            run_id.encode("utf-8"),
            b"\x00",
            candidate_kind.encode("utf-8"),
            b"\x00",
            target.encode("utf-8"),
            b"\x00",
            candidate_key.encode("utf-8"),
            b"\x00",
        ]
    )
    return f"cand_v2:{sha256_hex(raw)}"


def canonical_candidate_content(*, candidate_kind: str, target: str, payload: dict[str, Any]) -> bytes:
    if candidate_kind == "fact":
        pred_id = payload.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            pred_id = target
        terms = payload.get("terms")
        if not isinstance(terms, list):
            raise ValueError("fact candidate payload.terms must be list")
        normalized_terms = [_normalize_term_for_content(term) for term in terms]
        return _stable_json_bytes({"pred_id": pred_id, "terms": normalized_terms})

    entity_type = payload.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise ValueError("entity candidate payload.entity_type must be non-empty string")
    identity_fields = payload.get("identity_fields")
    if not isinstance(identity_fields, list):
        identity_fields = []
    resolved_identity = payload.get("resolved_identity")
    if not isinstance(resolved_identity, dict):
        resolved_identity = {}
    identity_types = payload.get("identity_types")
    if not isinstance(identity_types, dict):
        identity_types = {}
    missing_identity_fields = payload.get("missing_identity_fields")
    if not isinstance(missing_identity_fields, list):
        missing_identity_fields = []
    proposed_entity_ref = payload.get("proposed_entity_ref")
    if not (isinstance(proposed_entity_ref, str) and proposed_entity_ref):
        proposed_entity_ref = None
    return _stable_json_bytes(
        {
            "entity_type": entity_type,
            "identity_fields": [str(x) for x in identity_fields],
            "identity_types": _to_jsonable(identity_types),
            "resolved_identity": _to_jsonable(resolved_identity),
            "missing_identity_fields": [str(x) for x in missing_identity_fields],
            "proposed_entity_ref": proposed_entity_ref,
        }
    )


def extract_candidate_refs(candidate_set: DerivationOutput) -> set[str]:
    payload = candidate_set.payload
    if not isinstance(payload, dict):
        return set()
    terms = payload.get("terms")
    if not isinstance(terms, list):
        return set()
    refs: set[str] = set()
    for term in terms:
        if not isinstance(term, dict):
            continue
        if term.get("kind") != "candidate_ref":
            continue
        candidate_key = term.get("candidate_key")
        if isinstance(candidate_key, str) and candidate_key:
            refs.add(candidate_key)
    return refs


def _normalize_term_for_content(term: Any) -> dict[str, Any]:
    if isinstance(term, dict):
        kind = term.get("kind")
        if kind == "entity_ref":
            value = term.get("value")
            if isinstance(value, str):
                return {"kind": "entity_ref", "value": value}
            return {"kind": "entity_ref", "value": ""}
        if kind == "candidate_ref":
            candidate_key = term.get("candidate_key")
            if isinstance(candidate_key, str):
                return {"kind": "candidate_ref", "candidate_key": candidate_key}
            return {"kind": "candidate_ref", "candidate_key": ""}
        if kind == "literal":
            tag = term.get("tag")
            return {
                "kind": "literal",
                "tag": str(tag) if tag is not None else "",
                "value": _to_jsonable(term.get("value")),
            }
    if isinstance(term, tuple) and len(term) == 2:
        tag, value = term
        return {"kind": "literal", "tag": str(tag), "value": _to_jsonable(value)}
    return {"kind": "literal", "tag": "", "value": _to_jsonable(term)}


def _stable_json_bytes(value: Any) -> bytes:
    return json.dumps(_to_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_b64__": value.hex()}
    if isinstance(value, tuple):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, list):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def make_derivation_output(
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
    candidate_kind: str = "fact",
    confidence: float | None = None,
    confidence_kind: str = "none",
) -> DerivationOutput:
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

    key_tuple_digest = compute_key_tuple_digest(key_terms)
    candidate_key = compute_candidate_key_v2(
        derivation_id=derivation_id,
        derivation_version=derivation_version,
        candidate_kind=candidate_kind,
        target=target,
        payload=payload,
    )
    candidate_id = compute_candidate_id_v2(
        run_id=run_id,
        candidate_kind=candidate_kind,
        target=target,
        candidate_key=candidate_key,
    )

    return DerivationOutput(
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
        confidence=confidence,
        confidence_kind=confidence_kind,
        candidate_kind=candidate_kind,
        candidate_key=candidate_key,
        candidate_id=candidate_id,
    )


# Persisted candidate identifiers and payload keys remain the v2 compatibility
# protocol.  These direct aliases keep existing construction, ``isinstance``,
# unpickling, and equality semantics intact while read-only evaluation code
# adopts the accurate in-process name.
CandidateSet: TypeAlias = DerivationOutput
make_candidate = make_derivation_output

__all__ = [
    "CONFIDENCE_KINDS",
    "CandidateSet",
    "DerivationOutput",
    "canonical_candidate_content",
    "compute_candidate_id_v2",
    "compute_candidate_key_v2",
    "compute_key_tuple_digest",
    "extract_candidate_refs",
    "make_candidate",
    "make_derivation_output",
]
