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
