from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from factpy.adapters.souffle.provenance import (
    SouffleProofTreeV0,
    SouffleProvenanceError,
    parse_souffle_proof_json,
    run_package_provenance,
    run_provenance_explain,
)


DISPOSAL_JSON = r"""
{
  "proof": {
    "premises": "disposal_compliant(\"sentinel_7\", 920000)",
    "rule-number": "(R1)",
    "children": [
      {"axiom": "disposal_probability(\"sentinel_7\", 920000)"},
      {"axiom": "threshold_min(\"disposal_probability\", 900000)"}
    ]
  },
  "rules": [
    {"rule-number": "(R1)", "rule": "disposal_compliant(M,P) :- disposal_probability(M,P), threshold_min(\"disposal_probability\", T), P >= T."}
  ]
}
"""

PASSIVATION_JSON = r"""
{
  "proof": {
    "premises": "component_not_passivated(\"power_system\")",
    "rule-number": "(R3)",
    "children": [
      {"axiom": "has_sub_component(\"power_system\", \"battery_2\")"},
      {
        "premises": "component_not_passivated(\"battery_2\")",
        "rule-number": "(R2)",
        "children": [
          {"axiom": "has_sub_component(\"power_system\", \"battery_2\")"},
          {"axiom": "!component_passivated(\"battery_2\")"}
        ]
      }
    ]
  },
  "rules": [
    {"rule-number": "(R2)", "rule": "component_not_passivated(C) :- !component_passivated(C)."},
    {"rule-number": "(R3)", "rule": "component_not_passivated(P) :- has_sub_component(P, C), component_not_passivated(C)."}
  ]
}
"""


