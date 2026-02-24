# Core 开发进度与路线图（factpy_kernel）

- 范围：`src/factpy_kernel/core`
- 最后更新：2026-02-24
- 当前状态基线：`459 unittest OK`

## 1. 当前状态摘要（供快速判断）

### 已完成的关键工程治理

- `core` 与 `adapters` 已分层，`core` 不再静态依赖 `adapters`
- `Store` 完成第一阶段拆分（`api/_evaluate/_accept/_builders/_queries`）
- `Store.__init__` 强制 `SchemaIR` 校验（错误前置）
- `Ledger` 完成内存索引优化（claims/meta/claim_args/revokes）
- `policy/view` 热点路径已接入 `Ledger.find_claim_args(...)`
- 全量 `unittest` 通过（459 tests）
- record accept 语义闭环已收口（staging marker + role digest + projector 不可见性 gating + 结构化 diagnostics）
- `record_staging` 共享判定模块已落地（`accept` / `projector` 共用冲突语义）
- `project_view_facts_with_audit(...)` 已落地（默认 `project_view_facts(...)` 返回形状不变）

### 当前主要风险（简要）

1. `Ledger` 仍为纯内存实现（容量/持久化限制）
2. adapter 导出路径仍有部分全量扫描，可能成为下一性能热点
3. 性能基准尚未形成团队/CI 的回归门槛

### 当前性能基准（参考）

基准脚本：`tools/benchmarks/bench_core_ledger_paths.py`

- 规模：`rows=3000`, `claims=12000`, `meta_rows=48000`
- `compute_chosen_for_predicate(country)`: `~11ms`
- `project_view_facts(record)`: `~47ms`
- `resolve_mapping_predicate(er:canon_of)`: `~23ms`

## 2. 已完成里程碑（按主题）

### M1. 目录分层与边界治理（完成）

**目标**
- 建立 `core`（语义）与 `adapters`（引擎/导出适配）的工程边界

**结果**
- 目录结构完成重组
- `Souffle` 适配代码迁入 `adapters/souffle`
- 顶层兼容 shim 已移除（保留纯净目录）

**完成标准（已满足）**
- 新路径导入通过
- 全量测试通过

### M2. `Store` 边界纯化（完成）

**目标**
- 去除 `core.store.api` 对 adapter 的静态依赖

**结果**
- 引入 `register_engine_evaluator(...)`
- engine 逻辑下沉到 `adapters/souffle/engine_eval.py`
- adapter import 时自动注册 evaluator

**完成标准（已满足）**
- `core` 无静态 adapter import
- engine 模式未注册时报错明确
- 导入 adapter 后 engine 调用恢复可用

### M3. `Store` 模块拆分（阶段 1，完成）

**目标**
- 降低 `Store` 单文件复杂度，保持外部 API 不变

**结果**
- `store/_evaluate.py`：评估主流程
- `store/_accept.py`：接受与 digest 逻辑
- `store/_builders.py`：候选构建/record spec/type coercion
- `store/_queries.py`：explain/conflicts/mapping
- `store/api.py` 收敛为门面 + 注册点 + 少量兼容入口

**完成标准（已满足）**
- 全量测试通过
- adapter 不再依赖 `Store` 私有方法名

### M4. `Ledger` 内存索引优化（完成）

**目标**
- 降低 `find_claims/find_meta/has_active_revocation` 等热点查询开销

**结果**
- 新增 claims/meta/claim_args/revokes 索引
- 新增 `find_claim_args(...)`
- `policy/view` 热点调用改走索引
- 增加 `rebuild_indexes()` 支持直接私有列表修改后的索引重建

**完成标准（已满足）**
- 全量测试通过（459）
- 新增索引语义测试通过

### M5. record accept 语义收口（完成，P0/P0.5）

**目标**
- 收口 record 物化的部分写入可见性、冲突隐性 nondeterminism 与可诊断性缺口

**结果**
- record accept 引入 staging marker 与 role-level digest
- `accept` / `projector` 共用 `record_staging` 冲突判定（conflict 封闭）
- `projector` 对未 committed / conflict / aborted record 整组隐藏
- `projector` 增加 `roles_count_expected` 低成本完整性校验（count mismatch 隐藏）
- `AcceptResult.diagnostics` 增强（冲突后果对子调用方可见）

**完成标准（已满足）**
- record partial write 重试恢复回归通过
- committed+aborted / committed+inflight mismatch 冲突回归通过
- 全量测试通过（459）

### M6. projector 审计统计（完成，P1）

**目标**
- 在不改变默认 `project_view_facts(...)` 返回形状的前提下，为迁移/观测提供 record 可见性相关统计

**结果**
- 新增 `project_view_facts_with_audit(...) -> (facts, ProjectorAudit)`
- 单次扫描、单份索引、双出口（默认路径与 audit 路径共享实现）
- 审计统计覆盖：
  - legacy record（按 record 组 / exists 单位）
  - marker conflict（按 reason 聚合）
  - committed hidden count mismatch

**完成标准（已满足）**
- 新增 `test_view_projector_audit_v1.py`
- 默认 API 输出与历史行为一致（回归覆盖）

## 3. 当前架构决策（必须保持一致）

### D1. `core` 不静态 import `adapters`
- 通过注册机制注入 engine evaluator
- 原因：保证 `core` 可独立测试/评审/演进

### D2. `Ledger` 列表是真相，索引是缓存
- 索引只在 `append_*` 时维护
- `rebuild_indexes()` 用于测试/调试纠偏
- 原因：避免双真相问题

