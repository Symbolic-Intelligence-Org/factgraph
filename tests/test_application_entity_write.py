from __future__ import annotations

import unittest

from factgraph.application import (
    apply_write_plan,
    build_schema_index,
    execute_read_request,
    field_predicate,
    hydrate_entity,
    plan_write_command,
    planned_ops_to_inputs,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntityReadRequest,
    EntitySelector,
    EntityWriteCommand,
    EntityWritePlan,
    EntityWriteResult,
    FieldMutation,
    FieldPath,
    PlannedOpDTO,
)
from factgraph.core.evidence.write_protocol import WriteProtocolError, set_field
from factgraph.core.store import Database, Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity()
    name: str = Field()


class User(Entity):
    name: str = Identity()
    locale: str = Identity()
    lives_in: Country = Field()
    tag: list[str] = Field()


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Country, User])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _write_entity_exists(store: Store, index, ref) -> None:
    from factgraph.application import entity_info

    info = entity_info(index, ref.entity_type)
    set_field(store.ledger, info.exists_predicate_id, ref.encoded_ref or "", [])
    for field in info.identity_fields:
        pred = info.identity_predicates[field.name]
        set_field(
            store.ledger,
            pred.pred_id,
            ref.encoded_ref or "",
            [(field.type_domain, ref.identity[field.name])],
        )


