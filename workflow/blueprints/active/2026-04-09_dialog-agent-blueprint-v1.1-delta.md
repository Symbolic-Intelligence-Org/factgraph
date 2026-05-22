# Blueprint Delta: 对话式知识录入 Agent v1.1

- Status: draft
- Created: 2026-04-09
- Parent: [2026-03-29_dialog-agent-blueprint-v1.md](./2026-03-29_dialog-agent-blueprint-v1.md)
- Related Modules:
  - `src/factpy_kernel/agent/` (新建，尚不存在)
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/core/store/runtime.py`
- Audit Log:
  - [2026-04-09_dialog-agent-blueprint-v1.1-delta.audit.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.audit.md)

---

## 0. 修订背景

v1 蓝图 (2026-03-29) 定义了完整的 agent 系统设计。本 delta 基于两轮深度讨论的结论，对 v1 进行以下维度的校准：

1. **与当前代码 API surface 对齐** — v1 的若干假设不符合 `runtime_v1.py` 实际暴露的接口语义
2. **执行分层重排** — 从"功能导向"改为"控制面先行、读优先于写、写优先于生成"
3. **技术栈更新** — 基于 2026-04 市场调研，替换/补充若干组件选型
4. **能力拆分与边界收紧** — 若干 v1 能力被拆为子能力，明确当前代码支持边界

**原则：本文档只记录与 v1 的差异。未提及的 v1 内容保持不变。**

---

## 1. 技术栈变更

### 1.1 替换

| v1 选型 | v1.1 替换为 | 理由 |
|---------|-----------|------|
| OpenAI SDK 直接调用 | **PydanticAI** + LiteLLM | 类型安全、25+ provider 无差别切换、Pydantic 原生（项目已依赖 `pydantic>=2`）、tool call hooks 可拦截审计 |
| DSPy 做结构化输出 | **Instructor** 做输出约束 | Instructor 直接复用现有 Pydantic model（FactDraft 等），3 行集成、6M+ 月下载、自动 retry with validation feedback；DSPy 学习曲线高，降级为 Phase 2 文档提取优化器 |
| 自建对话状态机 | **Burr (Apache Incubator)** | 显式状态定义 + 内置追踪 UI + 可持久化到 SQLite/Postgres + 可单测；与 FactPy CandidateSet 状态机设计哲学一致 |

### 1.2 新增

| 组件 | 用途 | 引入阶段 |
|------|------|---------|
| **Langfuse** (self-hosted, MIT) | LLM 调用全链路审计：tracing、prompt versioning、evaluation | Phase 1 |
| **OpenTelemetry GenAI Conventions** | 可迁移的 trace 标准，与 Langfuse 原生集成 | Phase 1 |
| **PyMuPDF** (`pymupdf4llm`) | 快速 PDF→Markdown 提取（0.12s），替代 v1 的 pdfminer/pdfplumber | Phase 2 |
| **Docling** (IBM, Apache 2.0) | 复杂文档/表格提取（97.9% 表格精度），自托管 | Phase 2 |

### 1.3 保留不变

| 组件 | 说明 |
|------|------|
| **LiteLLM** | v1 已选定，保持。self-hosted、100+ provider、OpenAI-compatible |
| **NetworkX** | 保持。文档内实体关系图、PyReason 图结构检测 |
| **DSPy** | 角色变更：不再做通用结构化输出，降级为 Phase 2 文档提取管线中的提取优化器（MIPROv2 prompt 调优） |

### 1.4 不采纳

| 框架 | 排除理由 |
|------|---------|
| LangGraph | 过度工程化（6 状态流程不需要图论）；LangSmith 锁定 |
| CrewAI | 控制粒度不足以满足审计要求；同等负载成本 2.8x |
| Claude Agent SDK | 仅 Anthropic 模型，无法满足多 provider 需求 |
| OpenAI Agents SDK | tracing/eval 绑定 OpenAI；多 provider 名不副实 |
| LangSmith | 闭源；self-host 需企业版 |

---

## 2. 架构分层变更

### 2.1 架构图更新

v1 架构图中的组件引用更新：

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Agent 层                                  │
│  PydanticAI agents · Burr 状态机 · 意图识别 · slot filling · 确认    │
│  AgentSession · DraftManager · CandidatePayloadCache                │
│  DocumentPipelineOrchestrator · EngineRouter                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ FactDraft / RuleDraft (引擎无关 IR)
                               │ ExtractionBatch / EngineRoutingHint
┌──────────────────────────────▼──────────────────────────────────────┐
│                          系统适配层                                  │
│  SchemaDiscoveryAPI · AgentScopeGuard · BatchCommitEndpoint         │
│  DraftPreviewRenderer · DocumentParser · ExtractionRefiner          │
│  EngineRoutingAdvisor · ConsistencyChecker · SchemaRegistryAdapter  │
│  KGReadTools · ExplainTools                                         │
│  [复用基础组件] LiteLLM · Instructor · Langfuse · NetworkX          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ 现有内部接口
┌──────────────────────────────▼──────────────────────────────────────┐
│                       逻辑基底（现有系统，零改动原则）                 │
│  推理引擎(problog/pyreason/souffle/native) · Ledger · AnnotationStore│
│  EvidenceGraph · CandidateSet · WriteProtocol · SchemaIR            │
│  RuntimeSession · compile_authoring_rule_v1                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 新增组件说明

**CandidatePayloadCache**（Agent 层，Phase 1）

Agent 侧的 evaluate response 持久化层。解决 `accept_runtime_derivation()` 要求完整 candidate object（非 candidate_id）的问题。

```python
class CandidatePayloadCache:
    """
    Agent-side persistence for evaluate responses.

    背景：当前 list_runtime_candidates() (runtime_v1.py:1324) 只返回
    {candidate_id, pred_id, support_kind, confidence_kind}，
    而 accept_runtime_derivation() (runtime_v1.py:1107) 要求完整 candidate object。
    如果 agent 丢失 evaluate 的原始响应（网络断线、进程重启），无法恢复到可 accept 状态。

    设计：
    - Agent 每次调用 evaluate 后，将完整 response 写入本地持久化
    - 持久化后端：SQLite（与 Burr state checkpoint 共用 DB）
    - Key: (session_id, candidate_id) → Value: 完整 candidate payload JSON
    清理语义：
    - 逻辑层：session close 时必须调用 evict_session() 清除该 session 的所有缓存条目
    - 物理层：SQLite 文件可保留用于诊断（如事后审计），也可按部署策略定期清理
    两层不冲突：逻辑 evict 释放可查询状态，物理文件保留供取证。

    未来：kernel 侧实现 candidate readback 端点后，此缓存降级为加速层。
    """
    def store(self, session_id: str, candidates: list[dict]) -> None: ...
    def lookup(self, session_id: str, candidate_id: str) -> dict | None: ...
    def lookup_by_session(self, session_id: str) -> list[dict]: ...
    def evict_session(self, session_id: str) -> int: ...
