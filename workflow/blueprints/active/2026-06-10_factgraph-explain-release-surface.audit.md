# Audit Log: factgraph release surface — explain-layer v2 + conformance

Paired with [2026-06-10_factgraph-explain-release-surface.md](./2026-06-10_factgraph-explain-release-surface.md).

---

## A. Discovery (2026-06-10)

投影机制摸底(read-only):

- factgraph 公开仓库 = `scripts/project_release_surface.sh` 投影产物(`rsync --files-from=allowlist` → `/tmp` → 双向 consistency 校验 + denylist + bad-link 扫描),**非分支直推**。
- 我的 impl 分支 HEAD `53b6e9c8` 比最近 publish 基线领先 218 commit;直推会灌入 52 个 `workflow/` 治理文件。
- denylist 已覆盖治理排除:`scripts/*`、`*/AGENTS.md`、`CLAUDE.md`、`memory/*`、`docs/blueprints/*`、`docs/references/*`、`examples/`、`src/{agent,service,domains}/*` 等。
- **无任何 allowlist 含 `application/explain` 或 `docs/quickstart`**(origin/master 361 行、master/HEAD 275 行、sync 源 95c9b295/1e35c043 全 0);现有投影的 quickstart 是在投影分支上**手工 commit**(`e4dc9f12`/`d4e85180`),不走脚本。
- 现有投影分支树:0 个 `application/explain` / `certainty.py` / `schema_repr.py` → 完全不含本工作。

baseline 投影(现 275 行 allowlist):consistency PASS、denylist PASS,**bad-link FAIL** 于 `audit/docs/02_evidence_graph.md:129`(`src/domains/`,`b4df4b62` 引入)。全量 md 预扫确认这是唯一一处 bad-link;3 个新模块 doc + 3 个 quickstart 均干净。

精确 delta(`comm` 计算,非凭记忆):
- src 缺失于 allowlist = 9 个文件(含 3 个早已存在但从未发布:`protocol/explanation_render.py`、`protocol/docs/README.md`、`explain/docs/README.md`)。
- tests 候选 18,按既有 12 条 kernel-only / no-engine 策略 → 收 10,defer 8。

## B. Build Log (2026-06-10)

1. Blueprint + audit 创建(scope-freeze)。
2. baseline 投影(原 275 行 allowlist):consistency PASS、denylist PASS,bad-link **FAIL** @ `audit/docs/02_evidence_graph.md:129`(全量 md 预扫确认唯一一处)。
3. source fix:改写该 bad-link(`(src/domains/)` 括注 → `(host application)`,语义不变;`b4df4b62` 引入)。
4. allowlist +18 explain(9 src + 9 tests)。
   - **偏差①**:候选 `tests/test_audit_evidence_graph_render.py` 实为 range 内**删除文件**(seed 有、HEAD/FS 无;render 覆盖并入 `test_audit_evidence_graph.py`)→ rsync `link_stat` FAIL → 剔除,测试 10→9。
5. import-completeness 静态检查:`sdk/store.py` 懒加载 `factgraph.application.capabilities` 未解析。
   - **偏差②**(pre-existing parity gap,**非 explain 引入**):`application/capabilities.py` 在 monorepo 存在(仅 import 已发布 `tup_v1`)、seed 即有、且**现有已发布投影已含**,但本分支 allowlist 缺 → 折入 +1 行恢复 parity。
   - 澄清:`origin/master` allowlist(361 行)是 **pre-namespace-split**(`src/kernel/*`),非有效 base;本分支 `src/factgraph/*` 命名空间无真实回归(353 条"差异"全是 kernel 命名空间噪声)。
6. 投影 re-run #3:`PROJECTION READY`,**294 files**;`compileall` OK;import-completeness **0 unresolved**;manifest 无 `workflow//examples//docs/official/`。
7. 待 user review;**未 push**。

## C. Closure

PROJECTION READY + 用户 review + (授权后)push 时填写。
