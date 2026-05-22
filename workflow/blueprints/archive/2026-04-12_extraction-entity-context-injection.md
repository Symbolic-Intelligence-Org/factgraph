# Blueprint: Extraction Entity Context Injection (P0)

- Status: implemented
- Created: 2026-04-12
- Kind: **extraction layer enhancement** (not a contract change, not a schema change)
- Trigger: Notebook 08 端到端验证 + 调研报告 `docs/references/agentic-document-extraction-research.md` §B.1.2 Contextual Retrieval 方案
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py` (prompt template + context formatter)
  - `src/factpy_kernel/agent/extraction/extractor.py` (parameter passthrough)
  - `src/factpy_kernel/agent/extraction/batch.py` (entity accumulation + context threading)
  - `src/factpy_kernel/agent/extraction/models.py` (config flag)
- Audit Log:
  - [2026-04-12_extraction-entity-context-injection.audit.md](./2026-04-12_extraction-entity-context-injection.audit.md)

---

## 0. Scope

在 `BatchExtractor.extract_batch` 的逐段 LLM 提取循环中，注入 **跨段 entity context header**：每次成功提取后累积已识别的 entity mentions（entity_type + identity + key facts），在后续 segment 的 LLM prompt 中以结构化文本注入,使 LLM 能解析模糊的回指引用（"该模块"、"上述系统"）。

**做什么**:
- `BatchExtractionConfig` 加 `enable_entity_context: bool = True` opt-out flag
- `prompts.py` 新增 `format_entity_context_header()` 格式化函数
- `USER_PROMPT_TEMPLATE` 在 metadata 和 text 之间插入 `{entity_context_block}` 占位符
- `build_messages` 和 `extract_from_segment` 透传 `prior_entity_context: str = ""`
- `batch.py` 的 `extract_batch` 循环内累积 entity mentions 并注入后续调用

**不做什么**:
- 不改 `SYSTEM_PROMPT_TEMPLATE`（context 是 document-specific,不是 schema-level 指令）
- 不改 `DocumentSegment` / `FactDraftSpec` / `ExtractionProvenance` 等 model dataclasses
- 不改 `EntityResolver`（identity matching 逻辑不变）
- 不改 `ReadReviewOrchestrator`（单段 extraction via orchestrator 不传 context,和之前一致）
- 不改 `DocumentStaging` / parsers
- 不改 `SYSTEM_PROMPT_TEMPLATE` 的规则 1-10 和语义示例
- 不改 schema compilation / runtime session 层
- 不改 B3 load test harness
- 不做 Gleaning 二遍提取（那是 P1,另一个 blueprint）
- 不做 fuzzy identity matching（那是 P2,另一个 blueprint）

---

## 1. Problem

### 1.1 当前 per-segment 隔离的局限

`BatchExtractor.extract_batch` 对每个 segment 独立调用 `ExtractionAgent.extract_from_segment`。LLM 在处理 segment N 时,不知道 segment 0..N-1 已经识别了哪些 entities。这导致:

1. **回指失败**: segment 9 说 "the module described in Section 2.1"，但 LLM 看不到 section 2.1 的内容,无法解析 "the module" = "ingest"
2. **重复提取**: segment 3 和 segment 7 各自独立提出 `Module(name="ingest")`,EntityResolver 可以合并,但如果 segment 7 的 identity 表述不同（如用了 hash 或缩写）,就合并不上
3. **属性碎片化**: 一个 entity 的 description 在 page 1,owner 在 page 5,两段独立提取各自只拿到一个 attribute

### 1.2 Notebook 08 验证的具体表现

Notebook 08 用真实 gpt-4o-mini 对一段 inline README 提取:
- 7 segments → 8 proposals → 7 valid → 3 个 Module 全部识别 ✓
- 但 Document identity 用了 `doc_id` hash (`997c784df65baf90`) 而不是 "README.md" ✗
- 因为 inline README 恰好每段都重复 module 名字("The `ingest` module...")所以没有命中回指问题,但真实 PDF 不会这么友好

### 1.3 调研报告的直接依据

`docs/references/agentic-document-extraction-research.md` §B.1.2:
> "在 embedding 前为每个 chunk 添加上下文摘要（标题路径 + 简要描述），使 chunk 自解释"

§3.3.1 也提到 LightRAG 的 Gleaning 机制和 Schema 约束提取作为上下文连续性的解决方案。本 blueprint 实现的是最轻量的第一步:从已提取结果累积 entity mentions 注入后续 prompt。

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| EC-01 | Context 注入到 `USER_PROMPT_TEMPLATE`,不注入 `SYSTEM_PROMPT_TEMPLATE` | Context 是 document-specific 的运行时数据,不是 schema-level 的提取规则 |
| EC-02 | Context 格式为结构化自然语言（`- EntityType (key="val"): pred_id="value"`） | 匹配 schema summary 的风格,LLM 容易理解;不用 JSON 避免和 response model 格式混淆 |
| EC-03 | Context header 最大 2000 chars（`max_context_chars=2000`），按完整 entity 行截断 | 保守估计 ~500 tokens,不显著增加 per-segment token 消耗 |
| EC-04 | Entity key 用 `(entity_type, tuple(sorted(identity.items())))` — 和 `resolution.py:_compute_entity_key` 一致 | 确保 batch.py 的累积和 resolver 的合并使用同一个 identity 判定标准 |
| EC-05 | 默认开启（`enable_entity_context: bool = True`），`BatchExtractionConfig` 提供 opt-out | 严格 additive improvement;segment 0 的 context 为空,和当前行为一致;opt-out 用于 reproducibility 对比 |
| EC-06 | 只累积 `ExtractionResult.valid_specs` 的 entity mentions,不累积 error segments 和 rejected proposals | Error segment 没有可信的 entity 信息;rejected proposals 可能是幻觉,不应注入 |
| EC-07 | `prior_entity_context` 参数全链路 optional with default `""`，不改现有 callers | Backward compatible — orchestrator 的单段 extraction、B3 runner 的直接调用、所有测试均不需修改调用方 |
| EC-08 | 不改 `ExtractionAgent.__init__` 或 `BatchExtractor.__init__` 的签名 | 改动最小化 — 只在方法参数层面透传 |
| EC-09 | Compact fact 表示只取 `field_values[0]` 的值 | 避免多参 predicate 的 context 膨胀;第一个 field_value 通常是主要语义内容 |
| EC-10 | 新增测试 ~12 个,覆盖 format + injection + accumulation + opt-out + error-skip | 每个行为边界一个测试 |

---

## 3. Implementation

### 3.1 `models.py` — `BatchExtractionConfig` 加 flag (+2 lines)

**File**: `src/factpy_kernel/agent/extraction/models.py`

在 `BatchExtractionConfig` dataclass 的 `early_stop_on_batch_cap_reached` 之后加:

```python
enable_entity_context: bool = True
```

`__post_init__` 末尾加:

```python
if not isinstance(self.enable_entity_context, bool):
    raise AgentContractError("enable_entity_context must be bool")
