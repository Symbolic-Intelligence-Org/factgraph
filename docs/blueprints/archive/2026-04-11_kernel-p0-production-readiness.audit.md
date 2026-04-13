# Audit Log: Kernel P0 — Production Readiness

## 2026-04-11 — 初始设计

### 设计依据

基于 [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md) §4.1 识别的三条 P0 隐患：
- H-01 零认证 API
- H-02 SQLite 单连接 + `check_same_thread=False`
- H-03 `.env` 密钥暴露

用户指导：开独立 kernel 线，与 agent 主线并行，不混合。

### 审计报告对应的原始现状

**H-01** (audit §4.1):
> service/app_v1.py 全部 40+ 路由无认证中间件；任何网络可达者可读写任意 session、执行推导、导出数据

**H-02** (audit §4.1, 引 ledger.py:266-277):
> sqlite3.connect(path, check_same_thread=False, isolation_level=None)
> 多线程并发 → 死锁 / 库损坏；多 worker 部署不可用

**H-03** (audit §4.1):
> /hnsm-backend/.env 明文存储 OPENAI_API_KEY / NEO4J_PASSWORD
> 若仓库曾 push 则已泄露

### 2026-04-11 的复核发现

**H-03 的好消息**：
- `.env` 已在 `.gitignore` 第 22 行
- `git log --all --full-history -- .env` 返回空 → **从未提交到 git 历史**
- 所以"密钥泄露到远端"的风险实际上**没有发生**
- 剩余风险：本地磁盘明文 + 轮换流程缺失

这让 H-03 的严重度从"已泄露需要紧急处理"降级为"合规规范化工作"。但仍保留为 P0，因为：
1. 没有密钥管理规范 = 后续再次出现同类问题的概率高
2. 本地磁盘明文是真实的攻击面
3. 审计报告把它列为 P0

### 冻结决策

| # | 决策 | 理由 |
|---|------|------|
| KP0-01 | 只处理 P0（H-01/H-02/H-03），不含 P1/P2 | 上线硬门槛；P1/P2 独立蓝图 |
| KP0-02 | 不改 agent 侧业务逻辑；仅为 `HttpRuntimeAPI` 引入最小的 API key header 注入兼容点（可选 `api_key` / `api_key_header` 参数，默认 None） | Agent 主线的业务语义不变；但 HTTP adapter 必须能在 kernel 加认证后继续工作。详见 KP0-10 |
| KP0-03 | 不改 runtime_v1 的业务语义 | 只加认证层、修并发、密钥管理；DTO/response 形状不变 |
| KP0-04 | 最小可用方案，不引入 ORM / 框架迁移 | 降低改动面；保留后续深度改造空间 |
| KP0-05 | H-01 采用 FastAPI Depends + API Key Header | JWT/OAuth2 过重；API Key 是第一个认证层，可后续升级 |
| KP0-06 | 认证通过 2 个环境变量配置（`FACTPY_KERNEL_API_KEYS` + `FACTPY_KERNEL_AUTH_DISABLED`）| 显式 disable flag 避免"没配 key 就裸奔"的风险 |
| KP0-07 | H-02 采用 thread-local connection + RLock，保留 SQLite | aiosqlite/PostgreSQL 迁移是独立蓝图；thread-local 是单进程最小可用方案 |
| KP0-08 | `:memory:` 模式保留单线程语义 | memory db 本就不能跨连接共享；强制单线程 + 显式 warning |
| KP0-09 | H-03 采用密钥轮换 + .env.example + 文档化 | 不引入 secret manager（独立蓝图）；最小化动代码 |
| KP0-14 | public read API 与 writer 共享同一把 `RLock` | 仅靠 post-commit hooks 仍不足以阻止 reader 在 COMMIT 与 hook 之间看到 DB/index 不一致；public reads 必须串行化以满足一致性验收 |

## 2026-04-11 — 实现前收口修订 (3 处)

### 修订来源

用户 code review 发现 2 处 P1 + 1 处 P2 合同漏洞。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| KP0-10 | **冻结** C1 必须给 `HttpRuntimeAPI` 追加最小的 API key header 注入兼容点（可选 `api_key` / `api_key_header` 参数） | 当前 `HttpRuntimeAPI` 无 header 注入点；H-01 加 Depends 后所有 HTTP agent 调用会立即 401，无受支持的修复路径；KP0-02 原文"不改 agent 侧任何代码"过严 |
| KP0-11 | **冻结** HttpRuntimeAPI 调用方从 `FACTPY_KERNEL_API_KEY`（单数）读取；与 kernel 侧 `FACTPY_KERNEL_API_KEYS`（复数）区分 | 明确服务端配置 vs 客户端约定的命名边界 |
| KP0-12 | **冻结** H-02 的写路径必须覆盖 post-commit 内存索引更新；`_write_session()` 提供 post_commit hook 列表；SQLite COMMIT 成功后在释放锁之前执行 hooks | 当前 ledger.py:append_assertion / append_revocation 把 `_idx_add_*` 放在 `with self._transaction()` 外，reader 会看到"SQLite 已提交、内存索引旧值"的窗口；违反 H-02 的"无数据不一致"验收 |
| KP0-13 | **冻结** `Ledger.close()` 追踪所有 thread-local 连接；close 后 `_get_connection()` 抛 RuntimeError；close 幂等；调用方负责 quiesce worker 线程 | 原蓝图只关单个连接，多线程场景下会出现"主线程 close 了、worker 连接还活着"的半关闭状态 |

