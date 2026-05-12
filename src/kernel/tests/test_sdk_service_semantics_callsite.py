"""Red + guard baseline for Track 3 / E SDK/service SemanticsProfile call-site."""

from __future__ import annotations

import importlib
import unittest
from dataclasses import fields
from unittest.mock import patch

import kernel.application  # noqa: F401
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.evidence.write_protocol import set_field
from kernel.core.semantics import SemanticsProfile
from kernel.sdk.dsl import Branch, Inference, Pred, vars as sdk_vars
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore, SDKStoreError
from service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    risk_score: float = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


def _problog_profile(*, engine: str = "problog", probability: float = 0.35) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.e.problog",
        engine=engine,
        rule_projection={"problog": [{"target": "branch:0", "kind": "branch_probability", "value": probability}]},
    )


def _pyreason_profile(*, engine: str = "pyreason") -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.e.pyreason",
        engine=engine,
        rule_projection={
            "pyreason": [
                {"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]},
                {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]},
                {"target": "rule", "kind": "timestep_delay", "value": 2},
            ]
        },
        temporal_projection={"mode": "fixed_timesteps", "timesteps": 4},
    )


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
        pred_id="user:risk_score",
        e_ref=alice_ref,
        rest_terms=[("float64", 0.7)],
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


def _problog_derivation() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="drv.e.problog_tag",
            version="v1",
            where=[Pred("user:tag_seed", u, tag)],
            target="user:tag",
            head_vars=[u, tag],
        )


def _pyreason_derivation() -> Inference:
    with sdk_vars("u", "name", "risk") as (u, name, risk):
        return Inference(
            id="drv.e.pyreason_popular",
            version="v1",
            where=[Branch([Pred("user:name", u, name), Pred("user:risk_score", u, risk)])],
            target="user:popular",
            head_vars=[u],
        )


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.e.runtime_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
    }


def _mock_problog_output(sdk: SDKStore) -> str:
    alice_ref = sdk.ref(User, user_id="Alice")
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


def _mock_pyreason_empty(session, *, rules=None, rule_defs=None, facts=None, fact_defs=None, config=None):
    del rules
    del rule_defs
    del facts
    del fact_defs
    return PyReasonRunResult(
        interpretation=None,
        trace=None,
        trace_dict={"engine": "pyreason", "trace_type": "event_log", "timesteps": 1},
        derived_session=PyReasonSession(session._schema_ir),
        config=config or PyReasonRunConfig(),
        elapsed_seconds=0.01,
    )


def _first_error_message(resp: dict[str, object]) -> str:
    error = resp["errors"][0]  # type: ignore[index]
    if isinstance(error, dict):
        details = error.get("details")
        if isinstance(details, dict) and isinstance(details.get("message"), str):
            return details["message"]
        if isinstance(error.get("message"), str):
            return error["message"]
    return str(error)


