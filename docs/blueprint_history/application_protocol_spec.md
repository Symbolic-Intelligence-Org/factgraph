> 状态：已实现（Phase 0 范围）  
> 类型：协议蓝图  
> 说明：本文档保留为历史 application protocol Phase 0 协议草案；其 Phase 0 范围已有实现承接，但它不是当前实现真相的唯一来源。

# Application Protocol Specification

## Goal

定义 `application/protocol` 层的 Phase 0 协议草案，用于稳定以下边界：

- common DTO
- schema runtime DTO
- entity read DTO
- entity write DTO

本文件不讨论：

- SDK facade 设计
- HTTP API 形状
- graph projection 细节
- relationship family / binding 的完整协议

这些内容分别见：

- `docs/application_projection_blueprint.md`
- `docs/frontend_entity_ui_design.md`

## Design Decisions

- canonical DTO 使用 `dataclass(frozen=True)`
- `TypedDict` 仅用于 JSON ingress/egress 边界适配
- `EntityRef` 使用结构体，不绑定 `idref_v1` 字符串编码
- 错误通过 `errors: tuple[ErrorDTO, ...]` 返回，不穿透异常
- warnings 与 errors 分离
- 新增字段必须有默认值，保证前向兼容
- sequence 字段优先使用 tuple，避免 DTO 被原地修改

## Validation Boundary

协议约束分三层：

1. shape-level
   - 可在 `__post_init__` 中验证
   - 例如 required field、互斥字段、枚举值合法性
2. schema-level
   - 由 `schema_runtime` 或 `application` 层校验
   - 例如 entity type 是否存在、field path 是否有效、identity key 是否完整
3. execution-level
   - 由 planner / runtime / capability gating 校验
   - 例如是否支持 atomic multi write、是否允许 auto-binding

因此：

- DTO 构造不应尝试依赖运行时 store
- 需要 schema 或 capability 的校验必须延后到 application 层

## Common Types

### JSONValue

```python
JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
```

说明：

- protocol 层只允许 JSON-safe 值
- `bytes`、`datetime`、`UUID` 等 core/native 值，必须先被 adapter 规范化后再进入协议层
- `EntityRef` 不属于 `JSONValue`，而是独立结构体

### ErrorDTO

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorDTO:
    code: str
    message: str
    path: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, JSONValue] = field(default_factory=dict)
```

约束：

- `code` 应为 `SCREAMING_SNAKE_CASE`
- `path` 表示错误关联字段路径，例如 `("identity", "name")`
- `details` 只存 JSON-safe 调试信息

### WarningDTO

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WarningDTO:
    code: str
    message: str
    path: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, JSONValue] = field(default_factory=dict)
```

语义：

- 结构与 `ErrorDTO` 相同
- 只表示非致命问题，不阻塞 command / query

## Schema Runtime Protocol

### IdentityValue

```python
IdentityValue = dict[str, JSONValue]
```

约束：

- key 必须是 identity field name
- value 必须是 JSON-safe 且已完成 protocol 级规范化

### EntitySelector

`EntitySelector` 表示“用于查找或创建目标实体的选择器”。

它可以是完整 identity，也可以是等待 application 层进一步 materialize 的部分 identity。

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntitySelector:
    entity_type: str
    identity: IdentityValue = field(default_factory=dict)
    encoded_ref: str | None = field(default=None, compare=False)
    allow_identity_defaults: bool = False
```

约束：

- `entity_type` 必须是 schema 中已定义的 entity type name
- `identity` 的 key 必须是该 entity type identity field 的子集
- 当 `allow_identity_defaults=False` 时，selector 应能被解析成完整 `EntityRef`
- `encoded_ref` 仅为缓存，不参与比较语义

### EntityRef

`EntityRef` 表示“已完整解析的实体引用”。

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityRef:
    entity_type: str
    identity: IdentityValue
    encoded_ref: str | None = field(default=None, compare=False)
```

约束：

- `identity` 的 key 必须与该 entity type 的 identity field 一一对应
- `identity` 的 value 不允许嵌套 `EntityRef`
- `encoded_ref` 仅为缓存，不参与 `__eq__` / `__hash__`

示例：

```python
EntityRef(
    entity_type="User",
    identity={"name": "alice"},
    encoded_ref="idref_v1:..."
)
```

### FieldPath

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldPath:
    entity_type: str
    field_name: str
```

约束：

- `field_name` 必须是该 `entity_type` 下已定义的 field

### SchemaCapability

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaCapability:
    supports_atomic_multi_write: bool = False
    supports_post_write_recompute: bool = False
    supports_write_retract_combo: bool = False
```

用途：

- 用于 capability gating
- 决定某个 binding mode 是否允许被编译为 `enabled`

## Entity Read Protocol

### FieldValue

```python
FieldValue = JSONValue | EntityRef
```

