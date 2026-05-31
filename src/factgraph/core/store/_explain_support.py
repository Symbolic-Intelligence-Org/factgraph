from __future__ import annotations

from typing import Any

from factgraph.core.store._support import ProofReceipt, support_artifact_to_dict


def render_support_artifact(artifact: ProofReceipt) -> dict[str, Any]:
    # Currently delegates to support_artifact_to_dict for a JSON-friendly dict.
    # binding is list-of-pairs: [["$var", value], ...].
    # Add a dedicated display shape here if the canonical format diverges.
    return support_artifact_to_dict(artifact)


__all__ = ["render_support_artifact"]
