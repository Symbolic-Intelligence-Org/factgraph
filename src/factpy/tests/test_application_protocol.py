from __future__ import annotations

import unittest

from factpy.application.protocol import (
    EntityReadRequest,
    EntityRef,
    EntitySelector,
    EntityWriteCommand,
    EntityWritePlan,
    ErrorDTO,
    FieldMutation,
    FieldPath,
    FieldValueDTO,
    ProtocolShapeError,
)


class ApplicationProtocolTests(unittest.TestCase):
    def test_error_dto_requires_screaming_snake_case(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            ErrorDTO(code="entity_not_found", message="bad")

    def test_entity_ref_requires_non_empty_identity(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EntityRef(entity_type="User", identity={})

    def test_field_value_dto_rejects_tuple_for_single(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FieldValueDTO(
                field=FieldPath(entity_type="User", field_name="name"),
                value_kind="scalar",
                cardinality="single",
                value=("alice",),
            )

    def test_entity_read_request_get_requires_selector(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EntityReadRequest(mode="get", entity_type="User")

    def test_field_mutation_retract_disallows_value(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FieldMutation(
                op="retract",
                field=FieldPath(entity_type="User", field_name="tag"),
                value="vip",
                assertion_id="asrt_1",
            )

    def test_entity_write_command_rejects_entity_type_mismatch(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EntityWriteCommand(
                target=EntitySelector(entity_type="User", identity={"name": "alice"}),
                mutations=(
                    FieldMutation(
                        op="set",
                        field=FieldPath(entity_type="Country", field_name="name"),
                        value="Germany",
                    ),
                ),
            )

    def test_entity_write_plan_requires_no_errors_when_applicable(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EntityWritePlan(
                command=EntityWriteCommand(
                    target=EntitySelector(entity_type="User", identity={"name": "alice"}),
                ),
                resolved_target=EntityRef(entity_type="User", identity={"name": "alice"}),
                can_apply=True,
                errors=(ErrorDTO(code="IDENTITY_INCOMPLETE", message="bad"),),
            )


if __name__ == "__main__":
    unittest.main()
