# Authoring 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/authoring`
- 最后更新：2026-03-18
- 目标读者：需要理解 schema/rule/derivation 预检、发布、registry 工作流的开发者

## 1. 模块职责

`authoring` 是 **authoring/control plane**，负责把 DSL / DTO / Python 对象整理成可预检、可发布、可持久化的资产版本。

它主要处理：

- schema preflight / compile
- rule preflight / compile
- derivation preview / compile
- derivation `head` 语法到 canonical IR 的 schema-aware lowering
- authoring diagnostics 与 DTO
- registry 文件读写
- publish / apply / session 工作流

它不负责：

- runtime facts 持久化
- `Store` / `Ledger` 查询与物化执行
- HTTP/BFF 路由

## 2. 当前推荐公共入口

`authoring` 已完成第一阶段收口。新代码优先从以下分组模块进入：

- `factpy_kernel.authoring.schemas`
  - `schema_preflight(...)`
  - `compile_authoring_schema_v1(...)`
  - `parse_authoring_schema_dsl_v1(...)`
- `factpy_kernel.authoring.rules`
  - `rule_preflight(...)`
  - `compile_authoring_rule_v1(...)`
  - `parse_authoring_rule_dsl_v1(...)`
- `factpy_kernel.authoring.derivations`
  - `derivation_dry_run_preview(...)`
  - `compile_authoring_derivation_v1(...)`
  - `parse_authoring_derivation_dsl_v1(...)`
- `factpy_kernel.authoring.registry_workflow`
  - `FileAuthoringRegistry`
  - session / publish / apply 相关 DTO 构建与工作流入口

`factpy_kernel.authoring.__init__` 已聚合这些公共入口。旧的叶子模块仍存在，但更适合作为实现细节或兼容路径，而不是新增依赖入口。

## 3. 声明元数据 contract（当前实现）

authoring 当前对 schema / rule / derivation 的“管理型声明元数据”已收敛为一组最小字段：

- `version`
- `description`
- `tags`

边界约束：

- `Entity`
  - `entity_type` 直接来自类名，不单独声明 `schema_id`
  - schema DSL 中通过 `class Meta:` 提供 `version / description / tags`
  - `Meta.description` 优先；仅当未显式提供 `description` 时才回退类 docstring
  - `Meta` 不是开放字典，出现其他键会在 parse / SDK 声明期报错
- `Rule`
  - `description`、`tags` 走 `Rule(...)` 顶层参数或 authoring payload 顶层键
- `Derivation`
  - `description`、`tags` 走 `Derivation(...)` 顶层参数或 authoring payload 顶层键
  - `target` 仍是兼容字段；高层声明推荐以 `head` 为主

这些字段会被 compiler 校验并保留在 authoring 资产里，但不参与 `where` 校验、candidate 生成或 accept 语义。

### 3.1 schema DSL 示例

```python
class EmploymentEvent(Entity):
    """只有在 Meta.description 缺省时才作为 description fallback。"""

    class Meta:
        version = "v1"
        description = "雇佣事件"
        tags = ["employment", "event"]

    event_id: str = Identity(primary_key=True)
    company: str = Field(cardinality="single")
```

### 3.2 rule / derivation payload 示例

```python
rule_payload = {
    "rule_id": "employment_match",
    "version": "v1",
    "description": "匹配雇佣相关事实",
    "tags": ["employment", "query"],
    "select": ["$u"],
    "where": [("pred", "user:name", ["$u", "$name"])],
}

derivation_payload = {
    "derivation_id": "employment_event_from_resume",
    "version": "v1",
    "description": "从简历事实推导雇佣事件",
    "tags": ["employment", "derivation"],
    "head": {...},
    "where": [...],
}
```

## 4. 内部结构（按主题）

- `schema_compile.py`, `schema_dsl_parse.py`
  - schema DSL 解析与 `SchemaIR` 编译
- `rule_compile.py`, `rule_dsl_parse.py`
  - rule DSL 解析、校验与编译
- `derivation_compile.py`, `derivation_dsl_parse.py`
  - derivation DSL 解析、预览与编译（含 head 自动推断路径）
- `dto.py`, `diagnostic_codes.py`
  - authoring DTO 结构与稳定 diagnostic code
- `registry_fs.py`
  - 文件型 registry 后端
