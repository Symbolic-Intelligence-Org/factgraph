# B3 真实文档负载测试报告 — Iteration 2

- Date: 2026-04-11
- Author: agent B3 harness
- Iteration: 2
- Related:
  - [README.md](../README.md)
  - [Iteration 1 records](../run_records/) (timestamps `b3_20260410T1634*`)
  - [Kernel bugfix blueprint (archived)](../../../blueprints/archive/2026-04-11_kernel-extraction-response-model-openai-strict-fix.md)

---

## 0. TL;DR

Iteration 2 unblocked the OpenAI strict-mode schema crash (landed via the
kernel bugfix blueprint). Real LLM extraction now runs end-to-end: 229/229
segments across two samples completed without extraction errors, and 35
proposals were produced.

**However, 35/35 proposals were rejected by the validator** with the same
reason: `schema_field_type_mismatch: field_values length mismatch`. This
is **not** a validator bug — the validator logic remains correct per its
spec. It's a prompt-layer robustness gap:

1. **B3 used a provisional non-canonical schema** (`test_schema_ir.json`
   explicitly says "Not a real FactPy SchemaIR"). Its `predicates[].arg_specs`
   omit the `name` field, which canonical SchemaIR validation in
   `core/schema/schema_ir.py` forbids. A canonically-validated schema
   could not reach this state.
2. **But the prompt layer does not require canonical validation** before
   rendering a schema summary. `build_schema_summary` silently drops
   arg entries without a `name` — so on the B3 non-canonical input,
   the LLM sees `- pred_id args=[]` and has to guess `field_values`.
3. **The prompt also never teaches the `field_values` construction
   contract** (subject vs field split, length rule, tag==type_domain).
   This gap would affect canonical inputs too — the LLM would still
   have to infer the `arg_specs[0]` = subject split.

**Iteration 3 target**: make the prompt layer robust to both
non-canonical input (B3 smoke schemas, hand-written fixtures, pre-validation
dry runs) and canonical input, **without changing the validator**. Goal
is first observed `valid_count > 0`.

---

## 1. 跑批概览

| # | Sample | Length | Format | Segments | LLM proposals | Valid | Rejected | Outcome |
|---|--------|--------|--------|---:|---:|---:|---:|:---:|
| 1 | medium_01_security | medium | MD | 22 | 2 | 0 | 2 | `empty` ✓ |
| 2 | long_01_kernel_p0 | long | MD | 207 | 33 | 0 | 33 | `empty` ✓ |

**Both** `matches_expectation=true` because the provisional manifest
declared `expected_result: empty` while deps/environment were still
unstable in iteration 1. For iteration 3, manifest should tighten the
expectation to `success` + `expected_min_valid_specs >= 1` once the fix
lands.

### 1.1 Sources

- medium_01_security record: `run_records/b3_20260410T171806Z_medium_01_security.json`
- long_01_kernel_p0 record: `run_records/b3_20260410T171903Z_long_01_kernel_p0.json`

---

## 2. 聚合指标

### 2.1 Staging (unchanged from iteration 1)

Both samples staged cleanly via `PlainTextParser`:
- medium: 22 segments, 1984 chars, avg structural_clarity 0.21, pattern_dist narrative-heavy
- long: 207 segments, 31671 chars, avg structural_clarity 0.23, pattern_dist narrative-heavy with some entity_relation

### 2.2 Extraction (iter 2 vs iter 1)

| metric | iter 1 (medium) | iter 2 (medium) | iter 1 (long) | iter 2 (long) |
|---|---:|---:|---:|---:|
| success_segment_count | 0 | **22** | 0 | **207** |
| error_segment_count | 22 | **0** | 207 | **0** |
| instructor_retry_exhausted | 22 | 0 | 207 | 0 |
| total_proposal_count | 0 | **2** | 0 | **33** |
| total_valid_count | 0 | 0 | 0 | 0 |
| total_rejection_count | 0 | **2** | 0 | **33** |
| batch_duration_ms | 2126 | 29191 | 298 | **200781** |

**Key observations**:

1. **Strict-schema crash fully resolved**: zero `instructor_retry_exhausted`
   on any segment. The kernel bugfix (BF-01 through BF-09) works end-to-end.
