"""One rule surface: both rule forms reach the same capability, with the same answer.

The capability runtimes take a ``CompiledDerivationPlan`` or a ``RuleSpec``. Only
the shells in front of them demanded the SDK DSL ``Inference`` / ``Rule``, which
closed the whole capability surface to the rule form the application layer
authors anyway.

Each test here states the same rule twice - once as an ``Inference``, once as an
application ``Rule`` - sends both through the same shell against the same real
store, and requires the answers to agree. Real store, real schema, real runtime;
the determinism comes from constructed data whose outcome is forced.
"""

from __future__ import annotations

import unittest

from factgraph.application.protocol import Rule as ApplicationRule
from factgraph.application.protocol import compile_derivation_plan
from factgraph.application.protocol.rule_expr import RuleExpr, RuleExprError
from factgraph.core.rules.where_ast import Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, Inference, Pred, SDKStore, SDKStoreError, vars
from factgraph.sdk.shells.check import sdk_check
from factgraph.sdk.shells.diagnose import sdk_diagnose
from factgraph.sdk.shells.fact_overlay import sdk_fact_overlay_check
from factgraph.sdk.shells.rule_add_condition import sdk_rule_add_condition
from factgraph.sdk.shells.rule_disable import sdk_rule_disable
from factgraph.sdk.shells.rule_literal_replace import sdk_rule_literal_replace
from factgraph.sdk.shells.why_not import sdk_why_not
from factgraph.sdk.dsl import Rule as DSLRule
from factgraph.application.protocol import AddedCondition, ConditionPath, FactOverlay


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


def _store() -> SDKStore:
    sdk = SDKStore([Person])
    for name, age, region in (("alice", 30, "us"), ("bob", 41, "eu")):
        ref = sdk.entities.ref(Person, name=name)
        sdk.fields.set(Person.age, ref, age)
        sdk.fields.set(Person.region, ref, region)
    return sdk


# --- the same rule, said twice ------------------------------------------------
def _as_inference() -> Inference:
    with vars("p", "age") as (p, age):
        return Inference(
            id="parity.age",
            version="v1",
            when=[Pred("person:age", p, age)],
            head=Person.age(value=age),
        )


_P = Var("$p")
_AGE = Var("$age")


def _as_rule() -> ApplicationRule:
    return ApplicationRule(
        id="parity_age_body",
        when=(PredAtom("person:age", [_P, _AGE]),),
        ports={"p": _P, "age": _AGE},
    )


def _head() -> ApplicationRule:
    """The conclusion the body supports: the same predicate the Inference heads."""
    return ApplicationRule(
        id="person:age",
        when=(PredAtom("person:age", [_P, _AGE]),),
        ports={"p": _P, "age": _AGE},
    )


def _binding(sdk: SDKStore, *, age: int, name: str = "alice") -> dict[str, object]:
    return {"$p": sdk.entities.ref(Person, name=name), "$age": age}


def _rule_binding(sdk: SDKStore, *, age: int, name: str = "alice") -> dict[str, object]:
    """The same binding, under the names the lowered plan gives the head ports.

    The two forms do not name the head variables identically, and that is a
    property of the forms rather than a defect: an ``Inference`` heads on its own
    variables, while a ``Rule`` body plus a separate head ``Rule`` is lowered with
    the head ports aliased so they cannot collide with the body occurrence. A
    caller binds by the plan's head variable names, which the plan reports.

    This helper does exactly what a consumer does, so the parity below compares
    answers rather than accidentally comparing variable spellings.
    """
    head = _head()
    plan = compile_derivation_plan(_as_rule(), head=head)
    by_port = dict(zip(head.ports, plan.heads[0].head_var_names, strict=True))
    return {
        by_port["p"]: sdk.entities.ref(Person, name=name),
        by_port["age"]: age,
    }


