"""
B3 Review Packet Generator.

Reruns the extraction + resolution pipeline (stops before bundle) on one or
more samples from the B3 manifest and emits a per-sample review packet
markdown file. Does NOT modify run_records.

Output: `./review/review_pass_<DATE>_<sample_id>.md`, one file per sample.

Usage:
    PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python generate_review_packet.py \\
        --manifest samples_manifest.yaml \\
        --sample medium_01_security

    PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python generate_review_packet.py \\
        --manifest samples_manifest.yaml \\
        --sample-ids medium_01_security,long_01_kernel_p0

Notes:
    - The rerun uses the exact same manifest + schema_ir + prompt the archived
      iter 4 run used. With temperature=0.0 the regeneration should match the
      archived run_record spec counts (medium: 14 valid; long: 57 valid).
      Any drift is noted in the packet header.
    - The archived bundle IDs (`bundle_5cd1b343998c`, `bundle_172f0fcd7765`)
      cannot be reproduced because BundleManager is in-memory only. The packet
      references new, regenerated spec data; the archived run_records stay
      untouched.
    - Per-draft field format is YAML-like blocks (not a markdown table) because
      each draft has multi-line raw_text that doesn't fit a cell.
    - This script is one-shot and intentionally standalone. It reuses helper
      functions from run_load_test.py via import.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow importing helpers from run_load_test.py in the same directory.
sys.path.insert(0, str(Path(__file__).parent))

from run_load_test import (  # noqa: E402
    _build_extraction_stack,
    _build_scope,
    _build_tracer,
    _load_env_file,
    _read_manifest,
    _read_schema_ir,
)


# ─────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────


def _render_yaml_scalar(value: Any) -> str:
    """Render a scalar value as a single-line YAML-safe string.

    Strings are always double-quoted with internal quotes escaped. None/bool/
    numbers render as their YAML forms.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{str(value)}"'


def _render_entity_identity(identity: dict[str, Any]) -> list[str]:
    """Render entity_identity as indented YAML lines."""
    if not identity:
        return ["entity_identity: {}"]
    out = ["entity_identity:"]
    for name, value in identity.items():
        out.append(f"  {name}: {_render_yaml_scalar(value)}")
    return out


def _render_field_values(field_values: list[tuple[str, Any]]) -> list[str]:
    """Render field_values as indented YAML lines."""
    if not field_values:
        return ["field_values: []"]
    out = ["field_values:"]
    for tag, value in field_values:
        out.append(f"  - tag: {_render_yaml_scalar(tag)}")
        out.append(f"    value: {_render_yaml_scalar(value)}")
    return out


def _render_raw_text_block(raw_text: str, *, indent: str = "  ") -> list[str]:
    """Render raw_text as a YAML literal block scalar (|).

    Each line is prefixed with the given indent. Empty raw_text renders as
    ``raw_text: ""`` for compactness.
    """
    if raw_text == "":
        return ['raw_text: ""']
    out = ["raw_text: |"]
    for line in raw_text.splitlines() or [""]:
        out.append(f"{indent}{line}")
    return out


