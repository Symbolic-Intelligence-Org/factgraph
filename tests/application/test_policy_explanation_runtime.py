from __future__ import annotations

import unittest
from dataclasses import replace

from factgraph.application.explain.evidence_tree import (
    Builtin,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fails,
    Holds,
    NotReached,
    PortRef,
    Source,
)
from factgraph.application import project_policy_explanation_v0
from factgraph.application.policy_runtime import compile_policy
from factgraph.application.protocol.evaluation_run import (
    EvaluationRunAnchorV0,
    EvaluationRunExecutionProfileV0,
    EvaluationRunRowAnchorV0,
    EvaluationRunRulePinV0,
    EvaluationRunSelectionV0,
    EvaluationRunSummaryAnchorV0,
    EvaluationRunTargetV0,
    _plain,
    _token,
)
from factgraph.application.protocol.policy import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyOccurrence,
    PolicyUnify,
)
from factgraph.application.protocol import (
    PolicyExplanationProjectionError,
    PolicyNodeBranchStateV0,
)
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import SemanticRulePort, entity_identity
from factgraph.application.semantic_port_runtime import (
    build_resolved_rule,
)
from factgraph.application.semantic_address_runtime import (
    SemanticAddressSpace,
    manage_rule_occurrence,
)
from factgraph.application.schema_runtime import build_schema_index
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()


def _bundle():
    person = Var("$person")
    index = build_schema_index(
        compile_schema_from_classes([Person], generated_at="2026-08-12T00:00:00Z")
    )
    return build_resolved_rule(
        id="person_exists",
        version="1",
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": SemanticRulePort(person, entity_identity("Person"))},
        schema_index=index,
    )


def _occ(alias: str) -> PolicyOccurrence:
    return PolicyOccurrence(alias)


def _unify(left: str, right: str) -> PolicyUnify:
    return PolicyUnify(
        SemanticPortAddress(left, "person"),
        SemanticPortAddress(right, "person"),
    )


def _compiled(root, aliases: tuple[str, ...]):
    bundle = _bundle()
    space = SemanticAddressSpace(
        tuple(manage_rule_occurrence(bundle, alias) for alias in aliases)
    )
    return compile_policy(Policy("policy", root, version="1"), address_space=space)


