---
doc_type: spec
status: partial
source_of_truth: design
implementation_state: partial
owner: authoring
last_verified: 2026-03-14
---

> Partial status: 本文的 fixture 对 authoring 契约回归仍有参考价值，但其中包含历史语义样例，不应整体视为当前实现快照。

# Authoring 层契约 fixtures（Golden Fixtures v1）

> 注：本文件保留大量历史 fixture。Derivation 的当前执行语法以 v2 为准：`head` 自动判定 candidate kind，用户侧不再使用 `materialize_as/id_policy`。请优先参考 [docs/blueprint/candidate_protocol_v2.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/candidate_protocol_v2.md) 与 [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)。

目的：为 `/Users/zhenzhili/symbolic_agent/docs/Authoring 层契约.md` 提供 **语义映射回归样例**。本文件只锁定：

- Authoring 概念输入（伪代码/伪 DSL）
- 期望 Canonical SchemaIR 片段（关键字段）
- 期望 Authoring preflight / DTO / session DTO 的关键输出断言

不要求当前项目已实现 Python DSL parser；这些样例是未来 DSL/YAML/UI Editor 的共同编译基线。

---

## F1. 基础实体 + functional/multi 字段（Person / Company）

### F1-A Authoring 概念输入（伪表示）

```python
class Person(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="multi")
    age: int = Field(name="has_age", cardinality="functional")
    works_at: Company = Field(cardinality="multi")

class Company(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")
```

### F1-B 期望 SchemaIR 关键片段（canonical）

```json
{
  "entities": [
    {"entity_type": "Person", "identity_fields": [{"name": "source_system"}, {"name": "source_id"}]},
    {"entity_type": "Company", "identity_fields": [{"name": "source_system"}, {"name": "source_id"}]}
  ],
  "predicates": [
    {"pred_id": "person:name", "cardinality": "multi", "group_key_indexes": [0]},
    {"pred_id": "person:has_age", "cardinality": "functional", "group_key_indexes": [0]},
    {"pred_id": "person:works_at", "cardinality": "multi", "group_key_indexes": [0]},
    {"pred_id": "company:sector", "cardinality": "functional", "group_key_indexes": [0]}
  ]
}
```

### F1-C 关键断言（preflight / DTO）

- `schema_preflight.ok == true`
- `schema_preflight.summary.predicate_count == 4`
- `schema_preflight.summary.pred_ids` 包含 `person:has_age`
- 若使用 `build_schema_preflight_dto(...)`：
  - `status == "ok"`
  - `source_kind == "schema"`

---

## F2. 带维度的 functional 字段（fact_key → group_key_indexes）

### F2-A Authoring 概念输入（伪表示）

```python
class Person(Entity):
    source_system: str = Identity()
    source_id: str = Identity()

    # 每种语言一个 current name
    name_by_lang: str = Field(
        cardinality="functional",
        fact_key=["lang"],
        dims=[("lang", "string")]
    )
```

> 注：`fact_key=["lang"]` 是 Authoring 层语义名；canonical SchemaIR 必须落为 `group_key_indexes`。

### F2-B 期望 SchemaIR 关键片段（canonical）

```json
{
  "predicates": [
    {
      "pred_id": "person:name_by_lang",
      "arg_specs": [
        {"name": "person", "type_domain": "entity_ref"},
        {"name": "lang", "type_domain": "string"},
        {"name": "value", "type_domain": "string"}
      ],
      "cardinality": "functional",
      "group_key_indexes": [0, 1]
    }
  ]
}
```

### F2-C 关键断言（语义）

- `group_key_indexes` **必须**包含 `0`（E）
- `group_key_indexes` **必须**包含 `lang` 位置（`1`）
- `group_key_indexes` **不得**包含 value 位置（`2`）
- chosen / conflict 分组必须按 `(PredId, E, Lang)`，而非 `(PredId, E)` 或 `(PredId, E, Lang, Name)`

---

## F3. Reified relation（Employment）

### F3-A Authoring 概念输入（伪表示）

```python
class Employment(Entity):
    uid: str = Identity(default_factory="uuid4")
    employee: Person = Field(cardinality="functional")
    employer: Company = Field(cardinality="functional")
    since: int = Field(cardinality="functional")
    title: str = Field(cardinality="functional")
```

### F3-B 期望 SchemaIR 关键片段（canonical）

