# Task Blueprint: PyReason Rule Ext v0

- Status: implemented
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md) (Decision §D5, §D6)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/rule_ext.py` (new)
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/sdk/dsl/rule.py` (read only — not modified)
  - `src/factpy_kernel/sdk/dsl/expr.py` (read only — not modified)
- Audit Log:
  - [2026-03-26_pyreason-rule-ext-v0.audit.md](./2026-03-26_pyreason-rule-ext-v0.audit.md)

## 1. Problem

PyReason 规则当前是手写字符串 tuple：`("popular(x) <-1 popular(y), Friends(x,y)", "name")`。这绕过了 Rule DSL，不可验证，不可组合，且 `timestep_delay` 隐藏在字符串语法里。

## 2. Goals

- `PyReasonRuleExt(timestep_delay=0)` — 引擎特定规则参数
- `PyReasonRuleDef(rule=Rule(...), ext=PyReasonRuleExt(...))` — adapter-local wrapper
- `PyReasonFactDef(atom, name, start, end)` — typed 初始事实（替代 tuple）
- `compile_pyreason_rule(rule_def) → str` — WHERE DSL → PyReason 规则语法
- Runner 接受 `PyReasonRuleDef` + `PyReasonFactDef`
- Integration demo 不再手写 rule strings

## 3. Non-goals

- 不修改 `sdk/dsl/rule.py` 的 `Rule` 类（不加 `engine_ext` 字段）
- 不做 `Store.evaluate(mode="pyreason")`
- 不支持 `CompareExpr` / `NotExpr` / `RuleRefAtom`（v0 只支持 `PredAtom` + `LogicVar`）
- 不做 `PyReasonDerivationExt`（等 execute surface 再做）

## 4. Current Context

- `Rule(id, version, select, where, ...)` 是 frozen dataclass
- `where` 包含 `PredAtom(pred_id="user:popular", terms=(LogicVar(...),))`
- `select` 包含 head 声明（`HeadCall` 或 `Pred`）
- runner 当前接受 `rules: list[tuple[str, str]]`
- Decision §D5: `engine_ext` 是方向，但 v0 先做 adapter-local wrapper

## 5. Proposed Shape

### 5.1 New Types

```python
@dataclass(frozen=True)
class PyReasonRuleExt:
    timestep_delay: int = 0

@dataclass(frozen=True)
class PyReasonRuleDef:
    rule: Rule
    ext: PyReasonRuleExt = field(default_factory=PyReasonRuleExt)

@dataclass(frozen=True)
class PyReasonFactDef:
    atom: str       # "popular(Alice)"
    name: str       # "alice_popular"
    start: int = 0
    end: int = 0
```

### 5.2 Compile Helper

```python
def compile_pyreason_rule(rule_def: PyReasonRuleDef) -> tuple[str, str]:
    """Compile to (pyreason_body_str, rule_name)."""
    head = _compile_head(rule_def.rule)        # "popular(x)"
    body = _compile_body(rule_def.rule.where)  # "popular(y), Friends(x,y)"
    delay = rule_def.ext.timestep_delay        # 1
    return (f"{head} <-{delay} {body}", rule_def.rule.id)
```

WHERE atom → PyReason body atom 映射：
- `PredAtom("user:popular", LogicVar(x))` → `popular(x)`
- `PredAtom("friends:strength", LogicVar(x), LogicVar(y))` → `strength(x, y)`
- `LogicVar` term → 其 token（`x`, `y`, `z`）
- 字面量 → 直接嵌入

### 5.3 Runner Integration

`run_pyreason()` 签名扩展：

```python
def run_pyreason(
    session,
    *,
    rules: list[tuple[str, str]] | None = None,           # legacy string tuples
    rule_defs: list[PyReasonRuleDef] | None = None,        # new typed defs
    facts: list[tuple[str, str, int, int]] | None = None,  # legacy
    fact_defs: list[PyReasonFactDef] | None = None,        # new typed defs
    config=None,
) -> PyReasonRunResult:
```

两种入口共存，`rule_defs` 通过 `compile_pyreason_rule()` 转为 string 后合并到 `rules`。

### 5.4 Target Demo

```python
x, y, z = LogicVar("x"), LogicVar("y"), LogicVar("z")

rules = [
    PyReasonRuleDef(
        rule=Rule(
            id="shared_pet_popularity", version="1.0",
            select=[Pred("user:popular", x)],
            where=[
                Pred("user:popular", y),
                Pred("friends:strength", x, y),
                Pred("owns:since", y, z),
                Pred("owns:since", x, z),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=1),
    ),
    PyReasonRuleDef(
        rule=Rule(
            id="dog_owner_outdoorsy", version="1.0",
            select=[Pred("user:outdoorsy", x)],
            where=[
                Pred("owns:since", x, y),
                Pred("pet:dog_breed", y),
            ],
        ),
        ext=PyReasonRuleExt(timestep_delay=0),
    ),
]
```

## 6. Boundaries And Invariants

- 所有新类型在 `adapters/pyreason/rule_ext.py`，不在 core/
- `Rule` 类不修改（v0 是 wrapper，不是 extension）
- v0 compile 只处理 `PredAtom` + `LogicVar` + 字面量，遇到不支持的 atom 抛异常
- `PyReasonFactDef` 的 `atom` 仍是 PyReason 格式字符串（不做 fact DSL 编译）
- runner 保持向后兼容（legacy tuple 入口不删）

## 7. Acceptance

- [x] `PyReasonRuleExt` + `PyReasonRuleDef` + `PyReasonFactDef` 可用
- [x] `compile_pyreason_rule()` 正确生成 PyReason 规则语法
- [x] runner 接受 `rule_defs` + `fact_defs`
- [x] integration demo 使用 typed defs
- [x] v0 compile 限制有明确错误提示（不支持的 atom）
- [x] 测试覆盖 compile + runner integration

## 8. Implementation Plan

1. 新建 `adapters/pyreason/rule_ext.py`：types + compile helper
2. 更新 `adapters/pyreason/runner.py`：接受 `rule_defs` / `fact_defs`
3. 新建 `tests/test_pyreason_rule_ext.py`
4. 更新 `examples/pyreason_integration_demo.py`
5. 更新 `adapters/docs/03_pyreason_adapter.md`

## 9. Docs To Update

- 本蓝图 audit log
- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 实现已落地到 `adapters/pyreason/rule_ext.py`，新增 adapter-local `PyReasonRuleExt` / `PyReasonRuleDef` / `PyReasonFactDef`，并提供最小 `Rule.where -> PyReason syntax` compile helper。
- `runner.py` 现在同时支持 legacy tuple 输入与 typed `rule_defs` / `fact_defs`，保持向后兼容。
- `examples/pyreason_integration_demo.py` 已切换到 typed defs，不再手写规则字符串 tuple。
- `adapters/docs/03_pyreason_adapter.md` 已同步当前实现真相与 v0 限制。
- 验证结果：
  - 新增 `test_pyreason_rule_ext.py`，`21` tests 通过
  - 聚焦回归：`test_pyreason_rule_ext` + `test_pyreason_runner` + `test_pyreason_session`，共 `97` tests 通过
  - `python -m py_compile` 通过
  - demo 已验证 typed defs 路径可运行到真实 `pyreason` import/runtime 边界，并保持 graceful exit
- 偏差：无架构偏差。实现中额外支持了 `HeadCall` 形式的 rule head 编译，范围仍保持在 adapter-local v0。
