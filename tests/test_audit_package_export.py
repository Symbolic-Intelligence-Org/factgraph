"""Engine-neutral audit-package export (Block 1).

Proves that ``factgraph.audit.export_audit_package`` writes an audit package WITHOUT
Souffle (souffle is not installed in this dev environment, so merely running these tests
is the "no Souffle" condition), that the package round-trips through
``load_audit_package`` + ``AuditQuery`` against a REAL seeded store, that the
engine-neutral ledgers are byte-identical to the ones the Souffle adapter emits (so the
logic was relocated, not duplicated or changed), and that a fresh store stays honestly
empty.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import factgraph.adapters.souffle.package as souffle_package
from factgraph.audit import (
    AuditQuery,
    export_audit_package,
    load_audit_package,
    write_audit_artifacts,
)
from factgraph.application.derivation_runtime import accept_derivation_candidate_set
from factgraph.application.protocol import DerivationAcceptRequest
from factgraph.core.evidence.write_protocol import set_field
from factgraph.sdk import Case, EmitSpec, Inference, Pred, SDKStore, vars as sdk_vars
from factgraph.sdk.schema import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity()
    tag_seed: str = Field()
    tag: str = Field()


def _inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.audit_export.tag",
            version="v1",
            when=[Case([Pred("user:tag_seed", u, tag)], id="seed_path")],
            emits=EmitSpec("user:tag", [u, tag]),
        )


def _seed_real_store() -> SDKStore:
    """A real store with one accepted derived assertion (real run + accept-write)."""
    sdk = SDKStore([User])
    ref = sdk.entities.ref(User, user_id="Alice")
    set_field(
        sdk.ledger,
        pred_id="user:tag_seed",
        e_ref=ref,
        rest_terms=[("string", "vip")],
        meta={"source": "test"},
    )
    for cs in sdk.eval.evaluate_candidates(_inference(), engine="native"):
        accept_derivation_candidate_set(
            cs,
            DerivationAcceptRequest(
                approved_by="user-123",
                meta={"actor_id": "user-123", "tenant_id": "default", "action": "rule.accept"},
            ),
            store=sdk.store,
            derived_rule_id="inf.audit_export.tag",
            derived_rule_version="v1",
        )
    return sdk


class AuditPackageExportTests(unittest.TestCase):
    def test_export_audit_package_round_trips_real_store(self) -> None:
        sdk = _seed_real_store()
        with TemporaryDirectory() as tmp:
            manifest_path = export_audit_package(sdk.store, Path(tmp) / "pkg")
            self.assertTrue(manifest_path.exists())

            package = load_audit_package(manifest_path.parent)
            self.assertEqual(package.manifest["package_kind"], "audit")
            query = AuditQuery(package=package)

            runs = query.list_runs()
            self.assertEqual(len(runs), 1, "the single learning run is present")
            run_id = runs[0]["run_id"]

            accept_writes = query.list_accept_writes()
            self.assertTrue(accept_writes, "the accepted derived fact is in the accept-write ledger")
            self.assertEqual(accept_writes[0]["derived_rule_id"], "inf.audit_export.tag")
            self.assertEqual(accept_writes[0]["pred_id"], "user:tag")

            self.assertIsNotNone(query.get_run(run_id))
            bundle = query.get_run_bundle(run_id)
            self.assertEqual(bundle["run"]["run_id"], run_id)
            self.assertEqual(bundle["accept_writes"], accept_writes)

    def test_neutral_audit_ledgers_match_souffle_export(self) -> None:
        """Relocated, not duplicated: the neutral export and the Souffle adapter's audit
        branch write byte-identical audit/ ledgers for the same store."""
        sdk = _seed_real_store()
        # Pin time so the only export-time timestamp (mapping_resolution.generated_at)
        # matches across the two export calls; the ledger event_ts come from store meta
        # (identical for the same store).
        with TemporaryDirectory() as tmp, mock.patch("time.time_ns", return_value=1_700_000_000_000_000_000):
            neutral_dir = Path(tmp) / "neutral"
            souffle_dir = Path(tmp) / "souffle"
            export_audit_package(sdk.store, neutral_dir)
            souffle_package.export_package(
                sdk.store, souffle_dir, souffle_package.ExportOptions(package_kind="audit")
            )

            neutral_audit = _audit_bytes(neutral_dir)
            souffle_audit = _audit_bytes(souffle_dir)
            self.assertEqual(set(neutral_audit), set(souffle_audit))
            for rel in sorted(neutral_audit):
                self.assertEqual(
                    neutral_audit[rel], souffle_audit[rel], f"audit ledger differs: {rel}"
                )

    def test_export_audit_package_empty_store_is_honestly_empty(self) -> None:
        sdk = SDKStore([User])  # fresh: no accepts, no runs
        with TemporaryDirectory() as tmp:
            manifest_path = export_audit_package(sdk.store, Path(tmp) / "pkg")
            query = AuditQuery(package=load_audit_package(manifest_path.parent))
            self.assertEqual(query.list_runs(), [])
            self.assertEqual(query.list_accept_writes(), [])
            self.assertEqual(query.list_decisions(), [])
            self.assertEqual(query.list_failures(), [])

    def test_write_audit_artifacts_returns_required_audit_files(self) -> None:
        sdk = _seed_real_store()
        with TemporaryDirectory() as tmp:
            audit_files = write_audit_artifacts(sdk.store, Path(tmp) / "audit", policy_mode="edb")
            required = {
                "run_ledger",
                "candidate_ledger",
                "accept_write_ledger",
                "accept_failed",
                "mapping_resolution",
                "decision_log",
            }
            self.assertTrue(required.issubset(set(audit_files)))

    def test_package_export_module_is_engine_neutral(self) -> None:
        """The neutral module must never IMPORT the Souffle adapter (docstrings may
        mention it; actual import statements may not reference it)."""
        import ast
        import factgraph.audit.package_export as pe

        tree = ast.parse(Path(pe.__file__).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        offending = [name for name in imported if "adapters.souffle" in name]
        self.assertEqual(offending, [], f"neutral module imports Souffle adapter: {offending}")


def _audit_bytes(package_dir: Path) -> dict[str, bytes]:
    audit_dir = package_dir / "audit"
    return {
        path.relative_to(package_dir).as_posix(): path.read_bytes()
        for path in sorted(audit_dir.rglob("*"))
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
