from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field as dc_field
from typing import Any, Literal, TypeAlias
from types import MappingProxyType

from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY, Certainty


TreeStatus = Literal["holds", "fails", "not_reached"]
RuleRole = Literal["head", "body"]
PolicyConditionRole = Literal["left_field", "right_field", "compare"]
LayoutHint = Literal["tree", "timeline"]

LAYOUT_TREE: LayoutHint = "tree"
LAYOUT_TIMELINE: LayoutHint = "timeline"


@dataclass(frozen=True)
class BoundVar:
    name: str
    value: Any = None
    bound_by: str | None = None


@dataclass(frozen=True)
class Const:
    value: Any


@dataclass(frozen=True)
class Source:
    ref: str
    field: str | None = None
    value: Any = None
    meta: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))


@dataclass(frozen=True)
class PortRef:
    rule_occurrence_alias: str
    port_name: str


@dataclass(frozen=True)
class Fact:
    predicate: str
    terms: tuple[BoundVar | Const, ...]


@dataclass(frozen=True)
class Compare:
    op: str
    left: BoundVar | Const
    right: BoundVar | Const


@dataclass(frozen=True)
class Builtin:
    kind: str
    operands: tuple[BoundVar | Const, ...]


@dataclass(frozen=True)
class Aggregate:
    kind: str
    body_terms: tuple[BoundVar | Const, ...] = ()
    head_terms: tuple[BoundVar | Const, ...] = ()


AtomForm: TypeAlias = Fact | Compare | Builtin | Aggregate


@dataclass(frozen=True)
class Holds:
    certainty: Certainty = BOOLEAN_CERTAINTY
    support: tuple[Source, ...] = ()


@dataclass(frozen=True)
class Fails:
    certainty: Certainty = BOOLEAN_CERTAINTY
    support: tuple[Source, ...] = ()


@dataclass(frozen=True)
class NotReached:
    blocked_by: str | None = None


Verdict: TypeAlias = Holds | Fails | NotReached


@dataclass(frozen=True)
class EvidenceAtom:
    form: AtomForm
    verdict: Verdict
    atom_id: str
    repr_text: str | None = None
    negated: bool = False
    timestep: int | None = None


@dataclass(frozen=True)
class EvidenceJoin:
    left: PortRef
    right: PortRef
    status: TreeStatus
    join_id: str


@dataclass(frozen=True)
class EvidencePolicyCondition:
    """One compiler-injected, authored-Policy condition.

    Policy field lookups and comparisons are deliberately not represented as
    ``EvidenceRule`` atoms: they were not authored inside any reusable Rule.
    The wrapped ``EvidenceAtom`` retains the normal typed form, verdict and
    provenance while the surrounding coordinates make its Policy ownership
    explicit and replayable.
    """

    policy_node_id: str
    condition_id: str
    role: PolicyConditionRole
    atom: EvidenceAtom

    def __post_init__(self) -> None:
        if not isinstance(self.policy_node_id, str) or not self.policy_node_id:
            raise ValueError("policy_node_id must be a non-empty string")
        if not isinstance(self.condition_id, str) or not self.condition_id:
            raise ValueError("condition_id must be a non-empty string")
        if self.role not in {"left_field", "right_field", "compare"}:
            raise ValueError("policy condition role is invalid")
        if not isinstance(self.atom, EvidenceAtom):
            raise ValueError("policy condition atom must be EvidenceAtom")

    @property
    def status(self) -> TreeStatus:
        return _verdict_status(self.atom.verdict)


