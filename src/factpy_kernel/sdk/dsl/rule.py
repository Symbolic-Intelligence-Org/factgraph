from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SDKDSLError
from .expr import CompareExpr, HeadCall, NotExpr, RuleRefAtom, lower_where


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

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise SDKDSLError("Rule.id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise SDKDSLError("Rule.version must be non-empty string")
        if not isinstance(self.select, list) or not self.select:
            raise SDKDSLError("Rule.select must be non-empty list")
        if not isinstance(self.where, list) or not self.where:
            raise SDKDSLError("Rule.where must be non-empty list")

    def to_authoring_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self.id,
            "version": self.version,
            "select": [_lower_select_item(item) for item in self.select],
            "where": lower_where(self.where),
        }
        if self.expose:
            payload["expose"] = True
        if self.status is not None:
            payload["status"] = self.status
        return payload

    def dependency_rules(self) -> list[Rule]:
        found: dict[tuple[str, str], Rule] = {}

        def walk(node: Any) -> None:
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

        walk(self.where)
        return list(found.values())


@dataclass(frozen=True)
class Derivation:
    id: str
    version: str
    where: list[Any]
    head: HeadCall | None = None
    target: str | None = None
    head_vars: list[Any] | None = None
    mode: str | None = None
    temporal_view: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise SDKDSLError("Derivation.id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise SDKDSLError("Derivation.version must be non-empty string")
        if not isinstance(self.where, list) or not self.where:
            raise SDKDSLError("Derivation.where must be non-empty list")
        if self.head is not None and not isinstance(self.head, HeadCall):
            raise SDKDSLError("Derivation.head must be a DSL head call")

    def to_authoring_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "derivation_id": self.id,
            "version": self.version,
            "where": lower_where(self.where),
        }
        if self.head is not None:
            payload["head"] = self.head.to_authoring_head()
        if self.target is not None:
            payload["target"] = self.target
        if self.head_vars is not None:
            payload["head_vars"] = [_lower_select_item(item) for item in self.head_vars]
        if self.mode is not None:
            payload["mode"] = self.mode
        if self.temporal_view is not None:
            payload["temporal_view"] = self.temporal_view
        if self.status is not None:
            payload["status"] = self.status
        return payload


def _lower_select_item(item: Any) -> Any:
    if hasattr(item, "token") and isinstance(getattr(item, "token", None), str):
        return getattr(item, "token")
    return item
