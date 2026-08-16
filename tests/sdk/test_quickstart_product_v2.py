"""Executable contract for docs/quickstart/product_workflow_v2.md."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from factgraph.sdk import (
    AssetMeta,
    Database,
    Entity,
    EntityRef,
    FactGraph,
    Field,
    Identity,
    compile_schema_from_classes,
    outcome_from_run_v2,
    vars,
)


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()
    tags: list[str] = Field()


class ProductV2QuickstartTests(unittest.TestCase):
    def test_documented_database_create_load_and_attach_paths(self) -> None:
        with TemporaryDirectory(prefix="factgraph-product-quickstart-") as root:
            managed_workspace = Path(root) / "managed"
            with FactGraph.create(
                path=managed_workspace,
                schema_classes=[Person],
            ) as seed_fg:
                alice = seed_fg.entities.create(Person, person_id="alice")
                seed_fg.fields.set(Person.age, alice, 30)

            with FactGraph.load_workspace(
                managed_workspace,
                schema_classes=[Person],
            ) as loaded_fg:
                alice = loaded_fg.entities.ref(Person, person_id="alice")
                self.assertEqual(loaded_fg.fields.get(Person.age, alice), 30)

            attached_workspace = Path(root) / "attached"
            schema_ir = compile_schema_from_classes([Person])
            with Database.create(attached_workspace, schema_ir=schema_ir) as db:
                attached_fg = FactGraph.attach(db, schema_classes=[Person])
                person = attached_fg.entities.create(Person, person_id="attached")
                attached_fg.fields.set(Person.age, person, 44)
                attached_fg.close()

                # The facade never owns or closes a caller-owned Database.
                self.assertGreater(db.head().tx_seq, 0)

    def test_documented_rule_function_policy_scenario_explain_replay_path(self) -> None:
        fg = FactGraph.create(schema_classes=[Person])
        alice_e_ref = fg.entities.create(Person, person_id="alice")
        fg.fields.set(Person.age, alice_e_ref, 30)
        fg.fields.add(Person.tags, alice_e_ref, "baseline")
        alice = EntityRef("Person", {"person_id": "alice"})

        with vars("person", "age") as (person, age):
            person_values = fg.build_rule(
                id="person_values",
                version="1",
                meta=AssetMeta(name="Person values"),
                when=(Person(person), Person(person).age == age),
                ports={"person": person, "age": age},
                semantic_ports={"person": Person, "age": Person.age},
            )

        age_decade = fg.build_function(
            id="age_decade",
            version="1",
            meta=AssetMeta(name="Age decade"),
            implementation=lambda age: age // 10,
            inputs={"age": "int"},
            output="int",
        )
        policy = fg.policy_builder("people_by_decade", version="1")
        people = policy.use(person_values).as_("people")
        decade = policy.use(age_decade).as_("decade")
        decade.inputs(age=people.age)
        target = policy.build(policy.all(people, decade, decade.result >= 3))

        scenario = (
            fg.scenario()
            .set(
                Person.age,
                alice_e_ref,
                35,
                premise_id="reviewed-age",
                meta={
                    "source": {
                        "ref": "operator:case-42",
                        "locator": {"kind": "opaque", "opaque_ref": "review-form"},
                        "origin_role": "scenario_hypothesis",
                    },
                    "note": "run-local hypothesis",
                },
            )
            .build()
        )
        profile = fg.execution.native_deterministic(target=target).build()
        run = (
            fg.query(target)
            .bind(people.person, alice)
            .select("age", people.age)
            .select("decade", decade.result)
            .plan(profile=profile, scenario=scenario)
            .run()
        )

        outcome = outcome_from_run_v2(run)
        self.assertEqual(
            tuple(value.value for value in outcome.effective.rows[0].values),
            (35, 3),
        )
        explanation = outcome.explain(outcome.effective.rows[0])
        function_view = explanation.functions.occurrences[0]
        call = next(item for item in function_view.calls if item.inputs[0].value == 35)
        self.assertEqual(call.output.value, 3)
        self.assertIsNone(explanation.evidence.graph)

        wire = explanation.to_dict()
        canonical = explanation.to_canonical_bytes()
        self.assertEqual(wire["$schema"], "factgraph.product_explanation")
        self.assertEqual(wire["schema_version"], 2)
        self.assertEqual(wire["source_protocol"], "evaluation_run_v2")
        self.assertEqual(json.loads(canonical), wire)
        self.assertEqual(
            explanation.content_digest,
            f"sha256:{sha256(canonical).hexdigest()}",
        )
        evidence = wire["evidence"]
        self.assertIsInstance(evidence, dict)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence["state"], "not_available")
        self.assertEqual(
            evidence["reason_code"],
            "NATIVE_V2_DETACHED_EVIDENCE_GRAPH_NOT_IMPLEMENTED",
        )
        self.assertIsNone(evidence["graph"])
        self.assertEqual(outcome.replay().status, "matched")


if __name__ == "__main__":
    unittest.main()
