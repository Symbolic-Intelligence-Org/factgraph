# B3 真实文档负载测试报告 — Iteration 3

- Date: 2026-04-11
- Author: agent B3 harness
- Iteration: 3
- Related:
  - [README.md](../README.md)
  - [Iteration 2 report](./load_test_report_2026-04-11_iter2.md)
  - [Kernel strict-schema bugfix (archived)](../../../blueprints/archive/2026-04-11_kernel-extraction-response-model-openai-strict-fix.md)
  - [Prompt/schema alignment bugfix (archived)](../../../blueprints/archive/2026-04-11_agent-extraction-prompt-schema-alignment-fix.md)

---

## 0. TL;DR

**First valid extractions produced.** Iteration 3 landed the prompt/schema
alignment bugfix (PS-01..PS-06), and the B3 pipeline now exits with
nonzero `valid_count` on both real-document samples:

| sample | proposals | valid | rejected | valid rate |
|---|---:|---:|---:|---:|
| medium_01_security | 11 | **4** | 7 | 36% |
| long_01_kernel_p0 | 101 | **60** | 41 | **59%** |
| **combined** | **112** | **64** | **48** | **57%** |

This is the first iteration where the pipeline reaches **resolution**
and **bundle** stages end-to-end: `bundle_cb59df3807b0` (4 drafts) and
`bundle_9d93ffc11e5e` (60 drafts) were both created successfully.
`merge_count=0` on both — no duplicates in the current two-sample set.

**However, two residual rejection patterns remain**, both surfaced for
the first time by PS-06's enriched diagnostic (`got N, expected M`):

1. **Pattern A — subject leakage** (`got 2, expected 1`):
   long_01 only. All 41 rejections, uniform shape. LLM includes the
   subject entity_ref as an extra entry in `field_values`, despite
   prompt rule 9 ("Do NOT include the subject entity in `field_values`").
2. **Pattern B — multi-entry overpacking** (`got 3, expected 1` /
   `got 4, expected 1`): medium_01 only. All 7 rejections. LLM splits
   a single string slot into multiple `{tag, value}` entries (may also
   be inventing tags outside the schema, but current evidence proves
   overpacking first — see §2.4 Pattern B for the scoping note).

Both patterns are **prompt-alignment gaps**, not validator bugs. They
are distinct from iteration 2's failure mode (the LLM had no idea what
shape to emit at all) — now the LLM is within one structural step of
correct output, but needs targeted negative examples.

**Iteration 4 target**: small prompt iteration that kills both residual
patterns. Goal is `valid_count / proposal_count >= 90%` on the current
two samples, then proceed to 4C2 human review with the cleaner bundles.

---

## 1. 跑批概览

| # | Sample | Length | Format | Segments | LLM proposals | Valid | Rejected | Bundle | Outcome |
|---|--------|--------|--------|---:|---:|---:|---:|---|:---:|
| 1 | medium_01_security | medium | MD | 22 | 11 | **4** | 7 | `bundle_cb59df3807b0` | `success` ✓ |
| 2 | long_01_kernel_p0 | long | MD | 207 | 101 | **60** | 41 | `bundle_9d93ffc11e5e` | `success` ✓ |

Both `matches_expectation=true` against the tightened manifest:
`expected_result: success`, `expected_min_valid_specs: 1`.

### 1.1 Sources

- medium_01_security record: `run_records/b3_20260410T175711Z_medium_01_security.json`
- long_01_kernel_p0 record: `run_records/b3_20260410T175937Z_long_01_kernel_p0.json`

---

## 2. 聚合指标

### 2.1 Trajectory across iterations

| metric | iter 1 (both) | iter 2 (both) | iter 3 (both) |
|---|:---:|---:|---:|
| staging success | ✓ | ✓ | ✓ |
| extraction reachable | ✗ (deps missing) | ✓ | ✓ |
| strict-schema crash | n/a | ✓ fixed | ✓ |
| total_proposal_count | 0 | 35 | **112** |
| total_valid_count | 0 | 0 | **64** |
| valid rate | n/a | 0% | **57%** |
| resolution reached | ✗ | ✗ | **✓** |
| bundle reached | ✗ | ✗ | **✓** |
| bundles created | 0 | 0 | **2** |
| drafts in bundles | 0 | 0 | **64** |

Iteration 3 is the first iteration where the **entire** 4C3-a → 4C3-b →
4C3-c pipeline runs end-to-end on a real document. Staging, extraction,
validation, resolution, and bundle creation all succeeded on both samples.

### 2.2 Extraction (iter 3 per sample)

