# Task Blueprint: Kernel Namespace Split

- Status: implemented
- Created: 2026-04-27
- Last Updated: 2026-04-27
- Related Modules:
  - `src/factpy_kernel/` (现状,本 blueprint 后将被拆分)
  - `src/factpy_kernel/agent/` → 搬至 `src/agent/`
  - `src/factpy_kernel/service/` → 搬至 `src/service/`
  - `src/factpy_kernel/domains/` → 搬至 `src/domains/`
  - `src/factpy_kernel/audit/static_ui.py` → 搬至 `src/service/static_ui.py`
  - `src/factpy_kernel/sdk/ecss.py` → 搬至 `src/domains/ecss/sdk_helpers.py`
  - `src/factpy_kernel/audit/compliance.py` → 搬至 `src/domains/ecss/compliance.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [factpy-kernel-report-audit-2026-04-20.md](../../../factpy-kernel-report-audit-2026-04-20.md)(audit 报告对当前 namespace 不洁的诊断)
- Audit Log:
  - [2026-04-27_kernel-namespace-split.audit.md](./2026-04-27_kernel-namespace-split.audit.md)

## 1. Problem

`factpy_kernel.{agent, service, domains}` 三个 namespace 在概念上**不属于 kernel**:

- `agent/` 是 LLM extraction 应用层(刚转向、未落地)
- `service/` 是 HTTP delivery 层(`runtime_v1.py 2810` 是仓库最大 god file)
- `domains/ecss/` 是航天合规 domain-specific 实现
- `audit/static_ui.py 2528` 是 HTML 渲染,delivery 层
- `sdk/ecss.py` / `audit/compliance.py` 是 ecss 的跨模块 helpers,从 kernel 反向 import `domains/`

这些都是**架构谎言**——当前 namespace 不反映真实分层。开源 kernel 之前必须先把 namespace 拆到位,理由:

1. **Namespace 是契约**。一旦开源后再改名,会打爆所有早期用户的 import。改名只有"开源前"和"永远不改"两个时机
2. **依赖图天然单向**(`agent/service/domains → kernel`,反向只有 3 处已知违规),拆分门槛低
3. **OS 准备的前置条件**:不拆,publish 时要么写复杂的 file filter,要么把不该开源的代码也带出去
4. **代码质量风险面收窄**:audit 报告点名的 god files(runtime_v1, static_ui)随 service 一起搬出 kernel,**kernel 自身的开源面**直接干净一截

本 blueprint 同时收口 `kernel` 的**当前定义**:

- `kernel` v0.1 指向**面向 Python 接入方的可审计推理 substrate**
- 它承载 shared semantics、provenance / explain、多引擎执行、以及 Python-facing 的 authoring / facade / neutral runtime layer
- 它**不是**当前意义上的 "language-agnostic minimal semantics engine"
- 非 Python / 跨进程接入当前由独立 `service` package 承担;若未来要支持真正的 language-agnostic kernel,需要独立的 IR + CLI/IPC/gRPC 等接入面,不在本 blueprint 范围内

## 2. Goals

- 将 `factpy_kernel.{agent, service, domains}` 三个子 namespace 提升为独立 top-level packages:`agent`、`service`、`domains`(**包名占位为短名,长名/最终名后续单独定**)
- 处理 4 处跨 namespace 的耦合文件,使其归属正确的 package
- 将 6 个 ECSS-tied tests 跟 ecss code 一起搬入 `domains/ecss/tests/`
- 将 41 个 agent tests + 1 个 extraction HTTP test 跟 agent code 一起搬入 `agent/tests/`
- 将 4 个 static_ui-tied tests 跟 static_ui 一起搬入 `service/tests/`
- 将 6 个 benchmark harness tests 搬入 `tools/benchmarks/tests/`(它们 subprocess 进 tools/,本就不属 kernel)
- 修正 `core/annotation/docs/README.md` 的 "prototype" label(实际已 wired 进 core/store)
- 1023 tests 全绿
- examples/notebooks(`08`、`09`、`dora_pdf_extract.py`)端到端跑通
- **原子单 commit**——中间状态会全断 import

## 3. Non-goals

- **不**做 kernel 内部子模块重组(core/sdk/adapters/audit/authoring/application 内部不动)
- **不**改 god file(`sdk/batch.py 1838`、`sdk/store.py 1499`、`runtime_v1.py 2810`)的内部实现——只搬位置
- **不**修改 `archived/` blueprints 内的旧 path 引用——历史档案是 system of record,不动
- **不**做 OS 准备工作(LICENSE、CONTRIBUTING、.gitignore 清根、CI gate)——单独 blueprint
- **不**给 packages 定最终名——本 blueprint 用占位短名(`kernel`/`agent`/`service`/`domains`),最终名(可能换掉 `factpy` 前缀)是后续独立决策
- **不**拆 pyproject 成 multi-pyproject——保持单 root pyproject(选项 X),只在 `packages.find` 中枚举新 packages
- **不**验证 PyReason license 兼容性——这是 OS 前置 TODO,记录在 §6,但不是本 blueprint 的 acceptance
- **不**重写 4 个 static_ui-tied 测试为 DTO-level 测试——它们暂以"service-layer integration test"身份搬走,refactor 后续

## 4. Current Context

- **当前实现入口**:`src/factpy_kernel/` 是单一 top-level package,内含 14 个一级子模块
- **当前已知约束**:
  - 314 .py 文件、~57k LOC、1023 tests
  - hook 限制:assistant 不能直接 edit `src/factpy_kernel/` 下的非 .md 文件,实际改动由用户手动执行
  - GitHub Actions 跑 `unittest discover`(Python 3.10 / 3.11 矩阵)
  - 测试基础设施:`src/factpy_kernel/tests/_test_helpers.py`(只依赖 `factpy_kernel.sdk`)
- **依赖图复核结果**(2026-04-27 跑完 8 项检查):
  - `kernel → agent` 违规仅 1 处:`service/extraction_v1.py:9`(extraction_v1 跟 agent 一起搬走,违规自然消除)
  - `kernel → domains` 违规仅 2 处:`sdk/ecss.py:8`、`audit/compliance.py:5`(两者都跟 ecss 一起搬走)
  - `agent → kernel` 单向,涉及 4 个 namespace(self / core / sdk / service),无循环
  - `kernel/__init__.py` 空 docstring,无 cross-layer re-export
  - 无 conftest.py、无 monkey-patch、无 entry_points 注册
- **当前相关历史蓝图**:
  - `archived/2026-04-14_consumer-usage-handoff.md`(用户 facing 文档体系建立)
  - `archived/2026-04-14_document-extraction-http-api.md`(extraction_v1.py + app_v1.py 路由的来源)
- **session 上下文**:本 blueprint 是 OS 准备的前置步骤,后续会有独立 blueprint 处理 LICENSE / 清根 / CI gate / docs polish / publish

## 5. Proposed Shape

### 5.1 目标目录结构

```
src/
  kernel/                        ← 原 factpy_kernel/(去掉 agent, service, domains, ecss helpers, static_ui)
    core/                        保持
    sdk/                         保持(去 ecss.py)
    adapters/                    保持(pyreason 标 experimental)
      problog/
      pyreason/
      souffle/
    audit/                       保持(去 static_ui.py + compliance.py)
    authoring/                   保持
    application/                 保持
    tests/                       保持(去 agent/ecss/static_ui-tied/benchmark 测试)
    __init__.py                  保持空

  agent/                         ← 原 kernel/agent/
    candidate_cache.py
    documents/
    draft.py
    errors.py
    extraction/
    framework.py
    observability/
    orchestrator.py
    recovery.py
    session.py
    tools/                       (含 _runtime_api.py,跨包 import kernel.service.X)
    service/                     ← 新模块,容纳 extraction HTTP surface
      __init__.py                (新建)
      app.py                     (新建,FastAPI app + /v1/extraction/documents 路由)
      extraction_v1.py           ← 原 kernel/service/extraction_v1.py
      docs/                      ← 新建,extraction HTTP 文档 owner
        README.md                (新建,agent service 模块说明 + 索引)
        05_extraction.md         ← 原 kernel/service/docs/05_extraction.md(extraction DTO 契约跟 owner 走)
    tests/                       ← 原 kernel/tests/test_agent_*.py(41) + test_extraction_http_api.py
    __init__.py

  service/                       ← 原 kernel/service/(去 extraction_v1.py)
    _certainty_service.py
    _common.py
    _registry_io.py
    app_v1.py                    (删 line 60 + 323-344 extraction 路由块)
    auth.py
    registry_v1.py
    rules_v1.py
    runtime_v1.py
    static_ui.py                 ← 原 kernel/audit/static_ui.py
    tests/                       ← 4 个 kernel/tests/ 中依赖 static_ui 的测试
    __init__.py

  domains/
    __init__.py                  ← 原 kernel/domains/__init__.py
    ecss/                        ← 原 kernel/domains/ecss/
      temporal.py
      uncertainty.py
      vcd.py
      sdk_helpers.py             ← 原 kernel/sdk/ecss.py
      compliance.py              ← 原 kernel/audit/compliance.py
      tests/                     ← 6 个 kernel/tests/ 中 ecss-tied 测试
      __init__.py

