# T1.1 — Additive 新 Rule 类(application protocol DTO,storing core AST)

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))
- Related Modules:
  - `src/factgraph/application/protocol/` — new home for `Rule` DTO(application-first per `project_application_first_runtime_authority` + per `src/factgraph/application/docs/README.md` 显式层级:`sdk → application → core`)
  - `src/factgraph/core/rules/where_ast.py` — atom IR primitives(`PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom` / `Var` / `Const`)— `Rule.where` 内部存储 form
  - `src/factgraph/sdk/dsl/` — **完全不动**(包括 `expr.py` 的 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` / `BinaryExpr`)
- Related Docs:
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) — parent design essay §3.1-§3.14
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) — Track plan §2 T1 scope(T1.2 已扩 — absorb unified authoring syntax + DSL ergonomic extension)
- Audit Log:
  - [2026-05-22_t1-1-rule-class-additive.audit.md](./2026-05-22_t1-1-rule-class-additive.audit.md)

## 1. Problem

Parent essay 2066 行 / ~100 commitments 的 §3 commits 25 项(C1-C21 + C45-C48):用户面 `Rule(id, version, desc, where, ports)`,5 字段,AND-only,unified atom canonical(`User(u).field == value`)。**当前 shipped state**:

- `factgraph.sdk.dsl.rule:Rule`(line 54)字段集与新设计不同(含 `select` / `head` / 与 Inference 紧耦合)
- `factgraph.core.rules.rule_ir:RuleSpec`(line 28)是 IR-level,使用 `select_vars` / `where` / `expose`,无 `ports` / `desc` 概念
- Atom 形态:shipped 接受多种 atom 写法(`User(u), u.field == ...` 两行式,`Pred(...)`,裸 AttrRef 比较)— 与 parent §3.5 unified canonical 不一致

### 1.1 Step 4.2 review 发现的 scope refinement(2026-05-22)

初稿 blueprint 误判 §3.5 F6 "复用现有 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` primitives" 这句的位置 — 这些名字来自 SDK DSL(`sdk/dsl/expr.py`),不是 core IR。Core IR 在 `core/rules/where_ast.py` 用 `PredAtom` / `CmpAtom` / `Var` / `Const` 形态。

此外,unified canonical 用户面 `User(u).field == value` 当前**SDK DSL 不支持**:
- `User(u)` 返回 `ExistsAtom`(`sdk/dsl/expr.py:174-178`),ExistsAtom **没有** `__getattr__`,所以 `User(u).field` 当场 raise AttributeError
- `User(...)` 中 Ellipsis 走 `build_entity_dsl_call`(line 240)直接 raise SDKDSLError(只接受单个 LogicVar)
- 要支持 unified syntax 必须改 `sdk/dsl/expr.py` + 可能改 `sdk/schema.py`

若 T1.1 同时承担(a)application Rule DTO + (b)SDK DSL ergonomic 扩展 + (c)DSL→core 归一,则违反 `sdk → application → core` 单向依赖,且 slice 规模扩大到本来 T1.1+T1.2 的合并量。

**Step 4.2 lock**:T1.1 **降级**(P1 finding 选 A1)— 只引入 application Rule DTO,`Rule.where` 内部存储 **core AST atoms**(来自 `core/rules/where_ast.py`);**不动 SDK DSL**;unified authoring syntax + DSL ergonomic 扩展全部下放到 **T1.2**(Track plan 已同步更新)。

### 1.2 T1.1 的角色

**Foundation**:在 application protocol layer 添加新 Rule DTO,与旧 SDK Rule **共存**,不动 SDK 表面。后续 sub-slice 全部以本 slice 引入的新 Rule 类作为锚点:

- **T1.2**(已扩 scope)— DSL ergonomic 扩展(`ExistsAtom.__getattr__` / Ellipsis / cross-entity ref)+ DSL→core 归一 bridge + 旧形态 hard-cut
- **T1.3** — 新旧 Rule 命名冲突方案 + SDK re-export
- **T1.4** — port + alias 锁定

## 2. Goals

- 在 `src/factgraph/application/protocol/rule.py` 引入 **新 `Rule` frozen dataclass**,5 字段(`id` / `version` / `desc` / `where` / `ports`)
- **`where` 内部存储 core AST atoms**:`tuple[Atom, ...]`,其中 `Atom = PredAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom`(直接复用 `core/rules/where_ast.py` 已 ship 的 types — `RuleRefAtom` **不在允许集合**,per parent C9 新 paradigm Rule 间不通过 atom 引用交互)
- **`ports` 显式声明**:`Mapping[str, Var]` — value 必须是 `core.rules.where_ast:Var`(SDK DSL `LogicVar` 不进 application 层)
- **Construction-time validation**:
  - id non-empty string;where non-empty tuple;ports non-empty Mapping
  - 每个 `Var` in `ports.values()` 必须在 `where` 内某个 atom 的 terms 中出现(防 dangling port)
  - desc 模板内 `%port_name` 引用必须在 `ports.keys()`(per C5)
  - where 中所有 atoms 必须是允许的 5 种 kind 之一(reject RuleRefAtom per C9)
- **`atom_ids` property**:positional format `<rule_id>:atom_<index>`(per C19)
- **`content_digest` property**:`sha256_hex(canonical_bytes(where, ports))`,跨进程 deterministic stable(per C68;复用 `core/protocol/digests.py` 若已存在,否则 inline)
- **`render_desc(bindings=None)` method**:`%port_name` 插值;未绑定时输出 `<port_name>` 占位(per C5);未声明 port 引用构造期 reject
- **Immutability**:frozen dataclass + `where: tuple[Atom, ...]`(tuple,非 list)+ `ports` 用 `MappingProxyType` 或等价 frozen mapping;recursively immutable
- **Application 层 export**:`src/factgraph/application/protocol/__init__.py` 新增 re-export `Rule` + `RuleValidationError`(本 slice **不**进 SDK `__all__`)
- **Tests**:`tests/application/protocol/test_rule.py` 新建,覆盖构造期校验 / 5 atom kinds 允许 / RuleRefAtom 拒绝 / port-var dangling 拒绝 / desc 模板校验 + 渲染 / atom_id 位置 / immutability / content_digest deterministic

## 3. Non-goals

- **不动 `src/factgraph/sdk/dsl/` 任何文件**(包括 `expr.py` / `rule.py` / `branch.py` / `expr.py` / `vars.py` / `errors.py`)
- **不为新 Rule 提供用户面 ergonomic 构造接口**(unified `User(u).field == value` 这类 sugar 全部在 T1.2 — SDK DSL 扩展 + DSL→core bridge 这一层)
- **不实现 DSL→core normalization**(T1.2 — 包括 `ExistsAtom` 去重 / cross-entity ref 提取 / anonymous `...` Var 生成 / DSL term lowering)
- **不动 `core/rules/rule_ir.py:RuleSpec`**(旧 IR,仍服务 shipped Rule)
- **不动 `sdk/dsl/rule.py:Rule`**(legacy Rule 仍可用 — T1.2 在新 Rule 路径上拒绝旧形态;旧 Rule 自身不动直到 T1.3 命名冲突方案锁定)
- **不动 `sdk/dsl/branch.py:Branch`**(Track 1 shipped Branch(id=...)— per parent C13 不重命名只重新定位)
- **不进 SDK `__all__`**(SDK re-export 在 T1.3 锁名后)
- **不引入 RuleExpr**(T3)
- **不引入 head / `.eval` / Semantics**(T4 / T5)
- **不引入 atom kind canonical 9-list 文档化**(T2.1 — T1.1 接受 core AST 已有的 5 kinds,9 kinds 名单标准化是 T2.1 的事)
- **不实现 `.as_(...)` occurrence alias**(T3.2)
- **不引入 `Rule.projection()` sugar**(T4.4)
- **不引入 `inspect.is_closed`**(T4.5)
- **不引入 `RuleExpr.inspect`**(T3.5)
- **不实现 ArithExpr / AggregateExpr** value-producing forms(T2.2 / T2.3 — `BuiltinAtom` 在本 slice 仅作 atom kind allowed,不扩 expression form 语义)

## 4. Current Context

### 4.1 当前实现入口(grounded 2026-05-22 review)

| 关注 | 文件:line | 说明 |
|---|---|---|
| 当前 SDK Rule(legacy) | `src/factgraph/sdk/dsl/rule.py:54` | 含 `select` / `where` / `head`;与 Inference 紧耦合;本 slice 不动 |
| 当前 SDK Branch(Track 1) | `src/factgraph/sdk/dsl/branch.py:13` | `Branch(id=...)` 稳定 inspect 身份;本 slice 不动 |
| 当前 SDK RuleRef | `src/factgraph/sdk/dsl/rule.py:16` | 跨 Rule 引用;parent §10.3 / C9 锁 ruleref 不存在于新 paradigm — 新 Rule 拒绝 RuleRefAtom |
| 当前 IR RuleSpec | `src/factgraph/core/rules/rule_ir.py:28` | `rule_id` / `version` / `select_vars` / `where` / `expose`;本 slice 不动 |
| **Core AST atom primitives** | `src/factgraph/core/rules/where_ast.py` | `PredAtom`(line 35)/ `RuleRefAtom`(line 42)/ `CmpAtom`(line 50)/ `InAtom`(line 58)/ `BuiltinAtom`(line 65)/ `NotAtom`(line 72)/ `Var`(line 20)/ `Const`(line 26);**本 slice 复用,不动** |
| Core AST Expr containers | `src/factgraph/core/rules/where_ast.py` | `AndExpr`(line 81)/ `OrExpr`(line 87)— T1.1 只用 atoms list,不直接消费 OrExpr |
| Core AST parse + lower | `src/factgraph/core/rules/where_ast.py:99-254` | `parse_where_ir_to_ast(where_ir)` / `lower_ast_to_where_ir(expr)` — T1.1 可借此从 IR tuple 反序列化 atoms 用于测试,本 slice 不扩此 API |
| SDK DSL primitives(完全不动)| `src/factgraph/sdk/dsl/expr.py` | `LogicVar`(line 36)有 `__getattr__` → AttrRef;`AttrRef`(line 101);`BinaryExpr`(line 129);`ExistsAtom`(line 175)**无 `__getattr__`**;`CompareExpr`(line 195);`NotExpr`;`HeadCall`;`PredAtom`(SDK 版,与 core 同名不同字段);`build_entity_dsl_call`(line 225)— Ellipsis 走此处 raise |
| Atom evaluator | `src/factgraph/core/rules/where_eval.py`(1135 LOC) | 评估机制,本 slice 不动 |
| SDK exports | `src/factgraph/sdk/__init__.py:34-78` | `__all__` 含旧 `Rule` / `RuleRef` / `Branch` / `Inference` / `Query` / `Pred` / `Not` / `vars`;本 slice **不动** |
| Application protocol __init__ | `src/factgraph/application/protocol/__init__.py` | 现有 re-export 含 derivation / entity / ingest / proofframe 等;本 slice 新增 `Rule` + `RuleValidationError` |
| Application 层 docs | `src/factgraph/application/docs/` | README.md + 01_overview_en.md;新 Rule 文档加入这里(非 `protocol/docs/`,不存在)|

### 4.2 当前已知约束

- **Sacred branch isolation**:`master` / `v0.1-oss-prep` 不动
- **Dirty 集保留**:4 modified + 1 untracked 全程保留
- **依赖方向**:`sdk → application → core`(per `application/docs/README.md` 明确)— **T1.1 application Rule 不导入 sdk.dsl 任何类型**;`where` 内部存储类型限于 `core.rules.where_ast.Atom`
- **Application-first**:`feedback_application_first_runtime_authority` — DTO + pure function 在 application 层;SDK 只作 ergonomic shell(本 slice 不建 SDK shell)
- **Narrow public API**:`feedback_narrow_public_api` — 本 slice 不暴露到 SDK `__all__`
- **Invariant defense in depth**:frozen Rule + tuple where + frozen mapping ports;recursively immutable
- **Parent essay deviation**:essay §3.5 F6 写 "复用 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` primitives" 是 SDK DSL 角度;本 slice 用更深一层 core AST(`PredAtom` / `CmpAtom`)作为 Rule.where 的存储类型 — **架构改进,不破坏 essay 意图**;essay 意图是"复用现有 primitive,不重写 IR",本 slice 复用 core IR 而非 SDK DSL,deviation 记录于 §10

### 4.3 当前相关历史蓝图

| Blueprint | 路径 | 关系 |
|---|---|---|
| Track 1 Branch identity + rule inspect | `workflow/blueprints/archive/2026-05-12_*branch-identity*.md` | shipped Branch(id=...)— 本 slice 不动 |
| Track 3 SemanticsProfile 完整链 | `workflow/blueprints/archive/2026-05-12_*semantics*.md` | 与本 slice 正交 — Rule 本身不涉及 semantics |
| Slice 7C registry final removal | `workflow/blueprints/archive/2026-05-21_*registry-final*.md` | 移除了 filesystem RuleRegistry adapter;新 Rule 在 application 层与之解耦 |

## 5. Proposed Shape

### 5.1 新文件 / 模块结构

```
src/factgraph/application/protocol/
├── rule.py                  (新文件 ~180-250 LOC)
│   ├── class Rule           (frozen dataclass,5 字段 + atom_ids/content_digest properties + render_desc method)
│   ├── class RuleValidationError (per slice domain exception)
│   ├── _validate_where      (atom kind allowlist + port var reachability)
│   ├── _validate_ports      (Var 类型 + 不为 anonymous)
│   ├── _validate_desc       (desc 模板校验:%port_name 引用必须在 ports)
│   ├── _compute_content_digest (canonical bytes → sha256_hex;deterministic 跨进程)
│   └── (no normalization / dedup / cross-entity ref logic — all in T1.2)
└── __init__.py              (现有文件,新增 re-export `Rule` + `RuleValidationError`)

src/factgraph/application/docs/
├── README.md                (现有,加 §pointing 到新文件)
└── rule.md                  (新文件 ~80-120 行,说明新 Rule DTO 形态 + 与旧 SDK Rule 区分 + 待 T1.2 DSL ergonomic 引入后用户可用)
```

### 5.2 Rule 类公开形态(伪 API)

```python
from typing import Any, Mapping
from types import MappingProxyType
from dataclasses import dataclass, field

from factgraph.core.rules.where_ast import Atom, Var, PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom


class RuleValidationError(Exception):
    """T1.1 Rule 构造期校验失败的 domain exception。"""


_ALLOWED_ATOM_TYPES = (PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)
# RuleRefAtom 显式不允许(parent C9 新 paradigm Rule 间不通过 atom 引用交互)


@dataclass(frozen=True)
class Rule:
    """Atomic AND-only rule, per parent essay §3 (C1-C21 + C45-C48).

    Stores core AST atoms directly (from core/rules/where_ast.py).
    SDK DSL ergonomic authoring + DSL→core normalization is T1.2 scope.

    Construction-time validation only. No evaluation. No DSL types accepted.
    """

    id: str
    where: tuple[Atom, ...]
    ports: Mapping[str, Var]
    version: str | None = None
    desc: str | None = None

    def __post_init__(self) -> None:
        # validate 5 fields + atom-kind allowlist + port reachability + desc template
        ...

    @property
    def atom_ids(self) -> tuple[str, ...]:
        """Positional atom_id list: `<id>:atom_<index>` (per C19)."""

    @property
    def content_digest(self) -> str:
        """Canonical sha256 hex of (where, ports). Deterministic across processes (per C68)."""

    def render_desc(self, bindings: Mapping[str, Any] | None = None) -> str:
        """Render desc template with %port_name interpolation. Unbound -> '<port_name>' literal (per C5)."""
```

### 5.3 接受 / 拒绝形态

**T1.1 本 slice 在新 Rule.where 内只接受 core AST atom types。** 用户不能在 T1.1 直接写 `User(u).field == value`(那是 SDK DSL 形态;DSL → core normalization 在 T1.2 才落地)。

| Atom 类型 | 来源 | T1.1 行为 |
|---|---|---|
| `PredAtom(pred_id, terms)` | `core.rules.where_ast` | ✓ 接受 |
| `CmpAtom(op, lhs, rhs)` | `core.rules.where_ast` | ✓ 接受 |
| `InAtom(var, values)` | `core.rules.where_ast` | ✓ 接受 |
| `BuiltinAtom(op, args)` | `core.rules.where_ast` | ✓ 接受(本 slice 不扩 ArithExpr 语义;仅 atom kind allowed)|
| `NotAtom(body)` | `core.rules.where_ast` | ✓ 接受 |
| `RuleRefAtom(rule_id, ...)` | `core.rules.where_ast` | ✗ **构造期 raise RuleValidationError**(parent C9 新 paradigm Rule 间不通过 atom 引用交互)|
| `ExistsAtom` / `AttrRef` / `CompareExpr` 等 SDK DSL types | `sdk.dsl.expr` | ✗ **不接受**(application 层不导入 SDK DSL 类型)— 用户若试图传入,Python type check 失败或 `_validate_where` raise |
| `User(u).field == value` 类 unified syntax | SDK DSL ergonomic(尚未实现)| ✗ **shipped DSL 当前不支持**(`ExistsAtom` 无 `__getattr__`)— T1.2 范围 |
| `User(u), u.field == value`(两行式)| 当前 shipped DSL | ✗ T1.1 不接受(SDK DSL atoms 都不进 T1.1);**legacy 旧 Rule 仍接受此形态,T1.2 hard-cut**|
| `Pred("user:status", u, "active")` | 当前 shipped SDK DSL | ✗ 同上 |

> **P4 wording fix**:旧 SDK Rule **不 reject** 上述形态(legacy path 仍工作);新 application Rule **构造期 reject**(只接受 core AST 5 kinds)。

### 5.4 不在本 slice 实现的(留 T1.2)

- Anonymous `...`(Python Ellipsis)→ anonymous `Var` 生成(per C45)— **DSL ergonomic 扩展,T1.2 实施**
- `User(u).field == value` unified syntax 接受(需要 `ExistsAtom.__getattr__` 改造,T1.2)
- 跨 entity field ref `LivesIn(li).user == User(u)`(需要 DSL → core 提取与 dedup,T1.2)
- `ExistsAtom` 同 `(entity_type, var)` 去重(T1.2 — 当前 T1.1 用户直接写 core AST,不会出现需要 dedup 的语法形态)
- 拒绝 legacy 2-line / `Pred(...)` / 裸 AttrRef(T1.2 在 DSL→new Rule path 上 hard-cut)

### 5.5 Ports 类型推断(简化版,T1.1 仅 entity_ref / value 二分)

构造期 walk `where` atoms,对每个 `port_name → port_var`:

- 若 `port_var` 出现在 `PredAtom("XYZ:exists", [..., port_var, ...])`(模式 `EntityType:exists` 的 pred_id)→ port kind = `entity_ref`,entity_type = 从 pred_id 解析
- 否则 → port kind = `value`(value_type 留 T1.4 / T3.5 PortInspect 扩展)

T1.1 内部存储 port 类型 hint 即可(简单 dict 或 `MappingProxyType`),不暴露 PortInspect rich 表面(那是 T3.5)。

### 5.6 `__init__.py` 集成

```python
# src/factgraph/application/protocol/__init__.py 现有 + 新增
from .rule import Rule, RuleValidationError

__all__ = [
    # ... existing exports ...
    "Rule",                   # 新增(application protocol layer;不进 SDK __all__)
    "RuleValidationError",    # 新增
]
```

**注**:`factgraph.application.protocol.Rule` 与 `factgraph.sdk.Rule`(legacy)共存,不同 module 路径,语义不同 — T1.3 决定 SDK 表面的 Rule 名最终归属。

### 5.7 测试结构

```
tests/application/protocol/
├── test_rule.py             (新文件,~250-350 LOC)
│   ├── TestRuleConstruction (5 字段必需 / non-empty / 类型校验)
│   ├── TestAtomKindAllowlist (5 allowed kinds pass / RuleRefAtom rejected / SDK DSL types rejected)
│   ├── TestPortValidation   (ports key/value 类型 / Var 必须在 where 出现 / 无 port reachability)
│   ├── TestDescRender       (模板态 %port / 绑定态 / 未声明 port 引用 reject / 多 port 插值)
│   ├── TestAtomId           (positional 格式 `<id>:atom_<index>`)
│   ├── TestImmutability     (frozen / tuple / ports MappingProxyType)
│   ├── TestContentDigest    (相同 where+ports → 同 digest / atom 顺序不同 → 不同 digest / 跨进程 deterministic)
│   └── TestPortKindInference (entity_ref via pred `XYZ:exists` / value 其他)
```

预估 ~250-350 LOC tests。

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - **不**动 `src/factgraph/sdk/dsl/` 任何文件
  - **不**动 `src/factgraph/sdk/__init__.py` 的 `__all__`
  - **不**动 `src/factgraph/core/rules/rule_ir.py:RuleSpec`
  - **不**动 `src/factgraph/core/rules/where_ast.py`(只**消费**已 ship 的 types)
  - **不**动 atom evaluator(`where_eval.py`)
  - **不**动现有 tests
- **明确不做的内容**:
  - DSL ergonomic syntax(T1.2)
  - DSL → core normalization / dedup / cross-entity ref(T1.2)
  - Legacy 形态 hard-cut(T1.2)
  - Atom kind canonical 9-list 文档化(T2.1)
  - RuleExpr / head / `.eval` / Semantics(T3 / T4 / T5)
- **兼容性约束**:
  - 旧 SDK `from factgraph.sdk import Rule` 仍工作,返回旧 `sdk.dsl.Rule`
  - 新 user 用 `from factgraph.application.protocol import Rule` 获得新 Rule
  - 这两条不冲突(不同 module 路径 + 不同语义)
- **Invariants**:
  - 构造期所有失败 → `RuleValidationError`(domain exception);不抛 generic `ValueError` / `TypeError`
  - `where: tuple[Atom, ...]` outer container immutable(无法替换 tuple 本身)+ atom 顺序固定(stable order = 用户传入顺序;atom_id positional)
  - `ports` 通过 `MappingProxyType` 或等价 frozen mapping 保持 outer immutable(无法 setitem / delitem;`ports` values 是 `Var` 已经 frozen,内部无 list)
  - **Shallow immutability only**(per Step 4.2 v2 P1 finding):`PredAtom.terms` / `InAtom.values` / `BuiltinAtom.args` / `NotAtom.body` 等 core AST atom 内部仍是 mutable lists(shipped `core/rules/where_ast.py` 现状)。`frozen=True` dataclass 仅冻结 attribute 赋值,不冻结 list 内容 — 故 Rule 实例的 **container shallow immutable**,not recursively。Recursive immutability hardening **deferred**(留给后续 T1 sub-slice 或 dedicated hardening slice;**违反 `feedback_invariant_defense_in_depth` 已知,user 在 Step 4.2 v2 review 显式选择此 trade-off 以保持 T1.1 atomic — 不修改 shipped core AST types 为前提**)
  - `content_digest` 基于 canonical serialization,跨进程 deterministic
  - **依赖方向**:`application.protocol.rule` 只 import `core.rules.where_ast`(forward),**不**import `sdk.*`(no reverse)

## 7. Acceptance

- [ ] `factgraph.application.protocol.Rule` 类存在且可 import
- [ ] 5 允许 core atom kinds(`PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom`)构造通过(5 个 unit tests pass)
- [ ] `RuleRefAtom` 在 `where` 内构造期 raise `RuleValidationError`(1 个 negative test pass)
- [ ] SDK DSL types(若用户尝试传入 `ExistsAtom` / `AttrRef` 等)构造期 raise(2 个 negative tests pass)
- [ ] Ports 校验:value 必须是 `core.rules.where_ast.Var`(1 unit test);Var 必须在 where 出现(1 unit test)
- [ ] Desc rendering:模板态 / 绑定态 / 未声明 port 引用 reject 三场景(3 unit tests pass)
- [ ] Atom_id positional 格式 `<rule_id>:atom_<index>`(1 unit test pass)
- [ ] Rule **shallow** immutability:frozen `setattr` 失败 + `where` tuple 无法替换 + `ports` MappingProxyType 无法 setitem(3 unit tests pass)— **note**:atom 内部 list mutability per shipped core AST,recursive immutability deferred(§6 已声明)
- [ ] `content_digest` deterministic + atom 顺序影响 digest(2 unit tests pass)
- [ ] Port kind 推断:entity_ref via pred `XYZ:exists` / 其他 → value(2 unit tests pass)
- [ ] 旧 `factgraph.sdk.Rule` legacy 仍工作,所有现有 tests pass(non-regression)
- [ ] `src/factgraph/application/docs/rule.md` 新文件存在;`application/docs/README.md` 含指向新 doc 的入口
- [ ] `src/factgraph/application/protocol/__init__.py` re-export `Rule` + `RuleValidationError`
- [ ] **`workflow/CADENCE.md` 中 sacred branch isolation + dirty 集保留 + 单 small commit per phase 全程遵守**
- [ ] 依赖方向静态可验证:`grep "from factgraph.sdk" src/factgraph/application/protocol/rule.py` 返回空(无反向依赖)

## 8. Implementation Plan

> **轻量 cadence 模式**(per Track plan §1.2):跳过 Step 4.3 preflight / Step 4.5 self-check 独立 commits;主路径 draft → scoped → impl + tests + docs → closure → archive。

1. **[blueprint] Step 4.1 draft commit**:已落 — `1f57b61f`(initial draft,P1-P4 review 前)
2. **[blueprint] Step 4.2 review tightening commit**:本 commit。Apply P1+P2 (Option A1 scope degrade) + P3 (docs path) + P4 (§5.3 wording);blueprint + audit log + Track plan T1.2 row 同步。
3. **[blueprint] Step 4.6 scoped anchor commit**:`Status: draft` → `Status: scoped` + audit log event "scoped";只动 Status + audit log。
4. **[impl] 主 feat commit**:
   - 新建 `src/factgraph/application/protocol/rule.py`(~180-250 LOC,DTO only)
   - 新建 `tests/application/protocol/test_rule.py`(~250-350 LOC)
   - 更新 `src/factgraph/application/protocol/__init__.py`(re-export)
   - 新建 `src/factgraph/application/docs/rule.md`
   - 更新 `src/factgraph/application/docs/README.md` 加入口
5. **[impl] 可能的 fix commit**(如果 Step 4.7 review surface P1):仅在 reviewer surface 时;否则 skip。
6. **[closure] Step 4.8 closure commit**:`Status: scoped` → `Status: implemented` + `§10 Outcome` 填齐 + audit log event "implemented"。
7. **[archive] Step 4.9 archive commit**:`git mv` 蓝图 pair `active/` → `archive/`;basename 不变。

**预估总 commits**:5-6(draft `1f57b61f` / tightening 本commit / scoped / impl-feat / [optional fix] / closure + archive 可合并)。

## 9. Docs To Update

- **新建** `src/factgraph/application/docs/rule.md`(~80-120 行)— 描述:
  - 新 `Rule(id, version, desc, where, ports)` 5 字段语义
  - `where` 内部存储类型(core AST atom kinds:`PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom`;**不含** `RuleRefAtom`)
  - 与旧 `factgraph.sdk.Rule` 的明确区分(新旧共存,语义不同,T1.3 决定 SDK 表面归属)
  - **DSL ergonomic 用户面入口尚未提供**(T1.2 实施),T1.1 用户必须直接构造 core AST atoms
- **更新** `src/factgraph/application/docs/README.md` — 加 §pointing 到新 `rule.md`
- **不更新** `docs/README.md`(本 slice 不引入新持久公开文档入口;application/docs/ 是 application-internal)
- **不更新** `src/factgraph/sdk/docs/`(本 slice 不动 SDK 表面)
- **不更新** `docs/official/kernel/quickstart/`(本 slice 不动公开 quickstart;新 Rule 用户面 ergonomic 入口 T1.2 后才上)

## 10. Outcome / Deviations

待 implementation 完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- **Parent essay deviation** — essay §3.5 F6 写 "复用 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` primitives" 是 SDK DSL 角度;本 slice 用更深一层 core AST(`PredAtom` / `CmpAtom`)作为 `Rule.where` 存储类型。理由:依赖方向(`sdk → application → core`)+ slice 原子性(application 层不导入 SDK DSL)。Essay 高层意图(复用现有 primitive,不重写 IR)保留 — 只是复用方向变为 core 而非 SDK。Deviation 不引入新 commitment,Track plan 已同步更新(T1.2 absorb DSL ergonomic 扩展)。
- **Recursive immutability deferred**(per Step 4.2 v2 P1 finding)— T1.1 Rule 仅 shallow immutable;`PredAtom.terms` / `InAtom.values` / `BuiltinAtom.args` 等 core AST 内部 list 保持 shipped 现状(mutable)。这是 `feedback_invariant_defense_in_depth` 已知 trade-off,user 选择以保 slice atomic 不修改 shipped core AST。后续 immutability hardening slice 触发条件:出现实际 mutation 漂移事件 / 跨 Rule 构造-evaluation 之间 atom internals 被改的 bug / 用户社区报告。
- 归档说明:
