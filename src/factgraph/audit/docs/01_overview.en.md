# Audit Module Overview (factgraph)

- Scope: `src/factgraph/audit`
- Last updated: 2026-05-06
- Audience: developers consuming an audit package, running offline audit queries, or constructing audit DTOs

## 1. Module Responsibilities

> **Boundary — v0.1 factgraph-only wheel**
>
> This document describes how `factgraph.audit` integrates with downstream consumers. The following modules are referenced below but are **not part of the v0.1 factgraph-only wheel**:
>
> - `service.static_ui` — full audit static-site rendering (monorepo / future deliverable)
> - `domains.ecss.compliance` — ECSS row assembly + compliance matrix (optional domain bundle)
> - `domains.ecss.vcd` — ECSS VCD predicate preset (optional domain bundle)
>
> Calling these modules directly from a factgraph-only install raises `ModuleNotFoundError`. `AuditQuery.list_compliance_matrix(...)` raises `AuditOptionalDomainError` to give an actionable signal instead of letting users hit a bare import failure.

`audit` is the **audit-consumption layer**. It reads exported audit packages and exposes query, DTO, and evidence-graph consumption capabilities.

It is responsible for:

- audit package reading
- run / candidate / materialization / decision / failure queries
- requirement-scoped compliance-matrix queries
- authoring apply-event queries
- durable round event-log reading and querying
- audit DTO construction
- a shared in-memory representation layer for cross-engine explainability

It is not responsible for:

- live runtime fact queries
- registry asset versioning
- package export
- engine-native provenance generation
- full static-site rendering (owned by `service.static_ui`)
- ECSS compliance row assembly semantics (owned by `domains.ecss.compliance`)

## 2. Current Public Entry

- `load_audit_package(...)`
  - reads data from an audit package directory
- `AuditQuery`
  - structured query entrypoint
  - currently also offers offline rule-trace artifact queries
  - currently also offers offline witness-bearing candidate evidence-tree queries
  - currently also offers offline round event-log queries
- `start_round(...)` / `record_round_event(...)` / `finalize_round(...)`
  - external recorder API; the caller records produced results outside of capability runtimes
  - writes the optional `audit/round_events.jsonl` inside the audit package
  - buffered by default; `finalize_round(...)` lands atomically via tempfile + `os.replace`
- `load_authoring_apply_events(...)`
  - reads the authoring apply event log; workspace registry inputs read
    `db/audit/authoring_apply_events.jsonl` with legacy
    `registry/authoring_apply_events.jsonl` fallback, while audit package
    inputs keep the historical package-local path
- `EvidenceGraph(paths=...)`
  - the audit-layer unified explainability DTO, re-exported from
    `factgraph.application.explain`
  - tree and timeline paths for native, Souffle, ProbLog, and PyReason evidence
  - `evidence_graphs.jsonl` export in audit package (Souffle / PyReason / ProbLog)
  - `AuditQuery.get_candidate_evidence_graph()` query-layer access
  - the static candidate evidence page renders durable evidence with adapter fallbacks

Backing modules:

- `reader.py`
- `query.py`
- `dto.py`
- `authoring_events.py`
- `assertions.py`
- `evidence_graph.py`
- `round_events.py`

Batch 8 public-surface note: `factgraph.audit` is an **advanced importable** audit consumer surface in the factgraph package. Round event recording, round-event queries, and ProofFrame diff are documented audit/query APIs, but they are not mirrored as SDK facade methods in v0.1. Service / static-site delivery remains outside the factgraph-only public package.

Related contract documents:

- `src/factgraph/audit/docs/03_audit_package_contract.md`
  - audit package files, reader / query derived surfaces, minimum provenance carrier mapping
- delivery-layer static site contract
  - rendered static site, `site_manifest.json`, `ui_index.json` delivery contract

## 3. Typical Workflows

### 3.1 Reading an audit package

1. First export a `package_kind="audit"` package via the adapter / runtime
2. Call `load_audit_package(package_dir)`
3. Receive an `AuditPackageData`

### 3.2 Structured queries