### D3. `Store` 对外 API 稳定优先于内部结构纯度
- 外部调用方继续使用 `Store`
- 内部能力通过 `_*.py` 演进
- 原因：持续重构时降低连锁修改成本

## 4. 下一步开发/优化目标（按优先级）

### P1. 建立性能回归基线（短期）

**动机**
- 目前已完成多轮结构和索引优化，但没有固定回归门槛

**建议动作**
- 固定 benchmark 场景（如 `3k`、`10k` 两档）
- 记录基线结果到文档或 CI artifact
- 至少在性能相关 PR/重构前后执行一次

**验收标准**
- 有明确命令与记录格式
- 团队成员可重复得到同类结果（允许波动）

### P1. 定位 adapter 导出路径热点（claims/claim_args）

**动机**
- `adapters/souffle/package.py` 仍有多处全量遍历，可能成为大导出瓶颈

**建议动作**
- 用 profiler 或细粒度计时定位 `_build_fact_rows`、audit 相关聚合热点
- 优先利用 `Ledger.find_meta/find_claims/find_claim_args`，避免重复全量过滤

**验收标准**
- 导出相关测试通过
- 在固定场景下导出耗时明显下降（给出对比）

### P1. 观测与迁移策略：legacy record 可见性（audit/allow/deny）

**动机**
- 当前 legacy record（无 `record_digest`）默认兼容可见；需要先量化规模与异常分布，再决定是否收紧策略

**建议动作**
- 在 `projector` 审计统计基础上补充团队级观测（日志/导出/看板）
- 先使用 `audit` 统计评估迁移成本，再考虑显式 `legacy_record_visibility` 策略参数

**验收标准**
- 能看到 legacy 数量、marker conflict 数量、count mismatch 隐藏数量的稳定统计
- 不改变默认 `project_view_facts(...)` 行为

### P2. 为 `Ledger` 索引路径补更系统的语义测试

**动机**
- 目前已有基础覆盖，但组合过滤和顺序语义仍值得扩大样本

**建议动作**
- 增加 `find_meta` 多组合过滤顺序测试
- 增加 `find_claim_args` 与 property 回退语义一致性测试
- 增加 `rebuild_indexes()` 对 claims/revokes 的恢复测试

**验收标准**
- 测试能覆盖未来索引改动的常见回归类型

### P2. 逐步清理历史兼容入口（如 `evaluate_dummy`）

**动机**
- 减少 API 面与测试 warning

**建议动作**
- 先定位真实调用方
- 更新测试/调用方后删除

**验收标准**
- 无 deprecation warning
- 全量测试通过

### P3. 探索存储后端抽象（中期）

**动机**
- 当前 `Ledger` 内存实现难以覆盖更大规模或持久化场景

**建议动作（前置设计阶段）**
- 抽象 `Ledger` 所需最小查询接口集合
- 保持 append-only 与 query 语义一致

**验收标准**
- 有设计文档/接口草案
- 不急于实现持久化后端

## 5. 短期执行计划（建议 1~2 周）

### S1. 性能回归规范化
- 任务：为 benchmark 脚本约定默认规模与记录模板
- 文件：`tools/benchmarks/bench_core_ledger_paths.py`、本文件
- 验证：运行两档规模并记录输出

### S2. adapter 导出热点 profiling
- 任务：给 `adapters/souffle/package.py` 核心路径加临时计时或使用 profiler
- 验证：提交前移除临时代码或转为受控 debug 开关

### S3. 索引测试补强
- 任务：扩充 `test_ledger_indexes_v1.py`
- 验证：全量 `unittest` 通过

## 6. 中期规划（建议 1~2 月）

- 评估 `Ledger` 抽象接口，为持久化/快照后端做准备（设计优先）
- 形成性能回归门槛（CI 或团队固定流程）
- 继续清理 `Store` 历史兼容入口，降低门面复杂度
- 在新增语义能力时建立更严格的 core vs adapter parity 策略

## 7. 非目标（当前阶段明确不做）

- 不修改协议版本（`idref_v1` / `tup_v1` / `export_v1`）
- 不重写 `Ledger` 为数据库后端（本阶段只做内存优化）
- 不大幅改动 `Store` 对外方法签名
- 不把 adapter 逻辑重新拉回 `core`

## 8. 开发与验收清单（建议每次改 core 后执行）

### 必跑检查

```bash
python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'
```

### 性能相关改动建议附带

```bash
python tools/benchmarks/bench_core_ledger_paths.py --rows 3000 --rounds 3
```

### 文档更新规则

发生以下情况时，至少更新本文件与 `02_quality_assessment.md`：

- `Store` 结构再次拆分/合并
- `Ledger` 索引策略变更
- record 可见性 gating / staging 冲突语义变更
- projector 审计统计 contract 或统计口径变更
- 测试基线数量/状态变化
- benchmark 基线变化明显

## 9. 风险与回滚策略（针对当前改造）

- 如果 `Ledger` 索引导致行为异常：
  - 优先通过 `test_ledger_indexes_v1.py` 复现
  - 检查是否存在直接修改私有列表未调用 `rebuild_indexes()`
  - 必要时回退到线性扫描实现（保留 API 不变，回滚成本低）
- 如果 `Store` 重构导致行为异常：
  - 先确认 `Store` 门面签名是否被改变
  - 再检查 `_evaluate/_accept/_builders/_queries` 是否引入语义漂移

---

本文档的目标不是替代 issue tracker，而是提供 **当前 core 状态与下一步开发方向的稳定快照**。所有任务在执行前，应先确认是否仍符合本文档中的边界与不变量。
