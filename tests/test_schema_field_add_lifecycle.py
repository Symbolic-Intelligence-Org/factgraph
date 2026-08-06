"""Red + guard baseline for schema field-add lifecycle."""

from __future__ import annotations

import importlib
import json
from dataclasses import fields
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings

# Slice 7C / Q6-A (a.2): FileAuthoringRegistry was removed. Test methods
# that exercised the legacy adapter directly are skipped below.
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.sdk import Case, EmitSpec, FactGraph, Inference, Pred, SDKSchemaError, vars as sdk_vars
from factgraph.sdk.compile import compile_schema_from_classes
from factgraph.sdk.dsl import Rule
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStoreError


def _user_class(*, extra_fields: dict[str, Field] | None = None) -> type[Entity]:
    annotations: dict[str, object] = {
        "user_id": str,
        "name": str,
        "tag_seed": str,
        "tag": list[str],
    }
    namespace: dict[str, object] = {
        "__annotations__": annotations,
        "user_id": Identity(),
        "name": Field(),
        "tag_seed": Field(),
        "tag": Field(),
    }
    for field_name, descriptor in (extra_fields or {}).items():
        annotations[field_name] = list[str] if field_name.endswith("s2") else str
        namespace[field_name] = descriptor
    return type("User", (Entity,), namespace)


def _account_class() -> type[Entity]:
    namespace = {
        "__annotations__": {"account_id": str, "risk": str},
        "account_id": Identity(),
        "risk": Field(),
    }
    return type("Account", (Entity,), namespace)


def _user_with_identity_addition() -> type[Entity]:
    return type(
        "User",
        (Entity,),
        {
            "__annotations__": {
                "user_id": str,
                "tenant_id": str,
                "name": str,
                "tag_seed": str,
                "tag": list[str],
            },
            "user_id": Identity(),
            "tenant_id": Identity(),
            "name": Field(),
            "tag_seed": Field(),
            "tag": Field(),
        },
    )


def _user_with_changed_field(*, shape: str = "multi") -> type[Entity]:
    tag_annotation = str if shape == "single" else list[str]
    return type(
        "User",
        (Entity,),
        {
            "__annotations__": {
                "user_id": str,
                "name": str,
                "tag_seed": str,
                "tag": tag_annotation,
            },
            "user_id": Identity(),
            "name": Field(),
            "tag_seed": Field(),
            "tag": Field(),
        },
    )


def _user_with_removed_field() -> type[Entity]:
    return type(
        "User",
        (Entity,),
        {
            "__annotations__": {
                "user_id": str,
                "name": str,
                "tag_seed": str,
            },
            "user_id": Identity(),
            "name": Field(),
            "tag_seed": Field(),
        },
    )


def _user_with_nickname() -> type[Entity]:
    return _user_class(extra_fields={"nickname": Field()})


def _user_with_tags2() -> type[Entity]:
    return _user_class(extra_fields={"tags2": Field()})


def _user_with_nickname_and_tags2() -> type[Entity]:
    return _user_class(
        extra_fields={
            "nickname": Field(),
            "tags2": Field(),
        }
    )


def _user_account_class(*, with_nickname: bool = False) -> type[Entity]:
    annotations: dict[str, object] = {"account_id": str, "seed": str}
    namespace: dict[str, object] = {
        "__annotations__": annotations,
        "account_id": Identity(),
        "seed": Field(),
    }
    if with_nickname:
        annotations["nickname"] = str
        namespace["nickname"] = Field()
    return type("UserAccount", (Entity,), namespace)


def _seed_fg(*, registry_root: Path | None = None, path: Path | None = None):
    kwargs: dict[str, object] = {}
    if registry_root is not None:
        kwargs["registry_root"] = registry_root
    if path is not None:
        kwargs["path"] = path
    User = _user_class()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fg = FactGraph.create(schema_classes=[User], **kwargs)
    alice_ref = fg.entities.create(User, user_id="u-1")
    fg.fields.set(User.name, alice_ref, "Alice", meta={"source": "test"})
    fg.fields.set(User.tag_seed, alice_ref, "vip", meta={"source": "test"})
    return fg, User, alice_ref


def _schema_add_result_class():
    return getattr(importlib.import_module("factgraph.sdk"), "SchemaAddResult")


def _schema_mutation_runtime():
    return importlib.import_module("factgraph.application.schema_mutation_runtime")


def _read_manifest(workspace: Path) -> dict[str, object]:
    return json.loads((workspace / "factgraph_workspace.json").read_text(encoding="utf-8"))


