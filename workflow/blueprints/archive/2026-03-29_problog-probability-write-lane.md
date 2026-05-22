# Task Blueprint: ProbLog Probability Write Lane

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/core/evidence/write_protocol.py`
  - `src/factpy_kernel/adapters/problog/problog_export.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-03-29_problog-probability-write-lane.audit.md](./2026-03-29_problog-probability-write-lane.audit.md)

## 1. Problem

ProbLog fact-level probability is still borrowing the shared `meta.confidence` lane as its input source. That mixes framework-level confidence with engine-specific probability semantics and leaves no canonical write path for user-authored ProbLog fact probabilities.

## 2. Goals

- Add a dedicated `meta["probability"]` write path in the shared write protocol.
- Materialize user-authored fact probability into a canonical shared semantic annotation.
- Keep legacy compatibility by continuing to expose `meta.confidence` when users only provide `probability`.
- Update ProbLog export so canonical semantic probability lanes are read before legacy `meta.confidence`.

## 3. Non-goals

- No new public SDK helper beyond existing `set_field(..., meta=...)`.
- No change to ProbLog result import or accept-time `problog/semantic/probability`.
- No attempt to remove legacy `meta.confidence` reads from all callers in this task.

## 4. Current Context

- 当前实现入口：`set_field()` 通过 `write_protocol.py` 规范化 meta、写入 `MetaRow` 和共享 annotation。
- 当前已知约束：共享 annotation 白名单目前没有 `probability`；ProbLog export 已优先读取 `problog/semantic/probability`，但仍直接 fallback 到 `meta.confidence`。
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-29_problog-fact-probability-canonical-lane.md`

## 5. Proposed Shape

Treat fact-level probability as a first-class write-protocol convention key:

- `meta["probability"]` is accepted and type-checked as a float in `(0, 1]`.
- The write protocol emits `shared/semantic/probability` with observed origin from that meta key.
- `meta_rows` continue to retain `probability` as user metadata.
- If `probability` is provided and `confidence` is absent, normalize meta by deriving `confidence = probability` for legacy compatibility.
- ProbLog export reads probability in this order:
  1. `problog/semantic/probability`
  2. `shared/semantic/probability`
  3. `meta.confidence`
  4. default `1.0`

## 6. Boundaries And Invariants

- 必须保持的边界：`probability` 和 `confidence` 仍是不同语义 lane；自动派生只用于兼容，不改变其语义区分。
- 明确不做的内容：不在本任务内设计新的 dedicated SDK keyword 参数，也不清理所有旧 `meta.confidence` 作者入口。
- 兼容性约束：显式 `meta["confidence"]` 必须优先于自动派生值；已有 `problog/semantic/probability` 仍优先于 shared/user lane。

## 7. Acceptance

- [x] `set_field(..., meta={"probability": x})` 能写出 canonical shared probability lane
- [x] ProbLog export 优先读取 semantic probability annotations，再回退 legacy `meta.confidence`
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. [`write_protocol.py`] Add `probability` as a convention key, shared semantic annotation source, and compatibility-derived confidence source.
2. [`problog_export.py`] Extend fact probability lookup to read `shared/semantic/probability` before legacy `meta.confidence`.
3. Sync affected module docs and archive once code/tests are aligned.

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`
- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.en.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `write_protocol` 现已接受 `meta["probability"]` 作为一等 convention key，并双写为 `shared/semantic/probability` 与 `meta.probability`
  - 当用户未显式提供 `confidence` 时，`write_protocol` 会自动派生 `confidence = probability`，继续保留 shared/meta compatibility projection
  - ProbLog export 的 fact-level probability 读取顺序已更新为 `problog/semantic/probability` → `shared/semantic/probability` → `meta.confidence` → `1.0`
  - 针对 write lane 与 export fallback 的测试已补齐，并通过 full regression（580 tests, 0 failures）
- 与 blueprint 不同的地方：
  - 无实质偏离；实现保持在既定 write-lane + export-priority 范围内
- 为什么会有这些调整：
  - 无额外调整
- 归档说明：
  - 本文件与 audit 已归档到 `docs/blueprints/archive/`
