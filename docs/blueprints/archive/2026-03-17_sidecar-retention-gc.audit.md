# Task Blueprint Audit: Sidecar Retention And GC

- Blueprint: [2026-03-17_sidecar-retention-gc.md](./2026-03-17_sidecar-retention-gc.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened the post-sidecar retention/GC slice after durable readback had already shipped and the remaining pressure shifted to artifact lifecycle governance. |
| 2026-03-17 | scoped | Scope frozen | Locked sidecar-adjacent `.meta.json` metadata, asymmetric retention, `gc_rule_trace(...)` as a concrete maintenance method, and the first-pass GC result/validation contract. |
| 2026-03-17 | implementing | Carrier GC implementation started | Began `_artifact_sidecar.py` changes for sidecar-owned metadata, age-only rule-trace TTL GC, structured GC reporting, and focused contract tests plus core docs sync. |
| 2026-03-17 | implemented | Carrier GC shipped | Added `.meta.json` retention metadata, `GCResult`, `gc_rule_trace(...)`, focused GC tests, and synchronized core docs. |
| 2026-03-17 | implemented | Archive ready | Acceptance is satisfied after code, tests, and module docs were aligned. |

## Decision Notes

- 2026-03-17: The retention discussion should not be prematurely collapsed to `mtime-only`; the blueprint must compare OS-owned time metadata against application-owned metadata-plane candidates before scope freeze.
- 2026-03-17: `captured_at_ns` is a first-class candidate because filesystem `mtime` has reset/rename/testability weaknesses that are structural rather than incidental.
- 2026-03-17: `source_session_id` may be discussed as provenance metadata, but it should not be treated as a GC ownership key, especially for content-addressed `SupportArtifact`.
- 2026-03-17: Rainbird comparison is adopted as a boundary rule here: interaction/session log belongs to a separate delivery plane and should not be injected into evidence payload canonical bytes just for retention convenience.
- 2026-03-17: Scope remains intentionally open at `draft` until the §5 metadata-plane comparison and §7 acceptance criteria are tightened.
- 2026-03-17: The first retention slice chooses sidecar-adjacent `.meta.json` files with sidecar-owned `captured_at_ns`, rather than `mtime-only`, provenance-enriched metadata, or a shared journal/index.
- 2026-03-17: `SupportArtifact` remains write-and-retain in the first slice; only `RuleTraceArtifact` participates in automatic TTL GC.
- 2026-03-17: `captured_at_ns` should come from `FileArtifactSidecar` constructor-level clock injection rather than expanding `ArtifactSidecar` method signatures with call-site timestamp parameters.
- 2026-03-17: `_write_bytes(...)` should return a first-write boolean so metadata writes can occur only after a new payload commit, without extra pre-check I/O.
- 2026-03-17: GC should live as a concrete `FileArtifactSidecar` maintenance method, not as part of the minimal `ArtifactSidecar` protocol.
- 2026-03-17: GC should clean orphaned metadata files with warnings, but skip orphaned payload files that lack metadata because they cannot be aged safely.
- 2026-03-17: The first automatic rule-trace retention policy is age-only TTL driven by caller-supplied `ttl_ns`; count-based and rule-grouped retention remain deferred.
- 2026-03-17: `failed_keys` in the GC report should include both the durable key and the concrete filesystem path, since operator remediation is path-oriented.
- 2026-03-17: `ttl_ns <= 0` should raise `ValueError` instead of being treated as “delete everything”; destructive maintenance shortcuts must stay explicit.
- 2026-03-17: The GC report should include `total_scanned` because deleted/failed/skipped buckets are not sufficient to reconstruct pass coverage.
- 2026-03-17: `gc_rule_trace(...)` should snapshot `now_ns` once at method entry so a single GC pass remains deterministic and easy to test.
