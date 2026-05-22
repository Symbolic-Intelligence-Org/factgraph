# Task Blueprint: PyReason Annotation Gap Remediation

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/`
  - `src/factpy_kernel/core/evidence/`
  - `src/factpy_kernel/audit/`
  - `src/factpy_kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
  - [2026-03-27_value-carrying-semantics-v1-decision.md](./2026-03-27_value-carrying-semantics-v1-decision.md)
- Audit Log:
  - [2026-03-28_pyreason-annotation-gap-remediation.audit.md](./2026-03-28_pyreason-annotation-gap-remediation.audit.md)

## 1. Problem

PyReason 的 examples/demo 修复后，typed fact bound 已能进入 `run_pyreason(...)`，但当前实现仍有两类设计-代码偏差：

1. bounded materialization 仍有一处断裂：`build_pyreason_graph(...)` 对 bounded predicate 继续读 `fact["value"]`，没有优先使用 session 已记录的 `bound`
2. annotation pipeline 存在多处不一致：
   - shared `confidence` 在 write protocol 中被写成 `origin="observed"`，与 annotation store decision 中的 derived summary 语义冲突
   - PyReason session 生成的 `confidence` annotation 与 write protocol 双写后的同 key annotation origin 不一致
   - revocation 路径缺少 annotation 双写
   - accept helper 对模板 origin/derivation 约束没有本地校验
   - audit static UI annotation panel 未展示 derivation 列

这些 gap 会让 PyReason demo 输出与冻结决策不一致，也会让 annotation consumer 看到同一个 key 的矛盾语义。

## 2. Goals

- 修复 bounded graph materialization，使 schema 标注为 `pyreason_bounded` 的 predicate 优先使用事实 bound 进入 PyReason graph
- 统一 `shared/derived/confidence` 的 annotation origin 与 derivation 语义
- 让 revocation 继续沿用 shared annotation 双写约束
- 在 adapter accept helper 中本地拒绝非法 annotation template
- 补齐 UI、测试和模块文档，使当前实现与冻结决策一致

## 3. Non-goals

- 不重新设计 annotation data model
- 不扩展新的 annotation namespace/category
- 不处理非 PyReason 的新引擎语义扩展
- 不重做 examples 以外的额外 demo 体验优化

## 4. Current Context

- 当前实现入口：
  - `adapters/pyreason/runner.py` 负责 graph build 与 PyReason fact registration
  - `adapters/pyreason/session.py` 负责 buffered fact + annotation template 生成
  - `core/evidence/write_protocol.py` 负责 shared meta -> annotation dual-write
  - `adapters/pyreason/accept.py` 负责把 session annotation template 落到 ledger
  - `audit/static_ui.py` 负责 annotation panel 渲染
- 当前已知约束：
  - `confidence` 已在决策层冻结为 `shared/derived` summary，不是 observed source/meta
  - PyReason `Fact(...)` bound 通过 fact text `: [lo, hi]` 编码，不是单独参数
  - `AnnotationRow` 的 `origin="derived"` 时必须带 `derivation`
- 当前相关历史蓝图：
  - `2026-03-26_assertion-annotation-store-decision.md`
  - `2026-03-27_value-carrying-semantics-v1-decision.md`

## 5. Proposed Shape

本轮只做 gap remediation，不改分层：

- `session.py` 继续作为 PyReason-specific buffered fact surface，保留 annotation template 生成
- `runner.py` 在 bounded predicate graph materialization 时读取事实 bound，而不是依赖 claim value 重新解析
- `write_protocol.py` 把 shared whitelist 中的 `confidence` 固定为 `category="derived"`, `origin="derived"`，并在 revocation 路径复用同一 annotation projection helper
- `accept.py` 在写入前校验 template 的 `origin/derivation` 组合，避免不合法 template 直到 `Ledger.append_annotations(...)` 才爆炸
- `static_ui.py` annotation panel 增加 `derivation` 展示列

## 6. Boundaries And Invariants

- 必须保持的边界：
  - shared annotation 双写的 canonical 入口仍是 `write_protocol`
  - engine-specific semantic annotation 继续隔离在 engine namespace 下
  - `confidence` 仍保持 float，不引入新的 shared truth model
- 明确不做的内容：
  - 不让 PyReason graph materialization 重新依赖 raw string value 作为 bounded semantics 的真值来源
  - 不让 UI 推断新的 annotation 语义，只展示已有字段
- 兼容性约束：
  - legacy tuple `facts=` API 继续可用，默认 `[1.0, 1.0]`
  - 现有 annotation consumer JSON shape 不破坏；只增加更完整的表格列与更一致的 row 内容

## 7. Acceptance

- [x] bounded materialization 与 `pyreason_bounded` 设计一致
- [x] `confidence` annotation 在 PyReason/session/write_protocol 路径上语义一致
- [x] revocation 路径补齐 shared annotation 双写
- [x] accept helper 会拒绝非法 origin/derivation 组合
- [x] audit static UI 能显示 derivation 字段
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. `adapters/pyreason/runner.py` 调整 bounded graph materialization，并补 runner 测试覆盖 bound 优先级
2. `core/evidence/write_protocol.py` 统一 `confidence` origin，补 revocation annotation dual-write，并同步 write protocol 测试
3. `adapters/pyreason/accept.py` 增加模板校验；`audit/static_ui.py` 增加 derivation 列；同步 adapter/audit 测试
4. 更新 `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md` 与 `src/factpy_kernel/core/docs/01_architecture.md`
5. 跑 targeted unit tests，完成 Outcome / Deviations 并归档 blueprint

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- `src/factpy_kernel/core/docs/01_architecture.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - `runner.build_pyreason_graph(...)` 对 bounded predicate 现在优先使用显式 fact bound 的 lower-bound summary，兼容旧调用方时仍可回退到 raw value 解析
  - `write_protocol` 把 shared `confidence` 统一写成 `origin="derived"`，并通过 `meta["confidence_source"]` 或 `meta:confidence` 补齐 derivation
  - `retract_by_asrt(...)` 现在会对白名单 meta 做 shared annotation 双写
  - `accept.py` 在 materialize `pyreason/*` template 前会本地校验 `origin/derivation`
  - audit annotation panel 新增 `derivation` 列
- 与 blueprint 不同的地方：
  - 没有把 `confidence_source` 单独提升为 write_protocol whitelist annotation；本轮通过 `confidence.derivation` 和 session-side `confidence_source` meta 传递来源说明
- 为什么会有这些调整：
  - 这轮目标是修正已确认的 gap，并避免在 shared annotation whitelist 上做额外 contract 扩张
- 归档说明：
  - blueprint 与 audit 已在实现验证完成后移入 `docs/blueprints/archive/`