@dataclass(frozen=True)
class EvidenceRule:
    occurrence_alias: str
    rule_id: str
    role: RuleRole
    status: TreeStatus
    repr_text: str | None = None
    ports: Mapping[str, Any] = dc_field(default_factory=dict)
    atoms: tuple[EvidenceAtom, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ports", MappingProxyType(dict(self.ports)))


@dataclass(frozen=True)
class EvidenceTree:
    tree_id: str
    status: TreeStatus
    rules: tuple[EvidenceRule, ...]
    joins: tuple[EvidenceJoin, ...] = ()
    certainty: Certainty | None = BOOLEAN_CERTAINTY
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)
    # Keep this after the pre-F5C positional fields.  Old positional callers
    # therefore retain their ``joins, certainty, metadata`` argument layout.
    policy_conditions: tuple[EvidencePolicyCondition, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.policy_conditions, tuple) or not all(
            isinstance(item, EvidencePolicyCondition) for item in self.policy_conditions
        ):
            raise ValueError("tree.policy_conditions must be an EvidencePolicyCondition tuple")
        coordinates = tuple(
            (item.policy_node_id, item.condition_id, item.role) for item in self.policy_conditions
        )
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("tree.policy_conditions must have unique coordinates")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceTimeline:
    timeline_id: str
    status: TreeStatus
    events: tuple[Any, ...] = ()
    certainty: Certainty | None = None
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str
    layout_hint: LayoutHint
    subject_binding: Mapping[str, Any]
    paths: tuple[EvidenceTree | EvidenceTimeline, ...]
    certainty: Certainty | None = BOOLEAN_CERTAINTY
    metadata: Mapping[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_binding", MappingProxyType(dict(self.subject_binding)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class EvidenceProbeBranchTerminalBindings:
    """Canonical native terminal environments for one probed branch.

    This is deliberately an execution-side inventory rather than EvidenceGraph
    provenance: it records every surviving full environment after the branch's
    final materialized atom.  A consumer that projects away variables can use
    it to detect whether one visible row corresponds to several hidden native
    bindings.  Empty ``environments`` is a valid failed or blocked branch; it
    does not express a negative proof.

    Values retain their native canonical representation (not display-rendered
    values).  The prober supplies them already sorted and de-duplicated; this
    DTO only freezes each mapping so a caller cannot mutate the captured
    inventory through the public result.
    """

    branch_id: str
    environments: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.branch_id, str) or not self.branch_id:
            raise ValueError("branch_id must be a non-empty string")
        if not isinstance(self.environments, tuple):
            raise ValueError("environments must be a tuple")
        frozen: list[Mapping[str, Any]] = []
        for environment in self.environments:
            if not isinstance(environment, Mapping):
                raise ValueError("environment must be a mapping")
            if not all(isinstance(name, str) for name in environment):
                raise ValueError("environment keys must be strings")
            frozen.append(MappingProxyType(dict(sorted(environment.items()))))
        object.__setattr__(self, "environments", tuple(frozen))


@dataclass(frozen=True)
class EvidenceProbeResult:
    paths: tuple[EvidenceTree, ...]
    certainty: Certainty | None = BOOLEAN_CERTAINTY
    terminal_bindings: tuple[EvidenceProbeBranchTerminalBindings, ...] = ()

    def __post_init__(self) -> None:
        # Preserve the historical construction contract when the opt-in
        # inventory is absent.  Only validate the new cross-field invariant.
        if self.terminal_bindings == ():
            return
        if not isinstance(self.terminal_bindings, tuple) or not all(
            isinstance(item, EvidenceProbeBranchTerminalBindings) for item in self.terminal_bindings
        ):
            raise ValueError(
                "terminal_bindings must be an EvidenceProbeBranchTerminalBindings tuple"
            )
        path_ids = tuple(path.tree_id for path in self.paths)
        branch_ids = tuple(item.branch_id for item in self.terminal_bindings)
        if branch_ids != path_ids:
            raise ValueError("terminal_bindings must align with paths by branch_id")


def evidence_graph_to_dict(graph: EvidenceGraph) -> dict[str, Any]:
    if not isinstance(graph, EvidenceGraph):
        raise ValueError("graph must be EvidenceGraph")
    return {
        "graph_id": graph.graph_id,
        "engine": graph.engine,
        "layout_hint": graph.layout_hint,
        "subject_binding": _to_jsonable(graph.subject_binding),
        "paths": [_path_to_dict(path) for path in graph.paths],
        "certainty": _certainty_to_dict(graph.certainty),
        "metadata": _to_jsonable(graph.metadata),
    }


def evidence_graph_from_dict(row: Mapping[str, Any]) -> EvidenceGraph:
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    raw_paths = row.get("paths")
    if not isinstance(raw_paths, list):
        raise ValueError("row.paths must be list")
    return EvidenceGraph(
        graph_id=_require_str(row.get("graph_id"), "row.graph_id"),
        engine=_require_str(row.get("engine"), "row.engine"),
        layout_hint=_require_layout_hint(row.get("layout_hint")),
        subject_binding=_require_mapping(row.get("subject_binding", {}), "row.subject_binding"),
        paths=tuple(_path_from_dict(path) for path in raw_paths),
        certainty=_certainty_from_dict(row.get("certainty")),
        metadata=_require_mapping(row.get("metadata", {}), "row.metadata"),
    )


def _path_to_dict(path: EvidenceTree | EvidenceTimeline) -> dict[str, Any]:
    if isinstance(path, EvidenceTree):
        row = {
            "kind": "tree",
            "tree_id": path.tree_id,
            "status": path.status,
            "rules": [_rule_to_dict(rule) for rule in path.rules],
            "joins": [_join_to_dict(join) for join in path.joins],
            "certainty": _certainty_to_dict(path.certainty),
            "metadata": _to_jsonable(path.metadata),
        }
        # Preserve the pre-F5C JSON shape when a tree has no Policy-owned
        # conditions.  Readers nevertheless accept the field when present.
        if path.policy_conditions:
            row["policy_conditions"] = [
                _policy_condition_to_dict(condition) for condition in path.policy_conditions
            ]
        return row
    if isinstance(path, EvidenceTimeline):
        return {
            "kind": "timeline",
            "timeline_id": path.timeline_id,
            "status": path.status,
            "events": [
                _atom_to_dict(event) for event in path.events if isinstance(event, EvidenceAtom)
            ],
            "certainty": _certainty_to_dict(path.certainty),
            "metadata": _to_jsonable(path.metadata),
        }
    raise ValueError("path must be EvidenceTree or EvidenceTimeline")


def _path_from_dict(row: Any) -> EvidenceTree | EvidenceTimeline:
    if not isinstance(row, Mapping):
        raise ValueError("path row must be Mapping[str, Any]")
    kind = row.get("kind")
    if kind == "tree":
        raw_rules = row.get("rules")
        raw_joins = row.get("joins", [])
        raw_policy_conditions = row.get("policy_conditions", [])
        if not isinstance(raw_rules, list):
            raise ValueError("tree.rules must be list")
        if not isinstance(raw_joins, list):
            raise ValueError("tree.joins must be list")
        if not isinstance(raw_policy_conditions, list):
            raise ValueError("tree.policy_conditions must be list")
        return EvidenceTree(
            tree_id=_require_str(row.get("tree_id"), "tree.tree_id"),
            status=_require_tree_status(row.get("status"), "tree.status"),
            rules=tuple(_rule_from_dict(rule) for rule in raw_rules),
            joins=tuple(_join_from_dict(join) for join in raw_joins),
            policy_conditions=tuple(
                _policy_condition_from_dict(condition) for condition in raw_policy_conditions
            ),
            certainty=_certainty_from_dict(row.get("certainty")),
            metadata=_require_mapping(row.get("metadata", {}), "tree.metadata"),
        )
    if kind == "timeline":
        raw_events = row.get("events", [])
        if not isinstance(raw_events, list):
            raise ValueError("timeline.events must be list")
        return EvidenceTimeline(
            timeline_id=_require_str(row.get("timeline_id"), "timeline.timeline_id"),
            status=_require_tree_status(row.get("status"), "timeline.status"),
            events=tuple(_atom_from_dict(event) for event in raw_events),
            certainty=_certainty_from_dict(row.get("certainty")),
            metadata=_require_mapping(row.get("metadata", {}), "timeline.metadata"),
        )
    raise ValueError("path.kind must be 'tree' or 'timeline'")


def _rule_to_dict(rule: EvidenceRule) -> dict[str, Any]:
    return {
        "occurrence_alias": rule.occurrence_alias,
        "rule_id": rule.rule_id,
        "role": rule.role,
        "status": rule.status,
        "repr_text": rule.repr_text,
        "ports": _to_jsonable(rule.ports),
        "atoms": [_atom_to_dict(atom) for atom in rule.atoms],
    }


