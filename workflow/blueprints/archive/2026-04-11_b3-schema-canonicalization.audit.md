# Audit Log: B3 Schema Canonicalization — Parallel Canonical Fixture

## 2026-04-11 — Initial draft (continuation from archived commit-path blueprint)

### Trigger

The B3 load test runner's commit path wiring blueprint (`2026-04-11_load-test-runner-commit-path.md`) was archived as `implemented with deviations` on 2026-04-11 after two smoke test attempts both failed at `_build_commit_stack → service.runtime_v1.open_runtime_session(open_dto)`:

- **First attempt** (pre-CP-14): rejected with `"unexpected top-level keys: ['_note']; top-level structure is canonical"`
- **Second attempt** (post-CP-14): rejected with `"predicates[0].arg_specs[0].name must be non-empty string"`

The first failure was a superficial top-level metadata issue that CP-14 (runner filter for `_`-prefixed keys) fixed. The second failure is a deeper structural issue: the B3 provisional `test_schema_ir.json` (written at iter 2 as a smoke-test fixture, explicitly self-declared "Not a real FactPy SchemaIR") has four `predicates[].arg_specs[]` entries that omit the `name` field entirely. The canonical runtime validator inside `service.runtime_v1.open_runtime_session(...)` rejects this.

Reviewer's stop-rule on 2026-04-11:

> "如果第二次还是 runtime canonicalization failure, 先停, 不要继续补丁链"

Second attempt was still a runtime canonicalization failure (same `kind: runtime` error from the same entry point, different validator rule). Stop-rule fired. The archived blueprint closed as `implemented with deviations` with the runner wiring correct but the smoke test blocked by external schema non-canonicality.

Reviewer's continuation choice on 2026-04-11:

> "先关当前 blueprint, 再开 4a"
>
> "具体判断: 当前 2026-04-11_load-test-runner-commit-path.md 应该收成 implemented with deviations. 然后新开一个小 blueprint 走 4a: parallel canonical schema file."

See: [2026-04-11_load-test-runner-commit-path.md (archived)](../archive/2026-04-11_load-test-runner-commit-path.md) §9 Outcome.

### Root cause of the schema non-canonicality

The provisional `test_schema_ir.json` was written to satisfy the **B3 runner's preflight check** (non-empty dict with `entities` and `predicates` lists) and to feed the **extraction layer's `build_schema_summary`** function — both of which accept opaque schema content without canonical validation. Over iterations 3-5 the prompt layer grew workarounds for its non-canonical aspects:

- **PS-01** (iter 3): `build_schema_summary` falls back to positional names (`arg0:type_domain`) when `arg_specs[i].name` is missing. Reason: the B3 fixture omits `name` on all arg_specs.
- **PS-05** (iter 3, explicitly NOT applied): was proposed to add a similar positional fallback for `entities[].identity_fields[].name`, but was dropped because the B3 fixture already has `name` on all identity_fields. Only arg_specs are nameless.

The **canonical runtime validator** inside `service.runtime_v1` enforces the real contract:

- Top-level metadata keys must be canonical (`_note` is rejected)
- `predicates[].arg_specs[].name` must be non-empty strings
- Likely additional rules not yet probed (type_domain enums, projection structure, etc.)

This validator was never exercised before the commit-path blueprint's smoke test because no prior B3 phase (iter 4 / iter 5 / β.1 / format coverage) ever opened a runtime session. Only commit mode does, and commit mode was introduced by the just-archived blueprint.

### Why "parallel canonical fixture" (4a) over alternatives

Three fix approaches were evaluated on 2026-04-11:

| option | approach | pros | cons | verdict |
|---|---|---|---|---|
| **4a** | New `test_schema_ir_canonical.json` alongside the existing provisional schema. Runner loads the right one based on `--commit` flag | historical baselines fully preserved; clean two-file separation; no runtime transformation | requires designing a canonical schema (minor) | **chosen** |
| 4b | Modify `test_schema_ir.json` in place — add `name` fields, remove `_note` | one source of truth | pollutes iter 4 / iter 5 / β.1 / format coverage historical baselines | rejected |
| 4c | Runner-side schema canonicalization helper — synthesize missing `name` fields programmatically in `_build_commit_stack()` | no schema fixture changes; mirrors PS-01 prompt-layer pattern | runner becomes a schema normalizer; chain risk (each new validator rule requires a new line in the helper); ongoing maintenance burden | rejected |

