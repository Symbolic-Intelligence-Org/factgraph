# Entity / Field `repr` 模板 + 渲染解析 + inspect 查询表示

> **本文件状态**: draft (2026-06-04); 设计探索; 待 review / 多 session 修订
>
> **权威边界 (per `workflow/design/design-points/README.md`)**:
> 一个 design-point 是**候选设计 / 非权威参考**。它仅当被一个 adopted decision、一个 implemented blueprint、当前模块 docs、或 `architecture_principles.md` 引用时才成为约束。本文件描述的均为**提案**,尚未实现,**不得**据此认为代码已存在。

- First draft: 2026-06-04
- Last updated: 2026-06-04
- Scope: 在 Entity/Field 定义层引入声明式 `repr` 模板,供两个消费者共用 ——(A)explanation 的 atom-level 自然语言渲染;(B)entity 查询 / inspect / 快照的显示表示
- Parent / 相关: [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md)(D21 之后的 atom-level NL 方向);[`evaluate-result-flatten-and-query-style.zh.md`](evaluate-result-flatten-and-query-style.zh.md)(ε slice 的 `Explanation.repr` walker + 2026-06-04 desc fix 把 conclusion 行接通 `head.render_desc`)
- 触发动机: `Explanation.repr` 的 atom 行渲染成 `Atom: satisfied — support`(状态而非内容),且 entity-ref 显示为 `idref_v1:...` 长哈希,不可读。用户期望流畅自然语言(如 "Alice lives in US")。

---

## §1 问题

两个相关的不可读性:

1. **解释 atom 层**:walker 渲染每个 atom 的*状态*(`satisfied — support`),多个不同谓词的 atom 看起来完全一样(已确认是渲染塌缩,非数据 bug —— 节点 `engine_meta.atom_id` 各异)。
2. **entity-ref 显示**:无论解释里还是查询 / 快照返回里,entity 都以 `idref_v1:User:<hash>` 出现,而非 "Alice" / "US" / "English"。

根因:**没有一个声明式、与 schema co-located、跨消费者复用的"领域措辞"机制**。当前 `Rule.desc`(2026-06-04 已接通 conclusion 行)只解决了 conclusion 那一句;atom 层与通用 entity 显示仍缺。

## §2 提案总览

在 schema 定义层引入两级 `repr` 模板:

```python
class Country(Entity):
    code: str = Identity(repr="%ENT has code %FLD")            # identity 也可带 repr
    language: "Language" = Field(repr="%ENT's language is %FLD")  # 谓词措辞

    class Meta:
        repr = "%CLS %code"                                   # 实体显示 —— 只引用 identity 字段(+ %CLS)

class User(Entity):
    user_id: str = Identity(repr="%ENT has id %FLD")
    name: str = Field(repr="%ENT's name is %FLD")
    country: Country = Field(repr="%ENT lives in %FLD")
    age: int = Field(repr="%ENT is %FLD years old")

    class Meta:
        repr = "%CLS %user_id"   # 只引用 identity 字段(见 §4.2);故是 "User u-1" 而非 "User Alice"
```

两级各司其职:

| 级别 | 写在哪 | 解决什么 | `%` 占位 |
|---|---|---|---|
| **Field.repr / Identity.repr** | 字段 / 身份描述符 | 该字段对应**谓词**出现在规则 body 时的自然语言措辞 | `%ENT`=主体实体, `%FLD`=字段值, `%CLS`=类名 |
| **Meta.repr** | Entity 内嵌 `class Meta` | 该类型**实体的显示 label**(entity-ref → 可读串) | `%CLS`=类名, `%<field>`=该实体字段值;**只能引用 identity 字段**(见 §4.2) |

`Identity()` 与 `Field()` 对称,都接受 `repr=`。两者的 `repr` 是 **atom 措辞**(谓词出现在 body 时);与 `Meta.repr`(实体 label)正交、不重叠。

两个消费者共用这套模板:

- **消费者 A — 解释渲染**(§5):atom 行用 Field.repr,entity-ref 用其类型的 Meta.repr 解析。
- **消费者 B — entity inspect / 查询表示**(§6):快照 / 查询 / 搜索结果可直接拿到 Meta.repr 渲染出的 label。

