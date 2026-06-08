# Task Blueprint: S3 — Prober Main Body (application/explain/ + EvidenceTree)

- Status: implemented
- Created: 2026-06-08
- Last Updated: 2026-06-08 (Step 4.8 implemented)
- Parent Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md) (on v0.2.0-blueprint-explain-layer-2026-06-08)
- Related Modules:
  - `src/factgraph/application/explain/` (新建 — 本 slice 主体)
  - `src/factgraph/application/diagnose_runtime.py` (atom 求值器复用，无修改)
  - `src/factgraph/application/protocol/rule_expr_lowering.py` (OccurrenceMap / Join 数据结构复用)
  - `src/factgraph/audit/evidence_graph.py` (旧 EvidenceGraph 完全替换；保留为新 paths model re-export/serialization 入口)
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
2. 新 `EvidenceGraph`（含 `paths: tuple[EvidenceTree | EvidenceTimeline, ...]`）定义在 `application/explain/evidence_tree.py`；`audit/evidence_graph.py` re-export 新模型并删除旧 flat DAG implementation。
3. `probe_native(rule, bindings, view_facts, schema_index) -> EvidenceProbeResult` 为纯函数：不访问数据库，不修改任何已有协议类型。
4. `EvidenceAtom.repr_text = None` in S3（S4 负责烘焙，S3 不接触 Schema 渲染）。
5. 复用 `diagnose_runtime._extend_env_with_atom`（import private helper — 新代码 import，非旧代码修改）。
6. 完整 tests：standalone prober 测试，通过 mock `view_facts` 不依赖数据库。

## 3. Non-goals

- **不烘焙** `EvidenceAtom.repr_text`（`None` 占位）— S4。
- **不实施** souffle / problog / pyreason 探查器 — S6。
- **不通过 SDK 导出**新类型 — 维持 application-first。
- **不修改** `diagnose_runtime.py` 源码（只 import，不重构）。
- **不修改** `Explanation.evidence` 不变式 wire-up 细节 — S5（`Explanation.evidence` 由 S5 接通 native prober；S3 仅建立 prober 本体）。
- **S7 已并入 S3**：不再单独存在。

## 4. Current Context

**Preflight — Shipped State（2026-06-08 source-read）**:

| # | 文件 | 现状 | 与 S3 的关系 |
|---|---|---|---|
| 1 | `audit/evidence_graph.py` | `EvidenceGraph(graph_id,engine,root_node_id,nodes,edges,support_kind,layout_hint,metadata)` + `EvidenceNode/EvidenceEdge` + flat DAG 渲染 | **S3 完全替换**（Q-S3-A 锁定） |
| 2 | `evaluate_result.py:278` | `Explanation.evidence: EvidenceGraph \| None`；不变式 `passed iff evidence is not None` | S5 wire-up（S3 仅建立新类型）|
| 3 | `diagnose_runtime._extend_env_with_atom` | 已有 pred/eq/ne/gt/ge/lt/le/arith/not/in 求值器 | S3 import 复用 |
| 4 | `diagnose_runtime._normalize_where` | 规范化 rule body → OR branches | S3 import 复用 |
| 5 | `protocol/rule_expr_lowering.py` | `RuleExprLoweringPlan`（`branches`, `join_materializations`, `head_binding`）；`RuleExprJoinMaterialization(left_occurrence_alias, right_occurrence_alias, left_port, right_port)` | S3 作为 prober 输入类型 |
| 6 | `application/explain/` | **不存在** | S3 新建 |
| 7 | `explain-layer-complete-design.zh.md §3` | 完整 DTO 形态设计（`EvidenceTree/Rule/Atom`等） | 权威设计参考 |

**Open design questions — S3 启动前锁定**:

| ID | 问题 | 状态 |
|---|---|---|
| Q-S3-A | 新 `EvidenceGraph`（paths）与旧 `audit.EvidenceGraph` 如何共存？ | 已决：不共存，完全替换 |
| Q-S3-B | `EvidenceProbeResult` 形状：仅包含 `paths` 还是也包含 `certainty`/`metadata`？ | → 见 §5 决策 |
| Q-S3-C | `probe_native` 如何获取 `RuleExprLoweringPlan`？行内 lower vs 接收参数？ | → 见 §5 决策 |

## 5. Proposed Shape

### Q-S3-A: 完全替换（已锁定）

**决定**：S3 完全替换旧 `EvidenceGraph`，不保留双轨过渡。Alpha 版本无历史兼容性负担，以最干净的实现为准。
- 旧 `audit/evidence_graph.EvidenceGraph(nodes, edges, root_node_id, support_kind)` 在 S3 中移除。
- 旧 `EvidenceNode` / `EvidenceEdge` / flat DAG 渲染函数 / `evidence_graph_to_dict/from_dict` 一并清理。
- 新 DTO 层（`EvidenceGraph(paths)` + `EvidenceTree` 全家族）接管 `audit/evidence_graph.py` 或迁移到 `application/explain/evidence_tree.py`——具体文件分布由 Codex 决策（Q-S3-B 相关）。
- **S7 并入 S3**：原计划 S7（旧字段删除）不再独立 slice，本 S3 一次性完成。
- Adapters（souffle/problog/pyreason）在 S6 前无法构造新 `EvidenceGraph`；`Explanation.evidence` 暂为 `None`，acceptable（alpha 阶段 native 先行）。

### Q-S3-B / Q-S3-C: 委托 Codex 决策

