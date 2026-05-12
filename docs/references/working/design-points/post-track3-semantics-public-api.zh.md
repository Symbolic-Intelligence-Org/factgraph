# Post-Track-3 Public Semantics API 设计方向

- 状态: working design point(非合同,非 blueprint)
- 创建: 2026-05-12
- 上下文: Track 3 完成后(`origin/master @ 4bcb6a25`),identifies the next iteration of the Semantics public API
- 相关 archives:
  - [`docs/blueprints/archive/2026-05-12_sdk-service-semantics-callsite.md`](../../../blueprints/archive/2026-05-12_sdk-service-semantics-callsite.md)
  - [`docs/blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md`](../../../blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md)
  - [`docs/blueprints/archive/2026-05-12_problog-semantics-profile-migration.md`](../../../blueprints/archive/2026-05-12_problog-semantics-profile-migration.md)
  - [`docs/blueprints/archive/2026-05-12_semantics-profile-scaffolding.md`](../../../blueprints/archive/2026-05-12_semantics-profile-scaffolding.md)
  - [`docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md`](../../../blueprints/archive/2026-05-11_branch-confidence-decomposition.md)
- 相关 working refs:
  - [`docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`](./rule-policy-function-tree-and-syntax.zh.md)
  - [`docs/references/working/design-points/possibility-probability-transmission.zh.md`](./possibility-probability-transmission.zh.md)

## 1. 问题陈述

Track 3 完成后,`SemanticsProfile` 功能完整但作为 public authoring API 仍然太重:

- 一次性定义所有引擎的参数,但用户每次只用一种引擎推理
- `rule_projection.pyreason` 用 `body_atom:{branch}:{atom}` 位置引用,稳定性和可读性都一般
- `evaluate(deriv, engine="pyreason", semantics=profile)` 中 engine 与 profile 的引擎信息重复

`SemanticsProfile` 更像是**内部 canonical profile**,不是最舒服的 public authoring shape。

同时,实证调查发现一个 granularity gap: D 的 `body_atom:{branch}:{atom}` projection 路径表面上 per-atom,但内部 carrier (`body_predicate_bounds: dict[str, tuple]`) 是 per-predicate-id 的,两个 atom 共享同一 pred_id 时不能给不同 bound。

## 2. 关键前置: Branch Identity

当前 `Branch` 只有 `atoms`,没有 `id/name/version`。任何"per-branch semantics"都需要稳定引用 branch。

### 2.1 Branch id 策略

| 优先级 | 形式 | 何时用 |
|---|---|---|
| 1 (推荐) | 用户显式 `Branch(id="sensor_path", atoms=[...])` | 任何需要 profile 引用的场景 |
| 2 (fallback) | 系统在 inspect 时显示位置 id `b0/b1/...` | 未命名 branch |
| 否决 | 随机 UUID | 不可复现,registry/docs/tests 都会变差 |

### 2.2 同 Rule/Derivation 内 id 唯一约束

- 同一个 Rule 的多个 Branch 必须 id 唯一
- 跨 Rule 不要求(branch id 是 Rule-scoped 命名空间)
- 未命名 branch 在 inspect 中按位置生成 `b{branch_idx}` —— 跟现有 PyReason rule name 后缀 `_b{branch_idx}` 一致(见 [`where_compile.py:55`](../../../../src/kernel/adapters/pyreason/where_compile.py))

### 2.3 不放回 engine 参数

明确反对的方向: `Branch(id="...", atoms=[...], confidence=0.9)`。这会破坏 Track 3 A2 刚确立的"Branch 是纯结构"边界。engine semantics 在 runtime profile/semantics object 中引用 branch id,而不是放回 Branch。

## 3. Rule Inspect API

当前没有 public rule 结构 inspect API。`fg.eval.inspect_semantics(profile)` inspect 的是 profile lane,不是 rule/branch 结构。

### 3.1 建议 namespace

`fg.rules.inspect(rule)` —— rules namespace 当前为空,正好作为 first-class public API。

