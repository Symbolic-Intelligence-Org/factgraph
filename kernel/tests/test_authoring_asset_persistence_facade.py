"""Red + guard baseline for the authoring asset persistence facade."""

from __future__ import annotations

from dataclasses import fields
import importlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.routing import APIRoute

from kernel.application.protocol.derivation import CompiledDerivationPlan, DerivationEvaluateRequest
from kernel.authoring.registry_fs import FileAuthoringRegistry
from kernel.core.derivation.candidates import CandidateSet
from kernel.core.evidence.write_protocol import set_field
from kernel.core.schema.schema_ir import schema_digest
from kernel.core.store.runtime import Store
from kernel.sdk import Branch, FactGraph, Inference, Pred, Rule, RuleRef, SDKStore, vars as sdk_vars
from kernel.sdk.store import SDKStoreError
from kernel.sdk.schema import Entity, Field, Identity
from service.app_v1 import app


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


class Account(Entity):
    account_id: str = Identity(primary_key=True)
    risk_seed: str = Field(cardinality="single")
    risk: str = Field(cardinality="single")


def _sdk_module():
    return importlib.import_module("kernel.sdk")


def _saved_rule_ref_class():
    return getattr(_sdk_module(), "SavedRuleRef")


def _saved_inference_ref_class():
    return getattr(_sdk_module(), "SavedInferenceRef")


def _rule(*, rule_id: str = "rule.asset.tag_seed", version: str = "v1") -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id=rule_id,
            version=version,
            select=[u, tag],
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference(*, inference_id: str = "inf.asset.tag", version: str = "v1") -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id=inference_id,
            version=version,
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


def _account_rule(*, rule_id: str = "rule.asset.risk_seed", version: str = "v1") -> Rule:
    with sdk_vars("a", "risk") as (a, risk):
        return Rule(
            id=rule_id,
            version=version,
            select=[a, risk],
            where=[Branch([Pred("account:risk_seed", a, risk)], id="risk_path")],
            expose=True,
        )


def _make_fg() -> SDKStore:
    fg = FactGraph.create(schema_classes=[User])
    alice_ref = fg.ref(User, user_id="Alice")
    set_field(
        fg.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test", "confidence": 1.0},
    )
    return fg


class PersistenceNamespaceShapeTests(unittest.TestCase):
    def test_rules_namespace_exposes_persistence_methods(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        for method in ("save", "load", "list", "get"):
            with self.subTest(method=method):
                self.assertTrue(hasattr(fg.rules, method))

    def test_inferences_namespace_exists_with_persistence_methods(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        self.assertTrue(hasattr(fg, "inferences"))
        for method in ("save", "load", "list", "get"):
            with self.subTest(method=method):
                self.assertTrue(hasattr(fg.inferences, method))


class SavedRefExportTests(unittest.TestCase):
    def test_saved_ref_types_are_public_exports(self) -> None:
        sdk_module = _sdk_module()

        self.assertIn("SavedRuleRef", sdk_module.__all__)
        self.assertIn("SavedInferenceRef", sdk_module.__all__)
        self.assertTrue(hasattr(sdk_module, "SavedRuleRef"))
        self.assertTrue(hasattr(sdk_module, "SavedInferenceRef"))

    def test_saved_rule_ref_shape(self) -> None:
        SavedRuleRef = _saved_rule_ref_class()

        self.assertEqual([field.name for field in fields(SavedRuleRef)], ["rule_id", "version"])
        ref = SavedRuleRef(rule_id="rule.asset.tag_seed", version="v1")
        self.assertEqual(ref.rule_id, "rule.asset.tag_seed")
        self.assertEqual(ref.version, "v1")

    def test_saved_inference_ref_shape(self) -> None:
        SavedInferenceRef = _saved_inference_ref_class()

        self.assertEqual([field.name for field in fields(SavedInferenceRef)], ["inference_id", "version"])
        ref = SavedInferenceRef(inference_id="inf.asset.tag", version="v1")
        self.assertEqual(ref.inference_id, "inf.asset.tag")
        self.assertEqual(ref.version, "v1")


class PersistenceFacadeBehaviorTests(unittest.TestCase):
    def test_save_returns_typed_refs_not_raw_dicts_or_where_refs(self) -> None:
        SavedRuleRef = _saved_rule_ref_class()
        SavedInferenceRef = _saved_inference_ref_class()
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)

            rule_ref = fg.rules.save(_rule())
            inference_ref = fg.inferences.save(_inference())

        self.assertIsInstance(rule_ref, SavedRuleRef)
        self.assertNotIsInstance(rule_ref, dict)
        self.assertNotIsInstance(rule_ref, RuleRef)
        self.assertEqual(rule_ref.rule_id, "rule.asset.tag_seed")
        self.assertIsInstance(inference_ref, SavedInferenceRef)
        self.assertNotIsInstance(inference_ref, dict)
        self.assertEqual(inference_ref.inference_id, "inf.asset.tag")

    def test_load_returns_sdk_value_objects(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            rule_ref = fg.rules.save(_rule())
            inference_ref = fg.inferences.save(_inference())

            loaded_rule = fg.rules.load(rule_ref)
            loaded_inference = fg.inferences.load(inference_ref)

        self.assertIsInstance(loaded_rule, Rule)
        self.assertIsInstance(loaded_inference, Inference)

    def test_loaded_rule_and_inference_remain_runtime_usable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            alice_ref = fg.ref(User, user_id="Alice")
            set_field(
                fg.ledger,
                pred_id="user:tag_seed",
                e_ref=alice_ref,
                rest_terms=[("string", "vip")],
                meta={"source": "test"},
            )
            rule_ref = fg.rules.save(_rule())
            inference_ref = fg.inferences.save(_inference())

            loaded_rule = fg.rules.load(rule_ref)
            loaded_inference = fg.inferences.load(inference_ref)
            rows = fg.eval.run(loaded_rule)
            candidates = fg.eval.evaluate(loaded_inference)

        self.assertEqual(rows, [{"u": alice_ref, "tag": "vip"}])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].target, "user:tag")

    def test_list_returns_typed_refs(self) -> None:
        SavedRuleRef = _saved_rule_ref_class()
        SavedInferenceRef = _saved_inference_ref_class()
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            fg.rules.save(_rule())
            fg.inferences.save(_inference())

            rule_refs = fg.rules.list()
            inference_refs = fg.inferences.list()

        self.assertEqual([type(ref) for ref in rule_refs], [SavedRuleRef])
        self.assertEqual([type(ref) for ref in inference_refs], [SavedInferenceRef])

    def test_get_returns_latest_ref_and_load_accepts_explicit_version(self) -> None:
        SavedRuleRef = _saved_rule_ref_class()
        SavedInferenceRef = _saved_inference_ref_class()
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)
            fg.rules.save(_rule(version="v1"))
            fg.rules.save(_rule(version="v2"))
            fg.inferences.save(_inference(version="v1"))
            fg.inferences.save(_inference(version="v2"))

            latest_rule = fg.rules.get("rule.asset.tag_seed")
            loaded_rule_v1 = fg.rules.load("rule.asset.tag_seed", version="v1")
            latest_inference = fg.inferences.get("inf.asset.tag")
            loaded_inference_v1 = fg.inferences.load("inf.asset.tag", version="v1")

        self.assertIsInstance(latest_rule, SavedRuleRef)
        self.assertEqual(latest_rule.version, "v2")
        self.assertIsInstance(loaded_rule_v1, Rule)
        self.assertEqual(loaded_rule_v1.version, "v1")
        self.assertIsInstance(latest_inference, SavedInferenceRef)
        self.assertEqual(latest_inference.version, "v2")
        self.assertIsInstance(loaded_inference_v1, Inference)
        self.assertEqual(loaded_inference_v1.version, "v1")


