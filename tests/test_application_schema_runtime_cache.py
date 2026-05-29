"""Slice 2 Step 1 — SchemaIndex cache extension acceptance tests.

Verifies `SchemaIndex.identity_pred_ids` + `exists_pred_ids` frozensets
and `protected_anchor_pred_ids` union property per ADR-IC §4.3.1 + Slice 2
blueprint §8 Step 1.

NEW test file per Slice 2 SF7 (tests directory in scope; only NEW/relevant
tests required; legacy pre-Slice-1 fixtures NOT cleanup obligation).
"""
from factgraph.application.schema_runtime import SchemaIndex, build_schema_index
from factgraph.authoring.schema_compile import compile_authoring_schema_v1


def _build_index(authoring: dict) -> SchemaIndex:
    schema_ir = compile_authoring_schema_v1(authoring)
    return build_schema_index(schema_ir)


def test_schema_index_has_new_frozenset_fields():
    """SchemaIndex dataclass has identity_pred_ids + exists_pred_ids fields."""
    from dataclasses import fields as dc_fields

    field_names = {f.name for f in dc_fields(SchemaIndex)}
    assert "identity_pred_ids" in field_names
    assert "exists_pred_ids" in field_names
    # protected_anchor_pred_ids is a @property, NOT a dataclass field
    assert "protected_anchor_pred_ids" not in field_names


def test_build_schema_index_populates_identity_pred_ids():
    """build_schema_index populates identity_pred_ids from PredicateInfo.is_identity_field."""
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                    {"name": "tenant_id", "type_domain": "string"},
                ],
                "fields": [
                    {"__kind__": "field", "py_name": "name", "type_domain": "string", "cardinality": "single"},
                ],
            },
        ]
    }
    idx = _build_index(authoring)
    assert idx.identity_pred_ids == frozenset({"user:user_id", "user:tenant_id"})
    assert isinstance(idx.identity_pred_ids, frozenset)


def test_build_schema_index_populates_exists_pred_ids():
    """build_schema_index populates exists_pred_ids from PredicateInfo.is_entity_exists."""
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                ],
                "fields": [],
            },
            {
                "entity_type": "Order",
                "identity_fields": [
                    {"name": "order_id", "type_domain": "string"},
                ],
                "fields": [],
            },
        ]
    }
    idx = _build_index(authoring)
    # exists predicates use capitalized EntityType per schema_compile convention
    assert idx.exists_pred_ids == frozenset({"User:exists", "Order:exists"})
    assert isinstance(idx.exists_pred_ids, frozenset)


def test_protected_anchor_pred_ids_is_union():
    """protected_anchor_pred_ids property returns union of identity + exists frozensets."""
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                ],
                "fields": [
                    {"__kind__": "field", "py_name": "name", "type_domain": "string", "cardinality": "single"},
                ],
            },
        ]
    }
    idx = _build_index(authoring)
    expected_union = idx.identity_pred_ids | idx.exists_pred_ids
    assert idx.protected_anchor_pred_ids == expected_union
    assert isinstance(idx.protected_anchor_pred_ids, frozenset)


def test_identity_and_exists_independent_sets():
    """identity_pred_ids and exists_pred_ids are disjoint (SF9 two independent sets)."""
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                    {"name": "tenant_id", "type_domain": "string"},
                ],
                "fields": [],
            },
        ]
    }
    idx = _build_index(authoring)
    # Identity pred_ids and exists pred_ids must be disjoint
    overlap = idx.identity_pred_ids & idx.exists_pred_ids
    assert overlap == frozenset(), f"identity and exists pred_ids must be disjoint, got overlap {overlap}"


def test_membership_lookup_o1():
    """Cache membership lookup is O(1) frozenset native."""
    authoring = {
        "entities": [
            {
                "entity_type": "User",
                "identity_fields": [
                    {"name": "user_id", "type_domain": "string"},
                ],
                "fields": [
                    {"__kind__": "field", "py_name": "name", "type_domain": "string", "cardinality": "single"},
                ],
            },
        ]
    }
    idx = _build_index(authoring)

    # Identity field pred_id → identity_pred_ids hit
    assert "user:user_id" in idx.identity_pred_ids
    # Non-identity field pred_id → identity_pred_ids miss
    assert "user:name" not in idx.identity_pred_ids
    # Exists pred_id → exists_pred_ids hit
    assert "User:exists" in idx.exists_pred_ids
    # Identity field pred_id → exists_pred_ids miss
    assert "user:user_id" not in idx.exists_pred_ids
    # Union property: both Identity and exists hit
    assert "user:user_id" in idx.protected_anchor_pred_ids
    assert "User:exists" in idx.protected_anchor_pred_ids
    # Field pred_id → union miss
    assert "user:name" not in idx.protected_anchor_pred_ids
