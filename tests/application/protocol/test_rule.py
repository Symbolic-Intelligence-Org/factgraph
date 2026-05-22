from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType
import unittest

from factgraph.application.protocol import Rule, RuleValidationError
from factgraph.application.protocol.rule import PortType
from factgraph.core.rules.where_ast import (
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    RuleRefAtom,
    Var,
)
from factgraph.sdk.dsl.expr import ExistsAtom as SDKExistsAtom
from factgraph.sdk.dsl.expr import LogicVar as SDKLogicVar


class RuleConstructionTests(unittest.TestCase):
    def test_rule_requires_non_empty_id(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="", where=(PredAtom("User:exists", [u]),), ports={"user": u})

    def test_rule_requires_non_empty_tuple_where(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", where=(), ports={"user": u})

    def test_rule_requires_var_ports(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                where=(PredAtom("User:exists", [u]),),
                ports={"user": Const("u")},  # type: ignore[dict-item]
            )


class AtomKindAllowlistTests(unittest.TestCase):
    def test_five_core_atom_kinds_are_allowed(self) -> None:
        u = Var("u")
        atoms = (
            PredAtom("User:exists", [u]),
            CmpAtom("eq", u, Const("u-1")),
            InAtom(u, [Const("u-1"), Const("u-2")]),
            BuiltinAtom("add", [u, Const(1)]),
            NotAtom(AndExpr([CmpAtom("ne", u, Const("blocked"))])),
        )
        rule = Rule(id="r1", where=atoms, ports={"user": u})
        self.assertEqual(rule.where, atoms)

    def test_rule_ref_atom_is_rejected(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", where=(RuleRefAtom("other", "v1", [u]),), ports={"user": u})

    def test_sdk_dsl_types_are_rejected(self) -> None:
        u = SDKLogicVar("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                where=(SDKExistsAtom("User", u),),  # type: ignore[arg-type]
                ports={"user": Var("u")},
            )


class PortValidationTests(unittest.TestCase):
    def test_port_var_must_appear_in_where(self) -> None:
        u = Var("u")
        region = Var("region")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", where=(PredAtom("User:exists", [u]),), ports={"region": region})

    def test_port_types_infer_entity_ref_and_value(self) -> None:
        u = Var("u")
        status = Var("status")
        rule = Rule(
            id="r1",
            where=(
                PredAtom("User:exists", [u]),
                CmpAtom("eq", status, Const("active")),
            ),
            ports={"user": u, "status": status},
        )
        self.assertEqual(rule.port_types["user"], PortType(kind="entity_ref", entity_type="User"))
        self.assertEqual(rule.port_types["status"], PortType(kind="value"))


class DescRenderTests(unittest.TestCase):
    def test_render_desc_uses_placeholders_for_unbound_ports(self) -> None:
        u = Var("u")
        rule = Rule(
            id="r1",
            where=(PredAtom("User:exists", [u]),),
            ports={"user": u},
            desc="user %user is active",
        )
        self.assertEqual(rule.render_desc(), "user <user> is active")
        self.assertEqual(rule.render_desc({"user": "u-1"}), "user u-1 is active")

    def test_desc_rejects_undeclared_port(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                where=(PredAtom("User:exists", [u]),),
                ports={"user": u},
                desc="user %missing",
            )


class RuleIdentityTests(unittest.TestCase):
    def test_atom_ids_are_positional(self) -> None:
        u = Var("u")
        rule = Rule(
            id="active_user",
            where=(PredAtom("User:exists", [u]), CmpAtom("eq", u, Const("u-1"))),
            ports={"user": u},
        )
        self.assertEqual(rule.atom_ids, ("active_user:atom_0", "active_user:atom_1"))

    def test_content_digest_is_deterministic_and_order_sensitive(self) -> None:
        u = Var("u")
        a = PredAtom("User:exists", [u])
        b = CmpAtom("eq", u, Const("u-1"))
        first = Rule(id="r1", where=(a, b), ports={"user": u})
        same = Rule(id="r2", where=(a, b), ports={"user": u})
        reordered = Rule(id="r1", where=(b, a), ports={"user": u})
        self.assertEqual(first.content_digest, same.content_digest)
        self.assertNotEqual(first.content_digest, reordered.content_digest)


class ImmutabilityTests(unittest.TestCase):
    def test_rule_container_is_shallow_immutable(self) -> None:
        u = Var("u")
        rule = Rule(id="r1", where=(PredAtom("User:exists", [u]),), ports={"user": u})
        with self.assertRaises(FrozenInstanceError):
            rule.id = "other"  # type: ignore[misc]
        self.assertIsInstance(rule.ports, MappingProxyType)
        with self.assertRaises(TypeError):
            rule.ports["other"] = u  # type: ignore[index]
        with self.assertRaises(AttributeError):
            rule.where.append(PredAtom("User:exists", [u]))  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