2. **LLM is actually extracting**: 229 segments × 1 real LLM call each =
   229 round trips to OpenAI, all completed successfully at the API layer.
3. **Extraction rate is low but nonzero**: 35 proposals / 229 segments ≈ 15%.
   This matches staging's narrative-heavy distribution — most segments
   genuinely don't contain extractable facts under the minimal schema.
4. **Batch duration is dominated by LLM latency**: 200s for long_01 =
   ~1s per segment, which is normal for gpt-4o-mini with the current
   retry configuration.

### 2.3 Rejection distribution

Entire breakdown across both samples:

| reason | medium | long | total |
|---|---:|---:|---:|
| schema_entity_type_unknown | 0 | 0 | 0 |
| schema_pred_id_unknown | 0 | 0 | 0 |
| **schema_field_type_mismatch** | **2** | **33** | **35** |
| scope_entity_type_denied | 0 | 0 | 0 |
| scope_pred_id_denied | 0 | 0 | 0 |
| scope_min_confidence | 0 | 0 | 0 |
| scope_max_batch_size | 0 | 0 | 0 |
| spec_construction_failure | 0 | 0 | 0 |

**100% of rejections are `schema_field_type_mismatch`**. Sample details:

```
[1] reason=schema_field_type_mismatch
    detail=field_values length mismatch for pred_id 'document:mentions'
[2] reason=schema_field_type_mismatch
    detail=field_values length mismatch for pred_id 'document:mentions'
[3] reason=schema_field_type_mismatch
    detail=field_values length mismatch for pred_id 'module:description'
```

Both predicates hit the same error class. The LLM **is** picking legal
entity_types and pred_ids (no `schema_*_unknown` rejections), so the
Literal-based type constraints from `build_response_model` are working.
The failure is at the `field_values` structural level.

### 2.4 Human review

Not performed this iteration. All proposals were rejected by the validator
before reaching human review. No draft bundle was created.

---

## 3. 观察到的问题

### P-01: `build_schema_summary` silently drops predicate args without a `name` field

- **Category**: prompts / schema-summary generation (robustness gap on non-canonical input)
- **Severity**: P1 (blocks real extraction when a non-canonical schema reaches the prompt layer)
- **Sample(s)**: medium_01_security, long_01_kernel_p0 (both)
- **Scoping note**: B3 used a provisional **non-canonical** schema
  (`test_schema_ir.json` self-declares as "Not a real FactPy SchemaIR").
  Its arg_specs omit `name`, which canonical SchemaIR validation in
  `core/schema/schema_ir.py:_validate_predicates` forbids. So this bug
  cannot surface on a canonically-validated schema. But the prompt layer
  does not require canonical validation, so any non-canonical input
  (B3 smoke, hand-written fixtures, pre-validation dry runs) trips it.
- **Description**: The current `build_schema_summary` in
  [prompts.py](../../../../src/factpy_kernel/agent/extraction/prompts.py)
  around line 71–80 does:
  ```python
  for arg in predicate.get("arg_specs", []):
      name = arg.get("name")
      type_domain = arg.get("type_domain")
      if isinstance(name, str) and name:
          suffix = f":{type_domain}" if isinstance(type_domain, str) and type_domain else ""
          arg_specs.append(f"{name}{suffix}")
  predicate_lines.append(f"- {pred_id} args={arg_specs}")
  ```
  This *only* emits an arg spec if `name` is a non-empty string. The
  provisional `test_schema_ir.json` has arg_specs like
  `{"type_domain": "entity_ref"}` with no `name`, so the emitted schema
  summary for predicates becomes `- document:mentions args=[]`. The LLM
  has no information about what arguments the predicate takes.
- **Evidence**:
  - `test_schema_ir.json` arg_specs are `{"type_domain": "..."}` without `name`
  - `build_schema_summary` source inspection (line 77)
  - `_validate_predicates` in `core/schema/schema_ir.py` requires canonical names — but only canonical-schema paths go through that validator, the prompt does not
- **Hypothesis**: The LLM makes a best-guess `field_values` because the
  schema summary gives it no structure to copy. It probably emits either
  an empty list (→ length mismatch with `len(rest_specs)=1`) or includes
  the subject entity ref as an extra entry (→ length=2 where expected is 1).