```json
{
  "entities": [
    {"entity_type": "Employment", "identity_fields": [{"name": "uid", "type_domain": "uuid"}]}
  ],
  "predicates": [
    {"pred_id": "employment:exists", "cardinality": "functional", "group_key_indexes": [0]},
    {"pred_id": "employment:employee", "cardinality": "functional", "group_key_indexes": [0]},
    {"pred_id": "employment:employer", "cardinality": "functional", "group_key_indexes": [0]},
    {"pred_id": "employment:since", "cardinality": "functional", "group_key_indexes": [0]},
    {"pred_id": "employment:title", "cardinality": "functional", "group_key_indexes": [0]}
  ]
}
```

### F3-C 关键断言（语义）

- reified relation 必须生成 `<T>:exists`
- role predicates 与属性 predicates 必须使用同一 canonical 前缀/命名策略
- `uid` 默认值策略属于 authoring/write-time policy；一旦生成并落库，EntityRef 必须稳定

---

## F4. `aliases` / `display_name` 与 canonical `pred_id`

### F4-A Authoring 概念输入（伪表示）

```python
phone: str = Field(
    pred_id="person:phone",
    display_name="Phone",
    aliases=["mobile", "handy"],
    cardinality="multi"
)
```

### F4-B 期望 SchemaIR 关键片段（canonical）

```json
{
  "predicates": [
    {
      "pred_id": "person:phone",
      "cardinality": "multi",
      "group_key_indexes": [0],
      "aliases": ["mobile", "handy"],
      "display_name": "Phone"
    }
  ]
}
```

### F4-C 关键断言（执行边界）

- 写入 claim / view / export / where 编译统一使用 `person:phone`
- alias 仅用于导入解析映射或 authoring 搜索/兼容
- alias 不进入 `group_key_indexes` / conflict key / EntityRef

---

## F5. Authoring preflight / DTO / session DTO 聚合（当前已实装契约）

### F5-A schema preflight（warning）

输入：空 `predicates` 的 SchemaIR（但结构合法）

期望关键输出：

- `authoring_preflight_v1.kind == "schema"`
- `ok == true`
- `warnings[0].code == "empty_predicates"`
- `authoring_ui_dto_v1.status == "warning"`（经 `build_schema_preflight_dto` 包装）
- `authoring_ui_dto_v1.diagnostics_contract.diagnostics_contract_version == "authoring_diagnostics_contract_v1"`
- `authoring_ui_dto_v1.diagnostics_contract.codes/phases` 与 canonical registry 一致（见 `/Users/zhenzhili/symbolic_agent/docs/Authoring 层契约.md` 第 7 节）

### F5-B derivation preview（warning：preview truncation）

输入：某个谓词可返回 >20 行 candidate 的 derivation preview

期望关键输出：

- `authoring_preflight_v1.kind == "derivation_dry_run"`
- `summary.preview_limit == 20`
- `warnings` 包含 `preview_truncated`
- `authoring_ui_dto_v1.status == "warning"`

### F5-C session DTO 聚合（ok / warning / error）

通过 `build_authoring_session_dto(...)` 聚合 `schema/rule/derivation`：

- 任一 section `status=="error"` → session `status=="error"`
- 无 error 且任一 warning → session `status=="warning"`
- 全部 ok 且无 warning → session `status=="ok"`

期望关键输出：

```json
{
  "authoring_session_dto_version": "authoring_session_dto_v1",
  "kind": "authoring_session",
  "diagnostics_contract": {
    "diagnostics_contract_version": "authoring_diagnostics_contract_v1"
  },
  "status": "warning",
  "summary": {
    "section_count": 2,
    "diagnostic_count": 0,
    "warning_count": 2,
    "status_counts": {"ok": 0, "warning": 2, "error": 0}
  }
}
```

### F5-D publish plan DTO（dry-run only，基于 session DTO）

通过 `build_authoring_publish_plan_dto(authoring_session_dto)` 生成“可执行变更计划（仅 dry-run）”：

- `authoring_publish_plan_dto_version == "authoring_publish_plan_dto_v1"`
- `mode == "dry_run_only"`
- `diagnostics_contract.diagnostics_contract_version == "authoring_diagnostics_contract_v1"`
- `actions[].section` 按 session `order` 保序
- `actions[].status`：
  - section `status=="error"` → `blocked`
  - section `status=="ok|warning"` → `planned`
- `actions[].reason_code`（blocked/skipped 时）必须是结构化 code（例如 `publish_blocked_section_error` / `publish_skipped_unsupported_section`）
- plan 顶层 `diagnostics[]/warnings[]` 使用与 authoring DTO 相同的结构（`phase/code/path/message/severity`），并复用 `diagnostics_contract`
- `summary.planned_count/blocked_count` 与 `actions[]` 一致

