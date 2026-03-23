# Current Operational Memory

最后更新：2026-03-23

## 当前阶段

Active 蓝图：

- **母蓝图**: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md) — Phase 1 验证基本完成
- **ADR**: [2026-03-22_architectural-decisions-v2.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_architectural-decisions-v2.md) — 12 条冻结决策

核心判断：

- 项目定位是 **auditable reasoning framework**，不是自研 reasoning engine
- **Engine-native provenance 优于外部重建** — 在真实 ECSS 数据上实证确认
- Certainty v1 已冻结（16 contracts），只作为窄覆盖 heuristic lane
- Souffle provenance adapter v0 已实现（adapter-local，6 tests）
- ECSS 规则复杂度确认为低到中等，Datalog 完全适配
- **唯一技术阻塞**：`ruleref → Souffle query export` 边界阻止 composed 规则的 provenance

## 当前运行基线

- 测试基线：**240 tests 全绿**
- 分支：`master`
- ECSS demo：9 rules, 2 missions, 5 validation slices, 41 static HTML pages
- Souffle provenance：flat 规则可用（positive + negative proof trees）

## 下一步方向

**解决 `ruleref → Souffle query export` 边界**。这是阻止完整 ECSS demo provenance 的唯一 blocker。涉及 `where_compile.py`，需要开子蓝图。

## 当前不应继续扩张的方向

- certainty v1 新功能
- probability lane
- ProofNode v1 implementation（等 2+ 引擎样本）
- 更多 narrative / NL / ranking polish

## Handoff Archive

- [2026-03-20.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-20.md)
- [2026-03-21.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-21.md)
- [2026-03-22.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-22.md)
- [2026-03-23.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-23.md)

## 启动阅读顺序

1. [当前 handoff](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-03-23.md)
2. [ADR v2](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_architectural-decisions-v2.md)
3. [母蓝图](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
4. [Souffle provenance.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/adapters/souffle/provenance.py)
5. [ECSS demo notebook](/Users/zhenzhili/hnsm-backend/examples/ecss_compliance_demo.ipynb)
6. [core 架构文档](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
7. [annotation README](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/annotation/docs/README.md)
8. [archive inventory](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/README.md)
