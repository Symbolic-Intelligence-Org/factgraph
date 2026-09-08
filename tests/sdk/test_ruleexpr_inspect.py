from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from factgraph import sdk
from factgraph.application.protocol import (
    ConditionDescriptor,
    OccurrenceInspect,
    PortInspect,
    RuleExprInspect,
)
from factgraph.application.protocol import (
    Rule as ApplicationRule,
)
from factgraph.application.protocol.rule_expr import RuleExprError
from factgraph.core.rules.where_ast import (
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    Var,
)
from factgraph.sdk import dsl
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStoreError


class User(Entity):
    user_id: str = Identity()
    status: str = Field()
    region: str = Field()


class Account(Entity):
    account_id: str = Identity()
    tenant_id: str = Identity()
    region: str = Field()


def _application_rule(rule_id: str = "active_user", *, var_name: str = "u") -> ApplicationRule:
    user = Var(var_name)
    status = Var(f"{var_name}_status")
    return ApplicationRule(
        id=rule_id,
        when=(
            PredAtom("User:exists", [user]),
            PredAtom("User:status", [user, status]),
            CmpAtom("eq", status, Const("active")),
        ),
        ports={"user": user, "status": status},
        repr="User %user has status %status",
    )


def _other_rule() -> ApplicationRule:
    user = Var("v")
    return ApplicationRule(
        id="trusted_user",
        when=(PredAtom("User:exists", [user]),),
        ports={"user": user},
        repr="Trusted %user",
    )


class RuleExprInspectExportTests(unittest.TestCase):
    def test_sdk_exports_ruleexpr_inspect_public_names(self) -> None:
        self.assertIs(sdk.RuleExprInspect, RuleExprInspect)
        self.assertIs(sdk.OccurrenceInspect, OccurrenceInspect)
        self.assertIs(sdk.ConditionDescriptor, ConditionDescriptor)
        self.assertIs(sdk.PortInspect, PortInspect)
        self.assertEqual(len(sdk.__all__), len(set(sdk.__all__)))
        for name in ("RuleExprInspect", "OccurrenceInspect", "ConditionDescriptor", "PortInspect"):
            self.assertIn(name, sdk.__all__)


class RuleExprInspectDispatchTests(unittest.TestCase):
    def test_legacy_sdk_rule_inspect_dict_shape_is_preserved(self) -> None:
        with sdk.vars("u") as (u,):
            legacy = dsl.Rule(id="legacy", version="v1", select=[u], where=[sdk.Pred("User:exists", u)])

        inspected = sdk.SDKStore([User]).rules.inspect(legacy)

        self.assertIsInstance(inspected, dict)
        self.assertEqual(inspected["kind"], "Rule")
        self.assertEqual(inspected["branches"][0]["atom_ids"], ["c0.c0"])

    def test_legacy_sdk_inference_inspect_dict_shape_is_preserved(self) -> None:
        with sdk.vars("u") as (u,):
            inference = sdk.Inference(
                id="legacy_inference",
                version="v1",
                when=[sdk.Pred("User:exists", u)],
                emits=sdk.EmitSpec("User:status", [u]),
            )

        inspected = sdk.SDKStore([User]).rules.inspect(inference)

        self.assertIsInstance(inspected, dict)
        self.assertEqual(inspected["kind"], "Inference")
        self.assertIn("heads", inspected)

    def test_application_rule_inspect_returns_ruleexprinspect(self) -> None:
        rule = _application_rule()

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertIsInstance(inspected, RuleExprInspect)
        self.assertEqual(inspected.ast, ("rule", "active_user", "active_user"))
        self.assertEqual(inspected.templates, ("active_user",))
        self.assertEqual(inspected.port_visibility["active_user"], ("status", "user"))
        self.assertFalse(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ("user",))

    def test_ruleexpr_inspect_returns_ruleexprinspect(self) -> None:
        left = _application_rule().as_("left")
        right = _other_rule().as_("right")
        expr = (left & right).join(left.user.eq(right.user))

        inspected = sdk.SDKStore([User]).rules.inspect(expr)

        self.assertIsInstance(inspected, RuleExprInspect)
        self.assertEqual(len(inspected.occurrences), 2)
        self.assertEqual(len(inspected.joins), 1)
        self.assertEqual(inspected.unjoined_same_name_ports, ())
        self.assertFalse(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ())

    def test_unsupported_input_still_uses_sdk_store_error(self) -> None:
        with self.assertRaises(SDKStoreError):
            sdk.SDKStore([User]).rules.inspect(object())


