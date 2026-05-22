# Blueprint: Extraction Model Benchmark

- Status: implemented
- Created: 2026-04-13
- Kind: **diagnostic / benchmarking** (not a code change)
- Trigger: gpt-4o-mini 提取质量评估后,需要跨模型对比确定最佳默认模型
- Related Modules:
  - `scripts/benchmark_extraction.py`
  - `scripts/test_real_extraction.py`
  - `docs/references/working/extraction_benchmark_report.json`
- Audit Log:
  - [2026-04-13_extraction-benchmark.audit.md](./2026-04-13_extraction-benchmark.audit.md)

---

## 0. Scope

创建两个实用脚本 + 跑一次跨模型 benchmark:

1. `scripts/test_real_extraction.py` — standalone real-LLM extraction 测试脚本,支持内置样本 + 用户自定义文档(PDF/MD/DOCX/TXT)
2. `scripts/benchmark_extraction.py` — 跨模型 benchmark,对同一样本跑 gpt-4o-mini / gpt-4o / gpt-4.1-mini / gpt-4.1 四个 tier,产出对比报告 + ground truth hit matrix

**不做什么**:
- 不改 `src/factpy_kernel/` 任何代码
- 不改默认模型(benchmark 结论指导后续决策,不直接改 config)

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| BM-01 | 4 个模型 tier: gpt-4o-mini / gpt-4o / gpt-4.1-mini / gpt-4.1 | 覆盖 OpenAI 主力模型线从 lightweight 到 flagship |
| BM-02 | Ground truth: 8 条预期 facts (1 Document × 2 + 3 Module × 2) | 人工标注的 README 样本 golden set |
| BM-03 | 全部 P0-P2 改进默认开启 | 测试的是"当前最佳配置"下的模型能力差异 |
| BM-04 | 单次运行(不多轮平均) | OBS-01 variance 已知,单次足够看趋势 |

## 2. Acceptance Criteria

1. ✅ 4 个模型全部成功完成提取
2. ✅ 产出对比表 + ground truth hit matrix
3. ✅ JSON 报告保存到 `docs/references/working/`

## 3. Outcome

### Benchmark 结果

| Model | Recall | Precision | Entities | Duration |
|---|---|---|---|---|
| gpt-4o-mini | 75% (6/8) | 100% | 3/4 | 26.0s |
| gpt-4o | **88% (7/8)** | 54% | **4/4** | 13.8s |
| gpt-4.1-mini | 75% (6/8) | 78% | **4/4** | **10.3s** |
| gpt-4.1 | **88% (7/8)** | 41% | **4/4** | 19.6s |

### 关键发现

- Module 提取全模型一致(6/6 全中)
- Document entity 是分水岭: 只有 gpt-4o / gpt-4.1 成功提取
- `document:tag` 全军覆没(multi-cardinality 弱点)
- gpt-4.1-mini 把 "Project Alpha" 当成 Module(entity mistyping)
- 推荐: gpt-4o 最佳性价比,gpt-4.1 最高质量

### Final status: **implemented**
