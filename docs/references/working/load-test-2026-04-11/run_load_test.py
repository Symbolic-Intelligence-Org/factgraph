"""
B3 Load Test Runner — minimal executable pipeline.

This is NOT part of the agent codebase. It's a standalone script that drives
the agent end-to-end on real documents for load testing.

Usage:
    python run_load_test.py --manifest samples_manifest.yaml --sample short_01_pdf
    python run_load_test.py --manifest samples_manifest.yaml --all
    python run_load_test.py --manifest samples_manifest.yaml --all --dry-run
    python run_load_test.py --manifest samples_manifest.yaml --sample medium_02_blueprint_backref --commit

Pipeline (dry-run, DEFAULT): stage → batch extract → resolve → bundle preview (stops before commit)
Pipeline (--commit):         stage → batch extract → resolve → create_document_bundle → open_bundle_review → apply_bundle_review (all approve) → commit_bundle → stdout query_claims verification

Prerequisites:
    - pymupdf, pymupdf4llm, python-docx
    - instructor, litellm
    - Optional: langfuse (for tracing)
    - OPENAI_API_KEY (or other provider key) in env
    - Optional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY in env

Commit path (--commit, non-dry-run):
    Implemented via the ReadReviewOrchestrator facade per blueprint
    `2026-04-11_load-test-runner-commit-path` (scoped 2026-04-11).

    Commit-mode setup builds a per-invocation CommitStack holding:
    LocalRuntimeAPI + AgentSession (runtime-bound) + CandidatePayloadCache +
    AgentCheckpointStore + KGReadTools + ExplainTools + EvaluateTools +
    WriteTools + DocumentStaging + DraftManager + BundleManager +
    ReadReviewOrchestrator. The session is opened via
    `service.runtime_v1.open_runtime_session(open_dto)` (module-level
    function), NOT via LocalRuntimeAPI methods.

    Per-run isolation (CP-03): each --commit invocation creates a fresh
    tempdir `{tempdir}/b3_commit_{run_id}_XXXXXX/` containing `ledger.db`
    (runtime ledger) and `burr.db` (agent session + candidate_cache +
    checkpoint state). The tempdir is kept for post-mortem inspection
    after the run; OS /tmp cleanup handles long-term accumulation.

    Per-sample commit uses 4 orchestrator calls (CP-04):
      1. orchestrator.create_document_bundle(...)
      2. orchestrator.open_bundle_review(bundle_id)
      3. orchestrator.apply_bundle_review(bundle_id, [all-approve actions])
      4. orchestrator.commit_bundle(bundle_id, kind="add", confirmed_by=...)

    Optional post-commit verification (CP-12): after a successful commit,
    the runner calls kg_read_tools.query_claims() for up to 3 committed
    predicates and prints `[commit_verify] ... claim_count=N` lines to
    stdout. No new run_record schema fields; run_record uses the existing
    `bundle.committed_count` / `bundle.preview_only` / `bundle.commit_note`
    fields as the primary acceptance signal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────
# Manifest + config helpers
# ─────────────────────────────────────────────────────────────


def _load_env_file(env_path: Path) -> int:
    """
    Minimal .env loader (no python-dotenv dependency).

    Parses `KEY=VALUE` lines; ignores blank lines and `#` comments.
    Supports optional surrounding single/double quotes on the value.
    Only sets os.environ[KEY] if KEY is not already in os.environ
    (shell-env wins over file).

    Returns the number of variables loaded from the file.
    Silent no-op if the file doesn't exist.
    """
    if not env_path.exists():
        return 0
    loaded = 0
    with env_path.open() as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            # strip one layer of surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
                loaded += 1
    return loaded


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        print("ERROR: pyyaml not installed. Install with: pip install pyyaml")
        sys.exit(1)
    with manifest_path.open() as f:
        return yaml.safe_load(f)


def _read_schema_ir(schema_ir_path: Path) -> dict[str, Any]:
    with schema_ir_path.open() as f:
        return json.load(f)


def _read_commit_schema_ir(
    manifest: dict[str, Any],
    manifest_dir: Path,
) -> dict[str, Any]:
    """Load the canonical schema used by --commit mode's runtime session.

    Reads `commit_schema_ir_path` from the manifest if present, otherwise
    falls back to `test_schema_ir_canonical.json` next to the manifest.
    This schema is DIFFERENT from `schema_ir_path` — extraction uses the
    provisional schema, while `--commit` uses this canonical schema only
    for `service.runtime_v1.open_runtime_session(...)`.

    See: docs/blueprints/active/2026-04-11_b3-schema-canonicalization.md
    (SC-02, SC-04, SC-05)
    """
    rel = manifest.get("commit_schema_ir_path", "./test_schema_ir_canonical.json")
    path = (manifest_dir / rel).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"commit mode requires a canonical schema; not found at: {path}"
        )
    with path.open() as f:
        return json.load(f)


def _detect_dependencies() -> dict[str, bool]:
    """Check whether each optional dependency is importable."""
    status: dict[str, bool] = {}
    for name in ("pymupdf", "pymupdf4llm", "docx", "instructor", "litellm", "yaml", "langfuse"):
        try:
            if name == "docx":
                import docx  # type: ignore # noqa: F401
            elif name == "pymupdf":
                import pymupdf  # type: ignore # noqa: F401
            elif name == "pymupdf4llm":
                import pymupdf4llm  # type: ignore # noqa: F401
            elif name == "instructor":
                import instructor  # type: ignore # noqa: F401
            elif name == "litellm":
                import litellm  # type: ignore # noqa: F401
            elif name == "yaml":
                import yaml  # type: ignore # noqa: F401
            elif name == "langfuse":
                import langfuse  # type: ignore # noqa: F401
            status[name] = True
        except ImportError:
            status[name] = False
    return status


def _build_scope(scope_config: dict[str, Any]) -> Any:
    from factpy_kernel.agent import AgentScope
    return AgentScope(
        allowed_entity_types=(
            frozenset(scope_config["allowed_entity_types"])
            if scope_config.get("allowed_entity_types") else None
        ),
        allowed_pred_ids=(
            frozenset(scope_config["allowed_pred_ids"])
            if scope_config.get("allowed_pred_ids") else None
        ),
        max_batch_size=int(scope_config.get("max_batch_size", 100)),
        require_source=bool(scope_config.get("require_source", False)),
        min_confidence=float(scope_config.get("min_confidence", 0.0)),
        agent_id=scope_config.get("agent_id", "b3_load_test"),
        allow_document_ingest=bool(scope_config.get("allow_document_ingest", True)),
    )


def _build_tracer(langfuse_cfg: dict[str, Any] | None) -> Any:
    from factpy_kernel.agent.observability import build_tracer, LangfuseConfig

    if not langfuse_cfg or not langfuse_cfg.get("enabled"):
        return build_tracer(langfuse_config=None)

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = os.environ.get("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        print(
            "WARNING: Langfuse enabled in manifest but LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY not set. Degrading to NoOpTracer."
        )
        return build_tracer(langfuse_config=None)

    return build_tracer(
        langfuse_config=LangfuseConfig(
            public_key=pk,
            secret_key=sk,
            host=langfuse_cfg.get("host"),
        )
    )


def _build_extraction_stack(
    extraction_config: dict[str, Any],
    batch_config: dict[str, Any],
    resolution_config: dict[str, Any],
    tracer: Any,
) -> tuple[Any, Any, Any, Any, Any]:
    """Construct DocumentStaging + ExtractionAgent + BatchExtractor + EntityResolver.

    Returns (staging, ext_agent, batch_extractor, entity_resolver, batch_config_obj).
    """
    from factpy_kernel.agent import DocumentStaging
    from factpy_kernel.agent.extraction import (
        ExtractionAgent,
        ExtractionConfig,
        BatchExtractor,
        BatchExtractionConfig,
        EntityResolver,
        ResolutionConfig,
    )

    staging = DocumentStaging()

    ext_agent = ExtractionAgent(
        config=ExtractionConfig(
            model=extraction_config.get("model", "gpt-4o-mini"),
            max_retries=int(extraction_config.get("max_retries", 2)),
            temperature=float(extraction_config.get("temperature", 0.0)),
            max_text_chars=int(extraction_config.get("max_text_chars", 4000)),
            timeout_seconds=float(extraction_config.get("timeout_seconds", 30.0)),
        ),
        tracer=tracer,
    )

    batch_cfg_obj = BatchExtractionConfig(
        max_segments_per_batch=int(batch_config.get("max_segments_per_batch", 1000)),
        early_stop_on_batch_cap_reached=bool(
            batch_config.get("early_stop_on_batch_cap_reached", True)
        ),
    )
    batch_extractor = BatchExtractor(
        extraction_agent=ext_agent,
        batch_config=batch_cfg_obj,
        tracer=tracer,
    )

    entity_resolver = EntityResolver(
        config=ResolutionConfig(
            enable_dedupe=bool(resolution_config.get("enable_dedupe", True)),
            max_input_specs=int(resolution_config.get("max_input_specs", 10000)),
        ),
        tracer=tracer,
    )

    return staging, ext_agent, batch_extractor, entity_resolver, batch_cfg_obj


def _build_bundle_preview_stack(
    *,
    scope: Any,
) -> tuple[Any, Any, Any]:
    """Construct the minimal 4C2 carrier stack for bundle preview."""
    from factpy_kernel.agent import AgentSession, BundleManager, DraftManager

    session = AgentSession(scope=scope, status="active")
    draft_manager = DraftManager()
    bundle_manager = BundleManager(draft_manager=draft_manager)
    return session, draft_manager, bundle_manager


# ─────────────────────────────────────────────────────────────
# Commit path stack (--commit opt-in only)
# Per blueprint 2026-04-11_load-test-runner-commit-path (scoped).
# CP-13 spells out the full orchestrator dependency tree.
# ─────────────────────────────────────────────────────────────


@dataclass
class CommitStack:
    """Full commit-mode stack built once per --commit invocation.

    Fields correspond 1:1 to the CP-13 dependency tree. Caller is
    responsible for closing candidate_cache, checkpoint_store, and the
    runtime session in teardown (see main() try/finally).
    """

    runtime_api: Any               # LocalRuntimeAPI (stateless)
    runtime_session_id: str
    agent_session: Any             # AgentSession (runtime-bound)
    draft_manager: Any             # DraftManager
    bundle_manager: Any            # BundleManager
    orchestrator: Any              # ReadReviewOrchestrator
    candidate_cache: Any           # CandidatePayloadCache (needs .close())
    checkpoint_store: Any          # AgentCheckpointStore (needs .close())
    kg_read_tools: Any             # KGReadTools (for CP-12 post-commit verification)
    commit_tmpdir: Path            # per-run isolated tempdir (CP-03)
    ledger_path: str
    burr_db_path: str


def _build_commit_stack(
    *,
    scope: Any,
    schema_ir: dict[str, Any],
    commit_run_id: str,
) -> CommitStack:
    """Build the full commit-mode stack per CP-13.

    Creates a per-run isolated tempdir containing both `ledger.db`
    (runtime ledger) and `burr.db` (agent session + candidate_cache +
    checkpoint state). Opens a runtime session via the module-level
    `service.runtime_v1.open_runtime_session(open_dto)` function (Q6).
    Binds the AgentSession to that runtime session via
    `bind_runtime_session(runtime_session_id, bootstrap_spec=..., burr_db_path=...)`
    (Q2). Constructs the orchestrator and all its dependencies (CP-13).

    Parameters
    ----------
    scope : AgentScope
        Already-constructed scope from `_build_scope(manifest["scope"])`.
    schema_ir : dict
        Loaded schema IR that will be passed in the `open_dto` dict.
    commit_run_id : str
        Invocation-level run id used to name the tempdir prefix. Generated
        once by main() when --commit is set. Distinct from per-sample run_ids
        generated inside `_empty_record()`.

    Returns
    -------
    CommitStack
        Fully wired commit stack with all fields populated.

    Raises
    ------
    RuntimeError
        If `open_runtime_session()` returns `{"ok": False, ...}`.
    """
    # All agent/service imports live inside the function so that dry-run
    # invocations (the default) don't pay the import cost.
    from factpy_kernel.agent import (
        AgentCheckpointStore,
        AgentSession,
        BundleManager,
        CandidatePayloadCache,
        DocumentStaging,
        DraftManager,
        ReadReviewOrchestrator,
        RuntimeBootstrapSpec,
        WriteTools,
    )
    from factpy_kernel.agent.tools._runtime_api import LocalRuntimeAPI
    from factpy_kernel.agent.tools.evaluate import EvaluateTools
    from factpy_kernel.agent.tools.explain import ExplainTools
    from factpy_kernel.agent.tools.kg_read import KGReadTools
    from factpy_kernel.service.runtime_v1 import open_runtime_session

    # CP-03: per-run isolated tempdir containing BOTH SQLite files
    commit_tmpdir = Path(tempfile.mkdtemp(prefix=f"b3_commit_{commit_run_id}_"))
    ledger_path = str(commit_tmpdir / "ledger.db")
    burr_db_path = str(commit_tmpdir / "burr.db")

    # CP-14 (deviation, 2026-04-11): the canonical runtime validator inside
    # service.runtime_v1.open_runtime_session rejects top-level keys it does
    # not recognize. The B3 provisional test_schema_ir.json carries a self-
    # describing "_note" annotation (and may carry other `_`-prefixed metadata
    # in the future). Strip any `_`-prefixed top-level keys from schema_ir
    # before handing it to the canonical validator. The source fixture is
    # NOT modified; this filter is runner-local and only affects --commit
    # mode. Dry-run / extraction / staging paths continue to see the full
    # schema_ir including `_note`.
    schema_ir_for_commit: dict[str, Any] = {
        k: v for k, v in schema_ir.items() if not k.startswith("_")
    }
    stripped_meta_keys = sorted(set(schema_ir) - set(schema_ir_for_commit))
    if stripped_meta_keys:
        print(
            f"  [commit] CP-14: stripped non-canonical schema_ir metadata keys "
            f"for open_dto: {stripped_meta_keys}",
            flush=True,
        )

    # Q1 + Q6: open_dto is a plain dict; open session via service.runtime_v1
    open_dto: dict[str, Any] = {
        "schema_ir": schema_ir_for_commit,
        "ledger_path": ledger_path,
    }
    resp = open_runtime_session(open_dto)
    if not resp.get("ok"):
        raise RuntimeError(f"open_runtime_session failed: {resp}")
    runtime_session_id = resp["session"]["session_id"]

    # Q2: bind_runtime_session(runtime_session_id, bootstrap_spec=..., burr_db_path=...)
    agent_session = AgentSession(scope=scope, status="active")
    agent_session.bind_runtime_session(
        runtime_session_id,
        bootstrap_spec=RuntimeBootstrapSpec.from_open_dto(open_dto),
        burr_db_path=burr_db_path,
    )

    # Backing stores (SQLite-backed, per-run isolated)
    candidate_cache = CandidatePayloadCache(Path(burr_db_path))
    checkpoint_store = AgentCheckpointStore(Path(burr_db_path))

    # Runtime adapter + tools (CP-13 dependency tree)
    runtime_api = LocalRuntimeAPI()
    kg_read_tools = KGReadTools(runtime_api=runtime_api)
    explain_tools = ExplainTools(runtime_api=runtime_api)
    evaluate_tools = EvaluateTools(
        runtime_api=runtime_api,
        candidate_cache=candidate_cache,
        explain_tools=explain_tools,
        session=agent_session,
    )
    write_tools = WriteTools(runtime_api=runtime_api, session=agent_session)

    # Document + draft + bundle state
    document_staging = DocumentStaging()
    draft_manager = DraftManager()
    bundle_manager = BundleManager(draft_manager=draft_manager)

    # Orchestrator (CP-04 + CP-13)
    orchestrator = ReadReviewOrchestrator(
        session=agent_session,
        draft_manager=draft_manager,
        kg_read_tools=kg_read_tools,
        explain_tools=explain_tools,
        evaluate_tools=evaluate_tools,
        candidate_cache=candidate_cache,
        checkpoint_store=checkpoint_store,
        write_tools=write_tools,
        document_staging=document_staging,
        bundle_manager=bundle_manager,
    )

    return CommitStack(
        runtime_api=runtime_api,
        runtime_session_id=runtime_session_id,
        agent_session=agent_session,
        draft_manager=draft_manager,
        bundle_manager=bundle_manager,
        orchestrator=orchestrator,
        candidate_cache=candidate_cache,
        checkpoint_store=checkpoint_store,
        kg_read_tools=kg_read_tools,
        commit_tmpdir=commit_tmpdir,
        ledger_path=ledger_path,
        burr_db_path=burr_db_path,
    )


# ─────────────────────────────────────────────────────────────
# Record shape helpers
# ─────────────────────────────────────────────────────────────


def _empty_record(
    sample: dict[str, Any],
    *,
    manifest: dict[str, Any],
    sample_path: Path,
    dry_run: bool,
    run_started_at: datetime,
) -> dict[str, Any]:
    return {
        "_template_version": "2026-04-11",
        "sample_id": sample["sample_id"],
        "run_id": f"b3_{run_started_at.strftime('%Y%m%dT%H%M%SZ')}",
        "run_started_at": run_started_at.isoformat(),
        "dry_run": dry_run,
        "sample": {
            "path": str(sample["path"]),
            "doc_type": sample["doc_type"],
            "length_class": sample["length_class"],
            "domain": sample["domain"],
            "byte_size": sample_path.stat().st_size if sample_path.exists() else None,
            "expected_result": sample["expected_result"],
        },
        "config": {
            "extraction_model": manifest["extraction_config"].get("model"),
            "max_batch_size": manifest["scope"].get("max_batch_size"),
            "min_confidence": manifest["scope"].get("min_confidence"),
            "max_text_chars": manifest["extraction_config"].get("max_text_chars"),
            "enable_dedupe": manifest["resolution_config"].get("enable_dedupe"),
            "langfuse_enabled": (manifest.get("langfuse") or {}).get("enabled", False),
        },
        "staging": None,
        "extraction": None,
        "resolution": None,
        "bundle": None,
        "review": {
            "reviewed": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "reviewed_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "human_approval_rate": None,
            "review_notes": "PENDING: fill in after human review pass",
        },
        "outcome": {
            "expected_result": sample["expected_result"],
            "actual_result": None,
            "matches_expectation": None,
            "deviation_notes": None,
        },
        "langfuse": {
            "trace_ids": {
                "extraction_single_segment": [],
                "extraction_batch": None,
                "extraction_resolution": None,
            }
        },
        "observed_issues": [],
    }


def _fill_staging_success(record: dict[str, Any], staging_result: Any) -> None:
    pattern_dist: dict[str, int] = {"if_then": 0, "entity_relation": 0, "definition": 0, "narrative": 0}
    clarity_sum = 0.0
    segment_count = len(staging_result.segments)
    for seg in staging_result.segments:
        pattern_dist[seg.pattern_type] = pattern_dist.get(seg.pattern_type, 0) + 1
        clarity_sum += float(seg.structural_clarity)
    avg_clarity = (clarity_sum / segment_count) if segment_count else 0.0

    record["staging"] = {
        "success": True,
        "parser_name": staging_result.parser_name,
        "parser_version": staging_result.parser_version,
        "doc_id": staging_result.source.doc_id,
        "total_segments": segment_count,
        "total_chars": staging_result.total_chars,
        "high_clarity_count": staging_result.high_clarity_count,
        "avg_structural_clarity": round(avg_clarity, 4),
        "pattern_type_distribution": pattern_dist,
        "error_kind": None,
        "error_message": None,
    }


def _fill_staging_error(record: dict[str, Any], staging_error: Any) -> None:
    record["staging"] = {
        "success": False,
        "parser_name": None,
        "parser_version": None,
        "doc_id": None,
        "total_segments": 0,
        "total_chars": 0,
        "high_clarity_count": 0,
        "avg_structural_clarity": 0.0,
        "pattern_type_distribution": {"if_then": 0, "entity_relation": 0, "definition": 0, "narrative": 0},
        "error_kind": staging_error.error_kind,
        "error_message": staging_error.error_message,
    }


def _fill_extraction_result(record: dict[str, Any], batch_result: Any) -> None:
    from factpy_kernel.agent.extraction import (
        ExtractionError,
        ExtractionResult,
        ExtractionRejection,
    )

    metrics = batch_result.metrics

    per_segment_error_breakdown: dict[str, int] = {
        "llm_unavailable": 0,
        "llm_timeout": 0,
        "instructor_retry_exhausted": 0,
        "config_invalid": 0,
        "dependency_missing": 0,
        "unexpected": 0,
        "batch_cap_reached": 0,
    }
    rejection_breakdown: dict[str, int] = {
        "schema_entity_type_unknown": 0,
        "schema_pred_id_unknown": 0,
        "schema_field_type_mismatch": 0,
        "scope_entity_type_denied": 0,
        "scope_pred_id_denied": 0,
        "scope_min_confidence": 0,
        "scope_max_batch_size": 0,
        "spec_construction_failure": 0,
    }

    batch_cap_reached = False
    # Sample up to 3 per-segment error messages (first-seen), for diagnosis.
    error_samples: list[dict[str, str]] = []
    # Sample up to 3 rejection details (first-seen), for diagnosis.
    rejection_samples: list[dict[str, Any]] = []

    for seg_result in batch_result.segment_results:
        if isinstance(seg_result, ExtractionError):
            per_segment_error_breakdown[seg_result.error_kind] = (
                per_segment_error_breakdown.get(seg_result.error_kind, 0) + 1
            )
            if seg_result.error_kind == "batch_cap_reached":
                batch_cap_reached = True
            if len(error_samples) < 3:
                # Truncate long error messages to 500 chars to keep records compact.
                msg = seg_result.error_message
                if len(msg) > 500:
                    msg = msg[:500] + "…"
                error_samples.append({
                    "segment_id": seg_result.segment_id,
                    "error_kind": seg_result.error_kind,
                    "error_message": msg,
                })
        elif isinstance(seg_result, ExtractionResult):
            for rej in seg_result.rejections:
                rejection_breakdown[rej.reason] = rejection_breakdown.get(rej.reason, 0) + 1
                if rej.reason == "scope_max_batch_size" and rej.proposal_index == -1:
                    batch_cap_reached = True
                if len(rejection_samples) < 3:
                    detail = rej.detail
                    if len(detail) > 500:
                        detail = detail[:500] + "…"
                    rejection_samples.append({
                        "reason": rej.reason,
                        "proposal_index": rej.proposal_index,
                        "detail": detail,
                    })

    record["extraction"] = {
        "total_segments": metrics.total_segments,
        "success_segment_count": metrics.success_segment_count,
        "error_segment_count": metrics.error_segment_count,
        "total_proposal_count": metrics.total_proposal_count,
        "total_valid_count": metrics.total_valid_count,
        "total_rejection_count": metrics.total_rejection_count,
        "batch_duration_ms": metrics.batch_duration_ms,
        "batch_cap_reached": batch_cap_reached,
        "per_segment_error_breakdown": per_segment_error_breakdown,
        "rejection_breakdown": rejection_breakdown,
        "error_samples": error_samples,
        "rejection_samples": rejection_samples,
    }


def _fill_extraction_batch_error(record: dict[str, Any], batch_error: Any) -> None:
    record["extraction"] = {
        "total_segments": 0,
        "success_segment_count": 0,
        "error_segment_count": 0,
        "total_proposal_count": 0,
        "total_valid_count": 0,
        "total_rejection_count": 0,
        "batch_duration_ms": 0,
        "batch_cap_reached": False,
        "per_segment_error_breakdown": {
            "llm_unavailable": 0,
            "llm_timeout": 0,
            "instructor_retry_exhausted": 0,
            "config_invalid": 0,
            "dependency_missing": 0,
            "unexpected": 0,
            "batch_cap_reached": 0,
        },
        "rejection_breakdown": {
            "schema_entity_type_unknown": 0,
            "schema_pred_id_unknown": 0,
            "schema_field_type_mismatch": 0,
            "scope_entity_type_denied": 0,
            "scope_pred_id_denied": 0,
            "scope_min_confidence": 0,
            "scope_max_batch_size": 0,
            "spec_construction_failure": 0,
        },
        "batch_preflight_error_kind": batch_error.error_kind,
        "batch_preflight_error_message": batch_error.error_message,
    }


def _fill_resolution_result(record: dict[str, Any], resolution_result: Any) -> None:
    stats = resolution_result.stats
    merge_events_sample: list[dict[str, str]] = []
    for event in resolution_result.merge_events[:5]:  # cap at first 5 for readability
        merge_events_sample.append({
            "fact_key_repr": event.fact_key_repr,
            "primary_segment_id": event.primary_segment_id,
            "merged_segment_id": event.merged_segment_id,
            "entity_type": event.entity_type,
            "pred_id": event.pred_id,
        })

    record["resolution"] = {
        "input_spec_count": stats.input_spec_count,
        "output_spec_count": stats.output_spec_count,
        "merge_count": stats.merge_count,
        "unique_entity_count": stats.unique_entity_count,
        "unique_fact_count": stats.unique_fact_count,
        "resolution_duration_ms": stats.resolution_duration_ms,
        "merge_events_sample": merge_events_sample,
    }


def _fill_resolution_error(record: dict[str, Any], resolution_error: Any) -> None:
    record["resolution"] = {
        "input_spec_count": 0,
        "output_spec_count": 0,
        "merge_count": 0,
        "unique_entity_count": 0,
        "unique_fact_count": 0,
        "resolution_duration_ms": 0,
        "merge_events_sample": [],
        "preflight_error_kind": resolution_error.error_kind,
        "preflight_error_message": resolution_error.error_message,
    }


def _fill_bundle_preview(
    record: dict[str, Any],
    *,
    bundle_id: str | None,
    draft_count: int,
    committed: bool,
    commit_note: str | None = None,
    committed_count: int | None = None,
    failed_count: int = 0,
    failed_breakdown: dict[str, int] | None = None,
) -> None:
    """Populate record["bundle"] for both dry-run and --commit paths.

    committed_count precedence:
      - if `committed_count` is provided explicitly, use it as-is
      - else if `committed` is True, use `draft_count` (full success)
      - else 0 (dry-run or preview-only)

    failed_count / failed_breakdown are populated on partial-commit or
    commit-error paths. Defaults preserve the original dry-run schema
    so existing call sites don't need to change.
    """
    if committed_count is None:
        resolved_committed_count = draft_count if committed else 0
    else:
        resolved_committed_count = committed_count
    record["bundle"] = {
        "bundle_created": draft_count > 0,
        "bundle_id": bundle_id,
        "draft_count": draft_count,
        "committed_count": resolved_committed_count,
        "failed_count": failed_count,
        "failed_breakdown": failed_breakdown
        or {"shape": 0, "runtime": 0, "runtime_session_not_found": 0},
        "preview_only": not committed,
        "commit_note": commit_note,
    }


# ─────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────


def _run_single_sample(
    sample: dict[str, Any],
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    schema_ir: dict[str, Any],
    dry_run: bool,
    commit_stack: CommitStack | None = None,
) -> dict[str, Any]:
    """
    Run the full pipeline for a single sample and return a run record dict.

    Pipeline (dry-run):
        1. Read sample bytes
        2. DocumentStaging.stage_document(...) → StagingResult | StagingError
        3. BatchExtractor.extract_batch(...) → BatchExtractionResult | BatchExtractionError
        4. EntityResolver.resolve_batch(...) → ResolutionResult | ResolutionError
        5. Build per-sample preview stack (local BundleManager) + create_bundle
        6. Fill bundle preview record, return "success"

    Pipeline (--commit, commit_stack is not None):
        1-4. Same as dry-run up through resolution
        5. orchestrator.create_document_bundle(...) via the commit_stack's
           pre-built orchestrator (shared runtime session across samples)
        6. orchestrator.open_bundle_review(bundle_id)
        7. orchestrator.apply_bundle_review(bundle_id, [all-approve actions])
        8. orchestrator.commit_bundle(bundle_id, kind="add", confirmed_by=...)
        9. Inspect BundleCommitResult: full success → fill record with
           committed=True; partial failure → fill record with
           committed=False + commit_note, return "commit_error"
       10. Optional CP-12: kg_read_tools.query_claims() for up to 3
           committed predicates, print [commit_verify] lines to stdout
    """
    from factpy_kernel.agent.extraction import (
        BatchExtractionError,
        BatchExtractionResult,
        ResolutionError,
        ResolutionResult,
    )
    from factpy_kernel.agent.documents import StagingError, StagingResult

    run_started_at = datetime.now(timezone.utc)
    sample_path = manifest_dir / sample["path"]
    record = _empty_record(
        sample,
        manifest=manifest,
        sample_path=sample_path,
        dry_run=dry_run,
        run_started_at=run_started_at,
    )

    def _finalize_outcome(actual: str, deviation: str | None = None) -> dict[str, Any]:
        record["outcome"]["actual_result"] = actual
        record["outcome"]["matches_expectation"] = (actual == sample["expected_result"])
        record["outcome"]["deviation_notes"] = deviation
        finished_at = datetime.now(timezone.utc)
        record["run_finished_at"] = finished_at.isoformat()
        record["run_duration_ms"] = int((finished_at - run_started_at).total_seconds() * 1000)
        return record

    # Read bytes
    if not sample_path.exists():
        _fill_staging_error(
            record,
            type("Err", (), {"error_kind": "missing_file", "error_message": f"sample file not found: {sample_path}"})(),
        )
        return _finalize_outcome("staging_error", f"file not found: {sample_path}")

    try:
        content = sample_path.read_bytes()
    except Exception as exc:
        _fill_staging_error(
            record,
            type("Err", (), {"error_kind": "read_failure", "error_message": str(exc)})(),
        )
        return _finalize_outcome("staging_error", f"read failure: {exc}")

    # Build extraction stack per-sample (shared tracer across stack)
    try:
        tracer = _build_tracer(manifest.get("langfuse"))
        scope = _build_scope(manifest["scope"])
        staging, _ext_agent, batch_extractor, entity_resolver, _batch_cfg_obj = _build_extraction_stack(
            extraction_config=manifest["extraction_config"],
            batch_config=manifest.get("batch_config", {}),
            resolution_config=manifest.get("resolution_config", {}),
            tracer=tracer,
        )
    except Exception as exc:
        record["observed_issues"].append({
            "issue_id": "P-runner-001",
            "category": "other",
            "severity": "P1",
            "description": f"Failed to build extraction stack: {exc}",
            "evidence_ref": traceback.format_exc(),
        })
        return _finalize_outcome("extraction_error", f"extraction stack build failed: {exc}")

    # Step 1: stage
    stage_outcome = staging.stage_document(
        doc_name=sample_path.name,
        content=content,
        doc_type=sample["doc_type"],
    )
    if isinstance(stage_outcome, StagingError):
        _fill_staging_error(record, stage_outcome)
        return _finalize_outcome("staging_error")

    assert isinstance(stage_outcome, StagingResult)
    _fill_staging_success(record, stage_outcome)

    # Step 2: batch extract
    batch_outcome = batch_extractor.extract_batch(
        segments=list(stage_outcome.segments),
        schema_ir=schema_ir,
        scope=scope,
    )
    if isinstance(batch_outcome, BatchExtractionError):
        _fill_extraction_batch_error(record, batch_outcome)
        return _finalize_outcome("extraction_error")

    assert isinstance(batch_outcome, BatchExtractionResult)
    _fill_extraction_result(record, batch_outcome)

    if not batch_outcome.aggregated_specs:
        # No valid specs after extraction: still succeeded at pipeline level,
        # but record the empty outcome.
        _fill_bundle_preview(
            record,
            bundle_id=None,
            draft_count=0,
            committed=False,
            commit_note="No valid specs produced by batch extraction; bundle not created.",
        )
        return _finalize_outcome("empty")

    # Step 3: resolve
    resolve_outcome = entity_resolver.resolve_batch(list(batch_outcome.aggregated_specs))
    if isinstance(resolve_outcome, ResolutionError):
        _fill_resolution_error(record, resolve_outcome)
        return _finalize_outcome("resolution_error")

    assert isinstance(resolve_outcome, ResolutionResult)
    _fill_resolution_result(record, resolve_outcome)

    # Step 4: bundle creation — dry-run preview path vs commit path split
    if dry_run:
        # Existing dry-run preview path (unchanged): per-sample local stack
        try:
            preview_session, _preview_draft_manager, preview_bundle_manager = _build_bundle_preview_stack(
                scope=scope,
            )
            preview_bundle = preview_bundle_manager.create_bundle(
                session_id=preview_session.agent_session_id,
                source_document_id=resolve_outcome.doc_id,
                source_document_name=sample_path.name,
                facts=list(resolve_outcome.resolved_specs),
                created_by=scope.agent_id,
            )
        except Exception as exc:
            record["observed_issues"].append(
                {
                    "issue_id": "P-runner-003",
                    "category": "bundle/commit",
                    "severity": "P1",
                    "description": f"Failed to create bundle preview: {exc}",
                    "evidence_ref": traceback.format_exc(),
                }
            )
            _fill_bundle_preview(
                record,
                bundle_id=None,
                draft_count=0,
                committed=False,
                commit_note=f"bundle preview failed: {exc}",
            )
            return _finalize_outcome("resolution_error", f"bundle preview failed: {exc}")

        draft_count = len(preview_bundle.draft_ids)
        _fill_bundle_preview(
            record,
            bundle_id=preview_bundle.bundle_id,
            draft_count=draft_count,
            committed=False,
            commit_note="dry-run: real bundle preview created; not committed to ledger.",
        )
        return _finalize_outcome("success")

    # ─────────────────────────────────────────────────────────
    # Commit path (--commit, non-dry-run)
    # Uses the shared CommitStack built once by main() — NOT the
    # per-sample _build_bundle_preview_stack(). Goes through the
    # ReadReviewOrchestrator facade (4 calls per CP-04).
    # ─────────────────────────────────────────────────────────
    if commit_stack is None:
        # Defensive guard: should not happen because main() constructs
        # commit_stack before calling _run_single_sample with dry_run=False
        raise RuntimeError(
            "commit mode invoked without a commit_stack; main() bug"
        )

    from factpy_kernel.agent import BundleReviewAction
    from factpy_kernel.agent.errors import AgentContractError

    # CP-04 step 1: create bundle via orchestrator (scope validation + checkpoint)
    try:
        bundle = commit_stack.orchestrator.create_document_bundle(
            source_document_id=resolve_outcome.doc_id,
            source_document_name=sample_path.name,
            facts=list(resolve_outcome.resolved_specs),
        )
    except AgentContractError as exc:
        record["observed_issues"].append(
            {
                "issue_id": "P-runner-commit-001",
                "category": "bundle/commit",
                "severity": "P1",
                "description": f"create_document_bundle failed (scope): {exc}",
                "evidence_ref": traceback.format_exc(),
            }
        )
        _fill_bundle_preview(
            record,
            bundle_id=None,
            draft_count=0,
            committed=False,
            commit_note=f"create_document_bundle failed: {exc}",
        )
        return _finalize_outcome("bundle_error", f"create_document_bundle: {exc}")
    except Exception as exc:
        record["observed_issues"].append(
            {
                "issue_id": "P-runner-commit-002",
                "category": "bundle/commit",
                "severity": "P1",
                "description": f"create_document_bundle raised unexpectedly: {exc}",
                "evidence_ref": traceback.format_exc(),
            }
        )
        _fill_bundle_preview(
            record,
            bundle_id=None,
            draft_count=0,
            committed=False,
            commit_note=f"create_document_bundle error: {exc}",
        )
        return _finalize_outcome("bundle_error", f"unexpected: {exc}")

    draft_count = len(bundle.draft_ids)

    # CP-04 step 2: open bundle for review
    commit_stack.orchestrator.open_bundle_review(bundle.bundle_id)

    # CP-04 step 3: approve all drafts (B3 harness commits everything by default;
    # human review is a separate concern closed by β.1 verdict δ)
    commit_stack.orchestrator.apply_bundle_review(
        bundle.bundle_id,
        [BundleReviewAction(draft_id=d, action="approve") for d in bundle.draft_ids],
    )

    # CP-04 step 4: commit — returns BundleCommitResult (Q3)
    try:
        commit_result = commit_stack.orchestrator.commit_bundle(
            bundle.bundle_id,
            kind="add",
            confirmed_by=scope.agent_id or "b3_load_test",
        )
    except AgentContractError as exc:
        # Precondition violation (bundle not approved, no approved drafts, etc.)
        record["observed_issues"].append(
            {
                "issue_id": "P-runner-commit-003",
                "category": "bundle/commit",
                "severity": "P1",
                "description": f"commit_bundle precondition failed: {exc}",
                "evidence_ref": traceback.format_exc(),
            }
        )
        _fill_bundle_preview(
            record,
            bundle_id=bundle.bundle_id,
            draft_count=draft_count,
            committed=False,
            commit_note=f"commit precondition failed: {exc}",
        )
        return _finalize_outcome("commit_error", f"commit_bundle precondition: {exc}")

    # Q4: partial commits do NOT raise — inspect commit_result
    if commit_result.failed_count > 0:
        # At least one per-draft commit failed; surface via commit_note
        _fill_bundle_preview(
            record,
            bundle_id=bundle.bundle_id,
            draft_count=draft_count,
            committed=False,  # partial success — full success requires zero failures
            committed_count=commit_result.committed_count,
            failed_count=commit_result.failed_count,
            commit_note=(
                f"partial commit: {commit_result.committed_count}/{commit_result.total} drafts succeeded, "
                f"{commit_result.failed_count} failed; session={commit_stack.runtime_session_id}"
            ),
        )
        return _finalize_outcome(
            "commit_error",
            f"partial commit: {commit_result.failed_count} failures",
        )

    # Full success
    _fill_bundle_preview(
        record,
        bundle_id=bundle.bundle_id,
        draft_count=draft_count,
        committed=True,
        committed_count=commit_result.committed_count,
        commit_note=(
            f"committed {commit_result.committed_count} drafts to ledger "
            f"via LocalRuntimeAPI session {commit_stack.runtime_session_id}"
        ),
    )

    # CP-12 optional: runtime-side verification via kg_read_tools (Q7).
    # Result is logged to stdout only — NOT added to run_record (non-goals).
    if commit_result.committed_count > 0:
        committed_preds = sorted({
            spec.pred_id for spec in resolve_outcome.resolved_specs
        })[:3]  # sample up to 3 preds
        for pred_id in committed_preds:
            try:
                claims = commit_stack.kg_read_tools.query_claims(
                    commit_stack.runtime_session_id, pred_id=pred_id
                )
                print(
                    f"  [commit_verify] {sample['sample_id']} pred={pred_id} "
                    f"claim_count={len(claims)}",
                    flush=True,
                )
            except Exception as exc:
                # Non-fatal: verification is a secondary signal
                print(
                    f"  [commit_verify] {sample['sample_id']} pred={pred_id} "
                    f"query_claims failed: {exc}",
                    flush=True,
                )

    return _finalize_outcome("success")


def _save_run_record(record: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{record['run_id']}_{record['sample_id']}.json"
    output_path = output_dir / filename
    with output_path.open("w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    return output_path


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="B3 Agent load test runner")
    parser.add_argument(
        "--manifest",
        type=Path,
        required=False,
        help="Path to samples_manifest.yaml",
    )
    parser.add_argument(
        "--sample",
        type=str,
        default=None,
        help="Run a single sample by sample_id",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all samples in the manifest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,   # DEFAULT: dry-run
        help="(DEFAULT) Skip bundle commit; stop at bundle preview",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Opt out of dry-run. NOTE: commit path is currently stubbed; see docstring.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for run records (default: <manifest_dir>/run_records)",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Print optional dependency availability and exit without running",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Explicit .env path. Defaults: <manifest_dir>/.env, then <repo_root>/.env. "
             "Shell env always wins over file.",
    )
    args = parser.parse_args()

    if args.check_deps:
        status = _detect_dependencies()
        print("Optional dependency status:")
        for name, ok in status.items():
            marker = "✓" if ok else "✗"
            print(f"  {marker} {name}")
        return 0

    if args.manifest is None:
        parser.error("--manifest is required unless --check-deps is used")

    if not args.sample and not args.all:
        parser.error("Must specify either --sample <id> or --all")

    # --commit overrides the default dry-run
    dry_run = not args.commit

    manifest_path = args.manifest.resolve()
    manifest_dir = manifest_path.parent

    # Load .env files before reading manifest, so env-dependent settings resolve correctly.
    # Precedence (lowest → highest): repo-root .env → manifest-dir .env → --env-file → shell env.
    env_files_loaded: list[tuple[Path, int]] = []

    # Walk up the parent chain without a fixed depth limit. Stop at the first
    # directory that contains pyproject.toml OR .env, or at filesystem root.
    repo_root_env = manifest_dir
    current = manifest_dir
    while True:
        if (current / "pyproject.toml").exists() or (current / ".env").exists():
            repo_root_env = current
            break
        parent = current.parent
        if parent == current:  # filesystem root
            break
        current = parent

    root_env = repo_root_env / ".env"
    if root_env.exists():
        n = _load_env_file(root_env)
        env_files_loaded.append((root_env, n))

    local_env = manifest_dir / ".env"
    if local_env.exists() and local_env.resolve() != root_env.resolve():
        n = _load_env_file(local_env)
        env_files_loaded.append((local_env, n))

    if args.env_file is not None:
        if not args.env_file.exists():
            print(f"ERROR: --env-file not found: {args.env_file}")
            return 1
        n = _load_env_file(args.env_file)
        env_files_loaded.append((args.env_file, n))

    for path, count in env_files_loaded:
        print(f"  [env] loaded {count} var(s) from {path}")
    if not env_files_loaded:
        print("  [env] no .env file loaded (shell env only)")

    manifest = _read_manifest(manifest_path)

    # Read schema_ir (provisional — used by extraction path in both dry-run and commit mode)
    schema_ir_rel = manifest.get("schema_ir_path", "./test_schema_ir.json")
    schema_ir_path = (manifest_dir / schema_ir_rel).resolve()
    if not schema_ir_path.exists():
        print(f"ERROR: schema_ir_path not found: {schema_ir_path}")
        return 1
    try:
        schema_ir = _read_schema_ir(schema_ir_path)
    except Exception as exc:
        print(f"ERROR: failed to load schema_ir: {exc}")
        return 1

    # Read commit_schema_ir (canonical — used ONLY by --commit mode's runtime
    # session open call). Extraction continues to use the provisional schema_ir
    # above. See blueprint 2026-04-11_b3-schema-canonicalization (SC-05).
    commit_schema_ir: dict[str, Any] | None = None
    if not dry_run:
        try:
            commit_schema_ir = _read_commit_schema_ir(manifest, manifest_dir)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}")
            return 1
        except Exception as exc:
            print(f"ERROR: failed to load commit schema: {exc}")
            return 1

    output_dir = args.output_dir or (manifest_dir / "run_records")

    # Select samples
    if args.all:
        samples_to_run = manifest["samples"]
    else:
        samples_to_run = [s for s in manifest["samples"] if s["sample_id"] == args.sample]
        if not samples_to_run:
            print(f"ERROR: sample_id '{args.sample}' not found in manifest")
            return 1

    # Build the commit stack once per --commit invocation. Shared across
    # all samples in this run. Dry-run mode does NOT build it (zero cost).
    commit_stack: CommitStack | None = None
    if not dry_run:
        assert commit_schema_ir is not None, (
            "commit mode reached stack build with commit_schema_ir unset; "
            "main() schema load should have returned 1 already"
        )
        commit_run_id = f"b3commit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        try:
            commit_stack = _build_commit_stack(
                scope=_build_scope(manifest["scope"]),
                schema_ir=commit_schema_ir,
                commit_run_id=commit_run_id,
            )
        except Exception as exc:
            print(f"ERROR: failed to build commit stack: {exc}")
            traceback.print_exc()
            return 1
        print(f"  [commit] commit_run_id: {commit_run_id}")
        print(f"  [commit] tempdir: {commit_stack.commit_tmpdir}")
        print(f"  [commit] runtime_session_id: {commit_stack.runtime_session_id}")
        print(f"  [commit] ledger_path: {commit_stack.ledger_path}")
        print(f"  [commit] burr_db_path: {commit_stack.burr_db_path}")

    print(f"Running {len(samples_to_run)} sample(s). dry_run={dry_run}")
    any_failed = False
    try:
        for sample in samples_to_run:
            print(f"  → {sample['sample_id']}")
            try:
                record = _run_single_sample(
                    sample,
                    manifest=manifest,
                    manifest_dir=manifest_dir,
                    schema_ir=schema_ir,
                    dry_run=dry_run,
                    commit_stack=commit_stack,
                )
            except Exception as exc:
                any_failed = True
                print(f"    RUNNER CRASH: {exc}")
                traceback.print_exc()
                continue

            out = _save_run_record(record, output_dir)
            outcome = record["outcome"]["actual_result"]
            matches = record["outcome"]["matches_expectation"]
            marker = "✓" if matches else "!"
            print(f"    {marker} {outcome} → {out}")
    finally:
        # CP-11: teardown always runs, even on mid-run failure
        if commit_stack is not None:
            from factpy_kernel.service.runtime_v1 import close_runtime_session

            try:
                commit_stack.candidate_cache.close()
            except Exception as exc:
                print(
                    f"WARNING: failed to close candidate_cache: {exc}",
                    file=sys.stderr,
                )
            try:
                commit_stack.checkpoint_store.close()
            except Exception as exc:
                print(
                    f"WARNING: failed to close checkpoint_store: {exc}",
                    file=sys.stderr,
                )
            try:
                close_runtime_session(commit_stack.runtime_session_id)
            except Exception as exc:
                print(
                    f"WARNING: failed to close runtime session: {exc}",
                    file=sys.stderr,
                )
            # CP-03 retention policy: tempdir is intentionally NOT deleted.
            # Both ledger.db and burr.db stay on disk for post-mortem
            # inspection regardless of outcome. OS /tmp cleanup handles
            # long-term accumulation.
            print(
                f"[commit] tempdir kept for inspection: {commit_stack.commit_tmpdir}",
                flush=True,
            )

    return 2 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
