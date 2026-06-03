# Task Blueprint Audit: Evaluate-result flatten Slice α — Claim/EvidenceRef redundant-field removal

- Blueprint: [2026-06-03_eval-result-flatten-slice-alpha.md](./2026-06-03_eval-result-flatten-slice-alpha.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §6 Slice α
- Codex working branch (when assigned): `codex/v0.2.0-eval-result-flatten-slice-alpha-2026-06-XX` (per `feedback_worktree_parallel_implementation` — `codex/` prefix for in-flight work)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint created | Initial scope recorded on `v0.2.0-eval-result-flatten-adr-2026-06-03`. |
| 2026-06-03 | draft | Cadence correction — branch renamed | `v0.2.0-eval-result-flatten-adr-2026-06-03` → `v0.2.0-blueprint-eval-result-flatten-2026-06-03` per [`workflow/AGENTS.md`](../../AGENTS.md):69 canonical blueprint naming convention. Original "-adr-" form was not one of the 5 canonical branch types (audit / decision / blueprint / preflight / impl). |
| 2026-06-03 | draft | Cadence path locks recorded (per user 2026-06-03) | (i) §5.4 deprecation strategy locked locally on blueprint branch via Step 4.2 review + Step 4.4 amendment fold (single-Q consolidation; no separate Q-decision doc). (ii) Other 6 §5 unlocked Qs deferred to before Slice γ. (iii) Stage 1 audit doc deferred per Slice 4/5 precedent ([`workflow/CADENCE.md`](../../CADENCE.md) L268); Stage-0 source audit folded into design-point + this blueprint draft; Step 4.2 reviewer verifies via Rule 1 fresh reads. Details in blueprint §6.1. |
| 2026-06-03 | draft | Previous codex round-1 prompt withdrawn | The earlier prompt I drafted mislabeled the round-1 work as "audit" while structurally aligning with Stage 4.3 preflight, and put the work on a `codex/`-prefixed branch instead of either the blueprint branch (Step 4.2 review) or a canonical `v0.2.0-eval-result-flatten-preflight-2026-06-03` (Step 4.3). Withdrawn; new codex prompt issued for Step 4.2 draft review + tightening, executed directly on the blueprint branch. |
| 2026-06-03 | draft | Step 4.2 draft review + tightening (Codex round 1) | Rule 1 fresh reads verified the folded Stage-0 claims and surfaced 4 polish findings: P1-1 row digest helper cannot call deprecated properties before owner binding; P1-2 EvaluateResult row-binding order currently reads `EvidenceRef.result_id` pre-bind; P2-1 tests/verification anchors used non-existent `tests/factgraph` path; P2-2 internal code must preserve byte-equal digests without emitting deprecation warnings. Blueprint updated in-place on the blueprint branch; §5.4 local Q fold remains below escalation threshold. |

## Step 4.2 Review (Codex Round 1)

Reviewer: Codex
Branch: `v0.2.0-blueprint-eval-result-flatten-2026-06-03`
HEAD before tightening: `509b1f9e`

### Rule 1 Fresh-Read Spot Checks

| Claim | Fresh source verification | Result |
| --- | --- | --- |
| Shipped `Claim` has 5 fields (`kind`, `name`, `arguments`, `repr`, `digest`) | `src/factgraph/application/protocol/evaluate_result.py:85-99` | ✓ |
| Shipped `EvidenceRef` has 5 fields (`ref_id`, `result_id`, `row_id`, `fact_digest`, `closed_head_digest`) | `src/factgraph/application/protocol/evaluate_result.py:102-115` | ✓ |
| D17 equality assertions exist at row construction | `src/factgraph/application/protocol/evaluate_result.py:128-138` | ✓ |
| `EvidenceRef.ref_id` formula is already centralized as `evidence_ref_id_for(...)` | `src/factgraph/application/protocol/evaluate_result.py:413-429` | ✓; helper extraction may be a rename/wrapper, not a discovery task |
| `EvaluateResult.__post_init__` currently checks `row.evidence_ref.result_id` before rebinding rows | `src/factgraph/application/protocol/evaluate_result.py:213-236` | ✓; requires tightening |
| `_row_digest_for(row)` currently reads fields targeted for deprecation | `src/factgraph/application/protocol/evaluate_result.py:432-458` | ✓; requires tightening |
| Actual test paths are under `tests/application/protocol/` and `tests/sdk/`, not `tests/factgraph/` | `rg --files tests` found `tests/application/protocol/test_evaluate_result_dtos.py`, `tests/application/protocol/test_evaluate_result_digests.py`, `tests/sdk/test_evaluate_result_exports.py` | ✓ |

### Findings

| ID | Severity | Finding | Blueprint action |
| --- | --- | --- | --- |
| P1-1 | Required | `_row_digest_for(row)` currently reads `row.claim.arguments`, `row.claim.name`, and `row.evidence_ref.{fact_digest,result_id,row_id}`. If these become deprecated properties, digest computation will either emit warnings internally or fail before owner binding. | Added §5.4 requiring an explicit-context row digest helper that preserves `evaluate_row_digest_v1` bytes without deprecated-property access. Added acceptance + implementation step. |
| P1-2 | Required | `EvaluateResult.__post_init__` checks `row.evidence_ref.result_id != self.result_id` before `replace(row, _result_resolver=...)`. After Slice α, `result_id` is a deprecated owner-resolved property, so this check becomes a pre-bind failure. | §5.3 now requires removing the pre-bind check and binding rows first; acceptance requires `result[0].evidence_ref.result_id` warning + byte-equal value. |
| P2-1 | Recommended | Blueprint related modules and test command referenced `tests/factgraph/...`, but shipped evaluate-result tests live under `tests/application/protocol/` plus `tests/sdk/test_evaluate_result_exports.py`. | Related modules, acceptance pytest command, and implementation plan now use the real test cohort. |
| P2-2 | Recommended | Internal code (`_row_digest_for`, `_row_anchor_matches`, evidence metadata/explanation paths) must not treat deprecated properties as normal internal access. Otherwise normal `row.explain()` / `EvaluateResult` construction may emit user-facing warnings without user touching deprecated APIs. | Blueprint now explicitly requires digest helpers and internal compatibility paths to avoid deprecated-property access where byte-equal direct context is available. |

### §5.4 Local Q Fold Assessment

Codex does **not** recommend escalating §5.4 to a standalone Q-decision doc at Step 4.2. The local policy (one-release-cycle `DeprecationWarning`, removal in Slice γ) remains scoped to Slice α compatibility and does not yet force a cross-slice public compatibility decision beyond what parent design already records. Escalation remains available if Step 4.3 preflight finds unresolved cross-process serialization or SDK export compatibility blockers.

## Codex Pre-Impl Audit Tasks

These tasks ground the blueprint in shipped truth before impl starts. Codex must record findings under "Codex Audit Findings" before any code edit.

### Task A1 — Pin the `EvidenceRef.ref_id` derivation formula

**Goal:** Capture the exact shipped formula that produces `EvidenceRef.ref_id` so the new `_compute_evidence_ref_id(...)` helper is byte-equal.

**Steps:**
1. `grep -rn 'evidence_ref:[A-Za-z0-9]\+\|EvidenceRef(ref_id=\|_ref_id\|EVIDENCE_REF_ID' src/factgraph/`
2. Locate the construction site(s) that compute `ref_id` (likely `evaluate_result.py` row-builder helper or an adapter `_build_*`)
3. Record:
   - Full path + line of the formula
   - Input set (which fields feed in, what order)
   - Hash digest function used (e.g. `_sha256_token`, prefix used like `evref:`, encoding)
   - One worked example: input fields → output token (copy from a unit test if one exists; else construct one)

**Expected output in audit log (§Codex Audit Findings A1):**
```
- File: src/factgraph/application/protocol/evaluate_result.py:<line>
- Function: <name>
- Formula: ref_id = <PREFIX> + sha256( result_id | row_id | fact_digest | closed_head_digest ).hexdigest()
- Worked example: <inputs> → <token>
- Test reference (if any): tests/...
```

### Task A2 — Enumerate all `Claim(...)` / `EvidenceRef(...)` construction sites

**Goal:** Find every place where `Claim` or `EvidenceRef` is instantiated, so step 7 of the impl plan covers all sites.

**Steps:**
1. `grep -rn 'Claim(' src/factgraph/ tests/factgraph/ | grep -v 'class Claim\|@dataclass\|isinstance\|ProtocolShapeError\|# '`
2. `grep -rn 'EvidenceRef(' src/factgraph/ tests/factgraph/ | grep -v 'class EvidenceRef\|@dataclass\|isinstance\|ProtocolShapeError\|# '`
3. Bucket each hit into:
   - **Production** — `src/factgraph/` paths that build rows during evaluate
   - **Test fixture** — `tests/` paths constructing standalone DTOs
   - **Module docs example** — markdown code blocks (these may need a note but not code edit if they're illustrative)

**Expected output in audit log (§Codex Audit Findings A2):**
- Production sites: file:line list, count
- Test fixture sites: file:line list, count
- Module-docs example sites: file:line list, count
- Any site that does NOT fit the above buckets → flag with `?` for review

### Task A3 — Check whether `src/factgraph/application/protocol/docs/README.md` (or equivalent module docs) documents Claim / EvidenceRef field sets

**Goal:** Decide whether module docs need updating (§9 / §10 of blueprint).

**Steps:**
1. `ls src/factgraph/application/protocol/docs/ 2>/dev/null` — does a docs subtree exist for this module?
2. `grep -rn 'Claim\|EvidenceRef' src/factgraph/application/protocol/docs/ 2>/dev/null` — are these classes mentioned?

**Expected output in audit log (§Codex Audit Findings A3):**
- Module docs path (if exists): ...
- Mentions of Claim / EvidenceRef field set: yes/no, with line refs

### Task A4 — Cross-flip pre-conditions

Before any code edit, verify the shipped state still matches the blueprint assumptions:

1. `Claim` definition at `src/factgraph/application/protocol/evaluate_result.py:86-99` (5 fields: kind / name / arguments / repr / digest)
2. `EvidenceRef` definition at `:102-115` (5 fields: ref_id / result_id / row_id / fact_digest / closed_head_digest)
3. `EvaluateRow.__post_init__` D17 invariant block at `:128-147` (lines 135-138 contain the two cross-field equality assertions)
4. `EvaluateRow._result_resolver` pattern at `:126` + `_require_live_result` at `:149-152` (template for the new Claim/EvidenceRef resolvers)

**Expected output in audit log (§Codex Audit Findings A4):**
- For each of 1-4: ✓ matches blueprint anchor, or ⚠️ drift + actual line range

## Codex Audit Findings

(Codex appends findings here under each task's `### Task A<n>` heading after running the steps.)

### Task A1 findings

_(empty — to be filled by codex)_

### Task A2 findings

_(empty — to be filled by codex)_

### Task A3 findings

_(empty — to be filled by codex)_

### Task A4 findings

_(empty — to be filled by codex)_

## Decision Notes

按时间追加关键决策,尤其是:

- scope freeze
- scope expansion or reduction
- implementation blocker
- module docs sync completed
- archive completed

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Blueprint draft uses owner-resolver pattern (mirror of `EvaluateRow._result_resolver`) for Claim / EvidenceRef deprecated property fallback | Standalone frozen DTO has no fallback source for removed fields without an owner reference; the resolver pattern is already validated by shipped EvaluateRow / DetachedRowError |
| 2026-06-03 | D17 invariant equality assertions (L135-138) become structural tautology after Slice α | Deprecated properties literally return `row.row_id` / `row.claim.digest`; an explicit assertion would compare a value to itself |
| 2026-06-03 | Slice α retains `Claim` / `EvidenceRef` wrapper classes themselves | Wrapper removal is Slice γ scope; α is field-only cleanup with backward compat |
| 2026-06-03 | §5.4 deprecation strategy — local Q fold (no separate Q-decision doc at this point) | Per user lock 2026-06-03. §5.4 is the only §5 Q load-bearing for Slice α field-removal scope. Treat as local implementation policy on blueprint branch; consolidate via Step 4.2 review + Step 4.4 amendment. Escalation rule: if Step 4.2 surfaces public-compat or cross-slice impact for §5.4 (e.g., affects Slice β/γ deprecation contracts), upgrade to single Q-decision doc before scoped anchor. Closure §10 must record as `single-Q local lock consolidated on blueprint branch`. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Per user lock 2026-06-03. Stage-0 source audit considered folded into design-point [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) (§1-§4 friction + §8 file:line anchors) + this blueprint draft. No `workflow/audit/active/2026-06-03_eval-result-flatten-vs-shipped.md` produced. Step 4.2 reviewer must verify folded audit claims via Rule 1 fresh reads. Escalation rule: if source grounding insufficient at Step 4.2, supplement with preflight artifact at Step 4.3, do NOT regress to standalone Stage 1 doc. |

## Cross-flip checkpoints (per `feedback_audit_to_archive_cadence`)

- [ ] Audit findings A1-A4 recorded and user-reviewed before codex starts editing
- [ ] User authorizes scope freeze with explicit "可以推进"
- [ ] Per-step `pytest src/factgraph tests/factgraph -x` clean before next step
- [ ] Per-step grep verifies no construction site missed
- [ ] User authorizes archive with explicit "可以归档"
