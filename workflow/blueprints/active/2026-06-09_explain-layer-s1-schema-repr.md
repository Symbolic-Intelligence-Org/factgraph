# Task Blueprint: S1 — Schema DSL repr (Field/Identity/Meta) surface + validation

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/sdk/schema.py`(runtime DSL:`_DataMember`/`Identity`/`Field`/Meta)
  - `src/factgraph/authoring/schema_dsl_parse.py`(AST authoring 解析)
  - `src/factgraph/core/schema/schema_repr.py`(**新建** 共享校验 helper)
- Related Docs:
  - Design spec §5.2(占位符已锁): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s1-schema-repr.audit.md](./2026-06-09_explain-layer-s1-schema-repr.audit.md)

---

## 1. Problem

design §5.2:为 entity 字段/标签声明自然语言 repr 模板(`Field(repr=)`/`Identity(repr=)`/`Meta.repr`),供 S2 `render_entity_repr` + S4 prober 烘焙消费。S1 只做 **DSL surface + 校验**,不进 IR。

## 2. Goals

1. 两条 DSL 路径接受 `repr=`:`sdk/schema.py`(`Field`/`Identity` kwarg + Meta)+ `authoring/schema_dsl_parse.py`(同)。
2. **共享**校验 helper(新建 `core/schema/schema_repr.py`),两路复用,不各写一份(Codex point 1)。
3. 占位符按 design §5.2 **已锁矩阵**(见 §5)在定义/解析时校验。
4. **repr 不进 compiled SchemaIR → schema_digest 不变**(Codex point 2)。

## 3. Non-goals

- `render_entity_repr` 纯函数(S2)。
- 默认 label fallback 文本生成(S2 职责;S1 仅校验 explicit template — Codex point 5)。
- repr 进入 SchemaIR / canonical / digest(S2)。
- 两遍渲染 / prober 烘焙(S3/S4)。

## 4. Current Context(preflight 已完成,实读两路 + digest)

- **sdk 路径**:`_DataMember.__init__(*, description, pattern)`(schema.py:62)存 `self.description/self.pattern`;`_add_common_authoring`(:76)把它们写进 `to_authoring()` 的 `out` dict → compile。`Identity`(:85)/`Field`(:126)各自 `**legacy_kwargs` 拒绝表(:107/:149 "only accepts description= and pattern= in Form I")。
- **authoring 路径**:`_build_identity_from_kwargs`/`_build_field_from_kwargs` allow-list `{description, pattern}`(:194/:222);`_apply_common_member_kwargs` 灌 `out`。Meta:`_apply_entity_meta_fields` allow-list `{version, description, tags}`(:134)。
- **digest 边界(决定性)**:`schema_digest` = `canonicalize_schema_ir_identity_jcs`(schema_ir.py:96-98),仅排除部分 **top-level** key;entity/field 级 `description` 嵌套其中 → **在 digest 内**。故 `repr` 若入 IR 同路即改 digest。**S1 必须让 repr 完全不入 compiled IR**(不经 `_add_common_authoring`/`_apply_common_member_kwargs` 的 IR 发射路径)。
- **Form-I**:现有显式拒绝非 `{description,pattern}`(member)/`{version,description,tags}`(Meta)kwarg;S1 精确扩 allow-list 加 `repr`,其余仍拒。

## 5. Proposed Shape

### 占位符矩阵(design §5.2 已锁 — 非蓝图待决,纠正 Codex point 4)

| 占位符 | `Field.repr` / `Identity.repr` | `Meta.repr` |
|---|---|---|
| `%CLS`(类名) | ✓ | ✓ |
| `%ENT`(实体 label) | ✓ | **✗ 禁用(循环)** |
| `%FLD`(**当前**字段值) | ✓ **仅当前字段,禁引他字段** | ✗ |
| `%<field_name>`(identity 字段值) | **✗** | ✓ **仅 identity 字段** |

定义/解析时报错:unknown placeholder;`%ENT` 出现在 Meta.repr;`%FLD` 出现在 Meta.repr 或引用非当前字段;`%<field>` 出现在 member.repr;Meta.repr 的 `%<field>` 引用非-identity 字段;保留词撞字段名。

### 共享 helper(`core/schema/schema_repr.py`,Codex point 1)

```
validate_member_repr_template(template, *, field_name) -> None   # allowed {%CLS,%ENT,%FLD}
validate_meta_repr_template(template, *, identity_field_names) -> None  # allowed {%CLS, %<id_field>}
```
(或单一 `validate_schema_repr_template(template, *, allowed_placeholders, field_context=...)`;Codex 定形态,但**两路必须复用同一个**。)

### surface-only

- sdk:`_DataMember` 接 `repr=` → `self.repr`,**不**加入 `_add_common_authoring`/`to_authoring` 的 `out`;`Identity`/`Field` allow `repr` kwarg。Meta repr 在 sdk 类处理处接收+校验。
- authoring:member allow-list +`repr`、Meta allow-list +`repr`;校验后**不**写入 compile→IR 的 `out`(或写入中间 DTO 但 compile 不拷进 IR)。**净效果:repr ∉ compiled SchemaIR**。

## 6. Boundaries And Invariants

- **INV-digest-stable**:同一 schema 加/不加 `repr`,`schema_digest` 必须相等。repr 不入 compiled SchemaIR。
- 两路共享同一校验 helper(无重复实现)。
- Form-I:仅新增 `repr` 到 allow-list,其余未知 kwarg 仍拒;`description=`/`pattern=` 行为不变。
- 占位符矩阵严格按 design §5.2,不放宽(尤其 member 无 `%<field>` sibling、Meta 无 `%ENT`/`%FLD`)。
- INV-baseline-monorepo;单线性栈(S0 之上叠加)。

## 7. Acceptance

- [ ] sdk `Field(repr=)`/`Identity(repr=)`/Meta `repr` 接受 + 校验(runtime DSL tests)
- [ ] authoring parse 接受 `repr=`(member + Meta)+ 校验(AST parser tests)
- [ ] 两路调用**同一** `schema_repr` helper(无重复校验逻辑)
- [ ] 占位符矩阵红/绿:member 接受 %CLS/%ENT/%FLD、拒 %<field>;Meta 接受 %CLS/%<id_field>、拒 %ENT/%FLD;unknown placeholder 拒;Meta %<field> 非 identity 拒
- [ ] **digest no-change test**:同 schema with/without `repr` → `schema_digest` 相等;`repr` 不出现在 compiled SchemaIR
- [ ] Form-I:unknown kwarg 仍拒;`description=` 既有行为不变
- [ ] 受影响 docs(schema DSL)同步(由实现侧 src docs 一并处理)

## 8. Implementation Plan

1. 新建 `core/schema/schema_repr.py`:占位符校验 helper(member / meta 两 context,按 §5 矩阵)。
2. `sdk/schema.py`:`_DataMember` 接 `repr=`(存 `self.repr`,**不**入 authoring out);`Identity`/`Field` allow `repr`;Meta repr 接收+校验。
3. `authoring/schema_dsl_parse.py`:member allow-list +`repr`、Meta allow-list +`repr`;调 helper 校验;**不**入 compile→IR out。
4. 验证 `repr` ∉ compiled SchemaIR + digest 不变。
5. 测试矩阵(Codex point 6)+ Step 4.7/4.8 报告。

## 9. Docs To Update

- `src/factgraph/core/schema/docs/README.md`(repr DSL — v1 deferred,S1 补;由 src 侧一并处理)。

## 10. Outcome / Deviations

**落地**:impl `e6ff7940`(单线性栈 `… → 04aa2293(S1 蓝图) → e6ff7940(S1 code)`);master 未动,未 push。

**结果**:新建共享 helper `core/schema/schema_repr.py`(`validate_member_repr_template` / `validate_meta_repr_template`),`sdk/schema.py` + `authoring/schema_dsl_parse.py` **两路复用同一 helper**。占位符矩阵按 design §5.2 锁定执行。`repr` 不入 compiled IR。

**Gate(我独立验证)**:
- repr 在 `schema_compile.py`/`schema_ir.py`/`sdk/compile.py` **0 路径**(不入 IR)。
- `test_schema_repr_does_not_change_schema_digest_or_compiled_ir` 真测试(编译有/无 repr 两 schema 比 `schema_digest`)通过 → **INV-digest-stable 满足**。
- 占位符矩阵实现正确:member 拒 `%<field>`(:28 仅 CLS/ENT/FLD);Meta 拒 `%ENT/%FLD`(:52)+ 非 identity `%<field>`(:54)。
- cohort 33 tests OK(worktree 独立重跑);Codex 报 59 OK(更广 cohort);scope 10 文件全属 S1,无无关混入。

**良性偏差**:Codex 额外把 Relationship `Field(repr=)` 纳入同一 member 校验,防旁路(蓝图未列,正向)。

**归档**:暂留 active/,随里程碑批量归档。
