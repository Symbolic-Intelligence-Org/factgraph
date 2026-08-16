from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factgraph.authoring.schema_compile import (
    AuthoringSchemaCompileError,
    compile_authoring_schema_v1,
)
from factgraph.core.schema.meta_policy import (
    BUILTIN_PREMISE_ELIGIBLE_META_KEYS,
    EVENT_TIME_META_KEY,
    MetaKeyPolicy,
    SYSTEM_MANAGED_META_KEYS,
)
from factgraph.core.schema.schema_ir import (
    SchemaIRValidationError,
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest,
)
from factgraph.core.store.database import AssertionInput, Database, MetaEntry
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    is_premise_excluded,
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


class _AddedMetaPolicyEntity(Entity):
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
    def test_direct_compiled_policy_round_trips_through_database(self) -> None:
        policies = {
            "audit_note": MetaKeyPolicy(
                reader_class="audit",
                load_policy="lazy",
            ),
            "source": MetaKeyPolicy(
                premise_eligible=True,
                storage_scope="tx_liftable",
            ),
        }
        schema_ir = compile_schema_from_classes(
            [_MetaPolicyEntity],
            meta_keys=policies,
        )
        expected_digest = schema_digest(schema_ir)
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            database = Database.create(workspace, schema_ir=schema_ir)
            record = database.commit_changes(
                assertions=(
                    AssertionInput(
                        "__meta_policy_entity:entity_id",
                        (
                            (
                                "entity_ref",
                                "idref_v1:_MetaPolicyEntity:one",
                            ),
                            ("string", "one"),
                        ),
                        meta=(MetaEntry("audit_note", "str", "cold-only"),),
                    ),
                ),
                revocations=(),
                meta_defaults=(MetaEntry("source", "str", "batch"),),
            ).assertions[0]
            ledger = database._ledger_for_attach()
            store = Store(schema_ir, ledger=ledger)
            store.set_premise_exclusions(
                MetaExclusion("source", frozenset({"batch"}))
            )
            self.assertEqual(database.schema_digest, expected_digest)
            self.assertEqual(ledger._lazy_meta_keys, frozenset({"audit_note"}))
            self.assertFalse(
                any(row.key == "audit_note" for row in ledger._claim_meta_events)
            )
            self.assertEqual(
                ledger.effective_meta_rows(asrt_id=record.asrt_id, key="source")[
                    0
                ].value,
                "batch",
            )
            self.assertTrue(
                is_premise_excluded(
                    ledger,
                    record.asrt_id,
                    store.premise_exclusions,
                )
            )
            database.close()

            recompiled = compile_schema_from_classes(
                [_MetaPolicyEntity],
                meta_keys=policies,
            )
            self.assertEqual(schema_digest(recompiled), expected_digest)
            database = Database.open(workspace, schema_ir=recompiled)
            try:
                cold = database._ledger_for_attach()
                cold_store = Store(
                    recompiled,
                    ledger=cold,
                    premise_exclusions=MetaExclusion(
                        "source", frozenset({"batch"})
                    ),
                )
                self.assertEqual(cold._lazy_meta_keys, frozenset({"audit_note"}))
                self.assertFalse(
                    any(
                        row.key == "audit_note"
                        for row in cold._claim_meta_events
                    )
                )
                self.assertEqual(
                    cold.effective_meta_rows(
                        asrt_id=record.asrt_id,
                        key="audit_note",
                    )[0].value,
                    "cold-only",
                )
                self.assertTrue(
                    is_premise_excluded(
                        cold,
                        record.asrt_id,
                        cold_store.premise_exclusions,
                    )
                )
            finally:
                database.close()

    def test_system_managed_s_class_and_event_time_backfill_key_are_frozen(self) -> None:
        self.assertEqual(
            SYSTEM_MANAGED_META_KEYS,
            frozenset({"ingested_at", "ingest_key", "revoked_asrt_id"}),
        )
        self.assertEqual(EVENT_TIME_META_KEY, "event_time")

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
    def test_sdk_schema_refresh_revalidates_premise_configuration_atomically(
        self,
    ) -> None:
        current = compile_schema_from_classes(
            [_MetaPolicyEntity],
            meta_keys={
                "audit_note": MetaKeyPolicy(),
                "review_status": MetaKeyPolicy(premise_eligible=True),
            },
        )
        graph = FactGraph([_MetaPolicyEntity], store=Store(current))
        graph.set_premise_exclusions(
            MetaExclusion("review_status", frozenset({"rejected"}))
        )
        before_digest = graph._schema_digest
        before_schema = graph.schema_ir
        before_lazy = graph.ledger._lazy_meta_keys

        invalid = compile_schema_from_classes(
            [_MetaPolicyEntity, _AddedMetaPolicyEntity],
            meta_keys={
                "audit_note": MetaKeyPolicy(load_policy="lazy"),
            },
        )
        with self.assertRaisesRegex(
            SDKStoreError,
            "schema transition invalidates premise configuration",
        ):
            graph._refresh_schema_state(
                classes=[_MetaPolicyEntity, _AddedMetaPolicyEntity],
                schema_ir=invalid,
                schema_digest_value=schema_digest(invalid),
            )
        self.assertEqual(graph._schema_digest, before_digest)
        self.assertIs(graph.schema_ir, before_schema)
        self.assertEqual(graph.ledger._lazy_meta_keys, before_lazy)

        with self.assertRaisesRegex(
            SDKStoreError,
            "schema transition invalidates premise configuration",
        ):
            graph.add_schema_classes(_AddedMetaPolicyEntity)
        self.assertEqual(graph._schema_digest, before_digest)
        self.assertEqual(graph.premise_exclusions[0].key, "review_status")

        valid = compile_schema_from_classes(
            [_MetaPolicyEntity, _AddedMetaPolicyEntity],
            meta_keys={
                "audit_note": MetaKeyPolicy(load_policy="lazy"),
                "review_status": MetaKeyPolicy(premise_eligible=True),
            },
        )
        graph._refresh_schema_state(
            classes=[_MetaPolicyEntity, _AddedMetaPolicyEntity],
            schema_ir=valid,
            schema_digest_value=schema_digest(valid),
        )
        self.assertEqual(graph.ledger._lazy_meta_keys, frozenset({"audit_note"}))
        self.assertEqual(graph.premise_exclusions[0].key, "review_status")

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
                before_revision = store._premise_policy_revision
                with self.assertRaisesRegex(ValueError, "not declared premise_eligible"):
                    setter(value)
                self.assertEqual(current(), ())
                self.assertEqual(store._premise_policy_revision, before_revision)

    def test_premise_setters_advance_only_the_private_revision_after_success(self) -> None:
        schema_ir = compile_schema_from_classes([_MetaPolicyEntity])
        store = Store(schema_ir)

        self.assertFalse(hasattr(store, "premise_policy_revision"))
        self.assertEqual(store._premise_policy_revision, 0)
        preconfigured = Store(
            schema_ir,
            premise_exclusions=MetaExclusion("provenance_class", frozenset({"blocked"})),
        )
        self.assertEqual(preconfigured._premise_policy_revision, 0)

        configurations = (
            (
                store.set_premise_exclusions,
                MetaExclusion("provenance_class", frozenset({"blocked"})),
            ),
            (
                store.set_premise_allowances,
                PredicatePremiseAllowance(
                    "_MetaPolicyEntity:exists",
                    "origin_binding",
                    frozenset({"trusted"}),
                ),
            ),
            (
                store.set_premise_blocks,
                PredicatePremiseBlock(
                    "_MetaPolicyEntity:exists",
                    "provenance_class",
                    frozenset({"blocked"}),
                ),
            ),
        )
        for setter, value in configurations:
            with self.subTest(setter=setter.__name__):
                before = store._premise_policy_revision
                setter(value)
                self.assertEqual(store._premise_policy_revision, before + 1)
                setter(value)
                self.assertEqual(store._premise_policy_revision, before + 2)
                setter(None)
                self.assertEqual(store._premise_policy_revision, before + 3)

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
