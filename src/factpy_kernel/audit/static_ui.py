from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .authoring_events import load_authoring_apply_events, summarize_authoring_apply_events
from .assertions import load_assertion_index
from .dto import (
    build_authoring_apply_run_detail_dto,
    build_candidate_evidence_tree_narrative_dto,
    build_candidate_evidence_tree_dto,
    build_decision_detail_dto,
    build_rule_trace_detail_dto,
    build_rule_trace_list_dto,
    build_rule_trace_narrative_dto,
    build_run_detail_dto,
    build_run_list_dto,
)
from .query import AuditQuery
from .reader import load_audit_package


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def render_audit_static_site(package_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    data = load_audit_package(package_dir)
    query = AuditQuery(data)
    authoring_apply_events = load_authoring_apply_events(package_dir)
    authoring_apply_summary = summarize_authoring_apply_events(authoring_apply_events)
    compliance_matrix_rows = query.list_compliance_matrix()
    root = Path(out_dir)
    runs_dir = root / "runs"
    decisions_dir = root / "decisions"
    assertions_dir = root / "assertions"
    rule_traces_dir = root / "rule_traces"
    candidate_evidence_dir = root / "candidate_evidence"
    authoring_apply_runs_dir = root / "authoring_apply_runs"
    indexes_dir = root / "indexes"
    root.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    assertions_dir.mkdir(parents=True, exist_ok=True)
    rule_traces_dir.mkdir(parents=True, exist_ok=True)
    candidate_evidence_dir.mkdir(parents=True, exist_ok=True)
    authoring_apply_runs_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)

    run_list = build_run_list_dto(query)
    rule_trace_list = build_rule_trace_list_dto(query)
    assertion_index = load_assertion_index(data)
    run_ids: list[str] = []
    decision_ids: set[str] = set()
    assertion_ids = sorted(assertion_index.claims.keys())
    rule_trace_ids: list[str] = []
    candidate_evidence_ids: list[str] = []

    for asrt_id in assertion_ids:
        detail = assertion_index.get_assertion_detail(asrt_id)
        if detail is None:
            continue
        page = _render_assertion_detail_page(detail)
        (assertions_dir / f"{_slug_id(asrt_id)}.html").write_text(page, encoding="utf-8")

    for row in rule_trace_list.get("rule_traces", []):
        if not isinstance(row, dict):
            continue
        rule_run_id = row.get("rule_run_id")
        if not isinstance(rule_run_id, str) or not rule_run_id:
            continue
        rule_trace_ids.append(rule_run_id)
        detail = build_rule_trace_detail_dto(query, rule_run_id)
        narrative_dto = build_rule_trace_narrative_dto(query, rule_run_id)
        narrative = narrative_dto.get("narrative") if isinstance(narrative_dto.get("narrative"), dict) else None
        page = _render_rule_trace_detail_page(detail, assertion_index=assertion_index, narrative=narrative)
        (rule_traces_dir / f"{_slug_id(rule_run_id)}.html").write_text(page, encoding="utf-8")

    for candidate_id in sorted(
        {
            row.get("candidate_id")
            for row in query.list_candidates()
            if isinstance(row.get("candidate_id"), str) and row.get("candidate_id")
        }
    ):
        candidate_tree = build_candidate_evidence_tree_dto(query, candidate_id)
        candidate_narrative_dto = build_candidate_evidence_tree_narrative_dto(query, candidate_id)
        candidate_narrative = (
            candidate_narrative_dto.get("narrative")
            if isinstance(candidate_narrative_dto.get("narrative"), dict)
            else None
        )
        provenance_tree = query.get_candidate_provenance_tree(candidate_id)
        provenance_status = query.get_candidate_provenance_status(candidate_id)
        page = _render_candidate_evidence_page(
            candidate_tree,
            narrative=candidate_narrative,
            provenance_tree=provenance_tree,
            provenance_status=provenance_status,
        )
        (candidate_evidence_dir / f"{_slug_id(candidate_id)}.html").write_text(page, encoding="utf-8")
        candidate_evidence_ids.append(candidate_id)

    for run in run_list["runs"]:
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        run_ids.append(run_id)
        run_detail = build_run_detail_dto(query, run_id)
        run_page = _render_run_detail_page(run_detail, assertion_index=assertion_index)
        (runs_dir / f"{_slug_id(run_id)}.html").write_text(run_page, encoding="utf-8")
        for decision_id in run_detail.get("decision_ids", []):
            if isinstance(decision_id, str) and decision_id:
                decision_ids.add(decision_id)

    for decision_row in query.list_decisions():
        decision_id = decision_row.get("decision_id")
        if isinstance(decision_id, str) and decision_id:
            decision_ids.add(decision_id)

    for decision_id in sorted(decision_ids):
        decision_detail = build_decision_detail_dto(query, decision_id)
        page = _render_decision_detail_page(decision_detail, assertion_index=assertion_index)
        (decisions_dir / f"{_slug_id(decision_id)}.html").write_text(page, encoding="utf-8")

    authoring_apply_run_ids: list[str] = []
    for row in query.list_authoring_apply_runs():
        apply_request_id = row.get("apply_request_id")
        if not isinstance(apply_request_id, str) or not apply_request_id:
            continue
        authoring_apply_run_ids.append(apply_request_id)
        detail = build_authoring_apply_run_detail_dto(query, apply_request_id)
        page = _render_authoring_apply_run_detail_page(detail)
        (authoring_apply_runs_dir / f"{_slug_id(apply_request_id)}.html").write_text(page, encoding="utf-8")

    index_pages = _render_filter_index_pages(query)
    for rel_name, html in index_pages.items():
        (indexes_dir / rel_name).write_text(html, encoding="utf-8")

    authoring_apply_page = _render_authoring_apply_events_page(authoring_apply_events, authoring_apply_summary)
    (root / "authoring_apply_events.html").write_text(authoring_apply_page, encoding="utf-8")
    rule_trace_page = _render_rule_trace_index_page(rule_trace_list.get("rule_traces", []))
    (root / "rule_traces.html").write_text(rule_trace_page, encoding="utf-8")
    candidate_evidence_page = _render_candidate_evidence_index_page(candidate_evidence_ids)
    (root / "candidate_evidence.html").write_text(candidate_evidence_page, encoding="utf-8")
    compliance_matrix_page = _render_compliance_matrix_page(compliance_matrix_rows)
    (root / "compliance_matrix.html").write_text(compliance_matrix_page, encoding="utf-8")

    index_html = _render_index_page(
        run_list,
        index_pages=sorted(index_pages.keys()),
        authoring_apply_summary=authoring_apply_summary,
        rule_trace_count=len(rule_trace_ids),
        compliance_matrix_count=len(compliance_matrix_rows),
        candidate_evidence_count=len(candidate_evidence_ids),
    )
    (root / "index.html").write_text(index_html, encoding="utf-8")
    (root / "search.html").write_text(_render_search_page(), encoding="utf-8")
    ui_index_payload = _build_ui_index_payload(
        query=query,
        run_list=run_list,
        run_ids=sorted(set(run_ids)),
        decision_ids=sorted(decision_ids),
        assertion_ids=assertion_ids,
        rule_trace_ids=sorted(set(rule_trace_ids)),
        authoring_apply_run_ids=sorted(set(authoring_apply_run_ids)),
        index_pages=sorted(index_pages.keys()),
        authoring_apply_summary=authoring_apply_summary,
        candidate_evidence_ids=sorted(set(candidate_evidence_ids)),
        compliance_matrix_rows=compliance_matrix_rows,
        rule_trace_rows=rule_trace_list.get("rule_traces", []),
    )
    (root / "ui_index.json").write_text(
        json.dumps(ui_index_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    site_manifest = {
        "audit_ui_site_version": "audit_ui_site_v1",
        "package_kind": data.manifest.get("package_kind"),
        "run_count": len(run_ids),
        "decision_count": len(decision_ids),
        "assertion_count": len(assertion_ids),
        "rule_trace_count": len(rule_trace_ids),
        "candidate_evidence_count": len(candidate_evidence_ids),
        "authoring_apply_event_count": authoring_apply_summary.get("event_count", 0),
        "runs": [f"runs/{_slug_id(run_id)}.html" for run_id in sorted(set(run_ids))],
        "assertions": [f"assertions/{_slug_id(asrt_id)}.html" for asrt_id in assertion_ids],
        "rule_traces": [
            f"rule_traces/{_slug_id(rule_run_id)}.html" for rule_run_id in sorted(set(rule_trace_ids))
        ],
        "candidate_evidence": [
            f"candidate_evidence/{_slug_id(candidate_id)}.html"
            for candidate_id in sorted(set(candidate_evidence_ids))
        ],
        "authoring_apply_runs": [
            f"authoring_apply_runs/{_slug_id(apply_request_id)}.html"
            for apply_request_id in sorted(set(authoring_apply_run_ids))
        ],
        "indexes": [f"indexes/{name}" for name in sorted(index_pages.keys())],
        "index": "index.html",
        "search": "search.html",
        "ui_index": "ui_index.json",
        "authoring_apply_events": "authoring_apply_events.html",
        "rule_trace_index": "rule_traces.html",
        "candidate_evidence_index": "candidate_evidence.html",
        "compliance_matrix": "compliance_matrix.html",
        "compliance_matrix_row_count": len(compliance_matrix_rows),
    }
    (root / "site_manifest.json").write_text(
        json.dumps(site_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return site_manifest


def _render_index_page(
    run_list: dict[str, Any],
    *,
    index_pages: list[str],
    authoring_apply_summary: dict[str, Any] | None = None,
    rule_trace_count: int = 0,
    candidate_evidence_count: int = 0,
    compliance_matrix_count: int = 0,
) -> str:
    rows = []
    for run in run_list.get("runs", []):
        if not isinstance(run, dict):
            continue
        run_id = str(run.get("run_id", ""))
        href = f"runs/{_slug_id(run_id)}.html"
        rows.append(
            "<tr>"
            f"<td><a href='{escape(href, quote=True)}'>{escape(run_id)}</a></td>"
            f"<td>{escape(str(run.get('claim_count', 0)))}</td>"
            f"<td>{escape(str(run.get('decision_count', 0)))}</td>"
            f"<td>{escape(str(run.get('error_count', 0)))}</td>"
            f"<td>{escape(str(run.get('event_ts_max')))}</td>"
            "</tr>"
        )
    body = "".join(rows) if rows else "<tr><td colspan='5'>No runs</td></tr>"
    apply_count = (
        authoring_apply_summary.get("event_count", 0)
        if isinstance(authoring_apply_summary, dict)
        else 0
    )
    hero_cards = (
        "<div class='metric-grid'>"
        f"{_metric_card('Runs', len(run_list.get('runs', [])), 'Recorded reasoning runs in this audit bundle.')}"
        f"{_metric_card('Evidence Trees', candidate_evidence_count, 'Open these pages to inspect why a candidate was derived.')}"
        f"{_metric_card('Rule Traces', rule_trace_count, 'Trace which rules executed and how the proof chain expanded.')}"
        f"{_metric_card('Apply Events', apply_count, 'Authoring and audit events captured in the package.')}"
        "</div>"
    )
    return _html_page(
        title="Compliance Audit Review Site",
        body=(
            "<div class='hero'>"
            "<p class='eyebrow'>Audit Review Site</p>"
            "<h1>Compliance Audit Review Site</h1>"
            "<p class='hero-copy'>"
            "Review verdicts, inspect evidence trees, understand certainty, and share the exported audit "
            "bundle with any reviewer in a browser."
            "</p>"
            f"{hero_cards}"
            "</div>"
            "<div class='link-rail'>"
            "<a href='search.html'>Search</a>"
            f"<a href='authoring_apply_events.html'>Authoring Apply Events ({escape(str(apply_count))})</a>"
            f"<a href='rule_traces.html'>Rule Traces ({escape(str(rule_trace_count))})</a>"
            f"<a href='candidate_evidence.html'>Candidate Evidence Trees ({escape(str(candidate_evidence_count))})</a>"
            f"<a href='compliance_matrix.html'>Compliance Matrix ({escape(str(compliance_matrix_count))})</a>"
            "</div>"
            "<h2>Indexes</h2>"
            f"<ul>{''.join(_index_page_links(index_pages)) if index_pages else '<li>None</li>'}</ul>"
            "<h2>Runs</h2>"
            "<p class='section-copy'>Each run captures a deterministic reasoning session with its resulting decisions and evidence.</p>"
            "<table>"
            "<thead><tr><th>Run</th><th>Claims</th><th>Decisions</th><th>Errors</th><th>Last Event</th></tr></thead>"
            f"<tbody>{body}</tbody>"
            "</table>"
        ),
    )


def _render_compliance_matrix_page(rows: list[dict[str, Any]]) -> str:
    table_rows: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        req_id = row.get("req_id")
        title = row.get("title")
        standard_ref = row.get("standard_ref")
        status = row.get("status")
        milestone = row.get("review_milestone")
        verification_methods = row.get("verification_methods")
        rid_links = row.get("rid_links")
        methods_cell = _render_method_links(verification_methods)
        rid_cell = _render_rid_links(rid_links)
        evidence_cell = _render_compliance_evidence_links(row)
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(req_id or ''))}</td>"
            f"<td>{escape(str(title or ''))}</td>"
            f"<td>{escape(str(standard_ref or ''))}</td>"
            f"<td>{escape(str(status or ''))}</td>"
            f"<td>{escape(str(milestone or ''))}</td>"
            f"<td>{methods_cell}</td>"
            f"<td>{rid_cell}</td>"
            f"<td>{evidence_cell}</td>"
            "</tr>"
        )
    return _html_page(
        title="Compliance Matrix",
        body=(
            "<h1>Compliance Matrix</h1>"
            "<p><a href='index.html'>Back to runs</a></p>"
            f"<p>Rows: {escape(str(len(rows)))}</p>"
            "<table>"
            "<thead><tr><th>Requirement</th><th>Title</th><th>Standard Ref</th><th>Status</th><th>Milestone</th><th>Verification Methods</th><th>RID Links</th><th>Evidence</th></tr></thead>"
            f"<tbody>{''.join(table_rows) if table_rows else '<tr><td colspan=8>None</td></tr>'}</tbody>"
            "</table>"
        ),
    )


def _render_method_links(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    items: list[str] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        method = row.get("method")
        asrt_ids = row.get("asrt_ids")
        if not isinstance(method, str) or not method:
            continue
        items.append(
            f"{escape(method)} ({_render_assertion_links_inline(asrt_ids)})"
        )
    return "<br>".join(items) if items else "-"


def _render_rid_links(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    items: list[str] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        rid_id = row.get("rid_id")
        asrt_ids = row.get("asrt_ids")
        if not isinstance(rid_id, str) or not rid_id:
            continue
        items.append(
            f"{escape(rid_id)} ({_render_assertion_links_inline(asrt_ids)})"
        )
    return "<br>".join(items) if items else "-"


def _render_compliance_evidence_links(row: dict[str, Any]) -> str:
    links: list[str] = []
    for label, key in (
        ("requirement", "requirement_asrt_id"),
        ("status", "status_asrt_id"),
        ("milestone", "review_milestone_asrt_id"),
    ):
        asrt_id = row.get(key)
        if isinstance(asrt_id, str) and asrt_id:
            links.append(f"{escape(label)}: {_render_assertion_link(asrt_id)}")
    return "<br>".join(links) if links else "-"


def _render_assertion_links_inline(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "-"
    links = [
        _render_assertion_link(asrt_id)
        for asrt_id in value
        if isinstance(asrt_id, str) and asrt_id
    ]
    return ", ".join(links) if links else "-"


def _render_assertion_link(asrt_id: str) -> str:
    href = f"assertions/{_slug_id(asrt_id)}.html"
    return f"<a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a>"


def _render_run_detail_page(
    payload: dict[str, Any],
    *,
    assertion_index,
) -> str:
    run_id = str(payload.get("run_id", ""))
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    decision_links = []
    for decision in payload.get("decisions", []):
        if not isinstance(decision, dict):
            continue
        decision_id = decision.get("decision_id")
        if not isinstance(decision_id, str):
            continue
        href = f"../decisions/{_slug_id(decision_id)}.html"
        decision_links.append(
            "<li>"
            f"<a href='{escape(href, quote=True)}'>{escape(decision_id)}</a>"
            f" [{escape(str(decision.get('event_kind')))}]"
            "</li>"
        )
    timeline_rows = []
    for row in payload.get("timeline", []):
        if not isinstance(row, dict):
            continue
        timeline_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('event_ts')))}</td>"
            f"<td>{escape(str(row.get('entry_kind')))}</td>"
            f"<td>{escape(str(row.get('event_kind')))}</td>"
            f"<td>{escape(str(row.get('decision_id')))}</td>"
            "</tr>"
        )
    accept_write_rows = []
    assertion_summary_blocks = []
    rendered_assertions: set[str] = set()
    for row in payload.get("accept_writes", []):
        if not isinstance(row, dict):
            continue
        asrt_id = row.get("asrt_id")
        candidate_id = row.get("candidate_id")
        asrt_cell = escape(str(asrt_id))
        if isinstance(asrt_id, str) and asrt_id:
            asrt_href = f"../assertions/{_slug_id(asrt_id)}.html"
            asrt_cell = f"<a href='{escape(asrt_href, quote=True)}'>{escape(asrt_id)}</a>"
        accept_write_rows.append(
            "<tr>"
            f"<td>{escape(str(candidate_id))}</td>"
            f"<td>{asrt_cell}</td>"
            f"<td>{escape(str(row.get('pred_id')))}</td>"
            f"<td>{escape(str(row.get('ingested_at')))}</td>"
            "</tr>"
        )
        if isinstance(asrt_id, str) and asrt_id and asrt_id not in rendered_assertions:
            rendered_assertions.add(asrt_id)
            detail = assertion_index.get_assertion_detail(asrt_id)
            if isinstance(detail, dict):
                assertion_summary_blocks.append(_render_assertion_summary_block(detail, "../assertions"))
    return _html_page(
        title=f"Run {run_id}",
        body=(
            f"<h1>Run {escape(run_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            "<h2>Stats</h2>"
            "<ul>"
            f"<li>accept_writes={escape(str(stats.get('accept_write_count', 0)))}</li>"
            f"<li>candidates={escape(str(stats.get('candidate_count', 0)))}</li>"
            f"<li>decisions={escape(str(stats.get('decision_count', 0)))}</li>"
            f"<li>failures={escape(str(stats.get('failure_count', 0)))}</li>"
            "</ul>"
            "<h2>Decisions</h2>"
            f"<ul>{''.join(decision_links) if decision_links else '<li>None</li>'}</ul>"
            "<h2>Accept Writes</h2>"
            "<table><thead><tr><th>Candidate</th><th>Assertion</th><th>Pred</th><th>Ts</th></tr></thead>"
            f"<tbody>{''.join(accept_write_rows) if accept_write_rows else '<tr><td colspan=4>None</td></tr>'}</tbody></table>"
            "<h2>Assertion Summaries</h2>"
            f"{''.join(assertion_summary_blocks) if assertion_summary_blocks else '<p>None</p>'}"
            "<h2>Timeline</h2>"
            "<table><thead><tr><th>Ts</th><th>Kind</th><th>Event</th><th>Decision</th></tr></thead>"
            f"<tbody>{''.join(timeline_rows) if timeline_rows else '<tr><td colspan=4>None</td></tr>'}</tbody></table>"
        ),
    )


