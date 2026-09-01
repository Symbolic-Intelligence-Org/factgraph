from __future__ import annotations

import unittest

from factgraph.application import (
    build_product_compilation_context_v1,
    build_resolved_rule,
    build_schema_index,
)
from factgraph.application.protocol import SemanticRulePort, field_endpoint
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Country(Entity):
    code: str = Identity()


class Resident(Entity):
    resident_id: str = Identity()
    lives_in: Country = Field()


class ProductCompilationContextV1Tests(unittest.TestCase):
    def _fixture(self):
        schema_ir = compile_schema_from_classes(
            [Country, Resident], generated_at="2026-09-01T00:00:00Z"
        )
        index = build_schema_index(schema_ir)
        resident, country, resident_id = (
            Var("$resident"),
            Var("$country"),
            Var("$resident_id"),
        )
        bundle = build_resolved_rule(
            id="resident-country",
            version="1",
            when=(
                PredAtom("resident:resident_id", [resident, resident_id]),
                PredAtom("resident:lives_in", [resident, country]),
            ),
            ports={
                "resident_id": SemanticRulePort(
                    resident_id, field_endpoint("Resident", "resident_id")
                ),
            },
            schema_index=index,
        )
        return schema_ir, bundle

    def test_public_context_describes_fields_without_exposing_schema_index(self) -> None:
        schema_ir, bundle = self._fixture()

        context = build_product_compilation_context_v1(schema_ir)
        field = context.describe_field(bundle.contract.ports["resident_id"].endpoint)

        self.assertEqual(field.entity_type, "Resident")
        self.assertEqual(field.field_name, "resident_id")
        self.assertEqual(field.value_kind, "scalar")
        self.assertEqual(field.value_type, "string")
        self.assertEqual(field.cardinality, "single")
        self.assertFalse(hasattr(context, "schema_index"))

    def test_public_context_projects_anchored_entity_relation_premise(self) -> None:
        schema_ir, bundle = self._fixture()

        premises = build_product_compilation_context_v1(schema_ir).relation_premises(bundle)

        self.assertEqual(len(premises), 1)
        premise = premises[0]
        self.assertEqual(premise.predicate_id, "resident:lives_in")
        self.assertEqual(premise.owner_type, "Resident")
        self.assertEqual(premise.field_name, "lives_in")
        self.assertEqual(premise.cardinality, "single")
        self.assertEqual(
            tuple((item.position, item.type_domain, item.anchor_ports) for item in premise.arguments),
            ((0, "entity_ref", ("resident_id",)), (1, "entity_ref", ())),
        )


if __name__ == "__main__":
    unittest.main()
