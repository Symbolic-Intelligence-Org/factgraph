# Task Blueprint Audit: Artifact Sidecar Store

- Blueprint: [2026-03-17_artifact-sidecar-store.md](./2026-03-17_artifact-sidecar-store.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened the online-durable-readback slice after audit/export completeness had already been shipped. |
| 2026-03-17 | scoped | Scope frozen | Locked the first sidecar slice to constructor-injected, file-backed storage with `_lookup_*` fallback and fail-closed durable writes. |
| 2026-03-17 | scoped | False implemented state rolled back | Gap audit found the prior `implemented` / archived state unsupported by code, tests, and module docs; the child blueprint was restored to `active/` and its outcome claims were cleared. |
| 2026-03-17 | implementing | Row round-trip helpers landed | Added `support_artifact_from_dict(...)` and `rule_trace_artifact_from_dict(...)`, locked the opaque `original_where` / `rewritten_where` behavior in code, and verified the new helper semantics with focused plus full contract tests. |
| 2026-03-17 | implementing | File-backed carrier landed | Added `_artifact_sidecar.py` with `ArtifactSidecar` / `FileArtifactSidecar`, plus canonical `rule_trace_artifact_bytes(...)` support and focused sidecar tests covering read-miss, no-op rewrites, disk collisions, and `rule_run_id` path guards. |
| 2026-03-17 | implementing | Store integration landed | Wired `Store.__init__(..., artifact_sidecar=...)`, first-write durable persistence in `_remember_*`, miss fallback + direct dict rehydrate in `_lookup_*`, and propagation of sidecar read errors; verified with focused cross-store and integrity tests plus the full phase-3 contract suite. |
| 2026-03-17 | implemented | Runtime/SDK/docs sync completed | Added runtime `artifact_store_root`, SDK `artifact_store_root`, cross-session/cross-instance explain readback tests, and synchronized core/service/SDK docs to describe opt-in durable readback. |
| 2026-03-17 | implemented | Archive ready | Acceptance is now fully satisfied after code, tests, and module docs were brought back into alignment. |

## Decision Notes

- 2026-03-17: Sidecar fallback should live in `_lookup_support_artifact(...)` / `_lookup_rule_trace_artifact(...)`, not in `explain_*`, so artifact resolution remains centralized and rehydration is transparent.
- 2026-03-17: Sidecar should be attached via `Store.__init__(..., artifact_sidecar=...)` rather than a post-construction setter to avoid partial-lifecycle durability semantics.
- 2026-03-17: `Store.__init__` should accept `artifact_sidecar` as a keyword-only optional dependency alongside `engine_evaluator`, defaulting to `None`.
- 2026-03-17: When sidecar is configured, capture-time durable writes should fail closed; silent ignore or warning-only handling would create false durability guarantees.
- 2026-03-17: `Store._remember_*` should only call sidecar writes on the first in-memory registration (`existing is None`); repeated equal remembers should remain pure in-memory no-ops.
- 2026-03-17: Sidecar-hit rehydration in `_lookup_*` should write directly back into the in-memory artifact dicts rather than routing through `_remember_*`, to avoid redundant durable I/O and lifecycle mixing.
- 2026-03-17: Sidecar read failures inside `_lookup_*` should propagate as integrity errors rather than being downgraded to cache misses.
- 2026-03-17: `artifact_store_root` should use `str | None` on runtime/SDK public surfaces, matching `ledger_path`, while `FileArtifactSidecar` remains responsible for internal `Path` normalization.
- 2026-03-17: Runtime session open should validate `artifact_store_root` via `_optional_str(..., path=\"$.artifact_store_root\")` and continue to defer directory creation until the first durable write.
- 2026-03-17: `SDKStore.__init__(...)` and `SDKStore.from_schema_classes(...)` should both accept `artifact_store_root`; when a fully constructed `store` is already supplied, the root parameter is ignored rather than rejected.
- 2026-03-17: `_session_to_dict(...)` should not echo `artifact_store_root`; the root is treated as configuration input, not session state.
- 2026-03-17: The first sidecar slice should reuse the existing audit/export row shape for artifact payloads instead of inventing a second durable codec.
- 2026-03-17: The `ArtifactSidecar` protocol should expose only four operations: `write_support`, `write_rule_trace`, `read_support`, and `read_rule_trace`; read miss returns `None`, while same-key different-payload writes must raise collision errors.
- 2026-03-17: `FileArtifactSidecar` should accept `sidecar_root: Path | str`, normalize it to `Path`, map `support_digest` by stripping the `sha256:` prefix into `support/sha256/<hex>.json`, and store `rule_run_id` directly under `rule_trace/<rule_run_id>.json`.
- 2026-03-17: File-backed writes should use temp file + `os.replace()` to guarantee atomic single-file persistence.
- 2026-03-17: Disk collision errors should use `ValueError` and keep message shape parallel to the in-memory `_remember_*` collision errors, with explicit `on disk` wording plus the offending key.
- 2026-03-17: Disk collision detection should compare deterministic serialized bytes, not parsed dicts or rehydrated dataclasses.
- 2026-03-17: `FileArtifactSidecar` should perform check-then-write: existing target files are compared first and either no-op or raise; only absent targets proceed to temp-write + replace.
- 2026-03-17: Temp files should be created via `tempfile.mkstemp(dir=target.parent, suffix=".tmp")`, cleaned up in `finally`, and kept in the destination directory so `os.replace()` remains atomic.
- 2026-03-17: Although current `rule_run_id` values come from `uuid4().hex`, the file-backed carrier should still reject `/`, `\\`, and null-byte characters as a minimal path-safety guard.
- 2026-03-17: v1 sidecar should not introduce explicit thread/process locks; it guarantees single-file integrity and non-racy collision checks, but it is not a general multi-writer arbitration protocol for concurrent first-write races on the same key.
- 2026-03-17: `ArtifactSidecar` / `FileArtifactSidecar` should stay out of `factpy_kernel.core.store.__init__`; the first slice keeps them as underscore-module imports rather than widening the stable facade.
- 2026-03-17: Artifact rehydration should be implemented as module-level `*_from_dict(...)` helpers in `_support.py` and `_trace.py`, matching the existing `*_to_dict(...)` style rather than embedding codec logic in the sidecar carrier.
- 2026-03-17: Round-trip fidelity is only required for schema-owned structural containers plus `bytes` lifting; `Any`-typed leaf values may come back as JSON-native values, so tuple-valued leaves becoming lists is acceptable in the first slice.
- 2026-03-17: `from_dict(...)` must construct dataclasses normally and rely on `__post_init__` validators; validator failures are treated as stored-row integrity failures.
- 2026-03-17: `from_dict(...)` should ignore unknown keys so the same helper can accept both bare artifact payloads and sidecar/export rows with envelope fields such as `support_digest` or `rule_run_id`.
- 2026-03-17: `original_where` and `rewritten_where` should remain fully opaque JSON-native payloads during rehydration; even nested `{"__bytes_hex__": ...}` objects stay as-is rather than being converted back to bytes.
- 2026-03-17: Automatic retention / GC is explicitly deferred; the initial slice focuses only on online durable readback continuity.
- 2026-03-17: Runtime and SDK surfaces should expose the feature as an explicit `artifact_store_root` opt-in, rather than turning durable explainability on by default.
- 2026-03-17: A child blueprint must not remain archived once its `implemented` state has been invalidated; the correct recovery action is to restore it to `active/` with a truthful `scoped` status.
