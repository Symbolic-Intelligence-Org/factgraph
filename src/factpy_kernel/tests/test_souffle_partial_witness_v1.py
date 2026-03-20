from __future__ import annotations

import unittest

from factpy_kernel.adapters.souffle.engine_eval import (
    _ParsedWitnessRow,
    _build_support_rows_from_witness_rows,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.protocol.digests import sha256_token
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.store._support import (
    PredWitness,
    SOUFFLE_WITNESS_KIND,
    SupportArtifact,
    compute_support_digest,
    normalize_binding_items,
)
from factpy_kernel.core.store.runtime import Store
from factpy_kernel.sdk import Entity, Field, Identity, compile_schema_from_classes
from factpy_kernel.service.runtime_v1 import (
    RuntimeSession,
    _explain_ref_candidate,
    _get_candidate_tree,
)


class User(Entity):
    name: str = Identity(primary_key=True)
    status: str = Field(cardinality="single")


class SoufflePartialWitnessV1Tests(unittest.TestCase):
    def test_build_support_rows_from_witness_rows_merges_ids_and_prefers_lowest_branch(self) -> None:
        store = _MemorySupportStore()
        binding_items = normalize_binding_items({"$e": "user:alice", "$value": "Alice"})
        parsed_rows = [
            _ParsedWitnessRow(
                binding_items=binding_items,
                selected_branch_index=1,
                witness_atoms=(("b1.a0:user:status", "asrt-status"),),
            ),
            _ParsedWitnessRow(
                binding_items=binding_items,
                selected_branch_index=0,
                witness_atoms=(("b0.a0:user:name", "asrt-name-2"),),
            ),
            _ParsedWitnessRow(
                binding_items=binding_items,
                selected_branch_index=0,
                witness_atoms=(("b0.a0:user:name", "asrt-name-1"),),
            ),
        ]

        captures = _build_support_rows_from_witness_rows(
            store=store,
            where=[
                [("pred", "user:name", ["$e", "$value"])],
                [("pred", "user:status", ["$e", "$value"])],
            ],
            root_result_kind="fact",
            parsed_rows=parsed_rows,
        )

        self.assertEqual(len(captures), 1)
        capture = captures[0]
        self.assertEqual(capture.support_kind, SOUFFLE_WITNESS_KIND)
        artifact = store.support_artifacts[capture.support_digest]
        self.assertEqual(artifact.kind, SOUFFLE_WITNESS_KIND)
        self.assertEqual(
            [(row.pred_atom_key, row.asrt_ids) for row in artifact.pred_witnesses],
            [("b0.a0:user:name", ("asrt-name-1", "asrt-name-2"))],
        )

    def test_runtime_candidate_explain_and_tree_accept_souffle_witness_kind(self) -> None:
        store = Store(compile_schema_from_classes([User]))
        user_ref = encode_idref_v1("User", [("name", "string", "alice")])
        asrt_id = set_field(
            store.ledger,
            "user:name",
            user_ref,
            [("string", "Alice")],
        )
        artifact = SupportArtifact(
            kind=SOUFFLE_WITNESS_KIND,
            root_result_kind="fact",
            binding_items=normalize_binding_items({"$e": user_ref, "$value": "Alice"}),
            pred_witnesses=(
                PredWitness(
                    pred_atom_key="b0.a0:user:name",
                    asrt_ids=(asrt_id,),
                ),
            ),
            non_fact_steps=(),
            rule_refs=(),
            rule_ref_edges=(),
        )
        support_digest = compute_support_digest(artifact)
        store._remember_support_artifact(support_digest, artifact)
        store._remember_candidate_support("cand-souffle", support_digest, SOUFFLE_WITNESS_KIND)
        session = RuntimeSession(
            session_id="rt_test",
            store=store,
            ledger_path=None,
            registry_root=None,
            schema_digest=sha256_token(b"schema"),
            opened_at_ns=0,
            views={},
        )

        explain_resp = _explain_ref_candidate(session, "cand-souffle")
        self.assertEqual(explain_resp["kind"], "candidate")
        self.assertEqual(explain_resp["explain"]["support"]["kind"], SOUFFLE_WITNESS_KIND)

        tree = _get_candidate_tree(session, "cand-souffle")
        self.assertEqual(tree["support_kind"], SOUFFLE_WITNESS_KIND)
        support_section = tree["root"]["children"][0]
        self.assertEqual(support_section["node_kind"], "support_section")
        witness_group = support_section["children"][0]
        self.assertEqual(witness_group["node_kind"], "predicate_witness_group")
        self.assertEqual(witness_group["pred_atom_key"], "b0.a0:user:name")
        assertion_leaf = witness_group["children"][0]
        self.assertEqual(assertion_leaf["node_kind"], "assertion_fact")
        self.assertEqual(assertion_leaf["asrt_id"], asrt_id)


class _MemorySupportStore:
    def __init__(self) -> None:
        self.support_artifacts: dict[str, SupportArtifact] = {}

    def _remember_support_artifact(self, support_digest: str, artifact: SupportArtifact) -> None:
        self.support_artifacts[support_digest] = artifact


if __name__ == "__main__":
    unittest.main()
