# Current Operational Memory

最后更新：2026-03-22

## 当前阶段

当前阶段的唯一 active 母蓝图是：

- [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)

当前阶段的核心判断：

- 项目定位是 **auditable reasoning framework**，不是自研 reasoning engine。
- `certainty v1` 已冻结，只作为窄覆盖 heuristic lane 存在。
- 当前 `candidate_evidence_tree` 更接近 audit trail，不是完整 reasoning explanation。
- 下一步优先级不是继续补 delivery pipeline，而是：
  - 真实 ECSS 规则验证
  - Souffle provenance feasibility PoC

## 当前运行基线

- 测试基线：234 tests 全绿
- 分支：`master`
- delivery baseline：
  - runtime explain summary / narrative / NL
  - audit package / query / static site
  - candidate evidence tree
  - certainty v1 export / audit / static delivery

## 当前主风险

- 还没有读并编码真实 ECSS 规则
- 还没有验证规则复杂度是否超出当前 evidence tree 能力
- 还没有验证 Souffle provenance 接入成本与 proof shape

## 当前不应继续扩张的方向

- certainty v1 新功能
- probability lane
- ProofNode implementation
- 更多 narrative / NL / ranking polish

## Handoff Archive

- [2026-03-20.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-20.md)
- [2026-03-21.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-21.md)
- [2026-03-22.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-22.md)

## 启动阅读顺序

1. [当前阶段母蓝图](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
2. [core 架构文档](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
3. [annotation README](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/annotation/docs/README.md)
4. [service runtime docs](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/03_runtime_queries_views.md)
5. [audit overview](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/01_overview.md)
