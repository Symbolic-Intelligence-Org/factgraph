"""Red-baseline tests for Track 3 / A1 Inference.mode decomposition."""

from __future__ import annotations

import unittest
from dataclasses import fields
from unittest.mock import patch

from kernel.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from kernel.core.store._support import PROBLOG_PROVENANCE_KIND
from kernel.sdk.dsl import Inference, Pred, vars as sdk_vars
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore
from service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)

import kernel.adapters.problog  # noqa: F401,E402


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _authoring_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a1.user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [("pred", "user:tag_seed", ["$u", "$tag"])],
    }


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a1.runtime_user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
    }


class SDKDerivationModeSurfaceTests(unittest.TestCase):
    def test_derivation_dataclass_has_no_public_mode_field(self) -> None:
        self.assertNotIn("mode", {field.name for field in fields(Inference)})

    def test_derivation_constructor_rejects_mode_keyword(self) -> None:
        with sdk_vars("u", "tag") as (u, tag):
            with self.assertRaises(TypeError):
                Inference(
                    id="drv.a1.sdk_user_tag",
                    version="v1",
                    where=[Pred("user:tag_seed", u, tag)],
                    target="user:tag",
                    head_vars=[u, tag],
                    mode="problog",
                )

    def test_derivation_payload_emits_no_definition_time_mode(self) -> None:
        with sdk_vars("u", "tag") as (u, tag):
            derivation = Inference(
                id="drv.a1.sdk_user_tag",
                version="v1",
                where=[Pred("user:tag_seed", u, tag)],
                target="user:tag",
                head_vars=[u, tag],
            )

        self.assertNotIn("mode", derivation.to_authoring_payload())


class AuthoringDerivationModeTests(unittest.TestCase):
    def test_authoring_derivation_mode_key_is_rejected(self) -> None:
        payload = dict(_authoring_derivation_payload())
        payload["mode"] = "problog"

        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(payload)

        self.assertEqual(ctx.exception.path, "$.mode")
        self.assertIn("call-site", str(ctx.exception))

    def test_compiled_payload_keeps_internal_native_default(self) -> None:
        compiled = compile_authoring_derivation_v1(_authoring_derivation_payload())

        self.assertEqual(compiled["mode"], "native")


class ServiceDerivationModeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> tuple[str, SDKStore, str]:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        session_id = open_resp["session"]["session_id"]
        write_resp = write_runtime_fact(
            session_id,
            {
                "pred_id": "user:tag_seed",
                "e_ref": alice_ref,
                "rest_terms": [["string", "vip"]],
            },
            kind="add",
        )
        self.assertTrue(write_resp["ok"], write_resp)
        return session_id, sdk, alice_ref

    def _mock_problog_output(self, alice_ref: str) -> str:
        return "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("vip","{alice_ref}") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("vip","{alice_ref}") {{0.00019}} [at 4:7]',
                f'  result answer("vip","{alice_ref}") ("vip","{alice_ref}") {{{{}}}} {{0.00060}} []',
                f' complete answer("vip","{alice_ref}") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("vip","{alice_ref}"):\t0.42',
            ]
        )

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_service_derivation_uses_request_level_engine(self, mock_run) -> None:
        session_id, _sdk, alice_ref = self._open_session()
        mock_run.return_value = self._mock_problog_output(alice_ref)
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "problog",
                    "inference": _runtime_derivation_payload(),
                },
            )

            self.assertTrue(resp["ok"], resp)
            mock_run.assert_called_once()
            candidate = resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["support_kind"], PROBLOG_PROVENANCE_KIND)
            self.assertEqual(resp["meta"]["mode"], "problog")
        finally:
            close_runtime_session(session_id)

    def test_service_rejects_definition_time_derivation_mode(self) -> None:
        session_id, _sdk, _alice_ref = self._open_session()
        derivation = dict(_runtime_derivation_payload())
        derivation["mode"] = "native"
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "native",
                    "inference": derivation,
                },
            )

            self.assertFalse(resp["ok"], resp)
            self.assertEqual(resp["errors"][0]["path"], "$.inference.mode")
            self.assertIn("call-site", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)


if __name__ == "__main__":
    unittest.main()