(备选: `fg.eval.inspect_rule(rule)`,与 `inspect_semantics` 配对。倾向前者。)

### 3.2 返回结构草案

```python
fg.rules.inspect(rule)
# →
{
    "rule_id": "risk_rule",
    "version": "v1",
    "head": {...},                          # 含 head_call 等
    "branches": [
        {
            "id": "sensor_path",            # 显式或生成的 b0
            "index": 0,
            "atoms": [...],                 # 该 branch 的 atom 结构
        },
        {
            "id": "obstacle_path",
            "index": 1,
            "atoms": [...],
        },
    ],
}
```

- 只 inspect rule **结构**,不 inspect engine semantics
- engine semantics 仍走单独的 `inspect_semantics(profile)` 或新的 `inspect_semantics(semantics_obj)`

## 4. Single-Head Hard-Cut

当前 `Derivation.head` 支持单值或 list,内部 `_heads` tuple 可以多元素。

### 4.1 多头让以下都复杂

- `head_bound` API shape: 单值 vs `dict[head_idx, tuple]` vs list
- readback / accept / why-not 都要处理多头
- 跟 PyReason single-head conjunction 表达不直接匹配

### 4.2 倾向: pre-release hard-cut

- Track 1 G0 决定 hard-cut multi-head,public Rule/Derivation 收敛到单头
- 同步影响 PyReason: `head_bound` 退化为单值 tuple,不需 `dict` 或 list
- 与 `feedback_release_workflow_traps`(pre-release 允许 hard-cut)一致

## 5. Public Semantics API 重塑

### 5.1 命名候选

| 候选 | 优势 | 劣势 |
|---|---|---|
| `ProbLogSemantics` / `PyReasonSemantics` ← **推荐** | 对应 public `semantics=` kwarg 直观 | "Semantics" 这词在 Track 3 已经过载 |
| `ProbLogProjection` / `PyReasonProjection` | 跟 `rule_projection` 概念对齐 | 不那么 self-explanatory |
| `ProbLogProfile` / `PyReasonProfile` | 跟 `SemanticsProfile` 词族一致 | "Profile" 当前是 internal canonical |

**否决**:

- `ProbLogRuleExt` / `PyReasonRuleExt` —— `*Ext` 是 adapter internal bridge 的命名,不应升为 public

### 5.2 ProbLogSemantics 草案 shape

```python
ProbLogSemantics(
    branch_probabilities={
        "branch_id1": 0.5,
        "branch_id2": 0.8,
    },
)
```

`branch_probabilities` 用 branch id 索引,不再用 `branch:{index}` 位置。

### 5.3 PyReasonSemantics 草案 shape

```python
PyReasonSemantics(
    timestep_delay=2,
    head_bound=[0.8, 1.0],                  # 全 branch 默认 head interval,可选
    branch_bounds={                         # 覆盖具体 branch 的 head interval
        "sensor_path": [0.8, 1.0],
        "obstacle_path": [0.2, 0.8],
    },
    temporal_projection=...,                # 沿用 B 的 lane shape
    uncertainty_projection=...,             # 沿用 B 的 lane shape
)
```

语义:

- `head_bound`: 所有 branch 默认 head interval(可省)
- `branch_bounds`: 覆盖具体 branch 的 head interval
- `temporal_projection` / `uncertainty_projection`: 沿用 B 的字段定义(`mode="none"` / `mode="fixed_timesteps"` / `mode="valid_time_boundaries"` 等)
- **不支持 atom-level 标注**(`body_predicate_bounds` 退到 internal advanced)
- **不支持 multi-head**(已被 §4 cut)

### 5.4 退到 internal advanced 的能力

- `body_atom:{branch}:{atom}` 路径式 atom-level interval bound
- multi-head head_bound

这些仍然可以通过低阶 `kernel.core.semantics.SemanticsProfile` 表达(如果保留),或者通过未来 `*Semantics(advanced=...)` 字段访问。但 **不作为默认 public shape**。

## 6. Engine 自动推导

### 6.1 规则

