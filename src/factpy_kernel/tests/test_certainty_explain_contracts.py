from __future__ import annotations

import json
import unittest
from math import inf, nan
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.adapters.problog.problog_import import parse_problog_output
from factpy_kernel.audit import AuditQuery, load_audit_package, render_audit_static_site
from factpy_kernel.audit.static_ui import _slug_id
from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.core.annotation import derive_certainty_summary
from factpy_kernel.core.derivation.candidates import make_candidate
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError
from factpy_kernel.core.store._candidate_evidence_tree_narrative import render_candidate_evidence_tree_narrative
from factpy_kernel.core.store._candidate_evidence_tree_nl import render_candidate_evidence_tree_nl_explain
from factpy_kernel.core.store._confidence_kind_resolver import check_certainty_artifact_eligibility
from factpy_kernel.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    PredWitness,
    RuleRefEdge,
    SupportArtifact,
    compute_support_digest,
    normalize_binding_items,
    support_artifact_from_dict,
)
from factpy_kernel.sdk import SDKStore
from factpy_kernel.service._certainty_service import _lookup_condition_weights_for_candidate
from factpy_kernel.service.runtime_v1 import (
    accept_runtime_derivation,
    evaluate_runtime_derivation,
    export_runtime_package,
    _get_candidate_tree,
    _require_session,
    close_runtime_session,
    explain_runtime_narrative,
    explain_runtime_nl,
    explain_runtime_summary,
    explain_runtime_tree,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)

from factpy_kernel.tests._test_helpers import (
    User,
    _register_exposed_user_tag_rule,
    _seed_users_for_syntax_matrix,
)


def _skip_without_souffle(testcase: unittest.TestCase) -> None:
    from factpy_kernel.adapters.souffle.runner import find_souffle_binary

    if find_souffle_binary() is None:
        testcase.skipTest("souffle binary is unavailable; skipping provenance audit test")


def _export_single_candidate_audit_package_with_provenance(
    *,
    registry_root: str,
    tmp_dir: str,
) -> tuple[str, str]:
    sdk = SDKStore([User])
    refs = _seed_users_for_syntax_matrix(sdk)
    _register_exposed_user_tag_rule(
        sdk,
        registry_root,
        condition_weights={"b0.a0": 0.8},
    )

    reset_runtime_sessions_for_tests()
    open_resp = open_runtime_session({"registry_root": registry_root})
    if not open_resp["ok"]:
        raise AssertionError(f"open_runtime_session failed: {open_resp}")
    session_id = open_resp["session"]["session_id"]
    try:
        write_resp = write_runtime_fact(
            session_id,
            {
                "pred_id": "user:tag",
                "e_ref": refs["u1"],
                "rest_terms": [["string", "vip"]],
            },
            kind="add",
        )
        if not write_resp["ok"]:
            raise AssertionError(f"write_runtime_fact failed: {write_resp}")

        eval_resp = evaluate_runtime_derivation(
            session_id,
            {
                "derivation": {
                    "derivation_id": "drv.provenance.audit",
                    "version": "1.0.0",
                    "target": "user:tag",
                    "head_vars": ["$u", "$tag"],
                    "where": [
                        ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                        ["eq", "$tag", "vip"],
                    ],
                    "mode": "native",
                }
            },
        )
        if not eval_resp["ok"]:
            raise AssertionError(f"evaluate_runtime_derivation failed: {eval_resp}")
        candidate = dict(eval_resp["evaluation"]["candidates"][0])

        accept_resp = accept_runtime_derivation(
            session_id,
            {
                "candidate": candidate,
                "options": {"approved_by": "alice"},
            },
        )
        if not accept_resp["ok"]:
            raise AssertionError(f"accept_runtime_derivation failed: {accept_resp}")

        package_dir = str(Path(tmp_dir) / "audit_package")
        export_resp = export_runtime_package(
            session_id,
            {"out_dir": package_dir, "package_kind": "audit"},
        )
        if not export_resp["ok"]:
            raise AssertionError(f"export_runtime_package failed: {export_resp}")
        return package_dir, candidate["candidate_id"]
    finally:
        close_runtime_session(session_id)
        reset_runtime_sessions_for_tests()


def _base_certainty_tree(condition_node: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "candidate_evidence_tree",
        "root": {
            "node_id": "candidate:test",
            "node_kind": "candidate_result",
            "children": [
                {
                    "node_id": "support:test",
                    "node_kind": "support_section",
                    "children": [condition_node],
                }
            ],
        },
    }


def _predicate_condition_node(*, atom_key: str = "b0.a0:user:tag", **extra: Any) -> dict[str, Any]:
    node = {
        "node_id": f"pred:{atom_key}",
        "node_kind": "predicate_witness_group",
        "pred_atom_key": atom_key,
        "pred_id": "user:tag",
        "assertion_count": 1,
        "children": [],
    }
    node.update(extra)
    return node


def _row_support_artifact(*, e_ref: str, asrt_id: str):
    return support_artifact_from_dict(
        {
            "kind": "native_binding_v1",
            "root_result_kind": "row",
            "binding": [["$tag", "vip"], ["$u", e_ref]],
            "pred_witnesses": [
                {
                    "pred_atom_key": "b0.a0:user:tag",
                    "asrt_ids": [asrt_id],
                }
            ],
            "non_fact_steps": [],
            "rule_refs": [],
            "rule_ref_edges": [],
        }
    )


def _top_rule_ref_support_artifact(
    *,
    e_ref: str,
    rule_ref_id: str = "q.child_rule",
    child_support_digest: str | None,
    unresolved_reason: str | None = None,
):
    return support_artifact_from_dict(
        {
            "kind": "native_binding_v1",
            "root_result_kind": "fact",
            "binding": [["$tag", "vip"], ["$u", e_ref]],
            "pred_witnesses": [],
            "non_fact_steps": [
                {
                    "step_key": "b0.a0:ruleref",
                    "kind": "ruleref",
                    "status": "satisfied",
                    "details": [],
                }
            ],
            "rule_refs": [rule_ref_id],
            "rule_ref_edges": [
                {
                    "ruleref_atom_key": "b0.a0:ruleref",
                    "rule_ref_id": rule_ref_id,
                    "rule_ref_version": "1.0.0",
                    "child_support_digest": child_support_digest,
                    "unresolved_reason": unresolved_reason,
                }
            ],
        }
    )


def _remember_artifact(session_id: str, artifact: Any, *, digest: str | None = None) -> str:
    session = _require_session(session_id)
    support_digest = digest or compute_support_digest(artifact)
    session.store._remember_support_artifact(support_digest, artifact)
    return support_digest


