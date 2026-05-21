from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

from factgraph.sdk import (
    AssertionInput,
    CommitResult,
    Database,
    Entity,
    FactGraph,
    Field,
    FrozenSnapshotError,
    Identity,
    MetaEntry,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Account(Entity):
    account_id: str = Identity(primary_key=True)
    label: str = Field(cardinality="single")


def _schema_ir(classes: list[type[Entity]] | None = None) -> dict:
    return compile_schema_from_classes(classes or [User])


def _name_pred_id(fg: SDKStore) -> str:
    for pred in fg.schema_ir["predicates"]:
        if pred.get("owner_type") == "User" and pred.get("py_field_name") == "name":
            return pred["pred_id"]
    raise AssertionError("User.name predicate not found")


def _user_ref(value: str = "u-1") -> str:
    return f"idref_v1:User:{value}"


def _assertion(fg: SDKStore, name: str, *, user_id: str = "u-1") -> AssertionInput:
    return AssertionInput(
        pred_id=_name_pred_id(fg),
        fact_tuple=(("entity_ref", _user_ref(user_id)), ("string", name)),
        meta=(MetaEntry("source", "str", "attach-test"),),
    )


class DBAttachLifecycleTests(unittest.TestCase):
    def test_attach_returns_database_bound_store_and_commit_assertions_routes_to_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            fg = FactGraph.attach(db, schema_classes=[User])

            self.assertIs(fg._database, db)
            self.assertTrue(fg._attached_writable)
            self.assertIs(fg.ledger, db._ledger_for_attach())

            result = fg.commit_assertions([_assertion(fg, "Ada")])

            self.assertIsInstance(result, CommitResult)
            self.assertEqual(result.value, db.head())
            record = result.assertions[0]
            self.assertEqual(fg.assertions.by_id(record.asrt_id).asrt_id, record.asrt_id)

    def test_attach_validates_schema_against_database_not_ledger_meta_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            db._ledger.replace_ledger_meta("schema_digest", "sha256:" + "0" * 64)

            fg = FactGraph.attach(db, schema_classes=[User])

            self.assertEqual(fg._schema_digest, db.schema_digest)

        other = Database.create(schema_ir=_schema_ir([Account]))
        with self.assertRaisesRegex(SDKStoreError, "schema mismatch"):
            FactGraph.attach(other, schema_classes=[User])

    def test_attach_rejects_unknown_and_constructor_style_kwargs(self) -> None:
        db = Database.create(schema_ir=_schema_ir())

        for kwargs in (
            {"rules": object()},
            {"view": object()},
            {"path": ":memory:"},
            {"ledger": object()},
            {"unknown": object()},
        ):
            with self.subTest(kwargs=sorted(kwargs)):
                with self.assertRaises(SDKStoreError):
                    FactGraph.attach(db, schema_classes=[User], **kwargs)

    def test_commit_assertions_only_exists_on_attached_runtime(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        with self.assertRaisesRegex(SDKStoreError, "only available on FactGraph.attach"):
            fg.commit_assertions([_assertion(fg, "Ada")])

    def test_attached_flat_write_paths_are_rejected(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        flat_calls = {
            "fg.set": lambda: fg.set(User.name, _user_ref(), "Ada"),
            "fg.add": lambda: fg.add(User.tag, _user_ref(), "vip"),
            "fg.retract": lambda: fg.retract("asrt:" + "0" * 64),
            "fg.edit": lambda: fg.edit(User, user_id="u-1"),
            "fg.ingest": lambda: fg.ingest({}),
            "fg.add_schema_classes": lambda: fg.add_schema_classes(Account),
            "fg.save_rule": lambda: fg.save_rule(object()),
            "fg.save_inference": lambda: fg.save_inference(object()),
            "fg.accept": lambda: fg.accept(object()),
            "fg.accept_many": lambda: fg.accept_many([]),
            "fg.batch": lambda: fg.batch(),
            "fg.save": lambda: fg.save(),
        }

        for method_name, call in flat_calls.items():
            with self.subTest(method=method_name):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                        call()

    def test_attached_batch_is_rejected_before_record_exists_plan_can_be_built(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
            fg.batch()

    def test_attached_manager_write_paths_are_rejected(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        manager_calls = {
            "fg.write.set": lambda: fg.write.set(User.name, _user_ref(), "Ada"),
            "fg.write.add": lambda: fg.write.add(User.tag, _user_ref(), "vip"),
            "fg.write.retract": lambda: fg.write.retract("asrt:" + "0" * 64),
            "fg.write.edit": lambda: fg.write.edit(User, user_id="u-1"),
            "fg.schema.ingest": lambda: fg.schema.ingest({}),
            "fg.schema.add": lambda: fg.schema.add(Account),
            "fg.rules.save": lambda: fg.rules.save(object()),
            "fg.inferences.save": lambda: fg.inferences.save(object()),
            "fg.eval.accept": lambda: fg.eval.accept(object()),
            "fg.eval.accept_many": lambda: fg.eval.accept_many([]),
            "fg.views.create": lambda: fg.views.create("review", asrt_ids=[]),
            "fg.views.update": lambda: fg.views.update("review", asrt_ids=[]),
            "fg.views.delete": lambda: fg.views.delete("review"),
        }

        for method_name, call in manager_calls.items():
            with self.subTest(method=method_name):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                        call()

    def test_non_attached_views_and_batch_surface_still_work(self) -> None:
        fg = FactGraph.from_schema_classes([User])
        ref = fg.ref(User, user_id="u-1")
        asrt_id = fg.write.set(User.name, ref, "Ada")

        view = fg.views.create("review", asrt_ids=[asrt_id])

        self.assertEqual(view.asrt_ids, frozenset({asrt_id}))
        self.assertIs(fg.views.get("review"), view)
        self.assertIsNotNone(fg.batch())
        with self.assertRaises(FrozenSnapshotError):
            fg.views.created_elsewhere = object()

    def test_multiple_attaches_commit_against_current_database_head(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        first = FactGraph.attach(db, schema_classes=[User])
        second = FactGraph.attach(db, schema_classes=[User])

        first_result = first.commit_assertions([_assertion(first, "Ada", user_id="u-1")])
        second_result = second.commit_assertions([_assertion(second, "Grace", user_id="u-2")])

        self.assertEqual(second_result.parent_tx_id, first_result.value.tx_id)
        self.assertEqual(db.head(), second_result.value)

    def test_low_level_commit_does_not_populate_sdk_identity_cache(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])
        e_ref = _user_ref("manual")

        result = fg.commit_assertions(
            [
                AssertionInput(
                    pred_id=_name_pred_id(fg),
                    fact_tuple=(("entity_ref", e_ref), ("string", "Manual")),
                )
            ]
        )

        self.assertNotIn(e_ref, fg._identity_values_by_e_ref)
        self.assertEqual(fg.assertions.by_id(result.assertions[0].asrt_id).asrt_id, result.assertions[0].asrt_id)

    def test_sdk_exports_attach_boundary_types(self) -> None:
        from factgraph import sdk

        for name in ("AssertionInput", "CommitResult", "Database", "MetaEntry"):
            with self.subTest(name=name):
                self.assertIn(name, sdk.__all__)
                self.assertIsNotNone(getattr(sdk, name))


if __name__ == "__main__":
    unittest.main()