tools/
  benchmarks/                    现状不动
    tests/                       ← 6 个 kernel/tests/test_benchmark_*.py(新建)
```

### 5.2 命名空间映射(详尽清单)

```
=== 原 kernel/ 内部保持(只去某些文件)===
src/factpy_kernel/core/                                  → src/kernel/core/                 (整目录)
src/factpy_kernel/sdk/                                   → src/kernel/sdk/                  (去 ecss.py)
src/factpy_kernel/adapters/                              → src/kernel/adapters/             (整目录)
src/factpy_kernel/audit/                                 → src/kernel/audit/                (去 static_ui.py + compliance.py)
src/factpy_kernel/authoring/                             → src/kernel/authoring/            (整目录)
src/factpy_kernel/application/                           → src/kernel/application/          (整目录)
src/factpy_kernel/__init__.py                            → src/kernel/__init__.py
src/factpy_kernel/tests/_test_helpers.py                 → src/kernel/tests/_test_helpers.py
src/factpy_kernel/tests/test_<kernel-only>.py            → src/kernel/tests/                (除下方搬出的)

=== 整模块搬迁 ===
src/factpy_kernel/agent/                                 → src/agent/                       (顶级 package 化)
src/factpy_kernel/service/                               → src/service/                     (顶级 package 化,去 extraction_v1.py)
src/factpy_kernel/domains/                               → src/domains/                     (顶级 package 化,内含 __init__.py + ecss/)

=== 跨模块文件 ===
src/factpy_kernel/service/extraction_v1.py               → src/agent/service/extraction_v1.py
src/factpy_kernel/service/docs/05_extraction.md          → src/agent/service/docs/05_extraction.md (extraction DTO 文档跟 owner 走)
src/factpy_kernel/audit/static_ui.py                     → src/service/static_ui.py
src/factpy_kernel/sdk/ecss.py                            → src/domains/ecss/sdk_helpers.py
src/factpy_kernel/audit/compliance.py                    → src/domains/ecss/compliance.py

=== 新建文件 ===
src/agent/service/__init__.py                            (新建)
src/agent/service/app.py                                 (新建,FastAPI app + extraction 路由注册)
src/agent/service/docs/README.md                         (新建,agent service 模块说明 + extraction HTTP docs 索引)

=== 测试搬迁 ===
src/factpy_kernel/tests/test_agent_*.py (41)             → src/agent/tests/
src/factpy_kernel/tests/test_extraction_http_api.py      → src/agent/tests/

src/factpy_kernel/tests/test_problog_semantic_annotation_l4.py    → src/service/tests/
src/factpy_kernel/tests/test_problog_candidate_evidence_tree.py    → src/service/tests/
src/factpy_kernel/tests/test_annotation_consumer_l2.py             → src/service/tests/
src/factpy_kernel/tests/test_assertion_fact_meta_embedding.py      → src/service/tests/

src/factpy_kernel/tests/test_ecss_compliance_contracts.py          → src/domains/ecss/tests/
src/factpy_kernel/tests/test_domain_walkthrough_contracts.py       → src/domains/ecss/tests/
src/factpy_kernel/tests/test_evidence_tree_explain_contracts.py    → src/domains/ecss/tests/
src/factpy_kernel/tests/test_phase3_contracts_v1.py                → src/domains/ecss/tests/
src/factpy_kernel/tests/test_artifact_sidecar_contracts.py         → src/domains/ecss/tests/
src/factpy_kernel/tests/test_winning_branch_rule_trace_contracts.py → src/domains/ecss/tests/

src/factpy_kernel/tests/test_benchmark_workload_a_smoke.py         → tools/benchmarks/tests/
src/factpy_kernel/tests/test_benchmark_workload_a_compare.py       → tools/benchmarks/tests/
src/factpy_kernel/tests/test_benchmark_workload_b_smoke.py         → tools/benchmarks/tests/
src/factpy_kernel/tests/test_benchmark_workload_b_compare.py       → tools/benchmarks/tests/
src/factpy_kernel/tests/test_benchmark_workload_c_smoke.py         → tools/benchmarks/tests/
src/factpy_kernel/tests/test_benchmark_workload_c_compare.py       → tools/benchmarks/tests/
```

### 5.3 Import path 重写规则

```
# kernel 内部:整体 namespace 改名(在每个搬入 src/kernel/ 的文件中)
from factpy_kernel.X        → from kernel.X
from factpy_kernel           → from kernel

# agent 内部:self-references 改 namespace
from factpy_kernel.agent.X  → from agent.X
# agent 引用 kernel 的 import 改 namespace
from factpy_kernel.core.X   → from kernel.core.X
from factpy_kernel.sdk.X    → from kernel.sdk.X
from factpy_kernel.service.X → from service.X     (注意:service 也搬出去了)

# service 内部:self-references 改 namespace
from factpy_kernel.service.X → from service.X
# service 引用 kernel 的 import 改 namespace
from factpy_kernel.X        → from kernel.X

# domains/ecss 内部:self-references 改 namespace
from factpy_kernel.domains.ecss.X → from domains.ecss.X
# domains 引用 kernel 的 import 改 namespace
from factpy_kernel.X        → from kernel.X

# 跨模块文件的特殊处理
src/agent/service/extraction_v1.py:
  from factpy_kernel.agent.extraction → from agent.extraction
  from factpy_kernel.service._common  → from service._common

