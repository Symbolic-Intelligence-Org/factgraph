# Identity 与数据模型重设计（已归档 / superseded）

- Status: **archived 2026-05-28** — 已被拆分为 3 份独立 design-points 取代
- Authority: **historical exploration draft / superseded** — 不再代表当前设计;具体设计内容看下方"取代关系"指向的新 doc
- First draft: 2026-05-27
- Archived: 2026-05-28
- Scope (历史): Identity 机制重设计 + 底层数据模型精简的 umbrella draft
- Parent: 起源于 `docs/references/working/change-requests-2026-05-27/change-requests.md` 的逐项 PDF triage 讨论

## 取代关系（archive note 2026-05-28）

本 umbrella draft 在 2026-05-28 拆分为 3 份独立 design-points,本档作为历史 exploration 归档保留:

| 取代后的 doc | 承担本档的哪部分 |
|---|---|
| [`identity-mechanism-redesign.zh.md`](../active/identity-mechanism-redesign.zh.md) | Identity 半边:entity_ref opaque 化 / identity-as-facts / Schema 声明(Form I) / SDK API 表面分层(§12 AssertionView 统一) / 唯一性 / lookup / 历史 / Adapter 边界 |
| [`ledger-schema-specification.zh.md`](../active/ledger-schema-specification.zh.md) | Ledger schema 半边:claim-first immutable payload / claims+claim_meta+ledger_meta 三表 / INV-1 至 INV-15 / 7 条数据精简 migration |
| [`append-only-ledger-evaluation.zh.md`](../active/append-only-ledger-evaluation.zh.md) | append-only 范式 10 维度 best-practice 评估 + future gap (GDPR / bitemporal / compaction) |

本档不再更新。新决策、设计变更、本节"取代关系"映射的疑义,请到上面 3 份 doc 中查找。

---

**以下为历史 draft 内容,保留原始措辞和议题列表作为决策来源。** 实际现行设计以上述 3 份 doc 为准。

## 目录

```text
§1   目的
§2   范围
§3   动机
§4   不变量
§5   底层数据模型（已 draft 2026-05-27）
§6   数据精简提案（待 draft；§5 已锁定终态 schema 与契约，§6 展开 delta 与 migration 影响）
§7   Identity 重设计（待 draft）
§8   决策日志
§9   迁移路径（待 draft）
§10  关联文档与代码锚点
§11  写作节奏与当前状态
```

---

## §1 目的

这份 essay 承载两条相关但独立的议题：

1. **Identity 机制重设计** — 让 GNF 启蒙的两条核心原则（Things-not-Strings、Indivisibility of Facts）在 FactGraph 中真正落地，同时保持 append-only ledger 的可审计特性。
2. **底层数据精简** — 趁 Identity 重设计触动 ledger 写入路径的窗口，把 `meta_rows` ↔ `annotation_rows` 双写、`namespace` / `category` 多维分类机制、`claims` ↔ `revokes` 不对称、`rest_terms` JSON list 形态这几条历史累积包袱一起收口。

两条议题在同一份 essay 是因为 Identity 重设计的实现路径会经过 ledger 写入层，搭车做数据精简的边际成本低；分散到两份 essay 则需要协调两条 migration 时序，更复杂。

**这份 essay 不解决**：性能 benchmark、具体迁移工具实现、SDK 上层 API 形态调整（这些是后续 blueprint 期任务）。

**精简终态 schema 见 §5**（2 张数据表 + 2 张 infra 表 = 4 张总表）；下游代码耦合的影响面调研单独执行（subagent 报告 - 见 §11.2）。

---

## §2 范围

### §2.1 IN scope（本 essay 处理）

| 议题 | 范围说明 |
|---|---|
| **底层数据文档化** | `claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` 5 张数据表 + `ingest_keys` / `ledger_meta` 2 张 infra 表 + asrt_id 依赖链 + 写入/读取/撤销流 + 协议层（tup_v1 / idref_v1） |
| **数据精简 1** | `meta_rows` ↔ `annotation_rows` 收一份（annotation_rows 接管 canonical 角色） |
| **数据精简 2** | `annotation_rows.namespace` / `category` 多维分类机制下沉。`accept` / `accept_many` 退场后多 namespace 写入源消失；与"数据精简 1"合并为单一 fact_meta 表是终态目标 |
| **数据精简 3** | `claims` ↔ `revokes` 不对称统一（revoke 改为特殊 `pred_id` 的 Claim） |
| **数据精简 4** | `claims.rest_terms` ↔ `claim_args` 双存收口（value + value_tag 内联到 claims，`claim_args` 表删除）。前提是 INV-9（unary commitment）确立，详见 §4.9 |
| **Identity 重设计** | entity_ref 分配策略、identity-as-facts 落地、唯一性约束声明、lookup 索引、Things-not-Strings + Indivisibility 实现路径 |

### §2.2 OUT of scope（显式拒绝）

| 议题 | 拒绝理由 |
|---|---|
| `ledger_meta` / `ingest_keys` 重构 | 它们不是数据冗余，是 infra；分离关注 |
| 新增 `annotation_rows` 字段 / 新增 category 维度 | 本 essay 方向是简化收口，不是新增 schema 字段 |
| `adapters/{problog,pyreason,souffle}` 内部投影 | engine 适配器内核，与 ledger 数据模型解耦 |
| audit package format / round_events.jsonl 格式 | audit 层独立，不在 ledger 模型范围 |
| view / policy 层 chosen 算法变更 | 它们读 ledger 但不定义 ledger schema |
| service / wire / DTO 形态 | application/sdk 上层，独立议题 |
| 性能 benchmark / 实测迁移成本 | 设计期不验，blueprint 期再验 |
| 具体 migration 工具实现 | 落 blueprint 后再展开；本 essay 仅给"迁移可行路径" |

### §2.3 边界检验问题（每写一段问一次）

- 这一段是否在描述/修改 ledger 5+2 张表 + 协议层 + 写入流？→ IN
- 这一段是否在描述/修改 view / policy / audit / adapter？→ OUT
- 这一段是否涉及 benchmark / migration 实现？→ OUT
- 这一段是否触及 SDK 公开 API 形态？→ OUT（与本 essay 解耦；blueprint 期再设计）
- 模糊地带 → 列入 §8 决策日志的"待裁定边界"，不擅自包含

---

## §3 动机

### §3.1 Identity 机制的三条不满（2026-05-27 讨论中提出）

| # | 不满 | 代码证实 |
|---|---|---|
| **#1** | ID 单向 — `HASH(I1, I2, ...) → ID` 不可反推 | [`idref_v1.py:67-73`](../../../../src/factgraph/core/protocol/idref_v1.py) `sha256(canonical_bytes).b32_nopad_lower()` |
| **#2** | Identity 字段"用完即扔" — 仅参与 ID 构建，之后不作为 fact 存在 ledger 中 | [`facade.py:549-582`](../../../../src/factgraph/sdk/facade.py) `sdk_get` 路径用 `known_identity_values=identity_kwargs` 从调用者 echo 回 identity 值；存在性走 `<T>:exists` assertion，不走 identity-fact |
| **#3** | `Identity(primary_key=True)` / `Identity`（非 primary）/ `Field` 三层划分薄弱 | 在 [`encode_idref_v1`](../../../../src/factgraph/core/protocol/idref_v1.py) 中，所有 identity_fields 不论 `primary_key` 都同等参与 hash；二者在 ID 计算层面没差别 |

三条不满的共同根源：当前 Identity 机制把 identity **值**编码进 entity_ref **字符串**，identity 不作为 first-class 数据存在。

### §3.2 GNF 启蒙与未尽事项

FactGraph 的 Identity 与 Entity 设计部分启蒙自 Relational.ai 的 Graph Normal Form（GNF）。GNF 的两条核心原则：

