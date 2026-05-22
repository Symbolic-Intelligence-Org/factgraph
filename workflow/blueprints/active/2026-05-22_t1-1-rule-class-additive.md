# T1.1 — Additive 新 Rule 类(application protocol layer + unified atom canonical)

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Track: T1 Rule body 重塑(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))
- Related Modules:
  - `src/factgraph/application/protocol/` — new home for `Rule` DTO(application-first per `project_application_first_runtime_authority`)
  - `src/factgraph/core/rules/where_eval.py` / `where_ast.py` — atom IR primitives (`ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar`)reused without modification
  - `src/factgraph/sdk/dsl/rule.py` — current shipped Rule(line 54)**untouched** in this slice
- Related Docs:
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) — parent design essay §3.1-§3.14
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) — Track plan §2 T1 scope
- Audit Log:
  - [2026-05-22_t1-1-rule-class-additive.audit.md](./2026-05-22_t1-1-rule-class-additive.audit.md)

## 1. Problem

Parent essay 2066 行 / ~100 commitments 的 §3 commits 25 项(C1-C21 + C45-C48):用户面 `Rule(id, version, desc, where, ports)`,5 字段,AND-only,unified atom canonical(`User(u).field == value`)。**当前 shipped state** 与该承诺差异:

- Shipped `sdk.dsl.Rule`(src/factgraph/sdk/dsl/rule.py:54)字段集与新设计不同(含 `select` / `head` / 与 Inference 紧耦合)
- Shipped `core.rules.RuleSpec`(src/factgraph/core/rules/rule_ir.py:28)是 IR-level,使用 `select_vars` / `where` / `expose`,无 `ports` / `desc` 概念
- Atom canonical:shipped 接受多种 atom 写法(`User(u), u.field == ...` 两行式,`Pred(...)`,裸 AttrRef 比较)— 与 parent §3.5 unified canonical 不一致(此处仅做 additive 引入,**hard-cut 在 T1.2**)

T1.1 的角色是 **foundation**:在 application protocol layer 添加新 Rule 类,与旧 SDK Rule **共存**,不动旧 surface。后续 T1.2-T1.4 + T2/T3/T4/T5 全部以本 slice 引入的新类作为锚点。

## 2. Goals

- 在 `src/factgraph/application/protocol/rule.py` 引入 **新 `Rule` frozen dataclass**,5 字段(`id` / `version` / `desc` / `where` / `ports`),AND-only;构造期校验
- **Unified atom canonical 构造期 normalization**:接受 `EntityType(var).field == value` 形态,平展为现有 IR primitives(`ExistsAtom` / `AttrRef` / `CompareExpr`)的 list — parent §3.5 F6 锁定的 ~50-75 行 lowering 扩展
- **构造期 dedup**:同 `(entity_type, var)` 的 `ExistsAtom` 去重保留单份(per §3.5 F6)
- **新增 lowering case**:`CompareExpr` 的 RHS 为 `ExistsAtom` 时(跨 entity field 引用,如 `LivesIn(li).user == User(u)`),提取 Var 并把 ExistsAtom 加入 atoms 列表
- **Anonymous `...` (Python Ellipsis)** 处理:每次 `EntityType(...)` 调用产生独立 anonymous `LogicVar`;anonymous Var 不可声明为 port — 构造期校验(per C45)
- **Ports 显式声明**:不自动收集 free var;`ports` dict 显式给入;**port 类型自动从 atom 推断**(per C7 / C8)
- **Desc rendering**:`%port_name` 插值;引用未声明 port → 构造期 reject;未绑定 render → 输出 `<port_name>` 占位(per C5)
- **Immutability**:frozen dataclass,构造后所有字段不可改;atom 顺序固定为 atom_id 位置锚(per C17 / C18)
- **Atom ID 格式**:`<rule_id>:atom_<index>`(positional,per C19)
- **应用层 export**:`factgraph.application.protocol.__init__.py` re-export `Rule`(本 slice 不进 SDK `__all__`)
- **Tests**:新 module 完整单元测试覆盖 — 构造期校验 / atom normalization 7 种允许形态 / dedup / cross-entity ref / anonymous `...` / port type inference / desc render template+bound / immutability / atom_id

## 3. Non-goals

