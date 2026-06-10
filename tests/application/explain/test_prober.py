from __future__ import annotations

import unittest

import factgraph.application.explain.prober as prober_module
from factgraph.application import build_schema_index, entity_info, field_predicate
from factgraph.application.explain import EvidenceJoin, Fails, Holds, NotReached, probe_native
from factgraph.application.schema_runtime import encode_entity_ref
from factgraph.application.protocol import EntityRef, Rule
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
from factgraph.core.rules.where_ast import AndExpr, CmpAtom, Const, InAtom, NotAtom, OrExpr, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


def _status(result: object) -> str:
    paths = getattr(result, "paths")
    assert len(paths) == 1
    return paths[0].status


def _negated_atoms(result: object) -> tuple[object, ...]:
    paths = getattr(result, "paths")
    return tuple(
        atom
        for path in paths
        for rule in path.rules
        for atom in rule.atoms
        if atom.negated
    )


class NativeProberTests(unittest.TestCase):
    def test_monotonic_witness_backtracking_keeps_later_successful_env(self) -> None:
        x = Var("$x")
        rule = Rule(
            id="positive_p",
            when=(PredAtom("p", [x]), CmpAtom("gt", x, Const(1))),
            ports={"x": x},
        )
        plan = _lower_application_rule(rule, head=rule)

        only_true = probe_native(plan, {}, {"p": [(2,)]})
        false_then_true = probe_native(plan, {}, {"p": [(1,), (2,)]})

        self.assertEqual(_status(only_true), "holds")
        self.assertEqual(_status(false_then_true), "holds")

    def test_structure_preserves_head_body_occurrences_and_join_materialization(self) -> None:
        left_person = Var("$p")
        left_region = Var("$region")
        right_person = Var("$q")
        right_region = Var("$region")
        left = Rule(
            id="left_region",
            when=(PredAtom("Person:region", [left_person, left_region]),),
            ports={"person": left_person, "region": left_region},
        )
        right = Rule(
            id="right_region",
            when=(PredAtom("Person:region", [right_person, right_region]),),
            ports={"person": right_person, "region": right_region},
        )
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        result = probe_native(plan, {}, {"Person:region": [("alice", "US"), ("bob", "US")]})

        self.assertEqual(len(result.paths), 1)
        path = result.paths[0]
        self.assertEqual(path.status, "holds")
        head_rules = [rule for rule in path.rules if rule.role == "head"]
        body_rules = [rule for rule in path.rules if rule.role == "body"]
        self.assertEqual(tuple(rule.occurrence_alias for rule in head_rules), ("left_region",))
        self.assertEqual({rule.occurrence_alias for rule in body_rules}, {"left", "right"})
        self.assertNotIn("branch:0", {rule.occurrence_alias for rule in body_rules})
        self.assertTrue(path.joins)
        self.assertTrue(all(isinstance(join, EvidenceJoin) for join in path.joins))
        self.assertEqual(path.joins[0].left.rule_occurrence_alias, "left")
        self.assertEqual(path.joins[0].right.rule_occurrence_alias, "right")

    def test_not_reached_is_only_unbound_dependency(self) -> None:
        x = Var("$x")
        rule = Rule(id="needs_x", when=(CmpAtom("gt", x, Const(1)),), ports={"x": x})
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(plan, {}, {})

        atom = result.paths[0].rules[1].atoms[0]
        self.assertIsInstance(atom.verdict, NotReached)
        self.assertEqual(atom.verdict.blocked_by, "$needs_x__x")
        self.assertNotIn("$needs_x__x", atom.repr_text or "")
        self.assertIn("<unbound>", atom.repr_text or "")

    def test_downstream_check_after_failed_upstream_can_hold_from_prefix_anchor(self) -> None:
        x = Var("$x")
        rule = Rule(
            id="cascade",
            when=(PredAtom("missing", [x]), CmpAtom("eq", x, Const(2))),
            ports={"x": x},
        )
        plan = _lower_application_rule(rule, head=rule)
        seed_name = plan.occurrence_map[0].port_bindings[0].alias_local_execution_var.name

        result = probe_native(plan, {seed_name: 2}, {"missing": []})

        path = result.paths[0]
        atoms = path.rules[1].atoms
        self.assertEqual(path.status, "fails")
        self.assertIsInstance(atoms[0].verdict, Fails)
        self.assertIsInstance(atoms[1].verdict, Holds)

    def test_downstream_bind_atom_after_failed_upstream_is_not_reached_when_unbound(self) -> None:
        x = Var("$x")
        y = Var("$y")
        rule = Rule(
            id="cascade_bind",
            when=(PredAtom("missing", [x]), PredAtom("q", [y])),
            ports={"x": x, "y": y},
        )
        plan = _lower_application_rule(rule, head=rule)
        x_seed_name = next(
            binding.alias_local_execution_var.name
            for binding in plan.occurrence_map[0].port_bindings
            if binding.port_name == "x"
        )
        y_seed_name = next(
            binding.alias_local_execution_var.name
            for binding in plan.occurrence_map[0].port_bindings
            if binding.port_name == "y"
        )

        result = probe_native(plan, {x_seed_name: 1}, {"missing": [], "q": [(2,)]})

        path = result.paths[0]
        atoms = path.rules[1].atoms
        self.assertEqual(path.status, "fails")
        self.assertIsInstance(atoms[0].verdict, Fails)
        self.assertIsInstance(atoms[1].verdict, NotReached)
        self.assertEqual(atoms[1].verdict.blocked_by, y_seed_name)

    def test_exhaustive_verdict_advances_bind_atom_after_failed_filter(self) -> None:
        user = Var("$user")
        age = Var("$age")
        region = Var("$region")
        rule = Rule(
            id="senior_region",
            when=(
                PredAtom("age", [user, age]),
                CmpAtom("ge", age, Const(65)),
                PredAtom("region", [user, region]),
                CmpAtom("eq", region, Const("us")),
            ),
            ports={"user": user, "age": age, "region": region},
        )
        plan = _lower_application_rule(rule, head=rule)
        user_seed_name = next(
            binding.alias_local_execution_var.name
            for binding in plan.occurrence_map[0].port_bindings
            if binding.port_name == "user"
        )

        result = probe_native(
            plan,
            {user_seed_name: "u-1"},
            {"age": [("u-1", 30), ("u-2", 70)], "region": [("u-1", "us"), ("u-2", "eu")]},
        )

        path = result.paths[0]
        atoms = path.rules[1].atoms
        self.assertEqual(path.status, "fails")
        self.assertIsInstance(atoms[0].verdict, Holds)
        self.assertIsInstance(atoms[1].verdict, Fails)
        self.assertIsInstance(atoms[2].verdict, Holds)
        self.assertIsInstance(atoms[3].verdict, Holds)
        text = "\n".join(atom.repr_text or "" for atom in atoms)
        self.assertIn("region(u-1, us)", text)
        self.assertIn("us equals us", text)
        self.assertNotIn("u-2", text)
        self.assertNotIn("eu", text)

    def test_exhaustive_verdict_is_order_independent_after_failed_filter(self) -> None:
        user = Var("$user")
        age = Var("$age")
        region = Var("$region")
        facts = {"age": [("u-1", 30)], "region": [("u-1", "us")]}

        before_fail = Rule(
            id="region_before_fail",
            when=(
                PredAtom("age", [user, age]),
                PredAtom("region", [user, region]),
                CmpAtom("ge", age, Const(65)),
                CmpAtom("eq", region, Const("us")),
            ),
            ports={"user": user, "age": age, "region": region},
        )
        after_fail = Rule(
            id="region_after_fail",
            when=(
                PredAtom("age", [user, age]),
                CmpAtom("ge", age, Const(65)),
                PredAtom("region", [user, region]),
                CmpAtom("eq", region, Const("us")),
            ),
            ports={"user": user, "age": age, "region": region},
        )

        def run(rule: Rule) -> tuple[type[object], type[object], str]:
            plan = _lower_application_rule(rule, head=rule)
            user_seed_name = next(
                binding.alias_local_execution_var.name
                for binding in plan.occurrence_map[0].port_bindings
                if binding.port_name == "user"
            )
            result = probe_native(plan, {user_seed_name: "u-1"}, facts)
            atoms = result.paths[0].rules[1].atoms
            region_atom = next(atom for atom in atoms if atom.repr_text == "region(u-1, us)")
            eq_atom = next(atom for atom in atoms if atom.repr_text == "us equals us")
            return type(region_atom.verdict), type(eq_atom.verdict), result.paths[0].status

        self.assertEqual(run(before_fail), (Holds, Holds, "fails"))
        self.assertEqual(run(after_fail), (Holds, Holds, "fails"))

    def test_exhaustive_verdict_does_not_free_enumerate_key_unbound_predicate(self) -> None:
        user = Var("$user")
        region = Var("$region")
        rule = Rule(
            id="key_unbound_after_fail",
            when=(
                CmpAtom("eq", Const("no"), Const("yes")),
                PredAtom("region", [user, region]),
            ),
            ports={"user": user, "region": region},
        )
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(plan, {}, {"region": [("u-1", "us"), ("u-2", "eu")]})

        path = result.paths[0]
        atoms = path.rules[1].atoms
        self.assertEqual(path.status, "fails")
        self.assertIsInstance(atoms[0].verdict, Fails)
        self.assertIsInstance(atoms[1].verdict, NotReached)
        self.assertNotIn("u-1", atoms[1].repr_text or "")
        self.assertNotIn("u-2", atoms[1].repr_text or "")

    def test_or_branches_are_exhaustive_paths(self) -> None:
        x = Var("$x")
        left = Rule(id="left", when=(PredAtom("left_p", [x]),), ports={"x": x})
        right = Rule(id="right", when=(PredAtom("right_p", [x]),), ports={"x": x})
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=left)

        result = probe_native(plan, {}, {"left_p": [(1,)], "right_p": []})

        self.assertEqual(tuple(path.status for path in result.paths), ("holds", "fails"))
        self.assertIsInstance(result.paths[0].rules[1].atoms[0].verdict, Holds)

    def test_fact_repr_baking_uses_schema_template_and_entity_renderer(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = EntityRef("DisplayUser", {"user_id": "u-1"})
        calls: list[tuple[str, dict[str, object]]] = []
        original = prober_module.schema_runtime.render_entity_repr

        def spy_render_entity_repr(index, entity_type, identity_values):  # type: ignore[no-untyped-def]
            calls.append((entity_type, dict(identity_values)))
            return original(index, entity_type, identity_values)

        prober_module.schema_runtime.render_entity_repr = spy_render_entity_repr
        try:
            result = probe_native(
                plan,
                {},
                {"display_user:country": [(user_ref, "US")]},
                schema_index=schema_index,
            )
        finally:
            prober_module.schema_runtime.render_entity_repr = original

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "User u-1 lives in US")
        self.assertEqual(calls, [("DisplayUser", {"user_id": "u-1"})])

    def test_fact_repr_baking_recovers_bound_idref_identity_from_visible_facts(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        identity_pred_id = entity_info(schema_index, "DisplayUser").identity_predicates["user_id"].pred_id
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id

        result = probe_native(
            plan,
            {},
            {
                identity_pred_id: [(user_ref, "u-1")],
                country_pred_id: [(user_ref, "US")],
            },
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "User u-1 lives in US")
        self.assertNotIn(user_ref, atom.repr_text or "")

    def test_fact_repr_baking_falls_back_when_bound_idref_identity_is_not_visible(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id

        result = probe_native(
            plan,
            {},
            {country_pred_id: [(user_ref, "US")]},
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, f"{user_ref} lives in US")

    def test_not_atom_single_inner_renders_friendly_negated_repr_and_preserves_verdict(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")
            blocked: str = Field(repr="%ENT is blocked for %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="unblocked_user",
            when=(
                PredAtom("display_user:country", [user, country]),
                NotAtom(AndExpr([PredAtom("display_user:blocked", [user, Const("yes")])])),
            ),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        identity_pred_id = entity_info(schema_index, "DisplayUser").identity_predicates["user_id"].pred_id
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id
        blocked_pred_id = field_predicate(schema_index, "DisplayUser", "blocked").pred_id

        base_facts = {
            identity_pred_id: [(user_ref, "u-1")],
            country_pred_id: [(user_ref, "US")],
        }
        holds_result = probe_native(
            plan,
            {},
            {**base_facts, blocked_pred_id: []},
            schema_index=schema_index,
        )
        fails_result = probe_native(
            plan,
            {},
            {**base_facts, blocked_pred_id: [(user_ref, "yes")]},
            schema_index=schema_index,
        )

        holds_atom = _negated_atoms(holds_result)[0]
        fails_atom = _negated_atoms(fails_result)[0]
        self.assertIsInstance(holds_atom.verdict, Holds)
        self.assertIsInstance(fails_atom.verdict, Fails)
        self.assertEqual(holds_atom.repr_text, "!User u-1 is blocked for yes")
        self.assertEqual(fails_atom.repr_text, "!User u-1 is blocked for yes")
        self.assertNotIn("[", holds_atom.repr_text or "")
        self.assertNotIn("$", holds_atom.repr_text or "")

    def test_not_atom_and_body_groups_inner_repr_without_raw_tuple_text(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            age: int = Field(repr="%ENT is age %FLD")
            blocked: str = Field(repr="%ENT is blocked for %FLD")

        user = Var("$user")
        age = Var("$age")
        rule = Rule(
            id="not_blocked_adult",
            when=(
                PredAtom("display_user:age", [user, age]),
                NotAtom(
                    AndExpr(
                        [
                            PredAtom("display_user:blocked", [user, Const("yes")]),
                            CmpAtom("ge", age, Const(18)),
                        ]
                    )
                ),
            ),
            ports={"user": user, "age": age},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        identity_pred_id = entity_info(schema_index, "DisplayUser").identity_predicates["user_id"].pred_id
        age_pred_id = field_predicate(schema_index, "DisplayUser", "age").pred_id
        blocked_pred_id = field_predicate(schema_index, "DisplayUser", "blocked").pred_id

        result = probe_native(
            plan,
            {},
            {
                identity_pred_id: [(user_ref, "u-1")],
                age_pred_id: [(user_ref, 20)],
                blocked_pred_id: [],
            },
            schema_index=schema_index,
        )

        atom = _negated_atoms(result)[0]
        self.assertIsInstance(atom.verdict, Holds)
        self.assertEqual(atom.repr_text, "!(User u-1 is blocked for yes && 20 >= 18)")
        self.assertNotIn("[", atom.repr_text or "")
        self.assertNotIn("'", atom.repr_text or "")
        self.assertNotIn("$", atom.repr_text or "")

    def test_not_atom_or_of_and_body_renders_stable_grouped_repr(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")
            blocked: str = Field(repr="%ENT is blocked for %FLD")
            flag: str = Field(repr="%ENT has flag %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="not_blocked_or_flagged",
            when=(
                PredAtom("display_user:country", [user, country]),
                NotAtom(
                    OrExpr(
                        [
                            AndExpr(
                                [
                                    PredAtom("display_user:blocked", [user, Const("yes")]),
                                    PredAtom("display_user:flag", [user, Const("review")]),
                                ]
                            ),
                            AndExpr([PredAtom("display_user:blocked", [user, Const("no")])]),
                        ]
                    )
                ),
            ),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        identity_pred_id = entity_info(schema_index, "DisplayUser").identity_predicates["user_id"].pred_id
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id
        blocked_pred_id = field_predicate(schema_index, "DisplayUser", "blocked").pred_id
        flag_pred_id = field_predicate(schema_index, "DisplayUser", "flag").pred_id

        result = probe_native(
            plan,
            {},
            {
                identity_pred_id: [(user_ref, "u-1")],
                country_pred_id: [(user_ref, "US")],
                blocked_pred_id: [],
                flag_pred_id: [],
            },
            schema_index=schema_index,
        )

        atom = _negated_atoms(result)[0]
        self.assertIsInstance(atom.verdict, Holds)
        self.assertEqual(
            atom.repr_text,
            "!((User u-1 is blocked for yes && User u-1 has flag review) || User u-1 is blocked for no)",
        )
        self.assertNotIn("[", atom.repr_text or "")
        self.assertNotIn("'", atom.repr_text or "")
        self.assertNotIn("$", atom.repr_text or "")

    def test_repr_baking_has_fallbacks_for_fact_compare_and_builtin(self) -> None:
        x = Var("$x")
        rule = Rule(
            id="fallbacks",
            when=(
                PredAtom("p", [x]),
                CmpAtom("gt", x, Const(1)),
                InAtom(x, [Const(2), Const(3)]),
            ),
            ports={"x": x},
        )
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(plan, {}, {"p": [(2,)]}, schema_index=None)

        atoms = result.paths[0].rules[1].atoms
        self.assertEqual(atoms[0].repr_text, "p(2)")
        self.assertEqual(atoms[1].repr_text, "2 > 1")
        self.assertEqual(atoms[2].repr_text, "2 is in (2, 3)")

    def test_fact_field_entity_ref_uses_shared_renderer_for_cross_type_label(self) -> None:
        class Dept(Entity):
            class Meta:
                repr = "Dept %dept_id"

            dept_id: str = Identity()

        class Employee(Entity):
            class Meta:
                repr = "Employee %emp_id"

            emp_id: str = Identity()
            dept: Dept = Field(repr="%ENT dept %FLD")

        employee = Var("$employee")
        dept = Var("$dept")
        schema_index = build_schema_index(compile_schema_from_classes([Dept, Employee]))
        employee_ref = encode_entity_ref(EntityRef("Employee", {"emp_id": "e-1"}), index=schema_index)
        dept_ref = encode_entity_ref(EntityRef("Dept", {"dept_id": "d-1"}), index=schema_index)
        employee_info = entity_info(schema_index, "Employee")
        dept_info = entity_info(schema_index, "Dept")
        dept_pred_id = field_predicate(schema_index, "Employee", "dept").pred_id
        rule = Rule(id="employee_dept", when=(PredAtom(dept_pred_id, [employee, dept]),), ports={"employee": employee, "dept": dept})
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(
            plan,
            {},
            {
                employee_info.identity_predicates["emp_id"].pred_id: [(employee_ref, "e-1")],
                dept_info.identity_predicates["dept_id"].pred_id: [(dept_ref, "d-1")],
                dept_pred_id: [(employee_ref, dept_ref)],
            },
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "Employee e-1 dept Dept d-1")
        self.assertNotIn(employee_ref, atom.repr_text or "")
        self.assertNotIn(dept_ref, atom.repr_text or "")

    def test_compare_entity_refs_use_shared_renderer(self) -> None:
        class Dept(Entity):
            class Meta:
                repr = "Dept %dept_id"

            dept_id: str = Identity()

        class Employee(Entity):
            emp_id: str = Identity()
            dept: Dept = Field()

        employee = Var("$employee")
        dept = Var("$dept")
        schema_index = build_schema_index(compile_schema_from_classes([Dept, Employee]))
        employee_ref = encode_entity_ref(EntityRef("Employee", {"emp_id": "e-1"}), index=schema_index)
        dept_ref = encode_entity_ref(EntityRef("Dept", {"dept_id": "d-1"}), index=schema_index)
        dept_info = entity_info(schema_index, "Dept")
        dept_pred_id = field_predicate(schema_index, "Employee", "dept").pred_id
        rule = Rule(
            id="employee_dept_check",
            when=(PredAtom(dept_pred_id, [employee, dept]), CmpAtom("eq", dept, Const(dept_ref))),
            ports={"employee": employee, "dept": dept},
        )
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(
            plan,
            {},
            {
                dept_info.identity_predicates["dept_id"].pred_id: [(dept_ref, "d-1")],
                dept_pred_id: [(employee_ref, dept_ref)],
            },
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[1]
        self.assertEqual(atom.repr_text, "Dept d-1 equals Dept d-1")
        self.assertNotIn(dept_ref, atom.repr_text or "")

    def test_float64_hex_uses_display_text_in_fact_and_compare(self) -> None:
        class Measurement(Entity):
            sensor_id: str = Identity()
            reading: float = Field(repr="reading %FLD")

        sensor = Var("$sensor")
        reading = Var("$reading")
        schema_index = build_schema_index(compile_schema_from_classes([Measurement]))
        sensor_ref = encode_entity_ref(EntityRef("Measurement", {"sensor_id": "s-1"}), index=schema_index)
        reading_pred_id = field_predicate(schema_index, "Measurement", "reading").pred_id
        rule = Rule(
            id="measurement_reading",
            when=(PredAtom(reading_pred_id, [sensor, reading]), CmpAtom("eq", reading, Const("0x3ff8000000000000"))),
            ports={"sensor": sensor, "reading": reading},
        )
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(
            plan,
            {},
            {reading_pred_id: [(sensor_ref, "0x3ff8000000000000")]},
            schema_index=schema_index,
        )

        atoms = result.paths[0].rules[1].atoms
        self.assertEqual(atoms[0].repr_text, "reading 1.5")
        self.assertEqual(atoms[1].repr_text, "1.5 equals 1.5")

    def test_string_field_that_looks_like_float64_hex_is_not_decoded(self) -> None:
        class Label(Entity):
            label_id: str = Identity()
            code: str = Field(repr="code %FLD")

        subject = Var("$subject")
        code = Var("$code")
        schema_index = build_schema_index(compile_schema_from_classes([Label]))
        subject_ref = encode_entity_ref(EntityRef("Label", {"label_id": "l-1"}), index=schema_index)
        code_pred_id = field_predicate(schema_index, "Label", "code").pred_id
        rule = Rule(id="label_code", when=(PredAtom(code_pred_id, [subject, code]),), ports={"subject": subject, "code": code})
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(
            plan,
            {},
            {code_pred_id: [(subject_ref, "0x3ff8000000000000")]},
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "code 0x3ff8000000000000")

    def test_fact_repr_does_not_reinterpret_field_values_as_placeholders(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            note: str = Field(repr="%FLD / %ENT")

        user = Var("$user")
        note = Var("$note")
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        user_info = entity_info(schema_index, "DisplayUser")
        note_pred_id = field_predicate(schema_index, "DisplayUser", "note").pred_id
        rule = Rule(id="user_note", when=(PredAtom(note_pred_id, [user, note]),), ports={"user": user, "note": note})
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(
            plan,
            {},
            {
                user_info.identity_predicates["user_id"].pred_id: [(user_ref, "u-1")],
                note_pred_id: [(user_ref, "%ENT")],
            },
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "%ENT / User u-1")


if __name__ == "__main__":
    unittest.main()
