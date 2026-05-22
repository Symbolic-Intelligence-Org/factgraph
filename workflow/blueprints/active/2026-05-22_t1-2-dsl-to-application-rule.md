# T1.2 — DSL ergonomic 扩展 + DSL→application Rule 桥接 + legacy 形态拒绝(新 Rule path)

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))
- Related Modules:
  - `src/factgraph/sdk/dsl/expr.py` — `ExistsAtom`(line 175)需添加 `__getattr__`;`AttrRef`(line 101)需添加 optional `entity_type` 字段;`build_entity_dsl_call`(line 225)处理 Ellipsis;`_lower_compare`(line 345)可短路 AttrRef.entity_type 已知情况
  - `src/factgraph/sdk/schema.py` — `_looks_like_sdk_dsl_entity_call`(line 407)识别 Ellipsis;`_is_sdk_dsl_value` 接受 Ellipsis
  - `src/factgraph/sdk/dsl/__init__.py` — 新增 `build_application_rule` re-export(可选 SDK `__all__` — 待 T1.3 锁名)
  - **新文件** `src/factgraph/sdk/dsl/application_rule.py` — DSL→application Rule 桥接
  - `src/factgraph/application/protocol/rule.py` — **消费,不修改**(T1.1 frozen)
  - `src/factgraph/core/rules/where_ast.py` — 经 `parse_where_ir_to_ast` 消费,**不修改**
- Related Docs:
  - parent design essay [`rule-expression-and-proof-attempt.zh.md`](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) — §3.5(unified atom canonical)、§3.7(desc rendering)
  - track plan [`rule-expression-and-proof-track-plan.zh.md`](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) — §2 T1.2 row(post-v1 expanded scope)
  - T1.1 archived [`2026-05-22_t1-1-rule-class-additive.md`](../archive/2026-05-22_t1-1-rule-class-additive.md) — application Rule DTO 真源
- Audit Log:
  - [2026-05-22_t1-2-dsl-to-application-rule.audit.md](./2026-05-22_t1-2-dsl-to-application-rule.audit.md)

## 1. Problem

T1.1 ship `factgraph.application.protocol.Rule` DTO,`where: tuple[Atom, ...]` 内部存 core AST atoms。**用户面缺乏 ergonomic 构造路径** — 直接构造 `PredAtom("User:exists", [Var(name="$u"), ...])` 等 core AST atoms 冗长且与 parent §3.5 unified canonical 形态(`User(u).field == value`)不对齐。

### 1.1 当前 shipped SDK DSL 的 3 个 ergonomic gap

(a) **`User(u).field` 不工作** — `User(u)` 返回 `ExistsAtom`(`sdk/dsl/expr.py:175`);`ExistsAtom` **无 `__getattr__`**(line 174-178),故 `User(u).field` 当场 `AttributeError`。

(b) **`User(...)` Ellipsis 不被识别** — `EntityMeta.__call__`(`schema.py:146`)调用 `_looks_like_sdk_dsl_entity_call((...,), {})`(line 407);`_is_sdk_dsl_value(Ellipsis)` 返回 False(Ellipsis 不在 `is_dsl_term` 类型列表);路径 fall through 到 `super().__call__` 失败或产生非预期对象。

(c) **AttrRef 不携带 entity_type** — `LogicVar.__getattr__(item)`(`expr.py:55`)直接返回 `AttrRef(self, item)` — AttrRef 知道 record_var(LogicVar)但不知道实体类型;实体类型在 `_lower_compare`(line 345)的 bindings dict 里查找(`bindings.get(expr.left.record_var)`)。这意味着:
- 用户写 `User(u), u.field == "x"`(2-line)→ ExistsAtom 在 `where` list 单独出现 → bindings 添加 u→User → `_lower_compare` 查表得 entity_type。**legacy 路径已支持**。
- 用户写 `User(u).field == "x"`(unified)→ 若 `ExistsAtom.__getattr__` 仅返回纯 AttrRef(无 entity_type),则 ExistsAtom 不在 where list 中、bindings 没有 u→User 条目,`_lower_compare` 抛 "variable not bound" 错。

故 T1.2 (a) 必须同时:
- `ExistsAtom.__getattr__` 返回 `AttrRef`
- AttrRef 携带 `entity_type` 字段(从 `ExistsAtom.entity_type` 沿继承)
- 下游 lowering 路径短路 — AttrRef.entity_type 已知时不依赖 bindings 表

### 1.2 DSL→application Rule 桥接需求

T1.1 application `Rule(id, version, desc, where, ports)` 期待:
- `where: tuple[Atom, ...]` — core AST atoms(`PredAtom` / `CmpAtom` / 等)
- `ports: Mapping[str, Var]` — core `Var`

用户面期望:
- `where: list[ExistsAtom | CompareExpr | NotExpr | ...]` — SDK DSL atoms
- `ports: dict[str, LogicVar]` — DSL LogicVar

需要 SDK 侧 **桥接 函数** 完成:DSL atoms + LogicVars → core AST + Vars → application Rule。依赖方向 `sdk → application → core`(forward),由 SDK 实施(sdk imports application;application 不 import sdk)。

### 1.3 Legacy 形态 hard-cut(新 Rule path only)

Parent §3.5 禁止 3 种 legacy 形态:

```python
u.field == value                   # ✗ 裸 AttrRef 比较;LHS 必须是 EntityType(var).field
User(u), u.field == ...            # ✗ 两行分离形态;统一为 unified
Pred("user:status", u, "active")   # ✗ raw predicate atom;通过 EntityType(var).field 访问
```

T1.2 桥接在新 Rule path **构造期 reject** 上述 3 形态;**旧 SDK Rule path 不动**(legacy `factgraph.sdk.Rule` 仍可用相同 syntax — T1.3 处理 SDK 表面命名冲突)。

Hard-cut 实施关键:
- `ExistsAtom.__getattr__` 返回的 AttrRef **带 entity_type**(非 None)
- `LogicVar.__getattr__` 返回的 AttrRef **不带 entity_type**(None)— 故"2-line form" + "bare AttrRef compare" 在桥接处可以通过 `entity_type is None` 检测并拒绝
- 桥接 reject 用户在 where list 中直接放 `Pred(...)` 或 raw `PredAtom`

