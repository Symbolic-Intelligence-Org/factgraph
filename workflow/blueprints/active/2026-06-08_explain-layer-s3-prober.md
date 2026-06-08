# Task Blueprint: S3 — Prober Main Body (application/explain/ + EvidenceTree)

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08
- Parent Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md) (on v0.2.0-blueprint-explain-layer-2026-06-08)
- Related Modules:
  - `src/factgraph/application/explain/` (新建 — 本 slice 主体)
  - `src/factgraph/application/diagnose_runtime.py` (atom 求值器复用，无修改)
  - `src/factgraph/application/protocol/rule_expr_lowering.py` (OccurrenceMap / Join 数据结构复用)
  - `src/factgraph/audit/evidence_graph.py` (旧 EvidenceGraph — S7 前不修改)
  - `src/factgraph/application/protocol/evaluate_result.py` (Explanation — S5 前不修改)
- Related Docs:
  - [explain-layer-complete-design.zh.md §3/§4/§5/§6/§7/§8](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-08_explain-layer-s3-prober.audit.md](./2026-06-08_explain-layer-s3-prober.audit.md)

---

## 1. Problem

`application/explain/` 模块不存在。`Explanation.evidence` 仅在 native 路径 passed 时携带旧 flat DAG `EvidenceGraph`（`nodes/edges/root_node_id/support_kind`），无法表达 OR branch 结构、AND atom 三态（Holds/Fails/NotReached）或 failed 路径完整证据。

S0-S2 已落地（`Rule.repr`、Schema DSL `repr=`、Schema IR repr 持久化），prober 所需的依赖层已完备。

## 2. Goals

1. 新建 `src/factgraph/application/explain/` subpackage：
   - `evidence_tree.py`：所有新 DTO 数据类（`EvidenceGraph`（新）/ `EvidenceTree` / `EvidenceTimeline` / `EvidenceRule` / `EvidenceAtom` / `Fact` / `Compare` / `Builtin` / `Holds` / `Fails` / `NotReached` / `BoundVar` / `Const` / `Aggregate` / `Source` / `PortRef` / `EvidenceJoin` / `EvidenceProbeResult`）。
   - `prober.py`：`ProbeEnv` + native 路径穷尽探查器 `probe_native(...) -> EvidenceProbeResult`。
   - `__init__.py`：从 `evidence_tree.py` / `prober.py` 导出公开类型。
2. 新 `EvidenceGraph`（含 `paths: tuple[EvidenceTree | EvidenceTimeline, ...]`）定义在 `evidence_tree.py`，与旧 `audit/evidence_graph.EvidenceGraph` 独立共存。
3. `probe_native(rule, bindings, view_facts, schema_index) -> EvidenceProbeResult` 为纯函数：不访问数据库，不修改任何已有协议类型。
4. `EvidenceAtom.repr_text = None` in S3（S4 负责烘焙，S3 不接触 Schema 渲染）。
5. 复用 `diagnose_runtime._extend_env_with_atom`（import private helper — 新代码 import，非旧代码修改）。
6. 完整 tests：standalone prober 测试，通过 mock `view_facts` 不依赖数据库。

## 3. Non-goals

- **不修改** `src/factgraph/audit/evidence_graph.py`（旧 `EvidenceGraph` nodes/edges 结构）— S7 删除。
- **不修改** `src/factgraph/application/protocol/evaluate_result.py`（`Explanation.evidence` 类型不变）— S5 wire-up。
- **不烘焙** `EvidenceAtom.repr_text`（`None` 占位）— S4。
- **不实施** souffle / problog / pyreason 探查路径 — S6。
- **不通过 SDK 导出**新类型 — 维持 application-first。
- **不修改** `diagnose_runtime.py` 源码（只 import，不重构）。
- **不修改** `Explanation.evidence` 不变式（`passed iff evidence is not None`）— S5 放宽。

## 4. Current Context

**Preflight — Shipped State（2026-06-08 source-read）**:

| # | 文件 | 现状 | 与 S3 的关系 |
|---|---|---|---|
| 1 | `audit/evidence_graph.py` | `EvidenceGraph(graph_id,engine,root_node_id,nodes,edges,support_kind,layout_hint,metadata)` | S3 不修改；S7 删除 |
| 2 | `evaluate_result.py:278` | `Explanation.evidence: EvidenceGraph \| None`；不变式 `passed iff evidence is not None` | S5 修改 |
| 3 | `diagnose_runtime._extend_env_with_atom` | 已有 pred/eq/ne/gt/ge/lt/le/arith/not/in 求值器 | S3 import 复用 |
| 4 | `diagnose_runtime._normalize_where` | 规范化 rule body → OR branches | S3 import 复用 |
| 5 | `protocol/rule_expr_lowering.py` | `RuleExprLoweringPlan`（`branches`, `join_materializations`, `head_binding`）；`RuleExprJoinMaterialization(left_occurrence_alias, right_occurrence_alias, left_port, right_port)` | S3 作为 prober 输入类型 |
| 6 | `application/explain/` | **不存在** | S3 新建 |
| 7 | `explain-layer-complete-design.zh.md §3` | 完整 DTO 形态设计（`EvidenceTree/Rule/Atom`等） | 权威设计参考 |

