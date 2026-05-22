# Blueprint: Source Document Name Passthrough (F1 — Document Coverage Fix)

- Status: implemented
- Created: 2026-04-12
- Kind: **extraction layer bug fix** (prompt input correction)
- Trigger: 诊断发现 Document entity 系统性缺失的闭环根因 — `build_messages` 把 `doc_id` hash 传给 LLM,Example 3 禁止用 hash 做 title,LLM 正确拒绝 → Document 不被提取
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py`
  - `src/factpy_kernel/agent/extraction/extractor.py`
  - `src/factpy_kernel/agent/extraction/batch.py`
- Audit Log:
  - [2026-04-12_extraction-source-doc-name-passthrough.audit.md](./2026-04-12_extraction-source-doc-name-passthrough.audit.md)

---

## 0. Scope

透传 `source_doc_name: str | None` 参数到 LLM prompt 的 `Document: {doc_name}` 字段,替代 `segment.doc_id` hash。当 `source_doc_name` 可用时 LLM 看到人类可读文件名,Example 3 的 grounding rule 通过,Document entity 可被正常提取。

**做什么**: 3 个文件各加 1 个 optional 参数 + fallback 逻辑
**不做什么**: 不改 models.py、不改 DocumentSegment、不改 SYSTEM_PROMPT_TEMPLATE、不改 Example 3 规则、不改 EntityResolver

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| DN-01 | 路径 A(参数透传),不路径 B(改 DocumentSegment model) | 最小改动面,不改 frozen dataclass |
| DN-02 | `source_doc_name: str \| None = None` 默认 None,fallback `segment.doc_id` | Backward compatible — 所有现有 callers 不传此参数,行为不变 |
| DN-03 | 不改 Example 3 的 strict grounding rule | 规则有价值(防止 body prose 做 title);先把正确输入传进去 |

## 2. Implementation

3 个文件,~12 行生产代码:

- `prompts.py`: `build_messages` 加参数,`doc_name=source_doc_name if source_doc_name else segment.doc_id`
- `extractor.py`: `extract_from_segment` 加参数,透传到 `build_messages`
- `batch.py`: `extract_batch` 加参数,透传到两处 `extract_from_segment`(pass 1 + gleaning)

## 3. Acceptance Criteria

1. `py_compile` pass
2. `pytest` 1002 + ~2 new tests green
3. Notebook 08 adversarial: `source_doc_name="architecture_notes.md"` → Document entity 出现

## 4. Outcome / Deviations

Implemented as scoped, with no deviations.

- Production change: `source_doc_name: str | None` now threads through `BatchExtractor.extract_batch(...)`, `ExtractionAgent.extract_from_segment(...)`, and `build_messages(...)`.
- Prompt behavior: when `source_doc_name` is provided, `Document: {doc_name}` uses that human-readable source name; when it is omitted, behavior remains backward compatible and falls back to `segment.doc_id`.
- Verification:
  - `py_compile` passed on all changed files
  - regression passed: `1004 passed, 3 skipped, 0 failed`
  - Notebook 08 adversarial verification passed in notebook-equivalent execution with `source_doc_name="architecture_notes.md"`
    - pass 1: `14 proposals / 10 valid / 3 rejections`
    - `aggregated_specs = 10`
    - resolver output included `Document {'title': 'architecture_notes.md'}`
    - acceptance criterion #3 satisfied: Document entity appeared once a verbatim filename-level identifier was available to the prompt
- Carry-forward:
  - This closes the F1 document-coverage fix.
  - P2 (cascaded ER / fuzzy identity matching) remains shelved; the same adversarial verification still produced `NO FRAGMENTATION`.
