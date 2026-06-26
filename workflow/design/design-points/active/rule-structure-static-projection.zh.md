# Design-Point: `RuleStructure` — 引擎中立的规则结构投影(`fg.rules.structure`)

- Status: working
- Created: 2026-06-26
- Last Updated: 2026-06-26
- Authority: candidate design / non-authoritative reference. **Not current behavior.** 仅当被 adopted decision、implemented blueprint、当前模块 docs(`src/factgraph/*/docs/`)或 `workflow/foundations/architecture_principles.md` 引用时才成为约束。
- Inputs:
  - 用户-对话设计探索(2026-06-26,多轮 grounded design passes:静态结构可达性 → 检视面盘点 → API 设计评审 → EvidenceGraph 对位 → 静态可行性 → EvidenceGraph 定位/边界 → 引擎参数与 Tree/Timeline → 中立类型设计与命名)
  - shipped 类型:`RuleExprLoweringPlan`(`rule_expr_lowering.py`)、`EvidenceGraph`/`EvidenceTree`(`evidence_tree.py`)、`RuleExprInspect`(`rule_expr_inspect.py`)
- Outputs / Downstream:
  - decision [2026-06-26_evidencegraph-readonly-and-rule-structure-type.md](../../decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md)(proposed;锁定 §4.1 EvidenceGraph 只读定位 + §4.2 规则结构独立中立类型)
  - 一个 blueprint(实现 `fg.rules.structure`;harvest §3 类型契约)— 待 decision adopt 后开
- Related:
  - [explain-layer-complete-design.zh.md](./explain-layer-complete-design.zh.md)
  - [rule-namespace-rulespec-redesign.zh.md](./rule-namespace-rulespec-redesign.zh.md)

> **Authority reminder**:design-point 不能直接覆盖 shipped 行为。实现须经 decision → blueprint → impl 到达代码。

## 1. Problem framing

消费者(如 meander)需要规则的**静态结构**(branches / occurrences / atoms / joins)作为**数据**,*不运行 explain*,且能与 explain 的 `EvidenceGraph` **逐节点对位(对位)**:同一棵树,静态侧给**裸逻辑 / 变量**,explain 侧给**执行值 / verdict**——"display 与 explanation 是同一棵树的两个层级"。

现有两个面都不满足:

- **`RuleExprInspect`**(`fg.rules.inspect`)是静态视图,但它走**未-DNF 的作者树**(`rule_expr_inspect.py:343-354`)——无 DNF 分支、无 `branch_id`、atom 键是 `{rule.id}:atom_{idx}`。它**不携带 lowering-plan 的身份键**,无法与 `EvidenceGraph` 逐节点对位。
- **`EvidenceGraph`** 本身是对位的结构,但它**引擎污染**(带 `engine`、`EvidenceTree | EvidenceTimeline` union、`verdict`/`certainty`/`status`/`timestep`)且是**运行时输出**。把它当静态投影会(a)把引擎概念混进干净的规则结构,(b)给运行时类型塞一个"静态/未求值"模式。

核心设计原则:**rule 必须保持引擎中立、干净**;`EvidenceTree/Timeline` 真实受引擎影响。两者结构*相似*,但类型应*分开*。

## 2. Context

- `RuleExprLoweringPlan`(`rule_expr_lowering.py:124`)是**引擎无关骨架**(`_build_lowering_plan` 仅 DNF 归一 + 算 `canonical_key`)。带 DNF `branches`(`branch_id="c{idx}"`)、`occurrence_map`、join/head-link materializations。
- `EvidenceGraph`(`evidence_tree.py:154`)是运行时输出,**从 lowering plan 装配**;`paths` = 每 DNF 分支一棵 `EvidenceTree`(`tree_id=branch_id="c{idx}"`),pyreason 则是 `EvidenceTimeline`。
- 已确立(设计探索):lowering plan 是引擎无关骨架,每个 explain 身份键(`branch_id`/`occurrence_alias`/`atom_id`/`join_id`)都是它的确定性函数;`EvidenceTree` 结构在 native/souffle/problog 间**引擎一致**;`EvidenceTimeline` 仅 pyreason 产出(时序为运行时不动点产物)。
- **EvidenceGraph 定位(litmus)**:`EvidenceGraph` 是**只读派生投影**——Rule 在一次具体求值下渲染出的影子——**绝非 authoring substrate**。Rule(经 RuleExpr + lowering plan)是唯一、量化、可求值的行为源。Litmus:任何能力,若"用户能否绕过 Rule、从它拿到行为/事实/verdict?"答案为"能",即越界。

## 3. Proposal / direction

引入一个干净、**引擎中立的 `RuleStructure`** 类型:① 严格超集 `RuleExprInspect`;② 与 `Evidence*` 家族逐节点对仗;③ 从引擎无关的 `RuleExprLoweringPlan` 投影;④ 携带 plan 身份键,**按键**与 `EvidenceGraph` 对位(单一来源 ⇒ 无漂移)。配 `fg.rules.structure(rule) -> RuleStructure` SDK 动词。

