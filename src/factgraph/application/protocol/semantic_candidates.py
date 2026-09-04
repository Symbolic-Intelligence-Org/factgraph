from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .evaluate_result import canonical_bytes_for_evaluate
from .semantic_port import EntityIdentityEndpoint, FieldEndpoint

SemanticCandidateScalar: TypeAlias = str | int | float | bool
SemanticCandidateMatchMode: TypeAlias = Literal["exact", "unicode_casefold_v1"]
SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_V1 = (
    "factgraph.semantic-value-candidates.v1:"
    "typed-exact,unicode-nfc-trim-casefold,prefix-suggestions,revision-guard"
)


class SemanticCandidateShapeError(ValueError):
    """One semantic-candidate protocol value violates the closed contract."""


def _scalar(value: Any, label: str) -> SemanticCandidateScalar:
    if type(value) not in {str, int, float, bool}:
        raise SemanticCandidateShapeError(f"{label} must be string/int/float/bool")
    canonical_bytes_for_evaluate("semantic_candidate_scalar_v1", value)
    return value


def _token(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise SemanticCandidateShapeError(f"{label} must be non-empty text <= 256 chars")
    return value


def _digest(payload: object) -> str:
    return "sha256:" + sha256_hex(
        canonical_bytes_for_evaluate("semantic_value_candidate_batch_v1", _payload(payload))
    )


def _sha256_digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise SemanticCandidateShapeError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def _payload(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _payload(asdict(value))
    if isinstance(value, dict):
        return {str(key): _payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_payload(item) for item in value)
    return value


SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_DIGEST_V1 = _digest(
    SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_V1
)


@dataclass(frozen=True)
class SemanticValueCandidateRequestV1:
    """One read-only candidate lookup at an explicit semantic endpoint.

    ``supplied_value`` preserves its scalar type. ``match_mode`` selects typed
    equality or the frozen Unicode string matching policy; suggestions are
    bounded hints, never authoritative replacements for an equality match.
    ``correlation_key`` associates the result with this request, not a database ID.
    """

    correlation_key: str
    endpoint: EntityIdentityEndpoint | FieldEndpoint
    supplied_value: SemanticCandidateScalar
    match_mode: SemanticCandidateMatchMode
    suggestion_limit: int = 5

    def __post_init__(self) -> None:
        _token(self.correlation_key, "correlation_key")
        if not isinstance(self.endpoint, (EntityIdentityEndpoint, FieldEndpoint)):
            raise SemanticCandidateShapeError("endpoint must be an identity or field endpoint")
        _scalar(self.supplied_value, "supplied_value")
        if self.match_mode not in {"exact", "unicode_casefold_v1"}:
            raise SemanticCandidateShapeError("match_mode is unsupported")
        if self.match_mode == "unicode_casefold_v1" and not isinstance(self.supplied_value, str):
            raise SemanticCandidateShapeError("unicode_casefold_v1 requires string")
        if (
            isinstance(self.suggestion_limit, bool)
            or not isinstance(self.suggestion_limit, int)
            or not 0 <= self.suggestion_limit <= 5
        ):
            raise SemanticCandidateShapeError("suggestion_limit must be 0..5")


@dataclass(frozen=True)
class SemanticValueCandidateBatchRequestV1:
    """A nonempty batch of uniquely correlated lookups over one projected view.

    The canonical ``request_digest`` binds all items, including endpoint,
    supplied scalar type/value, matching mode and suggestion limit.
    """

    items: tuple[SemanticValueCandidateRequestV1, ...]
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not 1 <= len(self.items) <= 128:
            raise SemanticCandidateShapeError("items must contain 1..128 requests")
        if any(not isinstance(item, SemanticValueCandidateRequestV1) for item in self.items):
            raise SemanticCandidateShapeError("items contain invalid request")
        if len({item.correlation_key for item in self.items}) != len(self.items):
            raise SemanticCandidateShapeError("correlation keys must be unique")
        object.__setattr__(self, "request_digest", _digest(self.items))


@dataclass(frozen=True)
class SemanticValueCandidateResultV1:
    """Bounded canonical values for one correlated lookup, without internal IDs.

    Exact and normalized equality matches are separate from prefix suggestions.
    The truncation flags prohibit interpreting a bounded response as an exhaustive
    inventory when more values exist. The consumer owns selection and admission.
    """

    correlation_key: str
    exact_matches: tuple[SemanticCandidateScalar, ...] = ()
    normalized_matches: tuple[SemanticCandidateScalar, ...] = ()
    matches_truncated: bool = False
    suggestions: tuple[SemanticCandidateScalar, ...] = ()
    suggestions_truncated: bool = False

    def __post_init__(self) -> None:
        _token(self.correlation_key, "correlation_key")
        for name in ("exact_matches", "normalized_matches", "suggestions"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) > 5:
                raise SemanticCandidateShapeError(f"{name} must contain <= 5 values")
            for value in values:
                _scalar(value, name)
        if not isinstance(self.matches_truncated, bool) or not isinstance(
            self.suggestions_truncated, bool
        ):
            raise SemanticCandidateShapeError("truncation fields must be bool")


@dataclass(frozen=True)
class SemanticValueCandidateBatchResultV1:
    """Candidate evidence bound to one request and one guarded projected view.

    ``view_snapshot_digest`` identifies the view used for the whole batch.
    ``evidence_digest`` seals the request pin, view pin and every item. This
    revision guard does not claim a shared transaction with later execution.
    """

    request_digest: str
    view_snapshot_digest: str
    items: tuple[SemanticValueCandidateResultV1, ...]
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.request_digest, "request_digest"),
            (self.view_snapshot_digest, "view_snapshot_digest"),
        ):
            _sha256_digest(value, label)
        if not isinstance(self.items, tuple) or not 1 <= len(self.items) <= 128:
            raise SemanticCandidateShapeError("items must contain 1..128 results")
        if any(not isinstance(item, SemanticValueCandidateResultV1) for item in self.items):
            raise SemanticCandidateShapeError("items contain invalid result")
        if len({item.correlation_key for item in self.items}) != len(self.items):
            raise SemanticCandidateShapeError("result correlation keys must be unique")
        object.__setattr__(
            self,
            "evidence_digest",
            _digest((self.request_digest, self.view_snapshot_digest, self.items)),
        )


__all__ = [
    "SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_DIGEST_V1",
    "SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_V1",
    "SemanticCandidateMatchMode",
    "SemanticCandidateScalar",
    "SemanticCandidateShapeError",
    "SemanticValueCandidateBatchRequestV1",
    "SemanticValueCandidateBatchResultV1",
    "SemanticValueCandidateRequestV1",
    "SemanticValueCandidateResultV1",
]