最小示例（warning 非阻塞）：

```json
{
  "authoring_publish_plan_dto_version": "authoring_publish_plan_dto_v1",
  "kind": "authoring_publish_plan",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "action_count": 1,
    "planned_count": 1,
    "blocked_count": 0
  }
}
```

### F5-E apply result DTO（dry-run only，基于 publish plan DTO）

通过 `build_authoring_apply_dry_run_result_dto(authoring_publish_plan_dto)` 生成“执行预演结果（仅 dry-run）”：

- `authoring_apply_result_dto_version == "authoring_apply_result_dto_v1"`
- `mode == "dry_run_only"`
- `diagnostics_contract` 原样沿用 publish plan DTO（canonical `codes/phases`）
- `actions[].plan_status -> actions[].status` 映射：
  - `planned -> would_apply`
  - `blocked -> blocked`
  - `skipped -> skipped`
- `actions[].reason_code`（若存在）必须透传自 publish plan action
- 顶层 `diagnostics[]/warnings[]` 默认透传自 publish plan；apply 层可追加自身结构化 issue（`phase="publish.apply"`）
- `actions[].diagnostics[]/warnings[]` 也可追加 apply 层 issue（例如 `apply_blocked_action` / `apply_skipped_action`），用于区分 plan-level 与 apply-level 判断
- `summary.would_apply_count/blocked_count/skipped_count` 与 `actions[]` 一致

最小示例（存在 blocked + skipped）：

```json
{
  "authoring_apply_result_dto_version": "authoring_apply_result_dto_v1",
  "kind": "authoring_apply_result",
  "mode": "dry_run_only",
  "status": "error",
  "summary": {
    "action_count": 2,
    "would_apply_count": 0,
    "blocked_count": 1,
    "skipped_count": 1
  }
}
```

### F5-F publish workflow bundle DTO（dry-run only，session → plan → apply 聚合）

通过 `build_authoring_publish_workflow_dry_run_bundle_dto(authoring_session_dto)` 一次生成完整 dry-run 工作流结果：

- `authoring_publish_workflow_bundle_dto_version == "authoring_publish_workflow_bundle_dto_v1"`
- `kind == "authoring_publish_workflow_bundle"`
- `mode == "dry_run_only"`
- 顶层 `session/publish_plan/apply_result` 三段均保留（便于 UI/CLI 一次渲染）
- 顶层 `status` 为三段状态聚合（`error > warning > ok`）
- 顶层 `diagnostics_contract` 复用 canonical contract（与 session/plan/apply 一致）

最小示例（warning）：

```json
{
  "authoring_publish_workflow_bundle_dto_version": "authoring_publish_workflow_bundle_dto_v1",
  "kind": "authoring_publish_workflow_bundle",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "session_status": "warning",
    "publish_plan_status": "warning",
    "apply_result_status": "warning"
  }
}
```

### F5-K apply execute result DTO（真实执行最小版，registry fs backend）

通过 `build_authoring_apply_execute_result_dto(authoring_publish_plan_dto, registry=...)` 在 file registry backend 上执行 apply：

- `authoring_apply_execute_result_dto_version == "authoring_apply_execute_result_dto_v1"`
- `kind == "authoring_apply_execute_result"`
- `mode == "apply_execute_v1"`
- `registry.backend == "file_registry_fs_v1"`
- `idempotency.apply_request_id` 可选；若重复请求命中已记录 run event，可返回 `idempotency.replayed=true`
- `idempotency.plan_digest` 为 canonical plan digest（`sha256:<hex>`）；相同 `apply_request_id` + 不同 `plan_digest` 必须报错（不执行 action）
- `transaction.policy == "best_effort_no_rollback_v1"` 且 `transaction.prevalidate_before_write == true`
- prevalidate 阻塞时不得执行写入（`partial_apply=false`）；仅执行阶段失败且已有前序写入时，`partial_apply=true`
- `actions[].status` 允许：`applied|noop|blocked|skipped`
- `actions[].backend_result`（applied/noop 时）提供 registry 写入结果摘要
- `diagnostics[]/warnings[]` 仍沿用 canonical diagnostics contract；registry 冲突等细节可放在 `diagnostic.details.registry_error_*`

最小示例（一次 applied + 一次 noop）：

