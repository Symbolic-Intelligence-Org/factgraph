# Task Blueprint: factgraph release surface — explain-layer v2 + conformance

- Status: implemented
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: release-surface slice (`feedback_cleanup_slice_cadence` 轻量;narrative scope-freeze + 通用验收)
- Predecessor: archived [2026-06-09_explain-layer-v2] + [2026-06-10_explain-conformance-rework];并行 active [2026-06-10_explain-docs-paths-model-alignment]
- Authority: `scripts/release_surface_allowlist.txt`(白名单)+ `scripts/project_release_surface.sh`(投影脚本)+ `workflow/AGENTS.md` §"Scope Outside workflow/"
- Audit Log:
  - [2026-06-10_factgraph-explain-release-surface.audit.md](./2026-06-10_factgraph-explain-release-surface.audit.md)

---

## 1. Problem

explain 层 v2 + conformance(87 commits,`854d03b9..HEAD`)新增了公开 src 模块(`application/explain/*`、`protocol/certainty.py`、`protocol/explanation_render.py`、`core/schema/schema_repr.py` + 模块 docs)并重写了 `docs/quickstart`,但 factgraph release surface 尚未承载:

- **没有任何 allowlist 含 `application/explain`** → 新模块会被投影静默丢弃 → 公开包 import 断裂。
- 现有 factgraph 投影分支 `feature/v0.2.0-factgraph-publish-2026-06-03`(最后提交 2026-06-07)**早于全部 explain 工作**(merge-base 2026-06-03;树里 0 个 explain 文件)。
- explain 引入的模块 doc `audit/docs/02_evidence_graph.md:129` 引用私有路径 `src/domains/`,触发投影脚本的 bad-link 扫描 FAIL(`b4df4b62` 引入)。

## 2. Scope(scope-freeze)

**INCLUDE — allowlist 新增(9 src + 10 tests)**

src(强制;否则缺失/断 import):
- `application/explain/__init__.py`、`explain/evidence_tree.py`、`explain/prober.py`、`explain/docs/README.md`
- `application/protocol/certainty.py`、`protocol/explanation_render.py`、`protocol/docs/README.md`
- `core/schema/schema_repr.py`、`core/schema/docs/README.md`

tests(curated:仅 kernel/protocol/sdk 纯 python,匹配既有"不发引擎测试"策略):
- `application/explain/test_prober.py`
- `application/protocol/test_evaluate_result_dtos.py`、`protocol/test_explanation_render.py`
- `sdk/dsl/test_application_rule.py`、`sdk/test_explain_conformance_native.py`
- `test_application_schema_runtime.py`
- `test_audit_evidence_graph.py`、`test_audit_evidence_graph_render.py`
- `test_authoring_schema_repr.py`、`test_sdk_schema_repr.py`

**SOURCE FIX(为通过 bad-link 扫描)**
- `audit/docs/02_evidence_graph.md:129` —— 改写 `(src/domains/)` 括注,去掉私有路径 token(语义不变)。

**DOCS(sync 时手工加,不进 allowlist —— 匹配 `e4dc9f12`/`d4e85180` 模式)**
- `docs/quickstart/{evaluate_and_evidence,rules,schema_definition}.md`

**DEFER(本次不入面,按 kernel-only / no-engine 测试策略)**
- `tests/test_{problog,pyreason,souffle}_evidence_graph.py`、`test_pyreason_e2e.py`、`test_pyreason_provenance_v0.py`、`test_problog_semantics_profile_migration.py`(引擎运行时)
- `tests/sdk/test_t5_why_not_quarantine.py`、`tests/test_db_identity_substrate.py`(非 explain 范围)

**EXCLUDE(治理 / denylist —— 永不进公开面)**
- `workflow/**`(52)、`examples/explain_layer_demo.py`、`docs/official/**` —— denylist + AGENTS §"Scope Outside workflow/"

## 3. Non-goals

- 本 slice **不 push**(只做 staged 构建 + `/tmp` 投影自检 + 交付清单待审)。
- 不改 src 行为(仅 1 处 doc 改写以过 bad-link)。
- 不重排既有 12 条 kernel 测试面。

## 4. Approach

1. 加 19 条 allowlist(顺序无关;脚本比对时 sort 两侧)。
2. 改写 `audit/docs/02_evidence_graph.md` 那 1 处 bad-link。
3. 跑 `project_release_surface.sh` → `/tmp/factgraph_projection`,要求输出 `PROJECTION READY`。
4. 确认 3 个 `docs/quickstart` bad-link 干净(sync 时手工加)。
5. 交付:完整投影文件清单 + 测试 include/defer split,待用户 review。
6. (单独授权,gated)sync 投影 + 3 docs 到 `feature/v0.2.0-explain-layer-2026-06-10`,push factgraph。

## 5. Acceptance(通用 gate)

- [x] `project_release_surface.sh` 输出 `PROJECTION READY`(consistency + denylist + bad-link 全过)。✅ re-run #3 / 294 files
- [x] 投影 manifest 含全部 9 个新 explain src 文件。✅
- [x] allowlist 无删行(diff = 纯新增 19 行 = 18 explain + 1 `capabilities.py` parity)。✅
- [x] import-completeness:投影内无 shipped→non-shipped factgraph import(0 unresolved)+ `compileall` OK。✅
- [x] 3 个 `docs/quickstart` bad-link 干净(sync 时手工加)。✅ 预扫确认
- [x] 投影内无 `workflow/` / `examples/` / `docs/official`。✅
- [x] 仅在显式授权后才推分支。✅ 全量公开面构建后由**用户本地 push**(in-chat 授权无法过 auto-mode 数据外泄闸)

## 6. Outcome / Deviations

staged build 完成(**未 push**):
- `scripts/release_surface_allowlist.txt` +19 / −0(275→294):18 explain + `application/capabilities.py`(parity)。
- source fix:`audit/docs/02_evidence_graph.md` 1 处 bad-link。
- 投影 `PROJECTION READY`(294 files)+ `compileall` OK + import-completeness 0 unresolved。
- 偏差①:`test_audit_evidence_graph_render.py`(range 内删除文件)剔除测试面(10→9)。
- 偏差②:`application/capabilities.py` pre-existing parity gap 折入(非 explain 引入;现有发布投影已含,其依赖 `tup_v1` 已发布)。
- DEFER 测试 8(引擎运行时 / 非 explain 范围)。
**最终(全量公开面 pivot + 已发布)**:user review 时确认 allowlist 精简面会误删 154 个已公开测试 → 决策改取**全量公开面**。
- 构建:detached worktree @ `ed054fd0`,`git checkout ea26f566 -- <public roots>` + 剥离 `AGENTS.md`/`CLAUDE.md` 泄漏 → **454 文件 / 全 172 测试 / explain + capabilities 在内 / 私有泄漏 0 / bad-link 0 / 仅 2 删**(`AGENTS.md` 泄漏 + 已合并的 render 测试)。
- publish commit `5e21e817`(parent `ed054fd0`);diff 15A/2D/58M(+6541/−3114)。
- push 两度被 auto-mode 数据外泄闸拦(in-chat 授权不可清除)→ **由用户本地终端 push 成功**。
  - Repo `Symbolic-Intelligence-Org/factgraph` · Branch `feature/v0.2.0-explain-layer-2026-06-10` · Commit `5e21e817`
  - PR: https://github.com/Symbolic-Intelligence-Org/factgraph/pull/new/feature/v0.2.0-explain-layer-2026-06-10
- 遗留(待用户定):impl 分支 allowlist 提交 `ea26f566` 是否推 origin;本蓝图是否归档。