```

### 3.2 `prompts.py` — context 格式化 + 模板注入 (+54 lines)

**File**: `src/factpy_kernel/agent/extraction/prompts.py`

**3.2.1** `USER_PROMPT_TEMPLATE` 在 `Structural clarity: {structural_clarity:.2f}` 和 `Text:` 之间插入 `{entity_context_block}` 占位符。空字符串时只多一个空行,无语义影响。

**3.2.2** 新增 `format_entity_context_header(entries, *, max_context_chars=2000) -> str`，放在 `truncate_prompt_text` 之后、`build_messages` 之前。

输入: `list[dict]`，每个 dict 含 `entity_type` (str), `identity` (dict), `facts` (list[str])。
输出示例:
```
Previously identified entities in this document (use for reference resolution, do not re-extract these facts):
- Module (name="ingest"): module:description="handles document ingestion", module:owner="data-infra team"
- Module (name="resolve"): module:owner="Alice"
```
空输入返回 `""`。超 `max_context_chars` 按最后一个完整 entity 行截断 + `"\n... (context truncated)"`。

**3.2.3** `build_messages` 签名加 `prior_entity_context: str = ""`，在 `USER_PROMPT_TEMPLATE.format(...)` 调用里传 `entity_context_block=prior_entity_context`。

### 3.3 `extractor.py` — 透传参数 (+4 lines)

**File**: `src/factpy_kernel/agent/extraction/extractor.py`

`extract_from_segment` 签名加 `prior_entity_context: str = ""`。
在 `build_messages(...)` 调用里加 `prior_entity_context=prior_entity_context`。

### 3.4 `batch.py` — 核心累积逻辑 (+73 lines)

**File**: `src/factpy_kernel/agent/extraction/batch.py`

**3.4.1** Import `format_entity_context_header` from `.prompts`。

**3.4.2** `extract_batch` 循环前初始化: `entity_accumulator: dict[tuple, dict[str, object]] = {}`

**3.4.3** 循环内,每次 `extract_from_segment` 调用前:
```python
if effective_config.enable_entity_context and entity_accumulator:
    prior_entity_context = format_entity_context_header(list(entity_accumulator.values()))