1. Build an `AuditQuery(package)`
2. Call:
   - `list_runs()`
   - `get_run_bundle(run_id)`
   - `list_candidates(...)`
   - `get_candidate_evidence_tree(candidate_id)`
   - `get_candidate_certainty_summary(candidate_id)`
   - `list_decisions(...)`
   - `list_failures(...)`
   - `list_compliance_matrix(...)` (ECSS / domain-backed optional convenience)
   - `list_rule_traces(...)`
   - `get_rule_trace(rule_run_id)`
   - `list_rule_trace_summaries(...)`
   - `get_rule_trace_summary(rule_run_id)`
   - `get_rule_trace_narrative(rule_run_id)`
   - `get_mapping_resolution(...)`
   - `list_authoring_apply_events(...)`
   - `list_rounds()`
   - `list_round_events(round_id, kind=None)`
   - `get_round_event(round_id, sequence)`
   - `get_round_summary(round_id)`
   - `list_round_event_warnings()`
   - `diff_proof_frames(round_a, round_b, include_partial=False, include_unchanged=False)`

### 3.3 Round Event Log

The round event log is an optional audit-package file introduced in Batch 6. It persists a per-round summary of application capability call results. It does not replay capabilities and does not change Store / ledger semantics.

The current first slice covers:

- lifecycle: `round_started`, `round_finalized`
- capability: `check_result`, `diagnose_result`, `fact_overlay_result`, `why_not_result`, `proof_frame_result`

Explicitly deferred:

- Frontier projection event family
- 5a / 5b / 5c rule action result event family
- Batch 7 diff / cross-run aggregation index

The recorder uses the caller-supplied `round_id` plus a per-round monotonic `sequence`. Capability runtimes do not import `factgraph.audit`; the caller explicitly records events after each capability returns.

A passed Check projection persists its receipt envelope's
`as_of_event_seq=[tx_seq, op_ordinal]`. The proof body and `support_digest` stay
unchanged; audit/explain code may use `receipt_as_of_event_seq(...)` and
`effective_meta_at_receipt(...)` for fail-closed historical meta replay.

The reader is intentionally lenient on `round_events.jsonl`:

- malformed row: skipped, with a `ROUND_EVENT_MALFORMED` warning recorded
- duplicate `(round_id, sequence)`: first row wins, with a `ROUND_EVENT_DUPLICATE` warning recorded
- unknown future kind: preserved with raw payload, no warning
- missing `round_finalized`: `RoundSummary.is_finalized=False`

### 3.4 ProofFrame Diff

Batch 7 added a read-only `ProofFrame` diff at the audit query layer:

- Input: two explicit round ids
- Source data: Batch 6 `proof_frame_result` rows
- Frame identity: `request.support_digest + result.binding_items`
- Atom identity: `condition_key` within the same `support_digest`
- Output: `ProofFrameDiff` / `FrameDelta` / `AtomDelta` dataclasses

Default behavior:

- Only finalized rounds are compared; partial rounds raise `AuditQueryError`
- `include_partial=True` allows partial rounds and returns a `DIFF_INCLUDES_PARTIAL_ROUND` warning
- `future:proof_frame_result` rows are skipped, with a `DIFF_FUTURE_KIND_SKIPPED` warning
- Unchanged frames are omitted by default; `include_unchanged=True` includes them
- RuleRef / unsupported-equivalent ProofFrames (`atom_verdicts=[]`) are marked `rule_refs_unsupported` and produce no per-atom delta

This diff does not persist a new index, does not re-run capabilities, does not compare cross-round `affected_action_indices`, and does not implement Batch 7 L5 cross-run module aggregation.

### 3.5 Requirement / Compliance Matrix

When an audit package contains requirement-scoped assertions, `AuditQuery` exposes offline ECSS VCD / compliance-matrix query entrypoints. Row assembly semantics are owned by `domains.ecss.compliance`; the `audit` side only loads the package, builds the assertion index, and exposes query convenience through a lazy import.

In the factgraph-only v0.1 wheel, `domains.ecss` is not part of the install. This entrypoint is preserved as a monorepo / optional-domain compatibility surface; if `domains.ecss` is missing, the call raises `AuditOptionalDomainError` rather than treating `domains` as a factgraph-required dependency:

1. Use requirement / compliance predicates on the write side, for example:
   - `ecss:requirement`
   - `ecss:verification_method`
   - `ecss:compliance_status`
   - `ecss:requirement_rid`
   - `ecss:review_milestone`
2. Export still uses the existing `package_kind="audit"`; no dedicated raw-matrix artifact is added
3. Consumers go through:
   - `AuditQuery.list_compliance_matrix(...)`
   - `build_compliance_matrix_dto(...)`
4. The query implementation drills into the assertion / fact files already in the package rather than only consuming JSONL audit ledgers

### 3.6 Static audit pages (service owner)

