# Q-SYS-B Decision: `__system__.revokes` internal emission exception + 7 步 ledger migration slice strategy

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Q5b(internal `__system__.revokes` emission exception)+ Q15(7 步 ledger migration slice strategy)— **必须**回答 meta-ADR §4.3 Q15.1-Q15.5 acceptance boundary 5 项。**不**把 Q-PR1 / PyReason adapter rewrite 作为 Step 1 / Slice 3b dependency;明确划分 Slice 3b 必做 vs Step 2+ Slice 5(adapter rewrite slice)延后。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5b row(`audit:519`)+ Q15 row(`audit:529`)+ §6 INV-11/12/13/15 rows(`audit:285-289`)+ §5.3 A19/A21 rows
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted `ebafdb0c` §4.3 — Q15.1-Q15.5 acceptance boundary 5 项 **必须**在本 ADR §4 回答
  - `workflow/design/decisions/active/2026-05-29_q-sys-a-system-namespace-decision.md` adopted `75f1c8bc` — §4.1 G1 raw pred_id guard + G2 schema owner guard 锁;§4.2 Layer A/B reject;本 ADR §4.1 emission exception 是该 reservation 的内部例外路径,必须**不**走 G1/G2 user-facing guard
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted `2d0866ed` — §4.1 双路径 reject(Identity Claim retract / `:exists` Claim retract);本 ADR §4.1 emission path 必须不绕过 ADR-IC INV-7c 保护
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted `66434490` — §4.1 三层入口 + §4.5 schema 三分;本 ADR §4.1 emission 经 `fg.assertions.retract(asrt_id)` 入口 lowering(per ADR-IC §4.1 Layer 3 唯一 asrt_id-based mutation)
  - ledger-schema-specification design-point §2.1 当前 7 表 + §2.2 终态 3 表 + §3.1-§3.3 schema 终态 + §3.4 取消列表 + §9.1-§9.7 7 条精简 + §9.8 migration 时序
  - User reviewer 2026-05-29 ADR-SYS-B directional 4 项 review focus:只锁 Q5b + Q15 ledger migration / 必答 meta-ADR Q15.1-Q15.5 / NOT make Q-PR1 / PyReason adapter rewrite Step 1 dep / 明确 Slice 3b 必做 vs Step 2+ 延后
- Outputs / Downstream:
  - Slice 3b ledger migration refactor blueprint(`workflow/blueprints/active/2026-05-29_slice-3b-ledger-migration.md` 起草前置)— **本 ADR §4.6 Q15.5 是 Slice 3b "完成判定" 的 explicit contract**
  - Slice 5+(Step 2+)PyReason adapter rewrite slice 取得本 ADR §4.2 Q15.1 / §4.6 Q15.5 中标记 "deferred to Slice 5+" 的 work items 作为 acceptance criteria
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-INV9 / ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-sys-b-revokes-migration-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.3 Q15.1-Q15.5 minimum coverage requirement + §4.4 Step 1 zero-Q-PR1 dependency hard rule)
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`(ADR-IC §4.1 INV-7c reject 路径 + §4.3 `protected_anchor_pred_ids` cache;本 ADR §4.1 emission 必须 coexist 而非 bypass)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted @ `66434490`(ADR-API §4.1 Layer 3 `fg.assertions.retract(asrt_id)` 是唯一 asrt_id-based mutation 入口;本 ADR §4.1 emission 由该入口 lowering 产生)
  - `workflow/design/decisions/active/2026-05-29_q-sys-a-system-namespace-decision.md` adopted @ `75f1c8bc`(ADR-SYS-A §4.1 G1/G2 user-facing guard;本 ADR §4.1 emission 是 reservation 的 internal exception 路径)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q5b + Q15 — System namespace cluster + Ledger migration cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q5b | Internal `__system__.revokes` emission exception path | `audit:519` | System namespace |
| Q15 | 7 数据精简 migration slice strategy(覆盖 Q15.1-Q15.5 meta-ADR acceptance boundary)| `audit:529` | Ledger migration + System namespace |

### 1.2 Meta-ADR §4.3 Q15.1-Q15.5 acceptance boundary(必答)

per meta-ADR adopted `ebafdb0c` §4.3,本 ADR §4 **必须**回答以下 5 个 boundary questions(`meta-ADR:121-125`)— minimum coverage:

| Q | Title | 本 ADR 落点 |
|---|---|---|
| Q15.1 | claims 表 `rest_terms` 列是否在 Slice 3b 内删除?vs 留到 Step 2+ adapter rewrite slice | §4.2 |
| Q15.2 | `__system__.revokes` Claim 在当前 n-ary `rest_terms` schema 上如何编码?(临时 1-elem rest_terms 包装 vs Slice 3b 同步引入 value+value_tag 双列 + INV-9 weak enforce) | §4.3 |
| Q15.3 | `claim_meta` 跟 shipped `meta_rows` / `annotation_rows` 关系?(纯重命名;合并 annotation_rows 进 claim_meta + 加 namespace/category 字段;完全替代 + annotation_rows 删) | §4.4 |
| Q15.4 | `ingest_keys` 表在 Slice 3b 内是否删除?vs 留到 cleanup slice | §4.5 |
| Q15.5 | Slice 3b 的 Stage 4 blueprint acceptance criteria 的"完成"定义 | §4.6 |

### 1.3 User reviewer 2026-05-29 directional 4 项 review focus

| 项 | User guidance | 影响本 ADR |
|---|---|---|
| 1 | 只锁 Q5b + Q15 的 ledger migration 决策 | §2 Scope 显式;§3 Non-scope 显式 enumerate 其他 ADR 占用 |
| 2 | 必须回答 meta-ADR Q15.1-Q15.5 | §4.2-§4.6 5 个 Q each 锁;§8 acceptance § minimum coverage check |
| 3 | NOT 把 Q-PR1 / PyReason adapter rewrite 作为 Step 1 dependency | §4.2 Q15.1 选 weak enforce 不 drop 列;§3 Non-scope 显式列出;§6.5 zero-Q-PR1 confirm |
| 4 | 明确 Slice 3b 必做 vs 延后 Step 2+ | §4.6 Q15.5 完成判定显式 enumerate;§4.7 migration 时序表 |

### 1.4 Shipped baseline(audit §5.3 / §5.4 + ledger-spec §2.1)

**当前 7 表 schema**(per ledger-spec §2.1 + `src/factgraph/core/store/ledger.py:81-159`):
- `claims (seq, asrt_id, pred_id, e_ref, rest_terms TEXT)`
- `claim_args (id, asrt_id, idx, val_atom, tag)`
- `meta_rows (id, asrt_id, key, kind, value)`
- `annotation_rows (id, asrt_id, namespace, category, key, kind, value, origin, derivation)`
- `revokes (id, revoker_asrt_id, revoked_asrt_id)`
- `ingest_keys (ingest_key, asrt_id, kind)`
- `ledger_meta (key, value)`

**当前 retract 路径**(audit INV-11 row `:285`):
- `evidence/write_protocol.py:200-205` `retract_by_asrt` 写 `Revokes(revoker_asrt_id, revoked_asrt_id)` 行,**不**写 `__system__.revokes` Claim 到 `claims` 表 — pre-migration coherent baseline

**target schema**(per ledger-spec §2.2 + §3.1-§3.3):
```text
claims     (seq, asrt_id, pred_id, e_ref, value, value_tag)
claim_meta (asrt_id, key, value)  -- 复合 PK
ledger_meta (key, value)
```

**5+1 state classification**(audit §6):
- INV-11/12/13/15 全是 **(f) target-gap / pending migration** — shipped 当前 schema 不支持这些 invariant 的概念前提;Slice 3b 实施时建立 load-bearing boundary

## 2. Scope

本 ADR **锁**以下 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q5b** | Internal `__system__.revokes` emission exception path — `fg.assertions.retract(asrt_id)` 经 application layer lowering 进 protocol-level `ledger.append_revocation_claim(...)`;**不**走 G1/G2 user-facing guard(per ADR-SYS-A §4.2.3 Layer C 的 "internal API 分离" semantics)|
| **§4.2 Q15.1** | `claims.rest_terms` 列在 Slice 3b **保留**(添加 INV-9 weak enforce length ≤ 1);**真正 drop 列**延后到 Step 2+ Slice 5 adapter rewrite slice — 不让 Q-PR1 阻塞 Step 1 |
| **§4.3 Q15.2** | `__system__.revokes` Claim 编码:Slice 3b **同步引入** value + value_tag 双列(per ledger-spec §3.1 target);Claim 形态 `pred_id="__system__.revokes", e_ref=<revoked claim e_ref>, value=<revoked_asrt_id>, value_tag="string"`(per ledger-spec §3.1 + INV-11);rest_terms 字段写 empty list(weak enforce length ≤ 1)|
| **§4.4 Q15.3** | `claim_meta` 完全替代 — drop `meta_rows` + drop `annotation_rows`;新 `claim_meta` 不含 `namespace` / `category` / `origin` / `derivation` 4 列;复合 PK `(asrt_id, key)`(同步 Q15.7 一并落)|
| **§4.5 Q15.4** | `ingest_keys` 表 Slice 3b **删除**;ledger 不承担 idempotency;`_compute_ingest_key` / `Idempotency(...)` 参数链全清理;retract idempotency 走 `find_revoker` 风格(per INV-14)|
| **§4.6 Q15.5** | Slice 3b 完成判定 — option (b) 子集落地 + 剩余明确 Step 2+ 转;Slice 3b **必做** 5 项(精简 1+5 / 精简 3 / 精简 4 weak enforce / 精简 6 / 精简 7)+ Slice 5(Step 2+)1 项(精简 4 真正 drop rest_terms 列同 adapter rewrite)|
| **§4.7** | Migration 时序 — alpha 阶段允许 atomic schema flip;blueprint 期可选 incremental landing(参考 ledger-spec §9.8 4 阶段)|

## 3. Non-scope

本 ADR **不**锁(per user reviewer §1.3 第 1+3 项 + meta-ADR §4.2 grouping + cross-ADR boundaries):

| 不锁 | 留给谁 |
|---|---|
| `__system__.*` user-facing namespace reservation(G1/G2 guard)| **ADR-SYS-A**(已 adopted `75f1c8bc`)|
| Identity Claim emission / `:exists` co-emission / INV-7c cache(`protected_anchor_pred_ids`)| **ADR-IC**(已 adopted)|
| Q-PR1 / PyReason adapter `(source, target)` 2-position vs INV-9 unary 冲突 | **Step 2+ Slice 5 adapter rewrite slice + ADR-INV9**(本 ADR §4.2 Q15.1 显式不依赖此)|
| INV-9 strict adapter enforcement(`len(rest_terms) <= 1` runtime assertion)| **ADR-INV9**(本 ADR §4.2 Q15.1 仅 weak enforce — write path 保证 length ≤ 1;不加 runtime read-path strict check)|
| EntityEditor 不可变性 / commit / rollback 路径 | **ADR-IE** |
| docs sync timing(`04_api_surface.en.md` / `assertions.md` / `ledger-schema-specification`)| **ADR-DOCS**(Q17)|
| `MetaKeyRegistry`(`§5.3` 系统 meta key 中心化注册)的具体 schema | **Step 2+ docs slice + 后续 ADR**(本 ADR 仅引用其存在性)|
| ledger 跨语言 wire protocol / audit package format v2+(per ledger-spec §10 待裁定的 Q-DB / Q-TP1 / Q-VD / Q-WF)| **Step 2+** |
| Slice 3b 落地的 blueprint slicing(具体 commit 顺序 / impl 顺序)| Slice 3b blueprint |

## 4. Decision

### 4.1 Q5b — Internal `__system__.revokes` emission exception path:**application-layer lowering**

**锁定**:public `fg.assertions.retract(asrt_id)` 入口经 application-layer lowering 在 protocol layer **写入 `__system__.revokes` Claim 到 claims 表**,**不**走 ADR-SYS-A G1/G2 user-facing namespace guard。

#### 4.1.1 Emission path 层级

```text
[Layer 3 入口 — user-facing]
fg.assertions.retract(asrt_id)
  per ADR-API §4.1 + ADR-IC §4.1 Layer 3 唯一 asrt_id-based mutation 入口
  per ADR-IC §4.1 双路径 reject:protected anchor check
    (asrt_id 指向 Identity Claim → INV-7c raise;指向 :exists → transitional guard raise)