说明：

- 标量字段使用 `JSONValue`
- 引用字段使用 `EntityRef`

### FieldValueDTO

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FieldValueDTO:
    field: FieldPath
    value_kind: Literal["scalar", "entity_ref"]
    cardinality: Literal["single", "multi"]
    # single -> FieldValue | None
    # multi -> tuple[FieldValue, ...] | None
    value: FieldValue | tuple[FieldValue, ...] | None = None
```

约束：

- `cardinality="single"` 时，`value` 不能是 tuple
- `cardinality="multi"` 时，`value` 必须是 tuple
- `value_kind="entity_ref"` 时，所有值都必须是 `EntityRef`
- `value_kind="scalar"` 时，所有值都必须是 `JSONValue`

### AssertionRecordDTO

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssertionRecordDTO:
    assertion_id: str
    value: FieldValue | None = None
    active: bool = True
    meta: dict[str, JSONValue] = field(default_factory=dict)
```

约束：

- `assertion_id` 必须非空
- `value` 必须与所属字段的 kind 保持一致
- `meta` 只包含 protocol-safe 信息，不要求完整底层 ledger 表达

### FieldAssertionsDTO

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldAssertionsDTO:
    field: FieldPath
    active: tuple[AssertionRecordDTO, ...] = field(default_factory=tuple)
    history: tuple[AssertionRecordDTO, ...] = field(default_factory=tuple)
```

说明：

- `active` 表示当前活跃断言
- `history` 表示历史断言
- 当 `include_assertions=False` 时，可为空 tuple

### EntitySnapshotDTO

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntitySnapshotDTO:
    ref: EntityRef
    fields: dict[str, FieldValueDTO] = field(default_factory=dict)
    assertions: dict[str, FieldAssertionsDTO] = field(default_factory=dict)
    identity_available: bool = True
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)
```

约束：

- `fields` key 必须与 `FieldValueDTO.field.field_name` 一致
- `assertions` key 必须与 `FieldAssertionsDTO.field.field_name` 一致
- `identity_available=False` 时，`ref.identity` 仍表示当前 snapshot 的 canonical identity

使用场景：

- `identity_available=True` 表示该 snapshot 的 identity 已在当前 read path 中被完整 materialize，可直接复用为后续 selector
- `identity_available=False` 表示当前 snapshot 虽然带有 canonical `ref.identity`，但该 identity 是由投影或 hydration 过程恢复出的只读结果，不应默认作为“已验证的编辑入口”
- 典型场景包括 query hydration、部分投影视图、历史视图或其他非 entity-centric read path

### EntityReadRequest

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EntityReadRequest:
    mode: Literal["get", "find"]
    entity_type: str
    selector: EntitySelector | None = None
    field_filters: dict[str, FieldValue | tuple[FieldValue, ...]] = field(default_factory=dict)
    limit: int | None = None
    include_assertions: bool = False
    include_history: bool = False
    at_time_ns: int | None = None
    version: str | None = None
```

约束：

- `mode="get"` 时，`selector` 必填
- `mode="find"` 时，`selector` 可为空
- `limit` 仅用于 `find`
- `at_time_ns` 与 `version` 互斥
- `include_history=True` 时，允许自动推导 `include_assertions=True`
- `field_filters` 当前仅表示等值过滤，不表达复杂 where 逻辑
- `field_filters` 对 multi-value 字段采用“contains any”语义
- 如果需要“contains all”或“exact match”，应使用 query 协议，而不是 entity read 协议

### EntityReadResponse

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EntityReadResponse:
    mode: Literal["get", "find"]
    entity_type: str
    items: tuple[EntitySnapshotDTO, ...] = field(default_factory=tuple)
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)
```

约束：

- `mode="get"` 时，`items` 长度应为 `0..1`
- `errors` 非空时，`items` 仍可保留部分结果，但调用方不得默认其完整

示例：

```python
EntityReadRequest(
    mode="get",
    entity_type="User",
    selector=EntitySelector(entity_type="User", identity={"name": "alice"}),
    include_assertions=True,
)
```

错误示例：

```python
EntityReadResponse(
    mode="get",
    entity_type="User",
    items=(),
    errors=(
        ErrorDTO(
            code="ENTITY_NOT_FOUND",
            message="No entity matches selector",
            path=("selector",),
        ),
    ),
)
```

## Entity Write Protocol

### WriteValue

```python
WriteValue = JSONValue | EntitySelector | EntityRef
```

说明：

- 标量写入使用 `JSONValue`
- 引用写入允许使用 `EntityRef`
- 当依赖对象尚未完全 materialize 时，允许使用 `EntitySelector`

解析责任：

- `EntityWriteCommand` 只表达用户意图，不负责把 `EntitySelector` 解析为 `EntityRef`
- `EntityWritePlan` 生成阶段负责完成 selector resolution、identity materialization 和 dependency planning
- `plan apply` 阶段只消费已规划好的 `planned_ops`

