# Annotation Kernel Benchmarks

- 范围：`tools/benchmarks/`
- 最后更新：2026-03-21

## 1. Workload 概览

| Workload | 描述 | 代数 | 支持的 Baseline |
|----------|------|------|----------------|
| **A** | 图路径 min-max 置信度 | min-max (widest path) | problog, pyreason, souffle_proto, souffle_full_a |
| **B** | 时序状态模拟 + 规则驱动 | temporal state transition | problog, pyreason, souffle_proto |
| **C** | 结构候选排序 + max 聚合 | max aggregation + top-K | problog, pyreason, souffle_proto |
| **D** | Certainty annotation 派生 + ranking | bottleneck (min weighted impact) | annotation_kernel |

### 1.1 Baseline 实现状态（当前代码真相）

`bench_runner.py` 已为所有上表 baseline 预留 dispatch，但其中一部分当前仍是 smoke/stub 路径，会输出规范化 JSON 和 `unsupported_features`，而不是完整 benchmark 结果：

| Workload | Baseline | 当前状态 |
|----------|----------|----------|
| A | `problog` | 已实现 |
| A | `pyreason` | availability-only stub (`pyreason_bridge_v0_not_implemented`) |
| A | `souffle_proto` | 已实现 |
| A | `souffle_full_a` | 已实现 |
| B | `problog` | stub (`workload_b_problog_not_implemented`) |
| B | `pyreason` | stub (`pyreason_bridge_v0_not_implemented`) |
| B | `souffle_proto` | 已实现 |
| C | `problog` | 已实现 |
| C | `pyreason` | availability-only stub (`pyreason_bridge_v0_not_implemented`) |
| C | `souffle_proto` | 已实现 |
| D | `annotation_kernel` | 已实现 |

## 2. 目录结构

```
tools/benchmarks/
  bench_runner.py                 # 统一 CLI 入口（dispatch 到各 workload × baseline）
  bench_core_ledger_paths.py      # Ledger 微基准（独立）
  bench_scenario_a_audit_delivery_shape.py  # Scenario A 审计交付基准（独立）
  workload_a_reference.py         # Workload A 参考实现
  workload_b_reference.py         # Workload B 参考实现
  workload_c_reference.py         # Workload C 参考实现
  workload_d_reference.py         # Workload D 参考实现
  generate_workload_a.py          # Workload A fixture 生成器
  generate_workload_b.py          # Workload B fixture 生成器
  generate_workload_c.py          # Workload C fixture 生成器
  generate_workload_d.py          # Workload D fixture 生成器
  compare_workload_a.py           # Workload A golden 比较器
  compare_workload_b.py           # Workload B golden 比较器
  compare_workload_c.py           # Workload C golden 比较器
  compare_workload_d.py           # Workload D golden 比较器
  fixtures/                       # 输入 fixture JSON
  golden/                         # Golden output JSON
```

## 3. 每个 Workload 的使用方式

### 3.1 通用三步流程

```bash
cd tools/benchmarks

# 1. 生成 fixture + golden
python generate_workload_X.py --output fixtures/... --golden-output golden/...

# 2. 运行基准
PYTHONPATH=../../src python bench_runner.py \
  --workload X --baseline <baseline> \
  --input fixtures/... --output results/... \
  --measure-memory

# 3. 与 golden 比较
python compare_workload_X.py \
  --input fixtures/... --golden golden/... \
  --results results/... --output report/...
```

### 3.2 Workload A — 图路径 min-max 置信度

```bash
# 生成（默认 200 节点、800 边）
python generate_workload_a.py \
  --output fixtures/workload_a_N200_E800_seed42.json \
  --golden-output golden/workload_a_golden_seed42.json

# 运行 Souffle full_a baseline
PYTHONPATH=../../src python bench_runner.py \
  --workload A --baseline souffle_full_a \
  --input fixtures/workload_a_N200_E800_seed42.json \
  --output /tmp/a_result.json --measure-memory
```

### 3.3 Workload D — Certainty Annotation

