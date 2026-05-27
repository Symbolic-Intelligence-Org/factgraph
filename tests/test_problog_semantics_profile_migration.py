"""Red + guard baseline for Track 3 / C ProbLog SemanticsProfile consumption."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import factgraph.application as application  # noqa: F401
from factgraph.adapters.problog.problog_export import ProbLogExportError, _claim_probability
from factgraph.adapters.problog.rule_ext import ProbLogRuleExt, resolve_problog_engine_ext
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.semantics import SemanticsProfile
from factgraph.sdk.dsl import vars as sdk_vars
from factgraph.sdk.dsl import Inference, Pred
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.semantics import ProbLogSemantics
from factgraph.sdk.store import SDKStore, _lower_public_semantics


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _two_branch_where() -> list[list[tuple[str, str, list[str]]]]:
    return [
        [("pred", "user:tag_seed", ["$u", "vip"])],
        [("pred", "user:tag_seed", ["$u", "trial"])],
    ]


def _profile(
    *,
    engine: str = "problog",
    entries: list[dict[str, object]] | None = None,
    uncertainty_projection: dict[str, object] | None = None,
) -> SemanticsProfile:
    return SemanticsProfile(
        name="profile.c.problog",
        engine=engine,
        rule_projection={"problog": entries or [{"target": "branch:0", "kind": "branch_probability", "value": 0.4}]},
        uncertainty_projection=uncertainty_projection or {},
    )


class ProbLogSemanticsProfileResolverTests(unittest.TestCase):
    def test_profile_rule_projection_materializes_branch_probabilities_with_default_one(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=None,
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.4, 1.0))

    def test_profile_rule_projection_requires_problog_engine_at_consumption(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(engine="native"),
            )

        self.assertIn("SemanticsProfile.engine='problog'", str(ctx.exception))

    def test_profile_rule_projection_rejects_invalid_kind(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(entries=[{"target": "branch:0", "kind": "interval", "value": 0.4}]),
            )

        self.assertIn("branch_probability", str(ctx.exception))

    def test_profile_rule_projection_rejects_invalid_target_shape(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(
                    entries=[{"target": "body_atom:0:0", "kind": "branch_probability", "value": 0.4}]
                ),
            )

        self.assertIn("branch:{index}", str(ctx.exception))

    def test_profile_rule_projection_rejects_out_of_range_branch_index(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(entries=[{"target": "branch:2", "kind": "branch_probability", "value": 0.4}]),
            )

        self.assertIn("branch index", str(ctx.exception))

    def test_profile_rule_projection_rejects_out_of_range_probability(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(entries=[{"target": "branch:0", "kind": "branch_probability", "value": 0.0}]),
            )

        self.assertIn("(0,1]", str(ctx.exception))

    def test_profile_rule_projection_rejects_duplicate_branch_targets(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                semantics_profile=_profile(
                    entries=[
                        {"target": "branch:0", "kind": "branch_probability", "value": 0.4},
                        {"target": "branch:0", "kind": "branch_probability", "value": 0.5},
                    ]
                ),
            )

        self.assertIn("duplicate", str(ctx.exception))

    def test_matching_profile_engine_ext_and_legacy_carriers_are_allowed(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=ProbLogRuleExt(branch_probabilities=(0.4, 1.0)),
            legacy_body_confidences=[0.4, 1.0],
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.4, 1.0))

    def test_conflicting_profile_and_engine_ext_rejects_with_carrier_names(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=ProbLogRuleExt(branch_probabilities=(0.8, 1.0)),
                semantics_profile=_profile(),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.rule_projection.problog", message)
        self.assertIn("ProbLogRuleExt.branch_probabilities", message)

    def test_conflicting_profile_and_legacy_bridge_rejects_with_carrier_names(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=None,
                legacy_body_confidences=[0.8, 1.0],
                semantics_profile=_profile(),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.rule_projection.problog", message)
        self.assertIn("legacy_body_confidences", message)


class ProbLogSemanticsProfileCoreEvaluateTests(unittest.TestCase):
    def _make_sdk(self, *, seed_meta: dict[str, object] | None = None) -> SDKStore:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
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
            meta=seed_meta or {"source": "test"},
        )
        return sdk

    def _make_derivation(self) -> Inference:
        with sdk_vars("u", "tag") as (u, tag):
            return Inference(
                id="drv.c.problog_tag",
                version="v1",
                where=[Pred("user:tag_seed", u, tag)],
                target="user:tag",
                head_vars=[u, tag],
            )

    def _mock_output(self, sdk: SDKStore) -> str:
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

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_core_store_evaluate_semantics_profile_drives_exported_probability(self, mock_run) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="problog",
            semantics_profile=_profile(entries=[{"target": "branch:0", "kind": "branch_probability", "value": 0.35}]),
        )

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.35::rule_body_0", seen["program"])

    def test_core_store_evaluate_rejects_semantics_profile_outside_problog(self) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]

        with self.assertRaises(ValueError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="native",
                semantics_profile=_profile(),
            )

        self.assertIn("mode='problog'", str(ctx.exception))

    def test_core_store_evaluate_rejects_raw_uncertainty_by_default(self) -> None:
        sdk = self._make_sdk(seed_meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]})
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]

        with self.assertRaises(ProbLogExportError) as ctx:
            sdk.store.evaluate(
                derivation_id=compiled["derivation_id"],
                version=compiled["version"],
                target_pred_id=compiled["target_pred_id"],
                head_vars=compiled["head_vars"],
                where=compiled["where"],
                mode="problog",
                semantics_profile=_profile(),
            )

        self.assertIn("policy=reject", str(ctx.exception))

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_core_store_evaluate_projects_midpoint_raw_uncertainty(self, mock_run) -> None:
        sdk = self._make_sdk(seed_meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]})
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        sdk.store.evaluate(
            derivation_id=compiled["derivation_id"],
            version=compiled["version"],
            target_pred_id=compiled["target_pred_id"],
            head_vars=compiled["head_vars"],
            where=compiled["where"],
            mode="problog",
            semantics_profile=_profile(uncertainty_projection={"probabilistic": {"policy": "midpoint"}}),
        )

        self.assertIn("0.5::edb_fact", seen["program"])


class ProbLogSemanticsProfileGuardTests(unittest.TestCase):
    def test_exporter_stays_profile_agnostic(self) -> None:
        import factgraph.adapters.problog.problog_export as problog_export

        source = Path(problog_export.__file__).read_text(encoding="utf-8")
        self.assertNotIn("SemanticsProfile", source)

    def test_existing_legacy_body_confidences_bridge_survives(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=None,
            legacy_body_confidences=[0.7, 0.6],
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.7, 0.6))

    def test_existing_explicit_problog_rule_ext_survives(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=ProbLogRuleExt(branch_probabilities=(0.7, 0.6)),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.7, 0.6))


class PublicProbLogUncertaintyProjectionTests(unittest.TestCase):
    def test_problog_semantics_defaults_to_reject_uncertainty_projection(self) -> None:
        semantics = ProbLogSemantics()

        self.assertEqual(
            semantics.uncertainty_projection,
            {
                "probabilistic": {"policy": "reject"},
                "possibilistic": {"policy": "reject"},
                "fallback": "reject_unconfigured",
            },
        )

    def test_lowering_preserves_explicit_uncertainty_projection(self) -> None:
        semantics = ProbLogSemantics(
            uncertainty_projection={
                "probabilistic": {"policy": "midpoint"},
                "fallback": "reject_unconfigured",
            }
        )

        profile = _lower_public_semantics(
            semantics,
            derivation=ProbLogSemanticsProfileCoreEvaluateTests()._make_derivation(),
        )

        self.assertEqual(profile.engine, "problog")
        self.assertEqual(profile.uncertainty_projection["probabilistic"], {"policy": "midpoint"})
        self.assertEqual(profile.uncertainty_projection["fallback"], "reject_unconfigured")

    def test_direct_probability_projection_policies(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="Alice")
        asrt_id = set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]},
        )

        cases = {
            "lower": 0.2,
            "midpoint": 0.5,
            "upper": 0.8,
        }
        for policy, expected in cases.items():
            with self.subTest(policy=policy):
                actual = _claim_probability(
                    sdk.store,
                    asrt_id,
                    uncertainty_projection={"probabilistic": {"policy": policy}, "fallback": "reject_unconfigured"},
                )
                self.assertEqual(actual, expected)

    def test_identity_probability_requires_degenerate_probabilistic_bound(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="Alice")
        asrt_id = set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.4, 0.4]},
        )

        actual = _claim_probability(
            sdk.store,
            asrt_id,
            uncertainty_projection={"probabilistic": {"policy": "identity_probability"}},
        )

        self.assertEqual(actual, 0.4)

    def test_interval_policies_reject_for_problog_point_export(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="Alice")
        asrt_id = set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]},
        )

        for policy in ("probability_interval", "possibility_interval"):
            with self.subTest(policy=policy):
                with self.assertRaises(ProbLogExportError) as ctx:
                    _claim_probability(
                        sdk.store,
                        asrt_id,
                        uncertainty_projection={"probabilistic": {"policy": policy}},
                    )
                self.assertIn("not supported by ProbLog point export", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