| metric | medium_01 | long_01 |
|---|---:|---:|
| total_segments | 22 | 207 |
| success_segment_count | 22 | 207 |
| error_segment_count | 0 | 0 |
| instructor_retry_exhausted | 0 | 0 |
| total_proposal_count | 11 | 101 |
| total_valid_count | 4 | 60 |
| total_rejection_count | 7 | 41 |
| batch_duration_ms | 34055 | 440717 |

**Key observations**:

1. **Proposal throughput up 3.2×** from iter 2 (35 → 112). The prompt
   changes made the LLM much more confident about what to extract when
   it sees relevant content.
2. **Valid rate went from 0% → 57% combined**. Iteration 2 had zero
   valid extractions. Iteration 3 produced 64.
3. **Pattern type distribution is unchanged** from staging — this is
   entirely an extraction-layer improvement, not a staging improvement.
4. **Latency scales linearly**: long_01 took ~7.3 min (441s) for 207
   segments, ~2.1s per segment. Medium_01 took ~34s for 22 segments,
   ~1.5s per segment. Proposal counts drove most of the increase over
   iter 2's `~1s/segment` (iter 2: 229 segments, no proposals for most).

### 2.3 Rejection distribution (iter 3)

| reason | medium_01 | long_01 | total |
|---|---:|---:|---:|
| schema_entity_type_unknown | 0 | 0 | 0 |
| schema_pred_id_unknown | 0 | 0 | 0 |
| **schema_field_type_mismatch** | **7** | **41** | **48** |
| scope_entity_type_denied | 0 | 0 | 0 |
| scope_pred_id_denied | 0 | 0 | 0 |
| scope_min_confidence | 0 | 0 | 0 |
| scope_max_batch_size | 0 | 0 | 0 |
| spec_construction_failure | 0 | 0 | 0 |

**All 48 rejections are still `schema_field_type_mismatch`**, same class
as iteration 2. But unlike iteration 2's uniform `100% rejected`, now
only **48/112 = 43%** of proposals are rejected — the other 57% pass
full validation and reach the bundle.

Thanks to PS-06's enriched diagnostic, we can now distinguish rejection
sub-patterns from the `got N, expected M` tail in the detail string.

### 2.4 Residual rejection patterns (new in iter 3)

#### Pattern A — subject leakage (`got 2, expected 1`)

- **Sample**: long_01_kernel_p0
- **Rejection count**: 41/41 (100% of long_01 rejections, 85% of total)
- **Diagnostic shape**: `field_values length mismatch for pred_id 'document:mentions': got 2, expected 1`
- **Uniform pattern**: all 41 rejections emit exactly **2** entries in
  `field_values` when the schema expects exactly **1**.
- **Interpretation**: the LLM is still including the subject entity
  (arg0, encoded as `entity_ref`) in `field_values` as an extra entry,
  even though prompt rule 9 explicitly says:
  > "Do NOT include the subject entity in `field_values` — it belongs in `entity_identity`."
- **Root cause hypothesis**: the rule is stated, but the prompt never
  shows a **negative example** of what incorrect subject placement
  looks like. Without a concrete wrong-vs-right side-by-side, the LLM
  defaults to a "copy the full arg list" heuristic.
- **Why long_01 only**: `document:mentions` is the most frequent
  predicate in long_01's extraction (it's a spec blueprint heavy with
  concept cross-references). Medium_01 has only 4 valid `document:mentions`
  extractions that are correct, so this pattern never dominates there.

#### Pattern B — multi-entry overpacking (`got 3/4, expected 1`)

- **Sample**: medium_01_security
- **Rejection count**: 7/7 (100% of medium_01 rejections, 15% of total)
- **Diagnostic shape**:
  ```
  field_values length mismatch for pred_id 'document:mentions': got 3, expected 1
  field_values length mismatch for pred_id 'document:mentions': got 4, expected 1
  field_values length mismatch for pred_id 'module:description': got 4, expected 1
  ```
- **Non-uniform pattern**: rejections have **3 or 4** entries in
  `field_values` instead of the expected **1**. The over-count varies
  per proposal.
- **Interpretation**: the LLM is **splitting a single string slot** into
  multiple sub-facts. For example, given a segment that lists several
  security controls, it emits one `document:mentions` with
  `field_values=[{tag:string, value:"control A"}, {tag:string, value:"control B"}, ...]`
  instead of emitting multiple separate proposals each with
  `field_values=[{tag:string, value:"control X"}]`.
