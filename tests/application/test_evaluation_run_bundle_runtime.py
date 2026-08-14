from __future__ import annotations

import json
import unittest

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    entity_info,
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
    field_predicate,
    manage_rule_occurrence,
    resolve_selector,
)
from factgraph.application.evaluation_run_bundle_runtime import (
    MAX_EVALUATION_RUN_BUNDLE_BYTES,
    _build_evaluation_run_bundle_v0,
    _ir_from_wire,
    _validate_native_where_bytes,
    _validate_proof_receipt_bytes,
    _where_from_wire,
    _wire,
    _unwire,
)
from factgraph.application.protocol import (
    EntitySelector,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    Policy,
    PolicyLiteral,
    PolicyOccurrence,
    ProtocolShapeError,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.application.protocol.evaluation_run_bundle import (
    EvaluationRunNativePlanV0,
    EvaluationRunRelationV0,
    EvaluationRunValueV0,
    _certainty_digest,
)
from factgraph.application.protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import Entity, Field, Identity, SDKStore


class BlobRecord(Entity):
    key: str = Identity()
    payload: bytes = Field()
    enabled: bool = Field()


class EvaluationRunBundleRuntimeTests(unittest.TestCase):
    def test_native_capture_round_trip_includes_bytes_and_explicit_empty_dependency(self) -> None:
        graph = SDKStore([BlobRecord])
        index = build_schema_index(graph.schema_ir)
        ref = resolve_selector(
            EntitySelector(entity_type="BlobRecord", identity={"key": "one"}),
            index=index,
        )
        encoded = ref.encoded_ref or ""
        info = entity_info(index, "BlobRecord")
        set_field(graph.ledger, info.exists_predicate_id, encoded, [])
        set_field(
            graph.ledger, info.identity_predicates["key"].pred_id, encoded, [("string", "one")]
        )
        set_field(
            graph.ledger,
            field_predicate(index, "BlobRecord", "payload").pred_id,
            encoded,
            [("bytes", b"\x00\xff")],
        )
        set_field(
            graph.ledger,
            field_predicate(index, "BlobRecord", "enabled").pred_id,
            encoded,
            [("bool", True)],
        )

        entity, payload, enabled = Var("$entity"), Var("$payload"), Var("$enabled")
        resolved = build_resolved_rule(
            id="blob_values",
            version="1",
            when=(
                PredAtom(info.exists_predicate_id, [entity]),
                PredAtom(
                    field_predicate(index, "BlobRecord", "payload").pred_id, [entity, payload]
                ),
                PredAtom(
                    field_predicate(index, "BlobRecord", "enabled").pred_id, [entity, enabled]
                ),
            ),
            ports={
                "entity": SemanticRulePort(entity, entity_identity("BlobRecord")),
                "payload": SemanticRulePort(payload, field_endpoint("BlobRecord", "payload")),
                "enabled": SemanticRulePort(enabled, field_endpoint("BlobRecord", "enabled")),
            },
            schema_index=index,
        )
        space = SemanticAddressSpace((manage_rule_occurrence(resolved, "blob"),))
        policy = compile_policy(
            Policy("blob-policy", PolicyOccurrence("blob")), address_space=space
        )
        query = EvaluationQuery(
            policy.policy_digest,
            (
                EvaluationQuerySelection("payload", SemanticPortAddress("blob", "payload")),
                EvaluationQuerySelection("enabled", SemanticPortAddress("blob", "enabled")),
            ),
            (EvaluationQueryBinding(SemanticPortAddress("blob", "payload"), b"\x00\xff"),),
        )
        compiled = compile_evaluation_query(
            query, compiled_policy=policy, address_space=space, schema_index=index
        )
        result = graph.eval.evaluate(compiled)
        plan, _ = _materialize_adapter_derivation_plan(compiled._lowering_plan, engine="native")
        projected = project_view_facts_with_witness(graph.ledger, graph.schema_ir)
        dependencies = {atom.pred_id for atom in resolved.rule.when if isinstance(atom, PredAtom)}
        relations = {pred_id: projected[pred_id] for pred_id in dependencies}
        assert result._row_support_artifacts is not None

        bundle = _build_evaluation_run_bundle_v0(
            compiled,
            result,
            materialized_plan=plan,
            schema_ir=graph.schema_ir,
            effective_relations=relations,
            proof_receipts=result._row_support_artifacts,
        )
        encoded_bundle = evaluation_run_bundle_bytes(bundle)
        decoded = evaluation_run_bundle_from_bytes(encoded_bundle)

        self.assertEqual(decoded, bundle)
        self.assertNotIn("AP8", repr(bundle))
        self.assertNotIn("AP8", repr(bundle.native_plan))
        self.assertEqual(bundle.binding_values[0], EvaluationRunValueV0("bytes", "AP8"))
        self.assertEqual(bundle.rows[0].values[0][1], EvaluationRunValueV0("bytes", "AP8"))
        payload_relation = next(
            row for row in bundle.relations if row.predicate_id.endswith(":payload")
        )
        self.assertEqual(payload_relation.facts[0][1][1], EvaluationRunValueV0("bytes", "AP8"))
        self.assertEqual(bundle.relation_capture_scope, "plan_dependency_complete")

        duplicate_root_key = encoded_bundle.replace(
            b'{"$type":"EvaluationRunBundleV0"',
            b'{"$type":"EvaluationRunBundleV0","$type":"EvaluationRunBundleV0"',
            1,
        )
        with self.assertRaisesRegex(ProtocolShapeError, "duplicate"):
            evaluation_run_bundle_from_bytes(duplicate_root_key)
        with self.assertRaisesRegex(ProtocolShapeError, "non-standard constant"):
            evaluation_run_bundle_from_bytes(encoded_bundle.replace(b'"caller_managed"', b"NaN", 1))

        receipt_payload = json.loads(bundle.rows[0].proof_receipt_bytes)
        nested: object = "leaf"
        for _ in range(70):
            nested = [nested]
        receipt_payload["non_fact_steps"][0]["details"] = [["deep", nested]]
        deep_receipt = json.dumps(
            receipt_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        with self.assertRaisesRegex(ProtocolShapeError, "depth"):
            _validate_proof_receipt_bytes(deep_receipt)

    def test_all_tup_value_domains_round_trip(self) -> None:
        values = (
            EvaluationRunValueV0("entity_ref", "idref_v1:opaque"),
            EvaluationRunValueV0("string", "hello"),
            EvaluationRunValueV0("int", -7),
            EvaluationRunValueV0("float64", "0x3ff0000000000000"),
            EvaluationRunValueV0("bool", True),
            EvaluationRunValueV0("bytes", "AP8"),
            EvaluationRunValueV0("time", 123456789),
            EvaluationRunValueV0("uuid", "12345678-1234-1234-1234-123456789abc"),
        )
        self.assertEqual(
            tuple(item.tag for item in values),
            (
                "entity_ref",
                "string",
                "int",
                "float64",
                "bool",
                "bytes",
                "time",
                "uuid",
            ),
        )
        with self.assertRaises(ProtocolShapeError):
            EvaluationRunValueV0("bytes", "not+base64")
        with self.assertRaises(ProtocolShapeError):
            EvaluationRunValueV0("bool", 1)
        with self.assertRaises(ProtocolShapeError):
            _certainty_digest(("0x3FF0000000000000", "0x3ff0000000000000", "boolean"))
        with self.assertRaises(ProtocolShapeError):
            _certainty_digest(("0x8000000000000000", "0x3ff0000000000000", "boolean"))
        with self.assertRaises(ProtocolShapeError):
            _ir_from_wire({"$float64": "0x3FF0000000000000"}, 0)
        with self.assertRaises(ProtocolShapeError):
            _ir_from_wire({"$float64": "0x8000000000000000"}, 0)
        with self.assertRaisesRegex(ProtocolShapeError, "head_var_names"):
            EvaluationRunNativePlanV0(
                "d",
                "1",
                "p",
                tuple(f"$v{i}" for i in range(65)),
                b"[]",
                "sha256:" + "0" * 64,
                "sha256:" + "0" * 64,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "value_types"):
            EvaluationRunRelationV0(
                "p",
                ("string",) * 65,
                (),
            )

        with self.assertRaisesRegex(ProtocolShapeError, "non-standard constant"):
            _validate_proof_receipt_bytes(
                b'{"kind":"native_binding_v1","root_result_kind":"fact",'
                b'"binding":[],"pred_witnesses":[],"non_fact_steps":['
                b'{"step_key":"c0.a0","kind":"cmp","status":"holds",'
                b'"details":[["value",NaN]]}],"rule_refs":[],"rule_ref_edges":[]}'
            )

    def test_bundle_wire_whitelists_canonical_policy_literal_only(self) -> None:
        literal = PolicyLiteral("time", 123456789)
        self.assertEqual(_unwire(_wire(literal)), literal)
        with self.assertRaises(ProtocolShapeError):
            _unwire(
                {
                    "$type": "PolicyLiteral",
                    "fields": {"scalar_domain": "time", "value": True},
                }
            )

    def test_codec_fails_closed_for_shape_splice_size_and_plan_tag(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            evaluation_run_bundle_from_bytes(b"x" * (MAX_EVALUATION_RUN_BUNDLE_BYTES + 1))
        with self.assertRaisesRegex(ProtocolShapeError, "canonical JSON"):
            evaluation_run_bundle_from_bytes(b'{"$type":"\\ud800","fields":{}}')
        with self.assertRaisesRegex(ProtocolShapeError, "canonical JSON"):
            _validate_native_where_bytes(
                b'{"$list":[{"$tuple":[{"$scalar":"\\ud800"}]}]}'
            )
        with self.assertRaises(ProtocolShapeError):
            _where_from_wire({"$list": [{"$tuple": [{"$scalar": "python"}]}]})

        graph = SDKStore([BlobRecord])
        # A direct DTO mutation cannot be accepted even if its local component is resealed.
        schema_bytes = json.dumps(
            graph.schema_ir, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        self.assertGreater(len(schema_bytes), 0)
        with self.assertRaises(ProtocolShapeError):
            EvaluationRunValueV0("float64", "0x7ff8000000000000")


if __name__ == "__main__":
    unittest.main()
