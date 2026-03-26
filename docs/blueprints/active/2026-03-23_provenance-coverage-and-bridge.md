# Sub-Blueprint: Provenance Coverage, Bridge, and Query Ergonomics

- Status: scoped
- Created: 2026-03-23
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Audit Log: [2026-03-23_provenance-coverage-and-bridge.audit.md](./2026-03-23_provenance-coverage-and-bridge.audit.md)

## 1. Problem

Provenance is now in the audit pipeline, but the product surface is incomplete:

- Users cannot see which candidates have provenance and which don't
- Export silently skips candidates without recipes — not auditable
- Evidence tree and provenance tree are displayed side-by-side with no visual link
- Souffle depth truncation (`subproof` nodes) has no user-facing explanation
- No package-level summary of provenance coverage

## 2. Goals

Upgrade from "can display provenance" to "can audit provenance coverage, understand gaps, and visually connect provenance with evidence tree."

## 3. Non-Goals

- ProofNode v1 or unified cross-engine carrier
- Provenance in core / ledger / meta
- Query-time Souffle explain
- Multi-engine support
- New service endpoints

## 4. Scope: Three Steps

### Step 1: Provenance Coverage + Status Artifact

**New file in audit package**: `audit/provenance_statuses.jsonl`

Each row:
```json
{
  "candidate_id": "cand_v2:abc...",
  "status": "present",
  "engine": "souffle",
  "truncated": false
}
```

Status values:
- `present` — provenance tree successfully materialized
- `missing_recipe` — no derivation recipe cached for this candidate's run_id
- `export_failed` — query-bearing package export failed
- `no_matching_row` — Souffle ran but produced no output for this candidate
- `explain_failed` — Souffle `-t explain` returned error or empty
- `skipped` — non-Souffle engine or other skip reason

**Changes**:
- `runtime_v1.py`: `_materialize_provenance_trees` returns both trees dict AND statuses dict
- `package.py`: write `audit/provenance_statuses.jsonl` alongside `provenance_trees.jsonl`
- `reader.py`: `AuditPackageData.provenance_statuses` field
- `query.py`: `get_candidate_provenance_status(candidate_id)` method

**Truncation detection**: scan proof tree for any node with `node_type == "subproof"`. If found, set `truncated: true` in status.

### Step 2: Candidate Page Bridge + Truncation UX

**static_ui.py changes** (template/CSS only, no DTO changes):

1. **Provenance status badge** on each candidate evidence page:
   - Green badge: "Engine Provenance: Available"
   - Yellow badge: "Engine Provenance: Truncated (depth limit)"
   - Red badge: "Engine Provenance: Unavailable — [reason]"

2. **Truncation warning** when provenance tree contains subproof nodes:
   - "This proof tree was truncated by the Souffle engine at depth level 4. Nodes marked 'Truncated' can be expanded with deeper analysis. The truncation does not indicate missing evidence — the full derivation exists in the engine."

3. **Visual bridge note**: at the top of the Engine Provenance section, add a brief explanation: "The provenance tree below shows the Souffle engine's internal derivation for this candidate. Rule numbers (R1, R2, ...) are Souffle-internal and correspond to the compiled form of the rules shown in the Evidence Tree above." No data-level cross-reference — mapping `rule_ref_id` to Souffle `(Rn)` requires an export-time mapping artifact not yet available.

### Step 3: AuditQuery Package-Level Provenance Summary

**New query.py methods**:

```python
def list_candidates_with_provenance(self) -> list[dict]:
    """Candidates that have materialized provenance trees."""

def list_candidates_without_provenance(self) -> list[dict]:
    """Candidates missing provenance, with status/reason."""

def summarize_provenance_coverage(self) -> dict:
    """Package-level summary:
    {
        "total_candidates": 7,       # unique candidate_ids, not ledger rows
        "with_provenance": 3,
        "without_provenance": 4,
        "truncated": 1,
        "by_status": {"present": 3, "missing_recipe": 2, ...},
        "coverage_pct": 42.9,
    }
    # Note: counts are by unique candidate_id, not candidate_ledger rows.
    """
```

**Landing page update**: show provenance coverage metric on the audit site index page (e.g., "Provenance Coverage: 3/7 candidates (42.9%)")

## 5. Implementation Plan

```
Step 1: provenance_statuses.jsonl
  - runtime_v1.py: extend _materialize_provenance_trees to collect statuses
  - package.py: write provenance_statuses.jsonl
  - reader.py: load provenance_statuses
  - query.py: get_candidate_provenance_status

Step 2: candidate page bridge + truncation UX
  - static_ui.py: status badge, truncation warning, rule number cross-ref

Step 3: package-level summary
  - query.py: list_candidates_with/without_provenance, summarize_provenance_coverage
  - static_ui.py: landing page coverage metric
  - tests + docs
```

## 6. Acceptance Criteria

- Every accepted candidate has a provenance status entry in the audit package
- `present` candidates have provenance trees; others have a machine-readable reason
- Candidate evidence pages show provenance status badge
- Truncated trees show explicit warning text
- Landing page shows provenance coverage percentage
- `summarize_provenance_coverage()` returns accurate counts
- Old packages without `provenance_statuses.jsonl` gracefully fall back to empty
- 250+ tests green
- Audit docs updated

## 7. Boundary

- No ProofNode v1
- No core/ledger/meta changes
- No new service endpoints
- No multi-engine support
- Evidence tree ↔ provenance bridge is visual only (HTML labels), not a data model merge
