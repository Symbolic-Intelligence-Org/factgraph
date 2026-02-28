# Core 质量评估与模块评分（factpy_kernel）

- 评估范围：`src/factpy_kernel/core`
- 最后更新：2026-02-28
- 评估基线：`Store` 公共入口已收口到 `runtime/evaluation/queries/builders`，`Ledger` 已完成 SQLite write-through cache 持久化，record accept staging 语义收口，projector audit API 已落地
- 验证状态：`python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'` -> `509 tests OK`

## 1. 评估方法与评分维度

本文档只评估 **核心语义层（core）**，不包含 `adapters/sdk/authoring/audit` 的产品体验和部署复杂度。

评分维度（每项 10 分）：

- 架构边界清晰度
- 语义完整性（核心链路是否闭环）
- 代码可维护性（职责拆分、可读性、变更成本）
- 正确性与防御式校验
- 可测试性与回归保障
- 可扩展性（未来新增语义/能力）
- 性能（当前实现）

## 2. 总体评分（core）

| 维度 | 评分 | 说明 |
|---|---:|---|
| 架构边界清晰度 | 9.1 | `core` 与 `adapters` 已通过注册机制解耦；`Store` 公共入口与兼容 shim 边界更清楚 |
| 语义完整性 | 8.8 | 协议/Schema/写入/policy/view/rules/derivation/mapping 闭环完整，持久化恢复已打通 |
| 代码可维护性 | 8.9 | `Store` 已收口到 `runtime/evaluation/queries/builders`；`api.py` 仅保留兼容 shim |
| 正确性与防御式校验 | 9.3 | `SchemaIR` / 写协议 / where 校验较严格；record staging 与持久化恢复路径均有回归覆盖 |
| 可测试性与回归保障 | 9.4 | 全量 `unittest` 509 通过；新增持久化、服务层、模块收口回归 |
| 可扩展性 | 8.0 | 协议与模块分层良好，但 where Python/adapter 双实现与单进程 cache 模型仍需长期约束 |
| 性能（当前实现） | 8.0 | `Ledger` 读路径已恢复到原始基线量级，10k benchmark 基本持平；adapter 导出路径仍有优化空间 |
| **综合（主观加权）** | **8.9** | 在保持语义稳定的前提下，已具备持久化、恢复、审计与继续演进的工程基础 |

**结论**：`core` 已达到“可持久化、可恢复、可独立评审、可持续重构”的状态。当前主要工作重心已从“结构清理”转移到“性能深化、兼容清理与更高层接口整合”。

## 3. 模块级分析与评分

> 评分口径：在 core 范围内按当前代码形态评估，不包含 adapter/authoring/sdk 的成熟度。

### 3.1 `protocol`（`protocol/tup_v1.py`, `protocol/idref_v1.py`, `protocol/digests.py`）— 9.0/10

**职责**
- 定义 typed tuple 编码、idref 编码、digest 规则

**优点**
- 语义稳定、职责清晰、对上层完全基础设施化
- 与 `SchemaIR` / `derivation` / `write_protocol` 对接自然

**风险/不足**
- 协议一旦扩展（新 tag、新编码规则）需要非常谨慎处理兼容性

**建议**
- 维持“小而稳”，新增协议能力时明确版本边界

### 3.2 `schema`（`schema/schema_ir.py`）— 8.9/10

**职责**
- `SchemaIR` 校验、canonicalize、digest

**优点**
- 强校验风格一致，错误前置
- `Store.__init__` 已接入 `ensure_schema_ir(...)`，减少运行期延迟报错

**风险/不足**
- 某些高阶语义（例如部分 mapping 配置组合）仍可能更多在运行期暴露

**建议**
- 增加更细的静态校验（尤其 mapping 配置组合）

### 3.3 `store.ledger`（`store/ledger.py`）— 8.8/10

**职责**
- append-only SQLite 账本、幂等写入与读缓存查询接口

**优点**
- 数据模型直接、可审计性强
- SQLite 表负责持久化真相，内存索引负责热路径读取
- 已具备 `append_assertion(...)` / `append_revocation(...)`、`ingest_keys`、`ledger_meta`
- 测试侧已有 `_force_replace_meta_rows(...)` 明确替代旧的私有列表写回模式

**风险/不足**
- 当前文件型 `Ledger` 假设单进程 write-through cache
- adapter 导出路径尚未完全利用所有索引能力

