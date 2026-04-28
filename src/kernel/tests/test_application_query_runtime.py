from __future__ import annotations

import unittest

from kernel.application import (
    QueryRuntimeError,
    build_schema_index,
    entity_info,
    execute_query,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    EntitySelector,
    FieldPath,
    ProtocolShapeError,
    QueryReturnContract,
    QueryReturnSlot,
    QueryRuntimeRequest,
    QueryRuntimeResponse,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.store import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    nickname: str = Field(cardinality="single")


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(store: Store, index, name: str, nickname: str | None = None) -> str:
    ref = resolve_selector(EntitySelector(entity_type="Person", identity={"name": name}), index=index)
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    if nickname is not None:
        set_field(
            store.ledger,
            field_predicate(index, "Person", "nickname").pred_id,
            encoded,
            [("string", nickname)],
        )
    return encoded


class QueryDTOValidationTests(unittest.TestCase):
    def test_return_slot_entity_rejects_field_path(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnSlot(alias="p", kind="entity", var="$p", field_path=FieldPath(entity_type="Person", field_name="nickname"))

    def test_return_slot_scalar_requires_field_path(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnSlot(alias="n", kind="scalar", var="$n")

    def test_return_contract_rejects_duplicate_alias(self) -> None:
        slot = QueryReturnSlot(alias="x", kind="entity", var="$p")
        with self.assertRaises(ProtocolShapeError):
            QueryReturnContract(slots=(slot, slot))

    def test_return_contract_rejects_empty(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnContract(slots=())

    def test_request_rejects_non_list_where_ir(self) -> None:
        contract = QueryReturnContract(
            slots=(QueryReturnSlot(alias="p", kind="entity", var="$p"),),
        )
        with self.assertRaises(ProtocolShapeError):
            QueryRuntimeRequest(entity_type="Person", where_ir="not a list", return_contract=contract)  # type: ignore[arg-type]


class ExecuteQuerySmokeTests(unittest.TestCase):
    def test_execute_query_entity_slot_returns_response_envelope(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", "ally")
        info = entity_info(index, "Person")
        contract = QueryReturnContract(
            slots=(QueryReturnSlot(alias="p", kind="entity", var="$p"),),
        )
        request = QueryRuntimeRequest(
            entity_type="Person",
            where_ir=[("pred", info.exists_predicate_id, ["$p"])],
            return_contract=contract,
        )
        response = execute_query(request, store=store, index=index)
        self.assertIsInstance(response, QueryRuntimeResponse)
        self.assertEqual(response.errors, ())
        for row in response.rows:
            self.assertIn("p", row)

    def test_execute_query_unsupported_slot_kind_is_blocked_by_dto(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnSlot(alias="x", kind="aggregate", var="$x")  # type: ignore[arg-type]


class QueryRuntimeErrorTests(unittest.TestCase):
    def test_to_error_dto_round_trip(self) -> None:
        err = QueryRuntimeError(
            "missing binding",
            code="QUERY_MISSING_BINDING",
            path=("var", "$p"),
            details={"var": "$p"},
        )
        dto = err.to_error_dto()
        self.assertEqual(dto.code, "QUERY_MISSING_BINDING")
        self.assertEqual(dto.path, ("var", "$p"))
        self.assertEqual(dto.details, {"var": "$p"})


class QueryReturnSlotEntityTypeValidationTests(unittest.TestCase):
    """Commit 2a Q1: slot-level expected entity_type."""

    def test_entity_slot_accepts_entity_type(self) -> None:
        slot = QueryReturnSlot(alias="p", kind="entity", var="$p", entity_type="Person")
        self.assertEqual(slot.entity_type, "Person")

    def test_entity_slot_without_entity_type_is_allowed(self) -> None:
        slot = QueryReturnSlot(alias="p", kind="entity", var="$p")
        self.assertIsNone(slot.entity_type)

    def test_scalar_slot_must_not_set_entity_type(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnSlot(
                alias="n",
                kind="scalar",
                var="$n",
                field_path=FieldPath(entity_type="Person", field_name="nickname"),
                entity_type="Person",
            )

    def test_entity_type_empty_string_rejected(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryReturnSlot(alias="p", kind="entity", var="$p", entity_type="")


class QueryRequestPolicyLiteralTests(unittest.TestCase):
    """Commit 2a Q2/Q3: on_missing/on_type_mismatch literal extension."""

    def _basic_contract(self) -> QueryReturnContract:
        return QueryReturnContract(slots=(QueryReturnSlot(alias="p", kind="entity", var="$p"),))

    def test_on_missing_supports_null(self) -> None:
        request = QueryRuntimeRequest(
            entity_type="Person",
            where_ir=[],
            return_contract=self._basic_contract(),
            on_missing="null",
        )
        self.assertEqual(request.on_missing, "null")

    def test_on_type_mismatch_supports_null(self) -> None:
        request = QueryRuntimeRequest(
            entity_type="Person",
            where_ir=[],
            return_contract=self._basic_contract(),
            on_type_mismatch="null",
        )
        self.assertEqual(request.on_type_mismatch, "null")

    def test_on_missing_rejects_unknown_literal(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            QueryRuntimeRequest(
                entity_type="Person",
                where_ir=[],
                return_contract=self._basic_contract(),
                on_missing="abort",  # type: ignore[arg-type]
            )

    def test_on_type_mismatch_rejects_include_null_legacy(self) -> None:
        # commit 2a renamed include_null -> null; verify legacy literal is rejected
        with self.assertRaises(ProtocolShapeError):
            QueryRuntimeRequest(
                entity_type="Person",
                where_ir=[],
                return_contract=self._basic_contract(),
                on_missing="include_null",  # type: ignore[arg-type]
            )


class QueryTypeMismatchPolicyTests(unittest.TestCase):
    """Commit 2a Q2/Q3: on_type_mismatch policy enforcement against entity_type."""

    def _seed_two_persons(self) -> tuple[Store, object, str, str]:
        from kernel.application import (
            entity_info,
            field_predicate,
            resolve_selector,
        )
        from kernel.application.protocol import EntitySelector
        from kernel.core.evidence.write_protocol import set_field

        schema_ir = compile_schema_from_classes([Person])
        store = Store(schema_ir)
        index = build_schema_index(schema_ir)
        info = entity_info(index, "Person")

        ref_a = resolve_selector(EntitySelector(entity_type="Person", identity={"name": "alice"}), index=index)
        ref_b = resolve_selector(EntitySelector(entity_type="Person", identity={"name": "bob"}), index=index)
        for ref in (ref_a, ref_b):
            encoded = ref.encoded_ref or ""
            set_field(store.ledger, info.exists_predicate_id, encoded, [])
            set_field(
                store.ledger,
                info.identity_predicates["name"].pred_id,
                encoded,
                [("string", ref.identity["name"])],
            )
            set_field(
                store.ledger,
                field_predicate(index, "Person", "nickname").pred_id,
                encoded,
                [("string", ref.identity["name"] + "-nick")],
            )
        return store, index, ref_a.encoded_ref or "", ref_b.encoded_ref or ""

    def _build_request(
        self,
        *,
        entity_type: str | None,
        on_type_mismatch: str = "error",
        info_pred: str,
    ) -> QueryRuntimeRequest:
        slot = QueryReturnSlot(alias="p", kind="entity", var="$p", entity_type=entity_type)
        contract = QueryReturnContract(slots=(slot,))
        return QueryRuntimeRequest(
            entity_type="Person",
            where_ir=[("pred", info_pred, ["$p"])],
            return_contract=contract,
            on_type_mismatch=on_type_mismatch,  # type: ignore[arg-type]
        )

    def test_matching_entity_type_returns_rows(self) -> None:
        from kernel.application import entity_info, execute_query

        store, index, _, _ = self._seed_two_persons()
        info = entity_info(index, "Person")
        request = self._build_request(
            entity_type="Person",
            on_type_mismatch="error",
            info_pred=info.exists_predicate_id,
        )
        response = execute_query(request, store=store, index=index)
        self.assertEqual(response.errors, ())
        self.assertGreater(len(response.rows), 0)

    def test_mismatched_entity_type_with_error_policy_yields_error_dto(self) -> None:
        from kernel.application import entity_info, execute_query

        store, index, _, _ = self._seed_two_persons()
        info = entity_info(index, "Person")
        request = self._build_request(
            entity_type="Wombat",
            on_type_mismatch="error",
            info_pred=info.exists_predicate_id,
        )
        response = execute_query(request, store=store, index=index)
        self.assertEqual(response.rows, ())
        self.assertEqual(len(response.errors), 1)
        self.assertEqual(response.errors[0].code, "QUERY_TYPE_MISMATCH")

    def test_mismatched_entity_type_with_skip_policy_drops_rows(self) -> None:
        from kernel.application import entity_info, execute_query

        store, index, _, _ = self._seed_two_persons()
        info = entity_info(index, "Person")
        request = self._build_request(
            entity_type="Wombat",
            on_type_mismatch="skip",
            info_pred=info.exists_predicate_id,
        )
        response = execute_query(request, store=store, index=index)
        self.assertEqual(response.errors, ())
        self.assertEqual(response.rows, ())

    def test_mismatched_entity_type_with_null_policy_yields_null_alias(self) -> None:
        from kernel.application import entity_info, execute_query

        store, index, _, _ = self._seed_two_persons()
        info = entity_info(index, "Person")
        request = self._build_request(
            entity_type="Wombat",
            on_type_mismatch="null",
            info_pred=info.exists_predicate_id,
        )
        response = execute_query(request, store=store, index=index)
        self.assertEqual(response.errors, ())
        self.assertGreater(len(response.rows), 0)
        for row in response.rows:
            self.assertIsNone(row["p"])

    def test_unknown_entity_type_hydrate_error_uses_missing_policy(self) -> None:
        from kernel.application import entity_info, execute_query
        from kernel.core.evidence.write_protocol import set_field

        store, index, _, _ = self._seed_two_persons()
        info = entity_info(index, "Person")
        unknown_ref = "idref_v1:Wombat:abcdef"
        set_field(store.ledger, info.exists_predicate_id, unknown_ref, [])
        request = self._build_request(
            entity_type=None,
            on_type_mismatch="error",
            info_pred=info.exists_predicate_id,
        )
        request = QueryRuntimeRequest(
            entity_type=request.entity_type,
            where_ir=request.where_ir,
            return_contract=request.return_contract,
            on_missing="null",
            on_type_mismatch=request.on_type_mismatch,
        )
        response = execute_query(request, store=store, index=index)
        self.assertEqual(response.errors, ())
        self.assertTrue(any(row["p"] is None for row in response.rows))


if __name__ == "__main__":
    unittest.main()
