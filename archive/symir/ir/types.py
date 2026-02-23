"""Core IR types and JSON-serializable structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union
import json

from symir.errors import SchemaError


Layer = Literal["fact", "rule"]
RuleKind = Literal["rule_node", "rule_edge"]


@dataclass(frozen=True)
class IRPredicateRef:
    """Reference to a predicate in the IR.

    Attributes:
        name: Predicate name.
        arity: Number of terms.
        layer: "fact" or "rule".
    """

    name: str
    arity: int
    layer: Layer

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise SchemaError("Predicate name must be a non-empty string.")
        if not isinstance(self.arity, int) or self.arity < 0:
            raise SchemaError("Predicate arity must be a non-negative integer.")
        if self.layer not in ("fact", "rule"):
            raise SchemaError("Predicate layer must be 'fact' or 'rule'.")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "arity": self.arity, "layer": self.layer}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "IRPredicateRef":
        return IRPredicateRef(
            name=data["name"],
            arity=int(data["arity"]),
            layer=data["layer"],
        )


@dataclass(frozen=True)
class Var:
    """Variable term."""

    name: str

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise SchemaError("Var name must be a non-empty string.")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "var", "value": self.name}


@dataclass(frozen=True)
class Const:
    """Constant term."""

    value: Union[str, int, float, bool]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "const", "value": self.value}


IRTerm = Union[Var, Const]


def term_from_dict(data: dict[str, Any]) -> IRTerm:
    """Deserialize a term from a dict."""

    kind = data.get("kind")
    if kind == "var":
        return Var(name=str(data.get("value")))
    if kind == "const":
        return Const(value=data.get("value"))
    raise SchemaError(f"Unknown term kind: {kind}")


@dataclass(frozen=True)
class IRAtom:
    """Atomic predicate application."""

    predicate: IRPredicateRef
    terms: list[IRTerm]
    prob: Optional[float] = None
    negated: bool = False

    def __post_init__(self) -> None:
        if len(self.terms) != self.predicate.arity:
            raise SchemaError(
                f"Arity mismatch for predicate {self.predicate.name}: "
                f"expected {self.predicate.arity}, got {len(self.terms)}."
            )
        if self.prob is not None:
            if not isinstance(self.prob, (int, float)):
                raise SchemaError("Probability must be a number if provided.")
            if not (0.0 <= float(self.prob) <= 1.0):
                raise SchemaError("Probability must be within [0.0, 1.0].")

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate.to_dict(),
            "terms": [term.to_dict() for term in self.terms],
            "prob": self.prob,
            "negated": self.negated,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "IRAtom":
        return IRAtom(
            predicate=IRPredicateRef.from_dict(data["predicate"]),
            terms=[term_from_dict(t) for t in data.get("terms", [])],
            prob=data.get("prob"),
            negated=bool(data.get("negated", False)),
        )


@dataclass(frozen=True)
class IRRule:
    """Horn-like rule in the IR."""

    head: IRAtom
    body: list[IRAtom] = field(default_factory=list)
    prob: Optional[float] = None
    kind: RuleKind = "rule_node"
    is_nullary: bool = False

    def __post_init__(self) -> None:
        if self.kind not in ("rule_node", "rule_edge"):
            raise SchemaError("Rule kind must be 'rule_node' or 'rule_edge'.")
        if self.is_nullary:
            if self.head.predicate.arity != 0 or self.head.terms:
                raise SchemaError("Nullary rules must have arity 0 and no terms.")
        if self.prob is not None:
            if not isinstance(self.prob, (int, float)):
                raise SchemaError("Rule probability must be a number if provided.")
            if not (0.0 <= float(self.prob) <= 1.0):
                raise SchemaError("Rule probability must be within [0.0, 1.0].")

    def to_dict(self) -> dict[str, Any]:
        return {
            "head": self.head.to_dict(),
            "body": [atom.to_dict() for atom in self.body],
            "prob": self.prob,
            "kind": self.kind,
            "is_nullary": self.is_nullary,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "IRRule":
        return IRRule(
            head=IRAtom.from_dict(data["head"]),
            body=[IRAtom.from_dict(a) for a in data.get("body", [])],
            prob=data.get("prob"),
            kind=data.get("kind", "rule_node"),
            is_nullary=bool(data.get("is_nullary", False)),
        )


@dataclass(frozen=True)
class IRProgram:
    """Container for all facts and rules in a program."""

    facts: list[IRAtom] = field(default_factory=list)
    rules: list[IRRule] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": [fact.to_dict() for fact in self.facts],
            "rules": [rule.to_dict() for rule in self.rules],
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Serialize the program to JSON."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "IRProgram":
        return IRProgram(
            facts=[IRAtom.from_dict(a) for a in data.get("facts", [])],
            rules=[IRRule.from_dict(r) for r in data.get("rules", [])],
        )

    @staticmethod
    def from_json(payload: str) -> "IRProgram":
        """Deserialize a program from JSON."""

        return IRProgram.from_dict(json.loads(payload))