```

**KGReadTools**（系统适配层，Phase 1）

Agent 的 KG 读取工具集。v1 蓝图未将读取能力显式建模为 tool 层，v1.1 补充。

```python
class KGReadTools:
    """
    Agent 消费 KG 数据的 adapter 组合层（非直接 kernel endpoint 暴露）。
    每个方法组合一个或多个现有 runtime API，通过 Langfuse 自动追踪。

    注意：这些方法是对现有 runtime_v1 端点的 adapter 组合，
    不是独立的 kernel endpoint。底层映射：
      - query_claims  → list_runtime_claims (runtime_v1.py:257)
      - get_entity_snapshot → 组合 list_runtime_claims(pred_id=*, e_ref=entity_ref)
      - list_candidates → list_runtime_candidates (runtime_v1.py:1324)
                          仅支持 pred_id 过滤，不支持 state 过滤
      - list_rules → get_runtime_session_rules
    """
    def query_claims(self, session_id, pred_id, e_ref=None) -> list[ClaimResult]: ...
    def get_entity_snapshot(self, session_id, entity_type, identity) -> EntitySnapshot:
        """
        Adapter 组合：遍历该 entity 关联的所有 pred_id，
        聚合 list_runtime_claims 结果，构造快照。
        """
        ...
    def list_candidates(self, session_id, pred_id=None) -> list[CandidateSummary]: ...
    def list_rules(self, session_id) -> list[RuleSummary]: ...