`probe_native` 的返回值形状、`RuleExprLoweringPlan` 传参方式、`ProbeEnv` 内部接口由 Codex 在实施中决策。约束：
- 结果必须能填充 `EvidenceTree(status, rules, joins)`
- prober 为纯函数（不访问数据库）
- `EvidenceAtom.repr_text = None`（S4 烘焙）

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

- **Q-S3-A 已锁：完全替换** — 旧 `audit/evidence_graph.EvidenceGraph(nodes, edges)` 及 `EvidenceNode/EvidenceEdge` 在 S3 中删除；S7 并入 S3。
- **Adapter converters 输出新 DTO** — souffle/problog/pyreason provenance converter 已改为输出新 `EvidenceGraph(paths)`；S6 仍负责更丰富的 engine-specific atom/rule 填充。
- **新代码 import 私有 helper 可接受**：`from factgraph.application.diagnose_runtime import _extend_env_with_atom`——新文件 import，不修改 `diagnose_runtime.py`。
- **`evaluate_result.py` 的 wire-up 是 S5**：S3 可更新 `Explanation.evidence` 的类型注解以指向新 `EvidenceGraph`，但 prober 接通（实际填充 evidence）是 S5。
- **Certainty import 路径**：`from factgraph.application.protocol.evaluate_result import Certainty`。
- **prober 纯函数**：不访问数据库、不接触 SDK；view_facts 由调用方传入。
- **repr_text = None**：S3 所有 `EvidenceAtom` 的 `repr_text` 保持 `None`；S4 负责烘焙。
- **测试无数据库**：tests 用 mock `view_facts: dict[str, list[tuple]]`。

## 7. Acceptance

- [x] `src/factgraph/application/explain/__init__.py` 存在并导出所有公开 DTO 类型
- [x] `EvidenceGraph`（新）/ `EvidenceTree` / `EvidenceRule` / `EvidenceAtom` 均为 frozen dataclass
- [x] `Holds` / `Fails` / `NotReached` verdict variants 存在
- [x] `probe_native(plan, bindings, view_facts) -> EvidenceProbeResult` 可调用
- [x] native 路径 holds case：`EvidenceTree.status == "holds"`，所有 atoms `verdict = Holds`
- [x] native 路径 fails case：`EvidenceTree.status == "fails"`，失败 atom `verdict = Fails`
- [x] native 路径 not_reached case：未绑定变量的 atom `verdict = NotReached(blocked_by=...)`
- [x] 三层 status 聚合规则正确（holds > fails > not_reached 优先级）
- [x] `EvidenceAtom.repr_text` 为 `None`（repr_text 烘焙不在 S3 scope）
- [x] 旧 `EvidenceNode` / `EvidenceEdge` / `nodes` / `edges` / `root_node_id` / flat DAG renderer 从代码库中消除
- [x] `diagnose_runtime.py` 零 diff（只 import，不修改）
- [x] Focused shipped tests 通过（prober + audit graph + adapter provenance + diagnose native）
- [x] standalone prober tests（mock view_facts）覆盖 holds/fails/not_reached 三种路径

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

Implemented in `69593d36` on `v0.2.0-impl-prober-evidence-tree-2026-06-08`.

Summary:
- Added `factgraph.application.explain` with the new frozen paths-model DTOs and `probe_native(...)`.
- Replaced old `audit/evidence_graph.py` flat DAG implementation with a re-export/serialization bridge for `EvidenceGraph(paths)`.
- Removed old `EvidenceNode` / `EvidenceEdge` / `root_node_id` / flat DAG renderer from the active audit surface.
- Updated Souffle / ProbLog / PyReason provenance converters to emit `EvidenceGraph(paths)` using shallow tree/timeline atoms.
- Updated static UI rendering to show the structured paths payload instead of old HTML DAG rendering.
- Added standalone prober tests and rewrote audit/provenance graph tests for the new model.

Implementation decisions:
- Q-S3-B: `probe_native(...)` returns `EvidenceProbeResult(paths, certainty)`. `EvidenceGraph(...)` assembly remains a caller/S5 responsibility.
- Q-S3-C: `probe_native(...)` accepts a lowering-plan-like input (`branches` / `body_ir`) or raw branch list; it does not call the database.
- File layout: canonical DTO/prober code lives in `application/explain`; `audit/evidence_graph.py` remains as a compatibility import/serialization module for the new shape.

Verification:
- `PYTHONPATH=src python -m unittest tests.test_application_explain_prober tests.test_audit_evidence_graph tests.test_souffle_evidence_graph tests.test_problog_evidence_graph tests.test_pyreason_evidence_graph tests.test_application_diagnose_runtime_native` → 24 tests passed.
- `PYTHONPATH=src python -m compileall -q src/factgraph/application/explain src/factgraph/audit src/factgraph/adapters/problog/provenance.py src/factgraph/adapters/souffle/provenance.py src/factgraph/adapters/pyreason/provenance.py src/service/static_ui.py src/service/runtime_v1` → passed.
- Import sweep for `factgraph.audit`, `factgraph.application.explain`, adapter provenance modules, `service.static_ui`, and `service.runtime_v1` → passed.
- `git diff --check` → clean.
- `src/factgraph/application/diagnose_runtime.py` → zero diff.

Deviations:
- The impl branch was forked from sacred `master @ 562c7419`, so it does not contain later local DTO slices that introduced protocol-level `Certainty`; S3 defines a local `Certainty` in `application/explain/evidence_tree.py`.
- Adapter converters were migrated in S3 to prevent active import/runtime breakage after complete flat-DAG removal. Rich engine-specific rule/atom fill remains S6 scope.
- `support_kind` remains in candidate/support protocol and subject metadata; S3 removes it only as an old `EvidenceGraph` top-level field.
