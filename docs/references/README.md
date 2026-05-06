# Reference Docs

`docs/references/` 用于收口三类不会直接成为当前实现真相、但对 blueprint 和架构讨论有价值的材料：

- `external/`
  - 外部标准、竞品、论文、产品或方案比较。
- `bridges/`
  - 历史内部材料到当前 FactPy 结构的提炼、桥接和迁移说明。
- `working/`
  - 仅供当前讨论使用的工作笔记、启发式材料或未定稿参考文档。
- `templates/`
  - 这类文档的最小起点模板。

## 边界

- 本目录不是当前实现真相；当前实现请看 `src/factpy_kernel/*/docs/`。
- 本目录不是 blueprint 状态机；任务决策、边界和验收仍写在 `docs/blueprints/`。
- 本目录不是历史蓝图归档；历史蓝图和 reconstructed archive 仍按既有规则分别放在 `docs/blueprint_history/` 与 `docs/blueprints/archive/`。

## 工作流规则

1. 新的参考材料应放到本目录的子目录，不要散落在 `docs/references/` 根级或仓库根目录。
2. 文件名应尽量使用可读的描述性 slug，避免再出现 `temp.md` 这类失去语义的命名。
3. 如果某份 reference 文档影响了 blueprint 的问题边界、设计决策或验收标准，必须把被采纳的结论写回 active blueprint 和 audit。
4. 如果某份 reference 文档中的内容已经成为当前实现语义或稳定系统边界，必须继续回写到模块 docs 或 `docs/architecture_principles.md`。
5. `working/` 下的文档必须在 header 显式标明其非权威性质（typically `Status: working / ...` + `Authority: non-authoritative ...`）；它们可以在后续被提升到 `external/` / `bridges/`，也可以在失去价值后删除。

## 当前条目（2026-05-06 wrap-up 后）

> Index 完整覆盖全 56 个文件（54 .md + 2 binary）。每条目附简短性质描述。

### `external/` —— 外部标准、竞品、benchmark

- [external/rainbird-evidence-chain-compare.md](./external/rainbird-evidence-chain-compare.md) — Rainbird 证据链与 explainability 交付形态的外部比较笔记。
- [external/extraction-benchmark-dataset-survey.md](./external/extraction-benchmark-dataset-survey.md) — Extraction benchmark dataset survey（2026-04-13；factpy_kernel pipeline 公开 benchmark 选型评估）。
- [external/esa-demo-walkthrough.md](./external/esa-demo-walkthrough.md) — ESSB-ST-U-007 compliance demo walkthrough script（外部 use case 演示）。

### `bridges/` —— 历史内部 → 当前 FactPy 结构桥接

- [bridges/symir-blueprint-extraction.md](./bridges/symir-blueprint-extraction.md) — 历史 Symir 蓝图到当前 FactPy 结构的提炼和桥接工作文档。
- [bridges/factpy-kernel-report-audit-2026-04-20.md](./bridges/factpy-kernel-report-audit-2026-04-20.md) — `factpy_kernel` 模块层 audit 报告（2026-04-20）。

### `working/` —— in-flight 工作笔记（non-authoritative，per §3.5）

#### 根级（pre-OSS heritage 与市场材料）

- [working/cross-domain-compliance-framing.md](./working/cross-domain-compliance-framing.md) — 跨域合规与可追溯性 framing 笔记（pre-OSS heritage；2026-03 era 23 个 archived blueprints 引用）。
- [working/esa-positioning.md](./working/esa-positioning.md) — factpy 作为 auditable reasoning framework 的市场定位笔记。
- [working/product-readiness-audit-2026-04-09.md](./working/product-readiness-audit-2026-04-09.md) — Production hazard audit + 市场比较（2026-04-09；2 active blueprints + 2 archived 引用）。
- `working/extraction_benchmark_report.json` — Extraction benchmark 结构化数据。
- `working/factpy_esa_demo.pptx` — ESA demo 幻灯（binary）。

#### `working/load-test-2026-04-11/` —— Layer 4C 全链路 load test bundle（2026-04-11）

Agent extraction → batch → resolve → bundle → commit 全链 load test 协议、生成器、迭代报告与 review packet。