## 2. Goals

### 2.1 (a) SDK DSL ergonomic 扩展(additive,`sdk/dsl/expr.py` + `sdk/schema.py`)

- **`AttrRef` 添加 `entity_type: str | None = None`** 字段(default None;additive,不破坏 legacy AttrRef 用法)
- **`ExistsAtom.__getattr__(field) → AttrRef`** — 新方法;构造 AttrRef 时 set `entity_type=self.entity_type`
- **`LogicVar.__getattr__` 保持不变**(legacy 路径用)— 返回 AttrRef 时 `entity_type=None`
- **`_looks_like_sdk_dsl_entity_call` 识别 Ellipsis** — 仅在 **positional single Ellipsis arg** 分支 special-case `args[0] is Ellipsis`;**不动** `_is_sdk_dsl_value` 全局行为(per Step 4.2 v1 P1 — `_is_sdk_dsl_value` 同时被 `Field.__call__` kwargs / `EntityMeta.__call__` kwargs 共用,全局接 Ellipsis 会让 `User(field=...)` 走 head-call 路径生成坏 HeadCall payload)
- **`build_entity_dsl_call` 处理 Ellipsis** — `len(args)==1 and args[0] is Ellipsis` → 生成 unique anonymous `LogicVar`(`label=None`,token 自动)→ 返回 `ExistsAtom(entity_type, anon_var)`
- **`_lower_compare` MUST emit existence pred** when `AttrRef.entity_type` 已知(per Step 4.2 v1 P2):
  - 当 `CompareExpr.lhs` 是 `AttrRef(record_var, field, entity_type="X")` 且 `record_var not in bindings` → **prepend** `("pred", "X:exists", [record_var.token])` 到输出 + 更新 bindings;然后 emit field compare pred
  - 当 `CompareExpr.rhs` 是 `ExistsAtom(entity_type="Y", var=v)` (cross-entity ref,如 `LivesIn(li).user == User(u)`)→ prepend `("pred", "Y:exists", [v.token])` + 更新 bindings;然后 emit field compare pred(rhs term 取 v.token)
  - Symmetric for `expr.right` AttrRef.entity_type / `expr.left` ExistsAtom
  - **关键**:若 record_var 已在 bindings 中(用户已显式写了 `EntityType(var)` 或同一 var 已被其他 unified compare 引入)→ 不重复 emit existence pred(natural dedup via bindings 表)
- **`lower_term` 不需扩展**(因为 ExistsAtom 在 `_lower_compare` 内被直接消费,不进入 generic `lower_term`)
- 全部 additive — legacy SDK Rule 路径行为不变;legacy AttrRef-without-entity_type 路径(`u.field == ...` via `LogicVar.__getattr__`)仍走 bindings 表 fallback;legacy 用户**也可受益**于 unified syntax 扩展(legacy 接 `factgraph.sdk.Rule(where=[User(u).status == "active"])` 现在能 work — 之前要求 2-line)

### 2.2 (b) DSL → application Rule 桥接(新文件 `src/factgraph/sdk/dsl/application_rule.py`)

- 函数 `build_application_rule(*, id, where, ports, version=None, desc=None) → ApplicationRule`:
  - `id: str` — 直接传给 application Rule
  - `where: list[DSL_Atom]` — 用户给 DSL atoms(`ExistsAtom` / `CompareExpr` / `NotExpr` 等)
  - `ports: Mapping[str, LogicVar]` — 用户给 LogicVar
  - `version: str | None`
  - `desc: str | None`
- 实施步骤(实施细节在 §8):
  1. **Pre-lowering reject** — walk `where` list 查 legacy 形态(详 §2.3)
  2. **Lower DSL → IR tuples** — 复用现有 `sdk.dsl.expr.lower_where(where)`(已 ship line 290-300)
  3. **Parse IR tuples → core AST** — 复用现有 `core.rules.where_ast.parse_where_ir_to_ast(ir)`(已 ship line 99)
  4. **Convert ports** — `{name: Var(name=lv.token) for name, lv in ports.items()}`
  5. **Flatten OR-shape rejection** — application Rule 是 AND-only;若 `parse_where_ir_to_ast` 返回 `OrExpr` → raise(用户 where 不应包含 OR)
  6. **Build application Rule** — `Rule(id=id, where=tuple(and_expr.atoms), ports=core_ports, version=version, desc=desc)` — application Rule `__post_init__` 做自己的 validation
- 错误传播:DSL-level errors(`SDKDSLError`)与 application-level errors(`RuleValidationError`)分别保留;桥接 raise 自己的 `DSLToApplicationRuleError`(继承 Exception,domain-specific)对 legacy 形态拒绝
- **依赖方向**:`sdk.dsl.application_rule` import `application.protocol.rule` + `core.rules.where_ast`(forward);**no reverse**

### 2.3 (c) Legacy 形态 reject(桥接内,新 Rule path only)

Pre-lowering walk `where` list,reject:

| 形态 | 检测方式 | 错误 |
|---|---|---|
| `Pred(...)` raw atom in user where | `isinstance(atom, sdk.dsl.expr.PredAtom)` 或 type check | `DSLToApplicationRuleError("Pred(...) not allowed in new Rule path")` |
| 用户直接放 raw `PredAtom`(同上)| 同上 | 同上 |
| `CompareExpr` 的 `lhs` 或 `rhs` 是 `AttrRef` 且 `entity_type is None` | 递归 walk CompareExpr operands,查 AttrRef 的 entity_type | `DSLToApplicationRuleError("AttrRef must come from unified EntityType(var).field syntax; got bare AttrRef")` |
| 用户在 where 放 `RuleRefAtom`(sdk.dsl 版本)| `isinstance(atom, sdk.dsl.expr.RuleRefAtom)` | `DSLToApplicationRuleError("RuleRefAtom not allowed in new Rule path (parent C9)")` |

**不 reject**(legacy 路径行为不变;但桥接处 lowering 后 raise 是 fallback):
- `ExistsAtom` + `CompareExpr(AttrRef-with-entity_type)` — unified 形态合法
- `NotExpr` 包 unified 形态原子 — 合法
- `CompareExpr` 双方都是 `LogicVar` / `Const`(基础比较)— 合法

