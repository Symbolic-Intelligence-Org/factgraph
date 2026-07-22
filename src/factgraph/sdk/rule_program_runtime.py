"""Read-only evaluation of selected Horn programs on one FactGraph ledger."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from factgraph.application.protocol import Rule as ApplicationRule
from factgraph.application.protocol.evaluate_result import (
    rule_set_digest_for_entries,
    view_snapshot_digest_for_parts,
)
from factgraph.application.protocol.rule_expr import _RuleExpr
from factgraph.application.protocol.rule_expr_lowering import (
    _lower_application_rule,
    _lower_rule_expr,
    _materialize_native_derivation_plan,
    _validate_rule_expr_head_foundation,
)
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.store._support import ProjectedFact, compute_support_digest
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_case_index,
)
from factgraph.core.store.premise_filter import premise_scoped_ledger
from factgraph.core.view.projector import project_view_facts_with_witness

from .errors import SDKStoreError
from .rule_program import (
    EvaluationPremiseScope,
    RuleProgram,
    RuleProgramGoal,
    RuleProgramResult,
)

_INTERNAL_VERSION = "1.0"
_UNION_PREFIX = "__factgraph_program_union__"


def evaluate_rule_program(
    sdk: Any,
    program: RuleProgram,
    goal: RuleProgramGoal,
    *,
    engine: str = "native",
    scope: EvaluationPremiseScope | None = None,
) -> RuleProgramResult:
    """Evaluate ``goal`` from ``program`` without copying or writing the ledger."""

    if not isinstance(program, RuleProgram):
        raise SDKStoreError("evaluate_program program must be RuleProgram")
    if not isinstance(goal, RuleProgramGoal):
        raise SDKStoreError("evaluate_program goal must be RuleProgramGoal")
    if engine != "native":
        raise SDKStoreError("evaluate_program currently supports engine='native'")
    if scope is not None and not isinstance(scope, EvaluationPremiseScope):
        raise SDKStoreError("evaluate_program scope must be EvaluationPremiseScope or None")

    compiled = [_compile_clause(clause) for clause in program.clauses]
    produced: dict[str, list[tuple[Any, Any]]] = {}
    for clause, plan in zip(program.clauses, compiled, strict=True):
        head = plan.heads[0]
        produced.setdefault(head.target_pred_id, []).append((clause, plan))

    goal_producers = produced.get(goal.predicate)
    if not goal_producers:
        raise SDKStoreError(
            f"evaluate_program goal predicate {goal.predicate!r} has no producer clause"
        )
    arities = {len(plan.heads[0].head_var_names) for _clause, plan in goal_producers}
    if arities != {len(goal.terms)}:
        raise SDKStoreError(
            f"evaluate_program goal arity does not match {goal.predicate!r}: "
            f"goal={len(goal.terms)}, producers={sorted(arities)}"
        )

    program_token = _program_token(program, compiled)
    resolver_by_pred = {
        pred_id: _resolver_coordinate(program_token, pred_id, rows)
        for pred_id, rows in produced.items()
    }
    registry = RuleRegistry()

    clause_specs_by_pred: dict[str, list[RuleSpec]] = {}
    for clause, plan in zip(program.clauses, compiled, strict=True):
        head = plan.heads[0]
        rewritten = _rewrite_program_predicates(
            list(plan.body_ir),
            resolver_by_pred=resolver_by_pred,
        )
        spec = RuleSpec(
            rule_id=clause.rule_id,
            version=clause.version,
            select_vars=list(head.head_var_names),
            where=rewritten,
            expose=True,
        )
        registry.register(spec)
        clause_specs_by_pred.setdefault(head.target_pred_id, []).append(spec)

    for pred_id, specs in clause_specs_by_pred.items():
        resolver_id, resolver_version, resolver_arity = resolver_by_pred[pred_id]
        if len(specs) == 1:
            continue
        canonical_vars = [f"$arg{index}" for index in range(resolver_arity)]
        branches = [
            [("ruleref", spec.rule_id, spec.version, list(canonical_vars))]
            for spec in specs
        ]
        registry.register(
            RuleSpec(
                rule_id=resolver_id,
                version=resolver_version,
                select_vars=canonical_vars,
                where=branches,
                expose=True,
            )
        )

    exclusions, allowances, blocks = _resolved_scope(sdk, scope)
    scoped_ledger = premise_scoped_ledger(
        sdk.store.ledger,
        exclusions,
        allowances,
        blocks,
    )
    witness_facts = project_view_facts_with_witness(scoped_ledger, sdk.store.schema_ir)
    _merge_program_facts(sdk, witness_facts, program)
    view_facts = {
        pred_id: [row.fact_tuple for row in rows]
        for pred_id, rows in witness_facts.items()
    }
    view_snapshot_digest = _view_snapshot_digest(sdk, witness_facts)
    premise_scope_digest = _scope_digest(exclusions, allowances, blocks)

    resolver_id, resolver_version, _arity = resolver_by_pred[goal.predicate]
    root_where = [("ruleref", resolver_id, resolver_version, list(goal.terms))]
    evaluation = evaluate_native_where(
        view_facts,
        root_where,
        registry=registry,
        witness_facts=witness_facts,
        remember_support_artifact=sdk.store._remember_support_artifact,
    )
    support_digest: str | None = None
    if evaluation.bindings:
        binding = sorted(
            evaluation.bindings,
            key=lambda row: tuple(sorted((str(key), repr(value)) for key, value in row.items())),
        )[0]
        case_index = find_winning_case_index(
            where=root_where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=evaluation.rule_ref_resolutions,
        )
        edges = derive_rule_ref_edges_for_binding(
            where=root_where,
            binding=binding,
            rule_ref_resolutions=evaluation.rule_ref_resolutions,
            selected_case_index=case_index,
        )
        receipt = build_support_artifact_for_binding(
            where=root_where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_case_index=case_index,
            rule_ref_edges=edges,
        )
        support_digest = compute_support_digest(receipt)
        sdk.store._remember_support_artifact(support_digest, receipt)

    digest_entries = [
        (clause.rule_id, _clause_digest(clause, plan))
        for clause, plan in zip(program.clauses, compiled, strict=True)
    ]
    digest_entries.extend(
        (f"@program-fact:{fact.fact_id}", _program_fact_digest(fact))
        for fact in program.facts
    )
    rule_set_digest = rule_set_digest_for_entries(digest_entries)
    effective_rule_ids = tuple(sorted(clause.rule_id for clause in program.clauses))
    matched_rule_ids = _matched_rule_ids(
        sdk,
        support_digest,
        effective_rule_ids=frozenset(effective_rule_ids),
    )
    return RuleProgramResult(
        entailed=support_digest is not None,
        goal=goal,
        engine=engine,
        evaluated_at=datetime.now(timezone.utc),
        effective_rule_ids=effective_rule_ids,
        matched_rule_ids=matched_rule_ids,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        premise_scope_digest=premise_scope_digest,
        program_facts=program.facts,
        support_digest=support_digest,
        _support_lookup=sdk.store.explain_support,
    )


def _compile_clause(clause: Any) -> Any:
    if not isinstance(clause.head, ApplicationRule):
        raise SDKStoreError(
            f"RuleProgramClause {clause.rule_id!r} head must be an application Rule"
        )
    if isinstance(clause.body, ApplicationRule):
        # ``Rule.id`` doubles as the implicit occurrence alias in the RuleExpr
        # application protocol, whose alias grammar intentionally only admits
        # identifiers.  A RuleProgramClause has its own unrestricted, durable
        # policy identity (``clause.rule_id``), so use a compiler-local alias
        # instead of accidentally imposing the occurrence-alias grammar on
        # ontology rule ids such as ``payment.approval.standard``.
        body = replace(clause.body, id="program_body")
        lowering = _lower_application_rule(body, head=clause.head)
    elif isinstance(clause.body, _RuleExpr):
        lowering = _lower_rule_expr(clause.body, head=clause.head)
    else:
        raise SDKStoreError(
            f"RuleProgramClause {clause.rule_id!r} body must be an application Rule or RuleExpr"
        )
    _validate_rule_expr_head_foundation(lowering)
    plan, _traces = _materialize_native_derivation_plan(lowering)
    if len(plan.heads) != 1:
        raise SDKStoreError(f"RuleProgramClause {clause.rule_id!r} must have exactly one head")
    return plan


def _program_token(program: RuleProgram, compiled: list[Any]) -> str:
    clauses = tuple(
        (
            clause.rule_id,
            clause.version,
            _clause_digest(clause, plan),
        )
        for clause, plan in zip(program.clauses, compiled, strict=True)
    )
    facts = tuple(
        (fact.fact_id, _program_fact_digest(fact))
        for fact in sorted(program.facts, key=lambda row: row.fact_id)
    )
    payload = (clauses, facts)
    return sha256_hex(canonical_bytes_tup_v1([("string", repr(payload))]))[:20]


def _clause_digest(clause: Any, plan: Any) -> str:
    payload = (
        clause.rule_id,
        clause.version,
        tuple(repr(atom) for atom in plan.body_ir),
        tuple(
            (head.target_pred_id, tuple(head.head_var_names))
            for head in plan.heads
        ),
    )
    return sha256_hex(canonical_bytes_tup_v1([("string", repr(payload))]))


def _program_fact_digest(fact: Any) -> str:
    payload = (
        fact.fact_id,
        fact.predicate,
        tuple(repr(term) for term in fact.terms),
        tuple(sorted((str(key), repr(value)) for key, value in fact.provenance.items())),
    )
    return sha256_hex(canonical_bytes_tup_v1([("string", repr(payload))]))


def _merge_program_facts(
    sdk: Any,
    witness_facts: dict[str, list[ProjectedFact]],
    program: RuleProgram,
) -> None:
    """Overlay explicit program axioms on the premise-scoped customer view."""

    schema_arities = {
        row.get("pred_id"): row.get("arity")
        for row in sdk.store.schema_ir.get("predicates", [])
        if isinstance(row, dict)
    }
    for fact in program.facts:
        arity = schema_arities.get(fact.predicate)
        if arity is None:
            raise SDKStoreError(
                f"RuleProgramFact {fact.fact_id!r} uses unknown predicate {fact.predicate!r}"
            )
        if arity != len(fact.terms):
            raise SDKStoreError(
                f"RuleProgramFact {fact.fact_id!r} arity mismatch for "
                f"{fact.predicate!r}: expected {arity}, got {len(fact.terms)}"
            )
        rows = witness_facts.setdefault(fact.predicate, [])
        if any(row.fact_tuple == fact.terms for row in rows):
            continue
        rows.append(ProjectedFact(asrt_id=fact.fact_id, fact_tuple=fact.terms))
        rows.sort(key=lambda row: tuple(str(part) for part in row.fact_tuple))


def _resolver_coordinate(
    program_token: str,
    pred_id: str,
    rows: list[tuple[Any, Any]],
) -> tuple[str, str, int]:
    arities = {len(plan.heads[0].head_var_names) for _clause, plan in rows}
    if len(arities) != 1:
        raise SDKStoreError(
            f"RuleProgram producer arity mismatch for predicate {pred_id!r}: {sorted(arities)}"
        )
    if len(rows) == 1:
        clause = rows[0][0]
        return clause.rule_id, clause.version, next(iter(arities))
    safe_pred = "".join(ch if ch.isalnum() else "_" for ch in pred_id)
    return f"{_UNION_PREFIX}{program_token}__{safe_pred}", _INTERNAL_VERSION, next(iter(arities))


def _rewrite_program_predicates(
    where: list[Any],
    *,
    resolver_by_pred: dict[str, tuple[str, str, int]],
    nested: bool = False,
) -> list[Any]:
    """Replace positive uses of program-produced predicates with RuleRefs."""

    if all(isinstance(item, list) for item in where):
        return [
            _rewrite_program_predicates(branch, resolver_by_pred=resolver_by_pred, nested=nested)
            for branch in where
        ]
    out: list[Any] = []
    for atom in where:
        if not isinstance(atom, tuple) or not atom:
            out.append(atom)
            continue
        kind = atom[0]
        if kind == "pred" and len(atom) == 3 and atom[1] in resolver_by_pred:
            if nested:
                raise SDKStoreError(
                    "RuleProgram derived-predicate dependencies inside not/aggregate "
                    "require a stratified program evaluator"
                )
            rule_id, version, arity = resolver_by_pred[atom[1]]
            terms = atom[2]
            if not isinstance(terms, list) or len(terms) != arity:
                raise SDKStoreError(
                    f"RuleProgram dependency arity mismatch for predicate {atom[1]!r}"
                )
            out.append(("ruleref", rule_id, version, list(terms)))
            continue
        if kind == "not" and len(atom) == 2 and isinstance(atom[1], list):
            out.append(
                (
                    "not",
                    _rewrite_program_predicates(
                        atom[1], resolver_by_pred=resolver_by_pred, nested=True
                    ),
                )
            )
            continue
        if kind == "aggregate" and len(atom) >= 4 and isinstance(atom[3], list):
            copied = list(atom)
            copied[3] = _rewrite_program_predicates(
                atom[3], resolver_by_pred=resolver_by_pred, nested=True
            )
            out.append(tuple(copied))
            continue
        out.append(atom)
    return out


def _resolved_scope(sdk: Any, scope: EvaluationPremiseScope | None) -> tuple[Any, Any, Any]:
    if scope is None:
        return (
            sdk.store.premise_exclusions,
            sdk.store.premise_allowances,
            sdk.store.premise_blocks,
        )
    return (
        sdk.store.premise_exclusions if scope.exclusions is None else scope.exclusions,
        sdk.store.premise_allowances if scope.allowances is None else scope.allowances,
        sdk.store.premise_blocks if scope.blocks is None else scope.blocks,
    )


def _scope_digest(exclusions: Any, allowances: Any, blocks: Any) -> str:
    payload = (
        tuple(sorted(repr(item) for item in exclusions)),
        tuple(sorted(repr(item) for item in allowances)),
        tuple(sorted(repr(item) for item in blocks)),
    )
    return sha256_token(canonical_bytes_tup_v1([("string", repr(payload))]))


def _view_snapshot_digest(sdk: Any, witness_facts: dict[str, list[Any]]) -> str:
    ledger = sdk.store.ledger
    schema_token = sdk._schema_digest
    db_id = ledger.get_ledger_meta("db_id")
    if db_id is None:
        db_id = "mem:" + sha256_hex(
            canonical_bytes_tup_v1([("string", schema_token)])
        )
    base_tx_id = ledger.get_ledger_meta("head_tx_id")
    if base_tx_id is None:
        base_payload = (
            tuple(
                (claim.asrt_id, claim.pred_id, claim.e_ref, tuple(claim.rest_terms))
                for claim in sorted(ledger.find_claims(), key=lambda row: row.asrt_id)
            ),
            tuple(
                (row.revoker_asrt_id, row.revoked_asrt_id)
                for row in sorted(
                    ledger.revokes,
                    key=lambda item: (item.revoker_asrt_id, item.revoked_asrt_id),
                )
            ),
        )
        base_tx_id = "tx:" + sha256_hex(
            canonical_bytes_tup_v1([("string", repr(base_payload))])
        )
    assertion_ids = tuple(
        sorted(
            {
                _view_assertion_token(row.asrt_id)
                for rows in witness_facts.values()
                for row in rows
            }
        )
    )
    return view_snapshot_digest_for_parts(
        db_id=db_id,
        base_tx_id=base_tx_id,
        schema_digest=schema_token,
        asrt_ids=assertion_ids,
    )


def _view_assertion_token(asrt_id: str) -> str:
    if asrt_id.startswith("asrt:") and len(asrt_id) > len("asrt:"):
        return asrt_id
    return "asrt:" + sha256_hex(
        canonical_bytes_tup_v1([("string", str(asrt_id))])
    )


def _matched_rule_ids(
    sdk: Any,
    support_digest: str | None,
    *,
    effective_rule_ids: frozenset[str],
) -> tuple[str, ...]:
    if support_digest is None:
        return ()
    found: set[str] = set()
    seen: set[str] = set()

    def walk(digest: str) -> None:
        if digest in seen:
            return
        seen.add(digest)
        receipt = sdk.store.explain_support(digest) or {}
        for edge in receipt.get("rule_ref_edges", []) or []:
            rule_id = edge.get("rule_ref_id")
            if rule_id in effective_rule_ids:
                found.add(rule_id)
            child = edge.get("child_support_digest")
            if isinstance(child, str) and child:
                walk(child)

    walk(support_digest)
    return tuple(sorted(found))


__all__ = ["evaluate_rule_program"]
