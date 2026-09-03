"""Product-facing Rule/Policy authoring adapters.

The Q19 :mod:`factgraph.sdk.policy_authoring` façade is intentionally the
owner of managed-Policy syntax and lowering.  This module adds the small
product envelope around it: descriptive assets, a resolved Rule wrapper and
the symmetric direct/builder entry points.  It deliberately does *not* add a
registry, a new Rule/Policy compiler, or an evaluator.

``WeightedChoice`` is an intrinsic immutable Policy AST node.  The product
wrapper also carries a detached topology projection for sealing, capture and
the V2 adapter boundary, but that sidecar is derived from — never authoritative
over — the AST.  A tightly scoped internal V2 bridge derives a temporary
``PolicyAny`` skeleton only for the established typed compiler.  Legacy/V1
terminals reject the intrinsic node before it can be interpreted as ordinary
``Any``; only the V2 ProbLog path may lower it as an annotated disjunction.
"""

from __future__ import annotations

import inspect
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeAlias, get_type_hints

from factgraph.application.protocol.policy import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyFunctionOccurrenceV1,
    PolicyNode,
    PolicyOccurrence,
    PolicyUnify,
    PolicyV2Only,
    PolicyWeightedChoice,
    PolicyWeightedChoiceArm,
)
from factgraph.application.protocol.rule import Rule
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import (
    EntityIdentityEndpoint,
    FieldEndpoint,
    FunctionValueEndpointV1,
    ResolvedRuleContract,
    SemanticEndpoint,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.semantic_address_runtime import SemanticAddressSpace
from factgraph.application.semantic_port_runtime import (
    ResolvedRuleBundle,
    resolve_rule_contract,
)
from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import PredAtom, Var

from .dsl.application_rule import build_application_rule
from .errors import SDKStoreError
from .policy_authoring import (
    AuthoredPolicyTargetV1,
    PolicyAuthoringError,
    PolicyConstraintHandle,
    PolicyEntityPortHandle,
    PolicyFieldHandle,
    PolicyNodeHandle,
    PolicyOccurrenceHandle,
    PolicyPortHandle,
    PolicyScalarPortHandle,
    policy_draft,
)
from .schema import Entity, Field

if TYPE_CHECKING:
    from .store import SDKStore


ASSET_META_FORMAT_V1 = "asset_meta_v1"
ASSET_BINDING_FORMAT_V1 = "asset_binding_v1"
PRODUCT_RULE_IDENTITY_FORMAT_V1 = "product_rule_logical_identity_v1"
PRODUCT_POLICY_IDENTITY_FORMAT_V1 = "product_policy_logical_identity_v1"
PRODUCT_FUNCTION_IDENTITY_FORMAT_V1 = "product_function_logical_identity_v1"
PRODUCT_FUNCTION_SIGNATURE_FORMAT_V1 = "product_function_signature_v1"
PRODUCT_FUNCTION_TOPOLOGY_FORMAT_V1 = "product_function_occurrence_v1"
WEIGHTED_CHOICE_FORMAT_V1 = "weighted_choice_v1"

MAX_ASSET_NAME_CHARS_V1 = 256
MAX_ASSET_DESCRIPTION_CHARS_V1 = 4_096
MAX_ASSET_TAGS_V1 = 32
MAX_ASSET_TAG_CHARS_V1 = 64
MAX_WEIGHTED_CHOICE_ARMS_V1 = 32
MAX_WEIGHTED_CHOICE_KEY_PORTS_V1 = 8
MAX_WEIGHTED_CHOICE_ID_CHARS_V1 = 128
MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS_V1 = 32
MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE_V1 = 18

_ARM_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_CANONICAL_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


class ProductAuthoringError(SDKStoreError):
    """A typed rejection on the Q20 product authoring surface."""


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
        raise ProductAuthoringError(
            "product authoring value cannot be represented canonically",
            code="PRODUCT_AUTHORING_NONCANONICAL_VALUE",
        ) from exc


def _token(format_name: str, payload: object) -> str:
    return (
        f"sha256:{sha256_hex(_canonical_json_bytes({'format': format_name, 'payload': payload}))}"
    )


def _require_display_text(value: object, *, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or not value.strip():
        raise ProductAuthoringError(
            f"{label} must be a non-empty string", code="ASSET_META_INVALID_TEXT"
        )
    if len(value) > maximum:
        raise ProductAuthoringError(
            f"{label} exceeds {maximum} characters", code="ASSET_META_TEXT_TOO_LONG"
        )
    if value != unicodedata.normalize("NFC", value):
        raise ProductAuthoringError(
            f"{label} must already be NFC-normalized", code="ASSET_META_NONCANONICAL_TEXT"
        )
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ProductAuthoringError(
            f"{label} must not contain control characters", code="ASSET_META_INVALID_TEXT"
        )
    return value


@dataclass(frozen=True)
class AssetMeta:
    """Describe a Product Rule, Function, or Policy for human-facing use.

    The descriptor is deliberately immutable and does not participate in a
    Rule's ``content_digest`` or a Policy's compiler digest.  A product wrapper
    binds this separate descriptor to its exact logical target instead.

    Attributes:
        name: Required display name.
        description: Optional bounded description.
        tags: Canonically sorted, de-duplicated display tags.
        descriptor_digest: Derived digest of the canonical descriptor.

    Notes:
        ``AssetMeta`` is presentation metadata, not engine configuration,
        provenance authority, or a registry record. Changing it preserves the
        logical target identity but changes the product asset binding.
    """

    name: str
    description: str | None = None
    tags: tuple[str, ...] = ()
    descriptor_digest: str = field(init=False)

    def __post_init__(self) -> None:
        name = _require_display_text(
            self.name, label="AssetMeta.name", maximum=MAX_ASSET_NAME_CHARS_V1
        )
        description = self.description
        if description is not None:
            description = _require_display_text(
                description,
                label="AssetMeta.description",
                maximum=MAX_ASSET_DESCRIPTION_CHARS_V1,
            )
        if not isinstance(self.tags, tuple):
            raise ProductAuthoringError(
                "AssetMeta.tags must be a tuple of strings", code="ASSET_META_INVALID_TAGS"
            )
        if len(self.tags) > MAX_ASSET_TAGS_V1:
            raise ProductAuthoringError(
                f"AssetMeta.tags exceeds {MAX_ASSET_TAGS_V1} entries",
                code="ASSET_META_TOO_MANY_TAGS",
            )
        canonical_tags: list[str] = []
        for index, tag in enumerate(self.tags):
            text = _require_display_text(
                tag,
                label=f"AssetMeta.tags[{index}]",
                maximum=MAX_ASSET_TAG_CHARS_V1,
            )
            if text != text.strip():
                raise ProductAuthoringError(
                    "AssetMeta tags must not have leading or trailing whitespace",
                    code="ASSET_META_INVALID_TAGS",
                )
            canonical_tags.append(text)
        # Tag order is presentation-neutral.  The descriptor always preserves
        # only a deterministic de-duplicated inventory.
        ordered_tags = tuple(sorted(set(canonical_tags)))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "tags", ordered_tags)
        object.__setattr__(self, "descriptor_digest", _token(ASSET_META_FORMAT_V1, self.to_wire()))

    def to_wire(self) -> dict[str, object]:
        """Return the closed canonical descriptor snapshot for a future run."""

        return {
            "format": ASSET_META_FORMAT_V1,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
        }


@dataclass(frozen=True)
class AssetMetaAbsentV1:
    """Explicit descriptor state for raw compatibility targets."""

    state: Literal["absent"] = "absent"

    @property
    def descriptor_digest(self) -> Literal["absent"]:
        """Return the canonical marker used when no asset descriptor exists."""
        return "absent"

    def to_wire(self) -> dict[str, str]:
        """Return the canonical wire representation of absent metadata."""
        return {"format": ASSET_META_FORMAT_V1, "state": "absent"}


ASSET_META_ABSENT_V1 = AssetMetaAbsentV1()
AssetMetaStateV1: TypeAlias = AssetMeta | AssetMetaAbsentV1


def _normalize_asset_meta(value: AssetMeta | AssetMetaAbsentV1 | None) -> AssetMetaStateV1:
    if value is None:
        return ASSET_META_ABSENT_V1
    if isinstance(value, (AssetMeta, AssetMetaAbsentV1)):
        return value
    raise ProductAuthoringError(
        "meta must be AssetMeta or None", code="ASSET_META_INVALID_DESCRIPTOR"
    )


def asset_meta_for_target(target: object) -> AssetMetaStateV1:
    """Return a target's descriptor or the explicit raw ``absent`` state.

    Args:
        target: Product or compatible raw Rule/Policy target.

    Returns:
        The immutable descriptor, or ``ASSET_META_ABSENT_V1``.

    Raises:
        ProductAuthoringError: If the target kind is unsupported.
    """

    if isinstance(target, (ProductRuleV1, ProductPolicyV1, ProductFunctionV1)):
        return target.asset_meta
    if isinstance(target, (ResolvedRuleBundle, AuthoredPolicyTargetV1, Policy)):
        return ASSET_META_ABSENT_V1
    raise ProductAuthoringError(
        "asset metadata target must be a resolved Rule or managed Policy",
        code="ASSET_META_UNSUPPORTED_TARGET",
    )


def _rule_logical_identity(bundle: ResolvedRuleBundle) -> str:
    return _token(
        PRODUCT_RULE_IDENTITY_FORMAT_V1,
        {
            "rule_id": bundle.rule.id,
            "rule_version": bundle.rule.version,
            "rule_content_digest": bundle.rule.content_digest,
            "schema_digest": bundle.contract.schema_digest,
            "semantic_contract_digest": bundle.contract.semantic_contract_digest,
        },
    )


def _policy_logical_identity(
    target: AuthoredPolicyTargetV1,
    choices: tuple["WeightedChoiceTopologyV1", ...],
    functions: tuple["FunctionOccurrenceTopologyV1", ...] = (),
) -> str:
    payload: dict[str, object] = {
        "policy_id": target.policy.id,
        "policy_version": target.policy.version,
        "root_node_id": target.policy.when.node_id,
        "address_space_digest": target.address_space.address_space_digest,
        "weighted_choice_node_ids": tuple(choice.node_id for choice in choices),
    }
    # Preserve every pre-Q21 product Policy identity byte-for-byte.
    if functions:
        payload["function_occurrence_digests"] = tuple(item.topology_digest for item in functions)
    return _token(PRODUCT_POLICY_IDENTITY_FORMAT_V1, payload)


def _asset_binding_digest(
    *,
    target_kind: Literal["rule", "policy", "function"],
    logical_identity_digest: str,
    meta: AssetMetaStateV1,
) -> str:
    return _token(
        ASSET_BINDING_FORMAT_V1,
        {
            "target_kind": target_kind,
            "logical_identity_digest": logical_identity_digest,
            "descriptor_state": "present" if isinstance(meta, AssetMeta) else "absent",
            "descriptor_digest": meta.descriptor_digest,
        },
    )


@dataclass(frozen=True)
class ProductRuleV1(ResolvedRuleBundle):
    """A fully resolved Rule plus a separately sealed product descriptor."""

    asset_meta: AssetMetaStateV1 = ASSET_META_ABSENT_V1
    logical_identity_digest: str = field(init=False)
    asset_binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        ResolvedRuleBundle.__post_init__(self)
        meta = _normalize_asset_meta(self.asset_meta)
        logical_identity_digest = _rule_logical_identity(self)
        object.__setattr__(self, "asset_meta", meta)
        object.__setattr__(self, "logical_identity_digest", logical_identity_digest)
        object.__setattr__(
            self,
            "asset_binding_digest",
            _asset_binding_digest(
                target_kind="rule", logical_identity_digest=logical_identity_digest, meta=meta
            ),
        )

    @property
    def meta(self) -> AssetMetaStateV1:
        """Compatibility-friendly spelling for the immutable descriptor."""

        return self.asset_meta

    @property
    def bundle(self) -> ResolvedRuleBundle:
        """The resolved Rule contract consumed by existing Policy/Query paths.

        ``ProductRuleV1`` is itself a subtype of ``ResolvedRuleBundle`` so
        this accessor does not copy, look up or weaken its semantic contract.
        It exists to make the product envelope explicit to consumers that
        distinguish the Rule asset from the resolved compiler input.
        """

        return self

    def asset_snapshot(self) -> dict[str, object]:
        """Return the sealed Rule descriptor and logical-identity binding."""
        return asset_snapshot_v1(self)


_FunctionScalarDomainV1: TypeAlias = Literal["string", "int", "float64", "bool", "time", "uuid"]


@dataclass(frozen=True)
class FunctionPortV1:
    """One named scalar port in a pure Product Function signature."""

    name: str
    scalar_domain: _FunctionScalarDomainV1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name.isidentifier()
            or self.name.startswith("_")
        ):
            raise ProductAuthoringError(
                "Function port name must be a public Python identifier",
                code="PRODUCT_FUNCTION_INVALID_PORT",
            )
        if self.scalar_domain not in {"string", "int", "float64", "bool", "time", "uuid"}:
            raise ProductAuthoringError(
                "Function port scalar domain is unsupported",
                code="PRODUCT_FUNCTION_INVALID_PORT",
            )


