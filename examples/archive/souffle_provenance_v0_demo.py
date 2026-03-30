from __future__ import annotations

from factpy_kernel.adapters.souffle.provenance import parse_souffle_proof_json


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


def main() -> None:
    tree = parse_souffle_proof_json(PASSIVATION_JSON)[0]
    print(tree.query)
    for line in _render_node(tree.root, tree.rules):
        print(line)


def _render_node(node, rules, depth: int = 0) -> list[str]:
    indent = "  " * depth
    label = f"{indent}- {node.node_type}: {node.relation}{node.args}"
    if node.rule_number is not None:
        rule_text = rules.get(node.rule_number, "<missing rule text>")
        label += f" [{node.rule_number} {rule_text}]"
    lines = [label]
    for child in node.children:
        lines.extend(_render_node(child, rules, depth + 1))
    return lines


if __name__ == "__main__":
    main()