**2-line form 检测**:`User(u), u.field == "x"` 后,where 含 `[ExistsAtom(User, u), CompareExpr(AttrRef(record_var=u, field="field", entity_type=None), "==", "x")]`。**CompareExpr 的 AttrRef.entity_type 为 None**(因为 `u.field` 走 `LogicVar.__getattr__`,不带 entity_type)→ 桥接 reject。**精准检测,无需启发式**。

### 2.4 (d) `factgraph.sdk.dsl.__init__.py` re-export

新增:
```python
from .application_rule import build_application_rule, DSLToApplicationRuleError

__all__ = [
    # ... existing ...
    "build_application_rule",
    "DSLToApplicationRuleError",
]
```

**不进** `factgraph.sdk.__init__.py:__all__` — SDK 顶层 namespace 待 T1.3 锁定;T1.2 用户从 `factgraph.sdk.dsl` 显式 import。

### 2.5 (e) Tests

- **新文件** `tests/sdk/dsl/test_application_rule.py`:
  - **Unified canonical 7 pure forms**(per parent §3.5,无 mixed 形态):
    1. `User(u)` — bare existence
    2. `User(u).user_id == "u-2"` — identity literal
    3. `User(u).status == "active"` — field literal
    4. `User(u).score > 0.5` — field compare
    5. `User(...).name == "alice"` — anonymous Ellipsis + field
    6. `LivesIn(li).user == User(u)` — cross-entity ref(验证 existence pred 双 emit:`LivesIn:exists(li)` + `User:exists(u)` + field cross-ref)
    7. `LivesIn(li).country == country` — field-to-Var(命名)compare
  - **Existence pred emission verification**:Form 2-7 都验证 lowered output 含对应 `EntityType:exists(var.token)` 顶部 pred(不只是 field pred)
  - **Bindings dedup**:用户写 `[User(u), User(u).field == "x"]` 2-line(legacy 形态)→ 桥接 reject(`u.field` 走 LogicVar.__getattr__,AttrRef.entity_type=None);**不**测试"dedup 行为"(本 slice 不做 dedup pass,natural dedup via bindings 表)
  - **Legacy reject** 4 形态:`u.field == "x"`(裸 AttrRef)/ `User(u), u.field == "x"`(2-line)/ `Pred("user:exists", u)`(raw)/ `RuleRefAtom`(raw)→ 都 raise `DSLToApplicationRuleError`
  - OR-shape reject:`[[User(u)], [User(v)]]` 形态(2 分支)→ raise
  - Anonymous `...`:`User(...)` 每次独立 anonymous Var;tests 验证生成的 Var 不同 token
  - Ports validation 通过 application Rule(non-regression for T1.1 tests)
  - Round-trip:bridge 输出的 application Rule 用 T1.1 `content_digest` 计算 OK
- **新文件** `tests/sdk/dsl/test_existsatom_getattr.py`(或加入 `tests/sdk/dsl/test_unified_syntax.py`):
  - `User(u).field` 返回 AttrRef + entity_type="User"
  - `LogicVar.field` 仍返回 AttrRef + entity_type=None(legacy 路径)
  - `_lower_compare` 在 AttrRef.entity_type 已知时正确工作
- **新文件** `tests/sdk/test_schema_ellipsis.py`(或加入现有 schema tests):
  - `User(...)` 返回 ExistsAtom + anonymous Var
  - `User(..., ...)` 两个独立 anonymous Var(if allowed — 当前 build_entity_dsl_call 只接 1 arg)— 或 reject
- **Non-regression**:运行 T1.1 tests + 全 SDK tests + 全 application tests 全部 pass

## 3. Non-goals

- **不动** `factgraph.sdk.Rule`(legacy)— T1.3 处理
- **不动** Inference / Query / Branch / Pred / Not / RuleRef legacy DSL atoms 自身 — 仅在 build_application_rule 路径上 reject 它们
- **不动** `factgraph.application.protocol.Rule`(T1.1 frozen — 仅消费)
- **不动** `factgraph.core.rules.where_ast`(仅消费 `parse_where_ir_to_ast`)
- **不实现** RuleExpr 组合(T3)
- **不实现** head / `.eval` / Semantics(T4 / T5)
- **不实现** recursive immutability hardening(`feedback_invariant_defense_in_depth` deferred trade-off,继承自 T1.1)
- **不实现** atom kind canonical 9-list 文档化(T2.1)
- **不实现** ArithExpr / AggregateExpr value-producing forms(T2.2 / T2.3)— `BuiltinAtom` 经 lower_where 自动产出,通过 application Rule allowlist 接受;不扩 expression form 语义
- **不进 SDK 顶层 `__all__`**(待 T1.3)
- **不实现** dedup of same `(entity_type, var)` ExistsAtom — parent §3.5 F6 提到,但 lower_where 已通过 bindings 表确保唯一;T1.2 不显式实现"dedup pass"(可由用户主观使用 unified syntax 自然避免;若 2-line 被 reject,基本无 dedup 场景)
- **不引入** ArithExpr 增强 — 用户用 BinaryExpr(已 ship)+ lower_where 路径,产出 BuiltinAtom — application Rule 接受为 atom kind allowlist 成员;**不在本 slice 改 BuiltinAtom 语义或扩 ArithExpr API**(T2.2)

## 4. Current Context

### 4.1 当前实现入口(grounded 2026-05-22 review post T1.1)

