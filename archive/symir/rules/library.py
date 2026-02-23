"""Library specification registry for predicates and expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from symir.errors import SchemaError


@dataclass(frozen=True)
class LibrarySpec:
    """Specification for library predicates or expression nodes."""

    name: str
    arity: int
    kind: str  # "predicate" or "expr"
    description: str
    signature: Optional[list[str]] = None
    typing: Optional[str] = None
    backend_mapping: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        if self.kind not in ("predicate", "expr"):
            raise SchemaError("LibrarySpec kind must be 'predicate' or 'expr'.")
        if not self.name:
            raise SchemaError("LibrarySpec name must be non-empty.")
        if self.arity < 0:
            raise SchemaError("LibrarySpec arity must be non-negative.")
        if self.signature is not None and len(self.signature) != self.arity:
            raise SchemaError("LibrarySpec signature length must match arity.")

    @property
    def schema_id(self) -> str:
        if self.kind != "predicate":
            raise SchemaError("schema_id is only available for predicate specs.")
        payload = {
            "kind": self.kind,
            "name": self.name,
            "arity": self.arity,
            "signature": self.signature,
        }
        return _hash_payload(payload)


class Library:
    """Registry for library specs used in rendering."""

    def __init__(self) -> None:
        self._specs: dict[tuple[str, int, str], LibrarySpec] = {}

    def register(self, spec: LibrarySpec) -> None:
        key = (spec.name, spec.arity, spec.kind)
        if key in self._specs:
            raise SchemaError(
                f"Library spec already registered: {spec.name}/{spec.arity} ({spec.kind})"
            )
        self._specs[key] = spec

    def get(self, name: str, arity: int, kind: str) -> Optional[LibrarySpec]:
        return self._specs.get((name, arity, kind))

    def resolve_mapping(self, name: str, arity: int, kind: str, backend: str) -> Optional[str]:
        spec = self.get(name, arity, kind)
        if spec is None:
            return None
        if spec.backend_mapping:
            return spec.backend_mapping.get(backend)
        return None

    def predicate_ids(self) -> dict[str, LibrarySpec]:
        return {spec.schema_id: spec for spec in self._specs.values() if spec.kind == "predicate"}

    def get_predicate_by_id(self, predicate_id: str) -> Optional[LibrarySpec]:
        for spec in self._specs.values():
            if spec.kind == "predicate" and spec.schema_id == predicate_id:
                return spec
        return None

    def expr_ops(self) -> list[str]:
        return [spec.name for spec in self._specs.values() if spec.kind == "expr"]


def _hash_payload(payload: dict[str, object]) -> str:
    import json
    import hashlib

    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
