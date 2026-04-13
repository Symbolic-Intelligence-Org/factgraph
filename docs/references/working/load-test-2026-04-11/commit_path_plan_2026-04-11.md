# B3 Runner Commit Path — Inventory Plan (2026-04-11)

- Date: 2026-04-11
- Author: agent B3 working tracker
- Kind: **working tracker** (not a blueprint, not a report)
- Status: **CLOSED — escalated to blueprint chain, both archived as `implemented with deviations`** on 2026-04-11. Step 1 inventory complete; Step 2 never executed. Reviewer chose to escalate despite the working-plan-size classification in §3.3 because crossing from dry-run to real commit touches the `runtime/session/orchestrator/write` execution chain and introduces ledger side effects. Per repo rules this is a blueprint boundary regardless of line-count sizing.
- Continuation chain (both archived 2026-04-11):
  1. [2026-04-11_load-test-runner-commit-path.md](../../../blueprints/archive/2026-04-11_load-test-runner-commit-path.md) — runner wiring blueprint (CommitStack, 4-call orchestrator, CP-11 teardown, CP-14 `_`-prefixed key filter). Archived `implemented with deviations`: wiring correct, smoke blocked at `service.runtime_v1.open_runtime_session` on canonical validator rules 1 (`_note` top-level key) and 2 (`predicates[].arg_specs[].name` must be non-empty string). CP-14 resolved rule 1; rule 2 fired the stop rule and handed off to Option 4a.
  2. [2026-04-11_b3-schema-canonicalization.md](../../../blueprints/archive/2026-04-11_b3-schema-canonicalization.md) — parallel canonical fixture blueprint. Added `test_schema_ir_canonical.json` + `commit_schema_ir_path` manifest field + runner patch to load the canonical schema only in `--commit` mode. Archived `implemented with deviations`: SC-11 +43-line budget overrun accepted (Option A); SC-10 smoke surfaced canonical validator rule 3 (`predicates[].group_key_indexes must be list`); SC-13 strict one-shot stop rule fired correctly. See blueprint §9 Outcome for the full 3-rule cumulative record.
- **Carry-forward direction if this line reopens**: do NOT open a fourth probe-by-smoke blueprint. Three smoke attempts surfaced exactly three rules (one per attempt) because the validator short-circuits on the first violation; probing through smoke is provably unbounded. First step on any restart should be either reading the canonical validator source under `service.runtime_v1.open_runtime_session` to enumerate the full rule set in one pass, or reusing an existing canonical `SchemaIR` fixture from kernel / test code and adapting only the entity types / predicate IDs to match B3's `Document` / `Module` / `document:mentions` / `module:description` set.
- **B3 `--commit` end-to-end state**: still blocked at `open_runtime_session` on canonical validator rule 3. B3 `--dry-run` unchanged. `src/factpy_kernel/` zero diff throughout (977 / 2 regression held across both blueprints). 3 empty commit tempdirs left on disk per reviewer instruction.
- Follows: [format coverage plan](./format_coverage_plan_2026-04-11.md) (closed 2026-04-11 with verdict Option Y)
- Related:
  - [B3 runner stub commit section](./run_load_test.py) — lines ~699-725 (commit path currently stubbed)
  - [iter 5 review summary](./review/iter5/review_summary_iter5_2026-04-11.md)
  - [β.1 plan](./sample_expansion_plan_2026-04-11.md) (FINAL, verdict δ)

---

## 0. Goal

Answer 3 specific questions about wiring the B3 runner's stubbed commit path to a real ledger commit:

1. **What assembly is missing** between the current runner and a real commit?
2. **Which pieces are pure wiring, and which touch the agent/kernel contract?**
3. **Does this line naturally stay working-plan-sized, or will it escalate to a blueprint?**

These 3 answers decide whether commit-path work proceeds as a working plan (like β.1 and format coverage) or escalates to a scoped blueprint.

### 0.1 Why this line now

