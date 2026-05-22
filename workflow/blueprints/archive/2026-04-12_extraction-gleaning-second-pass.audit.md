# Audit Log: Extraction Gleaning / Second-Pass (P1)

## 2026-04-12 — Initial draft

### Trigger

P0 (Entity Context Header Injection) 已归档为 `implemented`。验证结果正向: valid specs 7→9, rejections 1→0。但暴露了增量 context 的局限: segment 0 和 segment 1 没有 entity context,如果这些 segment 包含可提取事实但因缺少 entity awareness 而 yield=0,P0 无法补救。

调研报告 §3.3.1 的 LightRAG Gleaning 机制提出"多遍提取 + 差异补全"方案。本 blueprint 实现第二遍提取:pass 1 结束后,用完整 entity context 重新审查低 yield segments。

### Priority context

| Priority | Name | Status |
|---|---|---|
| P0 | Entity context header injection | **implemented, archived** ✅ |
| **P1** | Gleaning / 二遍提取 | **本 blueprint** |
| P2 | 级联 ER (fuzzy identity matching) | 未开 |

### Frozen decisions

10 条 GL-01 ~ GL-10。核心:
- 复用 P0 的 `prior_entity_context` 参数(GL-01)
- 不新增 prompt template(GL-02)
- 只 glean 低 yield success segments(GL-03)
- Opt-in 默认关闭(GL-04)
- 异常 non-fatal(GL-07)

### Pre-implementation baseline

- Full test suite: **987 passed, 3 skipped** (post-P0)
- `src/factpy_kernel/agent/extraction/` 4 文件行数(post-P0):
  - `models.py`: ~170 lines
  - `prompts.py`: ~360 lines
  - `extractor.py`: ~290 lines (不改)
  - `batch.py`: ~340 lines

### Status transitions

- 2026-04-12 — draft created based on P0 archived results + research report §3.3.1
- 2026-04-12 — **scoped** (plan approved, 10 GL decisions frozen)
- 2026-04-12 — **implementing** (GL-01 ~ GL-10 landed across 3 production files + 3 test files; compile sanity passed)
- 2026-04-12 — **implemented with deviations** (regression green and Notebook 08 gleaning verification passed, but production/test line budgets both overran and Notebook 08 moved from validation-only to code-changed example)
- 2026-04-12 — **archived** (module docs aligned, blueprint §9 filled, deviations recorded)

## 2026-04-12 — Implementation + verification close-out

### Implementation summary

- `BatchExtractionConfig` now carries `enable_gleaning: bool = False` and `gleaning_yield_threshold: int = 0`
- `BatchExtractionResult` now carries `gleaning_segments_reexamined`
- `prompts.py` now exposes `format_gleaning_context(...)`
- `batch.py` now runs a second-pass gleaning loop after pass 1 for low-yield success segments, using `GLEANING PASS:` plus full entity context
- Tests were extended to cover gleaning formatter behavior, config/result validation, zero-yield reexamination, non-fatal gleaning exceptions, and batch-cap behavior

### Verification result

- Compile sanity: PASS on changed production + test files
- Regression: PASS (`1002 passed, 3 skipped, 1 warning, 4 subtests passed in 11.11s`)
- Notebook 08 behavioral verification:
  - real LLM extraction path re-run with `enable_gleaning=True`
  - pass-1 metrics stayed at `8 proposals / 7 valid / 1 rejection`
  - final `aggregated_specs len` increased to `10`
  - `gleaning_segments_reexamined = 3`
  - prompt trace captured 3 second-pass prompts with `GLEANING PASS:`
  - the first gleaning prompt targeted `seg[0]`, which had yielded `0 fact(s)` in pass 1

### Deviation record

- Production line budget overrun: `+85` vs target `≤+80`
- Test line budget overrun: `+209` vs target `≤+155`
- Notebook scope expansion: `examples/08_agent_document_workflow.ipynb` was updated even though the original scoped plan treated Notebook 08 as validation-only

### Outcome classification

- Final classification: **implemented with deviations**
- Core behavior is accepted: gleaning second pass runs, produces observable `GLEANING PASS` prompts, and increases final aggregated extraction yield on Notebook 08
- Deviations are scope/budget related, not semantic or correctness failures
