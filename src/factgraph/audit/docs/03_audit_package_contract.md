# Audit Package Contract

- Scope: `src/factgraph/audit`
- Last updated: 2026-05-06
- Owner: `factgraph.audit` reader / query / DTO surface

`factgraph.audit` consumes exported audit packages. It does not export packages, render the full static site, query live runtime state, or own domain-specific ECSS row semantics.

## 1. Package Root

An audit package is a directory with:

- `manifest.json`
- `manifest.package_kind == "audit"`
- `manifest.paths.audit_files`, an object mapping logical audit file names to package-relative paths
- optional `outputs/run_manifest.json`

`load_audit_package(package_dir)` validates this shape and returns `AuditPackageData`.

## 2. Required Audit Files

The reader currently requires these `manifest.paths.audit_files` entries:

| Key | Current path convention | Consumer role |
|---|---|---|
| `run_ledger` | `audit/run_ledger.jsonl` | run list and run detail DTOs |
| `candidate_ledger` | `audit/candidate_ledger.jsonl` | candidate lists, evidence tree lookup, provenance coverage |
| `accept_write_ledger` | `audit/accept_write_ledger.jsonl` | accepted write detail and run/decision linkage |
| `accept_failed` | `audit/accept_failed.jsonl` | failure list and timeline entries |
| `decision_log` | `audit/decision_log.jsonl` | decision detail and run timeline |
| `mapping_resolution` | `audit/mapping_resolution.json` | predicate mapping inspection |

Missing required files are hard read errors. JSONL rows must be JSON objects.

## 3. Optional Audit Files

Optional files are backward-compatible. If absent from the manifest or missing on disk, the reader returns an empty list or empty mapping.

| Key | Row shape | Reader field |
|---|---|---|
| `support_artifacts` | `ProofReceipt` JSON-friendly row keyed by `support_digest` | `support_artifacts` |
| `rule_trace_artifacts` | `RuleTraceArtifact` JSON-friendly row keyed by `rule_run_id` | `rule_trace_artifacts` |
| `certainty_summaries` | `{candidate_id, certainty_summary}` | `certainty_summaries` |
| `provenance_trees` | `{candidate_id, provenance_tree}` | `provenance_trees` |
| `provenance_statuses` | `{candidate_id, status, engine?, truncated?, reason?}` | `provenance_statuses` |
| `evidence_graphs` | `{candidate_id, evidence_graph}` | `evidence_graphs` |
| `assertion_annotations` | annotation rows for assertion detail panels | `assertion_annotations` |
| `provenance_timelines` | `{candidate_id, provenance_timeline}` | `provenance_timelines` |
| `round_events` | `RoundEvent` rows keyed by `(round_id, sequence)` | `round_events` / `round_event_warnings` |

`evidence_graphs` is stricter than most optional files: duplicate `candidate_id` rows are read errors because they would make the durable graph lookup ambiguous.

### 3.1 Optional Round Events

`round_events` uses the current path convention `audit/round_events.jsonl`. It is optional: old audit packages without the manifest key or file load with `AuditPackageData.round_events == ()`.

Each row is a JSON object:

| Field | Type | Notes |
|---|---|---|
| `round_id` | string | Caller-supplied opaque round id. |
| `sequence` | integer | Primary per-round order key;starts at 0. |
| `event_ts` | integer | Nanosecond timestamp;secondary metadata,not primary ordering. |
| `kind` | string | `round_started`, `check_result`, `diagnose_result`, `fact_overlay_result`, `why_not_result`, `proof_frame_result`, or `round_finalized` in the first slice. |
| `schema_version` | string | Starts at `"1.0"`. |
| `payload` | object | Kind-specific JSON projection;never a raw dataclass blob or `repr`. |

Lifecycle:

- sequence 0 is `round_started`
- capability events follow
- `round_finalized` is last and carries `event_count` plus `kind_counts`

The reader is intentionally lenient for this optional file:

- malformed row -> skipped, `ROUND_EVENT_MALFORMED` in `round_event_warnings`
- duplicate `(round_id, sequence)` -> first row wins, duplicate skipped, `ROUND_EVENT_DUPLICATE` warning
- unknown future kind -> preserved as a `RoundEvent`
- sequence gaps -> preserved and surfaced through `RoundSummary.sequence_gaps`
- missing `round_finalized` -> `RoundSummary.is_finalized == False`

