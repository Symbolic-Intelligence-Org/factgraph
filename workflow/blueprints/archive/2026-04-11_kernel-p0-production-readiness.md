# Blueprint: Kernel P0 — Production Readiness

- Status: implemented
- Created: 2026-04-11
- Parent: [product-readiness-audit-2026-04-09.md](../../references/working/product-readiness-audit-2026-04-09.md)
- Scope: **Kernel 侧**（非 agent 线），独立于 agent 蓝图推进
- Related Modules:
  - `src/factpy_kernel/service/app_v1.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/core/store/ledger.py`
  - `.env` / `.gitignore`

---

## 0. 目标与边界

**交付目标**：修复产品落地审计（2026-04-09）识别的 **P0 级隐患**，让 FactPy Kernel 可以通过上线门槛。

**冻结决策**（本轮锁定）：

| # | 决策 | 理由 |
|---|------|------|
| KP0-01 | 只处理 P0（H-01 / H-02 / H-03），不含 P1/P2 | 上线硬门槛；P1/P2 作为独立蓝图推进 |
| KP0-02 | 不改 agent 侧业务逻辑；仅为 `HttpRuntimeAPI` 引入最小的 API key header 注入兼容点 | Agent 主线的业务语义不变；但 HTTP adapter 必须能在 kernel 加认证后继续工作 |
| KP0-03 | 不改 runtime_v1 的业务语义 | 只加认证层、修并发、密钥管理；DTO/response 形状不变 |
| KP0-04 | 采用最小可用方案，不引入 ORM / 框架迁移 | 降低改动面；保留后续深度改造空间 |

**本蓝图覆盖的 P0 隐患**（来自 [audit report](../../references/working/product-readiness-audit-2026-04-09.md) §4.1）：

| ID | 隐患 | 位置 |
|----|------|------|
| H-01 | 零认证 API — 全部端点裸露 | `service/app_v1.py` 全部 40+ 路由 |
| H-02 | SQLite 单连接 + `check_same_thread=False` → 并发写入致库损坏 | `core/store/ledger.py:266-277` |
| H-03 | `.env` 中暴露真实密钥 | `/hnsm-backend/.env` (已 gitignored，但密钥仍在磁盘) |

**明确排除**：
- P1 隐患（H-04 ~ H-08: 内存字典、Ledger 全量加载、磁盘 GC、retract 级联/竞态）
- P2 隐患（H-09 ~ H-14: engine 超时、schema 演进、error 泄露等）
- Agent 侧任何修复
- 性能优化 / 压测
- 新能力

---

## 1. H-01: API 认证层

### 1.1 现状

`service/app_v1.py` 注册了 40+ FastAPI 路由，**零认证中间件**：

```python
# app_v1.py 当前状态（无认证）
app = FastAPI(title="factpy-kernel service", version="v1")
# 所有路由直接可达：
# POST /v1/runtime/sessions/open
# GET  /v1/runtime/sessions/{id}/...
# POST /v1/runtime/sessions/{id}/writes/set
# ... 等 40+ 路由 ...
```

**风险**（audit report 原文）：
- 任何网络可达者可读写任意 session、执行推导、导出数据
- 审计场景下认证缺失本身就是不合格项

### 1.2 冻结方案

**KP0-05 冻结**：采用 **FastAPI Depends + API Key Header** 的最小认证方案。

**不选 JWT / OAuth2** 的理由：
- JWT 需要 token lifecycle 管理（issue / refresh / revoke）
- OAuth2 需要认证服务器
- 两者都是中大型改造，与"最小可用"原则冲突
- API Key 作为**第一个认证层**，可后续升级

**不选 Bearer token** 的理由：
- Bearer 语义上是 OAuth2 的一部分，容易让人期望 OAuth2 flow
- API Key 作为独立 header 更清晰

### 1.3 架构

```
HTTP Request
    │
    ▼
┌─────────────────────────────┐
│ FastAPI middleware          │
│ (CORS / size limit)         │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ AuthDependency              │
│ (verify X-FactPy-API-Key)   │
│ → raise HTTPException 401   │
│   if missing or invalid     │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ Route handler               │
│ (unchanged runtime_v1 call) │
└─────────────────────────────┘
```

### 1.4 实现细节

**新建文件**: `src/factpy_kernel/service/auth.py`

```python
from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


class AuthConfig:
    """Authentication configuration loaded from environment."""

    def __init__(self) -> None:
        # Comma-separated API keys, loaded from env
        raw = os.environ.get("FACTPY_KERNEL_API_KEYS", "")
        self._allowed_keys: tuple[str, ...] = tuple(
            k.strip() for k in raw.split(",") if k.strip()
        )
        # If no keys configured, auth is effectively disabled
        # (explicit: must set FACTPY_KERNEL_AUTH_DISABLED=true to skip)
        self._disabled = os.environ.get("FACTPY_KERNEL_AUTH_DISABLED", "").lower() == "true"

    @property
    def enabled(self) -> bool:
        return not self._disabled

    @property
    def has_keys(self) -> bool:
        return len(self._allowed_keys) > 0

    def verify(self, provided_key: str | None) -> bool:
        """Constant-time compare against any allowed key."""
        if not provided_key:
            return False
        for allowed in self._allowed_keys:
            if hmac.compare_digest(provided_key, allowed):
                return True
        return False


# Module-level singleton; constructed at import
_auth_config = AuthConfig()


async def require_api_key(
    x_factpy_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """
    FastAPI dependency. Apply to every route that requires auth.

    Reads X-FactPy-API-Key header and verifies against configured keys.
    If FACTPY_KERNEL_AUTH_DISABLED=true, skips verification entirely
    (for local dev only; MUST NOT be set in production).
    """
    if not _auth_config.enabled:
        return  # explicitly disabled

    if not _auth_config.has_keys:
        # Fail closed: if auth is enabled but no keys configured, reject all
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication not configured",
        )

    if not _auth_config.verify(x_factpy_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "FactPyAPIKey"},
        )
```

