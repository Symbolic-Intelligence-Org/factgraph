# Audit Log: B3 Load Test Runner — Commit Path Wiring

## 2026-04-11 — Initial draft (escalated from commit_path_plan working tracker)

### Trigger

B3 load test runner has had a stubbed commit path since iter 1. Every B3 canonical run (iter 4, iter 5, β.1, format coverage — 10 distinct samples) has produced `bundle.committed_count = 0` and `bundle.preview_only = true` because the runner never opens a runtime session, binds it, or calls any commit operation.

After format coverage closed on 2026-04-11 with verdict Option Y (parser paths validated, no further prompt tuning), the reviewer flagged **runner commit path** as the next B3 priority. A working plan (`commit_path_plan_2026-04-11.md`) was opened to inventory the wiring gap.

The working plan's Step 1 inventory concluded:
- **Q1**: nothing structural is missing — all 9 required components exist in the agent layer
- **Q2**: 100% wiring, zero contract changes
- **Q3**: working-plan-sized (~40-50 lines in the runner only), no blueprint hallmarks present

Despite that classification, the reviewer **escalated to a blueprint** on 2026-04-11:

> "Step 1 的结论我认同: 这是 wiring, 不是 contract redesign. 但一旦进 Step 2, 就会把 runner 从 dry-run 扩到真实 commit, 跨到 `runtime/session/orchestrator/write` 这条执行链, 还涉及 ledger side effects. 按仓库规则, 这已经是需要 blueprint 的边界了."

See: [commit_path_plan_2026-04-11.md §5.1](../../references/working/load-test-2026-04-11/commit_path_plan_2026-04-11.md)

### Root cause of the escalation (not the root cause of the wiring gap)

Two blueprint-required triggers apply independently:

1. **Cross-module execution chain**: the commit path touches 6 agent-layer modules at runtime (`runtime_api`, `session`, `orchestrator`, `write_tools`, `draft_manager`, `bundle_manager`). Even though the code changes are all in one file (`run_load_test.py`), the execution flow crosses module boundaries. Repo rules treat this as a blueprint trigger regardless of code surface area.
2. **Side effects on persistent state**: commit writes to a ledger file. This is the first time the B3 runner will produce any persistent artifact beyond `run_records/*.json`. Even with per-run isolation, it is a new class of state mutation that deserves explicit scoping and acceptance criteria.

Either trigger alone would justify a blueprint; together they make it clearly required.

### Scope narrowing by the reviewer

The reviewer locked a narrow scope before the blueprint file was created:

> "开一个很小的 blueprint, 优先走 `ReadReviewOrchestrator.commit_bundle()` 路径"
>
> "scope 只包含:
> - `--commit` opt-in flag
> - `LocalRuntimeAPI` + `bind_runtime_session`
> - per-run isolated ledger path
> - runner teardown close
> - 1 个小样本 smoke test"
>
> "不做 manual loop, 除非实现时发现 orchestrator 缺关键 telemetry"

These 6 scope items map directly to CP-01 through CP-12 in the blueprint's frozen decisions table. The "manual loop only as CP-06 escalation clause" rule is preserved in CP-04.

### Frozen decisions (initial draft)

| # | Decision | Origin |
|---|----------|--------|
| CP-01 | Opt-in `--commit` CLI flag; dry-run stays default | reviewer scope item 1 |
| CP-02 | `LocalRuntimeAPI`, not `HttpRuntimeAPI` | reviewer scope item 2 + inventory §2.5 rationale |
| CP-03 | Per-run isolated ledger path (`{tempdir}/b3_commit_{run_id}.db`) | reviewer scope item 3 + escalation trigger #5 mitigation from commit_path_plan §3.3 |
| CP-04 | `ReadReviewOrchestrator.commit_bundle(bundle_id)` as commit entry point | reviewer explicit preference; matches agent-layer canonical pattern |
| CP-05 | Single-sample smoke test (default `medium_01_security`) | reviewer scope item 5 |
| CP-06 | Manual loop allowed only as fallback if orchestrator lacks critical telemetry; must be documented as CP-06a | reviewer explicit fallback clause |
| CP-07 | Zero changes to files under `src/factpy_kernel/` | runner-side-only scope |
| CP-08 | No new tests required (workflow test at agent layer is sufficient) | minimum surface area |
| CP-09 | Error handling populates existing `bundle.failed_breakdown` categories | reuses existing run_record schema |
| CP-10 | Runner patch scoped to `run_load_test.py` only; no new runner files | minimum surface area |
| CP-11 | `try/finally` teardown always closes runtime session | prevents leaks on mid-run failure |
| CP-12 | Acceptance is run_record state verification (`committed_count > 0`, `preview_only = false`, commit_note contains "committed") | verifiable without running any review pass |

