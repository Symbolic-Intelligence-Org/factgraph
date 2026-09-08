"""Retained, bounded evidence captured by a Product V2 evaluation.

The artifact is an execution result, not a replay request.  Its projector is
pure: opening one row reads only canonical artifact bytes and never requires a
Store, ledger, schema registry, ontology, or evaluator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from factgraph.application.explain.evidence_tree import (
    EvidenceGraph,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError

EvaluationEvidenceAvailabilityV2: TypeAlias = Literal[
    "available", "not_requested", "unsupported", "zero_row", "incomplete"
]
EvaluationEvidenceSideV2: TypeAlias = Literal["baseline", "effective", "candidate_effective"]

EVALUATION_EVIDENCE_CODEC_V2: Literal["factgraph.evaluation_evidence.v2"] = (
    "factgraph.evaluation_evidence.v2"
)
MAX_EVALUATION_EVIDENCE_V2_BYTES = 64 * 1024 * 1024
MAX_EVALUATION_EVIDENCE_V2_DEPTH = 64
_AVAILABILITY = frozenset(
    {"available", "not_requested", "unsupported", "zero_row", "incomplete"}
)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ProtocolShapeError("Evaluation evidence is not canonical JSON") from exc


def _token(raw: bytes) -> str:
    return f"sha256:{sha256_hex(raw)}"


def _require_token(value: object, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{label} must be a sha256 token")
    suffix = value[7:]
    if suffix != suffix.lower() or any(character not in "0123456789abcdef" for character in suffix):
        raise ProtocolShapeError(f"{label} must be a sha256 token")
    return value


def _depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(item) for item in value), default=0)
    return 0


@dataclass(frozen=True)
class EvaluationEvidenceEntryV2:
    side: EvaluationEvidenceSideV2
    engine: str
    observation_digest: str
    row_identity_digest: str
    graph_bytes: bytes = field(repr=False)
    graph_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.side not in {"baseline", "effective", "candidate_effective"}:
            raise ProtocolShapeError("Evaluation evidence side is invalid")
        if not isinstance(self.engine, str) or not self.engine:
            raise ProtocolShapeError("Evaluation evidence engine is invalid")
        _require_token(self.observation_digest, label="observation_digest")
        _require_token(self.row_identity_digest, label="row_identity_digest")
        graph = evaluation_evidence_graph_from_bytes_v2(self.graph_bytes)
        canonical = evaluation_evidence_graph_to_bytes_v2(graph)
        if canonical != self.graph_bytes:
            raise ProtocolShapeError("Evaluation evidence graph bytes are not canonical")
        expected = _token(canonical)
        if hasattr(self, "graph_digest"):
            if self.graph_digest != expected:
                raise ProtocolShapeError("Evaluation evidence graph digest is stale")
            return
        object.__setattr__(self, "graph_digest", expected)

    @property
    def target_key(self) -> tuple[str, str, str]:
        return self.side, self.engine, self.observation_digest


@dataclass(frozen=True)
class EvaluationEvidenceArtifactV2:
    run_digest: str
    profile_digest: str
    plan_digests: tuple[str, ...]
    entries: tuple[EvaluationEvidenceEntryV2, ...]
    codec_version: Literal["factgraph.evaluation_evidence.v2"] = EVALUATION_EVIDENCE_CODEC_V2
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.run_digest, label="run_digest")
        _require_token(self.profile_digest, label="profile_digest")
        if self.codec_version != EVALUATION_EVIDENCE_CODEC_V2:
            raise ProtocolShapeError("Evaluation evidence codec version is unsupported")
        if not self.plan_digests:
            raise ProtocolShapeError("Evaluation evidence must pin at least one plan")
        for item in self.plan_digests:
            _require_token(item, label="plan_digest")
        if tuple(sorted(set(self.plan_digests))) != self.plan_digests:
            raise ProtocolShapeError("Evaluation evidence plan digests are not canonical")
        if not self.entries or not all(isinstance(item, EvaluationEvidenceEntryV2) for item in self.entries):
            raise ProtocolShapeError("Available evaluation evidence requires entries")
        entries = tuple(sorted(self.entries, key=lambda item: item.target_key))
        if len({item.target_key for item in entries}) != len(entries):
            raise ProtocolShapeError("Evaluation evidence targets must be unique")
        raw = _artifact_payload_bytes(self, entries=entries)
        if len(raw) > MAX_EVALUATION_EVIDENCE_V2_BYTES:
            raise ProtocolShapeError("Evaluation evidence artifact exceeds protocol limit")
        expected = _token(raw)
        if hasattr(self, "artifact_digest"):
            if self.entries != entries or self.artifact_digest != expected:
                raise ProtocolShapeError("Evaluation evidence artifact seal is stale")
            return
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "artifact_digest", expected)

    def to_bytes(self) -> bytes:
        return evaluation_evidence_artifact_to_bytes_v2(self)


@dataclass(frozen=True)
class EvaluationEvidenceCaptureV2:
    availability: EvaluationEvidenceAvailabilityV2
    artifact: EvaluationEvidenceArtifactV2 | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.availability not in _AVAILABILITY:
            raise ProtocolShapeError("Evaluation evidence availability is invalid")
        if self.availability == "available":
            if not isinstance(self.artifact, EvaluationEvidenceArtifactV2) or self.reason_code is not None:
                raise ProtocolShapeError("Available evaluation evidence requires only an artifact")
        elif self.artifact is not None or not isinstance(self.reason_code, str) or not self.reason_code:
            raise ProtocolShapeError("Unavailable evaluation evidence requires only a reason")


def evaluation_evidence_graph_to_bytes_v2(graph: EvidenceGraph) -> bytes:
    if not isinstance(graph, EvidenceGraph):
        raise ProtocolShapeError("Evaluation evidence graph is malformed")
    return _canonical_json_bytes(evidence_graph_to_dict(graph))


def evaluation_evidence_graph_from_bytes_v2(raw: bytes) -> EvidenceGraph:
    value = _decode_canonical(raw, label="Evaluation evidence graph")
    if not isinstance(value, dict):
        raise ProtocolShapeError("Evaluation evidence graph must be an object")
    try:
        return evidence_graph_from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolShapeError("Evaluation evidence graph is malformed") from exc


def _entry_to_wire(entry: EvaluationEvidenceEntryV2) -> dict[str, object]:
    return {
        "side": entry.side,
        "engine": entry.engine,
        "observation_digest": entry.observation_digest,
        "row_identity_digest": entry.row_identity_digest,
        "graph": json.loads(entry.graph_bytes.decode("utf-8")),
        "graph_digest": entry.graph_digest,
    }


def _artifact_payload(artifact: EvaluationEvidenceArtifactV2, *, entries: tuple[EvaluationEvidenceEntryV2, ...] | None = None) -> dict[str, object]:
    return {
        "codec_version": artifact.codec_version,
        "run_digest": artifact.run_digest,
        "profile_digest": artifact.profile_digest,
        "plan_digests": list(artifact.plan_digests),
        "entries": [_entry_to_wire(item) for item in (artifact.entries if entries is None else entries)],
    }


def _artifact_payload_bytes(artifact: EvaluationEvidenceArtifactV2, *, entries: tuple[EvaluationEvidenceEntryV2, ...] | None = None) -> bytes:
    return _canonical_json_bytes(_artifact_payload(artifact, entries=entries))


def evaluation_evidence_artifact_to_bytes_v2(artifact: EvaluationEvidenceArtifactV2) -> bytes:
    if not isinstance(artifact, EvaluationEvidenceArtifactV2):
        raise ProtocolShapeError("Evaluation evidence artifact is malformed")
    fresh = EvaluationEvidenceArtifactV2(
        run_digest=artifact.run_digest,
        profile_digest=artifact.profile_digest,
        plan_digests=artifact.plan_digests,
        entries=artifact.entries,
        codec_version=artifact.codec_version,
    )
    if fresh.artifact_digest != artifact.artifact_digest:
        raise ProtocolShapeError("Evaluation evidence artifact seal is stale")
    return _canonical_json_bytes({**_artifact_payload(artifact), "artifact_digest": artifact.artifact_digest})


def evaluation_evidence_artifact_from_bytes_v2(raw: bytes) -> EvaluationEvidenceArtifactV2:
    value = _decode_canonical(raw, label="Evaluation evidence artifact")
    if not isinstance(value, dict) or set(value) != {
        "codec_version", "run_digest", "profile_digest", "plan_digests", "entries", "artifact_digest"
    }:
        raise ProtocolShapeError("Evaluation evidence artifact has unsupported fields")
    raw_entries = value["entries"]
    raw_plans = value["plan_digests"]
    if not isinstance(raw_entries, list) or not isinstance(raw_plans, list):
        raise ProtocolShapeError("Evaluation evidence artifact arrays are malformed")
    entries: list[EvaluationEvidenceEntryV2] = []
    for row in raw_entries:
        if not isinstance(row, dict) or set(row) != {
            "side", "engine", "observation_digest", "row_identity_digest", "graph", "graph_digest"
        }:
            raise ProtocolShapeError("Evaluation evidence entry has unsupported fields")
        entry = EvaluationEvidenceEntryV2(
            side=row["side"],  # type: ignore[arg-type]
            engine=row["engine"],  # type: ignore[arg-type]
            observation_digest=row["observation_digest"],  # type: ignore[arg-type]
            row_identity_digest=row["row_identity_digest"],  # type: ignore[arg-type]
            graph_bytes=_canonical_json_bytes(row["graph"]),
        )
        if row["graph_digest"] != entry.graph_digest:
            raise ProtocolShapeError("Evaluation evidence graph digest mismatch")
        entries.append(entry)
    artifact = EvaluationEvidenceArtifactV2(
        run_digest=value["run_digest"],  # type: ignore[arg-type]
        profile_digest=value["profile_digest"],  # type: ignore[arg-type]
        plan_digests=tuple(raw_plans),  # type: ignore[arg-type]
        entries=tuple(entries),
        codec_version=value["codec_version"],  # type: ignore[arg-type]
    )
    if value["artifact_digest"] != artifact.artifact_digest:
        raise ProtocolShapeError("Evaluation evidence artifact digest mismatch")
    return artifact


def project_evaluation_evidence_v2(
    artifact: EvaluationEvidenceArtifactV2,
    *,
    run_digest: str,
    side: EvaluationEvidenceSideV2,
    engine: str,
    observation_digest: str,
) -> EvidenceGraph:
    """Return one exact retained graph without consulting any live state."""

    if evaluation_evidence_artifact_from_bytes_v2(artifact.to_bytes()) != artifact:
        raise ProtocolShapeError("Evaluation evidence artifact round-trip mismatch")
    if artifact.run_digest != run_digest:
        raise ProtocolShapeError("Evaluation evidence run substitution")
    matches = tuple(
        item
        for item in artifact.entries
        if item.target_key == (side, engine, observation_digest)
    )
    if len(matches) != 1:
        raise ProtocolShapeError("Evaluation evidence target is absent or ambiguous")
    return evaluation_evidence_graph_from_bytes_v2(matches[0].graph_bytes)


def _decode_canonical(raw: bytes, *, label: str) -> object:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EVALUATION_EVIDENCE_V2_BYTES:
        raise ProtocolShapeError(f"{label} bytes are empty or exceed the limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError(f"{label} must be UTF-8 JSON") from exc
    if _depth(value) > MAX_EVALUATION_EVIDENCE_V2_DEPTH:
        raise ProtocolShapeError(f"{label} exceeds depth limit")
    if _canonical_json_bytes(value) != raw:
        raise ProtocolShapeError(f"{label} must be canonical JSON")
    return value


__all__ = [
    "EVALUATION_EVIDENCE_CODEC_V2",
    "EvaluationEvidenceArtifactV2",
    "EvaluationEvidenceAvailabilityV2",
    "EvaluationEvidenceCaptureV2",
    "EvaluationEvidenceEntryV2",
    "evaluation_evidence_artifact_from_bytes_v2",
    "evaluation_evidence_artifact_to_bytes_v2",
    "evaluation_evidence_graph_from_bytes_v2",
    "evaluation_evidence_graph_to_bytes_v2",
    "project_evaluation_evidence_v2",
]