class RegistryBindingTests(unittest.TestCase):
    def test_factgraph_create_accepts_registry_root(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            fg = FactGraph.create(schema_classes=[User], registry_root=tmp_dir)

            self.assertIsInstance(fg, FactGraph)

    def test_factgraph_create_accepts_registry_object(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))

            fg = FactGraph.create(schema_classes=[User], registry=registry)

            self.assertIsInstance(fg, FactGraph)

    def test_factgraph_create_rejects_conflicting_registry_inputs(self) -> None:
        with TemporaryDirectory() as root_a, TemporaryDirectory() as root_b:
            registry = FileAuthoringRegistry(Path(root_a))

            with self.assertRaises(SDKStoreError) as ctx:
                FactGraph.create(schema_classes=[User], registry_root=root_b, registry=registry)

        message = str(ctx.exception)
        self.assertIn("registry", message)
        self.assertIn("conflict", message)


class ApplicationAuthoringRuntimeTests(unittest.TestCase):
    def test_authoring_runtime_exports_application_functions(self) -> None:
        module = importlib.import_module("kernel.application.authoring_runtime")

        for name in (
            "save_rule",
            "load_rule",
            "list_rules",
            "get_rule",
            "save_inference",
            "load_inference",
            "list_inferences",
            "get_inference",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))


