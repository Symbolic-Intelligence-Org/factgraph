# Blueprint: Extraction Gleaning / Second-Pass (P1)

- Status: implemented with deviations
- Created: 2026-04-12
- Kind: **extraction layer enhancement** (not a contract change, not a schema change)
- Parent: [2026-04-12_extraction-entity-context-injection.md](../archive/2026-04-12_extraction-entity-context-injection.md) (P0, archived `implemented`)
- Trigger: P0 验证暴露增量 context 的局限（early segments 缺少 entity awareness）+ 调研报告 §3.3.1 Gleaning 方案
- Related Modules:
  - `src/factpy_kernel/agent/extraction/models.py` (config + result fields)
  - `src/factpy_kernel/agent/extraction/prompts.py` (gleaning context formatter)
  - `src/factpy_kernel/agent/extraction/batch.py` (gleaning loop)
- Audit Log:
  - [2026-04-12_extraction-gleaning-second-pass.audit.md](./2026-04-12_extraction-gleaning-second-pass.audit.md)

---

## 0. Scope

在 `BatchExtractor.extract_batch` 的 pass 1 循环结束后，对低 yield segments 做**第二次 LLM 调用**（gleaning），使用 **完整的** entity context（而非 P0 的增量 context），捕获 pass 1 因 context 不足而遗漏的事实。

**做什么**:
- `BatchExtractionConfig` 加 `enable_gleaning: bool = False` + `gleaning_yield_threshold: int = 0`
- `BatchExtractionResult` 加 `gleaning_segments_reexamined: int = 0`
- `prompts.py` 新增 `format_gleaning_context()` — 构建 "GLEANING PASS" 指令 + 完整 entity header
- `batch.py` pass 1 loop 后插入 gleaning loop，对合格 segments 重调 `extract_from_segment`

**不做什么**:
- 不改 `extractor.py`（复用 P0 的 `prior_entity_context` 参数）
- 不改 `SYSTEM_PROMPT_TEMPLATE` 或 `USER_PROMPT_TEMPLATE`
- 不改 `segment_results` / `per_segment_metrics`（pass 1 only）
- 不改 `EntityResolver` / `ReadReviewOrchestrator` / `DocumentStaging`
- 不改任何 model dataclasses（`DocumentSegment`, `FactDraftSpec` 等）
- 不做 fuzzy identity matching（那是 P2）
- 不改 B3 load test harness / Notebook 08

---

## 1. Problem

### 1.1 P0 的增量 context 局限

P0 的 entity context 是增量的：segment N 只看到 segments 0..N-1 的 entities。

| segment | P0 entity context 包含 | 问题 |
|---|---|---|
| seg 0 | 空 | 完全没有 entity awareness |
| seg 1 | seg 0 的 entities（如果有） | 如果 seg 0 yield=0，仍然空 |
| seg 6 (最后) | seg 0..5 的全部 entities | 最完整 |

Notebook 08 验证: seg[0] 和 seg[1] 不含 entity context,从 seg[2] 开始才有。

### 1.2 Gleaning 的价值

如果 seg 0 包含 "Project Alpha is a distributed data processing pipeline"，pass 1 可能提取了 `Document(title=...)` 但漏了某些 facts（因为没有 entity context 指引）。Gleaning 给 seg 0 第二次机会：此时 entity_accumulator 已包含 ALL entities from ALL segments。

调研报告 §3.4.3: "多遍提取 (Gleaning) — 多次 LLM 调用 + 差异补全 — 提高召回率但增加成本"。

### 1.3 成本控制

Gleaning 只对**低 yield** segments 做（默认 yield=0），不是全量重跑。典型 7-segment 文档里 0-yield segments 通常 0-2 个，所以额外 LLM 调用数 ≤ 2。

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| GL-01 | Gleaning 复用 `extract_from_segment` 的 `prior_entity_context` 参数,不加新接口 | 最小改动面;P0 已铺好路 |
| GL-02 | 不新增 prompt template — gleaning 通过在 `prior_entity_context` 前加 "GLEANING PASS" 指令实现 | 避免模板膨胀;USER_PROMPT_TEMPLATE 的 `{entity_context_block}` 已够用 |
| GL-03 | 只 glean pass 1 **成功但低 yield** 的 segments,不 glean error segments | Error 可能是 timeout/dependency 问题,retry 不是本 blueprint scope |
| GL-04 | `enable_gleaning=False` 默认关闭(opt-in) | 成本敏感;P0 是 opt-out 因为零额外 LLM 成本,P1 有额外 LLM 成本 |
| GL-05 | `gleaning_yield_threshold=0` 默认只 glean yield=0 的 segment | 最保守;用户可调高 |
| GL-06 | `segment_results` / `per_segment_metrics` 不改 — pass 1 only | Metrics 不 double-count;`aggregated_specs` 包含两 passes 的全部 valid specs |
| GL-07 | Gleaning 异常 non-fatal(catch + continue) | Gleaning 是 best-effort 增强,不应因一个 segment 的 gleaning 失败而中断整个 batch |
| GL-08 | Gleaning 内仍尊守 batch cap（`scope.max_batch_size`） | 一致性;不因 gleaning 超出 caller 的 budget |
| GL-09 | Gleaning 后 `entity_accumulator` 也更新 | 一致性,虽然实际影响极小(gleaning 在最后执行) |
| GL-10 | `BatchExtractionResult.gleaning_segments_reexamined` 记录 gleaning 覆盖的 segment 数 | 最小 metrics;future refinement 可加 gleaning_valid_count 等 |

---

## 3. Implementation

### 3.1 `models.py` (+16 lines)

