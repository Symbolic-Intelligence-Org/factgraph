"""Red + guard baseline for additive schema mutation lifecycle."""

from __future__ import annotations

import copy
from dataclasses import fields
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings

# Slice 7C / Q6-A (a.2): FileAuthoringRegistry was removed. Test methods
# that exercised the legacy adapter directly are skipped below.
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.sdk import (
    Branch,
    FactGraph,
    Inference,
    Pred,
    vars as sdk_vars,
)
from factgraph.sdk.compile import compile_schema_from_classes
from factgraph.sdk.dsl import Rule
from factgraph.sdk.store import SDKStoreError
from factgraph.sdk.schema import Entity, Field, Identity, Relationship


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag: str = Field()


class Account(Entity):
    account_id: str = Identity()
    risk_seed: str = Field()
    risk: str = Field()


class Device(Entity):
    device_id: str = Identity()
    owner: User = Field()
    status_seed: str = Field()


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field()


def _sdk_module():
    return importlib.import_module("factgraph.sdk")


def _schema_mutation_runtime():
    return importlib.import_module("factgraph.application.schema_mutation_runtime")


def _schema_add_result_class():
    return getattr(_sdk_module(), "SchemaAddResult")


def _validate_additive_extension(current_schema_ir: dict, candidate_schema_ir: dict) -> None:
    runtime = _schema_mutation_runtime()
    runtime.validate_additive_schema_extension(
        current_schema_ir=current_schema_ir,
        candidate_schema_ir=candidate_schema_ir,
    )


def _rule(*, rule_id: str = "rule.schema.tag_seed", version: str = "v1") -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, tag],
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference(*, inference_id: str = "inf.schema.tag", version: str = "v1") -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inference_id,
            version=version,
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


def _account_rule(*, rule_id: str = "rule.schema.risk_seed", version: str = "v1") -> Rule:
    with sdk_vars("a", "risk") as (a, risk):
        return Rule(
            id=rule_id,
            version=version,
            select=[a, risk],
            where=[Branch([Pred("account:risk_seed", a, risk)], id="risk_path")],
            expose=True,
        )


def _account_inference(
    *, inference_id: str = "inf.schema.risk", version: str = "v1"
) -> Inference:
    with sdk_vars("a", "risk") as (a, risk):
        return Inference(
            id=inference_id,
            version=version,
            where=[Branch([Pred("account:risk_seed", a, risk)], id="risk_path")],
            target="account:risk",
            head_vars=[a, risk],
        )


def _seed_fg(*, registry_root: Path | None = None, path: Path | None = None):
    kwargs = {}
    if registry_root is not None:
        kwargs["registry_root"] = registry_root
    if path is not None:
        kwargs["path"] = path
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        fg = FactGraph.create(schema_classes=[User], **kwargs)
    alice_ref = fg.entities.ref(User, user_id="Alice")
    set_field(
        fg.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test"},
    )
    set_field(
        fg.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test"},
    )
    return fg


def _predicate(schema_ir: dict, pred_id: str) -> dict:
    return next(pred for pred in schema_ir["predicates"] if pred["pred_id"] == pred_id)


def _entity(schema_ir: dict, entity_type: str) -> dict:
    return next(entity for entity in schema_ir["entities"] if entity["entity_type"] == entity_type)


def _read_workspace_manifest(workspace: Path) -> dict:
    return json.loads((workspace / "factgraph_workspace.json").read_text(encoding="utf-8"))


def _changed_user_class() -> type[Entity]:
    namespace = {
        "__annotations__": {"user_id": str, "nickname": str},
        "user_id": Identity(),
        "nickname": Field(),
    }
    return type("User", (Entity,), namespace)


