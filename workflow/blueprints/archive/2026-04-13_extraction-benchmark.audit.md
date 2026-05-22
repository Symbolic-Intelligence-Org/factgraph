# Audit Log: Extraction Model Benchmark

## 2026-04-13 — draft → implemented → archived

### Trigger

gpt-4o-mini 单次提取结果 recall=62.5%,需要对比更高 tier 模型确定是否值得切换默认模型。

### Execution

1. 创建 `scripts/test_real_extraction.py`: standalone 单模型测试,支持内置样本 + 用户文档
2. 创建 `scripts/benchmark_extraction.py`: 4-tier benchmark runner
3. 运行 benchmark: 4 模型 × 同一样本,产出对比报告

### Benchmark 结论

- gpt-4o / gpt-4.1 并列最高 recall (88%)
- gpt-4o 是最佳性价比 (recall 88% + cost ~$0.02)
- gpt-4.1-mini 最快 (10.3s) 但有 entity mistyping 问题
- 建议默认模型从 gpt-4o-mini 升级到 gpt-4.1

### Status transitions

- 2026-04-13 — draft → **implemented** → **archived**
