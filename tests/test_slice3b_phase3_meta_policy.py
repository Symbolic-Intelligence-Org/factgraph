from __future__ import annotations

import unittest

from factgraph.authoring.schema_compile import (
    AuthoringSchemaCompileError,
    compile_authoring_schema_v1,
)
from factgraph.core.schema.meta_policy import (
    BUILTIN_PREMISE_ELIGIBLE_META_KEYS,
    MetaKeyPolicy,
)
from factgraph.core.schema.schema_ir import (
    SchemaIRValidationError,
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest,
)
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
)
from factgraph.core.store.runtime import Store
from factgraph.sdk import (
    Entity,
    FactGraph,
    Identity,
    SDKSchemaError,
    SDKStoreError,
    compile_schema_from_classes,
)


class _MetaPolicyEntity(Entity):
    entity_id: str = Identity()


def _authoring_schema() -> dict:
    return {
        "entities": [
            {
                "entity_type": "_MetaPolicyEntity",
                "identity_fields": [
                    {"name": "entity_id", "type_domain": "string"}
                ],
                "fields": [],
            }
        ]
    }


class MetaPolicySchemaIRTests(unittest.TestCase):
    def test_no_declarations_preserve_phase2_bytes_and_digest(self) -> None:
        generated_at = "2026-08-03T00:00:00Z"
        compiled = compile_authoring_schema_v1(
            _authoring_schema(), generated_at=generated_at
        )
        expected = {
            "schema_ir_version": "v1",
            "entities": [
                {
                    "entity_type": "_MetaPolicyEntity",
                    "identity_fields": [
                        {"name": "entity_id", "type_domain": "string"}
                    ],
                }
            ],
            "predicates": [
                {
                    "pred_id": "_MetaPolicyEntity:exists",
                    "owner_type": "_MetaPolicyEntity",
                    "arity": 1,
                    "arg_specs": [
                        {"name": "__meta_policy_entity", "type_domain": "entity_ref"}
                    ],
                    "cardinality": "single",
                    "group_key_indexes": [0],
                    "is_entity_exists": True,
                },
                {
                    "pred_id": "__meta_policy_entity:entity_id",
                    "owner_type": "_MetaPolicyEntity",
                    "arity": 2,
                    "arg_specs": [
                        {"name": "__meta_policy_entity", "type_domain": "entity_ref"},
                        {"name": "entity_id", "type_domain": "string"},
                    ],
                    "cardinality": "single",
                    "group_key_indexes": [0],
                    "py_field_name": "entity_id",
                    "is_identity_field": True,
                },
            ],
            "projection": {
                "entities": ["_MetaPolicyEntity"],
                "predicates": [
                    "_MetaPolicyEntity:exists",
                    "__meta_policy_entity:entity_id",
                ],
            },
            "protocol_version": {
                "idref_v1": "idref_v1",
                "tup_v1": "tup_v1",
                "export_v1": "export_v1",
            },
            "generated_at": generated_at,
        }
        self.assertEqual(canonicalize_schema_ir_jcs(compiled), canonicalize_schema_ir_jcs(expected))
        self.assertEqual(schema_digest(compiled), schema_digest(expected))

    def test_authoring_normalizes_defaults_and_empty_mapping(self) -> None:
        empty = _authoring_schema()
        empty["meta_keys"] = {}
        self.assertNotIn("meta_keys", compile_authoring_schema_v1(empty))

        declared = _authoring_schema()
        declared["meta_keys"] = {
            "ordinary": {
                "reader_class": "runtime",
                "premise_eligible": False,
                "load_policy": "eager",
                "storage_scope": "claim",
                "query_indexed": False,
            }
        }
        self.assertEqual(
            compile_authoring_schema_v1(declared)["meta_keys"], {"ordinary": {}}
        )

    def test_policy_changes_enter_identity_digest_and_mapping_order_does_not(self) -> None:
        left = _authoring_schema()
        left["meta_keys"] = {
            "version": {"query_indexed": True, "reader_class": "audit"},
            "origin_binding": {"premise_eligible": True},
        }
        right = _authoring_schema()
        right["meta_keys"] = {
            "origin_binding": {"premise_eligible": True},
            "version": {"reader_class": "audit", "query_indexed": True},
        }
        baseline = compile_authoring_schema_v1(_authoring_schema())
        left_ir = compile_authoring_schema_v1(left)
        right_ir = compile_authoring_schema_v1(right)
        self.assertEqual(schema_digest(left_ir), schema_digest(right_ir))
        self.assertNotEqual(schema_digest(left_ir), schema_digest(baseline))

    def test_meta_key_names_matching_schema_metadata_still_enter_digest(self) -> None:
        baseline = compile_authoring_schema_v1(_authoring_schema())
        for key in ("repr", "generated_at"):
            authoring = _authoring_schema()
            authoring["meta_keys"] = {key: {}}
            with self.subTest(key=key):
                self.assertNotEqual(
                    schema_digest(compile_authoring_schema_v1(authoring)),
                    schema_digest(baseline),
                )

    def test_direct_ir_rejects_nonminimal_or_empty_meta_keys(self) -> None:
        compiled = compile_authoring_schema_v1(_authoring_schema())
        for meta_keys in ({}, {"ordinary": {"reader_class": "runtime"}}):
            candidate = dict(compiled)
            candidate["meta_keys"] = meta_keys
            with self.subTest(meta_keys=meta_keys):
                with self.assertRaises(SchemaIRValidationError):
                    ensure_schema_ir(candidate)

    def test_authoring_rejects_unknown_values_and_reserved_keys(self) -> None:
        invalid = (
            {"ordinary": {"unknown": True}},
            {"ordinary": {"reader_class": "operator"}},
            {"ordinary": {"premise_eligible": 1}},
            {"__system__.tx": {}},
            {"__factgraph_annotation_v1__:forged": {}},
            {"ingested_at": {}},
            {"ingest_key": {}},
            {"revoked_asrt_id": {}},
            {"assertion_digest": {}},
            {"schema_digest": {}},
            {"tx_id": {}},
        )
        for meta_keys in invalid:
            authoring = _authoring_schema()
            authoring["meta_keys"] = meta_keys
            with self.subTest(meta_keys=meta_keys):
                with self.assertRaises(AuthoringSchemaCompileError):
                    compile_authoring_schema_v1(authoring)

    def test_python_compile_surface_is_typed_and_canonical(self) -> None:
        ir = compile_schema_from_classes(
            [_MetaPolicyEntity],
            meta_keys={
                "ordinary": MetaKeyPolicy(),
                "origin_binding": MetaKeyPolicy(
                    reader_class="audit",
                    premise_eligible=True,
                    storage_scope="tx_liftable",
                ),
            },
        )
        self.assertEqual(
            ir["meta_keys"],
            {
                "ordinary": {},
                "origin_binding": {
                    "reader_class": "audit",
                    "premise_eligible": True,
                    "storage_scope": "tx_liftable",
                },
            },
        )
        with self.assertRaises(SDKSchemaError):
            compile_schema_from_classes(
                [_MetaPolicyEntity], meta_keys={"ordinary": {}}  # type: ignore[dict-item]
            )

    def test_builtin_premise_keys_are_frozen_by_decision(self) -> None:
        self.assertEqual(
            BUILTIN_PREMISE_ELIGIBLE_META_KEYS,
            frozenset({"provenance_class", "origin_binding"}),
        )