### FieldMutation

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class FieldMutation:
    op: Literal["set", "add", "retract"]
    field: FieldPath
    value: WriteValue | None = None
    assertion_id: str | None = None
    meta: dict[str, JSONValue] = field(default_factory=dict)
```

约束：

- `set` / `add` 必须提供 `value`
- `retract` 必须提供 `assertion_id`
- `set` / `add` 不得同时提供 `assertion_id`
- `retract` 不得同时提供 `value`
- 当 `FieldMutation` 被包含在 `EntityWriteCommand` 中时，`field.entity_type` 必须与 `command.target.entity_type` 一致

### EntityWriteCommand

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityWriteCommand:
    target: EntitySelector
    mutations: tuple[FieldMutation, ...] = field(default_factory=tuple)
    create_if_missing: bool = False
    include_dependencies: bool = True
    command_meta: dict[str, JSONValue] = field(default_factory=dict)
```

约束：

- `target.entity_type` 必须与所有 `mutation.field.entity_type` 一致
- `mutations` 可为空，仅当 command 用于“ensure entity exists”时成立
- `create_if_missing=False` 时，planner 不应静默创建新实体

### PlannedOpDTO

```python
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PlannedOpDTO:
    op: Literal["record_exists", "set", "add", "retract"]
    target: EntityRef
    field: FieldPath | None = None
    value: FieldValue | None = None
    assertion_id: str | None = None
    meta: dict[str, JSONValue] = field(default_factory=dict)
```

约束：

- `record_exists` 不应携带 `field`、`value` 或 `assertion_id`
- `set` / `add` 必须同时携带 `field` 与 `value`
- `retract` 必须同时携带 `field` 与 `assertion_id`
- 当 `field` 存在时，`field.entity_type` 必须与 `target.entity_type` 一致

### EntityWritePlan

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityWritePlan:
    command: EntityWriteCommand
    resolved_target: EntityRef | None = None
    resolved_dependencies: tuple[EntityRef, ...] = field(default_factory=tuple)
    planned_ops: tuple[PlannedOpDTO, ...] = field(default_factory=tuple)
    can_apply: bool = False
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)
```

约束：

- `can_apply=True` 时，`errors` 应为空
- `resolved_target` 为空通常表示 identity 尚未完整 materialize 或 schema 校验失败
- `planned_ops` 是 application planner 的稳定输出，可用于 preview 与 commit
- `can_apply=False` 时，`planned_ops` 可以非空，表示 preview 已生成但当前不满足执行条件
- `can_apply=False` 且 `planned_ops` 为空，通常表示 plan 生成本身失败；调用方应结合 `errors` 判断

说明：

- `resolved_dependencies` 表示 planner 将 command 中所有依赖 `EntitySelector` 解析并规范化后的结果
- `planned_ops` 必须只包含 `EntityRef`，不再保留未解析 selector

### AppliedOpResultDTO

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AppliedOpResultDTO:
    op_index: int
    status: Literal["applied", "skipped", "failed"]
    assertion_id: str | None = None
```

约束：

- `op_index` 对应 `EntityWritePlan.planned_ops` 中的稳定顺序
- `assertion_id` 仅在实际落 ledger 的写入操作中出现

### EntityWriteResult

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityWriteResult:
    resolved_target: EntityRef | None = None
    applied: tuple[AppliedOpResultDTO, ...] = field(default_factory=tuple)
    errors: tuple[ErrorDTO, ...] = field(default_factory=tuple)
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)
```

约束：

- `errors` 非空时，`applied` 允许为空或部分成功，具体由 command mode 决定
- Phase 0 暂不在协议层定义 partial-commit mode，默认由上层 command policy 控制

示例：

```python
EntityWriteCommand(
    target=EntitySelector(entity_type="User", identity={"name": "alice"}),
    mutations=(
        FieldMutation(
            op="set",
            field=FieldPath(entity_type="User", field_name="lives_in"),
            value=EntityRef(entity_type="Country", identity={"code": "DE"}),
        ),
    ),
    create_if_missing=False,
)
```

错误示例：

```python
EntityWriteResult(
    resolved_target=None,
    applied=(),
    errors=(
        ErrorDTO(
            code="IDENTITY_INCOMPLETE",
            message="Target identity could not be materialized",
            path=("target", "identity"),
        ),
    ),
)
```

## Open Questions

以下问题仍留待下一轮协议细化：

- `EntityReadResponse` 是否需要 cursor / pagination
- `EntityWriteCommand` 是否需要多 root entity 支持
- query / graph projection / relationship family DTO 的具体字段
- `ErrorDTO.code` 的命名空间约定
- 是否需要显式 `PolicyDTO` 表示 partial commit / atomic policy
