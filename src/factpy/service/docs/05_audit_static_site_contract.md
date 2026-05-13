# Audit Static Site Contract

- Scope: `src/service/static_ui.py`
- Last updated: 2026-04-28
- Owner: `service.static_ui`

`render_audit_static_site(package_dir, out_dir)` renders an already exported audit package into a static HTML site. The caller supplies both paths. The renderer does not choose a repository-level default output directory.

## 1. Inputs

- `package_dir`
  - Directory containing an audit package accepted by `kernel.audit.load_audit_package(...)`
  - Must have `manifest.json` with `package_kind == "audit"`
- `out_dir`
  - Destination directory for rendered HTML and JSON index files
  - Created if missing
  - Treated as caller-owned output

The renderer consumes `kernel.audit` reader/query/DTO APIs and domain-backed compliance query APIs. It does not own package export or domain semantics.

## 2. Generated Layout

Current rendered site files include:

| Path | Role |
|---|---|
| `index.html` | landing page for runs, counts, provenance coverage, and major indexes |
| `search.html` | client-side search page |
| `ui_index.json` | machine-readable UI index for navigation/search integration |
| `site_manifest.json` | machine-readable rendered site manifest |
| `runs/*.html` | run detail pages |
| `decisions/*.html` | decision detail pages |
| `assertions/*.html` | assertion detail pages |
| `rule_traces.html` | rule trace index |
| `rule_traces/*.html` | rule trace detail pages |
| `candidate_evidence.html` | candidate evidence index |
| `candidate_evidence/*.html` | candidate evidence detail pages |
| `authoring_apply_events.html` | authoring apply event index |
| `authoring_apply_runs/*.html` | authoring apply run detail pages |
| `indexes/*.html` | filter/index pages |
| `compliance_matrix.html` | ECSS compliance matrix page when rows are derivable |

Page filenames use a filesystem-safe reversible slug of the source id, not raw percent-encoded ids.

## 3. `site_manifest.json`

`site_manifest.json` is the compact rendered-site contract returned by `render_audit_static_site(...)`.

Stable consumer fields:

- `audit_ui_site_version`
- `package_kind`
- `run_count`
- `decision_count`
- `assertion_count`
- `rule_trace_count`
- `candidate_evidence_count`
- `authoring_apply_event_count`
- `index`
- `search`
- `ui_index`
- `authoring_apply_events`
- `rule_trace_index`
- `candidate_evidence_index`
- `compliance_matrix`
- `compliance_matrix_row_count`

Stable path-list fields:

- `runs`
- `assertions`
- `rule_traces`
- `candidate_evidence`
- `authoring_apply_runs`
- `indexes`

These lists are generated from package content and may be empty. Consumers should treat listed paths as relative to `out_dir`.

## 4. `ui_index.json`

`ui_index.json` is a fuller UI navigation/search index. It is intended for frontend/BFF integration and local static browsing helpers.

Stable high-level roles:

- counts for major page groups
- links to major index pages
- lookup maps from source ids to rendered page paths
- summaries needed for search and navigation

Consumers should avoid depending on incidental ordering or every nested helper field unless that field is documented in the relevant service/static UI docs or covered by tests.

## 5. Provenance And Evidence Rendering

The static site consumes audit package carriers; it does not generate engine-native provenance.

Current rendering behavior:

- candidate pages render `candidate_evidence_tree` when derivable from package carriers
- candidate pages prefer durable `evidence_graphs` and keep Souffle proof-tree fallback for old packages
- candidate pages show provenance availability/status when `provenance_statuses` exists
- landing page shows provenance coverage when status rows exist
- PyReason timeline carriers remain package/query data; static rendering support is intentionally conservative

## 6. Domain-Specific Pages

`compliance_matrix.html` is rendered by `service.static_ui`, but ECSS row semantics are owned by `domains.ecss.compliance` and exposed through `AuditQuery.list_compliance_matrix(...)`.

The static site only renders the rows it receives.

## 7. Non-Goals

- No live runtime querying
- No package export
- No full frontend application shell
- No guarantee that every generated HTML page is a stable API
- No full PROV conformance claim

The durable machine-readable contracts are the audit package files, `site_manifest.json`, and the documented high-level roles of `ui_index.json`.
