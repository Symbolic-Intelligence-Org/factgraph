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
    # Build index -> asrt_id mapping from written assertions (F-PL-3)
    asrt_id_by_index: dict[int, str] = {}
    for idx, entry in enumerate(written):
        if not isinstance(entry, dict):
            continue
        aid = entry.get("asrt_id", "")
        if isinstance(aid, str) and aid and aid != "<dry_run>":
            asrt_id_by_index[idx] = aid
    if not asrt_id_by_index:
        return 0

    templates = run_pending.pop(candidate_id, [])
    if not run_pending:
        pending_by_run.pop(run_id, None)
    if not isinstance(templates, list) or not templates:
        return 0

    rows: list[AnnotationRow] = []
    for template in templates:
        if not isinstance(template, dict) or template.get("namespace") != "problog":
            continue
        fact_index = template.get("fact_index", 0)
        asrt_id = asrt_id_by_index.get(fact_index if isinstance(fact_index, int) else 0)
        if asrt_id is None:
            continue
        rows.append(
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
        )
    if not rows:
        return 0
    ledger.append_annotations(rows)
    return len(rows)


__all__ = ["persist_problog_annotations"]
