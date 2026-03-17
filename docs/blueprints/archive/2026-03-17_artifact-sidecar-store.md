# Task Blueprint: Artifact Sidecar Store

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_artifact_sidecar.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_audit-package-artifact-export.md](../archive/2026-03-17_audit-package-artifact-export.md)
- Audit Log:
  - [2026-03-17_artifact-sidecar-store.audit.md](./2026-03-17_artifact-sidecar-store.audit.md)

## 1. Problem

当前 explainability 已经解决了 capture 与 session 内 readback，也已解决 audit package export completeness，但 online durable readback 仍然缺失。

Reconciliation note:

- 本子蓝图曾被错误标记为 `implemented` 并提前归档。
- gap audit 未找到对应的可验证实现证据，因此本文件已恢复到 `active/` 并回滚到 `scoped`。
- 后续只有在代码、测试与模块 docs 均完成并可核对时，才允许再次进入 `implemented` / `archive`。

现状：

- `SupportArtifact` 只存在于 `Store._support_artifacts`
- `RuleTraceArtifact` 只存在于 `Store._rule_trace_artifacts`
- `Store.explain_support(...)` 与 `Store.explain_rule_trace(...)` 都只解引用当前进程内 registry

这意味着：

- 只要 session / 进程结束，旧的 `support_digest` 与 `rule_run_id` 就无法在线读回
- 即使 operator 已经把 artifact export 到 audit package，也没有一个面向运行态 readback 的 durable substrate
- durable explain 仍然停留在离线 package，而没有进入在线 readback 路径

母蓝图已经明确：如果要补 online durable readback，优先方向应是独立 sidecar store，而不是扩张 ledger。

## 2. Goals

- 为 `SupportArtifact` 与 `RuleTraceArtifact` 引入一个最小可用的 sidecar durable store。
- 让共享同一 sidecar root 的不同 `Store` 实例能够跨 session / 进程读回旧 artifact。
- 保持现有 `Store.explain_support(...)` / `Store.explain_rule_trace(...)` 与 service explain endpoint 形状不变。
- 复用现有 artifact JSON-friendly row shape，避免为 sidecar 再定义一套新 codec 语义。
- 明确 sidecar 接入点、fallback 位置、写失败语义与当前 audit export 的边界。

## 3. Non-goals

- 不定义 generic `explain_ref` protocol。
- 不把 `candidate_id -> support_digest` 扩展成 durable index。
- 不为 `RuleTraceArtifact` 引入 canonical trace digest / trace key。
- 不把 sidecar 反向并入 ledger schema。
- 不在本轮让 audit package exporter 直接遍历 sidecar 全量内容。
- 不在本轮实现自动 GC / retention / compaction；artifact 生命周期先保持“写入后保留，直到 operator 手工清理 sidecar root”。

## 4. Current Context

- 当前 `Store` 的 explain registry 全在内存：
  - `_support_artifacts`
  - `_rule_trace_artifacts`
- 当前 explain readback 入口：
  - `Store.explain_support(support_digest)`
  - `Store.explain_rule_trace(rule_run_id)`
- 当前 audit package 已能导出：
  - `support_artifacts.jsonl`
  - `rule_trace_artifacts.jsonl`
- 当前已具备：
  - `SupportArtifact` / `RuleTraceArtifact` 的 row-shape `from_dict(...)` rehydrate helper
  - `src/factpy_kernel/core/store/_artifact_sidecar.py` 的 file-backed carrier
  - `Store.__init__(..., artifact_sidecar=...)` 注入点
  - `_lookup_support_artifact(...)` / `_lookup_rule_trace_artifact(...)` 的 sidecar miss fallback + in-memory rehydrate
  - runtime / SDK 对 sidecar root 的显式配置入口
  - core / service / SDK 模块 docs 同步
  - focused unittest 与 full contract suite，覆盖 carrier 语义、跨 `Store` / 跨 session / 跨 SDK 实例 readback，以及 sidecar integrity error propagation

## 5. Proposed Shape

### 5.1 Store Attachment Model

`Store` 通过 constructor injection 接收可选 `artifact_sidecar`。

原因：

- sidecar 是生命周期级依赖，而不是像 engine evaluator 一样可中途切换的策略
- 避免“先 capture 了一批非 durable artifact，后面才 attach durable store”的半配置状态