```

**ExplainTools**（系统适配层，Phase 1）

Agent 消费 explain surface 的 tool 集。v1 中 explain 被归入可视化辅助，v1.1 将其提升为独立 tool 层。

```python
class ExplainTools:
    """
    Agent 的 explain 消费层。
    默认路径：summary → steps → tree/timeline on demand。
    """
    def get_summary(self, session_id, candidate_id) -> ExplainSummary: ...
    def get_steps(self, session_id, candidate_id) -> list[ExplainStep]: ...
    def get_tree(self, session_id, candidate_id) -> EvidenceTreeResult | None: ...
    def get_timeline(self, session_id, candidate_id) -> TimelineResult | None: ...
```

---

## 3. Explain 默认路径变更

### 3.1 变更内容

**v1 默认路径**: summary → narrative → NL

**v1.1 默认路径**: summary → steps → tree/timeline on demand

### 3.2 理由

`explain_runtime_steps()` (runtime_v1.py) 是当前最适合 agent 消费的 explain surface：
- 已将三引擎推导线性化成可读步骤
- 比 nested tree/timeline 更适合 LLM 中间推理
- `narrative` 和 `NL` 面向人类终端展示设计，不适合 agent 中间消费

### 3.3 Agent 消费链路

```
1. get_summary(candidate_id)
   → 快速判断：候选数、置信度、引擎、关键统计
   → agent 决定是否需要深入

2. get_steps(candidate_id)
   → 线性因果链：[(step_num, step_kind, description, node_ref, detail)]
   → agent 逐步验证、向用户解释
   → 用户追问时定位到具体 step

3. get_tree(candidate_id) / get_timeline(candidate_id)
   → 仅当用户追问特定分支时按需拉取
   → tree: Souffle/ProbLog/Native 场景
   → timeline: PyReason 场景
```

### 3.4 Steps 的能力边界声明

跨三引擎稳定的字段：
- `step_num` / `step_kind` / `description` / `node_ref` / `detail`

**不稳定**（引擎间语义差异）：
- `detail` 的内容深度：native steps 有 rule_ref_ids、fact confidence；PyReason steps 更偏 bound_update/convergence
- "最弱前提分析" 不能仅靠 steps，需补拉 summary（含 `condition_weights`）或 tree

**agent 的处理策略**：
- 简单解释：steps-only
- "哪个前提最薄弱"：steps + summary.condition_weights
- "完整推导链"：按需拉取 tree 或 timeline

---

## 4. 能力拆分与优先级重排

### 4.1 W2 撤回能力拆分

v1 将撤回作为统一能力（Phase 2 的 `retract_fact` 对话流程）。v1.1 拆分为两个独立能力：

**W2a: 精确撤回**（P1）
- 用户指定或 agent 查到 `asrt_id` → 展示事实全貌 → 确认 → `retract_by_asrt()`
- 当前代码完全支持：`retract_runtime_fact()` (runtime_v1.py)
- 不做下游影响评估

**W2b: 语义撤回 + 影响评估**（P2/P3）
- 用户说 "删掉张三的年龄" → agent 查找匹配 claim → 评估下游影响 → 确认 → retract
- **前置依赖（均不存在）**：
  1. `assertion → candidate` 反向索引（premise_asrt_id → [candidate_id]）
  2. 级联影响标记机制（至少 warning 级别）
- 与 Truth Maintenance (审计报告 H-07) 同属一个基础设施块
- **不在 v1.1 交付范围内**

### 4.2 W3 规则创建边界收紧

v1 将规则创建写为通用 "RuleDraft → compile_authoring_rule_v1" 翻译。v1.1 明确为 **native-first**。

**原因**：当前真正支持 session 内动态注册的是 ephemeral rules，仅对 native evaluate 路径生效（见 `02_runtime_sessions.md`）。

**能力等级定义**：

```
Level 0 (P1): 规则查询
  - Agent 读取已注册规则定义，向用户解释规则含义
  - Tool: GET /sessions/{id}/rules