else:
    prior_entity_context = ""
```
传给 `extract_from_segment(..., prior_entity_context=prior_entity_context)`。

**3.4.4** 每次成功提取后(两处 `aggregated_specs.extend(...)` 之后)调用:
```python
_accumulate_entities(entity_accumulator, result.valid_specs)  # or accepted
```

**3.4.5** 新增模块级辅助函数 `_accumulate_entities(accumulator, specs)`：按 entity key 聚合,记录 `pred_id="value"` compact fact。Entity key 用 `(entity_type, tuple(sorted(identity.items())))` — 和 `resolution.py:199` 的 `_compute_entity_key` 一致（EC-04）。

### 3.5 Test files — 签名更新 + 新测试 (+161 lines)

**3.5.1** `test_agent_l4c3b_batch_extractor.py` line 73 + `test_agent_observability_extraction_hooks.py` line 137:
`_FakeExtractionAgent.extract_from_segment` 签名加 `prior_entity_context=""`。

**3.5.2** `test_agent_l4c3a_prompts.py` 新增 6 个测试:
- `format_entity_context_header` 空输入、单 entity、多 entity、截断
- `build_messages` with/without `prior_entity_context`

**3.5.3** `test_agent_l4c3b_batch_extractor.py` 新增 3 个测试:
- Context 跨段累积（segment 0 空、segment 1 含 segment 0 的 entities）
- `enable_entity_context=False` 时全部 segment 收到空 context
- Error segment 不累积

**3.5.4** `test_agent_l4c3b_models.py` 新增 3 个测试:
- `enable_entity_context` 默认 True / 显式 False / 非 bool 拒绝

---

## 4. Non-goals

- 不修改 `SYSTEM_PROMPT_TEMPLATE` 的任何规则或示例
- 不修改 `DocumentSegment` / `FactDraftSpec` / `ExtractionProvenance` 等 model dataclasses
- 不修改 `EntityResolver` 的 identity matching 逻辑（fuzzy matching 是 P2）
- 不实现 Gleaning / 二遍提取（那是 P1）
- 不实现 sliding-window segment context（不传 neighboring segments 的 raw text,只传 entity mentions）
- 不修改 `ReadReviewOrchestrator` 的 `extract_from_segment` / `extract_from_segments` 调用方式
- 不修改 B3 load test harness (`run_load_test.py`)
- 不修改 Notebook 08（验证时手动重跑即可）
- 不修改 `doc_name` 问题（LLM 用 doc_id hash 做 Document title identity — 那是 prompt alignment 的独立问题）
- 不增加 `cross_run_observations.md` 条目

---

## 5. Impact on Other Layers

| Layer | Impact | Reason |
|-------|--------|--------|
| Agent layer (`agent/extraction/`) | **4 files modified** | Core implementation surface |
| Agent layer (other modules) | **None** | orchestrator/session/tools/documents untouched |
| Kernel layer (`core/`) | **None** | Read-only |
| Runtime layer (`runtime/`) | **None** | Read-only |
| Service layer (`service/`) | **None** | Read-only |
| SDK layer (`sdk/`) | **None** | Read-only |
| B3 harness | **None** | `ExtractionAgent` 直接调用不传 `prior_entity_context`,得到默认 `""` |
| Notebook 08 | **None** (自动受益) | `BatchExtractor.extract_batch` 内部自动累积 context |
| Test suite | **2 files signature update + 3 files new tests** | ~12 new tests, 977 existing tests unaffected |

---

## 6. Acceptance Criteria

1. **Compile**: 8 个改动文件全部无语法错误
2. **Regression**: `python -m pytest src/factpy_kernel/tests/ -x -q` → 977 + ~12 new tests green
3. **Behavioral**: 在 Notebook 08 重跑 cell 15 (§6 extraction):
   - Segment 0 的 LLM 调用不含 entity context（和改动前一致）
   - Segment 1+ 的 LLM 调用 user prompt 里出现 "Previously identified entities in this document" header
   - `aggregated_specs` 数量可能略有变化（更多 correct attributions 或更少 duplicates）
4. **Opt-out**: `BatchExtractionConfig(enable_entity_context=False)` 时全部 segment 不含 context
5. **Line budget**: 生产代码 ≤+140 lines across 4 files; 测试代码 ≤+165 lines across 3 files

---

## 7. Known Constraints

- **Hook 限制**: `src/factpy_kernel/` 下 `.py` 文件不能用 Claude Edit/Write 工具直接编辑。代码变更以文本形式提供,用户手动 apply
- **Token budget**: context header 最大 2000 chars ≈ ~500 tokens。对于极大文档（100+ entities）context 会被截断,但这是 conservative 上限而非 bug
- **Segment 顺序依赖**: 累积 context 依赖 segments 的处理顺序。如果未来 `BatchExtractor` 支持并行 extraction,需要重新设计累积策略。当前是 sequential loop,没有并行问题

---

## 8. Open Questions (probe-by-implementation)

| # | Question | Default | Resolution method |
|---|----------|---------|-------------------|
| EC-Q1 | Context header 是否应该包含 `doc_name`（human-readable）而不仅是 entity mentions? | 不包含（`DocumentSegment` 上没有 `doc_name` 字段,只有 `doc_id` hash） | 如果验证发现 LLM 仍然用 hash 做 Document identity,这是独立问题,不在本 blueprint scope |
| EC-Q2 | `max_context_chars=2000` 是否过大或过小? | 2000 chars | Notebook 08 验证后可调 — 7 segments 的 README 只有 3 个 entity,context ~200 chars,远低于上限 |
| EC-Q3 | Error segment 的 entity context 是否应该 "reset"（不传 context 给下一个 segment）? | 不 reset — error segment 跳过累积,但前序累积的 context 继续传给后续 segment | 如果发现 error segment 后的 LLM 输出质量下降,考虑 reset 策略 |

---

## 9. Outcome / Deviations

- Implemented in:
  - `src/factpy_kernel/agent/extraction/models.py`
  - `src/factpy_kernel/agent/extraction/prompts.py`
  - `src/factpy_kernel/agent/extraction/extractor.py`
  - `src/factpy_kernel/agent/extraction/batch.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_batch_extractor.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_models.py`
  - `src/factpy_kernel/tests/test_agent_observability_extraction_hooks.py`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
- Test results:
  - Compile sanity on changed production + test files: PASS
  - Full regression: `987 passed, 3 skipped, 1 warning, 4 subtests passed in 11.67s`
  - New coverage points landed: prompt header formatting/injection, batch accumulation, opt-out, error-segment skip, config validation
- Notebook 08 verification:
  - Re-ran the cell 15 extraction setup against the real LLM path with a fresh runtime session and the notebook's inline README sample
  - `7 segments -> 9 proposals -> 9 valid -> 0 rejections -> aggregated_specs len 9`
  - `seg[0]` carried no entity context, consistent with pre-change behavior
  - `seg[1]` also carried no entity context because the accumulator was still empty at that point; the first prior valid entity was produced by `seg[1]`
  - `seg[2]..seg[6]` all carried the `Previously identified entities in this document` header, with observed context growth from 366 chars to 1086 chars
  - Behavioral conclusion: the implemented rule is "inject context once prior valid entities exist", not "inject context on every segment after index 0"
- Line budget compliance:
  - Production files: `models.py 168->170`, `prompts.py 327->366`, `extractor.py 282->283`, `batch.py 297->334` = **+79 lines total**, within the `≤+140` target
  - Test surface stayed within the blueprint's intended envelope: 2 signature-only updates + 10 new tests across 4 files; no regression pressure or follow-up trimming was needed
- EC-Q1 / EC-Q2 / EC-Q3 resolution:
  - **EC-Q1**: keep default. This blueprint did not add `doc_name` into the context header; the change remains strictly entity-context only
  - **EC-Q2**: keep `max_context_chars=2000`. Notebook 08 peaked at 1086 chars, comfortably below the cap
  - **EC-Q3**: keep the default "do not reset after error segments". Notebook 08 did not exercise an error segment, and the dedicated batch unit test now covers the skip-without-reset path
- Deviations:
  - None. The only clarification surfaced during verification is that context onset depends on the first prior successful extraction, which is consistent with EC-05/EC-06 and does not require a code change
- Final status: **implemented**