```python
# 推荐用法(engine 从 semantics 推导):
fg.eval.evaluate(deriv, semantics=PyReasonSemantics(...))
fg.eval.evaluate(deriv, semantics=ProbLogSemantics(...))

# 无 semantics 时仍可显式 engine:
fg.eval.evaluate(deriv, engine="native")
fg.eval.evaluate(deriv, engine="pyreason")    # 无 profile 也接受

# 显式 + 推导冲突时 reject:
fg.eval.evaluate(deriv, engine="problog", semantics=PyReasonSemantics(...))  # ← reject
```

### 6.2 解决方式

| 情况 | 行为 |
|---|---|
| 无 `semantics`,无 `engine` | 默认 `engine="native"` |
| 无 `semantics`,有 `engine="X"` | 使用 X |
| 有 `semantics`,无 `engine` | 用 `semantics.engine` 推导 |
| 有 `semantics`,有 `engine`,一致 | 接受 |
| 有 `semantics`,有 `engine`,不一致 | reject with mismatch 错误 |

E 的 D10(profile-engine mismatch reject)已经覆盖最后一条;前几条是 evaluate signature 层的新增行为。

## 7. PyReason Branch-Bound 编译模型

### 7.1 关键 empirical 发现

[`where_compile.py:55`](../../../../src/kernel/adapters/pyreason/where_compile.py):

```python
rule_name = base_name if len(branches) == 1 else f"{base_name}_b{branch_idx}"
```

**每个 branch 已经编译为独立的 PyReason rule**,name 用 `_b{branch_idx}` 后缀。这意味着:

- 单 branch: `derived_risky`
- 多 branch: `derived_risky_b0`, `derived_risky_b1`, ...

每条 PyReason rule 已经支持 head annotation(`head : [lo, hi] <-...`)。

### 7.2 `branch_bounds` 编译目标

```python
PyReasonSemantics(branch_bounds={
    "sensor_path": [0.8, 1.0],
    "obstacle_path": [0.2, 0.8],
})
```

编译为:

```text
risky(x) : [0.8, 1.0] <-1 sensor_alert(x), near_obstacle(x)    # derived_risky_b0
risky(x) : [0.2, 0.8] <-1 other_path(x)                          # derived_risky_b1
```

机械可行,跟现有 PyReason rule text 输出能力对齐。

### 7.3 内部 carrier 改造

当前 `PyReasonRuleExt`:

```python
head_bound: tuple[float, float] | None    # rule-global
body_predicate_bounds: dict[str, tuple]
```

需要新增 per-branch carrier,候选 shapes:

```python
# 候选 A: 新字段,与 head_bound 共存
PyReasonRuleExt(
    head_bound: tuple[float, float] | None,           # 默认
    branch_head_bounds: dict[str, tuple] | None,      # 新,覆盖
    body_predicate_bounds: dict[str, tuple],          # 保留 advanced
    timestep_delay: int,
)

# 候选 B: head_bound 改语义
PyReasonRuleExt(
    head_bounds: dict[str, tuple] | None,             # 用 branch id 索引,单 branch 时用 "*" 或 b0
    ...
)
```

A 候选 backward-compatible,推荐。详细 shape 在 future G0 锁定。

## 8. 3-Track 顺序与依赖

```
Track 1: Branch identity + rule inspect + single-head hard-cut
  ↓ (依赖: branch id 存在,inspect 可用,multi-head 决策)
Track 2: Public Semantics API 重塑 + engine 自动推导
  ↓ (依赖: public API shape 锁定)
Track 3 (post): PyReason branch-bound carrier + compile 模型
```

**严格串行,不能交错。** 反向依赖:

- Track 2 的 `branch_bounds={"sensor_path": ...}` 需要 Track 1 的 `Branch(id="sensor_path", ...)`
- Track 3 的内部 carrier shape(per-branch dict)需要 Track 2 的 public shape 锁定,否则可能反复改

## 9. 与现有 archive 的关系