- **不动 `sdk/dsl/rule.py:Rule` 类**(legacy 2-line / `Pred(...)` / 裸 AttrRef 仍可用 — hard-cut 在 T1.2)
- **不动 `core/rules/rule_ir.py:RuleSpec`**(旧 IR,仍服务 shipped Rule)
- **不动 `sdk/dsl/branch.py:Branch`**(Track 1 shipped Branch(id=...)— per parent C13 不重命名只重新定位)
- **不进 SDK `__all__`**(SDK re-export 在 T1.3 锁名后)
- **不改 atom IR primitives**(`ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` 形态不变)
- **不引入 RuleExpr**(T3)
- **不引入 head / `.eval` / Semantics**(T4 / T5)
- **不引入 atom kind canonical 9-list 文档化**(T2.1)
- **不实现 `.as_(...)` occurrence alias**(T3.2 — 但本 slice 需为后续 alias 留 alias-stable atom_id 接口)
- **不引入 `Rule.projection()` sugar**(T4.4)
- **不引入 `inspect.is_closed`**(T4.5)
- **不引入 `RuleExpr.inspect`**(T3.5)
- **不实现 `.atoms` / `eval_atom` Phase 2 introspection 表面**(per parent C16,Phase 2 evidence interpreter 范围;v1 由 atom_id + AtomDescriptor schema 在 T3.5 锁定)

## 4. Current Context

### 4.1 当前实现入口

| 关注 | 文件:line | 说明 |
|---|---|---|
| 当前 SDK Rule | `src/factgraph/sdk/dsl/rule.py:54` | 含 `select` / `where` / `head`;与 Inference 紧耦合 |
| 当前 SDK Branch(Track 1) | `src/factgraph/sdk/dsl/branch.py:13` | `Branch(id=...)` 稳定 inspect 身份,本 slice 不动 |
| 当前 SDK RuleRef | `src/factgraph/sdk/dsl/rule.py:16` | 跨 Rule 引用;parent §10.3 / C9 锁 ruleref 不存在 — 但 T1.1 不动 |
| 当前 IR RuleSpec | `src/factgraph/core/rules/rule_ir.py:28` | `rule_id` / `version` / `select_vars` / `where` / `expose` |
| Atom IR primitives | `src/factgraph/core/rules/where_ast.py` + `where_ast_validate.py` | `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` |
| Atom evaluator | `src/factgraph/core/rules/where_eval.py`(1135 LOC) | 评估机制,不动 |
| SDK exports | `src/factgraph/sdk/__init__.py:34-78` | `__all__` 含旧 `Rule` / `RuleRef` / `Branch` / `Inference` / `Query` / `Pred` / `Not` / `vars` |

### 4.2 当前已知约束

- **Sacred branch isolation**:`master` / `v0.1-oss-prep` 不动
- **Dirty 集保留**:4 modified + 1 untracked(`docs/references/working/design-points/readme.md`、3 example notebooks、`rainbird-ai sdk code/`)— 整个 slice 期间不动
- **Application-first**:`feedback_application_first_runtime_authority` — 新 Rule 必须先在 `factgraph.application` 落地 DTO + pure function;SDK 只作 ergonomic shell
- **Narrow public API**:`feedback_narrow_public_api` — 本 slice **不**暴露到 SDK `__all__`(SDK 暴露在 T1.3)
- **Invariant defense in depth**:`feedback_invariant_defense_in_depth` — frozen Rule 内部所有字段必须 recursively immutable(`where` list → tuple,`ports` dict → frozen mapping 或 tuple-of-tuples)

### 4.3 当前相关历史蓝图

| Blueprint | 路径 | 关系 |
|---|---|---|
| Track 1 Branch identity + rule inspect | `workflow/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md`(待 inventory 确认)| shipped Branch(id=...)— 本 slice 不动 |
| Track 3 SemanticsProfile 完整链 | `workflow/blueprints/archive/2026-05-12_*semantics*.md` | 与本 slice 正交 — Rule 本身不涉及 semantics |
| Track 3-post:Rule inspect + branch identity | 见 archive | 提供 `RuleInspect`,与本 slice 共存 |

## 5. Proposed Shape

### 5.1 新文件 / 新模块

