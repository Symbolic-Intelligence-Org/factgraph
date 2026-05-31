from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.audit import (
    AuditQuery,
    build_candidate_evidence_tree_narrative_dto,
    build_candidate_evidence_tree_summary_dto,
    build_candidate_evidence_tree_dto,
    build_rule_trace_narrative_dto,
    build_rule_trace_detail_dto,
    build_rule_trace_summary_dto,
    build_rule_trace_summary_list_dto,
    build_compliance_matrix_dto,
    load_audit_package,
)
from domains.ecss.compliance import (
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    extend_schema_ir_with_ecss_vcd_predicates,
)
from service.static_ui import render_audit_static_site
from factgraph.audit.assertions import load_assertion_index
from factgraph.authoring import (
    AuthoringDerivationCompileError,
    build_derivation_preview_dto,
    compile_authoring_schema_v1,
    compile_authoring_derivation_v1,
    parse_authoring_schema_dsl_v1,
    parse_authoring_derivation_dsl_v1,
)
from factgraph.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)
from domains.ecss import (
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_INTERVAL_END_PRED_ID,
    ECSS_INTERVAL_START_PRED_ID,
    ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    ECSS_WINDOW_END_PRED_ID,
    ECSS_WINDOW_START_PRED_ID,
    EcssTemporalError,
    EcssUncertaintyError,
    EcssVcdError,
    extend_schema_ir_with_ecss_uncertainty_predicates,
    extend_schema_ir_with_ecss_temporal_predicates,
)
from factgraph.core.rules.rule_ir import (
    RuleCompileError,
    RuleRegistry,
    RuleSpec,
    run_rule_with_trace,
)
from factgraph.core.rules._trace import (
    RuleTraceArtifact,
    RuleTraceInvocation,
    RuleTraceRuleRefLink,
    rule_trace_artifact_from_dict,
    rule_trace_artifact_to_dict,
    summarize_rule_trace_artifact_dict,
)
from factgraph.core.rules._trace_nl import render_rule_run_nl_explain
from factgraph.core.rules._trace_narrative import render_rule_run_narrative
from factgraph.core.rules.ruleref_types import NativeRuleRefResolution, NativeRuleRefRowSupport
from factgraph.core.rules.where_eval import WhereValidationError, _plan_body_atoms
from factgraph.core.store import Store, register_engine_evaluator
import factgraph.core.store._builders as store_builders
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar, GCResult
from factgraph.core.store._candidate_evidence_tree_narrative import render_candidate_evidence_tree_narrative
from factgraph.core.store._candidate_evidence_tree_nl import render_candidate_evidence_tree_nl_explain
from factgraph.core.store._candidate_evidence_tree_summary import summarize_candidate_evidence_tree_dict
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_branch_index,
)
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    ProjectedFact,
    compute_support_digest,
    support_artifact_from_dict,
    support_artifact_to_dict,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.view.projector import project_view_facts