**Open design questions — S3 启动前锁定**:

| ID | 问题 | 状态 |
|---|---|---|
| Q-S3-A | 新 `EvidenceGraph`（paths）与旧 `audit.EvidenceGraph` 如何共存？ | → 见 §5 决策 |
| Q-S3-B | `EvidenceProbeResult` 形状：仅包含 `paths` 还是也包含 `certainty`/`metadata`？ | → 见 §5 决策 |
| Q-S3-C | `probe_native` 如何获取 `RuleExprLoweringPlan`？行内 lower vs 接收参数？ | → 见 §5 决策 |

## 5. Proposed Shape

### Q-S3-A: 新旧 EvidenceGraph 共存策略

**决定**：在 `application/explain/evidence_tree.py` 定义新 `EvidenceGraph`，命名不变，模块路径不同。
- 旧：`factgraph.audit.evidence_graph.EvidenceGraph`（`nodes/edges` flat DAG）— S7 前不动。
- 新：`factgraph.application.explain.evidence_tree.EvidenceGraph`（`paths` 层级结构）。
- S5 修改 `Explanation.evidence` 类型时，导入新类型；旧类型由 S7 删除。
- Python 允许同名类在不同模块，不冲突。

### Q-S3-B: EvidenceProbeResult

`probe_native` 返回 `EvidenceProbeResult`（中间组装结果），而非直接返回 `EvidenceGraph`：

```python
@dataclass(frozen=True)
class EvidenceProbeResult:
    paths: tuple[EvidenceTree, ...]     # native: 只有 EvidenceTree
    certainty: Certainty | None = None  # 原始行 certainty（由调用方传入）
```

`EvidenceGraph`（含 `graph_id / engine / layout_hint / subject_binding / metadata`）由 S5 wire-up 层在调用 `probe_native` 后组装。这使 prober 纯粹：只处理路径，不持有标识信息。

### Q-S3-C: 获取 RuleExprLoweringPlan

`probe_native` 接收已 lowered 的 `RuleExprLoweringPlan` 作为参数。调用方（S5）负责 lower rule → plan。S3 不调用 `lower_rule_expr`，避免引入 SDK 依赖或重复 lower。

```python
def probe_native(
    plan: RuleExprLoweringPlan,
    bindings: Mapping[str, Any],
    view_facts: dict[str, list[tuple[Any, ...]]],
    schema_index: SchemaIndex | None = None,
) -> EvidenceProbeResult:
    ...
```

### EvidenceTree DTO 层（evidence_tree.py）

按设计文档 §3 实现，关键约定：

```python
# === 新 EvidenceGraph（paths 模型）===
@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str
    layout_hint: Literal["tree", "timeline"]
    subject_binding: Mapping[str, Any]
    paths: tuple["EvidenceTree | EvidenceTimeline", ...]
    certainty: Certainty | None = None
    metadata: Mapping[str, Any] = MappingProxyType({})

@dataclass(frozen=True)
class EvidenceTree:
    tree_id: str
    status: Literal["holds", "fails", "not_reached"]
    rules: tuple["EvidenceRule", ...]
    joins: tuple["EvidenceJoin", ...]
    certainty: Certainty | None = None

@dataclass(frozen=True)
class EvidenceRule:
    occurrence_alias: str
    rule_id: str
    role: Literal["body", "head"]
    status: Literal["holds", "fails", "not_reached"]
    ports: Mapping[str, Any]
    atoms: tuple["EvidenceAtom", ...]

@dataclass(frozen=True)
class EvidenceAtom:
    form:    "Fact | Compare | Builtin"
    verdict: "Holds | Fails | NotReached"
    atom_id: str                   # c{case}.c{cond}:{pred|kind}
    repr_text: str | None = None   # S4 负责烘焙；S3 产出 None
    negated: bool = False
    timestep: int | None = None    # 仅 pyreason

# === Verdict variants ===
@dataclass(frozen=True)
class Holds:      certainty: Certainty; support: tuple["Source", ...] = ()
@dataclass(frozen=True)
class Fails:      certainty: Certainty
@dataclass(frozen=True)
class NotReached: blocked_by: str | None  # atom_id; None = 无 prior binder

# === Form variants ===
@dataclass(frozen=True)
class Fact:     predicate: str; terms: tuple["Operand", ...]
@dataclass(frozen=True)
class Compare:  op: str; lhs: "Operand"; rhs: "Operand"
@dataclass(frozen=True)
class Builtin:  op: str; args: tuple["Operand", ...]; result: "Operand"

# === Operands ===
@dataclass(frozen=True)
class BoundVar:  name: str; value: Any | None; bound_by: str | None
@dataclass(frozen=True)
class Const:     value: Any
@dataclass(frozen=True)
class Aggregate: kind: str; target: "Operand | None"; filter: Any; value: Any | None

# === Source / Join ===
@dataclass(frozen=True)
class Source:    ref: str; field: str; value: Any; meta: Mapping[str, Any]
@dataclass(frozen=True)
class PortRef:   occurrence: str; port: str
@dataclass(frozen=True)
class EvidenceJoin: left: PortRef; right: PortRef; held: bool
```