1. Prepare an `AuditPackageData`
2. Call `service.static_ui.render_audit_static_site(package_dir, out_dir)`
3. Output static HTML and assets

Full static-site rendering does not belong to the `factgraph.audit` module. `service.static_ui` consumes `factgraph.audit` reader / query / DTO and domain-backed compliance rows, and owns rendered-site contracts such as `site_manifest.json` / `ui_index.json`.

Current static site page filenames / hrefs use a filesystem-safe reversible slug rather than raw percent-encoded ids. The generated site can therefore be browsed directly through ordinary static file servers without depending on special handling of `%xx` paths.

When the package contains requirement / compliance facts, the current static site additionally generates:

- `compliance_matrix.html`
  - displays requirement, status, milestone, verification methods, and RID links as an offline compliance-matrix table
  - each row links to the existing assertion-detail page through assertion id
- `rule_traces.html`
  - serves as a `rule_run_id` proof-entry index
- `rule_traces/{rule_run_id}.html`
  - a shareable detail page for a single rule trace
  - the page top includes a deterministic narrative block purely derived from `rule_run_summary`
  - the page shows the root rule, invocations, `pred_witnesses`, and `non_fact_steps`
  - witness assertions still drill into the existing assertion-detail page

In parallel with static HTML, the audit side also exposes the machine-readable `rule_run_summary` derived surface:

- `AuditQuery.get_rule_trace_summary(rule_run_id)`
- `AuditQuery.list_rule_trace_summaries(...)`
- `build_rule_trace_summary_dto(...)`
- `build_rule_trace_summary_list_dto(...)`

On top of that, the audit side also exposes the machine-readable `rule_run_narrative` surface:

- `AuditQuery.get_rule_trace_narrative(rule_run_id)`
- `build_rule_trace_narrative_dto(...)`

On top of that, the audit side also exposes the machine-readable `candidate_evidence_tree` surface:

- `AuditQuery.get_candidate_evidence_tree(candidate_id)`
- `build_candidate_evidence_tree_dto(...)`

On top of that, the audit side also exposes machine-readable candidate derived surfaces:

- `AuditQuery.get_candidate_evidence_tree_summary(candidate_id)`
- `AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)`
- `build_candidate_evidence_tree_summary_dto(...)`
- `build_candidate_evidence_tree_narrative_dto(...)`

When the package contains candidate rows, the current static site additionally generates:

- `candidate_evidence.html`
  - candidate evidence tree index
- `candidate_evidence/{candidate_id}.html`
  - node-kind-aware nested tree page
  - the page top includes a deterministic narrative block purely derived from `candidate_evidence_tree_summary`
  - assertion leaves continue to drill into the existing assertion-detail page
  - if a candidate has `rule_ref_edges` or legacy `rule_refs`, the page shows a `rule_ref_section` as needed
  - it currently also supports recursive child proof nodes:
    - `referenced_support`
    - `unresolved_support`
    - `recursion_boundary`
  - it currently also supports engine-degraded candidate trees:
    - `candidate_result`
    - `support_section`
    - `degraded_support`
  - audit consumes the same terminal taxonomy contract on the candidate tree as runtime:
    - `unresolved_support`
      - `child_support_unavailable`
      - `artifact_missing`
    - `recursion_boundary`
      - `cycle`
      - `depth_limit`
  - audit does not invent new reason enums; summary / query / static all continue to consume the same set of raw node-kind and reason fields
  - audit also consumes the same `node_kind` provenance-role taxonomy as runtime (frozen contract):
    - **structural**: `candidate_result`, `support_section`, `rule_ref_section`
    - **witness**: `predicate_witness_group`, `assertion_fact`
    - **constraint**: `non_fact_check`
    - **rule_chain**: `rule_ref`, `referenced_support`
    - **terminal**: `unresolved_support`, `recursion_boundary`
    - **degraded**: `degraded_support`
  - the first round does not add `source_kind` / `provenance_kind`; `node_kind` is the provenance-role carrier
  - deeper assertion-origin taxonomy is deferred
  - only the structured `rule_ref_edges` path enters the recursive terminal taxonomy; the legacy `rule_refs` fallback still keeps a flat `rule_ref` node
  - audit also consumes the same engine-degraded tree contract as runtime:
    - `degraded_support`
      - `support_kind`
      - `witness_status="degraded"`
      - `children=[]`
    - `degraded_support` does not reuse the native recursive terminal taxonomy
  - legacy `"none"` and `engine_no_witness_v1` are isomorphic on the tree surface

