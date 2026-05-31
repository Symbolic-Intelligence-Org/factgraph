"""Red + guard baseline for public Inference naming and FactGraph.create."""

from __future__ import annotations

import importlib
from pathlib import Path
import unittest

from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.rules.where_ast import PredAtom as CorePredAtom, Var as CoreVar
from factgraph.sdk import Case, EmitSpec, FactGraph, Pred, Rule, SDKStore, vars as sdk_vars
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag_hint: str = Field()
    tag: str = Field()


def _sdk_module():
    return importlib.import_module("factgraph.sdk")


def _inference_class():
    return getattr(_sdk_module(), "Inference")


def _make_sdk() -> SDKStore:
    sdk = SDKStore([User])
    alice_ref = sdk.entities.ref(User, user_id="Alice")
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test"},
    )
    set_field(
        sdk.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test"},
    )
    return sdk


def _rule() -> Rule:
    u = CoreVar("$u")
    tag = CoreVar("$tag")
    return Rule(
        id="public_inference_tag_seed",
        version="v1",
        when=(CorePredAtom("user:tag_seed", [u, tag]),),
        ports={"u": u, "tag": tag},
    )


def _inference():
    Inference = _inference_class()
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.public_inference.tag",
            version="v1",
            when=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            emits=EmitSpec("user:tag", [u, tag]),
        )


class PublicInferenceExportTests(unittest.TestCase):
    def test_factgraph_sdk_exports_inference_and_not_derivation(self) -> None:
        sdk_module = _sdk_module()

        self.assertIn("Inference", sdk_module.__all__)
        self.assertTrue(hasattr(sdk_module, "Inference"))
        self.assertNotIn("Derivation", sdk_module.__all__)
        self.assertFalse(hasattr(sdk_module, "Derivation"))

    def test_factgraph_sdk_dsl_exports_inference_and_not_derivation(self) -> None:
        dsl_module = importlib.import_module("factgraph.sdk.dsl")

        self.assertIn("Inference", dsl_module.__all__)
        self.assertTrue(hasattr(dsl_module, "Inference"))
        self.assertNotIn("Derivation", dsl_module.__all__)
        self.assertFalse(hasattr(dsl_module, "Derivation"))


class FactGraphCreateTests(unittest.TestCase):
    def test_factgraph_create_matches_from_schema_classes_digest(self) -> None:
        created = FactGraph.create(schema_classes=[User])
        baseline = FactGraph.from_schema_classes([User])

        self.assertIsInstance(created, FactGraph)
        self.assertEqual(schema_digest(created.schema_ir), schema_digest(baseline.schema_ir))


class PublicParameterInventoryTests(unittest.TestCase):
    def test_what_if_flat_shells_are_removed_from_public_store(self) -> None:
        for method_name in (
            "check",
            "diagnose",
            "why_not",
            "check_fact_overlay",
        ):
            with self.subTest(method_name=method_name):
                self.assertFalse(hasattr(SDKStore, method_name))

    def test_eval_namespace_hard_cuts_compiled_escape_hatches(self) -> None:
        sdk = SDKStore([User])

        self.assertFalse(hasattr(sdk.eval, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk.eval, "accept_compiled"))
        self.assertFalse(hasattr(sdk, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk, "accept_compiled"))

    def test_accept_many_flat_shell_is_removed(self) -> None:
        self.assertFalse(hasattr(SDKStore, "accept_many"))


class PublicInferencePayloadTests(unittest.TestCase):
    def test_inference_to_authoring_payload_keeps_derivation_substrate_keys(self) -> None:
        payload = _inference().to_authoring_payload()

        self.assertIn("derivation_id", payload)
        self.assertNotIn("inference_id", payload)
        self.assertEqual(payload["derivation_id"], "inf.public_inference.tag")

    def test_validate_provenance_default_remains_derivation_v1(self) -> None:
        sdk = SDKStore([User])

        self.assertTrue(callable(sdk.schema.validate_provenance))


class PublicInferenceDocsTests(unittest.TestCase):
    def test_sdk_rules_doc_file_renamed_to_inferences(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        sdk_docs = repo_root / "src" / "factgraph" / "sdk" / "docs"

        self.assertTrue((sdk_docs / "03_rules_and_inferences.en.md").exists())
        self.assertFalse((sdk_docs / "03_rules_and_derivations.en.md").exists())


class PublicInferenceDeferralGuards(unittest.TestCase):
    def test_fg_inferences_namespace_is_persistence_only_after_authoring_facade(self) -> None:
        sdk = SDKStore([User])

        self.assertTrue(hasattr(sdk, "inferences"))
        for method in ("inspect", "run", "evaluate", "accept"):
            with self.subTest(method=method):
                self.assertFalse(hasattr(sdk.inferences, method))

    def test_no_derivation_ref_or_inference_ref_in_factgraph_sdk(self) -> None:
        sdk_module = _sdk_module()

        self.assertNotIn("DerivationRef", sdk_module.__all__)
        self.assertNotIn("InferenceRef", sdk_module.__all__)
        self.assertFalse(hasattr(sdk_module, "DerivationRef"))
        self.assertFalse(hasattr(sdk_module, "InferenceRef"))


class PublicInferenceGuardTests(unittest.TestCase):
    def test_rules_inspect_rule_still_works(self) -> None:
        inspected = SDKStore([User]).rules.inspect(_rule())

        self.assertEqual(inspected.occurrences[0].template_id, "public_inference_tag_seed")
        self.assertEqual(inspected.occurrences[0].atoms[0].field, "tag_seed")

    def test_rules_inspect_inference_uses_existing_shape(self) -> None:
        inspected = SDKStore([User]).rules.inspect(_inference())

        self.assertEqual(inspected["kind"], "Inference")
        self.assertEqual(inspected["branches"][0]["id"], "seed_path")

    def test_direct_runtime_evaluate_inference_still_works_without_registry(self) -> None:
        sdk = _make_sdk()

        candidates = sdk.eval.evaluate(_inference(), engine="native")

        self.assertTrue(candidates)

    def test_track3_semantics_imports_still_available(self) -> None:
        sdk_module = _sdk_module()

        self.assertTrue(hasattr(sdk_module, "ProbLogConfig"))
        self.assertTrue(hasattr(sdk_module, "PyReasonConfig"))
        self.assertTrue(hasattr(sdk_module, "SemanticsProfile"))

    def test_semantics_profile_inspection_still_available(self) -> None:
        sdk = SDKStore([User])
        profile = SemanticsProfile(name="profile.public_inference.problog", engine="problog")

        inspected = sdk.eval.preview_config(profile)

        self.assertEqual(inspected["engine"], "problog")
