from __future__ import annotations

import unittest

from factgraph.application import (
    apply_write_plan,
    build_schema_index,
    execute_read_request,
    field_predicate,
    hydrate_entity,
    plan_write_command,
    resolve_selector,
)
from factgraph.application.protocol import (
    EntityReadRequest,
    EntitySelector,
    EntityWriteCommand,
    EntityWriteResult,
    FieldMutation,
    FieldPath,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    name: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    lives_in: Country = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


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
    def test_plan_write_command_creates_missing_target_with_identity_and_exists(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
        self.assertEqual([op.op for op in plan.planned_ops], ["set", "set", "record_exists", "add"])

    def test_apply_write_plan_writes_target_and_field_values(self) -> None:
        store, index = _build_store()
        command = EntityWriteCommand(
            target=EntitySelector(
                entity_type="User",
                identity={"name": "alice"},
                allow_identity_defaults=True,
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
        self.assertEqual(len(result.applied), 4)

        snapshot = hydrate_entity(plan.resolved_target.encoded_ref or "", store=store, index=index)
        self.assertEqual(snapshot.ref, plan.resolved_target)
        self.assertEqual(snapshot.fields["tag"].value, ("admin",))

    def test_plan_write_command_rejects_missing_target_when_create_disabled(self) -> None:
        store, index = _build_store()

        plan = plan_write_command(
            EntityWriteCommand(
                target=EntitySelector(
                    entity_type="User",
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                identity={"name": "alice"},
                allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                identity={"name": "alice"},
                allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
                    identity={"name": "alice"},
                    allow_identity_defaults=True,
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
