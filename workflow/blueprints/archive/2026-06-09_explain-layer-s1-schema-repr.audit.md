# Audit Log: S1 — Schema DSL repr

Paired with [2026-06-09_explain-layer-s1-schema-repr.md](./2026-06-09_explain-layer-s1-schema-repr.md).

---

## A. Preflight (2026-06-09, 实读两路 + digest 链)

- sdk DSL:`_DataMember.__init__(description, pattern)`(schema.py:62);`_add_common_authoring`(:76)发射进 `to_authoring` out;Form-I 拒绝表 :107/:149。
- authoring:member allow-list `{description,pattern}`(:194/:222);Meta allow-list `{version,description,tags}`(:134);`_apply_common_member_kwargs` 发射。
- digest:`schema_digest` → `canonicalize_schema_ir_identity_jcs`(schema_ir.py:96-98),仅排除部分 top-level key;entity/field 级嵌套 `description` 在 digest 内 → **repr 入 IR 必改 digest**。

## B. Codex S1 预判评估(2026-06-09)

| Codex point | 裁决 |
|---|---|
| 1 共享校验 helper(不双写) | ✅ 采纳 → 新建 `core/schema/schema_repr.py` |
| 2 S1 不进 IR / digest 不变 | ✅ 采纳,且 preflight **坐实必要性**(嵌套 description 在 digest 内) |
| 3 Form-I allow-list 精确扩展 | ✅ 采纳 → acceptance |
| 4 占位符 scope | ⚠️ **纠正**(见 C) |
| 5 默认 label 是 S2 | ✅ 采纳 |
| 6 测试矩阵 | ✅ 采纳 + digest no-change |
| 边界框定(no IR/canonical/digest) | ✅ 采纳为 INV-digest-stable |

## C. 纠正 Codex point 4(权威 = design §5.2 已锁,非蓝图待决)

Codex 占位符建议有两处与 design §5.2 冲突,已按权威矩阵锁进子蓝图 §5:

1. **member.repr 不允许 `%<field>`(sibling)**:design §5.2 `%FLD` = "仅当前字段,禁引他字段";`%<field_name>` 是 **Meta-only**。Codex 误给 Field/Identity 加 `%<field>` sibling 引用 → 删除。
2. **Meta.repr 不允许 `%ENT`**:design §5.2 明列 `%ENT` "Meta.repr 禁用(循环)"。Codex 误允许 Meta 用 `%ENT` → 删除。
3. Codex "Meta 是否允许 %FLD 要蓝图锁,倾向不允许":design **已锁** Meta 不含 `%FLD`(结论对,但非待决)。

锁定矩阵:member.repr = {`%CLS`,`%ENT`,`%FLD`(当前字段)};Meta.repr = {`%CLS`,`%<id_field>`(仅 identity)}。

(用户补正:`%FLD` 正是"给某 field/identity 写 repr 时的当前字段值",与 design 一致。)

## D. Open items(impl 时)

- helper 形态(两个具名函数 vs 单一带 context 参数)由 Codex 定,**但两路必须复用同一个**。
- Meta.repr `%<field>` 校验需 identity-field 集;确认 sdk 路径与 authoring 路径在校验时点都能取到 identity 字段名(类定义/解析序)。
- 确认 repr 不被 `to_authoring`/`_apply_common_member_kwargs` 顺带发射进 compile→IR(digest no-change test 兜底)。

## E. Gate result (Claude 独立验证 2026-06-09)

impl `e6ff7940`(parent = S1 蓝图 `04aa2293`,线性栈)。**PASS**:
- scope:10 文件全属 S1(helper / sdk / authoring / 2 tests / 4 docs),无 memory/无关混入。
- ★INV-digest-stable:`repr` 在 schema_compile/schema_ir/sdk/compile **0 路径**;`test_schema_repr_does_not_change_schema_digest_or_compiled_ir` 通过(编译有/无 repr 比 digest 相等)。
- 共享 helper:`schema_repr.py` 新增;sdk + authoring 两路均 import 同一 helper。
- 占位符矩阵(实读 schema_repr.py):member 仅 {CLS,ENT,FLD} 拒 %<field>(:28);Meta 拒 %ENT/%FLD(:52)+ 非 identity %<field>(:54);reserved 撞名(:71)+ malformed %(:63)拒。**与纠正后 §5.2 矩阵一致**。
- cohort:33 OK(独立)/ Codex 59 OK。

## F. Deviations(良性)

- Codex 额外覆盖 Relationship `Field(repr=)` 同一校验(防旁路)。