src/service/static_ui.py:
  (相对 import 保持,因为它从 audit/ 搬到 service/ 了,要重新 wire 它对原 audit/ 模块的依赖)
  from .authoring_events import ...  → from kernel.audit.authoring_events import ...
  from .assertions import ...         → from kernel.audit.assertions import ...
  from .dto import ...                → from kernel.audit.dto import ...
  from .evidence_graph import ...     → from kernel.audit.evidence_graph import ...
  from .query import ...              → from kernel.audit.query import ...
  from .reader import ...             → from kernel.audit.reader import ...

src/domains/ecss/sdk_helpers.py:
  from factpy_kernel.domains.ecss.vcd import ... → from domains.ecss.vcd import ...
  (kernel.sdk 的内部依赖保持: from kernel.sdk.X)

src/domains/ecss/compliance.py:
  from factpy_kernel.domains.ecss.vcd import ... → from domains.ecss.vcd import ...

# Runtime-sensitive 字符串重写(patch / patch.dict / patch.multiple / importlib.import_module / 任意 quoted importpath)
# 共 ~69 处命中(42 patch + 27 其它),散布在 tests + 部分 notebook(尤其 examples/07)
# 应用范围:仅对 grep 命中文件做(避免对所有 .py 全量跑误改非 runtime 字符串)
"factpy_kernel.tests._test_helpers   → "kernel.tests._test_helpers
"factpy_kernel.audit.static_ui       → "service.static_ui
"factpy_kernel.audit.compliance      → "domains.ecss.compliance
"factpy_kernel.sdk.ecss              → "domains.ecss.sdk_helpers
"factpy_kernel.agent                 → "agent
"factpy_kernel.service               → "service
"factpy_kernel.domains               → "domains
"factpy_kernel.                      → "kernel.
(同样规则应用于单引号 'factpy_kernel.X' 形式)

# Naked dotted refs(无 from/import/quote 前缀的 dotted path,常见于 markdown table、code 注释、inline backticks)
# 仅在 notebook nbformat 脚本(H.0)内应用,覆盖 examples/08 markdown cell 31 类场景
factpy_kernel.tests._test_helpers    → kernel.tests._test_helpers
factpy_kernel.audit.static_ui        → service.static_ui
factpy_kernel.audit.compliance       → domains.ecss.compliance
factpy_kernel.sdk.ecss               → domains.ecss.sdk_helpers
factpy_kernel.agent                  → agent
factpy_kernel.service                → service
factpy_kernel.domains                → domains
factpy_kernel.                       → kernel.

# Bare-string prose(无点号、无前缀)— 常见于 docstring、README prose、notebook prose
# 仅在 notebook nbformat 脚本(H.0)内应用最后一 pass,覆盖 examples/08 cell 3 类场景
\bfactpy_kernel\b                    → kernel
# 注:.py 中的 bare string 残留(_test_helpers.py:1 / run_re_docred.py:5)由 H.15 显式手工修,不依赖此 pass
# 注:.md 中的 bare string 残留由 H.14.3 manual review 决定(可能改 kernel,可能改 prose 重写)

# Extraction 路由从 kernel service 移除,改由 agent service app 提供
src/service/app_v1.py(原 kernel/service/app_v1.py):
  - DELETE: line 60   from factpy_kernel.service.extraction_v1 import extract_document_endpoint as _extract_handler
  - DELETE: line 323-344 整个 @app.post("/v1/extraction/documents") 路由块

src/agent/service/app.py(新建):
  - 提供独立 FastAPI app 实例(可独立部署,也可被外层 mount)
  - 注册 POST /v1/extraction/documents 路由
  - handler 来自 from agent.service.extraction_v1 import extract_document_endpoint
  - auth dependency:from service.auth import require_api_key(注意:service 是 top-level package,**不是** kernel.service)
  - shared HTTP helpers:from service._common import error_response(同上)
  - **复制 kernel.service.app_v1 的全局 `@app.exception_handler(Exception)` handler**,确保 unhandled exception 返回的 envelope JSON 和 kernel app 一致
  - 跨包依赖方向:agent → service,service → kernel(不引入 agent → kernel.service 这个伪路径)
  - 不重复 kernel app 的 lifespan / middleware,只承载 extraction surface

src/agent/service/__init__.py(新建):空 docstring 即可,不公开 re-export

src/agent/service/docs/README.md(新建):
  - 说明 agent service 模块的存在理由(extraction HTTP surface 归 agent owner)
  - 索引 05_extraction.md
  - 提示与 kernel.service 的关系(独立 app,不 mount kernel app)

# 测试内部 import 改 namespace
src/agent/tests/test_*.py:
  from factpy_kernel.agent.X       → from agent.X
  from factpy_kernel.tests._test_helpers import ... → from kernel.tests._test_helpers import ...
  (跨包 import test helper,合法 because agent 依赖 kernel)

src/agent/tests/test_extraction_http_api.py(从 kernel/tests/ 搬入):
  from factpy_kernel.service.app_v1 import app → from agent.service.app import app
  (TestClient 改用 agent app,extraction 路由现在由它提供)

src/service/tests/test_*.py:
  from factpy_kernel.audit.static_ui import ... → from service.static_ui import ...
  其它 import 按规则改

src/domains/ecss/tests/test_*.py:
  from factpy_kernel.domains.ecss import ... → from domains.ecss import ...
  from factpy_kernel.sdk.ecss import ...     → from domains.ecss.sdk_helpers import ...
  from factpy_kernel.audit.compliance import ... → from domains.ecss.compliance import ...
```

### 5.4 pyproject.toml 修改

```toml
[project]
name = "factpy-kernel"            # 暂不改名(包名 placeholder 留待 OS-prep 时再定)
version = "0.1.0"
# ...

[tool.setuptools.packages.find]
where = ["src"]
# 不再写 include/exclude;find 会自动发现 kernel/ agent/ service/ domains/ 4 个 package

[tool.setuptools.package-data]
# 若仍保留 package-data,旧 `factpy_kernel` key 必须改名为 `kernel`;
# 若迁移后已无对应 package data,则删除旧 key,不要保留过期配置
```

extras 不变(extraction / documents / service / observability),用户体验 `pip install -e ".[extraction,documents]"` 不变。

### 5.5 examples / notebooks 改动

**全部 import-bearing examples 都迁**(8 个 notebook + 1 个脚本),否则开源后用户 clone 跑前 7 个 demo 会撞片成片半坏:

| Example | 引用数 | 改动 | Validation 等级 |
|---|---|---|---|
| `examples/01_sdk_basics.ipynb` | 1 | import 重写 | **执行** |
| `examples/02_rules_and_derivations.ipynb` | 3 | import 重写 | **执行** |
| `examples/04_ecss_souffle_compliance.ipynb` | (含 ecss) | import + ecss 路径重写 | 只清零 grep,不强制执行(依赖 souffle 二进制) |
| `examples/05_dora_pyreason_propagation.ipynb` | 8 | import 重写 | 只清零 grep,不强制执行(依赖 pyreason) |
| `examples/06_problog_probabilistic.ipynb` | 5 | import 重写 | 只清零 grep,不强制执行(依赖 problog) |
| `examples/07_evidence_graph_multi_engine.ipynb` | 4 | import + **patch 字符串**重写(`patch("factpy_kernel.adapters...")`) | 只清零 grep,不强制执行 |
| `examples/08_agent_document_workflow.ipynb` | (含 agent) | import 重写 | **执行** |
| `examples/09_dora_document_extraction.ipynb` | (含 agent) | import 重写 | **执行** |
| `examples/dora_pdf_extract.py` | (含 agent) | import 重写 | **执行**(`--max-segments 2` smoke) |

**重写规则**(每个 cell 内的 Python 源码):
```
from factpy_kernel.agent.X     → from agent.X
from factpy_kernel.service.X   → from service.X
from factpy_kernel.domains.X   → from domains.X
from factpy_kernel.sdk.ecss    → from domains.ecss.sdk_helpers
from factpy_kernel.audit.compliance → from domains.ecss.compliance
from factpy_kernel.audit.static_ui  → from service.static_ui
from factpy_kernel.X           → from kernel.X
"factpy_kernel.X"              → quoted-string 规则同 §5.3
```

**Validation 分级语义**:
- "执行" = `jupyter nbconvert --to notebook --execute` 全 cell 跑通,无 import 错、无 runtime 错
- "只清零" = `python scripts/_namespace_rewrite_notebooks.py --check` 对该 notebook 报告 **cell sources(code + markdown)0 残余 `factpy_kernel`**;**不**对原始 .ipynb 做文本 grep,因 notebook 旧 outputs 可能含历史字面量,文本 grep 会被这些非 source 残留打爆;不强制 cell 全跑通(因依赖外部 engine binary)

### 5.6 文档修改(非搬迁,docs-only)

```
src/kernel/core/annotation/docs/README.md:
  - 把 "状态:internal / prototype" 改为 "状态:experimental / internal API"
  - 添加一行说明:"已被 kernel/core/store 内部消费,不允许 breaking change 但 public API 不承诺"