def _anchor(compiled, *, with_row: bool = True) -> EvaluationRunAnchorV0:
    rule_pins = tuple(
        EvaluationRunRulePinV0(
            pin.occurrence_alias,
            pin.rule_id,
            pin.rule_version,
            pin.rule_content_digest,
            pin.semantic_contract_digest,
        )
        for pin in compiled.rule_pins
    )
    target_values = (
        "policy",
        "policy_direct_v0",
        compiled.policy_id,
        compiled.policy_version,
        compiled.policy_id,
        compiled.policy_version,
        compiled.policy_digest,
        compiled.address_space_digest,
        "sha256:" + "1" * 64,
        compiled.policy_structure,
        compiled.lineage,
        rule_pins,
    )
    target = EvaluationRunTargetV0(
        original_target_kind="policy",
        normalization_kind="policy_direct_v0",
        target_id=compiled.policy_id,
        target_version=compiled.policy_version,
        normalized_policy_id=compiled.policy_id,
        normalized_policy_version=compiled.policy_version,
        policy_digest=compiled.policy_digest,
        address_space_digest=compiled.address_space_digest,
        schema_digest="sha256:" + "1" * 64,
        policy_structure=compiled.policy_structure,
        policy_lineage=compiled.lineage,
        rule_pins=rule_pins,
        target_digest=_token("evaluation_run_target_v0", _plain(target_values)),
    )
    query_digest = "2" * 64
    row_values = (
        0,
        "row-0",
        query_digest,
        "projection",
        "sha256:" + "3" * 64,
        "sha256:" + "4" * 64,
        "sha256:" + "5" * 64,
        "sha256:" + "6" * 64,
    )
    rows = (
        EvaluationRunRowAnchorV0(
            ordinal=0,
            row_id="row-0",
            query_digest=query_digest,
            claim_kind="projection",
            claim_digest=row_values[4],
            bindings_digest=row_values[5],
            head_scope_digest=row_values[6],
            certainty_digest=row_values[7],
            semantic_anchor_digest=_token("evaluation_run_row_anchor_v0", row_values[2:]),
        ),
    ) if with_row else ()
    summary_values = (
        query_digest,
        len(rows),
        tuple(item.semantic_anchor_digest for item in rows),
        "not_asserted",
        "unknown",
        "unspecified",
    )
    summary = EvaluationRunSummaryAnchorV0(
        query_digest=query_digest,
        row_count=len(rows),
        row_anchor_digests=summary_values[2],
        truth_interpretation="not_asserted",
        completeness="unknown",
        ordering="unspecified",
        summary_anchor_digest=_token("evaluation_run_summary_anchor_v0", summary_values),
    )
    profile = EvaluationRunExecutionProfileV0("native", "native_where_v1", "adapter-v0", None, "complete")
    first_alias = compiled.rule_pins[0].occurrence_alias
    selections = (
        EvaluationRunSelectionV0(
            "value", SemanticPortAddress(first_alias, "person"), "entity_ref"
        ),
    )
    values = (
        target,
        query_digest,
        (),
        selections,
        profile,
        "projection-head",
        "7" * 64,
        "sha256:" + "8" * 64,
        "evalr_v1:" + "9" * 64,
        "sha256:" + "a" * 64,
        "run_v1:" + "b" * 64,
        "2026-08-12T00:00:00Z",
        rows,
        summary,
        "identity_only",
        "digest_only_live_guard",
        "not_available",
        "live_recomputable_while_current",
    )
    return EvaluationRunAnchorV0(
        target=target,
        query_digest=query_digest,
        bindings=(),
        selections=selections,
        execution_profile=profile,
        projection_head_id="projection-head",
        projection_head_content_digest="7" * 64,
        view_snapshot_digest="sha256:" + "8" * 64,
        result_id="evalr_v1:" + "9" * 64,
        result_digest="sha256:" + "a" * 64,
        run_id="run_v1:" + "b" * 64,
        evaluated_at="2026-08-12T00:00:00Z",
        row_anchors=rows,
        summary=summary,
        capture_level="identity_only",
        view_capture="digest_only_live_guard",
        replay_availability="not_available",
        explain_availability="live_recomputable_while_current",
        anchor_digest=_token("evaluation_run_anchor_v0", _plain(values)),
    )


def _lineage_by_id(anchor: EvaluationRunAnchorV0):
    return {node.node_id: node for node in anchor.target.policy_lineage.authored_nodes}


def _structure_by_id(anchor: EvaluationRunAnchorV0):
    return {node.node_id: node for node in anchor.target.policy_structure.nodes}


def _branches(anchor: EvaluationRunAnchorV0) -> tuple[str, ...]:
    return tuple(sorted({
        ref.branch_id
        for node in anchor.target.policy_lineage.authored_nodes
        for ref in node.lowered_refs
    }))


def _applicable(anchor: EvaluationRunAnchorV0, node_id: str, branch_id: str) -> bool:
    node = _structure_by_id(anchor)[node_id]
    lineage = _lineage_by_id(anchor)[node_id]
    kind = "unify" if node.kind == "unify" else "branch"
    return any(ref.kind == kind and ref.branch_id == branch_id for ref in lineage.lowered_refs)


def _branch_state(
    anchor: EvaluationRunAnchorV0,
    node_id: str,
    branch_id: str,
    leaf_states: dict[tuple[str, str], str],
) -> str:
    node = _structure_by_id(anchor)[node_id]
    if not _applicable(anchor, node_id, branch_id):
        return "not_applicable"
    if node.kind in {"occurrence", "unify"}:
        return leaf_states.get((node_id, branch_id), "holds")
    children = tuple(
        _branch_state(anchor, child, branch_id, leaf_states)
        for child in node.child_node_ids
    )
    applicable = tuple(item for item in children if item != "not_applicable")
    if node.kind == "any":
        return applicable[0]
    if "fails" in applicable:
        return "fails"
    if "not_reached" in applicable:
        return "not_reached"
    return "holds"