[Layer 应用 — application]
  if asrt_id ∈ self._protected_anchor_pred_ids 之下任意 Claim → raise(per ADR-IC §4.3.1)
  else → ledger.append_revocation_claim(revoked_asrt_id=asrt_id, meta=...)

[Layer 协议 — protocol]
ledger.append_revocation_claim(revoked_asrt_id, meta)
  → 在 claims 表写一行:
    pred_id    = "__system__.revokes"
    e_ref      = <revoked claim 的 e_ref> (per INV-11)
    value      = revoked_asrt_id (string)
    value_tag  = "string"
    rest_terms = []  (Slice 3b 暂留列,weak enforce length 0;per §4.2)
  + 可选写 claim_meta(同 transaction;原子 per INV-3)
```

#### 4.1.2 为什么 internal exception path 不走 G1/G2

ADR-SYS-A 锁的 G1 / G2 guard 防的是 **user-facing pred_id supply**:
- G1 防 user 直接 `fg.assertions.write(pred_id="__system__.X", ...)`(per ADR-SYS-A §4.2.3 Layer C forward-looking,Step 1 无此入口)
- G2 防 user 通过 schema declaration 间接产生 `__system__:*` predicates(per ADR-SYS-A §4.2.1 Layer A.1/A.2)

本 ADR §4.1.1 path **没有任何 user-facing pred_id supply**:
- `fg.assertions.retract(asrt_id)` 入参是 asrt_id,user **不**指定 pred_id
- protocol-level `ledger.append_revocation_claim(...)` 是**专用 function name**,**不接受** user-supplied pred_id 参数(pred_id 是函数内部 hardcoded `"__system__.revokes"`)
- 该 function 不是 generic `append_claim(pred_id=..., ...)` — 后者若引入 应在 G1 guard 之下(per ADR-SYS-A §4.2.3 Layer C 规约)

**结论**:internal emission path 跟 G1/G2 guard **互不冲突** — 二者覆盖不同 surface;G1/G2 是 user-facing supply 边界,本 path 是 internal lowering,无 namespace bypass risk。

#### 4.1.3 跟 ADR-IC §4.1 / §4.3 protective cache 协调

- ADR-IC §4.1 双路径 reject:application layer 在 lowering 之前 check `asrt_id` 是否指向 protected anchor(Identity Claim / `:exists` Claim);命中 raise(INV-7c / existence-claim transitional guard)
- 本 ADR §4.1 lowering 仅在 reject **未触发** 时执行 — 跟 ADR-IC §4.3.1 `_protected_anchor_pred_ids = _identity_pred_ids ∪ _exists_pred_ids` cache 严格 coexist
- **关键**:本 ADR emission 路径不污染 ADR-IC cache — `__system__.revokes` Claim 不经 `is_identity_field` / `is_entity_exists` schema_ir flag,自然不入 cache(per ADR-SYS-A §4.4.2 P3-fix 显式 wording — schema-derived 冒号形式 vs future raw 点形式 SYS-B-owned;本 ADR 锁的是后者)

#### 4.1.4 Protocol function name + signature

```python
# core/store/ledger.py (Slice 3b 新增):
def append_revocation_claim(
    self,
    *,
    revoked_asrt_id: str,
    meta: dict[str, Any] | None = None,
) -> str:
    """Internal revocation emission — appends a `__system__.revokes` Claim.

    NOT exposed to user-facing API. Only called from application-layer
    fg.assertions.retract(asrt_id) lowering, after ADR-IC INV-7c /
    existence-claim transitional guard checks.

    Does NOT accept user-supplied pred_id; pred_id is hardcoded to
    `__system__.revokes` per INV-11.
    """
    revoked_claim = self.get_claim(revoked_asrt_id)
    if revoked_claim is None:
        raise WriteProtocolError(f"unknown revoked_asrt_id: {revoked_asrt_id}", ...)

    # Slice 3b 时:claims 表已含 value + value_tag 双列(per §4.3 Q15.2)
    # rest_terms 列 weak-enforce length 0(per §4.2 Q15.1)
    revoker_asrt_id = new_asrt_id()
    self._insert_claim(
        asrt_id=revoker_asrt_id,
        pred_id="__system__.revokes",
        e_ref=revoked_claim.e_ref,
        value=revoked_asrt_id,
        value_tag="string",
        rest_terms=[],
    )
    if meta:
        self._insert_claim_meta(revoker_asrt_id, meta)
    return revoker_asrt_id
