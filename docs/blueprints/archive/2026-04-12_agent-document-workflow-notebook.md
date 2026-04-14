# Blueprint: Agent Document Workflow Notebook (Notebook 08)

- Status: implemented
- Created: 2026-04-12
- Kind: **example / documentation** (not a code change)
- Trigger: Agent layer L1→L4C 全部完成后,缺少 agent 层面的公开 example — examples/ 目录只有 SDK/engine notebooks (01-07),无 agent demo
- Related Modules:
  - `examples/08_agent_document_workflow.ipynb`
  - `examples/README.md`
- Audit Log:
  - [2026-04-12_agent-document-workflow-notebook.audit.md](./2026-04-12_agent-document-workflow-notebook.audit.md)

---

## 0. Scope

创建 `examples/08_agent_document_workflow.ipynb` — agent layer 的 flagship demo notebook,覆盖 4C 全链路 (staging → real LLM extraction → entity resolution → bundle review → commit → ledger inspection),使用真实 OpenAI API。

**做什么**:
- 新建 32-cell notebook,使用 `compile_schema_from_classes` 编译 canonical SchemaIR
- 定义 `Document` + `Module` entity classes (field-only, 无 Relationship)
- Real gpt-4o-mini LLM extraction (非 mock)
- 包含 adversarial identity fragmentation diagnostic (§10.5) + P0-off control experiment
- 更新 `examples/README.md` Learning Path 表格 + Prerequisites

**不做什么**:
- 不改 `src/factpy_kernel/` 任何代码
- 不加 `.py` file pair (notebook-only convention)
- 不入 pytest suite

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| NB-01 | 追加 08 号,不填历史 03 空位 | 不破坏历史 sequence |
| NB-02 | Real LLM (非 mock) | 用户明确要求 "使用实际的 api" |
| NB-03 | `compile_schema_from_classes` 做 schema 编译 | canonical-by-construction,绕过 B3 canonical validator 坑 |
| NB-04 | Field-only predicates,不用 Relationship | 避免 OBS-02 Pattern B crossover |
| NB-05 | Pre-flight check: pydantic + diskcache + instructor + litellm + OPENAI_API_KEY | 在 factpy_kernel import 之前检查,失败给明确 install hint |
| NB-06 | `Document` / `Module` domain 和 B3 对齐 | 方便未来 B3 重开时交叉引用 |

## 2. Acceptance Criteria

1. ✅ 所有 code cells AST parse 无 SyntaxError
2. ✅ 端到端 real LLM 运行: `committed_count > 0`
3. ✅ `examples/README.md` Learning Path + Prerequisites 更新

## 3. Outcome

- **实现于**: `examples/08_agent_document_workflow.ipynb` (32 cells, 15 code + 17 markdown)
- **README 更新**: Learning Path 表格 +1 行, Prerequisites +1 段
- **Notebook 验证**: 多次 real-LLM 运行全部成功, valid specs 范围 5-10 (OBS-01 variance)
- **后续扩展**: P0-P2 改进后加入 adversarial diagnostic cells (§10.5 + P0-off control experiment)
- **Final status**: **implemented**
