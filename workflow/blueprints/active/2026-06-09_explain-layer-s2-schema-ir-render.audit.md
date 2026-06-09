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

## D. Gate result / Deviations

impl + gate 后填写。
