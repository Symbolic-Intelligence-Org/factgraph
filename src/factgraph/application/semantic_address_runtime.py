from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from factgraph.core.protocol.digests import sha256_hex

from .protocol import (
    ErrorDTO,
    ResolvedRuleContract,
    RuleOccurrence,
    RulePortRef,
    RuleValidationError,
)
from .protocol.semantic_address import SemanticPortAddress
from .protocol.semantic_port import SemanticEndpoint
from .semantic_port_runtime import (
    ResolvedRuleBundle,
    SemanticPortResolutionError,
    assert_rule_contract_current,
)

_ADDRESS_SPACE_FORMAT = "semantic_address_space_v1"


class SemanticAddressResolutionError(ValueError):
    """Typed failure while constructing or resolving a semantic address."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...],
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(code=self.code, message=str(self), path=self.path, details=self.details)


@dataclass(frozen=True)
class _ResolvedSemanticPortRef:
    """Resolver-produced value; not a public constructible protocol contract."""

    address: SemanticPortAddress
    execution_ref: RulePortRef
    endpoint: SemanticEndpoint
    semantic_contract_digest: str


@dataclass(frozen=True)
class ManagedRuleOccurrence:
    """One authored occurrence of an exact resolved Rule contract."""

    occurrence: RuleOccurrence
    contract: ResolvedRuleContract

    def __post_init__(self) -> None:
        if not isinstance(self.occurrence, RuleOccurrence):
            raise _error(
                "occurrence must be RuleOccurrence",
                "INVALID_MANAGED_OCCURRENCE",
                ("occurrence",),
            )
        if not isinstance(self.contract, ResolvedRuleContract):
            raise _error(
                "contract must be ResolvedRuleContract",
                "INVALID_MANAGED_OCCURRENCE",
                ("contract",),
            )
        _assert_occurrence_current(self)


@dataclass(frozen=True)
class SemanticAddressSpace:
    """Copied, frozen authored occurrence namespace for direct semantic ports."""

    occurrences: Collection[ManagedRuleOccurrence]
    address_space_digest: str = field(init=False)
    _by_alias: Mapping[str, ManagedRuleOccurrence] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        try:
            copied = tuple(self.occurrences)
        except TypeError as exc:
            raise _error(
                "occurrences must be a collection",
                "INVALID_OCCURRENCE_COLLECTION",
                ("occurrences",),
            ) from exc
        if not copied:
            raise _error(
                "occurrences must not be empty",
                "INVALID_OCCURRENCE_COLLECTION",
                ("occurrences",),
            )

        by_alias: dict[str, ManagedRuleOccurrence] = {}
        for index, occurrence in enumerate(copied):
            if not isinstance(occurrence, ManagedRuleOccurrence):
                raise _error(
                    "occurrences must contain ManagedRuleOccurrence values",
                    "INVALID_OCCURRENCE_COLLECTION",
                    ("occurrences", str(index)),
                )
            _assert_occurrence_current(occurrence)
            alias = occurrence.occurrence.alias
            if alias in by_alias:
                raise _error(
                    f"duplicate occurrence alias {alias!r}",
                    "DUPLICATE_OCCURRENCE_ALIAS",
                    ("occurrences", alias),
                )
            by_alias[alias] = occurrence

        ordered = tuple(by_alias[alias] for alias in sorted(by_alias))
        object.__setattr__(self, "occurrences", ordered)
        object.__setattr__(self, "_by_alias", MappingProxyType(dict(by_alias)))
        object.__setattr__(self, "address_space_digest", _address_space_digest(ordered))

    def resolve(self, address: SemanticPortAddress) -> _ResolvedSemanticPortRef:
        if not isinstance(address, SemanticPortAddress):
            raise _error(
                "address must be SemanticPortAddress",
                "INVALID_SEMANTIC_ADDRESS",
                ("address",),
            )
        managed = self._by_alias.get(address.occurrence_alias)
        if managed is None:
            raise _error(
                f"unknown occurrence alias {address.occurrence_alias!r}",
                "UNKNOWN_OCCURRENCE_ALIAS",
                ("address", "occurrence_alias"),
            )
        _assert_occurrence_current(managed)
        rule_ports = managed.occurrence.rule.ports
        contract_ports = managed.contract.ports
        if address.port_name not in rule_ports and address.port_name not in contract_ports:
            raise _error(
                f"unknown semantic port {address.port_name!r}",
                "UNKNOWN_SEMANTIC_PORT",
                ("address", "port_name"),
            )
        if address.port_name not in rule_ports or address.port_name not in contract_ports:
            raise _error(
                "Rule and semantic contract port sets no longer agree",
                "OCCURRENCE_CONTRACT_MISMATCH",
                ("address", "port_name"),
            )

        semantic_port = contract_ports[address.port_name]
        execution_ref = managed.occurrence.port(address.port_name)
        if semantic_port.var != execution_ref.var:
            raise _error(
                "Rule and semantic contract Vars no longer agree",
                "OCCURRENCE_CONTRACT_MISMATCH",
                ("address", "port_name"),
            )
        return _ResolvedSemanticPortRef(
            address=address,
            execution_ref=execution_ref,
            endpoint=semantic_port.endpoint,
            semantic_contract_digest=managed.contract.semantic_contract_digest,
        )


def manage_rule_occurrence(bundle: ResolvedRuleBundle, alias: str) -> ManagedRuleOccurrence:
    """Bind an authored alias to one exact F1-lite resolved Rule bundle."""

    if not isinstance(bundle, ResolvedRuleBundle):
        raise _error(
            "bundle must be ResolvedRuleBundle",
            "INVALID_RESOLVED_RULE_BUNDLE",
            ("bundle",),
        )
    try:
        occurrence = bundle.rule.as_(alias)
    except RuleValidationError as exc:
        raise _error(
            "invalid occurrence alias",
            "INVALID_OCCURRENCE_ALIAS",
            ("alias",),
            {"cause_type": type(exc).__name__},
        ) from exc
    return ManagedRuleOccurrence(occurrence=occurrence, contract=bundle.contract)


def _assert_occurrence_current(managed: ManagedRuleOccurrence) -> None:
    try:
        assert_rule_contract_current(managed.occurrence.rule, managed.contract)
    except SemanticPortResolutionError as exc:
        raise _error(
            "occurrence Rule does not match its semantic contract",
            "OCCURRENCE_CONTRACT_MISMATCH",
            ("occurrence", managed.occurrence.alias),
            {"semantic_port_code": exc.code},
        ) from exc


def _address_space_digest(occurrences: tuple[ManagedRuleOccurrence, ...]) -> str:
    payload = {
        "format": _ADDRESS_SPACE_FORMAT,
        "occurrences": [
            {
                "alias": managed.occurrence.alias,
                "rule": {
                    "id": managed.occurrence.rule.id,
                    "version": managed.occurrence.rule.version,
                    "content_digest": managed.occurrence.rule.content_digest,
                },
                "semantic_contract_digest": managed.contract.semantic_contract_digest,
            }
            for managed in occurrences
        ],
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return sha256_hex(encoded)


def _error(
    message: str,
    code: str,
    path: tuple[str, ...],
    details: dict[str, Any] | None = None,
) -> SemanticAddressResolutionError:
    return SemanticAddressResolutionError(message, code=code, path=path, details=details)


__all__ = [
    "ManagedRuleOccurrence",
    "SemanticAddressResolutionError",
    "SemanticAddressSpace",
    "manage_rule_occurrence",
]