**建议**
- 保持“SQLite 为真相、内存索引为缓存”的设计
- 如需多进程共享，先抽象刷新/失效语义

### 3.4 `store` 公共入口（`store/runtime.py`, `store/evaluation.py`, `store/builders.py`, `store/queries.py`, `store/_accept.py`, `store/api.py`）— 8.9/10

**职责**
- 对外提供 `Store` API，内部协调 core 各模块

**优点**
- 公共入口已收口，认知负担比旧的 `_*.py` 直连路径更低
- `Store` API 保持稳定，内部重构成本显著下降
- `core` 不静态依赖 adapter（通过 `register_engine_evaluator`）

**风险/不足**
- `api.py` 仍有兼容历史包袱
- `_accept.py` 还保留旧路径，原因是现有测试 monkeypatch 契约

**建议**
- 后续进一步压缩 compat surface
- 视需要补充更多模块级单测（不是只靠全量回归）

### 3.5 `evidence.write_protocol` — 8.9/10

**职责**
- append-only 写协议：写入、撤销、替换、幂等 ingest_key

**优点**
- 语义清晰，错误处理明确
- 已切到原子写入入口，事务边界在 `Ledger` 内部
- 幂等与撤销语义设计扎实

**风险/不足**
- 批量写入仍偏 MVP

**建议**
- 若未来增强批量写入，先定义事务失败策略与验收标准

### 3.6 `policy`（`active/chosen/policy_ir`）— 8.2/10

**职责**
- active/chosen 决策与 policy IR 生成（core 部分）

**优点**
- `chosen` tie-break 确定性强（`ingested_at + asrt_id`）
- 逻辑与 `view.projector` 协作自然

**风险/不足**
- `multi/temporal` chosen 路径仍有 MVP 约束（全部 active 视为 chosen）

**建议**
- 若要增强 temporal 语义，先定义清晰规则再修改 policy/view 一致性

### 3.7 `view`（`view/projector.py`）— 8.9/10

**职责**
- 从账本投影业务视图事实

**优点**
- `functional/multi/temporal(record/current)` 处理清晰
- 继续走 `Ledger` 热路径索引，性能已恢复到原始基线量级
- record 可见性 gating 与 `record_staging` 冲突判定一致
- 已提供 `project_view_facts_with_audit(...)`，支持 legacy/conflict/count-mismatch 统计且不改变默认 API 形状

**风险/不足**
- 审计统计目前以返回结构为主，团队级观测/导出链路仍需补齐

**建议**
- 保持语义优先；性能优化继续围绕 adapter 导出路径与调用次数做

### 3.8 `rules`（`where_eval.py`, `rule_ir.py`）— 8.3/10

**职责**
- where 子集 Python 解释执行、RuleSpec/RuleRegistry/RuleRef 执行

**优点**
- 子集明确、校验严格、错误提示质量较好
- RuleRef 循环防护与展开逻辑完整

**风险/不足**
- 与 adapter 中的 `where_compile` 仍存在双实现同步成本

**建议**
- 将 Python 语义视为基准，新增 where 能力时先落 core 再落 adapter

### 3.9 `derivation`（`candidates.py`, `accept.py`）— 9.0/10

**职责**
- 候选集合与接受物化

**优点**
- `CandidateSet` 结构清晰、幂等字段完备
- `accept_candidate_set` 已打通 record/fact 两类路径
- record accept 已引入 staging marker + role digest + 冲突封闭 + 结构化 diagnostics
- 与 `projector` 共用 `record_staging` 判定，降低跨层语义漂移风险

**风险/不足**
- 复杂错误分类仍有部分依赖 diagnostics code/message 约定

**建议**
- 未来如增加自动化审计/诊断，可逐步增强结构化错误类型

### 3.10 `mapping`（`mapping/canon.py`）— 8.4/10

**职责**
- mapping 谓词冲突解析与 tie-break

**优点**
- 结构化结果（candidates/decisions/conflicts）对审计友好
- 与 `Store.resolve_mapping` 对接边界清晰

**风险/不足**
- 性能仍取决于 `Ledger` 查询模式与元数据访问

**建议**
- 在大规模场景优先 benchmark + profiler 后定点优化

## 4. 已完成优化（本轮及近期）

### 4.1 架构与边界优化
- `core` 与 `adapters` 解耦：`Store.evaluate(mode='engine')` 通过注册机制委托，不再静态 import adapter
- `Store.__init__` 强制 `SchemaIR` 校验，错误前置
- `Store` 公共入口收口为：`runtime/evaluation/queries/builders`

### 4.2 持久化与数据访问优化
- `Ledger` 从纯内存实现迁移为 SQLite write-through cache
- 新增 `append_assertion(...)` / `append_revocation(...)`
- 新增 `ingest_keys` 独立表与 lazy backfill 路径
- 新增 `ledger_meta` 与 `schema_digest` 绑定恢复校验
- `policy/view` 热点继续走内存索引

### 4.3 测试与护栏
- 新增 `test_core_store_boundary_v1.py`：core 边界/engine 注册行为
- 新增 `test_ledger_indexes_v1.py`：Ledger 原子入口、索引与幂等语义回归
- 新增/增强 `test_derivation_accept_v1.py`：record partial recovery / conflict 封闭 / staging 可见性
- 新增 `test_view_projector_audit_v1.py`：projector audit 统计口径与默认 API 不变性
- 新增 `test_core_store_grouped_modules_v1.py`：`Store` 收口公共入口回归
- 全量 `unittest`：`509 tests OK`

## 5. 当前主要技术债（按优先级）

### P1：性能优化仍未形成 CI 基线门槛

- **影响**：后续重构可能无意回退性能
- **建议**：使用 `tools/benchmarks/bench_core_ledger_paths.py` 固定规模（例如 3k/10k）记录基线
- **验收标准**：至少形成团队可执行的 benchmark 运行规范（文档或 CI job）

### P1：adapter 导出路径仍有若干全量遍历（claims/claim_args）

- **影响**：大导出包生成时吞吐受限
- **建议**：针对 `adapters/souffle/package.py` 热点做 profiler 驱动优化，不盲目改写
- **验收标准**：导出相关测试不变，benchmark/实际导出耗时下降

### P2：文件型 `Ledger` 仍是单进程 write-through cache 模型

- **影响**：多进程共享时没有缓存刷新/失效保证
- **建议**：在需要多进程前，先设计最小刷新/一致性抽象
- **验收标准**：形成清晰的接口草案，而不是直接堆补丁

### P2：where Python/adapter 编译器双实现长期同步成本

- **影响**：新增 where 语义时易发生漂移
- **建议**：把 `core.rules.where_eval` 明确为语义基准，新增 parity 测试为强制项

### P2：projector 审计统计的团队级观测链路尚未收口

- **影响**：`ProjectorAudit` 能返回统计，但线上/批处理侧尚未统一消费或沉淀成看板/日志规范
- **建议**：先建立 audit 统计的消费入口（日志或定期导出），再基于指标趋势决定何时从 `legacy_record_visibility=allow` 迁移到 `audit/deny`
- **验收标准**：可稳定观察 legacy/conflict/count-mismatch 指标趋势

### P3：`evaluate_dummy` 与 `store.api` 兼容入口仍存在

- **影响**：API 表面略显杂糅；兼容成本尚未归零
- **建议**：在明确迁移窗口后移除，并更新测试与调用方

## 6. 测试与质量证据（当前）

- 全量测试：`509 tests OK`
- 边界护栏：`test_core_store_boundary_v1.py`
- 索引/持久化护栏：`test_ledger_indexes_v1.py`
- record accept 语义护栏：`test_derivation_accept_v1.py`
- projector 审计护栏：`test_view_projector_audit_v1.py`
- 分组模块护栏：`test_core_store_grouped_modules_v1.py`
- 基准脚本：`tools/benchmarks/bench_core_ledger_paths.py`

当前（`rows=3000`, `rounds=3`）基准值示例：

- `compute_chosen_for_predicate(country)`: `~12ms`
- `project_view_facts(record)`: `~74ms`
- `resolve_mapping_predicate(er:canon_of)`: `~28ms`

> 说明：该基准用于相对回归比较，不是生产 SLA 指标。

## 7. 何时需要更新本评估文档

以下任一变化后应重评（至少更新分数说明与技术债部分）：

- `Store` 再次大规模拆分/合并
- `Ledger` 持久化或缓存策略变更
- 新增 `type_domain` / `cardinality` / where 操作符
- `core` 与 `adapter` 边界策略变化
- 全量测试基线或 benchmark 基线显著变化
