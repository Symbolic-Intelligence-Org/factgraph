# Durable Round Persistence(Batch 6 of Round Story Completion Plan)

- Status: draft
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Related Modules:
  - `src/kernel/audit/`
  - `src/kernel/application/`
  - `src/kernel/adapters/souffle/package.py`
  - `src/kernel/core/store/_artifact_sidecar.py`
- Related Docs:
  - [Round Story Completion Plan](./2026-05-05_round-story-completion-plan.md) §5.6
  - [Application module overview](../../src/kernel/application/docs/01_overview.md)
  - [Audit module docs](../../src/kernel/audit/docs/01_overview.md)
  - [Audit package contract](../../src/kernel/audit/docs/03_audit_package_contract.md)
- Audit Log:
  - [2026-05-05_round-persistence.audit.md](./2026-05-05_round-persistence.audit.md)

## 1. Problem

Batch 0-5c now produce stable application-layer capability results for Check,Diagnose,Fact Overlay,Why-not,Frontier,ProofFrame,and rule actions. These results are still mostly transient Python objects or legacy audit-package rows.

Batch 6 must persist a round as a durable event log so Batch 7 can compute per-frame diffs and cross-run aggregation without re-running the original Python session. The parent plan asks for an L8 capability-event JSONL audit trail,round serialization/reload,and compatibility with existing `AuditQuery` / `load_audit_package`.

The main risk is a false merge:

- existing `kernel.audit` package rows describe accepted derivation candidates,provenance trees,rule traces,and package-level audit files;
- new capability events describe application runtime calls and their result surfaces;
- `ArtifactSidecar` persists support artifacts/rule traces by digest but is not a round event ledger;
- Batch 7 wants diff inputs,but Batch 6 must not implement diff or aggregation.

Step 0 must decide whether these can share one round-event schema or whether Batch 6 should suspend/abandon until a narrower persistence target is defined.

## 2. Goals

- Freeze a durable JSONL schema for application capability events selected by Step 0.
- Define a round package shape that can be serialized and reloaded.
- Keep existing audit package loading compatible,including old packages without round event logs.
- Add `AuditQuery` read APIs for the new event log only if Step 0 confirms they are truly query-layer responsibilities.
- Preserve stable result semantics from Batches 3-5c;do not reopen capability DTOs.
- Provide focused round-trip tests and drift gates that protect SDK/service/agent boundaries.

## 3. Non-goals

- No Batch 7 per-frame diff algorithm.
- No Batch 7 cross-run aggregation index.
- No public SDK/service route exposure.
- No Store ledger persistence semantics change.
- No mutation of support artifact digest semantics or `ArtifactSidecar` collision behavior.
- No ProofFrame protocol changes,including no revival of `superseded_by_full_eval`.
- No rule action DTO reshaping from Batch 5a/5b/5c.
- No backfill of the deferred Batch 4 ProofFrame `rule_refs` symmetric hardening.
- No replay that re-executes capabilities from persisted rows;Batch 6 persists observed results.
- No UI/static-site rendering work except docs saying how the rows can be read.

## 4. Current Context

### 4.1 Parent Plan

Round Story Completion Plan §5.6 says Batch 6 owns:

- capability-event JSONL schema(Check / Diagnose / Fact Overlay / Why-not / Frontier output + ProofFrame status);
- audit package serialization and reload of one round;
- compatibility with existing `AuditQuery` / `load_audit_package`;
- no L4 per-frame diff and no L5 cross-run aggregation.

### 4.2 Existing Audit Package

`kernel.adapters.souffle.package.export_package(..., ExportOptions(package_kind="audit"))` writes package files such as:

- `audit/run_ledger.jsonl`
- `audit/candidate_ledger.jsonl`
- `audit/accept_write_ledger.jsonl`
- `audit/decision_log.jsonl`
- optional support/rule trace/provenance/evidence graph/certainty/timeline JSONL files

`kernel.audit.reader.load_audit_package(...)` loads these into `AuditPackageData`;`AuditQuery` exposes run,candidate,evidence,provenance,and rule-trace queries over that package.

This is not yet a capability-event log. It is accepted-candidate/audit-package oriented.

### 4.3 Existing Artifact Sidecar

`ArtifactSidecar` stores `SupportArtifact` and `RuleTraceArtifact` payloads by digest/run id. It supports Store lookup and sidecar-backed recovery,but it is not ordered by capability call and does not carry round-level event semantics.

### 4.4 Stable Capability Result Surfaces

Batch 6 can depend on current application entrypoints as stable inputs:

- `check_derivation_binding(...)`
- `diagnose_derivation_binding(...)`
- `check_fact_overlay_binding(...)`
- `check_why_not_universe(...)`
- `build_frontier_view_facts(...)`
- `recheck_proof_frame(...)`
- `check_rule_disable_action(...)`
- `check_rule_literal_replace_action(...)`
- `check_rule_add_condition_action(...)`

Step 0 must decide which of these are in the first durable event set. Parent-plan wording mentions "Check / Diagnose / Fact Overlay / Why-not / Frontier output + ProofFrame status";rule action events were introduced after the parent plan and must be explicitly included,excluded,or deferred.

## 5. Step 0 Falsifiability

Step 0 must produce a source-grounded decision before scope freeze. It must not assume "all capability results can be one schema".

### 5.1 Falsifiability Checklist

| # | Falsifier | If true |
|---|---|---|
| 1 | A single event row cannot represent both result-bearing capabilities(Check/Diagnose/rule actions)and projection-only helpers(Frontier)without opaque payload blobs. | Split event families or narrow Batch 6 to result-bearing capabilities. |
| 2 | Persisting full result DTOs causes unstable or non-JSON payloads,or embeds Store/schema objects. | Require explicit JSON projection per capability;do not persist raw dataclasses. |
| 3 | Existing audit package rows already satisfy the Batch 7 inputs without new event rows. | Batch 6 may reduce to manifest/query compatibility only or suspend as premature. |
| 4 | Existing audit package rows and capability events have different lifecycle identities(package export vs application call)that cannot share one manifest namespace. | Add a separate optional `round_events` audit file rather than rewriting existing ledgers. |
| 5 | Rule action outputs need different event identity than Check/Diagnose because they carry an original-frame ProofFrame plus variant rows. | Define a distinct rule-action event kind or defer rule actions from Batch 6. |
| 6 | ProofFrame status alone is insufficient for Batch 7;per-atom verdicts are required now. | Persist ProofFrame summary plus atom verdict projection,or record Batch 7 entry criteria as blocked. |
| 7 | `AuditQuery` cannot expose round events without confusing existing run/candidate queries. | Add separate query methods and keep existing methods unchanged. |
| 8 | JSONL package reload cannot preserve event ordering deterministically without a stable sequence/id contract. | Step 0.B must freeze event id,sequence,and sort semantics before implementation. |
| 9 | Including request payloads would leak SDK/service objects or privacy-sensitive input. | Persist result summaries and stable references only;document request payload exclusion. |
| 10 | Round package writes would need to mutate `Store` or ledger state to be complete. | Abandon or narrow;Batch 6 must be write-package-only,not Store semantic persistence. |
| 11 | Backward compatibility with packages lacking `round_events.jsonl` requires invasive reader changes. | Reader must treat round events as optional;old package test is mandatory. |
| 12 | Batch 7 cannot consume the schema without aggregation-specific fields. | Do not add aggregation fields in Batch 6;record explicit Batch 7 carry-over instead. |
| 13 | Correct event ordering requires capability runtimes to emit events internally. | Treat this as a scope breaker unless Step 0 records a narrow hook;default is explicit recorder/wrapper outside capability runtimes. |
| 14 | A "round" cannot be modeled as an implicit time window and needs explicit lifecycle boundaries. | Step 0.B must freeze `start/end` or equivalent bracket semantics;do not infer rounds from timestamps. |
| 15 | Durable writes must be atomic-finalized rather than streaming append during in-flight capability calls. | Prefer buffered package finalization or document append semantics;Path B may be cleaner if atomicity cannot fit existing audit package layout. |

### 5.2 Candidate Paths

Step 0 must choose one of:

- **Path A — Narrow optional `round_events.jsonl` extension.**
  Add a new optional audit file in the existing package manifest and reader,with explicit event kinds and JSON projections for the selected capability results.

- **Path B — Separate round package distinct from legacy audit package.**
  Keep `load_audit_package(...)` stable and add a new `load_round_package(...)` style reader. This is valid if existing audit package semantics would be distorted by capability events.

- **Path C — Suspend/abandon Batch 6 as premature.**
  Use this if Batch 7's real diff inputs are not knowable yet,or if event-schema design collapses into opaque payload capture.

Default lean is Path A because the parent plan explicitly requires `AuditQuery` / `load_audit_package` compatibility,but Path A must fail if it requires rewriting existing ledgers or raw DTO blob persistence.

### 5.3 Step 0.B Carry-Overs

If Step 0.A chooses Path A or B,Step 0.B must freeze:

- event identity:round id,event id,sequence,timestamp/source fields;
- round lifecycle:explicit start/end bracket vs a narrower caller-supplied round id contract;
- event source mechanism:explicit recorder/wrapper vs runtime emit hook,with default no capability runtime imports from audit;
- write mode:buffered atomic finalize vs streaming append,including how partial writes are detected;
- event kind set:which capability results are first-slice events;
- payload projection per event kind:summary-only vs structured result projection;
- ProofFrame persistence:status only vs status + atom verdicts + narrative;
- rule action inclusion:defer vs include 5a/5b/5c result summaries;
- package layout:optional audit file vs separate package;
- reader/query surface:extend `AuditPackageData` and `AuditQuery` or add new reader class;
- old-package compatibility behavior;
- error handling for malformed event rows,duplicate event ids,and unknown future event kinds;
- test/drift gates.

### 5.4 Step 0.A Spike (synthesized 2026-05-06)

This spike answers §5.1 with source-grounded evidence and chooses among §5.2 paths. Evidence packs gathered from `kernel.audit`,`kernel.adapters.souffle.package`,`kernel.core.store._artifact_sidecar`,and the 9 application capability outputs(8 DTOs + 1 raw projection).

#### 5.4.1 Falsifier Verdicts

| # | Verdict | Source-grounded reason | Implication |
|---|---|---|---|
| 1 | TRUE | `build_frontier_view_facts` returns `dict[str,list[tuple[Any,...]]]`(`capability_helpers.py:207`)with no protocol DTO and no `status`;the other 8 entrypoints return verdict-bearing DTOs with explicit `status` enums. | Split event families;at minimum a verdict-bearing capability family for the 8,plus either a separate `frontier_projection` family or defer Frontier persistence to follow-up. |
| 2 | TRUE | Every result DTO carries non-JSON inner fields. `SupportArtifact`(`_support.py:97-127`)contains nested `PredWitness`/`NonFactStep`/`RuleRefEdge` frozen dataclasses,`BindingItems = tuple[tuple[str,Any],...]` with `Any`-typed values,and `DetailItems` of the same shape. All 9 result surfaces have at least one non-JSON inner field. | No raw `dataclasses.asdict()` blob persistence. Each event kind needs an explicit JSON projection helper that hex-encodes binding values,summarises nested artifacts,and uses stable digests for opaque structures. |
| 3 | FALSE | Existing audit package rows describe accepted derivation candidates and rule traces(`run_ledger`/`candidate_ledger`/`accept_write_ledger`/`decision_log`,`package.py:169-216`). They do not capture application capability call results. Batch 7 per-frame diff and cross-run aggregation need capability outputs,not acceptance ledgers. | Batch 6 must add new event rows;existing audit rows alone are insufficient. Path C(premature suspend)is not triggered by this falsifier. |
| 4 | TRUE(bounded) | Audit package rows are written at `export_package(...)` time after a Store derivation run(`package.py:573-584`);capability calls happen at any read-path moment with no Store run association. Different lifecycle identities. However sharing one package directory with manifest namespace separation(`manifest.json.paths.audit_files`,`package.py:320-358`)is feasible because the manifest already supports optional file additions. | Path A is feasible. Path B avoids cohabitation but loses `AuditQuery` reuse;default to Path A with explicit namespace separation in the manifest. |
| 5 | TRUE | Rule action result DTOs(5a/5b/5c)all carry `status + variant_rows: tuple[BindingItems,...] + proof_frame: ProofFrameRecheckResult \| None`(`rule_disable.py:80`,`rule_literal_replace.py:82`,`rule_add_condition.py:82`). Structurally distinct from Check(verdict only)and Diagnose(verdict + atom_locator). | Define distinct event kinds per capability family. Do not collapse rule-action events into the generic verdict shape. |
| 6 | TRUE | `ProofFrameRecheckResult` carries `status + binding_items + atom_verdicts: tuple[ProofFrameAtomVerdict,...]`(`proofframe.py:120-136`). Each `ProofFrameAtomVerdict` carries `atom_key + verdict + affected_action_indices`(all primitives). Batch 7 L4 per-frame diff requires atom-level granularity;status alone(3-way enum)cannot drive a diff. | ProofFrame projection must persist `status + atom_verdicts`(atom_key + verdict + affected_action_indices). `binding_items` requires hex-encoded value projection. |
| 7 | FALSE | `AuditQuery` is a stateless wrapper over frozen `AuditPackageData`(`query.py:55-61`);25+ public methods all keyed off `run_id`/`candidate_id`/`decision_id`. New round-event methods keyed off `round_id`/`event_id` would not collide with the existing namespace. | Extend `AuditQuery` with separate round-event query methods. Existing methods stay byte-stable. |
| 8 | TRUE | Existing JSONL ledgers carry `event_ts`(nanosecond int)but no sequence number;rows sorted at query time by `(event_ts,decision_id)`(`query.py:528-534`);duplicates allowed(no writer dedup). Two events with the same nanosecond timestamp would be order-ambiguous for replay. | Step 0.B must freeze `(round_id,sequence)` as primary identity with monotonic per-round sequence;`event_ts` becomes secondary metadata. |
| 9 | PARTIAL | Request DTOs carry kernel-level objects(`CompiledDerivationPlan`,`RuleSpec`,`SupportArtifact`,`BindingItems`)— no SDK/service classes. However `BindingItems` values are `Any` and caller-controlled;they may contain raw user-input strings or sensitive references. | Persist result summaries plus stable references(digests of plan/rule_spec;bindings projected via existing hex encoding for known kernel value types). Document in Step 0.B that binding-value privacy is the caller's responsibility. |
| 10 | FALSE | All 9 capabilities are read-path;no Store mutation,no ledger write(verified across runtime files). `ArtifactSidecar` writes are atomic and outside Store(`_artifact_sidecar.py:213-225`). Round persistence captures already-produced results. | Batch 6 stays write-package-only. No Store ledger semantics change. |
| 11 | FALSE | Reader iterates over OPTIONAL keys(`reader.py:99-111`):missing key in manifest or missing file returns empty list/dict gracefully. Adding `round_events` as an optional audit file follows this exact existing pattern. | Add new optional field on `AuditPackageData` defaulting to empty;old packages load unchanged. Old-package compat test mandatory in §7 acceptance. |
| 12 | FALSE | Aggregation is Batch 7's responsibility,not Batch 6's. Batch 6 persists per-call/per-frame fields(rule_id digest,atom_key,etc.);Batch 7 owns module/cross-run aggregation key derivation or mapping. Whether every needed group-by key is derivable from persisted fields is a Batch 7 question;if any are not,Batch 7 adds the mapping/index. | Batch 6 captures full per-call/per-frame output. Aggregation index files,group-by mapping,or cross-run derivation belong to Batch 7. Carry over:no aggregation index file in Batch 6;module_id and other group-by mapping defer to Batch 7 if needed. |
| 13 | FALSE | Zero runtimes import logger/recorder/audit/emit hooks(verified by agent search across all 9 runtime files). Internal emit would require `kernel.application` → `kernel.audit` import(boundary violation per §6). External recorder/wrapper at the application surface is feasible:caller invokes capability,then records the result. | Use explicit recorder/wrapper pattern. Capability runtimes do not import from `kernel.audit`. Boundary in §6 already encodes this. |
| 14 | TRUE | Existing audit package has no round/session concept;only `run_id` is auto-generated by Store per claim(`runtime.py:335`). Read-path capability calls have no Store run association. Without explicit bracket "round" is undefined;a time-window heuristic is fragile and not a contract. | Step 0.B must define `round_id` as caller-supplied(or via context manager `with start_round() as round:`). No timestamp-based inference. |
| 15 | TRUE | Existing audit package writer is NOT atomic(streams JSONL line-by-line per file;manifest written last;`package.py:573-584`). Streaming round events during in-flight calls would risk partial-round packages on crash with no atomic finalize signal. `ArtifactSidecar`'s tempfile + `os.replace` model demonstrates the atomic pattern. | Round write happens at round end via buffer-then-finalize;not streaming. Step 0.B carry-over:partial-round detection mechanism(e.g. finalize marker presence in manifest). |

