"""Red + guard baseline for Track 2 public Semantics API redesign."""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

import kernel.application  # noqa: F401
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.evidence.write_protocol import set_field
from kernel.core.semantics import SemanticsProfile
from kernel.sdk import Branch, Inference, Pred, SDKStore, vars as sdk_vars
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStoreError
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
    tag_hint: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


def _sdk_module():
    return importlib.import_module("kernel.sdk")


def _problog_semantics_class():
    return getattr(_sdk_module(), "ProbLogSemantics")


def _pyreason_semantics_class():
    return getattr(_sdk_module(), "PyReasonSemantics")


def _problog_semantics(*, probabilities: dict[str, float] | None = None):
    return _problog_semantics_class()(
        branch_probabilities=probabilities or {"seed_path": 0.35},
    )


def _pyreason_semantics():
    return _pyreason_semantics_class()(
        timestep_delay=2,
        head_bound=[0.7, 0.9],
        temporal_projection={"mode": "fixed_timesteps", "timesteps": 4},
    )


def _problog_profile(*, probability: float = 0.35) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.track2.problog",
        engine="problog",
        rule_projection={"problog": [{"target": "branch:0", "kind": "branch_probability", "value": probability}]},
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
    set_field(
        sdk.ledger,
        pred_id="user:tag_hint",
        e_ref=alice_ref,
        rest_terms=[("string", "trial")],
        meta={"source": "test", "confidence": 1.0},
    )
    return sdk


def _single_branch_derivation() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="drv.track2.single",
            version="v1",
            where=[Pred("user:tag_seed", u, tag)],
            target="user:tag",
            head_vars=[u, tag],
        )


def _two_branch_derivation() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="drv.track2.branches",
            version="v1",
            where=[
                Branch([Pred("user:tag_seed", u, tag)], id="seed_path"),
                Branch([Pred("user:tag_hint", u, tag)]),
            ],
            target="user:tag",
            head_vars=[u, tag],
        )


def _pyreason_derivation() -> Inference:
    with sdk_vars("u", "name", "risk") as (u, name, risk):
        return Inference(
            id="drv.track2.pyreason",
            version="v1",
            where=[Branch([Pred("user:name", u, name), Pred("user:risk_score", u, risk)], id="sensor_path")],
            target="user:popular",
            head_vars=[u],
        )


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.track2.runtime_tag",
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


class PublicSemanticsExportTests(unittest.TestCase):
    def test_kernel_sdk_exports_public_semantics_wrappers(self) -> None:
        sdk_module = _sdk_module()

        self.assertIn("ProbLogSemantics", sdk_module.__all__)
        self.assertIn("PyReasonSemantics", sdk_module.__all__)
        self.assertEqual(len(sdk_module.__all__), 40)

    def test_problog_semantics_exposes_engine_metadata(self) -> None:
        semantics = _problog_semantics()

        self.assertEqual(semantics.engine, "problog")
        self.assertEqual(semantics.branch_probabilities["seed_path"], 0.35)

    def test_pyreason_semantics_exposes_engine_metadata(self) -> None:
        semantics = _pyreason_semantics()

        self.assertEqual(semantics.engine, "pyreason")
        self.assertEqual(semantics.timestep_delay, 2)
        self.assertEqual(tuple(semantics.head_bound), (0.7, 0.9))

    def test_pyreason_semantics_accepts_branch_bounds_after_track3_post(self) -> None:
        semantics = _pyreason_semantics_class()(branch_bounds={"sensor_path": [0.7, 0.9]})

        self.assertEqual(semantics.branch_bounds["sensor_path"], (0.7, 0.9))


class EngineAutoDerivationTests(unittest.TestCase):
    def test_no_engine_and_no_semantics_defaults_to_native(self) -> None:
        sdk = _make_sdk()

        candidates = sdk.eval.evaluate(_single_branch_derivation())

        self.assertEqual(len(candidates), 1)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_no_engine_with_problog_semantics_derives_problog(self, mock_run) -> None:
        sdk = _make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(_two_branch_derivation(), semantics=_problog_semantics())

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.35::rule_body_0", seen["program"])

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_explicit_matching_engine_with_problog_semantics_is_allowed(self, mock_run) -> None:
        sdk = _make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(
            _two_branch_derivation(),
            engine="problog",
            semantics=_problog_semantics(probabilities={"b1": 0.8}),
        )

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.8::rule_body_1", seen["program"])

    def test_explicit_mismatched_engine_rejects_with_anchor(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_two_branch_derivation(), engine="pyreason", semantics=_problog_semantics())

        self.assertIn("engine='pyreason' does not match semantics.engine='problog'", str(ctx.exception))

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_semantics_profile_without_engine_derives_profile_engine(self, mock_run) -> None:
        sdk = _make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(_single_branch_derivation(), semantics=_problog_profile(probability=0.25))

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.25::rule_body_0", seen["program"])

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_pyreason_empty)
    def test_no_engine_with_pyreason_semantics_derives_pyreason(self, mock_run) -> None:
        sdk = _make_sdk()

        sdk.eval.evaluate(_pyreason_derivation(), semantics=_pyreason_semantics())

        rules = mock_run.call_args.kwargs["rules"]
        self.assertEqual(
            rules,
            [("popular(u) : [0.7, 0.9] <-2 name(u), risk_score(u)", "derived_popular")],
        )
        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 4)