```
src/factgraph/application/protocol/
├── rule.py                  (新文件 ~250-350 LOC)
│   ├── class Rule           (frozen dataclass,§3 5 字段 + 内部 atoms tuple + 内部 atom_ids)
│   ├── class RuleValidationError (per slice domain exception)
│   ├── _normalize_where     (~50-75 LOC unified atom canonical lowering)
│   ├── _infer_port_types    (port 类型从 atoms 推断)
│   ├── _validate_desc       (desc 模板校验:%port_name 引用必须在 ports)
│   ├── render_desc          (绑定/未绑定双形态)
│   └── _build_atom_ids      (positional `<rule_id>:atom_<index>`)
└── __init__.py              (现有文件,新增 re-export `Rule` from .rule)
```

**Rule 类公开形态**(伪 API):

```python
@dataclass(frozen=True)
class Rule:
    id: str                       # 必需,non-empty
    where: tuple[Atom, ...]       # 必需 atoms list(构造后转 tuple,immutable)
    ports: Mapping[str, LogicVar] # 必需 dict;value 必须是 LogicVar
    version: str | None = None    # 可选 free-form
    desc: str | None = None       # 可选,支持 %port 插值

    @property
    def atom_ids(self) -> tuple[str, ...]: ...  # positional <id>:atom_<index>

    @property
    def content_digest(self) -> str: ...  # canonical digest of (where, ports);供 T4.2 (id, content_digest) 双匹配使用

    def render_desc(self, bindings: Mapping[str, Any] | None = None) -> str: ...
```

### 5.2 Unified atom canonical 输入形态(per §3.5,T1.1 接受这 7 种)

| # | 形态 | normalize 输出 |
|---|---|---|
| 1 | `User(u)` | `[ExistsAtom(User, u)]` |
| 2 | `User(u).user_id == "u-2"` | `[ExistsAtom(User, u), CompareExpr(AttrRef(u, "user_id"), "==", "u-2")]` |
| 3 | `User(u).status == "active"` | `[ExistsAtom(User, u), CompareExpr(AttrRef(u, "status"), "==", "active")]` |
| 4 | `User(u).score > 0.5` | `[ExistsAtom(User, u), CompareExpr(AttrRef(u, "score"), ">", 0.5)]` |
| 5 | `User(...).name == "alice"` | `[ExistsAtom(User, anon_var), CompareExpr(AttrRef(anon_var, "name"), "==", "alice")]`(anon_var 每次独立) |
| 6 | `LivesIn(li).user == User(u)` | `[ExistsAtom(LivesIn, li), ExistsAtom(User, u), CompareExpr(AttrRef(li, "user"), "==", u)]` — RHS entity ref 提取并 dedup |
| 7 | `LivesIn(li).country == country` | `[ExistsAtom(LivesIn, li), CompareExpr(AttrRef(li, "country"), "==", country)]`(`country` 是命名 Var) |

**Dedup 规则**:对同 `(entity_type, var)` 的 `ExistsAtom`,保留首次出现,移除后续重复。

### 5.3 拒绝形态(本 slice **不 reject**,留给 T1.2)

T1.1 在新 Rule 类内部 normalize **只接受**上面 7 种 unified 形态。若用户传入旧形态,**抛 `RuleValidationError`**(构造期),但**不动旧 SDK Rule**。

| 形态 | T1.1 行为 | T1.2 行为(预告) |
|---|---|---|
| 新 Rule 中传 `u.field == value`(裸 AttrRef) | T1.1 构造期 raise | 旧 SDK Rule 现行接受;T1.2 在旧 Rule 拒绝 |
| 新 Rule 中传 `User(u), u.field == value`(两行式) | T1.1 构造期 raise | 同上 |
| 新 Rule 中传 `Pred("user:status", u, "active")` | T1.1 构造期 raise | 同上 |
| 旧 SDK Rule 用上述形态 | **不受影响**(本 slice 不动旧 SDK Rule) | T1.2 hard-cut |

### 5.4 LogicVar 与 anonymous `...` 处理

- 用户使用 `vars("u", "c")` 等(现行 SDK API)显式声明命名 LogicVar
- 用户使用 `User(...)` / `Country(...)` 中的 `...`(Python Ellipsis)触发 anonymous LogicVar 生成 — 每次出现独立
- Anonymous LogicVar 内部存在但无 stable 名;构造期校验:**anonymous Var 不能出现在 `ports` dict value 中**;违反 raise

### 5.5 Ports 类型推断

构造期 walk normalized atoms:

- 若 `port_var` 出现在 `ExistsAtom(EntityType, port_var)` → port 类型 = `EntityType`
- 若 `port_var` 只出现在 `CompareExpr(AttrRef(_, _), op, port_var)` → port 类型 = value type(从 schema 字段推断;可能 deferred 到 T1.4 完整实施;**T1.1 至少存储 hint**)

T1.1 仅需:
- entity-mediated port → `kind="entity_ref", entity_type="User"`
- value port → `kind="value", entity_type=None`(value_type / field 留 T1.4 / T3.5 PortInspect 扩展)

### 5.6 `__init__.py` 集成

```python
# src/factgraph/application/protocol/__init__.py 现有 + 新增
from .rule import Rule, RuleValidationError

__all__ = [
    # ... existing exports ...
    "Rule",                   # 新增
    "RuleValidationError",    # 新增
]
```

**注**:这里 `Rule` 名在 `factgraph.application.protocol` 命名空间;SDK 命名空间 `factgraph.sdk.Rule` 仍指向旧 `sdk.dsl.Rule`(本 slice 不动)。新旧二者不冲突(不同模块路径)。

### 5.7 测试结构

```
tests/application/protocol/
├── test_rule.py             (新文件)
│   ├── TestRuleConstruction (5 字段校验 / 必需字段 / non-empty / 类型)
│   ├── TestAtomNormalization (7 unified 形态 / dedup / cross-entity ref / 拒绝形态)
│   ├── TestAnonymousVar     (`...` 独立性 / anonymous 不能是 port)
│   ├── TestPortInference    (entity_ref / value port 推断)
│   ├── TestDescRender       (模板态 / 绑定态 / 未声明 port 引用 reject)
│   ├── TestAtomId           (positional 格式)
│   ├── TestImmutability     (frozen dataclass / atoms tuple 不可改)
│   └── TestContentDigest    (相同 where+ports → 同 digest;atom 顺序不同 → 不同 digest per §3.11 atom 顺序作为 atom_id 锚点)
```

预估 ~300-400 LOC tests。

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - 不动 `src/factgraph/sdk/dsl/` 任何文件(包括 `rule.py` / `branch.py` / `expr.py` / `vars.py` / `errors.py`)
  - 不动 `src/factgraph/core/rules/rule_ir.py:RuleSpec`
  - 不动 atom IR primitives 的 type signatures(`ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar`)
  - 不动 `src/factgraph/sdk/__init__.py` 的 `__all__`(SDK 表面不变)
  - 不动现有 tests(无现有 test 应该因本 slice 而失败 — 新 Rule 类不被现有代码消费)
- **明确不做的内容**:
  - **不**实现 atom kind canonical 9-list 标准化(T2.1 范围 — T1.1 用现有 IR primitives 平展,不引入 atom kind enum)
  - **不**实现 RuleExpr 组合(T3)
  - **不**实现 head / `.eval` / Semantics(T4 / T5)
  - **不**为新 Rule 添加 `save` / `load` / persistence(per parent §3.10 v1 ephemeral;v2 SavedRule deferred)
  - **不**实现 `branches` property(per parent C12 `branch` 词退为 evidence rendering 内部词汇;v1 新 Rule 不暴露 branches)
- **兼容性约束**:
  - 旧 SDK `from factgraph.sdk import Rule` 仍工作,返回旧 `sdk.dsl.Rule`
  - 新 user 用 `from factgraph.application.protocol import Rule` 获得新 Rule
  - 这两条不冲突 — 不同 module 路径 + 不同语义
- **Invariants**:
  - 新 Rule 构造期所有失败 → `RuleValidationError`(domain exception);**不抛 generic `ValueError` / `TypeError`**
  - normalized atoms 列表是 **stable order**(用户写入顺序);atom_id 由位置生成;atom 顺序不影响语义但影响 atom_id 与 content_digest
  - `frozen=True` + `where: tuple[Atom, ...]` + `ports: Mapping[...]`(MappingProxyType 或 frozen 等价)— recursively immutable
  - `content_digest` 计算用 canonical serialization(per `core/protocol/digests.py` 现有工具)— deterministic 跨进程

## 7. Acceptance