| 关注 | 文件:line | 说明 |
|---|---|---|
| `EntityMeta.__call__` | `src/factgraph/sdk/schema.py:146` | Entity callable 入口;routes `User(u)` 到 `build_entity_dsl_call` |
| `_looks_like_sdk_dsl_entity_call` | `src/factgraph/sdk/schema.py:407-414` | DSL entity call 检测;Ellipsis 当前 fail |
| `_is_sdk_dsl_value` | `src/factgraph/sdk/schema.py:399-404` | DSL value 检测;Ellipsis 当前 fail |
| `build_entity_dsl_call` | `src/factgraph/sdk/dsl/expr.py:225-242` | 构造 ExistsAtom;当前要求 single LogicVar arg |
| `LogicVar.__getattr__` | `src/factgraph/sdk/dsl/expr.py:55-58` | 返回 AttrRef(record_var=self, field_name=item)— 不带 entity_type |
| `ExistsAtom` | `src/factgraph/sdk/dsl/expr.py:174-178` | `(entity_type, var)`;无 `__getattr__` |
| `AttrRef` | `src/factgraph/sdk/dsl/expr.py:101-126` | `(record_var, field_name)`;无 entity_type 字段 |
| `_lower_compare` | `src/factgraph/sdk/dsl/expr.py:345-393` | 使用 bindings dict 查 record_var → entity_type;**T1.2 扩展** emit existence pred when AttrRef.entity_type known + handle CompareExpr RHS/LHS = ExistsAtom(cross-entity ref)|
| `lower_term` | `src/factgraph/sdk/dsl/expr.py:444-460` | DSL term → IR atom value;**当前 raise SDKDSLError on ExistsAtom**(本 slice 不直接扩展 `lower_term`;cross-entity ref 在 `_lower_compare` 内处理 ExistsAtom,不进入 generic `lower_term`)|
| `lower_where` | `src/factgraph/sdk/dsl/expr.py:290-300` | DSL atoms list → IR tuples list |
| `lower_where_branch` | `src/factgraph/sdk/dsl/expr.py:303-315` | DSL atoms branch → IR tuples branch(bindings 表生成于此) |
| `parse_where_ir_to_ast` | `src/factgraph/core/rules/where_ast.py:99-127` | IR tuples → AndExpr/OrExpr 树 |
| `Atom` typealias | `src/factgraph/core/rules/where_ast.py:77` | `PredAtom \| RuleRefAtom \| CmpAtom \| InAtom \| BuiltinAtom \| NotAtom` |
| `Var` | `src/factgraph/core/rules/where_ast.py:19-22` | `(name, origin)` |
| T1.1 application Rule | `src/factgraph/application/protocol/rule.py:42-110` | frozen dataclass;`where: tuple[Atom, ...]`(reject RuleRefAtom);ports: `Mapping[str, Var]` |
| T1.1 RuleValidationError | `src/factgraph/application/protocol/rule.py:27-29` | `ValueError` subclass |

### 4.2 当前已知约束

- **Sacred branch isolation**:`master` / `v0.1-oss-prep` 不动
- **Dirty 集保留**:`docs/references/working/design-points/readme.md` / 3 example notebooks / `rainbird-ai sdk code/` — 全程保留
- **依赖方向**:`sdk → application → core` 严格 forward;桥接 sdk/dsl/application_rule.py 可 import application.protocol + core.rules,不可被 application 或 core import
- **Application-first** 已由 T1.1 ship 满足(DTO + pure function 在 application);T1.2 桥接是 SDK ergonomic shell
- **Narrow public API**:`feedback_narrow_public_api` — T1.2 不进 SDK 顶层 `__all__`;只在 `sdk.dsl` 子命名空间暴露
- **Invariant defense in depth** trade-off 已继承 T1.1:shallow immutability only;T1.2 桥接产出的 application Rule 仍 shallow
- **rule-touching 1-at-a-time**:`feedback_smaller_batch_design_blueprints` — T1.2 = 单 sub-slice(per Track plan v1 expanded scope);blueprint draft 前已完成 shipped 源码 grep(本 §4.1 表)

### 4.3 当前相关历史蓝图

| Blueprint | 路径 | 关系 |
|---|---|---|
| T1.1 Rule DTO additive | `workflow/blueprints/archive/2026-05-22_t1-1-rule-class-additive.md` | application Rule 类已 ship;本 slice 桥接到此 |
| Track 1 Branch identity | `workflow/blueprints/archive/2026-05-12_*branch-identity*.md` | shipped Branch(id=...)— 本 slice 不动 |
| Track 3 SemanticsProfile | archive | 与本 slice 正交 |

## 5. Proposed Shape

### 5.1 新文件 / 模块结构

```
src/factgraph/sdk/dsl/
├── application_rule.py      (新文件 ~200-280 LOC)
│   ├── class DSLToApplicationRuleError(Exception)
│   ├── build_application_rule(*, id, where, ports, version=None, desc=None) -> ApplicationRule
│   ├── _validate_dsl_where(where_atoms) -> None         # pre-lowering reject legacy
│   ├── _check_attrref_entity_type(attr_ref) -> None     # nested check
│   ├── _convert_ports(dsl_ports) -> dict[str, Var]      # LogicVar → core Var
│   └── _flatten_to_atoms(parsed_expr) -> tuple[Atom, ...]  # AndExpr → tuple; OrExpr → raise
└── __init__.py              (现有,新增 re-export build_application_rule + DSLToApplicationRuleError)

src/factgraph/sdk/dsl/expr.py     (修改 — 4 个局部 edit)
├── AttrRef                  + optional `entity_type: str | None = None` 字段
├── ExistsAtom               + `__getattr__(field) -> AttrRef(record_var=self.var, field_name=field, entity_type=self.entity_type)`
├── (其他不动)

src/factgraph/sdk/schema.py       (修改 — 2 个局部 edit)
├── _is_sdk_dsl_value        + 接受 Ellipsis(`value is Ellipsis`)
├── _looks_like_sdk_dsl_entity_call  + 接受 single-Ellipsis arg
├── build_entity_dsl_call(via import)  + Ellipsis 路径生成 anonymous LogicVar → ExistsAtom

src/factgraph/sdk/dsl/expr.py:build_entity_dsl_call (修改)
├── + if len(args)==1 and args[0] is Ellipsis:
│       anon_var = LogicVar()
│       return ExistsAtom(entity_type=entity_type, var=anon_var)

src/factgraph/application/docs/rule.md    (修改 — 新增 §unified-syntax 段落 + bridge usage example)
```

### 5.2 `build_application_rule` 伪 API

