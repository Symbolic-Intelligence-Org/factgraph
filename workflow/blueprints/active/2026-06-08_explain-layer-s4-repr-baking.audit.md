# Audit Log: Explain Layer S4 — repr_text 烘焙 + 渲染器默认表

- Blueprint: [`2026-06-08_explain-layer-s4-repr-baking.md`](./2026-06-08_explain-layer-s4-repr-baking.md)
- Created: 2026-06-08
- Status: draft

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

*(实施阶段填入)*

---

## Deviations

*(实施阶段填入)*
