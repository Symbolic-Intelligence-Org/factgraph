from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast
from factpy_kernel.core.store.types import EngineExtBase

from ..error_codes import QUERY_ALIAS_CONFLICT, QUERY_UNBOUND_VAR
from .body import Body
from .errors import SDKDSLError
from .expr import CompareExpr, ExistsAtom, HeadCall, LogicVar, NotExpr, RuleRefAtom, lower_where


@dataclass(frozen=True)
class RuleRef:
    rule_id: str
    version: str

    def __init__(self, rule_id: str | Rule, *, version: str | None = None) -> None:
        if isinstance(rule_id, Rule):
            object.__setattr__(self, "rule_id", rule_id.id)
            object.__setattr__(self, "version", rule_id.version)
            object.__setattr__(self, "_rule_obj", rule_id)
            return
        if not isinstance(rule_id, str) or not rule_id:
            raise SDKDSLError("RuleRef rule_id must be non-empty string or Rule object")
        if not isinstance(version, str) or not version:
            raise SDKDSLError("RuleRef version must be non-empty string")
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "_rule_obj", None)

    def __call__(self, *terms: Any) -> RuleRefAtom:
        if not terms:
            raise SDKDSLError("RuleRef(...) call requires at least one term")
        return RuleRefAtom(
            rule_id=self.rule_id,
            version=self.version,
            terms=tuple(terms),
            rule_obj=getattr(self, "_rule_obj", None),
        )