@dataclass(frozen=True)
class ProductFunctionV1:
    """Represent one sealed, deterministic scalar Product Function.

    The callable is an in-process implementation capability and is excluded
    from equality/repr.  Durable identity uses the explicit implementation
    digest plus the canonical typed signature.  Replay captures materialized
    calls and therefore never invokes this callable again.

    Attributes:
        id: Application-defined Function identifier.
        implementation: Trusted synchronous Python callable.
        inputs: Ordered scalar input ports.
        output: The single scalar output port.
        implementation_digest: Pinned implementation identity.
        version: Optional application-defined version.
        asset_meta: Human-facing descriptor or explicit absent state.

    Notes:
        This is not a Rule builtin, action tool, MCP tool, or sandbox. Product
        Policy is the only composition owner, and Function-to-Function calls
        are intentionally unsupported in the current profile.
    """

    id: str
    implementation: Callable[..., object] = field(repr=False, compare=False, hash=False)
    inputs: tuple[FunctionPortV1, ...]
    output: FunctionPortV1
    implementation_digest: str
    version: str | None = None
    asset_meta: AssetMetaStateV1 = ASSET_META_ABSENT_V1
    signature_digest: str = field(init=False)
    logical_identity_digest: str = field(init=False)
    asset_binding_digest: str = field(init=False)
    _implementation_capability_id: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ProductAuthoringError(
                "Function id must be a non-empty string", code="PRODUCT_FUNCTION_INVALID_ID"
            )
        if self.version is not None and (not isinstance(self.version, str) or not self.version):
            raise ProductAuthoringError(
                "Function version must be a non-empty string or None",
                code="PRODUCT_FUNCTION_INVALID_VERSION",
            )
        if not callable(self.implementation):
            raise ProductAuthoringError(
                "Function implementation must be callable",
                code="PRODUCT_FUNCTION_IMPLEMENTATION_REQUIRED",
            )
        if (
            not isinstance(self.inputs, tuple)
            or not self.inputs
            or not all(isinstance(item, FunctionPortV1) for item in self.inputs)
        ):
            raise ProductAuthoringError(
                "Function inputs must be a non-empty FunctionPortV1 tuple",
                code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
            )
        if len({item.name for item in self.inputs}) != len(self.inputs):
            raise ProductAuthoringError(
                "Function input names must be unique", code="PRODUCT_FUNCTION_INVALID_SIGNATURE"
            )
        if not isinstance(self.output, FunctionPortV1) or self.output.name in {
            item.name for item in self.inputs
        }:
            raise ProductAuthoringError(
                "Function output must have a distinct public name",
                code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
            )
        if not isinstance(
            self.implementation_digest, str
        ) or not self.implementation_digest.startswith("sha256:"):
            raise ProductAuthoringError(
                "Function implementation_digest must be a sha256 token",
                code="PRODUCT_FUNCTION_INVALID_IMPLEMENTATION_DIGEST",
            )
        meta = _normalize_asset_meta(self.asset_meta)
        signature = _token(
            PRODUCT_FUNCTION_SIGNATURE_FORMAT_V1,
            {
                "inputs": tuple((item.name, item.scalar_domain) for item in self.inputs),
                "output": (self.output.name, self.output.scalar_domain),
            },
        )
        logical = _token(
            PRODUCT_FUNCTION_IDENTITY_FORMAT_V1,
            {
                "id": self.id,
                "version": self.version,
                "signature_digest": signature,
                "implementation_digest": self.implementation_digest,
                "semantics": "pure_deterministic_total_v1",
            },
        )
        object.__setattr__(self, "asset_meta", meta)
        # This is deliberately an in-process freshness guard, not durable
        # identity.  Durable capture pins ``implementation_digest`` and replay
        # never receives the callable.  The object id only prevents a frozen
        # live asset from being re-blessed after its callable field is swapped.
        object.__setattr__(self, "_implementation_capability_id", id(self.implementation))
        object.__setattr__(self, "signature_digest", signature)
        object.__setattr__(self, "logical_identity_digest", logical)
        object.__setattr__(
            self,
            "asset_binding_digest",
            _asset_binding_digest(
                target_kind="function", logical_identity_digest=logical, meta=meta
            ),
        )

    @property
    def meta(self) -> AssetMetaStateV1:
        """Return the immutable Function asset descriptor state."""
        return self.asset_meta

    def asset_snapshot(self) -> dict[str, object]:
        """Return the sealed Function descriptor and identity binding."""
        return asset_snapshot_v1(self)


def _derived_implementation_digest(implementation: Callable[..., object]) -> str:
    try:
        source = inspect.getsource(implementation)
    except (OSError, TypeError):
        source = None
    code = getattr(implementation, "__code__", None)
    payload = {
        "module": getattr(implementation, "__module__", None),
        "qualname": getattr(implementation, "__qualname__", None),
        "source": source,
        "code": None if code is None else code.co_code.hex(),
        "constants": None if code is None else tuple(repr(item) for item in code.co_consts),
        "defaults": repr(getattr(implementation, "__defaults__", None)),
    }
    if payload["source"] is None and payload["code"] is None:
        raise ProductAuthoringError(
            "Function implementation needs an explicit implementation_digest",
            code="PRODUCT_FUNCTION_IMPLEMENTATION_DIGEST_REQUIRED",
        )
    return _token("product_function_python_implementation_v1", payload)


def _domain_from_annotation(value: object, *, label: str) -> _FunctionScalarDomainV1:
    mapping: dict[object, _FunctionScalarDomainV1] = {
        str: "string",
        int: "int",
        float: "float64",
        bool: "bool",
    }
    domain = mapping.get(value)
    if domain is None:
        raise ProductAuthoringError(
            f"{label} annotation is not a supported Function scalar",
            code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
        )
    return domain


class FunctionBuilder:
    """Build one graph-independent deterministic Product Function.

    Use the staged builder when asset metadata is assembled separately from
    the callable. ``FactGraph.build_function(...)`` is the equivalent direct
    spelling.

    Notes:
        Constructing the builder does not register a name, invoke user code,
        or write to a FactGraph ledger.
    """

    __slots__ = ("_id", "_version", "_meta")

    def __init__(
        self,
        id: str,
        *,
        version: str | None = None,
        meta: AssetMeta | None = None,
    ) -> None:
        self._id = id
        self._version = version
        self._meta = _normalize_asset_meta(meta)

    def build(
        self,
        implementation: Callable[..., object],
        *,
        inputs: Mapping[str, _FunctionScalarDomainV1] | None = None,
        output: _FunctionScalarDomainV1 | None = None,
        output_name: str = "result",
        implementation_digest: str | None = None,
    ) -> ProductFunctionV1:
        """Validate and seal the callable as a Product Function.

        Args:
            implementation: Pure synchronous callable with required positional
                scalar parameters.
            inputs: Optional explicit input domains in exact Python signature
                order. When omitted, domains are inferred from annotations.
            output: Optional explicit output domain. When omitted, the return
                annotation is used.
            output_name: Public Policy/Query name for the single output port.
            implementation_digest: Optional explicit ``sha256:`` identity for
                callables whose source/code cannot be inspected reliably.

        Returns:
            A sealed ``ProductFunctionV1`` ready for
            ``policy.use(function).as_(...)``.

        Raises:
            ProductAuthoringError: If the callable, signature, domains, output
                name, or implementation digest is invalid.

        Examples:
            >>> def decade(age: int) -> int:
            ...     return age // 10
            >>> function = fg.function_builder("age_decade").build(decade)

        Notes:
            Validation does not execute ``implementation``. The callable runs
            later during V2 pre-engine materialization and is never called by
            detached replay.
        """
        if not callable(implementation):
            raise ProductAuthoringError(
                "Function implementation must be callable",
                code="PRODUCT_FUNCTION_IMPLEMENTATION_REQUIRED",
            )
        try:
            signature = inspect.signature(implementation)
            hints = get_type_hints(implementation)
        except (TypeError, ValueError, NameError) as exc:
            raise ProductAuthoringError(
                f"Function signature cannot be inspected: {exc}",
                code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
            ) from exc
        if any(
            parameter.kind
            not in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            or parameter.default is not inspect.Parameter.empty
            for parameter in signature.parameters.values()
        ):
            raise ProductAuthoringError(
                "Function inputs must be required positional scalar parameters",
                code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
            )
        if inputs is None:
            input_ports = tuple(
                FunctionPortV1(
                    name,
                    _domain_from_annotation(hints.get(name), label=f"Function input {name}"),
                )
                for name in signature.parameters
            )
        else:
            if tuple(inputs) != tuple(signature.parameters):
                raise ProductAuthoringError(
                    "Function inputs must exactly follow the Python signature order",
                    code="PRODUCT_FUNCTION_INVALID_SIGNATURE",
                )
            input_ports = tuple(FunctionPortV1(name, domain) for name, domain in inputs.items())
        output_domain = (
            _domain_from_annotation(hints.get("return"), label="Function return")
            if output is None
            else output
        )
        return ProductFunctionV1(
            id=self._id,
            version=self._version,
            implementation=implementation,
            inputs=input_ports,
            output=FunctionPortV1(output_name, output_domain),
            implementation_digest=(
                _derived_implementation_digest(implementation)
                if implementation_digest is None
                else implementation_digest
            ),
            asset_meta=self._meta,
        )


def function_builder(
    id: str,
    *,
    version: str | None = None,
    meta: AssetMeta | None = None,
) -> FunctionBuilder:
    """Start staged Product Function construction.

    Args:
        id: Stable application-defined Function identifier.
        version: Optional application-defined version.
        meta: Optional human-facing asset descriptor.

    Returns:
        A ``FunctionBuilder``. No registration, execution, or ledger write
        occurs.

    Raises:
        ProductAuthoringError: If the asset id, version, or metadata is
            invalid.
    """
    return FunctionBuilder(id, version=version, meta=meta)


def build_function(
    *,
    id: str,
    implementation: Callable[..., object],
    inputs: Mapping[str, _FunctionScalarDomainV1] | None = None,
    output: _FunctionScalarDomainV1 | None = None,
    output_name: str = "result",
    implementation_digest: str | None = None,
    version: str | None = None,
    meta: AssetMeta | None = None,
) -> ProductFunctionV1:
    """Build a deterministic Product Function in one call.

    Args:
        id: Stable application-defined Function identifier.
        implementation: Pure synchronous Python callable.
        inputs: Optional explicit ordered input-domain mapping.
        output: Optional explicit scalar output domain.
        output_name: Public name of the single output port.
        implementation_digest: Optional explicit ``sha256:`` implementation
            identity.
        version: Optional application-defined version.
        meta: Optional human-facing asset descriptor.

    Returns:
        A sealed ``ProductFunctionV1``.

    Raises:
        ProductAuthoringError: If any asset or callable contract is invalid.

    Notes:
        This is the direct equivalent of
        ``function_builder(...).build(...)``. It does not register a tool,
        invoke the callable, or write the ledger.
    """
    return function_builder(id, version=version, meta=meta).build(
        implementation,
        inputs=inputs,
        output=output,
        output_name=output_name,
        implementation_digest=implementation_digest,
    )


