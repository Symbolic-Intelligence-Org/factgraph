from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import gc
import inspect
import unittest
from unittest.mock import patch

import factgraph.application as application
import factgraph.application.captured_receipt_evidence_runtime as receipt_runtime
import factgraph.application.protocol as application_protocol
import factgraph.sdk as sdk
from factgraph.application import evaluation_run_bundle_evidence
from factgraph.application.explain import EvidenceGraph, evidence_graph_to_dict
from factgraph.application.protocol import Explanation, ProtocolShapeError
from factgraph.application.protocol.captured_receipt_evidence import (
    CapturedReceiptEvidenceV0,
)
from factgraph.application.protocol.evaluation_run import _plain, _token as _anchor_token
from factgraph.application.protocol.evaluation_run_bundle import _token as _bundle_token
from factgraph.application.protocol.explanation_render import narrate_evidence, walk_evidence
from factgraph.application.protocol.policy import PolicyLineage
from tests.application.test_evaluation_run_verification_runtime import _capture


_ZERO_TOKEN = "sha256:" + "0" * 64


def _import_application_builder_from_facade() -> object:
    from factgraph.application import build_captured_receipt_evidence_v0

    return build_captured_receipt_evidence_v0


def _import_protocol_dto_from_facade() -> object:
    from factgraph.application.protocol import CapturedReceiptEvidenceV0

    return CapturedReceiptEvidenceV0


def _import_sdk_builder_from_facade() -> object:
    from factgraph.sdk import build_captured_receipt_evidence_v0

    return build_captured_receipt_evidence_v0


def _import_sdk_dto_from_facade() -> object:
    from factgraph.sdk import CapturedReceiptEvidenceV0

    return CapturedReceiptEvidenceV0


def _native_inventory(evidence: CapturedReceiptEvidenceV0) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            condition.condition_id,
            condition.receipt_condition_key,
            condition.native_kind,
            condition.predicate_id,
            condition.assertion_ids,
            condition.captured_step_kind,
        )
        for condition in evidence.branch.conditions
    )


def _with_resealed_lineage_source_index(bundle):
    """Alter sealed Policy lineage only; receipt-native inventory must not move."""

    target = bundle.run_anchor.target
    lineage = target.policy_lineage
    node = lineage.authored_nodes[0]
    old_ref = next(ref for ref in node.lowered_refs if ref.kind == "body_atom")
    assert old_ref.source_index is not None
    replacement_ref = replace(old_ref, source_index=old_ref.source_index + 100)
    replacement_node = replace(
        node,
        lowered_refs=tuple(replacement_ref if ref == old_ref else ref for ref in node.lowered_refs),
    )
    replacement_lineage = PolicyLineage(
        authored_nodes=(replacement_node, *lineage.authored_nodes[1:]),
        lowered_origins=tuple(
            (replacement_ref, origins) if ref == old_ref else (ref, origins)
            for ref, origins in lineage.lowered_origins
        ),
    )
    target_values = tuple(
        replacement_lineage if name == "policy_lineage" else getattr(target, name)
        for name in target.__dataclass_fields__
        if name != "target_digest"
    )
    replacement_target = replace(
        target,
        policy_lineage=replacement_lineage,
        target_digest=_anchor_token("evaluation_run_target_v0", _plain(target_values)),
    )
    anchor = bundle.run_anchor
    anchor_values = tuple(
        replacement_target if name == "target" else getattr(anchor, name)
        for name in anchor.__dataclass_fields__
        if name != "anchor_digest"
    )
    replacement_anchor = replace(
        anchor,
        target=replacement_target,
        anchor_digest=_anchor_token("evaluation_run_anchor_v0", _plain(anchor_values)),
    )
    bundle_values = (
        replacement_anchor.anchor_digest,
        bundle.query_capture_digest,
        bundle.native_plan.plan_digest,
        bundle.schema_capture_digest,
        bundle.relations_capture_digest,
        bundle.rows_capture_digest,
        bundle.execution_contract,
        bundle.integrity,
        bundle.authenticity,
        bundle.privacy,
        bundle.custody,
        bundle.playback,
        bundle.replay_availability,
    )
    return replace(
        bundle,
        run_anchor=replacement_anchor,
        bundle_digest=_bundle_token("evaluation_run_bundle_v0", bundle_values),
    )