Per format coverage plan §5.5 and reviewer's explicit forward-looking note (2026-04-11):

> "如果 format coverage 收口后要选下一条，我会优先看 runner commit path，不是继续 prompt tuning。"

Format coverage proved the parser paths work; iter 5's `implemented with deviations` state is accepted; β.1 verdict δ committed to no further prompt tuning on the current iter 5 prompt. The next natural B3 priority is validating that the full pipeline can actually commit bundles to a persistent ledger, not just create in-memory previews.

### 0.2 What this plan is NOT

- NOT an iter 6 prompt iteration
- NOT a schema expansion
- NOT a 4C1 parser fix
- NOT a new feature for the agent layer
- NOT a refactor of any existing agent-side logic

Pure inventory at this stage. Whether it becomes a runner patch (Step 2) or a blueprint depends on the answers below.

---

## 1. Background — current runner commit stub

The runner's current commit path (`run_load_test.py`, `_run_single_sample()`, the commit section ~lines 699-725) is **explicitly stubbed**:

```python
# Step 5: commit (STUB — non-dry-run path)
# Committing requires AgentSession + DraftManager + BundleManager + WriteTools
# wired through a runtime adapter. For B3 first iteration, we intentionally
# keep this stubbed and treat non-dry-run the same as dry-run until a separate
# pass adds a runtime-bound runner.
```

And the runner docstring:

```
Commit path (non-dry-run):
    Currently STUBBED. The runner now builds a real 4C2 bundle preview
    (managed drafts + bundle_id), but it does not commit to a ledger.
    To enable commit, the runner needs an AgentSession + DraftManager +
    BundleManager + WriteTools wired through a runtime adapter
    (LocalRuntimeAPI or HttpRuntimeAPI) and a persistent runtime session.
```

Currently the runner builds a **preview** bundle in-memory via `_build_bundle_preview_stack()` and immediately returns. The `DraftBundle` object is real (bundle_id is generated, draft_ids are populated) but it's never committed to any persistent ledger. The run_record always reports `bundle.committed_count = 0` and `bundle.preview_only = true`.

---

## 2. Inventory findings (Step 1 complete)

### 2.1 Existing commit path components (all available, no construction needed)

| component | location | state | B3 runner usage |
|---|---|---|---|
| `LocalRuntimeAPI` | `src/factpy_kernel/agent/tools/_runtime_api.py` | **exists** | NOT currently instantiated |
| `RuntimeBootstrapSpec` + `open_session()` DTO | same module | **exists** | NOT currently called |
| `AgentSession.bind_runtime_session(...)` | `src/factpy_kernel/agent/session.py` (line 124) | **exists** | NOT currently called (runner creates `AgentSession` but leaves it unbound) |
| `BundleManager.create_bundle(...)` | `src/factpy_kernel/agent/documents/bundle.py` | **exists** | ✓ already called in `_build_bundle_preview_stack()` |
| `BundleManager.open_review(bundle_id)` | same | **exists** | NOT currently called |
| `BundleManager.apply_review(bundle_id, actions)` | same (lines 293-346) | **exists** | NOT currently called |
| `DraftManager.confirm_draft(draft_id)` | `src/factpy_kernel/agent/draft.py` (line 128) | **exists** | NOT currently called |
| `WriteTools.commit_draft(draft, bundle_id, confirmed_by)` | `src/factpy_kernel/agent/tools/write.py` (line 170) | **exists** | NOT currently called |
| `ReadReviewOrchestrator.commit_bundle(...)` | `src/factpy_kernel/agent/orchestrator.py` (lines 462-513) | **exists** — packages the full commit sequence | **key finding**: this is a ready-made helper that wraps confirm + write for many drafts |

**All 9 components already exist in the agent package**. The runner is not missing any class or method — it just isn't calling them.

### 2.2 Missing assembly steps in the runner

Concretely, to wire commit, the runner needs to call these operations in order (parallel to the existing dry-run path, but extended after bundle creation):

