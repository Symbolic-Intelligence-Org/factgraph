from __future__ import annotations

import inspect
import unittest

import factgraph.sdk as factgraph_sdk
from factgraph.application import build_schema_index, entity_info, resolve_selector
from factgraph.application.protocol import EntitySelector, Explanation, Rule, WhyNotUniverseResult
from factgraph.application.protocol import derivation_why_not as why_not_protocol
from factgraph.application.protocol import evaluate_result as evaluate_result_protocol
from factgraph.application import why_not_runtime
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, SDKStore
from factgraph.sdk.shells import why_not as sdk_why_not_shell
from factgraph.sdk.store import _SDKEvalManager


class QuarantinePerson(Entity):
    name: str = Identity()
    region: str = Field()


def _store() -> SDKStore:
    return SDKStore([QuarantinePerson])


def _seed_person(graph: SDKStore, name: str) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(
        EntitySelector(entity_type="QuarantinePerson", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "QuarantinePerson")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["name"].pred_id, encoded, [("string", name)])
    return encoded


def _person_exists_rule(rule_id: str = "QuarantinePerson:exists") -> Rule:
    person = Var("$person")
    return Rule(
        id=rule_id,
        when=(PredAtom("QuarantinePerson:exists", [person]),),
        ports={"person": person},
    )


def _closed_missing_person_head(graph: SDKStore) -> Rule:
    index = build_schema_index(graph.schema_ir)
    identity_predicate_id = entity_info(index, "QuarantinePerson").identity_predicates["name"].pred_id
    person = Var("$person")
    return Rule(
        id="QuarantinePerson:exists_closed_missing",
        when=(
            PredAtom("QuarantinePerson:exists", [person]),
            PredAtom(identity_predicate_id, [person, Const("missing")]),
        ),
        ports={"person": person},
    )


class T5WhyNotQuarantineTests(unittest.TestCase):
    def test_failed_explanation_is_t5_v1_why_not_envelope(self) -> None:
        graph = _store()
        _seed_person(graph, "alice")
        rule = _person_exists_rule()
        closed_missing = _closed_missing_person_head(graph)

        explanation = graph.eval.explain(rule, head=closed_missing, engine="native")

        self.assertIsInstance(explanation, Explanation)
        self.assertNotIsInstance(explanation, WhyNotUniverseResult)
        self.assertEqual(explanation.status, "failed")
        self.assertEqual(explanation.failure_class, "closed_head_false")
        self.assertIsNone(explanation.evidence)
        self.assertEqual(explanation.errors, ())
        for legacy_field in (
            "requested_universe",
            "passed",
            "failed",
            "diagnostic",
            "atom_locator",
        ):
            with self.subTest(legacy_field=legacy_field):
                self.assertFalse(hasattr(explanation, legacy_field))

    def test_no_t5_public_why_not_surface_exists(self) -> None:
        graph = _store()

        self.assertFalse(hasattr(graph.eval, "why_not"))
        self.assertFalse(hasattr(graph.eval, "why_not_v2"))
        self.assertFalse(hasattr(Explanation, "why_not"))
        self.assertFalse(hasattr(Explanation, "counterfactuals"))
        self.assertFalse(hasattr(evaluate_result_protocol.EvaluateResult, "why_not"))
        self.assertFalse(hasattr(evaluate_result_protocol.EvaluateResult, "counterfactuals"))
        self.assertNotIn("WhyNotUniverseResult", factgraph_sdk.__all__)
        self.assertNotIn("why_not", factgraph_sdk.__all__)
        self.assertFalse(hasattr(SDKStore, "why_not"))
        self.assertTrue(callable(sdk_why_not_shell.sdk_why_not))

    def test_legacy_why_not_surfaces_are_quarantined_not_deleted(self) -> None:
        self.assertIn("T5 quarantine", why_not_protocol.__doc__ or "")
        self.assertIn("T5 quarantine", why_not_runtime.__doc__ or "")
        self.assertIn("T5 quarantine", sdk_why_not_shell.__doc__ or "")

    def test_no_lossy_why_not_to_explanation_conversion_path_exists(self) -> None:
        sources = (
            inspect.getsource(evaluate_result_protocol._explain_live_row),
            inspect.getsource(_SDKEvalManager.explain),
        )
        forbidden = (
            "WhyNotUniverseResult",
            "WhyNotFailedRow",
            "WhyNotRowDiagnostic",
            "WhyNotConditionLocator",
            "DiagnoseResult",
            "atom_locator",
            "failed[0]",
        )

        for source in sources:
            for token in forbidden:
                with self.subTest(token=token):
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