```python
from factgraph.application.protocol.rule import Rule as ApplicationRule, RuleValidationError
from factgraph.core.rules.where_ast import Atom, AndExpr, OrExpr, Var, parse_where_ir_to_ast
from factgraph.sdk.dsl.expr import (
    AttrRef, CompareExpr, ExistsAtom, LogicVar, NotExpr, PredAtom as DSLPredAtom,
    RuleRefAtom as DSLRuleRefAtom, lower_where,
)


class DSLToApplicationRuleError(Exception):
    """Raised when DSL atoms cannot be lowered to application Rule (legacy form, OR shape, etc.)."""


def build_application_rule(
    *,
    id: str,
    where: list,
    ports: Mapping[str, LogicVar],
    version: str | None = None,
    desc: str | None = None,
) -> ApplicationRule:
    """Build application Rule from SDK DSL atoms.

    Accepts unified canonical syntax (User(u).field == value) + ports as LogicVars.
    Rejects legacy forms (bare AttrRef, 2-line, raw Pred) per parent essay §3.5.
    """
    _validate_dsl_where(where)
    ir = lower_where(where)                                     # → list of IR tuples (AND-shape) or list of list (OR-shape)
    if _is_or_shape(ir):
        raise DSLToApplicationRuleError("OR-shaped where not allowed (application Rule is AND-only)")
    parsed = parse_where_ir_to_ast(ir)                          # → AndExpr | OrExpr
    if isinstance(parsed, OrExpr):
        raise DSLToApplicationRuleError("OR-shaped where not allowed (application Rule is AND-only)")
    atoms_tuple = tuple(parsed.atoms)                           # tuple[Atom, ...]
    core_ports = _convert_ports(ports)
    return ApplicationRule(
        id=id,
        where=atoms_tuple,
        ports=core_ports,
        version=version,
        desc=desc,
    )
```

### 5.3 Anonymous `...` Ellipsis 实施(Step 4.2 v1 P1 修正)

**关键约束**:`_is_sdk_dsl_value` 是 `Field.__call__` kwargs 检测 + `EntityMeta.__call__` kwargs 检测共用;全局把 Ellipsis 视为 DSL value 会让 `User(field=...)` 这类 head-call 路径误判 → 生成坏 HeadCall payload。故 Ellipsis special-case **只在** `_looks_like_sdk_dsl_entity_call` 的 **positional single arg** 分支处理。

```python
# sdk/schema.py:_looks_like_sdk_dsl_entity_call (modified — positional Ellipsis only)
def _looks_like_sdk_dsl_entity_call(args, kwargs):
    if args and kwargs:
        return False
    if kwargs:
        return any(_is_sdk_dsl_value(v) for v in kwargs.values())   # UNCHANGED
    if len(args) == 1:
        if args[0] is Ellipsis:                                       # NEW: positional Ellipsis
            return True
        return _is_sdk_dsl_value(args[0])
    return False
```

```python
# sdk/schema.py:_is_sdk_dsl_value (UNCHANGED — Ellipsis not added here)
def _is_sdk_dsl_value(value):
    try:
        from .dsl.expr import is_dsl_head_kwarg_value
    except Exception:
        return False
    return bool(is_dsl_head_kwarg_value(value))
```

```python
# sdk/dsl/expr.py:build_entity_dsl_call (extended — Ellipsis branch)
def build_entity_dsl_call(entity_cls, args, kwargs):
    entity_type = getattr(entity_cls, "__name__", None)
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKDSLError("invalid entity class for DSL call")
    if kwargs:
        if args:
            raise SDKDSLError("...")
        return HeadCall(...)
    if len(args) == 1 and args[0] is Ellipsis:                        # NEW
        anon_var = LogicVar()                                          # label=None, token auto $v<N>
        return ExistsAtom(entity_type=entity_type, var=anon_var)
    if len(args) == 1 and isinstance(args[0], LogicVar):
        return ExistsAtom(entity_type=entity_type, var=args[0])
    raise SDKDSLError("entity DSL call expects exactly one LogicVar or Ellipsis ...")
```

**结果**:
- `User(u)`(LogicVar)→ 走 `_is_sdk_dsl_value(LogicVar)=True` 分支 → ExistsAtom
- `User(...)`(positional Ellipsis)→ 走 special-case 分支 → ExistsAtom(anonymous var)
- `User(field=...)`(kwarg Ellipsis)→ 走 kwargs 分支:`_is_sdk_dsl_value(Ellipsis)=False` → `_looks_like_sdk_dsl_entity_call` returns False → 不被识别为 DSL call → 走 `super().__call__` 正常 Entity 构造 → 不生成坏 HeadCall(P1 修复)

### 5.4 ExistsAtom.__getattr__ + AttrRef.entity_type

```python
# sdk/dsl/expr.py
@dataclass(frozen=True)
class AttrRef:
    record_var: LogicVar
    field_name: str
    entity_type: str | None = None    # NEW additive

    def __post_init__(self):
        ...

    # comparison dunders unchanged

@dataclass(frozen=True)
class ExistsAtom:
    entity_type: str
    var: LogicVar

    def __getattr__(self, item):       # NEW
        if item.startswith("_"):
            raise AttributeError(item)
        return AttrRef(self.var, item, entity_type=self.entity_type)
```

**注**:`@dataclass(frozen=True)` 与 `__getattr__` 共存 — `__getattr__` 仅在标准属性查找失败后调用(dataclass 字段 `entity_type` / `var` 通过 `__dict__` 直接命中,不走 `__getattr__`)。

### 5.4b `_lower_compare` 扩展(Step 4.2 v1 P2 — emit existence pred)

**问题**:unified syntax `User(u).field == "x"` 的 where list 仅含 `[CompareExpr(AttrRef(u, "field", entity_type="User"), "==", "x")]`;**ExistsAtom 不在 list 中**。若 `_lower_compare` 只产 field pred,缺少 `User:exists(u)` 顶部 pred,违反 parent §3.5 unified canonical 的 "existence + field predicate" 语义。

**解决**:`_lower_compare` 接受 AttrRef.entity_type 时**主动 emit existence pred**;并处理 CompareExpr 一端为 ExistsAtom 的 cross-entity ref 情况。

