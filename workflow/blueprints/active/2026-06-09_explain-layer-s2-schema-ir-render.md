# Task Blueprint: S2 — Schema IR repr storage + render_entity_repr

- Status: scoped
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/sdk/schema.py` / `authoring/schema_dsl_parse.py`(emit repr → authoring out)
  - `src/factgraph/authoring/schema_compile.py`(store repr → IR)
  - `src/factgraph/core/schema/schema_ir.py`(IR validation + **digest exclusion**)
  - `src/factgraph/application/schema_runtime.py`(`SchemaIndex`/`EntityTypeInfo`/`PredicateInfo` 携带 repr + **新增 `render_entity_repr`**)
- Related Docs:
  - Design spec §5.2(默认 label)/§5.3(解析遍): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s2-schema-ir-render.audit.md](./2026-06-09_explain-layer-s2-schema-ir-render.audit.md)

---

## 1. Problem

S1 在 DSL 层接收/校验了 `repr`,但**故意不入 IR**。S2 把 repr 流进 schema IR 并暴露到 `SchemaIndex`,再实现 design §5.3 解析遍纯函数 `render_entity_repr`(entity-ref + identity 值 → Meta.repr label;无 Meta.repr 时 §5.2 默认 label)。这是 S4 prober 烘焙(`%ENT` label 解析)的前置。

## 2. Goals

1. **emit 反转**:sdk `to_authoring` + authoring 解析现在**把 repr 写进 authoring out**(S1 是不写)。
2. compile 存 repr:entity `Meta.repr` + 各 `Field/Identity.repr` 进 IR。
3. **digest 决策(已锁,见 §6)**:repr 入 IR 但**排除出 identity digest** → `schema_digest` 不随 repr 变。
4. `SchemaIndex` 携带 repr:`EntityTypeInfo.meta_repr` + `PredicateInfo.repr`(或等价)。
5. **新增 `render_entity_repr`**(schema_runtime.py):解析遍 + §5.2 默认 label。

## 3. Non-goals

- prober 烘焙 / 渲染遍 / atom repr_text(S4)。
- `Rule.repr` 结论渲染(S0 已改名;结论行接通在 S4/S5)。
- `description` 处理 —— 已由前置 cleanup slice 2b **删除**;S2 不涉及 description(仅处理 repr)。
- 两遍渲染的"渲染遍"(S4);S2 只做"解析遍"(entity label)。

## 4. Current Context(preflight 已完成)

- **digest**:`SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS = {"generated_at"}`(schema_ir.py:31);S2 若把 `repr` 作为嵌套字段写进 IR,默认会进入 identity digest → 必须显式排除。Schema `description` 已由前置 cleanup slice 删除。
- **render target**:`schema_runtime.py` — `IdentityFieldInfo(name,type_domain)`、`PredicateInfo(... pattern)`、`EntityTypeInfo(entity_type, identity_fields, exists_predicate_id, identity_predicates)`、`SchemaIndex(schema_ir, schema_digest, entities, ...)`。repr 需经 IR → 这些 info 类。
- **compile**:`entity_out`(version/tags)+ `_copy_pattern_enum` 是 repr 存储 hook 点。
- **S1 现状**:repr 校验在 `schema_repr.py`(已复用),但 sdk `_add_common_authoring` / authoring `_apply_common_member_kwargs` 不发射 repr;S2 需让它们发射(或新增 repr 专门发射路径)。

## 5. Proposed Shape

### emit + store + index(repr 进 IR)

- sdk/authoring:repr 写入 authoring out(member repr + Meta repr)。
- compile:entity_out 加 `meta_repr`(或 `repr`);identity/field 条目加 `repr`。schema_ir 校验允许这些键。
- SchemaIndex:`EntityTypeInfo` 加 `meta_repr: str | None`;`PredicateInfo` 加 `repr: str | None`(member 级)。

### render_entity_repr(design §5.3 解析遍 + §5.2 默认 label)

```
render_entity_repr(index: SchemaIndex, entity_type: str, identity_values: Mapping[str, Any]) -> str
```
- 有 `Meta.repr`:替换 `%CLS`→entity_type;`%<id_field>`→identity_values[field]。
- 无 `Meta.repr`:默认 label = `"<EntityCls> <第一个 identity 字段值>"`(§5.2)。
- identity-only 约束保证此遍永远可解析(不依赖非 identity 字段)。

## 6. Boundaries And Invariants

- **★INV-digest-stable(延续 S1)**:`schema_digest(schema with repr)` == `schema_digest(same schema without repr)`。即 repr 入 IR 但**排除出 identity canonicalization**。
  - 机制(Codex S2 preflight 选其一,锁不变式不锁机制):
    - (a) repr 存入**顶层 excluded 区**(新顶层 key 加进 `SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS`,同步 REQUIRED/allowed 顶层校验);或
    - (b) repr 嵌套在 fields/entity,但 `canonicalize_schema_ir_identity_jcs` 在 canon 前**剥离 nested repr**。
- `description` 已由前置 cleanup slice 2b 删除;S2 digest 排除仅针对 repr。
- `render_entity_repr` 是**纯函数**(无 IO,只读 SchemaIndex + 入参)。
- 占位符替换严格按 §5.2(Meta 只 `%CLS` + identity 字段);S1 已在定义时校验,S2 渲染时可信任。
- INV-6 application-first;单线性栈(S1 之上)。

## 7. Acceptance

- [ ] repr 流入 IR:`Field/Identity.repr` + `Meta.repr` 出现在 compiled SchemaIR
- [ ] **★digest no-change**:同 schema with/without repr → `schema_digest` 相等(repr 排除出 identity canon);**新增专项测试**
- [ ] `SchemaIndex` 暴露 repr:`EntityTypeInfo.meta_repr` + `PredicateInfo.repr`(或等价)非空可读
- [ ] `render_entity_repr`:有 Meta.repr → 正确替换 `%CLS`/`%<id_field>`;无 → §5.2 默认 label;**红/绿覆盖两路**
- [ ] default label 边界:多 identity 字段时取第一个;identity 值缺失的处理(明确定义)
- [ ] `version` 等结构字段仍影响 digest,`repr` 不影响 digest
- [ ] 受影响 docs(schema IR / runtime)同步

## 8. Implementation Plan

1. emit:sdk `to_authoring` + authoring 解析发射 repr(member + Meta)进 authoring out。
2. compile:`schema_compile` 存 repr 进 entity_out / field 条目。
3. IR + digest:`schema_ir` 允许 repr 键;按 §6 机制把 repr 排除出 identity canon(digest no-change test 驱动)。
4. SchemaIndex:`EntityTypeInfo`/`PredicateInfo` 加 repr 字段 + 构建逻辑填充。
5. `render_entity_repr`:解析遍 + 默认 label(纯函数)。
6. 测试:IR 存储 + digest no-change + render 两路 + structural digest 回归;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/core/schema/docs/README.md`(repr 进 IR + digest 排除说明)
- `src/factgraph/application/docs/`(render_entity_repr 入口,若有)

## 10. Outcome / Deviations

实施后填写。
