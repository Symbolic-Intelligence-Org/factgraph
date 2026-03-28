"""Tests for WhereIR -> PyReason rule syntax compiler."""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from factpy_kernel.adapters.pyreason.where_compile import (
    PyReasonWhereCompileError,
    _clean_var,
    _pred_short_name,
    _validate_atom,
    compile_where_ir_to_pyreason,
)
from factpy_kernel.core.store.types import EngineExtBase


@dataclass(frozen=True)
class MockPyReasonRuleExt(EngineExtBase):
    timestep_delay: int = 0
    body_predicate_bounds: dict[str, tuple[float, float] | list[float]] = field(default_factory=dict)
    head_bound: tuple[float, float] | list[float] | None = None


def _test_schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {"pred_id": "user:popular", "arity": 2},
            {"pred_id": "user:tag", "arity": 2},
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
        ],
    }


class CompileWhereIRTests(unittest.TestCase):
    def test_single_pred_atom(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            schema_ir=_test_schema_ir(),
        )
        self.assertEqual(len(rules), 1)
        rule_str, rule_name = rules[0]
        self.assertEqual(rule_str, "popular(e) <-0 name(e)")
        self.assertEqual(rule_name, "derived_popular")

    def test_multiple_body_atoms(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[
                ("pred", "user:name", ["$e", "$v"]),
                ("pred", "user:tag", ["$e", "$t"]),
            ],
            schema_ir=_test_schema_ir(),
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0][0], "popular(e) <-0 name(e), tag(e)")

    def test_relationship_pred_emits_two_entity_vars(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$x"],
            where=[
                ("pred", "friends:strength", ["$x", "$y", "$v"]),
                ("pred", "user:popular", ["$y", "$p"]),
            ],
            schema_ir=_test_schema_ir(),
        )
        self.assertEqual(rules[0][0], "popular(x) <-0 strength(x, y), popular(y)")

    def test_relationship_target_uses_two_head_terms(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="friends:strength",
            head_vars=["$x", "$y", "$value"],
            where=[("pred", "user:popular", ["$x", "$p"])],
            schema_ir=_test_schema_ir(),
        )
        self.assertEqual(rules[0][0], "strength(x, y) <-0 popular(x)")

    def test_timestep_delay_from_engine_ext(self) -> None:
        ext = MockPyReasonRuleExt(timestep_delay=2)
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            schema_ir=_test_schema_ir(),
            engine_ext=ext,
        )
        self.assertEqual(rules[0][0], "popular(e) <-2 name(e)")

    def test_body_predicate_bounds_from_engine_ext(self) -> None:
        ext = MockPyReasonRuleExt(body_predicate_bounds={"user:name": (0.5, 1.0)})
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            schema_ir=_test_schema_ir(),
            engine_ext=ext,
        )
        self.assertEqual(rules[0][0], "popular(e) <-0 name(e) : [0.5, 1.0]")

    def test_head_bound_from_engine_ext(self) -> None:
        ext = MockPyReasonRuleExt(head_bound=(0.8, 0.9))
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[("pred", "user:name", ["$e", "$v"])],
            schema_ir=_test_schema_ir(),
            engine_ext=ext,
        )
        self.assertEqual(rules[0][0], "popular(e) : [0.8, 0.9] <-0 name(e)")

    def test_attribute_existence_model_skips_value_var(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e", "$value"],
            where=[("pred", "user:name", ["$e", "$name_val"])],
            schema_ir=_test_schema_ir(),
        )
        rule_str, _ = rules[0]
        self.assertEqual(rule_str, "popular(e) <-0 name(e)")
        self.assertNotIn("value", rule_str)
        self.assertNotIn("name_val", rule_str)

    def test_branch_group_compiles_to_multiple_rules(self) -> None:
        rules = compile_where_ir_to_pyreason(
            target_pred_id="user:popular",
            head_vars=["$e"],
            where=[
                [("pred", "user:name", ["$e", "$v"])],
                [("pred", "user:tag", ["$e", "$t"])],
            ],
            schema_ir=_test_schema_ir(),
        )
        self.assertEqual(
            rules,
            [
                ("popular(e) <-0 name(e)", "derived_popular_b0"),
                ("popular(e) <-0 tag(e)", "derived_popular_b1"),
            ],
        )


class AtomValidationTests(unittest.TestCase):
    def test_pred_atom_accepted(self) -> None:
        _validate_atom(("pred", "user:name", ["$e", "$v"]))

    def test_eq_atom_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            _validate_atom(("eq", "$x", "Alice"))
        self.assertIn("Equality", str(ctx.exception))

    def test_not_atom_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            _validate_atom(("not", [("pred", "user:name", ["$e", "$v"])]))
        self.assertIn("Negation", str(ctx.exception))

    def test_ruleref_atom_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            _validate_atom(("ruleref", "rule_1", "v1", ["$e"]))
        self.assertIn("Rule references", str(ctx.exception))

    def test_unknown_atom_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            _validate_atom(("aggregate", "count", ["$e"]))
        self.assertIn("not supported", str(ctx.exception))

    def test_empty_atom_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError):
            _validate_atom(())

    def test_empty_where_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError):
            compile_where_ir_to_pyreason(
                target_pred_id="user:popular",
                head_vars=["$e"],
                where=[],
                schema_ir=_test_schema_ir(),
            )

    def test_invalid_term_type_rejected(self) -> None:
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            compile_where_ir_to_pyreason(
                target_pred_id="user:popular",
                head_vars=["$e"],
                where=[("pred", "user:name", ["$e", True])],
                schema_ir=_test_schema_ir(),
            )
        self.assertIn("Unsupported term type", str(ctx.exception))

    def test_invalid_body_predicate_bounds_rejected(self) -> None:
        ext = MockPyReasonRuleExt(body_predicate_bounds={"user:name": (1.2, 1.0)})
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            compile_where_ir_to_pyreason(
                target_pred_id="user:popular",
                head_vars=["$e"],
                where=[("pred", "user:name", ["$e", "$v"])],
                schema_ir=_test_schema_ir(),
                engine_ext=ext,
            )
        self.assertIn("body_predicate_bounds", str(ctx.exception))

    def test_invalid_head_bound_rejected(self) -> None:
        ext = MockPyReasonRuleExt(head_bound=(1.2, 1.0))
        with self.assertRaises(PyReasonWhereCompileError) as ctx:
            compile_where_ir_to_pyreason(
                target_pred_id="user:popular",
                head_vars=["$e"],
                where=[("pred", "user:name", ["$e", "$v"])],
                schema_ir=_test_schema_ir(),
                engine_ext=ext,
            )
        self.assertIn("head_bound", str(ctx.exception))


class HelperTests(unittest.TestCase):
    def test_pred_short_name(self) -> None:
        self.assertEqual(_pred_short_name("user:name"), "name")
        self.assertEqual(_pred_short_name("friends:strength"), "strength")
        self.assertEqual(_pred_short_name("no_colon"), "no_colon")

    def test_clean_var(self) -> None:
        self.assertEqual(_clean_var("$e"), "e")
        self.assertEqual(_clean_var("$X"), "X")
        self.assertEqual(_clean_var("plain"), "plain")


if __name__ == "__main__":
    unittest.main()