### Explicit non-goals

- No `HttpRuntimeAPI` wiring
- No full 10-sample commit rerun
- No human review on committed drafts
- No persistent shared ledger
- No changes to `samples_manifest.yaml`, `test_schema_ir.json`, or any existing B3 sample / packet / report
- No changes to `generate_review_packet.py` or `format_coverage_generators/*.py`
- No `SYSTEM_PROMPT_TEMPLATE` change
- No `OBS-01` / `OBS-02` / `FUP-01` severity or status changes
- No new run_record schema fields
- No new observations filed unless the smoke test surfaces one
- No commit-mode reruns of iter 4 / iter 5 / β.1 / format coverage samples
- No schema-IR registration work (inherited from existing `LocalRuntimeAPI` path)

### Impact on other layers

| Layer | Impact | Reason |
|-------|--------|--------|
| Agent layer (`src/factpy_kernel/agent/`) | **None** | Read-only. The runner will call existing methods; it will not modify them |
| Kernel layer (`src/factpy_kernel/core/`) | **None** | Commit path is entirely at the agent/runner level |
| Runtime layer (`src/factpy_kernel/runtime/`) | **None** | `LocalRuntimeAPI` already wraps `runtime_v1` service helpers; no new wiring at the runtime layer |
| Service layer (`src/factpy_kernel/service/`) | **None** | HTTP service is untouched (HttpRuntimeAPI out of scope per CP-02) |
| B3 harness | **Runner patch only** | `run_load_test.py` is the only file modified |
| B3 samples | **None** | 10 existing samples stay as-is |
| B3 run_records | **One new smoke test record** | per CP-05 / CP-12 |
| Iter 4 / iter 5 / β.1 / format coverage artifacts | **None** | All frozen |
| `cross_run_observations.md` | **None** (unless smoke test surfaces something) | OBS-02 already captured what we know |
| Test suite | **None** (977 tests / 2 skipped unchanged) | CP-08 |

### Relationship to prior archived blueprints

This is the **first runner-layer blueprint** in the B3 line. Prior blueprints were all agent-side or kernel-side:

| blueprint | layer | scope |
|---|---|---|
| iter 3 `prompt-schema-alignment-fix` | agent (prompts.py + validator + tests) | structural prompt fix |
| iter 4 `prompt-residual-patterns-fix` | agent (prompts.py + tests) | structural example additions |
| iter 5 `prompt-semantic-grounding` | agent (prompts.py + tests) | semantic example additions |
| kernel `openai-strict-fix` | agent (llm.py + validation.py + tests) | response model fix |
| kernel `p0-production-readiness` | agent + kernel + runtime + service | production hardening |
| **commit-path (this)** | **runner only** | **runner wiring** |

This is structurally different from prior blueprints. Prior blueprints targeted the production pipeline; this one targets a test harness. The narrower scope is intentional and reflects the narrower goal.

### Pre-implementation baseline

- Full test suite: **977 tests, 2 skipped** (inherited from iter 5 archival state; unchanged by format coverage)
- Runner state: dry-run default, commit stub with `P-runner-002` observed_issue
- Runtime session count: zero persistent sessions ever opened by B3
- Ledger files produced by B3: zero (previously only in-memory `BundleManager` objects)

### Open questions at draft time (Q1–Q7)

Seven questions locked in blueprint §8. These are implementation-time questions that must be answered before the blueprint can be pushed from `draft` to `scoped`:

- **Q1**: `RuntimeBootstrapSpec.__init__` exact field list
- **Q2**: `AgentSession.bind_runtime_session(...)` exact signature
- **Q3**: `ReadReviewOrchestrator.commit_bundle(bundle_id)` return type + exception shape
- **Q4**: Partial-commit semantics of the orchestrator
- **Q5**: Smoke test sample choice (medium_01_security vs alternatives)
- **Q6**: `LocalRuntimeAPI.open_session(...)` ledger path config point
- **Q7**: Ledger verification path (is there a runtime-side read method, or do we use sqlite3 directly?)

