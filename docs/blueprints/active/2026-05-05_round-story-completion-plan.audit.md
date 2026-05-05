# Round Story Completion Plan — Audit Log

- Blueprint: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md)

## Event Log

| Date | Stage | Event | Notes |
|------|-------|-------|-------|
| 2026-05-05 | draft | Master plan created | 收敛后 9 批 + 3 子批结构;Batch 0 inventory rules / branching strategy / suspension protocol 全部冻结 |
| 2026-05-05 | scoped | Restore audit alignment | 蓝图 status 从 draft 对齐为 scoped,与 cross-session anchor 一致;Batch 0 `examples/12_rule_replay_demo.ipynb` 处置改为先 inspect 再删除/迁移 |
| 2026-05-05 | scoped | Batch 0 inventory completed | `examples/11_capabilities_e2e_demo.ipynb` / `examples/README.md` / `tutorials/evidence-pipeline.cn.md` 纳入 Batch 0;`examples/12_rule_replay_demo.ipynb` inspected 后删除,因其引用 reset 前 SDK replay substrate API |

## Decision Notes

### 2026-05-05 — Master Plan Origination

本 plan 起源于"5 capability 已 ship 但 round story 未闭环"的 stable-point 评估。Round 1 / Round 2 评估通过 3 个 subagent 并行完成:Agent X(Batch 0 inventory)/ Agent Y(Batch 4 v0.1.4 lessons)/ Agent Z(Batch 5 ProofFrame 与 status vocab)。基于结论与项目所有者输入,9 批结构 + 3 子批 + Batch 4 前置 + Batch 5 拆分被确定。

### 2026-05-05 — Restore Audit Alignment

Compact 前核验发现 cross-session anchor 已明确命名为 `project_round_story_completion_plan_scoped.md`,但 active blueprint 仍标 `Status: draft`,audit event 也只有 draft stage。为避免 fresh session 误判总控路线尚未冻结,本次将 blueprint status 对齐为 `scoped`。

同时强化 Batch 0 inventory 规则:`examples/12_rule_replay_demo.ipynb` 不允许留在 `examples/`,但 Batch 0 必须先 inspect 当前 notebook 内容,确认是否含可迁移 design note,再删除或迁入 `docs/references/working/<sub>/` 并标明 pre-reset / non-runnable provenance。默认仍是删除,但不允许 mechanical delete。

### 2026-05-05 — Batch 4 ProofFrame 前置

**触发原因:** Agent Z 调研指出,Batch 5 rule ops(disable / replace / add)启动时,binding 可能从"支 A 成立"变为"支 A 失效 + 支 B 救场",Diagnose 只能定位失败 atom,无法报告路径替代。若不前置 ProofFrame,rule ops 输出对用户不可解释。

**决议:** 原 Batch 5(ProofFrame)提前为 Batch 4;原 Batch 4(rule ops)拆为 5a/5b/5c。

**Constraint:** Batch 4 ProofFrame **必须 narrow**:仅 native + fact-overlay path,不做 cross-engine,不 unify capability status enum,不并入 L4/L5/L8。Statuses 限定为 ProofFrame-local 4 个值(`still_valid | invalidated | unknown | superseded_by_full_eval`)。narrative 由 deterministic renderer 消费这些 status 跨 capability 输出统一文字,各 capability 自身 status enum 不动。

### 2026-05-05 — Batch 5 拆分 5a/5b/5c

**触发原因:** Agent Y 调研 v0.1.4 abandoned 蓝图,发现 abandonment 真正原因是 **semantic decomposition**(`param_override` 实为 4 种正交语义被错误 merge),而非 layer 错误。Application-first 不能消除该问题,只能让 decomposition 更早可见。

**决议:** Batch 5 不能作为单批 4-7 session 推进。三子批:

- **5a Rule Disable**:1-2 session,refactor v0.1.3 native overlay 至 application layer。语义已验证。
- **5b Rule Condition Replace**:Step 0 必须三选一(Path A literal-only ship / Path B abandon / Path C 三 DTO 拆),implementation 仅在 Step 0 决议后启动。default 倾向 Path B(若 DTO not crisp)。
- **5c Add Condition + Binding Planner**:Direction G,新 capability,无 v0.1.x prior art。

