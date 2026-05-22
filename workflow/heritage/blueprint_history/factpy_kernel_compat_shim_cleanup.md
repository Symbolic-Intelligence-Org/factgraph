# factpy_kernel 兼容层移除清单（core/adapters 重构后）

## 目标

在 `src/factpy_kernel/core` 与 `src/factpy_kernel/adapters/souffle` 路径稳定后，逐步移除当前为兼容旧 import 路径保留的 shim。

## 当前兼容层（建议分批移除）

### A. 顶层兼容包（旧路径包名）

- `src/factpy_kernel/protocol/`
- `src/factpy_kernel/schema/`
- `src/factpy_kernel/store/`
- `src/factpy_kernel/evidence/`
- `src/factpy_kernel/policy/`
- `src/factpy_kernel/view/`
- `src/factpy_kernel/rules/`
- `src/factpy_kernel/derivation/`
- `src/factpy_kernel/mapping/`
- `src/factpy_kernel/export/`
- `src/factpy_kernel/runner/`

这些目录目前主要用于兼容旧 import，例如 `factpy_kernel.store.api`。

### B. core 内的 Souffle 兼容 shim

- `src/factpy_kernel/core/rules/where_compile.py`
- `src/factpy_kernel/core/view/souffle_view_gen.py`

这两个文件现在转发到 `adapters.souffle.*`，用于过渡。

## 移除前检查（必须满足）

1. `core/adapters/sdk/authoring/audit` 内部代码不再引用旧顶层路径（已完成一轮清理，复查即可）。
2. 测试中旧路径 import 已按策略处理：
   - 要么全部迁到新路径；
   - 要么明确保留一部分测试用于覆盖兼容层。
3. 外部调用方（脚本、notebook、文档示例）已迁移或接受破坏性变更。
4. 版本策略明确（是否通过 minor/major 版本移除兼容层）。

## 推荐移除顺序

### 第 1 批：内部 shim（低风险）

- 删除 `src/factpy_kernel/core/rules/where_compile.py`
- 删除 `src/factpy_kernel/core/view/souffle_view_gen.py`

前提：所有代码都改为直接使用：

- `factpy_kernel.adapters.souffle.where_compile`
- `factpy_kernel.adapters.souffle.souffle_view_gen`

### 第 2 批：顶层 adapter 相关旧路径（中风险）

- `src/factpy_kernel/export/*`
- `src/factpy_kernel/runner/*`

前提：`sdk/authoring/tests` 不再依赖旧 `factpy_kernel.export.*` / `factpy_kernel.runner.*`。

### 第 3 批：顶层 core 旧路径（高影响）

- `src/factpy_kernel/protocol/*`
- `src/factpy_kernel/schema/*`
- `src/factpy_kernel/store/*`
- `src/factpy_kernel/evidence/*`
- `src/factpy_kernel/policy/*`
- `src/factpy_kernel/view/*`
- `src/factpy_kernel/rules/*`
- `src/factpy_kernel/derivation/*`
- `src/factpy_kernel/mapping/*`

前提：所有上游模块和测试已统一到 `factpy_kernel.core.*` / `factpy_kernel.adapters.*`。

## 每次移除后的验证建议

1. 导入冒烟检查（核心 + adapter + sdk/authoring）
2. 运行测试（至少核心 smoke / 关键 e2e）
3. 搜索残留旧路径 import：

```bash
rg -n "from factpy_kernel\\.(protocol|schema|store|evidence|policy|view|rules|derivation|mapping|export|runner)|import factpy_kernel\\.(protocol|schema|store|evidence|policy|view|rules|derivation|mapping|export|runner)" src/factpy_kernel
```

## 建议的最终稳定导入约定

- 语义核心：`factpy_kernel.core.*`
- Souffle 适配：`factpy_kernel.adapters.souffle.*`
- 上游入口层：`factpy_kernel.sdk.*` / `factpy_kernel.authoring.*` / `factpy_kernel.audit.*`