class SchemaUpsertTests(unittest.TestCase):
    def test_first_save_auto_upserts_schema_ir(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            fg = FactGraph.create(schema_classes=[User], registry=registry)

            fg.rules.save(_rule())

            entry = registry.get_schema_entry()

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["schema_digest"], schema_digest(fg.schema_ir))

    def test_matching_schema_save_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            fg = FactGraph.create(schema_classes=[User], registry=registry)

            first = fg.rules.save(_rule(rule_id="rule.asset.tag_seed.a"))
            second = fg.inferences.save(_inference(inference_id="inf.asset.tag.a"))

            entry = registry.get_schema_entry()

        self.assertEqual(first.version, "v1")
        self.assertEqual(second.version, "v1")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["schema_digest"], schema_digest(fg.schema_ir))

    def test_schema_digest_mismatch_raises_without_overwrite(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            fg_user = FactGraph.create(schema_classes=[User], registry=registry)
            fg_user.rules.save(_rule())
            original_entry = registry.get_schema_entry()

            fg_account = FactGraph.create(schema_classes=[Account], registry=registry)
            with self.assertRaises(SDKStoreError) as ctx:
                fg_account.rules.save(_account_rule())

            after_entry = registry.get_schema_entry()

        message = str(ctx.exception)
        self.assertIn("schema", message)
        self.assertIn("digest", message)
        self.assertEqual(after_entry, original_entry)


class PublicSurfaceHardCutTests(unittest.TestCase):
    def test_sdkregistry_removed_from_public_sdk(self) -> None:
        sdk_module = _sdk_module()

        self.assertNotIn("SDKRegistry", sdk_module.__all__)
        self.assertFalse(hasattr(sdk_module, "SDKRegistry"))

    def test_saved_refs_are_not_runtime_selectors(self) -> None:
        SavedRuleRef = _saved_rule_ref_class()
        fg = FactGraph.create(schema_classes=[User])
        saved_ref = SavedRuleRef(rule_id="rule.asset.tag_seed", version="v1")

        with self.assertRaises((TypeError, SDKStoreError)) as ctx:
            fg.eval.run(saved_ref)

        self.assertIn("load", str(ctx.exception).lower())


class DirectRuntimePreservationGuards(unittest.TestCase):
    def test_direct_run_rule_still_works_without_registry(self) -> None:
        fg = _make_fg()

        rows = fg.eval.run(_rule())

        self.assertTrue(rows)

    def test_direct_evaluate_inference_still_works_without_registry(self) -> None:
        fg = _make_fg()

        candidates = fg.eval.evaluate(_inference(), engine="native")

        self.assertTrue(candidates)

    def test_ruleref_where_clause_remains_dsl_atom_not_saved_asset_ref(self) -> None:
        base_rule = _rule(rule_id="rule.asset.base")
        with sdk_vars("u", "tag") as (u, tag):
            parent = Rule(
                id="rule.asset.parent",
                version="v1",
                select=[u, tag],
                where=[RuleRef(base_rule)(u, tag)],
                expose=True,
            )

        lowered = parent.to_authoring_payload()["where"]

        self.assertEqual(lowered[0][0], "ruleref")
        self.assertEqual(lowered[0][1], "rule.asset.base")


class PriorSlicePreservationGuards(unittest.TestCase):
    def test_blueprint1_public_surface_remains(self) -> None:
        sdk_module = _sdk_module()
        fg = FactGraph.create(schema_classes=[User])
        params = inspect.signature(SDKStore.check).parameters

        self.assertTrue(hasattr(sdk_module, "Inference"))
        self.assertFalse(hasattr(sdk_module, "Derivation"))
        self.assertIsInstance(fg, FactGraph)
        self.assertIn("inference", params)

    def test_inference_wire_registry_surface_remains(self) -> None:
        routes = {route.path for route in app.routes if isinstance(route, APIRoute)}
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            result = registry.register_inference_spec(_inference().to_authoring_payload())
            payload = registry.read_inference_spec("inf.asset.tag", "v1")

        self.assertIn("/v1/runtime/sessions/{session_id}/inferences/evaluate", routes)
        self.assertIn("/v1/registry/inferences/read", routes)
        self.assertEqual(result["inference_id"], "inf.asset.tag")
        self.assertIn("derivation_id", payload)

    def test_no_queries_namespace_until_query_persistence_slice(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        self.assertFalse(hasattr(fg, "queries"))

    def test_rules_inspect_rule_and_inference_still_work(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        inspected_rule = fg.rules.inspect(_rule())
        inspected_inference = fg.rules.inspect(_inference())

        self.assertEqual(inspected_rule["kind"], "Rule")
        self.assertEqual(inspected_inference["kind"], "Inference")


class SubstratePreservationGuards(unittest.TestCase):
    def test_candidate_and_application_derivation_substrate_names_remain(self) -> None:
        candidate_fields = {field.name for field in fields(CandidateSet)}
        request_fields = {field.name for field in fields(DerivationEvaluateRequest)}
        plan_fields = {field.name for field in fields(CompiledDerivationPlan)}

        self.assertIn("derivation_id", candidate_fields)
        self.assertIn("derivation_version", candidate_fields)
        self.assertEqual(DerivationEvaluateRequest.__name__, "DerivationEvaluateRequest")
        self.assertFalse(hasattr(importlib.import_module("kernel.application.protocol.derivation"), "InferenceEvaluateRequest"))
        self.assertIn("plans", request_fields)
        self.assertIn("derivation_id", plan_fields)

    def test_core_store_runtime_still_uses_derivation_id_parameter(self) -> None:
        evaluate_params = inspect.signature(Store.evaluate).parameters
        accept_params = inspect.signature(Store.accept).parameters

        self.assertIn("derivation_id", evaluate_params)
        self.assertIn("derivation_id", accept_params)

    def test_inference_payload_still_uses_compiler_derivation_id(self) -> None:
        payload = _inference().to_authoring_payload()

        self.assertIn("derivation_id", payload)
        self.assertNotIn("inference_id", payload)