## §3 占位符语法

**命名约定(用户锁定 2026-06-04)**:**大写 = 保留角色;小写/实名 = 命名查找(字段名 / 端口名)**。两者据大小写区分,天然不冲突(`%CLS` vs `%user_id`)。

| 占位 | 含义 | 用在 |
|---|---|---|
| `%CLS` | EntityClass 名(如 "User") | Meta.repr / Field.repr / Identity.repr |
| `%ENT` | 谓词主体实体 → 其类型的 Meta.repr label | Field.repr / Identity.repr;**Meta.repr 禁用(自引循环)** |
| `%FLD` | 当前字段值;若 entity-ref 则递归用其类型 Meta.repr 解析,标量直印 | Field.repr / Identity.repr |
| `%<field_name>` | 当前实体某 **identity** 字段的值 | Meta.repr |
| `%<port_name>` | 端口绑定值 | Rule.desc(已存在)|

(命名取舍:`%CLS`/`%ENT`/`%FLD` 三字母大写,自文档化且不易与实名字段撞;原 `%E`/`%F` 单字母更短但隐晦 —— 二选一是审美决定,本文件采三字母。)

**`%FLD` 限定当前字段(guardrail)**:Field.repr **不允许**引用其他字段(如 `%user_id of %name`)。否则重新引入 identity-only 刚消解的"字段可用性/漂移"问题。要丰富显示主体,用 `%ENT`(走 Meta.repr,identity-safe)。

**`%ENT` 不可省**:atom 里唯一能表达"主体实体"的占位。**但禁止出现在 Meta.repr**(Meta.repr 正是定义 label 处,自引会无限递归)。

**校验**:类定义时拦截 —— `%ENT` 出现在 Meta.repr、`%FLD` 引用非当前字段、以及与保留词(CLS/ENT/FLD)同名的 identity 字段。

> **D-arity 已关闭**:数据底层恒定二元(`pred(主体, 单值)`,用户确认 2026-06-04),`%ENT`/`%FLD` 永远够用,无需索引式 `%1/%2`。

**与现有 `Rule.desc` 的协调(D-syntax 已定)**:`Rule.desc` 用 `%<port_name>` 命名式。本提案 Field.repr 用保留角色 `%ENT`/`%FLD`/`%CLS`,Meta.repr 用 `%CLS` + `%<identity_field>`。三者通过"大写=保留 / 小写=实名"约定共存,不冲突,不强行统一。详见上表 + 约定段。

## §4 两级模板详解

### §4.1 Field.repr / Identity.repr — 谓词措辞

一个字段 `User.country: Country = Field(repr="%ENT lives in %FLD")` 对应谓词 `user:country(u, c)`。渲染:
- `%ENT` ← 主体 `u`,用 `User.Meta.repr` 解析 → "User u-1"
- `%FLD` ← 值 `c`;因 country 字段类型是 entity-ref(Country),递归用 `Country.Meta.repr` 解析 → "Country US"
- 结果:**"User u-1 lives in Country US"**

标量字段 `User.age: int = Field(repr="%ENT is %FLD years old")` → `%FLD` 是标量直印 → "User u-1 is 30 years old"。

`Identity(repr=...)` 同理,描述该 identity 谓词出现在 body 时的措辞(如 `user:user_id(u, "u-1")` → "User u-1 has id u-1")。

**类型分派是硬要求**:渲染器必须按字段声明类型决定 `%FLD` 是"递归解析 entity-ref"还是"直印标量"。schema 已记录字段类型,可判定。

### §4.2 Meta.repr — 实体显示解析器(**必须只引用 identity 字段**)

`User.Meta.repr = "%CLS %user_id"`:把一个 User 实体渲染成 "User u-1"。这是**整个设计的关键解析器** —— `%ENT` 与 entity-ref 类型的 `%FLD` 都靠它把 idref 变可读;也是消费者 B(§6)的核心。

