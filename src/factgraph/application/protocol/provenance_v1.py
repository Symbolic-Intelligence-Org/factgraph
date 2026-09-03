"""Closed, FactGraph-neutral provenance references.

``ProvenanceRefV1`` is deliberately much smaller than a source record.  It is
safe to carry in a sealed Scenario/run/Explain artifact, but it does not carry
source content, ACLs, tenant information, credentials, admission decisions or
retention policy.  Those remain owned by the caller (for example Meander).

The values here are not generic ``dict`` metadata.  They have a strict,
bounded wire shape so that a future product surface can show a source *link*
without accidentally importing an external source-authority model into
FactGraph.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal, Mapping, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str

ProvenanceLocatorKindV1: TypeAlias = Literal["opaque", "line_span", "json_pointer"]
ProvenanceOriginRoleV1: TypeAlias = Literal[
    "scenario_hypothesis",
    "baseline_support",
    "agent_extraction",
    "operator_input",
    "imported_record",
]

_LOCATOR_KINDS = frozenset({"opaque", "line_span", "json_pointer"})
_ORIGIN_ROLES = frozenset(
    {
        "scenario_hypothesis",
        "baseline_support",
        "agent_extraction",
        "operator_input",
        "imported_record",
    }
)
_OPAQUE_REF_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")
_POINTER_SEGMENT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,128}$")

MAX_PROVENANCE_REFS_V1 = 16
MAX_PROVENANCE_POINTER_SEGMENTS_V1 = 16


def _token(label: str, payload: object) -> str:
    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:  # pragma: no cover - DTO guarded
        raise ProtocolShapeError(f"{label} payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


def _require_opaque_ref(value: object, *, field_name: str) -> str:
    _require_non_empty_str(value, field_name=field_name)
    assert isinstance(value, str)  # narrowed by _require_non_empty_str
    if _OPAQUE_REF_RE.fullmatch(value) is None:
        raise ProtocolShapeError(
            f"{field_name} must be a bounded opaque reference without control characters"
        )
    return value


def _require_sha256_token(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    digest = value[7:]
    if (
        len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    return value


@dataclass(frozen=True)
class ProvenanceLocatorV1:
    """A deliberately closed locator into the opaque ``source_ref``.

    ``opaque`` is for a caller-owned opaque locator token.  ``line_span``
    identifies inclusive positive line numbers and carries no text.  The
    ``json_pointer`` variant stores decoded path segments rather than a raw
    pointer string so its canonical wire form cannot hide non-canonical
    escaping.  It is a locator, not a source-content payload.
    """

    kind: ProvenanceLocatorKindV1
    opaque_ref: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    pointer: tuple[str, ...] = ()
    locator_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in _LOCATOR_KINDS:
            raise ProtocolShapeError("ProvenanceLocatorV1.kind is unsupported")
        if self.kind == "opaque":
            _require_opaque_ref(self.opaque_ref, field_name="ProvenanceLocatorV1.opaque_ref")
            if self.line_start is not None or self.line_end is not None or self.pointer:
                raise ProtocolShapeError("opaque provenance locator has unsupported fields")
        elif self.kind == "line_span":
            if self.opaque_ref is not None or self.pointer:
                raise ProtocolShapeError("line_span provenance locator has unsupported fields")
            for name in ("line_start", "line_end"):
                value = getattr(self, name)
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    raise ProtocolShapeError(f"ProvenanceLocatorV1.{name} must be positive int")
            assert self.line_start is not None and self.line_end is not None
            if self.line_end < self.line_start:
                raise ProtocolShapeError("ProvenanceLocatorV1 line_span is reversed")
        else:
            if (
                self.opaque_ref is not None
                or self.line_start is not None
                or self.line_end is not None
            ):
                raise ProtocolShapeError("json_pointer provenance locator has unsupported fields")
            if (
                not isinstance(self.pointer, tuple)
                or not self.pointer
                or len(self.pointer) > MAX_PROVENANCE_POINTER_SEGMENTS_V1
            ):
                raise ProtocolShapeError(
                    "ProvenanceLocatorV1.pointer must be a bounded non-empty tuple"
                )
            for index, segment in enumerate(self.pointer):
                if not isinstance(segment, str) or _POINTER_SEGMENT_RE.fullmatch(segment) is None:
                    raise ProtocolShapeError(
                        f"ProvenanceLocatorV1.pointer[{index}] must be bounded non-control text"
                    )
        object.__setattr__(
            self,
            "locator_digest",
            _token("provenance_locator_v1", self.to_wire()),
        )

    @classmethod
    def opaque(cls, opaque_ref: str) -> "ProvenanceLocatorV1":
        """Create a caller-owned opaque locator without embedding source content."""
        return cls(kind="opaque", opaque_ref=opaque_ref)

    @classmethod
    def line_span(cls, start: int, end: int) -> "ProvenanceLocatorV1":
        """Create an inclusive one-based source line span."""
        return cls(kind="line_span", line_start=start, line_end=end)

    @classmethod
    def json_pointer(cls, *segments: str) -> "ProvenanceLocatorV1":
        """Create a canonical JSON-pointer locator from decoded segments."""
        return cls(kind="json_pointer", pointer=tuple(segments))

    def to_wire(self) -> dict[str, object]:
        """Return the closed canonical locator payload."""
        if self.kind == "opaque":
            return {"kind": "opaque", "opaque_ref": self.opaque_ref}
        if self.kind == "line_span":
            return {
                "kind": "line_span",
                "line_start": self.line_start,
                "line_end": self.line_end,
            }
        return {"kind": "json_pointer", "pointer": list(self.pointer)}

    @classmethod
    def from_wire(cls, value: object) -> "ProvenanceLocatorV1":
        """Decode and validate a closed provenance-locator payload."""
        if not isinstance(value, Mapping):
            raise ProtocolShapeError("ProvenanceLocatorV1 wire must be object")
        keys = set(value)
        kind = value.get("kind")
        if kind == "opaque" and keys == {"kind", "opaque_ref"}:
            return cls(kind="opaque", opaque_ref=value["opaque_ref"])  # type: ignore[arg-type]
        if kind == "line_span" and keys == {"kind", "line_start", "line_end"}:
            return cls(
                kind="line_span",
                line_start=value["line_start"],  # type: ignore[arg-type]
                line_end=value["line_end"],  # type: ignore[arg-type]
            )
        if kind == "json_pointer" and keys == {"kind", "pointer"}:
            pointer = value["pointer"]
            if not isinstance(pointer, list):
                raise ProtocolShapeError(
                    "ProvenanceLocatorV1 json_pointer wire pointer must be list"
                )
            return cls(kind="json_pointer", pointer=tuple(pointer))  # type: ignore[arg-type]
        raise ProtocolShapeError("ProvenanceLocatorV1 wire has unsupported fields")


@dataclass(frozen=True)
class ProvenanceRefV1:
    """Safe source identity for Scenario, replay and product Explain values.

    ``admission_ref`` is only an opaque neutral reference to an externally
    made decision.  It conveys neither the decision, its authority nor any
    authorization.  It is deliberately distinct from ``source_ref``.
    """

    source_ref: str
    locator: ProvenanceLocatorV1
    origin_role: ProvenanceOriginRoleV1
    content_digest: str | None = None
    admission_ref: str | None = None
    reference_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_opaque_ref(self.source_ref, field_name="ProvenanceRefV1.source_ref")
        if not isinstance(self.locator, ProvenanceLocatorV1):
            raise ProtocolShapeError("ProvenanceRefV1.locator must be ProvenanceLocatorV1")
        if self.origin_role not in _ORIGIN_ROLES:
            raise ProtocolShapeError("ProvenanceRefV1.origin_role is unsupported")
        if self.content_digest is not None:
            _require_sha256_token(self.content_digest, field_name="ProvenanceRefV1.content_digest")
        if self.admission_ref is not None:
            _require_opaque_ref(self.admission_ref, field_name="ProvenanceRefV1.admission_ref")
        object.__setattr__(
            self,
            "reference_digest",
            _token("provenance_ref_v1", self.to_wire()),
        )

    def to_wire(self) -> dict[str, object]:
        """Return the safe opaque provenance-reference payload."""
        return {
            "ref": self.source_ref,
            "locator": self.locator.to_wire(),
            "content_digest": self.content_digest,
            "origin_role": self.origin_role,
            "admission_ref": self.admission_ref,
        }

    @classmethod
    def from_wire(cls, value: object) -> "ProvenanceRefV1":
        """Decode and validate a closed provenance-reference payload."""
        if not isinstance(value, Mapping) or set(value) != {
            "ref",
            "locator",
            "content_digest",
            "origin_role",
            "admission_ref",
        }:
            raise ProtocolShapeError("ProvenanceRefV1 wire has unsupported or missing fields")
        return cls(
            source_ref=value["ref"],  # type: ignore[arg-type]
            locator=ProvenanceLocatorV1.from_wire(value["locator"]),
            content_digest=value["content_digest"],  # type: ignore[arg-type]
            origin_role=value["origin_role"],  # type: ignore[arg-type]
            admission_ref=value["admission_ref"],  # type: ignore[arg-type]
        )


def canonical_provenance_refs_v1(
    values: object,
    *,
    field_name: str = "provenance",
) -> tuple[ProvenanceRefV1, ...]:
    """Return one bounded, ordered, full-wire-deduplicated source sequence.

    Provenance order is presentation-relevant, so first occurrence wins rather
    than sorting references by a source identifier.  Deduplication uses the
    complete wire identity, not just ``source_ref``: two spans in one source
    are distinct source references.
    """

    if not isinstance(values, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[ProvenanceRefV1, ...]")
    if len(values) > MAX_PROVENANCE_REFS_V1:
        raise ProtocolShapeError(f"{field_name} exceeds provenance reference cap")
    output: list[ProvenanceRefV1] = []
    seen: set[str] = set()
    for index, item in enumerate(values):
        if not isinstance(item, ProvenanceRefV1):
            raise ProtocolShapeError(f"{field_name}[{index}] must be ProvenanceRefV1")
        if item.reference_digest not in seen:
            seen.add(item.reference_digest)
            output.append(item)
    return tuple(output)


__all__ = [
    "MAX_PROVENANCE_POINTER_SEGMENTS_V1",
    "MAX_PROVENANCE_REFS_V1",
    "ProvenanceLocatorKindV1",
    "ProvenanceLocatorV1",
    "ProvenanceOriginRoleV1",
    "ProvenanceRefV1",
    "canonical_provenance_refs_v1",
]