**修改**: `src/factpy_kernel/service/app_v1.py`

在所有路由上追加 `Depends(require_api_key)`：

```python
from .auth import require_api_key
from fastapi import Depends

# Example route modification
@app.post(
    "/v1/runtime/sessions/open",
    dependencies=[Depends(require_api_key)],   # 新增
)
def route_open_runtime_session(dto: dict[str, Any]) -> dict[str, Any]:
    return runtime_v1.open_runtime_session(dto)
```

**对所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`**。

### 1.5 配置管理

**环境变量**（KP0-06 冻结）：

| 变量 | 用途 | 默认 | 生产必须 |
|------|------|------|---------|
| `FACTPY_KERNEL_API_KEYS` | 逗号分隔的允许密钥集 | 空 | 是 |
| `FACTPY_KERNEL_AUTH_DISABLED` | 显式关闭认证（仅 dev） | `false` | 必须未设或设为 `false` |

**密钥生成**：
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**密钥轮换流程**：
1. 生成新密钥
2. `FACTPY_KERNEL_API_KEYS="new_key,old_key"` — 同时接受新旧
3. 逐步切换客户端到新密钥
4. 确认无客户端使用旧密钥后，去掉 old_key

### 1.6 H-01 验收标准

- [ ] `service/auth.py` 实现，含 AuthConfig + require_api_key
- [ ] 所有 40+ 路由追加 `dependencies=[Depends(require_api_key)]`
- [ ] 未配置 `FACTPY_KERNEL_API_KEYS` 且未设 `FACTPY_KERNEL_AUTH_DISABLED=true` 时，所有请求返回 503
- [ ] 设置 `FACTPY_KERNEL_AUTH_DISABLED=true` 时所有请求放行（dev mode）
- [ ] 配置 API key 后，无 header / 错误 header 返回 401
- [ ] 正确 header 返回 200
- [ ] 常数时间比较（hmac.compare_digest）
- [ ] 单测覆盖：enabled/disabled/no_keys/valid_key/invalid_key 五种情形

### 1.7 明确不做

- **不做 per-user 权限**（RBAC）—— 所有持有有效 API key 的客户端权限相同
- **不做 rate limiting**（留给 P1）
- **不做 audit log 记录 API 调用者**（留给 P1）
- **不做 OAuth2 / JWT / mTLS 升级路径**（独立蓝图）
- **不做密钥轮换的自动化**（手动通过环境变量）
- **不做 FastAPI middleware level 全局认证**——采用显式 Depends 确保每个路由都可见其认证需求

### 1.8 HttpRuntimeAPI 兼容点（KP0-02 的具体落法）

**问题**：当前 `src/factpy_kernel/agent/tools/_runtime_api.py:HttpRuntimeAPI` 的 `_get_json` / `_post_json` / DELETE helper 都只发默认 header。一旦 kernel 路由加上 `Depends(require_api_key)`，所有 HTTP agent 调用会立即 401。

**KP0-10 冻结**：C1 必须给 `HttpRuntimeAPI` 追加一个最小的 API key header 注入兼容点。**不改 agent 业务语义**，只加可选构造参数。

**最小改动范围**：

```python
# src/factpy_kernel/agent/tools/_runtime_api.py (修改)

class HttpRuntimeAPI:
    """Minimal HTTP transport over service v1 routes."""

    def __init__(
        self,
        runtime_api_base: str,
        *,
        api_key: str | None = None,         # 新增：可选 API key
        api_key_header: str = "X-FactPy-API-Key",  # 新增：header 名（默认对齐 kernel 侧）
    ) -> None:
        if not isinstance(runtime_api_base, str) or not runtime_api_base:
            raise AgentContractError("runtime_api_base must be non-empty string")
        self._base = runtime_api_base.rstrip("/")
        self._extra_headers: dict[str, str] = {}
        if api_key is not None:
            if not isinstance(api_key, str) or not api_key:
                raise AgentContractError("api_key must be non-empty string when provided")
            self._extra_headers[api_key_header] = api_key

    # _get_json / _post_json / _delete_json 等 helper 内部追加：
    #   headers = {**default_headers, **self._extra_headers}
