# Review Pass 2026-04-11 — medium_02_blueprint_backref

## Header

- sample_id: `medium_02_blueprint_backref`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/medium/medium_02_blueprint_backref.md`
- doc_id: `931c74c474907bab`
- total_segments: 58
- total_proposal_count (regen): 10
- total_valid_count (regen): 10
- total_rejection_count (regen): 0
- generated_at: 2026-04-11T12:47:24.336483+00:00

### β.1 context (NEW sample, no iter 4 baseline)

This sample was **added in β.1** (2026-04-11) and has **no iter 4 baseline**. It was introduced specifically for the iter 5 → iter 6 decision process to cross-validate F-03 (Module routing breadth regression).

- **β.1 F-03 control role**: **POSITIVE control** — `medium_02_blueprint_backref` is an archived task blueprint (`2026-03-17_candidate-id-support-backref.md`) with high code-literal density (class names, function names, file paths, REST endpoints). Same structural profile as `long_01_kernel_p0` at ~1/5 the size. Expected to reproduce F-03 if the regression is content-density-proportional.
- **iter 5 canonical run record**: `run_records/b3_20260411T105211Z_medium_02_blueprint_backref.json` (canonical: 9 proposals / 9 valid / 0 rejected)
- **This packet vs canonical**: regen produced 10 proposals / 10 valid / 0 rejected (+1 proposal vs canonical, matches 0 rejections). Per OBS-01 that ±1 drift is normal variance.
- **Pipeline state**: iter 5 `SYSTEM_PROMPT_TEMPLATE` with Semantic Examples block (implemented with deviations, archived). Same prompt state as all other iter 5 packets in this directory. No code or prompt changes between iter 5 and β.1.

**Surprise finding from canonical run**: `medium_02` produced **zero structural rejections** — no Pattern A, no Pattern B, no any-shape rejections. This contrasts sharply with `long_01_kernel_p0`'s iter 5 canonical (43/36/7), which had Pattern B residual. Reviewer should pay attention to whether the 10 valid drafts are:

1. **All semantically correct** → iter 5 prompt works cleanly on short blueprints; long_01's rejections were a length/complexity effect
2. **Some F-03 failures hidden in valid drafts** → the absence of structural rejections is not the same as the absence of F-03

**Review purpose**: measure the **semantic F-03 rate** on this positive control. Specifically:
- How many of the 10 drafts are `Module` vs `Document`?
- Of the `Module` drafts, how many are actually real project-code classes/functions vs. file paths / HTTP headers / stdlib / hazard IDs (the F-03 failure shapes observed on long_01)?
- Of the `Document` drafts, how many use verbatim stable identifiers (F-01 success) vs fabricated titles (F-01 residual)?

**Do NOT backfill into any run_record.** Same reason as iter 5 packets: run_records carry pipeline metrics, not per-draft review decisions. Results will be aggregated into a new β.1 summary artifact after all 3 new packets are reviewed.

## Review instructions

For each draft below, fill in the `REVIEW` block at the bottom:

- `approve`: one of `yes` | `no` | `partial`
  - `yes` — the extracted fact is supported by `raw_text` and semantically correct
  - `no` — the fact is wrong, hallucinated, or unsupported by `raw_text`
  - `partial` — the fact is partially correct but needs rewording, scoping, or a different predicate
- `reason_code`: one of
  - `CORRECT` — no issue (use with `approve: yes`)
  - `HALLUCINATED` — fact is not present in raw_text at all
  - `OVERGENERAL` — fact is in raw_text but the object is too broad / too vague
  - `WRONG_ENTITY` — subject entity is mis-identified
  - `WRONG_PREDICATE` — relation should use a different pred_id
  - `WRONG_ARG` — the object/field_values value is factually wrong
  - `DUPLICATE` — same fact as another approved draft in this packet
  - `AMBIGUOUS` — raw_text is genuinely ambiguous; cannot judge
  - `OTHER` — fill in notes
- `notes`: free-text, optional

Summary metrics will be backfilled into the run_record `review` block after the pass is complete. This packet is the source of truth for per-draft decisions.

---

## Drafts

### Draft 001

```yaml
draft_index: 0
entity_type: "Document"
entity_identity:
  title: "architecture_principles.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=architecture_principles.md) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`architecture_principles.md` is genuinely mentioned, but `implemented` is the status of the current blueprint, not a supported topic or status for that related document."
```

---

### Draft 002

```yaml
draft_index: 1
entity_type: "Document"
entity_identity:
  title: "2026-03-17_durable-artifact-storage.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=2026-03-17_durable-artifact-storage.md) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`2026-03-17_durable-artifact-storage.md` is genuinely listed as a related doc, but `implemented` is not supported as a property of that document in the source segment."
```

---

### Draft 003

```yaml
draft_index: 2
entity_type: "Document"
entity_identity:
  title: "2026-03-17_support-artifact-native-capture.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=2026-03-17_support-artifact-native-capt…) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`2026-03-17_support-artifact-native-capture.md` is genuinely mentioned, but `implemented` is inherited from the current blueprint header rather than supported for that related document."
