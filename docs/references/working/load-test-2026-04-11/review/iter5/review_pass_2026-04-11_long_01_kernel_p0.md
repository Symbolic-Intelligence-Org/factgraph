# Review Pass 2026-04-11 — long_01_kernel_p0

## Header

- sample_id: `long_01_kernel_p0`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/long/long_01_kernel_p0.md`
- doc_id: `58b55aaa2a74dbc5`
- total_segments: 207
- total_proposal_count (regen): 46
- total_valid_count (regen): 36
- total_rejection_count (regen): 10
- generated_at: 2026-04-10T23:58:56.448235+00:00

### Iter 4 historical baseline

- archived_run_record: `run_records/b3_20260410T194711Z_long_01_kernel_p0.json`
- archived_bundle_id: `bundle_172f0fcd7765` (in-memory only, not reproducible)
- archived_valid_count: 57

This is the **pre-fix** iter 4 state, retained for historical reference only. The drift between iter 4's 57 valid drafts and this packet's 36 valid drafts is **not** run-to-run variance — it reflects the intentional semantic grounding fix applied between iter 4 and iter 5 (see §Iter 5 context below).

### Iter 5 context (read before reviewing)

**This packet is an iter 5 sample**, not an iter 4 sample. The pipeline has received the semantic grounding fix from the iter 5 blueprint:

- Blueprint: [`docs/blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.md`](../../../../blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.md) (status: `scoped`, applied to `prompts.py`, full regression green at **977 tests**)
- Iter 5 canonical run record: `run_records/b3_20260410T234302Z_long_01_kernel_p0.json` (canonical: 43 proposals / 36 valid / 7 rejected)

**Canonical vs. this packet**: this packet was regenerated via `generate_review_packet.py` separately from the canonical run. The long valid count matched canonical **exactly** (36 in both), though proposal count drifted slightly (canonical 43 / regen 46) and rejection count drifted slightly (canonical 7 / regen 10). Per OBS-01 that absolute-count drift is within normal variance; the `valid_count` match on both samples is a small positive signal for iter 5 stability.

**What the iter 5 fix was supposed to do**:

- **F-01 — Document title grounding**: teach the LLM that `Document.title` must be a stable identifier that appears **verbatim** in the source text (filenames, blueprint IDs, section anchors, explicit self-references). Drafts whose `title` is a doc_id hash, body prose synthesis, or section heading paraphrase should be tagged `WRONG_ENTITY`.
- **F-02 — `module:description` narrowing**: teach the LLM that `module:description` field values must be **declarative** descriptions of what the module is or does — not plans, checklists, test expectations, acceptance criteria, or coverage labels. Drafts whose description is a task or operational expectation should be tagged `WRONG_ARG`.
- **Per-type abstention**: teach the LLM to omit a proposal of a specific entity type when grounding for that type is weak, while still emitting valid proposals of other types for the same segment. Expected side effect: absolute proposal volume may drop. A volume decrease accompanied by a strict-rate increase is a pure win (SG-15).

**Iter 5 targets** (from blueprint SG-14):

| metric | iter 4 baseline | iter 5 target |
|---|---:|---:|
| combined strict approval rate `yes / total` | 11.6% | **≥40%** |
| combined salvageable rate `(yes + partial) / total` | 100% | **≥95% guardrail** (must not drop) |

**Review is NOT a backfill operation**. Do NOT:

- Backfill into the iter 4 archived run_record (`b3_20260410T194711Z_*`) — it refers to a different in-memory bundle
- Backfill into the iter 5 canonical run_record (`b3_20260410T234302Z_*`) — it carries pipeline metrics, not per-draft review decisions
- Modify any previously archived artifacts (iter 4 review packet, iter 4 report, `cross_run_observations.md`, etc.)

**What to do instead**: fill in the `REVIEW` block below each draft. After both iter 5 packets (medium + long) are reviewed, a new `review_summary_iter5_2026-04-11.md` will be written to aggregate strict approval rate, `reason_code` distribution, and the iter 4 → iter 5 qualitative delta.

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
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The filename appears verbatim in the source text, and the document is explicitly scoped as Kernel-side work independent of the agent line."
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
    value: "related to Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
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

**Summary**: `Module(module_name=app_v1.py) -- module:description --> string=related to Kernel 侧（非 agent 线），独立于 agen…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`app_v1.py` is a plausible module identity, but `related to Kernel 侧（非 agent 线）` is scope metadata from the blueprint header, not a declarative description of what the module is or does."
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
    value: "related to Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
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