@dataclass(frozen=True)
class Rule:
    id: str
    version: str
    select: list[Any]
    where: list[Any]
    expose: bool = False
    status: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    condition_weights: dict[str, float] = field(default_factory=dict)
    engine_ext: EngineExtBase | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise SDKDSLError("Rule.id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise SDKDSLError("Rule.version must be non-empty string")
        if not isinstance(self.select, list) or not self.select:
            raise SDKDSLError("Rule.select must be non-empty list")
        if not isinstance(self.where, list) or not self.where:
            raise SDKDSLError("Rule.where must be non-empty list")
        _validate_optional_description(self.description, owner="Rule")
        _validate_tags(self.tags, owner="Rule")
        _validate_condition_weights(self.condition_weights, owner="Rule")

    def to_authoring_payload(self) -> dict[str, Any]:
        normalized_where = _normalize_rule_where_for_payload(self.where)
        payload: dict[str, Any] = {
            "rule_id": self.id,
            "version": self.version,
            "select": [_lower_select_item(item) for item in self.select],
            "where": lower_where(normalized_where),
        }
        if self.expose:
            payload["expose"] = True
        if self.status is not None:
            payload["status"] = self.status
        if self.description is not None:
            payload["description"] = self.description
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.condition_weights:
            payload["condition_weights"] = {
                key: float(self.condition_weights[key]) for key in sorted(self.condition_weights)
            }
        return payload

    def dependency_rules(self) -> list[Rule]:
        return _dependency_rules_from_where(self.where)


@dataclass(frozen=True)
class Derivation:
    id: str
    version: str
    where: list[Any]
    head: Any = None
    target: str | None = None
    head_vars: list[Any] | None = None
    mode: str | None = None
    engine_ext: EngineExtBase | None = None
    status: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    _heads: tuple[HeadCall, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise SDKDSLError("Derivation.id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise SDKDSLError("Derivation.version must be non-empty string")
        if not isinstance(self.where, list) or not self.where:
            raise SDKDSLError("Derivation.where must be non-empty list")
        _validate_optional_description(self.description, owner="Derivation")
        _validate_tags(self.tags, owner="Derivation")
        object.__setattr__(self, "_heads", _normalize_derivation_head_items(self.head))

    @property
    def heads(self) -> list[HeadCall]:
        return list(self._heads)

    def to_authoring_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "derivation_id": self.id,
            "version": self.version,
            "where": lower_where(self.where),
        }
        if self._heads:
            if len(self._heads) == 1:
                payload["head"] = self._heads[0].to_authoring_head()
            else:
                payload["head"] = [item.to_authoring_head() for item in self._heads]
        if self.target is not None:
            payload["target"] = self.target
        if self.head_vars is not None:
            payload["head_vars"] = [_lower_select_item(item) for item in self.head_vars]
        if self.mode is not None:
            payload["mode"] = self.mode
        if self.status is not None:
            payload["status"] = self.status
        if self.description is not None:
            payload["description"] = self.description
        if self.tags:
            payload["tags"] = list(self.tags)
        return payload

    def dependency_rules(self) -> list[Rule]:
        return _dependency_rules_from_where(self.where)


@dataclass(frozen=True)
class ReturnContractEntry:
    var: str
    alias: str
    entity_type: str | None
    field_path: str | None


@dataclass(frozen=True)
class Query:
    head: Any
    where: list[Any]
    on_missing: str = "error"
    on_type_mismatch: str = "error"
    _normalized_head: tuple[Any, ...] = field(init=False, repr=False)
    _return_contract: tuple[ReturnContractEntry, ...] = field(init=False, repr=False)
    _initial_bound_vars: frozenset[str] = field(init=False, repr=False)
    _where_ir: list[Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.where, list) or not self.where:
            raise SDKDSLError("Query.where must be non-empty list", path="$.where")
        _validate_query_where_body_confidence(self.where, path="$.where")
        if self.on_missing not in {"error", "skip", "null"}:
            raise SDKDSLError("Query.on_missing must be one of: error|skip|null", path="$.on_missing")
        if self.on_type_mismatch not in {"error", "skip", "null"}:
            raise SDKDSLError(
                "Query.on_type_mismatch must be one of: error|skip|null",
                path="$.on_type_mismatch",
            )

        normalized_head = _normalize_query_head_items(self.head)
        return_contract = _head_to_return_contract(normalized_head)
        _validate_query_alias_conflicts(return_contract)

        initial_bound_vars = _collect_query_head_bound_vars(normalized_head)
        initial_entity_bindings = _collect_query_head_entity_bindings(normalized_head)

        try:
            where_ir = lower_where(
                self.where,
                initial_bindings=initial_entity_bindings,
            )
            where_ast = parse_where_ir_to_ast(where_ir)
            validate_where_ast(
                where_ast,
                mode="python",
                initial_bound_vars=set(initial_bound_vars),
            )
        except (WhereASTError, WhereASTValidationError) as exc:
            code = QUERY_UNBOUND_VAR if _is_query_unbound_error(exc) else None
            path = getattr(exc, "path", None) or "$.where"
            raise SDKDSLError(str(exc), code=code, path=path) from exc

        object.__setattr__(self, "_normalized_head", normalized_head)
        object.__setattr__(self, "_return_contract", return_contract)
        object.__setattr__(self, "_initial_bound_vars", frozenset(initial_bound_vars))
        object.__setattr__(self, "_where_ir", where_ir)

    @property
    def return_contract(self) -> list[ReturnContractEntry]:
        return list(self._return_contract)

    @property
    def initial_bound_vars(self) -> set[str]:
        return set(self._initial_bound_vars)

    @property
    def where_ir(self) -> list[Any]:
        return list(self._where_ir)

    def to_runtime_payload(self) -> dict[str, Any]:
        return {
            "head": [_query_head_item_to_payload(item) for item in self._normalized_head],
            "where": list(self._where_ir),
            "on_missing": self.on_missing,
            "on_type_mismatch": self.on_type_mismatch,
            "return_contract": [
                {
                    "var": entry.var,
                    "alias": entry.alias,
                    "entity_type": entry.entity_type,
                    "field_path": entry.field_path,
                }
                for entry in self._return_contract
            ],
            "initial_bound_vars": sorted(self._initial_bound_vars),
        }

    def dependency_rules(self) -> list[Rule]:
        return _dependency_rules_from_where(self.where)


def _lower_select_item(item: Any) -> Any:
    if hasattr(item, "token") and isinstance(getattr(item, "token", None), str):
        return getattr(item, "token")
    return item


def _normalize_rule_where_for_payload(where: list[Any]) -> list[Any]:
    if not isinstance(where, list) or not where:
        raise SDKDSLError("Rule.where must be non-empty list")
    has_body = any(isinstance(item, Body) for item in where)
    if not has_body:
        return where
    if not all(isinstance(item, Body) for item in where):
        raise SDKDSLError("where/body cannot mix Body(...) with bare branches")
    return [list(item.atoms) for item in where]


def _dependency_rules_from_where(where: Any) -> list[Rule]:
    found: dict[tuple[str, str], Rule] = {}

    def walk(node: Any) -> None:
        if isinstance(node, Body):
            walk(list(node.atoms))
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, tuple):
            for item in node:
                walk(item)
            return
        if isinstance(node, RuleRefAtom):
            dep = node.rule_obj
            if isinstance(dep, Rule):
                found[(dep.id, dep.version)] = dep
            return
        if isinstance(node, CompareExpr):
            walk(node.left)
            walk(node.right)
            return
        if isinstance(node, NotExpr):
            walk(node.body)
            return

    walk(where)
    return list(found.values())


def _validate_optional_description(value: str | None, *, owner: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise SDKDSLError(f"{owner}.description must be non-empty string when provided")


def _validate_tags(tags: Any, *, owner: str) -> None:
    if not isinstance(tags, list):
        raise SDKDSLError(f"{owner}.tags must be list[str]")
    for index, tag in enumerate(tags):
        if not isinstance(tag, str) or not tag:
            raise SDKDSLError(f"{owner}.tags[{index}] must be non-empty string")


def _validate_condition_weights(condition_weights: Any, *, owner: str) -> None:
    if not isinstance(condition_weights, dict):
        raise SDKDSLError(f"{owner}.condition_weights must be dict[str, float]")
    for key, value in condition_weights.items():
        if not isinstance(key, str) or not key:
            raise SDKDSLError(f"{owner}.condition_weights keys must be non-empty string")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SDKDSLError(f'{owner}.condition_weights["{key}"] must be numeric')
        weight = float(value)
        if not math.isfinite(weight) or weight <= 0:
            raise SDKDSLError(f'{owner}.condition_weights["{key}"] must be positive finite number')


def _validate_query_where_body_confidence(node: Any, *, path: str) -> None:
    if isinstance(node, Body):
        if node.confidence is not None:
            raise SDKDSLError("Query.where does not support Body.confidence", path=f"{path}.confidence")
        for idx, atom in enumerate(node.atoms):
            _validate_query_where_body_confidence(atom, path=f"{path}.atoms[{idx}]")
        return
    if isinstance(node, list):
        for idx, item in enumerate(node):
            _validate_query_where_body_confidence(item, path=f"{path}[{idx}]")
        return
    if isinstance(node, tuple):
        if (
            len(node) == 3
            and node[0] == "__body__"
            and isinstance(node[1], list)
        ):
            confidence = node[2]
            if confidence is not None:
                raise SDKDSLError("Query.where does not support Body.confidence", path=f"{path}[2]")
            for idx, atom in enumerate(node[1]):
                _validate_query_where_body_confidence(atom, path=f"{path}[1][{idx}]")


def _normalize_derivation_head_items(head: Any) -> tuple[HeadCall, ...]:
    if head is None:
        return tuple()
    if isinstance(head, list):
        head_items = list(head)
    else:
        head_items = [head]
    if not head_items:
        raise SDKDSLError("Derivation.head must be non-empty when provided", path="$.head")

    out: list[HeadCall] = []
    for idx, item in enumerate(head_items):
        path = f"$.head[{idx}]" if isinstance(head, list) else "$.head"
        if not isinstance(item, HeadCall):
            raise SDKDSLError("Derivation.head item must be a DSL head call", path=path)
        if item.callee_kind not in {"pred_ref", "entity_type"}:
            raise SDKDSLError("Derivation.head item must be Entity(...) or Entity.field(...)", path=path)
        out.append(item)
    return tuple(out)


def _normalize_query_head_items(head: Any) -> tuple[Any, ...]:
    if isinstance(head, list):
        head_items = list(head)
    else:
        head_items = [head]
    if not head_items:
        raise SDKDSLError("Query.head must be non-empty", path="$.head")

    out: list[Any] = []
    for idx, item in enumerate(head_items):
        path = f"$.head[{idx}]" if isinstance(head, list) else "$.head"
        if isinstance(item, ExistsAtom):
            out.append(item)
            continue
        if isinstance(item, HeadCall):
            if item.callee_kind != "pred_ref":
                raise SDKDSLError(
                    "Query.head only supports Entity(var) or Entity.field(...) forms",
                    path=path,
                )
            out.append(item)
            continue
        raise SDKDSLError(
            "Query.head item must be Entity(var) or Entity.field(...)",
            path=path,
        )
    return tuple(out)


def _head_to_return_contract(head_items: tuple[Any, ...]) -> tuple[ReturnContractEntry, ...]:
    out: list[ReturnContractEntry] = []
    for idx, item in enumerate(head_items):
        path = f"$.head[{idx}]"
        if isinstance(item, ExistsAtom):
            token = item.var.token
            alias = _alias_from_var_token(token, path=path)
            out.append(
                ReturnContractEntry(
                    var=token,
                    alias=alias,
                    entity_type=item.entity_type,
                    field_path=None,
                )
            )
            continue

        token = _projection_var_token_from_field_head(item, path=path)
        alias = _alias_from_var_token(token, path=path)
        out.append(
            ReturnContractEntry(
                var=token,
                alias=alias,
                entity_type=None,
                field_path=f"{item.entity_type}.{item.field}",
            )
        )
    return tuple(out)


def _projection_var_token_from_field_head(item: HeadCall, *, path: str) -> str:
    if "value" in item.kwargs and isinstance(item.kwargs["value"], LogicVar):
        return item.kwargs["value"].token

    logic_vars = [value for value in item.kwargs.values() if isinstance(value, LogicVar)]
    if not logic_vars:
        raise SDKDSLError(
            "Query field head must include at least one LogicVar argument",
            path=path,
        )
    return logic_vars[-1].token


def _alias_from_var_token(token: Any, *, path: str) -> str:
    if not isinstance(token, str) or not token.startswith("$") or len(token) < 2:
        raise SDKDSLError("Query var token must be '$' + identifier", path=path)
    return token[1:]


def _validate_query_alias_conflicts(return_contract: tuple[ReturnContractEntry, ...]) -> None:
    seen: set[str] = set()
    for entry in return_contract:
        if entry.alias in seen:
            raise SDKDSLError(
                f"query head alias conflict: {entry.alias}",
                code=QUERY_ALIAS_CONFLICT,
                path="$.head",
            )
        seen.add(entry.alias)


def _collect_query_head_bound_vars(head_items: tuple[Any, ...]) -> set[str]:
    out: set[str] = set()
    for item in head_items:
        if isinstance(item, ExistsAtom):
            out.add(item.var.token)
            continue
        for value in item.kwargs.values():
            if isinstance(value, LogicVar):
                out.add(value.token)
    return out


def _collect_query_head_entity_bindings(head_items: tuple[Any, ...]) -> dict[LogicVar, str]:
    out: dict[LogicVar, str] = {}
    for item in head_items:
        if isinstance(item, ExistsAtom):
            out[item.var] = item.entity_type
            continue
        for value in item.kwargs.values():
            if isinstance(value, LogicVar):
                out.setdefault(value, item.entity_type)
    return out


def _is_query_unbound_error(exc: Exception) -> bool:
    msg = str(exc)
    if "requires variables bound earlier in branch" in msg:
        return True
    if "variable must be bound before filter" in msg:
        return True
    if "requires both sides to be resolvable" in msg:
        return True
    if "requires at least one bound/constant side" in msg:
        return True
    if "used in path comparison before" in msg:
        return True
    return False


def _query_head_item_to_payload(item: Any) -> dict[str, Any]:
    if isinstance(item, ExistsAtom):
        return {
            "kind": "entity_head",
            "entity_type": item.entity_type,
            "var": item.var.token,
        }
    return {
        "kind": "field_head",
        "head_call": item.to_authoring_head(),
    }
