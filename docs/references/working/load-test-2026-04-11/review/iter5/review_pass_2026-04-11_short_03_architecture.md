# Review Pass 2026-04-11 — short_03_architecture

## Header

- sample_id: `short_03_architecture`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/short/short_03_architecture.md`
- doc_id: `a0c5e4daa3409c3e`
- total_segments: 23
- total_proposal_count (regen): 10
- total_valid_count (regen): 9
- total_rejection_count (regen): 1
- generated_at: 2026-04-11T12:47:47.834639+00:00

### β.1 context (NEW sample, no iter 4 baseline)

This sample was **added in β.1** (2026-04-11) and has **no iter 4 baseline**. It was introduced specifically for the iter 5 → iter 6 decision process to cross-validate F-03 (Module routing breadth regression).

- **β.1 F-03 control role (original framing — INVALIDATED BY RUN DATA)**: originally labeled "negative control" on the assumption that `architecture_principles.md` has low extraction pressure. **This assumption was invalidated by the canonical run** (segment hit rate 43.5%, highest observed in any B3 run to date). The backtick'd module/directory names (`core`, `authoring`, `application`, `service`, `sdk`, `docs/`, `memory/`) and numbered principle headers produce strong entity candidates. This sample is more accurately described as an **unexpectedly high-pressure narrative sample**, not a negative control.
- **β.1 F-03 control role (revised)**: **unexpected high-pressure sample**. Still useful for F-03 cross-validation but the reading must account for the revised extraction pressure profile — this is not "F-03 absent on a light-narrative doc", it's "F-03 behavior on a moderate-density sample whose pressure comes from backtick'd module terms rather than code literals per se".
- **iter 5 canonical run record**: `run_records/b3_20260411T114046Z_short_03_architecture.json` (canonical: 10 proposals / 8 valid / 2 rejected)
- **This packet vs canonical**: regen produced 10 proposals / 9 valid / 1 rejected (same proposal count, +1 valid, −1 rejection). Per OBS-01 that ±1 drift is normal variance.
- **Pipeline state**: iter 5 `SYSTEM_PROMPT_TEMPLATE` with Semantic Examples block (implemented with deviations, archived). Same prompt state as all other iter 5 packets in this directory.

**New observation from the canonical run**: one of the 2 canonical rejections was **Pattern B applied to `document:mentions`** (`field_values length mismatch for pred_id 'document:mentions': got 4, expected 1`). Previously Pattern B (multi-entry overpacking) was only observed on `module:description`. This is a predicate crossover of a known failure shape — not a new reason class, but a new behavioral context. Logged in `cross_run_observations.md` as OBS-02. Does not affect this review, but reviewer may encounter Document drafts whose field values feel "overly enumerative" even among the valid ones.

**Review purpose**: measure semantic approval rate on this mid-pressure sample. Specifically:
- How many of the 9 drafts are `Module` vs `Document`?
- Of `Module` drafts, how many use backtick'd module/directory names (`core`, `authoring`, `application`, etc.) as `mod_name`? These are project subsystems — **are they valid Module identities or is this F-03 spillover**?
- Of `Document` drafts, how many use fabricated titles vs verbatim identifiers? The architecture doc has explicit section headings that could serve as legit titles.

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
entity_type: "Module"
entity_identity:
  module_name: "core"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "负责运行时语义内核"
confidence: 1.0
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0010"
  char_offset_start: 270
  char_offset_end: 435
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `core` 负责运行时语义内核。
    - `authoring` 负责编译、预检、registry 工作流。
    - `application` 负责 core 之上的中性运行层。
    - `service` 负责前端/BFF 形态的 HTTP 交付面。
    - `sdk` 负责 Python authoring 与 facade 体验。
```

**Summary**: `Module(module_name=core) -- module:description --> string=负责运行时语义内核`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`core` is explicitly listed as a subsystem/module in the source text, and the extracted description is a direct declarative restatement."
```

---

### Draft 002

```yaml
draft_index: 1
entity_type: "Module"
entity_identity:
  module_name: "authoring"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "负责编译、预检、registry 工作流"
confidence: 1.0
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0010"
  char_offset_start: 270
  char_offset_end: 435
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `core` 负责运行时语义内核。
    - `authoring` 负责编译、预检、registry 工作流。
    - `application` 负责 core 之上的中性运行层。
    - `service` 负责前端/BFF 形态的 HTTP 交付面。
    - `sdk` 负责 Python authoring 与 facade 体验。
```

**Summary**: `Module(module_name=authoring) -- module:description --> string=负责编译、预检、registry 工作流`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`authoring` is explicitly listed as a subsystem/module in the source text, and the extracted description is directly supported."
```

---

### Draft 003

```yaml
draft_index: 2
entity_type: "Module"
entity_identity:
  module_name: "application"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "负责 core 之上的中性运行层"
confidence: 1.0
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0010"
  char_offset_start: 270
  char_offset_end: 435
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `core` 负责运行时语义内核。
    - `authoring` 负责编译、预检、registry 工作流。
    - `application` 负责 core 之上的中性运行层。
    - `service` 负责前端/BFF 形态的 HTTP 交付面。
    - `sdk` 负责 Python authoring 与 facade 体验。
```

