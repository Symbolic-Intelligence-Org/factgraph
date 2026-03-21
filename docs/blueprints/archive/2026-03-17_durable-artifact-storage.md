# Task Blueprint: Durable Artifact Storage

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
  - [2026-03-17_run-rule-trace-capture.md](../archive/2026-03-17_run-rule-trace-capture.md)
  - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
- Audit Log:
  - [2026-03-17_durable-artifact-storage.audit.md](./2026-03-17_durable-artifact-storage.audit.md)

## 1. Problem

explainability 当前已经有两条完整链路：

- native derivation
  - `SupportArtifact`
  - `support_digest`
  - `Store.explain_support(...)`
  - service `POST /queries/explain-support`
- rule runtime
  - `RuleTraceArtifact`
  - `rule_run_id`
  - `Store.explain_rule_trace(...)`
  - service `POST /queries/explain-rule-trace`

但这两条链路目前都只依赖 `Store` 的 in-process registry：

- `Store._support_artifacts`
- `Store._rule_trace_artifacts`

因此当前 explain handle 只有 session-scoped / process-local 语义：

- session 关闭后，handle 失效
- 多实例部署下，另一个实例无法解引用同一 handle
- audit package 当前不包含这些 artifact
- ledger 当前也不持久化这些 explain 载体

换句话说，explainability 已经可用，但还不是 durable / replayable / exportable。

## 2. Goals

- 澄清 explain artifact 的 durable storage 问题面，而不是直接进入实现。
- 比较至少三类 durable 承载方式：
  - ledger-coupled
  - audit-package-only
  - sidecar artifact store
- 分别讨论 `SupportArtifact` 与 `RuleTraceArtifact` 的 durable key、写入时机、读取路径、导出路径。
- 明确 durable storage 与以下问题的边界：
  - session lifecycle
  - service explain readback
  - audit/export package
  - future generic `explain_ref`
- 为后续实现型子蓝图提供可收口的方向，但当前不预设一定要落哪一种承载方式。

## 3. Non-goals

- 本蓝图不直接实现 durable storage。
- 不在本轮定义统一的 generic `explain_ref` protocol。
- 不在本轮实现 `candidate_id -> support_digest` 反查。
- 不在本轮实现 cross-instance artifact service。
- 不在本轮冻结 artifact schema 的长期版本化策略。
- 不把 explain artifact 直接混入现有 `CandidateSet`、`assertion` 或 service DTO 主合同。

## 4. Current Context

- 当前 core explain registry：
  - [`src/factpy_kernel/core/store/runtime.py`](../../../src/factpy_kernel/core/store/runtime.py)
  - `_support_artifacts: dict[str, SupportArtifact]`
  - `_rule_trace_artifacts: dict[str, RuleTraceArtifact]`
- 当前 readback：
  - `Store.explain_support(support_digest)`
  - `Store.explain_rule_trace(rule_run_id)`
- 当前 service explain：
  - `POST /queries/explain-support`
  - `POST /queries/explain-rule-trace`
  - 都明确是 session-scoped / in-process / non-durable
- 当前 durable substrate：
  - `Ledger`
    - durable append-only facts / meta / revokes
  - `audit package`
    - 通过 [`src/factpy_kernel/adapters/souffle/package.py`](../../../src/factpy_kernel/adapters/souffle/package.py) 导出
    - 当前已有 `run_ledger.jsonl`、`candidate_ledger.jsonl`、`accept_write_ledger.jsonl`、`decision_log.jsonl` 等文件
- 当前未做：
  - audit package 中没有 `support_artifacts.*`
  - audit package 中没有 `rule_trace_artifacts.*`
  - ledger 中没有专门的 explain artifact durable rows

## 5. Discussion Axes

### 5.1 Durable Key Semantics

当前两类 handle 的稳定性并不对称：

- `support_digest`
  - digest-based
  - 更接近 content-addressed key
  - 天然适合去重与 durable lookup
- `rule_run_id`
  - 运行期生成
  - 当前是 session/process 局部 id
  - 若进入 durable storage，是否保持 opaque run id，还是需要引入 secondary digest / trace hash，仍是开放问题

这里还需要一个额外约束：`RuleTraceArtifact` 当前并不天然适合“直接对 artifact bytes 做 content hash”。

原因是：

- `RuleTraceArtifact` 包含 `invocations`
- 每个 `RuleTraceInvocation` 又包含运行期生成的 `invocation_id`
- 即使两次运行在语义上得到等价的 trace 结构，artifact bytes 也可能因为这些运行期 id 不同而变化

因此，对 `RuleTraceArtifact` 直接做 content hash，当前更接近“运行实例唯一性”，而不是“语义等价去重”。如果后续真要引入 trace digest / trace key，可能需要先定义一个不含运行期 id 的 canonical projection，而不应直接复用现有 readback/capture 形状。

