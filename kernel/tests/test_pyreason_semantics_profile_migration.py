"""Red + guard baseline for Track 3 / D PyReason SemanticsProfile consumption."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import kernel.application  # noqa: F401
import kernel.adapters.pyreason  # noqa: F401
from kernel.adapters.pyreason.rule_ext import PyReasonRuleExt, compile_pyreason_rule
from kernel.adapters.pyreason.runner import PyReasonRunConfig, PyReasonRunResult
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.evidence.write_protocol import set_field
from kernel.core.semantics import SemanticsProfile
from kernel.sdk.dsl import Branch, Inference, Pred, Rule, vars as sdk_vars
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    risk_score: float = Field(cardinality="single")
    popular: str = Field(cardinality="single")


def _resolve_pyreason_engine_ext():
    from kernel.adapters.pyreason import rule_ext

    return getattr(rule_ext, "resolve_pyreason_engine_ext")


def _schema_ir() -> dict[str, Any]:
    return SDKStore([User]).schema_ir


def _where_two_body_atoms() -> list[list[tuple[str, str, list[str]]]]:
    return [
        [
            ("pred", "user:name", ["$u", "$name"]),
            ("pred", "user:risk_score", ["$u", "$risk"]),
        ]
    ]


def _where_with_non_pred_atom() -> list[list[tuple[str, str, list[str]] | tuple[str, str, str]]]:
    return [[("eq", "$name", "Alice")]]


def _profile(
    *,
    engine: str = "pyreason",
    rule_entries: list[dict[str, object]] | None = None,
    temporal_projection: dict[str, object] | None = None,
) -> SemanticsProfile:
    kwargs: dict[str, object] = {
        "name": "profile.d.pyreason",
        "engine": engine,
        "rule_projection": {
            "pyreason": rule_entries
            or [
                {"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]},
                {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]},
                {"target": "rule", "kind": "timestep_delay", "value": 2},
            ]
        },
    }
    if temporal_projection is not None:
        kwargs["temporal_projection"] = temporal_projection
    return SemanticsProfile(**kwargs)


def _make_sdk_with_valid_times() -> SDKStore:
    sdk = SDKStore([User])
    alice_ref = sdk.ref(User, user_id="Alice")
    bob_ref = sdk.ref(User, user_id="Bob")
    carol_ref = sdk.ref(User, user_id="Carol")
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=alice_ref,
        rest_terms=[("string", "Alice")],
        meta={"source": "test", "valid_from": "2026-01-10", "valid_to": "2026-02-10"},
    )
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=bob_ref,
        rest_terms=[("string", "Bob")],
        meta={"source": "test", "valid_to": "2026-03-01"},
    )
    set_field(
        sdk.ledger,
        pred_id="user:name",
        e_ref=carol_ref,
        rest_terms=[("string", "Carol")],
        meta={"source": "test", "valid_from": "2026-02-01"},
    )
    return sdk


def _make_derivation() -> Inference:
    with sdk_vars("u", "name") as (u, name):
        return Inference(
            id="drv.d.pyreason_popular",
            version="v1",
            where=[Pred("user:name", u, name)],
            target="user:popular",
            head_vars=[u],
        )


def _mock_run_empty(session, *, rules=None, rule_defs=None, facts=None, fact_defs=None, config=None):
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


class PyReasonSemanticsProfileResolverTests(unittest.TestCase):
    def test_profile_rule_projection_materializes_pyreason_rule_ext(self) -> None:
        resolved = _resolve_pyreason_engine_ext()(
            where=_where_two_body_atoms(),
            schema_ir=_schema_ir(),
            engine_ext=None,
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, PyReasonRuleExt)
        self.assertEqual(resolved.body_predicate_bounds["user:name"], (0.6, 1.0))
        self.assertEqual(tuple(resolved.head_bound or ()), (0.7, 0.9))
        self.assertEqual(resolved.timestep_delay, 2)

    def test_profile_rule_projection_requires_pyreason_engine_at_consumption(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(engine="problog"),
            )

        self.assertIn("SemanticsProfile.engine='pyreason'", str(ctx.exception))

    def test_profile_rule_projection_rejects_invalid_kind(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[{"target": "body_atom:0:0", "kind": "branch_probability", "value": [0.6, 1.0]}]
                ),
            )

        self.assertIn("interval_threshold", str(ctx.exception))

    def test_profile_rule_projection_rejects_invalid_body_target_shape(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[{"target": "body_atom:0", "kind": "interval_threshold", "value": [0.6, 1.0]}]
                ),
            )

        self.assertIn("body_atom:{branch}:{atom}", str(ctx.exception))

    def test_profile_rule_projection_rejects_out_of_range_body_atom(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[{"target": "body_atom:0:9", "kind": "interval_threshold", "value": [0.6, 1.0]}]
                ),
            )

        self.assertIn("body atom", str(ctx.exception))

    def test_profile_rule_projection_rejects_non_pred_body_atom(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_with_non_pred_atom(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[{"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]}]
                ),
            )

        self.assertIn("pred", str(ctx.exception))

    def test_profile_rule_projection_rejects_invalid_interval_values(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[{"target": "head:0", "kind": "interval", "value": [0.9, 0.2]}]
                ),
            )

        self.assertIn("0 <= lower <= upper <= 1", str(ctx.exception))

    def test_profile_rule_projection_rejects_duplicate_conflicting_targets(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=None,
                semantics_profile=_profile(
                    rule_entries=[
                        {"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]},
                        {"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.7, 1.0]},
                    ]
                ),
            )

        self.assertIn("duplicate", str(ctx.exception))

    def test_matching_profile_and_explicit_pyreason_rule_ext_are_allowed(self) -> None:
        resolved = _resolve_pyreason_engine_ext()(
            where=_where_two_body_atoms(),
            schema_ir=_schema_ir(),
            engine_ext=PyReasonRuleExt(
                timestep_delay=2,
                body_predicate_bounds={"user:name": (0.6, 1.0)},
                head_bound=(0.7, 0.9),
            ),
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, PyReasonRuleExt)
        self.assertEqual(resolved.timestep_delay, 2)

    def test_conflicting_profile_and_explicit_pyreason_rule_ext_rejects_with_carrier_names(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _resolve_pyreason_engine_ext()(
                where=_where_two_body_atoms(),
                schema_ir=_schema_ir(),
                engine_ext=PyReasonRuleExt(
                    body_predicate_bounds={"user:name": (0.8, 1.0)},
                ),
                semantics_profile=_profile(
                    rule_entries=[{"target": "body_atom:0:0", "kind": "interval_threshold", "value": [0.6, 1.0]}]
                ),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.rule_projection.pyreason", message)
        self.assertIn("PyReasonRuleExt", message)


class PyReasonTemporalProjectionTests(unittest.TestCase):
    def test_fixed_timesteps_profile_is_accepted(self) -> None:
        profile = _profile(rule_entries=[], temporal_projection={"mode": "fixed_timesteps", "timesteps": 4})

        self.assertEqual(profile.temporal_projection["mode"], "fixed_timesteps")
        self.assertEqual(profile.temporal_projection["timesteps"], 4)

    def test_unknown_temporal_mode_still_rejects(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _profile(rule_entries=[], temporal_projection={"mode": "custom_timeline", "steps": []})

        self.assertIn("custom_timeline", str(ctx.exception))

    def test_valid_time_boundaries_profile_is_accepted(self) -> None:
        profile = _profile(
            rule_entries=[],
            temporal_projection={"mode": "valid_time_boundaries", "universe": ["2026-01-01", "2026-12-31"]},
        )

        self.assertEqual(profile.temporal_projection["mode"], "valid_time_boundaries")
        self.assertEqual(profile.temporal_projection["universe"], ["2026-01-01", "2026-12-31"])

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_empty)
    def test_fixed_timesteps_profile_drives_pyreason_run_config(self, mock_run) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            semantics_profile=_profile(rule_entries=[], temporal_projection={"mode": "fixed_timesteps", "timesteps": 4}),
        )

        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 4)

    def test_fixed_timesteps_conflicts_with_engine_options_timesteps(self) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        with self.assertRaises(ValueError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="pyreason",
                engine_options={"timesteps": 5},
                semantics_profile=_profile(rule_entries=[], temporal_projection={"mode": "fixed_timesteps", "timesteps": 4}),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.temporal_projection.fixed_timesteps", message)
        self.assertIn("engine_options.timesteps", message)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_empty)
    def test_valid_time_boundaries_map_valid_meta_to_active_steps(self, mock_run) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            semantics_profile=_profile(
                rule_entries=[],
                temporal_projection={"mode": "valid_time_boundaries", "universe": ["2026-01-01", "2026-12-31"]},
            ),
        )

        session = mock_run.call_args.args[0]
        rows = {(fact["value"], fact["active_from"], fact["active_to"]) for fact in session.node_facts}
        self.assertIn(("Alice", 1, 3), rows)
        self.assertIn(("Bob", 0, 4), rows)
        self.assertIn(("Carol", 2, None), rows)
        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 5)

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_empty)
    def test_valid_time_boundaries_without_fact_times_uses_universe_only(self, mock_run) -> None:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test"},
        )
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            semantics_profile=_profile(
                rule_entries=[],
                temporal_projection={"mode": "valid_time_boundaries", "universe": ["2026-01-01", "2026-12-31"]},
            ),
        )

        session = mock_run.call_args.args[0]
        self.assertEqual(session.node_facts[0]["active_from"], 0)
        self.assertIsNone(session.node_facts[0]["active_to"])
        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 1)

    def test_valid_time_boundaries_conflicts_with_engine_options_timesteps(self) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        with self.assertRaises(ValueError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="pyreason",
                engine_options={"timesteps": 2},
                semantics_profile=_profile(
                    rule_entries=[],
                    temporal_projection={"mode": "valid_time_boundaries", "universe": ["2026-01-01", "2026-12-31"]},
                ),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.temporal_projection.valid_time_boundaries", message)
        self.assertIn("engine_options.timesteps", message)


class PyReasonSemanticsProfileCoreEvaluateTests(unittest.TestCase):
    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_empty)
    def test_core_store_evaluate_semantics_profile_drives_generated_rule(self, mock_run) -> None:
        sdk = _make_sdk_with_valid_times()
        with sdk_vars("u", "name", "risk") as (u, name, risk):
            derivation = Inference(
                id="drv.d.pyreason_popular",
                version="v1",
                where=[Branch([Pred("user:name", u, name), Pred("user:risk_score", u, risk)])],
                target="user:popular",
                head_vars=[u],
            )
        compiled = sdk._compile_derivation_input(derivation)[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            semantics_profile=_profile(),
        )

        rules = mock_run.call_args.kwargs["rules"]
        self.assertEqual(
            rules,
            [("popular(u) : [0.7, 0.9] <-2 name(u) : [0.6, 1.0], risk_score(u)", "derived_popular")],
        )

    def test_core_store_evaluate_rejects_pyreason_profile_outside_pyreason_mode(self) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        with self.assertRaises(ValueError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="native",
                semantics_profile=_profile(rule_entries=[]),
            )

        self.assertIn("mode='pyreason'", str(ctx.exception))

    def test_core_store_evaluate_rejects_profile_engine_mismatch(self) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        with self.assertRaises(ValueError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="pyreason",
                semantics_profile=SemanticsProfile(name="profile.d.problog", engine="problog"),
            )

        self.assertIn("SemanticsProfile.engine='pyreason'", str(ctx.exception))


class PyReasonSemanticsProfileGuardTests(unittest.TestCase):
    def test_existing_pyreason_rule_ext_compile_survives(self) -> None:
        with sdk_vars("u", "name") as (u, name):
            rule = Rule(
                id="rule.pyreason_guard",
                version="v1",
                select=[Pred("user:popular", u)],
                where=[Pred("user:name", u, name)],
            )

        compiled = compile_pyreason_rule(
            rule,
            engine_ext=PyReasonRuleExt(
                timestep_delay=2,
                body_predicate_bounds={"user:name": (0.5, 1.0)},
                head_bound=(0.8, 0.9),
            ),
        )

        self.assertEqual(compiled, ("popular(u) : [0.8, 0.9] <-2 name(u, name) : [0.5, 1.0]", "rule.pyreason_guard"))

    @patch("kernel.adapters.pyreason.engine_eval.run_pyreason", side_effect=_mock_run_empty)
    def test_existing_engine_options_timesteps_without_profile_survives(self, mock_run) -> None:
        sdk = _make_sdk_with_valid_times()
        compiled = sdk._compile_derivation_input(_make_derivation())[0]

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="pyreason",
            engine_options={"timesteps": 6},
        )

        config = mock_run.call_args.kwargs["config"]
        self.assertEqual(config.timesteps, 6)

    def test_problog_semantics_profile_consumption_survives(self) -> None:
        from kernel.adapters.problog.rule_ext import ProbLogRuleExt, resolve_problog_engine_ext

        resolved = resolve_problog_engine_ext(
            where=[[("pred", "user:name", ["$u", "$name"])]],
            engine_ext=None,
            semantics_profile=SemanticsProfile(
                name="profile.d.problog_guard",
                engine="problog",
                rule_projection={
                    "problog": [{"target": "branch:0", "kind": "branch_probability", "value": 0.5}]
                },
            ),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.5,))

    def test_pyreason_exporter_remains_profile_agnostic(self) -> None:
        import kernel.adapters.pyreason.where_compile as where_compile

        source = Path(where_compile.__file__).read_text(encoding="utf-8")
        self.assertNotIn("SemanticsProfile", source)


if __name__ == "__main__":
    unittest.main()
