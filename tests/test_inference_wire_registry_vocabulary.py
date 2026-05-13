"""Red + guard baseline for inference wire/registry vocabulary."""

from __future__ import annotations

from dataclasses import fields
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.routing import APIRoute

from factpy.application.protocol.derivation import CompiledDerivationPlan, DerivationEvaluateRequest
from factpy.authoring.registry_fs import FileAuthoringRegistry
from factpy.core.derivation.candidates import CandidateSet
from factpy.core.store.runtime import Store
from factpy.sdk import FactGraph, Inference, Pred, vars as sdk_vars
from factpy.sdk.registry import SDKRegistry
from factpy.sdk.schema import Entity, Field, Identity
from factpy.service import registry_v1
from factpy.service.app_v1 import app
from factpy.service.runtime_v1 import (
    _candidate_to_dict,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _runtime_inference_payload(*, inference_id: str = "inf.wire.tag") -> dict[str, object]:
    with sdk_vars("u", "tag") as (u, tag):
        inference = Inference(
            id=inference_id,
            version="v1",
            where=[Pred("user:tag_seed", u, tag)],
            target="user:tag",
            head_vars=[u, tag],
        )
    return inference.to_authoring_payload()


def _open_runtime_session() -> tuple[str, str]:
    reset_runtime_sessions_for_tests()
    fg = FactGraph.create(schema_classes=[User])
    resp = open_runtime_session({"schema_ir": fg.schema_ir})
    if not resp.get("ok"):
        raise AssertionError(resp)
    session_id = str(resp["session"]["session_id"])
    user_ref = fg.ref(User, user_id="Alice")
    return session_id, user_ref


def _first_error_path(resp: dict[str, object]) -> str:
    errors = resp.get("errors")
    if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
        raise AssertionError(f"response has no structured errors: {resp!r}")
    return str(errors[0].get("path"))


class ServiceRouteVocabularyTests(unittest.TestCase):
    def test_runtime_and_registry_routes_use_inference_vocabulary(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods or ())))
            for route in app.routes
            if isinstance(route, APIRoute)
        }

        self.assertIn(("/v1/runtime/sessions/{session_id}/inferences/evaluate", ("POST",)), routes)
        self.assertIn(("/v1/runtime/sessions/{session_id}/inferences/accept", ("POST",)), routes)
        self.assertIn(("/v1/registry/inferences/read", ("POST",)), routes)

    def test_derivation_routes_are_hard_cut(self) -> None:
        paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

        self.assertNotIn("/v1/runtime/sessions/{session_id}/derivations/evaluate", paths)
        self.assertNotIn("/v1/runtime/sessions/{session_id}/derivations/accept", paths)
        self.assertNotIn("/v1/registry/derivations/read", paths)


class RuntimeInferenceWireTests(unittest.TestCase):
    def test_evaluate_accepts_inference_request_key(self) -> None:
        session_id, _ = _open_runtime_session()

        resp = evaluate_runtime_derivation(
            session_id,
            {"engine": "native", "inference": _runtime_inference_payload()},
        )

        self.assertTrue(resp["ok"], resp)

    def test_evaluate_rejects_derivation_request_key_with_inference_path(self) -> None:
        session_id, _ = _open_runtime_session()

        resp = evaluate_runtime_derivation(
            session_id,
            {"engine": "native", "derivation": _runtime_inference_payload()},
        )

        self.assertFalse(resp["ok"], resp)
        self.assertIn("$.inference", _first_error_path(resp))

    def test_evaluate_response_envelope_uses_inference_id(self) -> None:
        session_id, user_ref = _open_runtime_session()
        write_resp = write_runtime_fact(
            session_id,
            {"pred_id": "user:tag_seed", "e_ref": user_ref, "rest_terms": [["string", "vip"]]},
            kind="add",
        )
        self.assertTrue(write_resp["ok"], write_resp)

        resp = evaluate_runtime_derivation(
            session_id,
            {"engine": "native", "inference": _runtime_inference_payload()},
        )

        self.assertTrue(resp["ok"], resp)
        evaluation = resp["evaluation"]
        self.assertIn("inference_id", evaluation)
        self.assertNotIn("derivation_id", evaluation)


