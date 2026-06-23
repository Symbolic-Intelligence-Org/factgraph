"""Assemble diagnostic companion query results into EvidenceGraph objects."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from factgraph.adapters.problog.diagnostic_emit import (
    DiagnosticProbLogResult,
    DiagnosticWitnessProbability,
)
from factgraph.application.explain.diagnostic_projection import CompanionProgram
from factgraph.application.explain.evidence_tree import (
    BOOLEAN_CERTAINTY,
    BoundVar,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceTree,
    Fails,
    Holds,
    LAYOUT_TREE,
    NotReached,
)
from factgraph.application.explain.prober import (
    ProbeEnv,
    fact_source_for_atom,
    _atom_form,
    _atom_status,
    _bake_repr_text,
    _body_rules_for_branch,
    _fold_join_status,
    _head_atom_indexes_for_branch,
    _head_rule_for_plan,
    _is_not_atom,
    _joins_for_trace,
    _normalize_compiled_body,
    _repr_not_atom,
    _render_term_value,
    _tree_status,
)
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprLoweringPlan,
    _materialize_adapter_derivation_plan,
)


class DiagnosticAssemblyError(Exception):
    pass


def diagnostic_problog_result_to_evidence_graph(
    result: DiagnosticProbLogResult,
    *,
    plan: RuleExprLoweringPlan,
    companion: CompanionProgram,
    graph_id: str,
    engine: str,
    view_facts: Mapping[str, Sequence[tuple[Any, ...]]],
    schema_index: object | None,
    rules_by_id: Mapping[str, Any],
    subject_binding: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
    graph_certainty: Certainty | None = None,
    probabilistic: bool = True,
    input_certainty_for_goal: Callable[[str, tuple[Any, ...]], Certainty | None] | None = None,
) -> EvidenceGraph:
    if not isinstance(result, DiagnosticProbLogResult):
        raise DiagnosticAssemblyError("result must be DiagnosticProbLogResult")
    materialize_engine = "problog" if engine == "problog" else "souffle" if engine == "souffle" else engine
    compiled, traces = _materialize_adapter_derivation_plan(plan, engine=materialize_engine)
    branches = _normalize_compiled_body(compiled.body_ir)
    companion_by_branch = {branch.branch_id: branch for branch in companion.branches}
    witnesses = _witnesses_by_atom(result.witnesses)
    atom_probs = _probabilities_by_atom(result)
    tree_paths: list[EvidenceTree] = []
    view = {key: list(value) for key, value in view_facts.items()}
    for branch_atoms, lowered_branch, trace in zip(branches, plan.branches, traces, strict=True):
        branch_id = trace.branch_id
        companion_branch = companion_by_branch.get(branch_id)
        if companion_branch is None:
            raise DiagnosticAssemblyError(f"missing companion branch {branch_id!r}")
        anchor_env = ProbeEnv.from_bindings({key: term.value for key, term in companion.anchor.items()})
        atom_results: list[tuple[int, tuple[Any, ...], EvidenceAtom, tuple[ProbeEnv, ...]]] = []
        branch_envs: list[ProbeEnv] = []
        known_envs: tuple[ProbeEnv, ...] = (anchor_env,)
        for idx, atom in enumerate(branch_atoms):
            key = (branch_id, idx)
            atom_witnesses = tuple(witnesses.get(key, ()))
            input_certainty = _input_certainty_for_atom(atom, atom_witnesses, input_certainty_for_goal)
            verdict = _verdict_for_atom(
                atom_probs.get(key),
                probabilistic=probabilistic,
                holds_certainty=input_certainty,
            )
            envs = _envs_for_witnesses(atom, atom_witnesses, anchor_env)
            if envs:
                branch_envs.extend(envs)
                known_envs = _merge_envs(known_envs, envs)
            form_envs = envs or known_envs
            form = _atom_form(atom, form_envs)
            negated = _is_not_atom(atom)
            if isinstance(verdict, NotReached) and not envs:
                repr_text = _not_reached_repr(atom)
            else:
                repr_text = (
                    _repr_not_atom(atom, form_envs, schema_index, view_facts=view)
                    if negated
                    else _bake_repr_text(form, schema_index, view_facts=view)
                )
            atom_id = f"{branch_id}:atom:{idx}"
            if isinstance(verdict, Holds):
                source = fact_source_for_atom(form, atom_id, engine=engine, repr_text=repr_text)
                if source is not None:
                    verdict = Holds(certainty=verdict.certainty, support=(source,))
            evidence_atom = EvidenceAtom(
                form=form,
                verdict=verdict,
                atom_id=atom_id,
                repr_text=repr_text,
                negated=negated,
            )
            atom_results.append((idx, atom, evidence_atom, envs))
        terminal_envs = _sorted_envs(branch_envs) or (anchor_env,)
        display_terminal_envs = _display_envs(
            terminal_envs,
            schema_index=schema_index,
            view_facts=view,
        )
        head_atom_indexes = _head_atom_indexes_for_branch(lowered_branch, trace, atom_results)
        head_atoms = tuple(evidence_atom for idx, _atom, evidence_atom, _envs in atom_results if idx in head_atom_indexes)
        body_rules = _body_rules_for_branch(
            plan,
            lowered_branch,
            trace,
            atom_results,
            terminal_envs=display_terminal_envs,
            head_atom_indexes=head_atom_indexes,
            rules_by_id=rules_by_id,
        )
        body_status = _tree_status((*body_rules,)) if body_rules else "holds"
        head_status = _atom_status(head_atoms) if head_atoms else body_status
        head_rule = _head_rule_for_plan(
            plan,
            status=head_status,
            terminal_envs=display_terminal_envs,
            initial_bindings=anchor_env.bindings,
            atoms=head_atoms,
            subject_binding=subject_binding,
        )
        rules = (head_rule, *body_rules)
        joins = _joins_for_trace(trace, atom_results)
        tree_status = _fold_join_status(_tree_status(rules), joins)
        branch_probability = result.branch_probabilities.get(branch_id)
        head_probability = result.head_probabilities.get(branch_id)
        occ_probabilities = {
            alias: probability
            for (prob_branch, alias), probability in result.occurrence_probabilities.items()
            if prob_branch == branch_id
        }
        tree_paths.append(
            EvidenceTree(
                tree_id=branch_id,
                status=tree_status,
                rules=rules,
                joins=joins,
                certainty=_probabilistic_certainty(branch_probability, probabilistic=probabilistic),
                metadata={
                    "branch_id": branch_id,
                    "runtime_case_index": trace.runtime_case_index,
                    "branch_probability": branch_probability,
                    "head_probability": head_probability,
                    "occ_probabilities": occ_probabilities,
                },
            )
        )
    return EvidenceGraph(
        graph_id=graph_id,
        engine=engine,
        layout_hint=LAYOUT_TREE,
        subject_binding=dict(subject_binding),
        paths=tuple(tree_paths),
        certainty=graph_certainty,
        metadata=dict(metadata or {}),
    )


def _not_reached_repr(atom: tuple[Any, ...]) -> str:
    kind = atom[0] if atom else "atom"
    if kind == "pred" and len(atom) > 1:
        return f"{atom[1]} not reached"
    if kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return f"{kind} not reached"
    if kind == "not":
        return "not-body not reached"
    return f"{kind} not reached"


def _probabilities_by_atom(
    result: DiagnosticProbLogResult,
) -> dict[tuple[str, int], list[tuple[str, float, str | None]]]:
    out: dict[tuple[str, int], list[tuple[str, float, str | None]]] = {}
    for row in result.atom_probabilities:
        out.setdefault((row.branch_id, row.atom_index), []).append((row.verdict, row.probability, row.blocked_by))
    return out


def _verdict_for_atom(
    rows: list[tuple[str, float, str | None]] | None,
    *,
    probabilistic: bool,
    holds_certainty: Certainty | None = None,
) -> Holds | Fails | NotReached:
    if not rows:
        raise DiagnosticAssemblyError("diagnostic atom has no verdict rows")
    holds = max((prob for verdict, prob, _blocked in rows if verdict == "holds"), default=0.0)
    if holds > 0.0:
        if holds_certainty is not None:
            return Holds(certainty=holds_certainty)
        return Holds(certainty=BOOLEAN_CERTAINTY)
    fails = max((prob for verdict, prob, _blocked in rows if verdict == "fails"), default=0.0)
    if fails > 0.0:
        return Fails(certainty=BOOLEAN_CERTAINTY)
    blocked = next((blocked for verdict, prob, blocked in rows if verdict == "not_reached" and prob > 0.0), None)
    if blocked is not None:
        return NotReached(blocked_by=blocked)
    raise DiagnosticAssemblyError("diagnostic atom did not produce a supported verdict")


def _input_certainty_for_atom(
    atom: tuple[Any, ...],
    witnesses: tuple[DiagnosticWitnessProbability, ...],
    input_certainty_for_goal: Callable[[str, tuple[Any, ...]], Certainty | None] | None,
) -> Certainty | None:
    if input_certainty_for_goal is None or not witnesses or atom[0] != "pred" or len(atom) < 3:
        return None
    pred_id = str(atom[1])
    witness = witnesses[0]
    return input_certainty_for_goal("edb_fact", ("_", pred_id, *witness.terms))


def _witnesses_by_atom(
    witnesses: tuple[DiagnosticWitnessProbability, ...],
) -> dict[tuple[str, int], list[DiagnosticWitnessProbability]]:
    out: dict[tuple[str, int], list[DiagnosticWitnessProbability]] = {}
    for witness in witnesses:
        out.setdefault((witness.branch_id, witness.atom_index), []).append(witness)
    for rows in out.values():
        rows.sort(key=lambda row: (-row.probability, _witness_sort_key(row.terms)))
    return out


def _envs_for_witnesses(
    atom: tuple[Any, ...],
    witnesses: tuple[DiagnosticWitnessProbability, ...],
    anchor_env: ProbeEnv,
) -> tuple[ProbeEnv, ...]:
    if not witnesses:
        return ()
    terms = _atom_terms(atom)
    envs: list[ProbeEnv] = []
    for witness in witnesses:
        bindings = dict(anchor_env.bindings)
        for term, value in zip(terms, witness.terms, strict=False):
            if isinstance(term, str) and term.startswith("$"):
                bindings[term] = value
        envs.append(ProbeEnv.from_bindings(bindings))
    return tuple(envs)


def _atom_terms(atom: tuple[Any, ...]) -> tuple[Any, ...]:
    if atom[0] == "pred":
        terms = atom[2] if len(atom) > 2 else ()
        return tuple(terms) if isinstance(terms, (list, tuple)) else ()
    if atom[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
        return (atom[1], atom[2])
    return tuple(atom[1:])


def _sorted_envs(envs: list[ProbeEnv]) -> tuple[ProbeEnv, ...]:
    if not envs:
        return ()
    deduped: dict[tuple[tuple[str, str], ...], ProbeEnv] = {}
    for env in envs:
        key = tuple(sorted((str(k), repr(v)) for k, v in env.bindings.items()))
        deduped.setdefault(key, env)
    return tuple(deduped[key] for key in sorted(deduped))


def _merge_envs(left: tuple[ProbeEnv, ...], right: tuple[ProbeEnv, ...]) -> tuple[ProbeEnv, ...]:
    merged = _sorted_envs([*left, *right])
    return tuple(sorted(merged, key=lambda env: (-len(env.bindings), repr(sorted(env.bindings.items())))))


def _display_envs(
    envs: tuple[ProbeEnv, ...],
    *,
    schema_index: object | None,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> tuple[ProbeEnv, ...]:
    out: list[ProbeEnv] = []
    for env in envs:
        bindings = {
            key: _render_term_value(
                BoundVar(name=key, value=value),
                schema_index=schema_index,
                view_facts=view_facts,
                decode_float64=True,
            )
            for key, value in env.bindings.items()
        }
        out.append(ProbeEnv.from_bindings(bindings))
    return tuple(out)


def _witness_sort_key(terms: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(repr(term) for term in terms)


def _probabilistic_certainty(value: float | None, *, probabilistic: bool) -> Certainty | None:
    if not probabilistic:
        return BOOLEAN_CERTAINTY if value is not None else None
    if value is None:
        return None
    return Certainty(value, value, "probabilistic")


__all__ = [
    "DiagnosticAssemblyError",
    "diagnostic_problog_result_to_evidence_graph",
]