- `publish.py`, `apply_execute.py`, `session.py`, `workflow.py`, `dsl_bridge.py`
  - authoring session / publish / apply / DSL bridge 工作流
- `cli.py`
  - authoring CLI 入口

## 5. Derivation v2 语义要点（实现口径）

- `head` 结构决定默认路径：
  - `EntityType(...)` -> entity 路径
  - `EntityType.field(...)` -> fact 路径
- 用户语法不再支持 `materialize_as` / `id_policy`；若输入包含这两个字段，compile 直接报错。
- schema compile 为所有 `Entity` 自动生成 `<T>:exists` predicate，不再依赖 `is_record` 作为行为开关。
- no-head（`target + head_vars`）仍保留为 fact-only 兼容路径。

### 5.1 最小输入示例（authoring payload）

fact 路径（`head=Entity.field(...)`）：

```python
payload = {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "head": {
        "kind": "head_call",
        "callee_kind": "pred_ref",
        "entity_type": "Person",
        "field": "country_copy",
        "kwargs": {"person": "$E", "country_copy": "$C"},
    },
    "where": [("pred", "person:country", ["$E", "$C"])],
}
```

entity 路径（`head=EntityType(...)`）：

```python
payload = {
    "derivation_id": "drv.speaks",
    "version": "1.0.0",
    "head": {
        "kind": "head_call",
        "callee_kind": "entity_type",
        "entity_type": "Speaks",
        "kwargs": {"user": "$U", "language": "$L"},
    },
    "where": [("pred", "person:country", ["$U", "de"]), ("pred", "user:lang_pref", ["$U", "$L"])],
}
```

### 5.2 常见 compile 错误（快速定位）

- `$.materialize_as`：用户仍传入了已废弃字段 `materialize_as`。
- `$.id_policy`：用户仍传入了已废弃字段 `id_policy`。
- `$.head`：`head` 结构非法，或与 schema 中字段/实体不匹配。
- `$.where[...]`：where sugar 无法在 schema 中找到对应 exists/role predicate。

## 6. Registry 文件布局

`FileAuthoringRegistry(root_dir=...)` 使用文件系统保存 authoring 资产，典型布局为：

```text
root_dir/
  schema/
    schema_ir.json
  rules/
    <rule_id>/<version>.json
  derivations/
    <derivation_id>/<version>.json
  registry_manifest.json
  authoring_apply_events.jsonl
```

这些文件是 **authoring 资产仓库**，不是 runtime 数据库。

## 7. 典型工作流

### 7.1 预检 / 编译

1. 输入 schema/rule/derivation 的 DSL、DTO 或对象定义
2. 通过 `schemas/rules/derivations` 分组模块做 parse / preflight / compile
3. 获得结构化结果或 diagnostics

### 7.2 发布到 registry

1. 创建 `FileAuthoringRegistry(root_dir=...)`
2. 写入 schema/rule/derivation 对应版本
3. 更新 manifest
4. 记录 apply/publish 相关 event

### 7.3 被 SDK / service 消费

- `SDKRegistry` 是 `authoring` 的 Python 友好 facade
- `service.registry_v1` 通过 `FileAuthoringRegistry` 提供 HTTP 读接口
- `service.runtime_v1` 也可读取 registry 中的 schema/rule，以支持 runtime session 与 `RuleRef` 解析

## 8. 与其他层的边界

- `core`
  - `authoring` 会调用 core 的 `SchemaIR`、规则编译和运行时契约，但不负责 runtime facts
  - `version / description / tags` 这类声明元数据在这里完成校验与保留；core 本身不赋予执行语义
- `sdk`
  - `SDKRegistry` 对 `authoring` 做更友好的封装
- `service`
  - service 层可把 authoring registry 暴露成前端可消费接口
- `ecss`
  - `factpy_kernel.ecss` 负责提供 shared domain preset（如 ECSS VCD predicates）
  - authoring 可消费这些 preset 进入 schema/registry 工作流，但不拥有 preset 本身
- `audit`
  - audit 读取的是导出的 package，不直接消费 authoring registry

## 9. 当前限制

- `authoring` 解决的是“资产版本”和“预检/发布工作流”，不是 runtime 执行闭环
- registry 中的 rule / derivation 还没有完全变成 runtime 的一等执行入口
- 叶子模块仍处于兼容期，第二阶段收口后可能继续收缩内部表面