```

### 4.2 Q15.1 — `claims.rest_terms` 列删除时机:**Slice 3b 保留 + weak enforce length ≤ 1;Step 2+ Slice 5 真正 drop**

**锁定**:Slice 3b **保留** `claims.rest_terms` 列;write path 加 weak enforce(写入时 length ≤ 1,违反 raise WriteProtocolError);**真正 drop 列** 延后到 **Step 2+ Slice 5 adapter rewrite slice**(跟 Q-PR1 / PyReason adapter 同步)。

#### 4.2.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (a) Slice 3b 内 drop rest_terms 列 + ALTER TABLE | 一次性精简到位 | force PyReason adapter rewrite 作为 Slice 3b 前置依赖;**违反 user reviewer §1.3 第 3 项**(不让 Q-PR1 作为 Step 1 dep)| ✗ |
| (b) Slice 3b 保留列 + weak enforce length ≤ 1 + 同步引入 value + value_tag(per Q15.2)| 列空着但 schema flip 完成;PyReason adapter 改 Slice 5 rewrite 一起 drop | 跟 ADR-SYS-B "解耦 Q-PR1" 原则一致;weak enforce 保证 Slice 3b 后 ledger 写入侧已经 unary;读 path 不受影响 | ✅ |
| (c) Slice 3b 完全不动 rest_terms,等 Step 2+ 一次性 drop | schema 终态不在 Slice 3b 达成;value+value_tag 双列不能引入(per Q15.2 选 1-elem rest_terms 包装)| 跟 Q15.2 同步引入 value+value_tag 目标冲突;Slice 3b 完成判定难定义 | ✗ |

**选 (b)**。

#### 4.2.2 Weak enforce 实施

```python
# core/store/ledger.py append_claim path (Slice 3b 加):
def _insert_claim(
    self, *, pred_id, e_ref, value, value_tag, rest_terms,
    asrt_id=None,
) -> str:
    # weak enforce per INV-9 unary commitment:
    if len(rest_terms) > 1:
        raise WriteProtocolError(
            f"rest_terms length {len(rest_terms)} exceeds 1 (INV-9 weak enforce); "
            f"PyReason 2-position rest_terms should write Relationship instance instead. "
            f"See ADR-SYS-B §4.2 + ADR-INV9 / Slice 5 adapter rewrite."
        )
    # ... rest of insert
