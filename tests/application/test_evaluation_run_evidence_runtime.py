from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    evaluation_run_bundle_evidence,
    manage_rule_occurrence,
)
from factgraph.application.explain import (
    EvidenceTree,
    Fact,
    Holds,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
from factgraph.application.protocol import (
    EvaluationQuery,
    EvaluationQuerySelection,
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyOccurrence,
    PolicyUnify,
    ProtocolShapeError,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from tests.application.test_evaluation_run_verification_runtime import _capture


def _resolved_person(graph, rule):
    index = build_schema_index(graph.schema_ir)
    return build_resolved_rule(
        id=rule.id,
        version=rule.version,
        when=rule.when,
        ports={
            "person": SemanticRulePort(rule.ports["person"], entity_identity("Person")),
            "age": SemanticRulePort(rule.ports["age"], field_endpoint("Person", "age")),
            "score": SemanticRulePort(
                rule.ports["score"], field_endpoint("Person", "score")
            ),
        },
        schema_index=index,
    )


class EvaluationRunEvidenceRuntimeTests(unittest.TestCase):
    def test_detached_graph_uses_assertion_sources_and_marks_query_materialization(self) -> None:
        graph, _rule, bundle = _capture(score=9)
        row_digest = bundle.rows[0].row_capture_digest
        graph.close()

        with patch(
            "factgraph.application.evaluation_run_verification_runtime.evaluate_native_where"
        ) as evaluator:
            evidence = evaluation_run_bundle_evidence(
                bundle,
                row_capture_digest=row_digest,
            )
        evaluator.assert_not_called()

        self.assertEqual(evidence.metadata["evidence_mode"], "detached_receipt_playback_v0")
        self.assertEqual(evidence.metadata["logical_verification"], "not_performed")
        self.assertIs(evidence.metadata["replay_verified"], False)
        self.assertEqual(evidence.metadata["authenticity"], "unverified")
        self.assertEqual(evidence.metadata["row_capture_digest"], row_digest)
        self.assertEqual(evidence.metadata["result_id"], bundle.run_anchor.result_id)
        self.assertEqual(evidence.metadata["row_id"], bundle.rows[0].row_id)
        self.assertEqual(evidence.metadata["claim_digest"], bundle.rows[0].claim_digest)
        self.assertEqual(
            evidence.metadata["semantic_row_anchor_digest"],
            bundle.run_anchor.row_anchors[0].semantic_anchor_digest,
        )
        self.assertEqual(len(evidence.paths), 1)
        tree = evidence.paths[0]
        self.assertIsInstance(tree, EvidenceTree)
        assert isinstance(tree, EvidenceTree)
        self.assertEqual(tree.status, "holds")
        self.assertEqual(tree.tree_id, "c0")

        projection, body = tree.rules
        self.assertEqual(projection.role, "head")
        self.assertEqual(body.occurrence_alias, "person")
        self.assertEqual(body.rule_id, "person_values")
        self.assertEqual(
            tuple(atom.atom_id for atom in body.atoms),
            ("c0:atom:0", "c0:atom:1", "c0:atom:2"),
        )
        sources = [source for atom in body.atoms for source in atom.verdict.support]
        captured_ids = {
            assertion_id
            for relation in bundle.relations
            for assertion_id, _values in relation.facts
        }
        self.assertTrue(sources)
        self.assertTrue(all(source.ref in captured_ids for source in sources))
        self.assertTrue(all(source.meta["assertion_id"] == source.ref for source in sources))
        self.assertTrue(all(isinstance(source.value, tuple) for source in sources))
        self.assertEqual(
            tuple(atom.atom_id for atom in projection.atoms),
            (*evidence.metadata["query_binding_atom_ids"],
             *evidence.metadata["projection_head_link_atom_ids"]),
        )
        self.assertEqual(
            evidence.metadata["outside_policy_lineage_atom_ids"],
            tuple(atom.atom_id for atom in projection.atoms),
        )
        self.assertEqual(
            evidence_graph_from_dict(evidence_graph_to_dict(evidence)),
            evidence,
        )

    def test_zero_or_unknown_row_selector_never_fabricates_failed_evidence(self) -> None:
        _graph, _rule, empty = _capture(score=999)
        self.assertEqual(empty.rows, ())
        with self.assertRaisesRegex(ProtocolShapeError, "not found"):
            evaluation_run_bundle_evidence(
                empty,
                row_capture_digest="sha256:" + "0" * 64,
            )

        _graph, _rule, bundle = _capture()
        with self.assertRaisesRegex(ProtocolShapeError, "not found"):
            evaluation_run_bundle_evidence(
                bundle,
                row_capture_digest="sha256:" + "0" * 64,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "non-empty"):
            evaluation_run_bundle_evidence(bundle, row_capture_digest="")

    def test_complete_bundle_validation_precedes_row_selection(self) -> None:
        _graph, _rule, bundle = _capture()
        forged = deepcopy(bundle)
        object.__setattr__(forged, "bundle_digest", "sha256:" + "0" * 64)

        with self.assertRaisesRegex(ProtocolShapeError, "bundle_digest"):
            evaluation_run_bundle_evidence(
                forged,
                row_capture_digest="sha256:" + "f" * 64,
            )

    def test_or_playback_contains_only_the_receipt_selected_branch(self) -> None:
        graph, rule, _bundle = _capture()
        resolved = _resolved_person(graph, rule)
        index = build_schema_index(graph.schema_ir)
        space = SemanticAddressSpace(
            tuple(
                manage_rule_occurrence(resolved, alias)
                for alias in ("common", "left", "right")
            )
        )
        policy = compile_policy(
            Policy(
                "branch-policy",
                PolicyAll(
                    (
                        PolicyOccurrence("common"),
                        PolicyAny((PolicyOccurrence("left"), PolicyOccurrence("right"))),
                    )
                ),
            ),
            address_space=space,
        )
        query = EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection(
                    "person", SemanticPortAddress("common", "person")
                ),
            ),
        )
        compiled = compile_evaluation_query(
            query,
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        result = graph.eval.evaluate(compiled, capture="run_bundle_v0")
        assert result.run_bundle is not None
        row = result.run_bundle.rows[0]

        evidence = evaluation_run_bundle_evidence(
            result.run_bundle,
            row_capture_digest=row.row_capture_digest,
        )

        tree = evidence.paths[0]
        assert isinstance(tree, EvidenceTree)
        self.assertIn(tree.tree_id, {"c0", "c1"})
        aliases = {rule.occurrence_alias for rule in tree.rules if rule.role == "body"}
        self.assertEqual(len(aliases), 2)
        self.assertTrue(any(alias.startswith("common") for alias in aliases))
        self.assertEqual(
            {atom.atom_id.split(":", 2)[0] for rule in tree.rules for atom in rule.atoms},
            {tree.tree_id},
        )
        self.assertTrue(
            all(isinstance(atom.form, Fact) and isinstance(atom.verdict, Holds)
                for rule in tree.rules if rule.role == "body" for atom in rule.atoms)
        )

    def test_authored_unify_is_structured_and_keeps_its_receipt_coordinate(self) -> None:
        graph, rule, _bundle = _capture()
        resolved = _resolved_person(graph, rule)
        index = build_schema_index(graph.schema_ir)
        space = SemanticAddressSpace(
            tuple(manage_rule_occurrence(resolved, alias) for alias in ("left", "right"))
        )
        policy = compile_policy(
            Policy(
                "joined-policy",
                PolicyAll(
                    (
                        PolicyOccurrence("left"),
                        PolicyOccurrence("right"),
                        PolicyUnify(
                            SemanticPortAddress("left", "person"),
                            SemanticPortAddress("right", "person"),
                        ),
                    )
                ),
            ),
            address_space=space,
        )
        compiled = compile_evaluation_query(
            EvaluationQuery(
                policy.policy_digest,
                (
                    EvaluationQuerySelection(
                        "person", SemanticPortAddress("left", "person")
                    ),
                ),
            ),
            compiled_policy=policy,
            address_space=space,
            schema_index=index,
        )
        result = graph.eval.evaluate(compiled, capture="run_bundle_v0")
        assert result.run_bundle is not None
        row = result.run_bundle.rows[0]

        evidence = evaluation_run_bundle_evidence(
            result.run_bundle,
            row_capture_digest=row.row_capture_digest,
        )

        tree = evidence.paths[0]
        assert isinstance(tree, EvidenceTree)
        self.assertEqual(len(tree.joins), 1)
        join = tree.joins[0]
        self.assertEqual(join.join_id, "c0:left.person=right.person")
        self.assertEqual(join.left.rule_occurrence_alias, "left")
        self.assertEqual(join.right.rule_occurrence_alias, "right")
        self.assertEqual(
            evidence.metadata["join_condition_ids"],
            ((join.join_id, "c0.c6:eq"),),
        )


if __name__ == "__main__":
    unittest.main()
