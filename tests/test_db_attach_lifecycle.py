from __future__ import annotations

import tempfile
import unittest
import warnings
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

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
    Rule,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
)
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.schema.schema_ir import schema_digest


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


class Account(Entity):
    account_id: str = Identity()
    label: str = Field()


def _schema_ir(classes: list[type[Entity]] | None = None) -> dict:
    return compile_schema_from_classes(classes or [User])


def _name_pred_id(fg: SDKStore) -> str:
    return _field_pred_id(fg, "name")


def _field_pred_id(fg: SDKStore, field_name: str) -> str:
    for pred in fg.schema_ir["predicates"]:
        if pred.get("owner_type") == "User" and pred.get("py_field_name") == field_name:
            return pred["pred_id"]
    raise AssertionError(f"User.{field_name} predicate not found")


def _exists_pred_id(fg: SDKStore) -> str:
    for pred in fg.schema_ir["predicates"]:
        if pred.get("owner_type") == "User" and pred.get("is_entity_exists"):
            return pred["pred_id"]
    raise AssertionError("User exists predicate not found")


def _user_ref(value: str = "u-1") -> str:
    return encode_idref_v1("User", [("user_id", "string", value)])


def _assertion(fg: SDKStore, name: str, *, user_id: str = "u-1") -> AssertionInput:
    return AssertionInput(
        pred_id=_name_pred_id(fg),
        fact_tuple=(("entity_ref", _user_ref(user_id)), ("string", name)),
        meta=(MetaEntry("source", "str", "attach-test"),),
    )


def _entity_assertions(fg: SDKStore, user_id: str, name: str) -> list[AssertionInput]:
    ref = _user_ref(user_id)
    meta = (MetaEntry("source", "str", "attach-view-test"), MetaEntry("ingested_at", "time", 1))
    return [
        AssertionInput(pred_id=_exists_pred_id(fg), fact_tuple=(("entity_ref", ref),), meta=meta),
        AssertionInput(
            pred_id=_field_pred_id(fg, "user_id"),
            fact_tuple=(("entity_ref", ref), ("string", user_id)),
            meta=meta,
        ),
        AssertionInput(pred_id=_name_pred_id(fg), fact_tuple=(("entity_ref", ref), ("string", name)), meta=meta),
    ]


def _user_name_rule() -> Rule:
    user = Var("$user")
    name = Var("$name")
    return Rule(
        id="user:name",
        when=(PredAtom("User:exists", [user]), PredAtom("user:name", [user, name])),
        ports={"user": user, "name": name},
    )


