from __future__ import annotations

from typing import Any

from factgraph.application.protocol.rule_expr_lowering import RuleExprJoinMaterialization


def atom_id_for_condition(branch_id: str, condition_index: int, *, materialized: bool = False) -> str:
    prefix = "materialized" if materialized else "atom"
    return f"{branch_id}:{prefix}:{condition_index}"


def join_id_for_materialization(join: RuleExprJoinMaterialization) -> str:
    return (
        f"{join.branch_id}:{join.left_occurrence_alias}.{join.left_port_name}"
        f"={join.right_occurrence_alias}.{join.right_port_name}"
    )


def vars_in_atom_tuple(atom: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(atom, str) and atom.startswith("$"):
        return (atom,)
    if isinstance(atom, (list, tuple)):
        for item in atom:
            found.extend(vars_in_atom_tuple(item))
    return tuple(dict.fromkeys(found))


def alias_for_atom(atom: tuple[Any, ...], aliases: tuple[str, ...]) -> str | None:
    variables = vars_in_atom_tuple(atom)
    for alias in aliases:
        prefix = f"${alias}__"
        if any(var.startswith(prefix) for var in variables):
            return alias
    return None


def is_head_atom(atom: tuple[Any, ...], aliases: tuple[str, ...]) -> bool:
    return alias_for_atom(atom, aliases) is None and any(
        name.startswith("$__head__") for name in vars_in_atom_tuple(atom)
    )


__all__ = [
    "alias_for_atom",
    "atom_id_for_condition",
    "is_head_atom",
    "join_id_for_materialization",
    "vars_in_atom_tuple",
]