src/kernel/AGENTS.md / docs/README.md / docs/architecture_principles.md:
  - 更新对 kernel 边界的描述(去掉 agent/service/domains 在 kernel 内的提法)

README.md / README.en.md:
  - 更新所有 import 示例(`factpy_kernel.agent.extraction` → `agent.extraction`)
  - 重新表述"两层能力"(kernel 部分 + agent 部分,但二者属于不同 packages)

src/kernel/agent/extraction/docs/USAGE.md(随 agent 搬走后路径变成 src/agent/extraction/docs/USAGE.md):
  - 更新 import 示例
```

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - 单 commit 原子提交,中间不允许出现 import 红
  - 1023 tests 全绿(包括所有搬迁后的位置)
  - examples/{08, 09} notebook + dora_pdf_extract.py 端到端跑通(cell 级 verify,不只是 import)
  - `archive/` 内 blueprints 一字不改
  - `kernel/__init__.py` 保持空(不要在拆分过程中添加 re-exports)
  - `_test_helpers.py` 留在 kernel,不复制到其它 package(避免 fixture drift)
- **定义约束**:
  - `kernel` 的当前定义固定为 D1:**面向 Python 接入方的可审计推理 substrate**;本 blueprint 不把它表述为 language-agnostic minimal engine
  - `service` 是非 Python / 跨进程 / delivery-facing 接入面;将其搬出 kernel 后,`kernel` 自身不再承诺任何非 Python surface
  - `application` 留在 kernel 内,但其 "neutral" 仅指 **domain-neutral Python runtime layer**,不是 language-neutral protocol
  - `audit` 留在 kernel 内,并且只承载 explain / provenance / query / readback;任何 rendering / formatting / consumer-facing output 都归 `service` 或更上层 package
  - D2(language-agnostic minimal engine)是已识别的未来方向,但需要独立 IR + CLI/IPC/gRPC 等工作;不在本 blueprint 范围内
- **明确不做的内容**:
  - 不重写任何 god file 的内部实现
  - 不改 sdk/dsl(Python builder)和 authoring/(text DSL parser)的 dual-DSL 设计
  - 不引入 entry_points / 插件注册机制
  - 不引入新的工具链(uv workspace、hatch monorepo 等)
  - 不重写 4 个 static_ui-tied 测试为 DTO-level 测试(本 blueprint 不动测试逻辑)
- **兼容性约束**:
  - 完全 break:任何外部代码 `import factpy_kernel.agent.X` 等会断
    - 因为还未开源,只影响**当前 monorepo 内的 user / colleagues**
    - notebooks + scripts 在本 blueprint 内全部更新
- **OS 准备的前置 TODOs(不阻塞本 blueprint,但 OS 前必须解决)**:
  - PyReason license 必须查证(若 GPL,需独立成 package 或删除)
  - LICENSE 文件、CONTRIBUTING、CODE_OF_CONDUCT、清根产物文件
  - CI gate(ruff / mypy / coverage)
  - 包名(`factpy-kernel` 是否换名)
  - **OpenAPI YAML 在 service 走出 kernel 后需重新决定归属与生成方式**:本 blueprint 不再维持 `docs/api/openapi.yaml` 与单一 live spec 一致;OS-prep 阶段决定是 (a) kernel-only yaml + agent-only yaml 双文件,(b) composed yaml 由部署时合成,还是 (c) 弃用文件契约仅留 live spec

## 7. Acceptance

- [ ] 4 个 top-level packages(`kernel`、`agent`、`service`、`domains`)在 `src/` 下建立,目录结构与 §5.1 一致
- [ ] §5.2 mapping 表中所有文件迁移完成,无遗漏
- [ ] §5.3 import path 重写规则已应用至所有相关文件
- [ ] `service/app_v1.py` 中 extraction 路由块(line 60 + 323-344)已删除
- [ ] `src/agent/service/app.py` 已新建,`/v1/extraction/documents` 路由可被 TestClient 命中
- [ ] `src/agent/service/app.py` 包含全局 `@app.exception_handler(Exception)`(envelope 与 kernel.service.app_v1 一致)
- [ ] `src/agent/service/app.py` 的 helper import 是 `from service._common` / `from service.auth`(**不是** `from kernel.service.X`)
- [ ] `src/agent/service/__init__.py` 已新建(空)
- [ ] `src/agent/service/docs/README.md` 已新建,索引迁入的 `05_extraction.md`
- [ ] `core/annotation/docs/README.md` 状态 label 已修正
- [ ] `pyproject.toml` 的 `packages.find` 已识别 4 个 packages,`package-data` 旧 `factpy_kernel` key 已删除或更名
- [ ] `PYTHONPATH=src python -m unittest discover` 在 `src/kernel/tests/`、`src/agent/tests/`、`src/service/tests/`、`src/domains/ecss/tests/`、`tools/benchmarks/tests/` 各自跑通,合计 1023 tests 全绿
- [ ] **执行级 examples**(全 cell 跑通,无 import / runtime 错):
  - `examples/01_sdk_basics.ipynb`
  - `examples/02_rules_and_derivations.ipynb`
  - `examples/08_agent_document_workflow.ipynb`
  - `examples/09_dora_document_extraction.ipynb`
  - `examples/dora_pdf_extract.py`(`--max-segments 2` smoke)
- [ ] **清零级 examples**(`python scripts/_namespace_rewrite_notebooks.py --check` exit 0,即所有 notebook 的 code + markdown cell sources 中 `factpy_kernel` 字串 0 残余;不对原始 .ipynb 做文本 grep,避免被 outputs 历史字面量打爆;不强制 cell 全跑通):
  - `examples/04_ecss_souffle_compliance.ipynb`
  - `examples/05_dora_pyreason_propagation.ipynb`
  - `examples/06_problog_probabilistic.ipynb`
  - `examples/07_evidence_graph_multi_engine.ipynb`(包括 `patch("factpy_kernel.adapters...")` 这类 quoted-string,nbformat 脚本统一处理)
- [ ] `archived/` 下 blueprints **未被修改**(`shasum -a 256` 比对一致)
- [ ] 残余 `factpy_kernel` 全局扫描限定在**当前真相面**(显式枚举 4 个 packages,**不**扫整个 `src/`):
  - 扫:`src/kernel src/agent src/service src/domains tools examples README.md README.en.md docs/README.md docs/architecture_principles.md docs/module_docs_convention.md memory/current.md`
  - 输出应为空。多重排除:
    - `examples/*.ipynb` **不**进 raw 文本扫(notebook outputs 必含历史字面量;notebook 验证统一交给 `--check`)
    - `src/*.egg-info/**` **不**扫(setuptools 自动生成的 metadata,含 `factpy_kernel.egg-info` 目录名,这是元数据不是迁移漏网;reinstall 时会更新)
    - `docs/blueprints/**`、`docs/references/**`、`memory/session_handoffs/**`、`docs/blueprint_history/**` 是历史档案,允许保留旧名,不进 validation
- [ ] **Docs / prose sweep** 已应用至所有 `src/**/docs/**/*.md` + `src/kernel/AGENTS.md` + `src/agent/AGENTS.md` + `examples/README.md` + `tools/benchmarks/README.md`(import 行 + 路径引用 + bare prose 残余必须人工 review 清零)
- [ ] **Wildcard 路径泛指 prose 已显式手工修**(catch-all sed 会把 `src/factpy_kernel/*/X` 错改成 `src/kernel/*/X`,语义错误,因 docs 不只在 kernel):
  - `docs/architecture_principles.md:55` — `src/factpy_kernel/*/docs/` → 重写为指代多 package(如 `src/<package>/**/docs/` 或 prose"每个 top-level package 的 `docs/` 子目录")
  - `examples/README.md:53` — 同上
  - `docs/module_docs_convention.md:5` / `:101` / `:105` — 同上(整文件已纳入 H.14 sweep + Phase I.6 scope)
- [ ] **Moved-test path 引用已显式 sed 映射**(catch-all `s|src/factpy_kernel/|src/kernel/|g` 对已搬迁 tests 是错的——它们在 src/agent/tests/ 等,不在 src/kernel/tests/),H.14.2 在 catch-all 之前加 13 条 prefix sed:
  - `src/factpy_kernel/tests/test_agent_*` → `src/agent/tests/test_agent_*`(prefix,1 条覆盖 ~40 个文件)
  - `src/factpy_kernel/tests/test_extraction_http_api` → `src/agent/tests/`
  - 4 条 static_ui-tied(test_problog_semantic_annotation_l4 / test_problog_candidate_evidence_tree / test_annotation_consumer_l2 / test_assertion_fact_meta_embedding)→ `src/service/tests/`
  - 6 条 ECSS-tied → `src/domains/ecss/tests/`
  - `src/factpy_kernel/tests/test_benchmark_*` → `tools/benchmarks/tests/`(prefix,1 条覆盖 6 个)
- [ ] **Bare-string `.py` 残留**(无点号、不在 import 也不在 quoted-string)已显式手工修:
  - `src/kernel/tests/_test_helpers.py:1`(docstring "Shared fixtures for factpy_kernel contract tests." → "Shared fixtures for kernel contract tests.")
  - `tools/benchmarks/extraction/run_re_docred.py:5`(docstring "The current factpy_kernel extract_document()" → "The current agent.extraction extract_document()")
- [ ] **README 测试命令已重写为 5 段**(单段命令 sed 后只跑 `src/kernel/tests` 漏掉 agent/service/domains/benchmark,必须手工显式覆盖):
  - `README.md:152` — 旧:`PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"` → 新:5 段命令(对齐 Phase I.3,各覆盖 `src/kernel/tests` `src/agent/tests` `src/service/tests` `src/domains/ecss/tests` `tools/benchmarks/tests`)
  - `README.en.md:152` — 同上
