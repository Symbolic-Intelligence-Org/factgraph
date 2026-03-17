# Task Blueprint: Sidecar Retention And GC

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/_artifact_sidecar.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_durable-artifact-storage.md](./2026-03-17_durable-artifact-storage.md)
  - [2026-03-17_artifact-sidecar-store.md](../archive/2026-03-17_artifact-sidecar-store.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-17_sidecar-retention-gc.audit.md](./2026-03-17_sidecar-retention-gc.audit.md)

## 1. Problem

`artifact-sidecar-store` 已经把 explainability 的 durable readback 补齐，但 sidecar 目前仍然没有生命周期治理。

这在两类 artifact 上的风险并不对称：

- `SupportArtifact`
  - key 是 `support_digest`
  - content-addressed
  - 重复写天然 no-op
  - 体积增长主要受新 support shape 数量影响
- `RuleTraceArtifact`
  - key 是 `rule_run_id`
  - 每次 run 都会生成新的 opaque id
  - 没有内容寻址去重
  - sidecar 目录会随运行次数线性增长

当前 sidecar 里也还没有应用层拥有的 retention metadata plane。

现状只有：

- durable key
- artifact payload bytes
- 文件系统时间元数据（如 `mtime` / `ctime`）

这会带来三个直接问题：

1. 仅依赖 `mtime` 会把 retention 语义外包给文件系统，而不是应用本身。
2. 现有 payload canonical bytes 不能直接混入 retention metadata，否则会破坏 `SupportArtifact` 的 content-addressed collision/no-op 语义。
3. sidecar 还没有枚举、删除或 GC 入口，因此无法定义 operator-facing maintenance 行为。

现在进入 retention/GC 讨论是合理的，因为 durable readback 已经落地，sidecar 已从“设计候选”变成“正在累积真实文件的 durable substrate”。

## 2. Goals

- 为 sidecar 的第一轮 retention / GC slice 定义清晰边界，而不是直接默认采用 `mtime-only`。
- 比较 sidecar retention metadata 的四类候选形状：
  - `mtime-only`
  - sidecar-owned `captured_at_ns`
  - sidecar-owned `captured_at_ns + source_session_id`
  - sidecar journal / index
- 明确 `SupportArtifact` 与 `RuleTraceArtifact` 是否采用不同的 retention 策略，并说明原因。
- 明确 GC 是 maintenance-path/operator-triggered 能力，还是需要进入 runtime hot path。
- 明确 sidecar GC 与 audit package/export completeness 的关系，避免把“已导出”错误地等同于“必须继续 pin 在 sidecar 上”。
- 把 retention policy、maintenance surface、reporting contract 与 deferred 项收口到可直接进入实现的 `scoped` 规格。

## 3. Non-goals

- 本蓝图不直接定义或实现 package pin / exported-artifact protection。
- 不在本轮实现 ledger-aware reference counting，或 `SupportArtifact` 的“是否仍被 ledger 引用”回收策略。
- 不在本轮做 `RuleTraceArtifact` 的 semantic compaction、trace digest、或 canonical trace key。
- 不在本轮把 GC 嵌入 capture-time/runtime hot path。
- 不在本轮做跨多个 sidecar root 的协调式 GC。
- 不把 retention metadata 直接嵌入 `SupportArtifact` / `RuleTraceArtifact` payload canonical bytes。
- 不把 `source_session_id` 定义成 GC ownership key；它如果进入首轮讨论，也只作为 provenance metadata 候选。

## 4. Current Context

- 当前 durable readback 入口已经存在：
  - `FileArtifactSidecar`
  - `Store.__init__(..., artifact_sidecar=...)`
  - `_remember_*` capture-time durable write
  - `_lookup_*` miss fallback + in-memory rehydrate
- 当前 sidecar 文件布局：
  - `support/sha256/<hex>.json`
  - `rule_trace/<rule_run_id>.json`
- 当前 `ArtifactSidecar` protocol 只包含单条 read/write：
  - `write_support(...)`
  - `write_rule_trace(...)`
  - `read_support(...)`
  - `read_rule_trace(...)`
- 当前没有：
  - `iter_*`
  - `delete_*`
  - `gc_*`
  - sidecar-owned metadata file
  - sidecar-owned journal / index
- 当前 retention 可见元数据只有文件系统层：
  - path
  - payload bytes
  - `mtime` / `ctime` 等 OS metadata