class RuleSurfaceParityTests(unittest.TestCase):
    # --- F1: the public lowering is the lowering that already runs ------------
    def test_compile_derivation_plan_matches_the_lowering_it_faces(self) -> None:
        from factgraph.application.protocol.rule_expr_lowering import (
            _lower_application_rule,
            _materialize_native_derivation_plan,
        )

        head = _head()
        direct, _traces = _materialize_native_derivation_plan(
            _lower_application_rule(_as_rule(), head=head)
        )
        through_facade = compile_derivation_plan(_as_rule(), head=head)

        self.assertEqual(through_facade.derivation_id, direct.derivation_id)
        self.assertEqual(through_facade.version, direct.version)
        self.assertEqual(through_facade.body_ir, direct.body_ir)
        self.assertEqual(through_facade.heads, direct.heads)

    def test_compile_derivation_plan_accepts_a_rule_expr(self) -> None:
        head = _head()
        expr = RuleExpr.all(_as_rule().as_("body"))
        plan = compile_derivation_plan(expr, head=head)
        self.assertEqual(len(plan.heads), 1)
        self.assertTrue(plan.body_ir)

    def test_compile_derivation_plan_rejects_anything_else(self) -> None:
        with self.assertRaises(RuleExprError):
            compile_derivation_plan(_as_inference(), head=_head())  # type: ignore[arg-type]

    # --- F2: the rule as the spec the rule runtime executes -------------------
    def test_to_rule_spec_names_the_rules_own_ports_and_body(self) -> None:
        spec = _as_rule().to_rule_spec()
        self.assertEqual(spec.rule_id, "parity_age_body")
        self.assertEqual(spec.version, "1.0")
        # Sorted by port name: "age" before "p".
        self.assertEqual(spec.select_vars, ["$age", "$p"])
        self.assertEqual(spec.where, [("pred", "person:age", ["$p", "$age"])])
        self.assertFalse(spec.expose)

    def test_to_rule_spec_keeps_an_explicit_version(self) -> None:
        rule = ApplicationRule(
            id="parity_age_body",
            when=(PredAtom("person:age", [_P, _AGE]),),
            ports={"p": _P, "age": _AGE},
            version="v7",
        )
        self.assertEqual(rule.to_rule_spec().version, "v7")

    def test_to_rule_spec_refuses_a_port_variable_the_runtime_cannot_bind(self) -> None:
        """A select variable without ``$`` would be unbound at run time.

        Prefixing it on one side only breaks the lookup; rewriting it on both
        sides would change the rule. So it is refused, with the reason.
        """
        bare = Var("p")
        rule = ApplicationRule(
            id="parity_bare_var",
            when=(PredAtom("person:age", [bare, _AGE]),),
            ports={"p": bare, "age": _AGE},
        )
        with self.assertRaises(Exception) as ctx:
            rule.to_rule_spec()
        self.assertIn("$", str(ctx.exception))

    def test_the_store_compiles_an_application_rule_like_any_other_rule(self) -> None:
        compiled = _store()._compile_rule_input(_as_rule())
        self.assertEqual(compiled["rule_id"], "parity_age_body")
        self.assertEqual(compiled["select_vars"], ["$age", "$p"])

    # --- F4: parity per shell -------------------------------------------------
    def _assert_same_answer(self, first: object, second: object) -> None:
        """The two forms must produce the same answer, field for field."""
        self.assertEqual(type(first), type(second))
        for field in ("status", "matched_count", "errors", "warnings", "rows", "notes"):
            if hasattr(first, field):
                with self.subTest(field=field):
                    self.assertEqual(getattr(first, field), getattr(second, field))

    def test_check_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        for age, expected in ((30, "passed"), (99, "failed")):
            with self.subTest(age=age):
                by_inference = sdk_check(sdk, _as_inference(), _binding(sdk, age=age))
                by_rule = sdk_check(
                    sdk, _as_rule(), _rule_binding(sdk, age=age), head=_head()
                )
                self.assertEqual(by_inference.status, expected)
                self._assert_same_answer(by_inference, by_rule)

    def test_diagnose_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        by_inference = sdk_diagnose(sdk, _as_inference(), _binding(sdk, age=30))
        by_rule = sdk_diagnose(sdk, _as_rule(), _rule_binding(sdk, age=30), head=_head())
        self._assert_same_answer(by_inference, by_rule)

    def test_why_not_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        by_inference = sdk_why_not(
            sdk, _as_inference(), [_binding(sdk, age=1, name="bob")]
        )
        by_rule = sdk_why_not(
            sdk, _as_rule(), [_rule_binding(sdk, age=1, name="bob")], head=_head()
        )
        self._assert_same_answer(by_inference, by_rule)

    def test_fact_overlay_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        by_inference = sdk_fact_overlay_check(
            sdk, _as_inference(), _binding(sdk, age=30), FactOverlay()
        )
        by_rule = sdk_fact_overlay_check(
            sdk, _as_rule(), _rule_binding(sdk, age=30), FactOverlay(), head=_head()
        )
        self._assert_same_answer(by_inference, by_rule)

    # --- F3: the head is required, and its absence says why -------------------
    def test_a_rule_without_a_head_is_refused_with_the_shell_path(self) -> None:
        sdk = _store()
        for shell, path, call in (
            ("check", "$.check.inference", lambda: sdk_check(sdk, _as_rule(), _binding(sdk, age=30))),
            ("diagnose", "$.diagnose.inference", lambda: sdk_diagnose(sdk, _as_rule(), _binding(sdk, age=30))),
            ("why_not", "$.why_not.inference", lambda: sdk_why_not(sdk, _as_rule(), [])),
            (
                "fact_overlay",
                "$.check_fact_overlay.inference",
                lambda: sdk_fact_overlay_check(sdk, _as_rule(), _binding(sdk, age=30), FactOverlay()),
            ),
        ):
            with self.subTest(shell=shell):
                with self.assertRaises(SDKStoreError) as ctx:
                    call()
                self.assertEqual(ctx.exception.path, path)
                self.assertIn("head=", str(ctx.exception))

    def test_an_unknown_rule_form_is_still_refused(self) -> None:
        sdk = _store()
        with self.assertRaises(SDKStoreError) as ctx:
            sdk_check(sdk, object(), _binding(sdk, age=30))  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.path, "$.check.inference")


