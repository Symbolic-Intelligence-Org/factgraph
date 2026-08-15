from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


ReaderClass = Literal["ledger", "runtime", "audit"]
LoadPolicy = Literal["eager", "lazy"]
StorageScope = Literal["claim", "tx_liftable"]

DEFAULT_READER_CLASS: ReaderClass = "runtime"
DEFAULT_PREMISE_ELIGIBLE = False
DEFAULT_LOAD_POLICY: LoadPolicy = "eager"
DEFAULT_STORAGE_SCOPE: StorageScope = "claim"
DEFAULT_QUERY_INDEXED = False

SYSTEM_MANAGED_META_KEYS = frozenset(
    {"ingested_at", "ingest_key", "revoked_asrt_id"}
)
EVENT_TIME_META_KEY = "event_time"

BUILTIN_PREMISE_ELIGIBLE_META_KEYS = frozenset(
    {"provenance_class", "origin_binding"}
)

_POLICY_ATTRIBUTES = frozenset(
    {
        "reader_class",
        "premise_eligible",
        "load_policy",
        "storage_scope",
        "query_indexed",
    }
)
_READER_CLASSES = frozenset({"ledger", "runtime", "audit"})
_LOAD_POLICIES = frozenset({"eager", "lazy"})
_STORAGE_SCOPES = frozenset({"claim", "tx_liftable"})
_RESERVED_META_KEY_PREFIXES = ("__system__.", "__factgraph_annotation_v1__:")
_RESERVED_META_KEYS = frozenset(
    {
        *SYSTEM_MANAGED_META_KEYS,
        "assertion_digest",
        "schema_digest",
        "tx_id",
    }
)


class MetaKeyPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class MetaKeyPolicy:
    """Typed declaration for one schema-level meta key.

    Defaults preserve the Phase 2 behavior of an ordinary, claim-scoped meta
    key. Canonical Schema IR serializes only attributes that differ from these
    defaults; an empty object remains a meaningful declaration.
    """

    reader_class: ReaderClass = DEFAULT_READER_CLASS
    premise_eligible: bool = DEFAULT_PREMISE_ELIGIBLE
    load_policy: LoadPolicy = DEFAULT_LOAD_POLICY
    storage_scope: StorageScope = DEFAULT_STORAGE_SCOPE
    query_indexed: bool = DEFAULT_QUERY_INDEXED

    def __post_init__(self) -> None:
        _validate_policy_values(
            {
                "reader_class": self.reader_class,
                "premise_eligible": self.premise_eligible,
                "load_policy": self.load_policy,
                "storage_scope": self.storage_scope,
                "query_indexed": self.query_indexed,
            },
            path="MetaKeyPolicy",
        )

    def canonical_attributes(self) -> dict[str, object]:
        """Return the canonical-minimal non-default policy attributes."""
        out: dict[str, object] = {}
        if self.reader_class != DEFAULT_READER_CLASS:
            out["reader_class"] = self.reader_class
        if self.premise_eligible != DEFAULT_PREMISE_ELIGIBLE:
            out["premise_eligible"] = self.premise_eligible
        if self.load_policy != DEFAULT_LOAD_POLICY:
            out["load_policy"] = self.load_policy
        if self.storage_scope != DEFAULT_STORAGE_SCOPE:
            out["storage_scope"] = self.storage_scope
        if self.query_indexed != DEFAULT_QUERY_INDEXED:
            out["query_indexed"] = self.query_indexed
        return out

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, path: str) -> MetaKeyPolicy:
        """Validate and construct a metadata-key policy from a mapping.

        Args:
            value: Policy attributes using the public schema vocabulary.
            path: Diagnostic path used in validation errors.

        Returns:
            A typed metadata-key policy with defaults applied.

        Raises:
            MetaKeyPolicyError: If an attribute or value is invalid.
        """
        if not isinstance(value, Mapping):
            raise MetaKeyPolicyError(f"{path} must be object")
        unknown = sorted(set(value) - _POLICY_ATTRIBUTES)
        if unknown:
            raise MetaKeyPolicyError(f"{path} has unknown attributes: {unknown}")
        _validate_policy_values(value, path=path)
        return cls(
            reader_class=value.get("reader_class", DEFAULT_READER_CLASS),
            premise_eligible=value.get(
                "premise_eligible", DEFAULT_PREMISE_ELIGIBLE
            ),
            load_policy=value.get("load_policy", DEFAULT_LOAD_POLICY),
            storage_scope=value.get("storage_scope", DEFAULT_STORAGE_SCOPE),
            query_indexed=value.get("query_indexed", DEFAULT_QUERY_INDEXED),
        )


def normalize_authoring_meta_keys(value: Any) -> dict[str, dict[str, object]] | None:
    """Validate authoring input and return canonical-minimal IR attributes."""

    if not isinstance(value, Mapping):
        raise MetaKeyPolicyError("$.meta_keys must be object")
    if not value:
        return None
    for key in value:
        _validate_meta_key(key, path="$.meta_keys")
    out: dict[str, dict[str, object]] = {}
    for key in sorted(value):
        policy = MetaKeyPolicy.from_mapping(value[key], path=f"$.meta_keys[{key!r}]")
        out[key] = policy.canonical_attributes()
    return out


