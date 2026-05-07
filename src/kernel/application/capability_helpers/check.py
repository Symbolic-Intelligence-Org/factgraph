"""Check capability helper builders."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.core.store._support import BindingItems

from kernel.application.protocol import (
    CheckRequest,
    CompiledDerivationPlan,
)

from ._binding import _normalize_helper_binding, _reject_sdk_origin
from .errors import CapabilityHelperError


def build_check_request(
    plan: CompiledDerivationPlan,
    binding: Mapping[str, Any] | BindingItems,
    *,
    engine: str = "native",
) -> CheckRequest:
    """Build a CheckRequest from application-canonical inputs."""

    _reject_sdk_origin(plan, path="plan")
    _reject_sdk_origin(binding, path="binding")
    _reject_sdk_origin(engine, path="engine")

    if not isinstance(plan, CompiledDerivationPlan):
        raise CapabilityHelperError("plan must be CompiledDerivationPlan")

    return CheckRequest(
        plan=plan,
        binding=_normalize_helper_binding(binding),
        engine=engine,  # type: ignore[arg-type]
    )


__all__ = [
    "build_check_request",
]
