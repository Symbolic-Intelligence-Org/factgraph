from __future__ import annotations

from ._builders import (
    build_tagged_args,
    coerce_value_for_tag,
    derivation_outputs_from_bindings,
    entity_derivation_outputs_from_bindings,
    entity_spec_from_head,
    find_schema_pred,
    hashable_value,
    read_group_key_indexes,
    resolve_head_ref,
)
from ._query_style_candidates import query_style_derivation_outputs_from_bindings

# Compatibility aliases for persisted candidate/materialization consumers.
candidates_from_bindings = derivation_outputs_from_bindings
entity_candidates_from_bindings = entity_derivation_outputs_from_bindings
query_style_candidates_from_bindings = query_style_derivation_outputs_from_bindings

__all__ = [
    "build_tagged_args",
    "candidates_from_bindings",
    "coerce_value_for_tag",
    "derivation_outputs_from_bindings",
    "entity_candidates_from_bindings",
    "entity_derivation_outputs_from_bindings",
    "entity_spec_from_head",
    "find_schema_pred",
    "hashable_value",
    "query_style_candidates_from_bindings",
    "query_style_derivation_outputs_from_bindings",
    "read_group_key_indexes",
    "resolve_head_ref",
]