def _verdict(state: str, ref: str):
    if state == "holds":
        return Holds(support=(Source(ref),))
    if state == "fails":
        return Fails(support=(Source(ref),))
    return NotReached(blocked_by="fixture")


def _evidence(
    anchor: EvaluationRunAnchorV0,
    *,
    leaf_states: dict[tuple[str, str], str] | None = None,
    path_states: dict[str, str] | None = None,
    represented_branches: tuple[str, ...] | None = None,
    extras: bool = False,
) -> EvidenceGraph:
    leaf_states = dict(leaf_states or {})
    path_states = dict(path_states or {})
    lineage = _lineage_by_id(anchor)
    pins = {pin.occurrence_alias: pin for pin in anchor.target.rule_pins}
    paths = []
    for branch_id in represented_branches or _branches(anchor):
        rules = []
        for node in anchor.target.policy_structure.nodes:
            if node.kind != "occurrence" or not _applicable(anchor, node.node_id, branch_id):
                continue
            refs = tuple(ref for ref in lineage[node.node_id].lowered_refs if ref.branch_id == branch_id)
            occurrence_ref = next(ref for ref in refs if ref.kind == "occurrence")
            body_refs = tuple(ref for ref in refs if ref.kind == "body_atom")
            state = leaf_states.get((node.node_id, branch_id), "holds")
            atoms = []
            for index, ref in enumerate(body_refs):
                atom_state = state if index == 0 else ("not_reached" if state == "not_reached" else "holds")
                atom_id = f"{branch_id}:atom:{ref.lowered_index}"
                atoms.append(
                    EvidenceAtom(
                        Builtin("fixture", ()),
                        _verdict(atom_state, f"asrt:{atom_id}"),
                        atom_id,
                    )
                )
            if extras and not rules:
                atoms.append(
                    EvidenceAtom(
                        Builtin("query_binding", ()),
                        Holds(support=(Source(f"query:{branch_id}"),)),
                        f"{branch_id}:atom:999",
                    )
                )
            assert node.occurrence_alias is not None and occurrence_ref.occurrence_alias is not None
            rules.append(
                EvidenceRule(
                    occurrence_alias=occurrence_ref.occurrence_alias,
                    rule_id=pins[node.occurrence_alias].rule_id,
                    role="body",
                    status=state,
                    atoms=tuple(atoms),
                )
            )
        if extras:
            rules.append(
                EvidenceRule(
                    occurrence_alias="projection-head",
                    rule_id="projection-head",
                    role="head",
                    status="holds",
                    atoms=(
                        EvidenceAtom(
                            Builtin("head_link", ()),
                            Holds(),
                            f"{branch_id}:materialized:999",
                        ),
                    ),
                )
            )
        joins = []
        for node in anchor.target.policy_structure.nodes:
            if node.kind != "unify" or not _applicable(anchor, node.node_id, branch_id):
                continue
            ref = next(
                ref
                for ref in lineage[node.node_id].lowered_refs
                if ref.branch_id == branch_id and ref.kind == "unify"
            )
            state = leaf_states.get((node.node_id, branch_id), "holds")
            assert all((ref.occurrence_alias, ref.port_name, ref.peer_occurrence_alias, ref.peer_port_name))
            join_id = (
                f"{branch_id}:{ref.occurrence_alias}.{ref.port_name}="
                f"{ref.peer_occurrence_alias}.{ref.peer_port_name}"
            )
            joins.append(
                EvidenceJoin(
                    PortRef(ref.occurrence_alias, ref.port_name),
                    PortRef(ref.peer_occurrence_alias, ref.peer_port_name),
                    state,
                    join_id,
                )
            )
        root_state = _branch_state(
            anchor, anchor.target.policy_structure.root_node_id, branch_id, leaf_states
        )
        paths.append(
            EvidenceTree(
                tree_id=branch_id,
                status=path_states.get(branch_id, root_state),
                rules=tuple(rules),
                joins=tuple(joins),
            )
        )
    row = anchor.row_anchors[0]
    return EvidenceGraph(
        "graph-1",
        "native",
        "tree",
        {},
        tuple(paths),
        metadata={
            "result_id": anchor.result_id,
            "row_id": row.row_id,
            "claim_digest": row.claim_digest,
            "semantic_row_anchor_digest": row.semantic_anchor_digest,
        },
    )


