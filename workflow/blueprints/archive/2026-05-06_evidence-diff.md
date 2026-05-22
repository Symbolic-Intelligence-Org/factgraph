# Evidence Diff / Cross-Run(Batch 7 of Round Story Completion Plan)

- Status: implemented
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

### 5.5 Step 0.A Spike (synthesized 2026-05-06)

This spike answers §5.1 with source-grounded evidence and chooses among §5.2 paths. Evidence sources:`src/kernel/audit/round_events.py`(post-hardening @ `95f0d14`),`src/kernel/audit/query.py`,`src/kernel/application/protocol/proofframe.py`,Batch 4 archived blueprint `2026-05-05_proofframe-rechecker.md`,and Batch 6 archived blueprint `2026-05-05_round-persistence.md`.

#### 5.5.1 Falsifier Verdicts

| # | Verdict | Source-grounded reason | Implication |
|---|---|---|---|
| 1 | FALSE | `proof_frame_result.payload.request.support_digest` is computed from the `SupportArtifact`(`round_events.py:393-400`),and `result.binding_items` is projected via `project_binding_items`(`round_events.py:401-405`)to a sorted JSON array of `[name, JsonValue]` pairs. Together they identify a proof frame without storing raw `SupportArtifact`. | Frame identity for cross-round pairing = `(support_digest, binding_items JSON)`. No new event-schema field needed. |
| 2 | FALSE | `_opaque_digest`(`round_events.py:579-580`)recurses via `_stable_digest_projection`(`round_events.py:583-603`)to produce canonical JSON with sorted keys;`project_json_value` is byte-stable for JSON primitives and digest-stable for non-primitives. Equality is reliable within the `(support_digest, binding_items)` frame identity. | No explicit frame-key field is needed;Step 0.B can derive a digest from `(support_digest, binding_items JSON)` if it wants a compact key. |
| 3 | FALSE | `atom_key: str` is non-empty validated(`proofframe.py:103`). Support keys are generated from branch/atom position and kind/predicate(`make_pred_atom_key` / `make_non_fact_step_key` in `_support.py:201-225`),and support capture builders use those helpers(`rule_ir.py:411-447`). They are stable inside the same `SupportArtifact`;`support_digest` is the persisted artifact identity. | Step 0.B must scope per-atom diff to matching `support_digest`;cross-artifact atom-key comparison is out of first-slice scope. |
| 4 | TRUE | `affected_action_indices: tuple[int, ...]`(`proofframe.py:100`)references positions in the per-event `EvaluationOverlay.actions` tuple. Index 0 in round A's overlay is not the same logical action as index 0 in round B's overlay. | Diff compares verdicts only;`affected_action_indices` are NOT comparable across rounds. Step 0.B carry-over: surface them per-event but exclude from cross-round delta. |
| 5 | TRUE | Per-event payload field surveys(`round_events.py:264-391`):`check_result` carries `plan_digest + binding + engine`;`proof_frame_result` carries `support_digest + overlay_digest + binding_items + atom_verdicts`. NO field exposes `module_id` or any module-level identity. `plan_digest` exists for some non-ProofFrame kinds,while ProofFrame's closest identity is `support_digest`;neither is a module identity. Per Batch 6 Step 0.A #12 carry-over,this is "Batch 7's responsibility — if needed key not derivable,Batch 7 adds mapping/index". | L5 cross-run aggregation cannot use `module_id`. Options:(a)per-kind aggregation by existing event-specific identity,(b)suspend L5,(c)defer L5 with module-mapping reactivation trigger. Selected (c) — defer L5 from first slice. |
| 6 | TRUE | Persisted payload shapes vary per kind. Common fields:`plan_digest + binding`(4 of 5: check / diagnose / fact_overlay / why_not). `proof_frame_result` has NO `plan_digest`;identity is `support_digest + overlay_digest + binding_items + atom_verdicts`. No common grouping key across all 5 kinds. | L5 aggregation cannot be one-grouping-key-fits-all. Combined with #5,reinforces L5 deferral from first slice. |
| 7 | FALSE | Frontier event family is projection-only(no verdict);rule-action event families carry `variant_rows + nested ProofFrame`. Neither is necessary for L4 per-frame ProofFrame diff over `proof_frame_result` rows. Some L5 aggregation use cases would need them,but L5 is deferred. | L4 first slice can ship without deferred Batch 6 §5.5.4 families. Document deferral with reactivation trigger. |
| 8 | TRUE(borderline) | Per the §5.1 #8 test condition:diff DTO(input: 2 frame identities;output: per-atom delta)and aggregation DTO(input: N rounds + group key;output: counts per group)share only generic round/event identity plus possibly event-specific payload keys(`support_digest` for ProofFrame,`plan_digest` for some non-ProofFrame kinds);output fields are mostly disjoint(per-atom delta lists vs group counts). Combined with #5/#6 L5 blockers,split is preferred. | First slice = L4 only(NARROWED Path A,not full Path C). L5 deferred without opening a parallel child blueprint;same precedent as Batch 6 §5.5.4 Frontier/rule-action deferrals. If Step 0.B finds the L4 DTO must carry aggregation-shaped fields,escalate to Path C. |
| 9 | FALSE | Aggregation index is a derived view over raw rows. No correctness-only use case;index would be a performance optimization. | No durable index in Batch 7. Aligns with Batch 6 Step 0.A #12 carry-over. |
| 10 | FALSE | Audit packages typically carry thousands of events,not millions. Linear scan over `AuditPackageData.round_events`(in-memory tuple)is acceptable. No measured performance issue. | Query-derived. Performance index is post-Batch-7 follow-up if measured need emerges. |
| 11 | FALSE | `proof_frame_result.payload.result.atom_verdicts`(`round_events.py:382-388`)carries `atom_key + verdict + affected_action_indices`. Per-atom verdict-change diff and frame-level status diff both compute purely from these projected fields;no raw `SupportArtifact` access required. | Diff scope = persisted ProofFrame projections only. No `SupportArtifact` lookup;no proof-tree-internals access. |
| 12 | TRUE | `RoundSummary.is_finalized` is True iff a `round_finalized` event is present(`round_events.py:summarize_round_events`,line 449-481). Partial rounds may be in-flight or crashed;atom_verdicts in such rounds are non-final. Cross-round diff between partial rounds risks comparing transient state. | Step 0.B default policy:require `is_finalized == True` on both rounds;opt-in flag to include partial rounds with explicit warning. |
| 13 | FALSE | `round_event_from_row`(post-hardening at `round_events.py:240-256`)downgrades `schema_version >= "2.0"` rows to `future:{kind}` namespace. Aggregation that filters by kind naturally skips them. | Diff filters by `kind == "proof_frame_result"` and skips `future:proof_frame_result`. Skipped count surfaced via Step 0.B-defined query method. |
| 14 | FALSE | Batch 7 capability is read-only over audit packages. Demo can be a notebook(e.g. `examples/12_evidence_diff_demo.ipynb`)or Python script reading a sample audit package and invoking new `AuditQuery.diff_proof_frames(...)`. No SDK route or service endpoint needed. | Demo as kernel-level notebook fixture. Same pattern as `examples/11_capabilities_e2e_demo.ipynb`(which still has the deferred Batch 4-6 demo gap). |
| 15 | FALSE | RuleRef-bearing artifacts produce `ProofFrameRecheckResult(status="unknown", atom_verdicts=())` per Batch 4 archive §11 Outcome(`status="unknown"` + empty `atom_verdicts`). Diff over such frames:status `unknown → unknown` or unknown → still_valid at frame level;empty `atom_verdicts` on both sides → degenerate per-atom diff with 0 atoms. Frame-level diff still works;per-atom diff is degenerate(not wrong). | Reject path:per-atom diff for RuleRef-bearing frames returns empty atom delta with explicit `rule_refs_unsupported` marker. Frame-level status diff still emits. Don't bundle Batch 4 hardening into Batch 7. |
| 16 | FALSE | Concrete consumers of L4 diff:(a)regression detection("did the latest rule edit invalidate previously-passing bindings?"),(b)audit / forensics("did this overlay action change proof X?"),(c)Batch 8 SDK consumer("before / after comparison view"). Without L4 diff,users compare narratives manually OR pull raw events and diff in user code. L4 diff reduces user effort and provides typed structured output. | L4 diff is foundation;Batch 8 may build user-facing wrapper. Not a vanity wrapper of Batch 4 narrative;real reduction in user effort. |

