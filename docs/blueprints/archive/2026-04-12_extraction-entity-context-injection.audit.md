# Audit Log: Extraction Entity Context Injection (P0)

## 2026-04-12 — Initial draft

### Trigger

Notebook 08 (`examples/08_agent_document_workflow.ipynb`) 的端到端验证暴露了 per-segment extraction 的局限: LLM 在处理每个 segment 时没有前序段落的 entity 信息,无法解析模糊回指。调研报告 `docs/references/agentic-document-extraction-research.md` §B.1.2 提出 Contextual Retrieval 方案,本 blueprint 实现其最轻量的第一步。

### Priority context

这是 P0 / P1 / P2 三步改进路径中的第一步:

| Priority | Name | Scope | Status |
|---|---|---|---|
| **P0** | Entity context header injection | `batch.py` 累积 + `prompts.py` 注入 | **本 blueprint** |
| P1 | Gleaning / 二遍提取 | `BatchExtractor` 对低 yield segments 带 entity list 重调 | 未开 |
| P2 | 级联 ER (fuzzy identity matching) | `EntityResolver` 加 embedding similarity tier | 未开 |

P0 和 P1 组合基本解决"entity 属性跨段分布"问题。P2 解决 identity 歧义。

### Frozen decisions

10 条 EC-01 ~ EC-10,见 blueprint §2。核心决策:
- Context 注入 user prompt（EC-01）
- 默认开启（EC-05）
- Entity key 和 resolver 一致（EC-04）
- 只累积 valid specs（EC-06）

### Pre-implementation baseline

- Full test suite: **977 tests, 2 skipped**
- `src/factpy_kernel/agent/extraction/` 4 个目标文件行数:
  - `models.py`: 168 lines
  - `prompts.py`: 327 lines
  - `extractor.py`: 282 lines
  - `batch.py`: 297 lines
- Notebook 08: 27 cells, 7 segments × gpt-4o-mini extraction = 8 proposals / 7 valid

### Status transitions

- 2026-04-12 — draft created based on plan file `playful-inventing-shore.md` + Notebook 08 verification + research report
- 2026-04-12 — **scoped** (plan approved by reviewer, 10 EC decisions frozen, implementation steps detailed in §3)
- 2026-04-12 — **implementing** (EC-01 ~ EC-10 landed across 4 production files + 4 test files; compile sanity passed)
- 2026-04-12 — **implemented** (full regression green: `987 passed, 3 skipped, 1 warning, 4 subtests passed in 11.67s`; Notebook 08 behavioral verification confirmed context injection on post-accumulation segments)
- 2026-04-12 — **archived** (module docs aligned, blueprint §9 filled, no deviations recorded)

## 2026-04-12 — Implementation + verification close-out

### Implementation summary

- `BatchExtractionConfig` now carries `enable_entity_context: bool = True`
- `prompts.py` now formats a bounded entity-context header and injects it between structural metadata and segment text
- `extractor.py` now threads `prior_entity_context` into `build_messages(...)`
- `batch.py` now accumulates prior valid entities by resolver-compatible identity key and injects that context into later segment calls
- Extraction tests were extended with 10 new checks covering formatter output, prompt injection, batch accumulation, opt-out behavior, error-segment skip behavior, and config validation

### Verification result

- Compile sanity: PASS on changed production + test files
- Regression: PASS (`987 passed, 3 skipped, 1 warning, 4 subtests passed in 11.67s`)
- Notebook 08 behavioral verification:
  - real LLM extraction path re-run on the inline README sample
  - `7 segments -> 9 proposals -> 9 valid -> 0 rejections -> aggregated_specs len 9`
  - `seg[0]` had no context, `seg[1]` still had no context because no prior valid entity existed yet, and `seg[2]..seg[6]` all carried the `Previously identified entities in this document` header
  - observed context length grew from 366 chars to 1086 chars, so the `max_context_chars=2000` cap was not stressed in this notebook path

### Outcome classification

- Final classification: **implemented**
- No code deviations were required
- The only verification clarification is behavioral wording: context onset depends on "first prior successful extraction", not on raw segment index
