# Evidence Diff / Cross-Run(Batch 7 of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Related Modules:
  - `src/kernel/audit`
  - `src/kernel/audit/round_events.py`
  - `src/kernel/audit/query.py`
  - `src/kernel/application/protocol/proofframe.py`
- Related Docs:
  - [docs/blueprints/active/2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md)
  - [docs/blueprints/archive/2026-05-05_proofframe-rechecker.md](../archive/2026-05-05_proofframe-rechecker.md)
  - [docs/blueprints/archive/2026-05-05_round-persistence.md](../archive/2026-05-05_round-persistence.md)
  - [src/kernel/audit/docs/03_audit_package_contract.md](../../../src/kernel/audit/docs/03_audit_package_contract.md)
- Audit Log:
  - [2026-05-06_evidence-diff.audit.md](./2026-05-06_evidence-diff.audit.md)

## 1. Problem

Batch 7 owns L4 per-frame proof tree diff and L5 cross-run module aggregation. Batch 4 shipped ProofFrame atom verdicts; Batch 6 persisted first-slice round events with `proof_frame_result` payloads. The new question is whether those persisted rows are sufficient to compute useful diffs and aggregation without re-running capabilities, or whether Batch 7 would require fields intentionally deferred from Batch 6.

This batch must not assume "diff" and "aggregation" are one capability just because the parent plan lists them together. A per-frame diff compares proof-frame outcomes across rounds; cross-run aggregation groups many events by stable identity. Those may share the same input rows, but they may not share output shape, lifecycle, or indexing needs.

## 2. Goals

- Decide, through Step 0, whether Batch 7 can ship a narrow read-only audit query extension over Batch 6 `round_events`.
- If Step 0 confirms feasibility, freeze a per-frame diff contract over persisted `proof_frame_result` events.
- If Step 0 confirms feasibility, freeze a cross-run aggregation contract over stable persisted identities, without adding a durable aggregation index unless proven necessary.
- Preserve Batch 4 ProofFrame protocol and Batch 6 round-event schema unless Step 0 records a parent-plan-level blocker and a scoped deviation.
- Keep all Batch 7 behavior read-only over audit packages.

## 3. Non-goals

- No new capability runtimes or application protocol DTOs.
- No SDK, service, agent, or public release surface work(Batch 8 owns that).
- No Store ledger mutation, ArtifactSidecar semantic change, or audit package exporter redesign.
- No new Batch 6 event families for Frontier or rule actions unless Step 0 proves Batch 7 is blocked without them.
- No revival of `superseded_by_full_eval`.
- No ProofFrame protocol change.
- No rule-action protocol change.
- No Batch 4 deferred ProofFrame `rule_refs` symmetric hardening.
- No diff over raw proof tree internals unavailable in `round_events.jsonl`.
- No durable aggregation index unless Step 0 proves query-time derivation is insufficient.
- No cross-engine semantics beyond persisted event rows.
- No UI/demo/public notebook work unless Step 0 makes it an explicit acceptance artifact.

## 4. Current Context

### 4.1 Parent Plan

Round Story Completion Plan §5.7 says:

- Goal: L4 per-frame proof tree diff + L5 cross-run module aggregation.
- Consumers: Batch 4 ProofFrame and Batch 6 persistence.
- Entry criteria: Batch 6 closed and ProofFrame schema stable.
- Exit criteria: per-frame diff algorithm shipped; cross-run aggregation index shipped by `module_id` or equivalent stable identity; historical comparison demo runnable.

### 4.2 Batch 4 Inputs

Batch 4 froze `ProofFrameRecheckResult` with:

- `status: ProofFrameStatus`, where `ProofFrameStatus = still_valid | invalidated | unknown`;
- `binding_items`;
- `atom_verdicts`, each with `atom_key`, `verdict`, and `affected_action_indices`;
- aggregation invariant `result.status == aggregate(result.atom_verdicts)`.

Batch 4 explicitly collapsed `superseded_by_full_eval`; Batch 7 must not rely on that status.

### 4.3 Batch 6 Inputs

Batch 6 added optional `audit/round_events.jsonl`, loaded into `AuditPackageData.round_events` and queried through `AuditQuery.list_rounds`, `list_round_events`, `get_round_event`, and `get_round_summary`.

The first-slice event kinds are:

- lifecycle:`round_started`, `round_finalized`;
- capability:`check_result`, `diagnose_result`, `fact_overlay_result`, `why_not_result`, `proof_frame_result`.