def _remember_resolved_single_rule_candidate(
    session_id: str,
    *,
    e_ref: str,
    asrt_id: str,
    candidate_id: str,
    confidence_kind: str,
    rule_ref_id: str = "q.child_rule",
) -> str:
    child_support_digest = _remember_artifact(
        session_id,
        _row_support_artifact(e_ref=e_ref, asrt_id=asrt_id),
    )
    support_digest = _remember_artifact(
        session_id,
        _top_rule_ref_support_artifact(
            e_ref=e_ref,
            rule_ref_id=rule_ref_id,
            child_support_digest=child_support_digest,
        ),
    )
    _require_session(session_id).store._remember_candidate_support(
        candidate_id,
        support_digest,
        "native_binding_v1",
        confidence_kind=confidence_kind,
    )
    return support_digest


class CertaintyExplainContractsTests(unittest.TestCase):
    def test_candidate_tree_narrative_adds_certainty_lines_when_provided(self) -> None:
        summary = {
            "candidate_id": "cand-certainty",
            "support_kind": "native_binding_v1",
            "is_degraded": False,
            "root_result_kind": "fact",
            "node_count_by_role": {
                "structural": 2,
                "witness": 1,
                "constraint": 1,
                "rule_chain": 1,
                "terminal": 0,
                "degraded": 0,
            },
            "witness_assertion_count": 1,
            "rule_ref_count": 1,
            "recursive_depth": 1,
            "has_unresolved": False,
            "has_boundary": False,
            "unresolved_reasons": [],
            "boundary_reasons": [],
        }
        narrative = render_candidate_evidence_tree_narrative(
            summary,
            certainty_summary={
                "confidence_kind": "certainty",
                "condition_count": 2,
                "weighted_condition_count": 1,
                "conditions": [
                    {
                        "atom_key": "b0.a0",
                        "node_kind": "predicate_witness_group",
                        "weight": 0.8,
                        "impact": 0.64,
                    },
                    {
                        "atom_key": "b0.a1",
                        "node_kind": "non_fact_check",
                        "weight": None,
                        "impact": None,
                    },
                ],
                "aggregate_certainty": 0.64,
            },
        )

        self.assertEqual(
            narrative["certainty_lines"],
            [
                "Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.64.",
                "Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.64. [bottleneck]",
                "Condition b0.a1 (non_fact_check): unweighted.",
            ],
        )
        self.assertEqual(
            narrative["certainty_bottleneck"],
            {"atom_keys": ["b0.a0"], "impact": 0.64},
        )

    def test_candidate_tree_nl_appends_certainty_paragraph_from_narrative(self) -> None:
        summary = {
            "candidate_id": "cand-certainty",
            "support_kind": "native_binding_v1",
            "is_degraded": False,
            "root_result_kind": "fact",
        }
        narrative = {
            "headline": "Candidate cand-certainty uses support kind native_binding_v1 across 4 tree node(s).",
            "overview_lines": ["Root result kind: fact."],
            "evidence_lines": ["Witness assertions: 1."],
            "rule_chain_lines": ["Rule reference nodes: 1."],
            "terminal_lines": ["No unresolved support or recursion boundaries were encountered."],
            "drilldown_lines": ["Open linked assertion nodes to inspect witness facts."],
            "certainty_lines": [
                "Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.8.",
                "Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.8.",
            ],
        }

        explain_nl = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")

        self.assertEqual(len(explain_nl["paragraphs"]), 5)
        self.assertEqual(
            explain_nl["paragraphs"][4],
            "Certainty summary: Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.8. Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.8.",
        )

    def test_nl_certainty_paragraph_includes_single_bottleneck_sentence(self) -> None:
        summary = {
            "candidate_id": "cand-bn1",
            "support_kind": "native_binding_v1",
            "is_degraded": False,
            "root_result_kind": "fact",
        }
        narrative = {
            "headline": "Candidate cand-bn1 headline.",
            "overview_lines": ["Overview."],
            "evidence_lines": ["Evidence."],
            "rule_chain_lines": ["Rule chain."],
            "terminal_lines": ["Terminal."],
            "drilldown_lines": ["Drilldown."],
            "certainty_lines": [
                "Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.24.",
                "Condition b0.a0 (predicate_witness_group): weight=0.4, impact=0.24. [bottleneck]",
                "Condition b0.a1 (predicate_witness_group): weight=0.6, impact=0.54.",
            ],
            "certainty_bottleneck": {"atom_keys": ["b0.a0"], "impact": 0.24},
        }
        result = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertIn(
            "The weakest condition is b0.a0 with impact 0.24.",
            result["paragraphs"][4],
        )

    def test_nl_certainty_paragraph_includes_dual_bottleneck_sentence(self) -> None:
        summary = {
            "candidate_id": "cand-bn2",
            "support_kind": "native_binding_v1",
            "is_degraded": False,
            "root_result_kind": "fact",
        }
        narrative = {
            "headline": "Candidate cand-bn2 headline.",
            "overview_lines": ["Overview."],
            "evidence_lines": ["Evidence."],
            "rule_chain_lines": ["Rule chain."],
            "terminal_lines": ["Terminal."],
            "drilldown_lines": ["Drilldown."],
            "certainty_lines": ["Certainty line."],
            "certainty_bottleneck": {"atom_keys": ["b0.a0", "b0.a1"], "impact": 0.3},
        }
        result = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertIn(
            "The weakest conditions are b0.a0 and b0.a1, each with impact 0.3.",
            result["paragraphs"][4],
        )

    def test_nl_certainty_paragraph_includes_triple_bottleneck_sentence(self) -> None:
        summary = {
            "candidate_id": "cand-bn3",
            "support_kind": "native_binding_v1",
            "is_degraded": False,
            "root_result_kind": "fact",
        }
        narrative = {
            "headline": "Candidate cand-bn3 headline.",
            "overview_lines": ["Overview."],
            "evidence_lines": ["Evidence."],
            "rule_chain_lines": ["Rule chain."],
            "terminal_lines": ["Terminal."],
            "drilldown_lines": ["Drilldown."],
            "certainty_lines": ["Certainty line."],
            "certainty_bottleneck": {"atom_keys": ["b0.a0", "b0.a1", "b0.a2"], "impact": 0.2},
        }
        result = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertIn(
            "There are 3 equally weak conditions (impact 0.2): b0.a0, b0.a1, and b0.a2.",
            result["paragraphs"][4],
        )

    def test_confidence_meta_requires_float_in_range(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-conf", locale="zh")

        with self.assertRaises(WriteProtocolError) as ctx_int:
            sdk.set(User.name, ref, "Alice", meta={"confidence": 1})
        self.assertIn("meta[confidence] must be float", str(ctx_int.exception))

        with self.assertRaises(WriteProtocolError) as ctx_range:
            sdk.set(User.name, ref, "Alice", meta={"confidence": 1.5})
        self.assertIn("within (0,1]", str(ctx_range.exception))

    def test_candidate_confidence_kind_defaults_validates_and_preserves_identity(self) -> None:
        base = make_candidate(
            derivation_id="drv.conf",
            derivation_version="1.0.0",
            run_id="run-conf",
            target="user:tag",
            key_terms=[("string", "user:tag"), ("entity_ref", "idref_v1:User:user_id=u1,locale=de")],
            payload={
                "pred_id": "user:tag",
                "terms": [
                    {"kind": "entity_ref", "value": "idref_v1:User:user_id=u1,locale=de"},
                    {"kind": "literal", "tag": "string", "value": "vip"},
                ],
            },
            support_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            support_kind="native_binding_v1",
            generated_at=1,
            tup_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            confidence=0.42,
        )
        self.assertEqual(base.confidence_kind, "none")

        probability = make_candidate(
            derivation_id="drv.conf",
            derivation_version="1.0.0",
            run_id="run-conf",
            target="user:tag",
            key_terms=[("string", "user:tag"), ("entity_ref", "idref_v1:User:user_id=u1,locale=de")],
            payload={
                "pred_id": "user:tag",
                "terms": [
                    {"kind": "entity_ref", "value": "idref_v1:User:user_id=u1,locale=de"},
                    {"kind": "literal", "tag": "string", "value": "vip"},
                ],
            },
            support_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            support_kind="native_binding_v1",
            generated_at=1,
            tup_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            confidence=0.42,
            confidence_kind="probability",
        )
        self.assertEqual(probability.confidence_kind, "probability")
        self.assertEqual(probability.candidate_key, base.candidate_key)
        self.assertEqual(probability.candidate_id, base.candidate_id)

        with self.assertRaises(ValueError) as ctx_invalid:
            make_candidate(
                derivation_id="drv.conf",
                derivation_version="1.0.0",
                run_id="run-conf",
                target="user:tag",
                key_terms=[("string", "user:tag"), ("entity_ref", "idref_v1:User:user_id=u1,locale=de")],
                payload={
                    "pred_id": "user:tag",
                    "terms": [
                        {"kind": "entity_ref", "value": "idref_v1:User:user_id=u1,locale=de"},
                        {"kind": "literal", "tag": "string", "value": "vip"},
                    ],
                },
                support_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
                support_kind="native_binding_v1",
                generated_at=1,
                tup_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
                confidence_kind="score",
            )
        self.assertIn("confidence_kind must be one of", str(ctx_invalid.exception))

    def test_problog_parse_output_sets_probability_confidence_kind(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u1", locale="de")

        candidates = parse_problog_output(
            f'answer("{ref}","vip"): 0.42',
            {
                "store": sdk.store,
                "query_vars": ["$u", "$tag"],
                "derivation_id": "drv.problog.tag",
                "version": "1.0.0",
                "target_pred_id": "user:tag",
                "head_vars": ["$u", "$tag"],
            },
            sdk.ledger,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].confidence, 0.42)
        self.assertEqual(candidates[0].confidence_kind, "probability")
        self.assertEqual(candidates[0].support_kind, ENGINE_NO_WITNESS_KIND)

    def test_problog_parse_output_accepts_tab_format_with_trailing_colon(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u1", locale="de")

        candidates = parse_problog_output(
            f'answer("{ref}","vip"):\t0.42',
            {
                "store": sdk.store,
                "query_vars": ["$u", "$tag"],
                "derivation_id": "drv.problog.tag",
                "version": "1.0.0",
                "target_pred_id": "user:tag",
                "head_vars": ["$u", "$tag"],
            },
            sdk.ledger,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].confidence, 0.42)
        self.assertEqual(candidates[0].confidence_kind, "probability")

    def test_candidate_summary_certainty_uses_override_registry_root_and_child_rule_weights(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as wrong_root, TemporaryDirectory() as right_root:
            FileAuthoringRegistry(Path(wrong_root)).upsert_schema_ir(sdk.schema_ir)
            _register_exposed_user_tag_rule(
                sdk,
                right_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": wrong_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                asrt_id = write_resp["write"]["assertion_id"]

                _remember_resolved_single_rule_candidate(
                    session_id,
                    e_ref=refs["u1"],
                    asrt_id=asrt_id,
                    candidate_id="cand-certainty",
                    confidence_kind="certainty",
                )

                no_override_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": "cand-certainty"})
                self.assertTrue(no_override_resp["ok"])
                self.assertIsNone(no_override_resp["certainty_summary"])

                summary_resp = explain_runtime_summary(
                    session_id,
                    {
                        "kind": "candidate",
                        "id": "cand-certainty",
                        "override_registry_root": right_root,
                    },
                )
                self.assertTrue(summary_resp["ok"])
                certainty = summary_resp["certainty_summary"]
                self.assertIsNotNone(certainty)
                self.assertEqual(certainty["confidence_kind"], "certainty")
                self.assertEqual(certainty["condition_count"], 1)
                self.assertEqual(certainty["weighted_condition_count"], 1)
                self.assertEqual(
                    certainty["conditions"],
                    [
                        {
                            "atom_key": "b0.a0",
                            "node_kind": "predicate_witness_group",
                            "weight": 0.8,
                            "impact": 0.8,
                        }
                    ],
                )
                self.assertEqual(certainty["aggregate_certainty"], 0.8)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_candidate_summary_certainty_all_unweighted_when_rule_has_no_condition_weights(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(sdk, registry_root)

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                asrt_id = write_resp["write"]["assertion_id"]

                _remember_resolved_single_rule_candidate(
                    session_id,
                    e_ref=refs["u1"],
                    asrt_id=asrt_id,
                    candidate_id="cand-certainty-unweighted",
                    confidence_kind="certainty",
                )

                summary_resp = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": "cand-certainty-unweighted"},
                )
                self.assertTrue(summary_resp["ok"])
                certainty = summary_resp["certainty_summary"]
                self.assertIsNotNone(certainty)
                self.assertEqual(certainty["condition_count"], 1)
                self.assertEqual(certainty["weighted_condition_count"], 0)
                self.assertEqual(certainty["conditions"][0]["atom_key"], "b0.a0")
                self.assertIsNone(certainty["conditions"][0]["weight"])
                self.assertIsNone(certainty["conditions"][0]["impact"])
                self.assertIsNone(certainty["aggregate_certainty"])
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_candidate_runtime_narrative_and_nl_add_certainty_only_with_matching_registry_root(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as wrong_root, TemporaryDirectory() as right_root:
            FileAuthoringRegistry(Path(wrong_root)).upsert_schema_ir(sdk.schema_ir)
            _register_exposed_user_tag_rule(
                sdk,
                right_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": wrong_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                asrt_id = write_resp["write"]["assertion_id"]

                _remember_resolved_single_rule_candidate(
                    session_id,
                    e_ref=refs["u1"],
                    asrt_id=asrt_id,
                    candidate_id="cand-certainty-runtime",
                    confidence_kind="certainty",
                )

                no_override_narrative = explain_runtime_narrative(
                    session_id,
                    {"kind": "candidate", "id": "cand-certainty-runtime"},
                )
                no_override_nl = explain_runtime_nl(
                    session_id,
                    {"kind": "candidate", "id": "cand-certainty-runtime"},
                )
                self.assertTrue(no_override_narrative["ok"])
                self.assertTrue(no_override_nl["ok"])
                self.assertNotIn("certainty_lines", no_override_narrative["narrative"])
                self.assertEqual(len(no_override_nl["explain_nl"]["paragraphs"]), 4)

                narrative_resp = explain_runtime_narrative(
                    session_id,
                    {
                        "kind": "candidate",
                        "id": "cand-certainty-runtime",
                        "override_registry_root": right_root,
                    },
                )
                nl_resp = explain_runtime_nl(
                    session_id,
                    {
                        "kind": "candidate",
                        "id": "cand-certainty-runtime",
                        "override_registry_root": right_root,
                    },
                )
                self.assertTrue(narrative_resp["ok"])
                self.assertTrue(nl_resp["ok"])
                self.assertEqual(
                    narrative_resp["narrative"]["certainty_lines"],
                    [
                        "Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.8.",
                        "Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.8. [bottleneck]",
                    ],
                )
                self.assertEqual(
                    narrative_resp["narrative"]["certainty_bottleneck"],
                    {"atom_keys": ["b0.a0"], "impact": 0.8},
                )
                self.assertEqual(len(nl_resp["explain_nl"]["paragraphs"]), 5)
                self.assertEqual(
                    nl_resp["explain_nl"]["paragraphs"][4],
                    "Certainty summary: Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.8. Condition b0.a0 (predicate_witness_group): weight=0.8, impact=0.8. [bottleneck] The weakest condition is b0.a0 with impact 0.8.",
                )
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_candidate_summary_non_certainty_lanes_return_null_certainty_summary(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            _remember_resolved_single_rule_candidate(
                session_id,
                e_ref=refs["u1"],
                asrt_id=asrt_id,
                candidate_id="cand-none",
                confidence_kind="none",
            )
            _remember_resolved_single_rule_candidate(
                session_id,
                e_ref=refs["u1"],
                asrt_id=asrt_id,
                candidate_id="cand-probability",
                confidence_kind="probability",
            )

            none_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": "cand-none"})
            probability_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": "cand-probability"})
            self.assertTrue(none_resp["ok"])
            self.assertTrue(probability_resp["ok"])
            self.assertIsNone(none_resp["certainty_summary"])
            self.assertIsNone(probability_resp["certainty_summary"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_candidate_summary_certainty_null_for_multiple_rule_ref_edges(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            child_a = _row_support_artifact(e_ref=refs["u1"], asrt_id=asrt_id)
            child_b = _row_support_artifact(e_ref=refs["u1"], asrt_id=asrt_id)
            child_support_digest_a = _remember_artifact(session_id, child_a, digest="sha256:" + ("aa" * 32))
            child_support_digest_b = _remember_artifact(session_id, child_b, digest="sha256:" + ("bb" * 32))

            top_artifact = support_artifact_from_dict(
                {
                    "kind": "native_binding_v1",
                    "root_result_kind": "fact",
                    "binding": [["$tag", "vip"], ["$u", refs["u1"]]],
                    "pred_witnesses": [],
                    "non_fact_steps": [
                        {"step_key": "b0.a0:ruleref", "kind": "ruleref", "status": "satisfied", "details": []},
                        {"step_key": "b0.a1:ruleref", "kind": "ruleref", "status": "satisfied", "details": []},
                    ],
                    "rule_refs": ["q.child_rule_a", "q.child_rule_b"],
                    "rule_ref_edges": [
                        {
                            "ruleref_atom_key": "b0.a0:ruleref",
                            "rule_ref_id": "q.child_rule_a",
                            "rule_ref_version": "1.0.0",
                            "child_support_digest": child_support_digest_a,
                            "unresolved_reason": None,
                        },
                        {
                            "ruleref_atom_key": "b0.a1:ruleref",
                            "rule_ref_id": "q.child_rule_b",
                            "rule_ref_version": "1.0.0",
                            "child_support_digest": child_support_digest_b,
                            "unresolved_reason": None,
                        },
                    ],
                }
            )
            support_digest = _remember_artifact(session_id, top_artifact, digest="sha256:" + ("cc" * 32))
            _require_session(session_id).store._remember_candidate_support(
                "cand-multi-rule",
                support_digest,
                "native_binding_v1",
                confidence_kind="certainty",
            )

            summary_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": "cand-multi-rule"})
            self.assertTrue(summary_resp["ok"])
            self.assertIsNone(summary_resp["certainty_summary"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_candidate_summary_certainty_null_for_nested_referenced_support(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            grandchild_support_digest = _remember_artifact(
                session_id,
                _row_support_artifact(e_ref=refs["u1"], asrt_id=asrt_id),
                digest="sha256:" + ("dd" * 32),
            )
            child_artifact = support_artifact_from_dict(
                {
                    "kind": "native_binding_v1",
                    "root_result_kind": "row",
                    "binding": [["$tag", "vip"], ["$u", refs["u1"]]],
                    "pred_witnesses": [],
                    "non_fact_steps": [
                        {"step_key": "b0.a0:ruleref", "kind": "ruleref", "status": "satisfied", "details": []},
                    ],
                    "rule_refs": ["q.grandchild_rule"],
                    "rule_ref_edges": [
                        {
                            "ruleref_atom_key": "b0.a0:ruleref",
                            "rule_ref_id": "q.grandchild_rule",
                            "rule_ref_version": "1.0.0",
                            "child_support_digest": grandchild_support_digest,
                            "unresolved_reason": None,
                        }
                    ],
                }
            )
            child_support_digest = _remember_artifact(session_id, child_artifact, digest="sha256:" + ("ee" * 32))
            top_support_digest = _remember_artifact(
                session_id,
                _top_rule_ref_support_artifact(
                    e_ref=refs["u1"],
                    child_support_digest=child_support_digest,
                ),
                digest="sha256:" + ("ff" * 32),
            )
            _require_session(session_id).store._remember_candidate_support(
                "cand-nested-rule",
                top_support_digest,
                "native_binding_v1",
                confidence_kind="certainty",
            )

            summary_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": "cand-nested-rule"})
            self.assertTrue(summary_resp["ok"])
            self.assertIsNone(summary_resp["certainty_summary"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_candidate_summary_certainty_null_for_unresolved_child_support(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                support_digest = _remember_artifact(
                    session_id,
                    _top_rule_ref_support_artifact(
                        e_ref=refs["u1"],
                        child_support_digest=None,
                        unresolved_reason="child_support_unavailable",
                    ),
                    digest="sha256:" + ("ab" * 32),
                )
                _require_session(session_id).store._remember_candidate_support(
                    "cand-unresolved-certainty",
                    support_digest,
                    "native_binding_v1",
                    confidence_kind="certainty",
                )

                summary_resp = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": "cand-unresolved-certainty"},
                )
                self.assertTrue(summary_resp["ok"])
                self.assertIsNone(summary_resp["certainty_summary"])
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_derive_certainty_summary_rejects_invalid_tree_dict_type(self) -> None:
        with self.assertRaises(ValueError):
            derive_certainty_summary([], {"b0.a0": 0.8}, "certainty")  # type: ignore[arg-type]

    def test_derive_certainty_summary_rejects_invalid_condition_weights_type(self) -> None:
        with self.assertRaises(ValueError):
            derive_certainty_summary(_base_certainty_tree(_predicate_condition_node()), [], "certainty")  # type: ignore[arg-type]

    def test_condition_weight_rejects_non_numeric_value(self) -> None:
        with self.assertRaises(ValueError):
            derive_certainty_summary(
                _base_certainty_tree(_predicate_condition_node()),
                {"b0.a0": "heavy"},
                "certainty",
            )

    def test_condition_weight_rejects_non_positive_or_non_finite_value(self) -> None:
        tree = _base_certainty_tree(_predicate_condition_node())
        for invalid_value in (0, -1, inf, nan):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    derive_certainty_summary(tree, {"b0.a0": invalid_value}, "certainty")

    def test_tri_state_lookup_none_vs_empty_vs_populated(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                rule_id="q.weighted_rule",
                condition_weights={"b0.a0": 0.8},
            )
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                rule_id="q.unweighted_rule",
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                asrt_id = write_resp["write"]["assertion_id"]

                _remember_resolved_single_rule_candidate(
                    session_id,
                    e_ref=refs["u1"],
                    asrt_id=asrt_id,
                    candidate_id="cand-weighted",
                    confidence_kind="certainty",
                    rule_ref_id="q.weighted_rule",
                )
                _remember_resolved_single_rule_candidate(
                    session_id,
                    e_ref=refs["u1"],
                    asrt_id=asrt_id,
                    candidate_id="cand-unweighted",
                    confidence_kind="certainty",
                    rule_ref_id="q.unweighted_rule",
                )

                child_a = _row_support_artifact(e_ref=refs["u1"], asrt_id=asrt_id)
                child_b = _row_support_artifact(e_ref=refs["u1"], asrt_id=asrt_id)
                child_support_digest_a = _remember_artifact(session_id, child_a, digest="sha256:" + ("11" * 32))
                child_support_digest_b = _remember_artifact(session_id, child_b, digest="sha256:" + ("22" * 32))
                multi_artifact = support_artifact_from_dict(
                    {
                        "kind": "native_binding_v1",
                        "root_result_kind": "fact",
                        "binding": [["$tag", "vip"], ["$u", refs["u1"]]],
                        "pred_witnesses": [],
                        "non_fact_steps": [
                            {"step_key": "b0.a0:ruleref", "kind": "ruleref", "status": "satisfied", "details": []},
                            {"step_key": "b0.a1:ruleref", "kind": "ruleref", "status": "satisfied", "details": []},
                        ],
                        "rule_refs": ["q.unweighted_rule", "q.weighted_rule"],
                        "rule_ref_edges": [
                            {
                                "ruleref_atom_key": "b0.a0:ruleref",
                                "rule_ref_id": "q.weighted_rule",
                                "rule_ref_version": "1.0.0",
                                "child_support_digest": child_support_digest_a,
                                "unresolved_reason": None,
                            },
                            {
                                "ruleref_atom_key": "b0.a1:ruleref",
                                "rule_ref_id": "q.unweighted_rule",
                                "rule_ref_version": "1.0.0",
                                "child_support_digest": child_support_digest_b,
                                "unresolved_reason": None,
                            },
                        ],
                    }
                )
                multi_support_digest = _remember_artifact(session_id, multi_artifact, digest="sha256:" + ("33" * 32))
                _require_session(session_id).store._remember_candidate_support(
                    "cand-ineligible",
                    multi_support_digest,
                    "native_binding_v1",
                    confidence_kind="certainty",
                )

                session = _require_session(session_id)
                weighted_tree = _get_candidate_tree(session, "cand-weighted")
                unweighted_tree = _get_candidate_tree(session, "cand-unweighted")
                ineligible_tree = _get_candidate_tree(session, "cand-ineligible")

                self.assertEqual(
                    _lookup_condition_weights_for_candidate(
                        session.store,
                        "cand-weighted",
                        weighted_tree,
                        registry_root=registry_root,
                    ),
                    {"b0.a0": 0.8},
                )
                self.assertEqual(
                    _lookup_condition_weights_for_candidate(
                        session.store,
                        "cand-unweighted",
                        unweighted_tree,
                        registry_root=registry_root,
                    ),
                    {},
                )
                self.assertIsNone(
                    _lookup_condition_weights_for_candidate(
                        session.store,
                        "cand-ineligible",
                        ineligible_tree,
                        registry_root=registry_root,
                    )
                )
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_condition_confidence_fallback_field(self) -> None:
        tree = _base_certainty_tree(_predicate_condition_node(confidence=0.25))
        summary = derive_certainty_summary(tree, {"b0.a0": 0.8}, "certainty")
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.conditions[0].impact, 0.2)
        self.assertEqual(summary.aggregate_certainty, 0.2)

    def test_real_evaluate_output_compatible_with_certainty_chain(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.certainty.e2e",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = eval_resp["evaluation"]["candidates"][0]
                candidate_id = candidate["candidate_id"]

                session = _require_session(session_id)

                self.assertEqual(
                    session.store.get_candidate_confidence_kind(candidate_id),
                    "certainty",
                )

                tree = _get_candidate_tree(session, candidate_id)
                self.assertIsInstance(tree, dict)
                self.assertIn("root", tree)

                condition_weights = _lookup_condition_weights_for_candidate(
                    session.store,
                    candidate_id,
                    tree,
                    registry_root=registry_root,
                )
                self.assertIsNotNone(condition_weights)
                assert condition_weights is not None
                self.assertEqual(condition_weights["b0.a0"], 0.8)

                derived = derive_certainty_summary(tree, condition_weights, "certainty")
                self.assertIsNotNone(derived)
                assert derived is not None
                self.assertGreater(derived.condition_count, 0)
                self.assertGreater(derived.weighted_condition_count, 0)
                self.assertIsNotNone(derived.aggregate_certainty)

                session.store._candidate_confidence_kind_index[candidate_id] = "certainty"

                summary_resp = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(summary_resp["ok"])
                certainty_summary = summary_resp["certainty_summary"]
                self.assertIsNotNone(certainty_summary)
                assert certainty_summary is not None
                self.assertIn("aggregate_certainty", certainty_summary)
                self.assertIn("conditions", certainty_summary)
                self.assertGreater(len(certainty_summary["conditions"]), 0)
                for condition in certainty_summary["conditions"]:
                    self.assertIn("atom_key", condition)
                    self.assertIn("weight", condition)
                    self.assertIn("impact", condition)

                narrative_resp = explain_runtime_narrative(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(narrative_resp["ok"])
                narrative = narrative_resp["narrative"]
                self.assertIn("certainty_lines", narrative)
                self.assertIn("certainty_bottleneck", narrative)
                bottleneck_lines = [
                    line for line in narrative["certainty_lines"] if "[bottleneck]" in line
                ]
                self.assertGreater(len(bottleneck_lines), 0)

                nl_resp = explain_runtime_nl(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(nl_resp["ok"])
                paragraphs = nl_resp["explain_nl"]["paragraphs"]
                self.assertEqual(len(paragraphs), 5)
                self.assertIn("weakest condition", paragraphs[4].lower())
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_audit_round_trip_materializes_certainty_summary_and_narrative(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.certainty.audit",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = dict(eval_resp["evaluation"]["candidates"][0])
                candidate_id = candidate["candidate_id"]
                self.assertEqual(candidate["confidence_kind"], "certainty")

                runtime_summary_resp = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(runtime_summary_resp["ok"])
                runtime_certainty = runtime_summary_resp["certainty_summary"]
                self.assertIsNotNone(runtime_certainty)

                runtime_narrative_resp = explain_runtime_narrative(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(runtime_narrative_resp["ok"])
                runtime_certainty_lines = runtime_narrative_resp["narrative"].get("certainty_lines")
                self.assertIsNotNone(runtime_certainty_lines)

                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": candidate,
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])

                package_dir = str(Path(tmp_dir) / "audit_package")
                export_resp = export_runtime_package(
                    session_id,
                    {"out_dir": package_dir, "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])

                package = load_audit_package(package_dir)
                self.assertIn(candidate_id, package.certainty_summaries)
                audit_certainty = package.certainty_summaries[candidate_id]
                self.assertEqual(audit_certainty, runtime_certainty)

                audit_query = AuditQuery(package)
                audit_cs = audit_query.get_candidate_certainty_summary(candidate_id)
                self.assertEqual(audit_cs, runtime_certainty)

                audit_narrative = audit_query.get_candidate_evidence_tree_narrative(candidate_id)
                self.assertIsNotNone(audit_narrative)
                assert audit_narrative is not None
                self.assertEqual(
                    audit_narrative.get("certainty_lines"),
                    runtime_certainty_lines,
                )
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_audit_round_trip_old_package_without_certainty_file_loads_normally(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as tmp_dir:
            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.tag_copy",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [["pred", "user:tag", ["$u", "$tag"]]],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = dict(eval_resp["evaluation"]["candidates"][0])

                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": candidate,
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])

                package_dir = str(Path(tmp_dir) / "audit_package")
                export_package(
                    _require_session(session_id).store,
                    Path(package_dir),
                    ExportOptions(package_kind="audit"),
                )

                package = load_audit_package(package_dir)
                self.assertEqual(package.certainty_summaries, {})

                audit_query = AuditQuery(package)
                self.assertIsNone(audit_query.get_candidate_certainty_summary(candidate["candidate_id"]))

                narrative = audit_query.get_candidate_evidence_tree_narrative(candidate["candidate_id"])
                self.assertIsNotNone(narrative)
                assert narrative is not None
                self.assertNotIn("certainty_lines", narrative)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_evaluate_without_registry_keeps_confidence_kind_none(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.no_registry",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "native",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["confidence_kind"], "none")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_evaluate_with_rule_without_condition_weights_keeps_none(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights=None,
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.no_weights",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = eval_resp["evaluation"]["candidates"][0]
                self.assertEqual(candidate["confidence_kind"], "none")
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_static_site_renders_certainty_section_in_candidate_evidence_page(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.certainty.static",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = dict(eval_resp["evaluation"]["candidates"][0])
                candidate_id = candidate["candidate_id"]
                self.assertEqual(candidate["confidence_kind"], "certainty")

                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": candidate,
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])

                package_dir = str(Path(tmp_dir) / "audit_package")
                export_resp = export_runtime_package(
                    session_id,
                    {"out_dir": package_dir, "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])

                site_dir = str(Path(tmp_dir) / "site")
                render_audit_static_site(package_dir, site_dir)

                html_path = (
                    Path(site_dir)
                    / "candidate_evidence"
                    / f"{_slug_id(candidate_id)}.html"
                )
                self.assertTrue(html_path.exists(), f"missing: {html_path}")
                html = html_path.read_text(encoding="utf-8")
                self.assertIn("Certainty Assessment", html)
                self.assertIn("certainty-aggregate", html)  # visual aggregate display
                self.assertIn("0.8", html)  # aggregate value present
                self.assertIn("bottleneck", html)  # strategy label present
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_provenance_trees_materialized_in_audit_package(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            provenance_path = Path(package_dir) / "audit" / "provenance_trees.jsonl"
            self.assertTrue(provenance_path.exists(), f"missing: {provenance_path}")

            rows = [
                json.loads(line)
                for line in provenance_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual([row["candidate_id"] for row in rows], [candidate_id])
            tree = rows[0]["provenance_tree"]
            root = tree.get("root")
            self.assertIsInstance(root, dict)
            assert isinstance(root, dict)
            self.assertIsInstance(root.get("relation"), str)
            self.assertIsInstance(root.get("node_type"), str)
            self.assertIsInstance(root.get("args"), list)

    def test_provenance_trees_loaded_by_audit_reader(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            package = load_audit_package(package_dir)
            self.assertIsInstance(package.provenance_trees, dict)
            self.assertIn(candidate_id, package.provenance_trees)

            audit_query = AuditQuery(package)
            tree = audit_query.get_candidate_provenance_tree(candidate_id)
            self.assertIsNotNone(tree)
            assert tree is not None
            self.assertIsInstance(tree.get("query"), str)
            self.assertIsInstance(tree.get("root"), dict)
            self.assertIsInstance(tree.get("rules"), dict)

    def test_provenance_statuses_materialized_in_audit_package(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            status_path = Path(package_dir) / "audit" / "provenance_statuses.jsonl"
            self.assertTrue(status_path.exists(), f"missing: {status_path}")

            rows = [
                json.loads(line)
                for line in status_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual([row["candidate_id"] for row in rows], [candidate_id])
            self.assertEqual(rows[0]["status"], "present")
            self.assertEqual(rows[0]["engine"], "souffle")
            self.assertIn("truncated", rows[0])

    def test_provenance_statuses_loaded_and_summarized_by_audit_query(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            package = load_audit_package(package_dir)
            self.assertIsInstance(package.provenance_statuses, dict)
            self.assertIn(candidate_id, package.provenance_statuses)

            audit_query = AuditQuery(package)
            status = audit_query.get_candidate_provenance_status(candidate_id)
            self.assertIsNotNone(status)
            assert status is not None
            self.assertEqual(status.get("status"), "present")
            self.assertEqual(status.get("engine"), "souffle")

            with_provenance = audit_query.list_candidates_with_provenance()
            without_provenance = audit_query.list_candidates_without_provenance()
            summary = audit_query.summarize_provenance_coverage()

            self.assertEqual(len(with_provenance), 1)
            self.assertEqual(with_provenance[0]["candidate_id"], candidate_id)
            self.assertEqual(without_provenance, [])
            self.assertEqual(summary["total_candidates"], 1)
            self.assertEqual(summary["with_provenance"], 1)
            self.assertEqual(summary["without_provenance"], 0)
            self.assertEqual(summary["coverage_pct"], 100.0)
            self.assertEqual(summary["by_status"].get("present"), 1)

    def test_old_package_without_provenance_returns_empty(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as tmp_dir:
            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.no_provenance",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [["pred", "user:tag", ["$u", "$tag"]]],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = dict(eval_resp["evaluation"]["candidates"][0])

                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": candidate,
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])

                package_dir = str(Path(tmp_dir) / "audit_package")
                export_package(
                    _require_session(session_id).store,
                    Path(package_dir),
                    ExportOptions(package_kind="audit"),
                )

                package = load_audit_package(package_dir)
                self.assertEqual(package.provenance_trees, {})
                self.assertEqual(package.provenance_statuses, {})

                audit_query = AuditQuery(package)
                self.assertIsNone(audit_query.get_candidate_provenance_tree(candidate["candidate_id"]))
                self.assertIsNone(audit_query.get_candidate_provenance_status(candidate["candidate_id"]))
                self.assertEqual(audit_query.list_candidates_with_provenance(), [])
                without_provenance = audit_query.list_candidates_without_provenance()
                self.assertEqual(len(without_provenance), 1)
                self.assertEqual(without_provenance[0]["candidate_id"], candidate["candidate_id"])
                self.assertEqual(without_provenance[0]["provenance_status"], "unknown")
                summary = audit_query.summarize_provenance_coverage()
                self.assertEqual(summary["total_candidates"], 1)
                self.assertEqual(summary["with_provenance"], 0)
                self.assertEqual(summary["without_provenance"], 1)
                self.assertEqual(summary["coverage_pct"], 0.0)
                self.assertEqual(summary["by_status"].get("unknown"), 1)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_static_site_renders_engine_provenance_section_in_candidate_evidence_page(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            site_dir = str(Path(tmp_dir) / "site")
            render_audit_static_site(package_dir, site_dir)

            html_path = Path(site_dir) / "candidate_evidence" / f"{_slug_id(candidate_id)}.html"
            self.assertTrue(html_path.exists(), f"missing: {html_path}")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Engine Provenance", html)
            self.assertIn("Engine Provenance: Available", html)
            self.assertIn("Base Fact", html)

    def test_static_site_index_renders_provenance_coverage_metrics(self) -> None:
        _skip_without_souffle(self)

        with TemporaryDirectory() as registry_root, TemporaryDirectory() as tmp_dir:
            package_dir, _candidate_id = _export_single_candidate_audit_package_with_provenance(
                registry_root=registry_root,
                tmp_dir=tmp_dir,
            )

            site_dir = str(Path(tmp_dir) / "site")
            render_audit_static_site(package_dir, site_dir)

            html_path = Path(site_dir) / "index.html"
            self.assertTrue(html_path.exists(), f"missing: {html_path}")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("Provenance Coverage", html)
            self.assertIn("100.0%", html)
            self.assertIn("1/1 candidates with engine proof", html)

    def test_fact_confidence_carried_to_evidence_tree(self) -> None:
        sdk = SDKStore([User])

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            with sdk.batch() as tx:
                user = tx.entity(User, user_id="u-conf-1", locale="en")
                user.name.set("Alice")
                tx.commit()
            user_ref = sdk.ref(User, user_id="u-conf-1", locale="en")

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": user_ref,
                        "rest_terms": [["string", "vip"]],
                        "meta": {"confidence": 0.7},
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.conf_carrier",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

                tree_resp = explain_runtime_tree(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(tree_resp["ok"])
                tree = tree_resp["tree"]

                root = tree["root"]
                rule_ref_section = [child for child in root["children"] if child["node_kind"] == "rule_ref_section"][0]
                rule_ref = rule_ref_section["children"][0]
                referenced_support = rule_ref["children"][0]
                support_section = [
                    child for child in referenced_support["children"] if child["node_kind"] == "support_section"
                ][0]
                predicate_witness_group = support_section["children"][0]
                self.assertEqual(predicate_witness_group["node_kind"], "predicate_witness_group")

                assertion = predicate_witness_group["children"][0]
                self.assertEqual(assertion["node_kind"], "assertion_fact")
                self.assertIn("confidence", assertion)
                self.assertAlmostEqual(assertion["confidence"], 0.7)

                self.assertIn("condition_confidence", predicate_witness_group)
                self.assertAlmostEqual(predicate_witness_group["condition_confidence"], 0.7)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_fact_confidence_propagates_to_certainty_summary(self) -> None:
        sdk = SDKStore([User])

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            with sdk.batch() as tx:
                user = tx.entity(User, user_id="u-conf-2", locale="en")
                user.name.set("Bob")
                tx.commit()
            user_ref = sdk.ref(User, user_id="u-conf-2", locale="en")

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": user_ref,
                        "rest_terms": [["string", "vip"]],
                        "meta": {"confidence": 0.6},
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.conf_e2e",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

                summary_resp = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(summary_resp["ok"])
                certainty_summary = summary_resp["certainty_summary"]
                self.assertIsNotNone(certainty_summary)
                assert certainty_summary is not None
                self.assertEqual(certainty_summary["condition_count"], 1)
                condition = certainty_summary["conditions"][0]
                self.assertAlmostEqual(condition["weight"], 0.8)
                self.assertAlmostEqual(condition["impact"], 0.48)
                self.assertAlmostEqual(certainty_summary["aggregate_certainty"], 0.48)

                narrative_resp = explain_runtime_narrative(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(narrative_resp["ok"])
                certainty_lines = narrative_resp["narrative"].get("certainty_lines", [])
                self.assertTrue(any("0.48" in line for line in certainty_lines))

                nl_resp = explain_runtime_nl(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(nl_resp["ok"])
                paragraphs = nl_resp["explain_nl"]["paragraphs"]
                self.assertEqual(len(paragraphs), 5)
                self.assertIn("0.48", paragraphs[4])
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_explain_summary_with_additive_aggregation(self) -> None:
        sdk = SDKStore([User])

        with TemporaryDirectory() as registry_root:
            _register_exposed_user_tag_rule(
                sdk,
                registry_root,
                condition_weights={"b0.a0": 0.8},
            )

            with sdk.batch() as tx:
                user = tx.entity(User, user_id="u-additive-1", locale="en")
                user.name.set("Alice")
                tx.commit()
            user_ref = sdk.ref(User, user_id="u-additive-1", locale="en")

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": registry_root})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": user_ref,
                        "rest_terms": [["string", "vip"]],
                        "meta": {"confidence": 0.7},
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.additive.e2e",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

                summary_default = explain_runtime_summary(
                    session_id,
                    {"kind": "candidate", "id": candidate_id},
                )
                self.assertTrue(summary_default["ok"])
                certainty_default = summary_default["certainty_summary"]
                self.assertEqual(certainty_default["aggregation"], "bottleneck")
                self.assertAlmostEqual(certainty_default["aggregate_certainty"], 0.56)

                summary_additive = explain_runtime_summary(
                    session_id,
                    {
                        "kind": "candidate",
                        "id": candidate_id,
                        "certainty_aggregation": "additive",
                    },
                )
                self.assertTrue(summary_additive["ok"])
                certainty_additive = summary_additive["certainty_summary"]
                self.assertEqual(certainty_additive["aggregation"], "additive")
                self.assertAlmostEqual(certainty_additive["aggregate_certainty"], 0.7)
                self.assertAlmostEqual(certainty_additive["conditions"][0]["impact"], 0.7)

                narrative_resp = explain_runtime_narrative(
                    session_id,
                    {
                        "kind": "candidate",
                        "id": candidate_id,
                        "certainty_aggregation": "additive",
                    },
                )
                self.assertTrue(narrative_resp["ok"])
                certainty_lines = narrative_resp["narrative"].get("certainty_lines", [])
                self.assertTrue(any("additive" in line.lower() for line in certainty_lines))
                self.assertNotIn("certainty_bottleneck", narrative_resp["narrative"])
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()


    # ── F-CORE-3: check_certainty_artifact_eligibility child guard ──────

    def _make_minimal_artifact(
        self,
        rule_ref_edges: tuple[RuleRefEdge, ...] = (),
    ) -> SupportArtifact:
        return SupportArtifact(
            kind="native_binding_v1",
            root_result_kind="fact",
            binding_items=normalize_binding_items({"$e": "e:test"}),
            pred_witnesses=(
                PredWitness(pred_atom_key="b0.a0:test:f", asrt_ids=("asrt-1",)),
            ),
            rule_ref_edges=rule_ref_edges,
        )

    def test_certainty_eligibility_missing_child_artifact(self) -> None:
        """child_support_digest present but lookup returns None → ineligible."""
        edge = RuleRefEdge(
            ruleref_atom_key="b0.rr0:q.child",
            rule_ref_id="q.child",
            rule_ref_version="v1",
            child_support_digest="sha256:" + "a" * 64,
        )
        parent = self._make_minimal_artifact(rule_ref_edges=(edge,))
        result = check_certainty_artifact_eligibility(parent, lambda _: None)
        self.assertIsNone(result)

    def test_certainty_eligibility_leaf_child(self) -> None:
        """child exists with no rule_ref_edges → eligible."""
        edge = RuleRefEdge(
            ruleref_atom_key="b0.rr0:q.child",
            rule_ref_id="q.child",
            rule_ref_version="v1",
            child_support_digest="sha256:" + "b" * 64,
        )
        parent = self._make_minimal_artifact(rule_ref_edges=(edge,))
        leaf_child = self._make_minimal_artifact(rule_ref_edges=())
        result = check_certainty_artifact_eligibility(parent, lambda _: leaf_child)
        self.assertIs(result, edge)

    def test_certainty_eligibility_non_leaf_child(self) -> None:
        """child exists with rule_ref_edges → ineligible."""
        grandchild_edge = RuleRefEdge(
            ruleref_atom_key="b0.rr0:q.grandchild",
            rule_ref_id="q.grandchild",
            rule_ref_version="v1",
            child_support_digest="sha256:" + "c" * 64,
        )
        edge = RuleRefEdge(
            ruleref_atom_key="b0.rr0:q.child",
            rule_ref_id="q.child",
            rule_ref_version="v1",
            child_support_digest="sha256:" + "d" * 64,
        )
        parent = self._make_minimal_artifact(rule_ref_edges=(edge,))
        non_leaf_child = self._make_minimal_artifact(rule_ref_edges=(grandchild_edge,))
        result = check_certainty_artifact_eligibility(parent, lambda _: non_leaf_child)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