- `SupportArtifact` 与 `RuleTraceArtifact` 的 durable economics 已经明确不对称：
  - `SupportArtifact` 由 `support_digest` content-addressed，自然 dedupe
  - `RuleTraceArtifact` 由 `rule_run_id` 标识，当前无 dedupe / compaction 基础
- 当前 audit package 已经把 artifact payload materialize 进 package：
  - package 一旦生成，其完整性不再依赖 sidecar 中原文件继续存在
  - exporter 当前也不会向 sidecar 写“已导出”标记
- Rainbird 参考文档给出的可采纳结论是：
  - interaction/session log 是独立交付层，不应为了方便直接塞进 evidence payload 本体
  - 这个原则直接约束了本蓝图的 metadata-plane 讨论：如果要引入 `captured_at_ns` 或 `source_session_id`，它们必须与 artifact payload canonical bytes 分离

## 5. Proposed Shape

本节收口首轮方案选择，配套 acceptance 也已锁定；蓝图现已进入 `scoped`。

### 5.1 Metadata Plane Options

四种候选的结论如下：

1. `mtime-only`
   - 不采用。
   - 原因不是“不能工作”，而是它把 retention 语义交给文件系统时间，存在 reset、rename 继承、以及测试中不可 freeze 的结构性缺陷。
2. sidecar-owned `captured_at_ns`
   - **首轮采用。**
   - 具体形状为 sidecar-adjacent metadata file，而不是写入 artifact payload canonical bytes。
3. sidecar-owned `captured_at_ns + source_session_id`
   - 作为 future provenance enhancement 保留，但不进入首轮实现。
   - `source_session_id` 不是 GC ownership key，把它一起拉进首轮只会扩大 metadata contract，而不会改善第一轮 TTL correctness。
4. sidecar journal / index
   - 不采用。
   - 它虽然能统一承载更多 metadata，但会引入并发 append、恢复、rotation/index rebuild 等额外复杂度，不适合第一轮。

因此首轮 metadata plane 明确收口为：

- payload file 保持现状：
  - `support/sha256/<hex>.json`
  - `rule_trace/<rule_run_id>.json`
- metadata file 与 payload 同目录并存：
  - `support/sha256/<hex>.meta.json`
  - `rule_trace/<rule_run_id>.meta.json`

metadata row 第一轮只要求能承载：

- `captured_at_ns: int`

首轮不要求写入：

- `source_session_id`
- export/package pin marker
- ledger reference data

这样可以同时保持三条边界：

- artifact payload canonical bytes 完全不变
- `_write_bytes(...)` 的 collision/no-op 语义完全不变
- metadata plane 仍由 sidecar 自己拥有，而不是外包给 OS `mtime`

### 5.2 Retention Asymmetry

首轮明确采用不对称策略：

- `SupportArtifact`
  - 第一轮 **不启用自动 TTL**
  - 保持“写入后保留”，仅支持 operator 手动删除或 root 级清理
  - sidecar 仍写 `captured_at_ns` metadata，为 future policy 留出基础
  - 不启用 TTL 的理由：
    - `support_digest` 已经 content-addressed，自然 dedupe
    - 自动 TTL 收益有限，但会引入“哪个写入赢得 timestamp”这类不必要歧义
- `RuleTraceArtifact`
  - 第一轮 **启用 age-only TTL 设计**
  - 是首轮 GC 的唯一自动回收目标

因此首轮 GC driver 只面向 `RuleTraceArtifact`，不主动扫描或删除 `SupportArtifact` payload。

### 5.3 Maintenance Surface

GC 明确收口为 maintenance-path / operator-triggered 能力，而不是 capture-time inline 行为。

具体形状：

- 不把 GC 方法加进 `ArtifactSidecar` protocol
- 首轮把 GC 作为 `FileArtifactSidecar` 的 concrete maintenance method
- operator script / maintenance caller 自行构造 `FileArtifactSidecar(...)` 并调用该方法

这保证：

- read/write protocol surface 保持最小
- 不把 retention 责任强加给未来所有 sidecar 实现
- 当前 runtime hot path 和 SDK/store 构造路径不需要新增 GC 协议耦合

第一轮 GC 目标形状收口为：

- `gc_rule_trace(ttl_ns: int, *, dry_run: bool = False) -> ...`

返回结果第一轮明确收口为结构化 `GCResult`，至少包含：

- `total_scanned: int`
- `deleted_keys: tuple[str, ...]`
- `deleted_orphan_meta_paths: tuple[str, ...]`
- `skipped_orphan_payload_paths: tuple[str, ...]`
- `failed_keys: tuple[tuple[str, str, str], ...]`
  - shape = `(rule_run_id, path_str, error_message)`