这一点意味着 durable storage 很可能不能简单地把两类 artifact 完全等同对待。

### 5.2 Write Timing

至少有三种时机需要比较：

1. capture-time durable write
   - artifact 一产生就落 durable store
   - 最接近真实运行时
   - 但侵入执行路径、写放大最大

2. export-time materialization
   - 平时只存在内存 registry
   - 在 `package_kind="audit"` 导出时才序列化进 package
   - 对 runtime 侵入最小
   - 但不能解决 session 结束后的在线 readback

3. lazy-on-readback persistence
   - 第一次 explain/readback 时才落 durable store
   - 可能减少写入量
   - 但会把运行时 truth 与持久化 truth 拉开

当前更值得优先比较的是 1 vs 2；3 看起来风险更高，容易引入不一致。

### 5.3 Storage Location Candidates

#### A. Ledger-coupled durable storage

思路：

- 在 ledger 侧增加 explain artifact rows / tables
- `support_digest` / `rule_run_id` 能直接从 ledger 读回

潜在优点：

- durable substrate 已存在
- 与当前 assertion/meta/audit 链接天然接近

潜在问题：

- 会把 explain artifact 强耦合到 ledger schema
- `RuleTraceArtifact` 与 append-only fact ledger 的语义并不天然一致
- 大体积 artifact 可能让 ledger 负担不合适的 payload

#### B. Audit-package-only durability

思路：

- runtime 仍只保留内存 registry
- durable artifact 只在 audit package 导出时写出

潜在优点：

- 不侵入运行时主路径
- 与当前 audit/export 思路一致

潜在问题：

- 不能解决 session 结束后的在线 explain readback
- 不等于真正的 durable storage，只能算 export-time durability

#### C. Sidecar artifact store

思路：

- 在 ledger 之外增加独立的 artifact store / artifact journal
- runtime capture 可写入 sidecar
- audit package 也可从 sidecar 导出

潜在优点：

- 边界最清晰
- 能同时服务 online readback 与 export
- 不必把 artifact schema 直接压进 ledger rows

潜在问题：

- 引入新的 durable subsystem
- key/index/GC/retention 都要单独设计

当前讨论里，这一类方案也许更值得重点比较，但还不应写成既定路线。

补充：本节三类落点与 §5.2 的 write timing 并不是独立无关的。

- `audit-package-only`
  - 天然更接近 `export-time materialization`
- `ledger-coupled`
  - 更接近 `capture-time durable write`
- `sidecar artifact store`
  - 可以同时支持 `capture-time durable write`，也可能被设计成较弱的 `lazy-on-readback persistence`

后续若要把讨论从 `draft` 收到 `scoped`，很可能需要把 “storage location × write timing” 压成一张更明确的比较矩阵，而不是继续分开比较。

### 5.4 Export Boundary

当前 audit package 已经是最接近 durable explain 的现有落点之一，因此至少需要讨论：

- `support_artifacts.jsonl` 是否应进入 audit package
- `rule_trace_artifacts.jsonl` 是否应进入 audit package
- 这些文件是全量 artifact dump，还是只导出 run/package 实际引用到的子集
- manifest 是否需要增加 artifact file index / digest

如果 durable storage 最终不走 audit-package-only，audit package 也很可能仍然是第一批 durable consumer。

### 5.5 Retention, GC, And Rehydration

durable artifact 一旦落地，就会出现新的运维问题：

- artifact 是否永久保留
- 是否按 run / package / session / age 做 GC
- `support_digest` 是否允许 dedupe
- `rule_run_id` 若没有 secondary content digest，如何做 dedupe / compaction
- service explain miss 时，是否允许从 durable storage rehydrate 回 store registry

这些问题当前都不该在没有蓝图的情况下直接进入实现。

## 6. Resolved Questions

1. `SupportArtifact` 是否更适合先走 content-addressed durable path，而 `RuleTraceArtifact` 暂时只进 export/package？  
   - 当前结论：**是**。
   - `support_digest` 已经是 content-addressed key，天然适合作为 durable artifact key。
   - `RuleTraceArtifact` 目前仍以 `rule_run_id` 作为运行期 opaque handle；在没有额外 canonical projection 的前提下，不应强行把它推进到 content-addressed path。

2. durable storage 的第一阶段目标是 online readback continuity、audit/export completeness，还是两者同时？  
   - 当前结论：**先只做 audit/export completeness**。
   - 第一阶段不解决 cross-session / cross-process online continuity，不引入新的在线 durable readback 依赖。
   - 这允许系统先把 artifact 从“只活在内存里”推进到“可被导出和持久化消费”。

3. 若要支持在线 durable readback，最小实现是否需要独立 sidecar store，而不是扩张 ledger？  
   - 当前结论：**需要 sidecar store，但不属于第一阶段范围**。
   - `SupportArtifact` 与 `RuleTraceArtifact` 都更接近 explain carrier，而不是 ledger 的一等 durable row。
   - 若后续真要支持 online durable readback，优先比较独立 sidecar store，而不是扩张 ledger。

