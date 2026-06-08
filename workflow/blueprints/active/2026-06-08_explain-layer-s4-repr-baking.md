# Task Blueprint: Explain Layer S4 — repr_text 烘焙 + 渲染器默认表

- Status: scoped
- Created: 2026-06-08
- Last Updated: 2026-06-08 (rev 2: 加入 Fact fallback 保底机制，scope freeze)
- Parent Blueprint: [`2026-06-08_explain-layer.md`](./2026-06-08_explain-layer.md)
- Slice: S4 (depends on S3 ✅, S2 ✅)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` — **主要改动**：激活 schema_index + `_bake_repr_text` + 保底 + 默认表
  - `src/factgraph/application/explain/evidence_tree.py` — 零改动（`repr_text` 字段已就绪）
  - `src/factgraph/application/schema_runtime.py` — 仅 Option A 时改动（补入 S2 repr 增量）
- Related Docs:
  - [explain-layer-complete-design.zh.md §5](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-08_explain-layer-s4-repr-baking.audit.md](./2026-06-08_explain-layer-s4-repr-baking.audit.md)

---

## 1. Problem

S3 实现了 `EvidenceAtom(form, verdict, atom_id, repr_text=None)`，但 `repr_text` 在 prober assembly 时永远写入 `None`：

```python
# prober.py 当前状态
def probe_native(..., schema_index: Any | None = None) -> EvidenceProbeResult:
    del schema_index  # ← 完全丢弃，未使用
```

结果：所有 `EvidenceAtom.repr_text is None`，atom 无可读自然语言标签。

## 2. Goals

1. 实现**渲染器默认表**（§5.7）：`Compare` / `Builtin` atom 不依赖 schema 就能得到 `repr_text`。
2. 实现 **`Fact` atom 保底机制**：即使没有 `Field.repr` 模板，也自动生成 `"predicate(val1, val2)"` 形式的 repr（`BoundVar.value` / `BoundVar.name` 已在 form 中，无需 schema）。
3. 实现**字段谓词模板渲染**（可选升级）：当 schema_index 提供且谓词有 `Field.repr` 模板时，用模板替代保底文本，得到更自然的措辞。
4. `probe_native(schema_index=None)` 退化行为：`Fact` / `Compare` / `Builtin` atom 均仍有 `repr_text`（保底或默认表），不退化为 `None`。

## 3. Non-Goals

- 零改动 `evidence_tree.py` DTO（`repr_text` 字段已就绪）。
- 不实现 `Rule.repr` conclusion 烘焙（归 S5 负责，S5 在 Explanation walker 层）。
- 不实现 `Explanation.repr_text` walker（归 S5）。
- 不修改 S3 的三态逻辑（Holds / Fails / NotReached）。
- 不修改 `diagnose_runtime.py`（S3 已确认 0-diff）。

## 4. Preflight Source Read — 关键发现（2026-06-08）

### 4.1 `EvidenceAtom.repr_text` 已就绪

`evidence_tree.py`（S3 impl `69593d36`）：

```python
@dataclass(frozen=True)
class EvidenceAtom:
    form: AtomForm
    verdict: Verdict
    atom_id: str
    repr_text: str | None = None  # ← 字段存在，prober 不写入
```

### 4.2 `probe_native` 丢弃 schema_index

```python
def probe_native(plan, bindings, view_facts, schema_index: Any | None = None):
    del schema_index  # ← S4 需要激活此参数
    ...
    atoms.append(EvidenceAtom(form=..., verdict=..., atom_id=...))  # repr_text 未传
```

### 4.3 `BoundVar` 已携带实际绑定值

```python
@dataclass(frozen=True)
class BoundVar:
    name: str        # 原始变量名，含 $ 前缀（如 "$User"）
    value: Any | None  # env.bindings.get(variable) — Holds atom 时为实际值
    bound_by: str | None
```

`_operand` 在构造 `Fact.terms` 时已经从 `env.bindings` 填入 `value`，因此不依赖 schema 就能渲染保底文本：

```python
def _fact_fallback_repr(form: Fact) -> str:
    parts = []
    for t in form.terms:
        if isinstance(t, BoundVar):
            parts.append(str(t.value) if t.value is not None else t.name)
        else:  # Const
            parts.append(str(t.value))
    return f"{form.predicate}({', '.join(parts)})"