```json
{
  "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
  "kind": "authoring_apply_execute_result",
  "mode": "apply_execute_v1",
  "status": "ok",
  "idempotency": {
    "apply_request_id": "req-123",
    "plan_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "replayed": false
  },
  "transaction": {
    "policy": "best_effort_no_rollback_v1",
    "rollback_supported": false,
    "rollback_attempted": false,
    "prevalidate_before_write": true,
    "prevalidate_status": "passed",
    "writes_started": true,
    "failure_phase": "none",
    "partial_apply": false
  },
  "registry": {
    "backend": "file_registry_fs_v1"
  },
  "summary": {
    "action_count": 2,
    "applied_count": 1,
    "noop_count": 1,
    "blocked_count": 0,
    "skipped_count": 0
  }
}
```

### F5-L publish workflow apply bundle DTO（session → plan → apply dry-run → apply execute）

通过 `build_authoring_publish_workflow_apply_bundle_dto(...)` 一次生成并执行完整 authoring 工作流（最小 file registry backend）：

- `authoring_publish_workflow_apply_bundle_dto_version == "authoring_publish_workflow_apply_bundle_dto_v1"`
- `kind == "authoring_publish_workflow_apply_bundle"`
- `mode == "apply_execute_v1"`
- 顶层保留 `session/publish_plan/apply_dry_run/apply_execute`
- `summary.apply_execute_*` 字段用于上层 UI/CLI 聚合展示

最小示例（warning 聚合）：

```json
{
  "authoring_publish_workflow_apply_bundle_dto_version": "authoring_publish_workflow_apply_bundle_dto_v1",
  "kind": "authoring_publish_workflow_apply_bundle",
  "mode": "apply_execute_v1",
  "status": "warning",
  "summary": {
    "session_status": "warning",
    "publish_plan_status": "warning",
    "apply_dry_run_status": "warning",
    "apply_execute_status": "warning",
    "apply_execute_partial_apply": false
  }
}
```

### F5-M file registry manifest / authoring apply events（最小持久化产物）

`FileAuthoringRegistry(root_dir)` 的最小持久化产物（v1）：

- `registry_manifest.json`
- `authoring_apply_events.jsonl`

`registry_manifest.json` 最小示例：

```json
{
  "authoring_registry_fs_version": "authoring_registry_fs_v1",
  "schema": {
    "path": "schema/schema_ir.json",
    "schema_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "rules": [
    {"rule_id": "rules.country_rows", "version": "v1", "path": "rules/rules.country_rows__abcd1234/v1__ef567890.json"}
  ],
  "derivations": [
    {"derivation_id": "drv.country", "version": "v1", "path": "derivations/drv.country__abcd1234/v1__ef567890.json"}
  ]
}
```

`authoring_apply_events.jsonl` 示例行（action + run）：

```json
{"kind":"authoring_apply_execute_action","action_id":"action:0:schema_preflight","section":"schema_preflight","action":"upsert_schema_ir","status":"applied","apply_request_id":"req-123"}
{"kind":"authoring_apply_execute_run","apply_request_id":"req-123","plan_digest":"sha256:1111111111111111111111111111111111111111111111111111111111111111","status":"ok","ok":true,"partial_apply":false,"idempotency":{"apply_request_id":"req-123","plan_digest":"sha256:1111111111111111111111111111111111111111111111111111111111111111","replayed":false},"transaction":{"policy":"best_effort_no_rollback_v1","rollback_supported":false,"rollback_attempted":false,"prevalidate_before_write":true,"prevalidate_status":"passed","writes_started":true,"failure_phase":"none","partial_apply":false}}
```

### F5-G schema DSL parser（语法层 → Authoring payload，最小切片）

`parse_authoring_schema_dsl_v1(source)` 只负责把受限 Python DSL 解析成 Authoring payload（**不直接生成 SchemaIR**）：

- 仅支持 `class <Name>(Entity): ...`
- 成员仅支持：
  - `x: T = Identity(...)`
  - `x: T = Field(...)`
  - `class Meta: ...`（简单常量赋值）
- 不执行用户代码（AST 解析子集）
- 解析结果可再交给 `compile_authoring_schema_v1(...)`

最小示例（DSL 输入）：

```python
class Person(Entity):
    source_id: str = Identity()
    age: int = Field(cardinality="functional", name="has_age")
    phone: str = Field(cardinality="multi", aliases=["mobile"])
```

最小示例（输出 payload 形状）：

```json
{
  "entities": [
    {
      "entity_type": "Person",
      "identity_fields": [{"name": "source_id", "type_domain": "string"}],
      "fields": [
        {"py_name": "age", "type_domain": "int", "cardinality": "functional", "name": "has_age"},
        {"py_name": "phone", "type_domain": "string", "cardinality": "multi", "aliases": ["mobile"]}
      ]
    }
  ]
}
```