Batch 6 deliberately deferred:

- Frontier event family;
- rule-action result event families;
- Batch 7 diff/aggregation/index logic.

`proof_frame_result` persists `status`, `binding_items`, and `atom_verdicts`. It does not persist the full `SupportArtifact`, full rule spec, module metadata, or a precomputed aggregation key.

## 5. Step 0 Falsifiability Frame

Step 0 must answer these before any DTO or query method is frozen.

### 5.1 Falsifiers

| # | Falsifier | If true |
|---|---|---|
| 1 | `proof_frame_result` rows do not contain enough stable identity to pair the same frame across two rounds. | Path B suspend,or add a narrowly scoped identity field only if it does not rewrite Batch 6 schema. |
| 2 | `binding_items` JSON projection cannot be used as stable frame identity because opaque digests or non-canonical values make equality unreliable. | Require explicit frame key in future event schema,or suspend Batch 7 until Batch 6 can be amended. |
| 3 | `atom_key` is not stable enough for per-atom diff across rounds. | Reduce L4 to frame-level status diff or suspend per-atom diff. |
| 4 | `affected_action_indices` is only meaningful inside one request and cannot be compared across rounds. | Exclude action-index comparison from diff;compare only verdict state,not causal index identity. |
| 5 | Cross-run aggregation needs `module_id`, but no persisted event payload contains a derivable stable module identity. | Step 0 must either define an equivalent stable identity from persisted fields or choose Path B/Path C; do not invent module identity from timestamps or round ids. |
| 6 | Check/Diagnose/Fact Overlay/Why-not rows need to participate in aggregation, but their payload shapes do not share a common grouping key with ProofFrame rows. | Split L4 ProofFrame diff from L5 aggregation or narrow first slice to ProofFrame-only. |
| 7 | Batch 7 cannot compute meaningful changes without Frontier or rule-action event families deferred in Batch 6. | Suspend,or explicitly limit Batch 7 to S3 first-slice rows and carry the deficit forward. |
| 8 | Per-frame diff and cross-run aggregation have different lifecycle identities and should be separate capabilities. Test condition:if the diff DTO input/output shape(two frame identities + per-atom delta)and aggregation DTO shape(N rounds + group-by counts)share fewer than two stable identity fields,or their output fields are mostly disjoint,Path C is preferred. | Path C split into child blueprints; do not ship both under one mixed DTO. |
| 9 | A durable aggregation index is required for correctness,not only performance. | Add index only if Step 0 proves query-time derivation is ambiguous or impossible. |
| 10 | Query-time aggregation over `round_events` is too slow only for large packages. | Keep Batch 7 query-derived; performance index belongs to follow-up unless correctness is affected. |
| 11 | Diff output would need raw `SupportArtifact` or proof tree internals not persisted by Batch 6. | Reduce diff scope to persisted ProofFrame verdicts or suspend. |
| 12 | Round finalization / partial-round behavior makes cross-run comparison unsafe. | Require `RoundSummary.is_finalized == True` by default and define explicit partial-round handling. |
| 13 | Unknown future event kinds or v2 schema rows make aggregation unsafe. | Ignore unknown/future rows for first-slice aggregation,with warnings or explicit skipped counts. |
| 14 | Batch 7 cannot produce a historical comparison demo without public-surface work. | Keep demo as kernel-level test fixture or defer demo to Batch 8. |
| 15 | The Batch 4 deferred ProofFrame `rule_refs` hardening must be fixed before diff can be trustworthy. | Either scope a separate hardening before Batch 7 or explicitly reject RuleRef-bearing proof frames from diff inputs. |
| 16 | L4 per-frame diff has no consumer value beyond existing Batch 4 ProofFrame narrative and raw round-event queries. | Path B suspend or defer L4 diff to Batch 8 public-surface work; do not ship a vanity query without a concrete consumer. |

### 5.2 Candidate Paths

**Path A — Query-derived diff + aggregation over Batch 6 events.**

Add audit-layer DTOs/query methods that derive results from `AuditPackageData.round_events`. No new durable files, no runtime imports, no schema rewrite. This is the default working hypothesis only if §5.1 falsifiers show persisted S3 rows are sufficient.

**Path B — Suspend Batch 7 as premature.**

Use this if Batch 6 did not persist enough identity for stable frame pairing or module aggregation. This is valid close-out, not failure.

**Path C — Split L4 and L5.**