```
Step 1 — Runtime adapter setup (one-time, runner startup):
  runtime_api = LocalRuntimeAPI()
  open_dto = RuntimeBootstrapSpec(schema_ir=..., ledger_path=...)
  runtime_session_id = runtime_api.open_session(open_dto)

Step 2 — AgentSession binding (before processing any sample):
  agent_session = AgentSession(scope=scope, status="active")
  agent_session.bind_runtime_session(
      runtime_session_id=runtime_session_id,
      bootstrap_spec=...,
      burr_db_path=...,
  )

Step 3 — Per-sample commit (after bundle creation, replaces current dry-run stub):
  bundle = bundle_manager.create_bundle(...)  # already done
  bundle_manager.open_review(bundle.bundle_id)
  bundle_manager.apply_review(
      bundle.bundle_id,
      [BundleReviewAction(draft_id=d, action="approve") for d in bundle.draft_ids]
  )
  # At this point, all drafts are approved but not yet committed to the ledger.
  # Use the existing orchestrator helper:
  commit_result = orchestrator.commit_bundle(bundle.bundle_id)
  # OR manually:
  for draft_id in bundle.approved_draft_ids:
      draft_manager.confirm_draft(draft_id)
      draft = draft_manager.get_draft(draft_id)
      write_tools.commit_draft(draft, bundle_id=bundle.bundle_id, confirmed_by="b3_load_test")

Step 4 — Session teardown (once, runner shutdown):
  runtime_api.close_session(runtime_session_id)
```

Estimated total lines added to `run_load_test.py`: **~40-50 lines** (runtime adapter construction + bind + new commit path + teardown + error handling).

### 2.3 The one contract edge

**Key finding**: WriteTools requires the `AgentSession` to have a non-empty `runtime_session_id` (see `write.py` lines 161-168). The B3 runner currently constructs `AgentSession(scope=scope, status="active")` (run_load_test.py line 229) but does NOT call `bind_runtime_session()`. That's the only piece of state transition the runner is missing — not a missing function, just a missing call.

This is **not a contract change** in the "agent/kernel contract" sense. It's a **call ordering** issue — the runner is creating an object in an incomplete state. Fixing it requires adding one call, not changing any function signature or schema.

### 2.4 Existing end-to-end test as reference implementation

`src/factpy_kernel/tests/test_agent_l4c2_workflow.py` (lines ~159-194) already demonstrates the exact pattern end-to-end — it creates a runtime API, binds a session, creates a bundle, reviews, confirms, commits, closes. The B3 runner can copy this pattern almost verbatim, adapted for its batch-extraction-driven flow instead of the test's synthetic-draft flow.

This is a strong positive signal: **the wiring pattern is already proven and has test coverage**.

### 2.5 Choice of runtime adapter

Two adapters exist:
- **`LocalRuntimeAPI`** — in-process, wraps `runtime_v1` service helpers directly. No HTTP, no serialization overhead.
- **`HttpRuntimeAPI`** — HTTP client for the running service. Requires a live HTTP server + auth (per iter 4 KP0-10 key injection).

For the B3 harness, **`LocalRuntimeAPI` is the correct choice**:
- B3 is an offline load test, not a deployment validation
- Zero deployment overhead
- No auth dependency on KP0-10 HTTP key flow
- Matches the existing B3 pattern (runner already instantiates pipeline components in-process)

The B3 runner should NOT use `HttpRuntimeAPI` unless the goal changes to "validate the HTTP deployment path" — a different line entirely.

### 2.6 What a committed run_record would look like

Currently (dry-run):
```json
"bundle": {
  "bundle_created": true,
  "bundle_id": "bundle_XXXXXXXXXXXX",
  "draft_count": 16,
  "committed_count": 0,
  "failed_count": 0,
  "failed_breakdown": {"shape": 0, "runtime": 0, "runtime_session_not_found": 0},
  "preview_only": true,
  "commit_note": "dry-run: real bundle preview created; not committed to ledger."
}
```