The write-side helper `finalize_round(...)` writes `round_events.jsonl` via tempfile + `os.replace` and updates the manifest with `paths.audit_files.round_events`.

## 4. Query-Derived Surfaces

The following are not separate durable package files today. They are derived by `AuditQuery` / DTO helpers from package files:

- `rule_run_summary`
- `rule_run_narrative`
- `candidate_evidence_tree`
- `candidate_evidence_tree_summary`
- `candidate_evidence_tree_narrative`
- provenance coverage summary
- authoring apply run summary/detail
- round summary and round event query results
- ProofFrame diff over finalized `proof_frame_result` rows

This distinction matters for compatibility: old packages can still load when optional durable files are absent, but derived surfaces may return empty results or raise a query/DTO error if their required source carrier is unavailable.

Batch 8 public-surface note:these query-derived surfaces are `factgraph.audit` advanced importable APIs. They are part of the factgraph audit reader/query layer,not SDK product facade methods and not service routes.

### 4.1 ProofFrame Diff

`AuditQuery.diff_proof_frames(round_a, round_b, include_partial=False, include_unchanged=False)` is a query-derived surface over `round_events`.

It does not add a new package file. It consumes only `proof_frame_result` events:

| Carrier | Field used |
|---|---|
| Frame identity | `payload.request.support_digest` + `payload.result.binding_items` |
| Frame status | `payload.result.status` |
| Atom identity | `payload.result.atom_verdicts[].condition_key` |
| Atom verdict | `payload.result.atom_verdicts[].verdict` |

Important boundaries:

- `affected_action_indices` are intentionally not compared across rounds.
- Only the same `support_digest` is compared at atom level; condition keys from different support artifacts are separate frames.
- `future:proof_frame_result` rows are skipped with `DIFF_FUTURE_KIND_SKIPPED`.
- partial rounds are rejected by default; `include_partial=True` emits `DIFF_INCLUDES_PARTIAL_ROUND`.
- frames with empty `atom_verdicts` are marked `rule_refs_unsupported` and do not produce per-atom deltas.
- L5 cross-run aggregation by module is deferred and has no durable index in this slice.

## 5. Domain-Specific Compliance

`AuditQuery.list_compliance_matrix(...)` is a compatibility convenience query over an audit package, but ECSS row assembly is owned by `domains.ecss.compliance`.

In the factgraph-only v0.1 wheel, `domains.ecss` is not part of the installed package set. Calling this convenience without the optional domain package raises `AuditOptionalDomainError` with an actionable message. Kernel consumers should treat this surface as domain-backed and optional, not as a guaranteed factgraph-only contract.

The audit layer:

- loads assertion facts and metadata
- exposes the query entrypoint
- wraps domain errors as `AuditQueryError`
- reports missing optional domain ownership as `AuditOptionalDomainError`

The ECSS domain layer:

- owns ECSS compliance predicate constants through `domains.ecss.vcd`
- owns requirement/compliance row assembly in `domains.ecss.compliance`
- defines ECSS-specific validation rules such as required `ingested_at` metadata

## 6. Minimum Provenance Mapping

The current package does not claim full PROV conformance. The minimum responsibility mapping is:

| Role | Current carriers |
|---|---|
| Entity | assertion rows, candidate rows, exported reports/static pages, `EvidenceGraph` nodes |
| Activity | run ledger rows, decision log rows, accept write rows, authoring apply events, package export |
| Agent | metadata such as `approved_by`, service/operator identifiers, authoring apply actors when present |
| Bundle | audit package root, run bundle from `AuditQuery.get_run_bundle(...)`, rendered static site root |
| Provenance of provenance | `provenance_statuses`, `evidence_graphs`, `provenance_timelines`, `support_artifacts`, `rule_trace_artifacts` |

Future provenance work should add fields or mappings explicitly rather than relying on page text or ad hoc payload conventions.

## 7. Ownership Boundary

- `factgraph.audit`: package read/query/DTO/evidence graph consumer contracts
- `service.static_ui`: full static HTML site rendering and rendered site manifest/index contracts
- `domains.ecss.compliance`: ECSS compliance row semantics
- `adapters` / runtime service: package export and optional provenance materialization