- [ ] **H.0 notebook script `--check` 模式的 residual 是磁盘真实值**(不能在 `--check` 内调用 rewrite 然后统计 — 那是 post-rewrite 计数,会假阳性 0):`--check` 路径只读 cell.source 计 `factpy_kernel` count,不调用 rewrite_text
- [ ] 单一 atomic commit(若必要可拆 commit,但每个中间 commit 都必须保持 import + tests 绿)
- [ ] 受影响模块 docs(`kernel/AGENTS.md`、`docs/README.md`、`README.md`、`README.en.md`)已同步

## 8. Implementation Plan

> **执行约束**:hook 限制 assistant 不能直接 edit kernel 下的非 .md 文件。所有代码搬迁与 import 重写**由用户手动完成**,assistant 提供完整指令清单与 sed 模板。Blueprint 中所有改动应**作为一个 atomic git commit**(或一组 squashable commits)执行,以避免 import 半红半绿的中间状态。

### Step 1 — 准备 sed 模板与文件清单(assistant 输出)

1. 生成完整的 `git mv` 命令清单(覆盖 §5.2 所有迁移)
2. 生成完整的 sed pattern 清单(覆盖 §5.3 所有 import 重写)
3. 用户在干净 work tree 上 review 清单

### Step 2 — 执行迁移(单一 atomic 操作)

> **关键顺序约束**:**不要**预先创建 top-level package 目录(`src/agent/`、`src/service/`、`src/domains/`)。预创建会让随后的 `git mv src/factpy_kernel/agent src/agent` 把整个 agent **嵌套**到 `src/agent/agent/` 里。正确做法:整目录搬迁先于二级目录创建,kernel 整体改名是最后一步。

1. **整模块搬迁(创建 top-level packages)**——不要预先 mkdir,让 git mv 创建:
   - `git mv src/factpy_kernel/agent src/agent`
   - `git mv src/factpy_kernel/service src/service`
   - `git mv src/factpy_kernel/domains src/domains`(内含 ecss/ 子目录)

2. **二级新目录创建**——此时 top-level 已存在,可安全 mkdir:
   - `mkdir -p src/agent/service src/agent/service/docs src/agent/tests`
   - `mkdir -p src/service/tests`
   - `mkdir -p src/domains/ecss/tests`
   - `mkdir -p tools/benchmarks/tests`

3. **跨模块文件搬迁**:
   - `git mv src/service/extraction_v1.py src/agent/service/extraction_v1.py`(注意 service 已搬到 src/service/)
   - `git mv src/service/docs/05_extraction.md src/agent/service/docs/05_extraction.md`
   - `git mv src/factpy_kernel/audit/static_ui.py src/service/static_ui.py`
   - `git mv src/factpy_kernel/sdk/ecss.py src/domains/ecss/sdk_helpers.py`
   - `git mv src/factpy_kernel/audit/compliance.py src/domains/ecss/compliance.py`

4. **测试搬迁**(用 shell glob 展开 + git mv 多源至已存在目录):
   - `git mv src/factpy_kernel/tests/test_agent_*.py src/agent/tests/`
   - `git mv src/factpy_kernel/tests/test_extraction_http_api.py src/agent/tests/`
   - `git mv src/factpy_kernel/tests/test_problog_semantic_annotation_l4.py src/factpy_kernel/tests/test_problog_candidate_evidence_tree.py src/factpy_kernel/tests/test_annotation_consumer_l2.py src/factpy_kernel/tests/test_assertion_fact_meta_embedding.py src/service/tests/`
   - `git mv src/factpy_kernel/tests/test_ecss_compliance_contracts.py src/factpy_kernel/tests/test_domain_walkthrough_contracts.py src/factpy_kernel/tests/test_evidence_tree_explain_contracts.py src/factpy_kernel/tests/test_phase3_contracts_v1.py src/factpy_kernel/tests/test_artifact_sidecar_contracts.py src/factpy_kernel/tests/test_winning_branch_rule_trace_contracts.py src/domains/ecss/tests/`
   - `git mv src/factpy_kernel/tests/test_benchmark_*.py tools/benchmarks/tests/`

