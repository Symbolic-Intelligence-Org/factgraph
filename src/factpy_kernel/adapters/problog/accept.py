"""ProbLog shared-surface annotation binder.

Persists pending ``problog/semantic/*`` templates after the shared
``Store.accept()`` path has written the actual assertion and produced
the final ``asrt_id``.
"""
from __future__ import annotations

from typing import Any

from factpy_kernel.core.store.ledger import AnnotationRow, Ledger


def persist_problog_annotations(
    ledger: Ledger,
    run_id: str,
    store: Any,
    accept_result: Any,
) -> int:
    """Persist pending ``problog/*`` annotations for a single accepted candidate."""
    if not isinstance(ledger, Ledger):
        raise ValueError("ledger must be a Ledger instance")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be non-empty string")

    pending_by_run = getattr(store, "_problog_pending_annotations", {})
    if not isinstance(pending_by_run, dict):
        return 0
    run_pending = pending_by_run.get(run_id)
    if not isinstance(run_pending, dict) or not run_pending:
        return 0

    candidate_id = getattr(accept_result, "candidate_id", None)
    if not isinstance(candidate_id, str) or not candidate_id:
        return 0

    written = getattr(accept_result, "written_assertions", [])
    if not isinstance(written, list) or not written:
        return 0
    first_written = written[0]
    asrt_id = first_written.get("asrt_id", "") if isinstance(first_written, dict) else ""
    if not isinstance(asrt_id, str) or not asrt_id or asrt_id == "<dry_run>":
        return 0

    templates = run_pending.pop(candidate_id, [])
    if not run_pending:
        pending_by_run.pop(run_id, None)
    if not isinstance(templates, list) or not templates:
        return 0

    rows = [
        AnnotationRow(
            asrt_id=asrt_id,
            namespace=str(template["namespace"]),
            category=str(template["category"]),
            key=str(template["key"]),
            kind=str(template["kind"]),
            value=template["value"],
            origin=str(template["origin"]),
            derivation=template.get("derivation"),
        )
        for template in templates
        if isinstance(template, dict) and template.get("namespace") == "problog"
    ]
    if not rows:
        return 0
    ledger.append_annotations(rows)
    return len(rows)


__all__ = ["persist_problog_annotations"]