- **Things not Strings**：实体身份独立于初始命名。例：城市从 "Bombay" 改名 "Mumbai" 仍是同一个 Thing；其 entity 身份不应因字符串变更而变成两个 entity。
- **Indivisibility of Facts**：一个关系模板最多一个 value column；多 value 应拆为多个一元关系。

当前 FactGraph 实现状态：

| 原则 | 实现状态 | 失败方式 |
|---|---|---|
| Things not Strings | ❌ **未实现** | entity_ref = `idref_v1:{type}:{hash(identity_tuple)}`；identity 字符串变 → hash 变 → entity_ref 变 → 在系统中变成两个不同 entity |
| Indivisibility of Facts | ⚠️ **半实现** | 单条 `Claim(asrt_id, pred_id, e_ref, rest_terms)` 在 SDK 层确实只承载一个 value；但 identity 值们被打包进 hash 输入，作为一个聚合参与 ID 构建，未拆为独立 fact |

用户笔记（obsidian `symb-Intelli./case-studies/palantir/7_FactPy Kernel 启示.md`）已记载 "GNF" 词汇**不作为对外营销词**使用（理由：在代码中没实现，且是 RelationalAI 的术语）。本 essay 引用 GNF 仅作为**内部设计纪律的启蒙**，不引入对外用语承诺。

### §3.3 数据模型累积冗余

讨论 Identity 重设计触及 ledger 写入路径时，对当前数据模型（[`ledger.py`](../../../../src/factgraph/core/store/ledger.py) + [`core/docs/01_architecture.en.md §4`](../../../../src/factgraph/core/docs/01_architecture.en.md)）做了一次 source-grep 审视。发现两条结构性冗余 + 一条与 `accept`/`accept_many` 共退场的多维分类机制 + 一条不对称：

| 议题 | 性质 | 历史背景 |
|---|---|---|
| `meta_rows` ↔ `annotation_rows` 部分双写 | 显式过渡态冗余 | `annotation_rows` 为 2026-03-26 引入的 canonical 层；架构 doc 自标 `meta_rows` 是 "Legacy Compat layer"。当前 7 个白名单 meta key 双写两表 |
| `annotation_rows.namespace` / `category` 多值机制 | 设计 capacity 落地极窄 + 写入源即将消失 | 设计意图："adapter 私有 lane + shared baseline + 优先级 fallback"；实际只在 ProbLog `_claim_probability` 一处真用完整模式。`derived` / `operational` category 零写入；非 `shared` namespace 的写入源全部经 `accept_problog_session` / `accept_pyreason_session` → `persist_*_annotations` 链路，`accept` 进入待清理后多 namespace 机制失去存在理由 |
| `claims` ↔ `revokes` 结构性不对称 | 设计选择，可统一可不统一 | revoke assertion 不产生 Claim 行，只产生 Revokes 边 + meta/annotation；reader 必须意识到 asrt_id 可能指向 Claim 也可能指向 Revokes |
| `claims.rest_terms` ↔ `claim_args` 同 data 双存 | 性能 denormalization | 业界常见模式；rest_terms 是 JSON 文本，claim_args 是行展开供索引查询 |

全部四条在 Identity 重设计触动 ledger 写入路径时一并收口，边际成本低。第四条（`rest_terms` ↔ `claim_args`）原本列为 OUT scope，2026-05-27 讨论中因 unary commitment（INV-9）的确立而反转纳入：unary 模型下 `claim_args` 行展开退化为冗余（每条 Claim 永远 0 或 1 args），与 `claims.rest_terms` JSON 列合并为 inline `value` + `value_tag` 双列后两表化一。

**设计哲学背景**：新的 `evaluate` 设计是"用户基于 evaluate 结果自行构造新项"，而非 `accept` / `accept_many` 时代的"系统自动落 candidate 为 assertion 并附带 engine-specific annotation"。accept-style 路径在 [`src/factgraph/sdk/docs/04_api_surface.en.md §2.9`](../../../../src/factgraph/sdk/docs/04_api_surface.en.md) 中被显式列为 "Removed legacy evidence shells"。namespace/category 多维分类原本是给后者服务的；前者下用户驱动所有写入，所有 provenance 由用户提供的 `meta` 携带，多 namespace 标签机制失去用武之地。

---

## §4 不变量

不变量是本 essay 范围内**必守的设计约束**。任何违反这几条的提案都不在 IN scope 内；如果某条提案需要松动某条不变量，必须先把该条不变量改写或下移到决策日志。

不变量按"层级从底到顶"列出。

### §4.1 INV-1：Append-only ledger

> 任何"删除"通过新 assertion 实现，原行永不就地修改。

**适用范围**：`claims` / `claim_args` / `meta_rows` / `annotation_rows` / `revokes` 5 张数据表。

**理由**：
- FactGraph 全栈的可审计性建立在此不变量上 — 历史可重放、可回溯、可解释
- 用户 2026-05-27 讨论中明确："如果我们坚持可审计的特性, 那 identity 不应该能够简单的 mutable, 而是通过类似 field 的 retract 和 write 的方式实现"

**含义**：
- Identity 重设计中，identity 变更走 retract + 新 write，不允许 in-place update
- 数据精简方案不能引入"覆盖式写入"语义

### §4.2 INV-2：asrt_id 全局唯一

> 每条 ledger 写入（包括撤销）对应一个 UUID4 hex 形式的 asrt_id；所有附加数据（meta / annotation / args / revokes 边）以 asrt_id 为关联键。

**适用范围**：全部 ledger 表。

**理由**：
- asrt_id 是当前 ledger 唯一的 join 根
- 改动 join 根的拓扑等于重做 ledger，超出本 essay scope

**含义**：
- entity_ref 重设计后仍需在 ledger 内有"per-write 唯一 ID"的概念
- 新机制不能引入"无 asrt_id 的旁路写"

### §4.3 INV-3：SQLite 单事务原子写

> 一个 user-level 写入（如 `fg.write.set(...)`）= 一个 SQLite transaction。

**适用范围**：[`Ledger.append_assertion`](../../../../src/factgraph/core/store/ledger.py) / `Ledger.append_revocation` / `Ledger.append_annotations`。

**理由**：
- 这是 ledger 一致性的底线 — 不能出现"Claim 写了但 meta 没写"的部分态
- 当前实现已是此模式

**含义**：
- Identity-as-facts 落地后，"创建 entity + 写第一批 identity facts"也必须在单 transaction 内完成（不能两步走，否则中间态 entity 存在但无 identity）

### §4.4 INV-4：协议层 tup_v1 字节级 canonical 不变

> [`tup_v1.py`](../../../../src/factgraph/core/protocol/tup_v1.py) 的 8 种 canonical tag（`string` / `int` / `float64` / `bool` / `bytes` / `time` / `uuid` / `entity_ref`）集合不增减；字节编码格式不变。

**适用范围**：[`canonical_bytes_tup_v1`](../../../../src/factgraph/core/protocol/tup_v1.py)。

**理由**：
- tup_v1 是跨语言/跨平台数据可移植性的基础
- v0.1.0-rc.1 export package 已用此格式

**含义**：
- entity_ref 形态可改（idref_v2 或类似），但只是 `entity_ref` tag 编码的 value 字符串格式变化，不动 tag 集合本身
- claims/revokes 统一（精简 3）**不破** INV-4：revoke Claim 的 value 用 `string` tag 承载被撤销 asrt_id，无需新增 `asrt_ref` tag（详见 §5.2 Claim 形态枚举）
- 8 种 canonical tag 在 SQL `value` 列的 canonical text 编码契约见 §5.4
- 如果未来真出现需要新 tag 的场景，必须先 escalate 到本不变量是否松动 — 默认不松

