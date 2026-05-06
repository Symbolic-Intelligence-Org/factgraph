"""Minimal Batch 7 audit ProofFrame diff demo.

Run from the repository root:

    python examples/12_evidence_diff_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from kernel.audit import AuditQuery, load_audit_package
from kernel.audit.round_events import (
    finalize_round,
    project_proof_frame_event_payload,
    record_round_event,
    start_round,
)


def main() -> None:
    with TemporaryDirectory() as tmpdir:
        package_dir = _minimal_audit_package(Path(tmpdir) / "audit_pkg")
        _write_round(
            package_dir,
            round_id="round-baseline",
            status="still_valid",
            atom_verdicts={"b0.a0:pred": "still_valid"},
        )
        _write_round(
            package_dir,
            round_id="round-with-overlay",
            status="invalidated",
            atom_verdicts={"b0.a0:pred": "invalidated"},
        )

        package = load_audit_package(package_dir)
        diff = AuditQuery(package).diff_proof_frames(
            "round-baseline",
            "round-with-overlay",
        )

        print(f"{diff.round_a_id} -> {diff.round_b_id}")
        for frame in diff.frame_deltas:
            binding = ", ".join(f"{name}={value!r}" for name, value in frame.frame_identity.binding_items)
            print(f"- frame {frame.frame_identity.support_digest} [{binding}]")
            if frame.frame_status_change is not None:
                print(
                    "  status: "
                    f"{frame.frame_status_change.before} -> {frame.frame_status_change.after}"
                )
            for atom in frame.atom_deltas:
                print(
                    f"  {atom.atom_key}: {atom.kind} "
                    f"({atom.before_verdict} -> {atom.after_verdict})"
                )


def _write_round(
    package_dir: Path,
    *,
    round_id: str,
    status: str,
    atom_verdicts: dict[str, str],
) -> None:
    recorder = start_round(round_id, event_ts=100)
    payload = project_proof_frame_event_payload(
        SimpleNamespace(support_artifact=None, overlay=("demo-overlay",)),
        SimpleNamespace(
            status=status,
            binding_items=(("$p", "alice"),),
            atom_verdicts=tuple(
                SimpleNamespace(
                    atom_key=atom_key,
                    verdict=verdict,
                    affected_action_indices=(),
                )
                for atom_key, verdict in sorted(atom_verdicts.items())
            ),
        ),
    )
    record_round_event(
        recorder,
        kind="proof_frame_result",
        payload=payload,
        event_ts=101,
    )
    finalize_round(recorder, package_dir, event_ts=102)


def _minimal_audit_package(package_dir: Path) -> Path:
    audit_dir = package_dir / "audit"
    audit_dir.mkdir(parents=True)
    audit_files = {
        "run_ledger": "audit/run_ledger.jsonl",
        "candidate_ledger": "audit/candidate_ledger.jsonl",
        "accept_write_ledger": "audit/accept_write_ledger.jsonl",
        "accept_failed": "audit/accept_failed.jsonl",
        "mapping_resolution": "audit/mapping_resolution.json",
        "decision_log": "audit/decision_log.jsonl",
    }
    for key, rel_path in audit_files.items():
        path = package_dir / rel_path
        if key == "mapping_resolution":
            path.write_text("{}", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")
    manifest = {"package_kind": "audit", "paths": {"audit_files": audit_files}}
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    return package_dir


if __name__ == "__main__":
    main()