class SchemaMutationAPITests(unittest.TestCase):
    def test_schema_namespace_exposes_register_extend_apply_methods(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        self.assertFalse(hasattr(fg.schema, "add"))
        self.assertTrue(hasattr(fg.schema, "register"))
        self.assertTrue(hasattr(fg.schema, "extend"))
        self.assertTrue(hasattr(fg.schema, "apply"))

    def test_schema_add_accepts_positional_entity_class(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        result = fg.schema.apply(Account)

        self.assertEqual(result.added_entities, ["Account"])

    def test_schema_add_accepts_schema_classes_keyword_form(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        result = fg.schema.apply(Account)

        self.assertEqual(result.added_entities, ["Account"])

    def test_schema_add_result_is_public_export_with_locked_shape(self) -> None:
        sdk_module = _sdk_module()
        SchemaAddResult = _schema_add_result_class()

        self.assertIn("SchemaAddResult", sdk_module.__all__)
        self.assertEqual(
            [field.name for field in fields(SchemaAddResult)],
            ["old_digest", "new_digest", "added_entities", "added_fields"],
        )

    def test_sdk_all_invariant_exports_schema_add_result(self) -> None:
        sdk_module = _sdk_module()

        self.assertIn("SchemaAddResult", sdk_module.__all__)


class SchemaMutationApplicationRuntimeTests(unittest.TestCase):
    def test_schema_mutation_runtime_exports_application_functions(self) -> None:
        runtime = _schema_mutation_runtime()

        for name in (
            "validate_additive_schema_extension",
            "add_schema_classes",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(runtime, name))


class SchemaMutationBehaviorTests(unittest.TestCase):
    def test_add_new_entity_updates_in_memory_schema_and_indexes(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        old_digest = fg.schema_ir and schema_digest(fg.schema_ir)

        result = fg.schema.apply(Account)
        account_ref = fg.entities.ref(Account, account_id="A1")
        fg.fields.set(Account.risk_seed, account_ref, "high")
        row = fg.entities.get(Account, account_id="A1")

        self.assertEqual(result.old_digest, old_digest)
        self.assertEqual(result.new_digest, schema_digest(fg.schema_ir))
        self.assertEqual(result.added_entities, ["Account"])
        self.assertIn(Account, fg._classes)
        self.assertEqual(fg._schema_digest, result.new_digest)
        self.assertEqual(fg.store.schema_ir, fg.schema_ir)
        self.assertEqual(getattr(row, "risk_seed"), "high")

    def test_readding_equivalent_entity_is_idempotent_noop(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        old_digest = schema_digest(fg.schema_ir)

        result = fg.schema.apply(User)

        self.assertEqual(result.old_digest, old_digest)
        self.assertEqual(result.new_digest, old_digest)
        self.assertEqual(result.added_entities, [])
        self.assertEqual(schema_digest(fg.schema_ir), old_digest)

    def test_new_entity_with_entity_ref_to_existing_entity_is_additive(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        result = fg.schema.apply(Device)
        user_ref = fg.entities.ref(User, user_id="Alice")
        device_ref = fg.entities.ref(Device, device_id="D1")
        fg.fields.set(Device.owner, device_ref, user_ref)

        self.assertEqual(result.added_entities, ["Device"])
        self.assertIn("device:owner", {pred["pred_id"] for pred in fg.schema_ir["predicates"]})


class SchemaMutationStrictValidatorTests(unittest.TestCase):
    def test_validator_accepts_pure_additive_extension(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = compile_schema_from_classes([User, Account])

        _validate_additive_extension(current, candidate)

    def test_validator_rejects_removing_existing_entity_type(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = compile_schema_from_classes([User, Account])
        candidate["entities"] = [
            entity for entity in candidate["entities"] if entity["entity_type"] != "User"
        ]

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("existing entity type", str(ctx.exception))

    def test_validator_rejects_identity_field_change(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = copy.deepcopy(current)
        _entity(candidate, "User")["identity_fields"][0]["name"] = "uid"

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("identity", str(ctx.exception))

    def test_validator_rejects_existing_predicate_id_change(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = copy.deepcopy(current)
        _predicate(candidate, "user:tag_seed")["pred_id"] = "user:tag_seed_changed"

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("predicate id", str(ctx.exception))

    def test_validator_rejects_relationship_target_change(self) -> None:
        current = compile_schema_from_classes([User, Friends])
        candidate = copy.deepcopy(current)
        _predicate(candidate, "friends:strength")["to_entity_type"] = "Account"

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("relationship target", str(ctx.exception))

    def test_validator_rejects_new_predicate_id_collision(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = compile_schema_from_classes([User, Account])
        _predicate(candidate, "account:risk_seed")["pred_id"] = "user:tag_seed"

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("predicate id collision", str(ctx.exception))

    def test_validator_rejects_existing_field_change(self) -> None:
        current = compile_schema_from_classes([User])
        candidate = copy.deepcopy(current)
        _predicate(candidate, "user:tag_seed")["cardinality"] = "multi"

        with self.assertRaises(SDKStoreError) as ctx:
            _validate_additive_extension(current, candidate)

        self.assertIn("existing field", str(ctx.exception))

    def test_failed_validation_leaves_state_unchanged(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        old_schema_ir = copy.deepcopy(fg.schema_ir)
        old_digest = schema_digest(fg.schema_ir)
        ChangedUser = _changed_user_class()

        with self.assertRaises(SDKStoreError):
            fg.schema.apply(ChangedUser)

        self.assertEqual(fg.schema_ir, old_schema_ir)
        self.assertEqual(schema_digest(fg.schema_ir), old_digest)
        self.assertNotIn(Account, fg._classes)


class SchemaMutationDigestAnchorTests(unittest.TestCase):
    def test_registry_old_digest_upserts_to_new_digest(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(fg.schema_ir)

            result = fg.schema.apply(Account)
            entry = registry.get_schema_entry()

        self.assertEqual(entry["schema_digest"], result.new_digest)

    def test_registry_absent_digest_creates_schema_entry(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)

            result = fg.schema.apply(Account)
            entry = FileAuthoringRegistry(Path(tmp_dir)).get_schema_entry()

        self.assertEqual(entry["schema_digest"], result.new_digest)

    def test_registry_mismatched_digest_raises(self) -> None:
        self.skipTest("FileAuthoringRegistry was removed by Q6-A")
        with TemporaryDirectory() as tmp_dir:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(compile_schema_from_classes([Account]))

            with self.assertRaises(SDKStoreError) as ctx:
                fg.schema.apply(Account)

        self.assertIn("registry schema_digest mismatch", str(ctx.exception))

    def test_ledger_old_digest_updates_to_new_digest(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            ledger_path = Path(tmp_dir) / "ledger.db"
            fg = FactGraph.create(schema_classes=[User], ledger_path=str(ledger_path))
            old_digest = schema_digest(fg.schema_ir)
            self.assertEqual(fg.ledger.get_ledger_meta("schema_digest"), old_digest)

            result = fg.schema.apply(Account)

        self.assertEqual(fg.ledger.get_ledger_meta("schema_digest"), result.new_digest)

    def test_unbound_in_memory_graph_allows_ledger_absent_path(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        result = fg.schema.apply(Account)

        self.assertEqual(schema_digest(fg.schema_ir), result.new_digest)

    def test_ledger_mismatched_digest_raises(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        fg.ledger.set_ledger_meta("schema_digest", schema_digest(compile_schema_from_classes([Account])))

        with self.assertRaises(SDKStoreError) as ctx:
            fg.schema.apply(Account)

        self.assertIn("ledger schema_digest mismatch", str(ctx.exception))


class SchemaMutationWorkspaceTests(unittest.TestCase):
    def test_workspace_manifest_updates_only_after_save(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)
            fg.save_workspace()
            old_manifest = _read_workspace_manifest(workspace)

            result = fg.schema.apply(Account)
            after_add_manifest = _read_workspace_manifest(workspace)
            fg.save_workspace()
            after_save_manifest = _read_workspace_manifest(workspace)

        self.assertEqual(after_add_manifest["schema_digest"], old_manifest["schema_digest"])
        self.assertEqual(after_save_manifest["schema_digest"], result.new_digest)

    # Q8 Phase 2 (Slice 6): test_post_add_rule_save_uses_new_schema_digest and
    # test_post_add_inference_save_uses_new_schema_digest were removed.
    # fg.rules.save / fg.inferences.save no longer exist; SavedRule/SavedInference
    # persistence was removed. Schema-digest behavior on schema extension is still
    # covered by other tests in this class.


class SchemaMutationDeferralTests(unittest.TestCase):
    def test_schema_delete_update_migrate_and_deprecate_are_not_public(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        for name in ("delete", "update", "migrate", "deprecate"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg.schema, name))


class SchemaMutationPreservationTests(unittest.TestCase):
    def test_existing_write_read_paths_work_without_schema_add(self) -> None:
        fg = _seed_fg()

        bob_ref = fg.entities.ref(User, user_id="Bob")
        fg.fields.set(User.name, bob_ref, "Bob")
        row = fg.entities.get(User, user_id="Bob")

        self.assertEqual(row.name, "Bob")

    def test_direct_runtime_paths_work_without_schema_add(self) -> None:
        fg = _seed_fg()

        self.assertEqual(fg.rules.inspect(_rule())["kind"], "Rule")
        self.assertEqual(len(fg.eval.evaluate(_inference())), 1)

    def test_application_runtime_modules_from_prior_slices_remain_importable(self) -> None:
        for module_name in (
            "factgraph.application.authoring_runtime",
            "factgraph.application.workspace_runtime",
        ):
            with self.subTest(module_name=module_name):
                importlib.import_module(module_name)

    def test_package_namespace_remains_distinct_from_workspace_save(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        self.assertTrue(hasattr(fg, "save_workspace"))
        self.assertTrue(hasattr(fg.package, "export_package"))

    def test_existing_facts_remain_readable_after_add(self) -> None:
        fg = _seed_fg()

        fg.schema.apply(Account)
        row = fg.entities.get(User, user_id="Alice")

        self.assertEqual(row.name, "Alice")
        self.assertEqual(row.tag_seed, "vip")

    # Q8 Phase 2 (Slice 6): test_existing_rules_and_inferences_remain_loadable_after_add
    # was removed. fg.rules.save / fg.inferences.save / fg.rules.load /
    # fg.inferences.load no longer exist. Runtime in-memory Rule/Inference
    # usage is still covered by test_existing_runtime_paths_still_work_after_add
    # below.

    def test_existing_runtime_paths_still_work_after_add(self) -> None:
        fg = _seed_fg()

        fg.schema.apply(Account)
        rule_info = fg.rules.inspect(_rule())
        inference_rows = fg.eval.evaluate(_inference())

        self.assertEqual(rule_info["kind"], "Rule")
        self.assertEqual(len(inference_rows), 1)

    def test_views_namespace_remains_in_memory_after_add(self) -> None:
        fg = _seed_fg()
        asrt_id = fg.fields.set(User.name, fg.entities.ref(User, user_id="Bob"), "Bob")
        view = fg.assertion_views.create("review", asrt_ids=[asrt_id])

        fg.schema.apply(Account)

        self.assertEqual(fg.assertion_views.get("review"), view)

    def test_track3_semantics_exports_remain_available(self) -> None:
        sdk_module = _sdk_module()

        for name in ("SemanticsProfile", "ProbLogSemantics", "PyReasonSemantics"):
            with self.subTest(name=name):
                self.assertIn(name, sdk_module.__all__)
                self.assertTrue(hasattr(sdk_module, name))

    def test_rule_inspect_still_accepts_rule_and_inference(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        self.assertEqual(fg.rules.inspect(_rule())["kind"], "Rule")
        self.assertEqual(fg.rules.inspect(_inference())["kind"], "Inference")

    # Q8 Phase 2 (Slice 6): test_blueprint2_authoring_facade_still_works was
    # removed. fg.rules.{save,list,get} / fg.inferences.{save,list,get} no
    # longer exist. The Blueprint 2 commitments are superseded by Q8 Phase 2
    # removal scope.

    def test_blueprint3_workspace_lifecycle_still_works(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            fg = _seed_fg(path=workspace)

            fg.save_workspace()
            loaded = FactGraph.load_workspace(workspace, schema_classes=[User])

            self.assertEqual(schema_digest(loaded.schema_ir), schema_digest(fg.schema_ir))


if __name__ == "__main__":
    unittest.main()