def _rule_from_dict(row: Any) -> EvidenceRule:
    if not isinstance(row, Mapping):
        raise ValueError("rule row must be Mapping[str, Any]")
    raw_atoms = row.get("atoms", [])
    if not isinstance(raw_atoms, list):
        raise ValueError("rule.atoms must be list")
    return EvidenceRule(
        occurrence_alias=_require_str(row.get("occurrence_alias"), "rule.occurrence_alias"),
        rule_id=_require_str(row.get("rule_id"), "rule.rule_id"),
        role=_require_role(row.get("role")),
        status=_require_tree_status(row.get("status"), "rule.status"),
        repr_text=_optional_str(row.get("repr_text"), "rule.repr_text"),
        ports=_require_mapping(row.get("ports", {}), "rule.ports"),
        atoms=tuple(_atom_from_dict(atom) for atom in raw_atoms),
    )


def _join_to_dict(join: EvidenceJoin) -> dict[str, Any]:
    return {
        "left": _port_ref_to_dict(join.left),
        "right": _port_ref_to_dict(join.right),
        "status": join.status,
        "join_id": join.join_id,
    }


def _join_from_dict(row: Any) -> EvidenceJoin:
    if not isinstance(row, Mapping):
        raise ValueError("join row must be Mapping[str, Any]")
    return EvidenceJoin(
        left=_port_ref_from_dict(row.get("left")),
        right=_port_ref_from_dict(row.get("right")),
        status=_require_tree_status(row.get("status"), "join.status"),
        join_id=_require_str(row.get("join_id"), "join.join_id"),
    )


def _policy_condition_to_dict(condition: EvidencePolicyCondition) -> dict[str, Any]:
    return {
        "policy_node_id": condition.policy_node_id,
        "condition_id": condition.condition_id,
        "role": condition.role,
        "atom": _atom_to_dict(condition.atom),
    }


def _policy_condition_from_dict(row: Any) -> EvidencePolicyCondition:
    if not isinstance(row, Mapping):
        raise ValueError("policy condition row must be Mapping[str, Any]")
    return EvidencePolicyCondition(
        policy_node_id=_require_str(row.get("policy_node_id"), "policy_condition.policy_node_id"),
        condition_id=_require_str(row.get("condition_id"), "policy_condition.condition_id"),
        role=_require_policy_condition_role(row.get("role")),
        atom=_atom_from_dict(row.get("atom")),
    )


def _port_ref_to_dict(port: PortRef) -> dict[str, Any]:
    return {"rule_occurrence_alias": port.rule_occurrence_alias, "port_name": port.port_name}


def _port_ref_from_dict(row: Any) -> PortRef:
    if not isinstance(row, Mapping):
        raise ValueError("port ref row must be Mapping[str, Any]")
    return PortRef(
        rule_occurrence_alias=_require_str(
            row.get("rule_occurrence_alias"), "port.rule_occurrence_alias"
        ),
        port_name=_require_str(row.get("port_name"), "port.port_name"),
    )


def _atom_to_dict(atom: EvidenceAtom) -> dict[str, Any]:
    return {
        "form": _form_to_dict(atom.form),
        "verdict": _verdict_to_dict(atom.verdict),
        "atom_id": atom.atom_id,
        "repr_text": atom.repr_text,
        "negated": atom.negated,
        "timestep": atom.timestep,
    }


def _atom_from_dict(row: Any) -> EvidenceAtom:
    if not isinstance(row, Mapping):
        raise ValueError("atom row must be Mapping[str, Any]")
    return EvidenceAtom(
        form=_form_from_dict(row.get("form")),
        verdict=_verdict_from_dict(row.get("verdict")),
        atom_id=_require_str(row.get("atom_id"), "atom.atom_id"),
        repr_text=_optional_str(row.get("repr_text"), "atom.repr_text"),
        negated=bool(row.get("negated", False)),
        timestep=_optional_int(row.get("timestep"), "atom.timestep"),
    )


