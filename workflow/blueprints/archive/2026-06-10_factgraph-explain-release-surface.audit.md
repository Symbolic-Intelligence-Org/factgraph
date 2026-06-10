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

## C. Closure (2026-06-10)

用户决策:factgraph 公开面取「**全量公开面**」(非 allowlist 精简面)。

- 发现:现公开分支 `ed054fd0` 发 **169** 测试(≈全量 172),且含 denylist 本应拦下的 `src/factgraph/AGENTS.md` 泄漏 → **allowlist+脚本并非该公开分支的真实组装方式**;按 allowlist 全替换会误删 154 个已公开测试。
- 全量构建(detached worktree @ `ed054fd0`;`git checkout ea26f566 -- <public roots>` + 剥离泄漏):**454 文件**,全部 **172** 测试,explain + `capabilities.py` 在内,私有泄漏 **0**,bad-link **0**,仅 **2 删**(`AGENTS.md` 泄漏 + 已合并的 `test_audit_evidence_graph_render.py`)。
- 新 publish commit **`5e21e817`**(parent `ed054fd0`,续 publish 血缘);diff 15A/2D/58M(+6541/−3114)。
- **push 被 auto-mode 数据外泄分类器拦截**(两次,含一次含 `ls-remote` 的只读命令):理由=「把私有全树推到公开仓库、绕过 curated allowlist projection」属 data exfiltration,且「in-chat 授权不可清除」。**未做任何绕过**。
- **已发布**:用户在本地终端 push 成功 → `Symbolic-Intelligence-Org/factgraph` branch `feature/v0.2.0-explain-layer-2026-06-10` @ `5e21e817`(worktree push 前 clean)。PR: https://github.com/Symbolic-Intelligence-Org/factgraph/pull/new/feature/v0.2.0-explain-layer-2026-06-10
- impl 分支 allowlist 提交 `ea26f566` 本地保留(**未推 origin**)。
- sacred master 不变 @ `854d03b9`。

**可复现 recipe**(若 /tmp worktree 被清):
```
git worktree add --detach /tmp/fg-rel-explain ed054fd0
cd /tmp/fg-rel-explain && git rm -rf .
git checkout ea26f566 -- src/factgraph tests docs/quickstart docs/SECURITY.md \
  .github/workflows/factgraph-tests.yml .gitignore CHANGELOG.md CODE_OF_CONDUCT.md \
  CONTRIBUTING.md LICENSE README.md pyproject.toml
find . -path ./.git -prune -o \( -name AGENTS.md -o -name CLAUDE.md \) -delete
git add -A && git commit -m "publish: sync factgraph release surface from hnsm ea26f566"
git push factgraph HEAD:refs/heads/feature/v0.2.0-explain-layer-2026-06-10
```