class SDKSemanticsCallsiteTests(unittest.TestCase):
    def test_kernel_sdk_exports_semantics_profile(self) -> None:
        sdk_module = importlib.import_module("kernel.sdk")

        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIs(sdk_module.SemanticsProfile, SemanticsProfile)

    def test_eval_namespace_inspect_semantics_wraps_core_helper(self) -> None:
        sdk = _make_sdk()

        inspected = sdk.eval.inspect_semantics(_problog_profile())

        self.assertEqual(inspected["engine"], "problog")
        self.assertTrue(inspected["uses"]["rule_projection"])

    def test_sdk_evaluate_rejects_mode_keyword_with_engine_anchor(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_problog_derivation(), mode="problog")

        self.assertIn("evaluate() does not accept mode= in E; use engine=", str(ctx.exception))

    def test_sdk_evaluate_rejects_semantics_profile_keyword_with_semantics_anchor(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_problog_derivation(), engine="problog", semantics_profile=_problog_profile())

        self.assertIn("evaluate() does not accept semantics_profile= in SDK; use semantics=", str(ctx.exception))

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_sdk_evaluate_problog_semantics_drives_exported_probability(self, mock_run) -> None:
        sdk = _make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(_problog_derivation(), engine="problog", semantics=_problog_profile())

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.35::rule_body_0", seen["program"])

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_pyreason_empty)
    def test_sdk_evaluate_pyreason_semantics_drives_generated_rule(self, mock_run) -> None:
        sdk = _make_sdk()

        sdk.eval.evaluate(_pyreason_derivation(), engine="pyreason", semantics=_pyreason_profile())

        rules = mock_run.call_args.kwargs["rules"]
        self.assertEqual(
            rules,
            [("popular(u) : [0.7, 0.9] <-2 name(u) : [0.6, 1.0], risk_score(u)", "derived_popular")],
        )
        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 4)

    def test_sdk_evaluate_rejects_native_profile_without_silent_ignore(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_problog_derivation(), engine="native", semantics=_problog_profile())

        self.assertIn("engine='native' does not consume SemanticsProfile", str(ctx.exception))

    def test_sdk_evaluate_rejects_souffle_profile_without_silent_ignore(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_problog_derivation(), engine="souffle", semantics=_problog_profile())

        self.assertIn("engine='souffle' does not consume SemanticsProfile", str(ctx.exception))

    def test_sdk_evaluate_rejects_profile_engine_mismatch(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_problog_derivation(), engine="pyreason", semantics=_problog_profile())

        self.assertIn("SemanticsProfile.engine='problog' does not match engine='pyreason'", str(ctx.exception))

    def test_sdk_evaluate_compiled_is_removed_from_public_surface(self) -> None:
        sdk = _make_sdk()

        self.assertFalse(hasattr(sdk.eval, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk, "evaluate_compiled"))


class ApplicationProtocolSemanticsCallsiteTests(unittest.TestCase):
    def test_derivation_evaluate_request_carries_semantics_profile(self) -> None:
        from kernel.application.protocol.derivation import CompiledDerivationPlan, DerivationEvaluateRequest

        request_fields = {field.name for field in fields(DerivationEvaluateRequest)}
        plan_fields = {field.name for field in fields(CompiledDerivationPlan)}

        self.assertIn("semantics_profile", request_fields)
        self.assertNotIn("semantics_profile", plan_fields)


class ServiceSemanticsCallsiteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.sdk = _make_sdk()
        open_resp = open_runtime_session({"schema_ir": self.sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        self.session_id = str(open_resp["session"]["session_id"])
        alice_ref = self.sdk.ref(User, user_id="Alice")
        write_resp = write_runtime_fact(
            self.session_id,
            {"pred_id": "user:tag_seed", "e_ref": alice_ref, "rest_terms": [["string", "vip"]]},
            kind="add",
        )
        self.assertTrue(write_resp["ok"], write_resp)

    def tearDown(self) -> None:
        close_runtime_session(self.session_id)
        reset_runtime_sessions_for_tests()

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_service_accepts_top_level_semantics_dict(self, mock_run) -> None:
        def _fake_run(pl_path, *, timeout, trace):
            return _mock_problog_output(self.sdk)

        mock_run.side_effect = _fake_run

        resp = evaluate_runtime_derivation(
            self.session_id,
            {
                "engine": "problog",
                "semantics": {
                    "name": "profile.e.service.problog",
                    "engine": "problog",
                    "rule_projection": {
                        "problog": [{"target": "branch:0", "kind": "branch_probability", "value": 0.35}]
                    },
                },
                "derivation": _runtime_derivation_payload(),
            },
        )

        self.assertTrue(resp["ok"], resp)
        self.assertEqual(resp["meta"]["mode"], "problog")

    def test_service_rejects_top_level_semantics_profile_keyword(self) -> None:
        resp = evaluate_runtime_derivation(
            self.session_id,
            {"engine": "problog", "semantics_profile": {"name": "x"}, "derivation": _runtime_derivation_payload()},
        )

        self.assertFalse(resp["ok"], resp)
        self.assertEqual(resp["errors"][0]["path"], "$.semantics_profile")
        self.assertIn("use semantics", _first_error_message(resp))

    def test_service_rejects_derivation_level_semantics(self) -> None:
        derivation = dict(_runtime_derivation_payload())
        derivation["semantics"] = {"name": "x"}

        resp = evaluate_runtime_derivation(self.session_id, {"engine": "problog", "derivation": derivation})

        self.assertFalse(resp["ok"], resp)
        self.assertEqual(resp["errors"][0]["path"], "$.derivation.semantics")

    def test_service_rejects_profile_engine_mismatch(self) -> None:
        resp = evaluate_runtime_derivation(
            self.session_id,
            {
                "engine": "pyreason",
                "semantics": {"name": "profile.e.service.problog", "engine": "problog"},
                "derivation": _runtime_derivation_payload(),
            },
        )

        self.assertFalse(resp["ok"], resp)
        self.assertIn("SemanticsProfile.engine='problog' does not match engine='pyreason'", _first_error_message(resp))


class ShellSemanticsRejectionTests(unittest.TestCase):
    def _assert_shell_rejects_profile_kwargs(self, call) -> None:
        for key in ("semantics", "semantics_profile"):
            with self.subTest(key=key):
                with self.assertRaises(SDKStoreError) as ctx:
                    call(**{key: _problog_profile()})

                self.assertIn(f"{key}= is not accepted", str(ctx.exception))

    def test_check_shell_rejects_profile_kwargs(self) -> None:
        sdk = _make_sdk()
        self._assert_shell_rejects_profile_kwargs(
            lambda **kwargs: sdk.what_if.check(_problog_derivation(), {"$u": "Alice", "$tag": "vip"}, **kwargs)
        )

    def test_diagnose_shell_rejects_profile_kwargs(self) -> None:
        sdk = _make_sdk()
        self._assert_shell_rejects_profile_kwargs(
            lambda **kwargs: sdk.what_if.diagnose(_problog_derivation(), {"$u": "Alice", "$tag": "vip"}, **kwargs)
        )

    def test_fact_overlay_shell_rejects_profile_kwargs(self) -> None:
        sdk = _make_sdk()
        self._assert_shell_rejects_profile_kwargs(
            lambda **kwargs: sdk.what_if.fact_overlay.check(
                _problog_derivation(),
                {"$u": "Alice", "$tag": "vip"},
                overlay={"assertions": []},
                **kwargs,
            )
        )

    def test_why_not_shell_rejects_profile_kwargs(self) -> None:
        sdk = _make_sdk()
        self._assert_shell_rejects_profile_kwargs(
            lambda **kwargs: sdk.what_if.why_not(
                _problog_derivation(),
                [{"$u": "Alice", "$tag": "vip"}],
                **kwargs,
            )
        )


class CoreConsumptionGuardTests(unittest.TestCase):
    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_core_problog_profile_consumption_survives(self, mock_run) -> None:
        sdk = _make_sdk()
        compiled = sdk._compile_derivation_input(_problog_derivation())[0]
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="problog",
            semantics_profile=_problog_profile(probability=0.45),
        )

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.45::rule_body_0", seen["program"])

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_pyreason_empty)
    def test_core_pyreason_profile_consumption_survives(self, mock_run) -> None:
        sdk = _make_sdk()
        compiled = sdk._compile_derivation_input(_pyreason_derivation())[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            semantics_profile=_pyreason_profile(),
        )

        rules = mock_run.call_args.kwargs["rules"]
        self.assertEqual(
            rules,
            [("popular(u) : [0.7, 0.9] <-2 name(u) : [0.6, 1.0], risk_score(u)", "derived_popular")],
        )

    def test_core_store_internal_mode_keyword_remains_supported(self) -> None:
        sdk = _make_sdk()
        compiled = sdk._compile_derivation_input(_problog_derivation())[0]

        candidates = sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="native",
        )

        self.assertEqual(len(candidates), 1)


if __name__ == "__main__":
    unittest.main()