This summary set is isomorphic to the runtime `rule_run_summary` and is purely derived from existing raw trace payloads.
This narrative set is isomorphic to the runtime `rule_run_narrative` and is purely derived from the existing `rule_run_summary`.
This candidate tree set is isomorphic to the runtime `candidate_evidence_tree` and is derived from:
- witness-bearing path: `candidate_ledger + support_artifacts + assertion detail`
- engine-degraded path: `candidate_ledger`
The candidate summary set is isomorphic to the runtime `candidate_evidence_tree_summary` and is purely derived from the existing raw tree.
The candidate narrative set is isomorphic to the runtime `candidate_evidence_tree_narrative` and is purely derived from the existing candidate summary.
When the audit package contains `certainty_summaries.jsonl`, the candidate narrative also includes an additive `certainty_lines` section, identical in shape to the runtime output.
Candidate NL explain is currently outside the audit first-round scope; the static page only consumes the narrative block and does not invent a separate NL DTO.

## 4. Boundaries with Other Layers

- `adapters`
  - audit packages are exported by adapters; audit handles reading and consumption
- `core`
  - audit does not directly query the live `Ledger`
- `authoring`
  - audit can consume authoring apply events carried by a package, but does not directly manage the registry
- `ecss`
  - the canonical preset owner for requirement / compliance predicates is `domains.ecss.vcd`
  - the ECSS compliance row-assembly owner is `domains.ecss.compliance`
  - audit lazily imports and exposes `AuditQuery.list_compliance_matrix(...)` but does not own ECSS row semantics; on a factgraph-only wheel where `domains.ecss` is missing, this entrypoint raises `AuditOptionalDomainError`
- `explainability`
  - the compliance matrix is responsible only for requirement-level delivery; finer assertion / support evidence drill-down is still owned by the assertion detail / explainability substrate
  - rule trace static delivery only consumes the existing `RuleTraceArtifact` from the package and does not add live explain endpoints
  - if a runtime live permalink exists, it should preferably reuse the existing page renderers and data shape from this module rather than building a second HTML template stack

## 5. Current Limitations

- audit primarily targets offline snapshots and is not a real-time audit interface
- there is no entrypoint that maps a live runtime store directly into audit queries
- audit capabilities depend on whether the exported package fully contains the required ledger / decision / authoring event information
- the requirement / compliance matrix is currently an offline-query-first shape and does not expose a live service endpoint
- `service.static_ui` currently supports both:
  - `rule_run_id` proof-entry pages
  - witness-bearing candidate evidence-tree pages
- but it still does not support an interactive graph UI, salience breakdown, or finer provenance contracts
- `service.static_ui` support for the compliance matrix is currently a single-page overview and does not include per-requirement detail pages or extra search facets
- if a live permalink is provided by the runtime service, it currently only reuses the existing rule-trace / candidate page renderers online; the audit export remains the durable shareable surface

## 6. Audit Package Artifact Files

When a package is exported with `package_kind="audit"`, in addition to ledger / decision related files the package also carries an explain-artifact dump:

- `audit/support_artifacts.jsonl`
  - flat JSONL rows keyed by `support_digest`
  - the payload reuses the JSON-friendly shape of `ProofReceipt`
- `audit/rule_trace_artifacts.jsonl`
  - flat JSONL rows keyed by `rule_run_id`
  - the payload reuses the JSON-friendly shape of `RuleTraceArtifact`
- `audit/certainty_summaries.jsonl` (optional)
  - flat JSONL rows keyed by `candidate_id`
  - row shape: `{"candidate_id": "...", "certainty_summary": {...}}`
  - written only when the candidate's certainty can be derived from runtime
    in-memory data
  - the `certainty_summary` payload is isomorphic to the `certainty_summary` field of the runtime `explain-summary`
  - older packages without this file: the reader returns an empty dict (backward compatible)
- `audit/provenance_trees.jsonl` (optional)
  - flat JSONL rows keyed by `candidate_id`
  - row shape: `{"candidate_id": "...", "provenance_tree": {...}}`
  - written only when export-time has both an accepted candidate and the ability to materialize a query-bearing Souffle package via session-scoped derivation recipe replay
  - the `provenance_tree` payload reuses the adapter-local `SouffleProofTreeV0` dict shape (`query` / `root` / `rules`)
  - older packages without this file: the reader returns an empty dict (backward compatible)