def _render_decision_detail_page(
    payload: dict[str, Any],
    *,
    assertion_index,
) -> str:
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    decision_id = str(payload.get("decision_id", ""))
    related = payload.get("related") if isinstance(payload.get("related"), dict) else {}
    runs = _sorted_unique_strings(related.get("run_ids"))
    mats = _sorted_unique_strings(related.get("candidate_ids"))
    asrt_ids = _sorted_unique_strings(
        [row.get("asrt_id") for row in payload.get("accept_writes", []) if isinstance(row, dict)]
        + [row.get("asrt_id") for row in payload.get("candidates", []) if isinstance(row, dict)]
        + ([decision.get("asrt_id")] if isinstance(decision.get("asrt_id"), str) else [])
        + (
            [value for value in decision.get("candidate_asrt_ids", []) if isinstance(value, str)]
            if isinstance(decision.get("candidate_asrt_ids"), list)
            else []
        )
    )
    assertion_links = []
    for asrt_id in asrt_ids:
        href = f"../assertions/{_slug_id(asrt_id)}.html"
        assertion_links.append(f"<li><a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a></li>")
    assertion_summary_blocks = []
    for asrt_id in asrt_ids:
        detail = assertion_index.get_assertion_detail(asrt_id)
        if isinstance(detail, dict):
            assertion_summary_blocks.append(_render_assertion_summary_block(detail, "../assertions"))
    return _html_page(
        title=f"Decision {decision_id}",
        body=(
            f"<h1>Decision {escape(decision_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            "<h2>Summary</h2>"
            "<ul>"
            f"<li>event_source={escape(str(decision.get('event_source')))}</li>"
            f"<li>event_kind={escape(str(decision.get('event_kind')))}</li>"
            f"<li>event_ts={escape(str(decision.get('event_ts')))}</li>"
            "</ul>"
            "<h2>Related</h2>"
            f"<p>runs={escape(','.join(runs)) or '-'}</p>"
            f"<p>candidate_ids={escape(','.join(mats)) or '-'}</p>"
            f"<p>assertions={escape(str(len(asrt_ids)))}</p>"
            f"<p>candidates={escape(str(len(payload.get('candidates', []))))}</p>"
            f"<p>failures={escape(str(len(payload.get('failures', []))))}</p>"
            "<h2>Assertions</h2>"
            f"<ul>{''.join(assertion_links) if assertion_links else '<li>None</li>'}</ul>"
            "<h2>Assertion Summaries</h2>"
            f"{''.join(assertion_summary_blocks) if assertion_summary_blocks else '<p>None</p>'}"
            "<h2>Payload</h2>"
            f"<pre>{escape(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
        ),
    )


def _render_assertion_detail_page(payload: dict[str, Any]) -> str:
    claim = payload.get("claim") if isinstance(payload.get("claim"), dict) else {}
    asrt_id = str(payload.get("asrt_id", ""))
    claim_args_rows = []
    for row in payload.get("claim_args", []):
        if not isinstance(row, dict):
            continue
        claim_args_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('idx')))}</td>"
            f"<td>{escape(str(row.get('tag')))}</td>"
            f"<td>{escape(str(row.get('val')))}</td>"
            "</tr>"
        )
    meta_sections = []
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for kind in sorted(meta):
            rows = meta.get(kind)
            if not isinstance(rows, list):
                continue
            items = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                items.append(
                    "<tr>"
                    f"<td>{escape(str(row.get('key')))}</td>"
                    f"<td>{escape(str(row.get('value')))}</td>"
                    "</tr>"
                )
            meta_sections.append(
                f"<h3>meta_{escape(kind)}</h3>"
                "<table><thead><tr><th>key</th><th>value</th></tr></thead>"
                f"<tbody>{''.join(items) if items else '<tr><td colspan=2>None</td></tr>'}</tbody></table>"
            )
    revoked_by = _sorted_unique_strings(payload.get("revoked_by"))
    revokes = _sorted_unique_strings(payload.get("revokes"))
    return _html_page(
        title=f"Assertion {asrt_id}",
        body=(
            f"<h1>Assertion {escape(asrt_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            "<h2>Claim</h2>"
            "<ul>"
            f"<li>pred_id={escape(str(claim.get('pred_id')))}</li>"
            f"<li>e_ref={escape(str(claim.get('e_ref')))}</li>"
            f"<li>tup_digest={escape(str(claim.get('tup_digest')))}</li>"
            f"<li>is_revoked={escape(str(payload.get('is_revoked')))}</li>"
            "</ul>"
            "<h2>claim_arg</h2>"
            "<table><thead><tr><th>idx</th><th>tag</th><th>val</th></tr></thead>"
            f"<tbody>{''.join(claim_args_rows) if claim_args_rows else '<tr><td colspan=3>None</td></tr>'}</tbody></table>"
            "<h2>Revocation</h2>"
            f"<p>revoked_by={escape(','.join(revoked_by)) or '-'}</p>"
            f"<p>revokes={escape(','.join(revokes)) or '-'}</p>"
            "<h2>Meta</h2>"
            f"{''.join(meta_sections) if meta_sections else '<p>None</p>'}"
            "<h2>Payload</h2>"
            f"<pre>{escape(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
        ),
    )


def _render_rule_trace_index_page(rows: list[dict[str, Any]]) -> str:
    table_rows: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rule_run_id = row.get("rule_run_id")
        root_rule = row.get("root_rule") if isinstance(row.get("root_rule"), dict) else {}
        if not isinstance(rule_run_id, str) or not rule_run_id:
            continue
        href = f"rule_traces/{_slug_id(rule_run_id)}.html"
        table_rows.append(
            "<tr>"
            f"<td><a href='{escape(href, quote=True)}'>{escape(rule_run_id)}</a></td>"
            f"<td>{escape(str(root_rule.get('rule_id') or ''))}</td>"
            f"<td>{escape(str(root_rule.get('version') or ''))}</td>"
            f"<td>{escape(str(row.get('invocation_count', 0)))}</td>"
            f"<td>{escape(str(row.get('witness_assertion_count', 0)))}</td>"
            f"<td>{escape(str(row.get('non_fact_step_count', 0)))}</td>"
            f"<td>{escape(str(row.get('root_row_count', 0)))}</td>"
            "</tr>"
        )
    return _html_page(
        title="Rule Traces",
        body=(
            "<h1>Rule Traces</h1>"
            "<p><a href='index.html'>Back to runs</a></p>"
            f"<p>Rows: {escape(str(len(rows)))}</p>"
            "<table>"
            "<thead><tr><th>rule_run_id</th><th>root_rule</th><th>version</th><th>invocations</th><th>witness assertions</th><th>non-fact steps</th><th>root rows</th></tr></thead>"
            f"<tbody>{''.join(table_rows) if table_rows else '<tr><td colspan=7>None</td></tr>'}</tbody>"
            "</table>"
        ),
    )