```python
# sdk/dsl/expr.py:_lower_compare (extended)
def _lower_compare(expr, bindings, *, temp_seq):
    extra_existence: list[Any] = []

    # LHS AttrRef with entity_type → emit existence + register binding
    if isinstance(expr.left, AttrRef) and expr.left.entity_type is not None:
        rv = expr.left.record_var
        if rv not in bindings:
            extra_existence.append(("pred", f"{expr.left.entity_type}:exists", [rv.token]))
            bindings[rv] = expr.left.entity_type

    # RHS AttrRef with entity_type → same
    if isinstance(expr.right, AttrRef) and expr.right.entity_type is not None:
        rv = expr.right.record_var
        if rv not in bindings:
            extra_existence.append(("pred", f"{expr.right.entity_type}:exists", [rv.token]))
            bindings[rv] = expr.right.entity_type

    # RHS = ExistsAtom (cross-entity ref): emit existence + extract var token for compare
    if isinstance(expr.right, ExistsAtom):
        ev = expr.right.var
        if ev not in bindings:
            extra_existence.append(("pred", f"{expr.right.entity_type}:exists", [ev.token]))
            bindings[ev] = expr.right.entity_type
        # treat right side as the LogicVar for subsequent comparison lowering
        right_for_compare = ev   # used by existing AttrRef-vs-Var path below

    # LHS = ExistsAtom (rare symmetric case): same
    if isinstance(expr.left, ExistsAtom):
        ev = expr.left.var
        if ev not in bindings:
            extra_existence.append(("pred", f"{expr.left.entity_type}:exists", [ev.token]))
            bindings[ev] = expr.left.entity_type
        # ... mirror

    # === Existing field compare logic continues, prepending extra_existence ===
    # (existing AttrRef-AttrRef / AttrRef-Other / Other-AttrRef branches unchanged
    #  except they now MAY have bindings auto-populated, so the
    #  "variable not bound" SDKDSLError won't trigger for unified syntax)
    
    existing_field_compare_output = _existing_lower_compare_logic(expr, bindings, temp_seq=temp_seq)
    return extra_existence + existing_field_compare_output
```

**关键性质**:
- **Bindings 表共享 dedup**:若同一 record_var 已在 bindings(用户已显式 `EntityType(var)` 在 where 早期,或上一个 unified compare 已注入)→ 不重复 emit `EntityType:exists`(自然 dedup via bindings 表)
- **Legacy 路径不变**:`AttrRef.entity_type is None`(LogicVar.__getattr__ 来源)→ 不进入新分支 → 走原有 bindings 表 fallback(若 record_var 未绑定则 raise legacy SDKDSLError)
- **Cross-entity ref 输出 3 preds**:`LivesIn(li).user == User(u)` →`[("pred", "LivesIn:exists", ["$li"]), ("pred", "User:exists", ["$u"]), ("pred", "livesin:user", ["$li", "$u"])]`(field pred 走 existing logic)
- **lower_term 不需扩展**:ExistsAtom 在 `_lower_compare` 内被识别并消费,不进入 `lower_term` generic path

### 5.5 legacy 形态 reject 实施

```python
def _validate_dsl_where(where_atoms):
    """Pre-lowering reject of legacy forms in new Rule path."""
    for idx, atom in enumerate(where_atoms):
        if isinstance(atom, DSLPredAtom):
            raise DSLToApplicationRuleError(
                f"where[{idx}]: Pred(...) raw atom not allowed in new Rule path; "
                f"use EntityType(var).field == value unified syntax instead"
            )
        if isinstance(atom, DSLRuleRefAtom):
            raise DSLToApplicationRuleError(
                f"where[{idx}]: RuleRef atom not allowed in new Rule path (parent essay C9: "
                f"Rule 间不通过 atom 引用交互)"
            )
        if isinstance(atom, CompareExpr):
            _check_compare_expr_attrrefs(atom, where_path=f"where[{idx}]")
        if isinstance(atom, NotExpr):
            _validate_dsl_where(atom.body)
        # ExistsAtom: legal as-is


def _check_compare_expr_attrrefs(cmp_expr, where_path):
    for side_name, side_value in [("lhs", cmp_expr.left), ("rhs", cmp_expr.right)]:
        if isinstance(side_value, AttrRef) and side_value.entity_type is None:
            raise DSLToApplicationRuleError(
                f"{where_path}.{side_name}: AttrRef must come from unified EntityType(var).field "
                f"syntax (got bare AttrRef with no entity_type — bare AttrRef and 2-line forms "
                f"are not allowed in new Rule path per parent essay §3.5)"
            )
```

**关键**:`entity_type=None` 是检测 legacy 形态的精确标记 — 不依赖启发式,不依赖语法层重新解析。

### 5.6 LogicVar → core Var ports 转换(Step 4.2 v1 P4 — anonymous reject 精确化)

```python
def _convert_ports(dsl_ports):
    """Convert SDK DSL LogicVar ports → core Var ports.

    Rejects anonymous LogicVars (label=None) per parent C45: anonymous Vars
    from User(...) Ellipsis cannot be declared as ports.
    """
    out = {}
    for name, lv in dsl_ports.items():
        if not isinstance(lv, LogicVar):
            raise DSLToApplicationRuleError(
                f"ports[{name!r}] must be LogicVar (got {type(lv).__name__})"
            )
        if lv.label is None:                                       # NEW (P4 fix)
            raise DSLToApplicationRuleError(
                f"ports[{name!r}] cannot be anonymous LogicVar (label=None); "
                f"anonymous Vars from User(...) Ellipsis cannot be declared as ports "
                f"per parent essay C45"
            )
        if not lv.token:
            raise DSLToApplicationRuleError(f"ports[{name!r}] LogicVar has no token")
        out[name] = Var(name=lv.token)  # core Var with $-prefixed name
    return out
```

**关键**:anonymous LogicVar(`label=None`)由 `build_entity_dsl_call` 在 Ellipsis 路径生成 —`LogicVar()` 默认 `label=None`,但 `token` 会被 `__post_init__` auto-generated 为 `$v<N>`(非空)。故仅 `not lv.token` 检测**无法**捕获 anonymous;**必须** `lv.label is None` 精确检测。