```

**约束**：
- `api_key` 参数**可选**，默认 None（向后兼容）
- 已有测试若不传 `api_key`，行为不变
- `LocalRuntimeAPI` 不受影响（直接调用 runtime_v1 函数，不过 HTTP 层）
- `resolve_runtime_api()` 工厂函数保持签名不变；如需注入 API key，调用方自行构造 `HttpRuntimeAPI(base, api_key=...)` 后通过 `runtime_api=` 参数传入

**配置约定**（KP0-11 冻结）：调用方从环境变量读取：

```python
api_key = os.environ.get("FACTPY_KERNEL_API_KEY")
http_api = HttpRuntimeAPI(runtime_api_base, api_key=api_key)
```

注意：**调用方自己决定读哪个环境变量**。kernel 侧用 `FACTPY_KERNEL_API_KEYS`（复数、逗号分隔）是服务端配置；客户端用 `FACTPY_KERNEL_API_KEY`（单数）是调用方约定。两者不是同一个变量。

### 1.9 H-01 + KP0-10 验收补充

- [ ] `HttpRuntimeAPI.__init__` 追加 `api_key` / `api_key_header` 参数
- [ ] `HttpRuntimeAPI` 现有不传 `api_key` 的构造调用保持向后兼容
- [ ] 单测：`HttpRuntimeAPI(base, api_key="xxx")` 的所有请求包含 `X-FactPy-API-Key: xxx` header
- [ ] 单测：未提供 `api_key` 时请求不含该 header
- [ ] 集成测试：kernel 启用认证 + `HttpRuntimeAPI` 传正确 key → 200；传错误 key → 401

---

## 2. H-02: SQLite 并发安全

### 2.1 现状

`core/store/ledger.py:266-277` 当前实现：

```python
self._conn = sqlite3.connect(
    path_str,
    check_same_thread=False,    # 关闭线程安全检查
    isolation_level=None,       # autocommit 模式
)
self._conn.row_factory = sqlite3.Row
if path_str == ":memory:":
    self._conn.execute("PRAGMA journal_mode = MEMORY")
else:
    self._conn.execute("PRAGMA journal_mode = WAL")
self._conn.execute("PRAGMA foreign_keys = OFF")
```

**风险**（audit report 原文）：
- 多 FastAPI worker 并发写入 → 死锁 / 库损坏
- 线程 A `BEGIN IMMEDIATE` 拿锁 → 崩溃未 COMMIT → 线程 B 永久阻塞
- 内存索引与 SQLite 数据库之间产生不一致
- **多 worker 部署直接不可用**（每个 worker 有独立的 `_SESSIONS` dict，session ID 跨 worker 不可达）

### 2.2 冻结方案

**KP0-07 冻结**：采用**线程本地连接池（thread-local connection）+ 保留 WAL 模式**的最小改造方案。

**不选 aiosqlite / asyncio 重写** 的理由：
- 整个 runtime_v1 是同步接口；切 async 是大改
- agent 侧也是同步假设
- 留给后续 async migration 蓝图

**不选 PostgreSQL 迁移** 的理由：
- 需要新增运维依赖
- 数据迁移脚本
- 是独立蓝图的范围
- WAL + thread-local 已能解决并发问题（单进程范围）

**显式承认的边界**：
- **本方案只解决单进程多线程并发**（FastAPI + threaded worker）
- **不解决多进程并发**（多 worker 部署仍然每个 worker 独立 ledger）
- 多进程部署依然需要依赖共享存储层（PostgreSQL / 网络文件系统）
- 这是 KP0-04 "最小可用" 的 trade-off

### 2.3 架构

```
Ledger instance (one per RuntimeSession)
    │
    ├── _lock: threading.RLock   — 粗粒度写锁
    │
    ├── _local: threading.local  — thread-local connections
    │
    └── _get_connection() → connection for current thread
         │
         ▼
    每个线程第一次调用时 lazy 构造 sqlite3.Connection
    同一线程复用同一 connection
    线程退出 → 自然 GC
```

### 2.4 实现细节

**修改**: `src/factpy_kernel/core/store/ledger.py`

```python
import threading
from contextlib import contextmanager
from typing import Iterator


