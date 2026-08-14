"""Focused V2 WeightedChoice → ProbLog annotated-disjunction tests."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factgraph.adapters.problog.problog_engine import run_problog
from factgraph.adapters.problog.problog_export import export_problog
from factgraph.adapters.problog.rule_ext import ProbLogRuleExt
from factgraph.application.evaluation_query_runtime import compile_evaluation_query
from factgraph.application.protocol.evaluation_query import (
    EvaluationQuery,
    EvaluationQuerySelection,
)
from factgraph.application.protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.protocol.semantic_port import entity_identity, field_endpoint
from factgraph.application.weighted_choice_problog_v2 import (
    ProductWeightedChoiceProbLogV2Error,
    _compile_product_policy_v2_skeleton_for_lowering,
    lower_product_policy_weighted_choice_to_problog_v2,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, SDKStore


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()


def _people_rule(graph: SDKStore):
    person, age = Var("$person"), Var("$age")
    return graph.build_rule(
        id="people",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={"person": person, "age": age},
        semantic_ports={
            "person": entity_identity("Person"),
            "age": field_endpoint("Person", "age"),
        },
    )


def _choice_target(graph: SDKStore):
    rule = _people_rule(graph)
    policy = graph.policy_builder("selected_people", version="1")
    key = policy.use(rule, as_="key")
    left = policy.use(rule, as_="left")
    right = policy.use(rule, as_="right")
    choice = policy.weighted_choice(
        id="source",
        on=(key.person,),
        choices=(
            policy.choice("left", probability="0.7", when=policy.all(left)),
            policy.choice("right", probability="0.3", when=policy.all(right)),
        ),
    )
    return policy.build(policy.all(key, choice))


def _compiled_plan(graph: SDKStore, target):
    # The public `.policy` remains deliberately unusable at legacy ingress.
    # This test exercises only the narrow internal V2 skeleton bridge which
    # retains the ProductPolicy envelope for immediate AD lowering.
    compiled_policy = _compile_product_policy_v2_skeleton_for_lowering(
        target=target,
        schema_index=graph._application_schema_index,
    )
    query = EvaluationQuery(
        compiled_policy.policy_digest,
        (EvaluationQuerySelection("person", SemanticPortAddress("key", "person")),),
    )
    compiled_query = compile_evaluation_query(
        query,
        compiled_policy=compiled_policy,
        address_space=target.address_space,
        schema_index=graph._application_schema_index,
    )
    plan, _ = _materialize_adapter_derivation_plan(
        compiled_query._lowering_plan,
        engine="problog",
    )
    return compiled_policy, plan


class WeightedChoiceProbLogV2Tests(unittest.TestCase):
    def test_helper_maps_lineage_to_branch_local_keys_and_canonical_domain(self) -> None:
        graph = SDKStore([Person])
        target = _choice_target(graph)
        compiled_policy, plan = _compiled_plan(graph, target)

        lowered = lower_product_policy_weighted_choice_to_problog_v2(
            target=target,
            compiled_policy=compiled_policy,
            plan=plan,
        )

        self.assertIsInstance(lowered.engine_ext, ProbLogRuleExt)
        assert lowered.engine_ext is not None
        choice = lowered.engine_ext.weighted_choice
        assert choice is not None
        self.assertEqual({branch.branch_index for branch in choice.branches}, {0, 1})
        self.assertEqual({branch.arm_id for branch in choice.branches}, {"left", "right"})
        # The lowering correctly preserves DNF-local aliases while making one
        # independent canonical AD domain for their shared semantic key.
        self.assertNotEqual(
            choice.branches[0].key_variables,
            choice.branches[1].key_variables,
        )
        self.assertEqual(choice.domain_key_variables, ("$__weighted_choice_key_0",))
        self.assertTrue(
            any("$__weighted_choice_key_0" in repr(atom) for atom in choice.domain_body)
        )

    @unittest.skipUnless(shutil.which("problog"), "requires the real ProbLog CLI")
    def test_real_problog_uses_one_exclusive_annotated_disjunction(self) -> None:
        graph = SDKStore([Person])
        person = graph.entities.create(Person, person_id="alice")
        set_field(graph.ledger, "person:age", person, [("int", 20)])
        target = _choice_target(graph)
        compiled_policy, plan = _compiled_plan(graph, target)
        lowered = lower_product_policy_weighted_choice_to_problog_v2(
            target=target,
            compiled_policy=compiled_policy,
            plan=plan,
        )
        head = lowered.heads[0]
        rule_spec = {
            "derivation_id": lowered.derivation_id,
            "version": lowered.version,
            "target_pred_id": head.target_pred_id,
            "head_vars": list(head.head_var_names),
            "query_vars": list(head.head_var_names),
            "where": lowered.body_ir,
            "engine_ext": lowered.engine_ext,
        }

        with TemporaryDirectory() as tmpdir:
            program_path = Path(tmpdir) / "choice.pl"
            export_problog(graph.store, rule_spec, program_path)
            program = program_path.read_text(encoding="utf-8")
            output = run_problog(program_path, trace=False)

        self.assertRegex(
            program,
            r"0\.7::fg_weighted_choice_[0-9a-f]+\(.*\); 0\.3::fg_weighted_choice_[0-9a-f]+\(",
        )
        self.assertNotIn("0.7::rule_body_", program)
        # Both logical branch bodies hold for the same person.  A categorical
        # AD therefore makes `answer(person)` certain (0.7 + 0.3 = 1), whereas
        # independent per-branch weights would incorrectly give 0.79.
        match = re.search(r"answer\([^\n]+\):\s*([0-9.]+)", output)
        self.assertIsNotNone(match, output)
        assert match is not None
        self.assertAlmostEqual(float(match.group(1)), 1.0, places=12)

    def test_nested_ordinary_any_is_rejected_instead_of_becoming_weighted_or(self) -> None:
        graph = SDKStore([Person])
        rule = _people_rule(graph)
        policy = graph.policy_builder("nested_choice", version="1")
        key = policy.use(rule, as_="key")
        left_a = policy.use(rule, as_="left_a")
        left_b = policy.use(rule, as_="left_b")
        right = policy.use(rule, as_="right")
        choice = policy.weighted_choice(
            id="source",
            on=(key.person,),
            choices=(
                policy.choice(
                    "left",
                    probability="0.7",
                    when=policy.all(policy.any(policy.all(left_a), policy.all(left_b))),
                ),
                policy.choice("right", probability="0.3", when=policy.all(right)),
            ),
        )
        target = policy.build(policy.all(key, choice))
        compiled_policy, plan = _compiled_plan(graph, target)

        with self.assertRaises(ProductWeightedChoiceProbLogV2Error) as context:
            lower_product_policy_weighted_choice_to_problog_v2(
                target=target,
                compiled_policy=compiled_policy,
                plan=plan,
            )

        self.assertEqual(context.exception.code, "WEIGHTED_CHOICE_V2_NESTED_OR_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
