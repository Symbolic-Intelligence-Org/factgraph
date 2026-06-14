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
from factgraph.sdk.dsl import EmitSpec, Inference, Pred
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.semantics import ProbLogConfig
from factgraph.sdk.store import SDKStore, _lower_public_semantics


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag: str = Field()


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


class ProbLogConfigProfileResolverTests(unittest.TestCase):
    def test_profile_rule_projection_materializes_case_probabilities_with_default_one(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=None,
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.case_probabilities, (0.4, 1.0))

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

        self.assertIn("case index", str(ctx.exception))

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
            engine_ext=ProbLogRuleExt(case_probabilities=(0.4, 1.0)),
            legacy_body_confidences=[0.4, 1.0],
            semantics_profile=_profile(),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.case_probabilities, (0.4, 1.0))

    def test_conflicting_profile_and_engine_ext_rejects_with_carrier_names(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=_two_branch_where(),
                engine_ext=ProbLogRuleExt(case_probabilities=(0.8, 1.0)),
                semantics_profile=_profile(),
            )

        message = str(ctx.exception)
        self.assertIn("SemanticsProfile.rule_projection.problog", message)
        self.assertIn("ProbLogRuleExt.case_probabilities", message)

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


class ProbLogConfigProfileCoreEvaluateTests(unittest.TestCase):
    def _make_sdk(self, *, seed_meta: dict[str, object] | None = None) -> SDKStore:
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
            meta=seed_meta or {"source": "test"},
        )
        return sdk

    def _make_derivation(self) -> Inference:
        with sdk_vars("u", "tag") as (u, tag):
            return Inference(
                id="drv.c.problog_tag",
                version="v1",
                when=[Pred("user:tag_seed", u, tag)],
                emits=EmitSpec("user:tag", [u, tag]),
            )

    def _mock_output(self, sdk: SDKStore) -> str:
        alice_ref = sdk.entities.ref(User, user_id="Alice")
        return "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("{alice_ref}","vip") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("{alice_ref}","vip") {{0.00019}} [at 4:7]',
                f'  result answer("{alice_ref}","vip") ("{alice_ref}","vip") {{{{}}}} {{0.00060}} []',
                f' complete answer("{alice_ref}","vip") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("{alice_ref}","vip"):\t0.42',
            ]
        )

    def _mock_nested_output(self, sdk: SDKStore) -> str:
        alice_ref = sdk.entities.ref(User, user_id="Alice")
        return "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("{alice_ref}","vip") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("{alice_ref}","vip") {{0.00019}} [at 4:7]',
                f'  call rule_body_0("{alice_ref}","vip") {{0.00020}} [at 3:1]',
                f'   call edb_fact(_, "user:tag_seed", "{alice_ref}", "vip") {{0.00021}} [at 2:1]',
                f'    result edb_fact(_, "user:tag_seed", "{alice_ref}", "vip") ("{alice_ref}","vip") {{{{}}}} {{0.00022}} []',
                f'   complete edb_fact(_, "user:tag_seed", "{alice_ref}", "vip") {{0.00023}} {{0.00002}} []',
                f'   result rule_body_0("{alice_ref}","vip") ("{alice_ref}","vip") {{{{}}}} {{0.00024}} []',
                f'  complete rule_body_0("{alice_ref}","vip") {{0.00025}} {{0.00005}} []',
                f'  result answer("{alice_ref}","vip") ("{alice_ref}","vip") {{{{}}}} {{0.00060}} []',
                f' complete answer("{alice_ref}","vip") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("{alice_ref}","vip"):\t0.42',
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

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_row_explain_uses_problog_provenance_bridge(self, mock_run) -> None:
        sdk = self._make_sdk(seed_meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]})
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        mock_run.return_value = self._mock_nested_output(sdk)

        result = sdk.eval.evaluate(
            self._make_derivation(),
            config=ProbLogConfig(uncertainty_projection={"probabilistic": {"policy": "midpoint"}}),
        )

        self.assertEqual(result.count(), 1)
        explanation = result[0].explain()
        graph = explanation.evidence
        self.assertIsNotNone(graph)
        assert graph is not None
        self.assertEqual(graph.engine, "problog")
        self.assertGreater(len(graph.paths), 0)
        self.assertEqual(
            set(graph.metadata),
            {
                "result_id",
                "row_id",
                "evidence_ref_id",
                "claim_digest",
                "closed_head_digest",
                "expr_digest",
                "rule_set_digest",
                "view_snapshot_digest",
                "config_digest",
                "result_digest",
                "engine",
                "engine_version",
                "adapter_version",
                "evaluated_at",
            },
        )
        tree = graph.paths[0]
        self.assertEqual(tree.metadata["answer_probability"], 0.42)
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        body_atoms = tuple(atom for rule in tree.rules if rule.role == "body" for atom in rule.atoms)
        self.assertGreater(len(body_atoms), 0)
        self.assertEqual(graph.certainty.kind, "probabilistic")
        self.assertEqual(graph.certainty.lo, 0.42)
        self.assertEqual(compiled["target_pred_id"], "user:tag")


