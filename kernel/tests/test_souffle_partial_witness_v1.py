from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kernel.adapters.souffle.tsv_v1 import write_tsv
from kernel.audit import (
    AuditQuery,
    build_candidate_evidence_tree_dto,
    build_candidate_evidence_tree_narrative_dto,
    build_candidate_evidence_tree_summary_dto,
    load_audit_package,
)
from service.static_ui import render_audit_static_site
from kernel.adapters.souffle.engine_eval import (
    _ParsedWitnessRow,
    _build_support_rows_from_witness_rows,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.protocol.digests import sha256_token
from kernel.core.protocol.idref_v1 import encode_idref_v1
from kernel.core.store._support import (
    PredWitness,
    SOUFFLE_WITNESS_KIND,
    SupportArtifact,
    compute_support_digest,
    normalize_binding_items,
    support_artifact_to_dict,
)
from kernel.core.store.runtime import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes
from service.runtime_v1 import (
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

    def test_audit_and_static_accept_souffle_witness_kind(self) -> None:
        user_ref = encode_idref_v1("User", [("name", "string", "alice")])
        artifact = SupportArtifact(
            kind=SOUFFLE_WITNESS_KIND,
            root_result_kind="fact",
            binding_items=normalize_binding_items({"$e": user_ref, "$value": "Alice"}),
            pred_witnesses=(
                PredWitness(
                    pred_atom_key="b0.a0:user:name",
                    asrt_ids=("asrt-user-name",),
                ),
            ),
            non_fact_steps=(),
            rule_refs=(),
            rule_ref_edges=(),
        )
        support_digest = compute_support_digest(artifact)

        with TemporaryDirectory() as tmpdir:
            package_dir = Path(tmpdir) / "pkg"
            _write_minimal_audit_package(
                package_dir=package_dir,
                candidate_id="cand-souffle",
                support_digest=support_digest,
                support_kind=SOUFFLE_WITNESS_KIND,
                artifact=artifact,
                asrt_id="asrt-user-name",
                pred_id="user:name",
                e_ref=user_ref,
                claim_args=["Alice"],
            )

            package = load_audit_package(package_dir)
            query = AuditQuery(package)

            tree = query.get_candidate_evidence_tree("cand-souffle")
            self.assertIsNotNone(tree)
            self.assertEqual(tree["support_kind"], SOUFFLE_WITNESS_KIND)
            witness_group = tree["root"]["children"][0]["children"][0]
            self.assertEqual(witness_group["node_kind"], "predicate_witness_group")
            self.assertEqual(witness_group["pred_atom_key"], "b0.a0:user:name")
            assertion_leaf = witness_group["children"][0]
            self.assertEqual(assertion_leaf["node_kind"], "assertion_fact")
            self.assertEqual(assertion_leaf["asrt_id"], "asrt-user-name")

            tree_dto = build_candidate_evidence_tree_dto(query, "cand-souffle")
            summary_dto = build_candidate_evidence_tree_summary_dto(query, "cand-souffle")
            narrative_dto = build_candidate_evidence_tree_narrative_dto(query, "cand-souffle")
            self.assertEqual(tree_dto["support_kind"], SOUFFLE_WITNESS_KIND)
            self.assertEqual(summary_dto["summary"]["support_kind"], SOUFFLE_WITNESS_KIND)
            self.assertIn("souffle_witness_v1", narrative_dto["narrative"]["headline"])

            site_dir = Path(tmpdir) / "site"
            render_audit_static_site(package_dir, site_dir)
            page = (site_dir / "candidate_evidence" / "cand-souffle.html").read_text(encoding="utf-8")
            self.assertIn("predicate_witness_group", page)
            self.assertIn("assertion_fact", page)
            self.assertIn("souffle_witness_v1", page)
            self.assertIn(narrative_dto["narrative"]["headline"], page)


class _MemorySupportStore:
    def __init__(self) -> None:
        self.support_artifacts: dict[str, SupportArtifact] = {}

    def _remember_support_artifact(self, support_digest: str, artifact: SupportArtifact) -> None:
        self.support_artifacts[support_digest] = artifact


def _write_minimal_audit_package(
    *,
    package_dir: Path,
    candidate_id: str,
    support_digest: str,
    support_kind: str,
    artifact: SupportArtifact,
    asrt_id: str,
    pred_id: str,
    e_ref: str,
    claim_args: list[str],
) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = package_dir / "audit"
    facts_dir = package_dir / "facts"
    audit_dir.mkdir(parents=True, exist_ok=True)
    facts_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "export_version": "v2",
        "package_kind": "audit",
        "paths": {
            "audit_files": {
                "run_ledger": "audit/run_ledger.jsonl",
                "candidate_ledger": "audit/candidate_ledger.jsonl",
                "accept_write_ledger": "audit/accept_write_ledger.jsonl",
                "accept_failed": "audit/accept_failed.jsonl",
                "decision_log": "audit/decision_log.jsonl",
                "mapping_resolution": "audit/mapping_resolution.json",
                "support_artifacts": "audit/support_artifacts.jsonl",
            },
            "facts": {
                "claim": "facts/claim.facts",
                "claim_arg": "facts/claim_arg.facts",
                "meta_str": "facts/meta_str.facts",
                "meta_time": "facts/meta_time.facts",
                "meta_int": "facts/meta_int.facts",
                "meta_float": "facts/meta_float.facts",
                "meta_bool": "facts/meta_bool.facts",
                "revokes": "facts/revokes.facts",
            },
        },
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (audit_dir / "run_ledger.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "accept_write_ledger.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "accept_failed.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "decision_log.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "mapping_resolution.json").write_text("{}\n", encoding="utf-8")
    (audit_dir / "candidate_ledger.jsonl").write_text(
        json.dumps(
            {
                "candidate_id": candidate_id,
                "support_digest": support_digest,
                "support_kind": support_kind,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "support_artifacts.jsonl").write_text(
        json.dumps(
            {"support_digest": support_digest, **support_artifact_to_dict(artifact)},
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    write_tsv(facts_dir / "claim.facts", [[asrt_id, pred_id, e_ref, "sha256:tup"]])
    write_tsv(
        facts_dir / "claim_arg.facts",
        [[asrt_id, str(index), value, "string"] for index, value in enumerate(claim_args)],
    )
    for name in ("meta_str", "meta_time", "meta_int", "meta_float", "meta_bool", "revokes"):
        write_tsv(facts_dir / f"{name}.facts", [])


if __name__ == "__main__":
    unittest.main()
