# Blueprint: Agent Layer 1 — 控制面 MVP

- Status: implemented
- Created: 2026-04-09
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Related Modules:
  - `src/factpy_kernel/agent/session.py` (新建)
  - `src/factpy_kernel/agent/draft.py` (新建)
  - `src/factpy_kernel/agent/candidate_cache.py` (新建)
  - `src/factpy_kernel/agent/errors.py` (新建)
  - `src/factpy_kernel/agent/framework.py` (新建)
  - `src/factpy_kernel/agent/tools/kg_read.py` (新建)
  - `src/factpy_kernel/agent/tools/explain.py` (新建)
  - `src/factpy_kernel/agent/tools/_runtime_api.py` (新建)
  - `src/factpy_kernel/agent/recovery.py` (新建)
  - `src/factpy_kernel/agent/docs/README.md` (新建)
  - `src/factpy_kernel/service/runtime_v1.py` (只读依赖)

---

## 0. 目标与边界

**交付目标**：agent 的会话/状态/持久化/恢复/工具调用底盘可用。

**明确排除**：
- 任何 LLM 调用逻辑（意图识别、slot filling、NL 生成）
- 事实/规则写入
- 文档提取
- 引擎路由

**验收标准**：
- AgentSession 可创建、可恢复（warm + cold）、可关闭
- DraftManager 可 CRUD draft、可 checkpoint、可从 checkpoint 恢复
- CandidatePayloadCache 可存/取/清理 evaluate response
- KGReadTools 可查询 schema/claims/candidates/rules
- ExplainTools 可拉取 summary/steps/tree/timeline
- 全部组件有单测覆盖

---

## 1. AgentSession 数据模型

```python
from dataclasses import dataclass, field
from typing import Literal
import time
import uuid


@dataclass
class RuntimeBootstrapSpec:
    """
    RuntimeSession 的重建规格。cold restart 时用此 spec 重新 open_runtime_session。

    持久化到 Burr state，与 AgentSession 共生命周期。

    设计选择：保存完整 open_dto（传给 open_runtime_session(dto) 的原始 dict），
    而非拆解成多个字段。理由：
    - open_runtime_session 的 DTO 结构可能随版本演进
    - cold restart 时直接 open_runtime_session(dto=self.open_dto) 即可
    - schema_ir_digest 冗余存储，用于快速匹配检查（无需反序列化整个 DTO）
    """
    schema_ir_digest: str               # schema_ir 的 JCS SHA256 digest（冗余，供快速匹配）
    open_dto: dict                      # 传给 open_runtime_session(dto) 的完整 DTO


@dataclass
class AgentSession:
    """
    Agent 层的会话实体。

    一个 AgentSession 绑定一个 RuntimeSession（通过 runtime_session_id）。
    AgentSession 持有自己的持久化状态（Burr checkpoint + CandidatePayloadCache），
    与 RuntimeSession 的生命周期松耦合。

    生命周期：
      created → active → closed
                  ↑        |
                  +--------+ (reopen after cold restart)
    """
    agent_session_id: str = field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:12]}")
    runtime_session_id: str | None = None    # 绑定的 RuntimeSession ID；cold restart 后可能变更
    bootstrap_spec: RuntimeBootstrapSpec | None = None

    scope: "AgentScope | None" = None        # 权限约束（v1 蓝图 §6.1）

    status: Literal["created", "active", "closed"] = "created"
    created_at: int = field(default_factory=lambda: int(time.time() * 1e9))
    last_active_at: int = field(default_factory=lambda: int(time.time() * 1e9))

    # Burr state checkpoint 路径
    burr_db_path: str | None = None          # SQLite file for Burr + CandidatePayloadCache

    def touch(self) -> None:
        """更新 last_active_at。每次 tool 调用时触发。"""
        self.last_active_at = int(time.time() * 1e9)
```

### 1.1 AgentSession 与 RuntimeSession 的关系

```
AgentSession (agent 侧，持久化到 Burr SQLite)
  │
  │  runtime_session_id (字符串引用，松耦合)
  │
  ▼
RuntimeSession (kernel 侧，进程内 dict，不持久化)
  │
  ▼
Store → Ledger (SQLite) → ArtifactSidecar (filesystem)
```

**关键约束**：
- AgentSession 不持有 RuntimeSession 对象引用（只有 ID）
- RuntimeSession 可能因进程重启而消失
- AgentSession 必须能检测 RuntimeSession 是否存活，并在需要时重建

### 1.2 状态转换

```
created ──[bind_runtime_session()]──→ active
active  ──[close()]──────────────────→ closed
active  ──[runtime session 消失]─────→ active (status 不变，但需要 recover)
closed  ──(终态，不可恢复)
```

---

## 2. RuntimeBootstrapSpec

### 2.1 何时创建

AgentSession 首次绑定 RuntimeSession 时，从 `open_runtime_session` 的请求参数中提取并保存。

```python
# 伪代码：AgentSession 创建流程
# 注意：对齐真实接口 open_runtime_session(dto: dict) → ok_response(session=...)
# 见 runtime_v1.py:168

def create_agent_session(open_dto: dict, scope: AgentScope) -> AgentSession:
    """
    open_dto 是传给 open_runtime_session 的完整 DTO，形如:
    {
        "schema_ir": { ... },              # 或通过 "registry_root" 指定 registry 路径（二选一）
        "ledger_path": "/path/to/ledger.db",    # 可选
        "artifact_store_root": "/path/to/artifacts",  # 可选
    }
    """
    # 1. 打开 RuntimeSession（真实接口签名）
    resp = open_runtime_session(dto=open_dto)
    # resp 结构: {"ok": True, "session": {"session_id": "rt_xxx", "schema_digest": "...", ...}}
    runtime_session_id = resp["session"]["session_id"]

    # 2. 构造 bootstrap spec（保存完整 DTO 供 cold restart 重建）
    spec = RuntimeBootstrapSpec(
        schema_ir_digest=resp["session"].get("schema_digest", ""),
        open_dto=open_dto,               # 保存完整 DTO，cold restart 时原样重发
    )

    # 3. 构造 AgentSession
    session = AgentSession(
        runtime_session_id=runtime_session_id,
        bootstrap_spec=spec,
        scope=scope,
    )
    session.status = "active"
    return session
```

### 2.2 何时使用

仅在 cold restart 时使用（见 §6）。Warm reconnect 不需要 bootstrap spec。

### 2.3 持久化

RuntimeBootstrapSpec 作为 AgentSession 的一部分，通过 Burr state checkpoint 持久化到 SQLite。

**注意**：`schema_ir` 完整存储可能较大（数十 KB）。如果 schema 极大，可考虑只存 digest + 从 registry 拉取。Layer 1 先存完整副本。

---

## 3. DraftManager 最小合同

```python
from dataclasses import dataclass, field
from typing import Literal, Any


@dataclass
class FactDraft:
    """复用 v1 蓝图 §4.1 定义，此处只列必要字段。"""
    draft_id: str
    entity_type: str
    entity_identity: dict[str, Any]
    pred_id: str
    field_values: list[tuple[str, Any]]
    confidence: float | None
    source: str | None
    source_loc: str | None
    note: str | None
    created_at: int
    status: Literal["pending", "confirmed", "committed", "rejected", "expired"]
    session_id: str                     # agent_session_id
    conversation_turn: int


class DraftManager:
    """
    Draft 的生命周期管理器。

    Layer 1 合同：仅 CRUD + 状态流转 + checkpoint/restore。
    不含 NL 解析、slot filling、schema 校验（这些是 Layer 2/3 的事）。

    持久化策略：
    - 运行时：in-memory dict[draft_id, FactDraft]
    - Checkpoint：通过 Burr state 序列化到 SQLite
    - Restore：从 Burr state 反序列化

    注意：Layer 1 仅支持 FactDraft。RuleDraft 在 Layer 4 引入。
    """

    def create_draft(self, session_id: str, **kwargs) -> FactDraft:
        """创建 pending 状态的 draft。分配 draft_id。"""
        ...

    def get_draft(self, draft_id: str) -> FactDraft | None:
        """按 ID 查询。"""
        ...

    def list_drafts(self, session_id: str, status: str | None = None) -> list[FactDraft]:
        """按 session 列出 draft，可选按 status 过滤。"""
        ...

    def update_draft(self, draft_id: str, **fields) -> FactDraft:
        """
        更新 draft 字段。仅 pending 状态可更新。
        不允许直接修改 status（用 confirm/reject/expire）。
        """
        ...

    def confirm_draft(self, draft_id: str) -> FactDraft:
        """pending → confirmed。前置：AgentScopeGuard.validate 通过。"""
        ...

    def reject_draft(self, draft_id: str) -> FactDraft:
        """pending/confirmed → rejected。"""
        ...

    def mark_committed(self, draft_id: str, asrt_id: str) -> FactDraft:
        """confirmed → committed。由 BatchCommitEndpoint 调用。"""
        ...

    def expire_drafts(self, session_id: str, max_age_ns: int) -> list[str]:
        """将超时的 pending draft 标记为 expired。返回 expired draft_ids。"""
        ...

    # ── Checkpoint / Restore ──

    def to_checkpoint(self) -> dict:
        """序列化所有 draft 为 JSON-serializable dict（供 Burr state 存储）。"""
        ...

    @classmethod
    def from_checkpoint(cls, data: dict) -> "DraftManager":
        """从 checkpoint 反序列化恢复。"""
        ...
```

### 3.1 状态转换图

```
pending ──[confirm_draft]──→ confirmed ──[mark_committed]──→ committed
   │                              │
   ├──[reject_draft]──→ rejected  ├──[reject_draft]──→ rejected
   │
   └──[expire_drafts]──→ expired
```

### 3.2 与 Burr 的集成

DraftManager 本身不做持久化 I/O。Burr action 在每次状态转换后调用 `to_checkpoint()`，将序列化结果写入 Burr state dict：

```python
# Burr state 结构
{
    "agent_session": { ... },               # AgentSession 序列化
    "draft_manager": { ... },               # DraftManager.to_checkpoint()
    "conversation_history": [ ... ],        # 对话历史（Layer 2 引入）
}
```

---

## 4. CandidatePayloadCache 表结构

### 4.1 SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS candidate_payload_cache (
    agent_session_id    TEXT    NOT NULL,
    runtime_session_id  TEXT    NOT NULL,
    candidate_id        TEXT    NOT NULL,
    payload_json        TEXT    NOT NULL,     -- 完整 candidate payload (JSON)
    stored_at           INTEGER NOT NULL,     -- epoch_nanos
    PRIMARY KEY (agent_session_id, runtime_session_id, candidate_id)
);

-- 快速查当前 runtime session 的 active candidates
CREATE INDEX IF NOT EXISTS idx_cpc_runtime
    ON candidate_payload_cache(runtime_session_id);

-- 快速清整个 agent session（含所有历史 runtime session）
CREATE INDEX IF NOT EXISTS idx_cpc_agent
    ON candidate_payload_cache(agent_session_id);
```

**三级主键的设计理由**：
- `agent_session_id` 是一级归属——`evict_agent_session()` 一次清理整个 agent 生命周期的所有缓存
- `runtime_session_id` 区分 cold restart 前后的不同 runtime session——旧的是 stale，新的是 active
- `candidate_id` 在 runtime session 内唯一

### 4.2 Python 接口

```python
import json
import sqlite3
import time
from pathlib import Path