一句话心智模型:**`Structure*` 就是把引擎剥掉的 `Evidence*`**——同一棵树、同一套身份键,没有 verdict/certainty/timestep。

### 3.1 层级对应

| `RuleStructure`(静态/中立) | `Evidence*`(运行时) | 对位键 |
|---|---|---|
| `RuleStructure`(容器) | `EvidenceGraph`(容器) | —(容器 id 不同;见下注) |
| `StructureBranch`(每 DNF 分支) | `EvidenceTree`(每 DNF 分支) | **`branch_id` ↔ `tree_id`(`"c{idx}"`)** |
| `StructureOccurrence` | `EvidenceRule` | **`occurrence_alias`** |
| `StructureAtom` | `EvidenceAtom` | **`atom_id`** |
| `StructureJoin` | `EvidenceJoin` | **`join_id`** |

**容器 id 注**:`RuleStructure.structure_id` = `plan.canonical_key`(per-rule);`EvidenceGraph.graph_id` 是 caller 提供的 per-run 值。两者 id 空间不同,**不是**对位键。对位发生在 branch-and-below:`structure.branches[i]` ↔ `graph.paths[i]`(by `branch_id == tree_id`)→ occurrence by `occurrence_alias` → atom by `atom_id` → join by `join_id`。四者都由同一个 `RuleExprLoweringPlan` 一次性派生 ⇒ 不会漂移。

### 3.2 类型契约(引擎中立;cut line = 无 `status`/`verdict`/`certainty`/`timestep`/`support`/`blocked_by`)

```
@dataclass(frozen=True)
class RuleStructure:                          # ←→ EvidenceGraph(容器)
    structure_id: str                         # plan.canonical_key(per-rule;非对位键)
    source_kind: Literal["rule", "rule_expr"]
    head_rule_id: str
    head_binding_kind: Literal["external", "inline", "projection"]
    ast: tuple[object, ...]                    # inspect AST,verbatim
    branches: tuple[StructureBranch, ...]      # 主存(plan.branches),非空
    ports: tuple[StructurePort, ...] = ()      # 去重的扁平 ports 视图(原 _ports)
    unjoined_same_name_ports: tuple[Mapping[str, object], ...] = ()
    head_closure: HeadClosure | None = None    # schema-gated;None == "未计算(无 schema)"
    metadata: Mapping[str, Any] = {}
    # 派生属性(inspect-floor parity):occurrences, joins, templates,
    #   port_visibility, is_closed, unbound_ports, render(bindings), render_compact()

@dataclass(frozen=True)
class StructureBranch:                         # ←→ EvidenceTree(每 DNF 分支)
    branch_id: str                             # KEY ↔ tree_id ("c{idx}")
    path: tuple[int, ...]
    occurrences: tuple[StructureOccurrence, ...]
    joins: tuple[StructureJoin, ...] = ()
    head_links: tuple[StructureHeadLink, ...] = ()

@dataclass(frozen=True)
class StructureOccurrence:                      # ←→ EvidenceRule
    occurrence_alias: str                       # KEY
    rule_id: str                                # ↔ EvidenceRule.rule_id(@property template_id 兼容别名)
    role: Literal["head", "body"]
    repr_text: str | None = None
    port_names: tuple[str, ...] = ()
    ports: Mapping[str, StructurePort] = {}     # typed(非运行值)
    atoms: tuple[StructureAtom, ...] = ()

@dataclass(frozen=True)
class StructureAtom:                            # ←→ EvidenceAtom
    atom_id: str                                # KEY
    kind: str                                   # entity_existence/field_predicate/pred/cmp/in/builtin/not
    form: AtomForm | None = None                # Fact|Compare|Builtin|Aggregate(结构化;terms = FreeVar|Const)
    subject: str | None = None
    entity_type: str | None = None
    field: str | None = None
    op: str | None = None
    value: object = None
    negated: bool = False
    summary: str = ""

@dataclass(frozen=True)
class StructurePortRef:                         # ←→ PortRef
    occurrence_alias: str
    port_name: str
    rule_id: str | None = None

@dataclass(frozen=True)
class StructureJoin:                            # ←→ EvidenceJoin
    left: StructurePortRef
    right: StructurePortRef
    join_id: str                                # KEY(= plan join_key)
    op: Literal["eq"] = "eq"

@dataclass(frozen=True)
class StructurePort:                            # ←→ PortInspect(仅活字段)
    name: str
    kind: Literal["entity_ref", "value"]
    entity_type: str | None = None
    # field / value_type DROPPED(inspect 里是死字段)

@dataclass(frozen=True)
class StructureHeadLink:                        # head 端口接线(无 Evidence 对应)
    head_port_name: str
    source_occurrence_alias: str
    source_port_name: str

@dataclass(frozen=True)
class HeadClosure:                             # schema-gated;无 schema 时 RuleStructure.head_closure=None
    is_closed: bool
    unbound_ports: tuple[str, ...]

@dataclass(frozen=True)
class FreeVar:                                  # 裸规则变量(BoundVar 的 run-free 版)
    name: str                                   # plan 变量名 ($alias__src)——保对位
    port_name: str | None = None                # 作者可读名("x"/"p")
# StructureTerm = FreeVar | Const
```

### 3.3 裸变量 + atom form

- 裸变量用 **`FreeVar(name, port_name)`**——*不用* `BoundVar(value=None)`(与运行时未绑定变量逐字相同,且渲染成 `<unbound>`)。`FreeVar` 同时带 plan 变量 `name`(对位键)与可读 `port_name`。
- `StructureAtom.form` 结构化承载四种 `AtomForm`(`Fact`/`Compare`/`Builtin`/`Aggregate`,terms 为 `FreeVar`/`Const`)供遍历;`summary`/`subject`/`value` 保留廉价字符串投影。

### 3.4 投影 + API

- 纯函数 `assemble_static_structure(plan: RuleExprLoweringPlan[, schema_index]) -> RuleStructure`(application 层),投影 plan 并铸造与 prober/assembler **相同**的 `branch_id`/`occurrence_alias`/`atom_id`/`join_id`(共享 key-minting helper;可考虑拆出 prober 的"skeleton-from-plan"使键单一来源)。
- SDK 壳 **`fg.rules.structure(rule)`**(application-first;SDK 为 ergonomic shell)。
- `fg.rules.inspect` 不变(返回 `RuleExprInspect`,文本/authoring 检视面)。`render()`/`render_compact()`(及未来可能的 `describe()`)是 `RuleStructure` 之上的**次要**文本层。

### 3.5 命名(打分胜出:`RuleStructure` + `Structure*` 家族)

`RuleStructure` 最高分(清晰、贴切、与 `Evidence*` 对仗、零冲突)。否决:`RuleBlueprint`(撞 workflow "blueprint" 治理词)、`RuleTree`(过度暗示 tree-only,它还带 flat joins + DNF 分支)、`RuleGraph`/`StructureGraph`(撞 `EvidenceGraph`)。节点家族统一 `Structure*` 前缀,不撞 `RuleJoinConstraint`/`RulePortRef`/`*Inspect`。

## 4. Open questions

- **Q1 → 已起 decision(proposed)**:"EvidenceGraph 只读派生定位 + litmus + core 不收 RuleStructure/EvidenceGraph 的机械明线 + 规则结构独立中立类型"已锁进 [decision](../../decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md) §4.1/§4.2(待 adopt)。
- **Q2**:`assemble_static_structure` 落点(`application/explain` vs `application/protocol`),以及为单一来源化身份键,需拆 `prober.py` 多少。
- **Q3**:`fg.rules.structure` 直接返回 `RuleStructure` 还是经一层 SDK 包装 DTO(application-first:纯函数在 application,SDK 壳)。
- **Q4**:pyreason/`EvidenceTimeline` 的 cross-model 语义映射(非节点恒等对位)是否需要单独表达,还是仅文档化为边界。

## 5. Consequences / downstream implications

若采纳此方向:

- **`Evidence*` 零改动**:`evidence_tree.py` 与其消费者(`narrate_evidence`/`walk_evidence`/`evidence_graph_to_dict`/audit DTO/runtime wrapper)**不动**——`RuleStructure` 是独立类型,无需 `Unevaluated` verdict / `engine` 放宽 / 边界拒收等"伪装中立"补丁(这是不混的最大收益:相比"复用 EvidenceGraph"方案,运行时侧改动大幅缩小)。
- **节点恒等对位不变式**(待文档化):同一规则的 `RuleStructure` 与 `fg.eval.explain(...).evidence` 在对位键(`branch_id`/`occurrence_alias`/`atom_id`/`join_id`)上节点恒等,仅差 `Evidence` 侧叠加(`status`/`verdict`/`certainty`/`engine`/`timestep`);键来自单一 plan ⇒ 无漂移。
- **范围 = Tree**:`RuleStructure` 是 Tree 形;pyreason/`EvidenceTimeline` 在节点恒等对位之外(cross-model 语义映射)。
- **下游落点**:Q1 → 一条 `workflow/design/decisions/` 的 decision(锁定定位 + 契约);随后一个 `workflow/blueprints/` 的 blueprint 实现 `fg.rules.structure`(slices 草图:拆 prober key-minting → 定义 `Structure*` 类型 → `assemble_static_structure` → inspect-floor 派生属性 + `HeadClosure` + 丢死字段 → `fg.rules.structure` 壳 → core 不收的机械守卫 → 对位/floor 测试 → 模块 docs)。
- **兼容**:`RuleExprInspect` + `fg.rules.inspect` 不变;`RuleStructure` 的扁平派生属性保住 inspect-floor 表面(含 `is_closed`/`unbound_ports` 经 `HeadClosure` 兼容属性默认)。

## 6. Status notes

`working` —— 设计方向已收敛(8 轮 grounded 探索),类型契约 + 命名 + 对位 + 定位/边界均落定;尚未起 decision/blueprint,实现未授权。下一步建议:把 Q1(EvidenceGraph 只读定位 + RuleStructure 契约)起成一条 decision,再据此开 implementation blueprint。