```

---

### Draft 004

```yaml
draft_index: 3
entity_type: "Document"
entity_identity:
  title: "2026-03-17_support-artifact-readback.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=2026-03-17_support-artifact-readback.md) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`2026-03-17_support-artifact-readback.md` is genuinely listed as a related doc, but `implemented` is not grounded as a fact about that document."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Document"
entity_identity:
  title: "2026-03-17_runtime-service-explain-readback.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=2026-03-17_runtime-service-explain-read…) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`2026-03-17_runtime-service-explain-readback.md` is genuinely mentioned, but the extracted value `implemented` is not supported for that related document in this segment."
```

---

### Draft 006

```yaml
draft_index: 5
entity_type: "Document"
entity_identity:
  title: "2026-03-17_candidate-id-support-backref.audit.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "implemented"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0001"
  char_offset_start: 48
  char_offset_end: 1002
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-03-17
    - Last Updated: 2026-03-17
    - Related Modules:
      - `src/factpy_kernel/core/store/runtime.py`
      - `src/factpy_kernel/core/store/_evaluate.py`
      - `src/factpy_kernel/core/store/_builders.py`
      - `src/factpy_kernel/core/derivation/candidates.py`
      - `src/factpy_kernel/service/runtime_v1.py`
    - Related Docs:
      - [docs/architecture_principles.md](../../architecture_principles.md)
      - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
      - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
      - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
      - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
    - Audit Log:
      - [2026-03-17_candidate-id-support-backref.audit.md](./2026-03-17_candidate-id-support-backref.audit.md)
```

**Summary**: `Document(title=2026-03-17_candidate-id-support-backref…) -- document:mentions --> string=implemented`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The audit file is genuinely linked in the segment, but `implemented` is still the status of the current blueprint, not a grounded fact about the audit document."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Document"
entity_identity:
  title: "CANDIDATE_PROTOCOL_V2.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "candidate-facing explain backref 说明"
confidence: 0.8
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0057"
  char_offset_start: 5718
  char_offset_end: 6927
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - 最终落地结果：
      - `Store` 新增 `_candidate_support_index`、`_remember_candidate_support(...)`、`_lookup_candidate_support(...)` 和公开 helper `get_candidate_support_digest(candidate_id)`
      - native evaluate 路径现已在 builder 外层登记 `candidate_id -> support_digest` backref
      - 仅 `support_kind="native_binding_v1"` 的 candidates 会进入 backref index；兼容路径的 `support_kind="none"` 不会被登记
      - entity path 下同一 row 产出的 entity candidate 与 role fact candidates 会共享同一 `support_digest` backref
      - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记
      - `src/factpy_kernel/core/docs/01_architecture.md` / `.en.md` 与 `CANDIDATE_PROTOCOL_V2.md` 已同步补充 candidate-facing explain backref 说明
    - 与 blueprint 不同的地方：
      - 写入点仍位于 `_evaluate.py` 的 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 `support_kind/support_digest`，没有继续保留额外的 binding-to-support 对齐层
    - 为什么会有这些调整：
      - candidate 本身已经携带最终的 `support_kind/support_digest`，直接按 candidate 登记 backref 更稳，也避免在 index 层重复实现 binding 重建或 row/candidate 对齐推断
    - 归档说明：
      - 本切片已实现并完成 targeted `unittest` 与 compile 验证；后续若继续推进 candidate-facing explainability，应在此基础上另开 convenience API 或 generic explain protocol 子蓝图，而不是在本文件中继续扩写
```

**Summary**: `Document(title=CANDIDATE_PROTOCOL_V2.md) -- document:mentions --> string=candidate-facing explain backref 说明`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`CANDIDATE_PROTOCOL_V2.md` is explicitly named in the source text as having synchronized candidate-facing explain backref documentation."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Document"
entity_identity:
  title: "src/factpy_kernel/core/docs/01_architecture.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "candidate-facing explain backref 说明"
confidence: 0.8
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0057"
  char_offset_start: 5718
  char_offset_end: 6927
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - 最终落地结果：
      - `Store` 新增 `_candidate_support_index`、`_remember_candidate_support(...)`、`_lookup_candidate_support(...)` 和公开 helper `get_candidate_support_digest(candidate_id)`
      - native evaluate 路径现已在 builder 外层登记 `candidate_id -> support_digest` backref
      - 仅 `support_kind="native_binding_v1"` 的 candidates 会进入 backref index；兼容路径的 `support_kind="none"` 不会被登记
      - entity path 下同一 row 产出的 entity candidate 与 role fact candidates 会共享同一 `support_digest` backref
      - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记
      - `src/factpy_kernel/core/docs/01_architecture.md` / `.en.md` 与 `CANDIDATE_PROTOCOL_V2.md` 已同步补充 candidate-facing explain backref 说明
    - 与 blueprint 不同的地方：
      - 写入点仍位于 `_evaluate.py` 的 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 `support_kind/support_digest`，没有继续保留额外的 binding-to-support 对齐层
    - 为什么会有这些调整：
      - candidate 本身已经携带最终的 `support_kind/support_digest`，直接按 candidate 登记 backref 更稳，也避免在 index 层重复实现 binding 重建或 row/candidate 对齐推断
    - 归档说明：
      - 本切片已实现并完成 targeted `unittest` 与 compile 验证；后续若继续推进 candidate-facing explainability，应在此基础上另开 convenience API 或 generic explain protocol 子蓝图，而不是在本文件中继续扩写
