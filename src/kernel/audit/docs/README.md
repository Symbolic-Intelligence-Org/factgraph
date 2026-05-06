# FactPy Audit 文档

本目录记录 `src/kernel/audit` 的当前实现口径，面向需要读取 audit package、做离线审计查询、构建 DTO 或消费 evidence graph 的开发者。完整静态站点渲染属于外部 delivery layer，不属于 kernel-only package。

## 当前文档

- `src/kernel/audit/docs/01_overview.md`
  - audit 模块职责、公共入口、审计工作流、round event log、与 runtime/registry 的边界。
- `src/kernel/audit/docs/02_evidence_graph.md`
  - audit 层统一 explainability DTO 与 standalone renderer：`EvidenceGraph` 的角色、最小数据模型、JSON round-trip helper、`evidence_graphs.jsonl` package contract、HTML fragment renderer 与当前边界。
- `src/kernel/audit/docs/03_audit_package_contract.md`
  - audit package 的 required/optional files、`round_events.jsonl` contract、query-derived surfaces、ECSS compliance ownership 边界与最小 provenance carrier mapping。

## 使用约定

- 本目录文档以当前 audit package 读取与查询实现为准。
- 如 `AuditQuery`、audit package contract 或 `EvidenceGraph` 共享 DTO 有变更，应同步更新本目录文档与相关测试。
- 如完整静态站点输出、`site_manifest.json` 或 `ui_index.json` 有变更，应同步更新对应 delivery-layer 文档。