Reviewer's reasoning for 4a (2026-04-11 message):

> "- 现在失败的不是 runner wiring, 而是 test_schema_ir.json 不是 canonical runtime schema
> - 继续在当前 blueprint 里补 schema, 会把'commit path wiring'和'schema canonicalization'两条线搅在一起
> - 4b 会污染历史 fixture, 不值得
> - 4c 会把 runner 变成 schema-normalizer, 边界最差"

### Frozen decisions (initial draft)

| # | Decision | Origin |
|---|----------|--------|
| SC-01 | New file `test_schema_ir_canonical.json` parallel to existing provisional schema | reviewer scope item 1: "新增一个并行 canonical fixture" |
| SC-02 | Same entity types + predicate IDs as provisional; only change is adding `name` to arg_specs | preserves extraction-draft / commit-validation compatibility |
| SC-03 | `test_schema_ir.json` is NOT modified | reviewer scope item 3: "不改现有 test_schema_ir.json" |
| SC-04 | Manifest gains one new optional top-level field `commit_schema_ir_path` | minimal manifest extension; additive, not breaking |
| SC-05 | Runner loads TWO schemas in commit mode — provisional for extraction, canonical for runtime session open | preserves extraction baseline; surgically replaces only the schema the canonical validator sees |
| SC-06 | `arg_spec.name` convention in the canonical schema: positional fallback (`arg0`, `arg1`) | matches prompts.py PS-01 existing convention; open to revision if smoke test rejects |
| SC-07 | Zero changes to files under `src/factpy_kernel/` | integration-layer fix; agent/kernel source tree stays read-only |
| SC-08 | Zero changes to iter 4 / iter 5 / β.1 / format coverage archived artifacts | historical baselines are sealed evidence |
| SC-09 | CP-14 filter stays in the runner as defensive code | three lines is cheap; removing it creates a regression vector for future non-canonical schemas |
| SC-10 | Smoke test: `--commit --sample medium_02_blueprint_backref` (same as archived blueprint) | consistency with the archived blueprint's CP-12 acceptance criteria |
| SC-11 | Runner patch bounded to ~15-20 lines (30-line deviation threshold) | surgical change; no touching `_build_commit_stack()` internals |
| SC-12 | No new tests, no new runner files, no changes to helpers | same discipline as archived blueprint |
| SC-13 | **Strict stop rule**: if smoke test fails, STOP — do not patch the canonical schema further within this blueprint | prevents infinite canonicalization patch chains; one-shot attempt |

### Explicit non-goals

- No `test_schema_ir.json` modification
- No modification of any archived iter 4 / iter 5 / β.1 / format coverage artifact
- No `_build_commit_stack()` internal changes
- No new entity types / predicates / type_domain values (pure 1:1 reshape + `name` additions)
- No agent-side or kernel-side code changes
- No `HttpRuntimeAPI` wiring
- No full 10-sample commit rerun
- No human review on committed drafts
- No retroactive canonicalization audit
- No new run_record schema fields
- No `SYSTEM_PROMPT_TEMPLATE` changes (β.1 verdict δ still holds)
- No changes to OBS-01 / OBS-02 / FUP-01 in `cross_run_observations.md`

### Impact on other layers

| Layer | Impact | Reason |
|-------|--------|--------|
| Agent layer (`src/factpy_kernel/agent/`) | **None** | Read-only |
| Kernel layer (`src/factpy_kernel/core/`) | **None** | Read-only |
| Runtime layer (`src/factpy_kernel/runtime/`) | **None** | Read-only |
| Service layer (`src/factpy_kernel/service/`) | **None** | HTTP service untouched |
| B3 harness | Runner patch (~31 lines per SC-11 ≤35 / >40 budget) + new schema fixture + manifest field | three files |
| B3 samples | **None** | 10 existing samples unchanged; `commit_schema_ir_path` is a runner-side field |
| B3 run_records | One new smoke test record (if smoke reaches `_run_single_sample`) | per SC-10 |
| Iter 4 / iter 5 / β.1 / format coverage | **None** | All frozen |
| `cross_run_observations.md` | **None** (unless smoke test surfaces something new) | OBS-02 already captured |
| Test suite | **None** (977 / 2 unchanged) | SC-12 |
| Archived commit-path blueprint | **None** | Historical rationale only |

