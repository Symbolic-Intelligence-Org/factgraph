"""Runtime introspection of shipped-supported enumerations.

Pure read-only function returning an immutable mapping of capability
keys to their supported values. All values are mirrored from shipped
constants — adding a value here implies the underlying validator
already accepts it.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from factgraph.core.protocol.tup_v1 import CANONICAL_TAGS as _PROTOCOL_TAGS

# Value-kind values from `application/schema_runtime.py:34` +
# `application/protocol/entity_read.py:38` (`Literal["scalar", "entity_ref"]`).
_VALUE_KINDS: frozenset[str] = frozenset({"scalar", "entity_ref"})

# Cardinality values from `application/schema_runtime.py:35` +
# `application/protocol/entity_read.py:39` (`Literal["single", "multi"]`).
_CARDINALITIES: frozenset[str] = frozenset({"single", "multi"})

# Scalar tags = canonical primitive tags minus the entity_ref tag (the
# latter is reported via `value_kinds`). Sourced from
# `core/protocol/tup_v1.py:CANONICAL_TAGS`.
_SCALAR_TAGS: frozenset[str] = frozenset(tag for tag in _PROTOCOL_TAGS if tag != "entity_ref")


_CAPABILITIES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "value_kinds": _VALUE_KINDS,
        "scalar_tags": _SCALAR_TAGS,
        "cardinalities": _CARDINALITIES,
    }
)


def compute_capabilities() -> Mapping[str, frozenset[str]]:
    """Return shipped-supported enumerations.

    Result is a frozen `MappingProxyType` of `frozenset[str]` values; both
    levels are immutable so callers cannot mutate the report.
    """
    return _CAPABILITIES
