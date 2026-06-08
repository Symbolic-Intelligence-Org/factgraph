# Task Blueprint: Explain Layer S4 — repr_text 烘焙 + 渲染器默认表

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08
- Parent Blueprint: [`2026-06-08_explain-layer.md`](./2026-06-08_explain-layer.md)
- Slice: S4 (depends on S3 ✅, S2 ✅)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` — 主要改动：激活 schema_index + 烘焙逻辑
  - `src/factgraph/application/explain/evidence_tree.py` — 零改动（`repr_text` 字段已就绪）
  - `src/factgraph/application/schema_runtime.py` — 可能引入（见 Q-S4-A）
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
2. 实现**字段谓词 repr 烘焙**：`Fact` atom 当 schema_index 提供且谓词有 `Field.repr` 模板时，渲染并写入 `repr_text`。
3. `probe_native(schema_index=None)` 退化行为：Compare/Builtin 仍可烘焙（默认表）；Fact 无模板时 `repr_text = None`。

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

### 4.3 S3 lineage 缺少 S2 的 repr 字段

S3 impl 基于 `master @ 562c7419`；S2 impl 基于 `feature/v0.2.0-factgraph-publish-2026-06-03`——两个独立谱系。

S3 lineage 中 `schema_runtime.PredicateInfo`：

```python
@dataclass(frozen=True)
class PredicateInfo:
    pred_id: str
    owner_type: str
    py_field_name: str | None
    cardinality: str
    value_type_domain: str | None
    is_entity_exists: bool = False
    is_identity_field: bool = False
    # ← 无 repr: str | None（S2 增量）
```

S2 的 `schema_runtime` 增量（`f13841b1`）：

- `PredicateInfo.repr: str | None = None`
- `EntityTypeInfo.repr: str | None = None`
- `IdentityFieldInfo.repr: str | None = None`
- `def render_entity_repr(entity_type, identity, *, index: SchemaIndex) -> str`

### 4.4 默认表 atoms 无 schema 依赖

§5.7 默认表中 `Compare`（eq/ne/ge/gt/le/lt）、`Builtin`（in/not/add/sub/neg/addc/mulc）的渲染不需要 schema_index，纯粹从 `form.op` + `form.args` 取值即可。

## 5. Proposed Shape

### 5.1 主要改动文件

**`src/factgraph/application/explain/prober.py`**（唯一改动文件）：

1. 删除 `del schema_index`，将其透传给内部 `_bake_repr_text`。
2. 所有 `EvidenceAtom(...)` 构造位置（Holds / Fails / NotReached 三处）统一追加 `repr_text=_bake_repr_text(form, schema_index)`.
3. 新增 `_bake_repr_text(form, schema_index) -> str | None`。
4. 新增默认表 helpers：`_repr_compare`, `_repr_builtin`，覆盖 §5.7 全部 atom 类型。
5. 新增字段谓词 repr helpers（依赖 Q-S4-A 策略，见下）。

### 5.2 `_bake_repr_text` 路由逻辑

```python
def _bake_repr_text(form: AtomForm, schema_index: Any | None) -> str | None:
    if isinstance(form, Compare):
        return _repr_compare(form)
    if isinstance(form, Builtin):
        return _repr_builtin(form)
    if isinstance(form, Fact):
        if schema_index is None:
            return None
        pred_repr = _pred_repr_template(form.predicate, schema_index)
        if pred_repr is None:
            return None
        return _render_field_repr(pred_repr, form, schema_index)
    return None  # Aggregate 等未来类型
