from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration loaded from environment."""

    allowed_keys: tuple[str, ...]
    disabled: bool = False

    @classmethod
    def from_env(cls) -> "AuthConfig":
        raw = os.environ.get("FACTPY_KERNEL_API_KEYS", "")
        allowed_keys = tuple(k.strip() for k in raw.split(",") if k.strip())
        disabled = os.environ.get("FACTPY_KERNEL_AUTH_DISABLED", "").lower() == "true"
        return cls(allowed_keys=allowed_keys, disabled=disabled)

    @property
    def enabled(self) -> bool:
        return not self.disabled

    @property
    def has_keys(self) -> bool:
        return bool(self.allowed_keys)

    def verify(self, provided_key: str | None) -> bool:
        if not provided_key:
            return False
        for allowed in self.allowed_keys:
            if hmac.compare_digest(provided_key, allowed):
                return True
        return False


def load_auth_config() -> AuthConfig:
    """Return the current auth config from environment variables."""

    return AuthConfig.from_env()


async def require_api_key(
    x_factpy_api_key: Annotated[str | None, Header(alias="X-FactPy-API-Key")] = None,
) -> None:
    """
    FastAPI dependency for v1 service routes.

    If auth is enabled and no keys are configured, fail closed with 503.
    Missing/invalid keys return 401.
    """

    config = load_auth_config()
    if not config.enabled:
        return

    if not config.has_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication not configured",
        )

    if not config.verify(x_factpy_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "FactPyAPIKey"},
        )
