from __future__ import annotations

import logging
from typing import Any

from fastapi import Body, FastAPI, Query
from fastapi.responses import JSONResponse

from factpy_kernel.service.registry_v1 import (
    list_registry_assets,
    read_registry_derivation,
    read_registry_manifest,
    read_registry_rule,
    read_registry_schema,
)
from factpy_kernel.service.rules_v1 import compile_rule_preview, list_profiles, validate_rule
from factpy_kernel.service.runtime_v1 import (
    close_runtime_session,
    export_runtime_package,
    get_runtime_session,
    list_runtime_claims,
    open_runtime_session,
    retract_runtime_fact,
    run_runtime_rule,
    write_runtime_fact,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="factpy-kernel service", version="v1")


@app.post("/v1/rules/validate")
def post_validate_rule(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return validate_rule(payload)


@app.post("/v1/rules/compile-preview")
def post_compile_rule_preview(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return compile_rule_preview(payload)


@app.get("/v1/profiles")
def get_profiles() -> dict[str, Any]:
    return list_profiles()


@app.post("/v1/runtime/sessions/open")
def post_open_runtime_session(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return open_runtime_session(payload)


@app.get("/v1/runtime/sessions/{session_id}")
def get_runtime_session_route(session_id: str) -> dict[str, Any]:
    return get_runtime_session(session_id)


@app.delete("/v1/runtime/sessions/{session_id}")
def delete_runtime_session_route(session_id: str) -> dict[str, Any]:
    return close_runtime_session(session_id)


@app.post("/v1/runtime/sessions/{session_id}/writes/set")
def post_runtime_set(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return write_runtime_fact(session_id, payload, kind="set")


@app.post("/v1/runtime/sessions/{session_id}/writes/add")
def post_runtime_add(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return write_runtime_fact(session_id, payload, kind="add")


@app.post("/v1/runtime/sessions/{session_id}/writes/retract")
def post_runtime_retract(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return retract_runtime_fact(session_id, payload)


@app.get("/v1/runtime/sessions/{session_id}/claims")
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


@app.post("/v1/runtime/sessions/{session_id}/rules/run")
def post_runtime_run_rule(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return run_runtime_rule(session_id, payload)


@app.post("/v1/runtime/sessions/{session_id}/packages/export")
def post_runtime_export_package(session_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return export_runtime_package(session_id, payload)


@app.post("/v1/registry/manifest")
def post_registry_manifest(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_manifest(payload)


@app.post("/v1/registry/schema/read")
def post_registry_schema(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_schema(payload)


@app.post("/v1/registry/assets/list")
def post_registry_assets(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return list_registry_assets(payload)


@app.post("/v1/registry/rules/read")
def post_registry_read_rule(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return read_registry_rule(payload)


@app.post("/v1/registry/derivations/read")
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