def _view(anchor: EvaluationRunAnchorV0, graph: EvidenceGraph):
    return project_policy_explanation_v0(
        anchor,
        graph,
        semantic_row_anchor_digest=anchor.row_anchors[0].semantic_anchor_digest,
    )


def _duplicate_semantic_row(anchor: EvaluationRunAnchorV0) -> EvaluationRunAnchorV0:
    first = anchor.row_anchors[0]
    second = replace(first, ordinal=1, row_id="row-1")
    rows = (first, second)
    summary_values = (
        anchor.query_digest,
        2,
        tuple(sorted(item.semantic_anchor_digest for item in rows)),
        "not_asserted",
        "unknown",
        "unspecified",
    )
    summary = replace(
        anchor.summary,
        row_count=2,
        row_anchor_digests=summary_values[2],
        summary_anchor_digest=_token("evaluation_run_summary_anchor_v0", summary_values),
    )
    values = tuple(
        rows if name == "row_anchors" else summary if name == "summary" else getattr(anchor, name)
        for name in anchor.__dataclass_fields__
        if name != "anchor_digest"
    )
    return replace(
        anchor,
        row_anchors=rows,
        summary=summary,
        anchor_digest=_token("evaluation_run_anchor_v0", _plain(values)),
    )


class PolicyExplanationProjectionTests(unittest.TestCase):
    def test_single_occurrence_maps_exact_atoms_and_sources(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        view = _view(anchor, _evidence(anchor))

        self.assertEqual(view.evaluation.root_state, "holds")
        self.assertEqual(view.evaluation.branches[0].participation, "contributes")
        entry = next(
            item
            for item in view.provenance.node_evidence
            if item.node_id == view.structure.root_node_id
        )
        self.assertEqual(len(entry.locators), 1)
        self.assertEqual(entry.locators[0].evidence_id, "c0:atom:0")
        self.assertEqual(entry.locators[0].source_refs, ("asrt:c0:atom:0",))
        self.assertEqual(view.interpretation, "logical_policy_evidence_not_authorization")
        self.assertNotIn("approved", repr(view))

    def test_query_and_head_extras_are_recorded_but_never_folded(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        view = _view(anchor, _evidence(anchor, extras=True))

        outside = {item.evidence_id for item in view.provenance.outside_policy_lineage}
        self.assertEqual(outside, {"c0:atom:999", "c0:materialized:999"})
        self.assertEqual(view.evaluation.root_state, "holds")

    def test_any_preserves_holding_and_failed_branches(self) -> None:
        root = PolicyAny((_occ("left"), _occ("right")))
        anchor = _anchor(_compiled(root, ("left", "right")))
        structure = _structure_by_id(anchor)
        right_id = next(
            node.node_id for node in structure.values() if node.occurrence_alias == "right"
        )
        right_branch = next(
            branch
            for branch in _branches(anchor)
            if _applicable(anchor, right_id, branch)
        )
        view = _view(anchor, _evidence(anchor, leaf_states={(right_id, right_branch): "fails"}))

        self.assertEqual(view.evaluation.root_state, "holds")
        branch_states = {item.branch_id: item.participation for item in view.evaluation.branches}
        self.assertEqual(branch_states[right_branch], "policy_failed")
        self.assertIn("contributes", set(branch_states.values()))
        right = next(item for item in view.evaluation.nodes if item.node_id == right_id)
        self.assertEqual(right.state, "fails")
        self.assertIn("not_applicable", {item.state for item in right.branch_states})

    def test_nested_all_any_uses_lineage_not_generated_alias_parsing(self) -> None:
        root = PolicyAll((_occ("common"), PolicyAny((_occ("left"), _occ("right")))))
        anchor = _anchor(_compiled(root, ("common", "left", "right")))
        view = _view(anchor, _evidence(anchor))
        common_id = next(
            node.node_id
            for node in anchor.target.policy_structure.nodes
            if node.occurrence_alias == "common"
        )
        entry = next(item for item in view.provenance.node_evidence if item.node_id == common_id)

        self.assertEqual(view.evaluation.root_state, "holds")
        self.assertEqual(len(entry.locators), 2)
        self.assertEqual(
            {item.occurrence_alias for item in entry.locators},
            {"common__c0", "common__c1"},
        )

    def test_unify_failure_and_not_reached_remain_direct_states(self) -> None:
        local = PolicyAll((_occ("left"), _occ("right"), _unify("left", "right")))
        root = PolicyAny((local, _occ("fallback")))
        anchor = _anchor(_compiled(root, ("left", "right", "fallback")))
        unify = next(node for node in anchor.target.policy_structure.nodes if node.kind == "unify")
        unify_branch = next(
            branch for branch in _branches(anchor) if _applicable(anchor, unify.node_id, branch)
        )
        for state in ("fails", "not_reached"):
            with self.subTest(state=state):
                view = _view(
                    anchor,
                    _evidence(anchor, leaf_states={(unify.node_id, unify_branch): state}),
                )
                projected = next(
                    item for item in view.evaluation.nodes if item.node_id == unify.node_id
                )
                self.assertEqual(projected.state, state)
                locator = next(
                    item
                    for item in view.provenance.node_evidence
                    if item.node_id == unify.node_id
                ).locators[0]
                self.assertEqual(locator.evidence_kind, "join")
                self.assertEqual(locator.status, state)

    def test_detached_selected_branch_can_leave_other_any_arm_not_applicable(self) -> None:
        anchor = _anchor(_compiled(PolicyAny((_occ("left"), _occ("right"))), ("left", "right")))
        selected = (_branches(anchor)[0],)
        view = _view(anchor, _evidence(anchor, represented_branches=selected))

        self.assertEqual(len(view.evaluation.branches), 1)
        self.assertTrue(any(node.state == "not_applicable" for node in view.evaluation.nodes))
        self.assertEqual(view.evaluation.root_state, "holds")

    def test_missing_or_duplicate_authored_atom_fails_total_projection(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor)
        tree = graph.paths[0]
        assert isinstance(tree, EvidenceTree)
        rule = tree.rules[0]
        missing = replace(graph, paths=(replace(tree, rules=(replace(rule, atoms=()),)),))
        duplicate = replace(
            graph,
            paths=(replace(tree, rules=(replace(rule, atoms=(*rule.atoms, rule.atoms[0])),)),),
        )

        for value, code in (
            (missing, "POLICY_LINEAGE_MAPPING_INCOMPLETE"),
            (duplicate, "DUPLICATE_EVIDENCE_COORDINATE"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(PolicyExplanationProjectionError) as ctx:
                    _view(anchor, value)
                self.assertEqual(ctx.exception.code, code)

    def test_wrong_rule_identity_fails_closed(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor)
        tree = graph.paths[0]
        assert isinstance(tree, EvidenceTree)
        bad_rule = replace(tree.rules[0], rule_id="other")
        graph = replace(graph, paths=(replace(tree, rules=(bad_rule,)),))

        with self.assertRaises(PolicyExplanationProjectionError) as ctx:
            _view(anchor, graph)
        self.assertEqual(ctx.exception.code, "POLICY_RULE_IDENTITY_MISMATCH")

    def test_body_rule_status_must_match_its_authored_atom_fold(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor)
        tree = graph.paths[0]
        assert isinstance(tree, EvidenceTree)
        body = next(rule for rule in tree.rules if rule.role == "body")
        contradictory = replace(
            graph,
            paths=(
                replace(
                    tree,
                    rules=tuple(
                        replace(rule, status="fails") if rule is body else rule
                        for rule in tree.rules
                    ),
                ),
            ),
        )

        with self.assertRaises(PolicyExplanationProjectionError) as ctx:
            _view(anchor, contradictory)
        self.assertEqual(ctx.exception.code, "POLICY_EVIDENCE_CONTRADICTION")

    def test_evidence_cannot_be_attached_to_another_semantic_row(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor)

        for key, value in (
            ("result_id", "evalr_v1:" + "f" * 64),
            ("row_id", "other-row"),
            ("claim_digest", "sha256:" + "f" * 64),
            ("semantic_row_anchor_digest", "sha256:" + "f" * 64),
        ):
            with self.subTest(key=key):
                forged = replace(graph, metadata={**graph.metadata, key: value})
                with self.assertRaises(PolicyExplanationProjectionError) as ctx:
                    _view(anchor, forged)
                self.assertEqual(ctx.exception.code, "EVIDENCE_ROW_ANCHOR_MISMATCH")

    def test_duplicate_semantic_rows_are_disambiguated_by_row_id(self) -> None:
        anchor = _duplicate_semantic_row(_anchor(_compiled(_occ("person"), ("person",))))
        graph = replace(_evidence(anchor), metadata={
            **_evidence(anchor).metadata,
            "row_id": anchor.row_anchors[1].row_id,
        })

        view = project_policy_explanation_v0(
            anchor,
            graph,
            semantic_row_anchor_digest=anchor.row_anchors[1].semantic_anchor_digest,
        )

        self.assertEqual(view.evaluation.root_state, "holds")

    def test_unknown_duplicate_and_timeline_paths_reject(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor)
        tree = graph.paths[0]
        assert isinstance(tree, EvidenceTree)
        cases = (
            (replace(graph, paths=(replace(tree, tree_id="unknown"),)), "UNKNOWN_EVIDENCE_BRANCH"),
            (replace(graph, paths=(tree, tree)), "DUPLICATE_EVIDENCE_BRANCH"),
            (
                replace(graph, paths=(EvidenceTimeline("timeline", "holds"),)),
                "UNSUPPORTED_EVIDENCE_LAYOUT",
            ),
        )
        for value, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(PolicyExplanationProjectionError) as ctx:
                    _view(anchor, value)
                self.assertEqual(ctx.exception.code, code)

    def test_zero_row_wrong_semantic_anchor_and_wrong_engine_reject(self) -> None:
        compiled = _compiled(_occ("person"), ("person",))
        anchor = _anchor(compiled)
        graph = _evidence(anchor)
        zero = _anchor(compiled, with_row=False)
        cases = (
            (zero, graph, "sha256:" + "f" * 64, "ZERO_ROW_HAS_NO_POLICY_VIEW"),
            (anchor, graph, "sha256:" + "f" * 64, "SEMANTIC_ROW_ANCHOR_NOT_FOUND"),
            (
                anchor,
                replace(graph, engine="souffle"),
                anchor.row_anchors[0].semantic_anchor_digest,
                "EVIDENCE_ENGINE_MISMATCH",
            ),
        )
        for run_anchor, inner, semantic, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(PolicyExplanationProjectionError) as ctx:
                    project_policy_explanation_v0(
                        run_anchor, inner, semantic_row_anchor_digest=semantic
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_positive_row_requires_one_contributing_policy_path(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        graph = _evidence(anchor, path_states={"c0": "fails"})

        with self.assertRaises(PolicyExplanationProjectionError) as ctx:
            _view(anchor, graph)
        self.assertEqual(ctx.exception.code, "POSITIVE_ROW_HAS_NO_HOLDING_POLICY_PATH")

    def test_holding_engine_path_cannot_hide_failed_policy_root(self) -> None:
        anchor = _anchor(_compiled(_occ("person"), ("person",)))
        root_id = anchor.target.policy_structure.root_node_id
        graph = _evidence(
            anchor,
            leaf_states={(root_id, "c0"): "fails"},
            path_states={"c0": "holds"},
        )

        with self.assertRaises(PolicyExplanationProjectionError) as ctx:
            _view(anchor, graph)
        self.assertEqual(ctx.exception.code, "POLICY_EVIDENCE_CONTRADICTION")

    def test_projection_is_deterministic_under_evidence_path_order(self) -> None:
        anchor = _anchor(_compiled(PolicyAny((_occ("left"), _occ("right"))), ("left", "right")))
        graph = _evidence(anchor)
        first = _view(anchor, graph)
        second = _view(anchor, replace(graph, paths=tuple(reversed(graph.paths))))

        self.assertEqual(first, second)
        self.assertEqual(first.projection_digest, second.projection_digest)

    def test_status_protocol_forbids_approved(self) -> None:
        with self.assertRaisesRegex(Exception, "state"):
            PolicyNodeBranchStateV0("c0", "approved")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