After commit-path wiring (non-dry-run):
```json
"bundle": {
  "bundle_created": true,
  "bundle_id": "bundle_XXXXXXXXXXXX",
  "draft_count": 16,
  "committed_count": 16,
  "failed_count": 0,
  "failed_breakdown": {"shape": 0, "runtime": 0, "runtime_session_not_found": 0},
  "preview_only": false,
  "commit_note": "committed 16 drafts to ledger via LocalRuntimeAPI session <session_id>"
}
```

`_fill_bundle_preview()` in the runner already has the right output shape — it just needs to be called with `committed=True` and a commit note after the commit sequence runs successfully.

---

## 3. The three questions answered

### 3.1 Q1 — What assembly is missing between the current runner and a real commit?

**Nothing structural is missing. The runner is missing 3 *call sequences*, not 3 *classes*:**

1. **Runtime adapter lifecycle** — instantiate `LocalRuntimeAPI`, call `open_session(...)`, call `close_session(...)` at teardown
2. **AgentSession runtime binding** — call `agent_session.bind_runtime_session(...)` after creating the session and before using it for commit operations
3. **Commit sequence per sample** — call `bundle_manager.open_review()` → `apply_review()` → (either `orchestrator.commit_bundle()` OR loop over `confirm_draft()` + `write_tools.commit_draft()`) after creating each bundle

Everything needed (classes, methods, validators) is already implemented and test-covered. The runner just isn't calling it.

### 3.2 Q2 — Which pieces are pure wiring, and which touch the agent/kernel contract?

**Zero contract changes required. 100% wiring.**

| piece | classification | reason |
|---|:---:|---|
| `LocalRuntimeAPI` construction + `open_session` | **WIRING** | existing factory, no new fields |
| `bind_runtime_session` call | **WIRING** | method already exists, just a missing call |
| `BundleManager.open_review` / `apply_review` | **WIRING** | methods exist, accept standard DTO shapes |
| `DraftManager.confirm_draft` | **WIRING** | state transition already defined |
| `WriteTools.commit_draft` | **WIRING** | already accepts the exact shape `create_bundle` produces |
| `orchestrator.commit_bundle` helper | **WIRING** | ready-made facade |
| Validator path equivalence | **WIRING** | commit-time validator is the same scope guard that ran during extraction; no second stricter pass |
| `FactDraftSpec` schema | **WIRING** | all required fields are already populated by the resolver (`extraction_provenance`, etc.) |
| `close_session` teardown | **WIRING** | existing method |

**The one edge case** — WriteTools requires `agent_session.runtime_session_id` to be non-empty — is a **call ordering** issue in the runner, not a contract gap. Adding the `bind_runtime_session` call fixes it.

No public API changes. No new parameters. No schema changes. No new validators. No signature changes.

### 3.3 Q3 — Does this line naturally stay working-plan-sized, or will it escalate to a blueprint?

**Working-plan-sized**, with high confidence. Here's the reasoning:

**Size estimate**:
- Runner changes: **~40-50 lines** (one-time setup + per-sample commit + teardown + error handling)
- Agent-side changes: **0 lines**
- Kernel-side changes: **0 lines**
- Schema / validator / response-model changes: **0 lines**
- New tests required: **optional** (existing `test_agent_l4c2_workflow.py` already covers the pattern; runner-side integration test could be added but is not strictly required for a working-plan iteration)
- Blueprint scope hallmarks present: **none**

**Compared to prior working-plan-vs-blueprint decisions**:

| line | code surface | contract changes | verdict |
|---|---|---|---|
| β.1 sample expansion | 0 code changes, 3 MD files + manifest | none | working plan ✓ |
| format coverage | 0 code changes, 3 binary files + 3 generators + manifest | none | working plan ✓ |
| commit path (this plan) | ~40-50 lines in runner only | none | **working plan ✓** |
| iter 5 (for comparison) | prompt template + test file | contract: new prompt framing | blueprint (correct call) |
| γ schema expansion (hypothetical) | schema + prompt + validator + tests | contract: new entity types | blueprint (correct call) |

