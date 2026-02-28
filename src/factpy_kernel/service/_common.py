from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceFacadeError(Exception):
    message: str
    kind: str
    path: str
    details: dict[str, Any]

    def __str__(self) -> str:
        return self.message


def facade_error(
    message: str,
    *,
    kind: str,
    path: str,
    details: dict[str, Any] | None = None,
) -> ServiceFacadeError:
    return ServiceFacadeError(
        message=message,
        kind=kind,
        path=path,
        details=dict(details or {}),
    )


def ok_response(*, meta: dict[str, Any] | None = None, **payload: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "meta": dict(meta or {}),
    }
    out.update(payload)
    return out


def error_response(errors: list[dict[str, Any]], *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": list(errors),
        "meta": dict(meta or {}),
    }


def exception_to_error(exc: Exception) -> dict[str, Any]:
    kind = getattr(exc, "kind", None)
    path = getattr(exc, "path", None)
    details = getattr(exc, "details", None)

    if not isinstance(kind, str) or not kind:
        kind = "runtime"
    if not isinstance(path, str) or not path:
        path = "$"
    if not isinstance(details, dict):
        details = {"message": str(exc)}
    else:
        details = dict(details)
        details.setdefault("message", str(exc))

    return {
        "kind": kind,
        "path": path,
        "details": details,
    }