这些字段的目的分别是：

- `total_scanned`
  - 让 operator 可以对 GC pass 做 sanity check
  - 不把“扫描了多少 candidate files”隐含地塞进其他字段长度推导
- `failed_keys`
  - 必须带 path，而不是只带 key
  - deletion/integrity failure 首先是 filesystem 级问题，operator 最需要直接可操作的路径

GC reporting 的其余语义也已冻结：

- age-only TTL
- 调用方提供阈值
- dry-run 可选
- failures 不应 silently swallow 成“看起来回收成功”
- orphan cleanup / skip 也必须进入结构化结果，而不是只做隐式 side effect

### 5.4 Capture-Time Metadata Write

`captured_at_ns` 的来源第一轮采用 constructor injection，而不是 call-site injection。

形状：

```python
FileArtifactSidecar(sidecar_root: Path | str, *, clock: Callable[[], int] = time.time_ns)
```

约束：

- `ArtifactSidecar` protocol 维持当前四个 read/write 方法签名，不新增 `captured_at_ns=...` 参数
- 调用方对时间戳无感知
- 测试可通过 frozen clock 注入稳定时间

原因：

- 不扩张 protocol
- 不让 runtime / SDK / Store 调用方承担时间传参责任
- 仍能获得应用层时间语义和稳定测试能力

metadata 写入时机：

- 仅在 payload first write 成功后写入对应 `.meta.json`
- 对 same-key / same-payload no-op，不重写 metadata
- 这要求 `_write_bytes(...)` 从“只返回 `None`”调整为返回 first-write 信号：
  - `True` = 新 payload 已落盘
  - `False` = 目标已存在且 payload bytes 相同，调用方应视为 no-op

首轮明确采用“`_write_bytes(...) -> bool`”而不是在外层额外 pre-check path existence：

- 避免额外 I/O
- 避免人为扩大 TOCTOU 窗口
- 让 payload durable write 与 metadata first-write 判断共享同一次底层决策

### 5.5 Rule Trace TTL Policy

`RuleTraceArtifact` 的首轮 TTL 策略明确采用 age-only 方案：

- 删除所有 `captured_at_ns` 早于 `now_ns - ttl_ns` 的 rule trace payload + metadata
- `ttl_ns` 由调用方传入
- `now_ns` 在 `gc_rule_trace(...)` 方法入口只快照一次，整个 pass 复用同一个 `now_ns`

首轮不采用：

- count-based retention
- 按 `root_rule_id` / `root_version` 分组的 policy
- “保留最新 K 条 + TTL” 复合策略

原因：

- age-only 与 `captured_at_ns` 直接对应
- 不需要额外索引或排序 contract
- 最容易被 operator 理解和验证

参数约束：

- `ttl_ns <= 0` 直接抛 `ValueError`
- 第一轮不把 `ttl_ns=0` 解释成“删除全部”

原因：

- 这是 maintenance path，不应把明显的调用错误默默解释成全量删除
- fail-closed 比“看起来方便”的 destructive shortcut 更安全

### 5.6 Orphan Handling

首轮需要显式定义 payload / metadata 不一致时的处理方式。

约束：

- `.meta.json` 存在但 payload 不存在
  - 视为 orphaned metadata
  - GC 应记录 warning，并清理该 `.meta.json`
- payload 存在但 `.meta.json` 不存在
  - 视为 legacy / incomplete payload
  - GC 应记录 warning，并跳过该 payload，不做自动删除
- 单个 orphan/integrity 异常不应让整次 GC fail-fast 终止

这样做的原因是：

- orphaned metadata 没有独立价值，删除是安全的
- orphaned payload 在没有 retention timestamp 时无法安全判断 age，自动删除风险高
- GC 的第一轮目标是 lifecycle maintenance，不是把 sidecar 变成严格修复工具

### 5.7 Export Boundary

当前已知边界：

- audit package 与 sidecar GC 在语义上应保持正交
- package 一旦生成，artifact 内容已经固化在 package 内
- sidecar GC 删除一个已经导出的 artifact，不应被视为破坏历史 package 完整性

因此 package pin 不应被偷偷混入第一轮 retention slice，而应保持显式 deferred。

## 6. Boundaries And Invariants