### Relationship to archived commit-path blueprint

| archived blueprint | this blueprint |
|---|---|
| Runner wiring (CommitStack, `_build_commit_stack`, 4-call orchestrator sequence, try/finally teardown, CP-14 filter) | Inherits all of it. Does NOT revert or modify any piece |
| CP-01 through CP-14 | All still honored |
| Smoke test blocked at `open_runtime_session` | This blueprint aims to unblock by providing a canonical schema |
| §9 Outcome | Records the blocker; continuation path points here |

This is a **direct continuation** blueprint, not a rewrite. Everything the archived blueprint's runner patch did stays done. This blueprint adds a parallel fixture + a small runner update to load it.

### Pre-implementation baseline

- Full test suite: **977 tests, 2 skipped** (inherited from iter 5, confirmed unchanged through both archived commit-path blueprint attempts)
- Runner state: `run_load_test.py` post-commit-path patch (1305 lines including CP-14 filter)
- Existing schema: `test_schema_ir.json` unchanged since iter 2 (provisional, non-canonical, self-declared smoke-only)
- Existing manifest: `smoke-3` (7 iter 5/β.1 MD samples + 3 format coverage binary samples)
- Reference test: `test_agent_l4c2_workflow.py` — source of truth for agent-layer commit path patterns

### Open questions at draft time (SC-Q1 to SC-Q5)

Five questions locked in blueprint §8:

- **SC-Q1**: Does canonical validator accept `arg0`/`arg1` positional names?
- **SC-Q2**: Does it accept an empty `projection` dict?
- **SC-Q3**: Does it care about specific `schema_ir_version` / `protocol_version` / `generated_at` values?
- **SC-Q4**: Should `manifest_version` bump from `smoke-3` to `smoke-4`?
- **SC-Q5**: Should commit mode use the canonical schema for extraction too? **Closed — Option B locked via SC-05** (extraction uses provisional, commit uses canonical).

SC-Q1 / SC-Q2 / SC-Q3 remain open and will be resolved by the smoke test itself (cheap — one runner invocation). SC-Q4 is a cosmetic decision for scope check. SC-Q5 is closed.

### Review notes

This blueprint is proposed as a **single-shot fix** with a strict stop rule (SC-13). The stop rule is **strict** — no inline retry of any kind. The expectation is:

- **Happy path**: canonical schema passes the validator on the first smoke test. Blueprint archives as `implemented` with SC-Q1/Q2/Q3 documented as "validator accepted the defaults" (positional arg names, empty projection, byte-identical provisional version/protocol_version/generated_at preservation).
- **Single-error path**: canonical schema fails on one or more validator rules that §3.1's defaults didn't anticipate. SC-13 stop rule fires immediately. Blueprint closes as `implemented with deviations` — the known rule is documented in the Outcome section for a future follow-up blueprint. **No inline retry** — even a "one-line fix and rerun" is explicitly out of scope for this blueprint. The reason: retry loops are how scope creep happens. If one retry is acceptable, two retries are debatable, three becomes a patch chain. Strict one-shot means a clean exit and a clean handoff to the next blueprint.
- **Multiple-error path**: same as the single-error path at the blueprint-lifecycle level — one smoke test failure event closes the blueprint regardless of how many validator rules were violated. If the smoke surfaces a catastrophic rejection (e.g. the whole predicates block is shape-mismatched), the classification leans toward `abandoned` instead of `implemented with deviations`. Either way, no inline retry.

**This blueprint is not designed to absorb a canonical-validator probing session**. Its job is to test whether the current `_note`-removal + `arg_spec.name` addition hypothesis is sufficient. If it is, we win cheaply. If not, the answer is "canonicalization needs a dedicated design session, not a fixture tweak" — and that's a different blueprint with a different scope.

**The strict stop rule is the primary architectural commitment** of this blueprint, not an afterthought. Reviewers who disagree with "no inline retry on the first smoke error" should reject this blueprint at scope check and propose a more relaxed alternative — but that alternative should be honest about the trade-off between fast-iteration and scope control.

### Status transitions