**约束(本设计的关键决策)**:`Meta.repr` 的 `%<field>` 占位**只能引用 identity 字段**(类定义时校验,引用非 identity Field → 报错)。理由是 identity 字段的两个特性(见 [`data_model.md`](../../../docs/quickstart/data_model.md) §1):

1. **不可变** —— identity claim 是 immutable anchor,改 identity = 改 e_ref = 不同实体。故解析 identity **永不漂移**。
2. **恒在** —— 任何存在实体的 identity claim 必然存在,故 **永远可解析**,不会缺字段。

这两点直接**消解 §7 的 D-source 两难**:Meta.repr 在任何时刻(甚至回查 ledger)都能忠实且完整解析,不受后续写入影响。这是把 repr 限定在 identity 上换来的关键收益。

**代价 + 立场(用户锁定 2026-06-04)**:label 由 identity 值构成。`user_id="u-1"` → "User u-1",**不是** "User Alice"。立场明确:**name 这类可变可读字段不进 label**;若确需某字段进 label,就**把它建模成 `Identity()`**(并接受其不可变 —— 你用来指代实体的东西本就该稳定)。**不设任何 non-identity display 逃生口**。这把整个实体显示统一在 identity 上,可重放性无死角。

### §4.3 默认 repr(未定义 Meta.repr 时)

类未定义 `class Meta.repr` 时,默认 label 为 **`"<EntityCls> <第一个 Identity 字段的值>"`**(如 `User` → "User u-1")。

- `<EntityCls>` = Python 类名(与用户代码一致)。
- "第一个 Identity" 按**类定义声明顺序**取。复合 identity(多 `Identity()`)只取首个 —— 显示上可能不唯一(非唯一键,e_ref 才是);要消歧请显式写 Meta.repr。

## §5 消费者 A:解释渲染

**集成方式(建议)**:**build-time 烘焙**,与 2026-06-04 desc fix 一致。在 evidence-graph 构建时(`evaluate_result.py` 的 `_layered_*` 路径,有 schema 访问权),把 Field.repr 渲染好的短语写进 atom 节点的 `value_summary`;walker(`explanation_render.py`)仍只管打印 `value_summary`,无需 schema 句柄。

**渲染流程(两遍)**:
1. **解析遍**:对每个 entity-ref 用其类型 `Meta.repr` + identity 值解析出 label(u→"User u-1",c→"Country US",l→"Language en")。因 Meta.repr 只引用 identity(§4.2),identity claim 恒在,这一遍永远成功。
2. **渲染遍**:用解析后的 label 渲染各 atom。identity 谓词 atom(喂 Meta.repr 的)可**折叠**,不单独成句。

**目标输出形态**(注意 conclusion 与 atom 的 label 来源不同):
```
<Alice speaks English> because                  ← conclusion 用 Rule.desc + head 端口绑定(speaker=Alice)
  ├─ User u-1 lives in Country US                ← atom 用 Field.repr + Meta.repr(identity label)
  ├─ Country US's language is Language en
  └─ User u-1 is 30 years old   (age ≥ 5)
```

> **conclusion/atom label 不一致(待议)**:conclusion 行经 head 端口可显示绑定的友好名("Alice"),而 atom 行的实体走 Meta.repr 显示 identity label("User u-1")。两者风格不统一是 identity-only 约束的直接后果。若要统一,要么 conclusion 也降到 identity label,要么放开 Meta.repr 的次级 display 口子(§4.2 代价段)。

### §5b 流畅 "because" 散文(第二渲染模式)

§5 的 walker 产出**缩进树**(machine-walkable,现 shipped `Explanation.repr`)。最初目标是**流畅嵌套 because 散文**。两者**共用同一批 per-node 短语**(Meta.repr label + Field.repr/默认表 atom 短语),只在**合成方式**不同:树用缩进+边连接词;散文用 `because` + AND/OR 连接 + assumption 嵌套。

**tier → 散文映射:**