- 协议：[README.md](./working/load-test-2026-04-11/README.md), [report_template.md](./working/load-test-2026-04-11/report_template.md), [run_record_template.json](./working/load-test-2026-04-11/run_record_template.json)
- 计划：[commit_path_plan_2026-04-11.md](./working/load-test-2026-04-11/commit_path_plan_2026-04-11.md), [format_coverage_plan_2026-04-11.md](./working/load-test-2026-04-11/format_coverage_plan_2026-04-11.md), [sample_expansion_plan_2026-04-11.md](./working/load-test-2026-04-11/sample_expansion_plan_2026-04-11.md)
- 观察：[cross_run_observations.md](./working/load-test-2026-04-11/cross_run_observations.md)
- Schema：[test_schema_ir_canonical.json](./working/load-test-2026-04-11/test_schema_ir_canonical.json)
- 执行脚本：[run_load_test.py](./working/load-test-2026-04-11/run_load_test.py), [generate_review_packet.py](./working/load-test-2026-04-11/generate_review_packet.py), [format_coverage_generators/](./working/load-test-2026-04-11/format_coverage_generators/)（3 个 Python generator）
- 迭代报告：[iter2](./working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter2.md), [iter3](./working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter3.md), [iter4](./working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter4.md)
- Review passes：[review/](./working/load-test-2026-04-11/review/)（含 [iter5/](./working/load-test-2026-04-11/review/iter5/) 子目录与 [review_summary_2026-04-11.md](./working/load-test-2026-04-11/review/review_summary_2026-04-11.md)）

#### `working/rule-replay-line-redesign-input/` —— Routemap 设计 heritage

> v0.1.x design probe (2026-04-30 .. 2026-05-03) → 9-batch routemap (2026-05-05 → 2026-05-06) 的设计输入 bundle。**Routemap CLOSED @ `6b32972`**；bundle 内容已被全 12 archived blueprints captured。

- 入口：[README.md](./working/rule-replay-line-redesign-input/README.md)
- Brainstorm：[00_brainstorm-original.md](./working/rule-replay-line-redesign-input/00_brainstorm-original.md)
- 设计史 B → B' → B''：[10_design-history-bprime-bdoubleprime/](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/)
  - [README.md](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/README.md)
  - [evidence-tree-context-bprime-2026-04-30.md](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/evidence-tree-context-bprime-2026-04-30.md) — B' context
  - [evidence-tree-proof-recheck-ideas-2026-04-30.md](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md) — proof-frame & rechecker notes
  - [operational-evidence-tree-rule-replay-design-2026-05-01.md](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md) — B'' working notes
  - [rule-replay-design-synthesis-2026-05-01.md](./working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/rule-replay-design-synthesis-2026-05-01.md) — B'' synthesis
- L0-L11 capability layering：[20_capability-layering-l0-l11.md](./working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
- Drift analysis：[30_drift-analysis-2026-05-02.md](./working/rule-replay-line-redesign-input/30_drift-analysis-2026-05-02.md)
- 8 design directions A-H + Decision 1：[40_design-discussion-A-with-decision-1.md](./working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
- v0.1.1 - v0.1.4 abandoned blueprints：[50_archived-blueprints/](./working/rule-replay-line-redesign-input/50_archived-blueprints/)（4 对 `.md` + `.audit.md`，含 v0.1.4 param-override negative-result）
- Lessons learned (9 immutable invariants)：[60_lessons-learned.md](./working/rule-replay-line-redesign-input/60_lessons-learned.md)
- Codebase baseline (2026-05-03)：[70_codebase-baseline-2026-05-03.md](./working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md)
- Conceptual interaction：[80_conceptual-interaction-design/](./working/rule-replay-line-redesign-input/80_conceptual-interaction-design/)
  - [README.md](./working/rule-replay-line-redesign-input/80_conceptual-interaction-design/README.md)
  - [check-operation-conceptual-interaction.md](./working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md)
  - [engine-extension-surface-architecture.md](./working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)

> **Lifecycle note:** Future cleanup batch 可考虑 promote 此 bundle → `bridges/`（涉及 ~12 inbound refs 更新，包括 1 active master plan + 11 archived blueprints + 1 memory anchor）。Routemap closure 已 captured 此 bundle 全部决议至 archived blueprints，promote 是 lifecycle 整理而非内容迁移。

### 根级 .md（待 future cleanup batch 迁移到 `external/`，inbound refs 需同步更新）

- [agentic-document-extraction-research.md](./agentic-document-extraction-research.md) — 商业领域 agentic 文档事实提取调研报告（2026-04；2 archived blueprint refs）。
- [cross-provider-entity-benchmark-report.md](./cross-provider-entity-benchmark-report.md) — Cross-provider entity identification benchmark report（2026-04-13；1 archived blueprint + 1 production code doc `src/agent/extraction/docs/USAGE.md:213` refs；移动需同步更新）。

### `templates/` —— 模板

- [templates/reference_note.md](./templates/reference_note.md) — Reference note 起点模板。
