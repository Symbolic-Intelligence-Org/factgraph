# Current Operational Memory

最后更新:2026-04-14

## 当前阶段

Agent 层 + extraction 管道已稳定,重心从"能力建设"转向"对外交付"。

- **最近一次 session handoff**: [session_handoffs/2026-04-13.md](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-04-13.md)(session 3,覆盖 L1-L4C agent 栈 + P0/P1/P2 + F1 + I1+I2 + B3 load harness + notebook 08 + ADE 研究报告)
- **session 3 之后新增(2026-04-13 晚到 2026-04-14)**:
  - Mistral native SDK 修复(`instructor.from_mistral()` + `MISTRAL_STRUCTURED_OUTPUTS`)→ Mistral Small 跑通 10/10 docs,F1=78%,超过 GPT-4.1 F1=68%
  - Validator `field_tag` fallback 修复
  - HTTP API `POST /v1/extraction/documents` 上线(route + handler + 422/500 error envelope + multipart upload)
  - `extract_document()` / `extract_document_from_ir()` 产品级入口
  - 真实 DORA RTS PDF 端到端验证(80 段 → 109 resolved facts,Mistral Small 免费版)
  - `demo/` 目录清理:迁移到 `examples/09_dora_document_extraction.ipynb` + `examples/dora_pdf_extract.py` + Streamlit 蓝图归档为 abandoned

核心判断:

- 项目定位仍是 **auditable reasoning framework**(session 2 结论未变)
- **Mistral Small native SDK 已成为默认推荐**:免费 + EU 管辖权 + F1 78% 高于 GPT-4.1,10/10 可靠性
- Extraction 管道功能验收通过;下一轮需要的是**文档化 + 对同事可用**,不是继续加能力
- `demo/` 目录实验被证实是错位(应归 `examples/`),已纠正

## 当前运行基线

- 测试基线:**1023 tests 全绿**(session 3 handoff 时 1020;+3 来自 HTTP API route tests)
- 分支:`master`
- HEAD:`6009e21`(session 3 handoff commit)
- 工作区有未提交的 extraction/service/test 变更(Mistral native SDK + HTTP API + DORA demo 清理)

## 已验证的对外接口

| 入口 | 用途 | 状态 |
|---|---|---|
| `extract_document(schema_classes=[...], content=bytes)` | Python 产品 API | 已实现 |
| `extract_document_from_ir(schema_ir={...}, content=bytes)` | pre-compiled schema IR 入口(供 HTTP handler 复用) | 已实现 |
| `POST /v1/extraction/documents`(multipart: file + options JSON) | HTTP 前端对接 | 已实现 + route/handler tests |
| `examples/09_dora_document_extraction.ipynb` | DORA 端到端 real-LLM demo | 可跑通 |
| `examples/dora_pdf_extract.py <pdf>` | CLI 真实 PDF 抽取 | 可跑通(2026-04-14 烟测过) |

## Active 蓝图现状

共 15 份 active/(全是 session 2 及之前的遗留:架构决策 v2、dialog agent、problog/pyreason explain、ontology feasibility、market alignment、dialog-agent v1.1 delta)。**没有 extraction / agent 管道的 active 蓝图** — 该线所有蓝图已归档。

- session 3 归档的蓝图都在 `docs/blueprints/archive/`,目前 untracked(还没 commit)
- 今天归档了 `2026-04-14_document-extraction-streamlit-demo`(abandoned)

## 下一步方向

**优先级 1**: 把 extraction/agent 管道对外包装成同事能独立使用的形态
- 蓝图名 `2026-04-14_consumer-usage-handoff.md`(draft → scoped → implementing → implemented)
- 产物预期:
  - `README.md`(仓库根,重写)
  - `src/factpy_kernel/agent/extraction/docs/USAGE.md`(新增 — `extract_document()` 使用手册)
  - `src/factpy_kernel/service/docs/05_extraction.md`(新增 — HTTP DTO 契约)
  - `src/factpy_kernel/service/docs/01_overview.md`(更新 — 添加 `/v1/extraction/documents` 路由)
  - `docs/README.md`(更新 — 索引新增条目)

**优先级 2(延后)**: extraction schema 自身的语义陷阱(`title` 同时做 identity + predicate 在 prose 里会被污染、`.exists` unary 噪声高)。DORA PDF 实跑已经暴露,但属于 schema 设计迭代,不是 blocking 交付。

**不该在这个阶段做的**:
- 不再加 extraction 改进(P3/P4/精度优化等)—— benchmark 报告里有空间但优先级低于交付
- 不再做新 demo/notebook —— `examples/09` 已覆盖 DORA 场景
- 不改 agent 层架构 —— L1-L4C 稳定了

## 未解决的未决点

- `docs/blueprints/active/` 里 session 2 遗留的 ontology / dialog-agent / market-alignment 蓝图需要一次性 triage(哪些已实际完成可归档、哪些继续保留、哪些撤销)—— 但不是本轮优先级
- 仓库根下 `archive/`、`esa_demo_output/`、`dora_demo_output/` 是历史产物区,被 `.gitignore` 的 `/*` 规则吞了,不会污染提交,但如果要彻底清理需要单独一轮

## 启动阅读顺序(新 session 用)

1. [本文件](/Users/zhenzhili/hnsm-backend/memory/current.md)
2. [最近一次 handoff](/Users/zhenzhili/hnsm-backend/memory/session_handoffs/2026-04-13.md)
3. [AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) + [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md)(工作流)
4. [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)(文档体系索引)
5. [agent/extraction/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/agent/extraction/docs/README.md)(当前 extraction 管道真相)
6. [service/docs/01_overview.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/01_overview.md)(HTTP 接口真相)
7. [examples/README.md](/Users/zhenzhili/hnsm-backend/examples/README.md)(demo 入口)
