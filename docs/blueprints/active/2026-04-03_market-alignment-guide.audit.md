# Audit Log: market-alignment-guide

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-04-03 | draft | Blueprint created | 基于 FCA 罚款案例、Reddit 社区反馈、专家访谈线索，对照代码验证建立能力矩阵。10 个能力维度：3 个 ✅、4 个 ⚠️、4 个 ❌。代码验证覆盖 accept.py, _certainty.py, _candidate_evidence_tree.py, static_ui.py, rule_ir.py, registry_fs.py, confidence.py, projector.py |
| 2026-04-03 | draft | 监管框架整合 | 新增 §8.4 监管框架对齐章节：整合 BaFin Orientierungshilfe (2025-12-18)、DORA、EU AI Act 的具体要求。新增 IT Finanzmagazin "Explain or Die" 文章分析。增加 FactPy 对监管要求的映射表。来源：it-finanzmagazin.de, klardenker.kpmg.de, bafin.de |
| 2026-04-03 | draft | CoT 概念修正 | 修正 §8.4.3：Chain-of-Thought 是 LLM prompting 技术（统计模型生成的推理步骤），与 FactPy 证据树（确定性规则引擎的形式化推导记录）是完全不同的技术范式。新增对比表格和产品定位建议。强调：证据树是 formal provenance trace，比 CoT 提供更强的审计保证，但仅覆盖规则引擎 |
| 2026-04-03 | draft | 五轮并行调研修正 | 基于 5 个并行调研代理的结果对蓝图进行全面修正。**主要变更**：(1) §5.1 FCA 罚款事实修正：年份 2025 非 2026、Barclays £42M 非 £43M、非协调行动、Barclays 是特定客户关系失败非企业级控制缺陷。来源：FCA Final Notices, AML Watcher, Mishcon de Reya。(2) 新增 §5.4 竞品分析：7 家供应商（Lucinity/NICE Actimize/Featurespace/ComplyAdvantage/Napier AI/SymphonyAI/Nasdaq Verafin）无一提供 formal provenance，确认市场空白。来源：各供应商官网 + Consilient 行业分析。(3) §8.4 根本性重写：FactPy 纯规则引擎很可能不算 EU AI Act 定义的"AI"（Article 3(1) conjunctive reading）；DORA 以 ICT 供应商身份适用、非 AI；BaFin Orientierungshilfe 主要针对 ML/AI。产品定位从"满足 AI 监管"修正为"帮助客户满足 AI 合规要求的审计基础设施"。来源：EU Commission Guidelines, BaFin Prinzipienpapier BDAI, EBA Q&A, Orrick/Noerr 法律分析。(4) CoT 可靠性实证：Anthropic 研究显示 CoT 忠实度 25%；Oxford/Bengio "CoT Is Not Explainability"；但无直接审计师偏好调查。(5) 待验证清单更新：V7-V10 已回答，新增 V11（Datalog 法律分类）V12（客户付费意愿） |
