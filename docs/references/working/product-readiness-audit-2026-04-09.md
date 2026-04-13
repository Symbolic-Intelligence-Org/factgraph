# FactPy Kernel 产品落地就绪度审计报告

> **日期**: 2026-04-09
> **范围**: 架构健全性 + 功能完整性 + 生产化隐患
> **方法**: 代码逐行审计 + 市场对标分析

---

## 一、市场定位与对标

### 1.1 市场格局 (2025-2026)

知识图谱市场规模：$1.07B (2024) → $6.94B (2030), CAGR 36.6%。
可审计性和可解释性正从差异化卖点变为 table-stakes。

### 1.2 对标产品矩阵

| 维度 | FactPy Kernel | Neo4j | Stardog | RDFox | AllegroGraph | ReasoningLayer |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 演绎推理 (Datalog) | Souffle | - | OWL RL | Datalog+OWL | RDFS++ | 有 |
| 概率推理 | ProbLog | - | - | - | - | 模糊逻辑 |
| 时序推理 | PyReason | - | - | - | 基础 | 有 |
| 多引擎编排 | 统一接口 | - | - | - | 双范式 | 双范式 |
| 证据树/证明链 | 多层渲染 | - | 单引擎 | 单引擎 | Prolog 链 | 有 |
| 自然语言解释 | narrative+NL | - | - | - | NL 查询 | - |
| OWL/RDFS 本体 | - | - | OWL 2 全集 | OWL 2 RL | RDFS++ | - |
| W3C PROV 对齐 | - | - | 部分 | 部分 | 部分 | - |
| 增量推理 | - | - | - | 有 (核心卖点) | - | - |
| 分布式/水平扩展 | - | 有 | 有 | 集群 | 有 | 有 |
| 合规矩阵 | 有 | - | - | - | - | - |

### 1.3 差异化定位

**FactPy Kernel 是目前市场上唯一将演绎/概率/时序三种推理范式统一在单一 Python 运行时中、并为每个推导结果生成跨引擎证据树的可审计推理框架。**

最近似竞品：
- **RDFox** — 嵌入式+推理+可解释，但单范式 (OWL+Datalog)
- **ReasoningLayer** — 多范式+证明树，但 SaaS 闭源、LLM 导向
- **AllegroGraph** — 多范式 (Prolog+RDFS+LLM)，但 Java/Lisp 单体

---

## 二、架构健全性评估

### 2.1 已具备的核心架构层

| 架构层 | 实现状态 | 行业对标 |
|--------|---------|---------|
| Append-only 事实账本 (SQLite) | 完整 | Event Sourcing 模式 |
| 多引擎推理调度 (Souffle/ProbLog/PyReason/Native) | 完整 | 超越市场 — 无对等产品 |
| 证据树溯源 (tree + narrative + timeline + NL + steps) | 完整 | 五种渲染视角，超出单引擎解释树 |
| Schema IR + 类型系统 | 完整 | canonical type tags |
| 候选集生命周期 (generated/accepted/rejected) | 完整 | SHA256 确定性哈希 + 幂等保护 |
| REST API 服务层 (40+ 端点) | 完整 | Session/Write/Derivation/Explain/View |
| 审计查询接口 | 完整 | runs/candidates/decisions/compliance/rule_traces |
| SDK Facade | 完整 | Python SDK: batch/entity/schema |

### 2.2 架构模式映射

```
项目实现                          行业最佳实践
──────                           ────────────
Append-only Ledger           ←→  Event Sourcing (CQRS)
Multi-engine Evaluator       ←→  Embedded Engine Composition
Evidence Tree per Candidate  ←→  Lazy Proof Tree Construction
ArtifactSidecar              ←→  Named Graph Provenance
CandidateSet 状态机           ←→  Materialization Pipeline
```

**结论：底层架构健全，模式选择合理。**

### 2.3 数据模型强度

- **Claim/ClaimArg**: 参数行展开 + 标签系统
- **AnnotationRow**: 四维元数据 `(namespace, category, key, origin)`，namespace 区分引擎
- **CandidateSet**: 冻结 dataclass，candidate_id / candidate_key 双重 SHA256
- **EvidenceGraph**: `EvidenceNode + EvidenceEdge`，DFS 环检测，布局提示
- **Revokes**: 审计链式撤回

### 2.4 领先市场的能力

1. 三范式推理统一编排 — 无对等产品
2. 跨引擎证据树 — 学术和商业均无先例
3. 概率推理一等公民 — 企业 KG 平台全部缺失
4. 五种解释渲染 — 超出 Stardog/RDFox 单一解释树
5. 合规矩阵 (compliance_matrix) — 市场产品均无
6. 纯 Python 生态 — AI/ML 集成友好

---

## 三、功能完整性差距

### 3.1 高优先级差距

| 差距 | 影响 | 对标 | 建议路径 |
|------|------|------|---------|
| W3C PROV-DM 导出 | 审计合规互通 | W3C PROV (60+ 实现) | EvidenceGraph → PROV Entity-Activity-Agent, `prov` 库 |
| 并发多用户访问 | 生产部署 | Neo4j/Stardog/RDFox | 连接池 + PostgreSQL 后端 |
| 增量推理 | 流式/实时场景 | RDFox 核心卖点 | Native evaluator delta-based |

### 3.2 中优先级差距

| 差距 | 建议路径 |
|------|---------|
| OWL/RDFS 本体互操作 | Layer A 类型层次 domain preset |
| 图算法/ML 集成 | NetworkX 复用 + adapter 接口 |
| 持久化存储选项 | PostgreSQL/DuckDB Ledger adapter |
| 可视化/Dashboard | Grafana 集成或自建前端 |

### 3.3 低优先级差距

- GraphQL API 层
- SPARQL 端点
- 分布式部署方案
- LLM/Agent 集成表面

---

## 四、生产化隐患（代码级审计）

### 4.1 P0 — 上线门槛

#### H-01: 零认证 API

- **位置**: `service/app_v1.py` 全部 40+ 路由
- **风险**: 任何网络可达者可读写任意 session、执行推导、导出数据
- **影响**: 审计场景下认证缺失本身就是不合格项

#### H-02: SQLite 单连接 + check_same_thread=False

- **位置**: `core/store/ledger.py:266-277`
- **代码**: `sqlite3.connect(path, check_same_thread=False, isolation_level=None)`
- **风险**: 多线程并发写入 → 死锁/库损坏；多 worker 部署不可用（session 跨 worker 不可达）
- **影响**: 无法使用标准 ASGI 多 worker 部署

#### H-03: .env 密钥泄露

- **位置**: `/hnsm-backend/.env`
- **内容**: OPENAI_API_KEY, NEO4J_PASSWORD 明文存储
- **影响**: 若仓库推送过远端则密钥已泄露

### 4.2 P1 — 运行稳定性

#### H-04: 七个无上限内存字典

- **位置**: `core/store/runtime.py:82-88`
- **缓存**: `_support_artifacts`, `_provenance_envelopes`, `_candidate_support_index`, `_candidate_support_kind_index`, `_candidate_confidence_kind_index`, `_candidate_pred_index`, `_rule_trace_artifacts`
- **机制**: ArtifactSidecar 写盘后仍缓存到内存，无 LRU/TTL 驱逐
- **估算**: 1000 次推导 × 50KB/证明树 = 50MB 仅 `_support_artifacts` 一项

#### H-05: Ledger 全量内存加载

- **位置**: `core/store/ledger.py:696-725`, `_load_from_db()` 方法
- **索引**: 15+ 个 dict/list 全量加载（claims, claim_args, annotations, meta_rows × 多维索引）
- **估算**: 100 万条 claim → 数百 MB 常驻内存

#### H-06: ArtifactSidecar 磁盘无限增长

- **位置**: `core/store/_artifact_sidecar.py`
- **问题**: `gc_rule_trace()` 仅清理 rule_trace，support 文件无 GC；GC 需手动调用
- **影响**: 运行数月后磁盘写满

#### H-07: 撤回不级联 — 无 Truth Maintenance

- **位置**: `core/evidence/write_protocol.py:169-207`
- **行为**: `retract_by_asrt()` 仅记录 Revokes 关系，不检查/标记依赖的派生事实
- **影响**: 被撤回前提的推导结论在 ledger 中成孤儿，审计时无法自证一致性
- **注意**: 证据树查询时检查 revocation，但 ledger 层面无保障

#### H-08: retract_by_asrt() 竞态条件

- **位置**: `core/evidence/write_protocol.py:181`
- **代码**: `find_revoker()` 在 `BEGIN IMMEDIATE` 事务外执行
- **风险**: 两个线程同时判断"未撤回" → 重复撤回记录

### 4.3 P2 — 规模化障碍

#### H-09: Souffle 子进程无超时

- **位置**: `adapters/souffle/runner.py:86`
- **代码**: `subprocess.run(...)` 无 timeout 参数 + `capture_output=True` 全缓存
- **对比**: ProbLog 有 timeout=30s

#### H-10: PyReason 全局锁

- **位置**: `adapters/pyreason/runner.py:25`
- **代码**: `_PYREASON_LOCK = threading.Lock()`
- **影响**: 所有 PyReason 推理串行执行；`pr.reason()` 无超时

#### H-11: Schema 无在线演进

- **位置**: `service/runtime_v1.py:1394`
- **行为**: Schema digest 精确匹配，任何字段变更 → session 不可用
- **影响**: 无法向运行中 session 添加可选字段

#### H-12: 证据树无快照隔离

- **位置**: `core/store/_candidate_evidence_tree.py`
- **行为**: 递归构建过程中回调读取 ledger，无原子快照
- **影响**: 并发修改下树的不同分支反映不同时刻状态

#### H-13: 错误响应泄露内部信息

- **位置**: `service/_common.py`
- **代码**: `details = {"message": str(exc)}` — 完整异常含路径/SQL/schema
- **影响**: 向客户端暴露服务器内部状态

#### H-14: 依赖版本过松 + 引擎二进制无校验

- **位置**: `pyproject.toml`, `adapters/souffle/runner.py:21-32`
- **问题**: `pydantic>=2` 无上界；Souffle 通过 `shutil.which()` 查找，无签名验证

---

## 五、隐患全景图

```
严重度     基础设施              数据完整性             安全性
────────  ──────────────────   ──────────────────   ────────────────
P0 致命   H-02 SQLite 并发      —                    H-01 零认证 API
          多 worker 不可用                            H-03 .env 泄露

P1 高危   H-04 无限内存字典     H-07 撤回不级联       H-13 错误泄露
          H-05 Ledger 全量加载  H-08 retract 竞态
          H-06 磁盘无 GC

P2 中危   H-09 Souffle 无超时   H-12 证据树无快照     H-14 二进制无校验
          H-10 PyReason 全局锁  H-11 Schema 无迁移    依赖版本过松
```

---

## 六、建议修复路线

### Phase 1: 上线门槛 (1-2 周)

1. API 认证层 — JWT/API Key + session RBAC
2. SQLite 连接安全 — 连接池 or aiosqlite
3. 密钥轮换 + .gitignore
4. 错误响应脱敏

### Phase 2: 稳定运行 (2-4 周)

5. Store 缓存 LRU 驱逐
6. Ledger 延迟加载 / 按需查询
7. ArtifactSidecar 自动 GC (support + rule_trace)
8. Souffle + PyReason 超时机制
9. retract_by_asrt() 竞态修复

### Phase 3: 规模化 (1-2 月)

10. Schema 版本兼容 / 在线迁移
11. Truth Maintenance 撤回级联标记
12. 证据树快照隔离
13. 多 worker / 多进程部署
14. 负载测试 + 并发测试

---

## 七、总结

**架构判定**: 核心推理管线（事实录入 → 多引擎推导 → 候选集管理 → 证据树溯源 → 审计查询）逻辑正确，架构模式合理，差异化定位清晰。

**落地判定**: 隐患集中在生产化基础设施层（并发、内存、认证、生命周期管理），不涉及架构重设计。均为已知模式的工程问题。

**市场判定**: 三范式推理编排 + 跨引擎证据树是独创能力，在合规/审计驱动的知识图谱场景有明确市场空白。