class ProbLogConfigProfileGuardTests(unittest.TestCase):
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
        self.assertEqual(resolved.case_probabilities, (0.7, 0.6))

    def test_existing_explicit_problog_rule_ext_survives(self) -> None:
        resolved = resolve_problog_engine_ext(
            where=_two_branch_where(),
            engine_ext=ProbLogRuleExt(case_probabilities=(0.7, 0.6)),
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.case_probabilities, (0.7, 0.6))


class PublicProbLogUncertaintyProjectionTests(unittest.TestCase):
    def test_problog_semantics_defaults_to_reject_uncertainty_projection(self) -> None:
        semantics = ProbLogConfig()

        self.assertEqual(
            semantics.uncertainty_projection,
            {
                "probabilistic": {"policy": "reject"},
                "possibilistic": {"policy": "reject"},
                "fallback": "reject_unconfigured",
            },
        )

    def test_lowering_preserves_explicit_uncertainty_projection(self) -> None:
        semantics = ProbLogConfig(
            uncertainty_projection={
                "probabilistic": {"policy": "midpoint"},
                "fallback": "reject_unconfigured",
            }
        )

        profile = _lower_public_semantics(
            semantics,
            derivation=ProbLogConfigProfileCoreEvaluateTests()._make_derivation(),
        )

        self.assertEqual(profile.engine, "problog")
        self.assertEqual(profile.uncertainty_projection["probabilistic"], {"policy": "midpoint"})
        self.assertEqual(profile.uncertainty_projection["fallback"], "reject_unconfigured")

    def test_direct_probability_projection_policies(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.entities.ref(User, user_id="Alice")
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

    def test_claim_probability_records_projection_decisions_without_changing_return_value(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.entities.ref(User, user_id="Alice")
        asrt_id = set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "raw_kind": "probabilistic", "bound": [0.2, 0.8]},
        )
        decisions: dict[str, dict[str, object]] = {}

        actual = _claim_probability(
            sdk.store,
            asrt_id,
            uncertainty_projection={"probabilistic": {"policy": "upper"}, "fallback": "reject_unconfigured"},
            projection_decisions=decisions,
        )

        self.assertEqual(actual, 0.8)
        self.assertEqual(
            decisions[asrt_id],
            {
                "asrt_id": asrt_id,
                "source": "uncertainty_projection",
                "raw_kind": "probabilistic",
                "bound": [0.2, 0.8],
                "policy": "upper",
                "resolved_probability": 0.8,
            },
        )

    def test_identity_probability_requires_degenerate_probabilistic_bound(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.entities.ref(User, user_id="Alice")
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
        ref = sdk.entities.ref(User, user_id="Alice")
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
