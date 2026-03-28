# Examples Index

本目录放的是示例、notebook 和少量导出产物。它们用于演示当前能力，但**不是**模块实现真相；实现真相仍以 `src/factpy_kernel/*/docs/` 为准。

维护约定：

- 同时存在 `.py` 和 `.ipynb` 时，优先把 `.py` 当作行为基线，再同步 notebook。
- PyReason notebook 若报 `No module named 'pyreason'`，先在 notebook 里检查 `sys.executable`，确认 kernel 指向装有 `pyreason` 的环境。
- `*.html` 导出产物不是主编辑入口，优先通过对应 demo 重新生成。

## 当前示例状态

- `examples/example_full.py`
  - 当前 SDK 的完整 walkthrough。已在 2026-03-28 重写到现行 API：`single|multi` cardinality、显式 derivation accept、无 `pred_id` override、无 `Meta.is_record`。
- `examples/factpy_example.ipynb`
  - 大而全的 notebook 参考。当前未发现与现行 SDK 表面明显冲突的问题。
- `examples/certainty_evidence_tree.ipynb`
  - certainty / evidence tree 高阶解释链路示例。当前保留。

- `examples/esa_demo.py`
  - ECSS + Souffle 的完整审计 bundle demo。已移除示例层 `schema_ir` raw predicate 注入，改为显式 `Entity` 声明承载 `ecss:*` schema。
- `examples/ecss_compliance_demo.ipynb`
  - `esa_demo.py` 的 notebook 版本。已同步去掉 `extend_schema_ir_with_ecss_*` hack。
- `examples/ecss_pyreason_demo.py`
  - ECSS + PyReason 区间推理 demo。当前 API 基本对齐，保留。
- `examples/ecss_pyreason_demo.ipynb`
  - notebook 版本。代码路径保留；输出是否可运行取决于 Jupyter kernel 环境。

- `examples/dora_demo.py`
  - DORA + Souffle 审计 demo。当前保留。
- `examples/dora_compliance_demo.ipynb`
  - `dora_demo.py` notebook 版本。当前保留。
- `examples/dora_demo_standalone.html`
  - DORA demo 导出的静态 HTML 产物，不是主要维护入口。
- `examples/dora_pyreason_demo.py`
  - DORA + PyReason 模糊区间 demo。当前保留。
- `examples/dora_pyreason_demo.ipynb`
  - notebook 版本。当前保留。

- `examples/multi_engine_evaluate_demo.py`
  - shared evaluate surface demo。已去掉 relationship `owner_type` 手工补丁；当前口径是先 `compile_schema_from_classes([...Entity, Relationship])`，再把 `schema_ir` 交给 `SDKStore([Entity...], schema_ir=...)`。
- `examples/multi_engine_evaluate_demo.ipynb`
  - notebook 版本，已同步同一修正。
- `examples/pyreason_integration_demo.py`
  - adapter-local 的 PyReason 端到端集成示例。当前保留。
- `examples/pyreason_spike.py`
  - 更低层的 standalone spike，用来说明 PyReason provenance 事件日志形态；不是推荐产品 surface，但保留作为历史和适配层参考。
- `examples/souffle_provenance_v0_demo.py`
  - Souffle proof JSON 的极小解析示例，当前保留。

## 本轮重构重点

- 清理示例层 `schema_ir` 篡改，避免绕过 `Entity` / `Field` 声明模型。
- 消除 relationship `owner_type` 手补逻辑，让示例直接依赖编译器输出。
- 把 `example_full.py` 从旧版 API 演示更新到当前 SDK 文档口径。