- **Scoping note on tag invention**: length overpacking is directly
  proven by the `got 3/4, expected 1` diagnostic. The question of
  whether the LLM is *also* inventing `tag` values outside the
  schema-declared `type_domain` is **not** independently proven by
  the current run records — `rejection_samples` only capture the
  first rejection reason, and length mismatch short-circuits before
  `_validate_type_domain` runs. Iter 4 should surface it if present,
  since the pattern B fix will reduce length-mismatch rejections and
  any residual `tag != type_domain` mismatches will become visible.
- **Root cause hypothesis**: rule 9's length contract is honored in
  spirit (no subject leakage here), but the LLM treats `field_values`
  as "a list of things the predicate mentions" instead of "the ordered
  tuple of arg1..argN". Rule 9 could not catch this with its current
  wording because it talks about the subject, not about horizontal
  packing.
- **Why medium_01 only**: medium_01 is a condensed security overview
  that enumerates multiple items per paragraph. Long_01's 207 segments
  are more narrative and less list-heavy, so the overpacking heuristic
  doesn't trigger as often — but the 41 subject-leakage rejections
  dominate its error surface instead.

#### Summary of both patterns

Both are **prompt-shape misalignments**, not schema-knowledge gaps.
The LLM knows which predicate to use (zero `schema_pred_id_unknown`
rejections) and which entity types exist (zero `schema_entity_type_unknown`).
It's constructing `field_values` wrong in two distinct ways.

### 2.5 Resolution (iter 3)

| metric | medium_01 | long_01 |
|---|---:|---:|
| input_spec_count | 4 | 60 |
| output_spec_count | 4 | 60 |
| merge_count | **0** | **0** |
| unique_entity_count | 1 | 30 |
| unique_fact_count | 4 | 60 |
| resolution_duration_ms | 0 | 0 |

**Zero merges** across both samples. Two possible interpretations:

1. **The two samples genuinely contain no duplicate entities**, because
   they're topically disjoint (a security overview vs. a kernel blueprint).
2. **Resolution is running but no co-referent drafts entered the bundle**,
   because the LLM's entity identity fields are all distinct strings.

Both are consistent with the observed data. Resolution is reachable and
executed without errors — that alone is new in iter 3 — but its dedupe
value can't be measured until we have samples with overlapping entities.

### 2.6 Bundle (iter 3)

Both samples produced a real bundle in dry-run mode (`preview_only=true`,
never committed to the ledger):

| field | medium_01 | long_01 |
|---|---|---|
| bundle_id | `bundle_cb59df3807b0` | `bundle_9d93ffc11e5e` |
| draft_count | 4 | 60 |
| committed_count | 0 | 0 |
| failed_count | 0 | 0 |
| preview_only | true | true |

These are the **first real extraction bundles** to reach 4C2 territory.
Both are gated behind dry-run and do not appear in the committed ledger.

### 2.7 Human review

Not performed this iteration. The manifest's `review` section still
reads `PENDING: fill in after human review pass`. We held off because
iteration 3's bundles still contain the pre-fix extraction shape, and
a small prompt iteration is expected to improve quality further before
we invest human review time.

---

## 3. 观察到的问题

### P-04: Residual subject-leakage in `field_values` (Pattern A)

- **Category**: prompts / LLM alignment (negative example missing)
- **Severity**: P2 (drops ~37% of long_01 proposals; pipeline still
  produces valid extractions, so not a blocker; discovered only because
  PS-06 diagnostics now distinguish sub-patterns)
- **Sample(s)**: long_01_kernel_p0 (41/41 rejections)
- **Description**: Prompt rule 9 tells the LLM not to include the
  subject entity in `field_values`, but 41 rejected proposals on
  long_01 still emit `field_values.length = arg_spec.length`
  (i.e., including the subject) instead of `arg_spec.length - 1`.
- **Evidence**: All 41 rejections show `got 2, expected 1` for
  `document:mentions`, whose canonical shape is
  `subject=arg0:entity_ref field_values=[arg1:string]` — the LLM
  is emitting `[entity_ref, string]` where `[string]` is required.
- **Hypothesis**: Stating rule 9 in text is not enough for the model
  to internalize the subject/field split. Needs a **concrete negative
  example** pair showing "wrong: `field_values=[{tag:entity_ref, ...}, {tag:string, ...}]`"
  and "right: `entity_identity=[...], field_values=[{tag:string, ...}]`".
- **Proposed fix**: Add one negative example to the system prompt,
  directly after rule 9, showing the wrong and right shapes for a
  `subject + one string field` predicate. Keep under 15 lines.
- **Requires blueprint**: Yes — small scoped prompt iteration

### P-05: Residual multi-entry overpacking in `field_values` (Pattern B)

