"""Frontier capability helper builders."""

from __future__ import annotations

from typing import Any

from kernel.core.store import Store
from kernel.core.view.projector import project_view_facts

from .errors import CapabilityHelperError


def build_frontier_view_facts(store: Store) -> dict[str, list[tuple[Any, ...]]]:
    """Project a Store into the view_facts shape expected by native frontier."""

    if not isinstance(store, Store):
        raise CapabilityHelperError("store must be Store")
    return project_view_facts(store.ledger, store.schema_ir)



__all__ = [
    "build_frontier_view_facts",
]