**This line looks like β.1 and format coverage in shape**: modest runner-side changes, zero contract impact, reuses existing agent-side primitives. It does not look like iter 5 or γ.

**Escalation triggers** (if any of these come up during implementation, stop and open a blueprint instead):

1. Commit-time validator turns out to be stricter than extraction-time and rejects drafts that passed extraction
2. `bind_runtime_session` requires schema IR registration that the B3 runner doesn't currently do and can't do with existing methods
3. Some `FactDraftSpec` field is required by commit but not populated by the resolver
4. `LocalRuntimeAPI` requires a ledger path that the B3 harness can't safely isolate from other B3 data
5. Committing a bundle mutates global state that leaks across runs (e.g., the commit writes into a shared default ledger file)

**Risk check**: trigger #5 is the most plausible concern. The runner should use a **per-run temporary ledger path** (something like `/tmp/b3_commit_<run_id>.db` or a configurable `ledger_path` in the manifest) so each canonical run is fully isolated. If that isolation pattern is hard to set up, we stop and blueprint. Otherwise we proceed.

---

## 4. Proposed Step 2 (pending user approval)

If you approve this line as working-plan-sized:

```
Step 2a — Add a `--commit` / ledger-path option to the runner
  → opt-in switch; dry-run stays the default
  → ledger path is per-run isolated (temp file with run_id)

Step 2b — Wire LocalRuntimeAPI + bind_runtime_session in runner init
  → ~10-15 lines

Step 2c — Replace the commit stub with real commit sequence
  → orchestrator.commit_bundle() OR the explicit 5-step loop
  → fill run_record with actual committed_count + commit_note
  → ~20-25 lines

Step 2d — Add error handling for commit failures
  → WriteError, DraftNotConfirmed, runtime_session_not_found, etc.
  → populate bundle.failed_breakdown correctly
  → ~5-10 lines

Step 2e — Close runtime session in runner teardown
  → ~2-3 lines

Step 3 — Smoke test
  → run the runner in commit mode on ONE small sample (short_01_readme or medium_01_security)
  → verify: ledger file created, committed_count > 0, pipeline didn't crash
  → NOT a full B3 rerun; just a sanity check that wiring works

Step 4 — Decision
  → if commit sample works: line closes as working plan, document outcome in §5
  → if commit sample fails: diagnose; either fix with ~small patch or escalate to blueprint
```

### 4.1 What Step 2 is explicitly NOT

