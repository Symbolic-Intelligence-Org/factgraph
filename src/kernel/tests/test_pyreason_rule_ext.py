"""Tests for PyReason rule extensions and compile helper."""
from __future__ import annotations

import sys
import types
import unittest
import warnings
from unittest.mock import patch

from kernel.adapters.pyreason.rule_ext import (
    PyReasonCompileError,
    PyReasonFactDef,
    PyReasonRuleExt,
    compile_pyreason_rule,
)
from kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.store.types import EngineExtBase
from kernel.sdk.dsl.errors import SDKDSLError
from kernel.sdk.dsl.expr import CompareExpr, HeadCall, LogicVar, Pred
from kernel.sdk.dsl.rule import Rule


x = LogicVar("x")
y = LogicVar("y")
z = LogicVar("z")


def _test_schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {"pred_id": "user:popular", "arity": 2},
            {"pred_id": "user:outdoorsy", "arity": 2},
            {"pred_id": "pet:dog_breed", "arity": 2},
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
            {
                "pred_id": "owns:since",
                "arity": 3,
                "relationship_type": "Owns",
                "from_entity_type": "User",
                "to_entity_type": "Pet",
            },
        ],
    }


class RuleExtTests(unittest.TestCase):
    def test_default_delay(self) -> None:
        ext = PyReasonRuleExt()
        self.assertEqual(ext.timestep_delay, 0)

    def test_custom_delay(self) -> None:
        ext = PyReasonRuleExt(timestep_delay=2)
        self.assertEqual(ext.timestep_delay, 2)

    def test_rejects_negative_delay(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonRuleExt(timestep_delay=-1)

    def test_rejects_bool_delay(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonRuleExt(timestep_delay=True)

    def test_accepts_body_predicate_bounds(self) -> None:
        ext = PyReasonRuleExt(body_predicate_bounds={"user:popular": (0.5, 1.0)})
        self.assertEqual(ext.body_predicate_bounds["user:popular"], (0.5, 1.0))

    def test_accepts_head_bound(self) -> None:
        ext = PyReasonRuleExt(head_bound=(0.8, 0.9))
        self.assertEqual(tuple(ext.head_bound or ()), (0.8, 0.9))

    def test_rejects_invalid_body_predicate_bounds(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonRuleExt(body_predicate_bounds={"user:popular": (1.1, 1.0)})

    def test_rejects_invalid_head_bound(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonRuleExt(head_bound=(1.1, 1.0))

    def test_frozen(self) -> None:
        ext = PyReasonRuleExt(timestep_delay=1)
        with self.assertRaises(AttributeError):
            ext.timestep_delay = 2


class FactDefTests(unittest.TestCase):
    def test_basic(self) -> None:
        fact = PyReasonFactDef(atom="popular(Alice)", name="alice_pop", start=0, end=3)
        self.assertEqual(fact.atom, "popular(Alice)")
        self.assertEqual(fact.name, "alice_pop")

    def test_defaults(self) -> None:
        fact = PyReasonFactDef(atom="popular(Alice)", name="test")
        self.assertEqual(fact.start, 0)
        self.assertEqual(fact.end, 0)
        self.assertEqual(tuple(fact.bound), (1.0, 1.0))

    def test_rejects_empty_atom(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonFactDef(atom="", name="test")

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonFactDef(atom="popular(Alice)", name="")

    def test_rejects_invalid_bound(self) -> None:
        with self.assertRaises(ValueError):
            PyReasonFactDef(atom="popular(Alice)", name="test", bound=[0.9, 0.2])


class CompileRuleTests(unittest.TestCase):
    def test_simple_rule(self) -> None:
        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )
        rule_str, name = compile_pyreason_rule(rule)
        self.assertEqual(name, "friend_pop")
        self.assertEqual(rule_str, "popular(x) <-1 popular(y), strength(x, y)")

    def test_delay_zero(self) -> None:
        rule = Rule(
            id="immediate",
            version="1.0",
            select=[Pred("user:outdoorsy", x)],
            where=[Pred("owns:since", x, y), Pred("pet:dog_breed", y)],
            engine_ext=PyReasonRuleExt(timestep_delay=0),
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "outdoorsy(x) <-0 since(x, y), dog_breed(y)")

    def test_multi_body_atoms(self) -> None:
        rule = Rule(
            id="r1",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[
                Pred("user:popular", y),
                Pred("friends:strength", x, y),
                Pred("owns:since", y, z),
                Pred("owns:since", x, z),
            ],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(
            rule_str,
            "popular(x) <-1 popular(y), strength(x, y), since(y, z), since(x, z)",
        )

    def test_body_predicate_bounds_compile_to_interval_suffix(self) -> None:
        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(
                timestep_delay=1,
                body_predicate_bounds={"user:popular": (0.5, 1.0)},
            ),
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "popular(x) <-1 popular(y) : [0.5, 1.0], strength(x, y)")

    def test_head_bound_compile_to_head_interval_suffix(self) -> None:
        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(
                timestep_delay=1,
                head_bound=(0.8, 0.9),
            ),
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "popular(x) : [0.8, 0.9] <-1 popular(y), strength(x, y)")

    def test_string_literal_in_term(self) -> None:
        rule = Rule(
            id="r2",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:name", x, "Alice")],
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertIn("name(x, Alice)", rule_str)

    def test_headcall_head_supported(self) -> None:
        rule = Rule(
            id="headcall_rule",
            version="1.0",
            select=[
                HeadCall(
                    callee_kind="pred_ref",
                    entity_type="User",
                    field="popular",
                    kwargs={"record": x},
                )
            ],
            where=[Pred("user:popular", y)],
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "popular(x) <-0 popular(y)")

    def test_rejects_unsupported_atom(self) -> None:
        rule = Rule(
            id="bad",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[CompareExpr("eq", x, y)],
        )
        with self.assertRaises(PyReasonCompileError) as ctx:
            compile_pyreason_rule(rule)
        self.assertIn("CompareExpr", str(ctx.exception))

    def test_rejects_empty_where(self) -> None:
        with self.assertRaises(SDKDSLError):
            Rule(id="bad", version="1.0", select=[Pred("user:popular", x)], where=[])

    def test_pred_id_without_colon(self) -> None:
        rule = Rule(
            id="r3",
            version="1.0",
            select=[Pred("popular", x)],
            where=[Pred("popular", y)],
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "popular(x) <-0 popular(y)")

    def test_rule_without_engine_ext_uses_default_pyreason_ext(self) -> None:
        rule = Rule(
            id="r4",
            version="1.0",
            select=[Pred("popular", x)],
            where=[Pred("popular", y)],
        )
        rule_str, _ = compile_pyreason_rule(rule)
        self.assertEqual(rule_str, "popular(x) <-0 popular(y)")

    def test_rejects_rule_with_wrong_engine_ext_type(self) -> None:
        class OtherExt(EngineExtBase):
            pass

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y)],
            engine_ext=OtherExt(),
        )
        with self.assertRaises(PyReasonCompileError) as ctx:
            compile_pyreason_rule(rule)
        self.assertIn("PyReasonRuleExt", str(ctx.exception))


class RunnerTypedDefTests(unittest.TestCase):
    def _fake_pyreason(self) -> tuple[types.SimpleNamespace, list[object], list[object], list[object], list[None]]:
        added_rules: list[object] = []
        added_facts: list[object] = []
        loaded_graphs: list[object] = []
        reset_calls: list[None] = []

        class MockInterpretation:
            def get_dict(self) -> dict[int, dict[str, dict[str, tuple[float, float]]]]:
                return {}

        fake_pyreason = types.SimpleNamespace(
            reset=lambda: reset_calls.append(None),
            load_graph=lambda graph: loaded_graphs.append(graph),
            add_rule=lambda rule: added_rules.append(rule),
            add_fact=lambda fact: added_facts.append(fact),
            reason=lambda *, timesteps: MockInterpretation(),
            settings=types.SimpleNamespace(atom_trace=False),
            Rule=lambda body, name: ("rule", body, name),
            Fact=lambda atom, name, start, end: ("fact", atom, name, start, end),
        )
        return fake_pyreason, added_rules, added_facts, loaded_graphs, reset_calls

    def test_run_pyreason_accepts_rule_objects_and_fact_defs(self) -> None:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:name", "Alice", "Alice", bound=[1.0, 1.0])
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9", bound=[0.8, 0.9])

        fake_pyreason, added_rules, added_facts, loaded_graphs, reset_calls = self._fake_pyreason()

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(timestep_delay=1, head_bound=(0.8, 0.9)),
        )
        fact_def = PyReasonFactDef(atom="popular(Alice)", name="alice_pop", start=0, end=3, bound=[0.4, 0.6])

        with patch.dict(sys.modules, {"pyreason": fake_pyreason}):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = run_pyreason(
                    session,
                    rule_defs=[rule],
                    fact_defs=[fact_def],
                    config=PyReasonRunConfig(timesteps=2, atom_trace=False),
                )

        self.assertEqual(len(loaded_graphs), 1)
        self.assertEqual(loaded_graphs[0].edges["Alice", "Bob"]["strength"], 0.8)
        self.assertEqual(
            added_rules,
            [("rule", "popular(x) : [0.8, 0.9] <-1 popular(y), strength(x, y)", "friend_pop")],
        )
        self.assertEqual(
            added_facts,
            [
                ("fact", "name(Alice) : [1.0, 1.0]", "session_node_0", 0, 2),
                ("fact", "popular(Alice) : [0.4, 0.6]", "alice_pop", 0, 3),
            ],
        )
        self.assertEqual(result.config.timesteps, 2)
        self.assertEqual(reset_calls, [None, None])

    def test_run_pyreason_warns_for_bounded_node_seeds_with_rules(self) -> None:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[0.4, 0.6])
        fake_pyreason, _, _, _, _ = self._fake_pyreason()

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )

        with patch.dict(sys.modules, {"pyreason": fake_pyreason}):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_pyreason(
                    session,
                    rule_defs=[rule],
                    config=PyReasonRunConfig(timesteps=2, atom_trace=False),
                )

        self.assertEqual(len(caught), 1)
        self.assertIn("implicit [1.0, 1.0] interval threshold", str(caught[0].message))
        self.assertIn("explicit clause bounds", str(caught[0].message))

    def test_run_pyreason_warns_for_bounded_fact_defs_with_rules(self) -> None:
        session = PyReasonSession(_test_schema_ir())
        fake_pyreason, _, _, _, _ = self._fake_pyreason()

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )
        fact_def = PyReasonFactDef(atom="popular(Alice)", name="alice_pop", start=0, end=3, bound=[0.4, 0.6])

        with patch.dict(sys.modules, {"pyreason": fake_pyreason}):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_pyreason(
                    session,
                    rule_defs=[rule],
                    fact_defs=[fact_def],
                    config=PyReasonRunConfig(timesteps=2, atom_trace=False),
                )

        self.assertEqual(len(caught), 1)
        self.assertIn("fact_def:alice_pop=(0.4, 0.6)", str(caught[0].message))

    def test_run_pyreason_does_not_warn_when_rule_has_explicit_body_interval(self) -> None:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[0.4, 0.6])
        fake_pyreason, _, _, _, _ = self._fake_pyreason()

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(
                timestep_delay=1,
                body_predicate_bounds={"user:popular": (0.4, 1.0)},
            ),
        )

        with patch.dict(sys.modules, {"pyreason": fake_pyreason}):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_pyreason(
                    session,
                    rule_defs=[rule],
                    config=PyReasonRunConfig(timesteps=2, atom_trace=False),
                )

        self.assertEqual(caught, [])

    def test_run_pyreason_does_not_warn_for_boolean_seeds(self) -> None:
        session = PyReasonSession(_test_schema_ir())
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[1.0, 1.0])
        fake_pyreason, _, _, _, _ = self._fake_pyreason()

        rule = Rule(
            id="friend_pop",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[Pred("user:popular", y), Pred("friends:strength", x, y)],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )

        with patch.dict(sys.modules, {"pyreason": fake_pyreason}):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                run_pyreason(
                    session,
                    rule_defs=[rule],
                    config=PyReasonRunConfig(timesteps=2, atom_trace=False),
                )

        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