def _truncate_for_header(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ─────────────────────────────────────────────────────────────
# Packet builder
# ─────────────────────────────────────────────────────────────


def _build_packet_markdown(
    *,
    sample_id: str,
    sample_path: Path,
    doc_id: str,
    total_segments: int,
    proposal_count: int,
    valid_count: int,
    rejection_count: int,
    resolved_specs: list[Any],
    archived_run_record: Path | None,
    archived_bundle_id: str | None,
    archived_valid_count: int | None,
    generated_at: datetime,
) -> str:
    """Build the full markdown packet for one sample.

    `resolved_specs` is a list of FactDraftSpec instances (from EntityResolver).
    Each spec has: entity_type, entity_identity, pred_id, field_values,
    extraction_provenance, confidence, note.
    """
    lines: list[str] = []

    lines.append(f"# Review Pass 2026-04-11 — {sample_id}")
    lines.append("")
    lines.append("## Header")
    lines.append("")
    lines.append(f"- sample_id: `{sample_id}`")
    lines.append(f"- sample_path: `{sample_path.as_posix()}`")
    lines.append(f"- doc_id: `{doc_id}`")
    lines.append(f"- total_segments: {total_segments}")
    lines.append(f"- total_proposal_count (regen): {proposal_count}")
    lines.append(f"- total_valid_count (regen): {valid_count}")
    lines.append(f"- total_rejection_count (regen): {rejection_count}")
    lines.append(f"- generated_at: {generated_at.isoformat()}")
    lines.append("")

    lines.append("### Archived iter 4 reference")
    lines.append("")
    if archived_run_record is not None:
        lines.append(f"- archived_run_record: `{archived_run_record.as_posix()}`")
    else:
        lines.append("- archived_run_record: (none)")
    if archived_bundle_id is not None:
        lines.append(f"- archived_bundle_id: `{archived_bundle_id}` (in-memory only, not reproducible)")
    if archived_valid_count is not None:
        drift = valid_count - archived_valid_count
        drift_note = (
            "exact match with archived iter 4"
            if drift == 0
            else f"**drift from archived iter 4: {drift:+d}**"
        )
        lines.append(f"- archived_valid_count: {archived_valid_count} — {drift_note}")
    lines.append("")
    lines.append(
        "The archived iter 4 bundle IDs died with the process that created them "
        "(`BundleManager` is in-memory only). This packet references newly "
        "regenerated specs. With `temperature=0.0` the regeneration should "
        "produce the same spec counts as the archived run; any drift is noted "
        "above."
    )
    lines.append("")

    lines.append("## Review instructions")
    lines.append("")
    lines.append("For each draft below, fill in the `REVIEW` block at the bottom:")
    lines.append("")
    lines.append("- `approve`: one of `yes` | `no` | `partial`")
    lines.append("  - `yes` — the extracted fact is supported by `raw_text` and semantically correct")
    lines.append("  - `no` — the fact is wrong, hallucinated, or unsupported by `raw_text`")
    lines.append("  - `partial` — the fact is partially correct but needs rewording, scoping, or a different predicate")
    lines.append("- `reason_code`: one of")
    lines.append("  - `CORRECT` — no issue (use with `approve: yes`)")
    lines.append("  - `HALLUCINATED` — fact is not present in raw_text at all")
    lines.append("  - `OVERGENERAL` — fact is in raw_text but the object is too broad / too vague")
    lines.append("  - `WRONG_ENTITY` — subject entity is mis-identified")
    lines.append("  - `WRONG_PREDICATE` — relation should use a different pred_id")
    lines.append("  - `WRONG_ARG` — the object/field_values value is factually wrong")
    lines.append("  - `DUPLICATE` — same fact as another approved draft in this packet")
    lines.append("  - `AMBIGUOUS` — raw_text is genuinely ambiguous; cannot judge")
    lines.append("  - `OTHER` — fill in notes")
    lines.append("- `notes`: free-text, optional")
    lines.append("")
    lines.append(
        "Summary metrics will be backfilled into the run_record `review` block "
        "after the pass is complete. This packet is the source of truth for "
        "per-draft decisions."
    )
    lines.append("")

    lines.append("---")
    lines.append("")

    if not resolved_specs:
        lines.append("## Drafts")
        lines.append("")
        lines.append("_(no resolved specs produced by the regeneration)_")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append("## Drafts")
    lines.append("")

    for idx, spec in enumerate(resolved_specs):
        entity_type = spec.entity_type
        entity_identity = dict(spec.entity_identity)
        pred_id = spec.pred_id
        field_values = list(spec.field_values)
        confidence = spec.confidence
        note = spec.note
        prov = spec.extraction_provenance

        identity_summary = ", ".join(
            f"{k}={_truncate_for_header(str(v), 40)}" for k, v in entity_identity.items()
        )
        field_summary_parts: list[str] = []
        for tag, value in field_values:
            field_summary_parts.append(
                f"{tag}={_truncate_for_header(str(value), 40)}"
            )
        field_summary = " | ".join(field_summary_parts) if field_summary_parts else "(none)"

        lines.append(f"### Draft {idx + 1:03d}")
        lines.append("")
        lines.append("```yaml")
        lines.append(f"draft_index: {idx}")
        lines.append(f"entity_type: {_render_yaml_scalar(entity_type)}")
        lines.extend(_render_entity_identity(entity_identity))
        lines.append(f"pred_id: {_render_yaml_scalar(pred_id)}")
        lines.extend(_render_field_values(field_values))
        lines.append(f"confidence: {_render_yaml_scalar(confidence)}")
        lines.append(f"note: {_render_yaml_scalar(note)}")
        lines.append("")
        lines.append("provenance:")
        lines.append(f"  source_document_id: {_render_yaml_scalar(prov.source_document_id)}")
        lines.append(f"  segment_id: {_render_yaml_scalar(prov.segment_id)}")
        lines.append(f"  char_offset_start: {prov.char_offset_start}")
        lines.append(f"  char_offset_end: {prov.char_offset_end}")
        lines.append(f"  page_number: {_render_yaml_scalar(prov.page_number)}")
        lines.append(f"  extraction_method: {_render_yaml_scalar(prov.extraction_method)}")
        merged_from_count = len(prov.merged_from) if hasattr(prov, "merged_from") else 0
        lines.append(f"  merged_from_count: {merged_from_count}")
        indented = [f"  {line}" for line in _render_raw_text_block(prov.raw_text, indent="  ")]
        lines.extend(indented)
        lines.append("```")
        lines.append("")
        lines.append(f"**Summary**: `{entity_type}({identity_summary}) -- {pred_id} --> {field_summary}`")
        lines.append("")
        lines.append("```yaml")
        lines.append("REVIEW:")
        lines.append('  approve: ""         # yes | no | partial')
        lines.append('  reason_code: ""     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER')
        lines.append('  notes: ""')
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────
# Pipeline rerun
# ─────────────────────────────────────────────────────────────


def _regenerate_specs_for_sample(
    *,
    sample: dict[str, Any],
    manifest: dict[str, Any],
    manifest_dir: Path,
    schema_ir: dict[str, Any],
) -> tuple[list[Any], dict[str, Any]]:
    """Run stage → batch extract → resolve, stopping before bundle.

    Returns (resolved_specs, pipeline_summary) where summary is a dict with
    the keys the packet builder needs.
    """
    from factpy_kernel.agent.documents import StagingError, StagingResult
    from factpy_kernel.agent.extraction import (
        BatchExtractionError,
        BatchExtractionResult,
        ResolutionError,
        ResolutionResult,
    )

    sample_path = manifest_dir / sample["path"]
    content = sample_path.read_bytes()

    tracer = _build_tracer(manifest.get("langfuse"))
    scope = _build_scope(manifest["scope"])
    (
        staging,
        _ext_agent,
        batch_extractor,
        entity_resolver,
        _batch_cfg_obj,
    ) = _build_extraction_stack(
        extraction_config=manifest["extraction_config"],
        batch_config=manifest.get("batch_config", {}),
        resolution_config=manifest.get("resolution_config", {}),
        tracer=tracer,
    )

    stage_outcome = staging.stage_document(
        doc_name=sample_path.name,
        content=content,
        doc_type=sample["doc_type"],
    )
    if isinstance(stage_outcome, StagingError):
        raise RuntimeError(f"staging failed: {stage_outcome.error_kind}: {stage_outcome.error_message}")
    assert isinstance(stage_outcome, StagingResult)

    batch_outcome = batch_extractor.extract_batch(
        segments=list(stage_outcome.segments),
        schema_ir=schema_ir,
        scope=scope,
    )
    if isinstance(batch_outcome, BatchExtractionError):
        raise RuntimeError(
            f"batch extraction failed: {batch_outcome.error_kind}: {batch_outcome.error_message}"
        )
    assert isinstance(batch_outcome, BatchExtractionResult)

    if not batch_outcome.aggregated_specs:
        resolved_specs: list[Any] = []
    else:
        resolve_outcome = entity_resolver.resolve_batch(list(batch_outcome.aggregated_specs))
        if isinstance(resolve_outcome, ResolutionError):
            raise RuntimeError(
                f"resolution failed: {resolve_outcome.error_kind}: {resolve_outcome.error_message}"
            )
        assert isinstance(resolve_outcome, ResolutionResult)
        resolved_specs = list(resolve_outcome.resolved_specs)

    pipeline_summary = {
        "doc_id": stage_outcome.source.doc_id,
        "total_segments": len(stage_outcome.segments),
        "proposal_count": batch_outcome.metrics.total_proposal_count,
        "valid_count": batch_outcome.metrics.total_valid_count,
        "rejection_count": batch_outcome.metrics.total_rejection_count,
    }
    return resolved_specs, pipeline_summary


# ─────────────────────────────────────────────────────────────
# Archived reference lookup
# ─────────────────────────────────────────────────────────────


_ARCHIVED_ITER4_REFERENCES: dict[str, dict[str, Any]] = {
    "medium_01_security": {
        "run_record": "run_records/b3_20260410T194444Z_medium_01_security.json",
        "bundle_id": "bundle_5cd1b343998c",
        "valid_count": 14,
    },
    "long_01_kernel_p0": {
        "run_record": "run_records/b3_20260410T194711Z_long_01_kernel_p0.json",
        "bundle_id": "bundle_172f0fcd7765",
        "valid_count": 57,
    },
}


def _archived_reference_for(sample_id: str, manifest_dir: Path) -> dict[str, Any]:
    ref = _ARCHIVED_ITER4_REFERENCES.get(sample_id, {})
    if not ref:
        return {
            "run_record": None,
            "bundle_id": None,
            "valid_count": None,
        }
    return {
        "run_record": manifest_dir / ref["run_record"],
        "bundle_id": ref["bundle_id"],
        "valid_count": ref["valid_count"],
    }


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────


def _load_env(manifest_dir: Path) -> None:
    current = manifest_dir
    while True:
        if (current / "pyproject.toml").exists() or (current / ".env").exists():
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    root_env = current / ".env"
    if root_env.exists():
        n = _load_env_file(root_env)
        print(f"  [env] loaded {n} var(s) from {root_env}")
    local_env = manifest_dir / ".env"
    if local_env.exists() and local_env.resolve() != root_env.resolve():
        n = _load_env_file(local_env)
        print(f"  [env] loaded {n} var(s) from {local_env}")


def main() -> int:
    parser = argparse.ArgumentParser(description="B3 Review Packet Generator")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sample", type=str, default=None, help="Single sample_id to regenerate")
    parser.add_argument(
        "--sample-ids",
        type=str,
        default=None,
        help="Comma-separated sample_ids (alternative to --sample)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for review packet files (default: <manifest_dir>/review)",
    )
    args = parser.parse_args()

    if not args.sample and not args.sample_ids:
        parser.error("Must specify --sample or --sample-ids")

    manifest_path = args.manifest.resolve()
    manifest_dir = manifest_path.parent

    _load_env(manifest_dir)

    manifest = _read_manifest(manifest_path)
    schema_ir_rel = manifest.get("schema_ir_path", "./test_schema_ir.json")
    schema_ir_path = (manifest_dir / schema_ir_rel).resolve()
    schema_ir = _read_schema_ir(schema_ir_path)

    if args.sample:
        sample_ids = [args.sample]
    else:
        sample_ids = [s.strip() for s in args.sample_ids.split(",") if s.strip()]

    samples_by_id = {s["sample_id"]: s for s in manifest["samples"]}
    missing = [sid for sid in sample_ids if sid not in samples_by_id]
    if missing:
        print(f"ERROR: sample_id(s) not found in manifest: {missing}")
        return 1

    output_dir = args.output_dir or (manifest_dir / "review")
    output_dir.mkdir(parents=True, exist_ok=True)

    for sid in sample_ids:
        sample = samples_by_id[sid]
        print(f"→ regenerating specs for {sid} ...")
        resolved_specs, summary = _regenerate_specs_for_sample(
            sample=sample,
            manifest=manifest,
            manifest_dir=manifest_dir,
            schema_ir=schema_ir,
        )
        print(
            f"  proposals={summary['proposal_count']} "
            f"valid={summary['valid_count']} "
            f"rejected={summary['rejection_count']} "
            f"resolved_specs={len(resolved_specs)}"
        )

        archived = _archived_reference_for(sid, manifest_dir)
        md = _build_packet_markdown(
            sample_id=sid,
            sample_path=manifest_dir / sample["path"],
            doc_id=summary["doc_id"],
            total_segments=summary["total_segments"],
            proposal_count=summary["proposal_count"],
            valid_count=summary["valid_count"],
            rejection_count=summary["rejection_count"],
            resolved_specs=resolved_specs,
            archived_run_record=archived["run_record"],
            archived_bundle_id=archived["bundle_id"],
            archived_valid_count=archived["valid_count"],
            generated_at=datetime.now(timezone.utc),
        )
        out_path = output_dir / f"review_pass_2026-04-11_{sid}.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"  → wrote {out_path.relative_to(manifest_dir)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
