from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .authoring_events import load_authoring_apply_events, summarize_authoring_apply_events
from .assertions import load_assertion_index
from .dto import (
    build_authoring_apply_run_detail_dto,
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
        page = _render_candidate_evidence_page(candidate_tree)
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
    return _html_page(
        title="Audit Runs",
        body=(
            "<h1>Audit Runs</h1>"
            "<p><a href='search.html'>Search</a></p>"
            f"<p><a href='authoring_apply_events.html'>Authoring Apply Events</a> ({escape(str(apply_count))})</p>"
            f"<p><a href='rule_traces.html'>Rule Traces</a> ({escape(str(rule_trace_count))})</p>"
            f"<p><a href='candidate_evidence.html'>Candidate Evidence Trees</a> ({escape(str(candidate_evidence_count))})</p>"
            f"<p><a href='compliance_matrix.html'>Compliance Matrix</a> ({escape(str(compliance_matrix_count))})</p>"
            "<h2>Indexes</h2>"
            f"<ul>{''.join(_index_page_links(index_pages)) if index_pages else '<li>None</li>'}</ul>"
            "<h2>Runs</h2>"
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


def _render_candidate_evidence_page(tree: dict[str, Any]) -> str:
    candidate_id = str(tree.get("candidate_id", ""))
    support_digest = str(tree.get("support_digest", ""))
    support_kind = str(tree.get("support_kind", ""))
    root = tree.get("root") if isinstance(tree.get("root"), dict) else {}
    binding = root.get("binding") if isinstance(root.get("binding"), dict) else {}
    rule_refs = [item for item in root.get("rule_refs", []) if isinstance(item, str) and item]
    rule_ref_edges = [
        item
        for item in root.get("rule_ref_edges", [])
        if isinstance(item, dict)
    ]
    return _html_page(
        title=f"Candidate Evidence {candidate_id}",
        body=(
            f"<h1>Candidate Evidence {escape(candidate_id)}</h1>"
            "<p><a href='../index.html'>Back to runs</a> | "
            "<a href='../candidate_evidence.html'>All candidate evidence trees</a></p>"
            "<h2>Summary</h2>"
            "<ul>"
            f"<li>support_digest={escape(support_digest)}</li>"
            f"<li>support_kind={escape(support_kind)}</li>"
            f"<li>root_result_kind={escape(str(root.get('root_result_kind')))}</li>"
            f"<li>rule_refs={escape(','.join(rule_refs)) or '-'}</li>"
            f"<li>rule_ref_edges={escape(str(len(rule_ref_edges)))}</li>"
            "</ul>"
            "<h2>Binding</h2>"
            f"<pre>{escape(json.dumps(binding, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "<h2>Tree</h2>"
            f"{_render_candidate_evidence_node(root, assertion_href_prefix='../assertions')}"
            "<details><summary>Raw Payload</summary>"
            f"<pre>{escape(json.dumps(tree, ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "</details>"
        ),
    )


def _render_candidate_evidence_node(node: dict[str, Any], *, assertion_href_prefix: str) -> str:
    node_kind = str(node.get("node_kind", ""))
    title = str(node.get("title", node.get("node_id", "")))
    items: list[str] = [
        f"<li>node_kind={escape(node_kind)}</li>",
    ]
    if node_kind == "candidate_result":
        items.append(f"<li>root_result_kind={escape(str(node.get('root_result_kind')))}</li>")
    elif node_kind == "support_section":
        items.append(f"<li>section_children={escape(str(len(node.get('children', []))))}</li>")
    elif node_kind == "rule_ref_section":
        items.append(f"<li>section_children={escape(str(len(node.get('children', []))))}</li>")
    elif node_kind == "rule_ref":
        items.append(f"<li>ruleref_atom_key={escape(str(node.get('ruleref_atom_key')))}</li>")
        items.append(f"<li>rule_ref_id={escape(str(node.get('rule_ref_id')))}</li>")
        items.append(f"<li>rule_ref_version={escape(str(node.get('rule_ref_version')))}</li>")
        items.append(f"<li>child_support_digest={escape(str(node.get('child_support_digest')))}</li>")
        items.append(f"<li>unresolved_reason={escape(str(node.get('unresolved_reason')))}</li>")
    elif node_kind == "referenced_support":
        items.append(f"<li>support_digest={escape(str(node.get('support_digest')))}</li>")
        items.append(f"<li>root_result_kind={escape(str(node.get('root_result_kind')))}</li>")
    elif node_kind == "unresolved_support":
        items.append(f"<li>reason={escape(str(node.get('reason')))}</li>")
        items.append(f"<li>child_support_digest={escape(str(node.get('child_support_digest')))}</li>")
    elif node_kind == "recursion_boundary":
        items.append(f"<li>boundary_reason={escape(str(node.get('boundary_reason')))}</li>")
    elif node_kind == "predicate_witness_group":
        items.append(f"<li>pred_atom_key={escape(str(node.get('pred_atom_key')))}</li>")
        items.append(f"<li>pred_id={escape(str(node.get('pred_id')))}</li>")
        items.append(f"<li>assertion_count={escape(str(node.get('assertion_count')))}</li>")
    elif node_kind == "non_fact_check":
        items.append(f"<li>step_key={escape(str(node.get('step_key')))}</li>")
        items.append(f"<li>check_kind={escape(str(node.get('check_kind')))}</li>")
        items.append(f"<li>status={escape(str(node.get('status')))}</li>")
        items.append(
            "<li>details="
            f"<pre>{escape(json.dumps(node.get('details'), ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "</li>"
        )
    elif node_kind == "assertion_fact":
        asrt_id = str(node.get("asrt_id", ""))
        href = f"{assertion_href_prefix}/{_slug_id(asrt_id)}.html"
        items.append(
            "<li>assertion="
            f"<a href='{escape(href, quote=True)}'>{escape(asrt_id)}</a>"
            "</li>"
        )
        items.append(f"<li>pred_id={escape(str(node.get('pred_id')))}</li>")
        items.append(f"<li>e_ref={escape(str(node.get('e_ref')))}</li>")
        items.append(
            "<li>claim_args="
            f"<pre>{escape(json.dumps(node.get('claim_args'), ensure_ascii=False, sort_keys=True, indent=2))}</pre>"
            "</li>"
        )

    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    child_html = "".join(
        f"<li>{_render_candidate_evidence_node(child, assertion_href_prefix=assertion_href_prefix)}</li>"
        for child in children
    )
    return (
        "<div style='border:1px solid #eee;padding:12px;margin:12px 0'>"
        f"<h3>{escape(title)}</h3>"
        f"<ul>{''.join(items)}</ul>"
        "<h4>Children</h4>"
        f"<ul>{child_html if child_html else '<li>None</li>'}</ul>"
        "</div>"
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


def _render_rule_trace_narrative_block(narrative: dict[str, Any] | None) -> str:
    if not isinstance(narrative, dict):
        return ""

    def _line_list(lines: Any) -> str:
        if not isinstance(lines, list) or not lines:
            return "<p>None</p>"
        items = [f"<li>{escape(str(line))}</li>" for line in lines if isinstance(line, str) and line]
        return f"<ul>{''.join(items) if items else '<li>None</li>'}</ul>"

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
    return quote(value, safe="")


def _html_page(*, title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,Arial,sans-serif;margin:24px;line-height:1.4}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:6px;text-align:left}"
        "th{background:#f5f5f5}code,pre{font-family:ui-monospace,Menlo,monospace}pre{overflow:auto;background:#fafafa;padding:12px;border:1px solid #eee}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )
