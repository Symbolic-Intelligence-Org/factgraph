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


if __name__ == "__main__":
    unittest.main()