def _with_profile(bundle, profile):
    anchor = bundle.run_anchor
    anchor_values = tuple(
        profile if name == "execution_profile" else getattr(anchor, name)
        for name in anchor.__dataclass_fields__
        if name != "anchor_digest"
    )
    replacement_anchor = replace(
        anchor,
        execution_profile=profile,
        anchor_digest=_anchor_token("evaluation_run_anchor_v0", _plain(anchor_values)),
    )
    bundle_values = (
        replacement_anchor.anchor_digest,
        bundle.query_capture_digest,
        bundle.native_plan.plan_digest,
        bundle.schema_capture_digest,
        bundle.relations_capture_digest,
        bundle.rows_capture_digest,
        bundle.execution_contract,
        bundle.integrity,
        bundle.authenticity,
        bundle.privacy,
        bundle.custody,
        bundle.playback,
        bundle.replay_availability,
    )
    return replace(
        bundle,
        run_anchor=replacement_anchor,
        bundle_digest=_bundle_token("evaluation_run_bundle_v0", bundle_values),
    )


class EvaluationRunReceiptEvidenceRuntimeTests(unittest.TestCase):
    def test_private_capture_preserves_graph_playback_and_has_no_public_export(self) -> None:
        graph, _rule, bundle = _capture(score=9)
        row_digest = bundle.rows[0].row_capture_digest

        existing_graph = evaluation_run_bundle_evidence(bundle, row_capture_digest=row_digest)
        self.assertIsInstance(existing_graph, EvidenceGraph)
        del existing_graph
        del graph
        gc.collect()

        with (
            patch(
                "factgraph.core.rules.ruleref_substrate.evaluate_native_where",
                side_effect=AssertionError("receipt capture must not evaluate"),
            ) as evaluator,
            patch(
                "factgraph.application.evaluation_run_verification_runtime."
                "verify_evaluation_run_bundle",
                side_effect=AssertionError("receipt capture must not verify"),
            ) as verifier,
            patch(
                "factgraph.core.store.runtime.Store.evaluate",
                side_effect=AssertionError("receipt capture must not open a Store"),
            ) as store_evaluate,
        ):
            evidence = receipt_runtime.build_captured_receipt_evidence_v0(
                bundle,
                row_capture_digest=row_digest,
            )
        evaluator.assert_not_called()
        verifier.assert_not_called()
        store_evaluate.assert_not_called()

        self.assertIsInstance(evidence, CapturedReceiptEvidenceV0)
        self.assertEqual(evidence.capture_status, "selected_receipt_captured")
        self.assertEqual(evidence.capture_basis, "sealed_native_plan_relation_receipt")
        self.assertEqual(evidence.integrity, "digest_sealed_not_authenticated")
        self.assertEqual(evidence.authenticity, "unverified")
        self.assertEqual(evidence.logical_verification, "not_performed")
        self.assertEqual(evidence.replay_verification, "not_performed")
        self.assertEqual(evidence.proof_parity, "not_claimed")
        self.assertEqual(evidence.row_capture_digest, row_digest)
        self.assertEqual(evidence.branch.branch_id, "c0")
        self.assertTrue(evidence.branch.conditions)
        self.assertFalse(hasattr(evidence, "paths"))
        self.assertFalse(hasattr(evidence, "metadata"))
        self.assertFalse(hasattr(evidence, "to_bytes"))
        self.assertFalse(hasattr(CapturedReceiptEvidenceV0, "from_bytes"))
        self.assertNotIn("policy", CapturedReceiptEvidenceV0.__dataclass_fields__)
        self.assertNotIn("values", CapturedReceiptEvidenceV0.__dataclass_fields__)
        self.assertNotIn("build_captured_receipt_evidence_v0", application.__all__)
        self.assertNotIn("CapturedReceiptEvidenceV0", application_protocol.__all__)
        self.assertNotIn("build_captured_receipt_evidence_v0", sdk.__all__)
        self.assertNotIn("CapturedReceiptEvidenceV0", sdk.__all__)
        self.assertFalse(hasattr(application, "build_captured_receipt_evidence_v0"))
        self.assertFalse(hasattr(application_protocol, "CapturedReceiptEvidenceV0"))
        self.assertFalse(hasattr(sdk, "build_captured_receipt_evidence_v0"))
        self.assertFalse(hasattr(sdk, "CapturedReceiptEvidenceV0"))
        for facade_import in (
            _import_application_builder_from_facade,
            _import_protocol_dto_from_facade,
            _import_sdk_builder_from_facade,
            _import_sdk_dto_from_facade,
        ):
            with self.assertRaises(ImportError):
                facade_import()
        for forbidden_name in (
            "EvidenceGraph",
            "PolicyLineage",
            "evaluation_run_bundle_evidence",
            "verify_evaluation_run_bundle",
        ):
            self.assertNotIn(forbidden_name, receipt_runtime.__dict__)

        captured_assertion_ids = {
            assertion_id
            for relation in bundle.relations
            for assertion_id, _values in relation.facts
        }
        for condition in evidence.branch.conditions:
            if condition.native_kind == "pred":
                self.assertIsNotNone(condition.predicate_id)
                self.assertIsNone(condition.captured_step_kind)
                self.assertTrue(condition.assertion_ids)
                self.assertEqual(condition.assertion_ids, tuple(sorted(condition.assertion_ids)))
                self.assertTrue(set(condition.assertion_ids) <= captured_assertion_ids)
            else:
                self.assertIsNone(condition.predicate_id)
                self.assertEqual(condition.assertion_ids, ())
                self.assertEqual(condition.captured_step_kind, condition.native_kind)
        evidence.validate()

    def test_capture_dto_is_rejected_by_generic_graph_and_explanation_consumers(self) -> None:
        _graph, _rule, bundle = _capture()
        evidence = receipt_runtime.build_captured_receipt_evidence_v0(
            bundle,
            row_capture_digest=bundle.rows[0].row_capture_digest,
        )

        with self.assertRaisesRegex(ValueError, "EvidenceGraph"):
            walk_evidence(evidence)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "EvidenceGraph"):
            narrate_evidence(evidence)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "EvidenceGraph"):
            evidence_graph_to_dict(evidence)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ProtocolShapeError, "EvidenceGraph"):
            Explanation(
                status="passed",
                evidence=evidence,  # type: ignore[arg-type]
                row=None,
                result_id=bundle.run_anchor.result_id,
            )

    def test_bundle_snapshot_precedes_all_selector_checks_and_ambiguity_fails_closed(self) -> None:
        _graph, _rule, bundle = _capture()
        forged = deepcopy(bundle)
        object.__setattr__(forged, "bundle_digest", _ZERO_TOKEN)
        for selector in ("", None, _ZERO_TOKEN):
            with self.assertRaisesRegex(ProtocolShapeError, "bundle_digest"):
                receipt_runtime.build_captured_receipt_evidence_v0(
                    forged,
                    row_capture_digest=selector,  # type: ignore[arg-type]
                )

        with self.assertRaisesRegex(ProtocolShapeError, "non-empty"):
            receipt_runtime.build_captured_receipt_evidence_v0(
                bundle,
                row_capture_digest="",
            )
        with self.assertRaisesRegex(ProtocolShapeError, "not found"):
            receipt_runtime.build_captured_receipt_evidence_v0(
                bundle,
                row_capture_digest=_ZERO_TOKEN,
            )

        row = bundle.rows[0]
        with self.assertRaisesRegex(ProtocolShapeError, "ambiguous"):
            receipt_runtime._select_snapshot_row(
                (row, row),
                row.row_capture_digest,
            )

    def test_fresh_decode_snapshot_blocks_toctou_mutation(self) -> None:
        _graph, _rule, bundle = _capture()
        row_digest = bundle.rows[0].row_capture_digest
        original_row_id = bundle.rows[0].row_id
        original_decoder = receipt_runtime.evaluation_run_bundle_from_bytes

        def decode_after_hostile_mutation(raw: bytes):
            object.__setattr__(bundle, "rows", ())
            object.__setattr__(bundle, "relations", ())
            return original_decoder(raw)

        with patch.object(
            receipt_runtime,
            "evaluation_run_bundle_from_bytes",
            side_effect=decode_after_hostile_mutation,
        ):
            evidence = receipt_runtime.build_captured_receipt_evidence_v0(
                bundle,
                row_capture_digest=row_digest,
            )
        self.assertEqual(evidence.row_id, original_row_id)
        self.assertTrue(evidence.branch.conditions)

    def test_nested_seals_reject_mutation_and_cross_bundle_splicing(self) -> None:
        _graph, _rule, bundle = _capture()
        evidence = receipt_runtime.build_captured_receipt_evidence_v0(
            bundle,
            row_capture_digest=bundle.rows[0].row_capture_digest,
        )
        condition = evidence.branch.conditions[0]

        with self.assertRaisesRegex(ProtocolShapeError, "condition digest is stale"):
            replace(condition, capture_context_digest=_ZERO_TOKEN)
        with self.assertRaisesRegex(ProtocolShapeError, "branch digest is stale"):
            replace(evidence.branch, branch_digest=_ZERO_TOKEN)
        with self.assertRaisesRegex(ProtocolShapeError, "evidence digest is stale"):
            replace(evidence, row_id="opaque-row-linkage-tampered")

        nested_mutation = replace(evidence)
        object.__setattr__(nested_mutation.branch.conditions[0], "condition_digest", _ZERO_TOKEN)
        with self.assertRaisesRegex(ProtocolShapeError, "condition digest is stale"):
            nested_mutation.validate()

        _other_graph, _other_rule, other_bundle = _capture()
        other = receipt_runtime.build_captured_receipt_evidence_v0(
            other_bundle,
            row_capture_digest=other_bundle.rows[0].row_capture_digest,
        )
        with self.assertRaisesRegex(ProtocolShapeError, "foreign context"):
            replace(
                evidence.branch,
                conditions=(other.branch.conditions[0], *evidence.branch.conditions[1:]),
            )

    def test_policy_lineage_changes_do_not_change_native_receipt_inventory(self) -> None:
        _graph, _rule, bundle = _capture()
        baseline = receipt_runtime.build_captured_receipt_evidence_v0(
            bundle,
            row_capture_digest=bundle.rows[0].row_capture_digest,
        )
        lineage_only_mutation = _with_resealed_lineage_source_index(bundle)
        mutated = receipt_runtime.build_captured_receipt_evidence_v0(
            lineage_only_mutation,
            row_capture_digest=lineage_only_mutation.rows[0].row_capture_digest,
        )

        self.assertEqual(_native_inventory(mutated), _native_inventory(baseline))
        self.assertNotIn("policy", CapturedReceiptEvidenceV0.__dataclass_fields__)
        self.assertNotIn("occurrence_alias", mutated.branch.__dataclass_fields__)
        self.assertNotIn("rule_id", mutated.branch.__dataclass_fields__)

    def test_unpinned_or_mismatched_profile_is_not_verification_or_authenticity(self) -> None:
        _graph, _rule, bundle = _capture()
        profile = bundle.run_anchor.execution_profile
        unpinned = _with_profile(
            bundle,
            replace(
                profile,
                engine_version=None,
                adapter_version=None,
                version_pinning="incomplete",
            ),
        )
        mismatched = _with_profile(
            bundle,
            replace(
                profile,
                engine_version="other-native-version",
                adapter_version="other-adapter-version",
                version_pinning="complete",
            ),
        )

        for candidate in (unpinned, mismatched):
            with (
                patch(
                    "factgraph.core.rules.ruleref_substrate.evaluate_native_where",
                    side_effect=AssertionError("receipt capture must not evaluate"),
                ) as evaluator,
                patch(
                    "factgraph.application.evaluation_run_verification_runtime."
                    "verify_evaluation_run_bundle",
                    side_effect=AssertionError("receipt capture must not verify"),
                ) as verifier,
            ):
                evidence = receipt_runtime.build_captured_receipt_evidence_v0(
                    candidate,
                    row_capture_digest=candidate.rows[0].row_capture_digest,
                )
            evaluator.assert_not_called()
            verifier.assert_not_called()
            self.assertEqual(evidence.authenticity, "unverified")
            self.assertEqual(evidence.logical_verification, "not_performed")
            self.assertEqual(evidence.replay_verification, "not_performed")
            self.assertEqual(evidence.proof_parity, "not_claimed")

    def test_runtime_has_no_graph_or_execution_seam_import_or_call(self) -> None:
        tree = ast.parse(inspect.getsource(receipt_runtime))
        forbidden_modules = {
            "evaluation_run_evidence_runtime",
            "evaluation_run_verification_runtime",
            "explain",
            "factgraph.application.evaluation_run_evidence_runtime",
            "factgraph.application.evaluation_run_verification_runtime",
            "factgraph.application.explain",
            "factgraph.core.store.runtime",
        }
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        self.assertTrue(imported_modules.isdisjoint(forbidden_modules))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertTrue(
            {
                "evaluation_run_bundle_evidence",
                "verify_evaluation_run_bundle",
                "evaluate_native_where",
                "Store",
            }.isdisjoint(imported_names)
        )
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(
            {
                "evaluation_run_bundle_evidence",
                "verify_evaluation_run_bundle",
                "evaluate_native_where",
                "Store",
            }.isdisjoint(called_names)
        )


if __name__ == "__main__":
    unittest.main()