5. **新建文件**(本 blueprint 引入的新代码):
   - 创建 `src/agent/service/__init__.py`(空)
   - 创建 `src/agent/service/app.py`(FastAPI app + extraction 路由,见 §5.3)
   - 创建 `src/agent/service/docs/README.md`(模块说明 + docs 索引)

6. **kernel 整目录改名**——**最后**一步,此时 factpy_kernel/ 内已无 agent/service/domains:
   - `git mv src/factpy_kernel src/kernel`

7. **批量 sed import + quoted-string 重写**(分 7 段 pass,顺序敏感):
   - **G.0**:`test_extraction_http_api.py` 单文件特殊重写(`from factpy_kernel.service.app_v1 import app` → `from agent.service.app import app`)
   - **G.0.5**(quoted-string,**仅对命中文件**):
     - 先收集:`STRING_TARGETS=$(rg -l -g '*.py' "['\"]factpy_kernel\\." src tools examples)`(用 rg,因 macOS BSD `grep -rlE --include` 不稳;rg 是仓库约定工具)
     - 再对 `$STRING_TARGETS` 跑 quoted-string 重写(覆盖 §5.3 quoted-string 规则,double + single quote 各 8 条)
     - **不**对所有 .py 全量跑——避免误改非 runtime 字符串
   - **G.1**(specific moved files,from/import):`tests._test_helpers` / `audit.static_ui` / `audit.compliance` / `sdk.ecss`
   - **G.2**(sub-namespace,from/import):`agent` / `service` / `domains`
   - **G.3**(catch-all,from/import):`factpy_kernel.X` → `kernel.X`
   - **G.4**(`src/service/static_ui.py` 相对 import 改绝对):`from .X import` → `from kernel.audit.X import`
   - **G.5**(**informational preview**,只列残留以规划 H.14/H.15 手工清理,**不**期望为空 — code-only sed 后必然还剩 docs / bare prose 残留;真正"必须为空"的 check 是 Phase I.6,在 H.14/H.15 之后):
     ```
     rg -n "factpy_kernel" \
       -g '!*.ipynb' \
       -g '!*.egg-info/**' \
       src/kernel src/agent src/service src/domains tools examples \
       README.md README.en.md docs/README.md docs/architecture_principles.md \
       docs/module_docs_convention.md memory/current.md
     ```
     scope 改 4 个 package 显式枚举(不扫整个 `src/`,避免 `src/*.egg-info/` setuptools metadata 误命中);
     增加 `docs/module_docs_convention.md`(durable docs entry,有 6 处 factpy_kernel 引用,不能漏);
     不扫 `docs/blueprints/**`、`docs/references/**`、`docs/blueprint_history/**`、`memory/session_handoffs/**`(历史档案);
     不扫 `examples/*.ipynb`(notebook 验证由 `--check` 承担)
   - **Notebook 处理**(.ipynb 不能用 sed 安全处理):一次性 Python 脚本 `scripts/_namespace_rewrite_notebooks.py`(nbformat 读写),应用 §5.3 全部规则(import + quoted-string + naked dotted + bare-string,7 段 pass)到 8 个 notebook 的 **code + markdown cells**(outputs 不动);`--check` 子模式直接读 `cell.source` 数 residual,不调 rewrite,反映磁盘真相

8. **手动文件修改**:
   - `src/service/app_v1.py`:删除 extraction 路由块(line 60 原位 + 323-344)
   - `src/service/static_ui.py`:相对 import 改为 `from kernel.audit.X import ...`
   - `src/kernel/core/annotation/docs/README.md`:更新 status label
   - 内容编写:`src/agent/service/app.py`(新文件)+ `src/agent/service/docs/README.md`
   - `src/service/docs/01_overview.md` / `06_frontend_integration.md` / `README.md`:删除 extraction 章节,更新索引
   - `src/factpy_kernel/agent/extraction/docs/USAGE.md`(随 agent 走后路径变):更新 import 示例
   - **Docs / prose sweep**(分 4 sub-step,顺序敏感):
     - **14.0 — 预先**手工修 wildcard 路径泛指 prose(catch-all sed 会语义错改;**必须先于 14.2 sed 跑**):
       - `docs/architecture_principles.md:55` — `src/factpy_kernel/*/docs/` 改写为指代多 package 形式(如 `src/<package>/**/docs/` 或 prose"每个 top-level package 的 `docs/` 子目录")
       - `examples/README.md:53` — 同上
       - `docs/module_docs_convention.md:5` / `:101` / `:105` — 3 处 wildcard(`src/factpy_kernel/*/docs/` 和 `src/factpy_kernel/<module>`)同上重写
     - **14.1** — 收集命中 .md 文件(增加 `docs/module_docs_convention.md`):`DOCS_TARGETS=$(rg -l "factpy_kernel" src/kernel src/agent src/service src/domains README.md README.en.md docs/README.md docs/architecture_principles.md docs/module_docs_convention.md examples/README.md tools/benchmarks/README.md memory/current.md -g '*.md')`
     - **14.2** — 单 sed 多 -e 重写每个 `$f`(顺序:**13 条 moved-test prefix 映射先行** → import 行 → 路径引用 → catch-all)。**注意**:**不要**在 sed 命令行内用反引号包裹注释行(会被 shell 当 command substitution 执行);分组注释用 sed 命令外的普通 `# ` shell 行
     - **14.3** — 残余 bare-string 人工 review 决定是否改 `kernel`
   - **Bare-string `.py` 残留人工修**(2 处,sed 不命中):
     - `src/kernel/tests/_test_helpers.py:1` — docstring "Shared fixtures for factpy_kernel contract tests." → "Shared fixtures for kernel contract tests."
     - `tools/benchmarks/extraction/run_re_docred.py:5` — "The current factpy_kernel extract_document()" → "The current agent.extraction extract_document()"
   - **README 测试命令重写**(单段命令机械改后只跑 src/kernel/tests,漏 4 个 dest;必须显式重写为 5 段):
     - `README.md:152` — 旧 1 段命令 → 新 5 段(覆盖 `src/kernel/tests` `src/agent/tests` `src/service/tests` `src/domains/ecss/tests` `tools/benchmarks/tests`,与 Phase I.3 一致)
     - `README.en.md:152` — 同上
   - **顺手清理 docs/module_docs_convention.md 内 fake test 例子**(非阻塞,但在 sweep 同一文件时一并修):
     - `:67` — `src/factpy_kernel/tests/test_core_ledger.py`(不存在)→ `src/kernel/tests/test_protocol_v1.py`
     - `:68` — `src/factpy_kernel/tests/test_derivation_accept.py`(不存在)→ `src/kernel/tests/test_annotation_store.py`

9. **pyproject.toml 修改**:`packages.find` 适配 4 个 packages,并更新或删除旧 `[tool.setuptools.package-data].factpy_kernel`

10. **examples / 顶层 README**(具体 notebook 清单见 §5.5):
    - 8 个 notebook(`01/02/04/05/06/07/08/09`)+ `dora_pdf_extract.py` 的 import 重写(notebook 由 Phase 7 的 nbformat 脚本统一处理)
    - `examples/07_evidence_graph_multi_engine.ipynb` 还含 `patch("factpy_kernel.adapters...")` quoted-string,nbformat 脚本一并重写
    - `examples/README.md` 路径引用更新
    - 顶层 `README.md` / `README.en.md` import 示例 + 双层叙事更新
    - `tools/benchmarks/README.md`(若引用 kernel test 路径)

### Step 3 — Validation

1. `pip install -e ".[extraction,documents,service,observability]"` 安装无错
2. `PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"` → kernel tests 绿
3. `PYTHONPATH=src python -m unittest discover -s src/agent/tests -p "test_*.py"` → agent tests 绿
4. `PYTHONPATH=src python -m unittest discover -s src/service/tests -p "test_*.py"` → service tests 绿
5. `PYTHONPATH=src python -m unittest discover -s src/domains/ecss/tests -p "test_*.py"` → domains/ecss tests 绿
6. `PYTHONPATH=src python -m unittest discover -s tools/benchmarks/tests -p "test_*.py"` → benchmark harness tests 绿
7. `python -c "from kernel.sdk import Entity, Field, Identity"` 烟测
8. `python -c "from agent.extraction import extract_document"` 烟测
9. `python -c "from agent.service.app import app"` 烟测(extraction app 独立存在)
10. `python -c "from service.app_v1 import app"` 烟测(注:此时 app 已不含 extraction 路由)
11. `python -c "from domains.ecss.vcd import *"` 烟测
12. `python examples/dora_pdf_extract.py samples/<x>.pdf --max-segments 2`
13. `jupyter nbconvert --to notebook --execute examples/09_dora_document_extraction.ipynb --output /tmp/_check_09.ipynb`
14. `jupyter nbconvert --to notebook --execute examples/08_agent_document_workflow.ipynb --output /tmp/_check_08.ipynb`
15. `git diff docs/blueprints/archive/` 必须为空

### Step 4 — Atomic commit + push

1. 一个 commit message,描述 namespace split 全貌,引用本 blueprint
2. blueprint status 由 `draft` → `implementing` → `implemented` → 移入 `archive/`
3. 更新 `memory/current.md`,反映新 namespace
4. 更新 `memory/README.md` 中相关索引或 handoff 指针(若有)

## 9. Docs To Update

> 显式列表(不依赖 `grep -r` 一次性扫)。每条都标注修改性质。

**新建**:
- `src/agent/service/docs/README.md`(新模块入口,索引迁入的 extraction docs,说明与 kernel.service 的关系)

**搬入新位置(随 owner 走)**:
- `src/factpy_kernel/service/docs/05_extraction.md` → `src/agent/service/docs/05_extraction.md`(extraction DTO 契约文档跟 owner 走)
- `src/factpy_kernel/agent/extraction/docs/USAGE.md` → `src/agent/extraction/docs/USAGE.md`(随 agent 整体搬走;内部 import 示例需更新)

**内容修改(原位 / 搬入后):删除 extraction 部分,更新交叉路径引用**:
- `src/factpy_kernel/service/docs/01_overview.md` → `src/service/docs/01_overview.md`(删除 `/v1/extraction/documents` 路由章节;更新对 05_extraction.md 的引用为指向 agent owner)
- `src/factpy_kernel/service/docs/06_frontend_integration.md` → `src/service/docs/06_frontend_integration.md`(删除 extraction 调用示例;不应继续作为 extraction 主文档)
- `src/factpy_kernel/service/docs/README.md` → `src/service/docs/README.md`(更新索引,去掉 05_extraction.md;说明 extraction 已迁至 agent.service.docs)

**kernel 内核心 docs(可能含 service / agent / domains 路径引用,需扫并改)**:
- `src/factpy_kernel/core/docs/04_service_layer.md` → `src/kernel/core/docs/04_service_layer.md`(若提及 service 路径或 extraction 路由,更新)
- `src/factpy_kernel/core/docs/04_public_contract_v1.md` → `src/kernel/core/docs/04_public_contract_v1.md`(同上,public contract 章节涉及 cross-package 引用)

**kernel 内边界文档(D1 定义同步)**:
- `src/kernel/AGENTS.md`(原 src/factpy_kernel/AGENTS.md;描述 D1 kernel 边界,去掉 agent/service/domains 内置提法)
- `src/kernel/core/annotation/docs/README.md`(状态 label 修正)
- `src/kernel/application/docs/01_overview.md`(把 "neutral runtime layer" 明确为 domain-neutral Python runtime layer)
- `src/kernel/audit/docs/README.md`(冻结 audit 只承载 explain / provenance / query / readback 的边界)

**agent 内文档(随搬入更新)**:
- `src/agent/AGENTS.md`(从原 src/factpy_kernel/agent/AGENTS.md 搬入)
- `src/agent/docs/README.md`(描述与 kernel / service 的依赖关系)

**仓库级 docs**:
- `docs/README.md`(顶层 docs 索引,所有 path 更新)
- `docs/architecture_principles.md`(若提到 factpy_kernel.agent / service / domains 的部分)
- `README.md` / `README.en.md`(顶层 README 的 import 示例与"两层能力"叙事)
- `examples/README.md`(若引用 factpy_kernel.* 路径)
- `tools/benchmarks/README.md`(若引用 kernel test 路径)
- `memory/current.md`(反映新 namespace)
- 本 blueprint 的 audit log(每个 stage 转换都加一条)

## 10. Outcome / Deviations

执行日期:2026-04-27(同 blueprint creation)

### 最终落地结果

- 4 个 top-level packages 建立:`src/{kernel,agent,service,domains}/`,旧 `src/factpy_kernel/` 不复存在
- `agent/service/{__init__,app,docs/{README,05_extraction}}.{py,md}` 新增 — 独立 FastAPI app + extraction owner 文档迁入
- `service/app_v1.py` extraction 路由块 + 入口 import 删除
- `service/static_ui.py` 从 audit/ 搬入,相对 import 全改绝对(`from kernel.audit.X`)
- `domains/ecss/{sdk_helpers,compliance}.py` 接收原 sdk/ecss 与 audit/compliance
- 测试搬迁:41 agent + 4 static_ui-tied + 6 ECSS-tied + 6 benchmark = 57 文件
- pyproject.toml `[tool.setuptools.package-data]` 整段删除
- 8 个 example notebooks(01/02/04/05/06/07/08/09)+ `dora_pdf_extract.py` import 全部重写
- README.md / README.en.md 完整重写(4-package narrative + 5 段测试命令 + import 示例 + path 链接)
- docs/architecture_principles.md / docs/module_docs_convention.md / examples/README.md 的 wildcard 路径 prose 已重写为多 package 形式
- core/annotation/docs/README.md status label 由 "internal / prototype" 改为 "experimental / internal API"
- service/docs/01_overview.md / 06_frontend_integration.md / README.md extraction 章节已删除或指向 agent.service
- 1023 tests 全绿(kernel 611 / agent 255+skipped 2 / service 42 / domains/ecss 99 / benchmark 16)
- 5 个执行级 examples 全部跑通(notebook 01/02/08/09 + dora_pdf_extract.py)
- 4 个清零级 examples(04/05/06/07)`--check` 残余 0
- 当前真相面 `factpy_kernel` 0 残余(Phase I.6 final scan 通过)

