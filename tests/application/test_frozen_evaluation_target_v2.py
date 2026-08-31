from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from factgraph.application.frozen_evaluation_target_v2 import (
    FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI,
    FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI,
    FrozenEvaluationTargetError,
    FrozenEvaluationTargetV2,
)
from factgraph.application.goal_plan_v2_runtime import (
    ProductInvocationAggregateLimitsV2,
    build_product_evaluation_invocation_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.sdk import SDKStore

from .test_branch_input_case_runtime import Person, _fixture


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _reseal(envelope: dict[str, object]) -> bytes:
    material = envelope["material"]
    payload = {
        "domain": "factgraph.frozen-evaluation-target-v2.material",
        "value": material,
    }
    envelope["material_digest"] = "sha256:" + hashlib.sha256(
        _canonical_bytes(payload)
    ).hexdigest()
    return _canonical_bytes(envelope)


def _first_record(value: object, suffix: str) -> dict[str, object] | None:
    if isinstance(value, dict):
        record = value.get("$record")
        if isinstance(record, str) and record.endswith(suffix):
            return value
        for item in value.values():
            found = _first_record(item, suffix)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _first_record(item, suffix)
            if found is not None:
                return found
    return None


def _runtime_graph(path: str | None = None) -> SDKStore:
    graph = SDKStore.create([Person], path=path)
    alice = graph.entities.create(Person, person_id="alice")
    graph.fields.set(Person.age, alice, 20)
    return graph


def _run(frozen: FrozenEvaluationTargetV2, graph: SDKStore):
    targeted = frozen.instantiate(
        "person",
        values={"person": EntityRef("Person", {"person_id": "alice"})},
    )
    invocation = build_product_evaluation_invocation_v2(
        graph=graph,
        primary=targeted,
        product_target=frozen.product_target,
        profile=graph.execution.native_deterministic(
            target=frozen.product_target
        ).build(),
        aggregate_limits=ProductInvocationAggregateLimitsV2(
            timeout_ms=30_000,
            max_rows=10,
            max_units=20,
            max_evidence_bytes=20_000,
            max_capture_bytes=1_000_000,
            max_scenarios=1,
        ),
    )
    return invocation.run()


class FrozenEvaluationTargetV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        graph, product, template, branch_ids = _fixture()
        self.frozen = FrozenEvaluationTargetV2(
            product,
            template.target,
            graph._application_schema_index,
            (template,),
        )
        graph.ledger.close()
        self.branch_ids = branch_ids
        self.raw = self.frozen.to_bytes()

    def test_bytes_and_digest_are_deterministic(self) -> None:
        graph, product, template, _branch_ids = _fixture()
        again = FrozenEvaluationTargetV2(
            product,
            template.target,
            graph._application_schema_index,
            (template,),
        )
        graph.ledger.close()
        self.assertEqual(again.to_bytes(), self.raw)
        self.assertEqual(again.material_digest, self.frozen.material_digest)
        restored = FrozenEvaluationTargetV2.from_bytes(self.raw)
        self.assertEqual(restored.to_bytes(), self.raw)
        self.assertEqual(restored.material_digest, self.frozen.material_digest)

    def test_decode_and_execute_never_calls_policy_compiler(self) -> None:
        graph = _runtime_graph()
        before = _run(self.frozen, graph)
        compiler_paths = (
            "factgraph.application.policy_runtime.compile_policy",
            "factgraph.application.evaluation_query_target_runtime.compile_policy",
            "factgraph.application.goal_plan_v2_runtime.compile_policy",
        )
        with (
            patch(compiler_paths[0], side_effect=AssertionError("compiler called")),
            patch(compiler_paths[1], side_effect=AssertionError("compiler called")),
            patch(compiler_paths[2], side_effect=AssertionError("compiler called")),
        ):
            restored = FrozenEvaluationTargetV2.from_bytes(self.raw)
            after = _run(restored, graph)
        graph.close()

        before_frame = before.effective.engine_frames[0]
        after_frame = after.effective.engine_frames[0]
        self.assertEqual(after_frame.observations, before_frame.observations)
        self.assertEqual(
            {
                (item.compiled_branch_id, item.evaluation_side, item.row_identity_digest)
                for item in after_frame.branch_witnesses
            },
            {
                (item.compiled_branch_id, item.evaluation_side, item.row_identity_digest)
                for item in before_frame.branch_witnesses
            },
        )
        self.assertEqual(
            {item.compiled_branch_id for item in after_frame.branch_witnesses},
            set(self.branch_ids),
        )

    def test_restart_process_decodes_and_executes_without_compiler(self) -> None:
        script = r'''
import json
import sys
from unittest.mock import patch

from factgraph.application.frozen_evaluation_target_v2 import FrozenEvaluationTargetV2
from factgraph.application.goal_plan_v2_runtime import (
    ProductInvocationAggregateLimitsV2,
    build_product_evaluation_invocation_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.sdk import SDKStore
from tests.application.test_branch_input_case_runtime import Person

graph = SDKStore.load_workspace(sys.argv[1], schema_classes=[Person])
with (
    patch("factgraph.application.policy_runtime.compile_policy", side_effect=AssertionError("compiler called")),
    patch("factgraph.application.evaluation_query_target_runtime.compile_policy", side_effect=AssertionError("compiler called")),
    patch("factgraph.application.goal_plan_v2_runtime.compile_policy", side_effect=AssertionError("compiler called")),
):
    frozen = FrozenEvaluationTargetV2.from_bytes(sys.stdin.buffer.read())
    targeted = frozen.instantiate(
        "person",
        values={"person": EntityRef("Person", {"person_id": "alice"})},
    )
    invocation = build_product_evaluation_invocation_v2(
        graph=graph,
        primary=targeted,
        product_target=frozen.product_target,
        profile=graph.execution.native_deterministic(target=frozen.product_target).build(),
        aggregate_limits=ProductInvocationAggregateLimitsV2(
            timeout_ms=30000,
            max_rows=10,
            max_units=20,
            max_evidence_bytes=20000,
            max_capture_bytes=1000000,
            max_scenarios=1,
        ),
    )
    run = invocation.run()
frame = run.effective.engine_frames[0]
print(json.dumps({
    "rows": [item.row_identity_digest for item in frame.observations],
    "witnesses": [
        [item.compiled_branch_id, item.row_identity_digest, item.proof_identity_digest]
        for item in frame.branch_witnesses
    ],
}, sort_keys=True))
graph.close()
'''
        with tempfile.TemporaryDirectory() as workspace:
            graph = _runtime_graph(workspace)
            before = _run(self.frozen, graph).effective.engine_frames[0]
            graph.save_workspace()
            graph.close()
            env = dict(os.environ)
            env["PYTHONPATH"] = "src"
            completed = subprocess.run(
                [sys.executable, "-c", script, workspace],
                cwd=os.getcwd(),
                env=env,
                input=self.raw,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", errors="replace"),
            )
            restarted = json.loads(completed.stdout)
        self.assertEqual(
            restarted["rows"],
            [item.row_identity_digest for item in before.observations],
        )
        self.assertEqual(
            sorted((item[0], item[1]) for item in restarted["witnesses"]),
            sorted(
                (item.compiled_branch_id, item.row_identity_digest)
                for item in before.branch_witnesses
            ),
        )

    def test_tamper_missing_material_unknown_version_and_abi_fail_closed(self) -> None:
        base = json.loads(self.raw)
        cases: list[tuple[dict[str, object], str]] = []

        digest_tamper = copy.deepcopy(base)
        digest_tamper["material_digest"] = "sha256:" + "0" * 64
        cases.append((digest_tamper, "FROZEN_TARGET_DIGEST_MISMATCH"))

        missing = copy.deepcopy(base)
        del missing["material"]["schema_ir"]
        cases.append((missing, "FROZEN_TARGET_MATERIAL_MISSING"))

        version = copy.deepcopy(base)
        version["version"] = 999
        cases.append((version, "FROZEN_TARGET_VERSION_UNSUPPORTED"))

        compiler_abi = copy.deepcopy(base)
        compiler_abi["compiler_abi"] = FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI + "-other"
        cases.append((compiler_abi, "FROZEN_TARGET_ABI_MISMATCH"))

        runtime_abi = copy.deepcopy(base)
        runtime_abi["runtime_abi"] = FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI + "-other"
        cases.append((runtime_abi, "FROZEN_TARGET_ABI_MISMATCH"))

        for envelope, code in cases:
            with self.subTest(code=code), self.assertRaises(
                FrozenEvaluationTargetError
            ) as raised:
                FrozenEvaluationTargetV2.from_bytes(_canonical_bytes(envelope))
            self.assertEqual(raised.exception.code, code)

    def test_resealed_missing_pin_and_unknown_record_fail_closed(self) -> None:
        missing_pin = json.loads(self.raw)
        pin = _first_record(missing_pin, ".PolicyRulePin")
        self.assertIsNotNone(pin)
        del pin["fields"]["rule_content_digest"]
        with self.assertRaises(FrozenEvaluationTargetError) as raised:
            FrozenEvaluationTargetV2.from_bytes(_reseal(missing_pin))
        self.assertEqual(raised.exception.code, "FROZEN_TARGET_MATERIAL_MISSING")

        unknown = json.loads(self.raw)
        record = _first_record(unknown, ".CompiledPolicyV0")
        self.assertIsNotNone(record)
        record["$record"] = "unknown.module.UnknownExecutable"
        with self.assertRaises(FrozenEvaluationTargetError) as raised:
            FrozenEvaluationTargetV2.from_bytes(_reseal(unknown))
        self.assertEqual(raised.exception.code, "FROZEN_TARGET_RECORD_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
