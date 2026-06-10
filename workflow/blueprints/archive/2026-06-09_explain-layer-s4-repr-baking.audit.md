# Audit Log: S4 — repr_text baking (G6)

Paired with [2026-06-09_explain-layer-s4-repr-baking.md](./2026-06-09_explain-layer-s4-repr-baking.md).

---

## A. Preflight (2026-06-09)

- prober `probe_native`(:46)当前 `del schema_index`(:52);`_atom_form`(:251)产 Fact/Compare/Builtin;`EvidenceAtom.repr_text` 默认 None。
- S2 资产:`render_entity_repr(index, entity_type, identity_values)`(schema_runtime.py:258);`PredicateInfo.repr`(:30);取 predicate 经 `field_predicates`/`predicates_by_id`。
- design:§5.1 边界(有 schema 字段 → Field.repr,余 → 默认表);§5.4 烘焙在 prober assembly;§5.7 默认表。
- v1 prober 有 `_bake_repr_text`/`_repr_compare`/`_repr_builtin`/`_fact_fallback_repr`(结构可参考),但 **未经 render_entity_repr**(S2 当时不存在)—— S4 的 G6 核心增量 = 实际调用 `render_entity_repr` 解析 `%ENT`。

## B. Locked decisions

- 烘焙在 prober assembly(§5.4);Fact 有 schema → Field.repr 模板 + `render_entity_repr`(%ENT);余 → §5.7 默认表。
- INV-reprtext-fact-always:Fact/Compare/Builtin 烘焙后非 None。
- schema_index=None → fallback 不崩。
- 不改 G1/G2(S3 测试须仍绿)。

## C. Open items for Codex

- Fact 的 `%ENT` 需要 subject 实体的 identity_values 来调 `render_entity_repr` —— 从 atom 的 BoundVar.value / entity-ref term 取;确认 entity-ref term 能解析出 entity_type + identity bundle(若 Fact 的 term 是标量非 entity-ref,`%ENT` 退化处理你定)。
- Aggregate repr_text:§5.7 给默认 or None,你定(非阻塞)。
- `_bake_repr_text` 是否可复用 v1 prober 的 `_repr_compare`/`_repr_builtin` 形态(结构 OK,补 render_entity_repr)。

## D. Gate result (Claude 独立验证 2026-06-09)

impl `80d4069d`(parent = S4 蓝图 `e3c34728`,线性栈)。**PASS**:
- scope:3 文件(prober + test + docs);无无关混入。
- ★G6:`_entity_repr_for_fact`(prober.py:319/327)真调 `render_entity_repr`;spy 测试(test:110-125)断言被调用。
- fallback:`_fact_fallback_repr`/`_repr_compare`/`_repr_builtin`;INV-reprtext-fact-always。
- ★G1/G2 回归:`_probe_atom` diff 仅加 `repr_text=`,核心未动;S3 monotonic+shape 同 cohort 仍绿。
- cohort 20 OK(独立)/ Codex 58。

裁决:**PASS**。

## E. Deviations(良性)

- 复用 v1 `_repr_compare`/`_repr_builtin` 形态 + G6 接 render_entity_repr。
- entity-ref term 解析 %ENT(标量 term 退化 fallback)。