def _rule_for_tag_seed(*, rule_id: str = "rule.field.seed", version: str = "v1") -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, tag],
            where=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference_for_tag(*, inference_id: str = "inf.field.tag", version: str = "v1") -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inference_id,
            version=version,
            when=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            emits=EmitSpec("user:tag", [u, tag]),
        )


def _rule_for_nickname(*, rule_id: str = "rule.field.nickname", version: str = "v1") -> Rule:
    with sdk_vars("u", "nickname") as (u, nickname):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, nickname],
            where=[Case([Pred("user:nickname", u, nickname)], id="nickname_path")],
            expose=True,
        )


class SchemaFieldAddAPIShapeTests(unittest.TestCase):
    def test_schema_add_accepts_same_entity_replacement_class(self) -> None:
        fg, OldUser, _ = _seed_fg()
        NewUser = _user_with_nickname()

        result = fg.schema.apply(NewUser)

        self.assertEqual(result.added_entities, [])
        self.assertEqual(result.added_fields, ["User.nickname"])
        self.assertNotIn(OldUser, fg._classes)
        self.assertIn(NewUser, fg._classes)

    def test_schema_add_accepts_schema_classes_keyword_for_field_add(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_nickname()

        result = fg.schema.apply(NewUser)

        self.assertEqual(result.added_fields, ["User.nickname"])

    def test_schema_add_result_public_shape_includes_added_fields(self) -> None:
        SchemaAddResult = _schema_add_result_class()

        self.assertEqual(
            [field.name for field in fields(SchemaAddResult)],
            ["old_digest", "new_digest", "added_entities", "added_fields"],
        )

    def test_equivalent_post_add_class_readd_is_idempotent(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_nickname()
        fg.schema.apply(NewUser)
        digest_after_add = schema_digest(fg.schema_ir)

        result = fg.schema.apply(NewUser)

        self.assertEqual(result.old_digest, digest_after_add)
        self.assertEqual(result.new_digest, digest_after_add)
        self.assertEqual(result.added_entities, [])
        self.assertEqual(result.added_fields, [])


class SchemaFieldAddClassReplacementTests(unittest.TestCase):
    def test_old_entity_class_is_rejected_after_replacement(self) -> None:
        fg, OldUser, _ = _seed_fg()
        NewUser = _user_with_nickname()
        fg.schema.apply(NewUser)

        with self.assertRaises(SDKStoreError) as ctx:
            fg.entities.get(OldUser, user_id="u-1")

        self.assertIn("schema declaration was superseded", str(ctx.exception))

    def test_old_field_descriptor_is_rejected_after_replacement(self) -> None:
        fg, OldUser, alice_ref = _seed_fg()
        NewUser = _user_with_nickname()
        fg.schema.apply(NewUser)

        with self.assertRaises(SDKStoreError) as ctx:
            fg.fields.set(OldUser.name, alice_ref, "Alice v2")

        self.assertIn("schema declaration was superseded", str(ctx.exception))

    def test_new_field_descriptor_is_active_after_replacement(self) -> None:
        fg, _, alice_ref = _seed_fg()
        NewUser = _user_with_nickname()

        fg.schema.apply(NewUser)
        asrt_id = fg.fields.set(NewUser.nickname, alice_ref, "Ali")
        row = fg.entities.get(NewUser, user_id="u-1")

        self.assertIsInstance(asrt_id, str)
        self.assertEqual(row.nickname, "Ali")


class SchemaFieldAddAbsenceSemanticsTests(unittest.TestCase):
    def test_missing_single_added_field_reads_as_none(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_nickname()

        fg.schema.apply(NewUser)
        row = fg.entities.get(NewUser, user_id="u-1")

        self.assertIsNone(row.nickname)

    def test_missing_multi_added_field_reads_as_empty_tuple(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_tags2()

        fg.schema.apply(NewUser)
        row = fg.entities.get(NewUser, user_id="u-1")

        self.assertEqual(row.tags2, ())

    def test_write_then_read_added_multi_field(self) -> None:
        fg, _, alice_ref = _seed_fg()
        NewUser = _user_with_tags2()

        fg.schema.apply(NewUser)
        fg.fields.add(NewUser.tags2, alice_ref, "founder")
        row = fg.entities.get(NewUser, user_id="u-1")

        self.assertEqual(row.tags2, ("founder",))


class SchemaFieldAddValidatorTests(unittest.TestCase):
    def test_validator_accepts_new_non_identity_predicate_on_existing_entity(self) -> None:
        OldUser = _user_class()
        NewUser = _user_with_nickname()

        _schema_mutation_runtime().validate_additive_schema_extension(
            current_schema_ir=compile_schema_from_classes([OldUser]),
            candidate_schema_ir=compile_schema_from_classes([NewUser]),
        )

    def test_identity_field_addition_is_rejected(self) -> None:
        fg, _, _ = _seed_fg()

        with self.assertRaises(SDKStoreError) as ctx:
            fg.schema.apply(_user_with_identity_addition())

        self.assertIn("identity", str(ctx.exception))

    def test_existing_field_cardinality_change_is_rejected(self) -> None:
        fg, _, _ = _seed_fg()

        with self.assertRaises(SDKStoreError) as ctx:
            fg.schema.apply(_user_with_changed_field(shape="single"))

        self.assertIn("existing field", str(ctx.exception))

    def test_existing_field_removal_is_rejected(self) -> None:
        fg, _, _ = _seed_fg()

        with self.assertRaises(SDKStoreError) as ctx:
            fg.schema.apply(_user_with_removed_field())

        self.assertIn("existing predicate id", str(ctx.exception))

    def test_new_field_predicate_id_collision_is_rejected(self) -> None:
        OldUser = _user_class()
        NewUser = _user_with_nickname()
        current = compile_schema_from_classes([OldUser])
        candidate = compile_schema_from_classes([NewUser])
        for pred in candidate["predicates"]:
            if pred.get("pred_id") == "user:nickname":
                pred["pred_id"] = "user:name"

        with self.assertRaises(SDKStoreError) as ctx:
            _schema_mutation_runtime().validate_additive_schema_extension(
                current_schema_ir=current,
                candidate_schema_ir=candidate,
            )

        self.assertIn("predicate id collision", str(ctx.exception))

    def test_field_default_surface_remains_absent(self) -> None:
        with self.assertRaises(SDKSchemaError):
            Field(default="n/a")  # type: ignore[call-arg]


class SchemaFieldAddDigestAnchorTests(unittest.TestCase):
    def test_ledger_digest_updates_after_field_add(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_nickname()

        result = fg.schema.apply(NewUser)

        self.assertEqual(fg.ledger.get_ledger_meta("schema_digest"), result.new_digest)

    def test_ledger_mismatch_rejects_field_add(self) -> None:
        fg, _, _ = _seed_fg()
        fg.ledger.replace_ledger_meta("schema_digest", schema_digest(compile_schema_from_classes([_account_class()])))

        with self.assertRaises(SDKStoreError) as ctx:
            fg.schema.apply(_user_with_nickname())

        self.assertIn("ledger schema_digest mismatch", str(ctx.exception))

    def test_registry_absent_schema_entry_is_created_for_field_add(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))
            result = fg.schema.apply(_user_with_nickname())
            entry = FileAuthoringRegistry(Path(tmp_dir)).get_schema_entry()

        self.assertEqual(entry["schema_digest"], result.new_digest)

    def test_registry_matching_schema_entry_updates_for_field_add(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(fg.schema_ir)

            result = fg.schema.apply(_user_with_nickname())
            entry = registry.get_schema_entry()

        self.assertEqual(entry["schema_digest"], result.new_digest)

    def test_registry_mismatch_rejects_field_add(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(compile_schema_from_classes([_account_class()]))

            with self.assertRaises(SDKStoreError) as ctx:
                fg.schema.apply(_user_with_nickname())

        self.assertIn("registry schema_digest mismatch", str(ctx.exception))


class SchemaFieldAddWorkspaceTests(unittest.TestCase):
    def test_workspace_schema_head_updates_immediately_and_save_only_touches_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg, _, _ = _seed_fg(path=workspace)
            fg.save_workspace()
            before = fg._database.head()
            old_meta = json.loads((workspace / "db" / "meta.json").read_text(encoding="utf-8"))

            result = fg.schema.apply(_user_with_nickname())
            after_add = fg._database.head()
            after_add_meta = json.loads(
                (workspace / "db" / "meta.json").read_text(encoding="utf-8")
            )
            fg.save_workspace()
            after_save = fg._database.head()
            after_save_meta = json.loads(
                (workspace / "db" / "meta.json").read_text(encoding="utf-8")
            )

        self.assertEqual(after_add.tx_seq, before.tx_seq + 1)
        self.assertEqual(after_add.schema_digest, result.new_digest)
        self.assertEqual(after_save, after_add)
        self.assertEqual(after_add_meta, old_meta)
        self.assertGreaterEqual(
            after_save_meta["last_saved_at_epoch_ns"],
            after_add_meta["last_saved_at_epoch_ns"],
        )

    def test_load_saved_workspace_requires_post_add_class(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg, _, _ = _seed_fg(path=workspace)
            NewUser = _user_with_nickname()

            fg.schema.apply(NewUser)
            fg.save_workspace()
            fg.close()
            loaded = FactGraph.load_workspace(workspace, schema_classes=[NewUser])
            loaded.close()

        self.assertEqual(schema_digest(loaded.schema_ir), schema_digest(fg.schema_ir))

    def test_load_saved_workspace_with_pre_add_class_rejects(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg, OldUser, _ = _seed_fg(path=workspace)
            fg.schema.apply(_user_with_nickname())
            fg.save_workspace()
            fg.close()

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.load_workspace(workspace, schema_classes=[OldUser])

        self.assertIn("schema_digest", str(ctx.exception))


class SchemaFieldAddSavedAssetCompatibilityTests(unittest.TestCase):
    def test_existing_saved_rule_and_inference_remain_loadable_after_field_add(self) -> None:
        self.skipTest("legacy saved rule/inference registry was removed by Q6-A/Q8")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))
            rule_ref = fg.rules.save(_rule_for_tag_seed())
            inference_ref = fg.inferences.save(_inference_for_tag())

            fg.schema.apply(_user_with_nickname())

            self.assertIsInstance(fg.rules.load(rule_ref), Rule)
            self.assertIsInstance(fg.inferences.load(inference_ref), Inference)

    def test_new_rule_referencing_added_field_saves_with_new_digest(self) -> None:
        self.skipTest("legacy saved rule registry was removed by Q6-A/Q8")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))

            result = fg.schema.apply(_user_with_nickname())
            rule_ref = fg.rules.save(_rule_for_nickname())
            entry = FileAuthoringRegistry(Path(tmp_dir)).get_schema_entry()

        self.assertEqual(rule_ref.rule_id, "rule.field.nickname")
        self.assertEqual(entry["schema_digest"], result.new_digest)

    def test_camelcase_field_add_rule_uses_compiler_predicate_prefix(self) -> None:
        OldUserAccount = _user_account_class()
        NewUserAccount = _user_account_class(with_nickname=True)
        fg = FactGraph.create(schema_classes=[OldUserAccount])

        result = fg.schema.apply(NewUserAccount)

        self.assertIn("user_account:nickname", {pred["pred_id"] for pred in fg.schema_ir["predicates"]})
        self.assertEqual(result.added_fields, ["UserAccount.nickname"])


class SchemaFieldAddPreservationTests(unittest.TestCase):
    def test_entity_add_behavior_still_works(self) -> None:
        fg, _, _ = _seed_fg()
        Account = _account_class()

        result = fg.schema.apply(Account)

        self.assertEqual(result.added_entities, ["Account"])

    def test_delete_update_migrate_and_deprecate_remain_absent(self) -> None:
        fg, _, _ = _seed_fg()

        for name in ("delete", "update", "migrate", "deprecate"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg.schema, name))

    def test_existing_facts_remain_readable_after_field_add(self) -> None:
        fg, _, _ = _seed_fg()
        NewUser = _user_with_nickname()

        fg.schema.apply(NewUser)
        row = fg.entities.get(NewUser, user_id="u-1")

        self.assertEqual(row.name, "Alice")
        self.assertEqual(row.tag_seed, "vip")

    def test_direct_runtime_paths_still_work_after_field_add(self) -> None:
        fg, _, _ = _seed_fg()

        fg.schema.apply(_user_with_nickname())

        self.assertEqual(fg.rules.inspect(_rule_for_tag_seed())["kind"], "Rule")
        self.assertEqual(len(fg.eval.evaluate(_inference_for_tag())), 1)

    def test_blueprint2_authoring_facade_still_works_after_field_add(self) -> None:
        self.skipTest("legacy authoring facade save/load was removed by Q6-A/Q8")
        with TemporaryDirectory() as tmp_dir:
            fg, _, _ = _seed_fg(registry_root=Path(tmp_dir))
            fg.schema.apply(_user_with_nickname())

            rule_ref = fg.rules.save(_rule_for_tag_seed())
            inference_ref = fg.inferences.save(_inference_for_tag())

            self.assertIsInstance(fg.rules.load(rule_ref), Rule)
            self.assertIsInstance(fg.inferences.load(inference_ref), Inference)

    def test_blueprint3_workspace_lifecycle_still_works_after_field_add(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg, _, _ = _seed_fg(path=workspace)
            NewUser = _user_with_nickname()
            fg.schema.apply(NewUser)

            fg.save_workspace()
            fg.close()
            loaded = FactGraph.load_workspace(workspace, schema_classes=[NewUser])
            loaded.close()

        self.assertEqual(schema_digest(loaded.schema_ir), schema_digest(fg.schema_ir))


if __name__ == "__main__":
    unittest.main()