```

**Summary**: `Document(title=src/factpy_kernel/core/docs/01_architec…) -- document:mentions --> string=candidate-facing explain backref 说明`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`src/factpy_kernel/core/docs/01_architecture.md` is explicitly named in the source text as having synchronized candidate-facing explain backref documentation."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Module"
entity_identity:
  module_name: "src/factpy_kernel/tests/test_phase3_contracts_v1.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记"
confidence: 0.9
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0057"
  char_offset_start: 5718
  char_offset_end: 6927
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - 最终落地结果：
      - `Store` 新增 `_candidate_support_index`、`_remember_candidate_support(...)`、`_lookup_candidate_support(...)` 和公开 helper `get_candidate_support_digest(candidate_id)`
      - native evaluate 路径现已在 builder 外层登记 `candidate_id -> support_digest` backref
      - 仅 `support_kind="native_binding_v1"` 的 candidates 会进入 backref index；兼容路径的 `support_kind="none"` 不会被登记
      - entity path 下同一 row 产出的 entity candidate 与 role fact candidates 会共享同一 `support_digest` backref
      - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记
      - `src/factpy_kernel/core/docs/01_architecture.md` / `.en.md` 与 `CANDIDATE_PROTOCOL_V2.md` 已同步补充 candidate-facing explain backref 说明
    - 与 blueprint 不同的地方：
      - 写入点仍位于 `_evaluate.py` 的 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 `support_kind/support_digest`，没有继续保留额外的 binding-to-support 对齐层
    - 为什么会有这些调整：
      - candidate 本身已经携带最终的 `support_kind/support_digest`，直接按 candidate 登记 backref 更稳，也避免在 index 层重复实现 binding 重建或 row/candidate 对齐推断
    - 归档说明：
      - 本切片已实现并完成 targeted `unittest` 与 compile 验证；后续若继续推进 candidate-facing explainability，应在此基础上另开 convenience API 或 generic explain protocol 子蓝图，而不是在本文件中继续扩写
```

**Summary**: `Module(module_name=src/factpy_kernel/tests/test_phase3_con…) -- module:description --> string=已新增 focused unittest，覆盖 native backref、…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`src/factpy_kernel/tests/test_phase3_contracts_v1.py` is a test file path, not the right `Module` subject type for this schema even though the coverage statement itself is supported."
```

---

### Draft 010

```yaml
draft_index: 9
entity_type: "Module"
entity_identity:
  module_name: "_evaluate.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "写入点仍位于 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 support_kind/support_digest"
confidence: 0.85
note: null

provenance:
  source_document_id: "931c74c474907bab"
  segment_id: "931c74c4_0057"
  char_offset_start: 5718
  char_offset_end: 6927
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - 最终落地结果：
      - `Store` 新增 `_candidate_support_index`、`_remember_candidate_support(...)`、`_lookup_candidate_support(...)` 和公开 helper `get_candidate_support_digest(candidate_id)`
      - native evaluate 路径现已在 builder 外层登记 `candidate_id -> support_digest` backref
      - 仅 `support_kind="native_binding_v1"` 的 candidates 会进入 backref index；兼容路径的 `support_kind="none"` 不会被登记
      - entity path 下同一 row 产出的 entity candidate 与 role fact candidates 会共享同一 `support_digest` backref
      - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused unittest，覆盖 native backref、missing id returns `None`、以及 compatibility candidate 不被登记
      - `src/factpy_kernel/core/docs/01_architecture.md` / `.en.md` 与 `CANDIDATE_PROTOCOL_V2.md` 已同步补充 candidate-facing explain backref 说明
    - 与 blueprint 不同的地方：
      - 写入点仍位于 `_evaluate.py` 的 builder 外层，但实际登记逻辑直接依赖 candidate 自身已写入的 `support_kind/support_digest`，没有继续保留额外的 binding-to-support 对齐层
    - 为什么会有这些调整：
      - candidate 本身已经携带最终的 `support_kind/support_digest`，直接按 candidate 登记 backref 更稳，也避免在 index 层重复实现 binding 重建或 row/candidate 对齐推断
    - 归档说明：
      - 本切片已实现并完成 targeted `unittest` 与 compile 验证；后续若继续推进 candidate-facing explainability，应在此基础上另开 convenience API 或 generic explain protocol 子蓝图，而不是在本文件中继续扩写
```

**Summary**: `Module(module_name=_evaluate.py) -- module:description --> string=写入点仍位于 builder 外层，但实际登记逻辑直接依赖 candidate…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`_evaluate.py` is a file/module artifact, not the intended `Module` subject type in this schema; the implementation detail is supported, but the entity routing is too broad."
```

---