class RuleExprInspectDTOTests(unittest.TestCase):
    def test_dtos_are_frozen_and_shape_validated(self) -> None:
        atom = ConditionDescriptor(atom_id="rule:atom_0", kind="pred", summary="pred")
        occurrence = OccurrenceInspect(
            template_id="rule",
            alias="alias",
            repr_template=None,
            ports=("user",),
            atoms=(atom,),
        )
        inspect = RuleExprInspect(
            ast=("rule", "alias", "rule"),
            occurrences=(occurrence,),
            joins=(),
            unjoined_same_name_ports=({"port_name": "user", "occurrences": ("alias",)},),
        )

        with self.assertRaises(FrozenInstanceError):
            atom.kind = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            occurrence.alias = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            inspect.ast = ()  # type: ignore[misc]

        with self.assertRaisesRegex(RuleExprError, "port_name and occurrences"):
            RuleExprInspect(ast=(), occurrences=(), joins=(), unjoined_same_name_ports=({"name": "user"},))
        with self.assertRaisesRegex(RuleExprError, "is_closed must be bool"):
            RuleExprInspect(ast=(), occurrences=(), joins=(), unjoined_same_name_ports=(), is_closed=None)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuleExprError, "unbound_ports must be tuple"):
            RuleExprInspect(ast=(), occurrences=(), joins=(), unjoined_same_name_ports=(), unbound_ports=("ok", ""))  # type: ignore[arg-type]

    def test_occurrence_atoms_use_rule_atom_ids_and_parent_c50_kinds(self) -> None:
        inspected = sdk.SDKStore([User]).rules.inspect(_application_rule())
        occurrence = inspected.occurrences[0]

        self.assertEqual(occurrence.alias, "active_user")
        self.assertEqual(occurrence.ports, ("status", "user"))
        self.assertEqual([atom.atom_id for atom in occurrence.atoms], [f"active_user:atom_{idx}" for idx in range(3)])
        self.assertEqual(occurrence.atoms[0].kind, "entity_existence")
        self.assertEqual(occurrence.atoms[0].entity_type, "User")
        self.assertEqual(occurrence.atoms[1].kind, "field_predicate")
        self.assertEqual(occurrence.atoms[1].field, "status")
        self.assertEqual(occurrence.atoms[2].kind, "cmp")
        self.assertEqual(occurrence.atoms[2].op, "eq")

    def test_entity_existence_accepts_non_empty_multi_term_predicates(self) -> None:
        marker = Const("marker")
        user = Var("u")
        rule = ApplicationRule(
            id="multi_exists",
            when=(PredAtom("User:exists", [marker, user]),),
            ports={"user": user},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        atom = inspected.occurrences[0].atoms[0]
        self.assertEqual(atom.kind, "entity_existence")
        self.assertEqual(atom.entity_type, "User")
        self.assertEqual(atom.subject, "'marker'")

    def test_ports_property_returns_c59_portinspect_descriptors(self) -> None:
        inspected = sdk.SDKStore([User]).rules.inspect(_application_rule())

        self.assertEqual(
            inspected.ports,
            (
                PortInspect(name="status", kind="value", value_type="unknown"),
                PortInspect(name="user", kind="entity_ref", entity_type="User"),
            ),
        )
        self.assertNotEqual(inspected.occurrences[0].ports, inspected.ports)

    def test_unjoined_same_name_ports_use_stable_key_shape(self) -> None:
        left = _application_rule().as_("left")
        right = _other_rule().as_("right")

        inspected = sdk.SDKStore([User]).rules.inspect(left & right)

        self.assertEqual(inspected.unjoined_same_name_ports, ({"port_name": "user", "occurrences": ("left", "right")},))

    def test_render_and_render_compact_are_deterministic_authoring_narratives(self) -> None:
        left = _application_rule().as_("left")
        right = _other_rule().as_("right")
        inspected = sdk.SDKStore([User]).rules.inspect((left & right).join(left.user.eq(right.user)))

        rendered = inspected.render({"left.user": "Alice", "left.status": "active", "right.user": "Bob"})

        self.assertIn("RuleExprInspect", rendered)
        self.assertIn("left:active_user User Alice has status active", rendered)
        self.assertIn("right:trusted_user Trusted Bob", rendered)
        self.assertIn("joins left.user = right.user", rendered)
        self.assertEqual(inspected.render_compact(), "(left:active_user & right:trusted_user).join(1)")

    def test_remaining_atom_kinds_are_described_without_execution_semantics(self) -> None:
        status = Var("status")
        user = Var("u")
        rule = ApplicationRule(
            id="atom_kinds",
            when=(
                InAtom(status, [Const("active"), Const("pending")]),
                BuiltinAtom("add", [Const(1), Const(2)]),
                NotAtom(body=AndExpr([PredAtom("User:exists", [user])])),
            ),
            ports={"status": status},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertEqual([atom.kind for atom in inspected.occurrences[0].atoms], ["in", "builtin", "not"])

    def test_value_port_direct_var_const_equality_closes(self) -> None:
        inspected = sdk.SDKStore([User]).rules.inspect(_application_rule())

        self.assertFalse(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ("user",))

        status = Var("status")
        rule = ApplicationRule(
            id="closed_status",
            when=(CmpAtom("eq", status, Const("active")),),
            ports={"status": status},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertTrue(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ())

    def test_value_port_direct_const_var_equality_closes(self) -> None:
        status = Var("status")
        rule = ApplicationRule(
            id="closed_status_reverse",
            when=(CmpAtom("eq", Const("active"), status),),
            ports={"status": status},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertTrue(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ())

    def test_value_port_non_literal_forms_remain_open(self) -> None:
        cases = (
            (PredAtom("User:status", [Var("u"), Var("status")]),),
            (BuiltinAtom("lower", [Var("status")]),),
            (InAtom(Var("status"), [Const("active")]),),
            (NotAtom(body=AndExpr([PredAtom("User:status", [Var("u"), Var("status")])])),),
            (CmpAtom("eq", Var("status"), Var("other")),),
            (CmpAtom("ne", Var("status"), Const("active")),),
        )

        for index, where in enumerate(cases):
            with self.subTest(index=index):
                rule = ApplicationRule(id=f"open_value_{index}", when=where, ports={"status": Var("status")})

                inspected = sdk.SDKStore([User]).rules.inspect(rule)

                self.assertFalse(inspected.is_closed)
                self.assertEqual(inspected.unbound_ports, ("status",))

    def test_entity_ref_single_primary_identity_literal_closes(self) -> None:
        user = Var("u")
        rule = ApplicationRule(
            id="closed_user",
            when=(
                PredAtom("User:exists", [user]),
                PredAtom("user:user_id", [user, Const("user-1")]),
            ),
            ports={"user": user},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertTrue(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ())

    def test_entity_ref_primary_identity_requires_entity_first_order(self) -> None:
        user = Var("u")
        rule = ApplicationRule(
            id="wrong_identity_order",
            when=(
                PredAtom("User:exists", [user]),
                PredAtom("user:user_id", [Const("user-1"), user]),
            ),
            ports={"user": user},
        )

        inspected = sdk.SDKStore([User]).rules.inspect(rule)

        self.assertFalse(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ("user",))

    def test_entity_ref_compound_primary_identity_requires_all_fields(self) -> None:
        account = Var("a")
        closed = ApplicationRule(
            id="closed_account",
            when=(
                PredAtom("Account:exists", [account]),
                PredAtom("account:account_id", [account, Const("acct-1")]),
                PredAtom("account:tenant_id", [account, Const("tenant-1")]),
            ),
            ports={"account": account},
        )
        open_rule = ApplicationRule(
            id="open_account",
            when=(
                PredAtom("Account:exists", [account]),
                PredAtom("account:account_id", [account, Const("acct-1")]),
            ),
            ports={"account": account},
        )

        sdk_store = sdk.SDKStore([Account])

        self.assertTrue(sdk_store.rules.inspect(closed).is_closed)
        inspected_open = sdk_store.rules.inspect(open_rule)
        self.assertFalse(inspected_open.is_closed)
        self.assertEqual(inspected_open.unbound_ports, ("account",))

    def test_missing_schema_keeps_entity_ref_unbound_without_raising(self) -> None:
        user = Var("u")
        rule = ApplicationRule(
            id="schema_missing",
            when=(
                PredAtom("User:exists", [user]),
                PredAtom("user:user_id", [user, Const("user-1")]),
            ),
            ports={"user": user},
        )

        # Direct protocol helper path has no SDK schema index and is conservative.
        from factgraph.application.protocol.rule_expr_inspect import _inspect_application_rule

        inspected = _inspect_application_rule(rule)

        self.assertFalse(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ("user",))

    def test_projection_rule_inspect_reports_closed_by_construction(self) -> None:
        projection = ApplicationRule.projection("region", "user")

        inspected = sdk.SDKStore([User]).rules.inspect(projection)

        self.assertTrue(inspected.is_closed)
        self.assertEqual(inspected.unbound_ports, ())
        self.assertEqual(tuple(port.name for port in inspected.ports), ("region", "user"))


if __name__ == "__main__":
    unittest.main()
