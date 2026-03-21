# Task Blueprint: certainty-salience-ranking-v1

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/core/annotation/_certainty.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py`
- Related Docs:
  - [2026-03-20_candidate-evidence-tree-salience-impact.md](../archive/2026-03-20_candidate-evidence-tree-salience-impact.md)（前置 decision freeze）
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
- Audit Log:
  - [2026-03-21_certainty-salience-ranking-v1.audit.md](./2026-03-21_certainty-salience-ranking-v1.audit.md)

## 1. Problem

`CertaintySummary.conditions` 已提供 per-condition `weight` / `impact` breakdown，`aggregate_certainty` 是 bottleneck（min weighted impact）。但当前 narrative / NL 只按插入序逐行列出 conditions，没有：

- 排序（消费者无法一眼看到最薄弱条件）
- 显式 bottleneck 标注（aggregate_certainty 是一个数字，没有回指是哪个 condition）
- NL 里没有"最薄弱条件是 X"的自然语言句子

上一轮 `candidate-evidence-tree-salience-impact` blueprint 冻结了 4 条结论：

1. salience 属于 annotation / value-semantics 层
2. query-time / read-time 计算
3. blocked on certainty / weight vocabulary → **现已解除**
4. first-round 不产出 implementation slice → **本 blueprint 是解除 blocker 后的第一个 implementation slice**

## 2. Goals

- 在 annotation 层新增 ranked conditions derived helper：按 impact 升序排序 + 显式标出 bottleneck condition
- narrative `certainty_lines` 消费 ranked view，把 conditions 按 impact 升序展示，bottleneck condition 附加 `[bottleneck]` 标注
- NL certainty paragraph 增加一句 weakest-condition 描述
- audit / static 通过复用 narrative 自然继承排序，不单独扩 contract

## 3. Non-goals

- 不开新 endpoint
- 不开独立 public DTO / salience surface
- 不做 top-K 聚焦
- 不做 probability lane
- 不做 scoring / percentile / distribution
- 不改 `CertaintySummary` dataclass 结构（ranking 是 derived view，不是 carrier 扩展）
- 不改 `certainty_summary` 的序列化 shape（JSON output 中 conditions 顺序不保证；ranking 只体现在 narrative/NL）

## 4. Current Context

- 当前实现入口：
  - `_build_certainty_lines(certainty_summary_dict)` 在 `_candidate_evidence_tree_narrative.py` line 134
  - 当前按 `conditions` list 的插入序逐行输出，无排序
  - NL 在 `_candidate_evidence_tree_nl.py` line 57 把 `certainty_lines` join 成一段，无 bottleneck 句
- 当前已知约束：
  - `conditions` 中可能有 unweighted 项（`weight=None, impact=None`）——排序时放在末尾
  - bottleneck = `aggregate_certainty` = `min(weighted impacts)`，但当前没有回指是哪个 condition
  - 多个 conditions 可能 share 同一 min impact（tie）——全部标注 `[bottleneck]`
- 当前相关历史蓝图：
  - `candidate-evidence-tree-salience-impact`（decision freeze，现已归档）
  - `certainty-aware-narrative-nl-delivery`（narrative/NL certainty 接入）
  - `certainty-runtime-boundary-cleanup`（helper 分层）

## 5. Proposed Shape

### 5.1 Annotation layer: `rank_certainty_conditions`

在 `src/factpy_kernel/core/annotation/_certainty.py` 新增 pure function：

```python
def rank_certainty_conditions(
    conditions: Sequence[ConditionImpact],
    aggregate_certainty: float | None,
) -> list[RankedCondition]:
```

输入：`CertaintySummary.conditions` + `aggregate_certainty`。

输出：`list[RankedCondition]`，其中：

```python
@dataclass(frozen=True)
class RankedCondition:
    atom_key: str
    node_kind: str
    weight: float | None
    impact: float | None
    is_bottleneck: bool    # True when impact == aggregate_certainty
