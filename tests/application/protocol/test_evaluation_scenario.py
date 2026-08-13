from __future__ import annotations

from dataclasses import replace
import unittest

from factgraph.application.protocol import (
    EntityRef,
    FieldPath,
    ProtocolShapeError,
    ScenarioFieldSubstitutionV0,
    ScenarioResolutionV0,
    ScenarioResultDiffV0,
    ScenarioScalarValueV0,
)
from factgraph.core.protocol.digests import sha256_token


def _token(text: str) -> str:
    return sha256_token(text.encode("utf-8"))


class ScenarioProtocolTests(unittest.TestCase):
    def test_input_shape_is_narrow(self) -> None:
        valid = ScenarioFieldSubstitutionV0(
            EntityRef("Person", {"employee_id": "alice"}),
            FieldPath("Person", "age"),
            22,
            "age-hypothesis",
        )
        self.assertEqual(valid.premise_id, "age-hypothesis")
        for value in (None, [], {}, EntityRef("Person", {"employee_id": "bob"})):
            with self.subTest(value=value), self.assertRaises(ProtocolShapeError):
                ScenarioFieldSubstitutionV0(
                    EntityRef("Person", {"employee_id": "alice"}),
                    FieldPath("Person", "age"),
                    value,  # type: ignore[arg-type]
                    "age-hypothesis",
                )
        with self.assertRaises(ProtocolShapeError):
            ScenarioFieldSubstitutionV0(
                EntityRef("Person", {"employee_id": "alice"}),
                FieldPath("Other", "age"),
                22,
                "age-hypothesis",
            )

    def test_scalar_storage_is_canonical(self) -> None:
        self.assertEqual(ScenarioScalarValueV0("int", 22).value, 22)
        self.assertEqual(ScenarioScalarValueV0("bytes", "AP8").value, "AP8")
        self.assertEqual(ScenarioScalarValueV0("float64", "0x3ff0000000000000").value, "0x3ff0000000000000")
        for tag, value in (("uuid", "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"), ("bytes", "%%"), ("float64", "1.0")):
            with self.subTest(tag=tag, value=value), self.assertRaises(ProtocolShapeError):
                ScenarioScalarValueV0(tag, value)  # type: ignore[arg-type]

    def test_result_and_resolution_seal_their_derived_digests(self) -> None:
        baseline = _token("baseline")
        effective = _token("effective")
        diff = ScenarioResultDiffV0(1, 1, baseline, effective, True)
        self.assertTrue(diff.diff_digest.startswith("sha256:"))
        with self.assertRaises(ProtocolShapeError):
            ScenarioResultDiffV0(1, 1, baseline, effective, False)
        resolution = ScenarioResolutionV0(
            premise_id="age-hypothesis",
            entity_ref="idref_v1:Person:test",
            field=FieldPath("Person", "age"),
            baseline_value=ScenarioScalarValueV0("int", 22),
            effective_value=ScenarioScalarValueV0("int", 35),
            base_view_digest=_token("view"),
            baseline_relation_digest=_token("relation-before"),
            effective_relation_digest=_token("relation-after"),
            semantic_value_changed=True,
            effective_source_changed=True,
            result_diff=diff,
        )
        self.assertTrue(resolution.operation_digest.startswith("sha256:"))
        self.assertTrue(resolution.scenario_digest.startswith("sha256:"))
        self.assertNotEqual(
            resolution.scenario_digest,
            replace(resolution, result_diff=None).scenario_digest,
        )
        with self.assertRaises(ProtocolShapeError):
            replace(resolution, semantic_value_changed=False)


if __name__ == "__main__":
    unittest.main()
