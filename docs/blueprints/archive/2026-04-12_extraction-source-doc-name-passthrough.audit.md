# Audit Log: Source Document Name Passthrough (F1)

## 2026-04-12 — draft → scoped

### Trigger

P0/P1 验证后的 coverage 诊断发现 Document entity 系统性缺失。根因链:
1. `build_messages` (prompts.py:382) 用 `segment.doc_id` (SHA256 hash) 填 `Document: {doc_name}`
2. SYSTEM_PROMPT_TEMPLATE Example 3 明确禁止 opaque hash 做 Doc.title
3. LLM 正确遵守 → 拒绝提取 Document

### Status transitions

- 2026-04-12 — draft created
- 2026-04-12 — **scoped** (3 DN decisions frozen, plan approved)
- 2026-04-12 — implementing (3 production files + 3 test files patched; compile passed)
- 2026-04-12 — implemented (`1004 passed, 3 skipped, 0 failed`; Notebook 08 adversarial verification succeeded with `source_doc_name=\"architecture_notes.md\"`)
- 2026-04-12 — archived

### Outcome

Acceptance closed cleanly.

- The root cause diagnosis held: once the prompt saw a human-readable source filename instead of the opaque `doc_id` hash, Document extraction became eligible under Example 3's grounding rule.
- Regression stayed green after the passthrough change.
- Notebook-equivalent adversarial verification produced a `Document {'title': 'architecture_notes.md'}` key in both extraction and resolver outputs, satisfying the blueprint's behavioral gate.
- No scope expansion was needed: `DocumentSegment`, Example 3, and resolver behavior all stayed unchanged.