```

注意：不含 `rank` 字段。第一轮没有 consumer 消费显式 rank 编号，排序结果通过 list 位置隐含表达即可。若未来需要展示 "ranked #N"，再追加。

排序规则：
- weighted conditions（`impact is not None`）按 impact 升序排在前面（最弱在最前）
- unweighted conditions（`impact is None`）按 atom_key 字母序排在末尾
- tie-breaking：同 impact 的 conditions 按 atom_key 字母序
- `is_bottleneck = True` 当且仅当 `impact is not None and aggregate_certainty is not None and impact == aggregate_certainty`

### 5.2 Narrative: ranked certainty_lines + certainty_bottleneck

`_build_certainty_lines` 改为调用 `rank_certainty_conditions`，输出排序后的 lines：

1. 第一行不变：`"Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): {value}."`
2. Conditions 按 `rank_certainty_conditions` 排序输出
3. bottleneck condition 行末附加 ` [bottleneck]`
4. unweighted 行不变：`"Condition {key} ({kind}): unweighted."`

示例：
```
Certainty (eligible child-proof subtree): aggregate certainty (bottleneck): 0.24.
Condition b0.a0 (predicate_witness_group): weight=0.4, impact=0.24. [bottleneck]
Condition b0.a1 (predicate_witness_group): weight=0.6, impact=0.54.
Condition b0.c0 (non_fact_check): unweighted.
```

**同时**，narrative dict 新增可选 `certainty_bottleneck` key（machine-readable，供 NL 消费）：

```python
narrative["certainty_bottleneck"] = {
    "atom_keys": ["b0.a0"],       # list[str], 所有 is_bottleneck=True 的 atom_key
    "impact": 0.24,               # float, bottleneck impact 值
}
```

- 无 bottleneck 时不写该 key（与 `certainty_lines` 可选模式一致）
- NL 消费 `narrative.get("certainty_bottleneck")` 而非解析 presentation string

### 5.3 NL: weakest-condition sentence

NL certainty paragraph 当前格式：`"Certainty summary: {joined certainty_lines}"`

改为：NL 从 `narrative.get("certainty_bottleneck")` 读取 machine-readable bottleneck 信息，在 join 后追加一句 weakest-condition 描述。

**单 bottleneck**（`len(atom_keys) == 1`）：
```
"The weakest condition is {atom_key} with impact {impact}."
```

**双 bottleneck**（`len(atom_keys) == 2`）：
```
"The weakest conditions are {key1} and {key2}, each with impact {impact}."
```

**3+ bottleneck**（`len(atom_keys) >= 3`）：
```
"There are {count} equally weak conditions (impact {impact}): {key1}, {key2}, and {key3}."
```
（Oxford comma，最后一个前加 "and"）

**无 bottleneck**（key 不存在或 `atom_keys` 为空）：不追加句子。

### 5.4 Audit / static

不单独扩 contract。audit narrative 和 static site 已消费 narrative output，排序和 bottleneck 标注自然继承。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `CertaintySummary` dataclass 不改
  - `certainty_summary` JSON 序列化 shape 不改（conditions 顺序在 JSON 中不保证，ranking 只在 narrative/NL 呈现）
  - 排序逻辑在 annotation 层（`_certainty.py`），不在 narrative renderer 里做排序
  - narrative renderer 只消费 `rank_certainty_conditions` 的输出
  - NL 只消费 `narrative.get("certainty_bottleneck")` + `narrative.get("certainty_lines")`，不消费 `certainty_summary` 也不重复排序
- 明确不做的内容：
  - 不改 `materialize_certainty_summary` / `certainty_summary_to_dict` 的输出 shape
  - 不新增 `ranked_conditions` 到 JSON output
  - 不在 export-time 物化 ranking（ranking 是 read-time derived）
- 兼容性约束：
  - 212 tests 全绿
  - narrative 输出向后兼容：已有的 certainty_lines 结构（first line = aggregate, subsequent lines = conditions）不变，只改顺序 + 追加 `[bottleneck]` 标记

## 7. Acceptance

- [ ] `_certainty.py` 新增 `RankedCondition` dataclass（无 `rank` 字段）+ `rank_certainty_conditions` pure function
- [ ] `rank_certainty_conditions` 排序规则：weighted 按 impact 升序 → unweighted 按 atom_key 字母序
- [ ] `is_bottleneck` 正确标注（含 tie 场景：同 impact 全标）
- [ ] `_build_certainty_lines` 消费 ranked view，bottleneck 行标 `[bottleneck]`
- [ ] narrative dict 新增 `certainty_bottleneck` key（machine-readable：`{atom_keys, impact}`）
- [ ] NL 从 `narrative.get("certainty_bottleneck")` 消费，不解析 presentation string
- [ ] NL weakest-condition 句覆盖 1 / 2 / 3+ bottleneck 三种 wording
- [ ] 212+ tests 全绿
- [ ] 新增 ranking-specific tests（排序、tie、unweighted-only、empty conditions、NL 1/2/3+ bottleneck）
- [ ] annotation docs 同步

## 8. Implementation Plan

1. [annotation/_certainty.py] 新增 `RankedCondition` dataclass + `rank_certainty_conditions` function + unit tests
2. [store/_candidate_evidence_tree_narrative.py] `_build_certainty_lines` 改为调用 `rank_certainty_conditions`，按排序输出 + `[bottleneck]` 标记
3. [store/_candidate_evidence_tree_nl.py] certainty paragraph 追加 weakest-condition 句
4. [tests] 新增 ranking-specific 测试用例
5. [docs] annotation docs 同步

## 9. Docs To Update

- `src/factpy_kernel/core/annotation/docs/README.md`
- `src/factpy_kernel/core/docs/01_architecture.md`（如需）
- `src/factpy_kernel/core/docs/01_architecture.en.md`（如需）

## 10. Outcome / Deviations

- 最终落地结果：
  - `_certainty.py`: `RankedCondition` dataclass + `rank_certainty_conditions` pure function
  - `_candidate_evidence_tree_narrative.py`: `_build_certainty_section` 替换 `_build_certainty_lines`，产出排序 `certainty_lines` + machine-readable `certainty_bottleneck`
  - `_candidate_evidence_tree_nl.py`: `_build_bottleneck_sentence` 消费 `certainty_bottleneck`，覆盖 1/2/3+ bottleneck wording
  - `annotation/__init__.py`: 补 `ConditionImpact`, `RankedCondition`, `rank_certainty_conditions` 导出
  - 7 ranking unit tests + 3 NL wording tests = 10 新测试（222 total）
  - 3 docs synced: annotation README, 01_architecture.md, 01_architecture.en.md
- 与 blueprint 不同的地方：
  - 2 个已有 narrative/NL 断言需要适配新排序顺序和 `[bottleneck]` 标记（test alignment，非新增测试）
- 为什么会有这些调整：
  - 旧断言逐字匹配 conditions 行，排序变更后必须对齐
- 归档说明：可归档到 `docs/blueprints/archive/`
