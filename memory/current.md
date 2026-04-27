# Current Operational Memory

最后更新:2026-04-27

## 当前阶段

**Namespace split 完成**:原单一 `factpy_kernel` package 拆分为 4 个独立 top-level packages,为 OS 准备扫清架构债。下一阶段是 OS-prep(LICENSE / 清根 / CI gate / 包名最终决定 / OpenAPI yaml 归属)。

- **本轮 blueprint**:[2026-04-27_kernel-namespace-split.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-04-27_kernel-namespace-split.md)(Decision 1-19,执行期 11 类 deviations 已记录)
- **执行节奏**:Phase A-F(整模块搬迁)→ Phase G(7 段 sed + nbformat 脚本)→ Phase H.1-H.16(手工编辑 + docs sweep)→ Phase I.0-I.6(全 7 项 validation 通过)
- **结果**:1023 tests 全绿(分 5 个目录)/ 5 执行级 examples 跑通 / `--check` 0 残余 / final scan 0 残余

## 当前 namespace(post-split)

```
src/
  kernel/          # 可审计推理 substrate(Python facade)
    core/ sdk/ adapters/ audit/ authoring/ application/ tests/
  agent/           # LLM extraction + 应用层
    extraction/ documents/ tools/ framework/ orchestrator/ session/ ...
    service/       # 独立 FastAPI app(extraction HTTP surface)
    tests/
  service/         # kernel 的 HTTP delivery 层(runtime / rules / registry)
    app_v1.py runtime_v1.py rules_v1.py registry_v1.py auth.py
    static_ui.py   # HTML 渲染(从 audit/ 搬入)
    tests/
  domains/
    ecss/          # ECSS-specific bundle(domain-aware code 集中地)
      vcd.py temporal.py uncertainty.py
      sdk_helpers.py compliance.py  # 从 kernel/sdk/ecss + kernel/audit/compliance 搬入
      tests/
tools/
  benchmarks/      # 含 6 个 benchmark harness tests(从 kernel/tests/ 搬入)
    tests/
```

## 当前运行基线

- 测试基线:**1023 tests 全绿**(kernel 611 / agent 255 + skipped 2 / service 42 / domains/ecss 99 / benchmark 16)
- 分支:`namespace-split`(待 atomic commit + push;尚未 merge 回 master)
- HEAD:master 的最后一个 commit(本 branch 还没 commit)
- 工作树:大量 R/A/M(371+ 文件改动 + 新增 blueprint/audit/script + 多处文档/import 修正)

## 已验证的对外接口

(post-split namespace,接口语义不变,仅 import path 改)

| 入口 | 用途 | 状态 |
|---|---|---|
| `from kernel.sdk import Entity, Field, Identity, ...` | Python SDK | 已验证 |
| `from agent.extraction import extract_document` | Python 产品 API | 已验证 |
| `from agent.extraction import extract_document_from_ir` | pre-compiled schema IR 入口 | 已验证 |
| `agent.service.app:app`(FastAPI) | extraction HTTP `/v1/extraction/documents` | 已验证 + tests |
| `service.app_v1:app`(FastAPI) | kernel runtime / rules / registry HTTP routes | 已验证 |
| `from service.static_ui import render_audit_static_site` | 审计 HTML 渲染 | 已验证 |
| `from domains.ecss.compliance import ...` | ECSS 合规矩阵 + VCD predicates | 已验证 |
| `examples/09_dora_document_extraction.ipynb` | DORA real-LLM demo | 已验证 |
| `examples/dora_pdf_extract.py <pdf>` | CLI 真实 PDF 抽取 | 已验证 |

## Active 蓝图现状

session 2 遗留的 15 份 active 蓝图仍在(架构决策 v2、dialog agent、problog/pyreason explain、ontology feasibility、market alignment、dialog-agent v1.1 delta)—— 等下一轮 triage。

本轮归档:[`2026-04-27_kernel-namespace-split.{md, audit.md}`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/) → `archive/`,status `implemented`。

## 下一步方向

**优先级 1**(blueprint 已识别):**OS-prep**
- LICENSE / CONTRIBUTING / CODE_OF_CONDUCT / .gitignore 清根产物
- CI gate(ruff / mypy / coverage / import-boundary)
- PyReason license 兼容性查证(可能影响 adapters/pyreason 是否进 OS extras)
- 最终包名决定(是否换掉 `factpy_kernel`/`factpy-kernel` 前缀)
- OpenAPI YAML 归属与生成方式(kernel-only / agent-only 双 yaml / composed yaml / 弃用文件契约)
- `kernel/audit/query.py` 的 `list_compliance_matrix` 是否进一步迁出 kernel 进 domains/ecss(架构净化,本轮 lazy import 是过渡方案)

**优先级 2**:session 2 遗留 active 蓝图 triage(已实现可归档 / 继续保留 / 撤销)

**不该在 OS-prep 阶段做的**:
- 不再做 namespace 内部子模块重组(本轮 Plan A 严格执行,内部结构稳定)
- 不再加 god file refactor(`runtime_v1.py 2810` / `static_ui.py 2528` / `sdk/store.py 1499` / `sdk/batch.py 1838`,作为 post-OS 内部质量提升)

## 工程踩坑记录(对未来执行有用)

- **Bash tool 实际是 zsh**:`for f in $VAR` 不 word-split,**用 `while IFS= read -r f; do ... done <<< "$VAR"`**
- **macOS BSD sed 不支持 `\b` word boundary**:bare-string token 替换用具体上下文(如 `(name)`、` `name` `)而非依赖 word boundary
- **跨包搬迁文件相对 import 必须改绝对**:不只是 `static_ui.py` 这一个,所有跨包搬迁的 .py 文件都要扫(本轮漏了 `domains/ecss/{compliance,sdk_helpers}.py`)
- **__init__.py re-exports 必须扫**:搬迁 .py 文件时检查它原所在 package 的 `__init__.py` 是否 re-export 了它的符号(本轮 kernel/audit/__init__.py 漏了 compliance + static_ui re-exports)
- **`from .X import` 模块级 import 在跨包后会引入跨包模块级耦合**:用 lazy import 在方法内做(本轮 audit/query.py 用此手法保留 `list_compliance_matrix` 而不污染 kernel 模块加载)

## 未解决的未决点

- 仓库根下 `archive/`、`esa_demo_output/`、`dora_demo_output/`、`out/` 等历史产物区被 `.gitignore` `/*` 规则吞,不污染提交,但如果要彻底清理需要单独一轮
- `dora_pdf_extract.py` 内部 "demo sample" 的默认路径已失效(demo/ 目录早已清理),小问题

## 启动阅读顺序(新 session 用)

1. [本文件](/Users/zhenzhili/hnsm-backend/memory/current.md)
2. [最新归档 blueprint](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-04-27_kernel-namespace-split.md)(架构现状 + 11 类 deviations)
3. [AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) + [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md)(工作流)
4. [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)(文档体系索引,post-split paths)
5. [src/kernel/AGENTS.md](/Users/zhenzhili/hnsm-backend/src/kernel/AGENTS.md)(kernel docs rules)
6. [src/agent/extraction/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/extraction/docs/README.md)(extraction 管道真相)
7. [src/service/docs/01_overview.md](/Users/zhenzhili/hnsm-backend/src/service/docs/01_overview.md)(kernel HTTP 接口真相)
8. [src/agent/service/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/service/docs/README.md)(extraction HTTP 真相)
9. [examples/README.md](/Users/zhenzhili/hnsm-backend/examples/README.md)(demo 入口)
