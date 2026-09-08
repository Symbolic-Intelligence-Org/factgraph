"""Read-only outcome expectations for the unified EvaluationQuery facade.

The v0 contract intentionally admits only ``contains_row``.  It observes a
completed projection result; it does not participate in Policy lowering or
turn an empty result into a general closed-world assertion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str

ExpectationStatusV0 = Literal[
    "satisfied",
    "not_satisfied",
    "underdetermined",
    "unsupported",
]
ExpectationCompletenessBasisV0 = Literal[
    "complete_native_enumeration_v0",
    "unknown",
    "unsupported",
]
ExpectationKindV0 = Literal["contains_row"]

_STATUSES = frozenset({"satisfied", "not_satisfied", "underdetermined", "unsupported"})
_BASES = frozenset({"complete_native_enumeration_v0", "unknown", "unsupported"})


@dataclass(frozen=True)
class ContainsRowExpectationV0:
    """Caller intent before selected values receive schema-aware domains."""

    expectation_id: str
    selected_values: tuple[tuple[str, object], ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.expectation_id, field_name="ContainsRowExpectationV0.expectation_id")
        if not isinstance(self.selected_values, tuple) or not self.selected_values:
            raise ProtocolShapeError(
                "ContainsRowExpectationV0.selected_values must be non-empty tuple[(alias, value), ...]"
            )
        aliases: list[str] = []
        normalized: list[tuple[str, object]] = []
        for index, item in enumerate(self.selected_values):
            if not isinstance(item, tuple) or len(item) != 2:
                raise ProtocolShapeError(
                    f"ContainsRowExpectationV0.selected_values[{index}] must be tuple[str, object]"
                )
            alias, value = item
            _require_non_empty_str(alias, field_name=f"ContainsRowExpectationV0.selected_values[{index}].alias")
            aliases.append(alias)
            normalized.append((alias, value))
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("ContainsRowExpectationV0 selected aliases must be unique")
        object.__setattr__(self, "selected_values", tuple(sorted(normalized, key=lambda item: item[0])))


@dataclass(frozen=True)
class ResolvedExpectationValueV0:
    """One expectation operand canonicalized to its selected value domain."""

    alias: str
    value_type: str
    normalized_value: object
    value_digest: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.alias, field_name="ResolvedExpectationValueV0.alias")
        _require_non_empty_str(self.value_type, field_name="ResolvedExpectationValueV0.value_type")
        _require_sha256_hex(self.value_digest, "ResolvedExpectationValueV0.value_digest")


@dataclass(frozen=True)
class CompiledContainsRowExpectationV0:
    """Schema-resolved expectation attached only to a targeted Query wrapper."""

    expectation_id: str
    query_digest: str
    values: tuple[ResolvedExpectationValueV0, ...]
    expectation_digest: str = field(init=False)
    kind: ExpectationKindV0 = "contains_row"

    def __post_init__(self) -> None:
        _require_non_empty_str(self.expectation_id, field_name="CompiledContainsRowExpectationV0.expectation_id")
        _require_sha256_hex(self.query_digest, "CompiledContainsRowExpectationV0.query_digest")
        if self.kind != "contains_row":
            raise ProtocolShapeError("CompiledContainsRowExpectationV0.kind must be contains_row")
        if not isinstance(self.values, tuple) or not self.values or not all(
            isinstance(item, ResolvedExpectationValueV0) for item in self.values
        ):
            raise ProtocolShapeError(
                "CompiledContainsRowExpectationV0.values must be non-empty tuple[ResolvedExpectationValueV0, ...]"
            )
        aliases = tuple(item.alias for item in self.values)
        if tuple(sorted(aliases)) != aliases or len(set(aliases)) != len(aliases):
            raise ProtocolShapeError(
                "CompiledContainsRowExpectationV0 values must have sorted unique aliases"
            )
        expected = _expectation_digest(self.expectation_id, self.query_digest, self.values)
        supplied = getattr(self, "expectation_digest", None)
        if supplied is None:
            object.__setattr__(self, "expectation_digest", expected)
        elif supplied != expected:
            raise ProtocolShapeError(
                "CompiledContainsRowExpectationV0.expectation_digest does not match content"
            )


@dataclass(frozen=True)
class ExpectationResultV0:
    """A sealed result-local outcome, not a policy or authorization verdict."""

    expectation_id: str
    kind: ExpectationKindV0
    expectation_digest: str
    query_digest: str
    targeted_query_wrapper_digest: str
    result_id: str
    result_digest: str
    run_anchor_digest: str | None
    status: ExpectationStatusV0
    completeness_basis: ExpectationCompletenessBasisV0
    matched_row_ids: tuple[str, ...]
    diagnostic_code: str
    outcome_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.expectation_id, field_name="ExpectationResultV0.expectation_id")
        if self.kind != "contains_row":
            raise ProtocolShapeError("ExpectationResultV0.kind must be contains_row")
        for name in (
            "expectation_digest",
            "targeted_query_wrapper_digest",
            "result_digest",
        ):
            _require_sha256_token(getattr(self, name), f"ExpectationResultV0.{name}")
        _require_sha256_hex(self.query_digest, "ExpectationResultV0.query_digest")
        _require_prefixed_token(self.result_id, "evalr_v1:", "ExpectationResultV0.result_id")
        if self.run_anchor_digest is not None:
            _require_sha256_token(self.run_anchor_digest, "ExpectationResultV0.run_anchor_digest")
        if self.status not in _STATUSES:
            raise ProtocolShapeError("ExpectationResultV0.status is unsupported")
        if self.completeness_basis not in _BASES:
            raise ProtocolShapeError("ExpectationResultV0.completeness_basis is unsupported")
        _require_non_empty_str(self.diagnostic_code, field_name="ExpectationResultV0.diagnostic_code")
        if not isinstance(self.matched_row_ids, tuple) or any(
            not isinstance(row_id, str) or not row_id for row_id in self.matched_row_ids
        ):
            raise ProtocolShapeError("ExpectationResultV0.matched_row_ids must be tuple[str, ...]")
        if tuple(sorted(self.matched_row_ids)) != self.matched_row_ids or len(set(self.matched_row_ids)) != len(self.matched_row_ids):
            raise ProtocolShapeError("ExpectationResultV0.matched_row_ids must be sorted and unique")
        if self.status == "satisfied":
            if not self.matched_row_ids or self.diagnostic_code != "EXPECTATION_CONTAINS_ROW_SATISFIED":
                raise ProtocolShapeError("satisfied contains-row result requires matching rows and its diagnostic")
        elif self.matched_row_ids:
            raise ProtocolShapeError("non-satisfied expectation result must not carry matching rows")
        if self.status == "not_satisfied":
            if (
                self.completeness_basis != "complete_native_enumeration_v0"
                or self.diagnostic_code != "EXPECTATION_CONTAINS_ROW_NOT_SATISFIED"
            ):
                raise ProtocolShapeError("not_satisfied requires complete native enumeration")
        elif self.status == "underdetermined":
            if self.completeness_basis != "unknown" or self.diagnostic_code != "EXPECTATION_COMPLETENESS_UNKNOWN":
                raise ProtocolShapeError("underdetermined requires unknown completeness")
        elif self.status == "unsupported":
            if self.completeness_basis != "unsupported" or self.diagnostic_code != "EXPECTATION_UNSUPPORTED":
                raise ProtocolShapeError("unsupported result requires unsupported basis")
        elif self.completeness_basis not in {"complete_native_enumeration_v0", "unknown"}:
            raise ProtocolShapeError("satisfied result cannot use unsupported completeness basis")
        expected = _outcome_digest(
            self.expectation_id,
            self.kind,
            self.expectation_digest,
            self.query_digest,
            self.targeted_query_wrapper_digest,
            self.result_id,
            self.result_digest,
            self.run_anchor_digest,
            self.status,
            self.completeness_basis,
            self.matched_row_ids,
            self.diagnostic_code,
        )
        supplied = getattr(self, "outcome_digest", None)
        if supplied is None:
            object.__setattr__(self, "outcome_digest", expected)
        elif supplied != expected:
            raise ProtocolShapeError("ExpectationResultV0.outcome_digest does not match content")


def _expectation_digest(
    expectation_id: str,
    query_digest: str,
    values: tuple[ResolvedExpectationValueV0, ...],
) -> str:
    return _token(
        "compiled_contains_row_expectation_v0",
        {
            "expectation_id": expectation_id,
            "query_digest": query_digest,
            "values": [
                [item.alias, item.value_type, item.value_digest]
                for item in values
            ],
        },
    )


def _outcome_digest(*values: object) -> str:
    return _token("evaluation_query_expectation_result_v0", values)


def _token(label: str, payload: object) -> str:
    raw = json.dumps(
        {"format": label, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return f"sha256:{sha256_hex(raw)}"


def _require_sha256_hex(value: object, field_name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ProtocolShapeError(f"{field_name} must be 64 lowercase sha256 hex characters")


def _require_sha256_token(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    _require_sha256_hex(value[7:], field_name)


def _require_prefixed_token(value: object, prefix: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ProtocolShapeError(f"{field_name} must start with {prefix!r}")
    _require_sha256_hex(value[len(prefix):], field_name)


__all__ = [
    "CompiledContainsRowExpectationV0",
    "ContainsRowExpectationV0",
    "ExpectationCompletenessBasisV0",
    "ExpectationKindV0",
    "ExpectationResultV0",
    "ExpectationStatusV0",
    "ResolvedExpectationValueV0",
]