def validate_canonical_meta_keys(value: Any) -> None:
    """Require the one canonical Schema IR representation of meta policies."""

    if not isinstance(value, Mapping):
        raise MetaKeyPolicyError("$.meta_keys must be object")
    if not value:
        raise MetaKeyPolicyError("$.meta_keys must be omitted when empty")
    normalized = normalize_authoring_meta_keys(value)
    assert normalized is not None
    for key in normalized:
        supplied = dict(value[key])
        if supplied != normalized[key]:
            default_attributes = sorted(set(supplied) - set(normalized[key]))
            raise MetaKeyPolicyError(
                f"$.meta_keys[{key!r}] is not canonical-minimal; "
                f"omit default attributes: {default_attributes}"
            )


def typed_meta_keys_to_authoring(
    value: Mapping[str, MetaKeyPolicy] | None,
) -> dict[str, dict[str, object]] | None:
    """Convert the typed Python compile surface to authoring JSON shape."""

    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise MetaKeyPolicyError("meta_keys must be mapping[str, MetaKeyPolicy]")
    raw: dict[str, dict[str, object]] = {}
    for key, policy in value.items():
        if not isinstance(policy, MetaKeyPolicy):
            raise MetaKeyPolicyError(
                f"meta_keys[{key!r}] must be MetaKeyPolicy, got {type(policy).__name__}"
            )
        raw[key] = policy.canonical_attributes()
    return normalize_authoring_meta_keys(raw)


def declared_meta_key_policy(schema_ir: Mapping[str, Any], key: str) -> MetaKeyPolicy | None:
    """Resolve one explicit or built-in declaration, with explicit precedence."""

    declarations = schema_ir.get("meta_keys", {})
    if isinstance(declarations, Mapping) and key in declarations:
        value = declarations[key]
        if not isinstance(value, Mapping):
            raise MetaKeyPolicyError(f"$.meta_keys[{key!r}] must be object")
        return MetaKeyPolicy.from_mapping(value, path=f"$.meta_keys[{key!r}]")
    if key in BUILTIN_PREMISE_ELIGIBLE_META_KEYS:
        return MetaKeyPolicy(premise_eligible=True)
    return None


def require_premise_eligible_meta_key(
    schema_ir: Mapping[str, Any], key: str, *, context: str
) -> None:
    policy = declared_meta_key_policy(schema_ir, key)
    if policy is None or not policy.premise_eligible:
        raise MetaKeyPolicyError(
            f"{context} references meta key {key!r}, which is not declared "
            "premise_eligible in this schema"
        )


def lazy_meta_keys(schema_ir: Mapping[str, Any]) -> frozenset[str]:
    declarations = schema_ir.get("meta_keys", {})
    if not isinstance(declarations, Mapping):
        raise MetaKeyPolicyError("$.meta_keys must be object")
    return frozenset(
        key
        for key, value in declarations.items()
        if MetaKeyPolicy.from_mapping(
            value, path=f"$.meta_keys[{key!r}]"
        ).load_policy
        == "lazy"
    )


def require_tx_liftable_meta_key(
    schema_ir: Mapping[str, Any], key: str, *, context: str
) -> None:
    policy = declared_meta_key_policy(schema_ir, key)
    if policy is None or policy.storage_scope != "tx_liftable":
        raise MetaKeyPolicyError(
            f"{context} references meta key {key!r}, which is not declared "
            "storage_scope='tx_liftable' in this schema"
        )


def _validate_meta_key(value: Any, *, path: str) -> None:
    if not isinstance(value, str) or not value:
        raise MetaKeyPolicyError(f"{path} keys must be non-empty strings")
    if value in _RESERVED_META_KEYS or value.startswith(_RESERVED_META_KEY_PREFIXES):
        raise MetaKeyPolicyError(f"{path} cannot declare reserved meta key: {value!r}")


def _validate_policy_values(value: Mapping[str, Any], *, path: str) -> None:
    reader_class = value.get("reader_class", DEFAULT_READER_CLASS)
    if not isinstance(reader_class, str) or reader_class not in _READER_CLASSES:
        raise MetaKeyPolicyError(
            f"{path}.reader_class must be one of {sorted(_READER_CLASSES)}"
        )
    premise_eligible = value.get("premise_eligible", DEFAULT_PREMISE_ELIGIBLE)
    if not isinstance(premise_eligible, bool):
        raise MetaKeyPolicyError(f"{path}.premise_eligible must be bool")
    load_policy = value.get("load_policy", DEFAULT_LOAD_POLICY)
    if not isinstance(load_policy, str) or load_policy not in _LOAD_POLICIES:
        raise MetaKeyPolicyError(
            f"{path}.load_policy must be one of {sorted(_LOAD_POLICIES)}"
        )
    storage_scope = value.get("storage_scope", DEFAULT_STORAGE_SCOPE)
    if not isinstance(storage_scope, str) or storage_scope not in _STORAGE_SCOPES:
        raise MetaKeyPolicyError(
            f"{path}.storage_scope must be one of {sorted(_STORAGE_SCOPES)}"
        )
    query_indexed = value.get("query_indexed", DEFAULT_QUERY_INDEXED)
    if not isinstance(query_indexed, bool):
        raise MetaKeyPolicyError(f"{path}.query_indexed must be bool")