| Archive | 当前形态 | Track 1-3 影响 |
|---|---|---|
| A2 `branch-confidence-decomposition` | `Body → Branch` 已重命名,Branch 只有 atoms | Track 1 给 Branch 加 id |
| A3 `engine-ext-decomposition` | 公共 `engine_ext` 已删除 | branch_bounds 是新替代抽象 |
| A4 `condition_weights-decomposition` | condition_weights 保留为 certainty projection input | 与本 doc 正交,不动 |
| B `semantics-profile-scaffolding` | `SemanticsProfile` value object 已落地 | 退到 internal canonical(或保留作 advanced) |
| C `problog-semantics-profile-migration` | ProbLog 消费 `rule_projection.problog` | Track 2 改用 `ProbLogSemantics`,C 的 carrier 保留为 internal |
| D `pyreason-semantics-profile-migration` | PyReason 消费 `rule_projection.pyreason` + `temporal_projection` | Track 2 + 3 重塑 public shape;internal carrier 改造 |
| E `sdk-service-semantics-callsite` | `evaluate(engine=, semantics=)` 公共 call-site | Track 2 加 engine 自动推导 |

**A1/A2/A3/A4 archives 全部保持不动。** Track 1-3 都是 forward-compatible 演进,不重写 archive。

## 10. Open Questions(留给未来 G0)

1. **Branch.id 必需 vs 可选?** 推荐可选,未命名 inspect 显示 `b0/b1`。
2. **`SemanticsProfile` 命运**: 完全废除 vs 保留作 internal canonical vs `advanced=...` 字段?推荐保留作内部 canonical。
3. **Branch id 在 lowered IR / authoring payload / registry 怎么保留?** 需要 source audit。
4. **`fg.rules.*` namespace 还应包含哪些 public APIs?**(validate? compile? lint?)
5. **multi-rule per branch 的 `_b{idx}` rule name 是否暴露给用户?** —— 倾向不暴露(internal-only);用户通过 branch id 引用。
6. **PyReason `branch_head_bounds` 内部表示**: `dict[branch_id_str, tuple]` vs `dict[branch_index_int, tuple]` vs `list[tuple | None]`?
7. **Engine 默认值**: `evaluate(deriv)` 无 semantics 无 engine 时默认 `native` 还是要求显式?推荐默认 `native`(向后兼容)。
8. **ProbLog `branch_probabilities` 单值 vs interval**: ProbLog 是单概率,保持单 `float`;不要为了对称把它改成 `tuple`。

## 11. 暂不动的边界

- Track 3 archives 全部不动
- 任何代码不动
- 任何 active blueprint 不动
- `v0.1.0-rc.1` tag 不动
- `release/0.1.x` branch 不动

Track 1-3 启动需要走 draft → G0 → G1 → G2 → G3 → G4 → publish 完整流程,跟 Track 3 各 slice 一致。每个 Track 应该:

- 单独 source-grounded audit
- 独立 blueprint 对(.md + .audit.md)
- 独立 milestone
- 独立 memory checkpoint

## 12. 推荐启动条件

不建议**立即**开 Track 1。建议:

- 至少一次 fresh-context session 之间,让今日 Track 3 burn 的 in-context state 释放
- 启动时先做 Branch identity 的 source audit:
  - 当前 `Branch` 怎么 lower 到 IR(`lower_where`)
  - authoring payload 怎么序列化 Branch
  - registry 是否需要存 branch id
  - 现有 `_normalize_rule_where_for_payload` / `_normalize_query_where_branch_wrapper` 是否需要改
- audit 完成后再开 Track 1 draft seed

## 13. 命名 / 设计 reference

- 当前 Track 3 design point: [`rule-policy-function-tree-and-syntax.zh.md`](./rule-policy-function-tree-and-syntax.zh.md) —— 提到 Body→Branch、policy 层、function tree
- 当前 uncertainty design point: [`possibility-probability-transmission.zh.md`](./possibility-probability-transmission.zh.md)
- E archive §10.5 列出 3 个 Track 3 之外的 follow-up: shell-profile flow、multi-interval validity、release packaging —— 这 3 个跟本 doc 的 Track 1-3 正交,可以独立开