**Constraint:** rule ops 总约束:不复活旧 SDK substrate;所有 rule action runtime 必须输出 ProofFrame status 消费 Batch 4 narrative。

### 2026-05-05 — Status Enum Unification 否决

**触发原因:** Agent Z 调研发现,看似重叠的 capability status 字面值(`passed/failed/no_candidate/atom_localized`)背后**上下文语义不同**:Check 是 boolean judgment,Why-not 是 set computation completion,Diagnose 是单 binding 诊断。enum 层 unify 是伪需求。

**决议:** Batch 4 不做 enum 层统一;改为 narrative renderer 跨 capability 渲染统一,各 capability protocol DTO 不动。本决议从 Batch 4 scope 中显式排除 enum unification,避免后续争论。

### 2026-05-05 — `examples/12_rule_replay_demo.ipynb` 处置

**触发原因:** Agent X 调研发现,该 notebook 引用 `kernel.sdk.CandidateDiff / EvidenceComparison / ReplayResult` —— **均为 reset 前 SDK substrate API**。留在 examples/ 当前分支上会让 reader 误以为 reset 后这些 API 仍可用。

**决议(写入 §8 Batch 0 Inventory Rules):** 优先删除;若需保留历史则移到 `docs/references/working/<sub>/` 且显式标 "pre-reset design probe, not runnable on current API"。**不允许留在 `examples/`**。

### 2026-05-05 — Batch 0 Inventory Close

**Inspection result:** `examples/12_rule_replay_demo.ipynb` 当前内容是 v0.1.1 preview notebook,直接 import `kernel.sdk.CandidateDiff / EvidenceComparison / ReplayResult` 并调用 `sdk.replay_with_patch(...)`;正文仍指向 reset 前 `docs/references/working/rule-replay/` 与旧 active blueprint。它不含需要迁成 current reference 的新结论。

**Decision:** 删除 `examples/12_rule_replay_demo.ipynb`,不迁移。Batch 0 同时纳入 `examples/11_capabilities_e2e_demo.ipynb`,更新后的 `examples/README.md`,以及临时设计区 `tutorials/evidence-pipeline.cn.md`。

### 2026-05-05 — SDK Shell 推到 Batch 8

**触发原因:** Batch 2 ergonomic 工作存在 scope 漂移风险(application helper 容易扩到 SDK shell)。per `feedback_narrow_public_api.md`,SDK 是 public surface;过早暴露不稳定 application protocol 会绑死。

**决议:** Batch 2 严格只做 application-layer helper / normalizer。SDK shell 与 service routes / release projection / allowlist 共同放 Batch 8(全部 application protocol 稳定后)。Batch 2 不允许任何 `kernel.sdk/` 修改。

### 2026-05-05 — 暂缓项明确(non-goals)

L7 cross-engine evidence translation / L9 UI / L10 sidecar / L11 mutable evidence / §6.7 declarative schema / 新引擎 onboarding / `kernel.sdk` substrate —— 全部本 plan 内**不预留 batch 槽位**。trigger 显式 fire 时单独开新蓝图。本决议 freeze 后续每批不再争 scope。

### 2026-05-05 — Branching Strategy 冻结

每批新开 branch,off 上一批 final state,push origin 作 reference,**不 merge 入 release base**。Master plan 自身在 `v0.1-round-story-plan-2026-05-05` branch(off 当前 demo branch stable head)。Batch 0 因工作量小,可与 master plan branch 合并;Batch 4 / 5a / 5b / 5c / 6 / 7 / 8 mandatory 独立 branch。

### 2026-05-05 — Suspension / Abandonment Protocol

任意批可在任一 sub-step suspend(scope 不清 / 真实需求不存在)或 abandon(Step 0 spike 发现 DTO not crisp)。abandonment 不强制级联;依赖前批输出的批 abandon 时,后批 Step 0.A 重审 entry criteria。Default 各批独立判断。