### §4.5 INV-5：Ledger 是 source of truth，in-memory 索引可重建

> SQLite 表是 truth；in-memory indexes 是 read cache / derived state，可在启动时从 ledger 重建。

**适用范围**：当前所有 in-memory 结构（policy / view / annotation index 等）。

**理由**：
- 这是 ledger 设计的根性质，确保灾难恢复能力
- 当前实现严格守此（[`core/docs/01_architecture.en.md §4.2`](../../../../src/factgraph/core/docs/01_architecture.en.md)）

**含义**：
- Identity lookup 索引若新增，必须可从 ledger 重建（不能成为独立 truth 来源）
- 数据精简收口后的新 schema 必须支持"从历史 ledger 重建索引"

### §4.6 INV-6：公开 SDK 路径不引入新 substrate vocabulary

> 来自 [`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md)：所有新增 runtime capability 先以 DTO + pure function 形式落在 `application`（`factgraph.application`）层；SDK 仅作为 product surface / ergonomic shell，不携带 substrate。

**适用范围**：本 essay 提出的任何 SDK 层 API 变更。

**理由**：
- 已有 application-first runtime authority 规范
- 防止 SDK 累积 substrate 概念，使跨语言 wire / 服务集成混乱

**含义**：
- Identity 重设计的运行时实体必须先在 `factgraph.application` 层定义
- SDK 上的 `Entity` / `Field` / `Identity` 描述符只是 application DTO 的语法糖

### §4.7 INV-7：Identity 变更可审计

> Identity 的"变更"（含新增 identity 字段、修改值、移除）必须走 ledger assertion 生命周期（retract + write），留完整 ledger 轨迹；不允许"静默替换"或"in-place update"。

**适用范围**：identity-as-facts 落地后的 identity field 写入路径。

**理由**：
- 用户 2026-05-27 讨论中明确要求："保持 audit 的特性"
- 这是 FactGraph 区别于其他系统的核心承诺

**含义**：
- Bombay → Mumbai 类 rename = retract 老 identity-fact + write 新 identity-fact，两条 assertion 都在 ledger 中
- 不能引入"identity update RPC"之类的 in-place 操作

### §4.8 INV-8：已发布 idref_v1 token 兼容路径

> v0.1.0-rc.1 已发布的 idref_v1 token 必须在新模型上线时**仍可被读取**（即"老 entity 还能用"，即使新 entity 不再用这种 token）。

**适用范围**：entity_ref 重设计 + lookup 路径。

**理由**：
- v0.1.0-rc.1 是已发布的 release candidate；外部消费者可能持有 idref_v1 token
- 完全断裂式迁移对生态破坏过大

**含义**：
- 新 entity_ref 形态（idref_v2 或类似）可与 idref_v1 共存
- Lookup 路径必须能识别两种 token 并分别处理
- **没有承诺**：永久向前兼容、新 entity 也用 idref_v1、idref_v1 token 也支持 identity-as-facts

**待裁定**：
- 旧 idref_v1 entity 是否需要"反向构造 identity-fact assertion"（migration 时回填）？还是接受"老 entity 没有 identity-fact，只能凭 ref 用"？详见 §9。

### §4.9 INV-9：Ledger Claim 是 unary fact

> 每条 `claims` row 严格表达 `(asrt_id, pred_id, e_ref, value?, value_tag?)` 的 unary 关系。n-ary 计算（Rule head 派生多 arity 事实等）仅存在于 in-memory evaluate 阶段；写入 ledger 必经过 unary 投影（拆分成多个 unary Claim）。

**适用范围**：`claims` 表 + `set_field` / `add_field` / `retract_by_asrt` 写入路径 + ledger 读取路径的 Claim 重组语义。

**理由**：
- 与新 evaluate-then-user-constructs 设计哲学一致（详见 §3.3 设计哲学背景 + §5）
- 让 ledger schema 收敛到极简的 4-tuple 形态（`(asrt_id, pred_id, e_ref, value, value_tag)`），无 list / 无 JSON / 无 variable arity
- 与 GNF "Indivisibility of Facts" 原则一致 — 每条 fact 是 indivisible 单位
- 用户 2026-05-27 讨论中明确接受："考虑到 asrt_id 是 unique 且和一次插入是强关联的，所有普通 claim 都严格是 'subject + 一个 value' 的 unary fact 并无太大问题"

**含义**：
- N-ary predicate（如 Datalog rule head `parent(alice, bob)`）必须 reify 为 entity-ref Field 或 Relationship 实例后再写入；不允许作为单条 Claim 的 multi-value rest_terms
- `claim_args` 表随此 commitment 一并删除（参见 §5）
- `tup_v1` 协议层仍保留 length>1 编码能力（INV-4 不变），但 ledger 写入路径永远只产生 length 0 或 1
- 这条 commitment 显式关闭 Datalog-style n-ary fact 作为 ledger 一等公民的留口；承担这一代价以换取 schema 的极简

### §4.10 INV-10：`__system__.*` pred_id 命名空间预留

> 任何 user-facing 写入路径必须拒绝 `pred_id` 以 `__system__.` 开头的写入。该命名空间仅 ledger 内部机制可使用。

**适用范围**：所有 user-facing 写入路径 — `fg.write.set` / `fg.write.add` / `fg.schema.ingest` / application 层写入门面。internal API（如 `retract_by_asrt` 构造的 revoke Claim）走分离路径，绕开 namespace check。

**理由**：
- 精简 3 后撤销 = `pred_id="__system__.revokes"` 的 Claim
- 若 user 能伪造该 pred_id，可构造虚假撤销
- 命名空间预留 + 写边界校验是把 system predicate 从 "约定字符串" 升级到 "first-class system event" 的关键约束（详见 INV-11 - INV-15）

**含义**：
- 校验失败抛专用 `WriteProtocolError`，错误码标识 namespace violation
- 内部 system event 写入（retract 等）走与 user 写入分离的内部 API

### §4.11 INV-11：Revoke claim payload shape 固定

> Revoke claim 在 ledger 中的形态严格为：
> - `pred_id` = `"__system__.revokes"`
> - `e_ref` = 被撤销 fact 的 e_ref（便于按 entity 查撤销）
> - `value` = revoked_asrt_id 字符串
> - `value_tag` = `"string"`
> - `fact_meta` 与普通 claim 同样支持

**适用范围**：`retract_by_asrt` 实现 + 任何构造 revoke claim 的内部路径。

**理由**：
- 固定 shape 让 reader 不需要解析 schema 就能识别 revoke claim
- e_ref 复用让 "按 entity 查所有撤销" 走 `(pred_id, e_ref)` 现有索引
- payload shape 固定也是 INV-15 查询性能依赖

**含义**：
- 不允许 revoke claim 有 0-arity / 其他 value_tag / 缺 e_ref 等变体
- shape 校验在 `retract_by_asrt` 入口完成

### §4.12 INV-12：Revoke target 约束（v1 严格）

> Retract 操作的 target asrt_id 必须：
> 1. 存在于 ledger（`get_claim(asrt_id) is not None`）
> 2. **target 必须是非 system claim**（`pred_id` 不以 `__system__.` 开头）

**适用范围**：`retract_by_asrt` 校验路径。

**理由**：
- 禁止撤销 system claim — 防止"revoke-of-revoke = 重新激活"语义，因为 reactivation 会把 active projection 从"集合差"升级为"只应用 active revoke claims"的二阶逻辑，复杂度跳一级
- 第一版严格禁止；reactivation / correction-of-correction 是独立未来设计议题，需要专门 INV + 配套 active projection 算法

**含义**：
- target 是 system claim 时 retract 抛错（专用错误码 `REVOKE_SYSTEM_CLAIM_FORBIDDEN`）
- 重复 retract 同一 target 不抛错，返回既有 revoker_asrt_id（详见 INV-14）

### §4.13 INV-13：Active projection 单一 truth 源

> active factual claims 的计算遵循唯一公式：
>
> ```
> active factual claims =
>     {c ∈ claims : c.pred_id NOT LIKE '__system__.%'}
>   MINUS
>     {c.value : c ∈ claims AND c.pred_id = '__system__.revokes'}
> ```
>
> 不允许引入第二 active 信号（如 soft flag 列、独立 active 状态表）。

**适用范围**：所有 read path 的 active 计算 + in-memory `_revoked_asrt_ids` set 的维护。

**理由**：
- INV-5 (ledger 是 source of truth) 在 active 维度的具体化
- 单一公式让 active 始终可以从 claims 表纯函数计算 / rebuild
- **system claims 自身的 active 状态不混入事实语义** — 这是关键收紧点：active 只针对 factual claims，不针对 system claims；公式左右两边的 scope 不同
- 与 INV-12 配套：因 system claim 不可被 revoke，"system claim 是否 active"在 v1 是无意义概念（永远 active），不参与事实公式

**含义**：
- in-memory `_revoked_asrt_ids` set 是公式右半边的投影 cache
- 任何"add 一个 active flag 列" / "在 fact_meta 写 `active=false`" 类提案违反 INV-13，应被拒绝
- 计算 active 不允许走 SQL CAST 之外的隐式状态

### §4.14 INV-14：Revoke 幂等性行为契约

> 重复 `retract_by_asrt(target_asrt_id)` 同一 target 必须**返回既有 revoker_asrt_id**，不产生第二条 revoke 记录。

**适用范围**：`retract_by_asrt` 实现。

**理由**：
- 幂等保证是 caller 不需要协调"该 target 是否已被 revoke"
- 与 INV-2 (asrt_id 全局唯一) + INV-3 (atomic write) 配套保证撤销操作的可重复性

**含义**：
- 这是**行为契约**，实现可以演化：
  - 当前模型（[`write_protocol.py:170-208`](../../../../src/factgraph/core/evidence/write_protocol.py)）：`retract_by_asrt` 传 `idempotency=None`，靠 `find_revoker(revoked_asrt_id)` 短路实现幂等；不走 `ingest_keys`
  - 精简 3 后：revoke 变成 `pred_id="__system__.revokes"` 的 Claim，**自动走 set_field 的 ingest_keys 标准幂等路径**，无需专用短路
- 两阶段实现机制不同但**幂等行为契约不变**；任何阶段的测试应针对契约写，不针对内部短路实现
- 注意：当前 INV-14 不要被误读为"retract 走 ingest_keys" — 那是精简 3 后的实现细节，不是当前事实

### §4.15 INV-15：普通查询默认 filter system claims

> `fg.read.*` 系列 API 默认查询结果不包含 system claims（`pred_id` 以 `__system__.` 开头者）：
> - `fg.read.snapshot` / `fg.read.find` / `fg.read.match` 等返回的 claim 集合默认 filter 掉
> - 需要观察 system claim（如审计撤销历史）走 `fg.audit.*` 专用 API

**适用范围**：所有公开 SDK 读取路径。

**理由**：
- 普通业务查询不应感知 ledger 内部撤销机制
- system claims 是 ledger 元数据，不应混入业务事实流
- 审计场景走 `fg.audit.explain_fact` / `fg.audit.diff_proof_frames` 等专用入口

**含义**：
- SQL 实现：`WHERE pred_id NOT LIKE '__system__.%'` 作为默认 filter（与 INV-13 公式左半边一致）
- 任何"绕过 filter 取 raw claims"的 SDK API 必须显式命名标注，让 reader 一眼看出在看 system claims
- in-memory cache / index 可能要分两份（fact claims index + system claims index）保持各自性能

### §4.16 不变量适用范围说明

这 15 条不变量是**为本 essay 的设计探索而锁定**的约束，不是 FactGraph 永久不可动摇的公理。

- INV-1 / INV-2 / INV-3 / INV-5 是 FactGraph 设计哲学层面的承诺，跨 essay 长期有效
- INV-4 / INV-6 是当前实现版本的约束，可在未来重大版本（如 v0.3+）重新评估
- INV-7 / INV-8 / INV-9 是本 essay 议题特异的约束，源自 2026-05-27 讨论的明确诉求
- **INV-10 - INV-15 是 system predicate revoke 模式的 institutionalization 约束族**：把 `__system__.revokes` 从 "约定字符串" 升级为 "first-class ledger system event"，确保撤销机制达到 Datomic / Event Sourcing 同等专业度

任何后续章节（§5-§9）如发现需要松动其中某条，必须：

1. 在涉及章节末尾添加"松动评估"小节，说明哪条不变量、为什么、影响范围
2. 更新 §8 决策日志
3. 等待用户审阅后才能在后续章节按"松动后"的规则展开

---

## §5 底层数据模型

> **状态**：working / 已完成首版整理（2026-05-27）。本章节锁定 ledger 数据模型的最终目标形态、SQL 编码契约、digest path 纪律和 implementation discipline。所有后续章节（§6 数据精简提案、§7 Identity 重设计、§9 迁移路径）以此为稳定底座。

### §5.1 演化总览

当前 ledger 形态（详见 [`src/factgraph/core/store/ledger.py`](../../../../src/factgraph/core/store/ledger.py) + [`src/factgraph/core/docs/01_architecture.en.md §4`](../../../../src/factgraph/core/docs/01_architecture.en.md)）：

```text
[5 张数据表]
  claims          (seq, asrt_id, pred_id, e_ref, rest_terms TEXT)
  claim_args      (asrt_id, idx, val_atom, tag)
  meta_rows       (asrt_id, key, kind, value)
  annotation_rows (asrt_id, namespace, category, key, kind, value, origin, derivation)
  revokes         (revoker_asrt_id, revoked_asrt_id)

[2 张 infra 表]
  ingest_keys, ledger_meta
```

精简后目标形态：

```text
[2 张数据表]
  claims    (seq, asrt_id, pred_id, e_ref, value, value_tag)
  fact_meta (id, asrt_id, key, value, value_tag, origin)

[2 张 infra 表]
  ingest_keys, ledger_meta
```

**5 → 2 张数据表**。变化通过 §6 中的 4 条数据精简实现；本章节定义**精简后**的 schema 契约。

### §5.2 Claim 数据结构

`claims` 表是 ledger 的核心 fact 载体。每条 row 表达**一条 unary fact**。

| 列 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `seq` | INTEGER | PRIMARY KEY AUTOINCREMENT | 物理写入序载体 / SQLite rowid alias；按 `ORDER BY seq` 实现"按写入时间顺序遍历" |
| `asrt_id` | TEXT | NOT NULL UNIQUE | **逻辑 PK** / 全 ledger join 根；UUID4 hex 形式 |
| `pred_id` | TEXT | NOT NULL | 谓词标识，schema 层约定（如 `"User:name"`、`"__system__.revokes"`）|
| `e_ref` | TEXT | NOT NULL | 主语 entity ref（如 `"idref_v1:User:abc..."` 或新协议 token；详见 §7 entity_ref 重设计）|
| `value` | TEXT | NULLABLE | 事实 value 的 SQL canonical text 编码；为 NULL 时表示 0-arity（如 `__exists__` 类断言）|
| `value_tag` | TEXT | NULLABLE | value 的类型 tag（8 种 tup_v1 canonical tag 之一）；与 value 同步 NULL/非 NULL |

#### 核心 commitment（INV-9）

每条 `claims` row 严格是 **unary fact** — 即 `(subject=e_ref, predicate=pred_id, value=value)` 的三元结构（含 value 为 NULL 的 0-arity 边界 case）。详见 [§4.9](#49-inv-9ledger-claim-是-unary-fact)。

#### Claim 形态枚举

| 形态 | value | value_tag | 例 |
|---|---|---|---|
| 普通 value field | 非 NULL canonical text | 8 种 tag 之一（非 entity_ref）| `("Alice", "string")` |
| Entity-ref field | 非 NULL ref string | `"entity_ref"` | `("idref_v1:User:bob...", "entity_ref")` |
| Multi-cardinality field 每一项 | 同上 | 同上 | 多 row，同 pred_id + e_ref |
| Existence 断言 | NULL | NULL | `(NULL, NULL)`，pred_id 为 `<EntityType>:__exists__` |
| Revoke fact | revoked asrt_id 字符串 | `"string"` | `("9f3a...", "string")`，pred_id=`"__system__.revokes"` |

### §5.3 fact_meta 数据结构

替代当前 `meta_rows` + `annotation_rows` 两表。承载**每条 fact 之上的元数据**（source / trace_id / raw_kind / bound 等）。

| 列 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 物理 rowid |
| `asrt_id` | TEXT | NOT NULL | 关联到 `claims.asrt_id` |
| `key` | TEXT | NOT NULL | meta key（如 `"source"`、`"raw_kind"`） |
| `value` | TEXT | NOT NULL | meta value 的 SQL canonical text 编码（与 `claims.value` 同规则）|
| `value_tag` | TEXT | NOT NULL | meta value 的 canonical 类型 tag（与 `claims.value_tag` 同语义）|
| `origin` | TEXT | NOT NULL DEFAULT 'observed' | `observed` / `derived`（保留 future capacity）|

约束：`UNIQUE(asrt_id, key)` — 同一 fact 上同一 meta key 唯一，写入是 upsert 语义。

#### 列名与 `claims` 的对齐

`fact_meta.value_tag` 与 `claims.value_tag` 是**同一概念** — 都是"text value 的 canonical 类型 tag"，故用同一列名。早期版本曾用不同列名（`fact_meta.kind` vs `claims.value_tag`）以"避免混淆"，2026-05-27 讨论中确认其实是同一概念，应当统一命名。

值集略有差异：

| 列 | value_tag 允许值 | 备注 |
|---|---|---|
| `claims.value_tag` | 8 种 tup_v1 canonical tag：`string` / `int` / `float64` / `bool` / `bytes` / `time` / `uuid` / `entity_ref` | 因 INV-9 unary commitment 严格限于 canonical 8 种，不允许嵌套结构 |
| `fact_meta.value_tag` | 上述 8 种 + `json`（用于嵌套结构如 `bound = [0.7, 0.9]`、`decision_path = [...]`） | meta 是 user-provided 元数据，允许复杂结构以兼容现有 meta 用法 |

`json` 在 fact_meta 是受控扩展，不污染 claims 的 canonical 集合。

#### 取消的列

`namespace` / `category` 两列**取消**：accept / accept_many 退场后多 namespace 写入源消失（详见 §3.3 + §6.2）。

`derivation` 列**取消**：原 annotation_rows 用，零写入。未来若需要恢复，与 `origin=derived` 配套设计单独的 derivation 链表，不放在 fact_meta 行内。

### §5.4 SQL value 列 canonical 编码契约

`claims.value` 列的 8 种 canonical tag 编码（与 `tup_v1.py` 字节级 canonical 互可转换，但 SQL 层用人类可读 + 可计算的 text 形式）：

| value_tag | SQL `value` 列编码 | 与 tup_v1 字节关系 |
|---|---|---|
| `string` | UTF-8 text 原文 | tup_v1: UTF-8 bytes（**相同形式**） |
| `int` | normalized decimal text（如 `"42"`、`"-7"`） | tup_v1: decimal ASCII（**相同形式**，由 `_int_to_canonical_text` 输出） |
| `float64` | finite shortest round-trip decimal | tup_v1: IEEE 754 raw 8 字节 big-endian（**不同形式，互可转换**） |
| `bool` | `"true"` / `"false"` | tup_v1: `\x01` / `\x00`（不同形式） |
| `bytes` | base64url 无 padding | tup_v1: raw bytes（不同形式） |
| `time` | epoch nanos decimal text（如 `"1738892400123456789"`） | tup_v1: int64 big-endian 8 字节，由 `struct.pack(">q", ...)`（**不同形式，互可转换**） |
| `uuid` | canonical lowercase UUID（`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`） | tup_v1: 16 raw 字节（不同形式） |
| `entity_ref` | 完整 ref 字符串（`"idref_v1:..."` 或新协议） | tup_v1: UTF-8 bytes（相同形式） |

#### `float64` normalization（写入路径强制）

`float64` value 在写入 SQL 前必须 **reparse-then-format**：

1. **finite 检查** — 拒绝 `NaN` / `±Inf`（与 `_float64_bits` 的 `math.isfinite` 检查对齐）
2. **`-0.0` normalize** — bits `0x8000000000000000` 转 `0.0`（与 `_float64_bits` 已实现的行为对齐）
3. **reparse-then-format** — Parse incoming text/value 为 float64 → 用 canonical formatter 输出；**不接受** `"1.2400"` 原样存

这保证：写入 → 读出 → 写入 ... 路径上 SQL canonical 字符串永远 bit-exact 等价。

Cross-language formatter（Python `repr(float)` / Rust `{:?}` / Go `strconv.FormatFloat(x, 'g', -1, 64)`）算法等价（Grisu / Ryu），但**边界 case 可能不一致**；详见 §5.6 golden tests 要求。

#### `time` 编码选择

SQL canonical 用 **epoch nanos decimal text**（与 `tup_v1` 字节编码对齐，计算友好），ISO 8601 留给 audit / UI **显示层**渲染：

| 用途 | 编码 |
|---|---|
| SQL 存储 (`claims.value`) | epoch nanos decimal text |
| Rule 计算（in-memory） | `int(value)` → nanos 整数，原生算术 |
| Tup_v1 canonical bytes | int64 big-endian 8 字节 |
| Audit / UI 显示 | display-time conversion 为 ISO 8601 UTC nanos（如 `"2026-05-27T14:30:00.000000000Z"`）|

不在 SQL 存 ISO 8601 的理由：Python `datetime` 在 3.12 前只有 microsecond 精度，9 位 nanos 需自写解析/格式化；`timestamp() * 1e9` 经过 float 会丢纳秒精度；ISO 多种合法表示 normalization 易写错。

#### 其他类型

- `int`：SQL canonical 与 tup_v1 ASCII 编码完全对齐，无需 reparse；只需 normalize（去前导零、负数带 `-`、零为 `"0"`）
- `string` / `entity_ref`：UTF-8 text 原样，无需 normalize
- `bool`：固定 `"true"` / `"false"`，无其他写法接受
- `bytes`：base64url（与 `tup_v1` 字节互可逆转换），无 padding（节省字符）
- `uuid`：固定 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` lowercase（由 `UUID_CANONICAL_RE` 校验）

#### `fact_meta.value_tag = "json"` 的编码（fact_meta 专属）

`json` 是 fact_meta 特有的 value_tag，用于承载嵌套结构。SQL canonical 编码规则：

- **canonical JSON 字符串**：sorted keys + no whitespace + UTF-8（不 escape ASCII 之外）
- Python 写入：`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- 数字编码遵循 JSON 标准；float / int 子集内部走 §5.4 的相应规则（float64 finite + `-0.0` normalize）
- 读取：`json.loads(value)` 还原 Python 对象

`json` 不出现在 `claims.value_tag`，因 INV-9 (unary fact) 不允许嵌套结构作为 fact value。如果某天需要"复合 fact value"，应建模为多个 unary Claim 或一个 entity-ref + 该 entity 自身携带 field（详见 §7）。

### §5.5 Digest path 纪律

**所有 digest / hash / 跨语言 wire 序列化必须经 `tup_v1` 字节层**，不允许走 SQL CAST 短路。规范路径：

```text
SQL 行（value: text, value_tag: text）
    ↓ parse 到 Python/Rust/Go 原生 typed value
    ↓ encode_value_bytes(value_tag, typed_value) → tup_v1 canonical bytes
    ↓ sha256 / blake3 / 其他 hash → digest
```

反例（**禁止**）：

```sql
-- ❌ 不要这样
SELECT sha256(value || value_tag) FROM claims;
-- ❌ 也不要这样
SELECT sha256(CAST(value AS REAL)::text) FROM claims;
```

理由：SQL 的 `CAST(text AS REAL)` 结果在 SQLite vs Postgres vs ... 可能微妙差异；text concat 跨平台不稳。digest 的 bit-exact 跨平台稳定性只能由 `tup_v1` 协议保证。

SQL CAST 可以用于**性能 path**（范围查询、partial index、generated column），但 CAST 结果**不可参与** digest 计算。

### §5.6 Implementation discipline

#### Cross-language float formatter golden tests

`float64` 的 "shortest round-trip decimal" 跨语言实现算法等价，但**边界 case 可能不一致**（subnormal、`1e-323`、`-0.0`、`5e-324` 等）。

实现必须建立 **golden tests**：

- 输入：一组固定 finite float64（含边界 case：max/min normal、min subnormal、`-0.0`、`1.0`、`0.1+0.2`、`1e-300`、`1e308` 等约 50-100 个）
- 期望：所有目标语言 implementation 输出**完全相同**的 decimal text
- 任一语言 formatter 违反 → 不允许接入

测试位置候选：`tests/protocol/test_float64_canonical_text.py`（Python）+ 跨语言时各自镜像。

#### asrt_id 生成

UUID4 hex 无 dashes，由 [`write_protocol.new_assertion_id`](../../../../src/factgraph/core/evidence/write_protocol.py) 生成。每次 `set_field` / `add_field` / `retract_by_asrt` 调用都产生一个新 asrt_id（INV-2）。

#### 写入原子性

每次 user-level 写入 = **一个 SQLite transaction**（INV-3）。原子写入跨表：

- 普通 set/add：写 1 行 claims + 0~N 行 fact_meta + 1 行 ingest_keys，单事务
- 撤销：写 1 行 claims（pred_id="__system__.revokes"） + 0~N 行 fact_meta，单事务

#### 索引基线

```sql
-- claims 主要索引
CREATE INDEX idx_claims_asrt_id ON claims(asrt_id);       -- 已有 UNIQUE
CREATE INDEX idx_claims_pred_eref ON claims(pred_id, e_ref);   -- 主查询模式
CREATE INDEX idx_claims_pred_value ON claims(pred_id, value);  -- 按 value 查询（如 identity lookup）
CREATE INDEX idx_claims_revokes ON claims(value) WHERE pred_id="__system__.revokes";  -- 撤销查询

-- fact_meta 索引
CREATE INDEX idx_fact_meta_asrt ON fact_meta(asrt_id);
CREATE INDEX idx_fact_meta_key ON fact_meta(key);
```

具体索引集合 + 性能特征在 blueprint 期再定，此处仅给基线。

### §5.7 写入 / 读取 / 撤销 流（新形态概览）

#### 普通写入

```text
fg.write.set(User.name, alice, "Alice", meta={"source": "import", "trace_id": "seed-001"})
    ↓
application/entity_write 层：
  - 解析 EntityRef alice → e_ref="idref_v1:User:abc..."
  - 解析 Field User.name → pred_id="User:name"
  - 解析 value "Alice" + Field.value_kind → ("Alice", "string")
    ↓
core/evidence/write_protocol.set_field(ledger, pred_id, e_ref, value, value_tag, meta)：
  - 生成 asrt_id（UUID4 hex）
  - 计算 ingest_key = hash(pred_id, e_ref, value, value_tag, meta)
  - 构造 Claim(asrt_id, pred_id, e_ref, value, value_tag)
  - 构造 fact_meta rows（系统 meta + 用户 meta；不再分白名单）
    ↓
ledger.append（单 transaction）：
  - INSERT claims
  - INSERT N fact_meta rows
  - INSERT ingest_keys
```

#### 撤销

```text
fg.write.retract(asrt_id, meta={"source": "manual-fix"})
    ↓
core/evidence/write_protocol.retract_by_asrt(ledger, revoked_asrt_id, meta)：
  - 检查 revoked_asrt_id 存在 + 未被撤销
  - 生成 revoker_asrt_id（UUID4 hex）
  - 构造 revoke Claim:
      Claim(
        revoker_asrt_id,
        pred_id="__system__.revokes",
        e_ref=<被撤销 fact 的 e_ref>,    # 便于按 entity 查撤销
        value=revoked_asrt_id,
        value_tag="string"
      )
  - 构造 fact_meta rows
    ↓
ledger.append（单 transaction）：
  - INSERT claims
  - INSERT N fact_meta rows
```

不再有独立的 `revokes` 表 — 撤销与普通 fact 在同一张 claims 上，通过 `pred_id` 区分。

#### 读取（按 entity + field）

```text
snap = fg.read.snapshot(User, user_id="u-1"); snap.name
    ↓
1. 由 (entity_type, identity_kwargs) 重算或查 e_ref（详见 §7 identity lookup 设计）
2. SELECT * FROM claims WHERE pred_id="User:name" AND e_ref=? → 候选 asrt_ids
3. SELECT value FROM claims WHERE pred_id="__system__.revokes" AND value IN (候选) → 已撤销集合
4. active asrt_ids = 候选 \ 已撤销
5. 按 cardinality 语义聚合：
   - single: 取 ORDER BY seq DESC 第一个 active 的 value
   - multi: 收集所有 active 的 value
6. 按 value_tag 反序列化 value → 还原原生 Python 类型
```

#### 读取（按 fact_meta 过滤）

```text
record = snap.field("name").active_assertions.where(source="import").one()
    ↓
1. 取该 field 的所有 active asrt_id（同上流程）
2. SELECT asrt_id FROM fact_meta WHERE asrt_id IN (...) AND key="source" AND value="import"
3. 返回对应 AssertionRecord
```

### §5.8 与 §2.2 OUT scope 的关系

精简后数据模型显式覆盖以下议题（与 §2.1 IN scope 对应）：

- ✅ 数据精简 1：`meta_rows` / `annotation_rows` 收口 → §5.3 fact_meta
- ✅ 数据精简 2：`namespace` / `category` 下沉 → §5.3 fact_meta 不含这两列
- ✅ 数据精简 3：`claims` / `revokes` 统一 → §5.2 claims + pred_id="__system__.revokes"
- ✅ 数据精简 4：`rest_terms` / `claim_args` 收口 → §5.2 claims + value/value_tag 内联

仍然 OUT of scope（与 §2.2 一致）：

- `ledger_meta` / `ingest_keys` 重构 — infra 不动
- 新增 `annotation_rows` 字段 / 维度 — 方向是简化收口，不是新增
- view / policy / audit / adapter 内部 — 读 ledger 但不定义 ledger schema
- service / wire / DTO 形态 — application/sdk 上层，独立议题
- 性能 benchmark / 迁移工具实现 — blueprint 期任务

### §5.9 章节总结

本章节锁定的稳定契约：

1. **Schema**：2 张数据表 (`claims` + `fact_meta`) + 2 张 infra 表
2. **Claim 4-tuple**：`(asrt_id, pred_id, e_ref, value, value_tag)` — 配合 INV-9 unary commitment
3. **8 种 value_tag**：与 `tup_v1` canonical bytes 互可转换，SQL canonical 用 human-readable + computable text 形式
4. **Float64 写入纪律**：finite + `-0.0` normalize + reparse-then-format
5. **Time 编码**：SQL canonical = epoch nanos decimal；ISO 8601 留给显示层
6. **Digest path 纪律**：SQL row → typed value → tup_v1 → digest；禁止 SQL CAST 参与 digest
7. **Golden tests**：跨语言 float formatter 必须 byte-exact 一致
8. **logical PK = asrt_id**（UNIQUE constraint），**physical write order = seq**（INTEGER PRIMARY KEY AUTOINCREMENT）

后续章节（§6-§9）以此为前提。任何违反这 8 条的提案需先回到本章节松动评估。

---

## §6 数据精简提案

> **状态**：待 draft。
> 四条独立但相关的简化（与 §2.1 数据精简 1-4 对应；终态 schema 见 §5）：
> - **6.1** `meta_rows` ↔ `annotation_rows` 收一份：annotation_rows 接管 canonical 角色，meta_rows 退场；SDK query path 改造影响面
> - **6.2** `namespace` / `category` 多维分类下沉：随 `accept` 退场而失去存在理由；候选形态 a/b/c（Q10）— 与 6.1 合一表后该议题部分自然消化
> - **6.3** `claims` ↔ `revokes` 统一：revoke 改为特殊 `pred_id` 的 Claim；专用窄索引性能损失评估（Q9）
> - **6.4** `rest_terms` ↔ `claim_args` 收口：unary commitment (INV-9) 确立后，rest_terms JSON list 内联为 `value` + `value_tag` 双列；`claim_args` 表删除
>
> 6.1 + 6.2 + 6.4 后 ledger 数据表从 5 张缩到 2 张（`claims` + `fact_meta`），加 infra 共 4 张。最终 schema 详见 §5。本章节展开每条简化的 delta、影响面、风险评估。

---

## §7 Identity 重设计

> **状态**：待 draft。
> 重头戏。需先收口 §8 决策日志中 Q1-Q8 的关键决策再展开。
> 暂定结构：
> - **7.1** 目标 shape（machine-derived from §4 invariants）：entity_ref opaque + identity-as-facts + retract+write rename + 系统索引
> - **7.2** entity_ref 分配策略（Q1）
> - **7.3** schema 层 identity 字段声明（Q2）
> - **7.4** 唯一性约束（Q3 + Q4）
> - **7.5** lookup 索引（Q5 + Q6）
> - **7.6** SDK 描述符调整（与 INV-6 一致）

---

## §8 决策日志

每条决策在被采纳前都属于"待裁定"。本节按时间顺序追加。

| 日期 | 决策点 | 选项 | 当前状态 |
|---|---|---|---|
| 2026-05-27 | doc 名称：`identity-mechanism` vs `identity-and-data-model` | 后者 | ✅ 已采纳 |
| 2026-05-27 | scope：是否合并数据精简议题 | 合并 | ✅ 已采纳 |
| 2026-05-27 | OUT scope：`rest_terms`↔`claim_args` 收口 | 排除 | ✅ 已采纳 |
| 2026-05-27 | namespace/category 多值机制是否随 `accept`/`accept_many` 退场而下沉 | 收口（与"数据精简 1"同 slice） | ✅ 已采纳 |
| 2026-05-27 | doc 位置：`docs/references/working/` vs `workflow/design/design-points/active/` | `workflow/design/design-points/active/` 单文件 essay | ✅ 已采纳 |
| 2026-05-27 | INV-9：Ledger Claim 是 unary fact（关闭 n-ary 留口） | 接受 | ✅ 已采纳（详见 §4.9） |
| 2026-05-27 | 数据精简 4：`rest_terms` / `claim_args` 收口反转纳入 IN scope | 接受（与 INV-9 同 slice） | ✅ 已采纳（取代原 OUT scope 决策） |
| 2026-05-27 | Q-time SQL canonical 编码（α ISO 8601 vs β epoch nanos decimal） | β epoch nanos decimal | ✅ 已采纳（详见 §5.4） |
| 2026-05-27 | SQL `value` 列 canonical 编码契约（8 种 value_tag 编码规则）| 锁定 §5.4 表 | ✅ 已采纳 |
| 2026-05-27 | Digest path 纪律：禁止 SQL CAST 参与 digest 计算 | 锁定 | ✅ 已采纳（详见 §5.5） |
| 2026-05-27 | `float64` 写入纪律：finite + `-0.0` normalize + reparse-then-format | 锁定 | ✅ 已采纳（详见 §5.4） |
| 2026-05-27 | Cross-language float formatter 必须 golden tests 锁住 | 锁定 | ✅ 已采纳（详见 §5.6） |
| 2026-05-27 | `fact_meta.kind` 与 `claims.value_tag` 统一命名为 `value_tag` | 统一 | ✅ 已采纳（fact_meta 多 `json` 作受控扩展；详见 §5.3） |
| 2026-05-27 | Q-RV1：撤销机制属于哪个工业系谱 | append-only correction event 系谱（与 Datomic / Event Sourcing 同系谱，实现上是 system predicate discriminator 而非 dedicated `added` boolean）| ✅ 已采纳（subagent + 2 个独立 agent 三方交叉验证）|
| 2026-05-27 | Q-CK：是否引入 `claim_kind` 列（Datomic `added` 同款）| 不引入 — 保持 system predicate + INV-10 至 INV-15 institutionalization；schema 不加列 | ✅ 已采纳 |
| 2026-05-27 | D-IK-K：`ingest_keys.kind` 列处置 | **分阶段**：当前保留（grep 确认 [ledger.py:978-1007](../../../../src/factgraph/core/store/ledger.py) `kind` 是 load-bearing routing — 区分 asrt_id 指向 claims 还是 revokes 表）；精简 3 完成后删除（届时 revoke 进 claims，`kind` 退化为可由 `claims.pred_id` 反推的冗余）| ✅ 已采纳 |
| 2026-05-27 | D-IK-T：是否移除整个 `ingest_keys` 表 | 不移除 — 独立 idempotency index 对 retry / 并发写 / 未来 request replay 扩展有工程价值 | ✅ 已采纳 |
| 2026-05-27 | INV-10：`__system__.*` pred_id namespace 预留 | 接受作硬不变量 | ✅ 已采纳（详见 §4.10）|
| 2026-05-27 | INV-11：Revoke claim payload shape 固定 | 接受作硬不变量 | ✅ 已采纳（详见 §4.11）|
| 2026-05-27 | INV-12：Revoke target 必须是非 system claim（禁止 revoke-of-revoke / reactivation in v1）| 接受 — v1 严格；reactivation 留 future 议题 | ✅ 已采纳（详见 §4.12）|
| 2026-05-27 | INV-13：Active projection 单一公式（factual claims 减 revoke targets）| 接受 — 公式严格 scope 到 factual claims，system claims 自身 active 状态不参与 | ✅ 已采纳（详见 §4.13）|
| 2026-05-27 | INV-14：Revoke 幂等性行为契约（重复 retract 返回既有 revoker）| 接受作行为契约（实现分阶段：当前 find_revoker 短路；精简 3 后走 ingest_keys）| ✅ 已采纳（详见 §4.14）|
| 2026-05-27 | INV-15：普通查询默认 filter system claims | 接受 — `fg.read.*` 默认排除 `__system__.*`；审计走 `fg.audit.*` | ✅ 已采纳（详见 §4.15）|
| — | Q1：entity_ref 分配方式（UUID4 / ULID / content-addressed-on-creation-meta / 混合） | — | 待裁定 |
| — | Q2：identity 字段在 schema 中如何重新声明 | — | 待裁定 |
| — | Q3：唯一性约束的 schema 形态（per-field / composite / 多 natural keys） | — | 待裁定 |
| — | Q4：写入时唯一性冲突的语义 | — | 待裁定 |
| — | Q5：lookup 索引的存储与重建语义 | — | 待裁定 |
| — | Q6：历史 lookup（"as of" 查询）的语义 | — | 待裁定 |
| — | Q7：backward compat with 现存 idref_v1 token | — | 待裁定 |
| — | Q8：annotation_rows 是否真能完全替代 meta_rows（SDK query path 改造） | — | 待裁定 |
| — | Q9：revoke 统一进 Claim 后，专用窄索引的性能损失如何抵消 | — | 待裁定 |
| — | Q10：namespace/category 收口具体形态（a: 完全去除两列、用 key 前缀编码 / b: 保留 namespace 锁定 `"shared"`、去掉 category / c: 保留两列作 reserved capacity） | — | 待裁定（§6.2 展开）|

---

## §9 迁移路径

> **状态**：待 draft。
> 处理 backward compat with idref_v1（INV-8）+ 现存 v0.1.0-rc.1 export package 的兼容性。
> 暂定结构：
> - **9.1** 老 idref_v1 entity 的兼容策略
> - **9.2** 新旧 entity_ref 共存的 lookup 路径
> - **9.3** 数据精简的 schema migration 时序（最好与 Identity 迁移同 slice 完成，避免两轮 SQLite 表结构变更）

---

## §10 关联文档与代码锚点

### §10.1 关联 workflow 工件

- [`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md) — INV-6 的形式来源（application-first runtime authority）
- [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) — 当前 ledger 范式（mono-temporal append-only with revocation）的 10 维度专业评估 + 已识别未来 gap（GDPR / bitemporal / compaction / upcaster 等）。本 essay 关注的 Identity anti-pattern 修复对应该 doc 的 G1，是当前任务焦点；G2-G8 属于该 doc 的 future 议题，不在本 essay scope

> 本 essay 的写作纪律（preflight code audit / iterative section / per-item change-request review / audit execution）在 Claude 操作 memory 中维护，不作为本 doc 引用对象。Identity 既有设计方向（owner/path-scoped > pure content-hash）同样在 Claude memory，正式 promotion 到 `workflow/foundations/` 或 `workflow/design/decisions/` 是独立议题。

### §10.2 代码锚点

- [`src/factgraph/core/protocol/idref_v1.py`](../../../../src/factgraph/core/protocol/idref_v1.py) — 当前 entity_ref 编码协议（待重设计）
- [`src/factgraph/core/protocol/tup_v1.py`](../../../../src/factgraph/core/protocol/tup_v1.py) — tuple 编码协议（INV-4 锁定）
- [`src/factgraph/core/store/ledger.py`](../../../../src/factgraph/core/store/ledger.py) — ledger schema + 数据结构定义
- [`src/factgraph/core/evidence/write_protocol.py`](../../../../src/factgraph/core/evidence/write_protocol.py) — 写入/撤销/替换路径
- [`src/factgraph/sdk/schema.py`](../../../../src/factgraph/sdk/schema.py) — `Entity` / `Field` / `Identity` 描述符（待重设计）
- [`src/factgraph/core/docs/01_architecture.en.md`](../../../../src/factgraph/core/docs/01_architecture.en.md) — 四层数据架构权威说明
- [`src/factgraph/sdk/docs/01_concepts.en.md`](../../../../src/factgraph/sdk/docs/01_concepts.en.md) — SDK 对象生命周期

