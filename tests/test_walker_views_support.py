"""SupportArtifactView and AssertionView tests for B Phase 3."""

from __future__ import annotations

import unittest

from factgraph.application.walker import (
    AssertionView,
    ConditionKeyView,
    FrozenTupleView,
    SupportArtifactView,
    WalkerFrozenError,
    WalkerReferenceError,
    WalkerSnapshotError,
)
from factgraph.core.store._support import NonFactStep, PredWitness, ProofReceipt
from factgraph.core.store.ledger import Claim, MetaRow


def _support_artifact() -> ProofReceipt:
    return ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=(("$p", "person:alice"),),
        pred_witnesses=(
            PredWitness(pred_condition_key="c0.c0:Person:age", asrt_ids=("a1", "a2")),
        ),
        non_fact_steps=(
            NonFactStep(step_key="c0.c1:eq", kind="eq", status="satisfied"),
        ),
    )


def _claims() -> dict[str, Claim]:
    return {
        "a1": Claim(
            asrt_id="a1",
            pred_id="Person:age",
            e_ref="person:alice",
            rest_terms=[("value", 40)],
        ),
        "a2": Claim(
            asrt_id="a2",
            pred_id="Person:age",
            e_ref="person:bob",
            rest_terms=[("value", 41)],
        ),
    }


def _meta() -> dict[str, tuple[MetaRow, ...]]:
    return {
        "a1": (
            MetaRow(asrt_id="a1", key="source", kind="str", value="seed"),
            MetaRow(asrt_id="a1", key="confidence", kind="float", value=0.9),
        )
    }


class AssertionViewTests(unittest.TestCase):
    def test_assertion_view_resolves_claim_and_meta_snapshot(self) -> None:
        claims = _claims()
        meta = _meta()
        view = AssertionView("a1", claims, meta)

        self.assertEqual(view.asrt_id, "a1")
        self.assertEqual(view.pred_id, "Person:age")
        self.assertEqual(view.e_ref, "person:alice")
        self.assertEqual(view.rest_terms, (("value", 40),))
        self.assertEqual([row.key for row in view.meta_rows], ["source", "confidence"])
        self.assertIs(view.underlying, claims["a1"])

    def test_assertion_view_snapshot_immune_to_claim_rest_terms_mutation(self) -> None:
        claims = _claims()
        view = AssertionView("a1", claims)

        claims["a1"].rest_terms.append(("late", "mutation"))

        self.assertEqual(view.rest_terms, (("value", 40),))
        self.assertEqual(view.underlying.rest_terms, [("value", 40), ("late", "mutation")])

    def test_assertion_view_deep_freezes_nested_values_and_hashes(self) -> None:
        claims = {
            "a1": Claim(
                asrt_id="a1",
                pred_id="Person:attrs",
                e_ref="person:alice",
                rest_terms=[
                    ("attrs", {"tags": ["vip", "active"], "score": 7}),
                ],
            )
        }
        meta = {
            "a1": (
                MetaRow(asrt_id="a1", key="source", kind="json", value={"channels": ["seed"]}),
            )
        }

        view = AssertionView("a1", claims, meta)
        claims["a1"].rest_terms[0][1]["tags"].append("late")  # type: ignore[index]
        meta["a1"][0].value["channels"].append("late")  # type: ignore[index]

        self.assertEqual(view.rest_terms, (("attrs", (("score", 7), ("tags", ("vip", "active")))),))
        self.assertEqual(view.meta_rows[0].value, (("channels", ("seed",)),))
        self.assertIsInstance(hash(view), int)

    def test_assertion_view_rejects_malformed_rest_terms(self) -> None:
        malformed_claims = {
            "a1": Claim("a1", "Person:age", "person:alice", [("ok", 1), ("", 2)]),
            "a2": Claim("a2", "Person:age", "person:bob", [("too", "long", "row")]),  # type: ignore[list-item]
        }

        with self.assertRaises(WalkerSnapshotError):
            AssertionView("a1", malformed_claims)
        with self.assertRaises(WalkerSnapshotError):
            AssertionView("a2", malformed_claims)

    def test_assertion_view_missing_claim_raises_reference_error(self) -> None:
        with self.assertRaises(WalkerReferenceError):
            AssertionView("missing", _claims())

    def test_assertion_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        view = AssertionView("a1", _claims())

        with self.assertRaises(WalkerFrozenError):
            view.pred_id = "Other"  # type: ignore[misc]

        self.assertFalse(hasattr(view, "source"))
        self.assertFalse(hasattr(view, "carrier"))
        self.assertFalse(hasattr(view, "raw"))

    def test_assertion_view_equality_excludes_underlying(self) -> None:
        a = AssertionView("a1", _claims())
        b_claims = _claims()
        b_claims["a1"] = Claim("a1", "Person:age", "person:alice", [("value", 40), ("late", "ignored")])
        b = AssertionView("a1", b_claims)

        self.assertNotEqual(a, b)
        same_surface = AssertionView("a1", _claims())
        self.assertEqual(a, same_surface)
        self.assertEqual(hash(a), hash(same_surface))