- `audit/provenance_statuses.jsonl` (optional)
  - flat JSONL rows keyed by `candidate_id`
  - row shape: `{"candidate_id": "...", "status": "...", "engine": "souffle", "truncated": false, "reason": "..."?}`
  - records whether provenance is available, why not, and whether the proof tree contains `subproof` depth truncation
  - materialized at export time alongside `provenance_trees.jsonl`; older packages without this file: the reader returns an empty dict (backward compatible)

These files are currently exported in full without reference-subset trimming; their job is to let an offline audit consumer read explain carriers, not to provide online durable readback.

`audit.reader` / `AuditQuery` / `service.static_ui` currently consume `rule_trace_artifacts.jsonl` uniformly:

- the reader reads JSONL rows (older packages without the file return an empty set)
- the query layer can offline-query by `rule_run_id`
- the query / DTO layer can also derive `rule_run_summary` from the same raw rows
- the query / DTO layer can also derive `rule_run_narrative` from the same summary surface
- `service.static_ui` can render `rule_run_id` into a shareable proof-entry page and append the deterministic rule-run narrative at the page top via the audit narrative DTO

`audit.reader` / `AuditQuery` / `service.static_ui` also currently consume `support_artifacts.jsonl` uniformly:

- the reader reads JSONL rows (older packages without the file return an empty set)
- the query layer can offline-rebuild the witness-bearing candidate evidence tree by `candidate_id -> support_digest` (currently including `native_binding_v1` and `souffle_witness_v1`)
- the query layer prefers `ProofReceipt.rule_ref_edges` and continues to offline-dereference child support artifacts via `child_support_digest`; if the package only has legacy `rule_refs`, it preserves a minimal fallback tree
- the DTO layer can directly return `candidate_evidence_tree` isomorphic to runtime
- `service.static_ui` can render `candidate_id` into a recursive sectioned tree page and continue drilling into the existing assertion-detail page

`audit.reader` / `AuditQuery` / `service.static_ui` also currently consume `certainty_summaries.jsonl` uniformly:

- the reader reads JSONL rows → parsed as a `{candidate_id: certainty_summary_dict}` mapping (older packages without the file return an empty dict)
- the query layer can query the materialized certainty_summary by `candidate_id`
- the query layer's `get_candidate_evidence_tree_narrative(candidate_id)` passes the materialized certainty_summary into the narrative renderer, producing a narrative with an additive `certainty_lines` section
- the `service.static_ui` candidate evidence page renders a certainty section at the end of the narrative block (when certainty_lines is present)
- certainty_summary is precomputed at export time by the runtime service (via the core `materialize_certainty_summary` helper); the audit side does not compute query-time (because `condition_weights` is not available offline)
- `condition_weights` is treated as certainty/explain projection input:
  it is not exported as an engine adapter parameter, and future runtime
  configuration for this lane belongs in
  `SemanticsProfile.certainty_projection`

`audit.reader` / `AuditQuery` / `service.static_ui` also currently consume `provenance_trees.jsonl` uniformly:

- the reader reads JSONL rows → parsed as a `{candidate_id: provenance_tree_dict}` mapping (older packages without the file return an empty dict)
- the query layer can query the materialized engine-native provenance tree by `candidate_id`
- the `service.static_ui` candidate evidence page renders an additive `Engine Provenance` section after the certainty section (when provenance_tree is present)
- provenance_tree is materialized at export time by the runtime service via query-bearing Souffle package replay; the audit side does not perform query-time Souffle execution

`audit.reader` / `AuditQuery` / `service.static_ui` also currently consume `provenance_statuses.jsonl` uniformly:

- the reader reads JSONL rows → parsed as a `{candidate_id: provenance_status_dict}` mapping (older packages without the file return an empty dict)
- the query layer can query a single provenance status by `candidate_id` and can also produce a package-level coverage summary
- `list_candidates_with_provenance()` / `list_candidates_without_provenance()` / `summarize_provenance_coverage()` all count by unique `candidate_id` rather than by raw `candidate_ledger` row count
- the `service.static_ui` candidate evidence page renders a provenance availability badge; when `truncated=true`, an additional depth-truncation warning is appended
- the `service.static_ui` landing page shows provenance coverage / truncated proof metric cards when the package contains `provenance_statuses.jsonl`

A dedicated `rule_trace_summary` artifact file is not currently added; summary is a purely derived surface at the read / query layer, not a new durable package contract.
A dedicated `candidate_evidence_tree` artifact file is also not currently added; the candidate tree is likewise a purely derived surface at the read / query layer, not a new durable package contract.
