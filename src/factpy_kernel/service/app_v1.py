from __future__ import annotations

import logging
from typing import Any

from fastapi import Body, Depends, FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from factpy_kernel.service.registry_v1 import (
    list_registry_assets,
    read_registry_derivation,
    read_registry_manifest,
    read_registry_rule,
    read_registry_schema,
)
from factpy_kernel.service.rules_v1 import compile_rule_preview, list_profiles, validate_rule
from factpy_kernel.service.runtime_v1 import (
    accept_runtime_derivation,
    clear_ephemeral_rules,
    close_runtime_session,
    create_runtime_view,
    delete_runtime_view,
    evaluate_runtime_derivation,
    explain_runtime_ref,
    explain_runtime_tree,
    explain_runtime_fact,
    explain_runtime_nl,
    explain_runtime_narrative,
    explain_runtime_rule_trace,
    explain_runtime_steps,
    explain_runtime_summary,
    explain_runtime_support,
    explain_runtime_timeline,
    explain_runtime_timeline_narrative,
    explain_runtime_timeline_summary,
    export_runtime_package,
    get_runtime_session_rules,
    get_runtime_view,
    get_runtime_session,
    get_runtime_session_schema,
    list_ephemeral_rules,
    list_runtime_candidates,
    list_runtime_views,
    list_runtime_conflicts,
    list_runtime_claims,
    open_runtime_session,
    project_runtime_view_facts,
    resolve_runtime_mapping,
    render_runtime_candidate_evidence_html,
    render_runtime_rule_trace_html,
    retract_runtime_fact,
    register_ephemeral_rule,
    run_runtime_rule,
    update_runtime_view,
    write_runtime_fact,
)
from factpy_kernel.service.auth import require_api_key

logger = logging.getLogger(__name__)

app = FastAPI(title="factpy-kernel service", version="v1")
AUTH_DEPENDENCIES = [Depends(require_api_key)]