```

#### 4.2.3 Step 2+ Slice 5 真正 drop 时机

per ledger-spec §9.4 + §9.8 时序 step 3:`rest_terms` 真正 drop 时机跟 PyReason adapter rewrite 同步(adapter rewrite 必须先去 2-position rest_terms 用法,改 Relationship);本 ADR §3 Non-scope 显式标记 Q-PR1 不在本 ADR scope。Step 2+ Slice 5 时:
- ALTER TABLE drop rest_terms 列
- 取消 §4.2.2 weak enforce(列已不存在,enforce 无必要)
- canonical_bytes_tup_v1 调用点 list 永远 length 0 或 1(已经 weak enforce 保证)

### 4.3 Q15.2 — `__system__.revokes` Claim 编码:**Slice 3b 同步引入 value + value_tag 双列;rest_terms 写 empty**

**锁定**:Slice 3b **同步引入** `claims.value` + `claims.value_tag` 双列(per ledger-spec §3.1 target schema);`__system__.revokes` Claim 形态严格遵循 INV-11:

```text
pred_id    = "__system__.revokes"
e_ref      = <revoked claim 的 e_ref>           (per INV-11 — 便于按 entity 查撤销)
value      = <revoked_asrt_id>                  (string canonical text)
value_tag  = "string"
rest_terms = []                                  (weak enforce length 0 per §4.2)
claim_meta = optional(source / trace_id / note / etc.)  (per INV-3 atomic 同 transaction)
```

#### 4.3.1 为什么同步引入 value + value_tag 不走 "1-elem rest_terms 包装"

| 选项 | 描述 | 评价 |
|---|---|---|
| (1) 临时 1-elem rest_terms 包装:`pred_id="__system__.revokes", rest_terms=[revoked_asrt_id]` | 不引入新列,只走旧 rest_terms 路径 | (i)需要在 Step 2+ Slice 5 再做 schema migration 把 1-elem rest_terms 改 value+value_tag — 双次 migration 成本高;(ii)`claim_meta` 等其他精简同 Slice 但 schema 终态形成两次,Slice 3b 完成判定模糊 |
| (2) Slice 3b 同步引入 value + value_tag 双列 + INV-9 weak enforce | claims 表 schema 达终态形态(列已就位);`__system__.revokes` 写 value=revoked_asrt_id;rest_terms 列保留但 empty(weak enforce);adapter rewrite Step 2+ 时 ALTER TABLE drop rest_terms 列 = 单次清理 | ✅ 选 |

**选 (2)**。

#### 4.3.2 Read path 影响

per ledger-spec §3.1 partial index:`idx_claims_revokes ON claims(value) WHERE pred_id = '__system__.revokes'` — 撤销查询走 value 列(不走 rest_terms);Slice 3b 加该索引即可。`find_revoker` 函数改:
```sql
-- Slice 3b 后:
SELECT asrt_id FROM claims
WHERE pred_id = '__system__.revokes' AND value = ?revoked_asrt_id
LIMIT 1;
```

### 4.4 Q15.3 — `claim_meta` 替代范围:**完全替代 + 删 4 列**

**锁定**:`meta_rows` + `annotation_rows` 两张表 **全删**;新 `claim_meta` 表 schema 严格按 ledger-spec §3.2:
- 列:`asrt_id` / `key` / `value`(3 列)
- **不含**:`id`(surrogate)/ `namespace` / `category` / `origin` / `derivation` / `kind` / `value_tag`(per Q15.3 + Q15.7 一并落)
- 复合 PK `(asrt_id, key)`(per Q15.7 同步落地)

#### 4.4.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (a) 纯 rename:`meta_rows` → `claim_meta`;`annotation_rows` 不动 | minimal change;但 annotation_rows 仍存在 → double meta source 不消除 | 违反 ledger-spec §3.4 取消列表 + §9.1 精简 1;Slice 3b 完成判定 incomplete | ✗ |
| (b) 合并 `annotation_rows` 进 `claim_meta` + 保留 `namespace` / `category` 字段 | 合并表数减 1,但 schema 复杂度未降 | (i)`namespace` / `category` 字段语义在 accept/accept_many 退场后(per design-point)无写入源 → dead columns;(ii) META_KEY_REGISTRY 中心化跟 namespace 字段冗余 | ✗ |
| (c) 完全替代 + `meta_rows` + `annotation_rows` 全删 + claim_meta 不含 4 列(namespace/category/origin/derivation)+ 复合 PK | schema 达终态 3 列;所有现有 user meta 重新写入 claim_meta;system meta key 走 META_KEY_REGISTRY 中心化 | ✅ 跟 ledger-spec §3.2 + §9.1 + §9.5 + §9.7 完全对齐 | ✅ |

**选 (c)**。

#### 4.4.2 SDK 影响(per ADR-API §4.4 `_meta` 统一)

- `AssertionRecordSet.where(_meta={"key": "value"})` query path:Slice 3b 改 claim_meta 索引(`idx_claim_meta_key_value`)
- shipped `accept` / `accept_many` 写 `annotation_rows` 路径在 Slice 3b 前已退场(per audit baseline);annotation_rows 表实际无写入源
- `kind` 列移除:per ledger-spec §3.2 注释 "所有 value 都是 TEXT;特殊格式由 META_KEY_REGISTRY 规定";SDK 读 path 不再 query kind 列

#### 4.4.3 跟 Q15.7(复合 PK)同 Slice 落地

per meta-ADR §4.3 Q15.5 acceptance boundary 留 "其他 sub-decisions 不允许遗漏";本 ADR §4.4 把 Q15.7(claim_meta 复合 PK + 删 surrogate `id`,per ledger-spec §9.7)**一并锁** — 因为 claim_meta 表新建即定 schema,不分两步:
- 新建 `claim_meta` 表时直接 `PRIMARY KEY (asrt_id, key)`,**不**有 surrogate `id INTEGER PRIMARY KEY AUTOINCREMENT`
- 跟 INV-2(asrt_id 全局唯一)配合,(asrt_id, key) 复合 PK 永远只被 INSERT 一次,从根上排除 UPDATE 路径,强化 INV-1 append-only

### 4.5 Q15.4 — `ingest_keys` 表删除时机:**Slice 3b 删除**

**锁定**:`ingest_keys` 表 Slice 3b **完全删除**;ledger 不承担 idempotency;retract idempotency 走 `find_revoker` 风格 search-based 实施(per INV-14)。

#### 4.5.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (α) Slice 3b 内删除 + 同 slice 改 retract idempotency 走 find_revoker | 一次性精简到位;跟 rest_terms weak enforce(精简 4)+ ingest_keys 删除(精简 6)同 slice(per ledger-spec §9.8 step 3 — 两者都触动 write_protocol) | ✅ user reviewer §1.3 第 4 项 "明确 Slice 3b 必做" 直接对齐 | ✅ |
| (β) 留 cleanup slice | Slice 3b 不动,Slice X 后再删 | 留 dead schema 期间 ingest_keys 表无新写入但保留 → 跟 INV-5 source-of-truth 原则冲突(冗余 idempotency 源);Slice 3b 完成判定模糊 | ✗ |

**选 (α)**。

#### 4.5.2 影响 enumeration(per ledger-spec §9.6)

- `_compute_ingest_key` 算法:保留作 SDK 层 helper 供上层 caller 自主使用;**不**从 ledger 调
- `Idempotency(...)` 参数从 `ledger.append_assertion` / `append_revocation_claim`(本 ADR §4.1.4 新增 function)签名移除
- `_find_active_claim_by_ingest_key`(write_protocol)函数移除
- `replace_field` 的 preflight dedup 简化(直接基于已 active claims 行查重,不查 ingest_keys / claim_meta)
- retract idempotency(INV-14)走 `find_revoker` SQL — 而非 ingest_keys lookup:
  ```sql
  -- 查现有 active revoker for target X:
  SELECT asrt_id FROM claims
  WHERE pred_id = '__system__.revokes' AND value = ?target_asrt_id
    AND asrt_id NOT IN (
      SELECT value FROM claims WHERE pred_id = '__system__.revokes'
    )
  LIMIT 1;
  ```

#### 4.5.3 跟 ADR-IC `_protected_anchor_pred_ids` cache 不冲突

- ADR-IC cache 仅 schema_ir-derived(`is_identity_field` + `is_entity_exists`);不涉及 idempotency 概念
- 本 ADR §4.5 删除 ingest_keys 是 idempotency 概念退场,跟 ADR-IC cache 完全独立

### 4.6 Q15.5 — Slice 3b 完成判定:**option (b) 子集落地 + 剩余明确 Step 2+ 转**

**锁定**:Slice 3b 完成判定 = option (b) **子集落地 + 剩余明确 Step 2+ 转**:

#### 4.6.1 Slice 3b **必做** 5 项(per ledger-spec §9 精简 1+5 / 3 / 4 weak / 6 / 7)

| 精简 | ledger-spec § | 本 ADR § | 必做内容 |
|---|---|---|---|
| 精简 1 + 5(`meta_rows` + `annotation_rows` → `claim_meta`)| §9.1 + §9.5 | §4.4 | drop meta_rows + drop annotation_rows + create claim_meta(3 列;不含 4 dropped 列 + 不含 kind / value_tag / surrogate id);META_KEY_REGISTRY 文档化引用 |
| 精简 3(`claims` ↔ `revokes` 统一)| §9.3 | §4.1 + §4.3 | drop revokes 表;`fg.assertions.retract` lowering 写 `__system__.revokes` Claim;`find_revoker` SQL 改;`idx_claims_revokes` partial index |
| 精简 4(`rest_terms` weak enforce + value + value_tag 双列)| §9.4 | §4.2 + §4.3 | 加 value + value_tag 双列;`rest_terms` 列保留但 write path weak enforce length ≤ 1;`claim_args` 表 drop |
| 精简 6(`ingest_keys` 删除 + ledger 不做 idempotency)| §9.6 | §4.5 | drop ingest_keys 表;`Idempotency(...)` 参数链清理;retract idempotency 走 find_revoker(INV-14)|
| 精简 7(`claim_meta` 复合 PK + 删 surrogate id)| §9.7 | §4.4.3 | claim_meta 表新建即 PRIMARY KEY (asrt_id, key);无 surrogate `id` 列 |

**Slice 3b schema 终态**:7 张表 → 3 张表(`claims` / `claim_meta` / `ledger_meta`),其中 `claims` 表暂保留 `rest_terms` 列但 weak enforce(per §4.2)。

#### 4.6.2 **延后** Step 2+ Slice 5 — 1 项

| 项 | 延后内容 | 触发条件 |
|---|---|---|
| 精简 4 真正 drop `rest_terms` 列 | ALTER TABLE drop rest_terms;取消 §4.2.2 weak enforce(列已无)| Q-PR1 PyReason adapter rewrite 完成(per ADR-INV9 + Slice 5)|

#### 4.6.3 Acceptance criteria(per meta-ADR §4.3 acceptance boundary)

Slice 3b blueprint Stage 4 acceptance criteria 必须包含:

- [ ] `meta_rows` 表 dropped(精简 1 part)
- [ ] `annotation_rows` 表 dropped(精简 1 + 2 part)
- [ ] `claim_meta` 表 created with schema (asrt_id, key, value);复合 PK;无 4 dropped 列 + 无 kind / value_tag / surrogate id(精简 1 + 5 + 7)
- [ ] `revokes` 表 dropped(精简 3)
- [ ] `claims` 表新 value + value_tag 双列加 + `rest_terms` 列保留(精简 3 + 4 part);`claim_args` 表 dropped(精简 4 part)
- [ ] `__system__.revokes` Claim emission 路径完整(`fg.assertions.retract` → application reject check → `append_revocation_claim` → write `__system__.revokes` Claim to claims)
- [ ] `idx_claims_revokes` partial index created;`find_revoker` SQL 重写
- [ ] `ingest_keys` 表 dropped(精简 6)
- [ ] `Idempotency(...)` 参数从 `append_assertion` / `append_revocation_claim` 签名移除
- [ ] retract idempotency 走 `find_revoker` 路径 verified(INV-14)
- [ ] write path weak enforce length ≤ 1 in place(per §4.2.2)— 输入 length > 1 raise WriteProtocolError
- [ ] all `__system__.*` namespace 仅由 `append_revocation_claim` emit(无其他 emission path;per ADR-SYS-A §4.4.2 SYS-B-owned emission concern)
- [ ] contract test 覆盖:`fg.assertions.retract(asrt_id)` 调用后 `find_revoker(asrt_id)` 返回非 None;重复 retract 同 asrt_id 返回**同一** revoker(INV-14 idempotency)
- [ ] **Step 2+ Slice 5 deferred** explicit marker:`workflow/blueprints/active/2026-05-29_slice-5-adapter-rewrite.md` 内 §0 Inputs 引用本 ADR §4.6.2 + 标 "drop rest_terms 列 + 取消 weak enforce" 是 Slice 5 acceptance criteria

### 4.7 Migration 时序:**alpha atomic flip;blueprint 期可选 incremental**

**锁定**:per ledger-spec §2.3 + §9.8 alpha 阶段说明:
- **alpha 状态无生产数据兼容性负担**:DDL drop + create 一次性 atomic schema flip;**不**需要 ALTER 数据 backfill 工具 / 跨版本 reader dispatch / view snapshot 兼容层
- **Slice 3b blueprint 可选 incremental landing**(per ledger-spec §9.8 推荐 4 阶段):降低单次 review/test 负担;但**不是必须**:
  1. 精简 1+5(meta_rows + annotation_rows → claim_meta)— schema 基础重构
  2. 精简 3(claims/revokes 统一)— 协调 accept 退场的 dead code
  3. 精简 4(weak enforce)+ 精简 6(ingest_keys 删除)**同 slice** — 二者都触动 write_protocol
  4. 精简 7(claim_meta 复合 PK 列结构最终清理)
- **Step 2+ Slice 5**:精简 4 真正 drop rest_terms 列 + adapter rewrite(独立 slice)

### 4.8 Cross-Q decision summary

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q5b | `fg.assertions.retract` → application reject check → `append_revocation_claim` (protocol layer hardcoded pred_id);**不**走 G1/G2 user-facing guard | `evidence/write_protocol.py` 新 `append_revocation_claim` function;application layer dispatch | Slice 3b(必做)|
| Q15.1 | Slice 3b 保留 rest_terms + weak enforce length ≤ 1;真正 drop 列延后 Step 2+ Slice 5 | `core/store/ledger.py` `_insert_claim` weak enforce check;不依赖 Q-PR1 adapter rewrite | Slice 3b(weak enforce)+ Slice 5(drop 列)|
| Q15.2 | Slice 3b 同步引入 value + value_tag 双列;`__system__.revokes` Claim 写 value=revoked_asrt_id + value_tag="string";`rest_terms=[]` | `ledger.py` claims 表 schema 改;`append_revocation_claim` 函数 | Slice 3b(必做)|
| Q15.3 | 完全替代 — meta_rows + annotation_rows 全删;claim_meta 不含 namespace/category/origin/derivation 4 列 | `ledger.py` DDL;`evidence/write_protocol.py` meta write path | Slice 3b(必做)|
| Q15.4 | Slice 3b 删除 ingest_keys 表;ledger 不做 idempotency;retract 走 find_revoker | `ledger.py` DDL + `_find_active_claim_by_ingest_key` 移除 + `Idempotency` 参数链清理 | Slice 3b(必做)|
| Q15.5 | option (b) 子集落地 + Step 2+ 转 — 5 项必做(精简 1+5/3/4 weak/6/7)+ 1 项延后(精简 4 真正 drop 列)| Slice 3b blueprint Stage 4 acceptance criteria 12 项(per §4.6.3)| Slice 3b(必做)+ Slice 5(延后)|
| §4.7 时序 | alpha atomic flip;blueprint 期可选 4 阶段 incremental | DDL drop/create;无数据 backfill | Slice 3b blueprint 决定 |

**整体**:Slice 3b 实施范围 ≈ 800-1200 行代码改动:
- DDL 重写(drop 5 表 + create 2 表 + 改 claims 表加 2 列)
- `core/store/ledger.py` 写入路径重写(`append_revocation_claim` 新函数 / `_insert_claim` weak enforce / `find_revoker` SQL)
- `core/evidence/write_protocol.py` 重写(`Idempotency` 参数链清理 / retract 走 find_revoker)
- application layer `fg.assertions.retract` lowering 集成
- contract test 覆盖(per §4.6.3 12 项 acceptance)
- docs(Slice 4)— `ledger-schema-specification` 跟 ADR-SYS-B 对齐;`04_api_surface.en.md` 加 retract idempotency 说明

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q5b alternative — Internal exception 走 protocol-layer flag (`bypass_namespace_check=True` kwarg on generic `append_claim`)

- **Why rejected**:把 `bypass_namespace_check` 作为 kwarg 暴露在 generic `append_claim` 上,会让 caller 在多处需要 internal emission(test fixture / migration tool / 等)误用;违反 "internal API 走分离 function name 路径"(per ledger-spec §4.7);本 ADR §4.1.4 选用 **专用 function `append_revocation_claim`**(无 kwarg,pred_id hardcoded)是更干净的边界。

#### Q5b alternative — Internal exception 在 SDK shell 层 emit Claim

- **Why rejected**:违反 INV-6 application-first runtime authority(per ADR-IC §4.2 emission layer 决策);SDK shell 不应承担 ledger 写知识。本 ADR §4.1 lowering 路径 SDK → application → protocol 跟 ADR-IC §4.2 一致。

#### Q15.1 alternative — Slice 3b 内 ALTER TABLE drop rest_terms

- **Why rejected**:force PyReason adapter rewrite 作为 Slice 3b 前置依赖 — **违反 user reviewer §1.3 第 3 项**(不让 Q-PR1 作为 Step 1 dep)+ meta-ADR §4.4 Step 1 zero-Q-PR1 hard rule;Slice 3b scope 会膨胀到包含 adapter rewrite,blueprint 难起草

#### Q15.1 alternative — Slice 3b 不动 rest_terms(不加 weak enforce)

- **Why rejected**:Slice 3b 写入 path 仍然可写 length > 1 rest_terms → INV-9 (unary fact) 在 Slice 3b 后**未生效**;`__system__.revokes` Claim 也要走该路径,跟 Q15.2 value+value_tag 双列不一致(若 Slice 3b 内同步引入 value+value_tag);weak enforce 是低成本(5 行 check)的正确做法。

#### Q15.2 alternative — 临时 1-elem rest_terms 包装(`pred_id="__system__.revokes", rest_terms=[revoked_asrt_id]`,不引入 value+value_tag 双列)

- **Why rejected**:**需要双次 migration** — Slice 3b 走 1-elem rest_terms,Step 2+ Slice 5 再做 value+value_tag 改造;成本远高于 Slice 3b 一次性同步引入;Slice 3b 完成判定 schema 终态模糊。

#### Q15.3 alternative — 纯 rename(`meta_rows` → `claim_meta`;`annotation_rows` 不动)

- **Why rejected**:`annotation_rows` 残留产生 double meta source 不消除;违反 INV-5 source-of-truth;违反 ledger-spec §3.4 取消列表;**Slice 3b 完成判定 incomplete**(per Q15.5 必做 5 项中 精简 1+5 落地不完整)。

#### Q15.3 alternative — 合并 + 保留 `namespace` / `category` 字段

- **Why rejected**:`accept` / `accept_many` 退场后无写入源 → dead columns;跟 META_KEY_REGISTRY 中心化原则冗余;违反 ledger-spec §9.2 + §9.5 精简范围。

#### Q15.4 alternative — `ingest_keys` 留 cleanup slice(Slice X 后再删)

- **Why rejected**:Slice 3b 后留 dead schema 期间 ingest_keys 表无写入但保留 → 违反 INV-5 source-of-truth;跟 rest_terms 不同 — rest_terms 留是为 adapter rewrite 解耦(Q-PR1 boundary),ingest_keys 无类似 boundary;**Slice 3b 完成判定不连贯**(per Q15.5 必做 5 项中精简 6 落地不完整)。

#### Q15.5 alternative — Slice 3b 必做全 7 项(含精简 4 真正 drop 列)

- **Why rejected**:**违反 user reviewer §1.3 第 3 项**;同 Q15.1 alternative — force Q-PR1 adapter rewrite 进 Slice 3b。

#### Q15.5 alternative — Slice 3b 仅必做 3 项(精简 1+5 / 3 / 6),精简 4 weak enforce 跟精简 7 都延后

- **Why rejected**:精简 7(claim_meta 复合 PK)跟新建 claim_meta 同一 DDL operation(per §4.4.3);分两次做需要 ALTER PRIMARY KEY,SQLite 不支持(需 recreate 表 + 数据搬迁);跟 alpha "atomic schema flip" 原则冲突;精简 4 weak enforce 是 Slice 3b `__system__.revokes` 走 value+value_tag 路径的 INV-9 前置条件,不可拆。

### 5.2 Cross-Q rejected combinations

#### Option `SYS-B-defer-everything`:Slice 3b 仅做 Q5b emission;Q15 全留 Step 2+

- **Why rejected**:Q5b emission 走 `append_revocation_claim` 写 `__system__.revokes` Claim 到 claims 表;若 Q15.3 claim_meta 改造不同步,meta 走 meta_rows / annotation_rows 旧 schema → Slice 3b 后跨 schema 混合不连贯;若 Q15.2 value+value_tag 不同步引入,`__system__.revokes` 必须走 1-elem rest_terms 包装 → 跟 Q15.1 weak enforce 冲突。**Q5b + Q15 是同 cluster cohesive 决策**,违反 meta-ADR §4.2 grouping.

#### Option `SYS-B-include-Q-PR1`:Slice 3b 包含 PyReason adapter rewrite + 精简 4 真正 drop 列

- **Why rejected**:scope explosion — Slice 3b 从 ledger schema migration 扩展到 adapter rewrite(跨模块);违反 meta-ADR §4.4 Step 1 zero-Q-PR1 hard rule + user reviewer §1.3 第 3 项;adapter rewrite 涉及 PyReason 适配器内部 Relationship instance 重设计,跟 ledger migration 是不同 concern。Step 2+ Slice 5 独立 slice 更干净。

#### Option `SYS-B-INV-9-strict`:Slice 3b 加 runtime read-path strict assertion(`assert len(claim.rest_terms) <= 1` 在读路径)

- **Why rejected**:write path weak enforce 已保证 Slice 3b 后 ledger 不会有 length > 1 rest_terms 写入;read path strict assertion 是 ADR-INV9 / Q4 scope(per ADR-IC §4.4 / meta-ADR §4.4 "INV-9 strict enforcement 留 Step 2+ adapter rewrite");Slice 3b 强行加 read path strict 会跟 ADR-INV9 决策耦合 + 跟 PyReason 适配器现有 2-position 行为冲突。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5b row(`audit:519`)+ Q15 row(`audit:529`)
- audit §6 INV-11 row(`audit:285`)— revokes 表 baseline `ledger.py:106-110` + `retract_by_asrt` 当前写 Revokes 行;Slice 3b migration 目标
- audit §6 INV-12 row(`audit:286`)— `retract_by_asrt` existence check shipped;part 2(system claim 拒绝)跟 INV-10/11 同 slice
- audit §6 INV-13 row(`audit:287`)— active projection 公式 shipped 等价 design(不同数据源);精简 3 后自然对齐
- audit §6 INV-15 row(`audit:289`)— read path default filter target-gap;**仅 after `__system__` emission 存在才必要** → Slice 3b after emission 路径建立同步加
- audit §5.3 A19 row + A21 row — 3-table ledger schema 终态 + 7 数据精简 migration path
- audit §5.4 N6 row — `_write_session` atomic context

### 6.2 Shipped code citations

- `src/factgraph/core/store/ledger.py:81-159` 当前 7-table DDL(将整体 重写)
- `src/factgraph/core/store/ledger.py:106-110` `revokes` 表 schema(将 drop)
- `src/factgraph/core/store/ledger.py:430-451` `_write_session` atomic context manager(本 ADR §4.1 emission 走该 transaction)
- `src/factgraph/core/evidence/write_protocol.py:200-205` `retract_by_asrt` 当前 写 Revokes(将改 dispatch 到 `append_revocation_claim`)
- `src/factgraph/core/evidence/write_protocol.py:231-249` `_validate_write_inputs` 当前类型 check(将加 §4.2.2 weak enforce length ≤ 1)
- `src/factgraph/core/protocol/tup_v1.py` 8 tag canonical;`rest_terms` JSON 序列化 path(将取消 — per Q15.1 Step 2+ 真正 drop;Slice 3b weak enforce 期间仍可用但写入永远 length 0/1)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-SYS-B grouping(Q5b + Q15 同 ADR)— justifies §2 单 ADR 覆盖 cluster
- meta-ADR §4.3 Q15.1-Q15.5 acceptance boundary — **本 ADR §4.2-§4.6 必答**(per §1.2 表)
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency hard rule — justifies §4.2 Q15.1 weak enforce + Step 2+ Slice 5 真正 drop 选择
- meta-ADR §4.4 4-layer enforcement — justifies §4.1 emission path application + protocol 双层(SDK shell 不 emit)

### 6.4 Design-point citations

- `workflow/design/design-points/active/ledger-schema-specification.zh.md` §2.1 当前 7 表 baseline(`:60-75`)
- ledger-spec §2.2 终态 3 表(`:77-86`)— Slice 3b 目标
- ledger-spec §2.3 关键设计承诺(`:90-101`)— alpha 阶段 atomic flip + claim-first immutable payload + `__system__.revokes` Claim 路径 + ledger 不 idempotency
- ledger-spec §3.1 claims 表终态(`:107-155`)— value + value_tag 双列 + Claim 形态枚举(含 `__system__.revokes` Claim 形态)+ partial index `idx_claims_revokes`
- ledger-spec §3.2 claim_meta 表终态(`:157-184`)— 3 列 + 复合 PK + 设计点
- ledger-spec §3.4 与现有 7 张表的取消列表(`:202-211`)— Q15.3 + Q15.4 + Q15.1 删除范围依据
- ledger-spec §4.7 INV-10(`:290-300`)+ §4.8 INV-11(`:302-309`)+ §4.9 INV-12(`:311-321`)+ §4.10 INV-13(`:323-336`)+ §4.11 INV-14(`:338-347`)+ §4.12 INV-15(`:349-355`)— Slice 3b 后建立 load-bearing 的 invariant set
- ledger-spec §4.7 "internal API(如 `retract_by_asrt`)走分离路径绕开 namespace check"(`:294`)— **§4.1 Q5b 决策核心 design-point 依据**
- ledger-spec §9.1-§9.7 7 条精简(`:718-776`)— Q15.1-Q15.4 + 精简 7 实施分解
- ledger-spec §9.8 migration 时序(`:778-791`)— §4.7 时序 + blueprint 4 阶段可选参考

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter rewrite **作为依赖** — confirmed Step 1 zero-blocker 合规。

**澄清**:
- §3 Non-scope 显式列 "Q-PR1 / PyReason adapter rewrite" 留 Step 2+ Slice 5
- §4.2.3 + §4.6.2 提到 "Step 2+ Slice 5 真正 drop rest_terms 列同 adapter rewrite" — **前向 carve-out**(本 ADR 不锁 Slice 5 的具体内容),**不是 dependency**
- Slice 3b 实施可在 Slice 5 / ADR-INV9 起草前完成,不会被 block

### 6.6 Cross-ADR 兼容性 + contract chain confirmation

#### 6.6.1 ADR-SYS-A(`75f1c8bc`)— emission path 跟 G1/G2 guard 不冲突
- 本 ADR §4.1 emission path 走专用 function `append_revocation_claim`(无 user-facing pred_id supply)— G1 防的是 user-facing raw pred_id;G2 防的是 schema-derived owner_type;本 path 既不是前者也不是后者
- 跟 ADR-SYS-A §4.4.2 P3-fix wording 一致:future internal `__system__.*` claims(点形式)是 SYS-B-owned emission concern,本 ADR scope 内显式定义

#### 6.6.2 ADR-IC(`2d0866ed`)— protective cache coexist
- 本 ADR §4.1 emission path 不污染 ADR-IC `_protected_anchor_pred_ids` cache(per §4.1.3)
- application layer dispatch 在 `append_revocation_claim` 之前 check ADR-IC INV-7c / existence-claim transitional guard(per §4.1.1 路径图)
- `__system__.revokes` 跟 ADR-IC §4.1 双路径 reject 互不干扰 — 后者保护 Identity / `:exists` Claim 不可单独 retract;前者是 retract 的实施路径(对 non-protected Claim)

#### 6.6.3 ADR-API(`66434490`)— Layer 3 唯一 asrt_id-based mutation 入口
- 本 ADR §4.1 emission 严格从 `fg.assertions.retract(asrt_id)`(ADR-API §4.1 Layer 3 唯一入口)lowering
- 不在 Layer 1 / Layer 2 / `fg.fields.*` / `fg.entities.*` 引入 revoke emission 路径
- 跟 ADR-API §4.2 `AssertionsManager` vs `AssertionView` 分离一致(retract 是 manager 上的 mutation method)

#### 6.6.4 Meta-ADR(`ebafdb0c`)— Q15.1-Q15.5 acceptance boundary coverage
- §4.2 Q15.1 答 + §4.3 Q15.2 答 + §4.4 Q15.3 答 + §4.5 Q15.4 答 + §4.6 Q15.5 答 — 5 项 minimum coverage **全部满足**

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 3b ledger migration refactor blueprint**(`workflow/blueprints/active/2026-05-29_slice-3b-ledger-migration.md`)可起草 — Q5b + Q15.1-Q15.5 全部 locked;§4.6.3 12 项 acceptance criteria 是 Stage 4 blueprint outline
- **ADR-INV9**(Q4)起草 — 本 ADR §4.2 weak enforce 跟 ADR-INV9 read-path strict assertion 边界已 carve-out;ADR-INV9 起草时引用本 ADR §3 Non-scope + §5.2 alternative reject
- **Slice 5(Step 2+)PyReason adapter rewrite slice** 准备 — 本 ADR §4.6.2 显式标 "drop rest_terms 列 + 取消 weak enforce" 是 Slice 5 acceptance criteria
- **ADR-IE / ADR-DOCS** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 3b blueprint draft(`workflow/blueprints/active/2026-05-29_slice-3b-ledger-migration.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-SYS-B adopt 后 |
| Slice 3b pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `Revokes(` / `meta_rows` / `annotation_rows` / `ingest_keys` / `Idempotency(` / `_compute_ingest_key` / `_find_active_claim_by_ingest_key` — 全部 migrate | Slice 3b blueprint preflight(Step 4.6.5)| Slice 3b blueprint scoped 后 |
| Slice 3b implementation:DDL 重写(drop 5 表 + create 2 表 + claims 表加 2 列保留 rest_terms)| Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 3b implementation:`append_revocation_claim` 新函数 + write path weak enforce + `find_revoker` SQL 重写 | Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 3b implementation:`Idempotency` 参数链清理 + retract idempotency 走 find_revoker(INV-14)| Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 5(Step 2+)blueprint:引用本 ADR §4.6.2 + §4.2.3 作为 acceptance criteria;drop rest_terms 列 + 取消 weak enforce + adapter rewrite | Slice 5 blueprint preflight | Step 2+ |
| docs sync(Slice 4)— `ledger-schema-specification` 跟 ADR-SYS-B 对齐;`04_api_surface.en.md` 加 retract idempotency + `_meta` claim_meta path 说明;`identity-mechanism-redesign §10` 同步 | Slice 4 docs sync | Slice 3b 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-INV9 起草时 Header `Depends on:` 引用本 ADR(§4.2 weak enforce vs strict 边界 carve-out);Slice 5 blueprint preflight 引用本 ADR §4.6.2
- **Blueprint pillar**:Slice 3b blueprint preflight(Step 4.3)必须 re-read 本 ADR §4 Decision;**§4.6.3 12 项 acceptance criteria 是 Stage 4 minimum coverage**
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q5b + Q15 行 status 仍是 "待 ADR 决策" — 实际 ADR-SYS-B 已 lock;**不**触发 audit doc post-stage sync(跟其他 Stage 2 ADRs 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3b blueprint 不可单方面 override Q5b / Q15.1-Q15.5 决策;若需要 override,走 "本 ADR superseded by 新 ADR-SYS-B-v2" 路径
- §4.1 emission path:carry-forward — internal exception 永远走专用 function name(`append_revocation_claim`),不可改为 generic `append_claim(pred_id=..., bypass_namespace=True)`(违反 ledger-spec §4.7 "internal API 分离" + 本 ADR §5.1 alt rejected)
- §4.2 weak enforce + Step 2+ drop 列:carry-forward — Slice 3b 后 ledger 写入永远 length ≤ 1;Slice 5 之前不可加 read-path strict(留 ADR-INV9 决策)
- §4.3 value + value_tag 双列 + `__system__.revokes` 形态:carry-forward — 不可改 Claim 形态(per INV-11);不可去 partial index `idx_claims_revokes`
- §4.4 claim_meta 完全替代 + 4 列 drop + 复合 PK:carry-forward — Slice 5+ 不可重新加回 namespace / category / origin / derivation / kind / value_tag / surrogate id 列
- §4.5 ingest_keys 删除 + ledger 不 idempotency:carry-forward — Slice 5+ 不可重新引入 ledger-side idempotency 机制(若 future 需要 idempotency,走 SDK / API policy layer)
- §4.6 Slice 3b 完成判定 12 项:carry-forward — Stage 4 acceptance criteria 任一项缺失则 Slice 3b blueprint 不可 mark `implemented`
- §4.2 deferred-to-Slice-5 explicit contract:**Slice 5 acceptance criteria 必须** drop rest_terms 列 + 取消 weak enforce + Q-PR1 adapter rewrite;Slice 5 不可单独完成其一(三者绑定)

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.7 Q5b + Q15.1-Q15.5 + 时序 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥9 项)+ cross-Q rejected combinations(≥3)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / 4 cross-ADR 兼容性 6 类 evidence
- [x] §6.6.4 显式 confirm meta-ADR Q15.1-Q15.5 minimum coverage 全部满足
- [x] §6.5 显式 confirm 全文 zero Q-PR1 dependency;Step 2+ Slice 5 carve-out 非 dependency
- [x] §4.1 Q5b internal emission path **不**走 ADR-SYS-A G1/G2 user-facing guard(走专用 function `append_revocation_claim`)
- [x] §4.6.3 显式 enumerate 12 项 Slice 3b acceptance criteria(option (b) 子集落地 + Step 2+ 转 具体内容)
- [x] §4.2 + §4.6.2 显式 deferred-to-Slice-5 carve-out(Q-PR1 / adapter rewrite / 真正 drop rest_terms 列三者绑定)
- [x] Header `Depends on:` 引用 meta-ADR + ADR-IC + ADR-API + ADR-SYS-A adopted commits
- [x] §7.4 显式 no-retroactive carry-forward 8 项

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 3b blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR + Stage 4 §10 Outcome acceptance criteria 含 §4.6.3 12 项
- [ ] Slice 3b implementation:`meta_rows` 表 dropped + `annotation_rows` 表 dropped + `claim_meta` created with schema `(asrt_id, key, value)` + PRIMARY KEY (asrt_id, key) + 无 4 dropped 列 + 无 kind/value_tag/surrogate id(per §4.4 + §4.4.3)
- [ ] Slice 3b implementation:`revokes` 表 dropped(per §4.1 + §4.6.1 精简 3)
- [ ] Slice 3b implementation:`claims` 表加 `value` + `value_tag` 双列 + `rest_terms` 列保留;`claim_args` 表 dropped(per §4.3 + §4.2)
- [ ] Slice 3b implementation:`ledger.append_revocation_claim(revoked_asrt_id, meta)` 函数存在;pred_id hardcoded `__system__.revokes`;不接受 user-supplied pred_id 参数(per §4.1.4)
- [ ] Slice 3b implementation:`fg.assertions.retract(asrt_id)` → application reject check(ADR-IC §4.1 INV-7c / existence-claim transitional)→ `append_revocation_claim` 路径 verified(per §4.1.1)
- [ ] Slice 3b implementation:`find_revoker(target_asrt_id)` 走 `SELECT FROM claims WHERE pred_id='__system__.revokes' AND value=?` SQL(per §4.3.2);`idx_claims_revokes` partial index existed
- [ ] Slice 3b implementation:`ingest_keys` 表 dropped + `Idempotency(...)` 参数从 `append_assertion` / `append_revocation_claim` 移除(per §4.5)
- [ ] Slice 3b implementation:`_compute_ingest_key` / `_find_active_claim_by_ingest_key` 函数移除(或保留 `_compute_ingest_key` 作 SDK helper per §4.5.2 alt;**不**从 ledger 调)
- [ ] Slice 3b implementation:write path weak enforce(`len(rest_terms) > 1` raise `WriteProtocolError` per §4.2.2);error message 含 ADR-SYS-B §4.2 reference + Slice 5 adapter rewrite hint
- [ ] Slice 3b implementation:contract test 覆盖 — `fg.assertions.retract(asrt_id)` 后 `find_revoker(asrt_id)` 非 None;重复 retract 同 asrt_id 返回**同一** revoker_asrt_id(INV-14 idempotency via find_revoker)
- [ ] Slice 3b implementation:contract test 覆盖 — `__system__.revokes` Claim 形态严格(`pred_id` / `e_ref` / `value` / `value_tag` / `rest_terms=[]`);claim_meta 可选附 source / trace_id / note 等 atomic
- [ ] Slice 3b implementation:contract test 覆盖 — Identity Claim retract(via `fg.assertions.retract(identity_asrt_id)`)在 application layer reject(per ADR-IC §4.1 INV-7c)**不**到达 `append_revocation_claim`;同理 `:exists` Claim retract 经 existence-claim transitional guard reject(per ADR-IC §4.4)
- [ ] Slice 3b implementation:ADR-SYS-A G1 / G2 guard 跟 `append_revocation_claim` 互不干扰 verified — `__system__.revokes` 不进 schema_ir;G1 catch 不到(无 user-facing pred_id supply);G2 不适用(非 schema declaration)
- [ ] Slice 5(Step 2+)blueprint Stage 4 acceptance criteria 含三项绑定:drop `rest_terms` 列 + 取消 §4.2.2 weak enforce + Q-PR1 PyReason adapter rewrite
- [ ] Slice 4 docs sync:`ledger-schema-specification §9` 跟 ADR-SYS-B §4 时序对齐;`04_api_surface.en.md` 加 retract idempotency(find_revoker)说明 + `_meta` claim_meta path;`identity-mechanism-redesign §10` 跟 ADR-SYS-B 对齐

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-SYS-B drafted | Q5b + Q15.1-Q15.5(meta-ADR §4.3 acceptance boundary 5 项必答 全覆盖)+ 时序。Q5b internal emission 走专用 `append_revocation_claim` function(不走 G1/G2);Q15.1 Slice 3b 保留 rest_terms 列 + weak enforce(Step 2+ Slice 5 真正 drop 同 adapter rewrite);Q15.2 同步引入 value + value_tag 双列;Q15.3 完全替代 claim_meta + drop 4 列;Q15.4 Slice 3b 删除 ingest_keys;Q15.5 option (b) 子集落地 + Step 2+ 转(5 项必做 + 1 项延后)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-IC adopted @ `2d0866ed` + ADR-API adopted @ `66434490` + ADR-SYS-A adopted @ `75f1c8bc` + user reviewer 2026-05-29 ADR-SYS-B 4 项 directional review focus + ledger-spec §2-§9 design-point。Branch: `v0.2.0-q-sys-b-revokes-migration-decision-2026-05-29`。Commit: TBD post-stage |
