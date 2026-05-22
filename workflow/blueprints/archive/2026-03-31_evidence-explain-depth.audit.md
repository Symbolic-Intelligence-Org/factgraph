# Audit Log: Evidence Explain Depth（事实溯源 + 逐步路径解释）

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-31 | draft | Blueprint created | 三引擎 evidence explain 深度增强：Phase 1 事实来源嵌入，Phase 2 逐步路径解释端点，Phase 3 反向查询显式 defer |
| 2026-03-31 | scoped | 三条开放问题关闭，冻结 D-EED1/D-EED2/D-EED3 | D-EED1: narrative 加可选 tree+locale 参数；D-EED2: v1 英文文本；D-EED3: flat list + detail.depth/parent_node_ref 层级提示 |
| 2026-03-31 | scoped | 审核修订 ×4 | (1) fact_meta 归一化：加 _extract_fact_meta() + 扩展 _runtime_assertion_detail_for_tree()；(2) 端点改 POST /queries/explain-steps；(3) rule_apply/conclusion 文案放宽（support_section 无 rule label，candidate_result 无 pred_id）；(4) Contract Fork §5.0 + 实施步骤补 P1-6 文档更新 |
| 2026-03-31 | implementing | 进入实现 | 补充 N-EED1（traversal/render 两阶段解耦）、N-EED2（dispatch helper 建议）；Outcome 区段重编号为 §10 |
| 2026-03-31 | implementing | Phase 1 完成 | 落地 P1-1~P1-7：_runtime_assertion_detail_for_tree 扩展 flat_meta、_extract_fact_meta helper、_build_assertion_leaf fact_meta 字段、narrative tree 参数+source_lines（修复 wrapper root 扫描 bug）、NL source_lines 段落、static_ui source tooltip、audit/query.py 接线、01_architecture.md + 03_runtime_queries_views.md 文档更新；659 tests green |
| 2026-03-31 | implementing | Phase 2 完成 | 落地 P2-1~P2-7：_candidate_evidence_tree_steps.py（N-EED1 两阶段：_StepRecord traversal + _describe_step render）、_candidate_provenance_timeline.py 追加 build_candidate_provenance_steps、runtime_v1.py explain_runtime_steps dispatch（tree path / pyreason path）、app_v1.py POST .../queries/explain-steps route、static_ui.py render_evidence_steps_html helper、01_architecture.md D-EED Phase 2 区段、test_candidate_evidence_steps.py 50 tests；709 tests green |
