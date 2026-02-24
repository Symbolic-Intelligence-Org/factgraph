from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias


class WhereASTError(Exception):
    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = path


@dataclass(frozen=True)
class Origin:
    source: Literal["sdk", "authoring", "raw_ir"]
    path: str | None = None


@dataclass(frozen=True)
class Var:
    name: str
    origin: Origin | None = None


@dataclass(frozen=True)
class Const:
    value: Any
    origin: Origin | None = None


Term: TypeAlias = Var | Const


@dataclass(frozen=True)
class PredAtom:
    pred_id: str
    terms: list[Term]
    origin: Origin | None = None


@dataclass(frozen=True)
class RuleRefAtom:
    rule_id: str
    version: str | None
    terms: list[Term]
    origin: Origin | None = None


@dataclass(frozen=True)
class CmpAtom:
    op: str
    lhs: Term
    rhs: Term
    origin: Origin | None = None


@dataclass(frozen=True)
class InAtom:
    var: Var
    values: list[Const]
    origin: Origin | None = None


@dataclass(frozen=True)
class BuiltinAtom:
    op: str
    args: list[Term]
    origin: Origin | None = None


@dataclass(frozen=True)
class NotAtom:
    body: "WhereExpr"
    origin: Origin | None = None


Atom: TypeAlias = PredAtom | RuleRefAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom


@dataclass(frozen=True)
class AndExpr:
    atoms: list[Atom]
    origin: Origin | None = None


@dataclass(frozen=True)
class OrExpr:
    branches: list[AndExpr]
    origin: Origin | None = None


WhereExpr: TypeAlias = AndExpr | OrExpr


_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}
_BUILTIN_TAGS = {"add", "sub", "neg", "addc", "mulc"}


def parse_where_ir_to_ast(where_ir: Any) -> WhereExpr:
    return _parse_where_expr(where_ir, path="$.where")


def lower_ast_to_where_ir(expr: WhereExpr) -> list[Any]:
    if isinstance(expr, AndExpr):
        return [_lower_atom(atom) for atom in expr.atoms]
    if isinstance(expr, OrExpr):
        return [[_lower_atom(atom) for atom in branch.atoms] for branch in expr.branches]
    raise WhereASTError(f"unsupported where expr node: {type(expr).__name__}")


def _parse_where_expr(raw: Any, *, path: str) -> WhereExpr:
    if not isinstance(raw, list) or not raw:
        raise WhereASTError("where/not body must be non-empty list", path=path)

    if all(isinstance(item, list) for item in raw):
        branches: list[AndExpr] = []
        for idx, branch in enumerate(raw):
            branch_path = f"{path}[{idx}]"
            if not isinstance(branch, list) or not branch:
                raise WhereASTError("OR branch must be non-empty list", path=branch_path)
            branches.append(_parse_and_expr(branch, path=branch_path))
        return OrExpr(
            branches=branches,
            origin=Origin(source="raw_ir", path=path),
        )

    return _parse_and_expr(raw, path=path)


def _parse_and_expr(raw: list[Any], *, path: str) -> AndExpr:
    atoms: list[Atom] = []
    for idx, atom_ir in enumerate(raw):
        atoms.append(_parse_atom(atom_ir, path=f"{path}[{idx}]"))
    if not atoms:
        raise WhereASTError("AND body must be non-empty", path=path)
    return AndExpr(
        atoms=atoms,
        origin=Origin(source="raw_ir", path=path),
    )


