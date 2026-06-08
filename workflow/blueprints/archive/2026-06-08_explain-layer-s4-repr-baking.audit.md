# Audit Log: Explain Layer S4 — repr_text 烘焙 + 渲染器默认表

- Blueprint: [`2026-06-08_explain-layer-s4-repr-baking.md`](./2026-06-08_explain-layer-s4-repr-baking.md)
- Created: 2026-06-08
- Status: implemented

---

## Preflight Source-Read（2026-06-08）

**文件 / commit 读取清单**

| 文件 | 谱系 commit | 核心发现 |
|---|---|---|
| `evidence_tree.py` | S3 impl `69593d36` | `EvidenceAtom.repr_text: str \| None = None` 已就绪 |
| `prober.py` | S3 impl `69593d36` | `del schema_index` — 参数接收但立即丢弃；三处 `EvidenceAtom(...)` 均无 `repr_text` 传入 |
| `schema_runtime.PredicateInfo` | S3 lineage（master 基线） | 无 `repr` 字段；`render_entity_repr` 不存在 |
| `schema_runtime.PredicateInfo` | S2 impl `f13841b1` | `repr: str \| None = None` 存在；`render_entity_repr` @ line 396 存在 |
| `design §5.7` | design doc | 默认表：Compare/Builtin 无 schema 依赖；Fact 用 `Field.repr` 模板 |

**关键约束**：S3 impl 谱系（master-based）缺少 S2 的 `PredicateInfo.repr` + `render_entity_repr`。S4 cherry-pick 或仅实现默认表两路均可行，决定权交 Codex（Q-S4-A）。

---

## Events

- **2026-06-08 scope-freeze**: Blueprint rev2 — Q-S4-A 决策修订：Option B（仅保底，不引入 S2 repr 增量）为推荐。新增 `_fact_fallback_repr` 保底路径（`BoundVar.value`）；`INV-reprtext-fact-always` 确立。Status → `scoped`。
- **2026-06-08 implemented**: Impl `83be07b9` chose Option B, baked `repr_text` for Fact/Compare/Builtin atoms, added `application/explain/docs/README.md`, and passed focused tests/compileall/import/diff checks.

---

## Deviations

- D-1: Option B chosen; no S2 repr cherry-pick. Schema-template rendering deferred until lineage merge, but Fact fallback/default renderer guarantees non-`None` text for generated Fact/Compare/Builtin atoms.
- D-2: `Fact + NotReached` does not occur in current prober semantics because `pred` atoms are binders. NotReached fallback was verified through missing-dependency `Compare` atoms without changing predicate binding behavior.