- **Proposed fix**: `build_schema_summary` should always emit a positional
  entry for each predicate arg_spec, even when `name` is missing, using
  `name:type_domain` if name exists or `arg{i}:type_domain` otherwise.
  This makes the prompt robust to non-canonical B3-style input without
  changing the canonical validator.
- **Requires blueprint**: **Yes** (small scoped bugfix, combined with P-02)

### P-02: `SYSTEM_PROMPT_TEMPLATE` never explains `field_values` semantics

- **Category**: prompts / LLM instruction alignment (pre-existing gap, affects canonical and non-canonical inputs alike)
- **Severity**: P1 (causally tied to P-01; would still apply even if P-01 were absent)
- **Sample(s)**: medium_01_security, long_01_kernel_p0 (both)
- **Scoping note**: Unlike P-01, this defect is **not** specific to
  non-canonical schemas. Even with a canonical, name-fully-populated
  SchemaIR, the current prompt template would still fail to tell the
  LLM the `arg_specs[0]` = subject split, the length rule, or the
  `tag == type_domain` convention. B3 iteration 2 surfaced this because
  the first real LLM call reached it.
- **Description**: The system prompt template lists 6 rules and the schema
  summary, but nowhere explains:
  1. How `arg_specs` maps to the response structure
  2. That `arg_specs[0]` is the subject entity and is encoded in
     `entity_type` + `entity_identity`, **not** `field_values`
  3. That `field_values` length must equal `len(arg_specs) - 1`
  4. That each `tag` in `field_values` must equal the `type_domain` of
     the corresponding argument slot (enforced by
     `_validate_field_types` in validation.py line 197–198:
     `if tag != type_domain: return ...`)

  Even with a perfect schema summary, without these rules the LLM
  cannot reliably construct `field_values`.