- 2026-04-11 — draft created based on commit-path archival + reviewer's 4a directive
- 2026-04-11 — **scope check v1 returned 3 findings** (2× P1 + 1× P2). All 3 fixed in place. Blueprint did NOT advance to `scoped` — stayed in `draft` for v2 scope check. See §Scope-check v1 fixes below.
- 2026-04-11 — **scoped**. Scope check v2 passed with no blocking findings. One non-blocking nit applied during the transition: the non-goals list in §2 still referenced "`run_load_test.py` beyond SC-11's ~20-line surface" — updated to "≤35 lines target, >40 lines flags as deviation" matching the corrected SC-11 budget. A secondary scan for remaining stale budget references turned up 3 more references that the reviewer hadn't flagged individually but were still inconsistent: §1.4 "Why this is a blueprint" narrative (had "~20 lines to run_load_test.py" in the working-plan-size rationale), §Impact on other layers table in this audit log (had "Runner patch (~15-20 lines)"), and §Review notes checklist item 5 (had "~20-line runner patch"). All 4 stales corrected together. Budget is now single-valued everywhere: **~31 lines actual estimate per §3.3.3, ≤35 target per SC-11, >40 flags as deviation per SC-11**. Blueprint is now internally consistent and ready for implementation. Next transition: `implementing` once the runner patch + fixture file + manifest field land.
- 2026-04-11 — **implementing** (with SC-11 deviation). All 3 implementation files landed: `test_schema_ir_canonical.json` (new, 51 lines, verified programmatically as an exact byte-semantic `provisional minus _note plus 4 arg_spec name` transform); `samples_manifest.yaml` (smoke-3 → smoke-4, +1 field `commit_schema_ir_path`, +10 file lines); `run_load_test.py` (+43 lines, 1325 → 1368). Compile check passed. Full regression passed: **977 tests / 2 skipped** (exact match with iter 5 baseline — SC-07 / CP-07 held: zero diffs under `src/factpy_kernel/`). SC-12 compliance: PASS (no new tests, no new runner files, generate_review_packet.py and format_coverage_generators/ untouched). **SC-11 compliance: DEVIATION (see below)**. All other SC checks pass (SC-01 through SC-10, SC-13 gated pending smoke).
- 2026-04-11 — **SC-11 deviation recorded**. Actual runner patch: **+43 lines**. SC-11 target ≤35. SC-11 hard cap >40. Overrun: **+3 lines above the hard cap, +8 lines above the target**. Breakdown of the +43:
  - `_read_commit_schema_ir` helper: **+25 lines** (planned ~20; 5 over because the docstring includes the blueprint path + SC-02/04/05 citations for traceability)
  - `main()` commit schema load block: **+14 lines** (planned ~10; 4 over because the try/except has dedicated `FileNotFoundError` handling with a targeted error message separate from the generic `Exception` catch — the two-branch shape is more informative at failure time than a single catch-all)
  - `assert commit_schema_ir is not None` guard before `_build_commit_stack` call: **+4 lines** (not in the §3.3 sketch — added during implementation as a runtime safety net against a future bug where `commit_stack` construction is attempted without `commit_schema_ir` being loaded; justified because it prevents a subtle class of regression that `main()`'s early-return-on-schema-load-failure cannot catch on its own)
  - Call site edit + blank lines + comments: **0 net** (planned)
  - **Total**: +25 + +14 + +4 + 0 = **+43 lines**
  
  **Reviewer decision (2026-04-11)**: **Option A — accept the deviation, do NOT trim**. Rationale from reviewer: *"多出来的行里, FileNotFoundError 分支和 assert commit_schema_ir is not None 都是有价值的防御, 不是装饰. 为了把 +43 压回 ≤35 去删这些, 收益不够."* The trade-off: 3-line overrun on the hard cap is small; the defensive code is meaningful; trimming for budget theater would remove useful context (docstring citations) or defensive coverage (assert guard). Option B (trim to ≤35) and Option C (amend SC-11 to ≤40/>45) were explicitly rejected.
  
  **SC-11 amendment**: the SC-11 row in §2 frozen decisions is NOT modified — the budget numbers stay at ≤35 / >40 as a historical target. This deviation is recorded in the audit log as a discrete event, not as a scope change. The distinction matters for future audit: "we overran by 3 lines and the reviewer accepted it" is different from "we loosened the budget to match the implementation".
  
  **What this means for the implementation phase**: the blueprint's implementation files (§3.1 fixture, §3.2 manifest, §3.3 runner patch) are all considered **landed**. Smoke test (Step 8 / SC-10) is the next and final gate. SC-13 stop rule applies: one smoke test attempt, no inline retry on failure.
- 2026-04-11 — **implemented with deviations**. SC-10 smoke test (`--commit --sample medium_02_blueprint_backref`) executed. Exit code 1. `_build_commit_stack → service.runtime_v1.open_runtime_session(open_dto)` rejected the canonical fixture on a **third distinct canonical validator rule** that neither prior commit-path smoke attempts nor this blueprint's §3.1 fixture design anticipated: `predicates[0].group_key_indexes must be list`. Per SC-13's strict one-shot stop rule, **no inline retry was attempted**. SC-13 fired correctly — the rule behaved as designed and produced a clean hand-off point. Two deviations total: (1) SC-11 line budget overrun accepted via Option A, already recorded above; (2) SC-10 smoke surfaced the third canonical rule and SC-13 blocked further patching. See blueprint §9 Outcome for the full cumulative-rule table (rule 1: `_note` top-level key, fixed by commit-path CP-14; rule 2: nameless `arg_specs[].name`, fixed by this blueprint's SC-02; rule 3: missing `predicates[].group_key_indexes`, not fixed). Cumulative validator signal across 3 smoke attempts: probe-by-smoke is provably slow and provably unbounded — each attempt surfaces exactly one new rule because the validator short-circuits on the first violation. Carry-forward recommendation recorded in blueprint §9: future work should read the canonical validator source directly (under `service.runtime_v1`) or reuse an existing canonical `SchemaIR` fixture from kernel / test code, rather than open a fourth blueprint adding `group_key_indexes` and rerunning. Per reviewer (2026-04-11): no new OBS entry in `cross_run_observations.md`; the three-rule record is canonical in this audit log and blueprint §9. Three empty commit tempdirs (`b3commit_20260411T163857Z_froam1fe`, `b3commit_20260411T165352Z_27y99k_2`, `b3commit_20260411T192640Z_xxuwm1xi`) remain on disk — not deleted per reviewer instruction. Test suite state unchanged (977 / 2). SC-07 held (zero diffs under `src/factpy_kernel/`). SC-12 held (no new tests, no new runner files). All other SC checks (SC-01 through SC-09) passed. SC-11 and SC-10 are the two deviations; both documented.
- 2026-04-11 — **archived**. Both files moved from `docs/blueprints/active/` to `docs/blueprints/archive/` in a single transition. Blueprint and audit log are now historical evidence only.

### Scope-check v1 fixes (2026-04-11)

Three findings surfaced during the first scope check. All addressed in the blueprint + this audit log before v2.

**P1-1 — §3.1 canonical JSON was not a true 1:1 mirror**

The original §3.1 JSON sketch silently introduced 4 changes beyond the declared SC-02 scope ("add `name` to predicates[].arg_specs[]"):

- dropped `relationship_type` from both predicates (provisional has `"relationship_type": "true"` on both)
- dropped `entities[].arg_specs` entirely (provisional has entity arg_specs with `field_name` / `type_domain` / `cardinality`)
- changed `protocol_version` from the provisional nested dict (`{"idref_v1": "1.0", "tup_v1": "1.0", "export_v1": "1.0"}`) to integer `1`
- changed `generated_at` from the provisional full ISO timestamp (`"2026-04-11T00:00:00Z"`) to a date-only string (`"2026-04-11"`)

None of these 4 changes were justified in SC-02 or the non-goals list. They expanded the unknown surface unnecessarily and contradicted the blueprint's own "narrow, additive canonicalization" framing.

**Fix**: §3.1 rewritten against the verified byte content of `test_schema_ir.json` (read during scope check v1). The new §3.1 preserves every non-`_note` top-level key exactly as-is, including:

- `schema_ir_version: "v1"`
- `entities[]` including the `arg_specs` with `field_name`/`type_domain`/`cardinality`
- `predicates[].relationship_type: "true"` on both predicates
- `projection: {}`
- `protocol_version` nested dict shape (3 inner keys preserved)
- `generated_at` full ISO timestamp preserved

Only two changes remain: delete `_note` key, add `name` to four `predicates[].arg_specs[]` entries. A diff block was added to §3.1 showing exactly what changes.

If the canonical validator rejects any of the preserved fields (e.g. `entities[].arg_specs` is in a format it doesn't like, `relationship_type: "true"` as a string is wrong, `protocol_version` object shape is rejected), the SC-13 stop rule fires. The minimum-diff approach exposes as much of the provisional schema to the canonical validator as possible in a single probe, which is the best signal per dollar.

**P1-2 — stop rule contradicted by open question language**

SC-13 said "STOP. Do NOT chain more patches." But SC-Q1's answer approach said "replace with semantic names in one edit" and SC-Q2 said "react to validator error if any". These are exactly patch chains — a one-line edit after a smoke failure IS a retry. The audit log's review notes reinforced the contradiction by saying "a one-line fix and retry is probably acceptable; anything larger is abandonment territory."

**Fix**: three changes made to align with SC-13's strict one-shot policy:

1. §8 Open Questions header changed from "to answer during Step 1 or before smoke test" to "probe-only; SC-13 stop rule applies". New policy paragraph at the top of §8 makes the stop rule explicit: if the smoke test rejects a specific choice, do NOT retry inline — stop and classify.
2. SC-Q1, SC-Q2, SC-Q3 each rewritten to use "**Probe**:" language instead of "**Answer approach**:" — and each explicitly says "do NOT edit to X inline — STOP and classify per SC-13."
3. Audit log §Review notes rewritten: removed the "one-line fix and retry is probably acceptable" language. Replaced with "strict one-shot, no inline retry, reason: retry loops are how scope creep happens. If one retry is acceptable, two retries are debatable, three becomes a patch chain. Strict one-shot means a clean exit and a clean handoff to the next blueprint."

The single policy is now **strict one-shot, no inline retry of any kind**. Failure → classify → handoff to a follow-up blueprint. This blueprint does not absorb canonical-validator probing sessions — that's a different blueprint.

**P2 — runner patch line budget internally inconsistent**

SC-11 said "~15-20 lines, 30-line deviation threshold". §3.3.3's concrete line-count breakdown was "+20 helper + ~10 main() + 1 call site = ~31 lines" and then claimed "slightly above... but well under the 30-line deviation flag threshold" — which is false, since 31 > 30. §6 Acceptance Criteria had "≤~35 lines", implicitly relaxing the cap.

**Fix**: SC-11 rewritten with a **single-valued budget**: target ≤35 lines, deviation flag at >40 lines. §3.3.3 updated to say the concrete estimate fits within SC-11's corrected budget. §6 updated to reference the same numbers. The line "originally drafted at ~15-20 lines" is recorded in SC-11's rationale column for audit trail, but the active budget is ≤35 / >40.

### Why these fixes matter

All three findings are blueprint-level internal inconsistencies, not implementation risks. The blueprint's underlying scope decision (Option 4a — parallel canonical fixture) is still correct. What changed is the precision of the frozen decisions so that implementation has unambiguous guidance.

After v1 fixes:
- §3.1 is a verifiable diff against `test_schema_ir.json`
- SC-Q1/Q2/Q3 + audit review notes all agree on strict one-shot
- SC-11 / §3.3.3 / §6 all agree on ≤35 / >40 budget

**Zero new open questions surfaced during v1 fixes.** The blueprint is ready for v2 scope check.

### What the reviewer should verify before pushing to `scoped`

1. **Scope is genuinely narrow** — 13 SC decisions + explicit non-goals + 5 open questions with 3 answerable-by-smoke-test
2. **SC-06 positional name convention** is acceptable (not semantic names like `subject`/`object`)
3. **SC-05 extraction preservation** is correct (extraction stays on provisional schema, commit uses canonical)
4. **SC-13 stop rule** is strict enough — one smoke test attempt, no patch chains
5. **3-file surface is honored**: new fixture + 1-line manifest + ~31-line runner patch (within SC-11's ≤35 / >40 budget)
6. **CP-14 retention** (SC-09) is sensible as defensive code
7. **SC-Q1/Q2/Q3 probe-via-smoke approach** is acceptable rather than reading validator source upfront
8. **Archived commit-path blueprint's runner patches are preserved** exactly as-is — this blueprint does not revert them, does not re-review them, does not modify `_build_commit_stack()` internals

If any of 1-8 looks wrong, stay in `draft`, request revision, cycle before `scoped`.