class SupportArtifactViewTests(unittest.TestCase):
    def test_wraps_support_artifact_tuple_fields(self) -> None:
        support = _support_artifact()
        view = SupportArtifactView(support, _claims(), _meta(), source_id="support-1")

        self.assertIs(view.underlying, support)
        self.assertEqual(view.source_id, "support-1")
        self.assertIsInstance(view.pred_witnesses, FrozenTupleView)
        self.assertIsInstance(view.non_fact_steps, FrozenTupleView)
        self.assertEqual(view.pred_witnesses.first().pred_condition_key, "c0.c0:Person:age")
        self.assertEqual(view.non_fact_steps.first().step_key, "c0.c1:eq")
        self.assertEqual(support.pred_witnesses[0].asrt_ids, ("a1", "a2"))
        self.assertEqual(support.non_fact_steps[0].step_key, "c0.c1:eq")

    def test_contextualizes_pred_and_step_atom_keys(self) -> None:
        view = SupportArtifactView(_support_artifact(), _claims())

        pred_key = view.parse_pred_condition_key("c0.c0:Person:age")
        step_key = view.parse_step_key("c0.c1:eq")

        self.assertIsInstance(pred_key, ConditionKeyView)
        self.assertEqual(pred_key.key, "c0.c0:Person:age")
        self.assertEqual(pred_key.case_index, 0)
        self.assertEqual(pred_key.condition_index, 0)
        self.assertEqual(pred_key.payload, "Person:age")
        self.assertEqual(pred_key.underlying, "c0.c0:Person:age")
        self.assertEqual(pred_key.kind, "pred")
        self.assertEqual(pred_key.pred_id, "Person:age")
        self.assertEqual(step_key.key, "c0.c1:eq")
        self.assertEqual(step_key.case_index, 0)
        self.assertEqual(step_key.condition_index, 1)
        self.assertEqual(step_key.payload, "eq")
        self.assertEqual(step_key.underlying, "c0.c1:eq")
        self.assertEqual(step_key.kind, "step")
        self.assertEqual(step_key.step_kind, "eq")

    def test_lookup_assertion_returns_assertion_view(self) -> None:
        view = SupportArtifactView(_support_artifact(), _claims(), _meta())

        assertion = view.lookup_assertion("a1")

        self.assertIsInstance(assertion, AssertionView)
        self.assertEqual(assertion.pred_id, "Person:age")
        self.assertEqual([row.key for row in assertion.meta_rows], ["source", "confidence"])

    def test_lookup_assertion_missing_claim_raises_reference_error(self) -> None:
        view = SupportArtifactView(_support_artifact(), _claims())

        with self.assertRaises(WalkerReferenceError):
            view.lookup_assertion("missing")

    def test_constructor_requires_support_artifact_and_claim_index_mapping(self) -> None:
        with self.assertRaises(TypeError):
            SupportArtifactView(object(), _claims())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            SupportArtifactView(_support_artifact(), None)  # type: ignore[arg-type]

    def test_claim_index_is_defensively_copied(self) -> None:
        claims = _claims()
        view = SupportArtifactView(_support_artifact(), claims)
        claims.pop("a1")

        self.assertEqual(view.lookup_assertion("a1").asrt_id, "a1")

    def test_claim_contents_are_snapshotted_at_support_view_construction(self) -> None:
        claims = _claims()
        view = SupportArtifactView(_support_artifact(), claims)

        claims["a1"].rest_terms.append(("late", "mutation"))

        self.assertEqual(view.lookup_assertion("a1").rest_terms, (("value", 40),))

    def test_meta_index_is_defensively_copied_at_support_view_construction(self) -> None:
        meta = _meta()
        view = SupportArtifactView(_support_artifact(), _claims(), meta)
        meta["a1"] = (
            MetaRow(asrt_id="a1", key="source", kind="str", value="late"),
        )

        assertion = view.lookup_assertion("a1")
        self.assertEqual([row.key for row in assertion.meta_rows], ["source", "confidence"])
        self.assertEqual(assertion.meta_rows[0].value, "seed")

    def test_support_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        view = SupportArtifactView(_support_artifact(), _claims())

        with self.assertRaises(WalkerFrozenError):
            view.source_id = "other"  # type: ignore[misc]

        self.assertFalse(hasattr(view, "source"))
        self.assertFalse(hasattr(view, "carrier"))
        self.assertFalse(hasattr(view, "raw"))

    def test_phase_3_support_types_reexport_from_application_package(self) -> None:
        from factgraph.application import AssertionView as AppAssertionView
        from factgraph.application import SupportArtifactView as AppSupportArtifactView

        self.assertIs(AppAssertionView, AssertionView)
        self.assertIs(AppSupportArtifactView, SupportArtifactView)


if __name__ == "__main__":
    unittest.main()
