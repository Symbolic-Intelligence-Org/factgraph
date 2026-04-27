# Task Blueprint Audit: Kernel Namespace Split

- Blueprint: [2026-04-27_kernel-namespace-split.md](./2026-04-27_kernel-namespace-split.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-27 | draft | Blueprint created | 基于 8 项依赖图复核(见 §4 Current Context)+ 4 轮模块成色复核而起草。Namespace 拆分范围、跨模块文件归属、6 类测试搬迁、pyproject 选项 X、`kernel` 包名占位、4 个 static_ui-tied 测试归属 service 等关键决策已与用户对齐。 |
| 2026-04-27 | draft | Kernel definition clarified | 用户确认 v0.1 采用 D1:"面向 Python 接入方的可审计推理 substrate"。`service` 被明确为非 Python / 跨进程 delivery surface;D2(language-agnostic minimal engine)记录为后续独立方向,不并入本 blueprint。 |
| 2026-04-27 | draft | Blueprint contradictions resolved | 在转 scoped 前对 3 处 blueprint-level 矛盾做收口修正:(1) extraction route 归属与 HTTP test/契约的悬挂(新增 agent service app 解决);(2) Step 2 `git mv` 顺序会导致 `src/agent/agent` 嵌套(重写顺序);(3) Docs To Update 清单显式列出 5 处关键 docs(避免依赖 grep 一把扫)。详见 Decision 10-12。 |
| 2026-04-27 | scoped | Blueprint scoped | 进一步清理残余执行级矛盾:将 `domains` 映射对齐为整包搬迁、把 `package-data` 旧 key 更新/删除纳入 pyproject 修改、移除 Step 3 中残留的 OpenAPI 校验并把测试命令拆成覆盖 5 个目标目录。 |
| 2026-04-27 | scoped | Step 1 v1 review feedback applied | Step 1 v1 暴露 5 处规格漂移:(a) `agent/service/app.py` 模板 import 写错 owner(`kernel.service.X` 应为 `service.X`);(b) sed 只覆盖 from/import,漏 69 处 `patch("factpy_kernel...")` quoted-string runtime targets;(c) examples scope 仅 4 个,漏 5 个 import-bearing notebooks;(d) pre-flight/validation 用 macOS 默认无的 `md5sum`;(e) 预先建 tests/__init__.py 引入未承诺的新文件。Blueprint 在 Step 1 v2 出之前先 patch §5.3(quoted-string 规则)/§5.5(8 notebook 全迁 + validation 分级)/§7(执行级 vs 清零级 acceptance + shasum)/§8 Step 2.7(7 段 sed pass + 收窄 G.0.5 + nbformat 脚本)。详见 Decision 14。 |
| 2026-04-27 | scoped | Step 1 v2 review feedback applied | Step 1 v2 review 暴露 3 阻塞 + 2 修正:(a) notebook 脚本只改 code cells 但 validation 用原始 .ipynb 文本 grep,outputs 旧字面量会打爆 0 残余检查;(b) G.0.5 用 macOS BSD 不稳的 `grep -rlE --include`;(c) G.5 / Phase I 漏网 grep scope 太宽,扫 active blueprints / references / session_handoffs 会长期 noisy;(d) H.4 docs README 仍引用 split 后已不存在的 `kernel.service` / `kernel.service.app_v1`;(e) pre-flight `| tail -3` 没 pipefail 会掩盖 baseline 失败。Blueprint 在 Step 1 v3 出之前再 patch §5.5(清零级改为脚本 --check,不做 .ipynb 文本 grep)/§7(同步 + 增加 当前真相面 残余扫描 acceptance)/§8 Step 2.7(G.0.5 改 rg、G.5 限定当前真相面)。详见 Decision 15。 |
| 2026-04-27 | scoped | Step 1 v3 review feedback applied | Step 1 v3 review 暴露 3 处仍在的矛盾(2 P1 + 1 P2):(a) Phase I.6 仍对 `examples/*.ipynb` 做 raw 文本扫,与 H.0 `--check` 只看 cell sources 自相矛盾(04 outputs 已含 `factpy_kernel`);(b) docs/prose sweep 缺失,267 处 `src/factpy_kernel/...` markdown 路径引用未被任何 sed pass 覆盖,Phase I.6 注定红;(c) 2 处 bare-string `.py` 残留(`_test_helpers.py:1` docstring + `run_re_docred.py:5` docstring)既无点号又非 quoted,sed 全漏。Blueprint 在 Step 1 v4 出之前再 patch §7(I.6 排除 .ipynb + 显式增加 docs sweep + 2 处 bare-string acceptance)/§8 Step 2.7 G.5(rg 加 `-g '!*.ipynb'`)/§8 Step 2.8(新增 docs / prose sweep 步骤 + 2 处 bare-string 显式手工修)。详见 Decision 16。 |
| 2026-04-27 | scoped | Step 1 v4 review feedback applied | Step 1 v4 review 暴露 4 处问题(2 P1 + 2 P2):(a) `Phase I.6` / `G.5` 扫整个 `src/`,会被 `src/factpy_kernel.egg-info/SOURCES.txt` 等 setuptools metadata 永久打爆;(b) `H.14.2` sed 片段用反引号包裹 `# === Pass N ===` 注释,会被 shell 当 command substitution,executor 直接炸;(c) `H.14.2` catch-all `s\|src/factpy_kernel/\|src/kernel/\|g` 会把 `src/factpy_kernel/*/docs/` 这类 wildcard 泛指错改成 `src/kernel/*/docs/`(语义错,因 docs 不只在 kernel);(d) `G.5` 写"应空"但运行时点早于 H.14/H.15,docs prose 还没 sweep,期望必然不成立。Blueprint 在 Step 1 v5 出之前再 patch §7(scope 改 4-package 显式枚举 + 增加 wildcard prose acceptance + egg-info 排除)/§8 Step 2.7 G.5(scope + egg-info 排除 + reframe 为 informational preview)/§8 Step 2.8 H.14(分 14.0-14.3 sub-step,14.0 预先手工修 wildcard,14.2 删反引号注释)。详见 Decision 17。 |
| 2026-04-27 | scoped | Step 1 v5 review feedback applied | Step 1 v5 review 暴露 3 处仍在的漏面(2 P1 + 1 P2):(a) `H.0` notebook 脚本只改 from/import + quoted-string,但 `examples/08` cell 3 含 7 处 bare prose(`install factpy_kernel itself` / `inside factpy_kernel` / `print("factpy_kernel imports OK.")`),cell 31 markdown table 含 dotted refs(`factpy_kernel.sdk.compile_schema_from_classes` 等),都不被现规则命中;(b) `H.14.2` 对 docs 中 `src/factpy_kernel/tests/...` 路径走 catch-all,但 43 处已搬迁 test 路径(agent/docs:38, observability/docs:4, ecss/docs:1)会被错改成 `src/kernel/tests/`;(c) `docs/module_docs_convention.md` 6 处 factpy_kernel 引用(3 wildcard `:5,:101,:105` + 3 specific `:26,:67-68`)整文件不在 G.5/I.6 scope 也不在 DOCS_TARGETS,会留 durable docs entry 系统漂移。Blueprint 在 Step 1 v6 出之前再 patch §5.3(增加 naked dotted refs + bare-string `\bfactpy_kernel\b` rewrite 规则,仅 H.0 notebook 脚本应用)/§7(增加 moved-test path 13 条 prefix 映射 acceptance + module_docs_convention.md 整文件纳入 scope)/§8 Step 2.7 G.5(scope 加 module_docs_convention.md)/§8 Step 2.8 H.14(:101/:105 加入 14.0 wildcard 修;14.1 DOCS_TARGETS 加 module_docs_convention.md;14.2 顺序 13 条 prefix 先于 catch-all)。详见 Decision 18。 |
| 2026-04-27 | scoped | Step 1 v6 review feedback applied | Step 1 v6 review 暴露 2 处 P1 阻塞:(a) `H.0` `process_notebook(write=False)` 仍会调用 `rewrite_text()` 改 in-memory `cell.source` 再统计 residual,导致 `--check` 报告的是 post-rewrite count(假阳性 0),Phase I.5 失去验证意义;(b) `README.md:152` / `README.en.md:152` 当前是单段 `unittest discover -s src/factpy_kernel/tests` 命令,经 H.14.2 catch-all 会变成 `src/kernel/tests`,但 split 后测试已分散到 5 个目录(`src/kernel/tests` `src/agent/tests` `src/service/tests` `src/domains/ecss/tests` `tools/benchmarks/tests`),机械 sed 后 README 命令漏跑大量测试,留下错误的当前真相。Blueprint 在 Step 1 v7 出之前再 patch §7(新增 README 5 段命令重写 + H.0 `--check` 不调用 rewrite 的 acceptance)/§8 Step 2.8 H(新增 README 测试命令显式重写步骤)。详见 Decision 19。 |
| 2026-04-27 | scoped | Step 1 v7 ratified | v7 通过 review,可执行。`scripts/_namespace_rewrite_notebooks.py` 已 Write 到 scripts/(`process_notebook` 拆 write/check 两路);README 决定用 5 段显式命令(不用 for-loop)对齐 Phase I.3。顺手清理纳入 H 段:`docs/module_docs_convention.md:67-68` 两个 fake test example name(`test_core_ledger.py` / `test_derivation_accept.py` 不存在)替换为真实文件(`test_protocol_v1.py` / `test_annotation_store.py`)。下一步:用户执行 Phase A→I,assistant standby validation 报错处理。 |
| 2026-04-27 | implementing | Status moved to implementing | Pre-flight 完成(restore 09 / .git/info/exclude 排除 .claude/worktrees / 建 namespace-split branch / status clean 只剩 3 个 namespace-split 工作产物)。开始 Phase A-F 执行。Blueprint 状态由 scoped 前移至 implementing。 |
| 2026-04-27 | implementing | Phase A-F executed | 整模块搬迁(agent/service/domains)+ 二级目录创建 + 跨模块文件搬迁 + 测试搬迁(57 个文件)+ 新建 agent/service 占位 + kernel 整目录改名。`set -euo pipefail` 下全步骤 exit 0。git status 371 个 R/A 状态,无意外。 |
| 2026-04-27 | implementing | Phase G executed (with zsh bug recovery) | G.0 + G.4 + G.6 一次成功;G.0.5 + G.1-G.3 第一遍空跑(zsh `for f in $VAR` 不 word-split,sed 报 File name too long),改 `while IFS= read -r f` re-run 全成功。G.6 nbformat 脚本 8 notebooks 共 58 substitutions,--check 残余 0。G.5 informational preview 残留 326 行(322 .md + 4 .py),其中 4 处 .py prose-context dotted refs(sed 漏)中 2 处是已知 H.15 bare-string,2 处新发现(sdk_helpers.py:142 error msg / core/store/api.py:7 docstring)纳入 H.15。 |
| 2026-04-27 | implementing | Phase H executed (H.5-H.16 + H.14 + H.15) | 14 个 .md 文件 + pyproject + 2 README 完整重写 + service/docs 删 extraction 章节 + 34 个 DOCS_TARGETS sweep + 6 个 wildcard prose 预修 + 4 处 bare-string `.py` 手工修。Phase H 中两次发现 sed 漏:naked-dotted refs(无 from/import/quote 前缀)+ slash 路径(`factpy_kernel/X` 不带点号)+ BSD sed `\b` 不支持 → 各加 targeted pass 解决。Final residual scan(用户验证 scope)0 残余。 |
| 2026-04-27 | implementing | Phase I executed (with 5 spec-gap fixes) | I.0-I.6 全过。但执行期间发现 5 类 spec gap 真实问题(详见主 blueprint §10 deviations 4-9):(a) kernel/audit/__init__.py 仍 re-export 已搬走的 compliance/static_ui 符号 → 删除 re-exports + 加注释;(b) kernel/audit/query.py 模块级 `from .compliance` 引入 kernel→domains 模块级耦合 → 改 lazy import;(c) domains/ecss/{compliance,sdk_helpers}.py 跨包搬迁后相对 import 漏改 → 改绝对 import;(d) 3 个 kernel-level integration 测试还在 `from kernel.audit import render_audit_static_site` → 改 `from service.static_ui`;(e) test_extraction_http_api.py 的 `patch("service.extraction_v1...")` 应为 `patch("agent.service.extraction_v1...")`;(f) 6 个 ECSS test 用 Python 脚本统一拆 `kernel.audit` 内的 ECSS_* / render_audit_static_site re-exports。修后 1023 tests 全绿、5 执行级 examples 跑通、--check 残余 0、final scan 0 残余。 |
| 2026-04-27 | implementing | Closure docs adjustments | 收口前补 3 处文档/workflow 漂移:(1) docs/README.md 顶层索引仍把 OpenAPI yaml 列为"当前真相 48 ops",改为"归属待定 (deferred to OS-prep)";(2) docs/module_docs_convention.md:67-68 仍写 fake test names(`test_core_ledger.py` / `test_derivation_accept.py` 不存在),替换为真实文件 `test_protocol_v1.py` / `test_annotation_store.py`;(3) blueprint §10 Outcome / Deviations 完整填写(11 类 deviations,3 tooling + 6 spec gap + 2 docs drift)。 |
| 2026-04-27 | implemented | Status moved to implemented | 全部 acceptance 项达成。归档前最后一步:atomic commit + 移入 archive/ + 更新 memory/current.md。 |

## Decision Notes

### 关键决策(2026-04-27 draft)

1. **拆分范围:Plan A(namespace split only)而非 Plan B(含内部重组)**
   - **Why**:用户确认只做 namespace 边界整理,不动 kernel 内部 14 个子模块的分组。原因:不混淆"开源准备"和"架构改进"两个目标
   - **影响**:`sdk/batch.py 1838` 等 god file 内部不动,作为 internal 代码质量后续问题处理

2. **`service/` 整体搬出 kernel(原计划只搬 `extraction_v1.py`)**
   - **Why**:用户在 namespace 讨论中提出 service 也是 delivery 层,超出 kernel 语境;assistant 复核后确认依赖方向单向(service → kernel,反向无)、且 god file `runtime_v1.py 2810` 一并搬出后 kernel 自身代码质量风险面显著收窄
   - **影响**:扩大了搬迁规模,但消除了原"app_v1.py 路由块拆分"这个非机械决策——service 整体走,kernel 完全不知道 HTTP 这件事

3. **`audit/static_ui.py` + 4 个 kernel-level 测试 → service**
   - **Why**:static_ui 是 HTML 渲染(delivery 层),与 service 同层;4 个测试本质上是"用渲染后 HTML 验证 DTO 数据结构正确",归 service-layer integration test
   - **未来 refactor 提示**:这 4 个测试更干净的写法是直接测 `audit/dto.py` 的 DTO,不经过 HTML——但本 blueprint 不动测试逻辑

4. **`sdk/ecss.py` + `audit/compliance.py` + 6 个 ECSS-tied 测试 → domains/ecss 作为 cohesive bundle**
   - **Why**:6 个测试每个都同时 import `domains.ecss` 和 `sdk.ecss`,两者强绑定;`sdk/ecss.py` 和 `audit/compliance.py` 单独剥离没意义
   - **影响**:原 `sdk/ecss.py` 改名为 `domains/ecss/sdk_helpers.py`(避免与 `kernel.sdk` 撞名)

5. **`test_benchmark_*.py`(6 个) → `tools/benchmarks/tests/`**
   - **Why**:这 6 个测试 subprocess 进 `tools/benchmarks/bench_runner.py`,本质是测 harness 输出形状,不测 kernel 代码;`tools/benchmarks/` 已有 33 个 git-tracked 文件,从来不在 kernel package 内
   - **影响**:消除"kernel tests 反向 subprocess 进 repo root tools/"这个反向耦合

6. **包名:占位为 `kernel` / `agent` / `service` / `domains` 短名,最终名后续单独决策**
   - **Why**:用户表态"factpy 名字配不上现状",但同时认可"namespace 大手术先做、命名后定"。占位短名让 blueprint 可独立推进,不被命名讨论阻塞
   - **影响**:本 blueprint 完成后,任何最终改名(如 `factpy_kernel` → `<newname>_kernel`)是机械 sed,可在 OS-prep blueprint 中处理

7. **pyproject 选项 X(单 root pyproject)而非 multi-pyproject**
   - **Why**:用户选 X,理由"之后再改也不怕"。开发体验(单一 `pip install -e .`)零变化;OS 时若需要独立 wheel 再单独处理
   - **影响**:不引入 uv workspace / hatch monorepo 等新工具链

8. **原子单 commit**
   - **Why**:中间状态会出现 import 红,无法分步推进;1023 tests 必须在 commit 完成的瞬间全绿
   - **影响**:对执行者的精度要求高,需要完整 sed 模板与 git mv 清单一次到位

9. **kernel 定义选 D1(Python auditable reasoning substrate),不选 D2(language-agnostic minimal engine)**
   - **Why**:将 `service` 搬出 kernel 后,当前实现不再保留任何非 Python 接入面。若宣称 D2,就必须同步提供 IR + CLI/IPC/gRPC 等最小非 Python surface;这不是 namespace split 的附带工作,而是独立专项
   - **影响**:`sdk` 不因本 blueprint 被额外拆出;`application` 在文档上必须明确为 domain-neutral Python runtime layer;`audit` 边界要硬化为 explain / provenance / query / readback,避免再次混入 rendering

10. **Extraction route 归属:agent 自建 FastAPI app,不 mount 回 kernel.service.app_v1**
    - **Why**:原 blueprint 只说"从 kernel app_v1 删除 extraction 路由",未指定路由迁去哪、test 怎么找到 endpoint、OpenAPI 如何保持一致。这是 blueprint-level 规格悬挂。candidate 解法对比:(a) agent 自建 `agent/service/app.py`(独立 FastAPI app,可独立部署也可被外层 mount)— 干净、所有权清晰;(b) APIRouter 注入回 kernel app — 强耦合,违反 D1 边界(kernel 不该承载 LLM extraction surface);(c) 删 test、留待未来重建 — 会丢失 HTTP 契约覆盖
    - **决策**:选 (a)。新增 `src/agent/service/{__init__.py, app.py, docs/README.md}`,extraction DTO 文档 `05_extraction.md` 跟 owner 一起从 service 迁到 agent
    - **影响**:`test_extraction_http_api.py` 改用 `from agent.service.app import app`;`docs/api/openapi.yaml` 在 service 走出 kernel 后的归属与生成方式无法在本 blueprint 内一并解决,降级为 OS-prep TODO(单 yaml vs 双 yaml vs composed yaml)

11. **`git mv` 顺序修正:整目录搬迁先于二级目录创建,kernel 整名是最后一步**
    - **Why**:原 Step 2.1 写"先创建 `src/agent/`、`src/service/`、`src/domains/` 等新目录"。这是 bug——预先创建 top-level dir 后再 `git mv src/factpy_kernel/agent src/agent`,会把整个 agent **嵌套**到 `src/agent/agent/`。同样问题出现在 service / domains
    - **决策**:重写 Step 2 为 6 阶段顺序:(1) 整模块搬迁 `git mv src/factpy_kernel/{agent,service,domains} src/{agent,service,domains}`(让 git mv 创建 top-level 目录);(2) 二级新目录 mkdir(`src/agent/service/`、各 tests/、`tools/benchmarks/tests/`);(3) 跨模块文件搬迁;(4) 测试搬迁;(5) 新建文件(agent service);(6) `git mv src/factpy_kernel src/kernel`(最后,此时旧目录已空到只剩 kernel 留存模块)
    - **影响**:Step 1 输出的 `git mv` 清单必须按此顺序,sed 重写在所有 `git mv` 之后

12. **Docs To Update 显式化:5 处关键 docs 不能依赖 grep 一把扫**
    - **Why**:原 §9 只列了"docs/README.md / architecture_principles.md / 顶层 README"等顶层文档,假设其余靠"grep -r factpy_kernel"批量扫到。但这种依赖会漂——5 处关键文档(`core/docs/04_service_layer.md`、`core/docs/04_public_contract_v1.md`、`service/docs/README.md`、`service/docs/01_overview.md`、`service/docs/06_frontend_integration.md`)涉及跨 package 路径引用 + 内容性删除(extraction 章节),需要显式列出
    - **决策**:§9 重写为 5 个分类:新建 / 搬入新位置 / 内容修改 / kernel 内边界文档 / agent 内文档 / 仓库级 docs。每条标注修改性质(搬迁 / 删 extraction 章节 / 更新 import 示例 / 边界硬化等)
    - **附加**:extraction HTTP 主文档 `service/docs/05_extraction.md` 跟随 owner 迁至 `agent/service/docs/`;`service/docs/01_overview.md` 和 `06_frontend_integration.md` 不再作为 extraction 主文档,只保留删除痕迹与索引指向 agent

13. **Scoped 前补齐 residual execution inconsistencies**
    - **Why**:完成 Decision 10-12 后,主 blueprint 仍有 4 处残余不一致:(a) §5.2 仍把 `domains` 写成 `ecss` 子目录搬迁,和 Step 2 的整包 `git mv src/factpy_kernel/domains src/domains` 不一致;(b) §5.4 / Step 2.9 只提 `packages.find`,遗漏了现有 `pyproject.toml` 中 `[tool.setuptools.package-data].factpy_kernel` 旧 key;(c) Step 3 仍残留 `scripts/export_openapi.py` 校验,与已降级到 OS-prep 的 OpenAPI 决策冲突;(d) Step 3 单条 `unittest discover -s src` 无法覆盖 `tools/benchmarks/tests/`
    - **决策**:在转 `scoped` 同一步完成 4 处清理:把 `domains` 映射对齐为整包搬迁;将 `package-data` 旧 key 更新/删除纳入 pyproject 修改;移除 OpenAPI validation;把测试命令拆为 `src/kernel/tests`、`src/agent/tests`、`src/service/tests`、`src/domains/ecss/tests`、`tools/benchmarks/tests` 五段
    - **影响**:Step 1 现在可以直接按 blueprint 产出完整 `git mv` 清单与 validation 命令,不再需要执行期二次解释

14. **Step 1 v1 review feedback — 5 处规格漂移修正**
    - **Why**:Step 1 v1 输出后用户 review 发现 5 处问题,严重度 P1×3 + P2×1 + P3×1:
      - **P1.a — agent/service/app.py 模板 import owner 错**:写成 `from kernel.service._common` / `from kernel.service.auth`,但 split 后 service 已经是 top-level package,正确形式是 `from service._common` / `from service.auth`。这不是 typo,是直接导致 import smoke 挂的 bug
      - **P1.b — sed 漏 quoted-string runtime targets**:G.0-G.3 只改 `from/import` 语句,`patch("factpy_kernel...")` / `patch.dict` / `patch.multiple` / `importlib.import_module(...)` 这类字符串字面量 runtime target 不被命中。复核发现 42 处 `patch(...)` + 27 处其它 quoted importpath = 69 处。不修补会直接炸测试,且 G.5 的"漏网 grep + 人工 review"无法承担这种 runtime-sensitive 修复责任
      - **P1.c — examples scope 不自洽**:原 §5.5 仅列 4 个 example(04/08/09/dora_pdf_extract),但实际 01/02/05/06/07 也都直接 import `factpy_kernel.X`(grep 验证 1+3+8+5+4 = 21 处引用)。不迁就是 5 个 demo 半坏,开源前低质量信号。`07_evidence_graph_multi_engine.ipynb` 还含 `patch("factpy_kernel.adapters...")`,跟 tests 同类问题
      - **P2 — 用了 macOS 默认无的 `md5sum`**:pre-flight 和 Phase I 都改成 `shasum -a 256`(macOS 内置)
      - **P3 — Phase E 预先建 4 个 tests/__init__.py**:`unittest discover` 不需要,引入未承诺的新文件,可能微妙改变 import 语义。撤掉,真有 discovery 问题再补
    - **决策**(在 Step 1 v2 出之前先 patch blueprint):
      - §5.3 Import path 重写规则增加 quoted-string section(8 条 double-quote + 8 条 single-quote)
      - §5.5 examples 改动重写为 8 notebook + 1 script 的完整表格,加 validation 分级(执行级 01/02/08/09/dora_pdf_extract;清零级 04/05/06/07)
      - §7 Acceptance 拆成"执行级"和"清零级"两组 examples;新增 3 条针对 agent/service/app.py 的 acceptance(exception handler / helper import owner / package-data 旧 key);archived blueprints 验证用 `shasum -a 256` 替换 md5sum
      - §8 Step 2.7 重写为 7 段 sed pass(G.0 / G.0.5 / G.1 / G.2 / G.3 / G.4 / G.5),G.0.5 收窄到 `STRING_TARGETS=$(grep -rlE "['\"]factpy_kernel\\." ...)` 命中文件,避免对所有 .py 全量误改;notebook 用一次性 `scripts/_namespace_rewrite_notebooks.py`(nbformat)统一处理
      - §8 Step 2.5 撤掉 4 个 tests/__init__.py 创建,只保留 agent/service/__init__.py
      - §5.3 agent/service/app.py 模板修正 helper import owner + 增加复制全局 `@app.exception_handler(Exception)` 的要求(envelope 与 kernel.service.app_v1 一致)
    - **影响**:Step 1 v2 在以下基础上产出:helper import 正确 / quoted-string 单独 pass / examples 全量 / shasum / 不预建 __init__.py / 异常 handler 复制。Step 1 v1 作为 review 基线被超越,不再 actionable

15. **Step 1 v2 review feedback — 3 阻塞 + 2 修正**
    - **Why**:Step 1 v2 输出后用户 review 发现:
      - **P0.a — notebook 脚本 vs validation 不匹配**:H.0 脚本只改 `code` cells,但 Phase I.5/I.6 对原始 `.ipynb` 做文本 grep,会把 markdown cells、raw cells、旧 outputs 里的 `factpy_kernel` 全算进去。`04/05/06/07` 必须 0 残余很可能被 outputs 历史字面量打爆。决策:扩脚本同时 rewrite markdown cells,加 `--check` 模式只检查 code+markdown cell sources(**不**看 outputs);validation 改为调用 `--check`,不再对 .ipynb 做文本 grep
      - **P0.b — G.0.5 用 macOS BSD 不稳的 grep**:`grep -rlE ... --include='*.py'` 在 macOS BSD grep 行为不一致(尤其 `-r` + `--include` 组合)。改用 `rg -l -g '*.py' "['\"]factpy_kernel\\." src tools examples`(rg 已是仓库约定工具)
      - **P0.c — G.5 / Phase I.6 grep scope 太宽**:扫到 `docs/blueprints/active/`(包括本 blueprint 自身)、`docs/references/`、`memory/session_handoffs/` 等历史档案,会长期 noisy。决策:scope 限定为"当前真相面" — `src tools examples README.md README.en.md docs/README.md docs/architecture_principles.md memory/current.md`,历史档案明确允许保留旧名引用
      - **P1.d — H.4 docs README 仍引用 dead name**:`agent/service/docs/README.md` 模板还写"不属于 `kernel.service`"、"不 mount 回 `kernel.service.app_v1`"。split 后这些名字已不存在,即使是负向引用也会让未来读者困惑。改为只写 positive reference(如 `service.app_v1` 仍是 service 包内合法名)
      - **P1.e — pre-flight `| tail -3` 掩盖失败**:无 `pipefail` 时 unittest 的 FAILED 退出会被 tail 截掉。决策:Phase scripts 顶部加 `set -euo pipefail`,baseline 命令去掉 `| tail -3`(unittest -q 输出本身已经短)
    - **决策**(在 Step 1 v3 出之前先 patch blueprint):
      - §5.5 "清零" 改为脚本 `--check` 模式;明确"不对原始 .ipynb 文本 grep"
      - §7 Acceptance 同步;增加"当前真相面残余扫描应为空" + 明示历史档案不进 validation
      - §8 Step 2.7 G.0.5 改用 rg;G.5 scope 限定为当前真相面 8 个路径
      - Step 1 v3 H.0 脚本改成 rewrite + check 双模式,rewrite 同时改 code + markdown cells
      - Step 1 v3 H.4 docs README 移除 kernel.service 负向引用
      - Step 1 v3 Pre-flight 加 `set -euo pipefail` + 去掉 `| tail -3`
    - **影响**:Step 1 v3 是基于"3 阻塞已修 + 2 小修正"的最终可执行版;v2 作为 review 基线被超越

16. **Step 1 v3 review feedback — 2 P1 + 1 P2**
    - **Why**:Step 1 v3 review 发现 3 处自相矛盾或漏面:
      - **P1.a — Phase I.6 仍把 raw notebook outputs 当失败**:H.0/`--check` 已明确"不查 outputs",但 Phase I.6 用 `rg -n "factpy_kernel" ... examples ...` 扫整份 .ipynb。`examples/04_ecss_souffle_compliance.ipynb` 的 outputs 含 `from factpy_kernel.sdk import ...` 等 5+ 处,以及 line 250+ 的 stack trace 路径 `~/hnsm-backend/src/factpy_kernel/sdk/store.py:480`,raw 文本扫会全部命中,与 tier-5 `--check` 自相矛盾
      - **P1.b — Docs / prose sweep 缺失,267 处 markdown 残留无 pass 覆盖**:复核命中 267 处 `src/factpy_kernel/...` 在 `src/**/docs/**/*.md`、`src/factpy_kernel/AGENTS.md`、`examples/README.md`、`src/factpy_kernel/sdk/docs/00_user_guide.en.md` 等。这些是**当前真相** docs(不是历史档案),Phase I.6 必扫到。v3 §9 Docs To Update 列了高层级 docs 但没有可执行 sweep step
      - **P2 — 2 处 bare-string `.py` 残留 sed 全漏**:`src/factpy_kernel/tests/_test_helpers.py:1` docstring "Shared fixtures for factpy_kernel contract tests." 与 `tools/benchmarks/extraction/run_re_docred.py:5` "The current factpy_kernel extract_document() extracts entity attributes" — 两处都是 bare 单词 `factpy_kernel`(无点号、非 import 语句、非 quoted-string),G.0-G.4 的所有 sed 模式都不命中;Phase I.6 会照样报错
    - **决策**(在 Step 1 v4 出之前先 patch blueprint):
      - §7 Acceptance:Phase I.6 显式排除 `examples/*.ipynb`,notebook 验证统一交给 `--check`;新增"Docs / prose sweep 已应用"acceptance;新增 2 处 bare-string acceptance(显式列出文件路径与改写内容)
      - §8 Step 2.7 G.5:`rg` 加 `-g '!*.ipynb'`,与 acceptance 对齐
      - §8 Step 2.8:新增"Docs / prose sweep"步骤,用 rg 收集 `src/**/docs/**/*.md` + `src/kernel/AGENTS.md` + `src/agent/AGENTS.md` + `examples/README.md` + `tools/benchmarks/README.md` 命中文件,sed 应用 import + 路径重写规则,残余 bare-string 人工 review;同步增加 2 处 bare-string 显式手工修
      - Step 1 v4 输出执行清单时把 docs sweep + 2 处 bare-string 显式列入 Phase H 步骤
    - **影响**:Step 1 v4 是真正的"可执行 + tier-6 残余应为 0"版本;v3 作为 review 基线被超越;`scripts/_namespace_rewrite_notebooks.py` 仍在 v4 落盘前不写仓库

17. **Step 1 v4 review feedback — 2 P1 + 2 P2**
    - **Why**:Step 1 v4 review 又发现 4 处问题:
      - **P1.a — `src/*.egg-info/**` 永久打爆 residual scan**:`pip install -e .` 后 setuptools 在 `src/factpy_kernel.egg-info/` 生成 PKG-INFO / SOURCES.txt / top_level.txt / dependency_links.txt / requires.txt,这些文件含 `factpy_kernel` 字样作为 package metadata 名(SOURCES.txt 头几行就是 `src/factpy_kernel/__init__.py` / `src/factpy_kernel.egg-info/PKG-INFO`)。`Phase I.6` / `G.5` 扫整个 `src/` 会永久红色,而这不是迁移漏网,是 metadata。决策:scope 改成显式枚举 4 个 package(`src/kernel src/agent src/service src/domains`),并加 `-g '!*.egg-info/**'` 防御
      - **P1.b — H.14.2 反引号注释会被当 command substitution 执行**:写法 `` `# === Pass 1 ===` `` 在 shell 里反引号会触发 command substitution。`# === Pass 1 ===` 作为命令在 subshell 内是注释返回空,但 `sed -i ''` 后多个空字符串参数会让 BSD sed 行为不可预测(可能被当文件名)。executor 极易炸。决策:**不要**在 sed 命令行内嵌反引号注释,改用 sed 命令外的普通 `# ` shell 注释行
      - **P2.c — H.14.2 catch-all 路径替换破坏 wildcard prose 语义**:`s|src/factpy_kernel/|src/kernel/|g` 会把 `docs/architecture_principles.md:55` 的 `src/factpy_kernel/*/docs/` 错改成 `src/kernel/*/docs/`(原意是"任一 module 的 docs",改后变成"只 kernel 包的 docs",但 docs 也在 agent/service/domains)。同质问题在 `examples/README.md:53`、`docs/module_docs_convention.md:5`。residual scan 看不出语义错。决策:把这 3 处列入 H.14.0 **预先**手工修(发生在 14.2 sed 之前),修后 sed 就不会命中
      - **P2.d — G.5 期望"应空"逻辑错**:G.5 在 Phase G(自动 sed)末尾运行,此时 H.14(docs sweep)+ H.15(bare-string)还没跑,残留必然有(docs/prose、wildcard 泛指、bare strings)。说"应空"是对未来状态的期望放在过去时点。决策:把 G.5 reframe 为"informational preview,用于规划 H.14/H.15 手工清理;不期望为空"。"必须为空"的 check 是 Phase I.6(在 H.14/H.15 之后)
    - **决策**(在 Step 1 v5 出之前先 patch blueprint):
      - §7 Acceptance:scope 改 4-package 显式枚举;增加"egg-info 排除"说明;增加 wildcard prose 手工修 acceptance(3 个文件)
      - §8 Step 2.7 G.5:scope 改 4-package + 加 `-g '!*.egg-info/**'` + reframe 为 informational preview(明示"不期望为空")
      - §8 Step 2.8 H.14:重组为 4 sub-step(14.0 预先手工修 wildcard、14.1 收集、14.2 sed、14.3 残余 review);明确不要在 sed 命令内嵌反引号注释
    - **影响**:Step 1 v5 是真正可执行 + 不会 false-positive 的版本;v4 作为 review 基线被超越;`scripts/_namespace_rewrite_notebooks.py` 仍在 v5 落盘前不写仓库

18. **Step 1 v5 review feedback — 2 P1 + 1 P2**
    - **Why**:Step 1 v5 review 又发现 3 处漏面:
      - **P1.a — Notebook 08 bare prose + markdown dotted refs 不被 H.0 规则覆盖**:`examples/08` cell 3 (code) 含 7 处 bare prose `factpy_kernel`(无点号,如 `install factpy_kernel itself` / `print("factpy_kernel imports OK.")` / `inside factpy_kernel`);cell 31 (markdown) 含 dotted refs `factpy_kernel.sdk.compile_schema_from_classes` 和 `factpy_kernel.service.runtime_v1.open_runtime_session`(在 markdown table 的 backtick 内,既无 from/import 前缀也无 quote 前缀)。`--check` 要求 cell sources 0 残余,这些不被规则改的话 tier-5 必挂
      - **P1.b — H.14.2 catch-all 对已搬迁 test 路径机械改错**:catch-all `s|src/factpy_kernel/|src/kernel/|g` 会把 `src/factpy_kernel/tests/test_agent_X.py` 错改成 `src/kernel/tests/test_agent_X.py`,但这些 tests 在 Phase D 已搬到 `src/agent/tests/`。复核命中:`src/factpy_kernel/agent/docs/README.md` 38 处 + `src/factpy_kernel/agent/observability/docs/README.md` 4 处 + `src/factpy_kernel/domains/ecss/docs/README.md` 1 处,共 43 处。需要在 catch-all 之前加 13 条 prefix-based sed 映射(`test_agent_*` / `test_extraction_http_api` / 4 条 static_ui-tied / 6 条 ECSS-tied / `test_benchmark_*`)
      - **P2.c — `docs/module_docs_convention.md` 整文件遗漏 scope**:该文件有 6 处 `factpy_kernel` 引用(`:5` / `:101` / `:105` 是 wildcard 路径泛指,`:26` / `:67-68` 是 specific 路径),既不在 v5 G.5/I.6 scope 也不在 H.14.1 DOCS_TARGETS。这是一个 durable docs entry(模块文档写作约定),不能漏。决策:把整个文件纳入 scope + 把 `:101` / `:105` 加入 H.14.0 wildcard 手工修(原本只列了 `:5`)
    - **决策**(在 Step 1 v6 出之前先 patch blueprint):
      - §5.3 新增两类 rewrite rule(只在 H.0 notebook 脚本里应用,不全局):naked dotted refs(`factpy_kernel.X` → `agent.X` / `service.X` / 等,无前缀)+ bare-string `\bfactpy_kernel\b` → `kernel`(word boundary,确保不影响已 dotted 的形式)
      - §7 Acceptance:增加 moved-test path 13 条 prefix 映射 acceptance;module_docs_convention.md 加入 scope
      - §8 Step 2.7 G.5:scope 加 `docs/module_docs_convention.md`
      - §8 Step 2.8 H.14:14.0 列出 module_docs_convention.md `:101` / `:105`(共 3 处);14.1 DOCS_TARGETS 加 module_docs_convention.md;14.2 在 catch-all path 之前插入 13 条 moved-test prefix 映射
    - **影响**:Step 1 v6 是真正可执行 + 0 false-positive 版本;v5 作为 review 基线被超越;`scripts/_namespace_rewrite_notebooks.py` 仍在 v6 落盘前不写仓库

19. **Step 1 v6 review feedback — 2 P1**
    - **Why**:Step 1 v6 review 又发现 2 处 P1 阻塞:
      - **P1.a — H.0 `--check` 假阳性**:`process_notebook` 不分 write/check 都调用 `rewrite_text(cell.source)`,然后统计修改后的 `cell.source.count("factpy_kernel")`。当 `--check` 跑时,即使磁盘 .ipynb 还有 `factpy_kernel` 残留,只要 rewrite 规则能覆盖,内存中已被改干净,residual 显示 0,`--check` 返回 exit 0。这意味着 Phase I.5 的"必须为空" check **完全失效** — 它验证的是"rewrite 规则能否覆盖",不是"磁盘文件是否已被改干净"
      - **P1.b — README 测试命令机械改后漏测**:`README.md:152` 和 `README.en.md:152` 当前是单条 `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"`。H.14.2 catch-all `s|src/factpy_kernel/|src/kernel/|g` 会改成 `src/kernel/tests`,看起来对,但实际上 split 后测试分散到 5 个目录,这条单段命令只跑 kernel tests,**漏掉 agent/service/domains/benchmark 全部测试**。开源后用户跑 README 命令会得到错误的"全绿"印象
    - **决策**(在 Step 1 v7 出之前先 patch blueprint):
      - §7 Acceptance:新增 README 5 段命令重写 acceptance(对齐 Phase I.3);新增 H.0 `--check` 必须只读 cell.source 不调用 rewrite 的 acceptance
      - §8 Step 2.8 H(手动文件修改):新增 README.md / README.en.md `:152` 测试命令显式重写步骤
      - Step 1 v7 H.0 脚本拆 process_notebook 为 write 和 check 两条路径:write 调 rewrite + 写盘 + 重数 residual;check 只读 cell.source 直接数 residual,不调 rewrite
    - **影响**:Step 1 v7 是真正的"--check 反映磁盘真相 + README 命令对齐 Phase I"版本;v6 作为 review 基线被超越;`scripts/_namespace_rewrite_notebooks.py` 仍在 v7 落盘前不写仓库

### 未决问题(转交 OS-prep blueprint)

- PyReason license 兼容性(若 GPL,需独立 package 或删除)
- 最终包名(是否换掉 `factpy` 前缀)
- LICENSE 文件 / CONTRIBUTING / 清根产物 / CI gate(ruff / mypy / coverage)
- OpenAPI YAML 在 service 走出 kernel 后的归属与生成方式(单 yaml / 双 yaml / composed yaml,见 Decision 10)

### 执行约束记录

- Hook 限制:assistant 不能直接 edit `src/` 下非 .md 文件,所有代码迁移由用户执行
- assistant 在 Step 1 提供完整 sed 模板与 `git mv` 清单
- archived blueprints 一字不改(用户原则:"否则就是干掉了我们自己工作流最可靠的部分")