# 示例：Fact(predicate="user_country", terms=(BoundVar("$User", "u-1"), BoundVar("$Country", "US")))
# → "user_country(u-1, US)"
```

### 4.4 S3 lineage 无 S2 repr 增量（影响模板路径，不影响保底路径）

S3 impl 基于 `master @ 562c7419`；S2 impl 基于 `feature/v0.2.0-factgraph-publish-2026-06-03`——两个独立谱系，**尚未合并**。

两个谱系分别开发：S3 有 prober，S2 有 schema repr。S4 impl 分支只能选其中一个为起点，另一个的改动在 S4 阶段暂时无法直接 import。

> **注**：这不是 bug 或错误，是 alpha 阶段并行开发的正常状态；所有谱系在 publish 合并时会统一。

S3 lineage 中 `schema_runtime.PredicateInfo` 无 `repr` 字段（S2 才有），因此模板路径需要 S2 的代码。保底路径**无此依赖**。

### 4.5 默认表 atoms 无 schema 依赖

§5.7 默认表中 `Compare`（eq/ne/ge/gt/le/lt）、`Builtin`（in/not/add/sub/neg/addc/mulc）的渲染不需要 schema_index，纯粹从 `form.op` + `form.args` 取值即可。`Fact` 保底路径同样无 schema 依赖（§4.3）。

## 5. Proposed Shape

### 5.1 主要改动文件

**`src/factgraph/application/explain/prober.py`**（唯一改动文件）：

1. 删除 `del schema_index`，将其透传给内部 `_bake_repr_text`。
2. 所有 `EvidenceAtom(...)` 构造位置（Holds / Fails / NotReached 三处）统一追加 `repr_text=_bake_repr_text(form, schema_index)`.
3. 新增 `_bake_repr_text(form, schema_index) -> str | None`。
4. 新增默认表 helpers：`_repr_compare`, `_repr_builtin`，覆盖 §5.7 全部 atom 类型。
5. 新增字段谓词 repr helpers（依赖 Q-S4-A 策略，见下）。

### 5.2 `_bake_repr_text` 路由逻辑（修订版）

```python
def _bake_repr_text(form: AtomForm, schema_index: Any | None) -> str | None:
    if isinstance(form, Compare):
        return _repr_compare(form)          # 默认表，无 schema 依赖
    if isinstance(form, Builtin):
        return _repr_builtin(form)          # 默认表，无 schema 依赖
    if isinstance(form, Fact):
        # 优先：schema 模板路径（需 schema_index + PredicateInfo.repr）
        if schema_index is not None:
            pred_repr = _pred_repr_template(form.predicate, schema_index)
            if pred_repr is not None:
                return _render_field_repr(pred_repr, form, schema_index)
        # 保底：raw predicate + term 值，始终可产出
        return _fact_fallback_repr(form)
    return None  # Aggregate 等未来 form 类型（S3 prober 暂未生成）