class BranchIdLoweringTests(unittest.TestCase):
    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_problog_semantics_resolves_explicit_and_fallback_branch_ids(self, mock_run) -> None:
        sdk = _make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return _mock_problog_output(sdk)

        mock_run.side_effect = _fake_run

        sdk.eval.evaluate(
            _two_branch_derivation(),
            semantics=_problog_semantics(probabilities={"seed_path": 0.35, "b1": 0.8}),
        )

        self.assertIn("0.35::rule_body_0", seen["program"])
        self.assertIn("0.8::rule_body_1", seen["program"])

    def test_problog_semantics_rejects_unknown_branch_id(self) -> None:
        sdk = _make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(
                _two_branch_derivation(),
                semantics=_problog_semantics(probabilities={"missing_path": 0.5}),
            )

        self.assertIn("unknown branch id", str(ctx.exception))


class InspectSemanticsWrapperTests(unittest.TestCase):
    def test_inspect_semantics_accepts_wrapper_and_returns_lowered_profile_preview(self) -> None:
        sdk = _make_sdk()

        inspected = sdk.eval.inspect_semantics(_problog_semantics(probabilities={"seed_path": 0.35}))

        self.assertEqual(inspected["engine"], "problog")
        self.assertEqual(inspected["semantics_type"], "ProbLogSemantics")
        self.assertIn("lowered_profile", inspected)
        self.assertEqual(inspected["lowered_profile"]["engine"], "problog")


class PublicBoundaryTests(unittest.TestCase):
    def test_evaluate_compiled_is_removed_from_public_sdk_surface(self) -> None:
        sdk = _make_sdk()

        self.assertFalse(hasattr(sdk.eval, "evaluate_compiled"))
        self.assertFalse(hasattr(sdk, "evaluate_compiled"))

    def test_service_rejects_lightweight_semantics_json_shape(self) -> None:
        reset_runtime_sessions_for_tests()
        sdk = _make_sdk()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        session_id = str(open_resp["session"]["session_id"])
        alice_ref = sdk.ref(User, user_id="Alice")
        try:
            write_resp = write_runtime_fact(
                session_id,
                {"pred_id": "user:tag_seed", "e_ref": alice_ref, "rest_terms": [["string", "vip"]]},
                kind="add",
            )
            self.assertTrue(write_resp["ok"], write_resp)
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "problog",
                    "semantics": {
                        "type": "problog",
                        "branch_probabilities": {"b0": 0.35},
                    },
                    "inference": _runtime_derivation_payload(),
                },
            )
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

        self.assertFalse(resp["ok"], resp)
        self.assertIn("service semantics accepts SemanticsProfile shape only in Track 2", _first_error_message(resp))

    def test_shells_continue_rejecting_public_wrapper_semantics(self) -> None:
        sdk = _make_sdk()
        semantics = _problog_semantics()
        shell_calls = (
            lambda: sdk.what_if.check(_single_branch_derivation(), {"$u": "Alice", "$tag": "vip"}, semantics=semantics),
            lambda: sdk.what_if.diagnose(_single_branch_derivation(), {"$u": "Alice", "$tag": "vip"}, semantics=semantics),
            lambda: sdk.what_if.fact_overlay.check(
                _single_branch_derivation(),
                {"$u": "Alice", "$tag": "vip"},
                overlay={"assertions": []},
                semantics=semantics,
            ),
            lambda: sdk.what_if.why_not(
                _single_branch_derivation(),
                [{"$u": "Alice", "$tag": "vip"}],
                semantics=semantics,
            ),
        )

        for call in shell_calls:
            with self.subTest(call=call):
                with self.assertRaises(SDKStoreError) as ctx:
                    call()

                self.assertIn("semantics= is not accepted", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