### KP0-02 的收窄

原文"不改 agent 侧任何代码"已修订为"不改 agent 侧业务逻辑；仅为 `HttpRuntimeAPI` 引入最小的 API key header 注入兼容点"。

这是**必要的扩展**，不是违反原则：
- Agent 业务语义完全不变（ExtractionAgent / BatchExtractor / EntityResolver / Orchestrator 的方法签名和行为不变）
- 只有 `HttpRuntimeAPI` 构造函数追加两个**可选**参数（默认 None）
- 向后兼容：现有不传 api_key 的调用行为不变
- 不传 api_key 在 kernel 认证开启后会 401，但这是**正确行为**（调用方缺少凭据）
- 没有这个改动，H-01 实施后 agent 的 HTTP 路径立即全线不可用，违反 C1 "最小可用" 的实际语义

### 实现前再收口（2 处）

1. **KP0-13 进一步收口**：
   - 复核发现 `sqlite3.Connection.close()` 在 `check_same_thread=True` 下**不能跨线程调用**
   - 因此 C1 不能再承诺“主线程 close() 会物理关闭其他线程创建的 connection”
   - 最终合同收敛为：
     - `close()` 标记 Ledger closed
     - 当前线程 connection 直接 close
     - 其他线程 connection 从 registry 中移除、对 Ledger API 不再可达
     - 调用方负责先 quiesce worker 线程，再等待线程退出 / GC 回收

2. **KP0-14 新增**：
   - 复核发现只做 `post_commit hooks` 仍不够
   - reader 若不拿同一把锁，仍可能在 writer 的 COMMIT 与 hook 之间看到 DB/index 不一致
   - 因此所有 public in-memory reads 必须共享 `RLock`

### 明确不做

以下项目明确**不在本蓝图范围**，需独立蓝图：
- P1 隐患：H-04 ~ H-08（内存字典、Ledger 全量加载、磁盘 GC、retract 级联/竞态）
- P2 隐患：H-09 ~ H-14（engine 超时、schema 演进、error 泄露等）
- Agent 侧任何修复
- aiosqlite / asyncio 迁移
- PostgreSQL / 其他后端迁移
- Secret manager 集成（Vault / AWS SM / 1Password CLI）
- RBAC / per-user 权限
- Rate limiting
- API audit logging（谁调了什么）
- JWT / OAuth2 / mTLS 升级
- 多进程并发 / 分布式 session
- 性能优化 / 压测
- Git history cleanup（.env 从未被 commit，无需）

### 关键 trade-off

**KP0-04 的"最小可用"意味着**：
- 本蓝图解决的是**上线硬门槛**，不是"生产最佳实践"
- 完成后 kernel 可以部署到可控网络环境（内部 VPN / 单集群）
- 不等于"互联网级生产就绪"——那需要 RBAC、rate limiting、audit log、secret manager、HA 部署等一系列独立蓝图

**显式承认的缺陷**：
1. API Key 无 per-user 区分 → 审计粒度低
2. 单进程并发 → 多 worker 部署仍需共享存储层
3. 密钥轮换手动 → 可能因忘记轮换而长期有效
4. `FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关 → 依赖部署 checklist

### 与 B3 负载测试的关系

B3（agent 真实文档负载测试）和 C1（kernel P0）是**独立并行线**：
- B3 在**开发环境**跑 agent 能力验证 —— 可以接受 kernel 未修复
- C1 修复 kernel 生产化隐患 —— 与 agent 能力验证无关
- 两者都完成后，才能在"生产环境"跑真实文档 + 认证 + 并发

### 与后续 kernel 蓝图的关系

本蓝图完成后，下一批可能需要的 kernel 蓝图：

1. **Kernel P1 生产化**：H-04/H-05/H-06/H-07/H-08（内存/磁盘/truth maintenance/竞态）
2. **Kernel Async Migration**：aiosqlite → 真正的 async 支持
3. **Kernel Backend Abstraction**：SQLite → PostgreSQL 可切换
4. **Kernel Secret Manager Integration**：Vault / AWS SM / 1Password CLI
5. **Kernel RBAC**：per-user 权限 + API audit log
6. **Kernel Rate Limiting**：滥用防护

这些都是独立蓝图，不挂在 C1 下面。

### 与 agent 能力线的互不影响保证

KP0-02（含 KP0-10 修订）/ KP0-03 保证 **agent 业务语义不受影响**：

**完全不变的部分**：
- `runtime_v1.py` 的函数签名和返回形状
- Agent 业务对象（ExtractionAgent / BatchExtractor / EntityResolver / ReadReviewOrchestrator / DraftManager / BundleManager 等）的构造签名、方法签名、行为
- `LocalRuntimeAPI`（直接调 `runtime_v1.*`，不过 HTTP 层，与认证无关）
- 所有现有 agent 测试（若不传 `api_key` 构造 `HttpRuntimeAPI`，行为与当前完全一致）

**有最小扩展的部分**（KP0-10）：
- `HttpRuntimeAPI.__init__` 追加可选参数 `api_key` / `api_key_header`
- 默认值为 None，**向后兼容**
- 当 kernel 启用认证且调用方不传 `api_key` 时，HTTP 调用会 401
  —— 这是正确行为（缺少凭据），不是回归

**调用方责任**：
- 读取客户端环境变量（`FACTPY_KERNEL_API_KEY`，单数）
- 构造 `HttpRuntimeAPI(base, api_key=...)`
- 本蓝图**不负责**在 agent 框架层自动注入 API key