### F5-H rule DSL parser（语法层 → Authoring rule payload，最小切片）

`parse_authoring_rule_dsl_v1(source)` 只解析受限 `Rule(...)` 调用为 Authoring rule payload（后续交给 `compile_authoring_rule_v1(...)`）：

- 仅支持顶层 `Rule(...)` 表达式或 `name = Rule(...)` 赋值
- 不执行用户代码（AST 子集）
- 不支持位置参数 / `**kwargs`

最小示例（DSL 输入）：

```python
country_rows = Rule(
    version="v1",
    select=["E", "$C"],
    body=[("pred", "person:country", ["$E", "$C"])],
    public=True
)
```

最小示例（输出 payload 形状）：

```json
{
  "name": "country_rows",
  "version": "v1",
  "select": ["E", "$C"],
  "body": [["pred", "person:country", ["$E", "$C"]]],
  "public": true
}
```

语法糖示例（DSL 输入）：

```python
rank_rows = Rule(
    version="v1",
    select=["E", "R"],
    where=Or(
        [Pred("person:rank", "$E", "$R"), In("$R", [3, 5]), Ge("$R", 4)],
        [Pred("person:rank", "$E", "$R"), Eq("$R", 9)]
    )
)
```

语法糖示例（输出 payload 形状）：

```json
{
  "name": "rank_rows",
  "version": "v1",
  "select": ["E", "R"],
  "where": [
    [["pred", "person:rank", ["$E", "$R"]], ["in", "$R", [3, 5]], ["ge", "$R", 4]],
    [["pred", "person:rank", ["$E", "$R"]], ["eq", "$R", 9]]
  ]
}
```

蓝图风格 where sugar 示例（DSL 输入，语法层）：

```python
with vars() as (li, p, c):
    Rule(
        select=["li", "p", "c"],
        where=[
            LivesIn(li),
            li.person == p,
            li.country == c,
        ],
    )
```

蓝图风格 where sugar 示例（parser 输出 payload 形状；注意此处仍是 sugar 原子）：

```json
{
  "select": ["li", "p", "c"],
  "where": [
    ["pred", "LivesIn:exists", ["$li"]],
    ["pred", "livesin:person", ["$li", "$p"]],
    ["pred", "livesin:country", ["$li", "$c"]]
  ]
}
```

说明（compile/preflight 阶段，schema-aware lowering）：

- 若提供 `SchemaIR`，上述 where sugar 会在 compile 阶段被映射到 schema 中真实的 record exists/role `pred_id`
- 例如可重写为 `li_record:exists` / `li_record:who` / `li_record:nation`（具体名称以 `SchemaIR.predicates` 为准，不依赖命名约定）

### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）

`parse_authoring_derivation_dsl_v1(source)` 只解析受限 `Derivation(...)` 调用为 Authoring derivation payload（后续交给 `compile_authoring_derivation_v1(...)`）：

- 仅支持顶层 `Derivation(...)` 表达式或 `name = Derivation(...)`
- 不执行用户代码（AST 子集）
- 不支持位置参数 / `**kwargs`

最小示例（DSL 输入，推荐写法：`head` 自动判定 candidate kind）：

```python
country_derivation = Derivation(
    head=Person.country(person=E, country=country),
    body=[("pred", "person:country", ["$E", "$country"])],
    mode="python",
    temporal_view="record"
)
```

最小示例（输出 payload 形状）：

```json
{
  "name": "country_derivation",
  "head": {
    "kind": "head_call",
    "callee_kind": "pred_ref",
    "entity_type": "Person",
    "field": "country",
    "kwargs": {"person": "$E", "country": "$country"}
  },
  "body": [["pred", "person:country", ["$E", "$country"]]],
  "mode": "python",
  "temporal_view": "record"
}
```

说明（v1 当前实现，硬边界）：

- `head_vars`（`select` 为兼容别名）按目标谓词 `target` 的 `arg_specs` 位置顺序映射。
- `arg0` 必须对应实体槽位（可绑定任意变量名，只要值能解码为 `entity_ref`）；这不是“实体字段平铺 select”。
- compile 阶段会把上述 `head=Person.country(...)` lowering 为 canonical `target_pred_id + head_vars`；parser fixture 这里展示的是**语法层 payload**，因此仍保留 `head`。
- Derivation 当前语法为 `head` 自动判定候选类型：`Entity.field(...) -> fact`，`EntityType(...) -> entity`。