def _render_candidate_evidence_index_page(candidate_ids: list[str]) -> str:
    rows: list[str] = []
    for candidate_id in candidate_ids:
        href = f"candidate_evidence/{_slug_id(candidate_id)}.html"
        rows.append(
            "<tr>"
            f"<td><a href='{escape(href, quote=True)}'>{escape(candidate_id)}</a></td>"
            "</tr>"
        )
    return _html_page(
        title="Candidate Evidence Trees",
        body=(
            "<h1>Candidate Evidence Trees</h1>"
            "<p><a href='index.html'>Back to runs</a></p>"
            f"<p>Rows: {escape(str(len(candidate_ids)))}</p>"
            "<table>"
            "<thead><tr><th>candidate_id</th></tr></thead>"
            f"<tbody>{''.join(rows) if rows else '<tr><td>None</td></tr>'}</tbody>"
            "</table>"
        ),
    )


def _render_candidate_evidence_page(
    tree: dict[str, Any],
    *,
    narrative: dict[str, Any] | None = None,
    provenance_tree: dict[str, Any] | None = None,
    provenance_status: dict[str, Any] | None = None,
) -> str:
    candidate_id = str(tree.get("candidate_id", ""))
    support_digest = str(tree.get("support_digest", ""))
    support_kind = str(tree.get("support_kind", ""))
    root = tree.get("root") if isinstance(tree.get("root"), dict) else {}
    binding = root.get("binding") if isinstance(root.get("binding"), dict) else {}
    mission_ref = binding.get("$m") if isinstance(binding.get("$m"), str) else None
    status_value = binding.get("$status") if isinstance(binding.get("$status"), str) else None
    rule_refs = [item for item in root.get("rule_refs", []) if isinstance(item, str) and item]
    rule_ref_edges = [
        item
        for item in root.get("rule_ref_edges", [])
        if isinstance(item, dict)
    ]
    root_result_kind = root.get("root_result_kind")
    narrative_block = _render_candidate_evidence_narrative_block(narrative)
    short_digest = support_digest[:30] + "..." if len(support_digest) > 30 else support_digest
    status_badge = _status_badge(status_value) if status_value is not None else ""
    fallback_badge = _status_badge(root_result_kind, label="DERIVED")
    summary_rows = [
        "<dl class='summary-grid'>",
        f"<dt>Support kind</dt><dd>{escape(support_kind)}</dd>",
        f"<dt>Result type</dt><dd>{escape('-' if root_result_kind is None else str(root_result_kind))}</dd>",
        f"<dt>Primary rule</dt><dd>{escape(rule_refs[0]) if rule_refs else '-'}</dd>",
        f"<dt>Rule chain depth</dt><dd>{escape(str(len(rule_ref_edges)))}</dd>",
        f"<dt>Digest</dt><dd><code>{escape(short_digest)}</code></dd>",
    ]
    if mission_ref is not None:
        summary_rows.append(f"<dt>Mission ref</dt><dd><code>{escape(mission_ref)}</code></dd>")
    if status_value is not None:
        summary_rows.append(
            f"<dt>{escape(_status_label(status_value))}</dt><dd>{status_badge}</dd>"
        )
    summary_rows.append("</dl>")
    provenance_status_block = ""
    if isinstance(provenance_status, dict):
        ps = str(provenance_status.get("status", "unknown"))
        truncated = bool(provenance_status.get("truncated"))
        engine = provenance_status.get("engine")
        engine_label = engine if isinstance(engine, str) and engine else "unknown"
        if ps == "present" and not truncated:
            badge_html = (
                "<span style='display:inline-block;padding:4px 12px;border-radius:20px;"
                "font-size:.78rem;font-weight:700;background:#c8e6c9;color:#1b5e20'>"
                f"Engine Provenance: Available ({escape(engine_label)})"
                "</span>"
            )
        elif ps == "present" and truncated:
            badge_html = (
                "<span style='display:inline-block;padding:4px 12px;border-radius:20px;"
                "font-size:.78rem;font-weight:700;background:#fff3e0;color:#e65100'>"
                f"Engine Provenance: Truncated ({escape(engine_label)})"
                "</span>"
            )
        else:
            reason = provenance_status.get("reason")
            reason_text = reason if isinstance(reason, str) and reason else ps
            badge_html = (
                "<span style='display:inline-block;padding:4px 12px;border-radius:20px;"
                "font-size:.78rem;font-weight:700;background:#ffcdd2;color:#b71c1c'>"
                f"Engine Provenance: Unavailable — {escape(reason_text)}"
                "</span>"
            )
        provenance_status_block = f"<div style='margin:12px 0'>{badge_html}</div>"
    provenance_block = ""
    if isinstance(provenance_tree, dict):
        provenance_root = provenance_tree.get("root")
        if isinstance(provenance_root, dict):
            bridge_note = (
                "<p style='color:var(--color-muted);font-size:.85rem;margin-bottom:8px'>"
                "The provenance tree below shows the Souffle engine's internal derivation for this candidate. "
                "Rule numbers (R1, R2, ...) are Souffle-internal and correspond to the compiled form of the "
                "rules shown in the Evidence Tree above."
                "</p>"
            )
            truncation_warning = ""
            if isinstance(provenance_status, dict) and provenance_status.get("truncated"):
                truncation_warning = (
                    "<div style='background:#fff3e0;border:1px solid #ffe0b2;border-radius:8px;"
                    "padding:10px 14px;margin:8px 0;font-size:.83rem'>"
                    "<strong style='color:#e65100'>⚠️ Depth-Truncated Proof</strong><br>"
                    "This proof tree was truncated by the Souffle engine at its default depth limit. "
                    "Nodes marked \"Truncated (depth limit)\" represent subtrees that can be expanded with "
                    "deeper analysis. The truncation does not indicate missing evidence — the full "
                    "derivation exists in the engine."
                    "</div>"
                )
            provenance_block = (
                "<h2>\U0001f52c Engine Provenance</h2>"
                f"{bridge_note}"
                f"{truncation_warning}"
                "<p style='color:var(--color-muted);font-size:.9rem;margin-bottom:12px'>"
                "Complete derivation chain from the Souffle reasoning engine. "
                "Each node shows a derivation step, leaf nodes are base facts or negation checks."
                "</p>"
                f"{_render_provenance_node_html(provenance_root)}"
            )
    return _html_page(
        title=f"Candidate Evidence {candidate_id}",
        body=(
            "<div class='snapshot-card'>"
            "<div>"
            "<p class='eyebrow'>Candidate Evidence</p>"
            "<h1>Evidence Tree Review</h1>"
            "<p class='hero-copy'>"
            "Use this page to answer three review questions: what result was derived, which rule chain produced it, "
            "and which facts support it."
            "</p>"
            "</div>"
            f"<div class='snapshot-meta'>{status_badge if status_badge else fallback_badge}</div>"
            "</div>"
            f"<p style='color:var(--color-muted);font-size:.85rem;margin-top:-4px;word-break:break-all'>{escape(candidate_id)}</p>"
            "<div class='nav'>"
            "<a href='../index.html'>\u2190 Runs</a>"
            "<a href='../candidate_evidence.html'>\u2190 All Evidence Trees</a>"
            "</div>"
            f"{''.join(summary_rows)}"
            f"{provenance_status_block}"
            f"{narrative_block}"
            f"{provenance_block}"
            "<h2>Derived Binding</h2>"
            "<p class='section-copy'>Bound values returned by the reasoning engine for this candidate.</p>"
            f"<pre>{escape(json.dumps(binding, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "<h2>\U0001f333 Evidence Tree</h2>"
            "<p class='section-copy'>"
            "This tree shows the complete proof chain \u2014 how the system arrived at this conclusion, "
            "which rules were applied, and what facts were used as evidence.</p>"
            f"{_render_candidate_evidence_node(root, assertion_href_prefix='../assertions')}"
            "<details><summary>\U0001f4be Raw JSON Payload</summary>"
            f"<pre>{escape(json.dumps(tree, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "</details>"
        ),
    )


def render_candidate_evidence_html(
    tree: dict[str, Any],
    *,
    narrative: dict[str, Any] | None = None,
    provenance_tree: dict[str, Any] | None = None,
    provenance_status: dict[str, Any] | None = None,
) -> str:
    return _render_candidate_evidence_page(
        tree,
        narrative=narrative,
        provenance_tree=provenance_tree,
        provenance_status=provenance_status,
    )


def _render_provenance_node_html(node: dict[str, Any], depth: int = 0) -> str:
    """Render a Souffle proof tree node as nested HTML."""
    node_type = str(node.get("node_type", "unknown"))
    relation = str(node.get("relation", "?"))
    args = node.get("args")
    arg_values = args if isinstance(args, list) else []
    rule_number = node.get("rule_number")
    children = node.get("children")
    child_nodes = children if isinstance(children, list) else []

    if node_type == "axiom":
        icon = "\U0001f4c4"
        label = "Base Fact"
        border_color = "var(--color-witness)"
        background = "#f0faf0"
    elif node_type == "negation":
        icon = "\u274c"
        label = "Negation Check"
        border_color = "var(--color-terminal)"
        background = "#fef0f0"
    elif node_type == "subproof":
        icon = "\U0001f50d"
        label = "Truncated (depth limit)"
        border_color = "var(--color-muted)"
        background = "#f5f5f5"
    else:
        icon = "\U0001f4cb"
        label = f"Rule {rule_number}" if isinstance(rule_number, str) and rule_number else "Derived"
        border_color = "var(--color-rule-chain)"
        background = "#f5f0ff"

    args_display = ", ".join(str(arg) for arg in arg_values[:4])
    if len(arg_values) > 4:
        args_display += ", ..."

    html = (
        f"<div style='border-left:3px solid {border_color};background:{background};"
        "border-radius:6px;padding:0;overflow:hidden;"
        f"margin:{4 if depth > 0 else 8}px 0 0 {depth * 20}px'>"
        "<div style='padding:8px 12px;font-size:.85rem'>"
        f"<span style='margin-right:6px'>{icon}</span>"
        f"<strong>{escape(label)}</strong>"
        f"<code style='margin-left:8px;font-size:.8rem;color:var(--color-muted)'>"
        f"{escape(relation)}({escape(args_display)})"
        "</code>"
        "</div>"
    )

    if child_nodes:
        html += "<div style='padding:0 8px 8px'>"
        for child in child_nodes:
            if isinstance(child, dict):
                html += _render_provenance_node_html(child, depth + 1)
        html += "</div>"

    html += "</div>"
    return html


_NODE_HUMAN_LABEL = {
    "candidate_result": ("\U0001f4cb", "Derived Result", "The conclusion derived by the reasoning engine"),
    "support_section": ("\U0001f4e6", "Supporting Evidence", "Evidence that supports this conclusion"),
    "rule_ref_section": ("\U0001f517", "Rule References", "Rules that were invoked to produce this result"),
    "degraded_support": ("\u26a0\ufe0f", "Degraded Evidence", "Evidence was expected but could not be fully resolved"),
    "rule_ref": ("\u27a1\ufe0f", "Rule Invocation", "A specific rule that was applied"),
    "referenced_support": ("\U0001f50d", "Child Proof", "Proof from a child rule that was referenced"),
    "unresolved_support": ("\u274c", "Unresolved", "Evidence that could not be resolved"),
    "recursion_boundary": ("\U0001f504", "Recursion Limit", "Proof chain stopped to prevent infinite loops"),
    "predicate_witness_group": ("\U0001f4ca", "Fact Match", "Facts that matched this condition in the rule"),
    "non_fact_check": ("\u2705", "Constraint Check", "A structural constraint that was verified"),
    "assertion_fact": ("\U0001f4c4", "Witness Fact", "An actual data fact used as evidence"),
}

_NODE_KIND_ROLE = {
    "candidate_result": "structural",
    "support_section": "structural",
    "rule_ref_section": "structural",
    "degraded_support": "degraded",
    "rule_ref": "rule-chain",
    "referenced_support": "rule-chain",
    "unresolved_support": "terminal",
    "recursion_boundary": "terminal",
    "predicate_witness_group": "witness",
    "non_fact_check": "constraint",
    "assertion_fact": "witness",
}


def _node_prop(key: str, val: str) -> str:
    return (
        f"<div class='prop'><span class='prop-key'>{escape(key)}</span>"
        f"<span class='prop-val'>{escape(val)}</span></div>"
    )


def _confidence_badge(value: float) -> str:
    if value >= 0.8:
        color, bg = "#2e7d32", "#e8f5e9"
    elif value >= 0.5:
        color, bg = "#f57f17", "#fff8e1"
    else:
        color, bg = "#c62828", "#ffebee"
    return (
        f"<span style='display:inline-block;padding:1px 8px;border-radius:10px;"
        f"font-size:.8rem;font-weight:600;background:{bg};color:{color}'>"
        f"{value:.0%}</span>"
    )


def _status_label(value: str | None) -> str:
    normalized = _normalize_status(value)
    if normalized in {"compliant", "non_compliant"}:
        return "Compliance status"
    if normalized:
        return "Derived status"
    return "Status"