Use this if per-frame diff is crisp over ProofFrame rows but cross-run aggregation needs a separate identity/index design, or vice versa. Child blueprints must be opened before implementation; do not ship a hidden two-capability merge in this blueprint.

### 5.3 Step 0.A Questions

Step 0.A must produce source-grounded answers for all 16 falsifiers and choose Path A, B, or C. It must cite:

- `src/kernel/audit/round_events.py` persisted payload shape;
- `src/kernel/audit/query.py` round-event query shape;
- `src/kernel/application/protocol/proofframe.py` ProofFrame identity and status shape;
- Batch 6 archived outcome and deferred event families.

### 5.4 Step 0.B Carry-Overs

If Step 0.A selects Path A or a narrowed Path C, Step 0.B must freeze:

- diff input selector: two explicit rounds, two events, or round groups;
- diff input cardinality: bilateral comparison(`A` vs `B`)vs baseline-with-many-variants(`baseline` vs `variants[]`);
- frame identity key: persisted `binding_items`, derived digest, event identity, or another stable key;
- atom diff identity: `atom_key` only vs `atom_key + verdict` vs per-event derived digest;
- diff output DTO shape and status vocabulary;
- aggregation grouping key: `module_id`, `rule_id`, `plan_digest`, `proof_frame binding digest`, or explicit "no module aggregation first slice";
- finalized-round policy: reject partial rounds vs include with warning;
- unknown/future event-kind handling;
- whether Batch 7 adds any durable index file or remains purely query-derived;
- test/demo artifact scope.

## 6. Boundaries And Invariants

- Batch 7 is read-only over audit packages.
- Existing `AuditQuery` methods must remain byte-stable for old packages and for packages with round events.
- No application runtime may import `kernel.audit`.
- No SDK/service/agent changes.
- No Store or ArtifactSidecar semantic changes.
- No ProofFrame protocol changes.
- No rule-action DTO changes.
- No `round_events.jsonl` schema change unless Step 0 proves Path A is impossible without an explicitly scoped Batch 6 amendment.
- Unknown future event kinds remain forward-compatible; Batch 7 must not make them hard read errors.
- `superseded_by_full_eval` remains absent.

## 7. Acceptance

- [ ] Step 0.A records all 16 falsifiers with source-grounded answers.
- [ ] Step 0.B freezes diff and aggregation shape before status moves to `scoped`.
- [ ] Implementation, if any, ships only after `Status: scoped`.
- [ ] Per-frame diff tests cover unchanged, status-changed, atom-verdict-changed, missing-frame, and partial-round behavior selected by Step 0.B.
- [ ] Cross-run aggregation tests cover selected grouping key and unknown/future event handling.
- [ ] Old audit packages without `round_events.jsonl` keep existing query behavior.
- [ ] Existing `AuditQuery` methods remain unchanged.
- [ ] No SDK/service/agent diffs.
- [ ] No application runtime imports from `kernel.audit`.
- [ ] No ProofFrame/rule-action protocol drift.
- [ ] No Batch 6 event-family expansion unless Step 0 explicitly scopes it.
- [ ] Module docs updated after implementation.
- [ ] Blueprint Outcome/Deviations completed and archived after implementation or suspension.

## 8. Implementation Plan

1. Step 0.A:falsify Batch 7 against persisted Batch 6 rows and Batch 4 ProofFrame shape;choose Path A/B/C.
2. Step 0.B:freeze diff/aggregation DTO/query shape,identity keys,partial-round policy,and drift gates.
3. Scope transition:move `Status: draft` to `Status: scoped` only after Step 0.B.
4. If Path A/partial Path C ships: add audit protocol DTOs for diff/aggregation under `src/kernel/audit`.
5. Add `AuditQuery` methods in a separate round namespace without changing existing method signatures.
6. Add tests for Step 0.B acceptance,old-package compatibility,and static drift gates.
7. Update `src/kernel/audit/docs`.
8. Complete Outcome/Deviations and archive.

## 9. Docs To Update

- `src/kernel/audit/docs/01_overview.md`
- `src/kernel/audit/docs/03_audit_package_contract.md`
- `src/kernel/audit/docs/README.md` if new docs entry is added.
- `docs/blueprints/archive/README.md` on archive.

## 10. Outcome / Deviations

To be completed after implementation or suspension:

- Final result:
- Deviations from scoped blueprint:
- Verification:
- Archive notes:
