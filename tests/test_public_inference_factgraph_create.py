"""Red + guard baseline for public Inference naming and FactGraph.create."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import unittest

from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.semantics import SemanticsProfile
from factgraph.sdk import Branch, FactGraph, Pred, Rule, SDKStore, vars as sdk_vars
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
    alice_ref = sdk.ref(User, user_id="Alice")
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test", "confidence": 1.0},
    )
    set_field(
        sdk.ledger,
        pred_id="user:tag_seed",
        e_ref=alice_ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test", "confidence": 1.0},
    )
    return sdk


def _rule() -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id="rule.public_inference.tag_seed",
            version="v1",
            select=[u, tag],
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            expose=True,
        )


def _inference():
    Inference = _inference_class()
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.public_inference.tag",
            version="v1",
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
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
    def test_what_if_public_signatures_use_inference_parameter(self) -> None:
        for method in (
            SDKStore.check,
            SDKStore.diagnose,
            SDKStore.why_not,
            SDKStore.check_fact_overlay,
        ):
            with self.subTest(method=method.__name__):
                params = inspect.signature(method).parameters

                self.assertIn("inference", params)
                self.assertNotIn("derivation", params)

    def test_eval_namespace_hard_cuts_compiled_escape_hatches(self) -> None:
        sdk = SDKStore([User])

        self.assertFalse(hasattr(sdk.eval, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk.eval, "accept_compiled"))
        self.assertFalse(hasattr(sdk, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk, "accept_compiled"))

    def test_accept_many_mode_keyword_is_out_of_scope_and_still_present(self) -> None:
        params = inspect.signature(SDKStore.accept_many).parameters

        self.assertIn("mode", params)


class PublicInferencePayloadTests(unittest.TestCase):
    def test_inference_to_authoring_payload_keeps_derivation_substrate_keys(self) -> None:
        payload = _inference().to_authoring_payload()

        self.assertIn("derivation_id", payload)
        self.assertNotIn("inference_id", payload)
        self.assertEqual(payload["derivation_id"], "inf.public_inference.tag")

    def test_validate_provenance_default_remains_derivation_v1(self) -> None:
        default = inspect.signature(SDKStore.validate_provenance).parameters["standard"].default

        self.assertEqual(default, "derivation_v1")


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
        for method in ("save", "load", "list", "get"):
            with self.subTest(method=method):
                self.assertTrue(hasattr(sdk.inferences, method))
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

        self.assertEqual(inspected["kind"], "Rule")
        self.assertEqual(inspected["branches"][0]["id"], "seed_path")

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

        self.assertTrue(hasattr(sdk_module, "ProbLogSemantics"))
        self.assertTrue(hasattr(sdk_module, "PyReasonSemantics"))
        self.assertTrue(hasattr(sdk_module, "SemanticsProfile"))

    def test_semantics_profile_inspection_still_available(self) -> None:
        sdk = SDKStore([User])
        profile = SemanticsProfile(name="profile.public_inference.problog", engine="problog")

        inspected = sdk.eval.inspect_semantics(profile)

        self.assertEqual(inspected["engine"], "problog")