语法糖示例（DSL 输入）：

```python
Derivation(
    target="person:rank",
    head_vars=["$E", "$R"],
    body=Or(
        [Pred("person:rank", "$E", "$R"), Gt("$R", 3)],
        [Pred("person:rank", "$E", "$R"), Not([Pred("person:blacklist", "$E", "x")])]
    ),
    mode="engine"
)
```

语法糖示例（输出 payload 形状）：

```json
{
  "target": "person:rank",
  "head_vars": ["$E", "$R"],
  "body": [
    [["pred", "person:rank", ["$E", "$R"]], ["gt", "$R", 3]],
    [["pred", "person:rank", ["$E", "$R"]], ["not", [["pred", "person:blacklist", ["$E", "x"]]]]]
  ],
  "mode": "engine"
}
```

entity head 示例（DSL 输入）：

```python
Derivation(
    head=Speaks(person=p, language=l),
    where=[Pred("person:country", "$E", "de"), Eq("$E", "$p")],
    mode="python"
)
```

entity head 示例（输出 payload 形状）：

```json
{
  "head": {
    "kind": "head_call",
    "callee_kind": "entity_type",
    "entity_type": "Speaks",
    "kwargs": {"person": "$p", "language": "$l"}
  },
  "where": [["pred", "person:country", ["$E", "de"]], ["eq", "$E", "$p"]],
  "mode": "python"
}
```

蓝图风格 where sugar 示例（Derivation DSL 输入，语法层）：

```python
with vars() as (p, c, l, li, hl):
    Derivation(
        head=Speaks(person=p, language=l),
        where=[
            LivesIn(li),
            HasLanguage(hl),
            li.person == p,
            li.country == c,
            hl.country == c,
            hl.language == l,
        ],
    )
```

蓝图风格 where sugar 示例（parser 输出 payload 形状；compile 阶段再做 schema-aware lowering）：

```json
{
  "head": {
    "kind": "head_call",
    "callee_kind": "entity_type",
    "entity_type": "Speaks",
    "kwargs": {"person": "$p", "language": "$l"}
  },
  "where": [
    ["pred", "LivesIn:exists", ["$li"]],
    ["pred", "HasLanguage:exists", ["$hl"]],
    ["pred", "livesin:person", ["$li", "$p"]],
    ["pred", "livesin:country", ["$li", "$c"]],
    ["pred", "haslanguage:country", ["$hl", "$c"]],
    ["pred", "haslanguage:language", ["$hl", "$l"]]
  ]
}
```

说明（schema-aware lowering，compile/preflight）：

- compile/preflight 在有 `SchemaIR` 时会把上述 sugar 原子映射到真实 record exists/role `pred_id`
- 若 `SchemaIR` 中不存在对应 record exists/role 谓词，compile 将报错（而不是继续按命名约定执行）
- 用户侧不再使用 `materialize_as` / `id_policy`，统一由 `head` 结构决定候选类型与后续实体化路径。

### F5-J DSL bridge（DSL source → session/workflow dry-run DTO，最小切片）

`authoring.registry_workflow` 提供“从 DSL 字符串直接到 dry-run DTO”的便捷入口（内部复用 parser + compile + preflight + workflow；旧 `authoring.dsl_bridge` 入口仍兼容）：

- `build_authoring_session_from_dsl_inputs_dto(...)`
- `build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto(...)`
- `build_authoring_session_from_dsl_inputs_safe_dto(...)`（parser 错误落为 canonical diagnostics）
- `build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto(...)`

约束（当前最小切片）：

- `rule_dsl` / `derivation_dsl` 若未提供 `store`，则必须同时提供 `schema_dsl`（由 session 自动编译 schema 并创建内存 Store）
- parser/compile/session/workflow 任一阶段异常统一包装为 `AuthoringDSLBridgeError`
- `safe` 变体在 parser 阶段失败时不抛异常；返回 `authoring_session_dto_v1` / workflow bundle，且错误落在对应 section 的 `diagnostics[]`（如 `schema.dsl_parse` / `rule.dsl_parse` / `derivation.dsl_parse`）
- `safe` 变体的 parser diagnostics 可携带 `dsl_error_kind`（`syntax|structure|input_type`）与可选 `details`（如 helper 级错误细分：`dsl_error_detail_code/helper/arg_index`）

最小示例（workflow bundle 输出形状）：