class RegistryServiceVocabularyTests(unittest.TestCase):
    def test_registry_service_exposes_inference_read_function(self) -> None:
        self.assertTrue(hasattr(registry_v1, "read_registry_inference"))
        self.assertFalse(hasattr(registry_v1, "read_registry_derivation"))

    def test_registry_inference_read_uses_inference_key_and_response(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.register_inference_spec(_runtime_inference_payload(inference_id="inf.registry.read"))

            resp = registry_v1.read_registry_inference(
                {
                    "root_dir": tmp_dir,
                    "inference_id": "inf.registry.read",
                    "version": "v1",
                }
            )

        self.assertTrue(resp["ok"], resp)
        self.assertIn("inference_spec", resp)
        self.assertNotIn("derivation_spec", resp)


class RegistryStorageVocabularyTests(unittest.TestCase):
    def test_file_authoring_registry_methods_use_inference_vocabulary(self) -> None:
        expected = (
            "register_inference_spec",
            "preview_register_inference_spec",
            "list_inference_ids",
            "list_inference_versions",
            "get_latest_inference_spec",
            "read_inference_spec",
        )
        stale = (
            "register_derivation_spec",
            "preview_register_derivation_spec",
            "list_derivation_ids",
            "list_derivation_versions",
            "get_latest_derivation_spec",
            "read_derivation_spec",
        )

        self.assertEqual([name for name in expected if not hasattr(FileAuthoringRegistry, name)], [])
        self.assertEqual([name for name in stale if hasattr(FileAuthoringRegistry, name)], [])

    def test_registry_storage_uses_inference_manifest_path_and_json(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))

            result = registry.register_inference_spec(_runtime_inference_payload(inference_id="inf.storage"))
            manifest = registry.read_manifest()
            spec_path = Path(tmp_dir) / str(result["path"])
            spec_payload = json.loads(spec_path.read_text(encoding="utf-8"))

        self.assertEqual(result["kind"], "inference")
        self.assertEqual(result["inference_id"], "inf.storage")
        self.assertNotIn("derivation_id", result)
        self.assertTrue(str(result["path"]).startswith("inferences/"))
        self.assertIn("inferences", manifest)
        self.assertNotIn("derivations", manifest)
        self.assertEqual(manifest["inferences"][0]["inference_id"], "inf.storage")
        self.assertIn("inference_id", spec_payload)
        self.assertNotIn("derivation_id", spec_payload)

    def test_registry_read_translates_inference_json_to_compiler_substrate(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.register_inference_spec(_runtime_inference_payload(inference_id="inf.translate"))

            payload = registry.read_inference_spec("inf.translate", "v1")

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertIn("derivation_id", payload)
        self.assertNotIn("inference_id", payload)
        self.assertEqual(payload["derivation_id"], "inf.translate")


class SDKRegistryVocabularyTests(unittest.TestCase):
    def test_sdk_registry_methods_use_inference_vocabulary(self) -> None:
        expected = (
            "register_inference_spec",
            "register_inference",
            "list_inference_ids",
            "list_inference_versions",
            "get_latest_inference_spec",
            "read_inference_spec",
        )
        stale = (
            "register_derivation_spec",
            "register_derivation",
            "list_derivation_ids",
            "list_derivation_versions",
            "get_latest_derivation_spec",
            "read_derivation_spec",
        )

        self.assertEqual([name for name in expected if not hasattr(SDKRegistry, name)], [])
        self.assertEqual([name for name in stale if hasattr(SDKRegistry, name)], [])


class InferenceWireRegistryGuardTests(unittest.TestCase):
    def test_candidate_payload_stays_derivation_substrate(self) -> None:
        candidate = CandidateSet(
            derivation_id="inf.guard",
            derivation_version="v1",
            run_id="run.guard",
            target="user:tag",
            key_tuple_digest="sha256:" + "0" * 64,
            tup_digest=None,
            payload={"pred_id": "user:tag", "terms": []},
            support_digest="sha256:" + "1" * 64,
            support_kind="native_binding_v1",
            generated_at=1,
            state="generated",
        )

        as_dict = _candidate_to_dict(candidate)

        self.assertEqual(candidate.derivation_id, "inf.guard")
        self.assertEqual(candidate.derivation_version, "v1")
        self.assertIn("derivation_id", as_dict)
        self.assertIn("derivation_version", as_dict)
        self.assertNotIn("inference_id", as_dict)

    def test_inference_payload_keeps_compiler_derivation_id_key(self) -> None:
        payload = _runtime_inference_payload(inference_id="inf.compiler")

        self.assertEqual(payload["derivation_id"], "inf.compiler")
        self.assertNotIn("inference_id", payload)

    def test_application_and_core_derivation_substrate_names_remain(self) -> None:
        plan_fields = {field.name for field in fields(CompiledDerivationPlan)}
        request_fields = {field.name for field in fields(DerivationEvaluateRequest)}
        evaluate_params = inspect.signature(Store.evaluate).parameters
        accept_params = inspect.signature(Store.accept).parameters

        self.assertIn("derivation_id", plan_fields)
        self.assertNotIn("inference_id", plan_fields)
        self.assertIn("plans", request_fields)
        self.assertIn("derivation_id", evaluate_params)
        self.assertIn("derivation_id", accept_params)

    def test_blueprint1_public_sdk_surface_remains(self) -> None:
        import factpy.sdk as sdk_module

        self.assertTrue(hasattr(sdk_module, "Inference"))
        self.assertFalse(hasattr(sdk_module, "Derivation"))
        self.assertTrue(hasattr(sdk_module.FactGraph, "create"))