### §10.3 外部启蒙

- Relational.ai Graph Normal Form（GNF）：Things-not-Strings + Indivisibility of Facts
  - 用户 obsidian 笔记 `symb-Intelli./design/06-基于Rel的语法调整.md`
  - 用户 obsidian 笔记 `wiki/pdfs/Data modeling - Graph Normal Form - RAI Documentation.pdf`
  - 注：根据用户 obsidian 笔记 `symb-Intelli./case-studies/palantir/7_FactPy Kernel 启示.md`，"GNF" 一词**不作为对外营销词**使用；本 essay 仅作为内部设计纪律的启蒙引用

### §10.4 上游讨论起点

- `docs/references/working/change-requests-2026-05-27/change-requests.md` — 外部 reviewer 的 PDF 转写（这份 essay 的讨论触发点）

---

## §11 写作节奏与当前状态

按 "confirm one section at a time" 纪律：

1. ~~§1-§4（目的 / 范围 / 动机 / 不变量）~~ ← **本批次完成**
2. 用户审 §1-§4 → draft §5（底层数据模型；基本是 source-grep 结果结构化文档化，争议低）
3. 用户审 §5 → draft §6（数据精简 3 条提案 + 取舍 + 风险）
4. 用户审 §6 → draft §7（Identity 重设计；先收口 Q1-Q9 的关键决策再展开）
5. 用户审 §7 → draft §9（迁移路径）
6. §8 决策日志在每次 draft 间持续更新

每章 draft 之间允许：
- 修改前面章节（保持决策一致性）
- 调整 scope 边界（更新 §2）
- 追加新 open questions（更新 §8）

不允许：
- 一次性 draft 多个 §
- 把 IN/OUT scope 跨过 §2.3 边界检验问题就改

### §11.1 当前批次完成状态

- [x] 单文件 essay 创建于 `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`
- [x] 7-field metadata header
- [x] §1 目的 / §2 范围 / §3 动机 / §4 不变量（含 INV-9 + INV-10 至 INV-15 system predicate institutionalization + 适用范围）
- [x] §5 底层数据模型（首版整理完成 2026-05-27 — schema / 编码契约 / digest 纪律 / discipline）
- [x] §8 决策日志（含已采纳 + 待裁定记录；累计 22+ 条）
- [x] §10 关联文档与代码锚点
- [x] §11 写作节奏 + subagent 调研摘要（§11.2）
- [ ] §5.2 / §5.7 加 system claim 边界说明（next batch）
- [ ] §6 / §7 / §9 待后续批次 draft
- [ ] 用户审阅 § 4 INV-10 至 INV-15 + §5 → 决定下一批

### §11.2 Subagent 调研结果摘要

本 essay 的设计决策受 3 次 subagent 调研支持，结果已落入相应章节：