def _function_relation_predicate_id(function: ProductFunctionV1, alias: str) -> str:
    suffix = sha256_hex(
        _canonical_json_bytes(
            {
                "function_digest": function.logical_identity_digest,
                "occurrence_alias": alias,
            }
        )
    )
    return f"__factgraph_function_v1:{suffix}"


def _function_port_predicate_id(relation_predicate_id: str, port_name: str) -> str:
    """Return one binary EDB predicate within a Function relation namespace."""

    return f"{relation_predicate_id}:{port_name}"


def _function_resolved_bundle(
    function: ProductFunctionV1,
    *,
    schema_digest: str,
    alias: str,
) -> ResolvedRuleBundle:
    relation_predicate_id = _function_relation_predicate_id(function, alias)
    call_key = Var("$__function_call_key")
    input_vars = tuple(Var(f"$__function_input_{index}") for index, _ in enumerate(function.inputs))
    output_var = Var("$__function_output")
    ordered_ports = (*function.inputs, function.output)
    ordered_vars = (*input_vars, output_var)
    rule = Rule(
        id=f"__factgraph_function_v1__{function.id}",
        version=function.version,
        when=tuple(
            PredAtom(_function_port_predicate_id(relation_predicate_id, port.name), [call_key, var])
            for port, var in zip(ordered_ports, ordered_vars, strict=True)
        ),
        ports={
            port.name: variable for port, variable in zip(ordered_ports, ordered_vars, strict=True)
        },
    )
    contract = ResolvedRuleContract(
        rule_id=rule.id,
        rule_version=rule.version,
        rule_content_digest=rule.content_digest,
        schema_digest=schema_digest,
        ports={
            port.name: SemanticRulePort(
                variable,
                FunctionValueEndpointV1(
                    function_digest=function.logical_identity_digest,
                    relation_predicate_id=_function_port_predicate_id(
                        relation_predicate_id, port.name
                    ),
                    port_name=port.name,
                    mode="output" if port is function.output else "input",
                    scalar_domain=port.scalar_domain,
                    position=index,
                ),
            )
            for index, (port, variable) in enumerate(
                zip(ordered_ports, ordered_vars, strict=True), start=1
            )
        },
    )
    return ResolvedRuleBundle(rule, contract)


@dataclass(frozen=True)
class FunctionInputBindingV1:
    """Bind one Product Function input port to a Rule occurrence address."""

    port_name: str
    source: SemanticPortAddress

    def __post_init__(self) -> None:
        if not isinstance(self.port_name, str) or not self.port_name:
            raise ProductAuthoringError(
                "Function input binding port must be non-empty",
                code="PRODUCT_FUNCTION_INVALID_BINDING",
            )
        if not isinstance(self.source, SemanticPortAddress):
            raise ProductAuthoringError(
                "Function input binding source must be a semantic address",
                code="PRODUCT_FUNCTION_INVALID_BINDING",
            )


@dataclass(frozen=True)
class FunctionOccurrenceTopologyV1:
    """Sealed Product Function occurrence and its Rule-port input edges."""

    alias: str
    function: ProductFunctionV1
    input_bindings: tuple[FunctionInputBindingV1, ...]
    relation_predicate_id: str
    topology_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias:
            raise ProductAuthoringError(
                "Function occurrence alias must be non-empty",
                code="PRODUCT_FUNCTION_INVALID_OCCURRENCE",
            )
        if not isinstance(self.function, ProductFunctionV1):
            raise ProductAuthoringError(
                "Function occurrence requires ProductFunctionV1",
                code="PRODUCT_FUNCTION_INVALID_OCCURRENCE",
            )
        if self.relation_predicate_id != _function_relation_predicate_id(self.function, self.alias):
            raise ProductAuthoringError(
                "Function occurrence relation predicate does not match the Function",
                code="PRODUCT_FUNCTION_INVALID_OCCURRENCE",
            )
        bindings = tuple(sorted(self.input_bindings, key=lambda item: item.port_name))
        if tuple(item.port_name for item in bindings) != tuple(
            sorted(port.name for port in self.function.inputs)
        ):
            raise ProductAuthoringError(
                "Function occurrence inputs must exactly cover the Function signature",
                code="PRODUCT_FUNCTION_INPUT_COVERAGE_MISMATCH",
            )
        source_aliases = {item.source.occurrence_alias for item in bindings}
        if len(source_aliases) != 1 or self.alias in source_aliases:
            raise ProductAuthoringError(
                "Function inputs must come from one Rule occurrence, never a Function occurrence",
                code="PRODUCT_FUNCTION_INPUT_SOURCE_UNSUPPORTED",
            )
        object.__setattr__(self, "input_bindings", bindings)
        object.__setattr__(
            self,
            "topology_digest",
            _token(
                PRODUCT_FUNCTION_TOPOLOGY_FORMAT_V1,
                {
                    "alias": self.alias,
                    "function_digest": self.function.logical_identity_digest,
                    "signature_digest": self.function.signature_digest,
                    "relation_predicate_id": self.relation_predicate_id,
                    "input_bindings": tuple(
                        (item.port_name, item.source.occurrence_alias, item.source.port_name)
                        for item in bindings
                    ),
                },
            ),
        )


class FunctionOccurrenceHandleV1(PolicyOccurrenceHandle):
    """Represent one owner-bound Product Function call site in a Policy."""

    __slots__ = ("function", "_input_bindings", "_function_occurrences")

    def __init__(
        self,
        base: PolicyOccurrenceHandle,
        function: ProductFunctionV1,
        function_occurrences: Mapping[str, "FunctionOccurrenceHandleV1"],
    ) -> None:
        super().__init__(base._owner, base._managed, base._schema_index)
        self.function = function
        self._input_bindings: dict[str, PolicyScalarPortHandle] = {}
        self._function_occurrences = function_occurrences

    def inputs(self, **sources: PolicyScalarPortHandle) -> "FunctionOccurrenceHandleV1":
        """Connect every Function input to direct scalar Rule ports.

        Args:
            **sources: Input-name to Rule scalar-port mapping. Names must cover
                the Function signature exactly, and all ports must come from
                one Rule occurrence in this Policy builder.

        Returns:
            This occurrence handle for fluent authoring.

        Raises:
            ProductAuthoringError: If coverage, domain, ownership, source
                occurrence, or topology constraints fail.

        Notes:
            Function outputs are directional and cannot be Query bindings or
            inputs to another Function in the current profile.
        """
        expected = {item.name: item for item in self.function.inputs}
        if set(sources) != set(expected):
            raise ProductAuthoringError(
                "Function inputs must exactly cover the declared signature",
                code="PRODUCT_FUNCTION_INPUT_COVERAGE_MISMATCH",
            )
        aliases: set[str] = set()
        for name, source in sources.items():
            if not isinstance(source, PolicyScalarPortHandle) or source._owner is not self._owner:
                raise ProductAuthoringError(
                    "Function inputs must use scalar ports from this Policy builder",
                    code="POLICY_CROSS_DRAFT_HANDLE",
                )
            if isinstance(source, PolicyFieldHandle):
                raise ProductAuthoringError(
                    "Function inputs currently require direct scalar Rule ports; expose the field as a Rule port first",
                    code="PRODUCT_FUNCTION_NAVIGATION_INPUT_UNSUPPORTED",
                )
            if source.scalar_domain != expected[name].scalar_domain:
                raise ProductAuthoringError(
                    f"Function input {name!r} has an incompatible scalar domain",
                    code="PRODUCT_FUNCTION_INPUT_DOMAIN_MISMATCH",
                )
            aliases.add(source.address.occurrence_alias)
        if len(aliases) != 1 or any(alias in self._function_occurrences for alias in aliases):
            raise ProductAuthoringError(
                "Function inputs must come from one Rule occurrence, never another Function",
                code="PRODUCT_FUNCTION_INPUT_SOURCE_UNSUPPORTED",
            )
        self._input_bindings = dict(sources)
        return self

    def topology(self) -> FunctionOccurrenceTopologyV1:
        """Return the validated topology captured for this Function occurrence."""
        return FunctionOccurrenceTopologyV1(
            alias=self.alias,
            function=self.function,
            input_bindings=tuple(
                FunctionInputBindingV1(name, handle.address)
                for name, handle in self._input_bindings.items()
            ),
            relation_predicate_id=_function_relation_predicate_id(self.function, self.alias),
        )


class _PendingPolicyUseV1:
    __slots__ = ("_builder", "_asset")

    def __init__(
        self, builder: "PolicyBuilder", asset: ResolvedRuleBundle | ProductFunctionV1
    ) -> None:
        self._builder = builder
        self._asset = asset

    def as_(self, alias: str) -> PolicyOccurrenceHandle:
        occurrence = self._builder.use(self._asset, as_=alias)
        assert isinstance(occurrence, PolicyOccurrenceHandle)
        return occurrence