```

### 5.3 默认表实现范围（§5.7 对照）

| §5.7 条目 | 实现 |
|---|---|
| `eq` / `ne` | `_repr_compare` — `"{lhs} is {rhs}"` / `"{lhs} is not {rhs}"` |
| `ge` / `gt` / `le` / `lt` | `_repr_compare` — `"at least/more than/at most/less than"` |
| `in` | `_repr_builtin` — `"{x} is one of {set}"` |
| `not(body)` | `_repr_builtin` — `"it is not the case that ..."` |
| `add` / `sub` / `addc` / `mulc` / `neg` | `_repr_builtin` — 简短算术短语 |
| Aggregate | 暂 `None`（Aggregate form 未在 S3 prober 中生成，defer） |

### 5.4 设计问题

#### Q-S4-A（lineage 策略）— Codex 决定

S4 需要 `PredicateInfo.repr` + `render_entity_repr`（S2 增量），但 S3 impl 不含这些。

**Option A：cherry-pick S2 schema_runtime 增量**
- S4 impl 分支 fork 自 S3 impl，cherry-pick S2 的 `schema_runtime.py` diff（三个 `repr` 字段 + `render_entity_repr` 函数）
- S4 可实现完整字段谓词烘焙
- 注意：cherry-pick 时 `schema_runtime.py` 两个谱系改动可能有冲突，需手工合并

**Option B：仅默认表（不 cherry-pick）**
- S4 impl 分支 fork 自 S3 impl，不 cherry-pick S2
- `_pred_repr_template` 始终返回 `None`（`PredicateInfo` 无 `repr` 字段时 fallback）
- `Fact` atom 的 `repr_text = None`；Compare/Builtin 仍可烘焙
- 字段谓词烘焙推迟到 S5/S6（谱系合并后）

**推荐**：Option A，字段谓词烘焙是 S4 的核心价值；Option B 仅交付一半。如果 cherry-pick 冲突过于复杂，改用 Option B 并记录为偏差。

#### Q-S4-B（`_render_field_repr` 模板渲染）— 委托 Codex

`Field.repr` 含 `%ENT / %FLD / %CLS` 占位符（§5.2）：

- `%CLS` → `owner_type`（实体类型名，直接从 `PredicateInfo.owner_type` 取）
- `%ENT` → 主体实体的 Meta.repr label；需调 `render_entity_repr`（Option A 才有）
- `%FLD` → 字段值；若为 entity-ref，递归调 `render_entity_repr`；否则直接 `str(val)`

`terms[0]` 通常是主体变量，`terms[1]` 是值变量。具体如何从 `env.bindings` 取值、`render_entity_repr` 调用签名，Codex 参考 S2 impl `f13841b1` `schema_runtime.py:396-420`。

## 6. Boundaries And Invariants

- **INV-reprtext-nullable**: `repr_text = None` 是合法态（无模板/无 schema 时），不是错误。
- **INV-frozen-at-construction**: `EvidenceAtom` 是 `frozen=True` dataclass；`repr_text` 必须在构造时写入，不可事后 patch。
- **INV-schema-index-optional**: `probe_native(schema_index=None)` 调用仍合法；Compare/Builtin 默认表路径不依赖 schema_index。
- **INV-zero-diff-diagnose**: `diagnose_runtime.py` 零改动（S3 确认 0-diff，S4 继续保持）。
- **INV-no-sdk-import**: `prober.py` 不引入 SDK 层依赖。
- **INV-notreached-repr**: `NotReached` atoms `repr_text` 可以为 `None`（原子尚未执行，无值可渲染）。

## 7. Acceptance

- [ ] `EvidenceAtom(form=Compare(op="eq",...), ...)` 的 `repr_text` 非 `None`（有默认表输出）
- [ ] `EvidenceAtom(form=Builtin(op="in",...), ...)` 的 `repr_text` 非 `None`
- [ ] `probe_native(..., schema_index=None)` 调用不报错；Fact atom `repr_text is None`
- [ ] Option A（cherry-pick）：`probe_native(..., schema_index=<valid index>)` 对有 `repr` 模板的字段谓词 Fact atom 返回 `repr_text` 非 `None`
- [ ] `diagnose_runtime.py` git diff 为 0 行（不改动）
- [ ] `evidence_tree.py` git diff 为 0 行（不改动）
- [ ] 所有既有 S3 prober 测试仍 pass
- [ ] compileall + import sweep pass

## 8. Implementation Plan

1. **[Codex]** 决定 Q-S4-A（Option A cherry-pick or Option B default-only）
2. **[Codex]** fork impl branch 自 S3 impl（`69593d36`），如 Option A 则 cherry-pick S2 schema_runtime diff
3. **[Codex]** 删除 `del schema_index`；在三处 `EvidenceAtom(...)` 追加 `repr_text=_bake_repr_text(form, schema_index)`
4. **[Codex]** 实现 `_repr_compare` / `_repr_builtin` 默认表 helpers
5. **[Codex]** Option A：实现 `_pred_repr_template` + `_render_field_repr`；Option B：`_pred_repr_template` 常返 `None`
6. **[Codex]** 运行测试、compileall、import sweep，验证 acceptance

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md` — 记录 `repr_text` 烘焙机制 + default renderer table
- 父 blueprint `2026-06-08_explain-layer.md` — 标记 S4 已落地

## 10. Outcome / Deviations

任务完成后填写。