service / SDK 层若要暴露 operator-facing 配置，负责把路径参数转换成 sidecar 实例，再注入 `Store(...)`。

第一轮 constructor signature 收口为：

```python
def __init__(
    self,
    schema_ir: dict,
    ledger: Ledger | None = None,
    *,
    engine_evaluator: EngineEvaluatorFn | None = None,
    artifact_sidecar: ArtifactSidecar | None = None,
) -> None:
```

其中 `artifact_sidecar` 为 keyword-only，可选，默认 `None`，与现有 `engine_evaluator` 并列。

### 5.2 Sidecar Carrier

第一轮 sidecar 采用 file-backed layout：

- `support/sha256/<hex>.json`
- `rule_trace/<opaque-rule-run-id>.json`

payload 直接复用当前 artifact export row shape：

- support row = `{"support_digest": ..., **support_artifact_to_dict(...)}`
- rule-trace row = `rule_trace_artifact_to_dict(...)`

这样 sidecar codec 与 audit export 保持对齐，只新增“按 key 单条读写”的 carrier，而不新增第二套 payload contract。

第一轮 carrier contract 收口为：

```python
class ArtifactSidecar(Protocol):
    def write_support(self, support_digest: str, artifact: SupportArtifact) -> None: ...
    def write_rule_trace(self, rule_run_id: str, artifact: RuleTraceArtifact) -> None: ...
    def read_support(self, support_digest: str) -> SupportArtifact | None: ...
    def read_rule_trace(self, rule_run_id: str) -> RuleTraceArtifact | None: ...
```

语义：

- read miss 返回 `None`，而不是异常。
- write 在 same key / same payload 时视为 no-op。
- write 在 same key / different payload 时视为 collision error，必须抛错。
  - collision 第一轮统一抛 `ValueError`
  - message 约定为：
    - `support_digest collision for different SupportArtifact on disk: {support_digest}`
    - `rule_run_id collision for different RuleTraceArtifact on disk: {rule_run_id}`

第一轮 file-backed carrier 命名为 `FileArtifactSidecar`，constructor 接收 `sidecar_root: Path | str`，内部统一归一化为 `Path`。

key 到文件路径的映射：

- `support_digest`
  - 第一轮只接受 `sha256:` 前缀
  - 通过 strip `sha256:` 得到 `<hex>`
  - 持久化路径为 `support/sha256/<hex>.json`
  - 若前缀不是 `sha256:`，直接抛错；future digest families 留给后续扩展