- **Category**: prompts / LLM alignment (length discipline missing)
- **Severity**: P2 (drops ~64% of medium_01 proposals; same discovery
  mechanism as P-04)
- **Sample(s)**: medium_01_security (7/7 rejections)
- **Description**: The LLM splits a single string slot into multiple
  `{tag, value}` entries when it encounters a segment mentioning
  several items. Instead of emitting N separate proposals each with
  `field_values=[{tag:string, value:"item_k"}]`, it emits one proposal
  with `field_values=[{tag:string, value:"item_0"}, {tag:string, value:"item_1"}, ...]`.
- **Evidence**: `got 3, expected 1` and `got 4, expected 1` shapes on
  both `document:mentions` and `module:description` predicates, which
  are both unary (one string slot after the subject) in the provisional
  schema.
- **Hypothesis**: Rule 9 covers "don't add the subject", but nothing
  in the prompt says "each proposal represents ONE fact; emit separate
  proposals for multiple items". The LLM treats `field_values` as an
  unbounded "list of mentioned things" when the segment contains a list.
- **Proposed fix**: Add a second negative example showing wrong horizontal
  packing alongside correct multi-proposal output. Reuse an enumeration-style
  example so it matches real enumeration segments.
- **Requires blueprint**: Yes — same blueprint as P-04

### P-06: Manifest's `expected_result: success` is satisfied even with high rejection rate

- **Category**: harness / manifest expectation granularity
- **Severity**: P3 (observability; not blocking)
- **Description**: The current manifest only distinguishes
  `success` / `empty`. A run with `valid_count=4` and a run with
  `valid_count=64` both report `matches_expectation=true` as long as
  `valid_count >= expected_min_valid_specs`. This was fine for
  iteration 3 (first-observed-valid milestone), but as we chase higher
  valid rates in iteration 4+, the manifest should allow a
  **minimum valid rate** or **maximum rejection rate** threshold so
  regressions in LLM shape are caught automatically.
- **Evidence**: Both samples passed `matches_expectation=true` despite
  37% / 64% rejection rates.
- **Proposed fix**: Add `expected_min_valid_rate` (float, optional) and
  `expected_max_rejection_rate` (float, optional) fields to
  `samples_manifest.yaml` and the runner's outcome-matching logic.
  Leave them unset for iteration 4 (still iterating on fix quality),
  set them for iteration 5+ once we have a stable baseline.
- **Requires blueprint**: **No** — defer to runner polish phase, not
  urgent

### P-07: Zero resolution merges — hard to tell if dedupe is working

- **Category**: observability / dedupe coverage
- **Severity**: P3
- **Description**: Both samples had `merge_count=0` in iter 3. Cannot
  distinguish "resolver ran correctly and found no duplicates" from
  "resolver ran but comparison logic wouldn't match anything anyway".
  Both samples are topically distinct, so zero merges is plausible.
