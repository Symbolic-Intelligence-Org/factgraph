"""Shared derivation binding/body matching helpers for application runtimes."""

from __future__ import annotations

from typing import Any

from kernel.core.rules.where_eval import (
    _normalize_not_body,
    _vars_in_atoms,
    _vars_in_not_bodies,
)
from kernel.core.store._support import BindingItems


def _binding_matches(final_binding: dict[str, Any], requested: BindingItems) -> bool:
    """Subset match: every (var, value) in requested must appear in final_binding.

    Empty requested binding matches any final binding (any-result-exists semantics
    per audit log Step 0.C). Complete binding is the special case where the
    subset equals the full set.
    """
    return all(final_binding.get(key) == value for key, value in requested)


def _all_body_vars(body: list[Any]) -> set[str]:
    """Extract every $-variable referenced in the where body.

    Walks one-level AND or two-level OR-of-AND, plus into ``not`` subexpressions
    and ``ruleref`` term lists.
    """
    if not body:
        return set()
    if all(isinstance(item, list) for item in body):
        atoms_flat: list[Any] = [atom for branch in body for atom in branch]
    else:
        atoms_flat = list(body)

    found: set[str] = set(_vars_in_atoms(atoms_flat))

    not_bodies: list[list[tuple[Any, ...]]] = []
    for atom in atoms_flat:
        if isinstance(atom, tuple) and atom and atom[0] == "not" and len(atom) == 2:
            not_bodies.extend(_normalize_not_body(atom[1]))
    if not_bodies:
        found.update(_vars_in_not_bodies(not_bodies))

    for atom in atoms_flat:
        if (
            isinstance(atom, tuple)
            and atom
            and atom[0] == "ruleref"
            and len(atom) == 4
            and isinstance(atom[3], list)
        ):
            for term in atom[3]:
                if isinstance(term, str) and term.startswith("$") and len(term) > 1:
                    found.add(term)
    return found
