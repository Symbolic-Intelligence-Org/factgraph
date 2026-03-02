from __future__ import annotations


class SDKDSLError(Exception):
    def __init__(self, message: str, *, code: str | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
