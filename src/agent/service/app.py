"""Standalone FastAPI app for agent extraction HTTP surface.

可独立部署:`uvicorn agent.service.app:app`
也可被外层 mount(取决于部署形态)。

依赖方向:agent.service → service(top-level package,不是 factgraph.service)
                       → factgraph(传递依赖经 service)
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from fastapi import Depends, FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from agent.service.extraction_v1 import extract_document_endpoint as _extract_handler
from service._common import error_response
from service.auth import require_api_key

logger = logging.getLogger(__name__)

app = FastAPI(title="agent-extraction service", version="v1")
AUTH_DEPENDENCIES = [Depends(require_api_key)]


@app.post("/v1/extraction/documents", dependencies=AUTH_DEPENDENCIES)
async def post_extract_document(
    file: UploadFile = File(...),
    options: str = Form(...),
):
    try:
        options_dict = _json.loads(options)
    except (ValueError, TypeError) as exc:
        return JSONResponse(
            status_code=422,
            content=error_response(
                [
                    {
                        "kind": "validation",
                        "path": "options",
                        "details": {"message": f"options is not valid JSON: {exc}"},
                    }
                ]
            ),
        )
    file_bytes = await file.read()
    return _extract_handler(
        file_bytes=file_bytes,
        doc_name=file.filename or "unknown",
        options=options_dict,
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_request: Any, exc: Exception) -> JSONResponse:
    """Mirror service.app_v1 envelope contract for unhandled exceptions."""
    logger.exception("Unhandled agent.service exception")
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