class CandidatePayloadCache:
    """
    Agent-side persistence for evaluate responses.

    共用 AgentSession 的 SQLite 文件（burr_db_path）。
    Burr 使用自己的表；CandidatePayloadCache 使用 candidate_payload_cache 表。

    归属模型：
    - 一级归属：agent_session_id（AgentSession 生命周期）
    - 二级分区：runtime_session_id（cold restart 后会变）
    - 三级标识：candidate_id

    清理语义：
    - 逻辑层：session close 时必须调用 evict_agent_session() 清除所有关联条目
    - 物理层：SQLite 文件可保留用于诊断
    """

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS candidate_payload_cache (
                agent_session_id    TEXT    NOT NULL,
                runtime_session_id  TEXT    NOT NULL,
                candidate_id        TEXT    NOT NULL,
                payload_json        TEXT    NOT NULL,
                stored_at           INTEGER NOT NULL,
                PRIMARY KEY (agent_session_id, runtime_session_id, candidate_id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cpc_runtime
                ON candidate_payload_cache(runtime_session_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cpc_agent
                ON candidate_payload_cache(agent_session_id)
        """)
        self._conn.commit()

    def store(
        self, agent_session_id: str, runtime_session_id: str, candidates: list[dict],
    ) -> None:
        """批量存储 evaluate 返回的 candidate payloads。幂等（UPSERT）。"""
        now = int(time.time() * 1e9)
        self._conn.executemany(
            """INSERT OR REPLACE INTO candidate_payload_cache
               (agent_session_id, runtime_session_id, candidate_id, payload_json, stored_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (agent_session_id, runtime_session_id, c["candidate_id"],
                 json.dumps(c, sort_keys=True), now)
                for c in candidates
            ],
        )
        self._conn.commit()

    def lookup_active(
        self, runtime_session_id: str, candidate_id: str,
    ) -> dict | None:
        """查询当前 runtime session 的单个 candidate payload。"""
        row = self._conn.execute(
            """SELECT payload_json FROM candidate_payload_cache
               WHERE runtime_session_id=? AND candidate_id=?""",
            (runtime_session_id, candidate_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def lookup_active_by_runtime(self, runtime_session_id: str) -> list[dict]:
        """查询当前 runtime session 下所有 candidate payloads。"""
        rows = self._conn.execute(
            """SELECT payload_json FROM candidate_payload_cache
               WHERE runtime_session_id=? ORDER BY stored_at""",
            (runtime_session_id,),
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def list_stale(
        self, agent_session_id: str, current_runtime_session_id: str,
    ) -> list[dict]:
        """
        查询该 agent session 下、不属于当前 runtime session 的所有 stale 条目。
        用于诊断 cold restart 后的历史 candidate。
        """
        rows = self._conn.execute(
            """SELECT runtime_session_id, candidate_id, payload_json, stored_at
               FROM candidate_payload_cache
               WHERE agent_session_id=? AND runtime_session_id!=?
               ORDER BY stored_at""",
            (agent_session_id, current_runtime_session_id),
        ).fetchall()
        return [
            {"runtime_session_id": r[0], "candidate_id": r[1],
             "payload": json.loads(r[2]), "stored_at": r[3]}
            for r in rows
        ]

    def evict_agent_session(self, agent_session_id: str) -> int:
        """
        清除该 agent session 的所有缓存条目（含所有历史 runtime session）。
        在 AgentSession.close() 时调用。
        """
        cursor = self._conn.execute(
            "DELETE FROM candidate_payload_cache WHERE agent_session_id=?",
            (agent_session_id,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
```

### 4.3 Cold restart 注意事项

Cold restart 后 `runtime_session_id` 会变（新 open 得到新 ID）。此时旧 runtime session 的 cached candidate **不可直接 accept**——accept 端点要求 candidate 属于当前 session。

处理策略：
1. Cold restart 后，旧 runtime_session_id 的缓存自然成为 stale（`list_stale()` 可查）
2. 不删除旧缓存——保留供诊断
3. Agent 需对需要 accept 的 derivation 重新 evaluate
4. 新 evaluate 结果通过 `store(agent_session_id, new_runtime_session_id, ...)` 存入
5. AgentSession.close() 时 `evict_agent_session()` 一次清理所有历史（含 stale + active）

---

## 5. KGReadTools / ExplainTools 方法签名

### 5.1 KGReadTools

```python
from dataclasses import dataclass


@dataclass
class ClaimResult:
    asrt_id: str
    pred_id: str
    e_ref: str
    rest_terms: list[tuple[str, object]]
    meta: dict                    # confidence, source, note, etc.
    is_revoked: bool


@dataclass
class EntitySnapshot:
    entity_type: str
    identity: dict[str, object]
    e_ref: str
    claims: list[ClaimResult]     # 该实体关联的所有 claims


@dataclass
class CandidateSummary:
    candidate_id: str
    pred_id: str
    support_kind: str
    confidence_kind: str
    # 注意：不含 state 字段（runtime inventory 不暴露 state）


@dataclass
class RuleSummary:
    """
    对齐 GET /sessions/{id}/rules 的真实返回结构。

    稳定返回字段：rule_id, version, source
    可选字段（仅 include_spec=true 时）：select_vars, where, expose
    见 02_runtime_sessions.md:522

    注意：rule_label / head_pred_id / engine 不在 inventory 返回中。
    如需这些字段，需从 spec 中推断或从 registry 查询——这是 Layer 2+ 的事。
    """
    rule_id: str
    version: str
    source: str                           # "fs" | "ephemeral" | "ephemeral_shadowed_by_fs"
    spec: dict | None = None              # 仅 include_spec=true 时非 None
                                          # 含 select_vars, where, expose 等


class KGReadTools:
    """
    Adapter 组合层——包装现有 runtime_v1 端点。

    底层映射：
      query_claims      → list_runtime_claims (runtime_v1.py)
      get_entity_snapshot → 组合多次 query_claims + schema lookup
      list_candidates   → list_runtime_candidates (仅支持 pred_id 过滤)
      list_rules        → GET /sessions/{id}/rules
      get_schema_summary → GET /sessions/{id}/schema
    """

    def __init__(self, runtime_api_base: str) -> None:
        """runtime_api_base: e.g. 'http://localhost:8000/v1/runtime'"""
        ...

    def query_claims(
        self, session_id: str, pred_id: str | None = None, e_ref: str | None = None,
    ) -> list[ClaimResult]:
        """
        包装 list_runtime_claims。
        pred_id / e_ref 均为可选过滤；至少可提供其一。
        Layer 1 实现放宽 pred_id 为可选，以便 get_entity_snapshot 直接按 e_ref 读取整实体 claims。
        """
        ...

    def get_entity_snapshot(
        self, session_id: str, entity_type: str, identity: dict[str, object],
    ) -> EntitySnapshot:
        """
        Adapter 组合：
        1. 从 schema 读取 entity_type 的 identity_fields
        2. 构造 e_ref（encode_idref_v1）
        3. 直接 query_claims(pred_id=None, e_ref=e_ref)
        4. 聚合为 EntitySnapshot

        说明：Layer 1 不做 N 次 pred_id fan-out 查询；直接按 e_ref 读取该实体全部 claims。
        """
        ...

    def list_candidates(
        self, session_id: str, pred_id: str | None = None,
    ) -> list[CandidateSummary]:
        """
        包装 list_runtime_candidates。
        仅支持 pred_id 过滤（runtime API 限制）。
        不支持 state 过滤（D-14）。
        """
        ...

    def list_rules(self, session_id: str, include_spec: bool = False) -> list[RuleSummary]:
        """
        包装 GET /sessions/{id}/rules。
        默认只返回 inventory 级别（rule_id, version, source）。
        include_spec=True 时额外返回 select_vars/where/expose。
        """
        ...

    def get_schema_summary(self, session_id: str) -> dict:
        """
        包装 GET /sessions/{id}/schema。
        返回 schema_ir 的精简视图（entity_types + predicates 列表）。
        用于 agent system prompt 骨架注入。
        """
        ...
```

### 5.2 ExplainTools

```python
@dataclass
class ExplainSummary:
    """
    Raw-first summary envelope。
    不在 Layer 1 过早统一——runtime 有两种 summary 合同：
    - tree candidate: candidate_evidence_tree_summary (12 fields)
                      + 可选 certainty_summary
      见 03_runtime_queries_views.md:628
    - PyReason candidate: candidate_provenance_timeline_summary (6 fields)
      见 03_runtime_queries_views.md:1728

    Layer 1 策略：保留 runtime 原始返回，加 kind 标记让消费方分支处理。
    Layer 2 可在此基础上叠加 normalized helper（如 get_conclusion()、get_key_metric()）。
    """
    candidate_id: str
    kind: str                             # "tree_summary" | "timeline_summary"
    summary: dict                         # runtime 原始 summary dict（引擎特定结构）
    certainty_summary: dict | None = None # 仅 tree_summary 时可能非 None


@dataclass
class ExplainStep:
    """
    Steps 的稳定字段。detail 内容引擎间不一致（见 delta §3.4）。
    """
    step_num: int
    step_kind: str                # "derivation" | "premise" | "seed" | ...
    description: str              # 人类可读描述
    node_ref: str | None          # 关联的 evidence tree node_id
    detail: dict                  # 引擎特定（不稳定）


@dataclass
class EvidenceTreeResult:
    candidate_id: str
    tree: dict                    # 完整 evidence tree dict
    support_kind: str


@dataclass
class TimelineResult:
    candidate_id: str
    timeline: dict                # 完整 CandidateProvenanceTimeline dict


class ExplainTools:
    """
    Agent 的 explain 消费层。

    默认消费路径（D-05）：summary → steps → tree/timeline on demand。

    Layer 1 设计原则：raw-first。
    - get_summary 返回 runtime 原始 envelope，不做伪统一
    - get_steps 返回稳定字段 + 引擎特定 detail
    - get_tree / get_timeline 按引擎分支返回，不支持的返回 None
    """

    def __init__(self, runtime_api_base: str) -> None: ...

    def get_summary(self, session_id: str, candidate_id: str) -> ExplainSummary:
        """
        包装 explain_runtime_summary。
        runtime 自身对 candidate 做多态 dispatch；agent 侧仅将 kind 归一化为
        tree_summary / timeline_summary。
        """
        ...

    def get_steps(self, session_id: str, candidate_id: str) -> list[ExplainStep]:
        """
        包装 explain_runtime_steps。
        所有引擎均支持，但 detail 深度引擎间不一致（见 delta §3.4）。
        """
        ...

    def get_tree(self, session_id: str, candidate_id: str) -> EvidenceTreeResult | None:
        """
        包装 explain_runtime_tree。
        Souffle / ProbLog / Native 支持。PyReason 返回 None。
        """
        ...

    def get_timeline(self, session_id: str, candidate_id: str) -> TimelineResult | None:
        """
        包装 explain_runtime_timeline。
        PyReason 支持。其他引擎返回 None。

        兼容说明：Layer 1 实现中，对现有 runtime native/非 timeline 候选的“伪 not supported”
        错误做了 fallback：先看 summary.kind，若不是 timeline_summary 则返回 None。
        """
        ...
```

---

## 6. Warm/Cold Recovery 时序

### 6.1 Warm Reconnect

**前提**：kernel 进程未重启，RuntimeSession 仍在 `_SESSIONS` dict 中。

```
Agent 进程重启 / 网络断线恢复
  │
  ├─ 1. 从 Burr SQLite 加载 AgentSession checkpoint
  │     → 拿到 agent_session_id, runtime_session_id, bootstrap_spec, scope
  │
  ├─ 2. 探测 RuntimeSession 是否存活
  │     → GET /v1/runtime/sessions/{runtime_session_id}
  │     → 200 OK = 存活
  │
  ├─ 3. 直接 rebind
  │     → AgentSession.runtime_session_id 不变
  │     → AgentSession.status = "active"
  │
  ├─ 4. 恢复 DraftManager
  │     → DraftManager.from_checkpoint(burr_state["draft_manager"])
  │
  ├─ 5. 恢复 CandidatePayloadCache
  │     → CandidatePayloadCache(burr_db_path)  // 同一 SQLite，表已存在
  │     → lookup_active_by_runtime(runtime_session_id) 验证缓存可用
  │
  └─ 6. 就绪
       → 所有 tool 可用
       → 所有 pending/confirmed draft 可继续操作
       → 所有 cached candidate 可直接 accept
```

### 6.2 Cold Restart

**前提**：kernel 进程已重启，RuntimeSession 已丢失。

```
Agent 进程重启
  │
  ├─ 1. 从 Burr SQLite 加载 AgentSession checkpoint
  │     → 拿到 agent_session_id, runtime_session_id, bootstrap_spec, scope
  │
  ├─ 2. 探测 RuntimeSession 是否存活
  │     → GET /v1/runtime/sessions/{runtime_session_id}
  │     → 404 / 连接失败 = RuntimeSession 已丢失
  │
  ├─ 3. 用 bootstrap_spec 重建 RuntimeSession
  │     → open_runtime_session(dto=bootstrap_spec.open_dto)
  │     → resp["session"]["session_id"] = 新 runtime_session_id'
  │
  ├─ 4. 更新 AgentSession 绑定
  │     → AgentSession.runtime_session_id = runtime_session_id'
  │     → Burr checkpoint 更新
  │
  ├─ 5. 恢复 DraftManager
  │     → DraftManager.from_checkpoint(burr_state["draft_manager"])
  │     → pending/confirmed draft 可继续（它们不绑定 runtime_session_id）
  │
  ├─ 6. 处理 CandidatePayloadCache
  │     → 旧 runtime_session_id 的缓存自然成为 stale
  │     → cache.list_stale(agent_session_id, runtime_session_id') 可查诊断
  │     → 不自动迁移（candidate 绑定 runtime session）
  │     → Agent 需对需要 accept 的 derivation 重新 evaluate
  │     → 新 evaluate: cache.store(agent_session_id, runtime_session_id', candidates)
  │
  └─ 7. 就绪（降级模式）
       → 读 tool 正常（schema/claims/rules 通过 ledger_path 恢复）
       → draft 正常
       → candidate accept 需重新 evaluate（降级）
```

### 6.3 恢复探测逻辑

```python
def recover_agent_session(burr_db_path: str, runtime_api_base: str) -> AgentSession:
    """
    统一恢复入口。自动判断 warm/cold 并执行对应路径。
    """
    # 1. 加载 checkpoint
    session, draft_mgr = load_from_burr(burr_db_path)

    # 2. 探测 runtime session
    try:
        resp = runtime_api.get_session(session.runtime_session_id)
        if resp.get("ok") is True:
            # Warm reconnect
            session.status = "active"
            session.touch()
            checkpoint_store.save(session, draft_manager)
            return RecoveryResult(
                session=session,
                draft_manager=draft_manager,
                candidate_cache=cache,
                mode="warm",
                stale_candidates=[],
            )
    except AgentRuntimeError:
        pass

    # 3. Cold restart — 用保存的完整 DTO 重建
    if session.bootstrap_spec is None:
        raise AgentRecoveryError("No bootstrap spec saved; cannot cold restart")

    resp = runtime_api.open_session(dict(session.bootstrap_spec.open_dto))
    old_runtime_id = session.runtime_session_id
    session.runtime_session_id = resp["session"]["session_id"]
    session.status = "active"
    session.touch()

    # 4. Stale candidates 自然保留——不 evict，不迁移
    stale = cache.list_stale(session.agent_session_id, session.runtime_session_id)
    checkpoint_store.save(session, draft_manager)

    return RecoveryResult(
        session=session,
        draft_manager=draft_manager,
        candidate_cache=cache,
        mode="cold",
        stale_candidates=stale,
    )
```

### 6.4 Ledger 持久化对恢复的影响

| Ledger 模式 | Warm reconnect | Cold restart |
|-------------|---------------|-------------|
| `:memory:` | 正常（进程内） | **数据丢失**——ledger 内容不可恢复。draft 可恢复但已 committed 的事实丢失 |
| 文件路径 | 正常 | 正常——open_runtime_session 重新加载 ledger 文件 |

**建议**：生产环境必须使用文件路径模式。`:memory:` 仅用于测试。

---

## 7. 目录结构

```
src/factpy_kernel/agent/
  ├── __init__.py
  ├── errors.py               # AgentContractError / AgentRuntimeError / recovery errors
  ├── session.py              # AgentSession, RuntimeBootstrapSpec
  ├── draft.py                # DraftManager, FactDraft
  ├── candidate_cache.py      # CandidatePayloadCache
  ├── recovery.py             # recover_agent_session, warm/cold 逻辑
  ├── framework.py            # Layer1AgentSkeleton, tool registry, optional dependency probe
  ├── docs/
  │   └── README.md           # 当前 agent 模块实现文档
  ├── tools/
  │   ├── __init__.py
  │   ├── _runtime_api.py     # LocalRuntimeAPI / HttpRuntimeAPI adapter
  │   ├── kg_read.py          # KGReadTools
  │   └── explain.py          # ExplainTools

src/factpy_kernel/tests/
  ├── test_agent_layer1_models.py
  └── test_agent_layer1_tools.py
```

---

## 8. 实现顺序

```
Step 1: AgentSession + RuntimeBootstrapSpec
        → 纯数据模型 + 序列化/反序列化
        → 不依赖任何外部组件

Step 2: CandidatePayloadCache
        → 独立 SQLite 表
        → 纯 CRUD + evict
        → 不依赖 Burr

Step 3: DraftManager
        → 纯内存 CRUD + 状态流转
        → to_checkpoint / from_checkpoint
        → 不依赖 Burr（只定义序列化格式）

Step 4: KGReadTools + ExplainTools
        → 对 runtime_v1 端点的 adapter 包装
        → 支持本地 in-process adapter；HTTP transport 为可选 stdlib urllib 实现

Step 5: Recovery
        → 组合 Step 1-4
        → warm/cold 探测 + 恢复逻辑

Step 6: Burr 集成
        → Layer 1 先落纯 Python checkpoint store + framework skeleton
        → 状态机定义（IDLE/INTENT/...，Layer 1 仅固定序列）
        → PydanticAI/Burr/Langfuse 只做 optional dependency probe + plumbing，不发 model call
```

---

## 9. 已知约束

1. **Burr SQLite schema 兼容性**：Burr 有自己的 SQLite 表结构。CandidatePayloadCache 在同一 DB 中创建自己的表。需确认 Burr 不会 DROP 非自身的表。
2. **Cold restart 后 candidate 不可直接 accept**：这是 kernel 的限制（candidate 绑定 session），不是 agent 的 bug。Agent 需向用户解释 "需要重新评估"。
3. **get_entity_snapshot 的 N+1 查询**：遍历所有 pred_id × e_ref 可能产生大量 API 调用。Layer 1 先不优化；Layer 2 可引入批量查询。
4. **ExplainTools 的引擎分支**：get_tree 对 PyReason 返回 None，get_timeline 对非 PyReason 返回 None。Agent（Layer 2）需根据 summary.kind 决定调哪个。
5. **RuleSummary 不含 rule_label/head_pred_id/engine**：runtime inventory 不返回这些字段。如需用于用户展示，Layer 2 需从 spec（include_spec=true）中提取或从 registry 查询。
6. **ExplainSummary 是 raw envelope**：Layer 1 不做跨引擎统一。消费方需按 `kind` 分支处理 `summary` dict 的内部结构。Layer 2 可叠加 normalized helper。
7. **open_runtime_session 的 DTO 可能包含大型 schema_ir**：RuntimeBootstrapSpec 保存完整 open_dto。如果 schema_ir 极大（数百 KB），cold restart 时反序列化可能有延迟。生产环境建议优先使用 `registry_root` 而非内联 schema_ir。
8. **Layer 1 未接真实 Burr/PydanticAI**：当前实现使用纯 Python checkpoint store + framework skeleton，保留未来替换点但不引入强依赖。
9. **HTTP transport 使用 stdlib urllib**：蓝图中的 adapter 已落为本地 in-process 默认 + 可选 urllib HTTP transport，而不是 `httpx` client。

---

## 10. Outcome / Deviations

### Delivered

- 新建 `src/factpy_kernel/agent/` Layer 1 模块：
  - `session.py`
  - `draft.py`
  - `candidate_cache.py`
  - `errors.py`
  - `recovery.py`
  - `framework.py`
  - `tools/_runtime_api.py`
  - `tools/kg_read.py`
  - `tools/explain.py`
- 新建模块文档：
  - `src/factpy_kernel/agent/docs/README.md`
- 新建测试：
  - `src/factpy_kernel/tests/test_agent_layer1_models.py`
  - `src/factpy_kernel/tests/test_agent_layer1_tools.py`

### Key Deviations

1. **未引入真实 Burr/PydanticAI/Langfuse 依赖**
   - 交付了纯 Python `AgentCheckpointStore` 与 `Layer1AgentSkeleton`
   - 保留 optional dependency probe / tool registry / tracing plumbing
   - 不实例化外部框架对象，也不发起 model call

2. **`KGReadTools.query_claims()` 放宽为 `pred_id` 可选**
   - 这是对 blueprint prose 的轻微扩展
   - 原因是 runtime `list_runtime_claims` 已支持 `pred_id=None`
   - 同时让 `get_entity_snapshot()` 能直接按 `e_ref` 读取整实体 claims

3. **`get_entity_snapshot()` 采用 `encode_idref_v1 + query by e_ref`**
   - 不做“按 entity_type 关联 predicates 再逐个 fan-out 查询”
   - 这样更贴当前 runtime surface，也避免 Layer 1 过早引入 N+1 模式

4. **`ExplainTools.get_timeline()` 含兼容性 fallback**
   - 对当前 runtime 在非 timeline 候选上的伪 unsupported 异常做 adapter 侧兜底
   - 若 summary.kind 不是 timeline_summary，则返回 `None`

### Validation

- `python -m py_compile` 覆盖新 agent 文件与新测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_layer1_models src.factpy_kernel.tests.test_agent_layer1_tools`：通过（17 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（771 tests）