| 节点 | 散文元素 |
|---|---|
| CONCLUSION | 头句 `<conclusion 短语>`(desc / Meta.repr) |
| RULE_EXPR | `because` + 组合模式:single→直接接;AND→`<J1>, and <J2>`;OR→`either <J1> or <J2>` |
| RULE | justification 子句。单规则:**透明**(直接列 atoms);多规则组合:`the assumption "<rule desc>" holds (because <atoms>)` |
| ATOM | Field.repr / 默认表短语,规则内 **AND 连接** |
| SEED | 可选 `(per ledger fact …)` 或折叠 |

**散文深度随 RuleExpr 结构**(解释了原始草稿的 "assumption of X AND assumption of Y"):

- **单规则**(region/language/age 同一 body)→ 扁平:
  ```
  Alice speaks English because Alice lives in Country US, US has language English, and Alice is at least 5 years old.
  ```
- **AND 组合**(rule1 地理 ∧ rule2 年龄,各为具名 assumption)→ 嵌套:
  ```
  Alice speaks English because
    the assumption "geographic match" holds (because Alice lives in Country US and US has language English), and
    the assumption "age eligibility" holds (because Alice is at least 5 years old).
  ```

**设计岔路(D-prose,待定):散文是新模式还是替换?**
- **方案 X(推荐)**:`repr` 缩进树不变;**新增** prose 渲染面(`Explanation.narrate()` 或 `repr(style="prose")`),复用同一批 build-time 烘焙短语 —— 两 walker、一套数据。结构化(machine)与人类可读各取所需。
- **方案 Y**:散文替换 `repr` —— 不建议(破坏现有结构化契约 + machine 消费者)。

注:散文模式仍属"解释渲染(消费者 A)"范围内,但是**第二个 walker**,与 §5 缩进树并存。default 表(§8)的措辞既供树也供散文复用。

## §6 消费者 B:entity inspect / 查询表示(**本设计范围外 / 未来工作**)

> **范围决定(用户锁定 2026-06-04)**:本设计这轮**只 adapt 到解释渲染(消费者 A)**。entity inspect / 查询显示这一层(下表接口)**移出本设计范围**,留待将来单独推进。下表仅作未来方向记录,不在本设计的实现/slice 计划内。

repr 模板(§4)是 schema-level 的,将来天然可复用于"把实体显示给人看"的任何地方。届时候选接口面(未来):

| 接口(未来) | 用途 |
|---|---|
| `EntitySnapshot.repr` | 快照可读 label |
| `fg.entities.repr(ref)` | 对裸 ref 直接求显示 |
| `fg.entities.match(...)` 结果带 `.repr` | 查询/搜索结果附 label |
| `fg.entities.inspect(...)` | 与 `fg.rules.inspect` 对称的 entity 结构 inspect |

(届时同样按应用优先:渲染逻辑为应用层纯函数 `render_entity_repr(...)`,SDK 面是薄 shell。)

## §7 解析语义 + 数据源

### §7.1 entity-ref → label
`%ENT` 与 entity-ref `%FLD`:取被引用实体的类型 → 用该类型 `Meta.repr` 渲染。

### §7.2 字段数据从哪来(D-source —— **已被 §4.2 identity-only 约束消解**)

原本的两难:`Meta.repr` 要解析某实体需该实体的字段值,而该字段可能不在渲染上下文(解释场景)、或回查 live ledger 会漂移。

**§4.2 的 identity-only 约束直接解决它**:Meta.repr 只引用 identity 字段,而 identity **不可变 + 恒在** → 任何时刻解析都忠实且完整,无漂移、无缺失。即使实现选择 build-time 回查 identity claim 也安全(identity 变了就是另一个实体)。

遗留:仅当将来放开"次级 non-identity display 口子"(§4.2 代价段)时,D-source 的 (a)/(b)/(a′) 权衡才重新出现 —— 届时对那条次级路径用 (a′) build-time 冻结。主路径(identity-only)无此问题。

### §7.3 环 / 深度
Meta.repr 互引(A→B→A)需**环检测 + 深度上限**;`%ENT` 解析也只展开一层(不无限递归嵌套 label)。

## §8 覆盖:Field.repr 管字段谓词,其余全走渲染器级默认表