class SouffleProvenanceV0Tests(unittest.TestCase):
    def test_parse_souffle_proof_json_parses_flat_and_recursive_cases(self) -> None:
        trees = parse_souffle_proof_json(DISPOSAL_JSON + "\n" + PASSIVATION_JSON)

        self.assertEqual(len(trees), 2)
        disposal, passivation = trees

        self.assertEqual(disposal.query, 'disposal_compliant("sentinel_7", 920000)')
        self.assertEqual(disposal.root.node_type, "derived")
        self.assertEqual(disposal.root.relation, "disposal_compliant")
        self.assertEqual(disposal.root.args, ("sentinel_7", "920000"))
        self.assertEqual(disposal.root.rule_number, "(R1)")
        self.assertEqual(len(disposal.root.children), 2)
        self.assertEqual(disposal.rules["(R1)"], 'disposal_compliant(M,P) :- disposal_probability(M,P), threshold_min("disposal_probability", T), P >= T.')

        self.assertEqual(passivation.query, 'component_not_passivated("power_system")')
        self.assertEqual(passivation.root.relation, "component_not_passivated")
        self.assertEqual(passivation.root.rule_number, "(R3)")
        self.assertEqual(len(passivation.root.children), 2)
        recursive_child = passivation.root.children[1]
        self.assertEqual(recursive_child.node_type, "derived")
        self.assertEqual(recursive_child.rule_number, "(R2)")
        negation_leaf = recursive_child.children[1]
        self.assertEqual(negation_leaf.node_type, "negation")
        self.assertEqual(negation_leaf.relation, "component_passivated")
        self.assertEqual(negation_leaf.args, ("battery_2",))

    def test_parse_souffle_proof_json_accepts_json_array_payload(self) -> None:
        payload = f"[{DISPOSAL_JSON.strip()}, {PASSIVATION_JSON.strip()}]"
        trees = parse_souffle_proof_json(payload)

        self.assertEqual([tree.root.relation for tree in trees], ["disposal_compliant", "component_not_passivated"])

    def test_parse_subproof_leaf_node(self) -> None:
        json_text = json.dumps(
            {
                "proof": {
                    "premises": "top(1)",
                    "rule-number": "(R1)",
                    "children": [
                        {"axiom": "base(1)"},
                        {"axiom": "subproof mid(0)"},
                    ],
                },
            }
        )
        trees = parse_souffle_proof_json(json_text)

        self.assertEqual(len(trees), 1)
        root = trees[0].root
        self.assertEqual(root.node_type, "derived")
        self.assertEqual(len(root.children), 2)

        base_child = root.children[0]
        self.assertEqual(base_child.node_type, "axiom")
        self.assertEqual(base_child.relation, "base")

        subproof_child = root.children[1]
        self.assertEqual(subproof_child.node_type, "subproof")
        self.assertEqual(subproof_child.relation, "mid")
        self.assertEqual(subproof_child.args, ("0",))
        self.assertEqual(subproof_child.children, ())

    def test_run_provenance_explain_calls_souffle_with_explain_mode(self) -> None:
        with TemporaryDirectory() as tmpdir:
            facts_dir = Path(tmpdir) / "facts"
            facts_dir.mkdir()
            program_path = Path(tmpdir) / "program.dl"
            program_path.write_text(".decl p(x:symbol)\n", encoding="utf-8")
            souffle_bin = Path(tmpdir) / "souffle"
            souffle_bin.write_text("", encoding="utf-8")

            expected_stdout = DISPOSAL_JSON + "\n" + PASSIVATION_JSON
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=expected_stdout,
                stderr="",
            )

            with patch(
                "factpy.adapters.souffle.provenance.subprocess.run",
                return_value=completed,
            ) as run_mock:
                trees = run_provenance_explain(
                    souffle_bin_path=souffle_bin,
                    program_path=program_path,
                    facts_dir=facts_dir,
                    queries=[
                        'disposal_compliant("sentinel_7", 920000)',
                        'component_not_passivated("power_system")',
                    ],
                )

            self.assertEqual(len(trees), 2)
            self.assertTrue(all(isinstance(tree, SouffleProofTreeV0) for tree in trees))
            _, kwargs = run_mock.call_args
            self.assertEqual(
                run_mock.call_args.args[0][0:6],
                [
                    str(souffle_bin),
                    "-F",
                    str(facts_dir),
                    "-D",
                    unittest.mock.ANY,
                    "-t",
                ][0:6],
            )
            self.assertIn("format json\n", kwargs["input"])
            self.assertIn('explain disposal_compliant("sentinel_7", 920000)\n', kwargs["input"])
            self.assertIn('explain component_not_passivated("power_system")\n', kwargs["input"])

    def test_run_provenance_explain_raises_on_non_zero_exit(self) -> None:
        with TemporaryDirectory() as tmpdir:
            facts_dir = Path(tmpdir) / "facts"
            facts_dir.mkdir()
            program_path = Path(tmpdir) / "program.dl"
            program_path.write_text(".decl p(x:symbol)\n", encoding="utf-8")
            souffle_bin = Path(tmpdir) / "souffle"
            souffle_bin.write_text("", encoding="utf-8")

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=2,
                stdout="",
                stderr="bad query",
            )

            with patch(
                "factpy.adapters.souffle.provenance.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaises(SouffleProvenanceError):
                    run_provenance_explain(
                        souffle_bin_path=souffle_bin,
                        program_path=program_path,
                        facts_dir=facts_dir,
                        queries=['component_not_passivated("power_system")'],
                    )

    def test_run_package_provenance_builds_program_from_package(self) -> None:
        with TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir) / "pkg"
            facts_dir = pkg_dir / "facts"
            rules_dir = pkg_dir / "rules"
            policy_dir = pkg_dir / "policy"
            facts_dir.mkdir(parents=True)
            rules_dir.mkdir()
            policy_dir.mkdir()

            (rules_dir / "view.dl").write_text(".decl view_fact(x:symbol)\n", encoding="utf-8")
            (rules_dir / "idb.dl").write_text(".decl derived_fact(x:symbol)\n", encoding="utf-8")
            (policy_dir / "policy_rules.dl").write_text(".decl policy_fact(x:symbol)\n", encoding="utf-8")
            (pkg_dir / "manifest.json").write_text(
                '{"paths":{"rules":{"view":"rules/view.dl","idb":"rules/idb.dl"}},"policy_mode":"idb"}',
                encoding="utf-8",
            )

            souffle_bin = Path(tmpdir) / "souffle"
            souffle_bin.write_text("", encoding="utf-8")
            captured: dict[str, object] = {}

            def _fake_run(
                souffle_bin_path: Path,
                program_path: Path,
                facts_dir_path: Path,
                queries: list[str],
            ) -> list[SouffleProofTreeV0]:
                captured["souffle_bin_path"] = souffle_bin_path
                captured["facts_dir"] = facts_dir_path
                captured["queries"] = list(queries)
                captured["program_text"] = program_path.read_text(encoding="utf-8")
                return []

            with patch(
                "factpy.adapters.souffle.runner.find_souffle_binary",
                return_value=souffle_bin,
            ), patch(
                "factpy.adapters.souffle.provenance.run_provenance_explain",
                side_effect=_fake_run,
            ):
                trees = run_package_provenance(
                    package_dir=pkg_dir,
                    queries=['component_not_passivated("power_system")'],
                )

            self.assertEqual(trees, [])
            self.assertEqual(captured["souffle_bin_path"], souffle_bin)
            self.assertEqual(captured["facts_dir"], facts_dir)
            self.assertEqual(captured["queries"], ['component_not_passivated("power_system")'])
            self.assertEqual(
                captured["program_text"],
                ".decl view_fact(x:symbol)\n\n.decl policy_fact(x:symbol)\n\n.decl derived_fact(x:symbol)\n\n",
            )


if __name__ == "__main__":
    unittest.main()
