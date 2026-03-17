# Audit 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/audit`
- 最后更新：2026-02-28
- 目标读者：需要消费 audit package、做离线审计查询或静态展示的开发者

## 1. 模块职责

`audit` 是 **审计消费层**。它读取已经导出的 audit package，并提供查询、DTO 和静态站点渲染能力。

它主要负责：

- audit package 读取
- run / candidate / materialization / decision / failure 查询
- authoring apply events 查询
- 审计 DTO 构建
- 静态审计页面生成

它不负责：

- live runtime facts 查询
- registry 资产版本管理
- package 导出

## 2. 当前公共入口

- `load_audit_package(...)`
  - 从 audit package 目录读取数据
- `AuditQuery`
  - 结构化查询入口
- `render_audit_static_site(...)`
  - 生成静态审计站点
- `load_authoring_apply_events(...)`
  - 读取 authoring apply event 日志

对应模块：

- `reader.py`
- `query.py`
- `dto.py`
- `static_ui.py`
- `authoring_events.py`
- `assertions.py`

## 3. 典型工作流

### 3.1 读取 audit package

1. 先通过 adapter/runtime 导出 `package_kind="audit"` 的 package
2. 调用 `load_audit_package(package_dir)`
3. 得到 `AuditPackageData`

### 3.2 结构化查询

1. 创建 `AuditQuery(package)`
2. 调用：
   - `list_runs()`
   - `get_run_bundle(run_id)`
   - `list_materializations(...)`
   - `list_candidates(...)`
   - `list_decisions(...)`
   - `list_failures(...)`
   - `get_mapping_resolution(...)`
   - `list_authoring_apply_events(...)`

### 3.3 静态审计页面

1. 准备 `AuditPackageData`
2. 调用 `render_audit_static_site(...)`
3. 输出静态 HTML/资源

## 4. 与其他层的边界

- `adapters`
  - audit package 由 adapter 导出，audit 负责读取和消费
- `core`
  - audit 不直接查询 live `Ledger`
- `authoring`
  - audit 可消费 package 中携带的 authoring apply events，但不直接管理 registry

## 5. 当前限制

- audit 主要面向离线快照，不是实时审计接口
- 没有直接把 live runtime store 映射成 audit query 的入口
- 审计能力依赖导出的 package 是否完整包含所需 ledger / decision / authoring event 信息

## 6. Audit Package Artifact Files

当 package 以 `package_kind="audit"` 导出时，当前 package 除了 ledger / decision 相关文件外，也会附带 explain artifact dump：

- `audit/support_artifacts.jsonl`
  - 以 `support_digest` 为 key 的 flat JSONL rows
  - payload 复用 `SupportArtifact` 的 JSON-friendly shape
- `audit/rule_trace_artifacts.jsonl`
  - 以 `rule_run_id` 为 key 的 flat JSONL rows
  - payload 复用 `RuleTraceArtifact` 的 JSON-friendly shape

这些文件当前是全量导出，不做引用子集裁剪；它们的职责是让离线 audit consumer 能读取 explain carrier，而不是提供 online durable readback。