def _parse_atom(raw: Any, *, path: str) -> Atom:
    if not (isinstance(raw, tuple) and raw and isinstance(raw[0], str)):
        raise WhereASTError("atom must be tuple(tag, ...)", path=path)
    tag = raw[0]

    if tag == "pred":
        if len(raw) != 3:
            raise WhereASTError("pred atom must be ('pred', pred_id, [terms...])", path=path)
        _, pred_id, terms = raw
        if not isinstance(terms, list):
            raise WhereASTError("pred atom terms must be list", path=path)
        return PredAtom(
            pred_id=pred_id,
            terms=[_parse_term(t, path=f"{path}[2][{idx}]") for idx, t in enumerate(terms)],
            origin=Origin(source="raw_ir", path=path),
        )

    if tag == "ruleref":
        if len(raw) != 4:
            raise WhereASTError(
                "ruleref atom must be ('ruleref', rule_id, version, [terms...])",
                path=path,
            )
        _, rule_id, version, terms = raw
        if version is not None and not isinstance(version, str):
            raise WhereASTError("ruleref version must be string or None", path=path)
        if not isinstance(terms, list):
            raise WhereASTError("ruleref atom terms must be list", path=path)
        return RuleRefAtom(
            rule_id=rule_id,
            version=version,
            terms=[_parse_term(t, path=f"{path}[3][{idx}]") for idx, t in enumerate(terms)],
            origin=Origin(source="raw_ir", path=path),
        )

    if tag in _CMP_OPS:
        if len(raw) != 3:
            raise WhereASTError(f"{tag} atom must be ('{tag}', lhs, rhs)", path=path)
        _, lhs, rhs = raw
        return CmpAtom(
            op=tag,
            lhs=_parse_term(lhs, path=f"{path}[1]"),
            rhs=_parse_term(rhs, path=f"{path}[2]"),
            origin=Origin(source="raw_ir", path=path),
        )

    if tag == "in":
        if len(raw) != 3:
            raise WhereASTError("in atom must be ('in', var, [values...])", path=path)
        _, var, values = raw
        var_term = _parse_term(var, path=f"{path}[1]")
        if not isinstance(var_term, Var):
            raise WhereASTError("in atom first argument must be variable", path=f"{path}[1]")
        if not isinstance(values, list):
            raise WhereASTError("in atom values must be list", path=f"{path}[2]")
        const_values: list[Const] = []
        for idx, value in enumerate(values):
            term = _parse_term(value, path=f"{path}[2][{idx}]")
            if not isinstance(term, Const):
                raise WhereASTError("in values must be constants", path=f"{path}[2][{idx}]")
            const_values.append(term)
        return InAtom(
            var=var_term,
            values=const_values,
            origin=Origin(source="raw_ir", path=path),
        )

    if tag in _BUILTIN_TAGS:
        return BuiltinAtom(
            op=tag,
            args=[_parse_term(v, path=f"{path}[{i}]") for i, v in enumerate(raw[1:], start=1)],
            origin=Origin(source="raw_ir", path=path),
        )

    if tag == "not":
        if len(raw) != 2:
            raise WhereASTError("not atom must be ('not', [body...])", path=path)
        return NotAtom(
            body=_parse_where_expr(raw[1], path=f"{path}[1]"),
            origin=Origin(source="raw_ir", path=path),
        )

    raise WhereASTError(f"unsupported atom tag: {tag}", path=path)


def _parse_term(raw: Any, *, path: str) -> Term:
    if isinstance(raw, str) and raw.startswith("$") and len(raw) > 1:
        return Var(name=raw, origin=Origin(source="raw_ir", path=path))
    return Const(value=raw, origin=Origin(source="raw_ir", path=path))


def _lower_atom(atom: Atom) -> tuple[Any, ...]:
    if isinstance(atom, PredAtom):
        return ("pred", atom.pred_id, [_lower_term(t) for t in atom.terms])
    if isinstance(atom, RuleRefAtom):
        return ("ruleref", atom.rule_id, atom.version, [_lower_term(t) for t in atom.terms])
    if isinstance(atom, CmpAtom):
        return (atom.op, _lower_term(atom.lhs), _lower_term(atom.rhs))
    if isinstance(atom, InAtom):
        return ("in", _lower_term(atom.var), [_lower_term(v) for v in atom.values])
    if isinstance(atom, BuiltinAtom):
        return (atom.op, *[_lower_term(arg) for arg in atom.args])
    if isinstance(atom, NotAtom):
        return ("not", lower_ast_to_where_ir(atom.body))
    raise WhereASTError(f"unsupported atom node: {type(atom).__name__}")


def _lower_term(term: Term) -> Any:
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Const):
        return term.value
    raise WhereASTError(f"unsupported term node: {type(term).__name__}")