class Ledger:
    def __init__(self, path: str | None = None) -> None:
        # ... existing setup ...

        # KP0-07: Thread-safe connection management
        self._path = path_str
        self._local = threading.local()
        self._write_lock = threading.RLock()

        # Initialize schema via the main-thread connection
        main_conn = self._get_connection()
        self._init_schema(main_conn)
        self._load_from_db_via(main_conn)

    def _get_connection(self) -> sqlite3.Connection:
        """
        Return a sqlite3.Connection for the current thread. Lazy-constructs
        a new connection on first access per thread.

        Thread-local semantics:
        - Each thread gets its own dedicated connection
        - Connections share the same underlying SQLite file
        - WAL mode allows concurrent readers + one writer across connections
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self._path,
                check_same_thread=True,   # KP0-07: re-enable thread safety check
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            if self._path == ":memory:":
                conn.execute("PRAGMA journal_mode = MEMORY")
            else:
                conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = OFF")
            # Longer busy timeout to tolerate writer contention
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 seconds
            self._local.conn = conn
        return conn

    @contextmanager
    def _write_session(
        self,
    ) -> Iterator[tuple[sqlite3.Connection, list[Callable[[], None]]]]:
        """
        Acquire write lock + per-thread connection + BEGIN IMMEDIATE.
        Yield (conn, post_commit_hooks).

        KP0-12 冻结的合同：
        - RLock 覆盖 **整个写入流程**：SQLite transaction + 内存索引更新
        - 调用方在 with block 内:
          1. 通过 conn 执行 SQLite writes
          2. 通过 post_commit.append(...) 注册内存索引更新 callables
        - 退出 try block 时:
          - 成功路径 -> conn.execute("COMMIT") -> 依序执行 post_commit hooks
          - 异常路径 -> conn.execute("ROLLBACK") -> hooks 不执行
        - 锁在 context manager 退出时才释放 -- 保证 reader 看不到
          "SQLite 已提交、内存索引仍旧值" 的窗口

        The process-level RLock ensures only one thread can hold a writer
        session at a time (belt-and-suspenders on top of SQLite's own
        write lock), which eliminates the "thread A crashes holding lock,
        thread B deadlocks" failure mode.
        """
        with self._write_lock:
            conn = self._get_connection()
            post_commit: list[Callable[[], None]] = []
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn, post_commit
            except Exception:
                conn.execute("ROLLBACK")
                # hooks 不执行 -- ROLLBACK 后内存索引保持不变
                raise
            else:
                conn.execute("COMMIT")
                for hook in post_commit:
                    hook()
```

**重要改动**（对现有 `Ledger` 所有方法）：
- `self._conn` 字段**删除**
- 读操作 → `self._get_connection().execute(...)`
- 写操作 → 必须走 `with self._write_session() as (conn, post_commit): ...`
- 所有内存索引更新（`_idx_add_*` / `_ingest_keys` / `_meta_by_*` 等）**通过 `post_commit.append(...)` 注册**，不再在 with block 外直接调用

### 2.4a 写路径重构模板（KP0-12 冻结 post-commit hooks）

**问题**（引 findings）：当前 `append_assertion()` / `append_revocation()` 把 `_idx_add_*` 和 `_ingest_keys` 更新放在 `with self._transaction()` 块**退出之后**。这意味着：

1. Thread A: `BEGIN IMMEDIATE` → `INSERT` → `COMMIT` → **释放 RLock** → `_idx_add_*`
2. 释放 RLock 和 `_idx_add_*` 之间，Thread B 可以拿到 RLock 开始新的写事务
3. 另一个 reader 线程此时可能看到"SQLite 已有新数据，但 Ledger._claims 等内存索引未更新"
4. 违反 H-02 的"数据一致性"验收

**唯一合法 pattern**（KP0-12 冻结，所有写路径必须遵守）：

```python
def append_assertion(
    self, *, claim: Claim, claim_args: list[ClaimArg],
    meta_rows: list[MetaRow], ...
) -> None:
    with self._write_session() as (conn, post_commit):
        # 1. SQLite writes
        conn.execute("INSERT INTO claims ...", ...)
        conn.executemany("INSERT INTO claim_args ...", ...)
        conn.executemany("INSERT INTO meta_rows ...", ...)

        # 2. 注册 post-commit 内存索引更新 callables
        #    这些在 SQLite COMMIT 成功后、锁释放前执行
        #    如果 COMMIT 失败（raise），hooks 不执行，内存索引未变
        post_commit.append(lambda: self._idx_add_claim(actual_claim))
        post_commit.append(lambda: self._idx_add_claim_args(actual_claim_args))
        post_commit.append(lambda: self._idx_add_meta(actual_meta_rows))
        post_commit.append(lambda: self._register_ingest_key(ingest_key, asrt_id))

    # with 退出之后：COMMIT 已完成，hooks 已执行，锁已释放
    # reader 从这个点开始看到的状态一定是一致的
```

**为什么必须是 post-commit hooks**：
- SQLite COMMIT 失败时，内存索引未改（hooks 未执行），**无需补偿逻辑**
- 所有写路径统一 pattern，可读性一致
- 锁保证覆盖整个"SQLite commit + 内存索引更新"的原子性窗口
- 不引入隐式回滚

**不允许的 anti-pattern**（实现者必读）：

以下三种写法**全部违反 KP0-12 冻结合同**，实现时出现任一种应视为 bug：

- ❌ 旧的单变量写法：~~`with self._write_session() as conn:`~~ ——
  `_write_session()` yields **tuple**，单变量解包是类型错误；即使能编译，也会绕过 post_commit 机制
- ❌ 在 `with` block 内、COMMIT 前直接调用 `self._idx_add_*(...)`（非 lambda）——
  违反 "commit 失败时内存索引未改" 的原子性保证
- ❌ 构造手动 delta 并在 `with` 块**外**调用 `self._idx_add_*`——
  脱离了 RLock 覆盖的原子性窗口，等同于原 bug

**必须迁移到此 pattern 的写路径**（至少）：
- `append_assertion`
- `append_revocation`
- `_force_replace_meta_rows`
- 任何其他直接修改 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的方法

### 2.4b Close 语义与多连接生命周期（KP0-13 冻结）

**问题**：`Ledger.close()` 当前只关闭 `self._conn`。改造成 thread-local 后，其他线程已经打开的连接不会被主线程的 `close()` 回收。

**实现前补充发现**：
- SQLite 在 `check_same_thread=True` 时，**不允许**由其他线程关闭某个线程创建的 `sqlite3.Connection`
- 因此主线程不能“强制关闭” worker 线程创建的 connection
- KP0-13 必须收敛为**close 后 API 不再可达 + 当前线程 connection 关闭 + registry 清空**，而不是“跨线程物理 close 保证”

**KP0-13 冻结的合同**：

```python
class Ledger:
    def __init__(self, path: str | None = None) -> None:
        # ... existing setup ...
        self._closed = False
        # _all_connections: 所有已经构造的 thread-local 连接的引用集合
        # 用 list + lock 而不是 threading.local，因为我们需要跨线程枚举
        self._all_connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("Ledger is closed; no new connections may be opened")
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path, check_same_thread=True, isolation_level=None)
            # ... PRAGMAs ...
            with self._connections_lock:
                if self._closed:
                    # Race: close() 在 _get_connection 中间执行
                    conn.close()
                    raise RuntimeError("Ledger was closed during connection acquisition")
                self._all_connections.append(conn)
            self._local.conn = conn
        return conn

    def close(self) -> None:
        """
        Close the ledger.

        After close():
        - `_get_connection()` raises RuntimeError
        - All subsequent write/read calls fail
        - 当前线程持有的 connection 会被直接 close
        - 其他线程已创建的 thread-local connection **不会被主线程强制 close**
          （SQLite `check_same_thread=True` 不允许）
        - 其他线程 connection 会从 registry 中移除，Ledger API 对其不再可达；
          调用方负责先 quiesce worker 线程，再等待其自然退出 / GC 回收连接

        Contract:
        - close() is idempotent
        - close() should be called from the "owning" thread (typically
          the thread that created the Ledger)
        - Other threads must not be actively mid-transaction when close()
          is called; caller is responsible for quiescing them first
        """
        with self._write_lock:
            with self._connections_lock:
                if self._closed:
                    return
                self._closed = True
                conns_to_close = list(self._all_connections)
                self._all_connections.clear()

        # 仅直接关闭当前线程持有的 connection；其他线程 connection 不能跨线程 close。
        current_conn = getattr(self._local, "conn", None)
        if current_conn is not None:
            with suppress(Exception):
                current_conn.close()
```

**约束**：
- `close()` **必须**在所有 worker 线程 quiesce 之后调用
- 如果某个 worker 线程在 `close()` 期间仍在用连接，行为未定义；调用方有义务保证无活跃写入
- `close()` 之后，即使某线程仍持有旧 `sqlite3.Connection` Python 对象，它也**不能再通过 Ledger API 获取或复用**
- `close()` 幂等（多次调用无副作用）
- `close()` 后 `_get_connection()` 抛 `RuntimeError`
- `__del__` 仍然调 `close()` 作为兜底

### 2.4c 读路径一致性（KP0-14 冻结）

**问题**：即使 KP0-12 把“SQLite COMMIT + post_commit hooks”放进同一把写锁，**reader 如果不拿同一把锁**，仍可能在 writer 的 COMMIT 与 hook 执行之间读到：

- SQLite 已写入的新状态
- 但内存索引仍是旧状态

这会再次违反 H-02 的“SQLite 与内存索引一致”验收。

**KP0-14 冻结**：所有读取**内存索引**的 public API 必须获取与 writer 相同的 `RLock`。

**覆盖范围**（至少）：
- `get_claim`
- `find_claims`
- `find_claim_args`
- `find_meta`
- `find_annotations`
- `has_active_revocation`
- `find_revoker`
- `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` properties
- 任何直接读取 `_claims` / `_claim_args` / `_meta_by_*` / `_ingest_keys` 的 public helper

**唯一合法 pattern**：

```python
def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
    with self._write_lock:
        if pred_id is not None and e_ref is not None:
            return list(self._claims_by_pred_e_ref.get((pred_id, e_ref), []))
        if pred_id is not None:
            return list(self._claims_by_pred_id.get(pred_id, []))
        if e_ref is not None:
            return list(self._claims_by_e_ref.get(e_ref, []))
        return list(self._claims)
```

**trade-off**：
- 读写会在同一个 `Ledger` 实例上串行化
- 这是 KP0-04 下可接受的最小一致性代价
- 不引入 RWLock / snapshot isolation / lock-free index swap 这类更重方案

### 2.5 `:memory:` 特殊处理

SQLite `:memory:` 数据库**不能跨线程共享**（每个连接是独立的内存库）。Thread-local connection 方案会让每个线程看到独立的空库。

**KP0-08 冻结**：`:memory:` 模式仅用于**单线程测试**。生产必须使用文件路径。

实现方式：
- `Ledger.__init__(path=":memory:")` 时，设置 `self._memory_mode = True`
- `_get_connection()` 在 memory mode 下始终返回同一个连接（不走 thread-local）
- 同时在 `__init__` 时 warn：`"memory ledger is single-threaded; do not use from multiple threads"`

### 2.6 `__deepcopy__` 处理

现有 `Ledger.__deepcopy__` 使用 `self._conn.backup(clone._conn)`。改造后：

```python
def __deepcopy__(self, memo: dict[int, Any]) -> Ledger:
    clone = Ledger()
    with self._write_lock:
        source_conn = self._get_connection()
        target_conn = clone._get_connection()
        source_conn.backup(target_conn)
    clone._reset_indexes()
    clone._load_from_db_via(clone._get_connection())
    memo[id(self)] = clone
    return clone
```

### 2.7 H-02 验收标准

- [ ] `Ledger._conn` 字段删除
- [ ] `Ledger._get_connection()` 实现 thread-local lazy 构造
- [ ] `Ledger._write_session()` 包裹 `threading.RLock` + `BEGIN IMMEDIATE` + post-commit hook（KP0-12）
- [ ] 所有写路径（`append_assertion` / `append_revocation` / `_force_replace_meta_rows` 等）迁移为：
  - SQLite writes 在 with block 的前段
  - 内存索引更新通过 `post_commit.append(...)` 在 SQLite COMMIT 后、锁释放前执行
- [ ] `:memory:` 模式保留单线程语义 + 显式 warning
- [ ] `__deepcopy__` 使用新连接模式
- [ ] **并发 write 测试**：10 个线程各自做 100 次 write，全部成功，无死锁
- [ ] **数据一致性测试**（KP0-12 新增）：writer 线程持续 append，多个 reader 线程在任意时刻 `find_claims(...)` 必须看到和 SQLite `SELECT` 完全一致的结果——不存在"SQLite 已写入但内存索引未更新"的时间窗
- [ ] **并发读写测试**：writer 线程 + 多个 reader 线程并行，读方不被 WAL 阻塞
- [ ] **崩溃恢复测试**：writer 线程中途 raise，`ROLLBACK` 被调用，post-commit hooks 不执行，内存索引未变；后续线程可正常获取 lock
- [ ] **Close 语义测试**（KP0-13 新增）：`close()` 后 `_get_connection()` 抛 `RuntimeError`；当前线程 connection 被关闭；registry 清空；`close()` 幂等
- [ ] **Read consistency 测试**（KP0-14 新增）：reader 通过 public read API 与 writer 并发时，永远看不到“SQLite 已提交但内存索引未更新”的状态
- [ ] 现有 kernel 全部测试通过（无回归）

### 2.8 明确不做

- **不做 aiosqlite 迁移**（独立蓝图）
- **不做 PostgreSQL 后端**（独立蓝图）
- **不解决多进程并发**（KP0-04 边界）
- **不做 connection pool 监控**（留给 P1 observability）
- **不做数据库升级迁移工具**（现有 `_DDL` 机制保留）

---

## 3. H-03: `.env` 密钥管理

### 3.1 现状

`/hnsm-backend/.env` 文件存在，含 `OPENAI_API_KEY` 和 `NEO4J_PASSWORD` 明文值。

**已做的防护**：
- `.env` 已在 `.gitignore` 第 22 行
- `git log --all --full-history -- .env` 返回空 → **从未提交到 git 历史**

**剩余风险**：
- 密钥仍然在本地磁盘明文存储
- 开发者机器被入侵 / 备份泄漏 / 临时复制 → 密钥暴露
- 没有密钥轮换流程
- 没有"密钥不应出现在 .env"的硬约束
- 审计报告在 4/9 日的快照中把它列为 P0

### 3.2 冻结方案

**KP0-09 冻结**：**轮换现有密钥 + 引入 `.env.example` 模板 + 文档化密钥管理流程**。

**不做**:
- 不引入 secret manager（Vault / AWS Secrets Manager / 1Password CLI）—— 独立蓝图
- 不改代码读取密钥的方式（仍然 `os.environ.get(...)`）
- 不改变 `.env` 作为本地开发约定

### 3.3 实施步骤

**Step 1: 密钥轮换（手动）**

```
1. 登录 OpenAI 控制台 → 生成新 API key → 撤销旧 key
2. 登录 Neo4j 管理界面（或内部）→ 修改密码
3. 其他在 .env 中的密钥同步处理
```

**Step 2: `.env.example` 模板**

新建 `/hnsm-backend/.env.example`（**入 git**）：

```bash
# Copy this file to .env and fill in your real values.
# Never commit .env.
# Never paste real keys into .env.example.

# ─── LLM Providers (for agent extraction) ───
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# ─── Kernel Service Authentication (KP0-01) ───
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# Comma-separated for multiple valid keys (key rotation).
# FACTPY_KERNEL_API_KEYS=

# For local dev only — MUST NOT be set in production.
# FACTPY_KERNEL_AUTH_DISABLED=false

# ─── Observability (Langfuse, optional) ───
# LANGFUSE_PUBLIC_KEY=pk-...
# LANGFUSE_SECRET_KEY=sk-...
# LANGFUSE_HOST=

# ─── Other service credentials ───
# Add any other credentials used by local development here, commented out.
```

**Step 3: 清理当前 `.env`**

本地 `.env` 必须：
1. 删除所有已轮换的旧密钥值
2. 填入新密钥
3. 不主动 push（已 gitignored）

**Step 4: 添加 pre-commit hook（可选但建议）**

新建 `scripts/check_no_secrets_in_env_example.sh`:

```bash
#!/usr/bin/env bash
# Fail if .env.example contains any line that looks like a real secret.
set -euo pipefail

if grep -E '^[A-Z_]+=[^#[:space:]]' .env.example; then
    echo "ERROR: .env.example contains real values (not comments). Remove them."
    exit 1
fi

echo "OK: .env.example has no real values."
```

这个 hook 不强制 CI 运行，但可以手动或通过 `.pre-commit-config.yaml` 挂到 git pre-commit。

**Step 5: 文档化**

在 `docs/SECURITY.md`（新建）或现有 onboarding doc 追加：

```markdown
## Secret Management

- Local development: use `.env` (gitignored). Copy from `.env.example`.
- `.env.example` is committed and must NEVER contain real values.
- Rotate any key immediately if suspected leaked.
- Production deployment: inject via container env vars or secret manager.
  Do NOT bundle `.env` into production images.

## Key Rotation Checklist

- [ ] Generate new key at provider
- [ ] Update `.env` locally
- [ ] Update production secret manager
- [ ] Verify new key works
- [ ] Revoke old key at provider
- [ ] Document rotation date
```

### 3.4 H-03 验收标准

- [ ] 所有现有 `.env` 中的密钥已在 provider 侧轮换（新密钥生成 + 旧密钥撤销）
- [ ] `.env.example` 模板文件存在并入 git
- [ ] `.env.example` 不含任何真实值（所有变量都以 `#` 注释）
- [ ] `docs/SECURITY.md` 存在并说明本 checklist
- [ ] `.env` 仍然被 `.gitignore` 覆盖（验证：`git check-ignore .env`）
- [ ] `git log --all -- .env` 仍为空（历史从未包含）
- [ ] （可选）pre-commit hook 脚本存在

### 3.5 明确不做

- **不引入 secret manager**（Vault / AWS SM / 1Password CLI）—— 独立蓝图
- **不改代码读取密钥的方式**
- **不做 runtime 密钥热加载**
- **不做密钥过期提醒 / 自动轮换**
- **不清理 git 历史**（已验证 `.env` 从未被提交；无需 `git filter-branch` / BFG）

---

## 4. 实现顺序

```
Step 1: H-03 密钥轮换（手动，不需要代码）
        → 立即执行，降低风险窗口
        → 生成新 key / 撤销旧 key / 更新本地 .env

Step 2: H-03 文档与模板
        → 创建 .env.example
        → 创建 docs/SECURITY.md
        → 验证 git ignored

Step 3: H-01 认证层实现 + HttpRuntimeAPI 兼容点（KP0-10）
        → 新建 service/auth.py
        → 单测：5 种情形
        → 修改 app_v1.py 所有路由追加 Depends
        → 扩展 agent/tools/_runtime_api.py:HttpRuntimeAPI 构造签名
        → 单测：HttpRuntimeAPI header 注入验证
        → 集成测试：完整请求链路 401/200（LocalRuntimeAPI + HttpRuntimeAPI）

Step 4: H-02 Ledger 并发修复
        → 重构 ledger.py 连接管理（thread-local + RLock + close 追踪）
        → _write_session 提供 post_commit hooks
        → append_assertion / append_revocation / 其他写路径迁移到 post_commit hook 模式
        → 修改所有 _conn 读调用点
        → :memory: 模式特殊处理
        → __deepcopy__ 更新
        → close() 追踪所有 thread-local 连接
        → 并发测试（4 种场景：write / 数据一致性 / 读写 / 崩溃恢复）
        → Close 语义测试
        → kernel 全量回归

Step 5: 集成验证
        → 真实部署一个测试实例
        → 用正确/错误 API key 打请求
        → 多线程并发跑 100 次写入
        → 确认无回归
```

**建议 Step 1 和 Step 2 立刻执行（~半天），Step 3-5 按正常节奏实施**。

---

## 5. 目录结构增量

```
src/factpy_kernel/service/
  ├── auth.py                        # (新建) AuthConfig + require_api_key
  ├── app_v1.py                      # (扩展) 所有路由追加 Depends
  └── runtime_v1.py                  # (不变)

src/factpy_kernel/agent/tools/
  └── _runtime_api.py                # (扩展) HttpRuntimeAPI +api_key +api_key_header
                                     #        KP0-10：最小兼容点；不改业务语义

src/factpy_kernel/core/store/
  └── ledger.py                      # (改造) 连接管理重构 + post-commit hooks + close 追踪

src/factpy_kernel/tests/
  ├── test_service_auth.py           # (新建) require_api_key 单测
  ├── test_service_app_v1_auth.py    # (新建) 路由级认证集成测试
  ├── test_agent_http_runtime_api_auth.py  # (新建) HttpRuntimeAPI 传 api_key 验证 header
  ├── test_ledger_concurrency.py     # (新建) 并发测试 + post-commit hook 一致性
  └── test_ledger_close.py           # (新建) thread-local 连接追踪 + close 语义

docs/
  └── SECURITY.md                    # (新建) 密钥管理规范

/hnsm-backend/
  ├── .env                           # (手动清理 + 新密钥) 不入 git
  └── .env.example                   # (新建) 模板，入 git

scripts/
  └── check_no_secrets_in_env_example.sh  # (可选)
```

---

## 6. 总体验收标准

**H-01 认证** ✓ 条件：
- 未配置密钥 → 503
- 错误 / 缺失 header → 401
- 正确 header → 200
- Dev mode (`AUTH_DISABLED=true`) → 放行
- 常数时间比较（hmac.compare_digest）
- 所有 40+ 路由覆盖

**H-02 并发** ✓ 条件：
- 线程 A 崩溃不阻塞线程 B
- 10 线程 × 100 次 write 并发无 race
- 内存索引与 DB 保持一致
- `:memory:` 单线程语义保留
- Kernel 全量回归通过

**H-03 密钥** ✓ 条件：
- 所有 `.env` 中的现有密钥已在 provider 侧轮换
- `.env.example` 入 git 且不含真实值
- `docs/SECURITY.md` 存在
- `git check-ignore .env` 返回成功

**整体门槛**:
- [ ] Kernel 全量测试通过
- [ ] 新增并发测试 + 认证测试通过
- [ ] 至少一次手动端到端验证（部署 + API key + 并发写入）

---

## 7. 已知约束

1. **不解决多进程并发**：KP0-04 明确的 trade-off。多 worker 部署仍需依赖共享存储层。这需要独立蓝图。
2. **API Key 不含 per-user 权限**：所有持有有效 key 的客户端权限相同。RBAC 是独立蓝图。
3. **不覆盖 rate limiting**：滥用防护留给独立蓝图。
4. **不覆盖 audit logging**：当前 kernel 不记录"谁调了什么 API"。留给独立蓝图。
5. **密钥轮换是手动流程**：没有自动轮换机制。
6. **P1 隐患仍然存在**：H-04 ~ H-08 不在本蓝图范围。上线后仍是已知问题。
7. **KP0-07 的 thread-local 不是连接池**：每个线程一个常驻连接，连接数 = 活跃线程数。长时间大量线程可能耗尽文件描述符。FastAPI 默认 threadpool 限制为 40 左右，在可接受范围。
8. **`.env.example` 的 pre-commit hook 是可选**：不强制 CI 运行；约定 + 代码审查 double check。
9. **H-03 不清理 git 历史**：已验证 `.env` 从未被 commit；不需要 `git filter-branch` / BFG。如果后续发现历史中仍有泄漏，需要独立处理。
10. **`FACTPY_KERNEL_AUTH_DISABLED=true` 是危险开关**：仅用于本地 dev；生产部署必须确保此变量未设或为 `false`。部署 checklist 应包含"确认 AUTH_DISABLED 未设"这一项。
11. **KP0-13 不保证跨线程物理关闭 SQLite 连接**：这是 `check_same_thread=True` 的原生限制。C1 保证的是 close 后 Ledger API 不再可达、当前线程 connection 关闭、registry 清空；worker thread connection 需由 quiesce + 线程退出回收。
12. **KP0-14 牺牲部分并发读吞吐换一致性**：同一 `Ledger` 实例的 public 读写都走同一把 `RLock`。这是最小可用方案，不是最终性能方案。

---

## 8. Outcome / Deviations

### Outcome

- H-01 已落地：
  - 新增 `src/factpy_kernel/service/auth.py`
  - `src/factpy_kernel/service/app_v1.py` 的 `/v1/...` 路由统一接入 `Depends(require_api_key)`
  - `src/factpy_kernel/agent/tools/_runtime_api.py` 为 `HttpRuntimeAPI` 增加最小 `api_key` / `api_key_header` 兼容点
- H-02 已落地：
  - `src/factpy_kernel/core/store/ledger.py` 从单共享连接改为 thread-local SQLite connection
  - 写路径统一迁移到 `_write_session() -> (conn, post_commit)` 合同
  - public read API 与 writer 共享同一把 `RLock`
  - `close()` 现在显式标记 closed，并阻止后续新连接打开
- H-03 仓库内产物已落地：
  - 新增 `.env.example`
  - 新增 `docs/SECURITY.md`
  - 新增 `scripts/check_no_secrets_in_env_example.sh`
- 受影响模块文档已同步：
  - `src/factpy_kernel/service/docs/README.md`
  - `src/factpy_kernel/service/docs/01_overview.md`
  - `src/factpy_kernel/service/docs/02_runtime_sessions.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/service/docs/04_rules_registry.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/agent/docs/README.md`
  - `docs/README.md`
- 验证结果：
  - `./scripts/check_no_secrets_in_env_example.sh` → `OK`
  - `git check-ignore .env` → `.env`
  - `git log --all --full-history -- .env` → 空
  - `python -m unittest discover -s src/factpy_kernel/tests` → `942 tests`, `1 skipped`

### Deviations

1. `AuthConfig` 没有采用早期示例中的 module-level singleton；实现改为 `load_auth_config()` 每次从环境变量读取。
   - 原因：测试可控性更好，不需要 reload 模块或 patch singleton。
   - 影响：不改变 H-01 的公开合同，只让 auth 配置在测试里更易切换。

2. `:memory:` 模式的 warning 没有在 `Ledger(...)` 构造时无条件发出；实现改为在跨线程访问 `:memory:` ledger 时再告警。
   - 原因：无条件 warning 会让现有测试输出过于嘈杂。
   - 影响：不改变 KP0-08 的真实边界，仍然只承诺单线程语义。

3. `close()` 语义最终按 KP0-13/KP0-14 的收紧版落地：保证“Ledger API 不再可达 + 当前线程连接关闭 + registry 清空”，不承诺跨线程物理 close。
   - 原因：`sqlite3.Connection.close()` 在 `check_same_thread=True` 下不能跨线程调用。
   - 影响：调用方必须先 quiesce worker 线程；这是已写入蓝图正文的真实边界。

4. 目录结构计划中的 `test_ledger_close.py` 没有单独创建；close 语义测试并入了 `src/factpy_kernel/tests/test_ledger_concurrency.py`。
   - 原因：close 语义与 post-commit / read consistency 是同一组 ledger 并发约束，合并测试更自然。
   - 影响：无产品语义偏差，只是测试文件组织方式不同。

5. H-03 的 provider-side 密钥轮换没有在仓库内自动完成。
   - 原因：这一步依赖外部控制台/凭据，不能由当前仓库代码替代。
   - 影响：仓库内模板、文档、脚本与 ignore/history 验证已完成；真实轮换仍是上线前的运维 checklist 项。
