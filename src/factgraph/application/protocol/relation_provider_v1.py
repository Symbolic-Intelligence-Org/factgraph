"""Restricted materialized relation providers for :class:`GoalPlanV1`.

The Query unification contract deliberately treats a provider as a relation
*supplier*, not as an opaque Rule.  A provider may do a pure computation or a
bounded read before the engine starts, but it must return finite, typed rows
and a sealed receipt.  Native, Souffle and ProbLog therefore consume the same
materialized relation; none of them invokes provider code itself.

This module contains declarations only.  The callable is intentionally kept
out of every digest and out of serializable result objects.  Callers pin a
``code_digest``/``provider_digest`` and the runtime seals the actual request
and returned receipt separately.  That is integrity metadata, not a claim
that FactGraph has inspected or proved the provider implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str
from .goal_plan_v1 import GoalValueV1

if TYPE_CHECKING:  # pragma: no cover - imported lazily by the bridge method.
    from .evaluation_run_v1 import ProviderReceiptRefV1


RelationProviderKindV1: TypeAlias = Literal["compute", "lookup"]
_KINDS = frozenset({"compute", "lookup"})

# These are deliberately protocol caps rather than a scheduling/billing policy.
# A provider result is a sealed, finite relation snapshot.  Letting the Python
# callable hand the runtime an arbitrarily large tuple would make "finite"
# technically true but operationally meaningless and would undermine the
# bounded-replay contract that consumes this DTO later.
MAX_PROVIDER_PREDICATES_V1 = 256
MAX_PROVIDER_BINDINGS_V1 = 256
MAX_PROVIDER_ROW_VALUES_V1 = 64
MAX_PROVIDER_ROWS_V1 = 50_000


def _token(label: str, payload: object) -> str:
    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # defensive; DTO fields are typed.
        raise ProtocolShapeError(f"{label} payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


def _require_token(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{name} must be sha256 token")
    raw = value[7:]
    if len(raw) != 64 or raw != raw.lower() or any(char not in "0123456789abcdef" for char in raw):
        raise ProtocolShapeError(f"{name} must be sha256 token")
    return value


def _canonical_predicate_ids(value: object, field_name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or not value
        or len(value) > MAX_PROVIDER_PREDICATES_V1
        or any(not isinstance(item, str) or not item for item in value)
        or value != tuple(sorted(value))
        or len(set(value)) != len(value)
    ):
        raise ProtocolShapeError(
            f"{field_name} must be canonical non-empty tuple[str, ...] within the provider cap"
        )
    return value


@dataclass(frozen=True)
class ProviderRequestV1:
    """Fully typed input passed to a provider before engine execution."""

    provider_digest: str
    query_digest: str
    schema_digest: str
    dependency_predicate_ids: tuple[str, ...]
    supplied_predicate_ids: tuple[str, ...]
    bindings: tuple[tuple[str, GoalValueV1], ...]
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("provider_digest", "query_digest", "schema_digest"):
            _require_token(getattr(self, name), f"ProviderRequestV1.{name}")
        dependency_ids = _canonical_predicate_ids(
            self.dependency_predicate_ids,
            "ProviderRequestV1.dependency_predicate_ids",
        )
        supplied_ids = _canonical_predicate_ids(
            self.supplied_predicate_ids,
            "ProviderRequestV1.supplied_predicate_ids",
        )
        if not set(supplied_ids).issubset(dependency_ids):
            raise ProtocolShapeError(
                "ProviderRequestV1.supplied_predicate_ids must be a subset of dependency_predicate_ids"
            )
        if not isinstance(self.bindings, tuple):
            raise ProtocolShapeError("ProviderRequestV1.bindings must be a tuple")
        if len(self.bindings) > MAX_PROVIDER_BINDINGS_V1:
            raise ProtocolShapeError("ProviderRequestV1.bindings exceeds the provider cap")
        normalized: list[tuple[str, GoalValueV1]] = []
        for index, item in enumerate(self.bindings):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0]
                or not isinstance(item[1], GoalValueV1)
            ):
                raise ProtocolShapeError(
                    f"ProviderRequestV1.bindings[{index}] must be (str, GoalValueV1)"
                )
            normalized.append(item)
        normalized.sort(key=lambda item: item[0])
        if len({item[0] for item in normalized}) != len(normalized):
            raise ProtocolShapeError("ProviderRequestV1 binding aliases must be unique")
        object.__setattr__(self, "bindings", tuple(normalized))
        object.__setattr__(
            self,
            "request_digest",
            _token(
                "provider_request_v1",
                {
                    "provider_digest": self.provider_digest,
                    "query_digest": self.query_digest,
                    "schema_digest": self.schema_digest,
                    "dependency_predicate_ids": dependency_ids,
                    "supplied_predicate_ids": supplied_ids,
                    "bindings": tuple(
                        (alias, value.tag, value.value_digest) for alias, value in normalized
                    ),
                },
            ),
        )


@dataclass(frozen=True)
class ProviderRelationRowV1:
    """One finite typed tuple returned by a provider.

    The schema validator in the runtime checks predicate existence, arity and
    domains.  The first value is constrained here to an entity reference so a
    provider cannot introduce an engine-only relation shape that the ordinary
    FactGraph relation codec cannot materialize.
    """

    predicate_id: str
    values: tuple[GoalValueV1, ...]
    origin_ref: str
    tuple_digest: str = field(init=False)
    row_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.predicate_id, field_name="ProviderRelationRowV1.predicate_id")
        _require_non_empty_str(self.origin_ref, field_name="ProviderRelationRowV1.origin_ref")
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or len(self.values) > MAX_PROVIDER_ROW_VALUES_V1
            or not all(isinstance(value, GoalValueV1) for value in self.values)
        ):
            raise ProtocolShapeError(
                "ProviderRelationRowV1.values must be non-empty GoalValueV1 tuple"
            )
        if self.values[0].tag != "entity_ref":
            raise ProtocolShapeError("ProviderRelationRowV1 first value must be entity_ref")
        object.__setattr__(
            self,
            "tuple_digest",
            _token(
                "provider_relation_tuple_v1",
                (
                    self.predicate_id,
                    tuple((value.tag, value.value_digest) for value in self.values),
                ),
            ),
        )
        object.__setattr__(
            self,
            "row_digest",
            _token(
                "provider_relation_row_v1",
                (
                    self.predicate_id,
                    tuple((value.tag, value.value_digest) for value in self.values),
                    self.origin_ref,
                ),
            ),
        )


@dataclass(frozen=True, repr=False)
class ProviderMaterializationV1:
    """A provider's sealed finite output and opaque provenance receipt."""

    provider_digest: str
    request_digest: str
    receipt_ref: str
    receipt_digest: str
    predicate_ids: tuple[str, ...]
    rows: tuple[ProviderRelationRowV1, ...]
    materialization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.provider_digest, "ProviderMaterializationV1.provider_digest")
        _require_token(self.request_digest, "ProviderMaterializationV1.request_digest")
        _require_non_empty_str(self.receipt_ref, field_name="ProviderMaterializationV1.receipt_ref")
        _require_token(self.receipt_digest, "ProviderMaterializationV1.receipt_digest")
        predicate_ids = _canonical_predicate_ids(
            self.predicate_ids,
            "ProviderMaterializationV1.predicate_ids",
        )
        if (
            not isinstance(self.rows, tuple)
            or len(self.rows) > MAX_PROVIDER_ROWS_V1
            or not all(isinstance(row, ProviderRelationRowV1) for row in self.rows)
        ):
            raise ProtocolShapeError(
                "ProviderMaterializationV1.rows must be ProviderRelationRowV1 tuple"
            )
        if any(row.predicate_id not in predicate_ids for row in self.rows):
            raise ProtocolShapeError(
                "ProviderMaterializationV1 row predicate is outside predicate_ids"
            )
        canonical = tuple(sorted(self.rows, key=lambda item: item.row_digest))
        if len({item.row_digest for item in canonical}) != len(canonical):
            raise ProtocolShapeError("ProviderMaterializationV1 has duplicate typed rows")
        if len({item.tuple_digest for item in canonical}) != len(canonical):
            raise ProtocolShapeError("ProviderMaterializationV1 has duplicate logical tuples")
        object.__setattr__(self, "rows", canonical)
        object.__setattr__(
            self,
            "materialization_digest",
            _token(
                "provider_materialization_v1",
                {
                    "provider_digest": self.provider_digest,
                    "request_digest": self.request_digest,
                    "receipt_ref": self.receipt_ref,
                    "receipt_digest": self.receipt_digest,
                    "predicate_ids": predicate_ids,
                    "rows": tuple(item.row_digest for item in canonical),
                },
            ),
        )

    def to_receipt_ref_v1(self) -> "ProviderReceiptRefV1":
        """Build the replay-safe opaque receipt bridge for this snapshot.

        The import is deliberately lazy: the relation-provider declaration is
        usable without importing the broader run/replay protocol, while every
        captured run can still pin exactly the same provider/request/output
        receipt tuple.  This is an integrity link, not a proof of provider
        internals or an instruction to call the provider again during replay.
        """

        from .evaluation_run_v1 import ProviderReceiptRefV1

        return ProviderReceiptRefV1(
            provider_digest=self.provider_digest,
            request_digest=self.request_digest,
            materialization_digest=self.materialization_digest,
            receipt_ref=self.receipt_ref,
            receipt_digest=self.receipt_digest,
        )

    def __repr__(self) -> str:
        return (
            "ProviderMaterializationV1("
            f"provider_digest={self.provider_digest!r}, receipt_ref=<redacted>, "
            f"predicate_ids={self.predicate_ids!r}, rows=<redacted>)"
        )


