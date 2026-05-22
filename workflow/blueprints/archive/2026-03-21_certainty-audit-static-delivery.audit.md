# Task Blueprint Audit: Certainty Audit And Static Delivery

- Blueprint: [2026-03-21_certainty-audit-static-delivery.md](./2026-03-21_certainty-audit-static-delivery.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | scoped | Blueprint created | Scope: export-time materialization of `certainty_summary` into `certainty_summaries.jsonl`; `AuditQuery` reads materialized data; static site renders `certainty_lines` section. Reuses existing certainty semantics — no probability lane, no ranking, no core summary changes. |
| 2026-03-21 | scoped | Review round 1 — 3 issues fixed | P1: `export_package` 缺少 `registry_root` 参数，无法访问 condition_weights — 新增 keyword-only `registry_root` 参数，`export_runtime_package` threading 传入。P1: 直接 import `runtime_v1.py` helper 会造成 cycle — 提取 service-neutral `materialize_certainty_summary` 到 core 层 `_certainty_materializer.py`。P3: 类型名应为 `AuditPackageData`（非 `AuditPackage`），已修正。 |
| 2026-03-21 | implementing | Review round 2 — approved | No blocking findings. Residual risks noted: backward compat for non-runtime callers, optional-file pattern parity, narrative parity assertion. |
| 2026-03-21 | implementing | Import 拓扑调整 — approved | 发现 `core → authoring` 和 `adapters → authoring` 会引入新 cycle edge。调整方案：materializer 拆两层（core 接收 pre-resolved weights，service 做 lookup）；`export_package` 改为接收预计算 `certainty_summaries` dict 而非 `registry_root`；`FileAuthoringRegistry` import 窄化到 `authoring.registry_fs`。 |
| 2026-03-21 | implementing | Phase 1 complete | 新建 `_certainty_materializer.py`（core 层）；`runtime_v1.py` thin orchestrator + `_compute_all_certainty_summaries` 预计算；`package.py` 纯 writer `certainty_summaries` kwarg；`runtime.py` 新增 `list_candidate_ids()`；3 处测试跟随签名改动。209 tests green。 |
| 2026-03-21 | implementing | Phase 2 complete | `reader.py` 读 `certainty_summaries.jsonl` 到 `AuditPackageData.certainty_summaries` dict（旧包回落空 dict）；`query.py` 新增 `get_candidate_certainty_summary()`，`get_candidate_evidence_tree_narrative()` 传入 certainty_summary。209 tests green。 |
| 2026-03-21 | implementing | Phase 3+4 complete | `static_ui.py` narrative block 渲染 `certainty_lines` section。3 new tests: audit round-trip certainty parity, backward compat old package, static site certainty rendering。测试走真实 evaluate→accept→export 链路（非手工 _remember）。212 tests green。 |
| 2026-03-21 | implemented | Phase 5 docs complete | 5 docs synced: `audit/docs/01_overview.md`, `service/docs/03_runtime_queries_views.md`, `core/annotation/docs/README.md`, `core/docs/01_architecture.md`, `core/docs/01_architecture.en.md`. Blueprint outcome filled, status → implemented. |

## Decision Notes

- `condition_weights` only exist in `FileAuthoringRegistry` filesystem, not in audit package — certainty cannot be derived offline; must materialize at export time
- `certainty_summaries.jsonl` is additive sidecar file — does not modify existing audit package files or `SupportArtifact` canonical bytes
- Backward compatible: old packages without the file load with empty certainty_summaries dict
- Only candidates with non-null `certainty_summary` get a line in the JSONL file
- Static site reuses existing `_render_narrative_section` pattern for `certainty_lines`
- Runtime delivery behavior completely unchanged — this blueprint only extends audit + static surfaces
- **Review R1**: certainty 物化逻辑必须提取到 core 层，不能从 `package.py` 反向 import `runtime_v1.py`（会形成 cycle）
- **Review R1**: `export_package` 新增 `registry_root: str | None = None` keyword-only 参数，由 `export_runtime_package` threading 传入
- **Review R1**: `AuditPackageData`（非 `AuditPackage`）是 `reader.py` 中的正确类型名