class ApplicationEntityWriteTests(unittest.TestCase):
    def test_apply_write_plan_database_route_commits_all_ops_in_one_tx(self) -> None:
        schema_ir = compile_schema_from_classes([Country, User])
        database = Database.create(schema_ir=schema_ir)
        store = Store(schema_ir=schema_ir, ledger=database._ledger_for_attach())
        index = build_schema_index(schema_ir)
        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="add",
                        field=FieldPath(entity_type="User", field_name="tag"),
                        value="admin",
                        meta={"source": "application-test"},
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        before = database.head()
        result = apply_write_plan(
            plan,
            store=store,
            index=index,
            database=database,
        )

        self.assertFalse(result.errors)
        self.assertEqual(len(result.applied), len(plan.planned_ops))
        after = database.head()
        self.assertEqual(after.tx_seq, before.tx_seq + 1)
        tx_ids = {
            row.value
            for applied in result.applied
            for row in store.ledger.find_meta(asrt_id=applied.assertion_id, key="tx_id")
        }
        self.assertEqual(tx_ids, {after.tx_id})
        tag_id = result.applied[-1].assertion_id
        assert tag_id is not None
        annotations = store.ledger.find_annotations(asrt_id=tag_id)
        self.assertEqual(
            [(row.namespace, row.category, row.key, row.value) for row in annotations],
            [("shared", "source", "source", "application-test")],
        )

    def test_apply_write_plan_database_route_is_atomic_on_translation_error(self) -> None:
        schema_ir = compile_schema_from_classes([Country, User])
        database = Database.create(schema_ir=schema_ir)
        store = Store(schema_ir=schema_ir, ledger=database._ledger_for_attach())
        index = build_schema_index(schema_ir)
        target = resolve_selector(
            EntitySelector(entity_type="User", identity={"name": "alice", "locale": "en"}),
            index=index,
        )
        plan = EntityWritePlan(
            command=EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
            ),
            resolved_target=target,
            planned_ops=(
                PlannedOpDTO(op="record_exists", target=target),
                PlannedOpDTO(
                    op="add",
                    target=target,
                    field=FieldPath(entity_type="User", field_name="tag"),
                    value="admin",
                    meta={"ingested_at": 1},
                ),
            ),
            can_apply=True,
        )

        before = database.head()
        result = apply_write_plan(plan, store=store, index=index, database=database)

        self.assertTrue(result.errors)
        self.assertEqual(database.head(), before)
        self.assertEqual(store.ledger.claims, [])

    def test_planned_ops_to_inputs_preserves_fact_shapes_and_write_metadata(self) -> None:
        _store, index = _build_store()
        target = resolve_selector(
            EntitySelector(entity_type="User", identity={"name": "alice", "locale": "en"}),
            index=index,
        )

        assertions, revocations = planned_ops_to_inputs(
            (
                PlannedOpDTO(op="record_exists", target=target, meta={"source": "unit"}),
                PlannedOpDTO(
                    op="add",
                    target=target,
                    field=FieldPath(entity_type="User", field_name="tag"),
                    value="admin",
                    meta={"source": "unit", "priority": 7, "event_time": 123},
                ),
                PlannedOpDTO(
                    op="retract",
                    target=target,
                    field=FieldPath(entity_type="User", field_name="tag"),
                    assertion_id="asrt:" + "1" * 32,
                    meta={"note": "cleanup"},
                ),
            ),
            index=index,
        )

        self.assertEqual(len(assertions), 2)
        self.assertEqual(len(revocations), 1)
        self.assertEqual(assertions[0].fact_tuple, (("entity_ref", target.encoded_ref),))
        self.assertEqual(
            assertions[1].fact_tuple,
            (("entity_ref", target.encoded_ref), ("string", "admin")),
        )
        assertion_meta = {row.key: (row.kind, row.value) for row in assertions[1].meta}
        self.assertEqual(assertion_meta["source"], ("str", "unit"))
        self.assertEqual(assertion_meta["priority"], ("int", 7))
        self.assertEqual(assertion_meta["event_time"], ("time", 123))
        self.assertEqual(assertion_meta["ingested_at"][0], "time")
        self.assertTrue(str(assertion_meta["ingest_key"][1]).startswith("sha256:"))
        revocation_meta = {row.key: (row.kind, row.value) for row in revocations[0].meta}
        self.assertEqual(revocation_meta["revoked_asrt_id"], ("str", "asrt:" + "1" * 32))
        self.assertEqual(revocation_meta["note"], ("str", "cleanup"))
        self.assertEqual(revocation_meta["ingested_at"][0], "time")

    def test_planned_ops_to_inputs_rejects_invalid_meta_like_legacy_writer(self) -> None:
        _store, index = _build_store()
        target = resolve_selector(
            EntitySelector(entity_type="User", identity={"name": "alice", "locale": "en"}),
            index=index,
        )
        op = PlannedOpDTO(
            op="add",
            target=target,
            field=FieldPath(entity_type="User", field_name="tag"),
            value="admin",
            meta={"ingested_at": 1},
        )

        with self.assertRaisesRegex(
            WriteProtocolError,
            "reserved and system-managed.*event_time",
        ):
            planned_ops_to_inputs((op,), index=index)

    def test_plan_write_command_creates_missing_target_with_identity_bundle(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="add",
                        field=FieldPath(entity_type="User", field_name="tag"),
                        value="admin",
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        self.assertTrue(plan.can_apply)
        self.assertIsNotNone(plan.resolved_target)
        # Materialization writes only the Identity bundle; :exists is virtual.
        self.assertEqual([op.op for op in plan.planned_ops], ["set", "set", "add"])

    def test_apply_write_plan_writes_target_and_field_values(self) -> None:
        store, index = _build_store()
        command = EntityWriteCommand(
            target=EntitySelector(
                entity_type="User",
                identity={"name": "alice", "locale": "en"},
            ),
            mutations=(
                FieldMutation(
                    op="add",
                    field=FieldPath(entity_type="User", field_name="tag"),
                    value="admin",
                ),
            ),
            create_if_missing=True,
        )

        plan = plan_write_command(command, store=store, index=index)
        result = apply_write_plan(plan, store=store, index=index)

        self.assertIsInstance(result, EntityWriteResult)
        self.assertEqual(result.errors, ())
        # 2 Identity set + 1 field add.
        self.assertEqual(len(result.applied), 3)

        snapshot = hydrate_entity(plan.resolved_target.encoded_ref or "", store=store, index=index)
        self.assertEqual(snapshot.ref, plan.resolved_target)
        self.assertEqual(snapshot.fields["tag"].value, ("admin",))

    def test_plan_write_command_rejects_missing_target_when_create_disabled(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                create_if_missing=False,
            ),
            store=store,
            index=index,
        )

        self.assertFalse(plan.can_apply)
        self.assertEqual(len(plan.errors), 1)
        self.assertEqual(plan.errors[0].code, "ENTITY_NOT_FOUND")

    def test_apply_write_plan_materializes_missing_dependency(self) -> None:
        store, index = _build_store()
        command = EntityWriteCommand(
            target=EntitySelector(
                entity_type="User",
                identity={"name": "alice", "locale": "en"},
            ),
            mutations=(
                FieldMutation(
                    op="set",
                    field=FieldPath(entity_type="User", field_name="lives_in"),
                    value=EntitySelector(entity_type="Country", identity={"code": "DE"}),
                ),
            ),
            create_if_missing=True,
            include_dependencies=True,
        )

        plan = plan_write_command(command, store=store, index=index)

        self.assertTrue(plan.can_apply)
        self.assertEqual(len(plan.resolved_dependencies), 1)
        self.assertEqual(plan.resolved_dependencies[0].entity_type, "Country")

        result = apply_write_plan(plan, store=store, index=index)
        self.assertEqual(result.errors, ())

        response = execute_read_request(
            EntityReadRequest(
                mode="get",
                entity_type="User",
                selector=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
            ),
            store=store,
            index=index,
        )
        self.assertEqual(response.errors, ())
        self.assertEqual(response.items[0].fields["lives_in"].value, plan.resolved_dependencies[0])

    def test_apply_write_plan_retracts_existing_assertion(self) -> None:
        store, index = _build_store()
        user_ref = resolve_selector(
            EntitySelector(
                entity_type="User",
                identity={"name": "alice", "locale": "en"},
            ),
            index=index,
        )
        _write_entity_exists(store, index, user_ref)
        tag_asrt = set_field(
            store.ledger,
            field_predicate(index, "User", "tag").pred_id,
            user_ref.encoded_ref or "",
            [("string", "admin")],
        )

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="retract",
                        field=FieldPath(entity_type="User", field_name="tag"),
                        assertion_id=tag_asrt,
                    ),
                ),
            ),
            store=store,
            index=index,
        )

        self.assertTrue(plan.can_apply)
        result = apply_write_plan(plan, store=store, index=index)
        self.assertEqual(result.errors, ())
        snapshot = hydrate_entity(user_ref.encoded_ref or "", store=store, index=index)
        self.assertEqual(snapshot.fields["tag"].value, ())