```json
{
  "authoring_publish_workflow_bundle_dto_version": "authoring_publish_workflow_bundle_dto_v1",
  "kind": "authoring_publish_workflow_bundle",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "session_status": "warning",
    "publish_plan_status": "warning",
    "apply_result_status": "warning"
  }
}
```

最小示例（safe session parse-error diagnostics 片段）：

```json
{
  "code": "authoring_rule_dsl_parse_error",
  "phase": "rule.dsl_parse",
  "path": "$.rule_dsl.body[0].where[].args[1]",
  "severity": "error",
  "dsl_error_kind": "structure",
  "details": {
    "dsl_error_detail_code": "helper_arg_type",
    "helper": "In",
    "arg_index": 1
  }
}
```

### F5-N authoring CLI（JSON/DSL 输入，最小入口）

最小命令（JSON payload 输入）：

```bash
python -m factpy_kernel.authoring.cli preflight --authoring-schema ./authoring_schema.json
python -m factpy_kernel.authoring.cli workflow-dry-run --authoring-schema ./authoring_schema.json --rule-request ./rule_request.json
python -m factpy_kernel.authoring.cli apply-execute --authoring-schema ./authoring_schema.json --registry-dir ./registry --apply-request-id req-001
```

最小命令（DSL 文件输入）：

```bash
python -m factpy_kernel.authoring.cli preflight --schema-dsl ./schema.py
python -m factpy_kernel.authoring.cli workflow-dry-run --rule-dsl ./rule.py --safe
python -m factpy_kernel.authoring.cli apply-execute --schema-dsl ./schema.py --registry-dir ./registry --apply-request-id req-002
python -m factpy_kernel.authoring.cli registry-list --registry-dir ./registry --kind rule_ids
python -m factpy_kernel.authoring.cli registry-list --registry-dir ./registry --kind apply_run_ids
python -m factpy_kernel.authoring.cli registry-show --registry-dir ./registry --kind rule --id rules.country_rows --latest
python -m factpy_kernel.authoring.cli registry-show --registry-dir ./registry --kind apply-run --id req-001
```

约束（v1，已实装）：

- DSL 输入通过 parser-first 路径编译为 authoring payload；不执行用户 Python 代码
- `--safe` 仅支持 `preflight` / `workflow-dry-run` 的 DSL 输入路径
- 同一组件不可同时给 JSON 与 DSL 输入（例如 `--authoring-schema` 与 `--schema-dsl` 不能并用）
- `registry-show rule|derivation` 必须给 `--latest` 或 `--version`
- `registry-list rule_versions|derivation_versions` 必须给 `--id`
- `registry-list apply_run_ids` 返回按 `apply_request_id` 排序的 run event 请求 id 列表（每个请求仅最近一次 run event）
- `registry-show apply-run` 只接受 `--id`（不接受 `--latest/--version`）

`apply-execute` 输出最小字段片段（JSON stdout）：

```json
{
  "authoring_publish_workflow_apply_bundle_dto_version": "authoring_publish_workflow_apply_bundle_dto_v1",
  "kind": "authoring_publish_workflow_apply_bundle",
  "mode": "apply_execute_v1",
  "apply_execute": {
    "kind": "authoring_apply_execute_result",
    "idempotency": {
      "apply_request_id": "req-001",
      "plan_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
      "replayed": false
    },
    "transaction": {
      "policy": "best_effort_no_rollback_v1",
      "rollback_supported": false,
      "rollback_attempted": false,
      "prevalidate_before_write": true,
      "prevalidate_status": "passed",
      "writes_started": true,
      "failure_phase": "none",
      "partial_apply": false
    }
  }
}
```

`registry-show` 输出最小字段片段（JSON stdout，rule latest）：

```json
{
  "kind": "authoring_registry_show_result",
  "show_kind": "rule",
  "latest": true,
  "id": "rules.country_rows",
  "item": {
    "rule_id": "rules.country_rows",
    "version": "v1"
  }
}
```

`registry-show` 输出最小字段片段（JSON stdout，apply-run）：

```json
{
  "kind": "authoring_registry_show_result",
  "show_kind": "apply-run",
  "id": "req-001",
  "item": {
    "kind": "authoring_apply_execute_run",
    "apply_request_id": "req-001",
    "status": "ok",
    "idempotency": {
      "apply_request_id": "req-001",
      "plan_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
      "replayed": false
    },
    "transaction": {
      "prevalidate_before_write": true,
      "failure_phase": "none",
      "partial_apply": false
    }
  }
}
```

`registry-list` 输出最小字段片段（JSON stdout，apply_run_ids）：