# --- F4: parity for the three rule-overlay shells -----------------------------
def _support(sdk: SDKStore, *, name: str = "alice", age: int = 30):
    """A real ProofReceipt from a real Check, the way these shells take one."""
    result = sdk_check(sdk, _as_inference(), _binding(sdk, age=age, name=name))
    return result.evidence_envelope.proof


def _sdk_rule() -> DSLRule:
    with vars("p", "age") as (p, age):
        return DSLRule(
            id="parity_age_body",
            version="1.0",
            select=[p, age],
            where=[Pred("person:age", p, age)],
        )


class RuleOverlayParityTests(unittest.TestCase):
    """The rule-overlay shells take a rule too, and both forms compile to one spec."""

    def _assert_same_answer(self, first: object, second: object) -> None:
        self.assertEqual(type(first), type(second))
        for field in ("status", "errors", "warnings", "notes"):
            if hasattr(first, field):
                with self.subTest(field=field):
                    self.assertEqual(getattr(first, field), getattr(second, field))

    def test_both_rule_forms_compile_to_the_same_spec(self) -> None:
        sdk = _store()
        from factgraph.sdk.shells._validation import resolve_rule_spec

        by_dsl = resolve_rule_spec(sdk, _sdk_rule(), path="$.parity.rule")
        by_application = resolve_rule_spec(sdk, _as_rule(), path="$.parity.rule")

        self.assertEqual(by_dsl.rule_id, by_application.rule_id)
        self.assertEqual(by_dsl.version, by_application.version)
        self.assertEqual(sorted(by_dsl.select_vars), sorted(by_application.select_vars))
        self.assertEqual(by_dsl.where, by_application.where)

    def test_rule_disable_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        support = _support(sdk)
        by_dsl = sdk_rule_disable(
            sdk, _sdk_rule(), support, case_index=0, condition_index=0
        )
        by_application = sdk_rule_disable(
            sdk, _as_rule(), support, case_index=0, condition_index=0
        )
        self._assert_same_answer(by_dsl, by_application)

    def test_rule_literal_replace_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        support = _support(sdk)
        kwargs = dict(
            case_index=0,
            condition_index=0,
            literal_path=ConditionPath(kind="pred_term", index=0),
            old_literal="alice",
            new_literal="bob",
        )
        by_dsl = sdk_rule_literal_replace(sdk, _sdk_rule(), support, **kwargs)
        by_application = sdk_rule_literal_replace(sdk, _as_rule(), support, **kwargs)
        self._assert_same_answer(by_dsl, by_application)

    def test_rule_add_condition_answers_the_same_for_both_forms(self) -> None:
        sdk = _store()
        support = _support(sdk)
        added = AddedCondition(atom=("eq", "$age", 30))
        by_dsl = sdk_rule_add_condition(
            sdk, _sdk_rule(), support, case_index=0, added_atom=added
        )
        by_application = sdk_rule_add_condition(
            sdk, _as_rule(), support, case_index=0, added_atom=added
        )
        self._assert_same_answer(by_dsl, by_application)

    def test_an_unknown_rule_form_is_still_refused(self) -> None:
        sdk = _store()
        with self.assertRaises(SDKStoreError) as ctx:
            sdk_rule_disable(
                sdk, object(), _support(sdk), case_index=0, condition_index=0
            )
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.rule")


if __name__ == "__main__":
    unittest.main()