def _form_to_dict(form: AtomForm) -> dict[str, Any]:
    if isinstance(form, Fact):
        return {
            "kind": "fact",
            "predicate": form.predicate,
            "terms": [_term_to_dict(term) for term in form.terms],
        }
    if isinstance(form, Compare):
        return {
            "kind": "compare",
            "op": form.op,
            "left": _term_to_dict(form.left),
            "right": _term_to_dict(form.right),
        }
    if isinstance(form, Builtin):
        return {
            "kind": "builtin",
            "builtin_kind": form.kind,
            "operands": [_term_to_dict(term) for term in form.operands],
        }
    if isinstance(form, Aggregate):
        return {
            "kind": "aggregate",
            "aggregate_kind": form.kind,
            "body_terms": [_term_to_dict(term) for term in form.body_terms],
            "head_terms": [_term_to_dict(term) for term in form.head_terms],
        }
    raise ValueError("unsupported atom form")


def _form_from_dict(row: Any) -> AtomForm:
    if not isinstance(row, Mapping):
        raise ValueError("atom form row must be Mapping[str, Any]")
    kind = row.get("kind")
    if kind == "fact":
        return Fact(
            predicate=_require_str(row.get("predicate"), "fact.predicate"),
            terms=tuple(
                _term_from_dict(term) for term in _require_list(row.get("terms", []), "fact.terms")
            ),
        )
    if kind == "compare":
        return Compare(
            op=_require_str(row.get("op"), "compare.op"),
            left=_term_from_dict(row.get("left")),
            right=_term_from_dict(row.get("right")),
        )
    if kind == "builtin":
        return Builtin(
            kind=_require_str(row.get("builtin_kind"), "builtin.kind"),
            operands=tuple(
                _term_from_dict(term)
                for term in _require_list(row.get("operands", []), "builtin.operands")
            ),
        )
    if kind == "aggregate":
        return Aggregate(
            kind=_require_str(row.get("aggregate_kind"), "aggregate.kind"),
            body_terms=tuple(
                _term_from_dict(term)
                for term in _require_list(row.get("body_terms", []), "aggregate.body_terms")
            ),
            head_terms=tuple(
                _term_from_dict(term)
                for term in _require_list(row.get("head_terms", []), "aggregate.head_terms")
            ),
        )
    raise ValueError("atom form kind must be fact, compare, builtin, or aggregate")


def _term_to_dict(term: BoundVar | Const) -> dict[str, Any]:
    if isinstance(term, BoundVar):
        return {
            "kind": "bound_var",
            "name": term.name,
            "value": _to_jsonable(term.value),
            "bound_by": term.bound_by,
        }
    if isinstance(term, Const):
        return {"kind": "const", "value": _to_jsonable(term.value)}
    raise ValueError("term must be BoundVar or Const")


def _term_from_dict(row: Any) -> BoundVar | Const:
    if not isinstance(row, Mapping):
        raise ValueError("term row must be Mapping[str, Any]")
    kind = row.get("kind")
    if kind == "bound_var":
        return BoundVar(
            name=_require_str(row.get("name"), "term.name"),
            value=_from_jsonable(row.get("value")),
            bound_by=_optional_str(row.get("bound_by"), "term.bound_by"),
        )
    if kind == "const":
        return Const(_from_jsonable(row.get("value")))
    raise ValueError("term.kind must be 'bound_var' or 'const'")


def _verdict_to_dict(verdict: Verdict) -> dict[str, Any]:
    if isinstance(verdict, Holds):
        return {
            "kind": "holds",
            "certainty": _certainty_to_dict(verdict.certainty),
            "support": [_source_to_dict(source) for source in verdict.support],
        }
    if isinstance(verdict, Fails):
        return {
            "kind": "fails",
            "certainty": _certainty_to_dict(verdict.certainty),
            "support": [_source_to_dict(source) for source in verdict.support],
        }
    if isinstance(verdict, NotReached):
        return {"kind": "not_reached", "blocked_by": verdict.blocked_by}
    raise ValueError("unsupported verdict")


def _verdict_from_dict(row: Any) -> Verdict:
    if not isinstance(row, Mapping):
        raise ValueError("verdict row must be Mapping[str, Any]")
    kind = row.get("kind")
    if kind == "holds":
        return Holds(
            certainty=_certainty_from_dict(row.get("certainty")) or BOOLEAN_CERTAINTY,
            support=tuple(
                _source_from_dict(source)
                for source in _require_list(row.get("support", []), "verdict.support")
            ),
        )
    if kind == "fails":
        return Fails(
            certainty=_certainty_from_dict(row.get("certainty")) or BOOLEAN_CERTAINTY,
            support=tuple(
                _source_from_dict(source)
                for source in _require_list(row.get("support", []), "verdict.support")
            ),
        )
    if kind == "not_reached":
        return NotReached(blocked_by=_optional_str(row.get("blocked_by"), "verdict.blocked_by"))
    raise ValueError("verdict.kind must be holds, fails, or not_reached")