**两类划分(用户锁定 2026-06-04)**:
- **字段谓词** `pred:field(subj, val)` → 由 schema 的 Field.repr / Identity.repr 措辞。
- **其余所有 atom 类型** → 走一套**渲染器级默认模板表**(内建,不在 schema 上配),统一处理。

渲染器级默认表覆盖范围(D-coverage,放宽后):

| atom 类型 | 默认措辞来源 |
|---|---|
| `<Type>:exists(x)` | "%ENT exists" / "%ENT is a {Type}" |
| `eq`("==") / `ne`("!=") | "%1 is %2" / "%1 is not %2" |
| `gt` / `ge` / `lt` / `le` | op→短语:`ge`→"at least", `gt`→"more than", `le`→"at most", `lt`→"less than" |
| 聚合 `max` / `min` / `count` / `sum` / ... | "%agg of %target {where ...}" 形态 |
| `in` | "%x is one of {...}" |
| `not(body)` | "it is not the case that {body}" |
| `BuiltinAtom` / arithmetic (`add`/`sub`/...) | 各自默认短语 |

要点:字段谓词的措辞**声明在 schema**(领域知识),其余结构性/比较/聚合 atom 的措辞**内建在渲染器**(与领域无关,通用)。两者边界:**有没有对应 schema 字段**。`==` / `max` 这类正如你说的,都归渲染器级默认表。

## §9 跨层数据流

```
SDK 编写面          schema IR              evidence-graph builder / inspect surface
─────────           ─────────              ────────────────────────────────────────
Field(repr=...)  ─► predicate 条目     ─► (A) 烘焙 atom 节点 value_summary
class Meta.repr  ─► entity 条目 +repr  ─► (B) render_entity_repr(应用层纯函数)
                                          └► snapshot.repr / fg.entities.repr / match label
```

新增工作有界:schema IR 现已记录 predicate↔field 映射,加 `repr` 字段;builder 与 inspect surface 消费。SDK `Field(repr=)` / `Meta.repr` 是 ergonomic 面,canonical 模板数据落在应用层 schema 表示。

## §10 开放决策(待 review 决定)

| ID | 决策 | 倾向 / 状态 |
|---|---|---|
| **D-source** | Meta.repr 字段数据来源 / 漂移 | **已解决** —— §4.2 identity-only 约束(不可变+恒在)消解 |
| **D-identity-only** | Meta.repr 是否硬性限定只引用 identity 字段 | **采纳(用户锁定 2026-06-04)**;校验在类定义时 |
| **D-display-escape** | 是否给 Meta 留"次级 non-identity 友好 display"口子 | **已解决 —— 不设逃生口**(用户锁定)。要友好名就把字段设为 Identity |
| **D-default** | 未定义 Meta.repr 时的默认 label | **已解决 —— `"<EntityCls> <1st Identity>"`**(§4.3)|
| **D-conclusion-atom** | conclusion 与 atom 实体显示一致性 | **Meta.repr 统管所有 entity-ref→label**;标量端口显示作者投影值;一致性落在作者是否始终用 entity-ref(§5)|
| **D-prose** | 流畅 because 散文是新渲染模式还是替换 `repr`(§5b)| **倾向方案 X** —— 新增 `narrate()` / `repr(style="prose")`,缩进树 `repr` 不变,两 walker 复用同一批短语;**待你拍板** |
| **D-syntax** | 占位语法 | **已定(用户锁定)** —— `%ENT`(主体,走 Meta.repr,不可省)+ `%FLD`(**仅当前字段**,禁引他字段以防漂移)+ `%CLS`(类名);约定"大写=保留 / 小写=实名";不强行统一,文档化区分 |
| **D-arity** | 多元谓词占位 | **已关闭** —— 数据底层恒定二元(用户确认),`%ENT/%FLD` 永远够用 |
| **D-surface** | 消费者 B(inspect/查询表示)接口 | **本设计范围外(用户锁定)** —— 这轮只 adapt 解释;§6 移为未来工作 |
| **D-coverage** | 非字段谓词 atom 的措辞 | **已定** —— 字段谓词走 schema Field.repr;其余全部(exists / eq(`==`)/ ne / cmp / 聚合 `max` 等 / in / not / builtin)走**渲染器级默认表**(§8)|
| **D-i18n** | repr 单字符串 vs mapping/callable | **已定** —— v1 单字符串;机制不做死,留 mapping/callable 升级路 |
| **D-fold** | identity 谓词 atom 是否折叠 | **已定 —— 折叠**,规则:**谓词字段出现在主体 Meta.repr 中 → 折叠**(因 identity-only,此规则确定可靠);`:exists` 同理 |
| **D-validate** | repr 占位符校验时机 | 类定义时校验(对齐现有 `_validate_desc`);含 Meta.repr identity-only 校验 + `%FLD` 仅当前字段 + `%ENT` 禁现于 Meta.repr + 保留词不撞字段名 |