`Certainty` 直接从 `factgraph.application.protocol.evaluate_result` 导入（已 exported）。

### ProbeEnv（prober.py）

```python
@dataclass
class ProbeEnv:
    bindings: dict[str, Any]               # 当前已绑定变量
    bound_vars: set[str]                   # 已绑定变量名集合
    binder_by_var: dict[str, str]          # var_name → atom_id（哪个 atom 绑定了它）
```

### 三层 status 聚合规则

- `EvidenceRule.status`：
  - "holds" iff 所有 atoms verdict = Holds
  - "fails" iff ≥1 atom verdict = Fails
  - "not_reached" iff 所有 atoms verdict = NotReached（且无 Fails）
- `EvidenceTree.status`：
  - "holds" iff 所有 rules.status = "holds"
  - "fails" iff ≥1 rule.status = "fails"
  - "not_reached" iff 所有 rules.status = "not_reached"
- **NotReached 触发条件**：仅变量未绑定（`binder_by_var` 中无记录）；前序 atom Fails **不**触发后续 atom NotReached。

### atom_id 约定（复用现有约定）

`c{case_index}.c{condition_index}:{pred_id|kind}` — 与现有 `_support.py:make_pred_condition_key` 对齐。

## 6. Boundaries And Invariants

- **新代码 import 私有 helper 可接受**：`from factgraph.application.diagnose_runtime import _extend_env_with_atom`——新文件 import，不修改 `diagnose_runtime.py`。
- **`audit/evidence_graph.py` 零修改**：旧 `EvidenceGraph` 及全部关联代码不动。
- **`evaluate_result.py` 零修改**：`Explanation.evidence` 类型和不变式不动（S5 负责）。
- **Certainty import 路径**：`from factgraph.application.protocol.evaluate_result import Certainty`。
- **prober 纯函数**：不访问数据库、不接触 SDK；view_facts 由调用方传入。
- **repr_text = None**：S3 所有 `EvidenceAtom` 的 `repr_text` 保持 `None`；S4 负责烘焙。
- **测试无数据库**：tests 用 mock `view_facts: dict[str, list[tuple]]`。

## 7. Acceptance

- [ ] `src/factgraph/application/explain/__init__.py` 存在并导出所有公开 DTO 类型
- [ ] `EvidenceGraph`（新）/ `EvidenceTree` / `EvidenceRule` / `EvidenceAtom` 均为 frozen dataclass
- [ ] `Holds` / `Fails` / `NotReached` verdict variants 存在
- [ ] `probe_native(plan, bindings, view_facts) -> EvidenceProbeResult` 可调用
- [ ] native 路径 holds case：`EvidenceTree.status == "holds"`，所有 atoms `verdict = Holds`
- [ ] native 路径 fails case：`EvidenceTree.status == "fails"`，失败 atom `verdict = Fails`
- [ ] native 路径 not_reached case：未绑定变量的 atom `verdict = NotReached(blocked_by=...)`
- [ ] 三层 status 聚合规则正确（holds > fails > not_reached 优先级）
- [ ] `EvidenceAtom.repr_text` 为 `None`（repr_text 烘焙不在 S3 scope）
- [ ] `audit/evidence_graph.py` 零 diff（git diff 验证）
- [ ] `evaluate_result.py` 零 diff（git diff 验证）
- [ ] `diagnose_runtime.py` 零 diff（git diff 验证）
- [ ] 所有 shipped tests 通过（prober 为新增，不影响旧 test baseline）
- [ ] standalone prober tests（mock view_facts）覆盖 holds/fails/not_reached 三种路径

## 8. Implementation Plan

1. 创建 `src/factgraph/application/explain/` subpackage
2. 实现 `evidence_tree.py`：所有 DTO frozen dataclass
3. 实现 `prober.py`：`ProbeEnv` + `probe_native`，import `_extend_env_with_atom` / `_normalize_where`
4. 更新 `application/explain/__init__.py` 导出
5. 编写 standalone tests（mock view_facts，三路径覆盖）
6. 运行全量 schema/application tests 确认零副作用

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`（新建，S3 完成后补）
- `workflow/design/design-points/active/explain-layer-complete-design.zh.md`（无需修改，设计已完备）

## 10. Outcome / Deviations

任务完成后填写。
