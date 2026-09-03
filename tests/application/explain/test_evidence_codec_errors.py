from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from factgraph.application.explain import (
    EvidencePolicyCondition,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
from factgraph.application.explain.evidence_tree import EvidenceProbeBranchTerminalBindings
from factgraph.application.protocol import ProtocolShapeError
from factgraph.application.protocol.evaluation_evidence_capture_v2 import (
    evaluation_evidence_graph_from_bytes_v2,
)
from factgraph.audit.reader import AuditReadError, _read_evidence_graphs


def _graph_row():
    atom = {
        "form": {
            "kind": "fact",
            "predicate": "person:name",
            "terms": [{"kind": "const", "value": "Alice"}],
        },
        "verdict": {"kind": "holds", "support": [{"ref": "assertion-1"}]},
        "atom_id": "atom-1",
    }
    port = {"rule_occurrence_alias": "residence", "port_name": "person"}
    return {
        "graph_id": "graph-1",
        "engine": "native",
        "layout_hint": "tree",
        "subject_binding": {},
        "certainty": {"lo": 1.0, "hi": 1.0, "kind": "boolean"},
        "paths": [
            {
                "kind": "tree",
                "tree_id": "tree-1",
                "status": "holds",
                "rules": [
                    {
                        "occurrence_alias": "residence",
                        "rule_id": "rule-1",
                        "role": "body",
                        "status": "holds",
                        "atoms": [atom],
                    }
                ],
                "joins": [{"left": port, "right": port, "status": "holds", "join_id": "join-1"}],
                "policy_conditions": [
                    {
                        "policy_node_id": "policy-1",
                        "condition_id": "condition-1",
                        "role": "compare",
                        "atom": atom,
                    }
                ],
            }
        ],
    }


def _malformed_rows():
    tree = ("paths", 0)
    rule = (*tree, "rules", 0)
    atom = (*rule, "atoms", 0)
    cases = (
        (("paths",), "row.paths must be list"),
        (tree, "path row must be Mapping[str, Any]"),
        ((*tree, "rules"), "tree.rules must be list"),
        ((*tree, "joins"), "tree.joins must be list"),
        ((*tree, "policy_conditions"), "tree.policy_conditions must be list"),
        (rule, "rule row must be Mapping[str, Any]"),
        ((*rule, "atoms"), "rule.atoms must be list"),
        ((*tree, "joins", 0), "join row must be Mapping[str, Any]"),
        ((*tree, "joins", 0, "left"), "port ref row must be Mapping[str, Any]"),
        ((*tree, "policy_conditions", 0), "policy condition row must be Mapping[str, Any]"),
        (atom, "atom row must be Mapping[str, Any]"),
        ((*atom, "form"), "atom form row must be Mapping[str, Any]"),
        ((*atom, "form", "terms"), "fact.terms must be list"),
        ((*atom, "form", "terms", 0), "term row must be Mapping[str, Any]"),
        ((*atom, "verdict"), "verdict row must be Mapping[str, Any]"),
        ((*atom, "verdict", "support", 0), "source row must be Mapping[str, Any]"),
        ((*atom, "timestep"), "atom.timestep must be int or None"),
        (("certainty",), "certainty row must be Mapping[str, Any] or None"),
        (("certainty", "lo"), "certainty.lo must be number"),
        (("metadata",), "row.metadata must be Mapping[str, Any]"),
    )
    for path, message in cases:
        row = deepcopy(_graph_row())
        parent = row
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = True
        yield path, row, message


class EvidenceCodecErrorContractTests(unittest.TestCase):
    def test_fixture_round_trips_before_fault_injection(self):
        graph = evidence_graph_from_dict(_graph_row())
        self.assertEqual(evidence_graph_from_dict(evidence_graph_to_dict(graph)), graph)

    def test_nested_shape_errors_remain_exact_value_errors(self):
        for path, row, message in _malformed_rows():
            with self.subTest(path=path), self.assertRaises(ValueError) as caught:
                evidence_graph_from_dict(row)
            self.assertIs(type(caught.exception), ValueError)
            self.assertEqual(str(caught.exception), message)
            self.assertIsNone(caught.exception.__cause__)

    def test_audit_reader_wraps_each_nested_shape_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence_graphs.jsonl"
            for location, row, message in _malformed_rows():
                path.write_text(
                    json.dumps({"candidate_id": "candidate-1", "evidence_graph": row}) + "\n"
                )
                with self.subTest(path=location), self.assertRaises(AuditReadError) as caught:
                    _read_evidence_graphs(Path(tmp), {"evidence_graphs": path.name})
                self.assertEqual(
                    str(caught.exception),
                    f"invalid evidence_graph for candidate candidate-1: {message}",
                )
                self.assertIs(type(caught.exception.__cause__), ValueError)
                self.assertEqual(str(caught.exception.__cause__), message)

    def test_retained_capture_wraps_each_nested_shape_error(self):
        for path, row, message in _malformed_rows():
            raw = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
            with self.subTest(path=path), self.assertRaises(ProtocolShapeError) as caught:
                evaluation_evidence_graph_from_bytes_v2(raw)
            self.assertEqual(str(caught.exception), "Evaluation evidence graph is malformed")
            self.assertIs(type(caught.exception.__cause__), ValueError)
            self.assertEqual(str(caught.exception.__cause__), message)

    def test_top_level_codec_and_dto_shape_errors_remain_value_errors(self):
        cases = (
            (evidence_graph_to_dict, (None,), "graph must be EvidenceGraph"),
            (evidence_graph_from_dict, (None,), "row must be Mapping[str, Any]"),
            (
                EvidencePolicyCondition,
                ("policy-1", "condition-1", "compare", None),
                "policy condition atom must be EvidenceAtom",
            ),
            (EvidenceProbeBranchTerminalBindings, ("branch-1", []), "environments must be a tuple"),
            (
                EvidenceProbeBranchTerminalBindings,
                ("branch-1", (None,)),
                "environment must be a mapping",
            ),
        )
        for factory, args, message in cases:
            with self.subTest(message=message), self.assertRaises(ValueError) as caught:
                factory(*args)
            self.assertIs(type(caught.exception), ValueError)
            self.assertEqual(str(caught.exception), message)