None of these block `draft` status. All block the push to `scoped`.

### Review notes

This blueprint is proposed as a **single** wiring iteration with explicit escalation clauses (CP-06) rather than as a multi-iteration plan. The expectation is:

- **Happy path**: Step 1 signature verification succeeds, Step 2-6 runner patch is ~40-50 lines, Step 7 smoke test passes, blueprint archives as `implemented`
- **Single-deviation path**: one or two of Q1-Q7 surprises, audit log records the deviation, blueprint still archives as `implemented with deviations`
- **Escalation path**: a structural surprise (e.g., orchestrator doesn't exist at that import path, or `LocalRuntimeAPI` has a totally different shape) forces stopping Step 7 and opening a larger blueprint; this blueprint archives as `abandoned` with the reason recorded

The "abandoned" case is considered unlikely because the inventory plan (commit_path_plan) already verified the 9 required components exist in the agent layer. But it's listed for completeness.

### Status transitions

- 2026-04-11 — draft created based on commit_path_plan escalation verdict
- 2026-04-11 — **Q1-Q7 code read pass complete** (reviewer instruction: "answer Q1-Q7 before scope check"). All 7 open questions resolved via inspection of `src/factpy_kernel/tests/test_agent_l4c2_workflow.py` (setUp lines 45-94, reference test lines 159-193) and `src/factpy_kernel/agent/orchestrator.py` (commit_bundle source lines 388-513). No code execution performed. No `src/` files modified. Three CP decisions refined (CP-02, CP-03, CP-04, CP-05) and one new CP-13 added. Blueprint §3 "The Fix" sketch corrected to use verified signatures. See §Q1-Q7 findings below for details.
- 2026-04-11 — **First scope check returned 3 findings** (P1 + P1 + P2). Blueprint was NOT pushed to `scoped` because of internal inconsistencies between the pre-Q1-Q7 sketch and the post-Q1-Q7 refined CP decisions. All 3 findings fixed in place. See §Scope-check fixes (2026-04-11) below for details.
- 2026-04-11 — **`scope check` ready (v2)**: all 3 findings closed, blueprint internally consistent. Awaiting reviewer re-check.
- 2026-04-11 — **scoped**. Scope check v2 passed with no blocking findings. One non-blocking cleanup applied during the transition: §4 "New failure modes introduced" list item on per-draft partial commit was rewritten from "Unknown at draft time — needs implementation-time verification ... Listed as an open question in §8" to the Q4-resolved form "resolved by Q4 — `BundleCommitResult` explicitly exposes partial success ... scoped smoke test is NOT expected to exercise this branch". This aligns §4 with the already-resolved Q4 in §8. All 12 original CP decisions + CP-13 are locked. Zero open questions remain. Orchestrator facade path is confirmed; manual loop path (CP-06) is untouched escape-hatch-only. Next transition: `implementing` once the runner patch lands.
- 2026-04-11 — **implementing**. Runner patch applied to `run_load_test.py` per the §3.1.2 / §3.1.3 / §3.1.4 sketches. Patch shape: +400 lines (905 → 1305), zero deletions outside the commit-stub replacement. `dataclass` and `tempfile` imports added. New `CommitStack` dataclass + `_build_commit_stack(scope, schema_ir, commit_run_id)` helper added after `_build_bundle_preview_stack`. `_fill_bundle_preview` extended with 3 optional parameters (`committed_count`, `failed_count`, `failed_breakdown`) — existing dry-run call sites unchanged. `_run_single_sample` signature extended with `commit_stack: CommitStack | None = None`. Commit branch replaces the stub with the 4-call orchestrator sequence (CP-04) + AgentContractError handling + partial-commit detection per Q4 + optional CP-12 stdout `[commit_verify]` lines. `main()` builds commit_stack once per `--commit` invocation and wraps the per-sample loop in try/finally with 3 independent close calls (CP-11). Compile check passed. Full regression passed: **977 tests, 2 skipped** (exact match with iter 5 baseline — CP-07 held, zero diffs under `src/factpy_kernel/`). Next: smoke test.
- 2026-04-11 — **first smoke test failed**. Invocation: `--commit --sample medium_02_blueprint_backref`. Exit code **1**. Failure stage: `_build_commit_stack → open_runtime_session(open_dto)`, **before** any per-sample processing started. Root cause: the B3 provisional `test_schema_ir.json` has a top-level `_note` key (a self-describing annotation in place since iter 2) that the canonical runtime validator rejects with `"unexpected top-level keys: ['_note']; top-level structure is canonical"`. This failure mode was previously invisible because extraction path, dry-run bundle preview path, and staging path all treat schema_ir as an opaque dict without canonical validation. Only commit mode exercises the canonical runtime validator, so the first commit attempt was also the first time this mismatch surfaced. No run_record was written (failed before `_run_single_sample()` was called). Empty tempdir `/var/folders/.../T/b3_commit_b3commit_20260411T163857Z_froam1fe` was created by `mkdtemp` before the validator rejection; left on disk per CP-03 retention. No stderr WARNINGs (teardown skipped because `commit_stack is None` at the catch point). Classified as a blueprint deviation (not a blueprint bug) — Q1's "open_dto shape is `{schema_ir, ledger_path}`" answer was correct about shape but the inventory didn't probe schema content against the canonical validator.
- 2026-04-11 — **CP-14 deviation recorded** (see §2 frozen decisions table). Minimal runner-side fix: strip top-level `_`-prefixed metadata keys from `schema_ir` before constructing `open_dto`. Rationale for picking this over alternatives: (a) does NOT touch `test_schema_ir.json` which would pollute iter 4/5/β.1/format coverage historical baselines; (b) does NOT touch extraction path which already works with the unfiltered schema; (c) ~3-line change scoped to `_build_commit_stack()` only; (d) informatively narrow — if a second smoke test finds yet another validator error, that is decisive evidence that a larger schema-canonicalization blueprint is needed (option 4), not more patches. Per reviewer stop-rule: if second smoke attempt fails on a different validator stage, STOP the patch chain and escalate to option 4.
- 2026-04-11 — **CP-14 runner patch applied**. `_build_commit_stack()` now filters out `_`-prefixed top-level keys from schema_ir before constructing open_dto. Prints `[commit] CP-14: stripped non-canonical schema_ir metadata keys for open_dto: [...]` when the filter hits. Compile check passed. Full regression re-run: **977 tests, 2 skipped** (no change). Ready for second smoke test.
- 2026-04-11 — **Second smoke test failed**. Invocation: `--commit --sample medium_02_blueprint_backref` (same as first attempt). Exit code **1**. CP-14 filter applied correctly (stdout confirmed `stripped non-canonical schema_ir metadata keys for open_dto: ['_note']`). First validator error was cleared. But `open_runtime_session` rejected at a **different validator stage**: `"predicates[0].arg_specs[0].name must be non-empty string"`. Root cause: the B3 provisional `test_schema_ir.json` has 4 arg_specs (across 2 predicates) that lack `name` fields entirely — the exact same schema defect that iter 3 PS-01 patched at the prompt layer by synthesizing positional fallback names (`arg0`, `arg1`). The canonical runtime validator enforces the original constraint. This is a **second runtime canonicalization failure**, same error class (`kind: runtime`, same `open_runtime_session` entry point), different validator rule. Per reviewer stop-rule, **the patch chain halts here**.
- 2026-04-11 — **Stop-rule fired**. No CP-15 added. No further runner patches attempted. Reviewer's direction: close this blueprint as `implemented with deviations` and open a new schema-canonicalization blueprint (Option 4a — parallel canonical fixture). Rationale for NOT continuing patches: the schema has multiple non-canonical properties (`_note`, missing arg_spec names, possibly more) and the runner is not the right place to normalize them. Canonicalization belongs at the schema fixture layer, and the proper scope is a separate blueprint with its own scoping gate.
- 2026-04-11 — **implemented with deviations**. Runner wiring is complete and correct (all 14 CP decisions honored, including CP-14). Smoke test blocked by external schema non-canonicality, which is out of scope for this blueprint. `_build_commit_stack`, `CommitStack`, 4-call orchestrator sequence, teardown, CP-14 filter — all preserved as-is in the runner. Continuation: `2026-04-11_b3-schema-canonicalization.md` (Option 4a, parallel canonical fixture) — opens the new blueprint at `draft` status. Full Outcome / Deviations section filled in blueprint §9.
- 2026-04-11 — **archived**. Moved from `docs/blueprints/active/` to `docs/blueprints/archive/`. This blueprint is now historical rationale only.

### Scope-check fixes (2026-04-11)

Three findings from the first scope check were addressed in place. Each is documented here for audit trail.

**Finding 1 [P1]**: Stale implementation path — blueprint §3.2 still introduced `_build_commit_ledger_path(run_id)` as a single-file helper, and §5/§6/§7 still referenced `medium_01_security` / `sqlite3` inspection / single-ledger model, all of which conflict with the post-Q1-Q7 refined CP-03/CP-05/CP-12.

**Fix**:

- **§3.2 rewritten**: the stale `_build_commit_ledger_path(run_id)` helper was deleted. The rewritten §3.2 explicitly states "There is **no separate `_build_commit_ledger_path` helper**" and directs the reader to §3.1.2's `_build_commit_stack` which creates the per-run tempdir inline via `mkdtemp(prefix=f"b3_commit_{run_id}_")` containing both `ledger.db` and `burr.db`.
- **§5 Implementation Order rewritten**: Step 1 marked COMPLETE (Q1-Q7 already verified signatures), Step 3 dropped the stale `_build_commit_ledger_path` helper, Step 4 (now Step 3 in the new numbering) describes `_build_commit_stack` with all CP-13 dependencies, Step 6 (smoke test) now references `medium_02_blueprint_backref` with expected ~10 drafts, Step 6 removed "sqlite3 .tables / .schema" inspection language in favor of stdout `[commit_verify]` lines and the persistent tempdir.
- **§6 Acceptance Criteria rewritten**: smoke test entry now uses `medium_02_blueprint_backref`, removed the sqlite3 "valid SQLite file / rows in facts table" check, added the stdout `[commit_verify]` claim_count check and the `[commit] tempdir kept for inspection` stdout check. Runner section updated to remove the `_build_commit_ledger_path` line item and to explicitly state "No new run_record schema fields" + "query_claims verification results are printed to stdout only".
- **§7 Known Constraints rewritten**: points 2-3 rewritten to default to `medium_02_blueprint_backref` and explain why `medium_01_security` was demoted (too thin vs OBS-01 variance). Point 5 (per-run isolation) rewritten to reference "per-run tempdir" instead of single ledger file and to explicitly state CP-03 retention policy. Point 8 (partial commit) rewritten to reflect Q4 findings (explicit telemetry, not silent swallow). Point 9 added: clarifies that `query_claims` verification is stdout-only per CP-12 / non-goals alignment.

**Finding 2 [P1]**: Contradiction on run_record schema changes — non-goals said "No new run_record schema fields" but §3.1.3 proposed `record["commit_verification"]` as a new field.

**Fix**:

- **§3.1.3 commit branch rewritten**: removed `record.setdefault("commit_verification", {})[pred_id] = {...}` and replaced with `print(f"  [commit_verify] {sample['sample_id']} pred={pred_id} claim_count={len(claims)}", flush=True)`. This is strictly additive to stdout, no run_record diff.
- **Non-goals clause updated**: the existing "No new run_record schema fields" line was expanded to explicitly say "Any CP-12 `query_claims` verification (Q7) is logged to stdout only, NOT added as a new run_record field". This makes the "pick one" decision explicit and locks it in place.
- **CP-12 row unchanged**: the CP table description was not edited — it already correctly said "the runner may optionally call `kg_read_tools.query_claims(...)`" without specifying where the result goes. The §3.1.3 stdout logging is the concrete implementation of that optional call.
- **Decision recorded**: reviewer chose Option A (strict, stdout-only, no new field) over Option B (allow new field, update non-goals). Option A preserves the durable "no schema change" invariant that has held across every prior B3 blueprint (SG-07 / PR-07 / PS-07).

**Finding 3 [P2]**: Inconsistent ledger retention policy across 4 locations — non-goals said "deleted after the test succeeds", CP-03 said "left for OS cleanup", §3.1.4 teardown said "NOT deleted", Known Constraints said "cleanup is the OS's responsibility".

**Fix**:

- **Non-goals clause rewritten**: the stale "deleted after the test succeeds" line was replaced with "the per-run tempdir is left on disk after the run (success or failure) so that `ledger.db` and `burr.db` are available for post-mortem inspection. OS `/tmp` cleanup handles long-term accumulation. Matches the existing pattern of leaving `run_records/*.json` in place after runs."
- **§3.1.4 teardown comment rewritten**: the comment block after `close_runtime_session` now explicitly says "CP-03 retention policy: commit_tmpdir is intentionally NOT deleted" and adds a `print(f"[commit] tempdir kept for inspection: {stack.commit_tmpdir}", flush=True)` line for operator awareness.
- **§7 Known Constraints point 5**: updated to reference "per-run tempdir" (not single ledger file) and to explicitly reference the CP-03 retention policy. The "cleanup is the OS's responsibility" phrasing is retained because it is factually correct and aligns with CP-03.
- All 4 locations now agree: **tempdir is kept for inspection, OS handles long-term cleanup, pattern matches existing `run_records/*.json` retention**.

### Reviewer's fix-selection rationale (documented for audit trail)

**Finding 2**: reviewer explicitly chose Option A (strict, stdout-only) over Option B (allow new field). Quote from the reviewer's fix decision on 2026-04-11:

> "`commit_verification` 要么不进 run_record, 要么正式承认它是新增 schema field"

Option A preserves the durable "no new run_record schema fields" non-goal which has held across every prior B3 blueprint iteration. Option B would have required updating non-goals AND documenting a schema diff AND justifying why this blueprint is the one that crosses the line. Option A is the lower-risk choice and preserves B3 reproducibility.

**Finding 3**: reviewer flagged the inconsistency but did not specify which resolution to pick. Blueprint author chose "kept for inspection" alignment based on:

- Post-mortem value if smoke test fails (ledger available for manual sqlite3 inspection after the fact)
- Matches existing pattern of leaving `run_records/*.json` on disk
- Explicit deletion adds code surface that could fail (file locked during teardown)
- OS `/tmp` cleanup handles long-term accumulation
- Format coverage plan's `samples/medium/medium_04_pdf_security.pdf` and similar binary artifacts are also left in place after generation — matches pattern

If reviewer prefers the opposite alignment ("delete after success, keep only on failure"), this decision can be flipped in a follow-up commit with one non-goals clause edit, one §3.1.4 teardown edit, and one §7 Known Constraints edit. The decision is documented here so the audit trail captures the alternative.

### Q1-Q7 findings (2026-04-11 code read pass)

**Summary**: all 7 questions resolved. Three CP decisions refined. One new CP added (CP-13, orchestrator dependency tree). Revised line count estimate for implementation: **~60-80 lines** of runner changes, up from original ~40-50 — the growth comes from spelling out the full orchestrator dependency tree in CP-13 rather than from any contract discovery.

**No contract surprises**. Every question resolved via existing test patterns; zero missing components; zero signature mismatches; zero unexpected preconditions. The escalation-to-blueprint decision is still correct because:

1. The cross-module execution chain is wider than the line count suggested (confirmed by CP-13 dependency tree)
2. The orchestrator requires a **4-call sequence per sample**, not a single `commit_bundle` call (confirmed by Q3 preconditions — bundle must be in `"approved"` state, which requires prior `open_bundle_review` + `apply_bundle_review`)
3. Two separate SQLite files per run are required, not one (confirmed by Q2 — `burr_db_path` is distinct from `ledger_path`)

**Q1 — RuntimeBootstrapSpec construction**: use `RuntimeBootstrapSpec.from_open_dto(open_dto)` classmethod, where `open_dto` is a plain dict with `schema_ir` + `ledger_path` keys. Verified from `test_agent_l4c2_workflow.py` line 52-53, 65.

**Q2 — bind_runtime_session signature**: `agent_session.bind_runtime_session(runtime_session_id: str, bootstrap_spec: RuntimeBootstrapSpec, burr_db_path: str)`. Three required args. `burr_db_path` is a separate SQLite file for session + candidate_cache + checkpoint state. Verified from `test_agent_l4c2_workflow.py` line 63-67.

**Q3 — commit_bundle signature + preconditions**:

```python
def commit_bundle(
    self,
    bundle_id: str,
    *,
    kind: Literal["set", "add"] = "set",
    confirmed_by: str | None = None,
) -> BundleCommitResult:
```

Preconditions (raise `AgentContractError`): bundle exists, `bundle.status == "approved"`, `bundle.approved_draft_ids` non-empty. Verified from `orchestrator.py` lines 462-476.

**Q4 — partial commit semantics**: explicit support. `BundleCommitResult` has `committed_count`, `failed_count`, `per_item_results: list[WriteResult | WriteError]`. No exception on per-draft failure. Verified from `orchestrator.py` lines 483-513.

**Q5 — smoke test sample**: `medium_02_blueprint_backref` (β.1 positive control, 10 valid drafts, zero rejections, ~1 min runtime). NOT `medium_01_security` because its 1-draft iter 5 result is too thin given OBS-01 variance.

**Q6 — runtime session open/close path**: sessions are opened via `service.runtime_v1.open_runtime_session(open_dto)` (module-level function), NOT `LocalRuntimeAPI.open_session(...)`. `LocalRuntimeAPI()` is a stateless wrapper used by `WriteTools`, `KGReadTools`, `EvaluateTools`, `ExplainTools`. Close via `close_runtime_session(session_id)` from the same module. Verified from `test_agent_l4c2_workflow.py` line 30-34, 39-42, 53, 100.

**Q7 — ledger verification path**: `KGReadTools.query_claims(runtime_session_id, pred_id=...)` returns a list of claim objects. Clean runtime-side read path. No sqlite3-specific code needed. Verified from `test_agent_l4c2_workflow.py` line 195-196.

### CP decision refinements triggered by Q1-Q7

| CP | original | refined | trigger |
|---|---|---|---|
| CP-02 | "LocalRuntimeAPI is the runtime adapter" | "`LocalRuntimeAPI()` is the runtime adapter passed to WriteTools/KGReadTools/EvaluateTools/ExplainTools. Session lifecycle is via `service.runtime_v1.open_runtime_session` / `close_runtime_session` module functions" | Q1 + Q6 |
| CP-03 | "per-run isolated ledger path" | "per-run isolated tempdir with BOTH `ledger.db` and `burr.db` SQLite files" | Q2 |
| CP-04 | "`commit_bundle(bundle_id)` is the entry point" | "4 orchestrator calls per sample: create_document_bundle → open_bundle_review → apply_bundle_review(all approve) → commit_bundle(kind='add', confirmed_by=...)" | Q3 |
| CP-05 | "default smoke test sample: `medium_01_security`" | "default `medium_02_blueprint_backref` (10 drafts, zero rejections); `medium_01_security` demoted to alt" | Q5 |

### New CP-13 added

CP-13 spells out the full orchestrator dependency tree: `CandidatePayloadCache`, `AgentCheckpointStore`, `KGReadTools`, `ExplainTools`, `EvaluateTools`, `WriteTools`, `DocumentStaging`, `DraftManager`, `BundleManager`, `ReadReviewOrchestrator` — 10 constructions total, all using existing classes with existing constructors. No new types, no new parameters, no contract changes.

**Rationale for adding CP-13**: the original blueprint sketch (before Q1-Q7) understated the orchestrator's dependency count. Listing the full tree in advance prevents implementation-time surprises. This is informational, not restrictive — it doesn't add constraints beyond what the existing reference test pattern already enforces.

### Line count revision

- Original estimate: ~40-50 lines of runner changes
- Post Q1-Q7 estimate: **~60-80 lines** of runner changes
- Growth reason: CP-13 dependency tree (the orchestrator needs ~15 construction lines that the original sketch elided)
- Still working-plan-sized in the "no contract changes" sense
- Still blueprint-required per cross-module execution chain + ledger side effects triggers
- The growth confirms that the reviewer's blueprint-escalation call was correct, not the working-plan classification

### Fresh open questions (none)

Zero new open questions surfaced during Q1-Q7 resolution. The blueprint is ready for scope check.

### What the reviewer should verify before pushing to `scoped`

1. **Scope is narrow enough**: 12 CP decisions + 6 explicit non-goals + 7 open questions = well-defined surface
2. **No scope creep**: blueprint does NOT try to also wire `HttpRuntimeAPI`, full commit rerun, or human review — all explicitly deferred
3. **The CP-06 escalation clause is clear**: "manual loop allowed only if orchestrator lacks critical telemetry"
4. **Q1-Q7 are answerable with code inspection**: they do not require running the code to resolve
5. **Acceptance (CP-12) is verifiable from run_record alone**: no subjective judgment required
6. **Teardown (CP-11) is in the right place**: `try/finally` around the per-sample loop, not around the whole main()
7. **Ledger isolation (CP-03) is sufficient for multiple parallel B3 sessions**: run_id uniqueness handles this

If any of 1–7 looks wrong, the reviewer's call is to stay in `draft`, request revision, and cycle before `scoped`.