#### 5.4.2 Path Selection: Path A

Selected **Path A — Narrow optional `round_events.jsonl` extension within existing audit package**.

Rationale tied to falsifier verdicts:
- Parent plan compatibility requirement(`AuditQuery`/`load_audit_package`)is met without a new reader class(#7 and #11 both FALSE — extension is clean).
- No fundamental block surfaced(#3,#10,#12 all FALSE — capability persistence is feasible).
- Lifecycle cohabitation feasible via optional file pattern(#4 TRUE-bounded — manifest supports namespace separation).
- Path B(separate package)would double maintenance and lose `AuditQuery` reuse without justification;triggered only if Path A's cohabitation breaks during Step 0.B.
- Path C(suspend/abandon)not justified;capability outputs are projectable(#2 TRUE but solvable via per-kind helpers)and persistence is feasible(#10 FALSE).

Path A constraints that must hold throughout implementation:
- `audit/round_events.jsonl` added as OPTIONAL audit file in the existing package layout.
- Write mode:buffer-then-finalize at round end(not streaming),per #15.
- Caller-supplied `round_id` with explicit lifecycle bracket,per #14.
- Per-event-kind JSON projection helpers,per #1/#2/#6.
- External recorder/wrapper at application surface;no capability runtime imports from `kernel.audit`,per #13(already encoded in §6).
- `AuditQuery` extended with new round-event methods;existing methods byte-stable,per #7.
- Old-package compat test mandatory,per #11.

Path A kill criteria(revisit Path B if any fire during Step 0.B):
- Manifest namespace separation cannot be achieved without renaming existing audit file keys.
- Atomic finalize cannot be implemented without rewriting the existing audit package writer.
- `AuditQuery` extension unavoidably collides with existing `run`/`candidate`/`decision` query namespace.

#### 5.4.3 Constraints Frozen for Step 0.B

These Step 0.A decisions are now FROZEN inputs to Step 0.B and must not be relitigated:

1. Path A is the selected working path for Step 0.B(optional `round_events.jsonl` in existing audit package);frozen unless a §5.4.2 kill criterion fires.
2. Distinct event KINDS per capability family;no unified verdict shape.
3. JSON projection per kind;no raw dataclass blob persistence.
4. Caller-supplied `round_id` with explicit lifecycle bracket;no time-window inference.
5. `(round_id,sequence)` as primary event identity;`event_ts` secondary.
6. Buffer-then-finalize at round end;no streaming during in-flight calls.
7. ProofFrame persistence shape:`status + atom_verdicts`(atom_key + verdict + affected_action_indices).
8. External recorder/wrapper at application surface;no capability runtime imports from `kernel.audit`.
9. `AuditQuery` extended via new round-event methods;existing methods byte-stable.
10. No aggregation index file in Batch 6;Batch 7 derives at query time.

Step 0.B remaining decisions(per §5.3 carry-overs not yet frozen by Step 0.A):
- Specific event identity field names and types(round_id,event_id,sequence,timestamp).
- Event kind set:which of the 9 capabilities are first-slice;whether Frontier is included.
- Exact payload projection per event kind(field-by-field schema).
- Rule action inclusion:defer or include 5a/5b/5c result summaries in the first slice.
- Reader/query surface details(method names,signatures,return shapes).
- Error handling for malformed event rows,duplicate event ids,unknown future event kinds.
- Test/drift gates list.
- Partial-round detection mechanism(finalize marker contract).

#### 5.4.4 Acceptance §7 Update

Step 0.A satisfies §7 row 1("Step 0.A records the 15 falsifiers with source-grounded answers"). Status remains `draft` until Step 0.B freezes the carry-overs above.

### 5.5 Step 0.B Spike (synthesized 2026-05-06)

This spike freezes the 8 §5.3 carry-overs plus the 8 §5.4.3 remaining decisions. First-slice scope is **S3(verdict + ProofFrame)** per user decision;rule actions and Frontier deferred per §5.5.4.

#### 5.5.1 Event Identity Fields

Every row carries:

| Field | Type | Notes |
|---|---|---|
| `round_id` | str | Caller-supplied at round start;opaque token,no inferred semantics. Required;non-empty. |
| `sequence` | int | Monotonic within a round,starts at 0,increments by 1 per event. Required. |
| `event_ts` | int | Nanosecond UTC timestamp;matches existing audit JSONL convention(`query.py:528-534`). Required. |
| `kind` | str | One of the 5 capability event kinds(§5.5.2)or `round_finalized`(§5.5.8). Required. |
| `schema_version` | str | Format `"<major>.<minor>"`;starts at `"1.0"`. Required. |

Primary identity is `(round_id, sequence)` per §5.4.3 #5. No separate `event_id` field;`event_id` is derivable as `f"{round_id}:{sequence}"` if downstream needs a single string.

#### 5.5.2 First-Slice Event Kind Set

S3 scope = 5 capability kinds + 2 lifecycle markers:

| Kind | Source |
|---|---|
| `round_started` | recorder lifecycle marker(§5.5.8;sequence 0) |
| `check_result` | `check_derivation_binding(...)` |
| `diagnose_result` | `diagnose_derivation_binding(...)` |
| `fact_overlay_result` | `check_fact_overlay_binding(...)` |
| `why_not_result` | `check_why_not_universe(...)` |
| `proof_frame_result` | `recheck_proof_frame(...)` |
| `round_finalized` | recorder lifecycle marker(§5.5.8;last sequence) |

Each round opens with `round_started` at sequence 0,emits capability events at sequences 1..N-1,closes with `round_finalized` at sequence N. `started_at` derives from `round_started.payload.started_at`,not from any capability event. This satisfies Step 0.A #14 explicit lifecycle bracket.

#### 5.5.3 Per-Kind Payload Projection

Each row has top-level identity fields(§5.5.1)plus a `payload: Mapping[str, object]` field. Below is the field-level shape per kind. All `BindingItems` projected to `list[[str, JsonValue]]` via stable JSON-projection helper(see §5.5.3.6 below). Plan / rule_spec / overlay / SupportArtifact stored as opaque digests only;impl resolves via existing sidecar / store.

**`round_started` payload:**
- `started_at: int`(nanosecond ts;equals `event_ts` of this row)

**`check_result` payload:**
- `request.plan_digest: str`
- `request.binding: list[[str, JsonValue]]`
- `request.engine: str`
- `result.status: str`(CheckStatus enum value)
- `result.requested_binding: list[[str, JsonValue]]`
- `result.matched_count: int | null`
- `result.matched_binding: list[[str, JsonValue]] | null`
- `result.evidence_envelope: {engine_payload_kind: str, payload_digest: str} | null`
- `errors: list[{code: str, message: str}]`
- `warnings: list[{code: str, message: str}]`

**`diagnose_result` payload:**
- `request.plan_digest: str`
- `request.binding: list[[str, JsonValue]]`
- `request.engine: str`
- `result.status: str`
- `result.requested_binding: list[[str, JsonValue]]`
- `result.matched_count: int | null`
- `result.matched_binding: list[[str, JsonValue]] | null`
- `result.failure_kind: str | null`
- `result.diagnostic_payload: {atom_key: str, attempted_binding: list[[str, JsonValue]]} | null`
- `errors`,`warnings` as above

**`fact_overlay_result` payload:**
- `request.plan_digest: str`
- `request.binding: list[[str, JsonValue]]`
- `request.overlay_digest: str`
- `request.engine: str`
- `result.status: str`
- `result.requested_binding: list[[str, JsonValue]]`
- `result.before: {status: str, matched_binding: list[[str, JsonValue]] | null} | null`
- `result.after: {status: str, matched_binding: list[[str, JsonValue]] | null} | null`
- `result.diff: {status_changed: bool, matched_count_delta: int, bindings_added: list[list[[str, JsonValue]]], bindings_removed: list[list[[str, JsonValue]]]} | null`
- `errors`,`warnings` as above

**`why_not_result` payload:**
- `request.plan_digest: str`
- `request.candidate_universe: list[list[[str, JsonValue]]]`
- `request.engine: str`
- `result.status: str`
- `result.requested_universe: list[list[[str, JsonValue]]]`
- `result.green: list[list[[str, JsonValue]]]`
- `result.red: list[{binding: list[[str, JsonValue]], diagnostic: {status: str, failure_kind: str | null, diagnostic_granularity: str, atom_locator: {branch_index: int, failed_atom_index: int, attempted_binding: list[[str, JsonValue]]} | null, errors: list[{code: str, message: str}], warnings: list[{code: str, message: str}]}}]`
- `errors`,`warnings` as above

**`proof_frame_result` payload:**
- `request.support_digest: str`
- `request.overlay_digest: str`
- `result.status: str`(one of `"still_valid"`,`"invalidated"`,`"unknown"`;no `superseded_by_full_eval`)
- `result.binding_items: list[[str, JsonValue]]`
- `result.atom_verdicts: list[{atom_key: str, verdict: str, affected_action_indices: list[int]}]`

**`round_finalized` payload:**
- `finalized_at: int`(nanosecond ts;equals `event_ts` of this row)
- `event_count: int`(total non-lifecycle events in this round)
- `kind_counts: {str: int}`(per-kind count for cross-checking)

**§5.5.3.6 BindingItems / value encoding:**

`JsonValue` is a stable JSON-projectable representation of a single binding value. Helper to be selected at impl time from existing kernel utilities;must round-trip primitive types(`int / float / str / bool / null / tuple of primitives`). Non-primitive values serialize as opaque digest reference. Impl phase to confirm coverage and document the helper choice in the audit log;Step 0.B does NOT freeze the helper identity,only the contract.

#### 5.5.4 Deferral Decisions

Out-of-first-slice and reactivation triggers:

| Deferred item | Reason | Reactivation trigger |
|---|---|---|
| `frontier_projection` event family | Frontier is projection-only(no status,no DTO);Step 0.A #1 TRUE → split family. | Demand for Frontier persistence emerges in Batch 7+,or Frontier gains a verdict-bearing wrapper. |
| `rule_disable_result` / `rule_literal_replace_result` / `rule_add_condition_result` | All three carry `variant_rows + nested ProofFrame`;designing rule-action schema before ProofFrame projection ships risks two competing schemas. | After `proof_frame_result` ships and projection schema is validated by at least one Batch 7 consumer;rule-action events then reuse `proof_frame_result` for the nested ProofFrame and add their own `rule_*_result` kind for `variant_rows`. |

These deferrals are NARROW first-slice scoping,not permanent exclusions. Future batches MAY add new event kinds without reopening Step 0;adding kinds is a forward-compatible reader operation per §5.5.6.

#### 5.5.5 AuditQuery Extension

New methods on `AuditQuery`(separate namespace from existing `run` / `candidate` / `decision` methods):

| Method | Return |
|---|---|
| `list_rounds() -> tuple[str, ...]` | All `round_id` values in package,sorted by first `event_ts`. |
| `list_round_events(round_id: str, *, kind: str \| None = None) -> tuple[RoundEvent, ...]` | All events for a round,optionally filtered by `kind`,sorted by `sequence`. |
| `get_round_event(round_id: str, sequence: int) -> RoundEvent \| None` | Single event by primary identity. |
| `get_round_summary(round_id: str) -> RoundSummary \| None` | Per-round summary:`event_count`,`kind_counts`,`started_at`,`finalized_at`,`is_finalized`,`sequence_gaps`. |
| `list_round_event_warnings() -> tuple[WarningDTO, ...]` | All warnings emitted by the lenient row reader while loading `round_events.jsonl`(§5.5.6). |

`RoundEvent` = frozen dataclass mirror of the JSON row:`(round_id: str, sequence: int, event_ts: int, kind: str, schema_version: str, payload: Mapping[str, object])`. No typed payload variants;consumers parse `payload` based on `kind`.

`AuditPackageData` gains two new fields:`round_events: tuple[RoundEvent, ...]` and `round_event_warnings: tuple[WarningDTO, ...]`,both defaulting to empty tuple for packages without `round_events.jsonl`. `round_event_warnings` carries warnings emitted by the lenient row reader for malformed or duplicate rows(§5.5.6).

No existing `AuditQuery` method signature or return shape changes(§5.4.3 #9).

#### 5.5.6 Error Handling

| Condition | Reader behavior |
|---|---|
| Malformed row(invalid JSON / missing required identity field) | Skip row;append `WarningDTO(code="ROUND_EVENT_MALFORMED", ...)` to package warnings. Do not crash. |
| Duplicate `(round_id, sequence)` | Keep first row encountered;skip subsequent;append `WarningDTO(code="ROUND_EVENT_DUPLICATE", ...)`. |
| Unknown `kind` value | Preserve row as `RoundEvent` with raw `payload`;list via `list_round_events()` so forward readers can opt in. Do not warn(forward compat is intentional). |
| Sequence gap(e.g. 0,1,3 missing 2) | Preserve as-is;`get_round_summary` exposes `sequence_gaps`. Do not warn. |
| Missing `round_finalized` row for a `round_id` | `RoundSummary.is_finalized = False`. Do not warn at load time(may be in-flight or crashed;caller decides). |
| `schema_version >= "1.0"` and `< "2.0"` | Best-effort projection. |
| `schema_version >= "2.0"` | Treat row kind as unknown. |

`round_events.jsonl` is loaded via a LENIENT row reader independent from the existing required-ledger `_read_jsonl`(which raises on invalid JSON). The lenient reader skips malformed or duplicate rows and emits `WarningDTO` entries to `AuditPackageData.round_event_warnings`(§5.5.5);it never raises on individual row failures.

#### 5.5.7 Drift Gates Test List

Mandatory Batch 6 implementation tests:

| ID | Coverage |
|---|---|
| T1 | Writer:round of all 5 first-slice capability kinds plus `round_started` and `round_finalized` → JSONL rows match field-level schema(§5.5.3). |
| T2 | Round-trip equality:writer output → reader → all event fields equal. |
| T3 | Old audit package without `round_events.jsonl` loads cleanly with empty `round_events`. |
| T4 | Existing `AuditQuery` methods byte-stable on packages with and without `round_events.jsonl`. |
| T5 | Malformed row → skip + `ROUND_EVENT_MALFORMED` warning. |
| T6 | Duplicate `(round_id, sequence)` → keep first + `ROUND_EVENT_DUPLICATE` warning. |
| T7 | Unknown event kind → preserved as `RoundEvent` with raw `payload`,no warning. |
| T8 | `kernel.application/*runtime*.py` contains ZERO import from `kernel.audit`(static scan,defends Step 0.A #13). |
| T9 | Every emitted row has `schema_version` field. |
| T10 | Round without `round_finalized` row → `RoundSummary.is_finalized == False`. |
| T11 | Recorder rejects write with missing or empty `round_id`. |
| T12 | Recorder rejects out-of-order sequence(must equal `last_sequence + 1`). |
| T13 | Atomic finalize:`finalize_round(...)` writes JSONL via tempfile + `os.replace`(matching `_artifact_sidecar.py:213-225`);crash before finalize → no `round_events.jsonl` change. |
| T14 | Round must open with `round_started` at sequence 0;recorder rejects `record(...)` or `finalize_round(...)` before `start_round(...)` is called. |
| T15 | `round_finalized.payload.event_count` equals the count of capability-kind events(non-lifecycle)in the round. |

#### 5.5.8 Partial-Round Detection

Mechanism:

- `round_finalized` event is emitted by recorder at `finalize_round(round_id)`.
- It is the LAST event of the round(highest sequence number).
- Its `payload` carries `event_count` and `kind_counts` for cross-checking.
- Reader determines round-finalization status by scanning rows:`is_finalized = any(e.kind == "round_finalized" for e in events)`.

No separate manifest file,no file-level finalize marker. The marker IS an event row(simplest forward-compat,zero new file types,easy for old readers to ignore).

If a process crashes mid-round under the default(buffered)mode:recorder buffers in memory,buffer is lost,zero rows reach disk,no partial round on disk. **Partial flush API is deferred from Batch 6**;default mode is buffered atomic finalize at round end. If long-running rounds need incremental durability,a separate post-Batch-6 hardening will introduce a partial-flush contract;such follow-up MUST also define how the missing-`round_finalized` reader behavior interacts with intentional partials.

#### 5.5.9 Acceptance §7 Update

Step 0.B satisfies §7 row 2("Step 0.B freezes Path A/B/C and all carry-over decisions before implementation"). Status remains `draft` in this commit;a separate scope-freeze commit transitions status to `scoped` after user approval of §5.5.

## 6. Boundaries And Invariants

- Existing `load_audit_package(...)` must continue loading old audit packages.
- Existing required audit files stay required;new round events must be optional unless Step 0 chooses a separate package.
- `AuditQuery.list_runs(...)`,candidate,evidence,provenance,and rule-trace APIs must not change behavior.
- No import from SDK/service/agent into `kernel.audit` or `kernel.application`.
- No Store ledger writes,no support cache mutation,no sidecar write required while serializing a round.
- No application capability runtime imports from `kernel.audit` unless Step 0 explicitly records an inversion-safe hook;default is audit owns serialization of already-produced results.
- No raw dataclass `repr` persistence;event rows must be JSON objects with version/kind fields.
- Unknown future event kinds should be skipped or exposed as raw rows according to Step 0.B,not crash old readers.
- Batch 4 deferred ProofFrame `rule_refs` hardening remains out of scope.

## 7. Acceptance

- [ ] Step 0.A records the 15 falsifiers with source-grounded answers.
- [ ] Step 0.B freezes Path A/B/C and all carry-over decisions before implementation.
- [ ] JSONL schema is documented with version,kind,identity,and payload projection.
- [ ] Round serialization/reload passes round-trip tests for the selected first-slice event set.
- [ ] Old audit packages without round events still load.
- [ ] `AuditQuery` compatibility tests show existing methods unchanged.
- [ ] If `AuditQuery` grows new methods,they are separate from existing run/candidate/evidence APIs.
- [ ] No SDK/service/agent changes.
- [ ] No Store ledger or `ArtifactSidecar` semantic changes.
- [ ] No ProofFrame protocol or rule-action protocol drift.
- [ ] No Batch 7 diff/aggregation code.
- [ ] Module docs under `src/kernel/audit/docs/` and `src/kernel/application/docs/` are updated if implementation ships.
- [ ] Archive blueprint/audit and update archive inventory after implementation.

## 8. Implementation Plan

1. Step 0.A:answer §5.1 and choose Path A/B/C.
2. Step 0.B:freeze schema,package layout,reader/query surface,and event-kind set.
3. Scope transition:change status to `scoped` only after Step 0 is recorded.
4. Protocol/schema module:implement event row normalization and JSON projection helpers selected by Step 0.
5. Writer/package integration:write selected JSONL rows without mutating Store or capability runtimes.
6. Reader/query integration:load optional rows and expose query API selected by Step 0.
7. Tests:round-trip,old package compatibility,malformed rows,duplicate ids,drift gates.
8. Docs:update audit/application docs and any durable docs index.
9. Close-out:Outcome/Deviations,archive blueprint/audit,update archive README.

## 9. Docs To Update

- `src/kernel/audit/docs/01_overview.md`
- `src/kernel/audit/docs/03_audit_package_contract.md`
- `src/kernel/application/docs/01_overview.md` if application result surfaces are described as persistable
- `docs/blueprints/archive/README.md` after archive

## 10. Outcome / Deviations

To be filled after implementation or abandonment:

- Final result:
- Deviations:
- Verification:
- Archive note:
