---
title: factpy-kernel 调研报告审计
created: 2026-04-20
tags:
  - audit/report
  - project/factpy-kernel
  - topic/market
  - topic/code-review
---

# factpy-kernel 调研报告审计

> [!summary]
> 结论先行：这份报告不是“胡写”，其中有相当一部分硬事实是可核实的，尤其是 AWS Automated Reasoning、DORA、EU AI Act 时间线、Norm Ai、AIUC、DARPA CLARA、本地仓库规模、`runtime_v1.py`/`ledger.py` 规模、`replace_field`/`accept_many` 的事务边界等。
>
> 但它也明显混杂了四种不同层级的信息：
> 1. **官方可核实事实**
> 2. **厂商自述 / marketing**
> 3. **本地仓库内部文档与作者自述**
> 4. **作者自己的强判断 / 推断**
>
> 最大问题不是“方向全错”，而是 **把推断写成定论、把 vendor marketing 写成市场事实、把局部代码观察写成绝对结论**。因此，这份报告更适合当“高强度红队意见草稿”，不适合直接当投资/战略尽调终稿。

## 总评

### 我对报告整体可信度的判断

| 维度 | 判断 | 说明 |
|---|---|---|
| 外部法规与发布日期 | 较高 | 多个关键日期和产品发布信息可由官方来源确认 |
| 融资/竞品存在性 | 中高 | 多数能找到公司官方或主流媒体支持 |
| 市场份额/窗口期/销售周期 | 中低 | 很多是经验判断或二手材料，不能当硬事实 |
| 本地代码规模/关键文件断言 | 较高 | 大量数字与文件可本地复核 |
| 本地代码质量总判断 | 中等 | 有真实问题，但不少措辞过猛，且有若干已过时/不准确点 |
| 创业结论 | 可参考但非定论 | 方向性判断有价值，但证据强度不足以支撑“几乎被挤占完毕”这种绝对表述 |

### 这份报告最有价值的地方

- 它抓住了真正重要的战略问题：`kernel` 叙事是否能卖给客户，和 AWS / AgentCore / 合规自动化产品的重叠是否过大。
- 它没有被“技术上很酷”迷惑，确实在反复逼问 buyer、distribution、认证、reference logo、vertical packaging。
- 它在本地代码层面识别出了一批真实的 load-bearing 风险：事务边界、单例注册、巨型模块、审计路径静默吞异常、边界靠自律不靠工具。

### 这份报告最需要修正的地方

- 把 **“存在同类产品”** 推到了 **“空间几乎被挤占完毕”**。
- 把 **“一些基础原语并非原创”** 推到了 **“几乎没有任何创新性”**。
- 把 **“CI 缺少 lint/type/coverage/import-boundary gate”** 写成了 **“没有任何质量自动化护栏”**。
- 把 **“局部技术尽调可能会挑出很多问题”** 写成了 **“OEM partner 第一天就会退场”**。

## 外部事实核查

### 1. AWS Bedrock Automated Reasoning Checks 已 GA，且与合规/审计叙事高度重叠

- 结论：**成立**
- 证据：
  - AWS 官方 GA 公告：2025-08-06 上线 Automated Reasoning checks in Amazon Bedrock Guardrails，宣称 “up to 99% accuracy” 并面向受监管场景。  
    来源：[AWS What's New](https://aws.amazon.com/about-aws/whats-new/2025/08/automated-reasoning-checks-amazon-bedrock-guardrails/)
  - AWS 官方文档明确把它定位为用 formal logic 验证 LLM 输出是否与 policy 一致，并提供 auditable feedback。  
    来源：[AWS Bedrock Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-automated-reasoning-checks.html)
  - AWS 与 PwC 的联合文章可证实它已被包装进 regulated-industry narrative。  
    来源：[PwC and AWS Build Responsible AI with Automated Reasoning on Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/pwc-and-aws-build-responsible-ai-with-automated-reasoning-on-amazon-bedrock/)
- 审计意见：
  - “和项目核心卖点高度重叠”这个判断 **方向正确**。
  - 但“因此你基本失去商业空间”是 **推断**，不是官方事实。

### 2. Byron Cook 与 AWS Automated Reasoning 的关联

- 结论：**基本成立**
- 证据：
  - AWS Security Blog 明确写 Byron Cook 是 AWS Automated Reasoning Group 的负责人。  
    来源：[AWS Security Profile: Byron Cook](https://aws.amazon.com/blogs/security/aws-security-profile-byron-cook-director-aws-automated-reasoning-group/)
  - Amazon Science 页面也明确把 Byron Cook 与 AWS 新的 Automated Reasoning checks 关联起来。  
    来源：[Amazon Science: Automated Reasoning](https://www.amazon.science/research-areas/automated-reasoning)
- 审计意见：
  - 报告把 “Byron Cook 团队” 写进 Bedrock reasoning 叙事是合理的，不算夸张。

### 3. DORA 时间线

- 结论：**成立**
- 证据：
  - ESMA 官方页面：DORA 于 2023-01-16 生效，自 2025-01-17 起适用。  
    来源：[ESMA DORA page](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/digital-operational-resilience-act-dora)
- 审计意见：
  - 报告中“DORA 已生效，窗口仍在”的时间判断基本准确。

### 4. EU AI Act Article 12 / Annex IV / 2026-08-02 时间点

- 结论：**大体成立，但需补充边界**
- 证据：
  - EU AI Act Service Desk：高风险系统的多数义务自 **2026-08-02** 起适用。  
    来源：[EU AI Act Implementation Timeline](https://ai-act-service-desk.ec.europa.eu/en/ai-act/eu-ai-act-implementation-timeline)
  - Article 12 确实要求高风险 AI 系统具备自动记录事件（logs）的能力。  
    来源：[Article 12: Record-keeping](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12)
  - Annex IV 确实定义了技术文档要求。  
    来源：[Annex IV](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-4)
- 审计意见：
  - 报告把 Article 12 当成 “硬窗口”是合理的。
  - 但应明确：**Article 12 只针对高风险 AI 系统**，不是所有 AI 产品天然适用。

### 5. EU AI Act “7% 全球营收罚款”

- 结论：**事实本身成立，但报告用法容易误导**
- 证据：
  - Article 99(3) 明确写明，对 Article 5 所涉 **被禁止的 AI practices**，最高罚款可达 EUR 35M 或全球年营收 7%。  
    来源：[Article 99: Penalties](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-99)
- 审计意见：
  - “7%” 是真的。
  - 但它对应的是 **最严重违规**，不是一般“解释性不够”就直接 7%。  
  - 报告若把这条直接当 buyer urgency 的通用论据，会 **夸大合规销售压力**。

### 6. Norm Ai 融资与定位

- 结论：**成立**
- 证据：
  - Norm 官方：2025-03-11 宣布融资 $48M，总融资 $87M。  
    来源：[Norm Ai Secures $48M](https://www.norm.ai/post/norm-ai-secures-48-million-to-transform-regulations-into-compliance-ai-agents)
- 审计意见：
  - 报告把 Norm Ai 视为“法规编译成 AI agents”的强验证样本，这个对比是有依据的。

### 7. AIUC 融资与“AI agent 保险”品类

- 结论：**成立**
- 证据：
  - Fortune 报道：AIUC 于 2025-07-23 以 $15M seed 出 stealth。  
    来源：[Fortune](https://fortune.com/2025/07/23/ai-agent-insurance-startup-aiuc-stealth-15-million-seed-nat-friedman/?queryly=related_article)
- 审计意见：
  - 报告把它归类为新 buyer 类别是合理的。
  - 但“factpy 几乎就是 AIUC 的地基”属于 **高强度推断**，证据不够。

### 8. Microsoft Agent Governance Toolkit

- 结论：**成立**
- 证据：
  - Microsoft Open Source Blog：2026-04-02 发布 Agent Governance Toolkit。  
    来源：[Microsoft Open Source Blog](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/)
- 审计意见：
  - 报告关于“runtime governance 层正在被大厂占位”的判断有事实基础。

### 9. AWS AgentCore Policy / agent infra 在 2026 年继续推进

- 结论：**成立**
- 证据：
  - AgentCore 总览页与官方 GA 公告可证实 Runtime / Policy / Memory / Observability 等都已形成产品线。  
    来源：[AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)  
    来源：[Policy in Amazon Bedrock AgentCore is now generally available](https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/)
- 审计意见：
  - 报告关于“平台层正在被云厂商吞掉”的结论 **方向正确**。

### 10. DARPA CLARA 机会

- 结论：**成立**
- 证据：
  - DARPA 官方页面确认 CLARA 项目存在，2026-02 发布，截止 2026-04-17。  
    来源：[DARPA CLARA](https://www.darpa.mil/research/programs/clara)
  - FAQ 中可见 funding cap 相关信息。  
    来源：[CLARA FAQ PDF](https://www.darpa.mil/sites/default/files/attachment/2026-02/program-clara-faq.pdf)
- 审计意见：
  - 报告把 CLARA 作为“政府/学术 anchor”的建议，证据强度很高。

### 11. Semantica 作为相邻/镜像型开源项目

- 结论：**大体成立**
- 证据：
  - 官方站点明确主打 context graph、decision intelligence、W3C PROV-O provenance、reasoning engines。  
    来源：[Semantica](https://hawksight-ai.github.io/semantica/)
- 审计意见：
  - “存在高度相邻定位的开源项目”是事实。
  - “几乎镜像”则是作者判断，不是客观事实；Semantica 的产品面明显更广。

### 12. Imandra 的客户/融资/定位

- 结论：**部分成立**
- 证据：
  - Amazon SBIR 奖项页摘要提到 Goldman Sachs 是其 public sector client 之一。  
    来源：[SBIR award abstract](https://www.sbir.gov/awards/187888)
  - OCaml success story 也提到 2017 年与 Goldman Sachs 的合作。  
    来源：[OCaml success story](https://ocaml.org/success-stories/financial-compliance-with-automated-reasoning)
  - 融资总额 $23M 可见于二级媒体。  
    来源：[PYMNTS](https://www.pymnts.com/artificial-intelligence-2/2025/startups-technique-brings-mathematical-precision-to-gen-ai/)
- 审计意见：
  - “Imandra 是真实在位者”成立。
  - 但融资额与客户叙述主要依赖二级来源，严肃尽调时最好再找公司/投资方一手材料。

### 13. AUI / Apollo-1 的 $750M valuation cap

- 结论：**成立**
- 证据：
  - 公司官方稿与 VentureBeat 都能找到。  
    来源：[AUI official](https://www.aui.io/resources/aui-raises-20-million-at-750-million-valuation-cap-following-breakthrough-in-neuro-symbolic-ai/)  
    来源：[VentureBeat](https://venturebeat.com/ai/the-beginning-of-the-end-of-the-transformer-era-neuro-symbolic-ai-startup/)
- 审计意见：
  - 这条可用，但更像“资本市场 narrative 证据”，不是 buyer demand 证据。

### 14. Stardog / Ontotext 客户与在位竞争者地位

- 结论：**部分成立**
- 证据：
  - Stardog 官方能确认 Boehringer、NASA、BNY Mellon 等客户/案例存在。  
    来源：[Stardog customers](https://www.stardog.com/company/customers/)  
    来源：[Stardog Series B expansion announcement](https://www.stardog.com/news/stardog-the-leading-enterprise-knowledge-graph-platform-expands-series-b-to-11.4-million-to-mature-go-to-market-initiatives/)
  - Ontotext 官方客户页能确认匿名 Korean bank、Swiss insurer、AstraZeneca 等。  
    来源：[Ontotext customers](https://www.ontotext.com/company/customers/)
- 审计意见：
  - 报告“这类 enterprise KG / reasoning 厂商早已在客户生产环境中”这个方向成立。
  - 但列出的具体 logo 和 anonymized case 混在一起，表达上不够严谨。

### 15. Oracle Argus “约 60% 市场份额”

- 结论：**证据不足**
- 证据：
  - Oracle 官方只称 Argus 为 “market-leading” / “industry-leading”，未给 60% 市占。  
    来源：[Oracle Argus](https://www.oracle.com/apac/life-sciences/safety-solutions/argus-safety-case-management/)
- 审计意见：
  - “Argus 是强势 incumbent”大概率成立。
  - “≈60% 市占”我未找到可信一手或高质量二手来源支持，不建议保留。

### 16. “RAG 可将 hallucination 降低 35–60%”

- 结论：**证据不足**
- 证据：
  - 能找到很多综述说明 RAG 通常有助于降低 hallucination。  
    来源：[Hallucination Mitigation for Retrieval-Augmented Large Language Models: A Review](https://www.mdpi.com/2227-7390/13/5/856)
  - 但报告中的 **35–60%** 我未找到足够稳固的主来源来支持其作为通用数字。
- 审计意见：
  - 可写成“RAG 通常能降低 hallucination 风险”，不要写成固定区间。

### 17. “70–80% AI initiatives 死在 pilot”

- 结论：**证据不足 / 口径松散**
- 审计意见：
  - 这是咨询/媒体文章里常见的二级传播数字，但不同语境下口径差异很大。
  - 作为文章修辞尚可，作为尽调结论不够硬。

## 本地代码断言核查

> [!note]
> 本节基于本地仓库 `/Users/zhenzhili/hnsm-backend` 的只读复核。

### 1. 仓库规模断言

- 结论：**成立**
- 复核结果：
  - `*.py` 文件数：`314`
  - 非测试 Python 行数：`57,209`
  - 测试文件数：`106`
  - 测试函数数：`1,023`
- 审计意见：
  - 这部分数字非常扎实，报告不是在虚张声势。

### 2. God file 行数

- 结论：**成立**
- 复核结果：
  - `service/runtime_v1.py`：`2810` 行
  - `audit/static_ui.py`：`2528` 行
  - `sdk/batch.py`：`1838` 行
  - `sdk/store.py`：`1499` 行
  - `core/store/ledger.py`：`1147` 行
- 审计意见：
  - “有多个巨型文件”这个问题是真实存在的。

### 3. 类型检查 / lint / coverage / boundary tooling 缺失

- 结论：**基本成立**
- 复核结果：
  - `pyproject.toml` 中未见 `mypy` / `pyright` / `ruff` / `coverage` / `pre-commit` / `import-linter` / `tach` 配置。
- 审计意见：
  - 报告关于“缺少机器强制边界工具”的判断是对的。
  - 但它后续把这一点推演成“没有任何质量自动化护栏”，就过头了。

### 4. “没有 CI / 没有任何自动化护栏”

- 结论：**不成立**
- 复核结果：
  - 仓库有 GitHub Actions 工作流：`.github/workflows/factpy-kernel-tests.yml`
  - 会在 Python 3.10 / 3.11 上跑 `unittest discover`
  - 也会装 `.[service]` 跑部分 service 测试
- 审计意见：
  - 更准确的说法应该是：**有测试型 CI，但没有 lint/type/coverage/import-boundary gate。**

### 5. `replace_field` 是否真 atomic

- 结论：**部分成立**
- 复核结果：
  - `replace_field()` 先 `_preflight_new_assertion(...)`，再 `retract_by_asrt(...)`，再 `set_field(...)`。
  - 也就是说，**验证失败时旧断言不会先被撤销**，这一点已经修补。
  - 但撤销与新写入仍是两个独立操作，不是单个 DB transaction。
- 审计意见：
  - 报告说“不是严格意义上的原子事务”是对的。
  - 但若把它表述成“F-CORE-1 只是文书修复”就不对，因为 **validation rollback 这一层确实已修**。

### 6. `accept_many_candidate_sets(mode="atomic")` 是否只是补偿性回滚

- 结论：**成立**
- 复核结果：
  - `_rollback_atomic_accept_many(...)` 对已写入 `asrt_id` 逐个 `retract_by_asrt(...)`，属于补偿性 rollback。
- 审计意见：
  - 报告在这点上是准确的：这是业务层“回滚语义”，不是数据库事务级原子性。

### 7. `_ENGINE_REGISTRY` 是模块级可变单例

- 结论：**成立**
- 复核结果：
  - `core/store/runtime.py` 中存在模块级 `_ENGINE_REGISTRY: dict[str, EngineEvaluatorFn] = {}`
- 审计意见：
  - 报告对此的风险描述有依据。

### 8. `Ledger.__deepcopy__` 的实现

- 结论：**成立，但使用次数被夸大**
- 复核结果：
  - `Ledger.__deepcopy__()` 的确通过 SQLite backup + reload 实现。
  - 但全仓库 `deepcopy(` 总命中数没有报告说的那么高，而且大多数不是对 `Ledger` 的复制。
- 审计意见：
  - “存在昂贵的 deepcopy 实现”成立。
  - “全 codebase 15 处调用”我没有复核出同等强度证据。

### 9. `except Exception` / `type: ignore` / `assert` / `print` / `logging`

- 结论：**部分成立，且报告统计口径不一致**
- 复核结果（按 `src/factpy_kernel/**/*.py`、排除 tests）：
  - `type: ignore`：`42`
  - `assert`：`274`
  - `except Exception`：`100`
  - `import logging`：`2`
  - `print(`：`3`
- 审计意见：
  - `42 type: ignore`、`274 assert`、`2 logging imports` 这几个数与报告接近或一致。
  - 但 `print()` 在 Python 源码里只有 `3` 处，且都在 `authoring/cli.py`；报告的 `91` 明显不是同一统计口径。
  - `except Exception` 的真实数量反而 **高于** 报告给出的 `41`。

### 10. 审计物化路径的静默吞异常

- 结论：**成立**
- 复核结果：
  - `runtime_v1.py:1985`, `2065`, `2106` 等位置确有 `except Exception: continue`
- 审计意见：
  - 这是报告中最值得保留的代码风险点之一。

### 11. “core 不静态 import adapters”

- 结论：**成立**
- 复核结果：
  - 在 `src/factpy_kernel/core` 下未发现对 `factpy_kernel.adapters` 的静态 import。
- 审计意见：
  - 这是报告给出的正向评价，且经复核成立。

### 12. import 边界违规示例

- 结论：**部分成立，且部分例子已过时或写错**
- 复核结果：
  - 成立的例子：
    - `adapters/pyreason/runner.py` 导入 `sdk.dsl.rule`
    - `sdk/store.py` 导入 `adapters.souffle.package` / `runner`
    - `service/runtime_v1.py` 导入 adapters / audit / authoring
    - `adapters/souffle/package.py` 导入 `authoring.registry_fs`
    - `adapters/problog/provenance.py` / `pyreason/provenance.py` 导入 `audit.evidence_graph`
  - 不成立或不再成立的例子：
    - `adapters/problog/rule_ext.py` 当前并不导入 `sdk`
    - `audit/assertions.py` 当前只导入 `adapters.souffle.tsv_v1`，不是报告里说的那种跨多层耦合例子
- 审计意见：
  - “边界主要靠人为自律”这个结论是对的。
  - 但报告列举的证据表里有几项已经过时，说明审计并非完全基于当前代码快照。

### 13. `core/annotation` 的“prototype + frozen contract”混合状态

- 结论：**成立**
- 复核结果：
  - `core/annotation/docs/README.md` 开头明确写目录状态是 `internal / prototype`
  - 同一文档后部又明确写 `Certainty V1 Contract (frozen)`
- 审计意见：
  - 报告指出“同目录里既写 prototype 又写 frozen”是个边界表述问题，这个观察是准确的。

### 14. F-CORE-4 / F-CORE-5 是否只是 docs-only 修复

- 结论：**成立**
- 复核结果：
  - `core/docs/01_architecture.md` 里 F-CORE-4 的修复是 inline 诊断注释
  - F-CORE-5 明确标为 `RESOLVED (docs-only)`
- 审计意见：
  - 报告这点是准确的。

### 15. “没有 cross-engine parity tests / 没有 provenance 全链 tests”

- 结论：**表述过头**
- 复核结果：
  - 仓库里确实存在一些 parity / provenance / evidence graph / timeline 相关测试：
    - `test_cross_coordinate_join_engine_matches_python`
    - `test_problog_semantic_annotation_l4`
    - 大量 `timeline` / `evidence_graph` / `provenance` tests
- 审计意见：
  - 若说“缺少更系统的 property-based parity / canonical invariants / end-to-end hostile mutation tests”，我同意。
  - 若说“这类测试不存在”，就不准确了。

## 对报告核心结论的修正

### 可以保留的强结论

- 作为 **通用 NeSy reasoning kernel**，这个项目的 buyer narrative 很弱，客户不会天然为 “kernel” 付费。
- AWS Automated Reasoning / AgentCore / Microsoft Agent Governance / Norm Ai 这一串趋势，确实说明“可信、可审计、可治理”的 narrative 已经不稀缺。
- 本地代码里真正最强的是 digest / provenance / evidence-tree / multi-engine substrate；最弱的是 service shell、边界治理工具、严格事务语义、可观测性与产品包装。

### 需要降级的结论

- “从底层到应用层几乎没有任何创新性”  
  应改为：**原语层面大多不是原创，但工程组合、契约整理和审计链设计有一定整合创新。**

- “发展空间几乎被挤占完毕”  
  应改为：**横向通用平台空间很拥挤；垂直合规与证据交付层仍有空间，但窗口和进入门槛都很苛刻。**

- “没有任何质量自动化护栏”  
  应改为：**有测试型 CI，但缺少 lint/type/coverage/import-boundary 等更强的工程护栏。**

- “OEM partner 第一天就退场”  
  应改为：**如果进入高标准 technical DD，这套代码会在事务语义、边界治理、静默异常、外壳复杂度上暴露显著问题。**

## 我对这份报告的最终判定

### 适合怎么用

- 适合当：
  - 红队化战略审查底稿
  - 创业路径收缩器
  - 产品定位重写的触发器

- 不适合当：
  - 投资人/客户面前的终版尽调材料
  - 可直接引用的“已证实市场事实”文档

### 一个更稳健的一句话版本

`factpy-kernel` 不是没有价值；它的问题是：**在“通用可审计推理内核”这个叙事下，外部差异化证据不够强，而在“垂直合规证据层/高可信 reasoning substrate”这个叙事下，它的内核强于外壳。**

## 关键来源

- [AWS Automated Reasoning checks GA](https://aws.amazon.com/about-aws/whats-new/2025/08/automated-reasoning-checks-amazon-bedrock-guardrails/)
- [AWS Automated Reasoning docs](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-automated-reasoning-checks.html)
- [AWS + PwC](https://aws.amazon.com/blogs/machine-learning/pwc-and-aws-build-responsible-ai-with-automated-reasoning-on-amazon-bedrock/)
- [DARPA CLARA](https://www.darpa.mil/research/programs/clara)
- [CLARA FAQ PDF](https://www.darpa.mil/sites/default/files/attachment/2026-02/program-clara-faq.pdf)
- [DORA / ESMA](https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/digital-operational-resilience-act-dora)
- [EU AI Act timeline](https://ai-act-service-desk.ec.europa.eu/en/ai-act/eu-ai-act-implementation-timeline)
- [EU AI Act Article 12](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12)
- [EU AI Act Article 99](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-99)
- [Norm Ai $48M / $87M](https://www.norm.ai/post/norm-ai-secures-48-million-to-transform-regulations-into-compliance-ai-agents)
- [AIUC $15M seed](https://fortune.com/2025/07/23/ai-agent-insurance-startup-aiuc-stealth-15-million-seed-nat-friedman/?queryly=related_article)
- [Microsoft Agent Governance Toolkit](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/)
- [AWS AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [AWS AgentCore Policy GA](https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/)
- [Semantica](https://hawksight-ai.github.io/semantica/)
- [Imandra / Goldman via SBIR abstract](https://www.sbir.gov/awards/187888)
- [OCaml success story: Imandra & Goldman Sachs](https://ocaml.org/success-stories/financial-compliance-with-automated-reasoning)
- [AUI official financing note](https://www.aui.io/resources/aui-raises-20-million-at-750-million-valuation-cap-following-breakthrough-in-neuro-symbolic-ai/)
- [Stardog customers](https://www.stardog.com/company/customers/)
- [Ontotext customers](https://www.ontotext.com/company/customers/)
- [Oracle Argus official page](https://www.oracle.com/apac/life-sciences/safety-solutions/argus-safety-case-management/)
- [Criteria2Query 3.0](https://pubmed.ncbi.nlm.nih.gov/38697494/)
- [McKinsey on explainability risk](https://www.mckinsey.com/capabilities/quantumblack/our-insights/building-ai-trust-the-key-role-of-explainability)