ProviderMaterializerV1: TypeAlias = Callable[[ProviderRequestV1], ProviderMaterializationV1]


@dataclass(frozen=True)
class RelationProviderV1:
    """Pre-engine Compute/Lookup relation supplier declaration.

    ``materialize`` may be called exactly once per Goal execution.  It is not
    included in equality or the provider digest so a durable run pins the
    declared code/contract digest rather than a Python object's address.
    """

    provider_id: str
    version: str
    kind: RelationProviderKindV1
    code_digest: str
    required_binding_aliases: tuple[str, ...]
    supplied_predicate_ids: tuple[str, ...]
    materialize: ProviderMaterializerV1 = field(repr=False, compare=False)
    provider_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.provider_id, field_name="RelationProviderV1.provider_id")
        _require_non_empty_str(self.version, field_name="RelationProviderV1.version")
        if self.kind not in _KINDS:
            raise ProtocolShapeError("RelationProviderV1.kind must be compute or lookup")
        _require_token(self.code_digest, "RelationProviderV1.code_digest")
        if not isinstance(self.required_binding_aliases, tuple) or any(
            not isinstance(alias, str) or not alias for alias in self.required_binding_aliases
        ):
            raise ProtocolShapeError(
                "RelationProviderV1.required_binding_aliases must be tuple[str, ...]"
            )
        aliases = tuple(sorted(self.required_binding_aliases))
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("RelationProviderV1 required binding aliases must be unique")
        if not callable(self.materialize):
            raise ProtocolShapeError("RelationProviderV1.materialize must be callable")
        supplied_ids = _canonical_predicate_ids(
            self.supplied_predicate_ids,
            "RelationProviderV1.supplied_predicate_ids",
        )
        object.__setattr__(self, "required_binding_aliases", aliases)
        object.__setattr__(self, "supplied_predicate_ids", supplied_ids)
        object.__setattr__(
            self,
            "provider_digest",
            _token(
                "relation_provider_v1",
                {
                    "provider_id": self.provider_id,
                    "version": self.version,
                    "kind": self.kind,
                    "code_digest": self.code_digest,
                    "required_binding_aliases": aliases,
                    "supplied_predicate_ids": supplied_ids,
                },
            ),
        )