**Summary**: `Module(module_name=runtime_v1.py) -- module:description --> string=related to Kernel 侧（非 agent 线），独立于 agen…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`runtime_v1.py` is a plausible module identity, but the extracted value is blueprint scope metadata rather than a description of the module itself."
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
    value: "related to Kernel 侧（非 agent 线），独立于 agent 蓝图推进"
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

**Summary**: `Module(module_name=ledger.py) -- module:description --> string=related to Kernel 侧（非 agent 线），独立于 agen…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`ledger.py` is a plausible module identity, but the extracted value is blueprint scope metadata rather than a declarative module description."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Document"
entity_identity:
  title: "KP0-05 冻结"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "FastAPI Depends + API Key Header 的最小认证方案"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0017"
  char_offset_start: 1850
  char_offset_end: 1912
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **KP0-05 冻结**：采用 **FastAPI Depends + API Key Header** 的最小认证方案。
```

**Summary**: `Document(title=KP0-05 冻结) -- document:mentions --> string=FastAPI Depends + API Key Header 的最小认证方案`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-05 冻结` is a verbatim stable identifier in the source text, and the extracted topic matches the line that follows the heading."
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
confidence: 1.0
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
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The file path appears verbatim, but `src/factpy_kernel/service/auth.py` is a code file artifact, not a `Document(title=...)` subject in this context."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Module"
entity_identity:
  module_name: "X-FactPy-API-Key"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Reads X-FactPy-API-Key header and verifies against configured keys."
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0034"
  char_offset_start: 4225
  char_offset_end: 4497
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Reads X-FactPy-API-Key header and verifies against configured keys.
        If FACTPY_KERNEL_AUTH_DISABLED=true, skips verification entirely
        (for local dev only; MUST NOT be set in production).
        """
        if not _auth_config.enabled:
            return  # explicitly disabled
```

**Summary**: `Module(module_name=X-FactPy-API-Key) -- module:description --> string=Reads X-FactPy-API-Key header and verif…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The raw text is about auth logic that reads the `X-FactPy-API-Key` header, but the header name itself is not the right `Module` subject for a declarative module description."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Module"
entity_identity:
  module_name: "X-FactPy-API-Key"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "If FACTPY_KERNEL_AUTH_DISABLED=true, skips verification entirely (for local dev only; MUST NOT be set in production)."
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0034"
  char_offset_start: 4225
  char_offset_end: 4497
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Reads X-FactPy-API-Key header and verifies against configured keys.
        If FACTPY_KERNEL_AUTH_DISABLED=true, skips verification entirely
        (for local dev only; MUST NOT be set in production).
        """
        if not _auth_config.enabled:
            return  # explicitly disabled