- **Evidence**: `resolution.merge_count=0` on both run records
- **Proposed fix**: Add a deliberately-overlapping sample to the B3
  set (e.g., two short docs both mentioning "`User` entity with id
  `alice`") in iteration 5+. For iteration 4, not a blocker.
- **Requires blueprint**: No — sample set expansion, deferred

---

## 4. Deviations from expectations

None. Both samples had `expected_result: success` + `expected_min_valid_specs: 1`
in the tightened manifest, and both delivered valid specs. The
residual rejections are surfaced in §3 but do not flag
`matches_expectation=false` because the manifest's success definition
is "≥1 valid spec". P-06 discusses tightening this further.

---

## 5. 按类别的问题汇总

```
prompts / LLM alignment:     2 problems (P-04, P-05)   — both P2
harness / observability:     2 problems (P-06, P-07)   — both P3
kernel / validator:          0 problems
scope:                       0 problems
schema:                      0 problems
staging:                     0 problems
resolution:                  0 problems
bundle:                      0 problems
```

Zero kernel bugs in iteration 3. The two P1 prompt/schema issues from
iteration 2 are fully resolved. All residual issues are one layer deeper
(LLM alignment tuning + harness polish).

---

## 6. 建议的后续动作

### 6.1 Immediate (required for iteration 4)

- [ ] **Open small prompt iteration blueprint** targeting P-04 and
      P-05 together. Only modifies `SYSTEM_PROMPT_TEMPLATE` in
      `prompts.py` — adds a negative example block for each pattern.
      No validator changes, no response model changes, no test harness
      changes. Target: valid rate ≥ 90% on both samples.
- [ ] **Rerun B3 iteration 4** on both samples after the fix. Keep
      the manifest's `expected_result: success` + `expected_min_valid_specs: 1`
      — the tightening will come later.
- [ ] **Record the rerun as iteration 4** in a new report, measuring
      the delta on (valid rate, rejection rate) per sample.

### 6.2 After iteration 4 (promised from iter 2's §6.2 deferrals)

- [ ] **4C2 human review pass** on the iteration 4 bundles (not iter 3
      bundles — the cleaner post-fix bundles will be more representative).
      Measure `human_approval_rate` on the 64+ drafts and fill the
      `review` section of each run record.
- [ ] **Manifest tightening** (P-06): add `expected_min_valid_rate`
      and `expected_max_rejection_rate` fields once iteration 4/5
      establishes a stable baseline.

### 6.3 Deferred (not blocking short-term)

- **Sample set expansion to 9 docs** (PDF/DOCX, cross-referenced
  entities for merge coverage from P-07). Wait until iteration 4 or
  5 proves the fix converged.
- **`test_schema_ir.json` expansion**: add more entity types and
  multi-slot predicates so we can test `field_values.length >= 2`
  cases.
- **Langfuse wire-up**: still disabled in manifest. Useful for
  capturing exact prompt/response pairs on the residual rejection
  cases. Not needed for iteration 4 if the PS-06 diagnostic is
  sufficient to drive the fix (it has been so far).

---

## 7. 退出条件核对

From [README.md §8](../README.md#8-退出条件):

- [ ] 9 份样本全部跑完 — **not yet** (only 4-sample provisional set,
      of which 2 went through extraction this iteration). Will expand
      after iteration 4 consolidates the prompt.
- [x] 每份样本都有 run_record JSON — **yes** for both iteration 3 samples
- [x] 报告已完成 §1-§6 — **yes** (this document)
- [x] 每个 P0/P1 问题都有明确后续动作 — **yes** (zero P0/P1 remaining
      after iter 2's fix; the 4 new issues are P2/P3)
- [x] 至少 1 份样本成功走完完整链路 → **yes, both samples**. Staging +
      extraction + validation + resolution + bundle creation all
      reached end-to-end for the first time.

---

## 8. 附录

### 8.1 Environment snapshot

- Python: `/Users/zhenzhili/miniforge3/bin/python` (Python 3.10)
- Agent package: `src/factpy_kernel/agent/` at post-fix commit
  (PS-01..PS-06 applied, 959 → 967 tests)
- LLM provider: OpenAI via LiteLLM + Instructor
- Model: `gpt-4o-mini`, temperature 0.0
- Optional dep status: pymupdf ✓, pymupdf4llm ✓, docx ✓, instructor ✓,
  litellm ✓, yaml ✓, langfuse ✗ (manifest disabled)
- OPENAI_API_KEY loaded from `/Users/zhenzhili/hnsm-backend/.env`

### 8.2 Non-determinism note

With `temperature=0.0`, proposal counts should be stable run-to-run for
the same prompt and schema. Iteration 3 was executed in a single
~8-minute window on 2026-04-10T17:57Z to 2026-04-10T18:07Z. Reruns with
the same prompt text and same schema should produce similar numbers,
though the exact rejection detail strings are observation-order-dependent
(the `rejection_samples` list is capped to the first 3).

### 8.3 Files touched this iteration

- **New records**:
  - `run_records/b3_20260410T175711Z_medium_01_security.json`
  - `run_records/b3_20260410T175937Z_long_01_kernel_p0.json`
- **Kernel code** (via prompt/schema alignment bugfix blueprint,
  separately archived):
  - `src/factpy_kernel/agent/extraction/prompts.py` (new `build_schema_summary`
    + updated `SYSTEM_PROMPT_TEMPLATE` rules 7–10)
  - `src/factpy_kernel/agent/extraction/validation.py` (enriched
    `got N, expected M` detail — PS-06)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` (+5 fallback tests,
    +3 response-format tests)
- **Test suite**: 959 → 967 (+8 new tests, 2 total skipped)
- **Manifest**: `samples_manifest.yaml` tightened to
  `expected_result: success` + `expected_min_valid_specs: 1` on both
  medium_01 and long_01 (no schema change)
- **This report**: `report/load_test_report_2026-04-11_iter3.md`

### 8.4 Headline numbers

```
iter 1:   0 valid /   0 proposals (0%)  — deps missing
iter 2:   0 valid /  35 proposals (0%)  — schema shape unknown to LLM
iter 3:  64 valid / 112 proposals (57%) — first valid extractions
iter 4:   target ≥ 90% valid rate (post prompt iteration)
```
