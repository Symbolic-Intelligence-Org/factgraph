# Review Pass 2026-04-11 — long_01_kernel_p0

## Header

- sample_id: `long_01_kernel_p0`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/long/long_01_kernel_p0.md`
- doc_id: `58b55aaa2a74dbc5`
- total_segments: 207
- total_proposal_count (regen): 108
- total_valid_count (regen): 77
- total_rejection_count (regen): 31
- generated_at: 2026-04-10T21:03:10.937165+00:00

### Archived iter 4 reference

- archived_run_record: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/run_records/b3_20260410T194711Z_long_01_kernel_p0.json`
- archived_bundle_id: `bundle_172f0fcd7765` (in-memory only, not reproducible)
- archived_valid_count: 57 — **drift from archived iter 4: +20**

### Variance caveat (added 2026-04-11, read before reviewing)

**This packet is ONE sample from the iter 4 distribution, not the definitive iter 4 bundle.**

After this packet was generated, a third canonical run was taken on the same pair of samples for a stability check. Three runs on `long_01_kernel_p0` produced `57 / 77 / 60` valid drafts, and three runs on `medium_01_security` produced `14 / 9 / 7` valid drafts — all with identical prompt, schema, manifest, and `temperature=0.0`. On long specifically, `run 2 (77)` is an upper outlier; `run 1 (57)` and `run 3 (60)` agree to within 3. See:

- [iteration 4 report §8 Addendum](../report/load_test_report_2026-04-11_iter4.md#8-addendum--2026-04-11-variance-correction)
- [cross-run observations OBS-01](../cross_run_observations.md#obs-01-p2-llm-extraction-counts-have-visible-variance-at-temperature00)

**Implications for this review pass**:

1. The 77 drafts in this packet are a **high-end sample** of what the current prompt produces on `long_01_kernel_p0`. The "typical" run generates ~57-60 valid drafts; this packet has ~17 more than the median. Those extra ~17 are not wrong; they are additional valid extractions the backend happened to produce in this particular run.
2. The review's purpose is **semantic quality assessment** — "of these 77 drafts, how many are correct?" — not count reconciliation against the archived run_record.
3. **Do NOT backfill these review results into the archived iter 4 run_record** (`b3_20260410T194711Z_long_01_kernel_p0.json`). That record refers to a different in-memory bundle that no longer exists. If any backfill is appropriate, it should go into a new summary artifact, not the archived JSON.
4. Rejection shape is 100% stable across all three runs: 100% `schema_field_type_mismatch`, 100% on `document:mentions`, 100% `got 2, expected 1` Pattern A subject leakage. Count variance is independent of error-mode analysis.
5. Because this sample is on the high end, the semantic approval **rate** (not count) measured here is slightly more informative per-draft — if 70/77 = ~91% are semantically correct, that is a per-draft signal, and the fact that a different run would have produced 60 drafts rather than 77 doesn't invalidate the 91% rate claim.

The archived iter 4 bundle IDs died with the process that created them (`BundleManager` is in-memory only). This packet references newly regenerated specs.

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
  title: "product-readiness-audit-2026-04-09.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0001"
  char_offset_start: 47
  char_offset_end: 430
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-04-11
    - Parent: [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md)
    - Scope: **Kernel 侧**（非 agent 线），独立于 agent 蓝图推进
    - Related Modules:
      - `src/factpy_kernel/service/app_v1.py`
      - `src/factpy_kernel/service/runtime_v1.py`
      - `src/factpy_kernel/core/store/ledger.py`
      - `.env` / `.gitignore`
```

**Summary**: `Document(title=product-readiness-audit-2026-04-09.md) -- document:mentions --> string=Kernel 侧（非 agent 线），独立于 agent 蓝图推进`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The scope sentence is supported, but the extracted subject is the parent audit document rather than the current kernel P0 blueprint."
```

---

### Draft 002

```yaml
draft_index: 1
entity_type: "Module"
entity_identity:
  module_name: "app_v1.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0001"
  char_offset_start: 47
  char_offset_end: 430
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-04-11
    - Parent: [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md)
    - Scope: **Kernel 侧**（非 agent 线），独立于 agent 蓝图推进
    - Related Modules:
      - `src/factpy_kernel/service/app_v1.py`
      - `src/factpy_kernel/service/runtime_v1.py`
      - `src/factpy_kernel/core/store/ledger.py`
      - `.env` / `.gitignore`
```

**Summary**: `Module(module_name=app_v1.py) -- module:description --> string=Kernel 侧（非 agent 线），独立于 agent 蓝图推进`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The related-module list names app_v1.py, but the scope sentence is about the blueprint as a whole, not a description of this module."
```

---

### Draft 003

```yaml
draft_index: 2
entity_type: "Module"
entity_identity:
  module_name: "runtime_v1.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0001"
  char_offset_start: 47
  char_offset_end: 430
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-04-11
    - Parent: [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md)
    - Scope: **Kernel 侧**（非 agent 线），独立于 agent 蓝图推进
    - Related Modules:
      - `src/factpy_kernel/service/app_v1.py`
      - `src/factpy_kernel/service/runtime_v1.py`
      - `src/factpy_kernel/core/store/ledger.py`
      - `.env` / `.gitignore`
```

**Summary**: `Module(module_name=runtime_v1.py) -- module:description --> string=Kernel 侧（非 agent 线），独立于 agent 蓝图推进`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "runtime_v1.py is listed as a related module, but the extracted value is still blueprint scope text rather than a module description."
```

---

### Draft 004

```yaml
draft_index: 3
entity_type: "Module"
entity_identity:
  module_name: "ledger.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0001"
  char_offset_start: 47
  char_offset_end: 430
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Status: implemented
    - Created: 2026-04-11
    - Parent: [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md)
    - Scope: **Kernel 侧**（非 agent 线），独立于 agent 蓝图推进
    - Related Modules:
      - `src/factpy_kernel/service/app_v1.py`
      - `src/factpy_kernel/service/runtime_v1.py`
      - `src/factpy_kernel/core/store/ledger.py`
      - `.env` / `.gitignore`
```

**Summary**: `Module(module_name=ledger.py) -- module:description --> string=Kernel 侧（非 agent 线），独立于 agent 蓝图推进`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "ledger.py is correctly surfaced from the related-modules list, but the attached text describes blueprint scope, not the module itself."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Document"
entity_identity:
  title: "修复产品落地审计（2026-04-09）"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "P0 级隐患"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0004"
  char_offset_start: 450
  char_offset_end: 519
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **交付目标**：修复产品落地审计（2026-04-09）识别的 **P0 级隐患**，让 FactPy Kernel 可以通过上线门槛。
```

**Summary**: `Document(title=修复产品落地审计（2026-04-09）) -- document:mentions --> string=P0 级隐患`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The text supports a delivery goal around fixing P0 issues, but the extracted Document title is an inline action target rather than a stable document identity."
```

---

### Draft 006

```yaml
draft_index: 5
entity_type: "Document"
entity_identity:
  title: "src/factpy_kernel/service/auth.py"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "新建文件"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0023"
  char_offset_start: 2693
  char_offset_end: 2738
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **新建文件**: `src/factpy_kernel/service/auth.py`
```

**Summary**: `Document(title=src/factpy_kernel/service/auth.py) -- document:mentions --> string=新建文件`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_PREDICATE"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source clearly marks auth.py as a new file, but that is closer to a file/module description than Document(... ) with document:mentions."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Document"
entity_identity:
  title: "Example route modification"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "/v1/runtime/sessions/open"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0040"
  char_offset_start: 5180
  char_offset_end: 5429
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # Example route modification
    @app.post(
        "/v1/runtime/sessions/open",
        dependencies=[Depends(require_api_key)],   # 新增
    )
    def route_open_runtime_session(dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.open_runtime_session(dto)
    ```
```

**Summary**: `Document(title=Example route modification) -- document:mentions --> string=/v1/runtime/sessions/open`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The route path is present in the code example, but the extracted subject is the example-section heading rather than a stable document entity."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Document"
entity_identity:
  title: "Example route modification"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "runtime_v1.open_runtime_session"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0040"
  char_offset_start: 5180
  char_offset_end: 5429
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # Example route modification
    @app.post(
        "/v1/runtime/sessions/open",
        dependencies=[Depends(require_api_key)],   # 新增
    )
    def route_open_runtime_session(dto: dict[str, Any]) -> dict[str, Any]:
        return runtime_v1.open_runtime_session(dto)
    ```
```

**Summary**: `Document(title=Example route modification) -- document:mentions --> string=runtime_v1.open_runtime_session`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The runtime_v1.open_runtime_session call is supported, but the example heading was turned into the document identity."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "实现，含 AuthConfig + require_api_key"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=实现，含 AuthConfig + require_api_key`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This checklist item is supported by the blueprint, but it is an implementation task, not a durable module description."
```

---

### Draft 010

```yaml
draft_index: 9
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "所有 40+ 路由追加 dependencies=[Depends(require_api_key)]"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=所有 40+ 路由追加 dependencies=[Depends(requi…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Appending dependencies to routes is an acceptance/checklist bullet, not the standing description of service/auth.py."
```

---

### Draft 011

```yaml
draft_index: 10
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "未配置 FACTPY_KERNEL_API_KEYS 且未设 FACTPY_KERNEL_AUTH_DISABLED=true 时，所有请求返回 503"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=未配置 FACTPY_KERNEL_API_KEYS 且未设 FACTPY_K…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The 503 behavior is explicitly listed, but it is testable behavior/acceptance criteria rather than a concise module description."
```

---

### Draft 012

```yaml
draft_index: 11
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "设置 FACTPY_KERNEL_AUTH_DISABLED=true 时所有请求放行（dev mode）"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=设置 FACTPY_KERNEL_AUTH_DISABLED=true 时所有…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The dev-mode allowance is present in the list, but it is a behavior requirement rather than the module's descriptive summary."
```

---

### Draft 013

```yaml
draft_index: 12
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "配置 API key 后，无 header / 错误 header 返回 401"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=配置 API key 后，无 header / 错误 header 返回 401`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The 401 behavior is supported in the source, but this is an acceptance bullet and not a stable description of the auth module."
```

---

### Draft 014

```yaml
draft_index: 13
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "正确 header 返回 200"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=正确 header 返回 200`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Returning 200 for the correct header is supported, but it is still an outcome/checklist statement rather than a module description."
```

---

### Draft 015

```yaml
draft_index: 14
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "常数时间比较（hmac.compare_digest）"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=常数时间比较（hmac.compare_digest）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Using compare_digest is a concrete implementation requirement, but not the enduring description of the module."
```

---

### Draft 016

```yaml
draft_index: 15
entity_type: "Module"
entity_identity:
  module_name: "service/auth.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0048"
  char_offset_start: 5936
  char_offset_end: 6369
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
    - [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
    - [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
    - [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
    - [ ] 配置 API key 后，无 header / 错误 header 返回 401
    - [ ] 正确 header 返回 200
    - [ ] 常数时间比较（hmac.compare_digest）
    - [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形
```

**Summary**: `Module(module_name=service/auth.py) -- module:description --> string=单测覆盖：enabled/disabled/no_keys/valid_key…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The test-coverage line is real, but it describes planned verification scope rather than the module itself."
```

---

### Draft 017

```yaml
draft_index: 16
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Minimal HTTP transport over service v1 routes."
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0056"
  char_offset_start: 7055
  char_offset_end: 7133
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    class HttpRuntimeAPI:
        """Minimal HTTP transport over service v1 routes."""
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=Minimal HTTP transport over service v1 …`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the class name and its docstring match exactly."
```

---

### Draft 018

```yaml
draft_index: 17
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "追加 api_key / api_key_header 参数"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0064"
  char_offset_start: 8538
  char_offset_end: 8847
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
    - [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
    - [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
    - [ ] 单测：未提供 `api_key` 时请求不含该 header
    - [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=追加 api_key / api_key_header 参数`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Adding api_key parameters is explicitly listed, but this is a planned change item rather than the module's standing description."
```

---

### Draft 019

```yaml
draft_index: 18
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "现有不传 api_key 的构造调用保持向后兼容"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0064"
  char_offset_start: 8538
  char_offset_end: 8847
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
    - [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
    - [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
    - [ ] 单测：未提供 `api_key` 时请求不含该 header
    - [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=现有不传 api_key 的构造调用保持向后兼容`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Backward compatibility is a valid checklist item, but not a durable description of HttpRuntimeAPI."
```

---

### Draft 020

```yaml
draft_index: 19
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "单测：HttpRuntimeAPI(base, api_key=\"xxx\") 的所有请求包含 X-FactPy-API-Key: xxx header"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0064"
  char_offset_start: 8538
  char_offset_end: 8847
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
    - [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
    - [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
    - [ ] 单测：未提供 `api_key` 时请求不含该 header
    - [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=单测：HttpRuntimeAPI(base, api_key="xxx") …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This line is a unit-test expectation, not the descriptive purpose of the module."
```

---

### Draft 021

```yaml
draft_index: 20
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "单测：未提供 api_key 时请求不含该 header"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0064"
  char_offset_start: 8538
  char_offset_end: 8847
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
    - [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
    - [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
    - [ ] 单测：未提供 `api_key` 时请求不含该 header
    - [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=单测：未提供 api_key 时请求不含该 header`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The header-absence test is supported, but it is still a test case rather than a stable module description."
```

---

### Draft 022

```yaml
draft_index: 21
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "集成测试：kernel 启用认证 + HttpRuntimeAPI 传正确 key → 200；传错误 key → 401"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0064"
  char_offset_start: 8538
  char_offset_end: 8847
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
    - [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
    - [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
    - [ ] 单测：未提供 `api_key` 时请求不含该 header
    - [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401
```

**Summary**: `Module(module_name=HttpRuntimeAPI) -- module:description --> string=集成测试：kernel 启用认证 + HttpRuntimeAPI 传正确 k…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The integration test statement is real, but it describes verification behavior rather than the module's core description."
```

---

### Draft 023

```yaml
draft_index: 22
entity_type: "Document"
entity_identity:
  title: "KP0-07 冻结"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "线程本地连接池（thread-local connection）+ 保留 WAL 模式的最小改造方案"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0072"
  char_offset_start: 9540
  char_offset_end: 9611
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **KP0-07 冻结**：采用**线程本地连接池（thread-local connection）+ 保留 WAL 模式**的最小改造方案。
```

**Summary**: `Document(title=KP0-07 冻结) -- document:mentions --> string=线程本地连接池（thread-local connection）+ 保留 WA…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The frozen decision text is supported, but the section label 'KP0-07 冻结' is not a stable document identity."
```

---

### Draft 024

```yaml
draft_index: 23
entity_type: "Document"
entity_identity:
  title: "KP0-04 \"最小可用\""
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "FastAPI + threaded worker"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0075"
  char_offset_start: 9820
  char_offset_end: 10000
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **显式承认的边界**：
    - **本方案只解决单进程多线程并发**（FastAPI + threaded worker）
    - **不解决多进程并发**（多 worker 部署仍然每个 worker 独立 ledger）
    - 多进程部署依然需要依赖共享存储层（PostgreSQL / 网络文件系统）
    - 这是 KP0-04 "最小可用" 的 trade-off
```

**Summary**: `Document(title=KP0-04 "最小可用") -- document:mentions --> string=FastAPI + threaded worker`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The trade-off around FastAPI + threaded workers is in the source, but 'KP0-04' is a section key rather than a real document identity."
```

---

### Draft 025

```yaml
draft_index: 24
entity_type: "Module"
entity_identity:
  module_name: "get_claim"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=get_claim) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The named helper is in the coverage list, but '覆盖范围（至少）' is only a generic heading and not a description of this item."
```

---

### Draft 026

```yaml
draft_index: 25
entity_type: "Module"
entity_identity:
  module_name: "find_claims"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=find_claims) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The helper/function name is present, but the extracted value is the shared coverage heading rather than a module-specific description."
```

---

### Draft 027

```yaml
draft_index: 26
entity_type: "Module"
entity_identity:
  module_name: "find_claim_args"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=find_claim_args) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This extraction points at a real API/helper, but the object text is the section heading '覆盖范围（至少）', not its actual description."
```

---

### Draft 028

```yaml
draft_index: 27
entity_type: "Module"
entity_identity:
  module_name: "find_meta"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=find_meta) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The underlying function/helper is listed, but the extracted description is only the generic coverage label."
```

---

### Draft 029

```yaml
draft_index: 28
entity_type: "Module"
entity_identity:
  module_name: "find_annotations"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=find_annotations) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The item exists in the coverage enumeration, but '覆盖范围（至少）' is not a meaningful module description for this entity."
```

---

### Draft 030

```yaml
draft_index: 29
entity_type: "Module"
entity_identity:
  module_name: "has_active_revocation"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=has_active_revocation) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The named public surface is supported by the list, but the extracted value is only the coverage heading."
```

---

### Draft 031

```yaml
draft_index: 30
entity_type: "Module"
entity_identity:
  module_name: "find_revoker"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=find_revoker) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The extracted entity comes from the '覆盖范围' list, but the object text is too generic to count as the entity's description."
```

---

### Draft 032

```yaml
draft_index: 31
entity_type: "Module"
entity_identity:
  module_name: "claims"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=claims) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The coverage list supports the entity name, but not the generic '覆盖范围（至少）' description attached to it."
```

---

### Draft 033

```yaml
draft_index: 32
entity_type: "Module"
entity_identity:
  module_name: "claim_args"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=claim_args) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This function/helper is truly listed, but the extracted object is still the umbrella heading rather than a concrete description."
```

---

### Draft 034

```yaml
draft_index: 33
entity_type: "Module"
entity_identity:
  module_name: "meta_rows"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=meta_rows) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The target name is in the source enumeration, but the description is only the repeated coverage heading."
```

---

### Draft 035

```yaml
draft_index: 34
entity_type: "Module"
entity_identity:
  module_name: "annotation_rows"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=annotation_rows) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source names this helper/property, but '覆盖范围（至少）' is not its actual description."
```

---

### Draft 036

```yaml
draft_index: 35
entity_type: "Module"
entity_identity:
  module_name: "revokes"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=revokes) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The entity is part of the coverage scope, but the extracted description remains the generic heading and loses the specific role."
```

---

### Draft 037

```yaml
draft_index: 36
entity_type: "Module"
entity_identity:
  module_name: "_claims"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=_claims) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "A real public surface is being pointed at, but the object text is still only the coverage heading."
```

---

### Draft 038

```yaml
draft_index: 37
entity_type: "Module"
entity_identity:
  module_name: "_claim_args"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=_claim_args) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The extracted item is named in the source list, but the generic heading is not a sufficient module description."
```

---

### Draft 039

```yaml
draft_index: 38
entity_type: "Module"
entity_identity:
  module_name: "_meta_by_*"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=_meta_by_*) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The helper/property is covered by the list, but the extracted text is merely the shared heading."
```

---

### Draft 040

```yaml
draft_index: 39
entity_type: "Module"
entity_identity:
  module_name: "_ingest_keys"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖范围（至少）"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0118"
  char_offset_start: 19320
  char_offset_end: 19627
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **覆盖范围**（至少）：
    - `get_claim`
    - `find_claims`
    - `find_claim_args`
    - `find_meta`
    - `find_annotations`
    - `has_active_revocation`
    - `find_revoker`
    - `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
    - 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper
```

**Summary**: `Module(module_name=_ingest_keys) -- module:description --> string=覆盖范围（至少）`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The entity is real, but the extracted description is only the repeated '覆盖范围（至少）' heading."
```

---

### Draft 041

```yaml
draft_index: 40
entity_type: "Document"
entity_identity:
  title: "KP0-08 冻结"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "`:memory:` 模式仅用于**单线程测试**。生产必须使用文件路径。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0124"
  char_offset_start: 20382
  char_offset_end: 20433
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **KP0-08 冻结**：`:memory:` 模式仅用于**单线程测试**。生产必须使用文件路径。
```

**Summary**: `Document(title=KP0-08 冻结) -- document:mentions --> string=`:memory:` 模式仅用于**单线程测试**。生产必须使用文件路径。`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source lists this entity in scope, but the object value is still just the generic coverage heading."
```

---

### Draft 042

```yaml
draft_index: 41
entity_type: "Document"
entity_identity:
  title: "不做 aiosqlite 迁移"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "独立蓝图"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0132"
  char_offset_start: 22222
  char_offset_end: 22387
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **不做 aiosqlite 迁移**（独立蓝图）
    - **不做 PostgreSQL 后端**（独立蓝图）
    - **不解决多进程并发**（KP0-04 边界）
    - **不做 connection pool 监控**（留给 P1 observability）
    - **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）
```

**Summary**: `Document(title=不做 aiosqlite 迁移) -- document:mentions --> string=独立蓝图`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The constraint is directly supported, but 'KP0-08 冻结' is a section label rather than a durable document title."
```

---

### Draft 043

```yaml
draft_index: 42
entity_type: "Document"
entity_identity:
  title: "不做 PostgreSQL 后端"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "独立蓝图"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0132"
  char_offset_start: 22222
  char_offset_end: 22387
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **不做 aiosqlite 迁移**（独立蓝图）
    - **不做 PostgreSQL 后端**（独立蓝图）
    - **不解决多进程并发**（KP0-04 边界）
    - **不做 connection pool 监控**（留给 P1 observability）
    - **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）
```

**Summary**: `Document(title=不做 PostgreSQL 后端) -- document:mentions --> string=独立蓝图`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The bullet is present verbatim, but the heading text was turned into the document identity."
```

---

### Draft 044

```yaml
draft_index: 43
entity_type: "Document"
entity_identity:
  title: "不解决多进程并发"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "KP0-04 边界"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0132"
  char_offset_start: 22222
  char_offset_end: 22387
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **不做 aiosqlite 迁移**（独立蓝图）
    - **不做 PostgreSQL 后端**（独立蓝图）
    - **不解决多进程并发**（KP0-04 边界）
    - **不做 connection pool 监控**（留给 P1 observability）
    - **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）
```

**Summary**: `Document(title=不解决多进程并发) -- document:mentions --> string=KP0-04 边界`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The content is supported, but '不做 PostgreSQL 后端' is a list item label rather than a stable document identity."
```

---

### Draft 045

```yaml
draft_index: 44
entity_type: "Document"
entity_identity:
  title: "不做 connection pool 监控"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "留给 P1 observability"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0132"
  char_offset_start: 22222
  char_offset_end: 22387
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **不做 aiosqlite 迁移**（独立蓝图）
    - **不做 PostgreSQL 后端**（独立蓝图）
    - **不解决多进程并发**（KP0-04 边界）
    - **不做 connection pool 监控**（留给 P1 observability）
    - **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）
```

**Summary**: `Document(title=不做 connection pool 监控) -- document:mentions --> string=留给 P1 observability`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This trade-off is explicitly in the bullet list, but the subject entity is the list item heading, not a real document."
```

---

### Draft 046

```yaml
draft_index: 45
entity_type: "Document"
entity_identity:
  title: "不做数据库升级迁移工具"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "现有 `_DDL` 机制保留"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0132"
  char_offset_start: 22222
  char_offset_end: 22387
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - **不做 aiosqlite 迁移**（独立蓝图）
    - **不做 PostgreSQL 后端**（独立蓝图）
    - **不解决多进程并发**（KP0-04 边界）
    - **不做 connection pool 监控**（留给 P1 observability）
    - **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）
```

**Summary**: `Document(title=不做数据库升级迁移工具) -- document:mentions --> string=现有 `_DDL` 机制保留`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The phrase '留给 P1 observability' is supported, but the extracted subject is still just a bullet heading."
```

---

### Draft 047

```yaml
draft_index: 46
entity_type: "Document"
entity_identity:
  title: "/hnsm-backend/.env"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "明文值"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0136"
  char_offset_start: 22431
  char_offset_end: 22499
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    `/hnsm-backend/.env` 文件存在，含 `OPENAI_API_KEY` 和 `NEO4J_PASSWORD` 明文值。
```

**Summary**: `Document(title=/hnsm-backend/.env) -- document:mentions --> string=明文值`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The '_DDL' line is in the source, but the bullet heading is not a stable document identity."
```

---

### Draft 048

```yaml
draft_index: 47
entity_type: "Document"
entity_identity:
  title: "剩余风险"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "密钥仍然在本地磁盘明文存储"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0138"
  char_offset_start: 22609
  char_offset_end: 22725
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **剩余风险**：
    - 密钥仍然在本地磁盘明文存储
    - 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
    - 没有密钥轮换流程
    - 没有"密钥不应出现在 .env"的硬约束
    - 审计报告在 4/9 日的快照中把它列为 P0
```

**Summary**: `Document(title=剩余风险) -- document:mentions --> string=密钥仍然在本地磁盘明文存储`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The file path is supported, but the object '明文值' is too lossy to capture the actual risk statement about contained secrets."
```

---

### Draft 049

```yaml
draft_index: 48
entity_type: "Document"
entity_identity:
  title: "剩余风险"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0138"
  char_offset_start: 22609
  char_offset_end: 22725
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **剩余风险**：
    - 密钥仍然在本地磁盘明文存储
    - 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
    - 没有密钥轮换流程
    - 没有"密钥不应出现在 .env"的硬约束
    - 审计报告在 4/9 日的快照中把它列为 P0
```

**Summary**: `Document(title=剩余风险) -- document:mentions --> string=开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The risk statement is present, but '剩余风险' is a section heading rather than a stable document identity."
```

---

### Draft 050

```yaml
draft_index: 49
entity_type: "Document"
entity_identity:
  title: "剩余风险"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "没有密钥轮换流程"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0138"
  char_offset_start: 22609
  char_offset_end: 22725
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **剩余风险**：
    - 密钥仍然在本地磁盘明文存储
    - 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
    - 没有密钥轮换流程
    - 没有"密钥不应出现在 .env"的硬约束
    - 审计报告在 4/9 日的快照中把它列为 P0
```

**Summary**: `Document(title=剩余风险) -- document:mentions --> string=没有密钥轮换流程`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This risk bullet is directly supported, but the subject remains the section heading instead of a real document identity."
```

---

### Draft 051

```yaml
draft_index: 50
entity_type: "Document"
entity_identity:
  title: "剩余风险"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "没有\"密钥不应出现在 .env\"的硬约束"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0138"
  char_offset_start: 22609
  char_offset_end: 22725
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **剩余风险**：
    - 密钥仍然在本地磁盘明文存储
    - 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
    - 没有密钥轮换流程
    - 没有"密钥不应出现在 .env"的硬约束
    - 审计报告在 4/9 日的快照中把它列为 P0
```

**Summary**: `Document(title=剩余风险) -- document:mentions --> string=没有"密钥不应出现在 .env"的硬约束`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The text does say there is no key-rotation process, but the extracted subject is still just the section heading."
```

---

### Draft 052

```yaml
draft_index: 51
entity_type: "Document"
entity_identity:
  title: "剩余风险"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "审计报告在 4/9 日的快照中把它列为 P0"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0138"
  char_offset_start: 22609
  char_offset_end: 22725
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **剩余风险**：
    - 密钥仍然在本地磁盘明文存储
    - 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
    - 没有密钥轮换流程
    - 没有"密钥不应出现在 .env"的硬约束
    - 审计报告在 4/9 日的快照中把它列为 P0
```

**Summary**: `Document(title=剩余风险) -- document:mentions --> string=审计报告在 4/9 日的快照中把它列为 P0`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The hard-constraint concern is supported, but '剩余风险' is not the actual document identity."
```

---

### Draft 053

```yaml
draft_index: 52
entity_type: "Document"
entity_identity:
  title: "58b55aaa2a74dbc5"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "Local development: use .env (gitignored). Copy from .env.example."
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0164"
  char_offset_start: 24600
  char_offset_end: 24908
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - Local development: use `.env` (gitignored). Copy from `.env.example`.
    - `.env.example` is committed and must NEVER contain real values.
    - Rotate any key immediately if suspected leaked.
    - Production deployment: inject via container env vars or secret manager.
      Do NOT bundle `.env` into production images.
```

**Summary**: `Document(title=58b55aaa2a74dbc5) -- document:mentions --> string=Local development: use .env (gitignored…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source mentions the 4/9 audit snapshot, but the section heading was used as the document title."
```

---

### Draft 054

```yaml
draft_index: 53
entity_type: "Document"
entity_identity:
  title: "H-03 文档与模板"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "创建 .env.example"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0174"
  char_offset_start: 25778
  char_offset_end: 25877
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Step 2: H-03 文档与模板
            → 创建 .env.example
            → 创建 docs/SECURITY.md
            → 验证 git ignored
```

**Summary**: `Document(title=H-03 文档与模板) -- document:mentions --> string=创建 .env.example`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The local-development guidance is present, but the subject entity is the opaque doc_id rather than a stable document title."
```

---

### Draft 055

```yaml
draft_index: 54
entity_type: "Document"
entity_identity:
  title: "H-03 文档与模板"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "创建 docs/SECURITY.md"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0174"
  char_offset_start: 25778
  char_offset_end: 25877
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Step 2: H-03 文档与模板
            → 创建 .env.example
            → 创建 docs/SECURITY.md
            → 验证 git ignored
```

**Summary**: `Document(title=H-03 文档与模板) -- document:mentions --> string=创建 docs/SECURITY.md`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The step item is correct, but 'H-03 文档与模板' is a plan heading rather than a stable document identity."
```

---

### Draft 056

```yaml
draft_index: 55
entity_type: "Document"
entity_identity:
  title: "H-03 文档与模板"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "验证 git ignored"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0174"
  char_offset_start: 25778
  char_offset_end: 25877
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Step 2: H-03 文档与模板
            → 创建 .env.example
            → 创建 docs/SECURITY.md
            → 验证 git ignored
```

**Summary**: `Document(title=H-03 文档与模板) -- document:mentions --> string=验证 git ignored`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Creating docs/SECURITY.md is explicitly listed, but the extracted subject is still the step heading."
```

---

### Draft 057

```yaml
draft_index: 56
entity_type: "Module"
entity_identity:
  module_name: "ledger.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "连接管理重构 + post-commit hooks + close 追踪"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0183"
  char_offset_start: 27168
  char_offset_end: 27279
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/core/store/
      └── ledger.py                      # (改造) 连接管理重构 + post-commit hooks + close 追踪
```

**Summary**: `Module(module_name=ledger.py) -- module:description --> string=连接管理重构 + post-commit hooks + close 追踪`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The verification step is in the source, but the subject was keyed to the planning heading instead of a document identity."
```

---

### Draft 058

```yaml
draft_index: 57
entity_type: "Module"
entity_identity:
  module_name: "test_service_auth"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "require_api_key 单测"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0184"
  char_offset_start: 27281
  char_offset_end: 27652
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/tests/
      ├── test_service_auth.py           # (新建) require_api_key 单测
      ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
      ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
      ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
      └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义
```

**Summary**: `Module(module_name=test_service_auth) -- module:description --> string=require_api_key 单测`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the code tree line directly names ledger.py and gives this concise description."
```

---

### Draft 059

```yaml
draft_index: 58
entity_type: "Module"
entity_identity:
  module_name: "test_service_app_v1_auth"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "路由级认证集成测试"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0184"
  char_offset_start: 27281
  char_offset_end: 27652
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/tests/
      ├── test_service_auth.py           # (新建) require_api_key 单测
      ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
      ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
      ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
      └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义
```

**Summary**: `Module(module_name=test_service_app_v1_auth) -- module:description --> string=路由级认证集成测试`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the test file name and its comment-level description match the source."
```

---

### Draft 060

```yaml
draft_index: 59
entity_type: "Module"
entity_identity:
  module_name: "test_agent_http_runtime_api_auth"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "HttpRuntimeAPI 传 api_key 验证 header"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0184"
  char_offset_start: 27281
  char_offset_end: 27652
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/tests/
      ├── test_service_auth.py           # (新建) require_api_key 单测
      ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
      ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
      ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
      └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义
```

**Summary**: `Module(module_name=test_agent_http_runtime_api_auth) -- module:description --> string=HttpRuntimeAPI 传 api_key 验证 header`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the route-level auth integration test is described exactly this way in the code tree."
```

---

### Draft 061

```yaml
draft_index: 60
entity_type: "Module"
entity_identity:
  module_name: "test_ledger_concurrency"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "并发测试 + post-commit hook 一致性"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0184"
  char_offset_start: 27281
  char_offset_end: 27652
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/tests/
      ├── test_service_auth.py           # (新建) require_api_key 单测
      ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
      ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
      ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
      └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义
```

**Summary**: `Module(module_name=test_ledger_concurrency) -- module:description --> string=并发测试 + post-commit hook 一致性`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the test module and its api_key-header purpose are directly supported by the source line."
```

---

### Draft 062

```yaml
draft_index: 61
entity_type: "Module"
entity_identity:
  module_name: "test_ledger_close"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "thread-local 连接追踪 + close 语义"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0184"
  char_offset_start: 27281
  char_offset_end: 27652
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    src/factpy_kernel/tests/
      ├── test_service_auth.py           # (新建) require_api_key 单测
      ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
      ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
      ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
      └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义
```

**Summary**: `Module(module_name=test_ledger_close) -- module:description --> string=thread-local 连接追踪 + close 语义`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the test file comment explicitly says concurrency tests plus post-commit hook consistency."
```

---

### Draft 063

```yaml
draft_index: 62
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "密钥管理规范"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0185"
  char_offset_start: 27654
  char_offset_end: 27710
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    docs/
      └── SECURITY.md                    # (新建) 密钥管理规范
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=密钥管理规范`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the source line directly describes test_ledger_close in these terms."
```

---

### Draft 064

```yaml
draft_index: 63
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "不解决多进程并发：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=不解决多进程并发：KP0-04 明确的 trade-off。多 worker …`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: SECURITY.md and the phrase '密钥管理规范' are paired explicitly in the code tree."
```

---

### Draft 065

```yaml
draft_index: 64
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "API Key 不含 per-user 权限：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=API Key 不含 per-user 权限：所有持有有效 key 的客户端权…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The API-key limitation is explicitly stated, but the extracted subject is the section label rather than a real document identity."
```

---

### Draft 066

```yaml
draft_index: 65
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "不覆盖 rate limiting：滥用防护留给独立蓝图。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=不覆盖 rate limiting：滥用防护留给独立蓝图。`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The rate-limiting trade-off is present in the text, but 'KP0-04' is still only a section key."
```

---

### Draft 067

```yaml
draft_index: 66
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "不覆盖 audit logging：当前 kernel 不记录'谁调了什么 API'。留给独立蓝图。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=不覆盖 audit logging：当前 kernel 不记录'谁调了什么 A…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The audit-logging limitation is supported, but the subject is the section identifier rather than a stable document."
```

---

### Draft 068

```yaml
draft_index: 67
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "密钥轮换是手动流程：没有自动轮换机制。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=密钥轮换是手动流程：没有自动轮换机制。`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Manual key rotation is indeed listed, but 'KP0-04' is not the actual document identity."
```

---

### Draft 069

```yaml
draft_index: 68
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "P1 隐患仍然存在：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=P1 隐患仍然存在：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The P1-risk sentence is in the source, but the extraction still keys the fact to a section label."
```

---

### Draft 070

```yaml
draft_index: 69
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "KP0-07 的 thread-local 不是连接池：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=KP0-07 的 thread-local 不是连接池：每个线程一个常驻连接，…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The thread-local warning is accurately extracted, but the subject remains the 'KP0-04' section identifier."
```

---

### Draft 071

```yaml
draft_index: 70
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: ".env.example 的 pre-commit hook 是可选：不强制 CI 运行；约定 + 代码审查 double check。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=.env.example 的 pre-commit hook 是可选：不强制 …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The pre-commit-hook caveat is supported, but the extraction still uses a section code as the document title."
```

---

### Draft 072

```yaml
draft_index: 71
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "H-03 不清理 git 历史：已验证 .env 从未被 commit；不需要 git filter-branch / BFG。如果后续发现历史中仍有泄漏，需要独立处理。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=H-03 不清理 git 历史：已验证 .env 从未被 commit；不需要…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The git-history statement is present, but the subject entity is again just the section label."
```

---

### Draft 073

```yaml
draft_index: 72
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "FACTPY_KERNEL_AUTH_DISABLED=true 是危险开关：仅用于本地 dev；生产部署必须确保此变量未设或为 false。部署 checklist 应包含'确认 AUTH_DISABLED 未设'这一项。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=FACTPY_KERNEL_AUTH_DISABLED=true 是危险开关：…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The dangerous-switch warning is supported verbatim, but the subject should not be Document(title=KP0-04)."
```

---

### Draft 074

```yaml
draft_index: 73
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "KP0-13 不保证跨线程物理关闭 SQLite 连接：这是 check_same_thread=True 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=KP0-13 不保证跨线程物理关闭 SQLite 连接：这是 check_sa…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The close-semantics limitation is real, but the extracted document identity is still just the section identifier."
```

---

### Draft 075

```yaml
draft_index: 74
entity_type: "Document"
entity_identity:
  title: "KP0-04"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "KP0-14 牺牲部分并发读吞吐换一致性：同一 Ledger 实例的 public 读写都走同一把 RLock。这是最小可用方案，不是最终性能方案。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0196"
  char_offset_start: 28446
  char_offset_end: 29425
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
    2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
    3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
    4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
    5. **密钥轮换是手动流程**：没有自动轮换机制。
    6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
    7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
    8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
    9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
    10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
    11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
    12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。
```

**Summary**: `Document(title=KP0-04) -- document:mentions --> string=KP0-14 牺牲部分并发读吞吐换一致性：同一 Ledger 实例的 publ…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The consistency/performance trade-off is supported by the source, but it is still keyed to the section label rather than a document."
```

---

### Draft 076

```yaml
draft_index: 75
entity_type: "Module"
entity_identity:
  module_name: "test_ledger_close.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "没有单独创建；close 语义测试并入了 `src/factpy_kernel/tests/test_ledger_concurrency.py`。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0205"
  char_offset_start: 31313
  char_offset_end: 31527
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    4. 目录结构计划中的 `test_ledger_close.py` 没有单独创建；close 语义测试并入了 `src/factpy_kernel/tests/test_ledger_concurrency.py`。
       - 原因：close 语义与 post-commit / read consistency 是同一组 ledger 并发约束，合并测试更自然。
       - 影响：无产品语义偏差，只是测试文件组织方式不同。
```

**Summary**: `Module(module_name=test_ledger_close.py) -- module:description --> string=没有单独创建；close 语义测试并入了 `src/factpy_kernel…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The text explicitly says test_ledger_close.py was not created, so using that file as the subject entity is not semantically correct."
```

---

### Draft 077

```yaml
draft_index: 76
entity_type: "Module"
entity_identity:
  module_name: "test_ledger_concurrency.py"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "close 语义测试并入了 `src/factpy_kernel/tests/test_ledger_concurrency.py`。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0205"
  char_offset_start: 31313
  char_offset_end: 31527
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    4. 目录结构计划中的 `test_ledger_close.py` 没有单独创建；close 语义测试并入了 `src/factpy_kernel/tests/test_ledger_concurrency.py`。
       - 原因：close 语义与 post-commit / read consistency 是同一组 ledger 并发约束，合并测试更自然。
       - 影响：无产品语义偏差，只是测试文件组织方式不同。
```

**Summary**: `Module(module_name=test_ledger_concurrency.py) -- module:description --> string=close 语义测试并入了 `src/factpy_kernel/tests/…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "test_ledger_concurrency.py is the correct subject, but this sentence is a change-log note about merged tests rather than a durable module description."
```

---