- `rule_run_id`
  - 第一轮直接把 opaque id 用作文件名
  - 持久化路径为 `rule_trace/<rule_run_id>.json`
  - 当前 `rule_run_id` 来自 `uuid4().hex`，因此在现有实现下是 filesystem-safe
  - carrier 仍需做最小防御性校验：若 `rule_run_id` 含 `/`、`\` 或 null byte，直接抛 `ValueError`

写入语义：

- `FileArtifactSidecar` 必须使用 temp file + `os.replace()` 做原子落盘，避免崩溃时留下半写文件。
- directory creation 可以是 lazy 的，但必须在单条 artifact write 之前完成。
- temp file 约定为 `tempfile.mkstemp(dir=path.parent, suffix=".tmp")`
- temp file 必须与目标文件位于同一目录，以保证 `os.replace()` 落在同一文件系统上
- 若写临时文件或 replace 过程抛错，必须在 `finally` 中尝试删除 temp file，并忽略 cleanup miss / unlink failure

碰撞检测：

- 第一轮采用 deterministic raw bytes compare，而不是 dict compare 或 dataclass round-trip compare
- 这要求 sidecar payload encoding 复用单一的 canonical JSON bytes 规则（`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`）
- carrier 采用 check-then-write：
  - 目标文件已存在时，先读取现有 bytes
  - same bytes 则直接返回
  - different bytes 则立即抛 collision error，不产生 temp file
  - 仅当目标文件不存在时，才进入 temp-write + `os.replace()` 流程

并发语义：

- 第一轮不引入 process-local 或 thread-local lock。
- v1 依赖文件系统的原子 rename 保证单次写入的文件完整性，而不是提供通用的多 writer 协调协议。
- 对已经存在的目标文件，carrier 必须执行 payload equality / collision 检查。
- 对“多个 writer 同时竞争写入同一个此前不存在的 key”的场景，v1 不承诺强一致的 collision arbitration；该场景不应被视为 sidecar 的并发协调主用法。

module boundary：

- 第一轮不把 `ArtifactSidecar` / `FileArtifactSidecar` 重新导出到 `factpy_kernel.core.store` facade
- 调用方直接使用 underscore module import：
  - `from factpy_kernel.core.store._artifact_sidecar import FileArtifactSidecar`
- `factpy_kernel.core.store.__init__` 继续只承载当前已有的稳定 facade 项

### 5.2.1 Row Round-trip Helpers

在引入 sidecar carrier 之前，需要先补齐 artifact row shape 的反向恢复能力。

第一轮收口为 module-level helper，而不是 dataclass method：

- `support_artifact_from_dict(row: Mapping[str, Any]) -> SupportArtifact`
- `rule_trace_artifact_from_dict(row: Mapping[str, Any]) -> RuleTraceArtifact`

约束：

- 输入 shape 必须直接对齐当前 audit/export 的 flat row，而不是 sidecar 私有格式
- helper 负责把 JSON row 恢复回 dataclass 所需的 tuple / sorted items 形状
- `{"__bytes_hex__": ...}` 这样的现有 JSON lifting 也必须可逆
- `support_digest` / `rule_run_id` 仍由 sidecar key 层负责，artifact helper 不额外发明新的 envelope

明确决策：

- leaf value fidelity
  - round-trip fidelity 只覆盖 artifact schema 自身定义的结构容器，以及 `bytes` 的 `{"__bytes_hex__": ...}` lifting。
  - `Any`-typed leaf 值（如 binding values、detail values、`original_where`、`rewritten_where`、`output_rows` 单元格）在读回后只要求保持 JSON-native 语义。
  - 若某个 leaf value 原本是 Python `tuple`，经 `_to_jsonable(...)` 写出并读回后变成 `list`，第一轮 **不视为 fidelity violation**。
- validator execution
  - `from_dict(...)` helper 必须通过正常 dataclass 构造路径创建对象，因此 `__post_init__` invariants 正常执行。
  - 若 sidecar / export row 触发 validator 报错，按 durable storage integrity error 处理，而不是把它归因于 helper API 本身。
- extra keys
  - `from_dict(...)` helper 应静默忽略 schema 之外的 key。
  - 这允许同一个 helper 同时接受裸 artifact payload 和带 envelope key 的 sidecar row / export row；调用方不需要先手工 strip `support_digest`、`rule_run_id` 等外层字段。
- rule-trace where payloads
  - `original_where` 与 `rewritten_where` 视为不透明 JSON-native 值。
  - round-trip 时不深入做 `_from_jsonable(...)` 反向恢复；其中若嵌套出现 `{"__bytes_hex__": ...}` 也保持原样 dict 返回。
  - 第一轮不尝试重建原始 Python container 类型、bytes leaf，或 DSL AST object。

这样可以保持职责分离：

- `_support.py` / `_trace.py` 负责 artifact schema round-trip
- `_artifact_sidecar.py` 只负责 key 到 row 的 carrier
- audit export 与 sidecar persistence 继续共享同一 payload contract

### 5.3 Write Timing

第一轮采用 capture-time durable write：

- `SupportArtifact` 在 `_remember_support_artifact(...)` 首次登记时写 sidecar
- `RuleTraceArtifact` 在 `_remember_rule_trace_artifact(...)` 首次登记时写 sidecar

写 sidecar 必须发生在新的 in-memory commit 之前；若 durable write 失败，本次 remember 直接失败，不能留下“内存成功 / durable 失败”的半成功状态。

接入到 `Store._remember_support_artifact(...)` / `_remember_rule_trace_artifact(...)` 时，第一轮只在 `existing is None` 分支触发 sidecar write：

- `existing is None`
  - 若配置了 sidecar，先写 sidecar
  - sidecar 成功后再写入 in-memory registry
- `existing == artifact`
  - 直接 return
  - 不再重复触发 sidecar I/O
- `existing != artifact`
  - 保持当前 collision error 语义

### 5.4 Fallback Location

sidecar fallback 放在 `_lookup_support_artifact(...)` / `_lookup_rule_trace_artifact(...)`，而不是 `explain_*`。

原因：

- `_lookup_*` 是 artifact resolution 层，`explain_*` 只是 render 层
- sidecar hit 后可统一 rehydrate 当前 session registry
- 未来若有其他内部调用者复用 `_lookup_*`，也能自动获得 durable fallback

语义：

1. 先查内存 registry
2. miss 时查 sidecar
3. hit 时把 artifact 直接回填到当前 registry dict
4. 再按既有 explain/render 路径返回

第一轮 rehydrate 不通过 `_remember_*` 重新登记，而是直接写入对应的 in-memory artifact dict：

- 避免在 sidecar hit 后再触发一次 no-op sidecar write
- 避免把“cache miss rehydrate”混同于“new artifact capture”
- 避免未来在 `_remember_*` 中新增 durable side effect 时形成意外递归或重复 I/O

### 5.5 Failure Semantics

第一轮采用 fail-closed：

- 未配置 sidecar：保持现状，无 durable 承诺
- 已配置 sidecar：首次 artifact durable write 失败时，直接抛错并中断当前 capture / rule-trace 生成流程

不采用 silent ignore 或仅 warning 的原因是：一旦 operator 显式启用 sidecar，就意味着句柄被承诺为 durable；吞掉写失败会制造虚假的 durability。

同样地，`_lookup_*` 中若 sidecar read 过程抛错（例如坏 JSON、decode 失败、`from_dict(...)` validator 失败），第一轮也应直接向上传播，而不是当作 miss 吞掉：

- 这是 durable storage integrity error，不是“artifact 不存在”
- 若把它降级成 miss，会掩盖真实的 sidecar 损坏或协议漂移
- 这与本节的 fail-closed 原则保持一致

### 5.6 Durable Key Semantics

- `SupportArtifact`
  - durable key 继续使用 `support_digest`
  - sidecar 允许天然去重；同 key 同 payload 为 no-op，不同 payload 视为 collision
- `RuleTraceArtifact`
  - durable key 继续使用 opaque `rule_run_id`
  - 第一轮不做跨 run dedupe，也不承诺语义等价 trace 合并

### 5.7 Service / SDK Surface

第一轮允许 runtime / SDK 显式配置 sidecar root：

- runtime session open DTO 增加可选 `artifact_store_root`
- `SDKStore` / `SDKStore.from_schema_classes(...)` 增加可选 `artifact_store_root`

若未提供该参数，行为保持现状。

第一轮参数类型与校验约定：

- `artifact_store_root` 在 service DTO 与 SDK public surface 上统一使用 `str | None`
- 该参数与现有 `ledger_path: str | None` 保持同风格
- path normalization 继续下沉到 `FileArtifactSidecar(artifact_store_root)` 内部完成

runtime session open：

- `open_runtime_session(...)` 对 `artifact_store_root` 采用与 `ledger_path` 一致的输入校验路径：
  - `_optional_str(dto.get("artifact_store_root"), path="$.artifact_store_root")`
- 第一轮不在 open 阶段主动创建 sidecar directory
- directory 仍由 `FileArtifactSidecar` 在首次 durable write 时 lazy 创建

SDK surface：

- 第一轮在 `SDKStore.__init__(...)` 与 `SDKStore.from_schema_classes(...)` 都暴露 `artifact_store_root: str | None = None`
- 若调用方已直接传入 `store=Store(...)`，则 `artifact_store_root` 与现有 `schema_ir` 一样只作为被忽略的辅助参数，不再额外报错
- 若未传 `store`，则 SDK 构造路径负责在内部创建 `FileArtifactSidecar(artifact_store_root)` 并注入 `Store`

session dict 回显：

- 第一轮 `_session_to_dict(...)` 不回显 `artifact_store_root`
- `artifact_store_root` 被视为配置输入，而不是 session runtime state
- 这与 `engine_evaluator` 等依赖不出现在 session dict 中的现有风格保持一致

### 5.8 Audit Export Interaction

当前 audit exporter 继续以当前 session registry 作为直接输入，不改成 sidecar dump。

交互边界：

- sidecar 与 audit export 复用相同 artifact row codec
- sidecar miss-rehydrate 命中的 artifact 会重新进入当前 registry，因此仍可被当前 session 的 package export 带出
- 但“仅靠 sidecar root 即导出全量历史 artifact”不属于本轮范围

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `Store.explain_support(...)` / `Store.explain_rule_trace(...)` 返回 shape 不变
  - service explain endpoint shape 与错误 kinds 保持兼容
  - `SupportArtifact` 与 `RuleTraceArtifact` 继续分开建模，不引入统一 explain carrier
- 明确不做的内容：
  - 不做 durable candidate-support backref
  - 不做 automatic GC / TTL
  - 不做 sidecar manifest / index 服务
  - 不做 package exporter 从 sidecar 全量扫描
- 兼容性约束：
  - sidecar 是 opt-in；未配置时行为必须与当前版本一致
  - sidecar payload 必须能从现有 export row shape round-trip 回 artifact dataclass
  - collision 检查必须保留：同 key 对应不同 payload 仍视为错误

## 7. Acceptance

- [x] `SupportArtifact` 与 `RuleTraceArtifact` 均具备基于当前 export row shape 的 `from_dict` round-trip helper
- [x] `Store` 支持可选 sidecar 注入
- [x] `SupportArtifact` 能跨 `Store` 实例 durable readback
- [x] `RuleTraceArtifact` 能跨 `Store` 实例 durable readback
- [x] sidecar fallback 收口在 `_lookup_*`，成功时会 rehydrate 当前内存 registry
- [x] sidecar 配置入口在 service / SDK 上可用，且未配置时兼容旧行为
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 在 `_support.py` 与 `_trace.py` 上补齐 `from_dict` round-trip helper，验证其与当前 audit/export row shape 完全对齐。
2. 在 core/store 引入 file-backed sidecar carrier，复用上述 row codec，而不是在 sidecar 层另起一套 schema。
3. 在 `Store` 上接入 constructor injection、capture-time durable write 和 `_lookup_*` miss fallback。
4. 把 runtime session open 与 SDK 构造入口接到可选 `artifact_store_root`。
5. 增加 targeted tests，覆盖跨实例 readback、rehydrate 行为和未配置 sidecar 的兼容路径。
6. 更新 core / service / SDK docs，并在母蓝图 audit 中记录此切片重新进入 active/scoped。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`
- `src/factpy_kernel/service/docs/02_runtime_sessions.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.en.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/factpy_kernel/sdk/docs/04_api_surface.md`
- `src/factpy_kernel/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `src/factpy_kernel/core/store/_artifact_sidecar.py`，提供 `ArtifactSidecar` / `FileArtifactSidecar`
  - `SupportArtifact` / `RuleTraceArtifact` 均已补齐 row-shape round-trip helper；`RuleTraceArtifact` 额外补齐 canonical `rule_trace_artifact_bytes(...)`
  - `Store` 现支持可选 `artifact_sidecar` constructor injection，并在 `_remember_*` 上做 first-write durable persistence，在 `_lookup_*` 上做 sidecar miss fallback + direct registry rehydrate
  - runtime session open DTO 新增可选 `artifact_store_root`；共享同一 root 的后续 session 可继续 explain support / rule trace
  - `SDKStore.__init__(...)` 与 `SDKStore.from_schema_classes(...)` 均新增可选 `artifact_store_root`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 focused sidecar tests 与 runtime / SDK cross-instance readback tests，并通过 full contract suite
  - core / service / SDK 模块 docs 已同步说明：默认 explain 仍是 in-process / session-scoped，`artifact_store_root` 为 opt-in durable readback 开关
- 与 blueprint 不同的地方：
  - 无实质偏移；实现最终仍保持 file-backed sidecar、check-then-write、fail-closed、以及 runtime/SDK 显式 opt-in 的 scoped 边界
- 为什么会有这些调整：
  - 中途先做了 gap-audit reconciliation，把一份虚假的 `implemented` / archived 子蓝图恢复回 active，再按真实代码与测试逐层补齐 helper、carrier、Store wiring、runtime/SDK surface 和 docs
- 归档说明：
  - 本切片现已满足 blueprint acceptance；后续若继续讨论 retention / compaction / sidecar-wide export / multi-writer coordination，应另开新子蓝图，而不是在本文件继续扩写