```

关键变化：`Fact` atom 从"无模板则 `None`"改为"无模板则保底"，`repr_text` 对 Fact/Compare/Builtin 始终非 `None`。

### 5.3 默认表 + 保底实现范围

| Atom 类型 | 实现策略 |
|---|---|
| `Compare` `eq` / `ne` | `_repr_compare` — `"{lhs} is {rhs}"` / `"{lhs} is not {rhs}"` |
| `Compare` `ge` / `gt` / `le` / `lt` | `_repr_compare` — `"at least/more than/at most/less than"` |
| `Builtin` `in` | `_repr_builtin` — `"{x} is one of {set}"` |
| `Builtin` `not(body)` | `_repr_builtin` — `"it is not the case that ..."` |
| `Builtin` `add/sub/addc/mulc/neg` | `_repr_builtin` — 简短算术短语 |
| `Fact`（有 `Field.repr` 模板） | `_render_field_repr` — 模板渲染（需 schema_index，见 Q-S4-A） |
| `Fact`（无模板 / 无 schema） | `_fact_fallback_repr` — `"predicate(val1, val2)"` — **始终有值** |
| `Aggregate` | `None`（S3 prober 未生成此 form，defer） |

### 5.4 设计问题

#### Q-S4-A（S2 repr 增量引入策略）— 委托 Codex

`_fact_fallback_repr` 保底路径**无需 S2 代码**（只用 `form.predicate` + `BoundVar.value`）。

模板路径（`_render_field_repr`）需要 S2 新增的 `PredicateInfo.repr` + `render_entity_repr`。S3 lineage 的 `schema_runtime.py` 没有这两项。

**Option A：在 S4 impl 分支手动补入 S2 的 repr 增量**
- S4 impl 分支 fork 自 S3 impl（`69593d36`）
- 手动将 S2 在 `schema_runtime.py` 添加的三个 `repr` 字段 + `render_entity_repr` 函数复制进来（约 80 行）
- 注意：S2 的 `schema_runtime.py` 在 `feature/` 谱系上，手动复制可能有少量上下文偏差，需核对
- S4 全量交付：保底 + 模板两路均工作

**Option B：仅保底路径（不引入 S2 repr 增量）**
- S4 impl 分支 fork 自 S3 impl，`schema_runtime.py` 不改动
- `_pred_repr_template` 始终返回 `None`（`PredicateInfo` 无 `repr` 字段）
- Fact atom 走保底路径，`repr_text = "predicate(val1, val2)"`
- 模板路径在谱系合并后自然激活，不需要额外 slice

**推荐**：Option B，理由：
1. 保底路径已满足用户要求（始终有值）
2. 避免手动复制跨谱系代码引入不一致风险
3. 模板路径在谱系合并时自动激活，无需再次 impl slice

如 Codex 评估 Option A 冲突少、成本低，可选 A 并记录为偏差。

#### Q-S4-B（`_render_field_repr` 模板渲染）— 委托 Codex（仅 Option A 时需要）

`Field.repr` 含 `%ENT / %FLD / %CLS` 占位符（§5.2）：

- `%CLS` → `PredicateInfo.owner_type`（直接取）
- `%ENT` → 主体实体的 Meta.repr label；调 `render_entity_repr(entity_type, identity, index=schema_index)`
- `%FLD` → `terms[1]` 的值；entity-ref 递归调 `render_entity_repr`，标量 `str(val)`

Codex 参考 S2 impl `f13841b1:src/factgraph/application/schema_runtime.py:396-420`。

## 6. Boundaries And Invariants

- **INV-reprtext-fact-always**: S4 后，`Fact` / `Compare` / `Builtin` atom 的 `repr_text` 始终非 `None`（保底路径兜底）。
- **INV-reprtext-aggregate-nullable**: `Aggregate` atom `repr_text` 可为 `None`（S3 prober 未生成该 form，defer）。
- **INV-notreached-repr**: `NotReached` atom 的保底路径仍可产出 `repr_text`（`BoundVar.name` 退化为变量名字符串）。
- **INV-frozen-at-construction**: `EvidenceAtom` 是 `frozen=True` dataclass；`repr_text` 必须在构造时写入，不可事后 patch。
- **INV-schema-index-optional**: `probe_native(schema_index=None)` 调用仍合法；退化到保底路径，不报错。
- **INV-zero-diff-diagnose**: `diagnose_runtime.py` 零改动（S3 确认 0-diff，S4 继续保持）。
- **INV-no-sdk-import**: `prober.py` 不引入 SDK 层依赖。

## 7. Acceptance

- [ ] `EvidenceAtom(form=Compare(op="eq",...), ...)` 的 `repr_text` 非 `None`（默认表）
- [ ] `EvidenceAtom(form=Builtin(op="in",...), ...)` 的 `repr_text` 非 `None`（默认表）
- [ ] `EvidenceAtom(form=Fact(...), verdict=Holds(...), ...)` 的 `repr_text` 非 `None`（保底路径：`"predicate(val1, val2)"`）
- [ ] `probe_native(..., schema_index=None)` 调用不报错；`Fact` atom `repr_text` 为保底文本（非 `None`）
- [ ] `EvidenceAtom(form=Fact(...), verdict=NotReached(...), ...)` 的 `repr_text` 为变量名保底形式（`"predicate($Var1, $Var2)"`）
- [ ] Option A 额外验证：对有 `Field.repr` 模板的谓词，`repr_text` 为模板渲染结果（非保底）
- [ ] `diagnose_runtime.py` git diff 为 0 行
- [ ] `evidence_tree.py` git diff 为 0 行
- [ ] 所有既有 S3 prober 测试仍 pass
- [ ] compileall + import sweep pass

## 8. Implementation Plan

1. **[Codex]** fork impl branch 自 S3 impl（`69593d36`）命名 `v0.2.0-impl-repr-baking-2026-06-08`
2. **[Codex]** 决定 Q-S4-A（Option B 推荐；Option A 若成本低亦可）
3. **[Codex]** 删除 `del schema_index`；在三处 `EvidenceAtom(...)` 追加 `repr_text=_bake_repr_text(form, schema_index)`
4. **[Codex]** 实现 `_fact_fallback_repr(form) -> str`（`BoundVar.value` 优先，`BoundVar.name` fallback）
5. **[Codex]** 实现 `_repr_compare` / `_repr_builtin` 默认表 helpers（§5.7）
6. **[Codex]** Option A 额外：手动补入 S2 `schema_runtime.py` repr 增量（`PredicateInfo.repr` + `render_entity_repr`）；实现 `_pred_repr_template` + `_render_field_repr`
7. **[Codex]** 运行测试、compileall、import sweep，验证 acceptance；记录偏差

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md` — 记录 `repr_text` 烘焙机制 + default renderer table
- 父 blueprint `2026-06-08_explain-layer.md` — 标记 S4 已落地

## 10. Outcome / Deviations

任务完成后填写。