`BatchExtractionConfig` 加 2 fields + 2 validations。
`BatchExtractionResult` 加 1 field + 1 validation。

### 3.2 `prompts.py` (+25 lines)

新函数 `format_gleaning_context(entity_entries, pass1_yield) -> str`:
- 空 entries → `""`
- 非空 → gleaning 指令前缀 + `format_entity_context_header(entries)` 的完整输出

### 3.3 `batch.py` (+38 lines)

Pass 1 loop 后、metrics 构造前:
1. 如果 `enable_gleaning` and `entity_accumulator` and not `batch_cap_reached`
2. 遍历 `zip(segments, segment_results)`
3. 跳过 error segments / high-yield segments
4. 对合格 segment: `format_gleaning_context` → `extract_from_segment` → extend `aggregated_specs`
5. Exception → catch + continue
6. `gleaning_count` → `BatchExtractionResult.gleaning_segments_reexamined`

### 3.4 `extractor.py` — 不改

---

## 4. Non-goals

(同 §0 "不做什么")

---

## 5. Impact on Other Layers

| Layer | Impact |
|---|---|
| `agent/extraction/` 3 files | Modified |
| `agent/extraction/extractor.py` | **None** |
| Agent layer (其他) | **None** |
| Kernel / Runtime / Service / SDK | **None** |
| B3 harness | **None** |
| Notebook 08 | **None**(验证时手动加 `BatchExtractionConfig(enable_gleaning=True)`) |
| Test suite | 3 files, ~15 new tests |

---

## 6. Acceptance Criteria

1. Compile: 改动文件 `py_compile` pass
2. Regression: 987 + ~15 new tests green
3. Behavioral: Notebook 08 用 `enable_gleaning=True` 重跑,`gleaning_segments_reexamined > 0`(如果有 0-yield segments)
4. Opt-out: 默认 `enable_gleaning=False` 行为和 P0 完全一致
5. Line budget: 生产代码 ≤+80 lines / 测试代码 ≤+155 lines

---

## 7. Known Constraints

- Hook 限制: `.py` 代码以文本提供,用户手动 apply
- Token budget: gleaning context 复用 P0 的 `max_context_chars=2000` 上限
- Segment 顺序: gleaning loop 按原始 segment 顺序遍历
- Duplicate specs: gleaning 可能产出和其他 segment 重复的 facts → downstream `EntityResolver` dedup 处理

---

## 8. Open Questions

| # | Question | Default | Resolution |
|---|----------|---------|------------|
| GL-Q1 | Gleaning 是否应该把 pass 1 中 THIS segment 已提取的 facts 也列给 LLM? | 不列(通过 "do not re-extract" 指令隐式避免) | Notebook 08 验证后看 duplicate 比例 |
| GL-Q2 | `gleaning_yield_threshold` 默认值 0 是否太保守? | 保守(0) | 可在 Notebook 08 试 threshold=1 对比 |

---

## 9. Outcome / Deviations

- Implemented in:
  - `src/factpy_kernel/agent/extraction/models.py`
  - `src/factpy_kernel/agent/extraction/prompts.py`
  - `src/factpy_kernel/agent/extraction/batch.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_batch_extractor.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_models.py`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
  - `examples/08_agent_document_workflow.ipynb`
- Test results:
  - Compile sanity on changed production + test files: PASS
  - Full regression: `1002 passed, 3 skipped, 1 warning, 4 subtests passed in 11.11s`
  - New coverage points landed: gleaning config validation, result field validation, gleaning prompt formatting, zero-yield reexamination, non-fatal gleaning exception handling, batch-cap respect
- Notebook 08 verification:
  - Re-ran the cell 15 extraction setup against the real LLM path with `enable_gleaning=True`
  - Pass-1 metrics remained `7 segments -> 8 proposals -> 7 valid -> 1 rejection`
  - Final `aggregated_specs len` increased from the P0 run's `9` to **`10`**
  - `gleaning_segments_reexamined = 3`
  - Prompt trace captured **3** second-pass prompts containing `GLEANING PASS:`
  - The first gleaning prompt was on `seg[0]`, with a 1298-char context block starting with `GLEANING PASS: This segment was previously examined and yielded 0 fact(s)...`
  - Behavioral conclusion: current implementation behaves exactly as GL-03 / GL-06 specify: pass-1 metrics stay unchanged, while gleaning contributes only through `aggregated_specs` and `gleaning_segments_reexamined`
- GL-Q1 / GL-Q2 resolution:
  - **GL-Q1**: keep default. The gleaning header continues to rely on the `do not re-extract` instruction rather than echoing this segment's own pass-1 facts. Notebook 08 still produced additional aggregated specs without any need to widen the header
  - **GL-Q2**: keep the default `gleaning_yield_threshold=0`. Notebook 08 still reexamined 3 segments under the conservative threshold, so there is no evidence yet that the default is too strict
- Deviations:
  - **Line budget deviation**: production code grew by **+85 lines** across the 4 blueprint-tracked files (`+15 models`, `+25 prompts`, `+0 extractor`, `+45 batch`), exceeding the `≤+80` target by `+5`
  - **Test budget deviation**: the 3 blueprint-tracked test files grew by **+209 lines** (`+32 prompts`, `+131 batch extractor`, `+46 models`), exceeding the `≤+155` target by `+54`
  - **Notebook scope deviation**: the blueprint originally treated Notebook 08 as validation-only; the implementation also updated `examples/08_agent_document_workflow.ipynb` to enable gleaning by default and correct the cell-15 explanatory markdown
- Final status: **implemented with deviations**