**Summary**: `Module(module_name=application) -- module:description --> string=负责 core 之上的中性运行层`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`application` is explicitly listed as a subsystem/module in the source text, and the extracted description is directly supported."
```

---

### Draft 004

```yaml
draft_index: 3
entity_type: "Module"
entity_identity:
  module_name: "service"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "负责前端/BFF 形态的 HTTP 交付面"
confidence: 1.0
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0010"
  char_offset_start: 270
  char_offset_end: 435
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `core` 负责运行时语义内核。
    - `authoring` 负责编译、预检、registry 工作流。
    - `application` 负责 core 之上的中性运行层。
    - `service` 负责前端/BFF 形态的 HTTP 交付面。
    - `sdk` 负责 Python authoring 与 facade 体验。
```

**Summary**: `Module(module_name=service) -- module:description --> string=负责前端/BFF 形态的 HTTP 交付面`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`service` is explicitly listed as a subsystem/module in the source text, and the extracted description is directly supported."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Module"
entity_identity:
  module_name: "sdk"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "负责 Python authoring 与 facade 体验"
confidence: 1.0
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0010"
  char_offset_start: 270
  char_offset_end: 435
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `core` 负责运行时语义内核。
    - `authoring` 负责编译、预检、registry 工作流。
    - `application` 负责 core 之上的中性运行层。
    - `service` 负责前端/BFF 形态的 HTTP 交付面。
    - `sdk` 负责 Python authoring 与 facade 体验。
```

**Summary**: `Module(module_name=sdk) -- module:description --> string=负责 Python authoring 与 facade 体验`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`sdk` is explicitly listed as a subsystem/module in the source text, and the extracted description is directly supported."
```

---

### Draft 006

```yaml
draft_index: 5
entity_type: "Document"
entity_identity:
  title: "principle document"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "提炼到原则文档、当前模块 docs 或新任务蓝图中"
confidence: 0.8
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0016"
  char_offset_start: 665
  char_offset_end: 856
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `docs/blueprint_history/` 保存历史阶段讨论、旧设计和未完成方向。
    - 若历史内容仍有价值，应提炼到原则文档、当前模块 docs 或新任务蓝图中，而不是直接重写旧文档。
    - 若需要把历史蓝图桥接到新归档区，应创建显式标注的 reconstructed archive 条目，并保留 `Historical Source` 与可验证 provenance。
```

**Summary**: `Document(title=principle document) -- document:mentions --> string=提炼到原则文档、当前模块 docs 或新任务蓝图中`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`principle document` is not a stable document identifier that appears verbatim as a title in the source text; the extracted object is supported, but the subject is misidentified."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Document"
entity_identity:
  title: "historical blueprint"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "桥接到新归档区"
confidence: 0.7
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0016"
  char_offset_start: 665
  char_offset_end: 856
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `docs/blueprint_history/` 保存历史阶段讨论、旧设计和未完成方向。
    - 若历史内容仍有价值，应提炼到原则文档、当前模块 docs 或新任务蓝图中，而不是直接重写旧文档。
    - 若需要把历史蓝图桥接到新归档区，应创建显式标注的 reconstructed archive 条目，并保留 `Historical Source` 与可验证 provenance。
```

**Summary**: `Document(title=historical blueprint) -- document:mentions --> string=桥接到新归档区`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`historical blueprint` is a synthesized concept label, not a stable document identifier grounded in the source text."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Document"
entity_identity:
  title: "reconstructed archive"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "创建显式标注的 reconstructed archive 条目"
confidence: 0.7
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0016"
  char_offset_start: 665
  char_offset_end: 856
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `docs/blueprint_history/` 保存历史阶段讨论、旧设计和未完成方向。
    - 若历史内容仍有价值，应提炼到原则文档、当前模块 docs 或新任务蓝图中，而不是直接重写旧文档。
    - 若需要把历史蓝图桥接到新归档区，应创建显式标注的 reconstructed archive 条目，并保留 `Historical Source` 与可验证 provenance。
```

**Summary**: `Document(title=reconstructed archive) -- document:mentions --> string=创建显式标注的 reconstructed archive 条目`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`reconstructed archive` names an archive concept, not a grounded document title for a `Document` entity."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Document"
entity_identity:
  title: "Historical Source"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "保留 Historical Source 与可验证 provenance"
confidence: 0.7
note: null

provenance:
  source_document_id: "a0c5e4daa3409c3e"
  segment_id: "a0c5e4da_0016"
  char_offset_start: 665
  char_offset_end: 856
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `docs/blueprint_history/` 保存历史阶段讨论、旧设计和未完成方向。
    - 若历史内容仍有价值，应提炼到原则文档、当前模块 docs 或新任务蓝图中，而不是直接重写旧文档。
    - 若需要把历史蓝图桥接到新归档区，应创建显式标注的 reconstructed archive 条目，并保留 `Historical Source` 与可验证 provenance。
```

**Summary**: `Document(title=Historical Source) -- document:mentions --> string=保留 Historical Source 与可验证 provenance`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`Historical Source` is a provenance field label in the source text, not the title of a document being mentioned."
```

---