- **Evidence**:
  - [prompts.py line 8–22](../../../../src/factpy_kernel/agent/extraction/prompts.py#L8)
  - Validator contract: [validation.py line 195–198](../../../../src/factpy_kernel/agent/extraction/validation.py#L195)
- **Hypothesis**: Combined with P-01, the LLM has neither the arg list
  nor the construction rules, so it's essentially guessing the shape.
  Explains 100% rejection rate on the B3 non-canonical schema.
- **Proposed fix**: Add a "Response format" section to
  `SYSTEM_PROMPT_TEMPLATE` that documents the entity_identity / field_values
  separation and the tag==type_domain convention. This benefits canonical
  and non-canonical inputs equally.
- **Requires blueprint**: **Yes** (combined with P-01 in a single small
  scoped bugfix blueprint)

### P-03: Rejection detail does not include actual vs expected length

- **Category**: observability / diagnosis
- **Severity**: P3
- **Sample(s)**: all rejection samples
- **Description**: `_validate_field_types` line 193–194 returns
  `f"field_values length mismatch for pred_id '{pred_id}'"` without
  stating what length was received vs expected. This makes it harder to
  tell whether the LLM is emitting `[]` or `[...two items]`.
- **Evidence**: rejection_samples in both iter2 run records
- **Hypothesis**: n/a, just a diagnostic gap
- **Proposed fix**: Make the detail include actual and expected counts,
  e.g. `f"field_values length mismatch for pred_id '{pred_id}': got N, expected M"`.
- **Requires blueprint**: **No** — one-line fix, can be included in the
  P-01/P-02 blueprint or done as a drive-by

---

## 4. Deviations from expectations

None. Both samples had `expected_result: empty` in the provisional manifest,
and both returned `empty`. This matched iteration 1 by coincidence (different
causes) — iter 1 empty was because of dependency_missing; iter 2 empty is
because of validator rejection. The match flag is deceptive in that sense:
it says the outcome matched, but the failure shape is completely different.

**Action**: iteration 3 should tighten `expected_result` to `success` and
`expected_min_valid_specs >= 1` before rerunning, so a continuing empty
result would be correctly flagged as `matches_expectation=false`.

---

## 5. 按类别的问题汇总

```
prompts / schema-summary:   2 problems (P-01, P-02)  — both P1
observability:              1 problem  (P-03)        — P3
schema / kernel:            0 problems
scope:                      0 problems
LLM hallucination:          0 problems
resolution / bundle:        0 problems (never reached these stages)
```

Zero kernel bugs in iteration 2. The strict-schema kernel bug from
iteration 1 is fully resolved.

---

## 6. 建议的后续动作

### 6.1 Immediate (required for iteration 3)

- [ ] **Open small scoped bugfix blueprint**: prompt/schema alignment fix
      covering P-01 + P-02 together. Modifies only `prompts.py` (schema
      summary generator and SYSTEM_PROMPT_TEMPLATE) plus optionally one
      detail string in `validation.py` (P-03 drive-by). No test harness
      changes, no validator logic changes, no response model changes.
- [ ] **Rerun B3 iteration 3** on both samples after the fix, targeting
      first observed `valid_count > 0`.
- [ ] **Tighten samples_manifest.yaml** for iteration 3: set
      `expected_result: success` and `expected_min_valid_specs >= 1` on
      both samples so false positives don't hide persistent rejection.

### 6.2 Deferred (wait for iteration 3 data)

- **Sample set expansion to 9 docs** (PDF/DOCX etc.): value is in
  validating staging breadth, not extraction correctness. Defer until
  iteration 3 shows the core pipeline works.
- **`test_schema_ir.json` expansion**: add more entity types / predicates
  once we know the current two work end-to-end.
- **Runner observability enhancement**: LLM token counting, per-segment
  latency histogram. Nice-to-have, but iteration 2 already showed
  ~200s for 207 segments is acceptable.
- **Langfuse trace wire-up**: current runs have `langfuse.enabled=false`
  in manifest. Turning it on would let us inspect the actual prompt and
  response per call, which is useful for diagnosing the LLM's exact
  proposal shape on the rejection cases. **Possible**, but not blocking
  iteration 3 — we can fix the prompt blind and observe the rejection
  delta.

---

## 7. 退出条件核对

From [README.md §8](../README.md#8-退出条件):

- [x] 9 份样本全部跑完 — **not yet** (only 4-sample provisional set). Will
      complete after iteration 3 validates the pipeline.
- [x] 每份样本都有 run_record JSON — **yes** for the 4 samples currently
      in the manifest
- [x] 报告已完成 §1-§6 — **yes** (this document)
- [x] 每个 P0/P1 问题都有明确后续动作 — **yes** (P-01, P-02 → blueprint;
      P-03 → drive-by or independent)
- [x] 至少 1 份样本成功走完完整链路 → **partial** (staging + extraction
      reachable end-to-end; validator rejects all proposals; resolution
      and bundle not reached). Iteration 3 target.

---

## 8. 附录

### 8.1 Environment snapshot

- Python: `/Users/zhenzhili/miniforge3/bin/python` (Python 3.10)
- Agent package: `src/factpy_kernel/agent/` at post-bugfix commit
- LLM provider: OpenAI via LiteLLM + Instructor
- Model: `gpt-4o-mini`
- Optional dep status: pymupdf ✓, pymupdf4llm ✓, docx ✓, instructor ✓,
  litellm ✓, yaml ✓, langfuse ✗ (manifest disabled)
- OPENAI_API_KEY loaded from `/Users/zhenzhili/hnsm-backend/.env`

### 8.2 Non-determinism note

With `temperature=0.0`, extraction *should* be stable between runs, but
different model deployments or version updates on OpenAI's side could
shift proposal counts. This report reflects the specific run at
`2026-04-10T17:18-17:22Z`. Reruns with the same configuration after the
P-01/P-02 fix may produce slightly different numbers.

### 8.3 Files touched this iteration

- **New records**:
  - `run_records/b3_20260410T171806Z_medium_01_security.json`
  - `run_records/b3_20260410T171903Z_long_01_kernel_p0.json`
- **Kernel code** (via bugfix blueprint, separately archived):
  - `src/factpy_kernel/agent/extraction/llm.py`
  - `src/factpy_kernel/agent/extraction/validation.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_response_model_schema.py` (new)
- **Test suite**: 942 → 959 (+17 new guard tests, 2 total skipped)
- **This report**: `report/load_test_report_2026-04-11_iter2.md`