Level 1 (P1): 规则校验
  - Agent 起草 Rule IR → validate + compile-preview 验证
  - 展示编译产物预览
  - Tool: POST /rules/validate, POST /rules/compile-preview
  - 全引擎均可校验，但不执行

Level 2 (P1): Native 规则执行
  - 注册 ephemeral rule → native evaluate → explain steps
  - 完整 draft → confirm → register → evaluate → accept loop
  - 限制: native engine only

Level 3 (P2+): 多引擎规则导出
  - 生成面向 Souffle/ProbLog/PyReason 的规则包
  - 导出为 package → 走 authoring pipeline
  - Agent 不直接执行，而是 "提交审批"
```

**v1 蓝图中 RuleDraft.engine_routing_hint 的影响**：
- Phase 1: 不使用 engine_routing_hint（所有规则走 native）
- Phase 2+: engine_routing_hint 决定导出目标引擎，但不决定 session 内执行引擎

### 4.3 I2/M1 前移

v1 将候选审查和 session 恢复分散在各 Phase 中。v1.1 将最小可用版本前移到 P0。

**理由**：agent 的核心 loop 是：

```
write facts → evaluate → [保持 candidate payload] → review → accept
```

如果 agent 丢失 evaluate response，loop 断裂。这不是 nice-to-have，是基础设施。

**P0 交付内容**：
- `CandidatePayloadCache`：agent 侧 evaluate response 持久化
- `AgentSession` 两种恢复模式：

  **Warm reconnect**（RuntimeSession 进程内仍存活）：
  1. 用 `runtime_session_id` 直接 rebind（GET /sessions/{id} 成功）
  2. Agent draft 恢复（Burr state checkpoint）
  3. Candidate payload 恢复（CandidatePayloadCache.lookup_by_session）

  **Cold restart**（RuntimeSession 已失效，如服务进程重启）：
  1. 用保存的 `RuntimeBootstrapSpec`（schema_ir + open 参数）重新 `open_runtime_session`
  2. 获得新 `runtime_session_id`，更新 AgentSession 绑定
  3. Agent draft 恢复（Burr state checkpoint）
  4. Candidate payload 恢复（CandidatePayloadCache — 注意：旧 session 的 candidate 不可 accept，需重新 evaluate）

**P2 后续**：
- Kernel 侧 candidate readback 端点（独立蓝图）
- `CandidatePayloadCache` 降级为加速层

### 4.4 W4 Stage 1 确认保留确定性

v1.1 明确**不采纳** LLM schema-guided 提取替代 Stage 1。

**理由**：Stage 1 的核心交付物不是 "提取结果"，而是确定性溯源底座：
`(doc_id, section_label, char_offset_start, char_offset_end, raw_text, structural_clarity)`

如果 Stage 1 用 LLM 做分段，offset 和 section boundary 不再确定性——LLM 分段行为不可复现，直接破坏审计链。

**修正后的管线**：

```
Stage 1 (确定性): PyMuPDF/Docling → 分段 + offset + structural_clarity
Stage 2 (LLM 约束): Instructor + schema constraint → entity/pred mapping
Stage 3 (人工审批): batch review UI（不可绕过）
```

Stage 2 中使用 Instructor（替代 v1 的 DSPy）做 schema-constrained 输出。DSPy 的 MIPROv2 优化器仅在提取准确率不达预期时启用，用于 prompt 调优。

---

## 5. 执行分层重排

### 5.1 v1 分期 vs v1.1 分期

v1 按功能域划分（Phase 1=事实 MVP, Phase 2=规则+路由+文档, Phase 3=高级）。

v1.1 改为按 **控制面 → 读 → 写 → 生成** 四层递进：

### 5.2 Layer 1: 控制面 MVP（对应 v1 Phase 1 前半）

**目标**：agent 的会话/状态/持久化/恢复/工具调用底盘可用。

- [ ] **AgentSession** 生命周期：创建/恢复/关闭，持有 session_id + AgentScope
- [ ] **Burr 状态机** 集成：状态定义（IDLE/INTENT/SLOT_FILLING/DRAFT_PREVIEW/COMMITTING/COMMITTED）+ 状态持久化到 SQLite
- [ ] **DraftManager**：in-memory staging + Burr state checkpoint 持久化
- [ ] **CandidatePayloadCache**：evaluate response 持久化到 SQLite
- [ ] **AgentSession 双层恢复**：RuntimeSession + DraftManager + CandidatePayloadCache
- [ ] **PydanticAI agent 骨架**：仅 tool registry + LiteLLM provider config + tracing plumbing，不发 model call
- [ ] **Langfuse 集成**：OTel trace decorator，所有 LLM 调用自动追踪
- [ ] **AgentScopeGuard**：权限约束校验（entity_type/pred_id 白名单、min_confidence）
- [ ] 基本单测覆盖

**不在 Layer 1 范围**：任何 LLM 调用逻辑、意图识别、slot filling、写入。

### 5.3 Layer 2: Read-first Agent（对应 v1 Phase 1 后半 + 新增）

**目标**：agent 能感知 schema、查询事实、消费 explain surface、执行 evaluate→review→accept loop。

- [ ] **SchemaDiscoveryAPI**：复用 v1 设计，增加骨架注入策略（高频 predicate 列表注入 system prompt，细节按需查）
- [ ] **KGReadTools**：query_facts / query_entity / list_candidates / list_rules
- [ ] **ExplainTools**：get_summary / get_steps / get_tree / get_timeline
- [ ] **PydanticAI 意图识别**：`query_schema` / `query_fact` / `evaluate` / `accept`（仅读+审查意图）
- [ ] **Evaluate → CandidatePayloadCache.store → Review → Accept** 完整 loop
- [ ] **Steps-first explain 集成**：agent 默认消费 steps，用户追问时展开 tree/timeline
- [ ] 集成测试覆盖

**不在 Layer 2 范围**：事实写入、规则创建、文档提取、引擎路由。

### 5.4 Layer 3: 最小写入（对应 v1 Phase 1 写入部分）

**目标**：agent 能将用户自然语言意图转为受约束的 FactDraft，经确认后写入 ledger。

- [ ] **PydanticAI 意图识别扩展**：`ingest_fact` / `retract_fact`
- [ ] **Slot filling**：复用 v1 设计（entity_type, pred_id, field_value, confidence, source）
- [ ] **Instructor 集成**：FactDraft 的 schema-constrained 生成（一次提取 + 信息不足时退化追问）
- [ ] **DraftPreviewRenderer.render_text**：Markdown 摘要预览
- [ ] **BatchCommitEndpoint**：单条提交 + approved_by/trace_id 写入 meta
- [ ] **W2a 精确撤回**：查找 asrt_id → 展示 → 确认 → retract_by_asrt
- [ ] 确认流程 + 审计 trail

**关键设计差异 vs v1**：
- 信息充分时一次性提取 FactDraft + confirm（不强制走完整状态机）
- 信息不足时自适应退化到多轮追问

### 5.5 Layer 4: 规则 + 文档 + 引擎路由（对应 v1 Phase 2）

**目标**：native-first 规则创建 + 文档提取管线 + 引擎路由。

**规则创建（native-first）**：
- [ ] Level 0-1：规则查询 + 规则校验（validate/compile-preview）
- [ ] Level 2：ephemeral rule → native evaluate → explain steps
- [ ] Level 3（后续）：多引擎规则导出

**文档提取**：
- [ ] 复用 v1 三阶段设计，Stage 1 改用 PyMuPDF + Docling
- [ ] Stage 2 改用 Instructor（Pydantic model 约束 LLM 输出），DSPy MIPROv2 仅做优化
- [ ] Stage 3 人工审批不变

**引擎路由**：
- [ ] 复用 v1 EngineRoutingAdvisor 设计
- [ ] 集成到 slot filling 流程

### 5.6 Layer 5: 高级特性（对应 v1 Phase 3 + 新增）

- [ ] Session-scoped dependency scan（遍历 support artifacts 提取 premise→candidate 映射）
- [ ] W2b 语义撤回 + 影响评估（依赖 dependency scan）
- [ ] SchemaDraft（复用 v1 设计）
- [ ] What-if dry-run / sandbox
- [ ] Durable lineage index（独立蓝图）
- [ ] Kernel-side candidate readback 端点（独立蓝图）

---

## 6. 开放问题更新

### 6.1 v1 开放问题的决策更新

| v1 问题 | v1.1 决策 |
|---------|----------|
| Agent 会话与 RuntimeSession 生命周期绑定方式 | **松耦合确认**：AgentSession 持有 session_id + Burr state + CandidatePayloadCache；三层独立持久化，独立恢复 |
| 对话历史是否持久化到 Ledger | **不持久化到 Ledger**。Burr state checkpoint 存对话状态；Langfuse 存 LLM 调用历史。审计粒度在 commit 时通过 meta 保证 |
| 置信度模糊语言映射表应固定还是可配置 | **先固定**，保持 v1 立场 |

### 6.2 新增开放问题

| 问题 | 当前立场 | 待决策 |
|------|---------|------|
| Burr state checkpoint 与 CandidatePayloadCache 是否共用同一 SQLite | 建议共用，减少连接管理。但需确认 Burr 的 SQLite schema 是否允许自定义表 | Layer 1 实现时确认 |
| Langfuse self-hosted 部署方式 | Docker Compose 用于开发，Kubernetes/Helm 用于生产 | 与部署架构对齐 |
| Steps 跨引擎语义差异是否需要 adapter 层标准化 | 当前不标准化（保持引擎原生 detail）；agent 通过 step_kind 分支处理 | Layer 2 实现时评估 |
| PydanticAI tool 定义是否自动从 KGReadTools/ExplainTools 方法签名生成 | 建议是——PydanticAI 原生支持从 typed function 生成 tool schema | Layer 1 实现时确认 |
| Agent-side SQLite（Burr + CandidatePayloadCache）的物理文件管理 | 建议 per-AgentSession 一个 DB file；逻辑 evict 在 session close 时强制执行，物理文件按部署策略清理 | Layer 1 设计时确认 |
| RuntimeBootstrapSpec 的持久化位置 | 保存在 Burr state（与 AgentSession 共生命周期）；包含 schema_ir digest + open_session 参数，用于 cold restart 重建 RuntimeSession | Layer 1 设计时确认 |

---

## 7. 已知约束更新

追加以下约束到 v1 的已知约束列表（v1 原有 8 条保持不变）：

**9. accept 需要完整 candidate object**：`accept_runtime_derivation()` (runtime_v1.py:1107) 要求完整 candidate payload，不接受 candidate_id。`list_runtime_candidates()` (runtime_v1.py:1324) 只返回摘要。Agent 必须自行持久化 evaluate response。

**10. Ephemeral rules 仅 native evaluate 生效**：session 内动态注册的规则仅对 native evaluate 路径生效（见 `02_runtime_sessions.md`）。ProbLog/PyReason/Souffle 规则需通过 authoring pipeline 离线注册。

**11. Steps detail 跨引擎不一致**：`explain_runtime_steps()` 的稳定字段为 step_num/step_kind/description/node_ref/detail。但 detail 内容深度引擎间有差异（native 有 rule_ref_ids、fact confidence；PyReason 偏 bound_update/convergence）。

**12. Accepted assertion meta 已有部分 lineage 信息**：`accept.py` (line 752) 写入 candidate_id/candidate_key/derived_rule_id/support_digest 到 meta。缺失的是反向边：premise_asrt_id → [candidate_id]。

**13. 文档提取 Stage 1 必须确定性**：Stage 1 的 offset/section_label 是审计链的锚点。不可用 LLM 替代分段逻辑。

---

## 8. 与产品落地审计报告的交叉引用

本 delta 的设计决策与 [产品落地审计报告](../references/working/product-readiness-audit-2026-04-09.md) 中识别的隐患的关系：

| 审计隐患 | 影响 Agent 设计 | 本 delta 的应对 |
|---------|----------------|---------------|
| H-01 零认证 API | Agent 调用 API 无认证 | 不在 agent 蓝图范围；标记为外部前置依赖 |
| H-02 SQLite 并发 | 多 agent 并发写入 ledger 可能死锁 | Layer 1 限制单 agent session；并发问题由 kernel 侧修复 |
| H-04 无限内存字典 | Agent 长运行导致 Store OOM | CandidatePayloadCache 提供 agent 侧缓存，减少对 Store 缓存的依赖 |
| H-07 撤回不级联 | W2b 语义撤回无法评估影响 | 拆分 W2a/W2b，W2b 后移到 Layer 5 |
| H-08 retract 竞态 | Agent 并发撤回可能重复 | Layer 3 的 W2a 做单线程撤回 + 确认，不触及竞态路径 |
| H-09 Souffle 无超时 | Agent 触发 evaluate 可能无限挂起 | 标记为外部前置依赖；agent 层加 LLM 调用超时，但 engine 超时需 kernel 侧修复 |

---

## 9. 决策日志摘要

| # | 决策 | 理由 | 日期 |
|---|------|------|------|
| D-01 | PydanticAI 替代 OpenAI SDK 直调 | 类型安全 + 25+ provider + 低锁定 | 2026-04-09 |
| D-02 | Burr 替代自建状态机 | 内置追踪 + 持久化 + Apache 长期维护 | 2026-04-09 |
| D-03 | Instructor 替代 DSPy 做结构化输出 | Pydantic 原生 + 3 行集成 + 成熟度高 | 2026-04-09 |
| D-04 | Langfuse + OTel 作为审计层 | MIT + self-host + 框架无关 | 2026-04-09 |
| D-05 | Steps-first explain（替代 narrative-first） | steps 已线性化三引擎，更适合 agent 消费 | 2026-04-09 |
| D-06 | Agent-side candidate payload 持久化（优先于 kernel readback） | 当前 list_candidates 只返回摘要；kernel 改造另开蓝图 | 2026-04-09 |
| D-07 | W2 拆分为 W2a/W2b | 无 assertion→candidate 反向索引 + 无级联标记 = 语义撤回不可行 | 2026-04-09 |
| D-08 | W3 native-first | ephemeral rules 仅 native evaluate 生效 | 2026-04-09 |
| D-09 | W4 Stage 1 保持确定性 | offset 是审计链锚点，LLM 分段不可复现 | 2026-04-09 |
| D-10 | 执行分层：控制面 → 读 → 写 → 生成 | 底盘先于发动机 | 2026-04-09 |
| D-11 | Session-scoped dependency scan 优先于 durable lineage index | accept meta 已有部分 lineage；反向边先按需扫描，不急持久化 | 2026-04-09 |
| D-12 | PyMuPDF + Docling 替代 pdfminer/pdfplumber | 速度 + 表格精度 + 自托管 | 2026-04-09 |
| D-13 | KGReadTools 是 adapter 组合层，不是独立 endpoint | 当前 runtime API 只有 list_claims/candidates/rules；query_entity 需组合多次调用 | 2026-04-09 |
| D-14 | list_candidates 不支持 state 过滤 | runtime inventory (line 1324) 只支持 pred_id 过滤；state 不在返回字段中 | 2026-04-09 |
| D-15 | AgentSession 恢复分 warm/cold 两条路径 | RuntimeSession 是进程内 map，进程重启后需要 RuntimeBootstrapSpec 重建 | 2026-04-09 |
| D-16 | CandidatePayloadCache 清理语义：逻辑 evict 强制、物理文件可保留 | 两层不冲突：evict 释放查询状态，文件保留供取证 | 2026-04-09 |
| D-17 | Layer 1 PydanticAI 骨架不发 model call | 与 "Layer 1 不含 LLM 调用逻辑" 完全一致；仅做 tool registry/provider config/tracing | 2026-04-09 |