from factgraph.sdk import (
    Case,
    Derivation,
    Entity,
    Field,
    Identity,
    Not,
    Pred,
    Query,
    Rule,
    RuleRef,
    SDKDSLError,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from domains.ecss.sdk_helpers import (
    apply_ecss_vcd_schema,
    make_ecss_requirement_ref,
    write_ecss_requirement_bundle,
)
from factgraph.sdk.ingest import CONVENTION_META_KEYS, SENSITIVE_SEMANTIC_META_KEYS
from service.app_v1 import app
from service.runtime_v1 import (
    _require_session,
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_nl,
    explain_runtime_narrative,
    explain_runtime_ref,
    explain_runtime_rule_trace,
    explain_runtime_summary,
    explain_runtime_support,
    explain_runtime_tree,
    export_runtime_package,
    open_runtime_session,
    project_runtime_view_facts,
    retract_runtime_fact,
    reset_runtime_sessions_for_tests,
    run_runtime_rule,
    write_runtime_fact,
)
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix


class WinningBranchRuleTraceContractsTests(unittest.TestCase):
    def test_support_artifact_from_dict_round_trip_ignores_envelope_and_restores_bytes(self) -> None:
        row = {
            "support_digest": "sha256:" + ("ab" * 32),
            "kind": "native_binding_v1",
            "root_result_kind": "fact",
            "binding": [
                ["$blob", {"__bytes_hex__": "00ff"}],
                ["$pair", [1, 2]],
            ],
            "pred_witnesses": [
                {
                    "pred_atom_key": "b0.a0:user:tag",
                    "asrt_ids": ["A1"],
                }
            ],
            "non_fact_steps": [
                {
                    "step_key": "b0.a1:eq",
                    "kind": "eq",
                    "status": "ok",
                    "details": [["payload", {"__bytes_hex__": "6162"}]],
                }
            ],
            "rule_refs": ["r.1"],
            "unexpected": "ignored",
        }

        artifact = support_artifact_from_dict(row)

        self.assertEqual(artifact.kind, "native_binding_v1")
        self.assertEqual(artifact.root_result_kind, "fact")
        self.assertEqual(artifact.binding_items, (("$blob", b"\x00\xff"), ("$pair", [1, 2])))
        self.assertEqual(artifact.pred_witnesses[0].pred_atom_key, "b0.a0:user:tag")
        self.assertEqual(artifact.non_fact_steps[0].details, (("payload", b"ab"),))
        self.assertEqual(
            support_artifact_to_dict(artifact),
            {
                "kind": "native_binding_v1",
                "root_result_kind": "fact",
                "binding": [
                    ["$blob", {"__bytes_hex__": "00ff"}],
                    ["$pair", [1, 2]],
                ],
                "pred_witnesses": [
                    {
                        "pred_atom_key": "b0.a0:user:tag",
                        "asrt_ids": ["A1"],
                    }
                ],
                "non_fact_steps": [
                    {
                        "step_key": "b0.a1:eq",
                        "kind": "eq",
                        "status": "ok",
                        "details": [["payload", {"__bytes_hex__": "6162"}]],
                    }
                ],
                "rule_refs": ["r.1"],
                "rule_ref_edges": [],
            },
        )

    def test_runtime_tree_renders_unresolved_rule_ref_edge_terminal_node(self) -> None:
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

            session = _require_session(session_id)
            support_digest = "sha256:" + ("cd" * 32)
            artifact = support_artifact_from_dict(
                {
                    "support_digest": support_digest,
                    "kind": "native_binding_v1",
                    "root_result_kind": "fact",
                    "binding": [["$tag", "vip"], ["$u", refs["u1"]]],
                    "pred_witnesses": [
                        {
                            "pred_atom_key": "b0.a0:user:tag",
                            "asrt_ids": [asrt_id],
                        }
                    ],
                    "non_fact_steps": [
                        {
                            "step_key": "b0.a1:ruleref",
                            "kind": "ruleref",
                            "status": "satisfied",
                            "details": [],
                        }
                    ],
                    "rule_refs": ["q.child_rule"],
                    "rule_ref_edges": [
                        {
                            "ruleref_atom_key": "b0.a1:ruleref",
                            "rule_ref_id": "q.child_rule",
                            "rule_ref_version": "1.0.0",
                            "child_support_digest": None,
                            "unresolved_reason": "child_support_unavailable",
                        }
                    ],
                }
            )
            session.store._remember_support_artifact(support_digest, artifact)
            session.store._remember_candidate_support("cand-unresolved-rule-ref", support_digest, "native_binding_v1")

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": "cand-unresolved-rule-ref"})
            self.assertTrue(tree_resp["ok"])
            rule_ref_section = tree_resp["tree"]["root"]["children"][1]
            self.assertEqual(rule_ref_section["node_kind"], "rule_ref_section")
            rule_ref_node = rule_ref_section["children"][0]
            self.assertEqual(rule_ref_node["ruleref_atom_key"], "b0.a1:ruleref")
            self.assertIsNone(rule_ref_node["child_support_digest"])
            self.assertEqual(rule_ref_node["unresolved_reason"], "child_support_unavailable")
            unresolved = rule_ref_node["children"][0]
            self.assertEqual(unresolved["node_kind"], "unresolved_support")
            self.assertEqual(unresolved["reason"], "child_support_unavailable")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_winning_branch_single_branch_rule_is_no_op(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [("pred", "user:tag", ["$u", "vip"])]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 0)

        artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=selected_branch_index,
            rule_ref_edges=(),
        )
        self.assertEqual(
            [row.pred_atom_key for row in artifact.pred_witnesses],
            ["b0.a0:user:tag"],
        )

    def test_winning_branch_prefers_lowest_index_when_multiple_branches_satisfy(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 0)

        artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=selected_branch_index,
            rule_ref_edges=(),
        )
        self.assertEqual(
            [row.pred_atom_key for row in artifact.pred_witnesses],
            ["b0.a0:user:tag"],
        )

    def test_winning_branch_excludes_non_satisfying_pred_branch(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "blocked"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_not_atom_recheck_excludes_branch_with_negated_match(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
                ProjectedFact(asrt_id="A2", fact_tuple=("user-1", "blocked")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("not", [("pred", "user:tag", ["$u", "blocked"])]), ("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_ruleref_that_cannot_ground_does_not_satisfy(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(
                NativeRuleRefResolution(
                    ruleref_atom_key="b0.a0:ruleref",
                    rule_ref_id="q.child_rule",
                    rule_ref_version="1.0.0",
                    row_supports=(
                        NativeRuleRefRowSupport(
                            row_terms=("user-1", "vip"),
                            child_support_digest="sha256:" + ("12" * 32),
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_arith_mismatch_excludes_branch(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1", "$x": 3, "$sum": 99}
        where = [
            [("addc", "$sum", "$x", 2)],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_digest_is_stable_for_same_input(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        first_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        first_artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=first_branch_index,
            rule_ref_edges=(),
        )
        second_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        second_artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=second_branch_index,
            rule_ref_edges=(),
        )

        self.assertEqual(first_branch_index, 0)
        self.assertEqual(second_branch_index, 0)
        self.assertEqual(compute_support_digest(first_artifact), compute_support_digest(second_artifact))

    def test_winning_branch_fails_fast_when_no_branch_satisfies_final_binding(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }

        with self.assertRaises(WhereValidationError) as ctx:
            find_winning_branch_index(
                where=[("pred", "user:tag", ["$u", "blocked"])],
                binding={"$u": "user-1"},
                witness_facts=witness_facts,
                rule_ref_resolutions=(),
            )
        self.assertIn("no satisfying branch", str(ctx.exception))

    def test_rule_ref_edge_derivation_fails_fast_on_duplicate_row_support_match(self) -> None:
        with self.assertRaises(WhereValidationError) as ctx:
            derive_rule_ref_edges_for_binding(
                where=[("ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"])],
                binding={"$u": "user-1", "$tag": "vip"},
                rule_ref_resolutions=(
                    NativeRuleRefResolution(
                        ruleref_atom_key="b0.a0:ruleref",
                        rule_ref_id="q.child_rule",
                        rule_ref_version="1.0.0",
                        row_supports=(
                            NativeRuleRefRowSupport(
                                row_terms=("user-1", "vip"),
                                child_support_digest="sha256:" + ("12" * 32),
                            ),
                            NativeRuleRefRowSupport(
                                row_terms=("user-1", "vip"),
                                child_support_digest="sha256:" + ("34" * 32),
                            ),
                        ),
                    ),
                ),
                selected_branch_index=0,
            )

        self.assertIn("multiple row_support matches", str(ctx.exception))

    def test_rule_trace_rule_ref_link_and_invocation_sorting_validation(self) -> None:
        with self.assertRaises(ValueError) as ctx_empty_key:
            RuleTraceRuleRefLink(ruleref_atom_key="", child_invocation_id="rr_1:i1")
        self.assertEqual(str(ctx_empty_key.exception), "ruleref_atom_key must be non-empty string")

        with self.assertRaises(ValueError) as ctx_empty_invocation:
            RuleTraceRuleRefLink(ruleref_atom_key="b0.a0:ruleref", child_invocation_id="")
        self.assertEqual(str(ctx_empty_invocation.exception), "child_invocation_id must be non-empty string")

        link_a = RuleTraceRuleRefLink(ruleref_atom_key="b0.a0:ruleref", child_invocation_id="rr_1:i1")
        link_b = RuleTraceRuleRefLink(ruleref_atom_key="b0.a1:ruleref", child_invocation_id="rr_1:i2")
        with self.assertRaises(ValueError) as ctx_unsorted:
            RuleTraceInvocation(
                invocation_id="rr_1:i0",
                parent_invocation_id=None,
                rule_id="q.user",
                version="1.0.0",
                memo_hit=False,
                memo_source_invocation_id=None,
                original_where=[],
                rewritten_where=[],
                bindings=(),
                output_rows=(),
                ruleref_links=(link_b, link_a),
            )
        self.assertEqual(str(ctx_unsorted.exception), "ruleref_links must be sorted by ruleref_atom_key")

    def test_rule_trace_artifact_from_dict_round_trip_keeps_where_payload_opaque(self) -> None:
        row = {
            "rule_run_id": "rr_1",
            "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
            "select_vars": ["$u"],
            "invocations": [
                {
                    "invocation_id": "rr_1:i1",
                    "parent_invocation_id": None,
                    "rule": {"rule_id": "q.user", "version": "1.0.0"},
                    "memo_hit": False,
                    "memo_source_invocation_id": None,
                    "original_where": [["pred", "user:tag", [{"__bytes_hex__": "00ff"}]]],
                    "rewritten_where": {"opaque": {"__bytes_hex__": "0a0b"}},
                    "bindings": [
                        [
                            ["$blob", {"__bytes_hex__": "6162"}],
                            ["$pair", [1, 2]],
                        ]
                    ],
                    "output_rows": [[{"__bytes_hex__": "0102"}, [3, 4]]],
                    "pred_witnesses": [
                        {
                            "binding_index": 0,
                            "pred_atom_key": "b0.a0:user:tag",
                            "asrt_ids": ["A1"],
                        }
                    ],
                    "non_fact_steps": [
                        {
                            "binding_index": 0,
                            "step_key": "b0.a1:eq",
                            "kind": "eq",
                            "status": "satisfied",
                            "details": [["payload", {"__bytes_hex__": "ff"}]],
                        },
                        {
                            "binding_index": 0,
                            "step_key": "b0.a2:not",
                            "kind": "not",
                            "status": "no_match",
                            "details": [["payload", {"__bytes_hex__": "0f"}]],
                        }
                    ],
                }
            ],
            "root_rows": [[{"__bytes_hex__": "c0ff"}]],
            "extra": "ignored",
        }

        artifact = rule_trace_artifact_from_dict(row)
        invocation = artifact.invocations[0]

        self.assertEqual(artifact.root_rule_id, "q.user")
        self.assertEqual(artifact.root_version, "1.0.0")
        self.assertEqual(invocation.original_where, [["pred", "user:tag", [{"__bytes_hex__": "00ff"}]]])
        self.assertEqual(invocation.rewritten_where, {"opaque": {"__bytes_hex__": "0a0b"}})
        self.assertEqual(invocation.bindings, ((("$blob", b"ab"), ("$pair", [1, 2])),))
        self.assertEqual(invocation.output_rows, ((b"\x01\x02", [3, 4]),))
        self.assertEqual(invocation.ruleref_links, ())
        self.assertEqual(invocation.non_fact_steps[0].status, "evaluated")
        self.assertEqual(invocation.non_fact_steps[1].status, "negated")
        self.assertEqual(invocation.non_fact_steps[0].details, (("payload", b"\xff"),))
        self.assertEqual(artifact.root_rows, ((b"\xc0\xff",),))
        self.assertEqual(
            rule_trace_artifact_to_dict(artifact),
            {
                "rule_run_id": "rr_1",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [
                    {
                        "invocation_id": "rr_1:i1",
                        "parent_invocation_id": None,
                        "rule": {"rule_id": "q.user", "version": "1.0.0"},
                        "memo_hit": False,
                        "memo_source_invocation_id": None,
                        "original_where": [["pred", "user:tag", [{"__bytes_hex__": "00ff"}]]],
                        "rewritten_where": {"opaque": {"__bytes_hex__": "0a0b"}},
                        "bindings": [
                            [
                                ["$blob", {"__bytes_hex__": "6162"}],
                                ["$pair", [1, 2]],
                            ]
                        ],
                        "output_rows": [[{"__bytes_hex__": "0102"}, [3, 4]]],
                        "pred_witnesses": [
                            {
                                "binding_index": 0,
                                "pred_atom_key": "b0.a0:user:tag",
                                "asrt_ids": ["A1"],
                            }
                        ],
                        "non_fact_steps": [
                            {
                                "binding_index": 0,
                                "step_key": "b0.a1:eq",
                                "kind": "eq",
                                "status": "evaluated",
                                "details": [["payload", {"__bytes_hex__": "ff"}]],
                            },
                            {
                                "binding_index": 0,
                                "step_key": "b0.a2:not",
                                "kind": "not",
                                "status": "negated",
                                "details": [["payload", {"__bytes_hex__": "0f"}]],
                            }
                        ],
                        "ruleref_links": [],
                    }
                ],
                "root_rows": [[{"__bytes_hex__": "c0ff"}]],
            },
        )

    def test_rule_trace_artifact_round_trip_preserves_ruleref_links(self) -> None:
        artifact = RuleTraceArtifact(
            rule_run_id="rr_linked",
            root_rule_id="q.user",
            root_version="1.0.0",
            select_vars=("$u",),
            invocations=(
                RuleTraceInvocation(
                    invocation_id="rr_linked:i1",
                    parent_invocation_id=None,
                    rule_id="q.user",
                    version="1.0.0",
                    memo_hit=False,
                    memo_source_invocation_id=None,
                    original_where=[["ruleref", "q.dep", "1.0.0", ["$u"]]],
                    rewritten_where=[["pred", "__rule_ref__q_dep__1_0_0", ["$u"]]],
                    bindings=((("$u", "idref_v1:User:user_id=u1"),),),
                    output_rows=(("idref_v1:User:user_id=u1",),),
                    ruleref_links=(
                        RuleTraceRuleRefLink(
                            ruleref_atom_key="b0.a0:ruleref",
                            child_invocation_id="rr_linked:i2",
                        ),
                    ),
                ),
                RuleTraceInvocation(
                    invocation_id="rr_linked:i2",
                    parent_invocation_id="rr_linked:i1",
                    rule_id="q.dep",
                    version="1.0.0",
                    memo_hit=False,
                    memo_source_invocation_id=None,
                    original_where=[["pred", "user:tag", ["$u", "vip"]]],
                    rewritten_where=[["pred", "user:tag", ["$u", "vip"]]],
                    bindings=((("$u", "idref_v1:User:user_id=u1"),),),
                    output_rows=(("idref_v1:User:user_id=u1",),),
                ),
            ),
            root_rows=(("idref_v1:User:user_id=u1",),),
        )

        round_tripped = rule_trace_artifact_from_dict(rule_trace_artifact_to_dict(artifact))
        self.assertEqual(round_tripped, artifact)
