# Task Blueprint: S4 — repr_text baking in prober assembly (G6)

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/explain/prober.py`(烘焙 repr_text + 接通 schema_index)
  - `src/factgraph/application/schema_runtime.py`(消费 `render_entity_repr` + `PredicateInfo.repr`)
- Related Docs:
  - Design spec §5.1(两类措辞来源)/§5.4(烘焙时机)/§5.7(默认表): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s4-repr-baking.audit.md](./2026-06-09_explain-layer-s4-repr-baking.audit.md)

---

## 1. Problem

S3 prober 产出结构 + 三态,但 `EvidenceAtom.repr_text=None`、`schema_index` 被 `del`(prober.py:52)。S4 = **G6**:prober assembly 实际**调用 `render_entity_repr`**(S2)+ Field.repr 模板 + §5.7 默认表,把每个 atom 烘焙成自然语言 `repr_text`。这是 repr 全链路真正接通的一步。

## 2. Goals

1. prober `probe_native` 接收并使用 `schema_index`(停止 `del`)。
2. atom 烘焙(design §5.1 边界):
   - **Fact atom 有对应 schema 字段** → `PredicateInfo.repr`(Field/Identity.repr 模板)+ `%ENT` 经 **`render_entity_repr`** 解析实体 label、`%FLD` 字段值、`%CLS` 类名。
   - **其余(Compare/Builtin/exists/Aggregate/not)** → §5.7 渲染器默认表。
3. **INV-reprtext-fact-always**:S4 后 Fact/Compare/Builtin atom 的 `repr_text` 必非 None(无 schema 模板时走 fallback)。

## 3. Non-goals

- `Explanation.evidence` 接通 / passed+failed 路径(S5)。
- adapters(S6)。
- `narrate()` prose 模式(future)。
- 改 prober 的 G1/G2 结构逻辑(S3 已定;S4 只加烘焙)。
- Aggregate 富渲染(design 留 repr_text=None 可接受;§5.7 给默认或 None)。

## 4. Current Context(preflight 已完成)

- prober:`probe_native(plan, bindings, view_facts, schema_index=None)`(:46)当前 `del schema_index`(:52);`_atom_form`(:251)产 Fact/Compare/Builtin;`EvidenceAtom(..., repr_text 默认 None)`。
- S2 资产:`render_entity_repr(index, entity_type, identity_values)`(schema_runtime.py:258);`PredicateInfo.repr`(:30,member 模板);`EntityTypeInfo.meta_repr`(:47);取 predicate 经 `field_predicates`/`predicates_by_id`。
- design §5.1 边界:有无对应 schema 字段决定 Field.repr vs 默认表;§5.4:烘焙在 prober assembly(schema 恒在场);§5.7 默认表(exists/eq/ne/ge/gt/le/lt/in/not/aggregate/builtin)。
- v1 prober 有 `_bake_repr_text`/`_pred_repr_template`/`_render_field_repr`/`_repr_compare`/`_repr_builtin`/`_fact_fallback_repr`(结构可参考;v1 问题在 G1/G2 非烘焙)——但 v1 **未**经 `render_entity_repr`(S2 当时不存在);S4 必须用 S2 的 `render_entity_repr` 做 `%ENT` 解析。

## 5. Proposed Shape

- `probe_native` 把 `schema_index` 传入 branch/atom 烘焙路径(不再 `del`)。
- 新 `_bake_repr_text(form, schema_index) -> str | None`:
  - `Fact`:查 `schema_index` 的 predicate repr 模板;有 → 用模板替换(`%CLS`=类名;`%ENT`=`render_entity_repr(index, entity_type, identity_values_of_subject)`;`%FLD`=字段值);无模板 → `_fact_fallback_repr`(如 `"pred(v1, v2)"`)。
  - `Compare`/`Builtin`:§5.7 默认表短语(eq/ne/ge/gt/le/lt/in/not/arith)。
  - 其余 → None 或默认。
- atom 构造点(:156/158/159)写入 `repr_text=_bake_repr_text(form, schema_index)`。

## 6. Boundaries And Invariants

- **INV-reprtext-fact-always**:Fact/Compare/Builtin 烘焙后 `repr_text` 非 None。
- 烘焙在 prober assembly(§5.4);`render_entity_repr` 必须被实际调用(G6 的核心:repr 链路接通,非占位)。
- 占位符替换信任 S1 定义时校验(Meta 只 identity 等);S4 渲染不再校验。
- 不改 G1/G2 结构;不改 verdict 逻辑;纯加烘焙。
- schema_index 缺失时(None)→ 全走 fallback 默认表(不崩)。
- INV-6;单线性栈(S3 之上)。

## 7. Acceptance

- [ ] `probe_native` 使用 `schema_index`(不再 `del`);传入烘焙路径
- [ ] **Fact + schema 字段** → repr_text 用 Field.repr 模板;**`render_entity_repr` 被实际调用**解析 `%ENT`(测试断言调用 + 输出含实体 label)
- [ ] **Compare/Builtin** → §5.7 默认表短语(eq/ne/ge/gt/le/lt/in/not 红/绿)
- [ ] **INV-reprtext-fact-always**:Fact/Compare/Builtin repr_text 非 None
- [ ] schema_index=None → fallback 不崩;repr_text 仍非 None(Fact fallback)
- [ ] 不改 G1/G2:S3 的 monotonic + shape 测试仍绿
- [ ] 受影响 docs(explain repr_text 烘焙)同步

## 8. Implementation Plan

1. `prober.py`:`probe_native` 停 `del schema_index`;沿 branch→atom 传 schema_index。
2. `_bake_repr_text(form, schema_index)`:Fact(schema 模板 + `render_entity_repr` for %ENT)/ Compare/Builtin(§5.7 默认表)/ fallback。
3. atom 构造点写 `repr_text`。
4. 测试:Fact schema 措辞(含 render_entity_repr 调用)+ Compare/Builtin 默认表 + INV-reprtext-fact-always + schema=None fallback + G1/G2 回归;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`(repr_text 烘焙 + §5.7 默认表 + render_entity_repr 接通)。

## 10. Outcome / Deviations

**落地**:impl `80d4069d`(线性栈 `… → e3c34728(S4蓝图) → 80d4069d(S4 code)`);master 未动,未 push。

**结果**:
- `probe_native` 接通 `schema_index`(:52,不再 del),沿 branch→atom 传入。
- `_bake_repr_text`(:284):Fact → `_repr_fact`(schema 模板 + `%ENT` 经 `_entity_repr_for_fact`→`render_entity_repr`,:319/327)、无 schema → `_fact_fallback_repr`;Compare → `_repr_compare`(§5.7);Builtin → `_repr_builtin`。
- atom 构造写 `repr_text`(:163/169/171)。

**Gate(我独立验证)**:
- ★**G6 link 实证**:`_entity_repr_for_fact`(:319/327)真调 `render_entity_repr`;spy 测试(test_prober.py:110-125)替换并断言被调用。repr 链路真正接通。
- fallback 齐全(schema-less Fact + Compare/Builtin);INV-reprtext-fact-always。
- **G1/G2 回归安全**:diff 仅加 `repr_text=`,prober 核心(candidate_envs/deduped/三态/结构)未动;S3 monotonic+shape 测试同 cohort 仍绿。
- cohort 20 OK(独立)/ Codex 58 OK。

**Deviations(良性)**:`_repr_compare`/`_repr_builtin` 复用 v1 形态 + 接 render_entity_repr(G6 增量);entity-ref term → identity bundle 解析 %ENT,标量 term 退化 fallback。

**归档**:暂留 active/,随里程碑批量归档。