## §11 边界情形

- **循环 Meta.repr**:A.repr 引 B,B.repr 引 A → 环检测 + 深度上限。(注:Meta.repr 只引用 identity 标量字段时通常不会嵌套 entity-ref,环风险低,但仍应防御。)
- **折叠只针对 identity atom**(D-fold):identity atom(如 `user:user_id(u, "u-1")`)与 label "User u-1" 冗余 → 折叠。**非 identity 字段 atom 不折叠** —— 在 identity-only 约束下,`user:name(u, "Alice")` 渲染成 "User u-1's name is Alice" 是补充信息(name 不在 label 里),保留。折叠规则可靠性由 identity-only 保证("字段在 Meta.repr 中" ⟺ "它是 label 的 identity 字段")。
- **未绑定字段**:identity-only 约束下 Meta.repr 不会遇到(identity 恒在)。仅"次级 non-identity display 口子"(若启用)才需降级 —— 印 identity / 短 id。
- **repr 缺省**:Field / Identity / Meta 无 repr → 优雅降级到默认模板(当前 terse 形式或 identity)。
- **多值 / 复合 identity**:复合 identity(多个 Identity 字段)Meta.repr 可引用多个 `%<id_field>`;`list[T]` 字段(非 identity)的 Field.repr 多值如何渲染(逐项?join?)—— 待定。
- **聚合 / 跨实体关系措辞**:Field.repr 是正向(主体→值);反向措辞("country of X is Y")需另议。

## §12 影响面与体量

**本设计范围(用户锁定)**:只 adapt 到**解释渲染(消费者 A)**;消费者 B(inspect/查询表示)移出(§6)。

- **跨层 feature**:SDK schema DSL(Field/Identity 加 `repr=` + class Meta.repr + 校验)+ schema IR(repr 字段 + Meta.repr,含 identity-only 校验)+ evidence-graph builder(build-time 烘焙 atom 短语 + entity label)+ explanation_render(渲染器级默认表覆盖 exists/eq/cmp/聚合/not/...)+ 文档 + 测试。
- 若推进,建议拆 slice(范围内):
  - **S1** schema 层:`Field/Identity(repr=)` + `class Meta.repr` + 校验(占位符 + Meta.repr identity-only)+ 默认 `"<EntityCls> <1st Identity>"`
  - **S2** schema IR + 应用层 `render_entity_repr`(identity → label)
  - **S3** Field.repr atom 短语 + entity label 烘焙进 evidence 节点 value_summary(消费者 A,缩进树 `repr`)
  - **S4** 渲染器级默认表(exists / eq / ne / cmp / 聚合 / in / not / builtin)+ identity atom 折叠
  - **S5**(若 D-prose 取方案 X)流畅 because 散文渲染面(`narrate()` / `repr(style="prose")`),复用 S3/S4 短语 + §5b tier→散文合成
  - 按 Audit-to-Archive Cadence 逐 slice。S1→S4 产出缩进树;S5 加散文模式。
- **仍开放(范围内但未定)**:D-prose(散文模式形态,§5b)、D-syntax(占位语法统一)、D-arity(多元谓词,可能 v1 只支持二元)、D-i18n(v1 单串)。
- **实现需显式授权**(per [[feedback_no_autonomous_code_edits]]);本文件仅设计探索。