**Test**:
- `with vars("u") as (u,): build_application_rule(ports={"user": u})` → pass(u.label="u")
- `anon = User(...)  # 产 ExistsAtom; anon.var.label is None`
- `build_application_rule(ports={"user": anon.var})` → raise `DSLToApplicationRuleError`(label=None)

### 5.7 测试结构

```
tests/sdk/dsl/
├── test_application_rule.py             (新文件 ~350-450 LOC)
│   ├── TestUnifiedSyntax              # 7 unified 形态 pass
│   ├── TestEllipsisAnonymous          # User(...) 每次独立;User(...) 多次互不冲突
│   ├── TestCrossEntityRef             # LivesIn(li).user == User(u)
│   ├── TestLegacyReject               # bare AttrRef / 2-line / Pred / RuleRef raise DSLToApplicationRuleError
│   ├── TestORShapeReject              # [[atom1], [atom2]] OR-shape raise
│   ├── TestPortsConvert               # LogicVar → Var token preserved
│   ├── TestAnonymousNotAsPort         # anonymous Var 不能作 port value
│   ├── TestApplicationRuleRoundTrip   # bridge → ApplicationRule.content_digest works
│   └── TestDescRender                 # bridge + render_desc 双绑定态正确
├── test_existsatom_getattr.py            (新文件 ~80-120 LOC)
│   ├── TestExistsAtomGetattr          # User(u).field 返回 AttrRef(entity_type="User")
│   ├── TestExistsAtomGetattrPrivate   # _-prefixed item raise AttributeError(避免 dataclass / __dunder 冲突)
│   └── TestLogicVarGetattrLegacy      # LogicVar.field 仍返回 AttrRef(entity_type=None) — non-regression
tests/sdk/
├── test_schema_ellipsis.py               (新文件 ~80-120 LOC)
│   ├── TestEntityEllipsis             # User(...) 产 ExistsAtom + anon Var
│   ├── TestMultipleEllipsis           # User(...) * 2 不同 anon Var(? 当前 build_entity_dsl_call 只接 1 arg)
│   └── TestEllipsisAsDslValue         # _is_sdk_dsl_value(Ellipsis) returns True
```

预估 ~510-690 LOC tests 总。

### 5.8 Non-regression scope

运行后保证 pass(reviewer 独立验证):
- 全 T1.1 tests:`tests/application/protocol/test_rule.py`(20 tests)
- 全现有 SDK DSL tests:legacy AttrRef-without-entity_type 路径仍正常(`u.field == "x"` 在 legacy SDK Rule path 仍工作)
- 全现有 schema tests:Entity callable + Field 兼容
- 全 ruff:本 slice 新文件 + 修改文件 pass

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - **不**动 `factgraph.application.protocol.Rule`(T1.1 frozen)
  - **不**动 `factgraph.core.rules.where_ast`
  - **不**动 legacy SDK `Rule` / `Inference` / `Query` / `Branch` / `Pred` / `Not` / `RuleRef`(都在 sdk/dsl/,T1.2 仅在 `expr.py` 局部 edit)
  - **不**动 `sdk/__init__.py` `__all__`(T1.3 处理 SDK 顶层名)
  - **不**改 `lower_where` / `parse_where_ir_to_ast` signatures(纯消费)
- **明确不做的内容**:
  - RuleExpr 组合(T3)/ Head(T4)/ `.eval`(T5)
  - 旧 SDK Rule path 内的 legacy 形态 hard-cut(T1.3 — 仅在新 Rule path 上 reject)
  - atom kind 9-list 文档化(T2.1)
  - ArithExpr / AggregateExpr 表达式形态扩展(T2.2 / T2.3)
  - Recursive immutability hardening(继承 T1.1 deferred)
  - SDK 顶层 `Rule` 名归属决策(T1.3)
- **兼容性约束**:
  - Legacy SDK `factgraph.sdk.Rule(select=..., where=..., head=...)` 仍可构造;legacy where syntax(`u.field == "x"`、`User(u), u.field == "x"`、`Pred(...)`)在 legacy Rule path **仍 work**
  - 用户面新选择:`from factgraph.sdk.dsl import build_application_rule`(显式 import 路径)→ 获得 unified syntax + 新 Rule
  - 两条路径并行,语义不混
- **Invariants**:
  - 桥接所有失败 → `DSLToApplicationRuleError`(domain exception);application Rule 构造期失败 → `RuleValidationError`;两层错误**不同 class**,便于用户区分
  - 桥接路径不修改原 DSL atom 对象;只构造新 core AST(immutable per T1.1 trade-off)
  - **依赖方向**:`sdk.dsl.application_rule` import `application.protocol.rule` + `core.rules.where_ast`(forward only);**不**反向 import
  - Ellipsis 产生的 anonymous LogicVar **不进** ports(桥接 reject)

## 7. Acceptance

- [ ] `from factgraph.sdk.dsl import build_application_rule, DSLToApplicationRuleError` 可 import
- [ ] `ExistsAtom.__getattr__("field")` 返回 AttrRef + `entity_type` 已 set 为 ExistsAtom.entity_type(2 unit tests pass)
- [ ] `LogicVar.__getattr__("field")` 仍返回 AttrRef + entity_type=None(legacy non-regression test pass)
- [ ] **`_is_sdk_dsl_value` UNCHANGED** — `_is_sdk_dsl_value(Ellipsis)` returns **False**(1 unit test 防回归;P1 修复)
- [ ] `_looks_like_sdk_dsl_entity_call((...,), {})` returns True(positional Ellipsis,1 unit test)
- [ ] `_looks_like_sdk_dsl_entity_call((), {"field": Ellipsis})` returns **False**(kwarg Ellipsis 不被识别为 DSL call,1 unit test 防 P1 回归)
- [ ] `User(...)` 产 ExistsAtom + anonymous LogicVar(不同 token,1 unit test)
- [ ] **`_lower_compare` emit existence pred** 验证(Step 4.2 v1 P2):
  - `User(u).field == "x"` lowered → `[("pred", "User:exists", ["$u"]), ("pred", "user:field", ["$u", "x"])]`(2 preds,1 unit test)
  - `LivesIn(li).user == User(u)` lowered → 3 preds 含 `LivesIn:exists($li)` + `User:exists($u)` + field cross-ref(1 unit test)
  - Bindings 表 dedup:`[User(u).a == 1, User(u).b == 2]` lowered → 只 emit `User:exists($u)` **一次**(natural dedup;1 unit test)
