# FactPy Audit 文档

本目录记录 `src/factpy_kernel/audit` 的当前实现口径，面向需要读取 audit package、做离线审计查询和静态展示的开发者。

## 当前文档

- `src/factpy_kernel/audit/docs/01_overview.md`
  - audit 模块职责、公共入口、审计工作流、与 runtime/registry 的边界。
- `src/factpy_kernel/audit/docs/02_evidence_graph.md`
  - audit 层统一 explainability DTO：`EvidenceGraph` 的角色、最小数据模型、冻结枚举与当前边界。

## 使用约定

- 本目录文档以当前 audit package 读取与查询实现为准。
- 如 `AuditQuery`、静态 UI、audit package contract 或 `EvidenceGraph` 共享 DTO 有变更，应同步更新本目录文档与相关测试。
