# Audit Log: Architectural Decisions v2

| Date | Status | Event | Notes |
|------|--------|-------|-------|
| 2026-03-22 | scoped | Blueprint created | Consolidated from talk.md (old traceability blueprint) + session design doc + engine provenance research + ECSS domain validation. Supersedes 3 archived parent blueprints. |
| 2026-03-26 | scoped | ADR-13: ProofNode → provenance envelope | PyReason spike proved proof tree (Souffle) and event log (PyReason) are fundamentally different shapes. §5.4 rewritten: unified `ProofNode` tree withdrawn, replaced by per-candidate engine-specific `ProvenanceEnvelope` with `engine` + `payload_type` dispatch. Frozen decision #4 updated. §6.1 updated with PyReason research. §6.2 updated with current progress (Souffle complete, PyReason spike done, ProbLog not started). |
