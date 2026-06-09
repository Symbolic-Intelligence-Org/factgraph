from __future__ import annotations

from .evidence_tree import (
    Aggregate,
    AtomForm,
    BoundVar,
    Builtin,
    Compare,
    Const,
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidenceProbeResult,
    EvidenceRule,
    EvidenceTimeline,
    EvidenceTree,
    Fact,
    Fails,
    Holds,
    NotReached,
    PortRef,
    Source,
    Verdict,
)
__all__ = [
    "Aggregate",
    "AtomForm",
    "BoundVar",
    "Builtin",
    "Compare",
    "Const",
    "EvidenceAtom",
    "EvidenceGraph",
    "EvidenceJoin",
    "EvidenceProbeResult",
    "EvidenceRule",
    "EvidenceTimeline",
    "EvidenceTree",
    "Fact",
    "Fails",
    "Holds",
    "NotReached",
    "PortRef",
    "ProbeEnv",
    "Source",
    "Verdict",
    "probe_native",
]


def __getattr__(name: str):
    if name in {"ProbeEnv", "probe_native"}:
        from .prober import ProbeEnv, probe_native

        return {"ProbeEnv": ProbeEnv, "probe_native": probe_native}[name]
    raise AttributeError(name)