class DBAttachLifecycleTests(unittest.TestCase):
    def test_attached_entities_create_delete_each_advance_one_consistent_tx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            schema_ir = _schema_ir()
            db = Database.create(workspace, schema_ir=schema_ir)
            fg = FactGraph.attach(db, schema_classes=[User])
            initial = db.head()

            e_ref = fg.entities.create(User, user_id="u-entity", meta={"source": "attach"})
            created = db.head()

            self.assertEqual(created.tx_seq, initial.tx_seq + 1)
            created_claims = fg.ledger.find_claims(e_ref=e_ref)
            self.assertEqual(len(created_claims), 2)
            self.assertEqual(
                {
                    row.value
                    for claim in created_claims
                    for row in fg.ledger.find_meta(asrt_id=claim.asrt_id, key="tx_id")
                },
                {created.tx_id},
            )
            self.assertTrue(all(not fg.ledger.has_active_revocation(row.asrt_id) for row in created_claims))

            revoked = fg.entities.delete(e_ref, meta={"note": "remove"})
            deleted = db.head()

            self.assertEqual(revoked, 2)
            self.assertEqual(deleted.tx_seq, created.tx_seq + 1)
            self.assertEqual(deleted.state_digest, initial.state_digest)
            revoker_ids = [fg.ledger.find_revoker(row.asrt_id) for row in created_claims]
            self.assertTrue(all(isinstance(row, str) for row in revoker_ids))
            self.assertEqual(
                {
                    meta.value
                    for revoker_id in revoker_ids
                    for meta in fg.ledger.find_meta(asrt_id=revoker_id, key="tx_id")
                },
                {deleted.tx_id},
            )
            self.assertEqual(
                {
                    annotation.value
                    for revoker_id in revoker_ids
                    for annotation in fg.ledger.find_annotations(asrt_id=revoker_id, key="note")
                },
                {"remove"},
            )
            db.close()
            reopened = Database.open(workspace, schema_ir=schema_ir)
            self.assertEqual(reopened.head(), deleted)
            reopened.close()

    def test_view_attached_entities_create_delete_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            writer = FactGraph.attach(db, schema_classes=[User])
            writer.entities.create(User, user_id="u-view")
            view = db.create_view("entity-view", [row.asrt_id for row in writer.ledger.claims])
            scoped = FactGraph.attach(db, schema_classes=[User], view=view)

            with self.assertRaisesRegex(SDKStoreError, "view-attached.*read-only"):
                scoped.entities.create(User, user_id="blocked")
            with self.assertRaisesRegex(SDKStoreError, "view-attached.*read-only"):
                scoped.entities.delete(User, user_id="u-view")
            with self.assertRaisesRegex(SDKStoreError, "view-attached.*read-only"):
                scoped.batch()

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

    def test_attach_accepts_same_schema_with_new_generated_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "factgraph.authoring.schema_compile._utc_now_iso_z",
                side_effect=("2026-06-06T00:00:00Z", "2026-06-06T00:00:01Z"),
            ):
                schema_ir = _schema_ir()
                db = Database.create(Path(tmp) / "workspace", schema_ir=schema_ir)
                fg = FactGraph.attach(db, schema_classes=[User])

        self.assertEqual(schema_digest(schema_ir), db.schema_digest)
        self.assertEqual(fg._schema_digest, db.schema_digest)
        self.assertNotEqual(schema_ir["generated_at"], fg.schema_ir["generated_at"])

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

    def test_attached_canonical_write_paths_are_rejected(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        # Q8 Phase 2 (Slice 6): fg.save_rule / fg.save_inference were removed
        # entirely (no longer exist on SDKStore). Remaining flat write paths
        # are still rejected when attached.
        write_calls = {
            "fg.fields.set": lambda: fg.fields.set(User.name, _user_ref(), "Ada"),
            "fg.fields.add": lambda: fg.fields.add(User.tag, _user_ref(), "vip"),
            "fg.assertions.retract": lambda: fg.assertions.retract("asrt:" + "0" * 64),
            "fg.entities.edit": lambda: fg.entities.edit(User, user_id="u-1"),
            "fg.ingest": lambda: fg.schema.ingest({}),
            "fg.add_schema_classes": lambda: fg.add_schema_classes(Account),
            "fg.save_workspace": lambda: fg.save_workspace(),
        }

        for method_name, call in write_calls.items():
            with self.subTest(method=method_name):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                        call()

    def test_attached_batch_commits_multiple_entities_in_one_tx(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])
        before = db.head()

        with fg.batch(meta={"source": "attached-batch"}) as tx:
            first = tx.entity(User, user_id="batch-1")
            first.name.set("Ada")
            first.tag.add("admin")
            second = tx.entity(User, user_id="batch-2")
            second.name.set("Grace")
            committed = tx.commit()

        after = db.head()
        self.assertEqual(after.tx_seq, before.tx_seq + 1)
        self.assertEqual(set(committed.apply_result.refs_by_handle_id), {first.handle_id, second.handle_id})
        self.assertGreaterEqual(len(committed.apply_result.assertion_ids), 5)
        self.assertEqual(
            {
                row.value
                for asrt_id in committed.apply_result.assertion_ids
                for row in fg.ledger.find_meta(asrt_id=asrt_id, key="tx_id")
            },
            {after.tx_id},
        )
        self.assertEqual(fg.entities.get(User, user_id="batch-1").name, "Ada")
        self.assertEqual(fg.entities.get(User, user_id="batch-2").name, "Grace")

    def test_attached_wire_batch_plan_commits_in_one_tx(self) -> None:
        from factgraph.sdk.batch import WireBatchPlan

        source = FactGraph.create(schema_classes=[User])
        with source.batch() as tx:
            user = tx.entity(User, user_id="wire-1")
            user.name.set("Wire")
            payload = tx.preview(objects=[user]).export(source).to_dict()

        db = Database.create(schema_ir=_schema_ir())
        target = FactGraph.attach(db, schema_classes=[User])
        before = db.head()
        wire = WireBatchPlan.from_dict(payload)
        result = wire.apply(target)
        after = db.head()

        self.assertEqual(after.tx_seq, before.tx_seq + 1)
        self.assertEqual(
            {
                row.value
                for asrt_id in result.assertion_ids
                for row in target.ledger.find_meta(asrt_id=asrt_id, key="tx_id")
            },
            {after.tx_id},
        )
        self.assertEqual(target.entities.get(User, user_id="wire-1").name, "Wire")
        with patch.object(
            target.ledger,
            "find_meta",
            side_effect=AssertionError("batch idempotency must not scan global meta rows"),
        ):
            repeated = wire.apply(target)
        self.assertEqual(db.head(), after)
        self.assertEqual(repeated.assertion_ids, result.assertion_ids)

    def test_attached_wire_retract_then_identical_reassert_preserves_field(self) -> None:
        from factgraph.sdk.batch import WireBatchPlan

        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])
        fg.entities.create(User, user_id="wire-reassert")
        with fg.batch() as tx:
            user = tx.entity(User, user_id="wire-reassert")
            user.name.set("Alice")
            tx.commit(objects=[user])
        old_claim = fg.ledger.find_claims(
            pred_id=_name_pred_id(fg),
            e_ref=_user_ref("wire-reassert"),
        )[0]

        with fg.batch() as tx:
            user = tx.entity(User, user_id="wire-reassert")
            user.name.set("Alice")
            payload = tx.preview(objects=[user]).export(fg).to_dict()
        write_index = next(
            index
            for index, op in enumerate(payload["ops"])
            if op["kind"] == "set" and op["field_name"] == "name"
        )
        payload["ops"].insert(
            write_index,
            {
                "kind": "retract",
                "handle_id": user.handle_id,
                "entity_type": "User",
                "pred_id": _name_pred_id(fg),
                "field_name": "name",
                "assertion_id": old_claim.asrt_id,
                "meta": {"note": "replace-identically"},
                "path": "$.ops[retract-name]",
            },
        )

        before = db.head()
        result = WireBatchPlan.from_dict(payload).apply(fg)
        after = db.head()
        active = [
            claim
            for claim in fg.ledger.find_claims(
                pred_id=_name_pred_id(fg),
                e_ref=_user_ref("wire-reassert"),
            )
            if not fg.ledger.has_active_revocation(claim.asrt_id)
        ]

        self.assertEqual(after.tx_seq, before.tx_seq + 1)
        self.assertEqual(len(active), 1)
        self.assertNotEqual(active[0].asrt_id, old_claim.asrt_id)
        self.assertEqual(active[0].rest_terms, [("string", "Alice")])
        self.assertIn(active[0].asrt_id, result.assertion_ids)

    def test_attached_wire_duplicate_retract_replay_is_idempotent(self) -> None:
        from factgraph.sdk.batch import WireBatchPlan

        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])
        fg.entities.create(User, user_id="wire-retract-replay")
        with fg.batch() as tx:
            user = tx.entity(User, user_id="wire-retract-replay")
            user.name.set("Alice")
            tx.commit(objects=[user])
        target = fg.ledger.find_claims(
            pred_id=_name_pred_id(fg),
            e_ref=_user_ref("wire-retract-replay"),
        )[0]

        with fg.batch() as tx:
            user = tx.entity(User, user_id="wire-retract-replay")
            user.name.set("unused")
            payload = tx.preview(objects=[user]).export(fg).to_dict()
        payload["ops"] = [op for op in payload["ops"] if op["kind"] == "ref"]
        retract = {
            "kind": "retract",
            "handle_id": user.handle_id,
            "entity_type": "User",
            "pred_id": _name_pred_id(fg),
            "field_name": "name",
            "assertion_id": target.asrt_id,
            "meta": {"note": "first-wins"},
            "path": "$.ops[retract-name]",
        }
        payload["ops"].extend((retract, {**retract, "path": "$.ops[retract-name-duplicate]"}))
        wire = WireBatchPlan.from_dict(payload)

        before = db.head()
        first = wire.apply(fg)
        committed = db.head()
        revoker = fg.ledger.find_revoker(target.asrt_id)
        self.assertIsNotNone(revoker)
        assert revoker is not None
        repeated = wire.apply(fg)

        self.assertEqual(committed.tx_seq, before.tx_seq + 1)
        self.assertEqual(db.head(), committed)
        self.assertEqual(first.assertion_ids, repeated.assertion_ids)
        self.assertEqual(first.assertion_ids.count(revoker), 2)
        self.assertEqual(
            sum(row.revoked_asrt_id == target.asrt_id for row in fg.ledger.revokes),
            1,
        )

    def test_attached_manager_write_paths_are_rejected(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        # Q8 Phase 2 (Slice 6): fg.rules.save / fg.inferences.save were removed
        # entirely (no longer exist on rules/inferences namespaces). Remaining
        # manager write paths are still rejected when attached.
        manager_calls = {
            "fg.fields.set": lambda: fg.fields.set(User.name, _user_ref(), "Ada"),
            "fg.fields.add": lambda: fg.fields.add(User.tag, _user_ref(), "vip"),
            "fg.assertions.retract": lambda: fg.assertions.retract("asrt:" + "0" * 64),
            "fg.entities.edit": lambda: fg.entities.edit(User, user_id="u-1"),
            "fg.schema.ingest": lambda: fg.schema.ingest({}),
            "fg.schema.apply": lambda: fg.schema.apply(Account),
            "fg.assertion_views.create": lambda: fg.assertion_views.create("review", asrt_ids=[]),
            "fg.assertion_views.update": lambda: fg.assertion_views.update("review", asrt_ids=[]),
            "fg.assertion_views.delete": lambda: fg.assertion_views.delete("review"),
        }

        for method_name, call in manager_calls.items():
            with self.subTest(method=method_name):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                        call()

    def test_non_attached_views_and_batch_surface_still_work(self) -> None:
        fg = FactGraph.from_schema_classes([User])
        ref = fg.entities.ref(User, user_id="u-1")
        asrt_id = fg.fields.set(User.name, ref, "Ada")

        view = fg.assertion_views.create("review", asrt_ids=[asrt_id])

        self.assertEqual(view.asrt_ids, frozenset({asrt_id}))
        self.assertIs(fg.assertion_views.get("review"), view)
        self.assertIsNotNone(fg.batch())
        with self.assertRaises(FrozenSnapshotError):
            fg.assertion_views.created_elsewhere = object()

    def test_multiple_attaches_commit_against_current_database_head(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        first = FactGraph.attach(db, schema_classes=[User])
        second = FactGraph.attach(db, schema_classes=[User])

        first_result = first.commit_assertions([_assertion(first, "Ada", user_id="u-1")])
        second_result = second.commit_assertions([_assertion(second, "Grace", user_id="u-2")])

        self.assertEqual(second_result.parent_tx_id, first_result.value.tx_id)
        self.assertEqual(db.head(), second_result.value)

    def test_attach_with_durable_view_scopes_reads_and_evaluate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            writer = FactGraph.attach(db, schema_classes=[User])
            result = writer.commit_assertions(
                [
                    *_entity_assertions(writer, "u-1", "Ada"),
                    *_entity_assertions(writer, "u-2", "Grace"),
                ]
            )
            ada_ids = [record.asrt_id for record in result.assertions[:3]]
            view = db.create_view("ada_only", ada_ids)

            scoped = FactGraph.attach(db, schema_classes=[User], view=view)

            self.assertIs(scoped._database, db)
            self.assertFalse(scoped._attached_writable)
            self.assertEqual([row.name for row in scoped.entities.where(User)], ["Ada"])
            self.assertEqual(scoped.entities.get(User, user_id="u-1").name, "Ada")
            self.assertIsNone(scoped.entities.get(User, user_id="u-2"))

            rule = _user_name_rule()
            matched = scoped.entities.match(User, rule)
            evaluated = scoped.eval.evaluate(rule, head=rule, engine="native")

            self.assertEqual([row.name for row in matched], ["Ada"])
            self.assertEqual(evaluated.count(), 1)
            self.assertEqual(evaluated.fingerprint.view_snapshot_digest, view.view_digest)
            self.assertIn("Ada", str(evaluated[0].bindings))
            self.assertNotIn("Grace", str(evaluated[0].bindings))

    def test_attach_with_view_uses_frozen_base_tx_not_current_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            writer = FactGraph.attach(db, schema_classes=[User])
            first = writer.commit_assertions(_entity_assertions(writer, "u-1", "Ada"))
            view = db.create_view("first_only", [record.asrt_id for record in first.assertions])
            writer.commit_assertions(_entity_assertions(writer, "u-2", "Grace"))

            scoped = FactGraph.attach(db, schema_classes=[User], view=view)
            evaluated = scoped.eval.evaluate(_user_name_rule(), head=_user_name_rule(), engine="native")

            self.assertEqual([row.name for row in scoped.entities.where(User)], ["Ada"])
            self.assertEqual(evaluated.count(), 1)
            self.assertIn("Ada", str(evaluated[0].bindings))
            self.assertEqual(scoped.ledger.get_ledger_meta("head_tx_id"), view.base_tx_id)

    def test_view_attached_runtime_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            writer = FactGraph.attach(db, schema_classes=[User])
            result = writer.commit_assertions(_entity_assertions(writer, "u-1", "Ada"))
            view = db.create_view("readonly", [record.asrt_id for record in result.assertions])
            scoped = FactGraph.attach(db, schema_classes=[User], view=view)

            with self.assertRaisesRegex(SDKStoreError, "view-attached runtimes are read-only"):
                scoped.commit_assertions(_entity_assertions(scoped, "u-2", "Grace"))
            with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                scoped.assertion_views.create("another", asrt_ids=[])

    def test_attach_with_view_rejects_in_memory_view_and_stale_database_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Database.create(Path(tmp) / "workspace", schema_ir=_schema_ir())
            writer = FactGraph.attach(db, schema_classes=[User])
            result = writer.commit_assertions(_entity_assertions(writer, "u-1", "Ada"))
            view = db.create_view("ada", [record.asrt_id for record in result.assertions])
            memory_view = FactGraph.from_schema_classes([User]).assertion_views.create(
                "memory",
                asrt_ids=[result.assertions[0].asrt_id],
            )

            with self.assertRaisesRegex(SDKStoreError, "durable Database view"):
                FactGraph.attach(db, schema_classes=[User], view=memory_view)
            with self.assertRaisesRegex(SDKStoreError, "view schema mismatch"):
                FactGraph.attach(
                    db,
                    schema_classes=[User],
                    view=replace(view, schema_digest="sha256:" + "0" * 64),
                )
            with self.assertRaisesRegex(SDKStoreError, "view db_id mismatch"):
                FactGraph.attach(db, schema_classes=[User], view=replace(view, db_id="db:different"))
            with self.assertRaisesRegex(SDKStoreError, "base_tx_id not found"):
                FactGraph.attach(db, schema_classes=[User], view=replace(view, base_tx_id="tx:" + "0" * 64))

    def test_method_level_view_kwargs_still_reject_with_attach_hint(self) -> None:
        fg = FactGraph.from_schema_classes([User])
        rule = _user_name_rule()

        with self.assertRaisesRegex(Exception, "unknown filter fields"):
            fg.entities.where(User, view=object())
        with self.assertRaisesRegex(SDKStoreError, "FactGraph\\.attach\\(db, view=view\\)"):
            fg.entities.match(User, rule, view=object())
        with self.assertRaisesRegex(SDKStoreError, "FactGraph\\.attach\\(db, view=view\\)"):
            fg.eval.evaluate(rule, head=rule, view=object())
        with self.assertRaisesRegex(SDKStoreError, "FactGraph\\.attach\\(db, view=view\\)"):
            fg.eval.explain(rule, head=rule, view=object())

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