```bash
# 生成（默认 20 conditions、depth 4）
python generate_workload_d.py \
  --output fixtures/workload_d_C20_D4_seed42.json \
  --golden-output golden/workload_d_golden_seed42.json

# 运行 annotation_kernel baseline
PYTHONPATH=../../src python bench_runner.py \
  --workload D --baseline annotation_kernel \
  --input fixtures/workload_d_C20_D4_seed42.json \
  --output /tmp/d_result.json --measure-memory

# 比较
python compare_workload_d.py \
  --input fixtures/workload_d_C20_D4_seed42.json \
  --golden golden/workload_d_golden_seed42.json \
  --results /tmp/d_result.json \
  --output /tmp/d_comparison.json
```

**Workload D generator 参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--conditions` | 20 | condition 节点数量 |
| `--max-depth` | 4 | 树最大嵌套深度 |
| `--weighted-ratio` | 0.8 | 带 weight 的 condition 比例 |
| `--confidence-ratio` | 0.7 | 带 condition_confidence 的节点比例 |
| `--seed` | 42 | 随机种子 |
| `--scale` | 1x | 规模标签 |

**Workload D golden diff 检查项：**

| 检查项 | 阈值 | 说明 |
|--------|------|------|
| aggregate_certainty | abs < 1e-6 | 瓶颈值匹配 |
| per-condition impact | abs < 1e-6 | 每个 condition 的 impact 匹配 |
| ranking order | exact | atom_key 序列完全匹配 |
| bottleneck marking | set equality | is_bottleneck 集合匹配 |
| condition coverage | set diff | 无 missing / extra |

## 4. 独立基准

### bench_core_ledger_paths.py

Ledger 微基准，测量 `compute_chosen_for_predicate`、`project_view_facts`、`resolve_mapping_predicate` 的最小/中位耗时。

```bash
PYTHONPATH=../../src python bench_core_ledger_paths.py --rows 3000 --rounds 5
```

### bench_scenario_a_audit_delivery_shape.py

Scenario A 审计交付全链路基准（rule 执行 → trace readback → export → static render）。

```bash
PYTHONPATH=../../src python bench_scenario_a_audit_delivery_shape.py --scales 1,100,1000 --output /tmp/scenario_a.json
```

## 5. 回归检测

在 annotation 模块变更后，运行以下序列验证无回归：

```bash
cd tools/benchmarks

# Workload D（certainty annotation 核心）
PYTHONPATH=../../src python bench_runner.py \
  --workload D --baseline annotation_kernel \
  --input fixtures/workload_d_C20_D4_seed42.json \
  --output /tmp/d_result.json --measure-memory

# Workload A（验证 annotation import 无副作用）
PYTHONPATH=../../src python bench_runner.py \
  --workload A --baseline souffle_full_a \
  --input fixtures/workload_a_N200_E800_seed42.json \
  --output /tmp/a_result.json --measure-memory

# 比较 D
python compare_workload_d.py \
  --input fixtures/workload_d_C20_D4_seed42.json \
  --golden golden/workload_d_golden_seed42.json \
  --results /tmp/d_result.json \
  --output /tmp/d_comparison.json
```

## 6. Fixture / Golden 约定

- Fixture 文件命名：`workload_X_<scale_params>_seed<N>.json`
- Golden 文件命名：`workload_X_golden_seed<N>.json`
- 所有 JSON 以 `ensure_ascii=False, indent=2, sort_keys=True` 写入，末尾带换行
- 种子固定确保可重现：相同参数 → 相同输出

## 7. 扩展新 Workload

1. 新建 `workload_X_reference.py`：实现 `generate_workload_X()`、`build_workload_X_golden()`、`compare_result_to_golden()`
2. 新建 `generate_workload_X.py`：CLI wrapper 调用 reference
3. 新建 `compare_workload_X.py`：CLI wrapper 调用 reference 的 compare
4. 在 `bench_runner.py` 中：
   - 添加 `WORKLOAD_X` 常量
   - 添加 `_load_workload_X()` loader
   - 添加 dispatch 分支 + baseline runner(s)
5. 生成 fixture + golden 并提交