```

**Summary**: `Module(module_name=X-FactPy-API-Key) -- module:description --> string=If FACTPY_KERNEL_AUTH_DISABLED=true, sk…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source text supports the conditional behavior, but `X-FactPy-API-Key` is still the wrong subject entity; this is auth behavior, not a module description of the header."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Module"
entity_identity:
  module_name: "X-FactPy-API-Key"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "if not _auth_config.enabled, return  # explicitly disabled"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0034"
  char_offset_start: 4225
  char_offset_end: 4497
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Reads X-FactPy-API-Key header and verifies against configured keys.
        If FACTPY_KERNEL_AUTH_DISABLED=true, skips verification entirely
        (for local dev only; MUST NOT be set in production).
        """
        if not _auth_config.enabled:
            return  # explicitly disabled
```

**Summary**: `Module(module_name=X-FactPy-API-Key) -- module:description --> string=if not _auth_config.enabled, return  # …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This extracts a code branch tied to auth config under the header name `X-FactPy-API-Key`; the behavior is supported, but the subject entity is mis-routed."
```

---

### Draft 010

```yaml
draft_index: 9
entity_type: "Module"
entity_identity:
  module_name: "HttpRuntimeAPI"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Minimal HTTP transport over service v1 routes."
confidence: 1.0
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
  notes: "`HttpRuntimeAPI` is a grounded code identifier, and `Minimal HTTP transport over service v1 routes.` is a clean declarative description from the class docstring."
```

---

### Draft 011

```yaml
draft_index: 10
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
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-07 冻结` is a verbatim stable identifier in the source text, and the extracted topic matches the heading content."
```

---

### Draft 012

```yaml
draft_index: 11
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "覆盖整个写入流程：SQLite transaction + 内存索引更新"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=覆盖整个写入流程：SQLite transaction + 内存索引更新`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The contract text is about how the system uses the lock, but `RLock` is not the right `Module` subject for this extracted description."
```

---

### Draft 013

```yaml
draft_index: 12
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "通过 conn 执行 SQLite writes"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=通过 conn 执行 SQLite writes`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The phrase `通过 conn 执行 SQLite writes` is supported, but it describes a step in the write-session contract, not the module/entity `RLock` itself."
```

---

### Draft 014

```yaml
draft_index: 13
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "通过 post_commit.append(...) 注册内存索引更新 callables"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=通过 post_commit.append(...) 注册内存索引更新 cal…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The extracted action is supported by the raw text, but the subject should be the write-session contract or hook flow, not `RLock` as a module identity."
```

---

### Draft 015

```yaml
draft_index: 14
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "成功路径 -> conn.execute(\"COMMIT\") -> 依序执行 post_commit hooks"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=成功路径 -> conn.execute("COMMIT") -> 依序执行 …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This is a supported contract clause, but it is mis-bound to `RLock` rather than the write-session contract that owns the behavior."
```

---

### Draft 016

```yaml
draft_index: 15
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "异常路径 -> conn.execute(\"ROLLBACK\") -> hooks 不执行"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=异常路径 -> conn.execute("ROLLBACK") -> hoo…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The rollback clause is present in the source text, but `RLock` is the wrong subject entity for it."
```

---

### Draft 017

```yaml
draft_index: 16
entity_type: "Module"
entity_identity:
  module_name: "RLock"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "锁在 context manager 退出时才释放 -- 保证 reader 看不到 \"SQLite 已提交、内存索引仍旧值\" 的窗口"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0087"
  char_offset_start: 12391
  char_offset_end: 12829
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    KP0-12 冻结的合同：
            - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
            - 调用方在 with block 内:
              1. 通过 conn 执行 SQLite writes
              2. 通过 post_commit.append(...) 注册内存索引更新 callables
            - 退出 try block 时:
              - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
              - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
            - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
              "SQLite 已提交、内存索引仍旧值" 的窗口
```

**Summary**: `Module(module_name=RLock) -- module:description --> string=锁在 context manager 退出时才释放 -- 保证 reader …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The consistency-window guarantee is supported, but it is attached to the broader write-session contract, not `RLock` as a module description."
```

---

### Draft 018

```yaml
draft_index: 17
entity_type: "Module"
entity_identity:
  module_name: "post_commit"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "注册内存索引更新 callables 在 SQLite COMMIT 成功后、锁释放前执行"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0095"
  char_offset_start: 14745
  char_offset_end: 15179
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # 2. 注册 post-commit 内存索引更新 callables
            #    这些在 SQLite COMMIT 成功后、锁释放前执行
            #    如果 COMMIT 失败（raise），hooks 不执行，内存索引未变
            post_commit.append(lambda: self._idx_add_claim(actual_claim))
            post_commit.append(lambda: self._idx_add_claim_args(actual_claim_args))
            post_commit.append(lambda: self._idx_add_meta(actual_meta_rows))
            post_commit.append(lambda: self._register_ingest_key(ingest_key, asrt_id))
```

**Summary**: `Module(module_name=post_commit) -- module:description --> string=注册内存索引更新 callables 在 SQLite COMMIT 成功后、…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`post_commit` appears in the source text, but this draft still misidentifies a hook list/variable as the module entity."
```

---

### Draft 019

```yaml
draft_index: 18
entity_type: "Module"
entity_identity:
  module_name: "post_commit"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "如果 COMMIT 失败，hooks 不执行，内存索引未变"
confidence: 0.8
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0095"
  char_offset_start: 14745
  char_offset_end: 15179
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # 2. 注册 post-commit 内存索引更新 callables
            #    这些在 SQLite COMMIT 成功后、锁释放前执行
            #    如果 COMMIT 失败（raise），hooks 不执行，内存索引未变
            post_commit.append(lambda: self._idx_add_claim(actual_claim))
            post_commit.append(lambda: self._idx_add_claim_args(actual_claim_args))
            post_commit.append(lambda: self._idx_add_meta(actual_meta_rows))
            post_commit.append(lambda: self._register_ingest_key(ingest_key, asrt_id))
```

**Summary**: `Module(module_name=post_commit) -- module:description --> string=如果 COMMIT 失败，hooks 不执行，内存索引未变`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The COMMIT-failure behavior is supported, but `post_commit` is not the right module subject for this statement."
```

---

### Draft 020

```yaml
draft_index: 19
entity_type: "Module"
entity_identity:
  module_name: "post_commit"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "添加 claim、claim_args 和 meta 数据到内存索引"
confidence: 0.7
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0095"
  char_offset_start: 14745
  char_offset_end: 15179
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # 2. 注册 post-commit 内存索引更新 callables
            #    这些在 SQLite COMMIT 成功后、锁释放前执行
            #    如果 COMMIT 失败（raise），hooks 不执行，内存索引未变
            post_commit.append(lambda: self._idx_add_claim(actual_claim))
            post_commit.append(lambda: self._idx_add_claim_args(actual_claim_args))
            post_commit.append(lambda: self._idx_add_meta(actual_meta_rows))
            post_commit.append(lambda: self._register_ingest_key(ingest_key, asrt_id))
```

**Summary**: `Module(module_name=post_commit) -- module:description --> string=添加 claim、claim_args 和 meta 数据到内存索引`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The memory-index updates are supported by the source text, but they are actions within the hook flow, not a declarative description of a `Module(post_commit)`."
```

---

### Draft 021

```yaml
draft_index: 20
entity_type: "Module"
entity_identity:
  module_name: "post_commit"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "注册 ingest key"
confidence: 0.7
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0095"
  char_offset_start: 14745
  char_offset_end: 15179
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    # 2. 注册 post-commit 内存索引更新 callables
            #    这些在 SQLite COMMIT 成功后、锁释放前执行
            #    如果 COMMIT 失败（raise），hooks 不执行，内存索引未变
            post_commit.append(lambda: self._idx_add_claim(actual_claim))
            post_commit.append(lambda: self._idx_add_claim_args(actual_claim_args))
            post_commit.append(lambda: self._idx_add_meta(actual_meta_rows))
            post_commit.append(lambda: self._register_ingest_key(ingest_key, asrt_id))
```

**Summary**: `Module(module_name=post_commit) -- module:description --> string=注册 ingest key`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`注册 ingest key` is supported by the code snippet, but `post_commit` is the wrong subject entity for the extracted fact."
```

---

### Draft 022

```yaml
draft_index: 21
entity_type: "Document"
entity_identity:
  title: "58b55aaa2a74dbc5"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "所有读取内存索引的 public API 必须获取与 writer 相同的 RLock"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0117"
  char_offset_start: 19254
  char_offset_end: 19318
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **KP0-14 冻结**：所有读取**内存索引**的 public API 必须获取与 writer 相同的 `RLock`。
```

**Summary**: `Document(title=58b55aaa2a74dbc5) -- document:mentions --> string=所有读取内存索引的 public API 必须获取与 writer 相同的 R…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`58b55aaa2a74dbc5` is the internal doc_id hash, not a stable identifier that appears verbatim in the source text as a valid `Document.title`."
```

---

### Draft 023

```yaml
draft_index: 22
entity_type: "Document"
entity_identity:
  title: "docs/SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "本 checklist"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0168"
  char_offset_start: 25152
  char_offset_end: 25458
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - [ ] 所有现有 `.env` 中的密钥已在 provider 侧轮换（新密钥生成 + 旧密钥撤销）
    - [ ] `.env.example` 模板文件存在并入 git
    - [ ] `.env.example` 不含任何真实值（所有变量都以 `#` 注释）
    - [ ] `docs/SECURITY.md` 存在并说明本 checklist
    - [ ] `.env` 仍然被 `.gitignore` 覆盖（验证：`git check-ignore .env`）
    - [ ] `git log --all -- .env` 仍为空（历史从未包含）
    - [ ] （可选）pre-commit hook 脚本存在
```

**Summary**: `Document(title=docs/SECURITY.md) -- document:mentions --> string=本 checklist`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "OVERGENERAL"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`docs/SECURITY.md` is grounded, but `本 checklist` is too generic and underspecified to be a strong `document:mentions` fact."
```

---

### Draft 024

```yaml
draft_index: 23
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "密钥管理规范"
confidence: 1.0
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
  notes: "The file name `SECURITY.md` and the topic `密钥管理规范` are directly paired in the source text."
```

---

### Draft 025

```yaml
draft_index: 24
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "密钥"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0192"
  char_offset_start: 28199
  char_offset_end: 28335
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **H-03 密钥** ✓ 条件：
    - 所有 `.env` 中的现有密钥已在 provider 侧轮换
    - `.env.example` 入 git 且不含真实值
    - `docs/SECURITY.md` 存在
    - `git check-ignore .env` 返回成功
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=密钥`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "OVERGENERAL"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`密钥` is present, but it is too broad to stand as a high-quality mention fact for `SECURITY.md` on its own."
```

---

### Draft 026

```yaml
draft_index: 25
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "所有 `.env` 中的现有密钥已在 provider 侧轮换"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0192"
  char_offset_start: 28199
  char_offset_end: 28335
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **H-03 密钥** ✓ 条件：
    - 所有 `.env` 中的现有密钥已在 provider 侧轮换
    - `.env.example` 入 git 且不含真实值
    - `docs/SECURITY.md` 存在
    - `git check-ignore .env` 返回成功
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=所有 `.env` 中的现有密钥已在 provider 侧轮换`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The checklist item is present in the raw text, but it is a rollout condition, not a grounded topic that `SECURITY.md` itself is shown to mention here."
```

---

### Draft 027

```yaml
draft_index: 26
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "`.env.example` 入 git 且不含真实值"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0192"
  char_offset_start: 28199
  char_offset_end: 28335
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **H-03 密钥** ✓ 条件：
    - 所有 `.env` 中的现有密钥已在 provider 侧轮换
    - `.env.example` 入 git 且不含真实值
    - `docs/SECURITY.md` 存在
    - `git check-ignore .env` 返回成功
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=`.env.example` 入 git 且不含真实值`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "This is a checklist condition from the source segment, not a clean grounded topic that `SECURITY.md` is shown to mention."
```

---

### Draft 028

```yaml
draft_index: 27
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "`git check-ignore .env` 返回成功"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0192"
  char_offset_start: 28199
  char_offset_end: 28335
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    **H-03 密钥** ✓ 条件：
    - 所有 `.env` 中的现有密钥已在 provider 侧轮换
    - `.env.example` 入 git 且不含真实值
    - `docs/SECURITY.md` 存在
    - `git check-ignore .env` 返回成功
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=`git check-ignore .env` 返回成功`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`git check-ignore .env` returning success is a checklist verification item, not a grounded content topic for `SECURITY.md`."
```

---

### Draft 029

```yaml
draft_index: 28
entity_type: "Module"
entity_identity:
  module_name: "KP0-04"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。"
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

**Summary**: `Module(module_name=KP0-04) -- module:description --> string=明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-04` is a hazard/trade-off identifier, not the right `Module` subject for a module description."
```

---

### Draft 030

```yaml
draft_index: 29
entity_type: "Module"
entity_identity:
  module_name: "KP0-07"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "的 thread-local 不是连接池。每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。"
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

**Summary**: `Module(module_name=KP0-07) -- module:description --> string=的 thread-local 不是连接池。每个线程一个常驻连接，连接数 = 活…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-07` is a hazard identifier, not a module; the extracted statement is supported but mis-routed to the wrong entity type."
```

---

### Draft 031

```yaml
draft_index: 30
entity_type: "Module"
entity_identity:
  module_name: "KP0-13"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "不保证跨线程物理关闭 SQLite 连接。这是 check_same_thread=True 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。"
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

**Summary**: `Module(module_name=KP0-13) -- module:description --> string=不保证跨线程物理关闭 SQLite 连接。这是 check_same_thre…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-13` is a hazard identifier, not a module entity. The statement is supported, but the subject routing is wrong."
```

---

### Draft 032

```yaml
draft_index: 31
entity_type: "Module"
entity_identity:
  module_name: "KP0-14"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "牺牲部分并发读吞吐换一致性。同一 Ledger 实例的 public 读写都走同一把 RLock。这是最小可用方案，不是最终性能方案。"
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

**Summary**: `Module(module_name=KP0-14) -- module:description --> string=牺牲部分并发读吞吐换一致性。同一 Ledger 实例的 public 读写都走…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`KP0-14` is a hazard identifier, not a module entity. The trade-off statement is supported but attached to the wrong subject type."
```

---

### Draft 033

```yaml
draft_index: 32
entity_type: "Document"
entity_identity:
  title: "SECURITY.md"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "新增"
confidence: null
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0200"
  char_offset_start: 29473
  char_offset_end: 30731
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - H-01 已落地：
      - 新增 `src/factpy_kernel/service/auth.py`
      - `src/factpy_kernel/service/app_v1.py` 的 `/v1/...` 路由统一接入 `Depends(require_api_key)`
      - `src/factpy_kernel/agent/tools/_runtime_api.py` 为 `HttpRuntimeAPI` 增加最小 `api_key` / `api_key_header` 兼容点
    - H-02 已落地：
      - `src/factpy_kernel/core/store/ledger.py` 从单共享连接改为 thread-local SQLite connection
      - 写路径统一迁移到 `_write_session() -> (conn, post_commit)` 合同
      - public read API 与 writer 共享同一把 `RLock`
      - `close()` 现在显式标记 closed，并阻止后续新连接打开
    - H-03 仓库内产物已落地：
      - 新增 `.env.example`
      - 新增 `docs/SECURITY.md`
      - 新增 `scripts/check_no_secrets_in_env_example.sh`
    - 受影响模块文档已同步：
      - `src/factpy_kernel/service/docs/README.md`
      - `src/factpy_kernel/service/docs/01_overview.md`
      - `src/factpy_kernel/service/docs/02_runtime_sessions.md`
      - `src/factpy_kernel/service/docs/03_runtime_queries_policy.md`
      - `src/factpy_kernel/service/docs/04_rules_registry.md`
      - `src/factpy_kernel/core/docs/01_architecture.md`
      - `src/factpy_kernel/agent/docs/README.md`
      - `docs/README.md`
    - 验证结果：
      - `./scripts/check_no_secrets_in_env_example.sh` → `OK`
      - `git check-ignore .env` → `.env`
      - `git log --all --full-history -- .env` → 空
      - `python -m unittest discover -s src/factpy_kernel/tests` → `942 tests`, `1 skipped`
```

**Summary**: `Document(title=SECURITY.md) -- document:mentions --> string=新增`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "OVERGENERAL"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`SECURITY.md` is grounded, but the extracted value `新增` is too generic to be a useful or precise mention fact."
```

---

### Draft 034

```yaml
draft_index: 33
entity_type: "Module"
entity_identity:
  module_name: "AuthConfig"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "没有采用早期示例中的 module-level singleton；实现改为 load_auth_config() 每次从环境变量读取。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0202"
  char_offset_start: 30749
  char_offset_end: 30926
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. `AuthConfig` 没有采用早期示例中的 module-level singleton；实现改为 `load_auth_config()` 每次从环境变量读取。
       - 原因：测试可控性更好，不需要 reload 模块或 patch singleton。
       - 影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。
```

**Summary**: `Module(module_name=AuthConfig) -- module:description --> string=没有采用早期示例中的 module-level singleton；实现改为 …`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "`AuthConfig` is a grounded code identifier, and the extracted value is a declarative implementation description rather than a task or checklist item."
```

---

### Draft 035

```yaml
draft_index: 34
entity_type: "Module"
entity_identity:
  module_name: "AuthConfig"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "原因：测试可控性更好，不需要 reload 模块或 patch singleton。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0202"
  char_offset_start: 30749
  char_offset_end: 30926
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. `AuthConfig` 没有采用早期示例中的 module-level singleton；实现改为 `load_auth_config()` 每次从环境变量读取。
       - 原因：测试可控性更好，不需要 reload 模块或 patch singleton。
       - 影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。
```

**Summary**: `Module(module_name=AuthConfig) -- module:description --> string=原因：测试可控性更好，不需要 reload 模块或 patch singlet…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The sentence beginning with `原因：` is rationale for the design choice, not a declarative description of what `AuthConfig` is or does."
```

---

### Draft 036

```yaml
draft_index: 35
entity_type: "Module"
entity_identity:
  module_name: "AuthConfig"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。"
confidence: 0.9
note: null

provenance:
  source_document_id: "58b55aaa2a74dbc5"
  segment_id: "58b55aaa_0202"
  char_offset_start: 30749
  char_offset_end: 30926
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    1. `AuthConfig` 没有采用早期示例中的 module-level singleton；实现改为 `load_auth_config()` 每次从环境变量读取。
       - 原因：测试可控性更好，不需要 reload 模块或 patch singleton。
       - 影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。
```

**Summary**: `Module(module_name=AuthConfig) -- module:description --> string=影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ARG"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The `影响：` sentence is impact/rationale metadata, not a declarative description of `AuthConfig` itself."
```

---