- Not a full B3 rerun on all 10 samples (that's a separate phase if we decide to)
- Not the FUP-01 record-replay cache (still deferred)
- Not human review of committed drafts (commits don't change the semantic review question)
- Not a deployment validation (LocalRuntimeAPI only, no HTTP)
- Not a multi-run ledger that persists across B3 phases (each commit run uses a fresh temp ledger)

### 4.2 Blueprint escalation gate for Step 2

If during Step 2 any of the 5 escalation triggers (§3.3) surface, stop and open a scoped blueprint. Otherwise complete Step 2 as working-plan work.

---

## 5. Decision (FINAL — escalated to blueprint on 2026-04-11)

- [x] **ESCALATE to blueprint** — Step 2 was NOT executed as working plan
- [ ] ~~Approve as working-plan-sized~~
- [ ] ~~Different sub-scope~~
- [ ] ~~Pause~~

### 5.1 Reviewer's escalation rationale (2026-04-11)

> "Step 1 的结论我认同: 这是 wiring, 不是 contract redesign. 但一旦进 Step 2, 就会把 runner 从 dry-run 扩到真实 commit, 跨到 `runtime/session/orchestrator/write` 这条执行链, 还涉及 ledger side effects. 按仓库规则, 这已经是需要 blueprint 的边界了."

Key points:

- The **wiring-vs-contract classification in §3.2 is accepted** — this is not a contract redesign
- But the **runtime boundary crossing** (dry-run → real commit) and the **ledger side effect** together meet the repo's blueprint-required bar, independent of line count
- Working-plan size is not a sufficient condition to skip blueprinting — the repo rules say *cross-module execution chain touches* and *side effects on persistent state* also trigger the blueprint requirement
- Commit-path wiring touches `runtime/session/orchestrator/write` which spans 4 agent-layer modules even though the code changes are all in the runner

### 5.2 Continuation — blueprint scope (frozen by reviewer before blueprint creation)

The blueprint is **narrow**, matching the Step 2 outline from §4 with one explicit constraint: use the existing `ReadReviewOrchestrator.commit_bundle()` facade, NOT the manual confirm+write loop, unless implementation surfaces a telemetry gap.

Scope locked by reviewer:

1. **`--commit` opt-in flag** — dry-run stays default
2. **`LocalRuntimeAPI` + `bind_runtime_session`** — no HttpRuntimeAPI
3. **Per-run isolated ledger path** — auto-generated per run_id
4. **Runner teardown `close_session`**
5. **1 small-sample smoke test** — not a full B3 rerun
6. **Orchestrator facade only** — no manual loop unless orchestrator lacks required telemetry

### 5.3 What this plan does NOT commit

- No code changes made to the runner (Step 2 skipped)
- iter 5 `SYSTEM_PROMPT_TEMPLATE` untouched (still frozen per β.1 verdict δ)
- No modifications to agent/kernel source tree during this plan's lifetime
- No new run_records or test files
- Agent-side modules untouched (the blueprint will NOT change them either)

### 5.4 Plan sealed as closed-to-escalation

This plan is now historical evidence of the **decision process** that led to the blueprint. §2 inventory and §3 three-question answers are the authoritative record of why escalation was chosen over a working-plan Step 2. The blueprint (once opened) carries forward the implementation work.

**What cannot be changed without reopening this plan**:

- The §2 inventory findings (they are factual code-inspection results)
- The §3 three-question classifications (wiring vs contract)
- The §3.3 escalation triggers list (inherited by the blueprint's risk section)
- The §5.1 escalation rationale (reviewer's quoted decision)

**What can still be linked from here going forward**:

- The archived blueprint at `docs/blueprints/archive/2026-04-11_load-test-runner-commit-path.md` cites this plan as its trigger; its successor schema-canonicalization blueprint at `docs/blueprints/archive/2026-04-11_b3-schema-canonicalization.md` cites the commit-path blueprint's archival as its own trigger — see the head Status section for the full 2-blueprint continuation chain and the carry-forward note
- Any future audit or retrospective discussion of "why did we blueprint rather than work-plan this" can cite §5.1

---

## 6. What is frozen during this plan

- **All B3 phases before commit path**: iter 4, iter 5, β.1, format coverage — all sealed as historical evidence
- **`SYSTEM_PROMPT_TEMPLATE`**: iter 5 state, unchanged
- **`test_schema_ir.json`**: unchanged
- **`generate_review_packet.py`**: unchanged
- **Agent source code under `src/factpy_kernel/agent/`**: commit-path work is runner-side only; agent layer is read-only for this plan
- **Kernel source code under `src/factpy_kernel/core/`**: commit-path work does not touch kernel internals
- **OBS-01, OBS-02, FUP-01**: unchanged; commit path does not affect or depend on them

The only files this plan might modify in Step 2 are:

1. `docs/references/working/load-test-2026-04-11/run_load_test.py` (~40-50 lines added)
2. `docs/references/working/load-test-2026-04-11/samples_manifest.yaml` (**optional** — only if we add a manifest-level `commit_mode` config field)
3. This plan file (fill in §5 decision + outcome after Step 2)

Everything else stays untouched.
