# FactPy Adapters 文档

本目录记录 `src/factpy_kernel/adapters` 的当前实现口径，面向需要理解 core 与外部执行/导出引擎边界的开发者。

## 当前文档

- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
  - Souffle adapter 的职责、模块分工、导出/运行链路、与 core 的边界。
- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
  - ProbLog adapter 的职责、导出/执行/解析链路、与 core 的边界。

## 使用约定

- 当前 `adapters` 目录下包含 `souffle` 与 `problog` 适配器。
- 如未来新增其它引擎适配器，应按同样方式在本目录追加新文档，而不是把所有适配器揉进一篇里。