class ProviderMaterializationError(ValueError):
    """Fail-closed pre-engine provider materialization error."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def invoke_relation_provider_v1(
    provider: RelationProviderV1,
    request: ProviderRequestV1,
) -> ProviderMaterializationV1:
    """Materialize one provider output before any evaluation adapter runs."""

    if not isinstance(provider, RelationProviderV1):
        raise ProviderMaterializationError(
            "provider must be RelationProviderV1", code="PROVIDER_INVALID"
        )
    if not isinstance(request, ProviderRequestV1):
        raise ProviderMaterializationError(
            "request must be ProviderRequestV1", code="PROVIDER_REQUEST_INVALID"
        )
    if request.provider_digest != provider.provider_digest:
        raise ProviderMaterializationError(
            "provider request is not pinned to this provider",
            code="PROVIDER_REQUEST_MISMATCH",
        )
    if request.supplied_predicate_ids != provider.supplied_predicate_ids:
        raise ProviderMaterializationError(
            "provider request does not name this provider's declared predicate subset",
            code="PROVIDER_REQUEST_SUPPLIED_PREDICATES_MISMATCH",
        )
    provided = {alias for alias, _ in request.bindings}
    missing = tuple(alias for alias in provider.required_binding_aliases if alias not in provided)
    if missing:
        raise ProviderMaterializationError(
            "provider required bindings are absent",
            code="PROVIDER_REQUIRED_BINDING_MISSING",
        )
    try:
        output = provider.materialize(request)
    except ProviderMaterializationError:
        raise
    except Exception as exc:
        raise ProviderMaterializationError(
            "provider materialization raised before engine execution",
            code="PROVIDER_MATERIALIZATION_FAILED",
        ) from exc
    if not isinstance(output, ProviderMaterializationV1):
        raise ProviderMaterializationError(
            "provider materialization must return ProviderMaterializationV1",
            code="PROVIDER_MATERIALIZATION_SHAPE",
        )
    if (
        output.provider_digest != provider.provider_digest
        or output.request_digest != request.request_digest
    ):
        raise ProviderMaterializationError(
            "provider materialization does not match the pinned request",
            code="PROVIDER_MATERIALIZATION_MISMATCH",
        )
    if output.predicate_ids != request.supplied_predicate_ids:
        raise ProviderMaterializationError(
            "provider materialization does not cover exactly its declared predicate subset",
            code="PROVIDER_MATERIALIZATION_COVERAGE_MISMATCH",
        )
    return output


__all__ = [
    "ProviderMaterializationError",
    "ProviderMaterializationV1",
    "ProviderMaterializerV1",
    "ProviderRelationRowV1",
    "ProviderRequestV1",
    "RelationProviderKindV1",
    "RelationProviderV1",
    "MAX_PROVIDER_BINDINGS_V1",
    "MAX_PROVIDER_PREDICATES_V1",
    "MAX_PROVIDER_ROWS_V1",
    "MAX_PROVIDER_ROW_VALUES_V1",
    "invoke_relation_provider_v1",
]
