# Audit Log: S2 — Schema IR repr + render_entity_repr

Paired with [2026-06-09_explain-layer-s2-schema-ir-render.md](./2026-06-09_explain-layer-s2-schema-ir-render.md).

---

## A. Preflight (2026-06-09)

- digest:`SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS = {"generated_at"}`(schema_ir.py:31);嵌套 `description` 在 digest 内 → repr 入 IR 默认改 digest。
- render target:`schema_runtime.py` `IdentityFieldInfo`/`PredicateInfo`(含 description/pattern)/`EntityTypeInfo`/`SchemaIndex`。
- compile 存储 hook:`entity_out`(schema_compile.py:113-135)+ `_copy_description_pattern_enum`(:439)。
- S1 现状:repr 校验在 `schema_repr.py`(复用),但未发射进 authoring out;S2 需发射。

## B. ★Locked decision — repr 排除出 identity digest(2026-06-09)

**决策:repr 入 IR 但不进 schema identity digest**(`schema_digest` 不随 repr 变)。

- 经过:S2 preflight 发现 digest 仅排除 generated_at,repr 入 IR 默认会 churn digest。`<user>` 未答 AskUserQuestion;按 planner 职责裁定。
- 理由:repr 是纯呈现模板,编辑不应使 schema identity 失效(cache / view-snapshot / replay)。与 schema-digest-stability 精神一致。延续 S1 的 digest-stable 不变式。
- 边界:`description` 维持现状(进 digest),S2 不动;repr 与 description 的 digest 不一致作为已知张力记录,未来如需统一另立评估(对应 v2 program audit §D 的延伸)。
- **可被 `<user>` 推翻**:若改为 repr 进 digest(随 description 先例),则去掉 §6 排除机制即可。

## C. Open items for Codex S2 preflight

- digest 排除**机制**二选一(不变式已锁,机制开放):(a) 顶层 excluded repr 区(加进 `SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS` + 同步顶层 required/allowed 校验);(b) nested repr + canon 时剥离。建议选对 digest-critical canon 改动最小者。
- `render_entity_repr` 签名最终形态(`(index, entity_type, identity_values)` 提案)+ identity 值缺失时行为(报错 vs 占位)。
- `EntityTypeInfo.meta_repr` / `PredicateInfo.repr` 命名与填充点。

## D. Gate result (Claude 独立验证 2026-06-09)

impl `cd9b62fc`(parent = cleanup 收口 `657e364c`,线性栈)。**PASS**:
- scope:14 文件(5 schema 逻辑 + __init__ 导出 + 3 测试 + 5 docs);无 memory/无关混入。
- ★INV-digest-stable:`_schema_identity_view`(:97-105)递归剥 `repr`+generated_at;`test_schema_repr_enters_compiled_ir_without_changing_schema_digest` 证 `schema_digest(without)==schema_digest(with)`(:61)+ repr 在 full IR(:63)。机制 (b)。
- render_entity_repr:三路测试(默认 label / meta 模板 / 缺值 MISSING_ENTITY_IDENTITY_VALUE)+ 逻辑实读正确(%CLS + %<id_field>,仅 identity 字段替换,S1 已保证有效性)。
- SchemaIndex:`EntityTypeInfo.meta_repr` + `PredicateInfo.repr`。
- cohort 58 OK(独立)/ Codex 136(skip 9)。

裁决:**PASS**。

## E. Open items resolved / Deviations

- digest 机制:Codex 选 (b) nested + canon 递归剥离(对 IR 结构侵入小于 (a) 顶层区),合理。
- render 缺值行为:抛 `MISSING_ENTITY_IDENTITY_VALUE`(子蓝图 open item 已定)。
- 小建议:补"结构变更仍改 digest"专项测试(目前由既有 cohort 间接覆盖)。