class PremiseEligibilityClosureTests(unittest.TestCase):
    def test_builtins_remain_eligible_without_schema_bytes(self) -> None:
        store = Store(
            compile_schema_from_classes([_MetaPolicyEntity]),
            premise_exclusions=MetaExclusion(
                "provenance_class", frozenset({"blocked"})
            ),
            premise_allowances=PredicatePremiseAllowance(
                "_MetaPolicyEntity:exists",
                "origin_binding",
                frozenset({"trusted"}),
            ),
        )
        self.assertEqual(store.premise_exclusions[0].key, "provenance_class")
        self.assertEqual(store.premise_allowances[0].key, "origin_binding")

    def test_each_configuration_entry_rejects_undeclared_key_atomically(self) -> None:
        store = Store(compile_schema_from_classes([_MetaPolicyEntity]))
        attempts = (
            (
                store.set_premise_exclusions,
                MetaExclusion("undeclared", frozenset({"blocked"})),
                lambda: store.premise_exclusions,
            ),
            (
                store.set_premise_allowances,
                PredicatePremiseAllowance(
                    "_MetaPolicyEntity:exists",
                    "undeclared",
                    frozenset({"allowed"}),
                ),
                lambda: store.premise_allowances,
            ),
            (
                store.set_premise_blocks,
                PredicatePremiseBlock(
                    "_MetaPolicyEntity:exists",
                    "undeclared",
                    frozenset({"blocked"}),
                ),
                lambda: store.premise_blocks,
            ),
        )
        for setter, value, current in attempts:
            with self.subTest(setter=setter.__name__):
                with self.assertRaisesRegex(ValueError, "not declared premise_eligible"):
                    setter(value)
                self.assertEqual(current(), ())

    def test_explicit_declaration_opens_and_can_tighten_builtin(self) -> None:
        open_schema = compile_schema_from_classes(
            [_MetaPolicyEntity],
            meta_keys={"review_status": MetaKeyPolicy(premise_eligible=True)},
        )
        store = Store(open_schema)
        store.set_premise_blocks(
            PredicatePremiseBlock(
                "_MetaPolicyEntity:exists",
                "review_status",
                frozenset({"rejected"}),
            )
        )
        self.assertEqual(store.premise_blocks[0].key, "review_status")

        tightened_schema = compile_schema_from_classes(
            [_MetaPolicyEntity],
            meta_keys={"origin_binding": MetaKeyPolicy()},
        )
        tightened = Store(tightened_schema)
        with self.assertRaisesRegex(ValueError, "not declared premise_eligible"):
            tightened.set_premise_exclusions(
                MetaExclusion("origin_binding", frozenset({"revoked"}))
            )

    def test_constructor_rejects_undeclared_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "not declared premise_eligible"):
            Store(
                compile_schema_from_classes([_MetaPolicyEntity]),
                premise_blocks=PredicatePremiseBlock(
                    "_MetaPolicyEntity:exists",
                    "source",
                    frozenset({"untrusted"}),
                ),
            )

    def test_sdk_configuration_entries_report_closed_schema_error(self) -> None:
        graph = FactGraph.create(schema_classes=[_MetaPolicyEntity])
        attempts = (
            (
                graph.set_premise_exclusions,
                MetaExclusion("undeclared", frozenset({"blocked"})),
            ),
            (
                graph.set_premise_allowances,
                PredicatePremiseAllowance(
                    "_MetaPolicyEntity:exists",
                    "undeclared",
                    frozenset({"allowed"}),
                ),
            ),
            (
                graph.set_premise_blocks,
                PredicatePremiseBlock(
                    "_MetaPolicyEntity:exists",
                    "undeclared",
                    frozenset({"blocked"}),
                ),
            ),
        )
        for setter, value in attempts:
            with self.subTest(setter=setter.__name__):
                with self.assertRaisesRegex(SDKStoreError, "not declared premise_eligible"):
                    setter(value)


if __name__ == "__main__":
    unittest.main()