### 与 blueprint 不同的地方(execution-time deviations)

#### Tooling deviations

1. **`for f in $VAR` 在 Bash tool 下不 word-split**(Phase G + H 都中招)
   - **原因**:Bash tool 实际用 zsh,zsh 不在默认 IFS 上 word-split unquoted variable expansion
   - **修法**:全部改用 `while IFS= read -r f; do ... done <<< "$VAR"`(POSIX 兼容,bash/zsh 都正确)
   - **影响**:Phase G.0.5 + G.1-G.3 第一遍 sed 全部空跑(sed 报 "File name too long"),修法后重跑全成功

2. **macOS BSD sed 不支持 `\b` word boundary**(Phase H.14.3 补漏 pass + 1 处手工修)
   - **原因**:`\b` 是 GNU sed 扩展,BSD sed(macOS 自带)不识别
   - **修法**:针对 bare-string `factpy_kernel`(无点号)用具体 token 替换(如 `(factpy_kernel)`、` `factpy_kernel` `)而非依赖 word boundary;1 处 markdown 标题(`src/kernel/AGENTS.md:1`)手工改
   - **影响**:H.14 sweep 后还有 1 处残余,手工修后清零

3. **shasum baseline 在 pre-flight 漏跑**
   - **原因**:pre-flight 脚本里写了但实际执行时没跑那一段
   - **修法**:I.0 改用 `git diff HEAD docs/blueprints/archive` + `git status -s docs/blueprints/archive` 验证,语义等价
   - **影响**:验证目标(archived/ 一字未改)达成,验证手段不同

#### Spec gap deviations(blueprint 未预见的真实问题)

4. **`kernel/audit/__init__.py` re-export 已搬走的 `compliance.*` + `static_ui.*` 符号**
   - **原因**:blueprint 关注"搬迁文件"和"修改 importer",**未关注被搬迁文件的 re-exporter `__init__.py`**;`audit/__init__.py` 是 kernel.audit 的 public API,re-export 了 compliance / static_ui 符号
   - **修法**:删除 audit/__init__.py 中 compliance / static_ui 相关的 import 块 + __all__ 条目;加注释说明搬出去向
   - **影响**:I.2 import smoke 第一次失败,修后通过

5. **`kernel/audit/query.py` 模块级 `from .compliance import` 引入 kernel→domains 模块级耦合**
   - **原因**:query.py 有 `list_compliance_matrix()` 方法依赖 ECSS compliance 工具;blueprint 把 compliance.py 搬到 domains 后,query.py 的 import 变成 kernel→domains(违反 D1 边界)
   - **修法**:把 `from .compliance import` 移到方法内 lazy import,模块级零依赖,运行期再 import
   - **影响**:kernel 模块加载不再依赖 domains;list_compliance_matrix() 调用时仍需 domains.ecss 在路径上(测试与生产部署都满足)
   - **架构提示**:此函数本质上是 ECSS-aware,长期看应迁出 kernel/audit 进 domains/ecss(本 blueprint 不做)

6. **跨包搬迁文件相对 import 漏改**(同 G.4 static_ui 那类问题,但 G.4 只覆盖了 static_ui,其它跨包文件没扫)
   - 影响文件:`domains/ecss/compliance.py:16`(`from .assertions`)、`domains/ecss/sdk_helpers.py:19-20`(`from .errors / .store`)
   - **修法**:改绝对 import:`compliance.py` → `from kernel.audit.assertions`;`sdk_helpers.py` → `from kernel.sdk.errors / store`
   - **影响**:I.2 import smoke 第二次失败,修后通过

7. **3 个 kernel-level 测试**(`test_certainty_explain_contracts` / `test_evidence_graph_audit_delivery` / `test_souffle_partial_witness_v1`)还在 `from kernel.audit import render_audit_static_site`
   - **原因**:这 3 个测试本来就是 integration 跨包测,blueprint 把它们留在 kernel/tests 是对的(它们测的是 kernel reasoning + audit chain);但 `render_audit_static_site` 已搬到 service.static_ui
   - **修法**:`from kernel.audit import ... render_audit_static_site` → `from kernel.audit import ...`(去除 render_audit_static_site)+ `from service.static_ui import render_audit_static_site`
   - **影响**:kernel tests 第一次失败 3 errors,修后 611 全绿

8. **agent test 的 `patch("service.extraction_v1.X")` patch path 错改**
   - **原因**:G.0.5 quoted-string sed 规则有 `"factpy_kernel.service` → `"service`,对 extraction_v1 错改为 `service.extraction_v1`(应为 `agent.service.extraction_v1`)
   - **修法**:targeted sed:`"service\.extraction_v1\.` → `"agent.service.extraction_v1.`,改 2 处
   - **影响**:agent tests 第一次失败 2 errors,修后 255 全绿(skipped 2)

9. **6 个 ECSS test 的 `from kernel.audit import ECSS_*`** 因 audit/__init__.py 删 re-export 而失效
   - **修法**:写 Python 脚本统一拆分 import 块,把 ECSS_* + helpers → `domains.ecss.compliance`,render_audit_static_site → `service.static_ui`,其余符号留 `kernel.audit`
   - **影响**:ECSS tests 第一次失败 6 errors,修后 99 全绿

#### Blueprint 内 docs 漂移(执行后期补)

10. **docs/README.md 顶层文档索引仍把 OpenAPI yaml 列为"当前真相机读契约 48 ops"** —— 与 blueprint defer 决策(Decision 10 + OS-prep TODO)冲突。已改写为"归属待定 (deferred to OS-prep)",注明拆分后 yaml 不再与单一 live spec 一致
11. **docs/module_docs_convention.md:67-68 fake test names**(`test_core_ledger.py` / `test_derivation_accept.py` 不存在)—— 替换为真实文件 `test_protocol_v1.py` / `test_annotation_store.py`(blueprint H.16 已计划但实际编辑漏跑,close-out 时补上)

### 为什么会有这些调整

- **#1-3(tooling)**:Bash tool 的实际 shell 是 zsh 不是 bash,而 BSD sed 不是 GNU sed —— blueprint 默认假设的是 bash + GNU sed,这是默认假设错误
- **#4-9(spec gap)**:blueprint 关注 "搬迁哪些文件" 而非 "搬迁后哪些 importer / re-exporter / lazy-coupled callsite 受影响",依赖图复核没下沉到 `__init__.py` re-export 这一层
- **#10-11(docs 漂移)**:execution 期间补做的小型 docs 同步,blueprint 已计划但执行时被遗漏

### 归档说明

- Status:`scoped` → `implementing`(2026-04-27 Phase A-F 开始时切换)→ `implemented`(本次 close-out)
- 移入:`docs/blueprints/archive/2026-04-27_kernel-namespace-split.md` 与 `.audit.md`
- 后续 OS-prep blueprint 必须接收以下 TODOs:
  - PyReason license 兼容性
  - 最终包名(是否换 `factpy_kernel`)
  - LICENSE / CONTRIBUTING / 清根产物 / CI gate
  - OpenAPI yaml 归属与生成方式
  - kernel/audit/query.py 的 `list_compliance_matrix` 是否进一步迁出 kernel(架构净化)
- archive 后,memory/current.md 和 memory/MEMORY.md 索引中相关 path 需同步更新