| Dispatch | 调研主题 | 落入位置 |
|---|---|---|
| **1** (2026-05-27) | 行业 10 维度 ledger 范式 survey（Datomic / XTDB / SQL:2011 / Event Sourcing / Kafka / RocksDB）| 完整结果保存在 [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md)；本 essay 用于佐证 INV-1 / INV-5 / INV-9；G2-G8 future gap 不在本 essay scope |
| **2** (2026-05-27) | 下游代码耦合 migration impact survey（52 文件 / 5 CRITICAL 模块 / 5 open Q）| Q-PR1 (PyReason edge) / Q-VD (View snapshot digest) / Q-WF (Audit package v2→v3) / Q-DB (SQLite on-disk migration) / Q-TP1 (tup_v1 协议解读) — 这些 question 在 §8 决策日志跟踪，结果会反映到 §9 迁移路径 |
| **3** (2026-05-27) | Revoke + idempotency 专业度评估（vs Datomic / Stripe / EventStoreDB / Kafka）+ 2 个 cross-validation agent | 结果落入 INV-10 至 INV-15 (system predicate institutionalization) + Q-CK / D-IK-K / D-IK-T 决策；2 个 cross-validation agent 在措辞精确性上做了重要修正（INV-12 不支持 revoke-of-revoke、INV-13 scope 到 factual claims、INV-14 描述当前 find_revoker 而非 ingest_keys）|

调研完整结果在 chat session 上下文 + dispatch 1 的成果保存在 [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md)；本 essay 仅保留经决策吸收的部分。