#### 5.5.2 Path Selection: Path A (narrowed first slice = L4 per-frame ProofFrame diff only)

Selected **Path A with first slice narrowed to L4 per-frame ProofFrame diff over `proof_frame_result` events**. L5 cross-run aggregation deferred from first slice.

Rationale tied to falsifier verdicts:
- L4 feasibility:#1 / #2 / #3 FALSE(frame identity stable via `(support_digest, binding_items)`;atom_key stable within the same `support_digest`),#11 FALSE(atom_verdicts sufficient),#15 FALSE(RuleRef degenerate but not blocking),#16 FALSE(real consumer value).
- L5 blockers:#5 TRUE(no `module_id` derivable),#6 TRUE(kinds don't share grouping key),#8 TRUE-borderline(DTO shapes mostly disjoint).
- Path B(full suspend)not justified — L4 itself is shippable with clear consumer value(#16 FALSE).
- Path C(full split into two simultaneous child blueprints)is heavier ceremony than necessary because this blueprint now ships only the L4 side. L5 is not partially implemented;it is deferred with explicit reactivation triggers,matching Batch 6 §5.5.4 precedent(Frontier + rule-action event families deferred at first slice). If Step 0.B forces L4 DTOs to carry L5-shaped fields,Path C becomes mandatory.

Path A constraints that must hold throughout implementation:
- L4 per-frame ProofFrame diff is the ONLY first-slice capability;L5 explicitly deferred per §5.5.3 #11.
- Read-only over `AuditPackageData.round_events`;no new durable files;no schema rewrite.
- AuditQuery extension via new methods on round-event namespace;existing methods byte-stable.
- No application runtime imports `kernel.audit`(per Batch 6 Step 0.A #13 boundary).
- Diff scope = same `support_digest` only(per #3 caveat);no cross-artifact atom-key comparison in first slice.
- Partial rounds rejected by default with opt-in flag(per #12).

Path A kill criteria(revisit Path C if any fire during Step 0.B):
- DTO design surfaces additional disjoint output fields beyond per-atom delta + frame status delta — would push toward formal Path C split.
- Per-atom diff for RuleRef-bearing frames cannot be made non-misleading even with the `rule_refs_unsupported` marker — would narrow further or escalate.
- Diff implementation would need to import any `kernel.application` runtime module — would violate Batch 6 Step 0.A #13 boundary.

#### 5.5.3 Constraints Frozen for Step 0.B

These Step 0.A decisions are now FROZEN inputs to Step 0.B and must not be relitigated:

1. Path A first slice = L4 per-frame ProofFrame diff over `proof_frame_result` events;no L5 in first slice.
2. Frame identity = `(support_digest, binding_items JSON)` where `binding_items` uses `project_binding_items` byte-equality.
3. Atom diff identity = `atom_key` scoped by same `support_digest`.
4. Diff scope = same `support_digest` only;no cross-artifact atom-key comparison in first slice.
5. Action indices NOT compared across rounds(only verdicts);per #4 TRUE.
6. Diff input cardinality = bilateral(`A vs B`);no multi-variant baseline in first slice.
7. Partial rounds rejected by default(`is_finalized == True` required on both rounds);opt-in flag with explicit warning to include partial.
8. RuleRef-bearing frames → degenerate per-atom diff with explicit `rule_refs_unsupported` marker;frame-level status diff still emits.
9. Read-only over `AuditPackageData.round_events`;no durable index file;no Batch 6 schema amendment.
10. AuditQuery extension via new `diff_*` methods on round-event namespace;existing methods byte-stable.
11. L5 cross-run aggregation deferred. Reactivation requires a fresh blueprint that proves one of two concrete inputs:(a)a module-level consumer plus a durable module-mapping mechanism,or (b)a per-kind aggregation first slice with explicit grouping keys for every included event kind. Vague "module_id later" language is not enough.

Step 0.B remaining decisions(per §5.4 carry-overs not yet frozen by Step 0.A):
- Diff DTO field-by-field shape(frame delta + per-atom delta lists + per-frame metadata).
- Diff status vocabulary(e.g. `frame_status_changed` / `atom_added` / `atom_removed` / `atom_verdict_changed` / `unchanged`).
- Empty / degenerate handling:frames missing in one round(added vs removed),frames with empty `atom_verdicts`(RuleRef + ProofFrame `unsupported`-equivalent both produce empty).
- AuditQuery method signatures(single `diff_proof_frames(round_a, round_b, ...)` vs split methods per cardinality).
- Test / drift gates list(round-trip equality,partial-round rejection,AuditQuery byte-stability,application-runtime no-`kernel.audit` import,RuleRef degenerate handling,unknown-kind skip).
- Demo artifact scope(notebook fixture vs Python script).
- L5 reactivation documentation location(carry to anchor `project_round_story_completion_plan_scoped.md` deferred section,or new follow-up anchor file).

#### 5.5.4 Acceptance §7 Update

Step 0.A satisfies §7 row 1("Step 0.A records all 16 falsifiers with source-grounded answers"). Status remains `draft` in this commit;a separate scope-freeze commit transitions to `scoped` after Step 0.B completes.

### 5.6 Step 0.B Spike (synthesized 2026-05-06)

This spike freezes the 7 §5.5.3 carry-overs. First slice = L4 per-frame ProofFrame diff per §5.5.2 Path A;L5 deferred per §5.5.3 #11.

#### 5.6.1 Diff DTO Shape

All DTOs are frozen dataclasses in `src/kernel/audit/proof_frame_diff.py`(new module). Shape grounded in §5.5.3 frozen identity:

```
ProofFrameDiff:
  round_a_id: str
  round_b_id: str
  frame_deltas: tuple[FrameDelta, ...]
  warnings: tuple[WarningDTO, ...]           # partial-round opt-in,future-kind skip,etc.

FrameDelta:
  frame_identity: FrameIdentity
  source_a: EventReference | None            # None if frame_added
  source_b: EventReference | None            # None if frame_removed
  frame_status_change: FrameStatusChange | None    # None if both sides have same status
  atom_deltas: tuple[AtomDelta, ...]
  markers: tuple[FrameMarker, ...]           # see §5.6.2

EventReference:
  round_id: str
  sequence: int

FrameIdentity:
  support_digest: str
  binding_items: tuple[tuple[str, JSONValue], ...]    # canonical sorted

FrameStatusChange:
  before: ProofFrameStatus | None            # None if frame_added
  after: ProofFrameStatus | None             # None if frame_removed

AtomDelta:
  atom_key: str
  kind: AtomDeltaKind
  before_verdict: ProofFrameStatus | None    # None for atom_added
  after_verdict: ProofFrameStatus | None     # None for atom_removed
```

Type aliases:
- `ProofFrameStatus = Literal["still_valid", "invalidated", "unknown"]`(reused from `kernel.application.protocol.proofframe`).
- `AtomDeltaKind = Literal["atom_added", "atom_removed", "atom_verdict_changed"]`.
- `FrameMarker = Literal["rule_refs_unsupported"]`(extensible in future schema versions).

`affected_action_indices` is NOT carried in `AtomDelta` per §5.5.3 #5(action indices are per-event and not cross-round comparable).

`ProofFrameDiff` intentionally has no `generated_at_ns` field. The diff is a deterministic derived view over persisted round events; adding a query-time timestamp would make equality tests and cache keys unstable without improving audit provenance. Callers needing timestamps can read source event timestamps through `EventReference`.

#### 5.6.2 Status Vocabulary

Frame-level state is derived from `(source_a, source_b, frame_status_change)`:

| State | Encoding |
|---|---|
| `frame_added` | `source_a=None, source_b=set, frame_status_change=None or set` |
| `frame_removed` | `source_a=set, source_b=None, frame_status_change=None or set` |
| `frame_status_changed` | both sources set,`frame_status_change` set |
| `frame_unchanged` | both sources set,`frame_status_change=None`,`atom_deltas=()`. Omitted from `frame_deltas` by default;included only when `include_unchanged=True`. |

Atom-level kinds(`AtomDelta.kind`):
- `atom_added`:`before_verdict=None`,`after_verdict` set
- `atom_removed`:`before_verdict` set,`after_verdict=None`
- `atom_verdict_changed`:both verdicts set,`before_verdict != after_verdict`

Unchanged atoms are NOT included in `atom_deltas` by default. There is no `atom_unchanged` kind;omission carries the same meaning.

Frame markers(`FrameMarker`)are carried as `markers: tuple[FrameMarker, ...]`:
- `rule_refs_unsupported`:emitted when either side has empty `atom_verdicts`(Batch 4 RuleRef-bearing artifact;`status="unknown"` + `atom_verdicts=()` per Batch 4 archive §11 Outcome). Implies `atom_deltas=()` regardless of frame status.

#### 5.6.3 Empty / Degenerate Handling

| Condition | FrameDelta encoding |
|---|---|
| Frame in A only(matched by `(support_digest, binding_items)` in A,not in B) | `source_a=set, source_b=None, frame_status_change=None, atom_deltas=(), markers=()` |
| Frame in B only | `source_a=None, source_b=set, frame_status_change=None, atom_deltas=(), markers=()` |
| Both rounds,both sides have empty `atom_verdicts`(RuleRef on both) | `markers=("rule_refs_unsupported",), atom_deltas=()`;`frame_status_change` set if `status_a != status_b`,else None |
| Both rounds,one side empty `atom_verdicts`(mixed RuleRef vs non-RuleRef for same `(support_digest, binding_items)`) | `markers=("rule_refs_unsupported",), atom_deltas=()`(cannot reliably diff atoms when one side has none);`frame_status_change` set if statuses differ |
| Both rounds,both populated,same atom set + same verdicts + same frame status | Frame omitted from `frame_deltas` unless `include_unchanged=True` |
| Both rounds,both populated,frame status flipped + per-atom verdict changes | `frame_status_change` set;`atom_deltas` lists changed atoms |
| Both rounds,both populated,atom set differs | `atom_deltas` lists `atom_added` / `atom_removed` per side |

#### 5.6.4 AuditQuery Extension

Single new method on `AuditQuery`:

```python
def diff_proof_frames(
    self,
    round_a: str,
    round_b: str,
    *,
    include_partial: bool = False,
    include_unchanged: bool = False,
) -> ProofFrameDiff:
    ...
```

Behavior contract:
- Validates `round_a` / `round_b` are non-empty strings present in `self.package.round_events`;raises `AuditQueryError` if missing.
- Loads `proof_frame_result` events for each round from `self.package.round_events`.
- Skips `future:proof_frame_result` events;emits one `WarningDTO(code="DIFF_FUTURE_KIND_SKIPPED", details={"round_id": ..., "skipped_count": N})` per round with skips.
- If `include_partial=False` and either round has `RoundSummary.is_finalized=False`,raises `AuditQueryError("round X is not finalized")`.
- If `include_partial=True` and either round is partial,emits `WarningDTO(code="DIFF_INCLUDES_PARTIAL_ROUND", details={"round_id": ...})`.
- Pairs frames by canonical `(support_digest, binding_items JSON)` equality.
- Returns `ProofFrameDiff` with all matched + unmatched frames + warnings.

No single-frame filter method in first slice;callers filter `result.frame_deltas` in user code if needed.
Reactivation trigger for a dedicated single-frame method:Batch 8 SDK or a repeated internal caller needs a stable method that accepts `FrameIdentity` and returns one `FrameDelta | None`. Until then,the whole-diff method keeps the audit query surface smaller.

`AuditPackageData` gains no new fields. No new optional audit file. No durable index. Existing `AuditQuery` methods unchanged(byte-stable).

#### 5.6.5 Drift Gates

Mandatory Batch 7 implementation tests:

| ID | Coverage |
|---|---|
| T1 | Two rounds with identical 5 frames + identical atom_verdicts → `frame_deltas=()`(with `include_unchanged=False` default) |
| T2 | Frame in A only → `FrameDelta(source_b=None, ...)` |
| T3 | Frame in B only → `FrameDelta(source_a=None, ...)` |
| T4 | Status flipped,same atom set → `FrameDelta(frame_status_change=set, atom_deltas=...)` |
| T5 | Atom set differs(A has atom_x,B has atom_y)→ `atom_added` + `atom_removed` deltas |
| T6 | RuleRef-bearing frame both sides(both `atom_verdicts=()`)→ `markers=("rule_refs_unsupported",), atom_deltas=()` |
| T7 | Mixed RuleRef vs non-RuleRef same identity → `markers=("rule_refs_unsupported",), atom_deltas=()` |
| T8 | `include_partial=False` + partial round → raises `AuditQueryError` |
| T9 | `include_partial=True` + partial round → succeeds + `DIFF_INCLUDES_PARTIAL_ROUND` warning |
| T10 | `future:proof_frame_result` rows skipped + `DIFF_FUTURE_KIND_SKIPPED` warning per round |
| T11 | Existing `AuditQuery` methods byte-stable on package with `round_events`(carry from Batch 6 T4) |
| T12 | `kernel.application/*runtime*.py` contains ZERO import from `kernel.audit`(carry from Batch 6 T8) |
| T13 | `affected_action_indices` is NOT a field on any `AtomDelta` instance(per §5.5.3 #5) |
| T14 | Same `support_digest` + same `atom_key` → atoms paired correctly across rounds |
| T15 | Different `support_digest` → frames treated as separate(no cross-artifact comparison)per §5.5.3 #4 |
| T16 | Missing `round_id` in package → raises `AuditQueryError("round X not found")` |
| T17 | `include_unchanged=True` + same-status frame both populated → `FrameDelta` emitted with `frame_status_change=None, atom_deltas=()` |
| T18 | `ProofFrameDiff` has no `generated_at_ns`;same inputs produce equal DTOs across repeated calls |
| T19 | `source_a` / `source_b` are `EventReference` instances,not raw tuple aliases |

#### 5.6.6 Demo Artifact

New Python script `examples/12_evidence_diff_demo.py`(no notebook in first slice):
- Builds a minimal audit package with 2 rounds(`round-baseline` and `round-with-overlay`)using `start_round` / `record_round_event` / `finalize_round` from `kernel.audit.round_events`.
- Both rounds invoke `recheck_proof_frame(...)` on the same `SupportArtifact` with different `EvaluationOverlay` actions.
- Calls `AuditQuery(package).diff_proof_frames("round-baseline", "round-with-overlay")` and prints frame deltas via simple stringification.

Notebook integration with `examples/11_capabilities_e2e_demo.ipynb` is OUT of first slice(would couple Batch 7 to the deferred Batch 4-6 demo gap).

#### 5.6.7 L5 Reactivation Documentation Location

L5 reactivation triggers documented in two places:
1. Cross-session anchor `project_round_story_completion_plan_scoped.md` deferred items section:one-line summary referencing §5.5.3 #11 of the archived Batch 7 blueprint.
2. Batch 7 archived blueprint §10 Outcome / Deviations:full reactivation triggers per §5.5.3 #11 wording.

No new standalone anchor file. Keeps memory index lean per `MEMORY.md` 200-line guidance.

#### 5.6.8 Acceptance §7 Update

Step 0.B satisfies §7 row 2("Step 0.B freezes diff and aggregation shape before status moves to `scoped`"). Status remains `draft` in this commit;a separate scope-freeze commit transitions to `scoped` after user approval of §5.6.

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

- [x] Step 0.A records all 16 falsifiers with source-grounded answers.
- [x] Step 0.B freezes diff and aggregation shape before status moves to `scoped`.
- [x] Implementation, if any, ships only after `Status: scoped`.
- [x] Per-frame diff tests cover unchanged, status-changed, atom-verdict-changed, missing-frame, and partial-round behavior selected by Step 0.B.
- [x] Cross-run aggregation remains deferred per §5.5.3 #11; future-kind skip behavior is tested for the L4 first slice.
- [x] Old audit packages without `round_events.jsonl` keep existing query behavior.
- [x] Existing `AuditQuery` methods remain unchanged.
- [x] No SDK/service/agent diffs.
- [x] No application runtime imports from `kernel.audit`.
- [x] No ProofFrame/rule-action protocol drift.
- [x] No Batch 6 event-family expansion unless Step 0 explicitly scopes it.
- [x] Module docs updated after implementation.
- [x] Blueprint Outcome/Deviations completed and archived after implementation or suspension.

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

- Final result: implemented Batch 7 L4 ProofFrame diff as a read-only audit query surface over Batch 6 `round_events`.
- Shipped scope:
  - new `src/kernel/audit/proof_frame_diff.py` DTO/diff module with `ProofFrameDiff`, `FrameDelta`, `FrameIdentity`, `EventReference`, `FrameStatusChange`, and `AtomDelta`;
  - `AuditQuery.diff_proof_frames(round_a, round_b, include_partial=False, include_unchanged=False)`;
  - deterministic frame identity via `(support_digest, binding_items JSON)` and atom identity via `atom_key` scoped by the same `support_digest`;
  - RuleRef / unsupported-equivalent marker `rule_refs_unsupported`;
  - future-kind and partial-round warnings;
  - `examples/12_evidence_diff_demo.py`;
  - audit module docs updated.
- Deviations from scoped blueprint:
  - none.
  - L5 cross-run aggregation remains deferred per §5.5.3 #11; no durable aggregation index was added.
- Verification:
  - `python -m unittest src.kernel.tests.test_audit_proof_frame_diff src.kernel.tests.test_audit_round_events src.kernel.tests.test_provenance_timeline_audit_delivery src.kernel.tests.test_evidence_graph_audit_delivery src.kernel.tests.test_audit_optional_domains`
  - `python -m unittest discover -s src/kernel/tests -p "test_*.py"` → 1288 OK / 1 skipped
  - `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py examples/12_evidence_diff_demo.py`
  - `git diff --check`
  - static guard: no `kernel.audit` import from application runtimes; no SDK/service/agent/ProofFrame/rule-action/ArtifactSidecar drift.
- Archive notes:
  - L5 aggregation reactivation requires a fresh blueprint proving a durable module-mapping mechanism or explicit per-kind grouping keys.
  - Batch 4 ProofFrame `rule_refs` symmetric hardening remains separately tracked and was not bundled into Batch 7.