- retention metadata 不能破坏现有 artifact payload canonical bytes 规则。
- `SupportArtifact` 的 content-addressed key 语义必须保持不变。
- `RuleTraceArtifact` 继续使用 opaque `rule_run_id`；本蓝图不顺带引入 trace digest。
- 若首轮采用应用层 metadata，则它必须由 sidecar 自身拥有，而不是依赖文件系统时间碰巧可用。
- `source_session_id` 若被讨论，也应被视为 provenance metadata，而不是 `SupportArtifact` 的所属权证明。
- 本蓝图不预设任何 compaction 语义。

## 7. Acceptance

- [x] sidecar retention metadata plane 已冻结为 sidecar-adjacent `.meta.json` + `captured_at_ns`，且 blueprint 明确记录了为什么未采用 `mtime-only`、`source_session_id` 首轮增强、以及 journal/index。
- [x] `SupportArtifact` 与 `RuleTraceArtifact` 的 retention policy 已明确分离：前者首轮不启用自动 TTL，后者首轮采用 age-only TTL。
- [x] `FileArtifactSidecar` 的首轮扩展面已明确：constructor-level clock injection、payload first-write 后 metadata write、以及 `gc_rule_trace(...)` maintenance method。
- [x] `_write_bytes(...) -> bool` 的 first-write contract 已明确，且 `.meta.json` 只在 payload first write 成功后写入；same-key/same-payload no-op 不得重写 metadata。
- [x] `gc_rule_trace(...)` 的参数与时钟语义已明确：`ttl_ns > 0`，非正值抛 `ValueError`，`now_ns` 在方法入口只快照一次。
- [x] GC 结果 reporting shape 已明确，至少包含 `total_scanned`、`deleted_keys`、`deleted_orphan_meta_paths`、`skipped_orphan_payload_paths`、以及带 `(rule_run_id, path_str, error_message)` 的 `failed_keys`。
- [x] orphan handling 已明确：orphaned metadata 可清理，orphaned payload 必须 skip，不得因单个 orphan/integrity 问题让整次 GC fail-fast。
- [x] audit/export 边界与 deferred 能力已明确记录：package pin、ledger-aware GC、compaction、count-based retention、rule-grouped retention 都保持 deferred。
- [x] 如进入实现，受影响模块 docs 的同步范围已明确。

## 8. Implementation Plan

1. 在 `_artifact_sidecar.py` 落 sidecar-adjacent `.meta.json`、constructor-level `clock` 注入、以及 `_write_bytes(...) -> bool` first-write contract。
2. 在 `FileArtifactSidecar` 落 `gc_rule_trace(...)`、`GCResult` reporting、TTL validation、single-snapshot `now_ns`、和 orphan handling。
3. 用 focused tests 锁定 metadata first-write/no-op、age-only TTL、`ttl_ns <= 0`、orphan policy、failure reporting、以及 deterministic `now_ns` 语义。
4. 实现完成后同步 core/service/SDK docs，并补齐 `Outcome / Deviations` 后再归档。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若引入 service/operator-facing maintenance 入口）
- `src/factpy_kernel/sdk/docs/04_api_surface.md`（若引入 SDK-facing maintenance 入口）
- `docs/README.md`（仅当新增稳定文档入口时）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `FileArtifactSidecar` 现已在首次 durable write 时为 payload 写入 sidecar-adjacent `.meta.json`，metadata row 第一轮承载 `captured_at_ns`。
  - `_write_bytes(...)` 现返回 first-write `bool`，使 metadata 只在 payload 首次落盘后写入；same-key/same-payload no-op 不会重写 metadata。
  - `FileArtifactSidecar.gc_rule_trace(ttl_ns, dry_run=False)` 已实现，返回结构化 `GCResult`，覆盖 age-only TTL、single-snapshot `now_ns`、orphan handling 与带 path 的 `failed_keys` reporting。
  - focused tests 已补齐 metadata first-write/no-op、dry-run、TTL validation、single-snapshot `now_ns`、orphan policy 与 corrupt metadata failure reporting。
  - core 中英文模块 docs 已同步，说明 `.meta.json` metadata plane 与 `gc_rule_trace(...)` maintenance surface。
- 与 blueprint 不同的地方：
  - `GCResult.total_scanned` 按 `rule_trace/` 目录下参与本轮判定的唯一 artifact stem 计数，而不是按原始文件数计数。
- 为什么会有这些调整：
  - 该计数方式可以把 payload/meta 配对视为一个 GC candidate，同时仍把 orphan metadata 单独计入扫描覆盖，更贴近 operator 对“一轮 GC 看过多少 artifact key”的理解。
- 归档说明：
  - blueprint、audit、代码、tests 与 core docs 已对齐，可作为本轮 sidecar retention/GC 的历史 rationale 归档。