def _status_badge(value: Any, *, label: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    normalized = _normalize_status(value)
    display = label or value.strip().replace("_", "-").upper()
    if normalized in {"compliant", "complete", "pass", "passed"}:
        css_class = "status-ok"
    elif normalized in {"non_compliant", "incomplete", "fail", "failed"}:
        css_class = "status-bad"
    else:
        css_class = "status-neutral"
    return f"<span class='status-badge {css_class}'>{escape(display)}</span>"


def _normalize_status(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _render_candidate_evidence_node(node: dict[str, Any], *, assertion_href_prefix: str) -> str:
    node_kind = str(node.get("node_kind", ""))
    role = _NODE_KIND_ROLE.get(node_kind, "structural")
    icon, label, description = _NODE_HUMAN_LABEL.get(node_kind, ("\u25cb", node_kind, ""))

    props: list[str] = []

    if node_kind == "candidate_result":
        rk = node.get("root_result_kind")
        if rk:
            props.append(_node_prop("Result type", str(rk)))
    elif node_kind == "support_section":
        props.append(_node_prop("Evidence items", str(len(node.get("children", [])))))
    elif node_kind == "rule_ref_section":
        props.append(_node_prop("Rules referenced", str(len(node.get("children", [])))))
    elif node_kind == "degraded_support":
        props.append(_node_prop("Support kind", str(node.get("support_kind"))))
        props.append(_node_prop("Status", str(node.get("witness_status"))))
    elif node_kind == "rule_ref":
        rid = node.get("rule_ref_id", "")
        ver = node.get("rule_ref_version", "")
        props.append(_node_prop("Rule", f"{rid} (v{ver})"))
    elif node_kind == "referenced_support":
        sd = str(node.get("support_digest", ""))
        props.append(_node_prop("Proof digest", sd[:24] + "..." if len(sd) > 24 else sd))
    elif node_kind == "unresolved_support":
        props.append(_node_prop("Reason", str(node.get("reason"))))
    elif node_kind == "recursion_boundary":
        props.append(_node_prop("Reason", str(node.get("boundary_reason"))))
    elif node_kind == "predicate_witness_group":
        pred_id = str(node.get("pred_id", ""))
        count = node.get("assertion_count", 0)
        cc = node.get("condition_confidence")
        props.append(_node_prop("Predicate", pred_id))
        props.append(_node_prop("Matching facts", str(count)))
        if cc is not None:
            props.append(
                f"<div class=\'prop\'><span class=\'prop-key\'>Confidence</span>"
                f"<span class=\'prop-val\'>{_confidence_badge(cc)}</span></div>"
            )
    elif node_kind == "non_fact_check":
        status = str(node.get("status", ""))
        check_kind = str(node.get("check_kind", ""))
        status_icon = "\u2705" if status == "satisfied" else "\u274c"
        label_map = {"ruleref": "Rule reference resolved", "eq": "Equality constraint"}
        human_check = label_map.get(check_kind, check_kind)
        props.append(_node_prop("Check", f"{human_check} {status_icon}"))
    elif node_kind == "assertion_fact":
        asrt_id = str(node.get("asrt_id", ""))
        href = f"{assertion_href_prefix}/{_slug_id(asrt_id)}.html"
        claim_args = node.get("claim_args", [])
        values = ", ".join(
            str(a.get("val", "")) for a in claim_args if isinstance(a, dict)
        ) if isinstance(claim_args, list) else ""
        pred_id = str(node.get("pred_id", ""))
        conf = node.get("confidence")
        if values:
            props.append(
                f"<div class=\'prop\'><span class=\'prop-key\'>Value</span>"
                f"<span class=\'prop-val\' style=\'font-weight:600;font-size:.95rem\'>{escape(values)}</span></div>"
            )
        props.append(_node_prop("Predicate", pred_id))
        if conf is not None:
            props.append(
                f"<div class=\'prop\'><span class=\'prop-key\'>Confidence</span>"
                f"<span class=\'prop-val\'>{_confidence_badge(conf)}</span></div>"
            )
        props.append(
            f"<div class=\'prop\'><span class=\'prop-key\'>Detail</span>"
            f"<span class=\'prop-val\'><a href=\'{escape(href, quote=True)}\'>View assertion \u2192</a></span></div>"
        )

    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    child_html = "".join(
        _render_candidate_evidence_node(child, assertion_href_prefix=assertion_href_prefix)
        for child in children
    )
    desc_html = f"<div class='node-desc'>{escape(description)}</div>" if description else ""
    return (
        f"<div class='tree-node node-kind-{escape(role)}'>"
        f"<div class='node-header'><span class='icon'>{icon}</span> {escape(label)}</div>"
        f"<div class='node-body'>{desc_html}{''.join(props)}</div>"
        + (f"<div class='node-children'>{child_html}</div>" if child_html else "")
        + "</div>"
    )

def _render_rule_trace_detail_page(
    payload: dict[str, Any],
    *,
    assertion_index,
    narrative: dict[str, Any] | None = None,
) -> str:
    rule_run_id = str(payload.get("rule_run_id", ""))
    root_rule = payload.get("root_rule") if isinstance(payload.get("root_rule"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    witness_assertion_ids = [
        item for item in payload.get("witness_assertion_ids", []) if isinstance(item, str) and item
    ]
    select_vars = [item for item in payload.get("select_vars", []) if isinstance(item, str)]
    root_rows = [item for item in payload.get("root_rows", []) if isinstance(item, list)]

    root_row_items = [
        "<li>" + escape(json.dumps(row, ensure_ascii=False, sort_keys=True)) + "</li>"
        for row in root_rows
    ]
    witness_links = [
        f"<li><a href='../assertions/{escape(_slug_id(asrt_id), quote=True)}.html'>{escape(asrt_id)}</a></li>"
        for asrt_id in witness_assertion_ids
    ]

    invocation_blocks: list[str] = []
    invocations = [item for item in trace.get("invocations", []) if isinstance(item, dict)]
    for invocation in invocations:
        rule = invocation.get("rule") if isinstance(invocation.get("rule"), dict) else {}
        witness_rows: list[str] = []
        for witness in invocation.get("pred_witnesses", []):
            if not isinstance(witness, dict):
                continue
            asrt_links = []
            for asrt_id in witness.get("asrt_ids", []):
                if not isinstance(asrt_id, str) or not asrt_id:
                    continue
                href = f"../assertions/{_slug_id(asrt_id)}.html"
                asrt_links.append(f"<a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a>")
            witness_rows.append(
                "<tr>"
                f"<td>{escape(str(witness.get('binding_index')))}</td>"
                f"<td>{escape(str(witness.get('pred_atom_key')))}</td>"
                f"<td>{', '.join(asrt_links) if asrt_links else '-'}</td>"
                "</tr>"
            )
        non_fact_rows: list[str] = []
        for step in invocation.get("non_fact_steps", []):
            if not isinstance(step, dict):
                continue
            non_fact_rows.append(
                "<tr>"
                f"<td>{escape(str(step.get('binding_index')))}</td>"
                f"<td>{escape(str(step.get('step_key')))}</td>"
                f"<td>{escape(str(step.get('kind')))}</td>"
                f"<td>{escape(str(step.get('status')))}</td>"
                f"<td><pre>{escape(json.dumps(step.get('details'), ensure_ascii=False, sort_keys=True, indent=2))}</pre></td>"
                "</tr>"
            )
        ruleref_items: list[str] = []
        for link in invocation.get("ruleref_links", []):
            if not isinstance(link, dict):
                continue
            ruleref_items.append(
                "<li>"
                f"{escape(str(link.get('ruleref_atom_key')))} -> {escape(str(link.get('child_invocation_id')))}"
                "</li>"
            )
        invocation_blocks.append(
            "<div style='border:1px solid #eee;padding:12px;margin:12px 0'>"
            f"<h3>{escape(str(invocation.get('invocation_id')))}</h3>"
            "<ul>"
            f"<li>parent_invocation_id={escape(str(invocation.get('parent_invocation_id')))}</li>"
            f"<li>rule_id={escape(str(rule.get('rule_id')))}</li>"
            f"<li>version={escape(str(rule.get('version')))}</li>"
            f"<li>memo_hit={escape(str(invocation.get('memo_hit')))}</li>"
            f"<li>binding_count={escape(str(len(invocation.get('bindings', [])) if isinstance(invocation.get('bindings'), list) else 0))}</li>"
            f"<li>output_row_count={escape(str(len(invocation.get('output_rows', [])) if isinstance(invocation.get('output_rows'), list) else 0))}</li>"
            "</ul>"
            "<h4>Predicate Witnesses</h4>"
            "<table><thead><tr><th>binding_index</th><th>pred_atom_key</th><th>assertions</th></tr></thead>"
            f"<tbody>{''.join(witness_rows) if witness_rows else '<tr><td colspan=3>None</td></tr>'}</tbody></table>"
            "<h4>Non-fact Steps</h4>"
            "<table><thead><tr><th>binding_index</th><th>step_key</th><th>kind</th><th>status</th><th>details</th></tr></thead>"
            f"<tbody>{''.join(non_fact_rows) if non_fact_rows else '<tr><td colspan=5>None</td></tr>'}</tbody></table>"
            "<h4>RuleRef Links</h4>"
            f"<ul>{''.join(ruleref_items) if ruleref_items else '<li>None</li>'}</ul>"
            "</div>"
        )

    assertion_summary_blocks = []
    for asrt_id in witness_assertion_ids:
        detail = assertion_index.get_assertion_detail(asrt_id)
        if isinstance(detail, dict):
            assertion_summary_blocks.append(_render_assertion_summary_block(detail, "../assertions"))

    narrative_block = _render_rule_trace_narrative_block(narrative)

    return _html_page(
        title=f"Rule Trace {rule_run_id}",
        body=(
            f"<h1>Rule Trace {escape(rule_run_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a> | "
            "<a href='../rule_traces.html'>All rule traces</a></p>"
            f"{narrative_block}"
            "<h2>Summary</h2>"
            "<ul>"
            f"<li>root_rule_id={escape(str(root_rule.get('rule_id')))}</li>"
            f"<li>root_rule_version={escape(str(root_rule.get('version')))}</li>"
            f"<li>select_vars={escape(json.dumps(select_vars, ensure_ascii=False))}</li>"
            f"<li>root_row_count={escape(str(stats.get('root_row_count', 0)))}</li>"
            f"<li>invocation_count={escape(str(stats.get('invocation_count', 0)))}</li>"
            f"<li>witness_assertion_count={escape(str(stats.get('witness_assertion_count', 0)))}</li>"
            f"<li>pred_witness_count={escape(str(stats.get('pred_witness_count', 0)))}</li>"
            f"<li>non_fact_step_count={escape(str(stats.get('non_fact_step_count', 0)))}</li>"
            "</ul>"
            "<h2>Root Rows</h2>"
            f"<ul>{''.join(root_row_items) if root_row_items else '<li>None</li>'}</ul>"
            "<h2>Witness Assertions</h2>"
            f"<ul>{''.join(witness_links) if witness_links else '<li>None</li>'}</ul>"
            "<h2>Assertion Summaries</h2>"
            f"{''.join(assertion_summary_blocks) if assertion_summary_blocks else '<p>None</p>'}"
            "<h2>Invocations</h2>"
            f"{''.join(invocation_blocks) if invocation_blocks else '<p>None</p>'}"
            "<h2>Payload</h2>"
            f"<pre>{escape(json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
        ),
    )


def render_rule_trace_detail_html(
    payload: dict[str, Any],
    *,
    assertion_lookup,
    narrative: dict[str, Any] | None = None,
) -> str:
    class _AssertionLookupAdapter:
        def get_assertion_detail(self, asrt_id: str) -> dict[str, Any] | None:
            return assertion_lookup(asrt_id)

    return _render_rule_trace_detail_page(
        payload,
        assertion_index=_AssertionLookupAdapter(),
        narrative=narrative,
    )


def _render_rule_trace_narrative_block(narrative: dict[str, Any] | None) -> str:
    if not isinstance(narrative, dict):
        return ""

    headline = narrative.get("headline")
    headline_html = (
        f"<p>{escape(headline)}</p>"
        if isinstance(headline, str) and headline
        else "<p>None</p>"
    )
    return (
        "<h2>Narrative</h2>"
        f"{headline_html}"
        "<h3>Overview</h3>"
        f"{_line_list(narrative.get('overview_lines'))}"
        "<h3>Predicate Witnesses</h3>"
        f"{_line_list(narrative.get('predicate_lines'))}"
        "<h3>Non-fact Checks</h3>"
        f"{_line_list(narrative.get('non_fact_check_lines'))}"
        "<h3>Drilldown</h3>"
        f"{_line_list(narrative.get('drilldown_lines'))}"
    )


def _render_certainty_visual(narrative: dict[str, Any]) -> str:
    certainty_lines = narrative.get("certainty_lines")
    if not isinstance(certainty_lines, list) or not certainty_lines:
        return ""

    bottleneck = narrative.get("certainty_bottleneck")
    bottleneck_keys: set[str] = set()
    if isinstance(bottleneck, dict):
        bottleneck_keys = set(bottleneck.get("atom_keys", []))

    first_line = certainty_lines[0] if certainty_lines else ""
    aggregate_val = ""
    strategy = "bottleneck"
    if "additive" in first_line.lower():
        strategy = "additive"
    agg_match = re.search(r":\s*([\d.]+)", first_line)
    if agg_match:
        aggregate_val = agg_match.group(1)
    aggregate_class = "neutral"
    try:
        aggregate_class = _certainty_level_class(float(aggregate_val))
    except ValueError:
        aggregate_class = "neutral"

    bars_html = ""
    for line in certainty_lines[1:]:
        if not line.startswith("Condition "):
            continue
        parts = re.match(
            r"Condition (\S+) \((\w+)\): weight=([\d.]+), impact=([\d.]+)\.(.*)",
            line,
        )
        if not parts:
            continue
        atom_key = parts.group(1)
        _nk = parts.group(2)
        weight = parts.group(3)
        impact_str = parts.group(4)
        is_bottleneck = atom_key in bottleneck_keys
        try:
            impact_num = float(impact_str)
            impact_pct = impact_num * 100
        except ValueError:
            impact_num = 0.0
            impact_pct = 0
        bar_class = _certainty_level_class(impact_num)
        badge = (
            "<span class=\'certainty-badge bottleneck\'>\u26a0 weakest</span>"
            if is_bottleneck else ""
        )
        bars_html += (
            "<div class=\'certainty-bar-row\'>"
            f"<span class=\'certainty-bar-label\'>{escape(atom_key)}{badge}</span>"
            f"<div class=\'certainty-bar-track\'>"
            f"<div class=\'certainty-bar-fill {bar_class}\' style=\'width:{impact_pct:.1f}%\'></div>"
            "</div>"
            f"<span class=\'certainty-bar-value\'>{escape(impact_str)}</span>"
            f"<span style=\'color:var(--color-muted);font-size:.8rem\'>(w={escape(weight)})</span>"
            "</div>"
        )

    return (
        "<div class=\'certainty-section\'>"
        "<div class=\'certainty-header\'>"
        "<h3>\U0001f4ca Certainty Assessment</h3>"
        f"<span class=\'certainty-aggregate {aggregate_class}\'>{escape(aggregate_val)}</span>"
        "</div>"
        f"<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 12px\'>"
        f"\U0001f3af Strategy: <strong>{escape(strategy)}</strong> \u2014 "
        f"{'Weakest-link model: the lowest condition determines overall certainty' if strategy == 'bottleneck' else 'Proportional model: each condition contributes to overall certainty'}"
        "</p>"
        "<p style=\'font-size:.85rem;margin:0 0 8px\'>"
        "Each bar shows how much a condition contributes to the overall certainty "
        "(impact = weight \u00d7 confidence):</p>"
        f"{bars_html}"
        "</div>"
    )


def _certainty_level_class(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _render_candidate_evidence_narrative_block(narrative: dict[str, Any] | None) -> str:
    if not isinstance(narrative, dict):
        return ""

    headline = narrative.get("headline")
    headline_html = (
        f"<p><strong>{escape(headline)}</strong></p>"
        if isinstance(headline, str) and headline
        else ""
    )

    certainty_html = _render_certainty_visual(narrative)

    return (
        "<div class=\'narrative-section\'>"
        "<h2 style=\'margin-top:0;border:0\'>\U0001f4dd Analysis Summary</h2>"
        f"{headline_html}"
        "<h3>\U0001f50e Overview</h3>"
        "<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 4px\'>High-level summary of what was derived and how the evidence is structured:</p>"
        f"{_line_list(narrative.get('overview_lines'))}"
        "<h3>\U0001f4d1 Evidence Details</h3>"
        "<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 4px\'>What facts were found to support this derivation:</p>"
        f"{_line_list(narrative.get('evidence_lines'))}"
        "<h3>\u2699\ufe0f Rule Chain</h3>"
        "<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 4px\'>Which rules were invoked and how deep the proof chain extends:</p>"
        f"{_line_list(narrative.get('rule_chain_lines'))}"
        "<h3>\U0001f6a7 Completeness</h3>"
        "<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 4px\'>Whether any evidence gaps or recursion limits were encountered:</p>"
        f"{_line_list(narrative.get('terminal_lines'))}"
        "<h3>\U0001f50d Drill-Down</h3>"
        "<p style=\'color:var(--color-muted);font-size:.85rem;margin:0 0 4px\'>How to explore the evidence tree in more detail:</p>"
        f"{_line_list(narrative.get('drilldown_lines'))}"
        "</div>"
        f"{certainty_html}"
    )


def _line_list(lines: Any) -> str:
    if not isinstance(lines, list) or not lines:
        return "<p>None</p>"
    items = [f"<li>{escape(str(line))}</li>" for line in lines if isinstance(line, str) and line]
    return f"<ul>{''.join(items) if items else '<li>None</li>'}</ul>"


def _render_filter_index_pages(query: AuditQuery) -> dict[str, str]:
    decisions = query.list_decisions()
    failures = query.list_failures()
    accept_writes = query.list_accept_writes()

    by_event_kind: dict[str, list[dict[str, Any]]] = {}
    for row in decisions:
        key = row.get("event_kind")
        key_text = key if isinstance(key, str) and key else "<none>"
        by_event_kind.setdefault(key_text, []).append(row)

    by_error_class: dict[str, list[dict[str, Any]]] = {}
    for row in failures:
        key = row.get("error_class")
        key_text = key if isinstance(key, str) and key else "<none>"
        by_error_class.setdefault(key_text, []).append(row)

    by_pred_id_decisions: dict[str, list[dict[str, Any]]] = {}
    by_pred_id_accept_writes: dict[str, list[dict[str, Any]]] = {}
    for row in decisions:
        pred_id = row.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            by_pred_id_decisions.setdefault(pred_id, []).append(row)
    for row in accept_writes:
        pred_id = row.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            by_pred_id_accept_writes.setdefault(pred_id, []).append(row)

    return {
        "event_kinds.html": _render_event_kind_index_page(by_event_kind),
        "error_classes.html": _render_error_class_index_page(by_error_class),
        "predicates.html": _render_predicate_index_page(by_pred_id_decisions, by_pred_id_accept_writes),
    }


def _build_ui_index_payload(
    *,
    query: AuditQuery,
    run_list: dict[str, Any],
    run_ids: list[str],
    decision_ids: list[str],
    assertion_ids: list[str],
    rule_trace_ids: list[str],
    candidate_evidence_ids: list[str],
    authoring_apply_run_ids: list[str],
    index_pages: list[str],
    authoring_apply_summary: dict[str, Any] | None = None,
    compliance_matrix_rows: list[dict[str, Any]] | None = None,
    rule_trace_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decisions = query.list_decisions()
    failures = query.list_failures()
    accept_writes = query.list_accept_writes()
    candidates = query.list_candidates()

    event_kind_counts: dict[str, int] = {}
    for row in decisions:
        key = row.get("event_kind")
        if isinstance(key, str) and key:
            event_kind_counts[key] = event_kind_counts.get(key, 0) + 1

    error_class_counts: dict[str, int] = {}
    for row in failures:
        key = row.get("error_class")
        if isinstance(key, str) and key:
            error_class_counts[key] = error_class_counts.get(key, 0) + 1

    predicate_decision_counts: dict[str, int] = {}
    predicate_accept_write_counts: dict[str, int] = {}
    for row in decisions:
        pred_id = row.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            predicate_decision_counts[pred_id] = predicate_decision_counts.get(pred_id, 0) + 1
    for row in accept_writes:
        pred_id = row.get("pred_id")
        if isinstance(pred_id, str) and pred_id:
            predicate_accept_write_counts[pred_id] = predicate_accept_write_counts.get(pred_id, 0) + 1

    authoring_apply_events = load_authoring_apply_events(query.package.package_dir)
    authoring_apply_runs: list[dict[str, Any]] = []
    authoring_apply_status_counts: dict[str, int] = {}
    authoring_apply_section_counts: dict[str, int] = {}
    authoring_apply_request_ids: set[str] = set()
    for event in authoring_apply_events:
        raw = event.raw if isinstance(event.raw, dict) else {}
        status = raw.get("status")
        if isinstance(status, str) and status:
            authoring_apply_status_counts[status] = authoring_apply_status_counts.get(status, 0) + 1
        section = raw.get("section")
        if isinstance(section, str) and section:
            authoring_apply_section_counts[section] = authoring_apply_section_counts.get(section, 0) + 1
        apply_request_id = raw.get("apply_request_id")
        if isinstance(apply_request_id, str) and apply_request_id:
            authoring_apply_request_ids.add(apply_request_id)
        if raw.get("kind") == "authoring_apply_execute_run":
            summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
            authoring_apply_runs.append(
                {
                    "apply_request_id": raw.get("apply_request_id"),
                    "status": raw.get("status"),
                    "ok": bool(raw.get("ok")),
                    "path": "authoring_apply_events.html"
                    + (
                        f"#req-{_slug_id(str(raw.get('apply_request_id')))}"
                        if isinstance(raw.get("apply_request_id"), str) and raw.get("apply_request_id")
                        else ""
                    ),
                    "applied_count": summary.get("applied_count", 0),
                    "noop_count": summary.get("noop_count", 0),
                    "blocked_count": summary.get("blocked_count", 0),
                    "skipped_count": summary.get("skipped_count", 0),
                }
            )
    authoring_apply_runs = sorted(
        authoring_apply_runs,
        key=lambda row: str(row.get("apply_request_id", "")),
    )

    run_rows = []
    for row in run_list.get("runs", []):
        if not isinstance(row, dict):
            continue
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        run_rows.append(
            {
                "run_id": run_id,
                "path": f"runs/{_slug_id(run_id)}.html",
                "claim_count": row.get("claim_count", 0),
                "decision_count": row.get("decision_count", 0),
                "error_count": row.get("error_count", 0),
                "has_failures": bool(row.get("has_failures")),
                "event_ts_min": row.get("event_ts_min"),
                "event_ts_max": row.get("event_ts_max"),
            }
        )

    run_pages = {run_id: f"runs/{_slug_id(run_id)}.html" for run_id in run_ids}
    decision_pages = {decision_id: f"decisions/{_slug_id(decision_id)}.html" for decision_id in decision_ids}
    assertion_pages = {asrt_id: f"assertions/{_slug_id(asrt_id)}.html" for asrt_id in assertion_ids}
    rule_trace_pages = {rule_run_id: f"rule_traces/{_slug_id(rule_run_id)}.html" for rule_run_id in rule_trace_ids}
    candidate_evidence_pages = {
        candidate_id: f"candidate_evidence/{_slug_id(candidate_id)}.html" for candidate_id in candidate_evidence_ids
    }
    authoring_apply_run_pages = {
        request_id: f"authoring_apply_runs/{_slug_id(request_id)}.html"
        for request_id in sorted({rid for rid in authoring_apply_run_ids if isinstance(rid, str) and rid})
    }
    authoring_apply_request_pages = {
        request_id: authoring_apply_run_pages.get(
            request_id,
            f"authoring_apply_events.html#req-{_slug_id(request_id)}",
        )
        for request_id in sorted(authoring_apply_request_ids)
    }

    run_to_decisions: dict[str, set[str]] = {run_id: set() for run_id in run_ids}
    decision_to_runs: dict[str, set[str]] = {decision_id: set() for decision_id in decision_ids}
    decision_to_assertions: dict[str, set[str]] = {decision_id: set() for decision_id in decision_ids}
    run_to_assertions: dict[str, set[str]] = {run_id: set() for run_id in run_ids}
    assertion_to_runs: dict[str, set[str]] = {asrt_id: set() for asrt_id in assertion_ids}
    assertion_to_decisions: dict[str, set[str]] = {asrt_id: set() for asrt_id in assertion_ids}

    candidates_by_decision: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        decision_id = row.get("decision_id")
        if isinstance(decision_id, str) and decision_id:
            candidates_by_decision.setdefault(decision_id, []).append(row)

    for row in accept_writes:
        asrt_id = row.get("asrt_id")
        run_id = row.get("run_id")
        if isinstance(asrt_id, str) and asrt_id and isinstance(run_id, str) and run_id:
            if run_id in run_to_assertions:
                run_to_assertions[run_id].add(asrt_id)
            if asrt_id in assertion_to_runs:
                assertion_to_runs[asrt_id].add(run_id)

    for row in decisions:
        decision_id = row.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            continue

        linked_run_ids: set[str] = set()
        run_id = row.get("run_id")
        if isinstance(run_id, str) and run_id:
            linked_run_ids.add(run_id)
        for value in row.get("run_ids", []) if isinstance(row.get("run_ids"), list) else []:
            if isinstance(value, str) and value:
                linked_run_ids.add(value)

        for linked_run_id in linked_run_ids:
            if linked_run_id in run_to_decisions:
                run_to_decisions[linked_run_id].add(decision_id)
            if decision_id in decision_to_runs:
                decision_to_runs[decision_id].add(linked_run_id)

        linked_asrt_ids: set[str] = set()
        asrt_id = row.get("asrt_id")
        if isinstance(asrt_id, str) and asrt_id:
            linked_asrt_ids.add(asrt_id)
        for value in row.get("candidate_asrt_ids", []) if isinstance(row.get("candidate_asrt_ids"), list) else []:
            if isinstance(value, str) and value:
                linked_asrt_ids.add(value)
        for cand_row in candidates_by_decision.get(decision_id, []):
            cand_asrt_id = cand_row.get("asrt_id")
            if isinstance(cand_asrt_id, str) and cand_asrt_id:
                linked_asrt_ids.add(cand_asrt_id)

        for linked_asrt_id in linked_asrt_ids:
            if decision_id in decision_to_assertions:
                decision_to_assertions[decision_id].add(linked_asrt_id)
            if linked_asrt_id in assertion_to_decisions:
                assertion_to_decisions[linked_asrt_id].add(decision_id)
            for linked_run_id in linked_run_ids:
                if linked_run_id in run_to_assertions:
                    run_to_assertions[linked_run_id].add(linked_asrt_id)
                if linked_asrt_id in assertion_to_runs:
                    assertion_to_runs[linked_asrt_id].add(linked_run_id)

    predicates = sorted(set(predicate_decision_counts.keys()) | set(predicate_accept_write_counts.keys()))
    return {
        "audit_ui_index_version": "audit_ui_index_v1",
        "counts": {
            "runs": len(run_ids),
            "decisions": len(decision_ids),
            "assertions": len(assertion_ids),
            "rule_traces": len(rule_trace_ids),
            "candidate_evidence": len(candidate_evidence_ids),
            "failures": len(failures),
            "compliance_matrix_rows": len(compliance_matrix_rows or []),
            "authoring_apply_events": (
                authoring_apply_summary.get("event_count", 0)
                if isinstance(authoring_apply_summary, dict)
                else 0
            ),
        },
        "links": {
            "index": "index.html",
            "search": "search.html",
            "site_manifest": "site_manifest.json",
            "authoring_apply_events": "authoring_apply_events.html",
            "rule_traces": "rule_traces.html",
            "candidate_evidence": "candidate_evidence.html",
            "compliance_matrix": "compliance_matrix.html",
            "indexes": [f"indexes/{name}" for name in index_pages],
        },
        "lookup": {
            "run_pages": run_pages,
            "decision_pages": decision_pages,
            "assertion_pages": assertion_pages,
            "rule_trace_pages": rule_trace_pages,
            "candidate_evidence_pages": candidate_evidence_pages,
            "authoring_apply_request_pages": authoring_apply_request_pages,
            "authoring_apply_run_pages": authoring_apply_run_pages,
            "run_to_decisions": {k: sorted(v) for k, v in sorted(run_to_decisions.items())},
            "run_to_assertions": {k: sorted(v) for k, v in sorted(run_to_assertions.items())},
            "decision_to_runs": {k: sorted(v) for k, v in sorted(decision_to_runs.items())},
            "decision_to_assertions": {k: sorted(v) for k, v in sorted(decision_to_assertions.items())},
            "assertion_to_runs": {k: sorted(v) for k, v in sorted(assertion_to_runs.items())},
            "assertion_to_decisions": {k: sorted(v) for k, v in sorted(assertion_to_decisions.items())},
        },
        "runs": run_rows,
        "rule_traces": [_json_safe(row) for row in (rule_trace_rows or []) if isinstance(row, dict)],
        "authoring_apply_runs": authoring_apply_runs,
        "filters": {
            "event_kinds": [
                {"event_kind": key, "count": event_kind_counts[key], "page": "indexes/event_kinds.html"}
                for key in sorted(event_kind_counts)
            ],
            "error_classes": [
                {"error_class": key, "count": error_class_counts[key], "page": "indexes/error_classes.html"}
                for key in sorted(error_class_counts)
            ],
            "predicates": [
                {
                    "pred_id": pred_id,
                    "decision_count": predicate_decision_counts.get(pred_id, 0),
                    "accept_write_count": predicate_accept_write_counts.get(pred_id, 0),
                    "page": "indexes/predicates.html",
                }
                for pred_id in predicates
            ],
            "authoring_apply_statuses": [
                {
                    "status": key,
                    "count": authoring_apply_status_counts[key],
                    "page": "authoring_apply_events.html",
                }
                for key in sorted(authoring_apply_status_counts)
            ],
            "authoring_apply_sections": [
                {
                    "section": key,
                    "count": authoring_apply_section_counts[key],
                    "page": "authoring_apply_events.html",
                }
                for key in sorted(authoring_apply_section_counts)
            ],
            "authoring_apply_request_ids": [
                {
                    "apply_request_id": request_id,
                    "count": 1,
                    "page": authoring_apply_request_pages[request_id],
                }
                for request_id in sorted(authoring_apply_request_ids)
            ],
            "rule_traces": [
                {
                    "rule_run_id": row.get("rule_run_id"),
                    "root_rule_id": (
                        row["root_rule"].get("rule_id")
                        if isinstance(row.get("root_rule"), dict)
                        else None
                    ),
                    "count": 1,
                    "page": rule_trace_pages.get(str(row.get("rule_run_id", "")), "rule_traces.html"),
                }
                for row in (rule_trace_rows or [])
                if isinstance(row, dict) and isinstance(row.get("rule_run_id"), str) and row.get("rule_run_id")
            ],
        },
        "authoring_apply": _json_safe(authoring_apply_summary or {"event_count": 0, "status_counts": {}, "section_counts": {}}),
        "rule_trace_index": {
            "page": "rule_traces.html",
            "count": len(rule_trace_rows or []),
        },
        "candidate_evidence_index": {
            "page": "candidate_evidence.html",
            "count": len(candidate_evidence_ids),
        },
        "compliance_matrix": {
            "page": "compliance_matrix.html",
            "count": len(compliance_matrix_rows or []),
        },
    }


def _render_authoring_apply_events_page(
    events: list[Any],
    summary: dict[str, Any],
) -> str:
    rows: list[str] = []
    for event in events:
        raw = getattr(event, "raw", None)
        if not isinstance(raw, dict):
            continue
        row_attrs = ""
        req_id = raw.get("apply_request_id")
        req_cell = escape(str(req_id))
        if isinstance(req_id, str) and req_id:
            row_attrs = f" id='req-{escape(_slug_id(req_id), quote=True)}'"
            req_href = f"authoring_apply_runs/{_slug_id(req_id)}.html"
            req_cell = f"<a href='{escape(req_href, quote=True)}'>{escape(req_id)}</a>"
        rows.append(
            f"<tr{row_attrs}>"
            f"<td>{escape(str(raw.get('kind')))}</td>"
            f"<td>{escape(str(raw.get('action_id')))}</td>"
            f"<td>{escape(str(raw.get('section')))}</td>"
            f"<td>{escape(str(raw.get('status')))}</td>"
            f"<td>{req_cell}</td>"
            "</tr>"
        )
    return _html_page(
        title="Authoring Apply Events",
        body=(
            "<h1>Authoring Apply Events</h1>"
            "<p><a href='index.html'>Back to runs</a></p>"
            "<h2>Summary</h2>"
            "<ul>"
            f"<li>event_count={escape(str(summary.get('event_count', 0)))}</li>"
            f"<li>status_counts={escape(json.dumps(summary.get('status_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>section_counts={escape(json.dumps(summary.get('section_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            "</ul>"
            "<h2>Events</h2>"
            "<table><thead><tr><th>kind</th><th>action_id</th><th>section</th><th>status</th><th>apply_request_id</th></tr></thead>"
            f"<tbody>{''.join(rows) if rows else '<tr><td colspan=5>None</td></tr>'}</tbody></table>"
        ),
    )


def _render_authoring_apply_run_detail_page(payload: dict[str, Any]) -> str:
    apply_request_id = str(payload.get("apply_request_id", ""))
    run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    idempotency = payload.get("idempotency") if isinstance(payload.get("idempotency"), dict) else {}
    transaction = payload.get("transaction") if isinstance(payload.get("transaction"), dict) else {}
    classifications = payload.get("classifications") if isinstance(payload.get("classifications"), dict) else {}
    action_stats = payload.get("action_stats") if isinstance(payload.get("action_stats"), dict) else {}
    failure_summary = payload.get("failure_summary") if isinstance(payload.get("failure_summary"), dict) else {}
    execution_path = payload.get("execution_path")
    execution_path_label = payload.get("execution_path_label")
    execution_path_counts = (
        payload.get("execution_path_counts") if isinstance(payload.get("execution_path_counts"), dict) else {}
    )
    events_rows: list[str] = []
    for row in payload.get("events", []):
        if not isinstance(row, dict):
            continue
        reason_code = row.get("reason_code")
        diagnostics = row.get("diagnostics") if isinstance(row.get("diagnostics"), list) else []
        diagnostics_summary = row.get("diagnostics_summary") if isinstance(row.get("diagnostics_summary"), dict) else {}
        diag_codes = diagnostics_summary.get("codes") if isinstance(diagnostics_summary.get("codes"), list) else []
        diag_summary = ""
        if diag_codes:
            diag_summary = ",".join(str(code) for code in diag_codes if isinstance(code, str) and code)
        elif diagnostics:
            first = diagnostics[0]
            if isinstance(first, dict) and first.get("code"):
                diag_summary = str(first.get("code"))
        events_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('kind')))}</td>"
            f"<td>{escape(str(row.get('action_id')))}</td>"
            f"<td>{escape(str(row.get('section')))}</td>"
            f"<td>{escape(str(row.get('status')))}</td>"
            f"<td>{escape(str(reason_code if reason_code is not None else ''))}</td>"
            f"<td>{escape(diag_summary)}</td>"
            "</tr>"
        )
    return _html_page(
        title=f"Authoring Apply Run {apply_request_id}",
        body=(
            f"<h1>Authoring Apply Run {escape(apply_request_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a> | "
            "<a href='../authoring_apply_events.html'>All authoring apply events</a></p>"
            "<h2>Run</h2>"
            "<ul>"
            f"<li>status={escape(str(run.get('status')))}</li>"
            f"<li>ok={escape(str(run.get('ok')))}</li>"
            f"<li>kind={escape(str(run.get('kind')))}</li>"
            "</ul>"
            "<h2>Idempotency</h2>"
            "<ul>"
            f"<li>apply_request_id={escape(str(idempotency.get('apply_request_id')))}</li>"
            f"<li>plan_digest={escape(str(idempotency.get('plan_digest')))}</li>"
            f"<li>replayed={escape(str(idempotency.get('replayed')))}</li>"
            f"<li>conflict={escape(str(idempotency.get('conflict')))}</li>"
            "</ul>"
            "<h2>Transaction</h2>"
            "<ul>"
            f"<li>policy={escape(str(transaction.get('policy')))}</li>"
            f"<li>rollback_attempted={escape(str(transaction.get('rollback_attempted')))}</li>"
            f"<li>prevalidate_before_write={escape(str(transaction.get('prevalidate_before_write')))}</li>"
            f"<li>prevalidate_status={escape(str(transaction.get('prevalidate_status')))}</li>"
            f"<li>writes_started={escape(str(transaction.get('writes_started')))}</li>"
            f"<li>failure_phase={escape(str(transaction.get('failure_phase')))}</li>"
            f"<li>partial_apply={escape(str(transaction.get('partial_apply')))}</li>"
            "</ul>"
            "<h2>Classifications</h2>"
            "<ul>"
            f"<li>replayed={escape(str(classifications.get('replayed')))}</li>"
            f"<li>conflict={escape(str(classifications.get('conflict')))}</li>"
            f"<li>prevalidate_blocked={escape(str(classifications.get('prevalidate_blocked')))}</li>"
            f"<li>runtime_blocked_after_write={escape(str(classifications.get('runtime_blocked_after_write')))}</li>"
            f"<li>execution_path={escape(str(execution_path))}</li>"
            f"<li>execution_path_label={escape(str(execution_path_label))}</li>"
            "</ul>"
            "<h2>Summary</h2>"
            "<ul>"
            f"<li>event_count={escape(str(summary.get('event_count', 0)))}</li>"
            f"<li>status_counts={escape(json.dumps(summary.get('status_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>section_counts={escape(json.dumps(summary.get('section_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>stats.event_count={escape(str(stats.get('event_count', 0)))}</li>"
            f"<li>stats.action_event_count={escape(str(stats.get('action_event_count', 0)))}</li>"
            f"<li>stats.run_event_count={escape(str(stats.get('run_event_count', 0)))}</li>"
            f"<li>action_stats.status_counts={escape(json.dumps(action_stats.get('status_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>action_stats.reason_code_counts={escape(json.dumps(action_stats.get('reason_code_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>action_stats.diagnostic_code_counts={escape(json.dumps(action_stats.get('diagnostic_code_counts', {}), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>failure_summary.first_failure_action_id={escape(str(failure_summary.get('first_failure_action_id')))}</li>"
            f"<li>failure_summary.first_failure_section={escape(str(failure_summary.get('first_failure_section')))}</li>"
            f"<li>failure_summary.blocked_action_reason_codes={escape(json.dumps(failure_summary.get('blocked_action_reason_codes', []), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>failure_summary.blocked_action_diagnostic_codes={escape(json.dumps(failure_summary.get('blocked_action_diagnostic_codes', []), ensure_ascii=False, sort_keys=True))}</li>"
            f"<li>execution_path_counts={escape(json.dumps(execution_path_counts, ensure_ascii=False, sort_keys=True))}</li>"
            "</ul>"
            "<h2>Events</h2>"
            "<table><thead><tr><th>kind</th><th>action_id</th><th>section</th><th>status</th><th>reason_code</th><th>diag0</th></tr></thead>"
            f"<tbody>{''.join(events_rows) if events_rows else '<tr><td colspan=6>None</td></tr>'}</tbody></table>"
            "<h2>Payload</h2>"
            f"<pre>{escape(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
        ),
    )


def _render_search_page() -> str:
    script = """
(() => {
  const qInput = document.getElementById("q");
  const typeInput = document.getElementById("type");
  const statusEl = document.getElementById("status");
  const resultsEl = document.getElementById("results");
  const countsEl = document.getElementById("counts");

  const qp = new URLSearchParams(window.location.search);
  if (qp.has("q")) qInput.value = qp.get("q") || "";
  if (qp.has("type")) typeInput.value = qp.get("type") || "all";

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function rowLink(path, label, meta) {
    return "<li><a href='" + esc(path) + "'>" + esc(label) + "</a>" +
      (meta ? " <span style='color:#666'>" + esc(meta) + "</span>" : "") +
      "</li>";
  }

  const TYPE_MAP = {
    all: null,
    run: "runs",
    rule_trace: "ruleTraces",
    decision: "decisions",
    assertion: "assertions",
    pred_id: "predicates",
    event_kind: "eventKinds",
    error_class: "errorClasses",
    authoring_apply_request_id: "authoringApplyRequestIds",
    authoring_apply_status: "authoringApplyStatuses",
    authoring_apply_section: "authoringApplySections",
  };

  function render(index, q, typeFilter) {
    const needle = q.trim().toLowerCase();
    const selectedBucket = TYPE_MAP[typeFilter] || null;
    if (!needle) {
      countsEl.textContent = "Type to search runs / rule traces / decisions / assertions / predicates / event kinds / error classes / authoring apply";
      resultsEl.innerHTML = "";
      return;
    }

    const hits = { runs: [], ruleTraces: [], decisions: [], assertions: [], predicates: [], eventKinds: [], errorClasses: [], authoringApplyRequestIds: [], authoringApplyStatuses: [], authoringApplySections: [] };
    for (const run of (index.runs || [])) {
      if (String(run.run_id || "").toLowerCase().includes(needle)) {
        hits.runs.push(run);
      }
    }
    for (const row of (index.rule_traces || [])) {
      const ruleRunId = String(row.rule_run_id || "").toLowerCase();
      const rootRuleId = String(((row.root_rule || {}).rule_id) || "").toLowerCase();
      if (ruleRunId.includes(needle) || rootRuleId.includes(needle)) {
        hits.ruleTraces.push(row);
      }
    }
    for (const [decisionId, path] of Object.entries((index.lookup || {}).decision_pages || {})) {
      if (decisionId.toLowerCase().includes(needle)) {
        hits.decisions.push({ decision_id: decisionId, path });
      }
    }
    for (const [asrtId, path] of Object.entries((index.lookup || {}).assertion_pages || {})) {
      if (asrtId.toLowerCase().includes(needle)) {
        hits.assertions.push({ asrt_id: asrtId, path });
      }
    }
    for (const row of (((index.filters || {}).predicates) || [])) {
      if (String(row.pred_id || "").toLowerCase().includes(needle)) {
        hits.predicates.push(row);
      }
    }
    for (const row of (((index.filters || {}).event_kinds) || [])) {
      if (String(row.event_kind || "").toLowerCase().includes(needle)) {
        hits.eventKinds.push(row);
      }
    }
    for (const row of (((index.filters || {}).error_classes) || [])) {
      if (String(row.error_class || "").toLowerCase().includes(needle)) {
        hits.errorClasses.push(row);
      }
    }
    for (const row of (((index.filters || {}).authoring_apply_request_ids) || [])) {
      if (String(row.apply_request_id || "").toLowerCase().includes(needle)) {
        hits.authoringApplyRequestIds.push(row);
      }
    }
    for (const row of (((index.filters || {}).authoring_apply_statuses) || [])) {
      if (String(row.status || "").toLowerCase().includes(needle)) {
        hits.authoringApplyStatuses.push(row);
      }
    }
    for (const row of (((index.filters || {}).authoring_apply_sections) || [])) {
      if (String(row.section || "").toLowerCase().includes(needle)) {
        hits.authoringApplySections.push(row);
      }
    }

    const visibleBuckets = selectedBucket ? [selectedBucket] : ["runs","ruleTraces","decisions","assertions","predicates","eventKinds","errorClasses","authoringApplyRequestIds","authoringApplyStatuses","authoringApplySections"];
    const total = visibleBuckets.reduce((n, key) => n + (hits[key] || []).length, 0);
    countsEl.textContent = `Results: ${total} (type=${typeFilter || "all"})`;

    const sections = [];
    function maybePush(bucketKey, html) {
      if (visibleBuckets.includes(bucketKey)) sections.push(html);
    }
    maybePush("runs", "<h2>Runs</h2><ul>" + (hits.runs.map(r => rowLink(r.path, r.run_id, `claims=${r.claim_count} decisions=${r.decision_count} errors=${r.error_count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("ruleTraces", "<h2>Rule Traces</h2><ul>" + (hits.ruleTraces.map(r => rowLink(((index.lookup || {}).rule_trace_pages || {})[r.rule_run_id] || \"rule_traces.html\", r.rule_run_id, `root_rule=${((r.root_rule || {}).rule_id) || \"\"} witnesses=${r.witness_assertion_count || 0}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("decisions", "<h2>Decisions</h2><ul>" + (hits.decisions.map(r => rowLink(r.path, r.decision_id, "")).join("") || "<li>None</li>") + "</ul>");
    maybePush("assertions", "<h2>Assertions</h2><ul>" + (hits.assertions.map(r => rowLink(r.path, r.asrt_id, "")).join("") || "<li>None</li>") + "</ul>");
    maybePush("predicates", "<h2>Predicates</h2><ul>" + (hits.predicates.map(r => rowLink(r.page, r.pred_id, `decisions=${r.decision_count} accept_writes=${r.accept_write_count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("eventKinds", "<h2>Event Kinds</h2><ul>" + (hits.eventKinds.map(r => rowLink(r.page, r.event_kind, `count=${r.count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("errorClasses", "<h2>Error Classes</h2><ul>" + (hits.errorClasses.map(r => rowLink(r.page, r.error_class, `count=${r.count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("authoringApplyRequestIds", "<h2>Authoring Apply Request IDs</h2><ul>" + (hits.authoringApplyRequestIds.map(r => rowLink(r.page, r.apply_request_id, `count=${r.count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("authoringApplyStatuses", "<h2>Authoring Apply Statuses</h2><ul>" + (hits.authoringApplyStatuses.map(r => rowLink(r.page, r.status, `count=${r.count}`)).join("") || "<li>None</li>") + "</ul>");
    maybePush("authoringApplySections", "<h2>Authoring Apply Sections</h2><ul>" + (hits.authoringApplySections.map(r => rowLink(r.page, r.section, `count=${r.count}`)).join("") || "<li>None</li>") + "</ul>");
    resultsEl.innerHTML = sections.join("");
  }

  function syncUrl() {
    const p = new URLSearchParams();
    if (qInput.value) p.set("q", qInput.value);
    if (typeInput.value && typeInput.value !== "all") p.set("type", typeInput.value);
    const qs = p.toString();
    const next = qs ? ("?" + qs) : window.location.pathname;
    history.replaceState(null, "", next);
  }

  fetch("ui_index.json")
    .then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(index => {
      statusEl.textContent = "Loaded ui_index.json";
      render(index, qInput.value || "", typeInput.value || "all");
      qInput.addEventListener("input", () => {
        syncUrl();
        render(index, qInput.value || "", typeInput.value || "all");
      });
      typeInput.addEventListener("change", () => {
        syncUrl();
        render(index, qInput.value || "", typeInput.value || "all");
      });
    })
    .catch(err => {
      statusEl.textContent = "Failed to load ui_index.json: " + err;
    });
})();
""".strip()
    return _html_page(
        title="Audit Search",
        body=(
            "<h1>Audit Search</h1>"
            "<p><a href='index.html'>Back to runs</a></p>"
            "<p><label for='q'>Search</label> <input id='q' type='search' placeholder='run_id / decision_id / asrt_id / pred_id' style='min-width:420px'> "
            "<label for='type'>Type</label> "
            "<select id='type'>"
            "<option value='all'>all</option>"
            "<option value='run'>run</option>"
            "<option value='rule_trace'>rule_trace</option>"
            "<option value='decision'>decision</option>"
            "<option value='assertion'>assertion</option>"
            "<option value='pred_id'>pred_id</option>"
            "<option value='event_kind'>event_kind</option>"
            "<option value='error_class'>error_class</option>"
            "<option value='authoring_apply_request_id'>authoring_apply_request_id</option>"
            "<option value='authoring_apply_status'>authoring_apply_status</option>"
            "<option value='authoring_apply_section'>authoring_apply_section</option>"
            "</select></p>"
            "<p id='status'>Loading ui_index.json...</p>"
            "<p id='counts'></p>"
            "<div id='results'></div>"
            f"<script>{script}</script>"
        ),
    )


def _render_event_kind_index_page(groups: dict[str, list[dict[str, Any]]]) -> str:
    blocks: list[str] = []
    for event_kind in sorted(groups):
        rows = sorted(groups[event_kind], key=lambda r: (str(r.get("decision_id", "")), str(r.get("event_ts", ""))))
        search_href = _search_href(event_kind, "event_kind", prefix="..")
        items = []
        for row in rows:
            decision_id = str(row.get("decision_id", ""))
            run_ids = _sorted_unique_strings(row.get("run_ids"))
            href = f"../decisions/{_slug_id(decision_id)}.html" if decision_id else ""
            decision_link = (
                f"<a href='{escape(href, quote=True)}'>{escape(decision_id)}</a>" if decision_id else "-"
            )
            items.append(
                "<tr>"
                f"<td>{decision_link}</td>"
                f"<td>{escape(','.join(run_ids)) or '-'}</td>"
                f"<td>{escape(str(row.get('pred_id')))}</td>"
                f"<td>{escape(str(row.get('event_ts')))}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h3>{escape(event_kind)} ({len(rows)})</h3>"
            f"<p><a href='{escape(search_href, quote=True)}'>Open in search</a></p>"
            "<table><thead><tr><th>Decision</th><th>Runs</th><th>Pred</th><th>Ts</th></tr></thead>"
            f"<tbody>{''.join(items) if items else '<tr><td colspan=4>None</td></tr>'}</tbody></table>"
        )
    return _html_page(
        title="Event Kind Index",
        body=(
            "<h1>Decision Event Kinds</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            f"{''.join(blocks) if blocks else '<p>No decisions</p>'}"
        ),
    )


def _render_error_class_index_page(groups: dict[str, list[dict[str, Any]]]) -> str:
    blocks: list[str] = []
    for error_class in sorted(groups):
        rows = sorted(groups[error_class], key=lambda r: (str(r.get("decision_id", "")), str(r.get("event_ts", ""))))
        search_href = _search_href(error_class, "error_class", prefix="..")
        items = []
        for row in rows:
            decision_id = str(row.get("decision_id", ""))
            href = f"../decisions/{_slug_id(decision_id)}.html" if decision_id else ""
            decision_link = (
                f"<a href='{escape(href, quote=True)}'>{escape(decision_id)}</a>" if decision_id else "-"
            )
            items.append(
                "<tr>"
                f"<td>{decision_link}</td>"
                f"<td>{escape(','.join(_sorted_unique_strings(row.get('run_ids')))) or '-'}</td>"
                f"<td>{escape(str(row.get('event_kind')))}</td>"
                f"<td>{escape(str(row.get('message')))}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h3>{escape(error_class)} ({len(rows)})</h3>"
            f"<p><a href='{escape(search_href, quote=True)}'>Open in search</a></p>"
            "<table><thead><tr><th>Decision</th><th>Runs</th><th>Event</th><th>Message</th></tr></thead>"
            f"<tbody>{''.join(items) if items else '<tr><td colspan=4>None</td></tr>'}</tbody></table>"
        )
    return _html_page(
        title="Error Class Index",
        body=(
            "<h1>Failure Error Classes</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            f"{''.join(blocks) if blocks else '<p>No failures</p>'}"
        ),
    )


def _render_predicate_index_page(
    decision_groups: dict[str, list[dict[str, Any]]],
    accept_write_groups: dict[str, list[dict[str, Any]]],
) -> str:
    pred_ids = sorted(set(decision_groups.keys()) | set(accept_write_groups.keys()))
    blocks: list[str] = []
    for pred_id in pred_ids:
        decisions = sorted(decision_groups.get(pred_id, []), key=lambda r: str(r.get("decision_id", "")))
        accept_writes = sorted(
            accept_write_groups.get(pred_id, []),
            key=lambda r: (str(r.get("candidate_id", "")), str(r.get("asrt_id", ""))),
        )
        search_href = _search_href(pred_id, "pred_id", prefix="..")
        decision_items = []
        for row in decisions:
            decision_id = str(row.get("decision_id", ""))
            href = f"../decisions/{_slug_id(decision_id)}.html" if decision_id else ""
            decision_link = (
                f"<a href='{escape(href, quote=True)}'>{escape(decision_id)}</a>" if decision_id else "-"
            )
            decision_items.append(
                "<li>"
                f"{decision_link} [{escape(str(row.get('event_kind')))}]"
                "</li>"
            )
        accept_write_items = []
        for row in accept_writes:
            asrt_id = row.get("asrt_id")
            asrt_link = escape(str(asrt_id))
            if isinstance(asrt_id, str) and asrt_id:
                href = f"../assertions/{_slug_id(asrt_id)}.html"
                asrt_link = f"<a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a>"
            accept_write_items.append(
                "<li>"
                f"{escape(str(row.get('candidate_id')))} → {asrt_link}"
                "</li>"
            )
        blocks.append(
            f"<h3>{escape(pred_id)}</h3>"
            f"<p><a href='{escape(search_href, quote=True)}'>Open in search</a></p>"
            f"<p>decisions={len(decisions)} | accept_writes={len(accept_writes)}</p>"
            "<h4>Decisions</h4>"
            f"<ul>{''.join(decision_items) if decision_items else '<li>None</li>'}</ul>"
            "<h4>Accept Writes</h4>"
            f"<ul>{''.join(accept_write_items) if accept_write_items else '<li>None</li>'}</ul>"
        )
    return _html_page(
        title="Predicate Index",
        body=(
            "<h1>Predicate Index</h1>"
            "<p><a href='../index.html'>Back to runs</a></p>"
            f"{''.join(blocks) if blocks else '<p>No predicate rows</p>'}"
        ),
    )


def _index_page_links(index_pages: list[str]) -> list[str]:
    pretty = {
        "event_kinds.html": "Decision Event Kinds",
        "error_classes.html": "Failure Error Classes",
        "predicates.html": "Predicate Index",
    }
    out: list[str] = []
    for name in index_pages:
        href = f"indexes/{name}"
        out.append(f"<li><a href='{escape(href, quote=True)}'>{escape(pretty.get(name, name))}</a></li>")
    return out


def _search_href(query_text: str, type_name: str, *, prefix: str = ".") -> str:
    return f"{prefix}/search.html?q={quote(query_text, safe='')}&type={quote(type_name, safe='')}"


def _render_assertion_summary_block(detail: dict[str, Any], assertions_href_prefix: str) -> str:
    claim = detail.get("claim") if isinstance(detail.get("claim"), dict) else {}
    asrt_id = str(detail.get("asrt_id", ""))
    href = f"{assertions_href_prefix}/{_slug_id(asrt_id)}.html"
    claim_args = detail.get("claim_args")
    arg_summary_parts: list[str] = []
    if isinstance(claim_args, list):
        for row in claim_args[:3]:
            if not isinstance(row, dict):
                continue
            arg_summary_parts.append(
                f"{row.get('idx')}:{row.get('tag')}={row.get('val')}"
            )
    meta = detail.get("meta") if isinstance(detail.get("meta"), dict) else {}
    source_value = _meta_summary_value(meta, "str", "source")
    ingested_at_value = _meta_summary_value(meta, "time", "ingested_at")
    return (
        "<div style='border:1px solid #eee;padding:8px;margin:8px 0'>"
        f"<p><strong><a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a></strong></p>"
        f"<p>pred={escape(str(claim.get('pred_id')))} | e_ref={escape(str(claim.get('e_ref')))}</p>"
        f"<p>claim_arg={escape('; '.join(arg_summary_parts)) or '-'}</p>"
        f"<p>source={escape(str(source_value))} | ingested_at={escape(str(ingested_at_value))} | revoked={escape(str(bool(detail.get('is_revoked'))))}</p>"
        "</div>"
    )


def _meta_summary_value(meta: dict[str, Any], kind: str, key: str) -> Any:
    rows = meta.get(kind)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("key") == key:
            return row.get("value")
    return None


def _sorted_unique_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str)})