- [ ] `factgraph.application.protocol.Rule` 类存在且可 import
- [ ] 7 种 unified atom 形态都能 normalize 到 IR primitives 列表(7 个 unit tests pass)
- [ ] 旧 atom 形态(裸 AttrRef / 两行式 / Pred)在新 Rule 内构造时 raise `RuleValidationError`(3 个 negative tests pass)
- [ ] Anonymous `...` 每次出现独立 + anonymous 不能是 port(2 个 unit tests pass)
- [ ] Ports 类型推断:entity_ref / value 两种 kind 正确(2 个 unit tests pass)
- [ ] Desc rendering:模板态 / 绑定态 / 未声明 port 引用 reject 三场景(3 个 unit tests pass)
- [ ] Atom_id positional 格式 `<rule_id>:atom_<index>`(1 个 unit test pass)
- [ ] Rule frozen / atoms tuple 不可改(2 个 immutability tests pass)
- [ ] `content_digest` deterministic + 跨进程 stable + atom 顺序影响 digest(3 个 unit tests pass)
- [ ] 旧 `factgraph.sdk.Rule`(legacy)仍工作,所有现有 tests pass(non-regression)
- [ ] 受影响模块 docs 已同步 — `src/factgraph/application/protocol/docs/` 新增 `rule.md`(或并入既有 docs)说明新 Rule
- [ ] **不**新增 docs/README.md 持久入口(本 slice 是 application-internal 引入)
- [ ] 跨 entity ref 形态 6(`LivesIn(li).user == User(u)`)能 dedup ExistsAtom 并产出 3-element 平展(1 个 unit test pass)
- [ ] **`workflow/CADENCE.md` 中 sacred branch isolation + dirty 集保留 + 单 small commit per phase 全程遵守**

## 8. Implementation Plan

> **轻量 cadence 模式**(per Track plan §1.2):本 slice 跳过 Step 4.3 preflight / Step 4.5 self-check 独立 commits — 这些子步骤折叠到 Step 4.7 impl 的内部 review;blueprint draft → scoped → impl + tests + docs → closure → archive 主路径保留。

1. **[blueprint] Step 4.1 draft commit**:本 commit。审阅 + 锁定 TPQ-1 partial(新 Rule 路径 = `factgraph.application.protocol.rule:Rule`)。
2. **[blueprint] Step 4.2 review tightening commit**(reviewer = 用户):surfaces P1-P4 findings,我 apply。
3. **[blueprint] Step 4.6 scoped anchor commit**:`Status: draft` → `Status: scoped` + audit log event "scoped";只动 Status 字段 + audit log。
4. **[impl] 主 feat commit**:
   - 新建 `src/factgraph/application/protocol/rule.py`(~250-350 LOC)
   - 新建 `tests/application/protocol/test_rule.py`(~300-400 LOC)
   - 更新 `src/factgraph/application/protocol/__init__.py`(re-export `Rule` + `RuleValidationError`)
   - 新建 `src/factgraph/application/protocol/docs/rule.md` 或并入既有 docs(说明新 Rule + unified atom canonical 接受形态)
5. **[impl] 可能的 fix commit**(如果 Step 4.7 review surface P1):仅在 reviewer surface 时;否则 skip。
6. **[closure] Step 4.8 closure commit**:`Status: scoped` → `Status: implemented` + `§10 Outcome` 填齐 + audit log event "implemented"。
7. **[archive] Step 4.9 archive commit**:`git mv` 蓝图 pair `active/` → `archive/`;basename 不变;sibling audit 同时 mv。

**预估总 commits**:4-5(draft / scoped / impl-feat / [optional fix] / closure + archive 可合并)。

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/`(已存在 / 待查) — 新增或更新 `rule.md`,描述:
  - 新 `Rule(id, version, desc, where, ports)` 5 字段语义
  - 7 种 unified atom canonical 接受形态
  - Dedup + cross-entity ref + anonymous `...` 规则
  - Ports 类型推断 + desc rendering
  - **与旧 `factgraph.sdk.Rule` 的明确区分**(新旧共存,新在 application protocol layer,旧在 SDK DSL layer)
- **不更新** `docs/README.md`(本 slice 不引入新持久公开文档入口)
- **不更新** `src/factgraph/sdk/docs/`(本 slice 不动 SDK 表面)
- **不更新** `docs/official/kernel/quickstart/`(本 slice 不动公开 quickstart;新 Rule 在用户层尚未替代旧 Rule)

## 10. Outcome / Deviations

待 implementation 完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