def _source_to_dict(source: Source) -> dict[str, Any]:
    return {
        "ref": source.ref,
        "field": source.field,
        "value": _to_jsonable(source.value),
        "meta": _to_jsonable(source.meta),
    }


def _source_from_dict(row: Any) -> Source:
    if not isinstance(row, Mapping):
        raise ValueError("source row must be Mapping[str, Any]")
    return Source(
        ref=_require_str(row.get("ref"), "source.ref"),
        field=_optional_str(row.get("field"), "source.field"),
        value=_from_jsonable(row.get("value")),
        meta=_require_mapping(row.get("meta", {}), "source.meta"),
    )


def _certainty_to_dict(certainty: Certainty | None) -> dict[str, Any] | None:
    if certainty is None:
        return None
    return {"lo": certainty.lo, "hi": certainty.hi, "kind": certainty.kind}


def _certainty_from_dict(row: Any) -> Certainty | None:
    if row is None:
        return None
    if not isinstance(row, Mapping):
        raise ValueError("certainty row must be Mapping[str, Any] or None")
    return Certainty(
        lo=_require_float(row.get("lo"), "certainty.lo"),
        hi=_require_float(row.get("hi"), "certainty.hi"),
        kind=_require_certainty_kind(row.get("kind")),
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_from_jsonable(item) for item in value)
    if isinstance(value, Mapping):
        return {str(key): _from_jsonable(item) for key, item in value.items()}
    return value


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be Mapping[str, Any]")
    return _from_jsonable(value)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be list")
    return value


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be non-empty string")
    return value


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, field_name)


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be int or None")
    return value


def _require_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be number")
    return float(value)


def _require_tree_status(value: Any, field_name: str) -> TreeStatus:
    if value not in {"holds", "fails", "not_reached"}:
        raise ValueError(f"{field_name} must be holds, fails, or not_reached")
    return value


def _require_role(value: Any) -> RuleRole:
    if value not in {"head", "body"}:
        raise ValueError("rule.role must be head or body")
    return value


def _require_policy_condition_role(value: Any) -> PolicyConditionRole:
    if value not in {"left_field", "right_field", "compare"}:
        raise ValueError("policy condition role must be left_field, right_field, or compare")
    return value


def _verdict_status(verdict: Verdict) -> TreeStatus:
    if isinstance(verdict, Holds):
        return "holds"
    if isinstance(verdict, Fails):
        return "fails"
    return "not_reached"


def _require_layout_hint(value: Any) -> LayoutHint:
    if value not in {LAYOUT_TREE, LAYOUT_TIMELINE}:
        raise ValueError("row.layout_hint must be tree or timeline")
    return value


def _require_certainty_kind(value: Any) -> Literal["boolean", "probabilistic", "possibilistic"]:
    if value not in {"boolean", "probabilistic", "possibilistic"}:
        raise ValueError("certainty.kind must be boolean, probabilistic, or possibilistic")
    return value


__all__ = [
    "Aggregate",
    "AtomForm",
    "BOOLEAN_CERTAINTY",
    "BoundVar",
    "Builtin",
    "Certainty",
    "Compare",
    "Const",
    "EvidenceAtom",
    "EvidenceGraph",
    "EvidenceJoin",
    "EvidencePolicyCondition",
    "EvidenceProbeBranchTerminalBindings",
    "EvidenceProbeResult",
    "EvidenceRule",
    "EvidenceTimeline",
    "EvidenceTree",
    "Fact",
    "Fails",
    "Holds",
    "LAYOUT_TIMELINE",
    "LAYOUT_TREE",
    "LayoutHint",
    "NotReached",
    "PortRef",
    "PolicyConditionRole",
    "RuleRole",
    "Source",
    "TreeStatus",
    "Verdict",
    "evidence_graph_from_dict",
    "evidence_graph_to_dict",
]