def _slug_id(value: str) -> str:
    return quote(value, safe="").replace("%", "~")


def _html_page(*, title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title>"
        "<style>"
        ":root{"
        "--color-structural:#375a7f;--color-witness:#2e7d32;--color-constraint:#ad6800;"
        "--color-rule-chain:#7c4d9d;--color-terminal:#b42318;--color-degraded:#6b7280;"
        "--color-bg:#f5f2ea;--color-surface:#fffdf8;--color-border:#d6d1c4;--color-text:#2b2b2b;--color-muted:#6b6b6b;"
        "--color-accent:#9c6b2f;--color-accent-soft:#efe3cf;--color-success:#2e7d32;--color-success-soft:#e7f4ea;"
        "--color-warning:#ad6800;--color-warning-soft:#fff3d6;--color-danger:#b42318;--color-danger-soft:#fdecea;"
        "--radius:10px;--shadow:0 10px 30px rgba(43,43,43,0.08)"
        "}"
        "body{font-family:Georgia,'Times New Roman',serif;margin:0;padding:24px 32px;line-height:1.5;"
        "color:var(--color-text);background:linear-gradient(180deg,#f7f4ee 0%,#f1ede3 100%);max-width:1200px;margin:0 auto;padding:24px 32px}"
        "h1{font-size:1.8rem;font-weight:700;margin-bottom:4px;letter-spacing:-0.01em}"
        "h2{font-size:1.15rem;font-weight:600;margin-top:28px;padding-bottom:6px;border-bottom:2px solid var(--color-border)}"
        "a{color:#0f5d85;text-decoration:none}a:hover{text-decoration:underline}"
        "table{border-collapse:collapse;width:100%;background:var(--color-surface)}th,td{border:1px solid var(--color-border);padding:8px;text-align:left}"
        "th{background:#ece4d6;font-weight:600;font-size:.85rem;text-transform:uppercase;letter-spacing:.03em}"
        "code,pre{font-family:ui-monospace,\'SF Mono\',Menlo,monospace;font-size:.85rem}"
        "pre{overflow:auto;background:var(--color-surface);padding:12px 16px;border:1px solid var(--color-border);border-radius:var(--radius)}"
        ".nav{margin-bottom:20px;font-size:.85rem;color:var(--color-muted)}"
        ".nav a{margin-right:12px}"
        ".summary-grid{display:grid;grid-template-columns:140px 1fr;gap:4px 12px;font-size:.9rem;margin:8px 0 16px}"
        ".summary-grid dt{color:var(--color-muted);font-weight:500;text-align:right}"
        ".summary-grid dd{margin:0;word-break:break-all}"
        ".hero,.snapshot-card,.narrative-section,.certainty-section{background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius);box-shadow:var(--shadow)}"
        ".hero{padding:22px 24px;margin-bottom:20px;background:linear-gradient(135deg,#fdfaf4 0%,#f4ebdb 100%)}"
        ".snapshot-card{padding:20px 22px;margin-bottom:10px;display:flex;align-items:flex-start;justify-content:space-between;gap:18px}"
        ".eyebrow{margin:0 0 6px;font-size:.75rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--color-accent)}"
        ".hero-copy{margin:0;color:var(--color-muted);max-width:780px}"
        ".metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:18px}"
        ".metric-card{background:rgba(255,255,255,0.72);border:1px solid var(--color-border);border-radius:var(--radius);padding:14px 16px}"
        ".metric-card-label{display:block;font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--color-muted)}"
        ".metric-card-value{display:block;font-size:1.7rem;font-weight:700;margin:4px 0 6px}"
        ".metric-card-copy{display:block;font-size:.85rem;color:var(--color-muted)}"
        ".link-rail{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}"
        ".link-rail a{display:inline-flex;align-items:center;padding:8px 12px;border-radius:999px;background:var(--color-surface);border:1px solid var(--color-border);box-shadow:var(--shadow)}"
        ".section-copy{color:var(--color-muted);font-size:.88rem;margin:0 0 12px}"
        ".status-badge{display:inline-block;padding:4px 10px;border-radius:999px;font-size:.8rem;font-weight:700;letter-spacing:.04em}"
        ".status-ok{background:var(--color-success-soft);color:var(--color-success)}"
        ".status-bad{background:var(--color-danger-soft);color:var(--color-danger)}"
        ".status-neutral{background:var(--color-accent-soft);color:var(--color-accent)}"
        ".snapshot-meta{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}"
        ".tree-node{border-left:3px solid var(--color-border);background:var(--color-surface);border-radius:var(--radius);"
        "box-shadow:var(--shadow);margin:8px 0;padding:0;overflow:hidden}"
        ".tree-node>.node-header{display:flex;align-items:center;gap:8px;padding:8px 14px;"
        "font-weight:600;font-size:.85rem;color:#fff}"
        ".tree-node>.node-body{padding:8px 14px 10px;font-size:.85rem}"
        ".tree-node>.node-body .prop{display:flex;gap:6px;padding:2px 0}"
        ".tree-node>.node-body .prop-key{color:var(--color-muted);min-width:100px;flex-shrink:0}"
        ".tree-node>.node-body .prop-val{word-break:break-all}"
        ".tree-node>.node-children{padding:0 0 0 20px}"
        ".node-kind-structural>.node-header{background:var(--color-structural)}"
        ".node-kind-witness>.node-header{background:var(--color-witness)}"
        ".node-kind-constraint>.node-header{background:var(--color-constraint)}"
        ".node-kind-rule-chain>.node-header{background:var(--color-rule-chain)}"
        ".node-kind-terminal>.node-header{background:var(--color-terminal)}"
        ".node-kind-degraded>.node-header{background:var(--color-degraded)}"
        ".icon{font-size:1rem;line-height:1}"
        ".certainty-section{padding:16px 20px;margin:12px 0}"
        ".certainty-header{display:flex;align-items:baseline;gap:12px;margin-bottom:12px}"
        ".certainty-header h3{margin:0;font-size:1rem}"
        ".certainty-aggregate{font-size:1.1rem;font-weight:700;border-radius:999px;padding:4px 12px}"
        ".certainty-aggregate.high{background:var(--color-success-soft);color:var(--color-success)}"
        ".certainty-aggregate.medium{background:var(--color-warning-soft);color:var(--color-warning)}"
        ".certainty-aggregate.low{background:var(--color-danger-soft);color:var(--color-danger)}"
        ".certainty-aggregate.neutral{background:var(--color-accent-soft);color:var(--color-accent)}"
        ".certainty-bar-row{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:.85rem}"
        ".certainty-bar-label{min-width:180px;flex-shrink:0}"
        ".certainty-bar-track{flex:1;height:20px;background:#e8e3d8;border-radius:10px;overflow:hidden;position:relative}"
        ".certainty-bar-fill{height:100%;border-radius:10px;transition:width .3s}"
        ".certainty-bar-fill.high{background:linear-gradient(90deg,#4caf50,#2e7d32)}"
        ".certainty-bar-fill.medium{background:linear-gradient(90deg,#ffd54f,#ad6800)}"
        ".certainty-bar-fill.low{background:linear-gradient(90deg,#ef9a9a,#b42318)}"
        ".certainty-bar-value{min-width:50px;text-align:right;font-weight:600}"
        ".certainty-badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.75rem;"
        "font-weight:600;margin-left:6px}"
        ".certainty-badge.bottleneck{background:#ffebee;color:#c62828}"
        ".certainty-strategy{font-size:.8rem;color:var(--color-muted);font-weight:400}"
        ".narrative-section{padding:16px 20px;margin:12px 0}"
        ".narrative-section h3{font-size:.95rem;color:var(--color-muted);margin:12px 0 4px;font-weight:600}"
        ".narrative-section ul{margin:0;padding-left:20px}"
        ".narrative-section li{margin:2px 0;font-size:.9rem}"
        ".node-desc{color:var(--color-muted);font-size:.8rem;font-style:italic;margin-bottom:4px}details{margin-top:16px}summary{cursor:pointer;font-weight:600;font-size:.9rem;color:var(--color-muted)}"
        "@media (max-width: 800px){body{padding:16px}.summary-grid{grid-template-columns:1fr}.summary-grid dt{text-align:left}.snapshot-card{flex-direction:column}.certainty-bar-row{flex-direction:column;align-items:stretch}.certainty-bar-label{min-width:0}.link-rail{flex-direction:column}}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


def _metric_card(label: str, value: Any, copy: str) -> str:
    return (
        "<div class='metric-card'>"
        f"<span class='metric-card-label'>{escape(label)}</span>"
        f"<span class='metric-card-value'>{escape(str(value))}</span>"
        f"<span class='metric-card-copy'>{escape(copy)}</span>"
        "</div>"
    )