4. audit package 是否应只导出引用到的 artifact，而不是全量 session registry？  
   - 当前结论：**第一轮导出全量 session registry**。
   - 当前 audit package 其他 ledger/log 文件本身就是全量 dump。
   - 引用子集裁剪需要额外建立 artifact usage index，不应进入第一阶段。

5. `rule_run_id` 若要 durable，是否需要引入 trace digest / trace key？  
   - 当前结论：**第一轮不需要**。
   - 在 export/package completeness 目标下，`rule_run_id` 作为 package 内的 opaque id 已足够。
   - trace digest / canonical trace key 留到 future online durable readback / sidecar-store 方向再比较。

## 7. Selected Direction

当前已收口的工作方向如下：

- durable artifact storage 的**第一阶段只做 audit/export completeness**
- `SupportArtifact` 与 `RuleTraceArtifact` 的 durable 策略**刻意分开**
  - `SupportArtifact`
    - durable 语义继续以 `support_digest` 为主
    - 第一阶段通过 audit package export 把现有 content-addressed artifact 写出
  - `RuleTraceArtifact`
    - 第一阶段只在 package 内以 `rule_run_id` 作为 opaque key 写出
    - 暂不引入 trace digest / canonical trace key
- 第一阶段**不扩张 ledger**
- 第一阶段**不做 online durable readback continuity**
- 第一阶段的实现切口为：
  - `audit-package-artifact-export`
  - 目标是让 audit package 在现有 ledger/log 文件之外新增 artifact files 与 minimal manifest/index

## 8. Acceptance

- [x] durable artifact storage 的问题面被单独拆清，不再混在 generic explain 讨论里
- [x] ledger / audit-package / sidecar 三类候选落点都被比较
- [x] `SupportArtifact` 与 `RuleTraceArtifact` 的 durable key 差异被显式讨论
- [x] export boundary 被明确纳入比较
- [x] 为后续实现型子蓝图收口出更具体的切口

## 9. Next Slice Candidates

本蓝图当前已选定的第一份实现型子蓝图是：

1. `audit-package-artifact-export`
   - 只为 audit package 增加 artifact files
   - 第一阶段默认导出全量 session registry
   - `SupportArtifact` 继续以 `support_digest` 为 durable handle
   - `RuleTraceArtifact` 暂以 `rule_run_id` 作为 package 内 opaque key
   - 当前已拆为并完成子蓝图：[2026-03-17_audit-package-artifact-export.md](../archive/2026-03-17_audit-package-artifact-export.md)

当前后续切口完成情况如下：

2. `artifact-sidecar-store`
   - 只做 online durable readback 的 sidecar store
   - gap audit 曾证伪先前的虚假归档状态；现已按真实实现完成并归档：[2026-03-17_artifact-sidecar-store.md](../archive/2026-03-17_artifact-sidecar-store.md)
3. `candidate-support-backref`
   - 在 durable artifact 语义稳定后，再讨论 `candidate_id -> support_digest`
   - 当前已拆为并完成子蓝图：[2026-03-17_candidate-id-support-backref.md](../archive/2026-03-17_candidate-id-support-backref.md)
4. `sidecar-retention-gc`
   - Retention metadata plane 和 `RuleTraceArtifact` age-only GC。
   - 已实现并归档：[2026-03-17_sidecar-retention-gc.md](../archive/2026-03-17_sidecar-retention-gc.md)

## 10. Outcome / Deviations

- 最终落地结果：全部 4 个 child slice 已实现并归档。
  1. `audit-package-artifact-export` — audit package 导出 artifact files（全量 session registry）
  2. `artifact-sidecar-store` — file-backed sidecar carrier，Store constructor injection，cross-store readback
  3. `candidate-id-support-backref` — `candidate_id → support_digest/support_kind` session-scoped backref index
  4. `sidecar-retention-gc` — sidecar-adjacent `.meta.json`，`RuleTraceArtifact` age-only TTL GC
- 与 blueprint 不同的地方：
  - §7 Selected Direction 原计划"第一阶段只做 audit/export completeness"，实际推进中 sidecar store + backref + GC 也在同一批次落地，覆盖了原定后续阶段的 online durable readback 能力。
  - §3 Non-goals 中的 "`candidate_id -> support_digest` 反查"实际已在 backref child slice 中实现（session-scoped）。
- 为什么会有这些调整：evidence tree 六轮实现需要 candidate → support 的 readback 链路作为前置；sidecar store 的 gap audit 发现先前归档状态不实，触发了真实实现。
- 归档说明：母蓝图移至 `docs/blueprints/archive/`。所有 acceptance criteria 已满足，4 个 child slice 均已独立归档。