@app.post("/v1/rules/validate", dependencies=AUTH_DEPENDENCIES)
def post_validate_rule(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return validate_rule(payload)


@app.post("/v1/rules/compile-preview", dependencies=AUTH_DEPENDENCIES)
def post_compile_rule_preview(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return compile_rule_preview(payload)


@app.get("/v1/profiles", dependencies=AUTH_DEPENDENCIES)
def get_profiles() -> dict[str, Any]:
    return list_profiles()


@app.post("/v1/runtime/sessions/open", dependencies=AUTH_DEPENDENCIES)
def post_open_runtime_session(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return open_runtime_session(payload)


@app.get("/v1/runtime/sessions/{session_id}", dependencies=AUTH_DEPENDENCIES)
def get_runtime_session_route(session_id: str) -> dict[str, Any]:
    return get_runtime_session(session_id)


@app.get("/v1/runtime/sessions/{session_id}/schema", dependencies=AUTH_DEPENDENCIES)
def get_runtime_session_schema_route(session_id: str) -> dict[str, Any]:
    return get_runtime_session_schema(session_id)


@app.delete("/v1/runtime/sessions/{session_id}", dependencies=AUTH_DEPENDENCIES)
def delete_runtime_session_route(session_id: str) -> dict[str, Any]:
    return close_runtime_session(session_id)


@app.post("/v1/runtime/sessions/{session_id}/writes/set", dependencies=AUTH_DEPENDENCIES)
def post_runtime_set(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return write_runtime_fact(session_id, payload, kind="set")


@app.post("/v1/runtime/sessions/{session_id}/writes/add", dependencies=AUTH_DEPENDENCIES)
def post_runtime_add(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return write_runtime_fact(session_id, payload, kind="add")


@app.post("/v1/runtime/sessions/{session_id}/writes/retract", dependencies=AUTH_DEPENDENCIES)
def post_runtime_retract(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return retract_runtime_fact(session_id, payload)


@app.get("/v1/runtime/sessions/{session_id}/claims", dependencies=AUTH_DEPENDENCIES)
def get_runtime_claims_route(
    session_id: str,
    pred_id: str | None = Query(default=None),
    e_ref: str | None = Query(default=None),
    include_meta: bool = Query(default=False),
    include_args: bool = Query(default=False),
    limit: int | None = Query(default=None),
) -> dict[str, Any]:
    return list_runtime_claims(
        session_id,
        pred_id=pred_id,
        e_ref=e_ref,
        include_meta=include_meta,
        include_args=include_args,
        limit=limit,
    )


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-fact", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_fact(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_fact(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_ref(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_ref(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-tree", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_tree(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_tree(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-summary", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_summary(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_summary(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-narrative", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_narrative(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_narrative(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-nl", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_nl(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_nl(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-support", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_support(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_support(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-rule-trace", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_rule_trace(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_rule_trace(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-timeline", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_timeline(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_timeline(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-timeline-summary", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_timeline_summary(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_timeline_summary(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-timeline-narrative", dependencies=AUTH_DEPENDENCIES)
def post_runtime_explain_timeline_narrative(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return explain_runtime_timeline_narrative(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/explain-steps", dependencies=AUTH_DEPENDENCIES)
async def _explain_steps(session_id: str, payload: dict[str, Any] = Body(...)):
    return explain_runtime_steps(session_id, payload)


@app.get("/v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}", dependencies=AUTH_DEPENDENCIES)
def get_runtime_candidate_evidence_page(session_id: str, candidate_id: str) -> HTMLResponse:
    return HTMLResponse(render_runtime_candidate_evidence_html(session_id, candidate_id))


@app.get("/v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}", dependencies=AUTH_DEPENDENCIES)
def get_runtime_rule_trace_page(session_id: str, rule_run_id: str) -> HTMLResponse:
    return HTMLResponse(render_runtime_rule_trace_html(session_id, rule_run_id))


@app.post("/v1/runtime/sessions/{session_id}/queries/conflicts", dependencies=AUTH_DEPENDENCIES)
def post_runtime_conflicts(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return list_runtime_conflicts(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/resolve-mapping", dependencies=AUTH_DEPENDENCIES)
def post_runtime_resolve_mapping(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return resolve_runtime_mapping(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/queries/view-facts", dependencies=AUTH_DEPENDENCIES)
def post_runtime_view_facts(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return project_runtime_view_facts(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/views/create", dependencies=AUTH_DEPENDENCIES)
def post_runtime_view_create(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return create_runtime_view(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/views/update", dependencies=AUTH_DEPENDENCIES)
def post_runtime_view_update(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return update_runtime_view(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/views/delete", dependencies=AUTH_DEPENDENCIES)
def post_runtime_view_delete(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return delete_runtime_view(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/views/get", dependencies=AUTH_DEPENDENCIES)
def post_runtime_view_get(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return get_runtime_view(session_id, payload)


@app.get("/v1/runtime/sessions/{session_id}/views", dependencies=AUTH_DEPENDENCIES)
def get_runtime_view_list(session_id: str) -> dict[str, Any]:
    return list_runtime_views(session_id)


@app.post("/v1/runtime/sessions/{session_id}/rules/run", dependencies=AUTH_DEPENDENCIES)
def post_runtime_run_rule(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return run_runtime_rule(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/derivations/evaluate", dependencies=AUTH_DEPENDENCIES)
def post_runtime_evaluate_derivation(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return evaluate_runtime_derivation(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/derivations/accept", dependencies=AUTH_DEPENDENCIES)
def post_runtime_accept_derivation(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return accept_runtime_derivation(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/ephemeral-rules", dependencies=AUTH_DEPENDENCIES)
def post_runtime_register_ephemeral_rule(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return register_ephemeral_rule(session_id, payload)


@app.get("/v1/runtime/sessions/{session_id}/ephemeral-rules", dependencies=AUTH_DEPENDENCIES)
def get_runtime_ephemeral_rules(session_id: str) -> dict[str, Any]:
    return list_ephemeral_rules(session_id)


@app.get("/v1/runtime/sessions/{session_id}/rules", dependencies=AUTH_DEPENDENCIES)
def get_runtime_session_rules_route(
    session_id: str,
    include_spec: bool = False,
) -> dict[str, Any]:
    return get_runtime_session_rules(session_id, include_spec=include_spec)


@app.get("/v1/runtime/sessions/{session_id}/candidates", dependencies=AUTH_DEPENDENCIES)
def get_runtime_candidates_route(
    session_id: str,
    pred_id: str | None = None,
) -> dict[str, Any]:
    return list_runtime_candidates(session_id, pred_id_filter=pred_id)


@app.delete("/v1/runtime/sessions/{session_id}/ephemeral-rules", dependencies=AUTH_DEPENDENCIES)
def delete_runtime_ephemeral_rules(session_id: str) -> dict[str, Any]:
    return clear_ephemeral_rules(session_id)


@app.post("/v1/runtime/sessions/{session_id}/packages/export", dependencies=AUTH_DEPENDENCIES)
def post_runtime_export_package(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return export_runtime_package(session_id, payload)


@app.post("/v1/registry/manifest", dependencies=AUTH_DEPENDENCIES)
def post_registry_manifest(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_manifest(payload)


@app.post("/v1/registry/schema/read", dependencies=AUTH_DEPENDENCIES)
def post_registry_schema(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_schema(payload)


@app.post("/v1/registry/assets/list", dependencies=AUTH_DEPENDENCIES)
def post_registry_assets(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return list_registry_assets(payload)


@app.post("/v1/registry/rules/read", dependencies=AUTH_DEPENDENCIES)
def post_registry_read_rule(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_rule(payload)


@app.post("/v1/registry/derivations/read", dependencies=AUTH_DEPENDENCIES)
def post_registry_read_derivation(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_derivation(payload)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_request: Any, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled service exception")
    return JSONResponse(
        status_code=200,
        content={
            "ok": False,
            "errors": [
                {
                    "kind": "runtime",
                    "path": "$",
                    "details": {"message": str(exc)},
                }
            ],
            "meta": {},
        },
    )
