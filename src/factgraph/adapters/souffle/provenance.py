from __future__ import annotations

import ast
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factgraph.application.explain.evidence_tree import (
    LAYOUT_TREE,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    Fact,
    Holds,
    Source,
)
from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY
from factgraph.core.store._support import SOUFFLE_WITNESS_KIND


class SouffleProvenanceError(Exception):
    pass


@dataclass(frozen=True)
class SouffleProofNodeV0:
    """Single node in a Souffle proof tree. Adapter-local, not a core contract."""

    node_type: str
    relation: str
    args: tuple[str, ...]
    rule_number: str | None
    children: tuple["SouffleProofNodeV0", ...]


@dataclass(frozen=True)
class SouffleProofTreeV0:
    """Complete proof response from Souffle -t explain."""

    query: str
    root: SouffleProofNodeV0
    rules: dict[str, str]


def souffle_proof_tree_to_evidence_graph(
    proof_tree: SouffleProofTreeV0,
    *,
    candidate_id: str,
    support_kind: str = SOUFFLE_WITNESS_KIND,
) -> EvidenceGraph:
    """Convert a Souffle proof tree into an EvidenceGraph tree."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")

    rules: list[EvidenceRule] = []

    root = proof_tree.root
    rules.append(
        EvidenceRule(
            occurrence_alias="head",
            rule_id=root.rule_number or root.relation,
            role="head",
            status="holds",
            ports={},
            atoms=(_evidence_atom_for_proof_node(root, candidate_id=candidate_id, role="head"),),
        )
    )
    _append_body_rules(root, proof_tree=proof_tree, candidate_id=candidate_id, rules=rules)

    return EvidenceGraph(
        graph_id=f"eg:{candidate_id}",
        engine="souffle",
        layout_hint=LAYOUT_TREE,
        subject_binding={},
        paths=(
            EvidenceTree(
                tree_id=candidate_id,
                status="holds",
                rules=tuple(rules),
                joins=(),
                certainty=BOOLEAN_CERTAINTY,
                metadata={"support_kind": support_kind},
            ),
        ),
        certainty=BOOLEAN_CERTAINTY,
        metadata={
            "query": proof_tree.query,
            "rule_count": len(proof_tree.rules),
            "root_relation": proof_tree.root.relation,
            "root_rule_number": proof_tree.root.rule_number,
            "support_kind": support_kind,
        },
    )


def _append_body_rules(
    node: SouffleProofNodeV0,
    *,
    proof_tree: SouffleProofTreeV0,
    candidate_id: str,
    rules: list[EvidenceRule],
) -> None:
    if node.children:
        rule_number = node.rule_number or node.relation
        rules.append(
            EvidenceRule(
                occurrence_alias=f"souffle:{rule_number}",
                rule_id=rule_number,
                role="body",
                status="holds",
                ports={},
                atoms=tuple(
                    _evidence_atom_for_proof_node(child, candidate_id=candidate_id, role="body")
                    for child in node.children
                ),
            )
        )
    for child in node.children:
        _append_body_rules(child, proof_tree=proof_tree, candidate_id=candidate_id, rules=rules)


def _evidence_atom_for_proof_node(
    node: SouffleProofNodeV0,
    *,
    candidate_id: str,
    role: str,
) -> EvidenceAtom:
    atom_text = _proof_node_atom_text(node)
    source = Source(
        ref=f"souffle:{candidate_id}:{role}:{atom_text}",
        value=atom_text,
        meta={
            "event_status": node.node_type,
            "relation": node.relation,
            "args": node.args,
            "rule_number": node.rule_number,
            "child_count": len(node.children),
        },
    )
    return EvidenceAtom(
        form=Fact(
            predicate=node.relation,
            terms=tuple(Const(arg) for arg in node.args),
        ),
        verdict=Holds(certainty=BOOLEAN_CERTAINTY, support=(source,)),
        atom_id=f"souffle:{candidate_id}:{role}:{atom_text}",
        repr_text=atom_text,
        negated=node.node_type == "negation",
    )


def souffle_proof_tree_from_dict(row: dict[str, Any]) -> SouffleProofTreeV0:
    """Reconstruct ``SouffleProofTreeV0`` from an audit-package dict."""
    if not isinstance(row, dict):
        raise ValueError("row must be dict")
    root = row.get("root")
    if not isinstance(root, dict):
        raise ValueError("row.root must be dict")
    raw_rules = row.get("rules", {})
    if not isinstance(raw_rules, dict):
        raise ValueError("row.rules must be dict")
    return SouffleProofTreeV0(
        query=str(row.get("query", "")),
        root=_souffle_proof_node_from_dict(root),
        rules={
            str(key): str(value)
            for key, value in raw_rules.items()
            if isinstance(key, str) and key and isinstance(value, str)
        },
    )


def parse_souffle_proof_json(json_text: str) -> list[SouffleProofTreeV0]:
    payloads = _decode_json_values(json_text)
    trees: list[SouffleProofTreeV0] = []
    for payload in payloads:
        trees.extend(_parse_response_payload(payload))
    return trees


def run_provenance_explain(
    souffle_bin_path: Path,
    program_path: Path,
    facts_dir: Path,
    queries: list[str],
) -> list[SouffleProofTreeV0]:
    cleaned_queries = [query.strip() for query in queries if query.strip()]
    if not cleaned_queries:
        return []
    if not souffle_bin_path.exists():
        raise FileNotFoundError(f"missing souffle binary: {souffle_bin_path}")
    if not program_path.exists():
        raise FileNotFoundError(f"missing Souffle program: {program_path}")
    if not facts_dir.exists() or not facts_dir.is_dir():
        raise FileNotFoundError(f"missing facts directory: {facts_dir}")

    explain_input = "format json\n" + "".join(f"explain {query}\n" for query in cleaned_queries)

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.run(
            [
                str(souffle_bin_path),
                "-F",
                str(facts_dir),
                "-D",
                tmpdir,
                "-t",
                "explain",
                str(program_path),
            ],
            input=explain_input,
            capture_output=True,
            text=True,
            check=False,
        )

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown Souffle explain failure"
        raise SouffleProvenanceError(
            f"Souffle provenance explain failed with exit_code={proc.returncode}: {detail}"
        )

    return parse_souffle_proof_json(proc.stdout)


def run_package_provenance(
    package_dir: Path,
    queries: list[str],
) -> list[SouffleProofTreeV0]:
    """Run provenance explain on an exported factpy package.

    Convenience wrapper: assembles the Souffle program from the package's
    manifest (same logic as runner._build_program_file), locates the
    Souffle binary, and calls run_provenance_explain.

    This is adapter-local. It does NOT modify the package or its manifest.
    """
    from factgraph.adapters.souffle.runner import find_souffle_binary

    pkg_dir = Path(package_dir)
    manifest_path = pkg_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    facts_dir = pkg_dir / "facts"

    view_text = (pkg_dir / manifest["paths"]["rules"]["view"]).read_text(encoding="utf-8")
    idb_text = (pkg_dir / manifest["paths"]["rules"]["idb"]).read_text(encoding="utf-8")
    policy_text = ""
    if manifest.get("policy_mode") == "idb":
        policy_path = pkg_dir / "policy" / "policy_rules.dl"
        if policy_path.exists():
            policy_text = policy_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as work_dir:
        program_path = Path(work_dir) / "program.dl"
        program_path.write_text(
            "\n".join([view_text, policy_text, idb_text]) + "\n",
            encoding="utf-8",
        )

        souffle_bin = find_souffle_binary()
        if souffle_bin is None:
            raise SouffleProvenanceError("souffle binary not found")

        return run_provenance_explain(souffle_bin, program_path, facts_dir, queries)


def _parse_response_payload(payload: Any) -> list[SouffleProofTreeV0]:
    if isinstance(payload, list):
        trees: list[SouffleProofTreeV0] = []
        for item in payload:
            trees.extend(_parse_response_payload(item))
        return trees

    if not isinstance(payload, dict):
        raise SouffleProvenanceError(f"expected object or list response, got: {type(payload).__name__}")

    proof_payload = payload.get("proof")
    if not isinstance(proof_payload, dict):
        raise SouffleProvenanceError("response is missing object field: proof")

    rules = _parse_rules(payload.get("rules"))
    root = _parse_proof_node(proof_payload)
    return [
        SouffleProofTreeV0(
            query=_proof_query_text(proof_payload),
            root=root,
            rules=rules,
        )
    ]


def _parse_rules(raw_rules: Any) -> dict[str, str]:
    if not isinstance(raw_rules, list):
        return {}
    rules: dict[str, str] = {}
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        rule_number = item.get("rule-number")
        rule_text = item.get("rule")
        if isinstance(rule_number, str) and rule_number and isinstance(rule_text, str):
            rules[rule_number] = rule_text
    return rules


def _parse_proof_node(payload: Any) -> SouffleProofNodeV0:
    if not isinstance(payload, dict):
        raise SouffleProvenanceError(f"proof node must be an object, got: {type(payload).__name__}")

    if "premises" in payload:
        premise = payload.get("premises")
        if not isinstance(premise, str) or not premise.strip():
            raise SouffleProvenanceError("derived node is missing non-empty premises text")
        relation, args = _parse_atom_text(premise)
        raw_children = payload.get("children")
        if raw_children is None:
            children = ()
        elif isinstance(raw_children, list):
            children = tuple(_parse_proof_node(item) for item in raw_children)
        else:
            raise SouffleProvenanceError("derived node children must be a list when present")
        rule_number = payload.get("rule-number")
        if rule_number is not None and not isinstance(rule_number, str):
            raise SouffleProvenanceError("derived node rule-number must be a string when present")
        return SouffleProofNodeV0(
            node_type="derived",
            relation=relation,
            args=args,
            rule_number=rule_number,
            children=children,
        )

    if "axiom" in payload:
        axiom = payload.get("axiom")
        if not isinstance(axiom, str) or not axiom.strip():
            raise SouffleProvenanceError("axiom node is missing non-empty axiom text")
        is_negation = axiom.lstrip().startswith("!")
        stripped = axiom.lstrip("!").strip()
        if stripped.startswith("subproof "):
            subproof_atom = stripped[len("subproof ") :].strip()
            if subproof_atom:
                relation, args = _parse_atom_text(subproof_atom)
            else:
                relation, args = "subproof", ()
            return SouffleProofNodeV0(
                node_type="subproof",
                relation=relation,
                args=args,
                rule_number=None,
                children=(),
            )
        relation, args = _parse_atom_text(axiom)
        return SouffleProofNodeV0(
            node_type="negation" if is_negation else "axiom",
            relation=relation,
            args=args,
            rule_number=None,
            children=(),
        )

    raise SouffleProvenanceError("proof node must contain either premises or axiom")


def _proof_query_text(proof_payload: dict[str, Any]) -> str:
    for key in ("premises", "axiom"):
        value = proof_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise SouffleProvenanceError("proof root is missing query text")


def _parse_atom_text(atom_text: str) -> tuple[str, tuple[str, ...]]:
    raw_text = atom_text.strip()
    if not raw_text:
        raise SouffleProvenanceError("atom text must be non-empty")
    if raw_text.startswith("!"):
        raw_text = raw_text[1:].strip()

    if "(" not in raw_text:
        return raw_text, ()

    try:
        expr = ast.parse(raw_text, mode="eval")
    except SyntaxError as exc:
        raise SouffleProvenanceError(f"invalid Souffle atom syntax: {atom_text}") from exc

    call = expr.body
    if not isinstance(call, ast.Call):
        raise SouffleProvenanceError(f"expected function-call atom syntax: {atom_text}")
    if call.keywords:
        raise SouffleProvenanceError(f"keyword args are unsupported in Souffle atoms: {atom_text}")

    relation = _parse_relation_name(call.func, atom_text)
    args = tuple(_parse_atom_arg(arg, raw_text) for arg in call.args)
    return relation, args


def _parse_relation_name(func: ast.AST, atom_text: str) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return ast.unparse(func)
    raise SouffleProvenanceError(f"unsupported relation name syntax: {atom_text}")


def _parse_atom_arg(arg: ast.AST, source_text: str) -> str:
    if isinstance(arg, ast.Constant):
        if isinstance(arg.value, str):
            return arg.value
        if arg.value is None:
            return "null"
        return str(arg.value)
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
        return f"-{_parse_atom_arg(arg.operand, source_text)}"
    return ast.unparse(arg)


def _proof_node_atom_text(node: SouffleProofNodeV0) -> str:
    base = node.relation
    if node.args:
        base = f"{base}({', '.join(node.args)})"
    if node.node_type == "negation":
        return f"!{base}"
    if node.node_type == "subproof":
        return f"subproof {base}"
    return base


def _proof_node_component_and_value(node: SouffleProofNodeV0) -> tuple[str, str]:
    if not node.args:
        return ("()", "true")
    component = node.args[0]
    if len(node.args) == 1:
        return (component, "true")
    return (component, ", ".join(node.args[1:]))


def _souffle_proof_node_from_dict(row: dict[str, Any]) -> SouffleProofNodeV0:
    if not isinstance(row, dict):
        raise ValueError("proof node row must be dict")
    args = row.get("args")
    children = row.get("children")
    if not isinstance(args, list):
        raise ValueError("proof node args must be list")
    if not isinstance(children, list):
        raise ValueError("proof node children must be list")
    rule_number = row.get("rule_number")
    return SouffleProofNodeV0(
        node_type=str(row.get("node_type", "unknown")),
        relation=str(row.get("relation", "?")),
        args=tuple(str(arg) for arg in args),
        rule_number=rule_number if isinstance(rule_number, str) else None,
        children=tuple(
            _souffle_proof_node_from_dict(child)
            for child in children
            if isinstance(child, dict)
        ),
    )


def _decode_json_values(json_text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    length = len(json_text)
    while index < length:
        while index < length and json_text[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            value, next_index = decoder.raw_decode(json_text, index)
        except json.JSONDecodeError as exc:
            raise SouffleProvenanceError(
                f"invalid JSON provenance stream near index {exc.pos}: {exc.msg}"
            ) from exc
        values.append(value)
        index = next_index
    return values


__all__ = [
    "SouffleProofNodeV0",
    "SouffleProofTreeV0",
    "SouffleProvenanceError",
    "parse_souffle_proof_json",
    "run_provenance_explain",
    "run_package_provenance",
    "souffle_proof_tree_from_dict",
    "souffle_proof_tree_to_evidence_graph",
]
