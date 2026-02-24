from __future__ import annotations

import logging
from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from factpy_kernel.facade.rules_v1 import compile_rule_preview, list_profiles, validate_rule

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
