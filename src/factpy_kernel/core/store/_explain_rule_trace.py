from __future__ import annotations

from typing import Any

from factpy_kernel.core.rules._trace import RuleTraceArtifact, rule_trace_artifact_to_dict


def render_rule_trace_artifact(artifact: RuleTraceArtifact) -> dict[str, Any]:
    # Currently delegates to rule_trace_artifact_to_dict for a JSON-friendly dict.
    # Add a dedicated display shape here if the canonical format diverges.
    return rule_trace_artifact_to_dict(artifact)


__all__ = ["render_rule_trace_artifact"]