def _canonical_probability(value: object) -> str:
    if type(value) is not str:
        raise ProductAuthoringError(
            "WeightedChoice probability must be a canonical decimal string, never float",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    if not value or len(value) > MAX_WEIGHTED_CHOICE_PROBABILITY_CHARS_V1:
        raise ProductAuthoringError(
            "WeightedChoice probability exceeds its bounded decimal codec",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    if not _CANONICAL_DECIMAL_RE.fullmatch(value):
        raise ProductAuthoringError(
            "WeightedChoice probability must be a finite non-exponent decimal string",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    if "." in value and value.endswith("0"):
        raise ProductAuthoringError(
            "WeightedChoice probability must not have trailing decimal zeroes",
            code="WEIGHTED_CHOICE_NONCANONICAL_PROBABILITY",
        )
    fractional = value.partition(".")[2]
    if len(fractional) > MAX_WEIGHTED_CHOICE_PROBABILITY_SCALE_V1:
        raise ProductAuthoringError(
            "WeightedChoice probability exceeds the supported decimal scale",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    try:
        decimal = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex already excludes this.
        raise ProductAuthoringError(
            "WeightedChoice probability is not a decimal",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        ) from exc
    if not (Decimal("0") < decimal <= Decimal("1")):
        raise ProductAuthoringError(
            "WeightedChoice probability must be greater than zero and at most one",
            code="WEIGHTED_CHOICE_INVALID_PROBABILITY",
        )
    return value


@dataclass(frozen=True)
class WeightedChoiceArmV1:
    """One semantic arm of an exclusive categorical choice."""

    arm_id: str
    probability: str
    condition_node_id: str
    # ``None`` is valid for a decoded/replayed topology.  The live builder
    # requires its private owner token before it will admit an arm into a new
    # Policy, so a decoded arm cannot be smuggled into a different authoring
    # session.
    _owner: object | None = field(default=None, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.arm_id, str)
            or len(self.arm_id) > MAX_WEIGHTED_CHOICE_ID_CHARS_V1
            or not _ARM_ID_RE.fullmatch(self.arm_id)
        ):
            raise ProductAuthoringError(
                "WeightedChoice arm id must be a bounded identifier",
                code="WEIGHTED_CHOICE_INVALID_ARM_ID",
            )
        object.__setattr__(self, "probability", _canonical_probability(self.probability))
        if not isinstance(self.condition_node_id, str) or not self.condition_node_id.startswith(
            "pn:"
        ):
            raise ProductAuthoringError(
                "WeightedChoice arm must name one structural Policy condition",
                code="WEIGHTED_CHOICE_INVALID_ARM_CONDITION",
            )


@dataclass(frozen=True)
class WeightedChoiceTopologyV1:
    """Sealed projection of intrinsic, non-deterministic Policy topology.

    ``skeleton_node_id`` names the canonical temporary ``PolicyAny`` shape
    derived from the intrinsic node for the controlled V2 compiler bridge. It
    is never public authored logic and never evidence that the arms mean
    ordinary OR.
    """

    choice_id: str
    selection_key: tuple[SemanticPortAddress, ...]
    arms: tuple[WeightedChoiceArmV1, ...]
    skeleton_node_id: str
    kind: Literal["exclusive"] = "exclusive"
    node_id: str = field(init=False)
    topology_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.choice_id, str)
            or len(self.choice_id) > MAX_WEIGHTED_CHOICE_ID_CHARS_V1
            or not _ARM_ID_RE.fullmatch(self.choice_id)
        ):
            raise ProductAuthoringError(
                "WeightedChoice id must be a bounded identifier",
                code="WEIGHTED_CHOICE_INVALID_ID",
            )
        if self.kind != "exclusive":
            raise ProductAuthoringError(
                "only WeightedChoice kind='exclusive' is implemented",
                code="WEIGHTED_CHOICE_KIND_UNSUPPORTED",
            )
        if (
            not isinstance(self.selection_key, tuple)
            or not self.selection_key
            or len(self.selection_key) > MAX_WEIGHTED_CHOICE_KEY_PORTS_V1
            or not all(isinstance(address, SemanticPortAddress) for address in self.selection_key)
        ):
            raise ProductAuthoringError(
                "WeightedChoice on= must be a bounded non-empty tuple of direct semantic ports",
                code="WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
            )
        if len(set(self.selection_key)) != len(self.selection_key):
            raise ProductAuthoringError(
                "WeightedChoice selection key cannot repeat a semantic port",
                code="WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
            )
        if (
            not isinstance(self.arms, tuple)
            or not self.arms
            or len(self.arms) > MAX_WEIGHTED_CHOICE_ARMS_V1
            or not all(isinstance(arm, WeightedChoiceArmV1) for arm in self.arms)
        ):
            raise ProductAuthoringError(
                "WeightedChoice choices must be a bounded non-empty tuple of arms",
                code="WEIGHTED_CHOICE_INVALID_ARMS",
            )
        ordered_arms = tuple(sorted(self.arms, key=lambda arm: arm.arm_id))
        if len({arm.arm_id for arm in ordered_arms}) != len(ordered_arms):
            raise ProductAuthoringError(
                "WeightedChoice arm ids must be unique", code="WEIGHTED_CHOICE_DUPLICATE_ARM_ID"
            )
        if len({arm.condition_node_id for arm in ordered_arms}) != len(ordered_arms):
            raise ProductAuthoringError(
                "WeightedChoice arms must have distinct structural conditions",
                code="WEIGHTED_CHOICE_DUPLICATE_ARM_CONDITION",
            )
        with localcontext() as context:
            context.prec = 128
            total = sum((Decimal(arm.probability) for arm in ordered_arms), Decimal("0"))
        if total != Decimal("1"):
            raise ProductAuthoringError(
                "exclusive WeightedChoice arm probabilities must sum exactly to 1",
                code="WEIGHTED_CHOICE_PROBABILITY_TOTAL",
            )
        if not isinstance(self.skeleton_node_id, str) or not self.skeleton_node_id.startswith(
            "pn:"
        ):
            raise ProductAuthoringError(
                "WeightedChoice skeleton_node_id must name a PolicyAny node",
                code="WEIGHTED_CHOICE_INVALID_SKELETON",
            )
        object.__setattr__(self, "arms", ordered_arms)
        payload = self.to_wire(include_digests=False)
        digest = _token(WEIGHTED_CHOICE_FORMAT_V1, payload)
        object.__setattr__(self, "topology_digest", digest)
        object.__setattr__(self, "node_id", f"wc:{sha256_hex(_canonical_json_bytes(payload))}")

    def to_wire(self, *, include_digests: bool = True) -> dict[str, object]:
        """Return the canonical WeightedChoice topology payload.

        Args:
            include_digests: Include the derived node and topology digests.

        Returns:
            A canonical mapping suitable for sealed Product V2 capture.
        """
        payload: dict[str, object] = {
            "format": WEIGHTED_CHOICE_FORMAT_V1,
            "choice_id": self.choice_id,
            "kind": self.kind,
            "selection_key": tuple(
                (address.occurrence_alias, address.port_name) for address in self.selection_key
            ),
            "arms": tuple(
                {
                    "arm_id": arm.arm_id,
                    "probability": arm.probability,
                    "condition_node_id": arm.condition_node_id,
                }
                for arm in self.arms
            ),
            "skeleton_node_id": self.skeleton_node_id,
        }
        if include_digests:
            payload["node_id"] = self.node_id
            payload["topology_digest"] = self.topology_digest
        return payload


class ProductPolicyNode:
    """A product-builder structural node that cannot leak into Q19 raw APIs."""

    __slots__ = ("_owner", "_raw")

    def __init__(self, owner: object, raw: PolicyNodeHandle) -> None:
        self._owner = owner
        self._raw = raw

    def __bool__(self) -> bool:
        raise ProductAuthoringError(
            "Policy symbolic values have no Python truth value; use builder.all(...) or builder.any(...)",
            code="POLICY_SYMBOLIC_BOOLEAN_UNSUPPORTED",
        )

    def __hash__(self) -> int:
        raise TypeError("Policy symbolic values cannot be used as hash keys")

    def __eq__(self, other: object) -> Any:
        raise ProductAuthoringError(
            "Policy structural nodes are symbolic; compose them with builder.all(...) or builder.any(...)",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )

    def __ne__(self, other: object) -> Any:
        raise ProductAuthoringError(
            "Policy structural nodes are symbolic; compose them with builder.all(...) or builder.any(...)",
            code="POLICY_SYMBOLIC_EQUALITY_UNSUPPORTED",
        )


class WeightedChoiceHandle(ProductPolicyNode):
    """A builder-time structural carrier plus its V2 topology projection."""

    __slots__ = ("topology",)

    def __init__(
        self,
        owner: object,
        raw: PolicyNodeHandle,
        topology: WeightedChoiceTopologyV1,
    ) -> None:
        super().__init__(owner, raw)
        self.topology = topology


@dataclass(frozen=True)
class ProductPolicyV1(AuthoredPolicyTargetV1):
    """A Q19 target with a sealed product envelope and derived choice capture."""

    asset_meta: AssetMetaStateV1 = ASSET_META_ABSENT_V1
    weighted_choices: tuple[WeightedChoiceTopologyV1, ...] = ()
    function_occurrences: tuple[FunctionOccurrenceTopologyV1, ...] = ()
    logical_identity_digest: str = field(init=False)
    asset_binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        AuthoredPolicyTargetV1.__post_init__(self)
        meta = _normalize_asset_meta(self.asset_meta)
        if not isinstance(self.weighted_choices, tuple) or not all(
            isinstance(choice, WeightedChoiceTopologyV1) for choice in self.weighted_choices
        ):
            raise ProductAuthoringError(
                "weighted_choices must be a tuple of WeightedChoiceTopologyV1",
                code="WEIGHTED_CHOICE_INVALID_TOPOLOGY",
            )
        choices = tuple(sorted(self.weighted_choices, key=lambda choice: choice.node_id))
        if len({choice.node_id for choice in choices}) != len(choices):
            raise ProductAuthoringError(
                "weighted choices must have unique node ids", code="WEIGHTED_CHOICE_DUPLICATE_NODE"
            )
        if len({choice.choice_id for choice in choices}) != len(choices):
            raise ProductAuthoringError(
                "weighted choice ids must be unique within one Policy",
                code="WEIGHTED_CHOICE_DUPLICATE_ID",
            )
        ast_choices = _weighted_choices_from_policy_ast(self.policy)
        if choices != ast_choices:
            raise ProductAuthoringError(
                "WeightedChoice sidecar must be the exact projection of the authored Policy AST",
                code="WEIGHTED_CHOICE_AST_SIDECAR_MISMATCH",
            )
        _assert_intrinsic_weighted_choice_nodes_current(self.policy)
        _validate_weighted_choices_against_target(self.policy, self.address_space, choices)
        if not isinstance(self.function_occurrences, tuple) or not all(
            isinstance(item, FunctionOccurrenceTopologyV1) for item in self.function_occurrences
        ):
            raise ProductAuthoringError(
                "function_occurrences must be FunctionOccurrenceTopologyV1 values",
                code="PRODUCT_FUNCTION_INVALID_TOPOLOGY",
            )
        functions = tuple(sorted(self.function_occurrences, key=lambda item: item.alias))
        if len({item.alias for item in functions}) != len(functions):
            raise ProductAuthoringError(
                "Function occurrence aliases must be unique",
                code="PRODUCT_FUNCTION_INVALID_TOPOLOGY",
            )
        _validate_function_occurrences_against_target(self.policy, self.address_space, functions)
        if choices and functions:
            raise ProductAuthoringError(
                "WeightedChoice and Function occurrences cannot share one first-slice Policy",
                code="PRODUCT_FUNCTION_WEIGHTED_CHOICE_UNSUPPORTED",
            )
        _validate_product_policy_execution_marker(self.policy, choices, functions)
        logical_identity_digest = _policy_logical_identity(self, choices, functions)
        object.__setattr__(self, "asset_meta", meta)
        object.__setattr__(self, "weighted_choices", choices)
        object.__setattr__(self, "function_occurrences", functions)
        object.__setattr__(self, "logical_identity_digest", logical_identity_digest)
        object.__setattr__(
            self,
            "asset_binding_digest",
            _asset_binding_digest(
                target_kind="policy", logical_identity_digest=logical_identity_digest, meta=meta
            ),
        )

    @property
    def meta(self) -> AssetMetaStateV1:
        """Return the immutable Policy asset descriptor state."""
        return self.asset_meta

    @property
    def requires_v2_profile(self) -> bool:
        """Return whether this Policy contains Product V2-only topology."""
        return bool(self.weighted_choices or self.function_occurrences)

    def asset_snapshot(self) -> dict[str, object]:
        """Return the sealed Policy descriptor and logical-identity binding."""
        return asset_snapshot_v1(self)


def _function_markers_from_policy_ast(
    policy: Policy,
) -> tuple[PolicyFunctionOccurrenceV1, ...]:
    return tuple(
        sorted(
            (
                node
                for node in _policy_nodes(policy.when)
                if isinstance(node, PolicyFunctionOccurrenceV1)
            ),
            key=lambda item: item.alias,
        )
    )


def _validate_function_occurrences_against_target(
    policy: Policy,
    address_space: SemanticAddressSpace,
    functions: tuple[FunctionOccurrenceTopologyV1, ...],
) -> None:
    markers = _function_markers_from_policy_ast(policy)
    if tuple(item.alias for item in markers) != tuple(item.alias for item in functions):
        raise ProductAuthoringError(
            "Function sidecar must exactly cover intrinsic Policy Function markers",
            code="PRODUCT_FUNCTION_AST_SIDECAR_MISMATCH",
        )
    for marker, topology in zip(markers, functions, strict=True):
        expected_bindings = tuple((item.port_name, item.source) for item in topology.input_bindings)
        if (
            marker.function_digest != topology.function.logical_identity_digest
            or marker.signature_digest != topology.function.signature_digest
            or marker.relation_predicate_id != topology.relation_predicate_id
            or marker.input_bindings != expected_bindings
        ):
            raise ProductAuthoringError(
                "intrinsic Policy Function marker does not match its sealed sidecar",
                code="PRODUCT_FUNCTION_AST_SIDECAR_MISMATCH",
            )
        try:
            managed = next(
                item
                for item in address_space.occurrences
                if item.occurrence.alias == topology.alias
            )
        except StopIteration as exc:
            raise ProductAuthoringError(
                "Function occurrence is absent from the semantic address space",
                code="PRODUCT_FUNCTION_ADDRESS_SPACE_MISMATCH",
            ) from exc
        for port in (*topology.function.inputs, topology.function.output):
            semantic = managed.contract.ports.get(port.name)
            if not isinstance(getattr(semantic, "endpoint", None), FunctionValueEndpointV1):
                raise ProductAuthoringError(
                    "Function occurrence semantic ports do not match the Function signature",
                    code="PRODUCT_FUNCTION_ADDRESS_SPACE_MISMATCH",
                )


def _weighted_choices_from_policy_ast(policy: Policy) -> tuple[WeightedChoiceTopologyV1, ...]:
    """Project intrinsic choice semantics into the V2 replay/lowering sidecar.

    The public AST is the authority.  ``WeightedChoiceTopologyV1`` remains a
    convenient detached capture DTO for the runner, but it is never accepted
    as an independent source capable of erasing or changing the AST's
    categorical semantics.
    """

    if not isinstance(policy, Policy):
        raise ProductAuthoringError(
            "WeightedChoice AST projection requires Policy",
            code="WEIGHTED_CHOICE_AST_INVALID",
        )
    projected: list[WeightedChoiceTopologyV1] = []
    for node in _policy_nodes(policy.when):
        if not isinstance(node, PolicyWeightedChoice):
            continue
        try:
            projected.append(
                WeightedChoiceTopologyV1(
                    choice_id=node.choice_id,
                    selection_key=node.selection_key,
                    arms=tuple(
                        WeightedChoiceArmV1(
                            arm_id=arm.arm_id,
                            probability=arm.probability,
                            condition_node_id=arm.condition_node_id,
                        )
                        for arm in node.arms
                    ),
                    skeleton_node_id=PolicyAny(node.children).node_id,
                    kind=node.kind,
                )
            )
        except Exception as exc:
            raise ProductAuthoringError(
                "intrinsic WeightedChoice cannot be projected into its V2 topology",
                code="WEIGHTED_CHOICE_AST_INVALID",
            ) from exc
    choices = tuple(sorted(projected, key=lambda choice: choice.node_id))
    if len({choice.choice_id for choice in choices}) != len(choices):
        raise ProductAuthoringError(
            "authored Policy has duplicate WeightedChoice ids",
            code="WEIGHTED_CHOICE_DUPLICATE_ID",
        )
    if len({choice.node_id for choice in choices}) != len(choices):
        raise ProductAuthoringError(
            "authored Policy has duplicate WeightedChoice topology nodes",
            code="WEIGHTED_CHOICE_DUPLICATE_NODE",
        )
    return choices


def _assert_intrinsic_weighted_choice_nodes_current(policy: Policy) -> None:
    """Reject mutable-object tampering with an intrinsic choice node's seal."""

    for node in _policy_nodes(policy.when):
        if not isinstance(node, PolicyWeightedChoice):
            continue
        try:
            rebuilt = PolicyWeightedChoice(
                choice_id=node.choice_id,
                selection_key=node.selection_key,
                arms=tuple(
                    PolicyWeightedChoiceArm(
                        arm_id=arm.arm_id,
                        probability=arm.probability,
                        condition=arm.condition,
                    )
                    for arm in node.arms
                ),
                kind=node.kind,
            )
        except Exception as exc:
            raise ProductAuthoringError(
                "intrinsic WeightedChoice no longer satisfies its canonical shape",
                code="WEIGHTED_CHOICE_AST_INVALID",
            ) from exc
        if rebuilt != node or rebuilt.node_id != node.node_id:
            raise ProductAuthoringError(
                "intrinsic WeightedChoice node seal is stale",
                code="WEIGHTED_CHOICE_AST_STALE",
            )


def _embed_weighted_choices_in_policy_ast(
    policy: Policy,
    choices: tuple[WeightedChoiceTopologyV1, ...],
) -> Policy:
    """Replace builder-only ``PolicyAny`` skeletons with intrinsic choice AST.

    Q19's draft builder owns the existing handle/ownership mechanics and can
    only create deterministic nodes.  Product authoring therefore makes this
    one immutable post-build conversion before publishing a ProductPolicy.
    The input skeleton never escapes as the public authored AST.
    """

    if not choices:
        return policy
    by_skeleton = {choice.skeleton_node_id: choice for choice in choices}
    if len(by_skeleton) != len(choices):
        raise ProductAuthoringError(
            "WeightedChoice skeleton ids must be unique",
            code="WEIGHTED_CHOICE_SKELETON_MISMATCH",
        )

    def transform_node(node: PolicyNode) -> PolicyNode:
        if isinstance(node, (PolicyUnify, PolicyCompare, PolicyOccurrence)):
            return node
        if isinstance(node, PolicyFunctionOccurrenceV1):
            raise ProductAuthoringError(
                "WeightedChoice embedding cannot consume an intrinsic Function node",
                code="WEIGHTED_CHOICE_AST_INVALID",
            )
        if isinstance(node, PolicyWeightedChoice):
            raise ProductAuthoringError(
                "builder cannot embed an already intrinsic WeightedChoice node",
                code="WEIGHTED_CHOICE_AST_INVALID",
            )
        if isinstance(node, PolicyAny):
            choice = by_skeleton.get(node.node_id)
            if choice is not None:
                by_condition = {child.node_id: child for child in node.children}
                try:
                    arms = tuple(
                        PolicyWeightedChoiceArm(
                            arm_id=arm.arm_id,
                            probability=arm.probability,
                            condition=by_condition[arm.condition_node_id],
                        )
                        for arm in choice.arms
                    )
                except KeyError as exc:
                    raise ProductAuthoringError(
                        "WeightedChoice arm is absent from its builder skeleton",
                        code="WEIGHTED_CHOICE_SKELETON_MISMATCH",
                    ) from exc
                return PolicyWeightedChoice(
                    choice_id=choice.choice_id,
                    selection_key=choice.selection_key,
                    arms=arms,
                    kind=choice.kind,
                )
            children: list[PolicyOccurrence | PolicyAll | PolicyAny | PolicyWeightedChoice] = []
            for child in node.children:
                transformed = transform_node(child)
                if not isinstance(
                    transformed, (PolicyOccurrence, PolicyAll, PolicyAny, PolicyWeightedChoice)
                ):
                    raise ProductAuthoringError(
                        "WeightedChoice AST conversion produced a non-structural ANY child",
                        code="WEIGHTED_CHOICE_AST_INVALID",
                    )
                children.append(transformed)
            return PolicyAny(tuple(children))
        if isinstance(node, PolicyAll):
            return PolicyAll(tuple(transform_node(child) for child in node.children))
        raise ProductAuthoringError(
            "WeightedChoice AST conversion received an unsupported Policy node",
            code="WEIGHTED_CHOICE_AST_INVALID",
        )

    root = transform_node(policy.when)
    if not isinstance(root, (PolicyOccurrence, PolicyAll, PolicyAny, PolicyWeightedChoice)):
        raise ProductAuthoringError(
            "WeightedChoice AST conversion produced an invalid Policy root",
            code="WEIGHTED_CHOICE_AST_INVALID",
        )
    embedded = Policy(policy.id, root, policy.version)
    if _weighted_choices_from_policy_ast(embedded) != choices:
        raise ProductAuthoringError(
            "WeightedChoice AST conversion did not preserve sidecar topology",
            code="WEIGHTED_CHOICE_AST_SIDECAR_MISMATCH",
        )
    return embedded


def _embed_function_occurrences_in_policy_ast(
    policy: Policy,
    functions: tuple[FunctionOccurrenceTopologyV1, ...],
) -> Policy:
    """Replace synthetic compiler occurrences with intrinsic V2 markers."""

    if not functions:
        return policy
    by_alias = {item.alias: item for item in functions}

    def transform(node: PolicyNode) -> PolicyNode:
        if isinstance(node, PolicyOccurrence):
            topology = by_alias.get(node.alias)
            if topology is None:
                return node
            return PolicyFunctionOccurrenceV1(
                alias=topology.alias,
                function_digest=topology.function.logical_identity_digest,
                relation_predicate_id=topology.relation_predicate_id,
                signature_digest=topology.function.signature_digest,
                input_bindings=tuple(
                    (item.port_name, item.source) for item in topology.input_bindings
                ),
            )
        if isinstance(node, (PolicyUnify, PolicyCompare, PolicyFunctionOccurrenceV1)):
            return node
        if isinstance(node, PolicyWeightedChoice):
            raise ProductAuthoringError(
                "Function and WeightedChoice cannot share one first-slice Policy",
                code="PRODUCT_FUNCTION_WEIGHTED_CHOICE_UNSUPPORTED",
            )
        children = tuple(transform(child) for child in node.children)
        if isinstance(node, PolicyAny):
            if not all(
                isinstance(
                    child,
                    (
                        PolicyOccurrence,
                        PolicyFunctionOccurrenceV1,
                        PolicyAll,
                        PolicyAny,
                    ),
                )
                for child in children
            ):
                raise ProductAuthoringError(
                    "Function AST conversion produced an invalid Any child",
                    code="PRODUCT_FUNCTION_AST_INVALID",
                )
            return PolicyAny(children)  # type: ignore[arg-type]
        return PolicyAll(children)

    root = transform(policy.when)
    if not isinstance(
        root,
        (PolicyOccurrence, PolicyFunctionOccurrenceV1, PolicyAll, PolicyAny),
    ):
        raise ProductAuthoringError(
            "Function AST conversion produced an invalid Policy root",
            code="PRODUCT_FUNCTION_AST_INVALID",
        )
    return Policy(policy.id, root, policy.version)


def _policy_nodes(node: PolicyNode) -> tuple[PolicyNode, ...]:
    if isinstance(node, (PolicyAll, PolicyAny, PolicyWeightedChoice)):
        return (node, *(nested for child in node.children for nested in _policy_nodes(child)))
    return (node,)


def _policy_branch_aliases(node: PolicyNode) -> tuple[frozenset[str], ...]:
    from factgraph.application.protocol.policy import PolicyCompare, PolicyOccurrence, PolicyUnify

    if isinstance(node, (PolicyOccurrence, PolicyFunctionOccurrenceV1)):
        return (frozenset((node.alias,)),)
    if isinstance(node, (PolicyUnify, PolicyCompare)):
        return (frozenset(),)
    if isinstance(node, (PolicyAny, PolicyWeightedChoice)):
        result: list[frozenset[str]] = []
        for child in node.children:
            result.extend(_policy_branch_aliases(child))
        return tuple(result)
    # PolicyAll joins every structural child.  Constraints contribute no
    # occurrence aliases and therefore naturally leave branch totality intact.
    assert isinstance(node, PolicyAll)
    partial: tuple[frozenset[str], ...] = (frozenset(),)
    for all_child in node.children:
        child_branches = _policy_branch_aliases(all_child)
        partial = tuple(left | right for left in partial for right in child_branches)
    return partial


def _validate_product_policy_execution_marker(
    policy: Policy,
    choices: tuple[WeightedChoiceTopologyV1, ...],
    functions: tuple[FunctionOccurrenceTopologyV1, ...] = (),
) -> None:
    """Verify the derived choice capture agrees with the public intrinsic AST.

    ``PolicyWeightedChoice`` itself is the durable V2-only boundary and
    survives ordinary Policy rewrapping. ``PolicyV2Only`` is a defense-in-
    depth marker on the exact product carrier. Ordinary product Policies
    retain plain :class:`Policy` values and preserve V0/V1 behavior.
    """

    ast_choices = _weighted_choices_from_policy_ast(policy)
    if choices != ast_choices:
        raise ProductAuthoringError(
            "WeightedChoice sidecar does not match the authored Policy AST",
            code="WEIGHTED_CHOICE_AST_SIDECAR_MISMATCH",
        )
    if not choices and not functions and isinstance(policy, PolicyV2Only):
        raise ProductAuthoringError(
            "V2-only Policy marker requires WeightedChoice or Function topology",
            code="WEIGHTED_CHOICE_V2_MARKER_UNEXPECTED",
        )


def _validate_weighted_choices_against_target(
    policy: Policy,
    address_space: SemanticAddressSpace,
    choices: tuple[WeightedChoiceTopologyV1, ...],
) -> None:
    if not choices:
        return
    all_nodes = _policy_nodes(policy.when)
    by_id = {node.node_id: node for node in all_nodes}
    if len(by_id) != len(all_nodes):  # Q19 should already make this impossible.
        raise ProductAuthoringError(
            "Policy has duplicate structural nodes", code="WEIGHTED_CHOICE_POLICY_TOPOLOGY_INVALID"
        )
    complete_branches = _policy_branch_aliases(policy.when)
    for choice in choices:
        carrier = next(
            (
                node
                for node in all_nodes
                if isinstance(node, PolicyWeightedChoice) and node.choice_id == choice.choice_id
            ),
            None,
        )
        if not isinstance(carrier, PolicyWeightedChoice):
            raise ProductAuthoringError(
                "WeightedChoice sidecar is not attached to an intrinsic Policy node",
                code="WEIGHTED_CHOICE_SKELETON_MISMATCH",
            )
        skeleton = PolicyAny(carrier.children)
        if skeleton.node_id != choice.skeleton_node_id:
            raise ProductAuthoringError(
                "WeightedChoice sidecar skeleton no longer matches its intrinsic node",
                code="WEIGHTED_CHOICE_SKELETON_MISMATCH",
            )
        if {child.node_id for child in carrier.children} != {
            arm.condition_node_id for arm in choice.arms
        }:
            raise ProductAuthoringError(
                "WeightedChoice arms do not exactly match their Policy skeleton",
                code="WEIGHTED_CHOICE_SKELETON_MISMATCH",
            )
        for address in choice.selection_key:
            try:
                address_space.resolve(address)
            except Exception as exc:
                raise ProductAuthoringError(
                    "WeightedChoice selection key does not resolve in this Policy",
                    code="WEIGHTED_CHOICE_UNRESOLVED_SELECTION_KEY",
                ) from exc
            if any(address.occurrence_alias not in branch for branch in complete_branches):
                raise ProductAuthoringError(
                    "WeightedChoice selection key must be branch-total in every arm",
                    code="WEIGHTED_CHOICE_PARTIAL_SELECTION_KEY",
                )


def _assert_weighted_choice_topology_current_v1(choice: WeightedChoiceTopologyV1) -> None:
    """Recompute a sidecar's full canonical seal from its live fields.

    Frozen dataclasses are a convenience, not an integrity boundary: capture
    and replay code must assume that a decoded/in-process object might have
    been altered with ``object.__setattr__``.  A Policy's logical identity only
    carries each choice's ``node_id``, so accepting a stale node/digest here
    would let an altered arm, key, or skeleton retain the old product binding.
    """

    if not isinstance(choice, WeightedChoiceTopologyV1):
        raise ProductAuthoringError(
            "weighted choice topology has invalid runtime shape",
            code="WEIGHTED_CHOICE_INVALID_TOPOLOGY",
        )
    try:
        recomputed = WeightedChoiceTopologyV1(
            choice_id=choice.choice_id,
            selection_key=choice.selection_key,
            arms=choice.arms,
            skeleton_node_id=choice.skeleton_node_id,
            kind=choice.kind,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProductAuthoringError(
            "weighted choice topology no longer satisfies its canonical shape",
            code="WEIGHTED_CHOICE_TOPOLOGY_INVALID",
        ) from exc
    try:
        arms_match = choice.arms == recomputed.arms
        node_id_matches = choice.node_id == recomputed.node_id
        digest_matches = choice.topology_digest == recomputed.topology_digest
    except AttributeError as exc:
        raise ProductAuthoringError(
            "weighted choice topology is missing a sealed field",
            code="WEIGHTED_CHOICE_TOPOLOGY_INVALID",
        ) from exc
    if not arms_match:
        raise ProductAuthoringError(
            "weighted choice arms are no longer in canonical order",
            code="WEIGHTED_CHOICE_TOPOLOGY_NONCANONICAL",
        )
    if not node_id_matches or not digest_matches:
        raise ProductAuthoringError(
            "weighted choice topology digest/node_id does not match its current fields",
            code="WEIGHTED_CHOICE_TOPOLOGY_DIGEST_MISMATCH",
        )


def asset_snapshot_v1(
    target: ProductRuleV1 | ProductPolicyV1 | ProductFunctionV1,
) -> dict[str, object]:
    """Return a side-specific descriptor/binding snapshot for V2 capture.

    Args:
        target: Sealed Product Rule, Policy, or Function asset.

    Returns:
        Canonical logical identity, descriptor, and association digests.

    Raises:
        ProductAuthoringError: If the target or one of its seals is stale.
    """

    if not isinstance(target, (ProductRuleV1, ProductPolicyV1, ProductFunctionV1)):
        raise ProductAuthoringError(
            "asset snapshot requires ProductRuleV1 or ProductPolicyV1",
            code="ASSET_META_UNSUPPORTED_TARGET",
        )
    assert_asset_binding_current_v1(target)
    return {
        "logical_identity_digest": target.logical_identity_digest,
        "asset_binding_digest": target.asset_binding_digest,
        "asset_meta": target.asset_meta.to_wire(),
        "descriptor_digest": target.asset_meta.descriptor_digest,
    }


def assert_asset_binding_current_v1(
    target: ProductRuleV1 | ProductPolicyV1 | ProductFunctionV1,
) -> None:
    """Fail closed if a descriptor/target association was structurally spliced.

    Product wrappers are frozen in normal Python use, but V2 capture/replay
    treats all in-memory input as untrusted enough to recompute this seal.  In
    particular, swapping a complete descriptor snapshot from target B onto A
    without recomputing A's association cannot pass this check.

    Args:
        target: Product Rule, Policy, or Function to verify.

    Raises:
        ProductAuthoringError: If any logical, topology, implementation, or
            descriptor association seal is stale.
    """

    if not isinstance(target, (ProductRuleV1, ProductPolicyV1, ProductFunctionV1)):
        raise ProductAuthoringError(
            "asset binding requires ProductRuleV1 or ProductPolicyV1",
            code="ASSET_META_UNSUPPORTED_TARGET",
        )
    meta = _normalize_asset_meta(target.asset_meta)
    if isinstance(meta, AssetMeta):
        expected_descriptor = _token(ASSET_META_FORMAT_V1, meta.to_wire())
        if meta.descriptor_digest != expected_descriptor:
            raise ProductAuthoringError(
                "AssetMeta descriptor digest does not match its descriptor",
                code="ASSET_DESCRIPTOR_DIGEST_MISMATCH",
            )
    if isinstance(target, ProductFunctionV1):
        fresh = ProductFunctionV1(
            id=target.id,
            version=target.version,
            implementation=target.implementation,
            inputs=target.inputs,
            output=target.output,
            implementation_digest=target.implementation_digest,
            asset_meta=meta,
        )
        expected_identity = fresh.logical_identity_digest
        expected_binding = fresh.asset_binding_digest
        if (
            target.signature_digest != fresh.signature_digest
            or target.inputs != fresh.inputs
            or target.output != fresh.output
            or target._implementation_capability_id != fresh._implementation_capability_id
        ):
            raise ProductAuthoringError(
                "Function signature or live implementation capability seal is stale",
                code="PRODUCT_FUNCTION_SIGNATURE_STALE",
            )
    elif isinstance(target, ProductRuleV1):
        ResolvedRuleBundle.__post_init__(target)
        expected_identity = _rule_logical_identity(target)
        expected_binding = _asset_binding_digest(
            target_kind="rule", logical_identity_digest=expected_identity, meta=meta
        )
    else:
        AuthoredPolicyTargetV1.__post_init__(target)
        choices = target.weighted_choices
        if not isinstance(choices, tuple) or not all(
            isinstance(choice, WeightedChoiceTopologyV1) for choice in choices
        ):
            raise ProductAuthoringError(
                "weighted choice topology has invalid runtime shape",
                code="WEIGHTED_CHOICE_INVALID_TOPOLOGY",
            )
        for choice in choices:
            _assert_weighted_choice_topology_current_v1(choice)
        canonical_choices = tuple(sorted(choices, key=lambda choice: choice.node_id))
        if canonical_choices != choices or len({choice.node_id for choice in choices}) != len(
            choices
        ):
            raise ProductAuthoringError(
                "weighted choice topology is not canonical", code="WEIGHTED_CHOICE_INVALID_TOPOLOGY"
            )
        if choices != _weighted_choices_from_policy_ast(target.policy):
            raise ProductAuthoringError(
                "WeightedChoice sidecar does not match the current authored Policy AST",
                code="WEIGHTED_CHOICE_AST_SIDECAR_MISMATCH",
            )
        _assert_intrinsic_weighted_choice_nodes_current(target.policy)
        functions = target.function_occurrences
        if not isinstance(functions, tuple) or not all(
            isinstance(item, FunctionOccurrenceTopologyV1) for item in functions
        ):
            raise ProductAuthoringError(
                "Function topology has invalid runtime shape",
                code="PRODUCT_FUNCTION_INVALID_TOPOLOGY",
            )
        for item in functions:
            assert_asset_binding_current_v1(item.function)
            fresh_topology = FunctionOccurrenceTopologyV1(
                alias=item.alias,
                function=item.function,
                input_bindings=item.input_bindings,
                relation_predicate_id=item.relation_predicate_id,
            )
            if fresh_topology.topology_digest != item.topology_digest:
                raise ProductAuthoringError(
                    "Function occurrence topology seal is stale",
                    code="PRODUCT_FUNCTION_TOPOLOGY_STALE",
                )
        _validate_function_occurrences_against_target(
            target.policy, target.address_space, functions
        )
        _validate_product_policy_execution_marker(target.policy, choices, functions)
        _validate_weighted_choices_against_target(target.policy, target.address_space, choices)
        expected_identity = _policy_logical_identity(target, choices, functions)
        expected_binding = _asset_binding_digest(
            target_kind="policy", logical_identity_digest=expected_identity, meta=meta
        )
    if target.logical_identity_digest != expected_identity:
        raise ProductAuthoringError(
            "product target logical identity digest does not match its target",
            code="PRODUCT_TARGET_IDENTITY_MISMATCH",
        )
    if target.asset_binding_digest != expected_binding:
        raise ProductAuthoringError(
            "asset binding digest does not match target and descriptor",
            code="ASSET_BINDING_DIGEST_MISMATCH",
        )


def _build_raw_rule(
    *,
    id: str,
    version: str | None,
    when: Sequence[Any],
    ports: Mapping[str, Any],
    repr: str | None,
) -> Rule:
    # Advanced callers may pass the established application AST directly.  The
    # ordinary SDK DSL body continues through its existing bridge unchanged.
    if (
        isinstance(when, (tuple, list))
        and when
        and all(isinstance(value, Var) for value in ports.values())
    ):
        try:
            return Rule(id=id, version=version, repr=repr, when=tuple(when), ports=ports)
        except (TypeError, ValueError) as exc:
            raise ProductAuthoringError(
                f"Rule body rejected: {exc}", code="PRODUCT_RULE_INVALID_BODY"
            ) from exc
    try:
        return build_application_rule(
            id=id,
            version=version,
            repr=repr,
            when=list(when),
            ports=ports,
        )
    except (TypeError, ValueError) as exc:
        raise ProductAuthoringError(
            f"Rule body rejected: {exc}", code="PRODUCT_RULE_INVALID_BODY"
        ) from exc


def _resolve_semantic_ports(
    *,
    rule: Rule,
    semantic_ports: Mapping[str, SemanticEndpoint | SemanticRulePort | type[Entity] | Field],
) -> dict[str, SemanticRulePort]:
    if not isinstance(semantic_ports, Mapping) or not semantic_ports:
        raise ProductAuthoringError(
            "semantic_ports must be a complete non-empty mapping",
            code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
        )
    resolved: dict[str, SemanticRulePort] = {}
    for name, value in semantic_ports.items():
        if not isinstance(name, str) or not name:
            raise ProductAuthoringError(
                "semantic_ports keys must be non-empty strings",
                code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
            )
        if name not in rule.ports:
            raise ProductAuthoringError(
                f"semantic_ports contains unknown Rule port {name!r}",
                code="PRODUCT_RULE_SEMANTIC_PORT_COVERAGE",
            )
        if isinstance(value, SemanticRulePort):
            if value.var != rule.ports[name]:
                raise ProductAuthoringError(
                    f"semantic port {name!r} must use the Rule's resolved variable",
                    code="PRODUCT_RULE_SEMANTIC_PORT_VAR_MISMATCH",
                )
            resolved[name] = value
        elif isinstance(value, (EntityIdentityEndpoint, FieldEndpoint)):
            resolved[name] = SemanticRulePort(rule.ports[name], value)
        else:
            endpoint = _semantic_endpoint_from_sdk_descriptor(value)
            if endpoint is None:
                raise ProductAuthoringError(
                    f"semantic port {name!r} must be an SDK Entity class, Field descriptor, "
                    "endpoint, or SemanticRulePort",
                    code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
                )
            resolved[name] = SemanticRulePort(rule.ports[name], endpoint)
    if set(resolved) != set(rule.ports):
        raise ProductAuthoringError(
            "semantic_ports must exactly cover Rule ports",
            code="PRODUCT_RULE_SEMANTIC_PORT_COVERAGE",
        )
    return resolved


def _semantic_endpoint_from_sdk_descriptor(value: object) -> SemanticEndpoint | None:
    """Lower the public schema descriptors accepted by product Rule authoring.

    ``Entity`` means the complete entity-identity endpoint; a bound ``Field``
    means its scalar field endpoint.  The following rule-contract resolution
    still verifies the endpoint against the exact graph schema and witnesses
    it in the Rule body, so this convenience form never weakens admission.
    """

    if isinstance(value, type) and issubclass(value, Entity):
        return entity_identity(_sdk_entity_type_name(value))
    if isinstance(value, Field):
        try:
            owner = value.sdk_owner_cls
        except Exception as exc:
            raise ProductAuthoringError(
                "semantic Field descriptor must be bound to an SDK Entity class",
                code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
            ) from exc
        if not isinstance(owner, type) or not issubclass(owner, Entity):
            raise ProductAuthoringError(
                "semantic Field descriptor must belong to an SDK Entity class",
                code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
            )
        return field_endpoint(_sdk_entity_type_name(owner), value.sdk_attr_name)
    return None


def _sdk_entity_type_name(entity_cls: type[Entity]) -> str:
    """Read the canonical entity name from a bound public schema declaration."""

    try:
        spec = entity_cls.sdk_entity_spec()
    except Exception as exc:
        raise ProductAuthoringError(
            "semantic Entity class must be a compiled SDK Entity declaration",
            code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
        ) from exc
    entity_type = spec.get("entity_type") if isinstance(spec, dict) else None
    if not isinstance(entity_type, str) or not entity_type:
        raise ProductAuthoringError(
            "semantic Entity class has no canonical entity type",
            code="PRODUCT_RULE_INVALID_SEMANTIC_PORTS",
        )
    return entity_type


class RuleBuilder:
    """Resolve one authored SDK Rule against one exact FactGraph schema.

    The staged builder owns asset identity/metadata; :meth:`build` supplies
    the logical body, public ports, and semantic-port contract.

    Notes:
        Building returns an immutable resolved asset. It does not register the
        Rule by id, execute it, or write to the ledger.
    """

    __slots__ = ("_graph", "_id", "_version", "_meta")

    def __init__(
        self,
        graph: "SDKStore",
        id: str,
        *,
        version: str | None = None,
        meta: AssetMeta | None = None,
    ) -> None:
        if not isinstance(id, str) or not id:
            raise ProductAuthoringError(
                "Rule id must be a non-empty string", code="PRODUCT_RULE_INVALID_ID"
            )
        if version is not None and (not isinstance(version, str) or not version):
            raise ProductAuthoringError(
                "Rule version must be a non-empty string or None",
                code="PRODUCT_RULE_INVALID_VERSION",
            )
        self._graph = graph
        self._id = id
        self._version = version
        self._meta = _normalize_asset_meta(meta)

    @property
    def id(self) -> str:
        """Return the Product Rule identifier owned by this builder."""
        return self._id

    @property
    def version(self) -> str | None:
        """Return the optional Product Rule version."""
        return self._version

    @property
    def meta(self) -> AssetMetaStateV1:
        """Return the immutable descriptor that will be bound to the Rule."""
        return self._meta

    def build(
        self,
        *,
        when: Sequence[Any],
        ports: Mapping[str, Any],
        semantic_ports: Mapping[str, SemanticEndpoint | SemanticRulePort | type[Entity] | Field],
        repr: str | None = None,
    ) -> ProductRuleV1:
        """Build and fully resolve a Product Rule.

        Product code can declare ``semantic_ports`` entirely with public SDK
        schema values: use an ``Entity`` class for its complete identity and a
        bound ``Field`` descriptor for one scalar field, for example
        ``{"person": Person, "age": Person.age}``. Existing explicit
        endpoint / ``SemanticRulePort`` forms remain advanced compatibility
        inputs. Every form is resolved against this builder's graph.

        Args:
            when: Logical SDK Rule body.
            ports: Mapping from public port names to Rule variables.
            semantic_ports: Complete semantic meaning for every public port.
            repr: Optional legacy presentation template.

        Returns:
            A graph-bound ``ProductRuleV1`` usable by Product Policy and typed
            Query without a later registry lookup.

        Raises:
            ProductAuthoringError: If Rule construction, port coverage, schema
                resolution, or semantic typing fails.

        Notes:
            Product Function calls and engine settings do not belong in a
            Rule body. Policy composes Rule and Function as peer occurrences;
            an execution profile owns adapter semantics.
        """

        rule = _build_raw_rule(
            id=self._id,
            version=self._version,
            when=when,
            ports=ports,
            repr=repr,
        )
        declared = _resolve_semantic_ports(rule=rule, semantic_ports=semantic_ports)
        try:
            contract = resolve_rule_contract(
                rule,
                declared,
                schema_index=self._graph._application_schema_index,
            )
        except (TypeError, ValueError) as exc:
            code = getattr(exc, "code", "PRODUCT_RULE_SEMANTIC_RESOLUTION_REJECTED")
            raise ProductAuthoringError(
                f"Rule semantic resolution rejected: {exc}", code=code
            ) from exc
        return ProductRuleV1(rule, contract, self._meta)


def rule_builder(
    graph: "SDKStore",
    id: str,
    *,
    version: str | None = None,
    meta: AssetMeta | None = None,
) -> RuleBuilder:
    """Start staged Product Rule construction for one graph.

    Args:
        graph: FactGraph whose compiled schema resolves semantic ports.
        id: Stable application-defined Rule identifier.
        version: Optional application-defined version.
        meta: Optional human-facing asset descriptor.

    Returns:
        A graph-bound ``RuleBuilder`` without executing or registering a Rule.
    """
    return RuleBuilder(graph, id, version=version, meta=meta)


def build_rule(
    graph: "SDKStore",
    *,
    id: str,
    when: Sequence[Any],
    ports: Mapping[str, Any],
    semantic_ports: Mapping[str, SemanticEndpoint | SemanticRulePort | type[Entity] | Field],
    version: str | None = None,
    meta: AssetMeta | None = None,
    repr: str | None = None,
) -> ProductRuleV1:
    """Build and resolve a Product Rule in one call.

    ``semantic_ports`` accepts the same public ``Entity`` / ``Field`` forms
    as :meth:`RuleBuilder.build`.

    Args:
        graph: FactGraph whose schema resolves semantic ports.
        id: Stable application-defined Rule identifier.
        when: Logical SDK Rule body.
        ports: Public port-to-variable mapping.
        semantic_ports: Complete semantic meaning for every public port.
        version: Optional application-defined version.
        meta: Optional human-facing asset descriptor.
        repr: Optional legacy presentation template.

    Returns:
        A sealed, graph-bound ``ProductRuleV1``.

    Raises:
        ProductAuthoringError: If construction or semantic resolution fails.

    Notes:
        This is the direct equivalent of ``rule_builder(...).build(...)`` and
        has no separate compiler or registry path.
    """

    return rule_builder(graph, id, version=version, meta=meta).build(
        when=when,
        ports=ports,
        semantic_ports=semantic_ports,
        repr=repr,
    )


_ProductStructuralInput: TypeAlias = ProductPolicyNode | PolicyOccurrenceHandle
_ProductAllInput: TypeAlias = ProductPolicyNode | PolicyOccurrenceHandle | PolicyConstraintHandle


class PolicyBuilder:
    """Compose graph-bound Rule and Function assets into one Product Policy.

    Handles issued by a builder carry its private owner token. Mixing handles
    across builders fails before compilation, even when aliases happen to
    match.

    Notes:
        ``id`` and ``version`` identify the authored asset; they do not create
        a global registry entry. Policy is the only composition owner for
        Product Rule and Product Function.
    """

    __slots__ = (
        "_graph",
        "_draft",
        "_meta",
        "_owner",
        "_choices",
        "_choice_conditions",
        "_functions",
    )

    def __init__(
        self,
        graph: "SDKStore",
        id: str,
        *,
        version: str | None = None,
        meta: AssetMeta | None = None,
    ) -> None:
        self._graph = graph
        self._draft = policy_draft(graph, id, version=version)
        self._meta = _normalize_asset_meta(meta)
        self._owner = object()
        self._choices: list[WeightedChoiceTopologyV1] = []
        self._choice_conditions: dict[str, PolicyNodeHandle] = {}
        self._functions: dict[str, FunctionOccurrenceHandleV1] = {}

    @property
    def id(self) -> str:
        """Return the Product Policy identifier owned by this builder."""
        return self._draft.id

    @property
    def version(self) -> str | None:
        """Return the optional Product Policy version."""
        return self._draft.version

    @property
    def meta(self) -> AssetMetaStateV1:
        """Return the immutable descriptor that will be bound to the Policy."""
        return self._meta

    def use(
        self,
        asset: ResolvedRuleBundle | ProductFunctionV1,
        *,
        as_: str | None = None,
    ) -> PolicyOccurrenceHandle | _PendingPolicyUseV1:
        """Declare a local Rule or Function occurrence.

        Args:
            asset: Resolved Product Rule or Product Function to compose.
            as_: Optional local alias. When omitted, call ``.as_(alias)`` on
                the returned pending-use object.

        Returns:
            An owner-bound occurrence handle, or a pending handle supporting
            the fluent ``policy.use(asset).as_(...)`` spelling.

        Raises:
            ProductAuthoringError: If the asset type, alias, topology, or
                current first-slice Function/WeightedChoice combination is
                unsupported.

        Notes:
            ``use`` declares a Policy-local occurrence. It does not register,
            execute, or mutate the source asset.
        """

        if as_ is None:
            return _PendingPolicyUseV1(self, asset)
        if isinstance(asset, ProductFunctionV1):
            if self._choices:
                raise ProductAuthoringError(
                    "Function and WeightedChoice cannot share one first-slice Policy",
                    code="PRODUCT_FUNCTION_WEIGHTED_CHOICE_UNSUPPORTED",
                )
            bundle = _function_resolved_bundle(
                asset,
                schema_digest=self._graph._application_schema_index.schema_digest,
                alias=as_,
            )
            base = self._draft.use(bundle, as_=as_)
            handle = FunctionOccurrenceHandleV1(base, asset, self._functions)
            self._draft._occurrences[as_] = handle
            self._functions[as_] = handle
            return handle
        if not isinstance(asset, ResolvedRuleBundle):
            raise ProductAuthoringError(
                "Policy use requires ProductRuleV1/ResolvedRuleBundle or ProductFunctionV1",
                code="PRODUCT_POLICY_UNSUPPORTED_ASSET",
            )
        return self._draft.use(asset, as_=as_)

    occurrence = use

    def all(self, *items: _ProductAllInput) -> ProductPolicyNode:
        """Require every supplied occurrence, node, or constraint.

        Nested topology is preserved for structured Explain. Use this method
        instead of Python ``and``, whose truthiness is rejected.

        Args:
            *items: Owner-bound Rule/Function occurrences, structural nodes,
                or typed constraints that must all hold.

        Returns:
            An owner-bound logical conjunction for further composition or
            final ``build(...)``.

        Raises:
            ProductAuthoringError: If an item is unsupported, cross-owned, or
                violates Function/choice structural restrictions.

        Notes:
            Nested authored topology is retained for structured Explain; this
            method does not flatten the Policy into engine branches.
        """
        raw = tuple(self._raw_all_item(item) for item in items)
        return ProductPolicyNode(self._owner, self._draft.all(*raw))

    def any(self, *items: _ProductStructuralInput) -> ProductPolicyNode:
        """Require at least one supplied occurrence or structural node.

        ``any`` is logical OR and carries no probability. Use
        :meth:`weighted_choice` for an exclusive categorical model.

        Args:
            *items: Owner-bound occurrences or structural nodes of which at
                least one must hold.

        Returns:
            An owner-bound logical disjunction for further composition or
            final ``build(...)``.

        Raises:
            ProductAuthoringError: If an item is unsupported, cross-owned, or
                cannot participate in this deterministic topology.

        Notes:
            ``any`` never accepts weights or engine settings. Use
            ``weighted_choice(...)`` only when the authored business model is
            explicitly exclusive and probabilistic.
        """
        raw = tuple(self._raw_structural_item(item) for item in items)
        return ProductPolicyNode(self._owner, self._draft.any(*raw))

    def same(
        self, left: PolicyEntityPortHandle, right: PolicyEntityPortHandle
    ) -> PolicyConstraintHandle:
        """Require two entity-valued ports to refer to the same entity.

        Args:
            left: First owner-bound entity port.
            right: Second owner-bound entity port.

        Returns:
            An identity-unification constraint for a containing ``all`` node.

        Raises:
            ProductAuthoringError: If the handles do not belong to this builder
                or are not entity ports.
        """
        return self._draft.same(left, right)

    def choice(
        self,
        id: str,
        *,
        probability: str,
        when: _ProductStructuralInput,
    ) -> WeightedChoiceArmV1:
        """Describe one arm of an exclusive ``weighted_choice``.

        Args:
            id: Stable arm identifier local to the choice.
            probability: Canonical decimal probability string.
            when: Structural condition for this arm.

        Returns:
            An owner-bound arm descriptor for :meth:`weighted_choice`.
        """

        raw = self._raw_structural_item(when)
        arm = WeightedChoiceArmV1(id, probability, raw._node.node_id, self._owner)
        previous = self._choice_conditions.get(arm.condition_node_id)
        if previous is not None and previous is not raw:
            raise ProductAuthoringError(
                "WeightedChoice arm condition collides with a different structural node",
                code="WEIGHTED_CHOICE_INVALID_ARM_CONDITION",
            )
        self._choice_conditions[arm.condition_node_id] = raw
        return arm

    def weighted_choice(
        self,
        *,
        id: str,
        on: tuple[PolicyPortHandle, ...],
        choices: tuple[WeightedChoiceArmV1, ...],
        kind: Literal["exclusive"] = "exclusive",
    ) -> WeightedChoiceHandle:
        """Create an explicit exclusive categorical choice.

        The returned handle can be nested in :meth:`all` or :meth:`any`.  It is
        V2-only; its builder-time structural carrier is replaced with an
        intrinsic ``PolicyWeightedChoice`` before the public Policy is built.

        Args:
            id: Stable Policy-local choice identifier.
            on: Non-empty tuple of direct ports defining the selection key.
            choices: Arms created by this exact builder.
            kind: Choice model; currently only ``"exclusive"``.

        Returns:
            A V2-only structural handle.

        Raises:
            ProductAuthoringError: If keys/arms cross builders, probabilities
                are invalid, more than one choice is authored, or the topology
                conflicts with a Product Function occurrence.

        Notes:
            Arm weights belong to authored Policy semantics. A ProbLog profile
            only activates the choice and cannot override them.
        """

        if self._choices:
            raise ProductAuthoringError(
                "this V2 authoring surface supports exactly one WeightedChoice per Policy",
                code="WEIGHTED_CHOICE_MULTIPLE_UNSUPPORTED",
            )
        if self._functions:
            raise ProductAuthoringError(
                "Function and WeightedChoice cannot share one first-slice Policy",
                code="PRODUCT_FUNCTION_WEIGHTED_CHOICE_UNSUPPORTED",
            )

        if not isinstance(on, tuple) or not on:
            raise ProductAuthoringError(
                "WeightedChoice on= must be a non-empty tuple of direct Policy ports",
                code="WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
            )
        addresses: list[SemanticPortAddress] = []
        for item in on:
            if not isinstance(item, PolicyPortHandle) or isinstance(item, PolicyFieldHandle):
                raise ProductAuthoringError(
                    "WeightedChoice on= accepts direct Policy ports, not field navigation",
                    code="WEIGHTED_CHOICE_INVALID_SELECTION_KEY",
                )
            if item._owner is not self._draft._owner:
                raise ProductAuthoringError(
                    "WeightedChoice selection key must use this Policy builder's ports",
                    code="POLICY_CROSS_DRAFT_HANDLE",
                )
            addresses.append(item.address)
        if not isinstance(choices, tuple) or not choices:
            raise ProductAuthoringError(
                "WeightedChoice choices must be a non-empty tuple",
                code="WEIGHTED_CHOICE_INVALID_ARMS",
            )
        for arm in choices:
            if not isinstance(arm, WeightedChoiceArmV1) or arm._owner is not self._owner:
                raise ProductAuthoringError(
                    "WeightedChoice arms must come from this Policy builder",
                    code="WEIGHTED_CHOICE_CROSS_BUILDER_ARM",
                )
        raw_by_node_id = self._raw_conditions_by_id(choices)
        # Q19 owns canonical child order.  We retain the arm ids separately so
        # probability identity cannot accidentally inherit structural ordering.
        skeleton = self._draft.any(*tuple(raw_by_node_id[arm.condition_node_id] for arm in choices))
        topology = WeightedChoiceTopologyV1(
            id,
            tuple(addresses),
            choices,
            skeleton._node.node_id,
            kind,
        )
        self._choices.append(topology)
        return WeightedChoiceHandle(self._owner, skeleton, topology)

    def build(self, root: _ProductStructuralInput) -> ProductPolicyV1:
        """Validate and seal the final Product Policy target.

        Args:
            root: Root structural node or occurrence from this exact builder.

        Returns:
            A ``ProductPolicyV1`` containing the logical Policy, semantic
            address space, asset binding, and any V2-only topology captures.

        Raises:
            PolicyAuthoringError: If occurrence coverage or authored Policy
                structure is invalid.
            ProductAuthoringError: If Product Function or WeightedChoice
                topology is incomplete, stale, or cross-owned.

        Notes:
            Building does not evaluate the Policy or write the ledger. V2-only
            Function/WeightedChoice markers make legacy terminals fail closed
            rather than degrading their semantics.
        """
        raw = self._raw_structural_item(root)
        function_topologies = tuple(
            self._functions[alias].topology() for alias in sorted(self._functions)
        )
        if function_topologies:
            constraints = tuple(
                PolicyCompare.eq(
                    SemanticPortAddress(topology.alias, binding.port_name),
                    binding.source,
                )
                for topology in function_topologies
                for binding in topology.input_bindings
            )
            node = raw._node
            node = (
                PolicyAll((*node.children, *constraints))
                if isinstance(node, PolicyAll)
                else PolicyAll((node, *constraints))
            )
            raw = PolicyNodeHandle(self._draft._owner, node)
        try:
            target = self._draft.build(raw)
        except PolicyAuthoringError:
            raise
        # Q19 creates the private deterministic skeleton needed for existing
        # handle ownership and address-space checks.  Before publication,
        # replace every recorded skeleton with an intrinsic PolicyWeightedChoice
        # node so even ``Policy(id, product.policy.when)`` keeps the V2-only
        # semantics.  The V2 bridge is the only place allowed to derive a
        # transient PolicyAny form again for typed compilation.
        intrinsic = _embed_weighted_choices_in_policy_ast(target.policy, tuple(self._choices))
        intrinsic = _embed_function_occurrences_in_policy_ast(intrinsic, function_topologies)
        policy: Policy
        if self._choices or function_topologies:
            policy = PolicyV2Only(intrinsic.id, intrinsic.when, intrinsic.version)
        else:
            policy = intrinsic
        return ProductPolicyV1(
            policy,
            target.address_space,
            target._authoring_owner,
            self._meta,
            tuple(self._choices),
            function_topologies,
        )

    def _raw_all_item(self, value: _ProductAllInput) -> PolicyNodeHandle | PolicyConstraintHandle:
        if isinstance(value, PolicyConstraintHandle):
            if value._owner is not self._draft._owner:
                raise ProductAuthoringError(
                    "Policy all must use values from this Policy builder",
                    code="POLICY_CROSS_DRAFT_HANDLE",
                )
            return value
        return self._raw_structural_item(value)

    def _raw_structural_item(self, value: _ProductStructuralInput) -> PolicyNodeHandle:
        if isinstance(value, ProductPolicyNode):
            if value._owner is not self._owner:
                raise ProductAuthoringError(
                    "Policy structural node belongs to a different Policy builder",
                    code="POLICY_CROSS_DRAFT_HANDLE",
                )
            return value._raw
        if isinstance(value, PolicyOccurrenceHandle):
            if value._owner is not self._draft._owner:
                raise ProductAuthoringError(
                    "Policy occurrence belongs to a different Policy builder",
                    code="POLICY_CROSS_DRAFT_HANDLE",
                )
            return value
        raise ProductAuthoringError(
            "Policy structural input must be an occurrence, all(...), any(...), or weighted_choice(...)",
            code="POLICY_INVALID_ROOT",
        )

    def _raw_conditions_by_id(
        self, choices: tuple[WeightedChoiceArmV1, ...]
    ) -> dict[str, PolicyNodeHandle]:
        # Choice arms carry stable node ids rather than raw nodes so the public
        # arm DTO remains a sealed topology value.  Recover the handle from the
        # builder's local node registry maintained by ``choice``.
        result: dict[str, PolicyNodeHandle] = {}
        # ``WeightedChoiceArmV1`` intentionally does not expose a raw node;
        # this mapping is confined to the authoring session and cannot escape
        # into the immutable topology DTO.
        known = self._choice_conditions
        for arm in choices:
            raw = known.get(arm.condition_node_id)
            if not isinstance(raw, PolicyNodeHandle):
                raise ProductAuthoringError(
                    "WeightedChoice arm condition was not created by this Policy builder",
                    code="WEIGHTED_CHOICE_INVALID_ARM_CONDITION",
                )
            result[arm.condition_node_id] = raw
        return result


__all__ = [
    "ASSET_META_ABSENT_V1",
    "ASSET_META_FORMAT_V1",
    "AssetMeta",
    "AssetMetaAbsentV1",
    "AssetMetaStateV1",
    "FunctionBuilder",
    "FunctionInputBindingV1",
    "FunctionOccurrenceHandleV1",
    "FunctionOccurrenceTopologyV1",
    "FunctionPortV1",
    "PolicyBuilder",
    "ProductAuthoringError",
    "ProductPolicyNode",
    "ProductPolicyV1",
    "ProductFunctionV1",
    "ProductRuleV1",
    "RuleBuilder",
    "WEIGHTED_CHOICE_FORMAT_V1",
    "WeightedChoiceArmV1",
    "WeightedChoiceHandle",
    "WeightedChoiceTopologyV1",
    "assert_asset_binding_current_v1",
    "asset_meta_for_target",
    "asset_snapshot_v1",
    "build_rule",
    "build_function",
    "function_builder",
    "rule_builder",
]