- [ ] `build_application_rule(...)` 接受 7 种 unified canonical pure forms 产正确 application Rule(7 unit tests pass;**无 mixed `User(u), User(u).field == ...` 形态** — P3 修复)
- [ ] `build_application_rule(...)` reject:bare AttrRef compare(`u.field == "x"`)/ 2-line form(`User(u), u.field == "x"`)/ `Pred(...)` raw / RuleRefAtom — 4 negative tests pass with `DSLToApplicationRuleError`
- [ ] OR-shape where reject(1 negative test)
- [ ] **Anonymous LogicVar(`label is None`)作 ports value reject**(P4 修复;`_convert_ports` 检查 `lv.label is None`,**非** `not lv.token` — anonymous LogicVar 有 auto token)(1 negative test)
- [ ] LogicVar(label 非 None) ports → core Var 转换 token 保留(1 unit test)
- [ ] Bridge → application Rule `content_digest` 跨进程 deterministic(1 unit test)
- [ ] Bridge → application Rule `render_desc("user %user")` 双绑定态正确(2 unit tests)
- [ ] **Non-regression**:T1.1 tests (20) + 全 SDK tests + 全 application tests + 全 core tests pass(`PYTHONPATH=src python -m unittest discover tests`)
- [ ] **ruff** clean on:`src/factgraph/sdk/dsl/application_rule.py` / `src/factgraph/sdk/dsl/expr.py` / `src/factgraph/sdk/schema.py` / `tests/sdk/dsl/test_application_rule.py` / `tests/sdk/dsl/test_existsatom_getattr.py` / `tests/sdk/test_schema_ellipsis.py`
- [ ] **依赖方向静态可验证**:`grep "from factgraph.sdk" src/factgraph/application/protocol/rule.py` 返空;`grep "from factgraph.sdk" src/factgraph/core/rules/` 返空
- [ ] `sdk/dsl/__init__.py` 含 `build_application_rule` + `DSLToApplicationRuleError` re-export
- [ ] `src/factgraph/application/docs/rule.md` 新增 §unified-syntax + bridge usage 段落
- [ ] **Sacred branch isolation + dirty 集保留** 全程遵守

## 8. Implementation Plan

> **轻量 cadence 模式**(per Track plan §1.2):跳过 Step 4.3 preflight / Step 4.5 self-check 独立 commits;主路径 draft → scoped → impl + tests + docs → closure → archive。

1. **[blueprint] Step 4.1 draft commit**:本 commit。
2. **[blueprint] Step 4.2 review tightening commits**(reviewer = 用户):若 surfaces P1-Pn,我 apply。可能多轮(类似 T1.1 v1/v2/v3 模式)。
3. **[blueprint] Step 4.6 scoped anchor commit**:`Status: draft` → `Status: scoped` + audit log "scoped" 事件。
4. **[impl] 主 feat commit**:
   - 修改 `src/factgraph/sdk/dsl/expr.py`(`AttrRef` 加 `entity_type`;`ExistsAtom.__getattr__`;`build_entity_dsl_call` Ellipsis 分支)
   - 修改 `src/factgraph/sdk/schema.py`(`_is_sdk_dsl_value` Ellipsis)
   - 新建 `src/factgraph/sdk/dsl/application_rule.py`(~200-280 LOC)
   - 更新 `src/factgraph/sdk/dsl/__init__.py`(re-export)
   - 新建 `tests/sdk/dsl/test_application_rule.py`(~350-450 LOC)
   - 新建 `tests/sdk/dsl/test_existsatom_getattr.py`(~80-120 LOC)
   - 新建 `tests/sdk/test_schema_ellipsis.py`(~80-120 LOC)
   - 更新 `src/factgraph/application/docs/rule.md`(加 §unified-syntax + usage example)
5. **[impl] 可能的 fix commit**(若 Step 4.7 review surface P1):surgical 修复;否则 skip。
6. **[closure] Step 4.8 closure commit**:`Status: scoped` → `Status: implemented` + `§10 Outcome` 填齐 + audit log "implemented" 事件。
7. **[archive] Step 4.9 archive commit**:`git mv` 蓝图 pair `active/` → `archive/`;basename 不变。

**预估总 commits**:5-7(draft / [N rounds tightening] / scoped / impl-feat / [optional fix] / closure + archive 可合并)。

## 9. Docs To Update

- **更新** `src/factgraph/application/docs/rule.md`(T1.1 已 ship)— 新增:
  - §**Unified syntax(via SDK DSL bridge)**:展示 `User(u).field == value` 等 7 形态 + Ellipsis + cross-entity ref
  - §**Bridge usage**:从 `factgraph.sdk.dsl` import `build_application_rule` 的端到端 example
  - §**Legacy form rejection**:列出 3 种被 reject 的 legacy 形态 + 各自 error message 模式
- **不**新建 `src/factgraph/sdk/dsl/docs/`(若不存在;若已有 SDK DSL docs 入口可加 §pointing)— 待确认
- **不更新** `docs/README.md`(本 slice 不引入新顶层 docs 入口)
- **不更新** `docs/official/kernel/quickstart/`(用户面 quickstart 仍指向 legacy Rule;新 Rule + bridge 真正成为 SDK 默认前 — T1.3 — 不动)

## 10. Outcome / Deviations

待 implementation 完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- **AttrRef.entity_type additive 扩展** — 复用既有 frozen dataclass + default value 加字段,legacy 路径行为不变(`entity_type=None` 时 `_lower_compare` 走 bindings 表 fallback);若实施期发现下游 lowering / bindings 表与 AttrRef.entity_type 冗余冲突,记录于此 + 决策保留方向
- **依赖于 T1.1 shipped impl 行为**:`application.protocol.Rule` 接受 `tuple[Atom, ...]` 直接;若 T1.1 future hardening 改变 acceptance,本 slice 桥接需同步更新
- **Recursive immutability** 继承 T1.1 deferred(per `feedback_invariant_defense_in_depth` trade-off)
- 归档说明:
