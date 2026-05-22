# Task Blueprint: Audit Package Artifact Export

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_durable-artifact-storage.md](../active/2026-03-17_durable-artifact-storage.md)
  - [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)
  - [2026-03-17_support-artifact-readback.md](../archive/2026-03-17_support-artifact-readback.md)
  - [2026-03-17_run-rule-trace-capture.md](../archive/2026-03-17_run-rule-trace-capture.md)
  - [2026-03-17_runtime-service-explain-readback.md](../archive/2026-03-17_runtime-service-explain-readback.md)
- Audit Log:
  - [2026-03-17_audit-package-artifact-export.audit.md](./2026-03-17_audit-package-artifact-export.audit.md)

## 1. Problem

当前 explain artifact 已经存在于 runtime 内存 registry 中：

- `Store._support_artifacts`
- `Store._rule_trace_artifacts`

但 audit package 还没有把这些 explain carrier 导出出来。

这意味着：

- package 内只能看到 ledger / decision / candidate 记录
- 看不到 `support_digest` 对应的 `SupportArtifact`
- 看不到 `rule_run_id` 对应的 `RuleTraceArtifact`
- explainability 仍不能被 package consumer 离线重放或审计

在 durable artifact storage 的第一阶段方向已经收口为“先做 audit/export completeness”之后，最自然的第一份实现型切口就是把这两类 artifact 显式加入 audit package。

## 2. Goals

- 为 audit package 增加 `SupportArtifact` 导出文件。
- 为 audit package 增加 `RuleTraceArtifact` 导出文件。
- 明确两类 artifact 在 package 中的 key 语义：
  - `SupportArtifact` 以 `support_digest` 为 key
  - `RuleTraceArtifact` 以 `rule_run_id` 为 package-local opaque key
- 保持当前 runtime service / online readback 行为不变。
- 让 package consumer 能在离线环境下拿到完整 artifact dump，而不仅是 handle。

## 3. Non-goals

- 不实现 cross-session / cross-process online durable readback。
- 不引入 sidecar artifact store。
- 不扩张 ledger schema。
- 不在本轮引入 `RuleTraceArtifact` 的 trace digest / canonical trace key。
- 不在本轮实现 artifact 子集裁剪；第一轮导出全量 registry。
- 不在本轮定义 generic `explain_ref` protocol。

## 4. Current Context

- 当前 runtime explain capture / readback 已完成：
  - `Store.explain_support(support_digest)`
  - `Store.explain_rule_trace(rule_run_id)`
- 当前 artifact registry 仍是 in-process：
  - `_support_artifacts`
  - `_rule_trace_artifacts`
- 当前 audit package 由 [`src/factpy_kernel/adapters/souffle/package.py`](../../../src/factpy_kernel/adapters/souffle/package.py) 导出，已有多个 ledger/log 文件，但没有 artifact dump。
- 当前母蓝图已选定：
  - 第一阶段只做 audit/export completeness
  - `SupportArtifact` 与 `RuleTraceArtifact` 保持不同 durable key 语义
  - `RuleTraceArtifact` 先不引入 secondary digest

## 5. Proposed Shape

- 在现有 audit package 中新增两类 artifact 文件，命名待与当前 package manifest 风格对齐：
  - `support_artifacts.jsonl`
  - `rule_trace_artifacts.jsonl`
- 第一轮按全量 registry 导出：
  - 不做引用子集过滤
  - 不做 GC / dedupe / compaction
- `support_artifacts.jsonl`
  - 每条记录显式包含 `support_digest`
  - artifact payload 复用 `_support.py` 的 JSON-friendly shape
  - row shape 采用与现有 `candidate_ledger.jsonl` / `decision_log.jsonl` 一致的 **flat row** 风格，而不是额外包一层 `"artifact": {...}`
  - 第一轮目标形状：
    ```json
    {
      "support_digest": "sha256:...",
      "kind": "native_binding_v1",
      "root_result_kind": "fact",
      "binding": [["$x", "Alice"]],
      "pred_witnesses": [{"pred_atom_key": "b0.a0:person", "asrt_ids": ["asrt_1"]}],
      "non_fact_steps": [],
      "rule_refs": []
    }
    ```
- `rule_trace_artifacts.jsonl`
  - 每条记录显式包含 `rule_run_id`
  - artifact payload 复用 `_trace.py` 的 JSON-friendly shape
  - row shape 同样采用 flat row，而不是 `"artifact": {...}` 包裹
  - 第一轮目标形状：
    ```json
    {
      "rule_run_id": "rr_123",
      "root_rule": {"rule_id": "r1", "version": "v1"},
      "invocations": [...],
      "generated_at": 1760000000000000000
    }
    ```
- 如当前 package manifest 有集中索引或 file list，需同步增加 artifact files 的 presence / metadata
  - 第一轮预期通过 `audit_files` 增加：
    - `support_artifacts`
    - `rule_trace_artifacts`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不改变现有 service explain 接口
  - 不改变现有 `Store.explain_support(...)` / `Store.explain_rule_trace(...)` 语义
  - 不把 artifact durable write 引入 runtime capture 主路径
- 明确不做的内容：
  - 不做 online durable readback
  - 不做 artifact 引用裁剪
  - 不做 canonical trace digest
  - 不做 ledger-coupled persistence
- 兼容性约束：
  - 现有 audit package consumer 不应因新增 artifact 文件而破坏读取旧文件的路径
  - 若 package metadata 需要扩充，应保持旧 consumer 可忽略新增字段
  - `package.py` 第一轮可直接读取 `store._support_artifacts` 与 `store._rule_trace_artifacts`；若后续需要收紧 `Store` 边界，再单独比较 package-oriented read-only accessor

## 7. Acceptance

- [x] audit package 能导出 `SupportArtifact` 文件
- [x] audit package 能导出 `RuleTraceArtifact` 文件
- [x] `SupportArtifact` 与 `RuleTraceArtifact` 在 package 内的 key 语义被明确并落实
- [x] 没有引入 online durable readback 或 ledger schema 扩张
- [x] 受影响 audit/package docs 已同步

## 8. Implementation Plan

1. 读取当前 audit package 导出结构，确认 file manifest / output layout / metadata 扩展点。
2. 在 package exporter 中接入 `Store` artifact registries 的读取与 JSONL 序列化。
3. 为两类 artifact 增加 package-level file naming 和 row shape。
4. 如存在 manifest/index，补充 artifact file presence 与必要 metadata。
5. 更新 audit/package docs 与相关 contract tests。

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（如需补充 package/export side note）
- `docs/README.md`（仅在新增 durable docs 入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - `src/factpy_kernel/adapters/souffle/package.py` 已为 `package_kind="audit"` 导出新增：
    - `audit/support_artifacts.jsonl`
    - `audit/rule_trace_artifacts.jsonl`
  - 两类 artifact 文件均采用 flat JSONL row：
    - `SupportArtifact` rows 以 `support_digest` 作为显式 key 注入
    - `RuleTraceArtifact` rows 直接复用 `rule_trace_artifact_to_dict(...)` 中已有的 `rule_run_id`
  - `manifest.json` 的 `paths.audit_files` 已同步增加：
    - `support_artifacts`
    - `rule_trace_artifacts`
  - `src/factpy_kernel/audit/docs/01_overview.md` 与 `src/factpy_kernel/service/docs/03_runtime_queries_views.md` 已同步补充 artifact files 说明
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 已新增 package export 回归测试，覆盖 manifest entries 与 flat row shape
- 与 blueprint 不同的地方：
  - 无实质偏移；实现按 scoped 版蓝图收口
- 为什么会有这些调整：
  - 不适用
- 归档说明：
  - 本切片已完成并通过最小编译与 targeted `unittest` 验证；后续若继续推进 online durability，应回到 durable-storage 母蓝图或新开的 sidecar-store 子蓝图，而不是在本文件中继续扩写