```json
{
  "kind": "authoring_registry_list_result",
  "list_kind": "apply_run_ids",
  "count": 2,
  "items": ["req-001", "req-002"]
}
```

`apply-execute --transaction-policy prevalidate_no_partial_strict_v2` 成功输出最小字段片段（v2 最小实现）：

```json
{
  "kind": "authoring_publish_workflow_apply_bundle",
  "apply_execute": {
    "status": "ok",
    "transaction": {
      "policy": "prevalidate_no_partial_strict_v2",
      "prevalidate_before_write": true,
      "prevalidate_status": "passed",
      "writes_started": true,
      "failure_phase": "none",
      "partial_apply": false
    },
    "diagnostics": []
  }
}
```

`apply-execute --transaction-policy unknown_policy_x` 错误输出最小字段片段（未知策略）：

```json
{
  "kind": "authoring_publish_workflow_apply_bundle",
  "apply_execute": {
    "status": "error",
    "transaction": {
      "policy": "unknown_policy_x",
      "prevalidate_before_write": false,
      "prevalidate_status": "skipped_transaction_policy_unsupported",
      "writes_started": false,
      "failure_phase": "prevalidate",
      "partial_apply": false
    },
    "diagnostics": [
      {
        "path": "$.apply_execute_options.transaction_policy",
        "details": {
          "requested_policy": "unknown_policy_x",
          "supported_policies": ["best_effort_no_rollback_v1"],
          "v2_reserved_not_implemented": false
        }
      }
    ]
  }
}
```

`authoring_apply_events.jsonl` 中 runtime blocked action event 最小片段（v1，已实装）：

```json
{
  "kind": "authoring_apply_execute_action",
  "apply_request_id": "req-rt-1",
  "action_id": "action:1:rule_preflight",
  "section": "rule_preflight",
  "status": "blocked",
  "reason_code": "apply_blocked_action",
  "diagnostics_summary": {
    "count": 1,
    "codes": ["apply_blocked_action"]
  }
}
```

`audit_ui_dto_v1` 中 `authoring_apply_run_detail` 最小片段（执行态摘要）：

```json
{
  "kind": "authoring_apply_run_detail",
  "apply_request_id": "req-rt-1",
  "execution_path": "runtime_partial",
  "execution_path_label": "Runtime partial apply",
  "execution_path_counts": {"runtime_partial": 1},
  "action_stats": {
    "diagnostic_code_counts": {"apply_blocked_action": 1}
  },
  "failure_summary": {
    "first_failure_action_id": "action:1:rule_preflight",
    "first_failure_section": "rule_preflight",
    "blocked_action_reason_codes": ["apply_blocked_action"],
    "blocked_action_diagnostic_codes": ["apply_blocked_action"]
  }
}
```

事务语义 v2（spec-only，未实装）预留片段（用于 docs 对齐校验；非 canonical runtime 输出）：

```json
{
  "kind": "authoring_apply_transaction_policy_v2_reserved",
  "transaction_policy": "prevalidate_no_partial_strict_v2",
  "spec_status": "reserved_not_implemented",
  "opt_in_required": true,
  "silent_upgrade_from_v1_forbidden": true,
  "phase": "publish.apply",
  "reserved_diagnostics_codes": [
    "apply_v2_prevalidate_blocked_actions_present",
    "apply_v2_partial_apply_forbidden",
    "apply_v2_transaction_policy_unsupported"
  ],
  "compatibility": {
    "idempotency_replay_same_as_v1": true,
    "prevalidate_failure_phase": "prevalidate",
    "writes_started_when_prevalidate_blocked": false,
    "partial_apply_forbidden": true
  }
}
```

---

## F6. 反例清单（用于后续 DSL 编译器 diagnostics）

以下反例建议在未来 DSL 编译器 / authoring parser 中作为固定回归项：

1. `fact_key` 引用未知维度（例如 `fact_key=["lang"]` 但未声明 `lang`）
2. `fact_key` 把 value 列误纳入 key（应拒绝）
3. `aliases` 与 canonical `pred_id` 冲突（重复/歧义）
4. Identity 字段与 Field 角色重叠且未显式声明策略（建议 warning 或 error）
5. `temporal_view="current"` 但 schema/where 不涉及 temporal 谓词（当前 preflight 已给 warning）

这些反例暂不要求本轮实现 parser，只要求后续 diagnostics code 与 `/Users/zhenzhili/symbolic_agent/docs/Authoring 层契约.md` 第 7 节口径一致。