class ApplicationEntityWriteCardinalityTests(unittest.TestCase):
    def test_set_on_multi_cardinality_field_raises_mismatch(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="set",
                        field=FieldPath(entity_type="User", field_name="tag"),
                        value="admin",
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        self.assertFalse(plan.can_apply)
        self.assertEqual(len(plan.errors), 1)
        err = plan.errors[0]
        self.assertEqual(err.code, "FIELD_CARDINALITY_MISMATCH")
        self.assertEqual(err.path, ("mutations", "0", "op"))
        self.assertEqual(err.details.get("op"), "set")
        self.assertEqual(err.details.get("cardinality"), "multi")
        self.assertEqual(err.details.get("field_name"), "tag")

    def test_add_on_single_cardinality_field_raises_mismatch(self) -> None:
        store, index = _build_store()
        country_ref = resolve_selector(
            EntitySelector(entity_type="Country", identity={"code": "DE"}),
            index=index,
        )

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="add",
                        field=FieldPath(entity_type="User", field_name="lives_in"),
                        value=country_ref,
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        self.assertFalse(plan.can_apply)
        self.assertEqual(len(plan.errors), 1)
        err = plan.errors[0]
        self.assertEqual(err.code, "FIELD_CARDINALITY_MISMATCH")
        self.assertEqual(err.details.get("op"), "add")
        self.assertEqual(err.details.get("cardinality"), "single")
        self.assertEqual(err.details.get("field_name"), "lives_in")

    def test_set_on_single_field_passes(self) -> None:
        store, index = _build_store()
        country_ref = resolve_selector(
            EntitySelector(entity_type="Country", identity={"code": "DE"}),
            index=index,
        )

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="set",
                        field=FieldPath(entity_type="User", field_name="lives_in"),
                        value=country_ref,
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.errors, ())

    def test_add_on_multi_field_passes(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice", "locale": "en"},
                ),
                mutations=(
                    FieldMutation(
                        op="add",
                        field=FieldPath(entity_type="User", field_name="tag"),
                        value="admin",
                    ),
                ),
                create_if_missing=True,
            ),
            store=store,
            index=index,
        )

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.errors, ())


if __name__ == "__main__":
    unittest.main()
