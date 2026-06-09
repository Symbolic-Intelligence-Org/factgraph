# Task Blueprint: Cleanup — remove schema entity/field/Meta `description`

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Type: cleanup slice(subtractive;`feedback_cleanup_slice_cadence` 轻量格式)
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/sdk/schema.py`(`_DataMember.description` / `Entity.Meta.description`)
  - `src/factgraph/authoring/schema_dsl_parse.py`(member + Meta description 解析/allow-list)
  - `src/factgraph/authoring/schema_compile.py`(`_compile_optional_description` / `_copy_description_pattern_enum` 的 description 部分 / entity description)
  - `src/factgraph/core/schema/schema_ir.py`(IR description 校验,如有)
  - `src/factgraph/application/schema_runtime.py`(`PredicateInfo.description`)
- Audit Log:
  - [2026-06-09_explain-layer-cleanup-schema-description.audit.md](./2026-06-09_explain-layer-cleanup-schema-description.audit.md)

---

## 1. Problem / 动机

`<user>` 决定移除 schema entity/field/Meta `description`:它是 `repr` 的下位替代,且**当前零消费**。preflight 实证(2026-06-09):

- `.description` 读取点 **0**(全 src 无任何逻辑/render/API 消费 schema description)。
- `PredicateInfo.description` 运行时**不读**。
- tests / examples 中 schema `description=` 用法 **0**。
- `sdk/dsl/rule.py` 的 `Rule.description` / `Inference.description` 是**独立概念**(owner="Rule"/"Inference"),**不在本 slice 范围**。

排在 S2(repr 入 IR)之前,使 S2 的 digest 排除机制只需处理 repr。

## 2. Scope-freeze(narrative)

删除 schema **entity/field/Meta** 三处 `description`:DSL 参数(`Field(description=)`/`Identity(description=)`/`Entity.Meta.description`)+ authoring AST 解析与 allow-list + compile 存储 + IR(如有 description 键)+ `PredicateInfo.description` + 相关 docs。`pattern=` 保留不动。Rule/Inference description 不动。

## 3. Non-goals

- 不动 `Rule.description` / `Inference.description`(sdk/dsl/rule.py — 独立)。
- 不动 `pattern=`。
- 不加 `repr`(S2)。
- 不动 `generated_at` 等既有 digest 排除。

## 4. Boundaries And Invariants

- 纯减法;删除后 schema DSL 不再接受 `description=`(member)/`Meta.description`(breaking,但 0 消费/0 测试/0 example,pre-release 可接受)。
- **digest 影响**:description 当前在 identity digest 内;删除后含 description 的 schema digest 会变 —— 但 tests/examples 无 description-bearing schema,预期 **0 digest 测试破坏**(acceptance 兜底)。
- 不引入新 surface;INV-6;单线性栈(S1 之上,S2 之前)。
- 精确 stage(81 项无关 dirty 在树)。

## 5. Acceptance(generic cleanup gates)

- [ ] schema `description` 在 sdk/authoring/compile/IR/runtime(`PredicateInfo`)全部移除;`.description`(schema 侧)残留 grep = 0
- [ ] `Field(description=...)` / `Identity(description=...)` / `Meta.description` 现在被拒(unknown kwarg / unknown Meta key)
- [ ] `pattern=` 行为不变;`Rule/Inference.description` 不受影响
- [ ] 全量 schema cohort(sdk schema / authoring parse / compile / runtime / digest)green;无 pinned-digest 测试因此破坏
- [ ] schema DSL docs 移除 description 描述

## 6. Implementation Plan

1. `sdk/schema.py`:移除 `_DataMember` description 参数/存储/emit;`Identity`/`Field` 不再接受 description;`Entity.Meta` 不再接受 description。
2. `authoring/schema_dsl_parse.py`:member allow-list 去 `description`(留 `pattern`);Meta allow-list 去 `description`(留 `version`/`tags`);移除 description 解析。
3. `schema_compile.py`:移除 description 编译/存储(`_compile_optional_description` / `_copy_description_pattern_enum` description 分支 / entity description)。
4. `schema_ir.py`:移除 description 校验(如有)。
5. `schema_runtime.py`:移除 `PredicateInfo.description` + 填充。
6. docs + 测试回归;Step 4.7/4.8。

## 7. Outcome / Deviations

**落地**:impl `f4300425`(线性栈 `… → fcd10b16(cleanup蓝图) → f4300425(cleanup code)`);master 未动,未 push。

**结果**:schema entity/field/Meta `description` 从 sdk/authoring/compile/IR/runtime 全部移除;`PredicateInfo.description` 删除。`pattern=`(18)/`repr`(29,S1 成果)/`Rule/Inference.description`(独立)全部保留。两路新增拒绝测试 `test_schema_description_metadata_is_not_accepted`。docs(quickstart/authoring/core 契约/sdk api)同步。Codex 顺手同步了 S2 蓝图的 stale hook(`_copy_pattern_enum` / `version,tags` / digest 回归项)。

**Gate(我独立验证)**:5 个 schema 逻辑文件 description 残留 **0**;保留项未误删;两路拒绝测试存在;schema cohort **55 tests OK**(独立,含 digest 敏感区,无 pinned-digest 破坏)。Codex 报 focused 61 / broader 133(skip 9)OK。

**归档**:暂留 active/,随里程碑批量归档。
