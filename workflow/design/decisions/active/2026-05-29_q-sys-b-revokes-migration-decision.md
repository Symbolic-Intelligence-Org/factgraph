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

### 4.1 Q5b — Internal `__system__.revokes` emission exception path:**application-layer lowering + INV-12 target reject**

**锁定**:public `fg.assertions.retract(asrt_id)` 入口经 application-layer lowering 走 `write_protocol.append_revocation_claim(...)` 高级函数,内部 normalize 后调用现有 `Ledger.append_assertion(typed_rows)` typed-rows API — 写入 `__system__.revokes` Claim 到 claims 表;**不**走 ADR-SYS-A G1/G2 user-facing namespace guard;**显式实施 INV-12 part 2**(target 必须非 system claim — 禁止 revoke-of-revoke)。

#### 4.1.1 Emission path 层级(含 INV-12 target reject)

```text
[Layer 3 入口 — user-facing]
fg.assertions.retract(asrt_id)
  per ADR-API §4.1 + ADR-IC §4.1 Layer 3 唯一 asrt_id-based mutation 入口

[Layer 应用 — application]
  1. ADR-IC protected anchor check
     if asrt_id 指向 Identity Claim(pred_id ∈ _identity_pred_ids)→ raise SDKStoreError(INV-7c)
     if asrt_id 指向 :exists Claim(pred_id ∈ _exists_pred_ids)→ raise SDKStoreError(existence-claim transitional guard)
  2. INV-12 part 2 check(★ 本 ADR §4.1.5 显式锁):
     target_claim = ledger.get_claim(asrt_id)
     if target_claim is None → raise WriteProtocolError(unknown revoked_asrt_id)  [INV-12 part 1]
     if target_claim.pred_id.startswith("__system__.") → raise WriteProtocolError(INV-12 part 2 — no revoke-of-revoke)  ← ★
  3. INV-14 idempotency check
     existing_revoker = find_revoker(asrt_id)
     if existing_revoker is not None → return existing_revoker  [no new write]
  4. lowering → write_protocol.append_revocation_claim(revoked_asrt_id=asrt_id, meta=...)

[Layer write_protocol — high-level normalization]
write_protocol.append_revocation_claim(ledger, revoked_asrt_id, meta) → str:
  - 已通过 §4.1.1 Layer 应用 上三步前置 check
  - 生成 revoker_asrt_id;normalize meta → typed MetaRow list
  - 构造 typed Claim(pred_id="__system__.revokes",hardcoded;无 user-supplied 路径)
  - 调用 Ledger.append_assertion(claim=..., claim_args=[], meta_rows=...)

[Layer ledger — typed-rows append]
Ledger.append_assertion(claim, claim_args=[], meta_rows, ...) → AppendResult
  (existing shipped typed API,无需新方法;revoke claim 仅是 pred_id 特殊的 Claim)
```

#### 4.1.2 为什么 internal exception path 不走 G1/G2

ADR-SYS-A 锁的 G1 / G2 guard 防的是 **user-facing pred_id supply**:
- G1 防 user 直接 `fg.assertions.write(pred_id="__system__.X", ...)`(per ADR-SYS-A §4.2.3 Layer C forward-looking,Step 1 无此入口)
- G2 防 user 通过 schema declaration 间接产生 `__system__:*` predicates(per ADR-SYS-A §4.2.1 Layer A.1/A.2)

本 ADR §4.1.1 path **没有任何 user-facing pred_id supply**:
- `fg.assertions.retract(asrt_id)` 入参是 asrt_id,user **不**指定 pred_id
- write_protocol-level `append_revocation_claim(...)` 是**专用 function name**,**不接受** user-supplied pred_id 参数(pred_id 在 function 内部 hardcoded `"__system__.revokes"`)
- 该 function 不是 generic `append_claim(pred_id=..., ...)` — 后者若引入 应在 G1 guard 之下(per ADR-SYS-A §4.2.3 Layer C 规约)
- Ledger.append_assertion 是 typed-rows API,本身 schema-agnostic;hardcoded pred_id 的责任在 write_protocol 层

**结论**:internal emission path 跟 G1/G2 guard **互不冲突** — 二者覆盖不同 surface;G1/G2 是 user-facing supply 边界,本 path 是 internal lowering,无 namespace bypass risk。

#### 4.1.3 跟 ADR-IC §4.1 / §4.3 protective cache 协调

- ADR-IC §4.1 双路径 reject:application layer 在 lowering 之前 check `asrt_id` 是否指向 protected anchor(Identity Claim / `:exists` Claim);命中 raise(INV-7c / existence-claim transitional guard)
- 本 ADR §4.1 lowering 仅在 reject **未触发** 时执行 — 跟 ADR-IC §4.3.1 `_protected_anchor_pred_ids = _identity_pred_ids ∪ _exists_pred_ids` cache 严格 coexist
- **关键**:本 ADR emission 路径不污染 ADR-IC cache — `__system__.revokes` Claim 不经 `is_identity_field` / `is_entity_exists` schema_ir flag,自然不入 cache(per ADR-SYS-A §4.4.2 P3-fix 显式 wording — schema-derived 冒号形式 vs future raw 点形式 SYS-B-owned;本 ADR 锁的是后者)

#### 4.1.4 函数 layering + signature

**层级 contract**(P1-amend 显式锁):

| Layer | 函数 | 输入 | 责任 |
|---|---|---|---|
| application | `fg.assertions.retract(asrt_id)` lowering | asrt_id + meta | ADR-IC reject + INV-12 part 2 check + INV-14 find_revoker + dispatch |
| write_protocol | `append_revocation_claim(ledger, revoked_asrt_id, meta)` | revoked_asrt_id + meta dict | normalize meta → typed rows;生成 revoker_asrt_id;构造 typed Claim(pred_id hardcoded);调用 Ledger typed API |
| ledger | `Ledger.append_assertion(claim, claim_args=[], meta_rows, ...)` | typed Claim / MetaRow / etc. | 持久化 typed rows(已 shipped,无需新方法)|

**为什么 write_protocol 层而非 ledger 层**:
- shipped `Ledger.append_assertion`(`ledger.py:363`)接受 typed `Claim` / `ClaimArg` / `MetaRow` rows;normalization 在 write_protocol 做(per `write_protocol.py:128` `set_field` 模式)
- 加新 Ledger 方法(如 `append_revocation_claim(revoked_asrt_id, meta)`)会让 Ledger 处理 raw meta dict + asrt_id generation,违反 typed-rows API contract
- "internal API 走分离 function name" 的语义体现在 **write_protocol 层的函数名**(`append_revocation_claim`)— 不是 Ledger 层
- Slice 3b 实施时,renamed/replaced `retract_by_asrt`(`write_protocol.py:170`)→ `append_revocation_claim`;Ledger.append_revocation(`ledger.py:430+`,shipped 路径写 Revokes 表)同步移除

```python
# evidence/write_protocol.py (Slice 3b 重命名 + 重写):
def append_revocation_claim(
    ledger: Ledger,
    revoked_asrt_id: str,
    meta: dict[str, Any] | None = None,
) -> str | None:
    """Internal revocation emission — writes a `__system__.revokes` Claim
    to the claims table via Ledger typed-rows API.

    NOT exposed to user-facing API; called only from application-layer
    fg.assertions.retract(asrt_id) lowering.

    Caller (application layer) MUST first apply:
      - ADR-IC §4.1 protected anchor reject(Identity / :exists)
      - INV-12 part 2 check(target.pred_id NOT startswith "__system__.")
      - INV-14 find_revoker idempotency check

    Caller MUST NOT supply pred_id; hardcoded to "__system__.revokes"
    per INV-11.
    """
    if not isinstance(revoked_asrt_id, str) or not revoked_asrt_id:
        raise WriteProtocolError("revoked_asrt_id must be non-empty string")

    revoked_claim = ledger.get_claim(revoked_asrt_id)
    if revoked_claim is None:
        raise WriteProtocolError(f"unknown revoked_asrt_id: {revoked_asrt_id}")

    # Defensive INV-12 part 2 reassertion at write_protocol layer
    # (application layer should already have caught; defense in depth)
    if revoked_claim.pred_id.startswith("__system__."):
        raise WriteProtocolError(
            f"INV-12 part 2: target {revoked_asrt_id!r} is a system claim "
            f"(pred_id={revoked_claim.pred_id!r}); revoke-of-revoke is forbidden. "
            f"See ADR-SYS-B §4.1.5."
        )

    revoker_asrt_id = new_assertion_id()
    normalized_meta = _normalize_meta(meta)
    typed_meta_rows = _meta_rows_for_claim(revoker_asrt_id, normalized_meta, ...)

    # Construct typed Claim — pred_id hardcoded; value+value_tag per INV-11
    revoke_claim = Claim(
        asrt_id=revoker_asrt_id,
        pred_id="__system__.revokes",        # hardcoded; no user-supplied path
        e_ref=revoked_claim.e_ref,           # per INV-11
        value=revoked_asrt_id,               # per INV-11
        value_tag="string",                  # per INV-11
        rest_terms=[],                       # Slice 3b transitional: always empty
                                              # for new write paths (per §4.3.2)
    )

    ledger.append_assertion(
        claim=revoke_claim,
        claim_args=[],                       # claim_args 表 Slice 3b 已 dropped
        meta_rows=typed_meta_rows,
        idempotency=None,                    # ingest_keys deleted per §4.5
        asrt_id=revoker_asrt_id,
    )
    return revoker_asrt_id
```

#### 4.1.5 INV-12 part 2 — target reject(禁止 revoke-of-revoke)★ P1-amend

**锁定**(per ledger-spec §4.9 INV-12):`fg.assertions.retract(asrt_id)` lowering 路径 **必须** 在 `append_revocation_claim` 之前 check:`target_claim = ledger.get_claim(asrt_id)`;若 `target_claim.pred_id.startswith("__system__.")` → raise。

**理由**:
- per design-point ledger-spec §4.9 INV-12:"Retract 操作的 target asrt_id 必须...(2) target 必须是非 system claim(pred_id 不以 `__system__.` 开头)"
- 禁止 revoke system claim 防止 "revoke-of-revoke = 重新激活" 语义(per design-point §4.9 理由)
- 该 check **必须** 在 application layer 实施(per meta-ADR §4.4 4-layer enforcement;**也** 在 write_protocol layer defense in depth — per §4.1.4 code 注释)
- 配套效果:`find_revoker` SQL 不需要 "exclude revoked revokers" 防御性 subquery(无 revoker 可被 revoke;per §4.5.2)

**Error message**(application + write_protocol 两处):

```python
raise SDKStoreError(  # application layer
    f"Cannot retract {asrt_id!r}: target is a system claim "
    f"(pred_id={target.pred_id!r}).\n"
    f"  System claims (pred_id starting with '__system__.') cannot be revoked "
    f"per INV-12 part 2 (no revoke-of-revoke). See ADR-SYS-B §4.1.5.\n"
    f"  System claims are emitted by internal mechanisms only and have their own "
    f"lifecycle (e.g., __system__.revokes Claims live until target Claim is "
    f"itself purged in a future compaction operation — Step 2+ design)."
)
```

### 4.2 Q15.1 — `claims.rest_terms` 列删除时机:**Slice 3b 保留(legacy compatibility);Step 2+ Slice 5 真正 drop**;**不**做 blanket weak enforce(INV-9 强制留 ADR-INV9)

**锁定**:Slice 3b **保留** `claims.rest_terms` 列作 **legacy compatibility 路径**(PyReason adapter 等未 rewrite 路径继续写 rest_terms);**真正 drop 列** 延后到 **Step 2+ Slice 5 adapter rewrite slice**;**不**在本 ADR 加 blanket `len(rest_terms) <= 1` runtime weak enforce — INV-9 strict / weak enforce 整套是 **ADR-INV9 / Q4 scope**,不属本 ADR(per §3 Non-scope)。

#### 4.2.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (a) Slice 3b 内 drop rest_terms 列 + ALTER TABLE | 一次性精简到位 | force PyReason adapter rewrite 作为 Slice 3b 前置依赖;**违反 user reviewer §1.3 第 3 项**(不让 Q-PR1 作为 Step 1 dep)| ✗ |
| (b) Slice 3b 保留列 + 加 blanket `len ≤ 1` weak enforce | weak enforce 保证 Slice 3b 后 ledger 写入侧已经 unary | **会立即 break PyReason adapter**(adapter 当前写 2-position rest_terms)— 实质 force Q-PR1 dep;同时跟 ADR-INV9 strict/weak enforce 决策耦合 | ✗ |
| **(c)** **Slice 3b 保留列作 legacy path,新 write paths 用 value+value_tag(rest_terms=[]),legacy adapter 路径不动;INV-9 enforce 留 ADR-INV9** | dual-coexistence:new code 走 value+value_tag(per §4.3),legacy adapter 仍写 rest_terms;Slice 5 时 adapter rewrite + drop 列 + ADR-INV9 strict enforce | **真正解耦 Q-PR1**;跟 user reviewer §1.3 第 3 项 + §3 Non-scope INV-9 strict 留 ADR-INV9 一致 | ✅ |
| (d) Slice 3b 完全不动 rest_terms,等 Step 2+ 一次性 drop;value+value_tag 也不引入(用 1-elem rest_terms 包装 `__system__.revokes`)| schema 终态不在 Slice 3b 达成 | 跟 Q15.2 同步引入 value+value_tag 目标冲突;Slice 3b 完成判定不连贯 | ✗ |

**选 (c)**。

#### 4.2.2 Slice 3b dual-coexistence 规则

| Write path | 写入形态 | 是否 Slice 5 受影响 |
|---|---|---|
| **NEW** application/SDK write paths(`fg.fields.set/add`,per ADR-API §4.1)| value + value_tag = authoritative;**rest_terms = `[]`**(empty)| Slice 5 drop rest_terms 列后:只写 value+value_tag(无变化)|
| **NEW** revoke emission(`write_protocol.append_revocation_claim` per §4.1.4)| value=revoked_asrt_id,value_tag="string";**rest_terms = `[]`** | 同上 |
| **LEGACY** PyReason adapter(per Q-PR1 deferred)| 当前形态(rest_terms=[a, b] 2-position);value/value_tag 可 NULL | Slice 5 adapter rewrite 时改写;Slice 5 drop 列后 adapter 必须已 rewrite |
| **LEGACY** 其他未 migrate write paths(若存在)| 当前形态 | 同 adapter — Slice 3b pre-impl grep 必须 enumerate(per §7.2 follow-up)|

**关键**:Slice 3b 期间 ledger.claims 表是 dual-truth schema(value+value_tag 跟 rest_terms 都可承载 1-arity data);Slice 5 drop rest_terms 后 single truth。

#### 4.2.3 为什么不加 blanket weak enforce

- **会 break legacy adapter**:PyReason adapter 当前写 2-position rest_terms;Slice 3b 加 `len(rest_terms) <= 1` blanket enforce 会立即让 adapter raise → force Q-PR1 rewrite 进 Slice 3b
- **INV-9 strict / weak enforce 整套是 ADR-INV9 scope**:per meta-ADR §4.4 + audit Q4 row + 本 ADR §3 Non-scope
- **Slice 3b 的 enforce 是 narrow check**:仅在新函数 `append_revocation_claim`(per §4.1.4)写 `rest_terms=[]` 是 hardcoded(无 runtime check 需要)— 自然 trivially 满足 INV-9

#### 4.2.4 Step 2+ Slice 5 真正 drop 时机

per ledger-spec §9.4 + §9.8 时序 step 3:**三项绑定**(per §7.4 no-retroactive):
- ALTER TABLE drop `rest_terms` 列
- PyReason adapter rewrite(per Q-PR1)— 写 Relationship instance 或 multiple unary Claims
- ADR-INV9 strict / weak enforce 落地 — 由 ADR-INV9 决策(本 ADR 不锁形态)

### 4.3 Q15.2 — `__system__.revokes` Claim 编码 + general canonical value/value_tag mapping:**Slice 3b 同步引入双列;all NEW writes 用 value+value_tag;legacy 路径 rest_terms 保留**

**锁定**:Slice 3b **同步引入** `claims.value` + `claims.value_tag` 双列(per ledger-spec §3.1 target schema);**所有 NEW write paths**(SDK fields.set/add per ADR-API + revoke emission per §4.1.4)使用 value+value_tag 为 authoritative source;`rest_terms` 列写 `[]`(empty);**legacy 路径**(PyReason adapter)继续写 rest_terms(per §4.2.2 dual-coexistence)。

#### 4.3.1 `__system__.revokes` Claim 形态(per INV-11)

```text
pred_id    = "__system__.revokes"
e_ref      = <revoked claim 的 e_ref>           (per INV-11 — 便于按 entity 查撤销)
value      = <revoked_asrt_id>                  (string canonical text)
value_tag  = "string"
rest_terms = []                                  (empty,per §4.2.2 NEW write paths 规则)
claim_meta = optional(source / trace_id / note / etc.)  (per INV-3 atomic 同 transaction)
```

#### 4.3.2 General canonical value / value_tag mapping(★ P1-amend — 覆盖所有 Claim form)

per ledger-spec §3.1 Claim 形态枚举 + 本 ADR §4.2.2 dual-coexistence:

| Claim form | pred_id | value | value_tag | rest_terms 列(Slice 3b)|
|---|---|---|---|---|
| Existence(`<EntityType>:exists`,per ADR-IC §4.4 transitional)| `<EntityType>:exists` | NULL | NULL | `[]`(NEW write paths)|
| Unary value field(普通 1-arity,non entity_ref)| `<EntityType>:<field_name>` | canonical text per tup_v1 | one of 7 non-`entity_ref` tags(string / int / float64 / bool / bytes / time / uuid)| `[]`(NEW write paths)|
| Unary entity_ref field | `<EntityType>:<field_name>` | encoded e_ref string(idref_v1 format)| `"entity_ref"` | `[]`(NEW write paths)|
| Identity Claim(per ADR-IC §4.2 emission)| `<EntityType>:<identity_field_name>` | canonical value per type_domain | tag per type_domain | `[]`(NEW write paths)|
| Multi-cardinality 每一项 | `<EntityType>:<field_name>` | canonical value per item | tag per type_domain | `[]`(NEW write paths;multi 表现为 multiple rows 不同 asrt_id)|
| `__system__.revokes`(per §4.3.1) | `__system__.revokes` | revoked_asrt_id string | `"string"` | `[]`(per INV-11 + §4.2.2)|
| **LEGACY** PyReason adapter 2-position | (各种 rule head pred)| NULL | NULL | `[a, b]`(legacy write — Slice 5 改写)|

**Slice 3b 期间 rest_terms 列角色**(per §4.2.2 dual-coexistence):
- **NEW write paths**:rest_terms 列 = **always empty** `[]`;value+value_tag 是 authoritative source
- **LEGACY write paths**(PyReason adapter 未 rewrite 路径):rest_terms 列 = **legacy data carrier**;value+value_tag 可 NULL
- **Read path**:
  - **优先 read value+value_tag**(NEW claims 全在此路径)
  - **fallback to rest_terms**(LEGACY claims;value+value_tag 为 NULL 时)— 仅对 Slice 5 adapter rewrite 前的 legacy 路径有效
  - **Step 2+ Slice 5 之后**:fallback 路径 dead code 清理(所有 claims 都走 value+value_tag)

#### 4.3.3 为什么同步引入 value + value_tag 不走 "1-elem rest_terms 包装"

| 选项 | 描述 | 评价 |
|---|---|---|
| (1) 临时 1-elem rest_terms 包装:`pred_id="__system__.revokes", rest_terms=[revoked_asrt_id]` | 不引入新列,只走旧 rest_terms 路径 | (i)需要在 Step 2+ Slice 5 再做 schema migration 把 1-elem rest_terms 改 value+value_tag — 双次 migration 成本高;(ii)Slice 3b 完成判定 schema 终态模糊;(iii)`idx_claims_revokes ON claims(value) WHERE pred_id='__system__.revokes'` partial index 无法在 Slice 3b 加(value 列不存在)|
| (2) Slice 3b 同步引入 value + value_tag 双列 | claims 表 schema 达终态列形态(列已就位);NEW writes(含 revoke)写 value+value_tag;legacy rest_terms 路径不动 | ✅ 选 |

**选 (2)**。

#### 4.3.4 Read path 影响

per ledger-spec §3.1 partial index:`idx_claims_revokes ON claims(value) WHERE pred_id = '__system__.revokes'` — 撤销查询走 value 列(不走 rest_terms);Slice 3b 加该索引即可。`find_revoker` 函数改(per §4.5.2)。

其他 read path 改造(per §4.3.2 优先级):
- `Ledger.get_claim(asrt_id)` 返回 Claim row;`Claim.value` / `Claim.value_tag` 是 NEW 字段,优先使用;`Claim.rest_terms` 保留作 legacy fallback
- SDK `fg.assertions.where(field=..., value=...)` per ADR-API §4.4 走 value 列 query(NEW 索引 `idx_claims_pred_value`)
- `claim_args` 表 dropped per 精简 4 — JSON `rest_terms` 列内联(NEW path 写 [],legacy path 写 [a,b];都不需要 row-展开)

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

### 4.5 Q15.4 — `ingest_keys` 表删除时机:**Slice 3b 删除**;**普通 set/add write dedup 语义显式锁**(★ P2-amend)

**锁定**:`ingest_keys` 表 Slice 3b **完全删除**;**ledger 层不承担 idempotency**(per ledger-spec §2.3);application 层为 `fg.fields.set` 保留 preflight active-claim matching(替代 ingest_keys lookup;**preserve 当前行为**);`fg.fields.add` 走 multiset semantics(允许重复);retract idempotency 走 `find_revoker` SQL(per INV-14)。

#### 4.5.1 决策选项 + 选择(ingest_keys 删除时机)

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (α) Slice 3b 内删除 + 同 slice 改 retract idempotency 走 find_revoker | 一次性精简到位;跟 rest_terms 列保留(精简 4)+ ingest_keys 删除(精简 6)同 slice(per ledger-spec §9.8 step 3 — 两者都触动 write_protocol) | ✅ user reviewer §1.3 第 4 项 "明确 Slice 3b 必做" 直接对齐 | ✅ |
| (β) 留 cleanup slice | Slice 3b 不动,Slice X 后再删 | 留 dead schema 期间 ingest_keys 表无新写入但保留 → 跟 INV-5 source-of-truth 原则冲突(冗余 idempotency 源);Slice 3b 完成判定模糊 | ✗ |

**选 (α)**。

#### 4.5.2 普通 set/add write dedup 语义(★ P2-amend — preserve behavior 跨 schema migration)

**问题**:shipped `set_field`(`write_protocol.py:128-157`)用 `_compute_ingest_key` + `Idempotency(on_conflict="skip")` 做 preflight dedup:若同内容已写入(by ingest_key),return 既有 asrt_id 不写新行。Slice 3b 删除 `ingest_keys` 表后,**default 行为变化** — 同内容写入会产 multiple distinct asrt_id;若不显式锁,Slice 3b 是不可见的 behavior change。

**锁定**:

| API 入口(per ADR-API §4.1)| Dedup 行为(Slice 3b 后)| 实施 |
|---|---|---|
| `fg.fields.set(F, e_ref, value)`(single-cardinality replacement)| **preserve 当前 dedup**:preflight 查 active-claim by `(pred_id, e_ref, value, value_tag)` — 命中 return 既有 asrt_id;未命中 append 新 claim | application layer `_find_active_claim_by_value(pred_id, e_ref, value, value_tag)` SQL helper(替代 ingest_keys lookup)|
| `fg.fields.add(F, e_ref, value)`(multi-cardinality append)| **multiset semantics**:每次调用 append 新 asrt_id;允许 multiple distinct asrt_ids 对同一 `(F, e_ref, value)` | 无 preflight dedup;直接 append |
| `fg.entities.create(EntityCls, **id)` + auto-emitted Identity Claims | **single emission per e_ref**(per ADR-IC §4.2 emission input contract):若 e_ref 已 materialized(同 `materialized_refs` set 已含),跳过 emission;否则 emit Identity Claims | application layer `_materialization_ops` 用 `materialized_refs` set check(已 shipped per ADR-IC §4.2)|
| `fg.assertions.retract(asrt_id)` lowering | **idempotent via find_revoker**(per §4.5.4 + INV-14)| application layer `find_revoker` SQL check before `append_revocation_claim` |

**为什么 set 保留 dedup**:
- shipped 行为 user 已依赖(test fixture 同内容多次写入 expect single asrt_id)— Slice 3b 是 schema migration,**不该**改 set 语义
- preflight active-claim matching 跟 ledger-spec §2.3 "ledger 不承担 idempotency" 一致 — dedup 在 application layer 实施,ledger 仅做 append
- 实施代价:`_find_active_claim_by_value` SQL 是 single-query `WHERE pred_id=? AND e_ref=? AND value=? AND value_tag=?`(走 NEW 索引 `idx_claims_pred_value` per ledger-spec §3.1);跟 ingest_keys lookup 等价

**为什么 add 不保留 dedup**:
- multi-cardinality 字段允许 multiset semantics(per design-point identity §12.5);user 添加 duplicate value 应被允许(代表 multiple sources / multiple times)
- 跟 shipped `add_field`(`write_protocol.py:160-167` aliased to `set_field`)行为**有变化** — Slice 3b 后 `add` 不再 dedup;Slice 4 docs sync 必须显式说明

#### 4.5.3 ingest_keys 删除的影响 enumeration(per ledger-spec §9.6)

- `_compute_ingest_key` 算法:保留作 SDK 层 helper 供上层 caller 自主使用;**不**从 ledger 调
- `Idempotency(...)` 参数从 `ledger.append_assertion`(`ledger.py:363`)+ 调用方移除
- `_find_active_claim_by_ingest_key`(write_protocol)函数移除
- 新增 `_find_active_claim_by_value(pred_id, e_ref, value, value_tag)` SQL helper(per §4.5.2 set dedup 实施)
- `replace_field` preflight dedup 简化(走 value+value_tag 索引,不查 ingest_keys / claim_meta)

#### 4.5.4 Retract idempotency(INV-14)走 `find_revoker`(★ P1.1-amend 简化 SQL)

per INV-14 + 本 ADR §4.1.5 INV-12 part 2 锁定(target 必须非 system claim;无 revoker 可被 revoke):

```sql
-- find_revoker SQL (Slice 3b):
SELECT asrt_id FROM claims
WHERE pred_id = '__system__.revokes' AND value = ?target_asrt_id
LIMIT 1;
```

**为什么不需要 "exclude revoked revokers" 防御性 subquery**:
- INV-12 part 2(per §4.1.5)硬 reject `retract(asrt_id)` where `target.pred_id.startswith("__system__.")` — `__system__.revokes` Claim **本身** 是 system claim,无法被 retract
- → 不存在 "已被 revoke 的 revoker" 状态 — subquery `... AND asrt_id NOT IN (SELECT value FROM claims WHERE pred_id='__system__.revokes')` 是 dead defense
- 简化 SQL 也降低 read path 复杂度;`idx_claims_revokes` partial index 直接命中

#### 4.5.5 跟 ADR-IC `_protected_anchor_pred_ids` cache 不冲突

- ADR-IC cache 仅 schema_ir-derived(`is_identity_field` + `is_entity_exists`);不涉及 idempotency 概念
- 本 ADR §4.5 删除 ingest_keys 是 idempotency 概念退场,跟 ADR-IC cache 完全独立

### 4.6 INV-15 read-path default filter:**默认 exclude `__system__.*`;asrt_id 直查路径 bypass**(★ P1.4-amend — closing ADR-SYS-A §4.4.2 carve-out)

**锁定**:Slice 3b 同步实施 INV-15 read-path default filter — `__system__.*` system claims 默认从 user-facing read API 结果中 **排除**;asrt_id 直查路径(audit/replay use case)**bypass** filter。

#### 4.6.1 为什么本 ADR 锁(closing ADR-SYS-A §4.4.2 carve-out)

ADR-SYS-A adopt 时显式 carve out INV-15 read-path filter(per ADR-SYS-A §3 Non-scope + §4.4.2 wording — "future internal `__system__.*` claims by SYS-B-owned emission concern;read filter 跟 emission 时序耦合,留 SYS-B 锁");本 ADR §4.1 emission path Slice 3b 落地,**必须**同步锁 read filter — 否则 system claims emission 后会污染 user-facing read 结果。

per ledger-spec §4.12 INV-15:`fg.read.*` 系列 API 默认查询结果不包含 `pred_id LIKE '__system__.%'` claims;SQL `WHERE pred_id NOT LIKE '__system__.%'`。

#### 4.6.2 Read API 矩阵(per ADR-API §4.1 三层 namespace + §4.2 `AssertionsManager` / `AssertionView`)

| Read API | Default filter | 实施 |
|---|---|---|
| `fg.entities.get / where / match / exists / ref`(Layer 1)| **filter** | underlying SQL 加 `AND pred_id NOT LIKE '__system__.%'` 到 claim-scan path |
| `fg.fields.get(F, e_ref)`(Layer 2)| **N/A** — Field descriptor 来自 schema-declared,不会指向 `__system__.*` pred_id(per ADR-SYS-A G2 reject)| 自然安全 |
| `fg.assertions.where(field=, e_ref=, value=, ...)`(Layer 3 canonical filter)| **filter** | 加 `AND pred_id NOT LIKE '__system__.%'` 到 SQL |
| `fg.assertions.active` / `.all` properties(`AssertionsManager` + `AssertionView`)| **filter** | underlying RecordSet 构造时加 filter |
| `fg.assertions.field(F)` → `AssertionView`(per ADR-API §4.2.4)| **filter**(per Field descriptor;自然不会指向 `__system__.*`)| 自然安全 |
| `fg.assertions.by_id(asrt_id)` / `by_ids([...])`(per ADR-API §4.2.2 Rule 5)| **bypass** — asrt_id 直查 audit/replay 路径;必须能 return system claims | SQL `WHERE asrt_id = ?` 不加 system filter |
| `fg.assertions.at(t)`(Rule 4 终结 → RecordSet)| **filter** | underlying RecordSet 继承 |
| Future `fg.audit.*`(Step 2+)| **bypass** — audit 需完整可见 | Step 2+ ADR 锁 |

#### 4.6.3 SQL 实施约定

per ledger-spec §4.10 INV-13 active projection 公式 `factual claims = {c : c.pred_id NOT LIKE '__system__.%'} MINUS revokes` — INV-15 filter 跟 INV-13 公式左半边 **同构** ,SQL 实施直接复用:

```sql
-- Default user-facing read query (Slice 3b):
SELECT ... FROM claims
WHERE pred_id NOT LIKE '__system__.%'
  AND (... — caller-supplied conditions ...);

-- by_id / by_ids bypass:
SELECT ... FROM claims
WHERE asrt_id = ?
  -- no system filter;由 caller 负责处理 system claim if returned
```

#### 4.6.4 为什么 by_id bypass

per identity §12.5 Rule 5:"by_id 查 .all 不是 .active" — audit / replay 场景需要按 id 拿到已 revoked record;同理 system claims 也需要 by_id 可达(audit `__system__.revokes` Claim 的写入历史 / replay)。Bypass 在 by_id 是 carry-forward(per §7.4)。

#### 4.6.5 跟 ADR-API §4.2.2 `AssertionView` 类型契约不冲突

- ADR-API `AssertionView` 类型契约暴露 `.active` / `.all` properties 等 — 本 ADR §4.6.2 lock 这些 property underlying SQL 加 `__system__.*` filter
- AssertionsManager 委托 read shortcuts 到内部 `_ledger_view: AssertionView`(per ADR-API §4.2.1)— 同样应用 filter
- by_id / by_ids 的 bypass 是 AssertionView 类型契约范围内的实施细节(Rule 5)

### 4.7 Q15.5 — Slice 3b 完成判定:**option (b) 子集落地 + 剩余明确 Step 2+ 转**

**锁定**:Slice 3b 完成判定 = option (b) **子集落地 + 剩余明确 Step 2+ 转**。

#### 4.7.1 Slice 3b **必做** 5 项(per ledger-spec §9 精简 1+5 / 3 / 4 partial / 6 / 7)

| 精简 | ledger-spec § | 本 ADR § | 必做内容 |
|---|---|---|---|
| 精简 1 + 5(`meta_rows` + `annotation_rows` → `claim_meta`)| §9.1 + §9.5 | §4.4 | drop meta_rows + drop annotation_rows + create claim_meta(3 列;不含 4 dropped 列 + 不含 kind / value_tag / surrogate id);META_KEY_REGISTRY 文档化引用 |
| 精简 3(`claims` ↔ `revokes` 统一)| §9.3 | §4.1 + §4.3 + §4.6 | drop revokes 表;`fg.assertions.retract` lowering 经 §4.1.5 INV-12 reject + INV-14 find_revoker + `write_protocol.append_revocation_claim`;`idx_claims_revokes` partial index;INV-15 read filter |
| 精简 4 **partial**(value + value_tag 双列加 + dual-coexistence;rest_terms 列 **保留**)| §9.4 part | §4.2 + §4.3 | 加 value + value_tag 双列;NEW write paths 用 value+value_tag(rest_terms=[]);legacy 路径继续写 rest_terms;`claim_args` 表 drop;**不**加 blanket weak enforce(INV-9 strict/weak 留 ADR-INV9 + Slice 5)|
| 精简 6(`ingest_keys` 删除 + ledger 不做 idempotency)| §9.6 | §4.5 | drop ingest_keys 表;`Idempotency(...)` 参数链清理;retract idempotency 走 find_revoker(INV-14);set 走 `_find_active_claim_by_value` preserving behavior;add 改 multiset semantics |
| 精简 7(`claim_meta` 复合 PK + 删 surrogate id)| §9.7 | §4.4.3 | claim_meta 表新建即 PRIMARY KEY (asrt_id, key);无 surrogate `id` 列 |

**Slice 3b schema 终态**:7 张表 → 3 张表(`claims` / `claim_meta` / `ledger_meta`),其中 `claims` 表 **暂保留** `rest_terms` 列作 legacy compatibility(per §4.2)+ **加** value + value_tag 双列。

#### 4.7.2 **延后** Step 2+ Slice 5 — 1 项(三项绑定)

| 项 | 延后内容 | 触发条件(三项绑定)|
|---|---|---|
| 精简 4 真正 drop `rest_terms` 列(+ Q-PR1 adapter rewrite + ADR-INV9 strict enforce)| ALTER TABLE drop rest_terms;adapter rewrite 改写 Pyreason 2-position;ADR-INV9 锁的 strict / weak enforce 落地 | 三项绑定:任一项缺失则 Slice 5 不可 mark `implemented` |

#### 4.7.3 Acceptance criteria(per meta-ADR §4.3 acceptance boundary)

Slice 3b blueprint Stage 4 acceptance criteria 必须包含:

**Schema migration**:
- [ ] `meta_rows` 表 dropped(精简 1 part)
- [ ] `annotation_rows` 表 dropped(精简 1 + 2 part)
- [ ] `claim_meta` 表 created with schema (asrt_id, key, value);复合 PK;无 4 dropped 列 + 无 kind / value_tag / surrogate id(精简 1 + 5 + 7)
- [ ] `revokes` 表 dropped(精简 3)
- [ ] `claims` 表新 value + value_tag 双列加 + `rest_terms` 列保留(精简 3 + 4 partial);`claim_args` 表 dropped(精简 4 part)
- [ ] `ingest_keys` 表 dropped(精简 6)

**Emission path**:
- [ ] `__system__.revokes` Claim emission 路径完整(`fg.assertions.retract` → application(INV-7c + INV-12 part 2 + find_revoker)→ `write_protocol.append_revocation_claim` → typed Claim → `Ledger.append_assertion`)
- [ ] `write_protocol.append_revocation_claim` function 是 high-level normalization(pred_id hardcoded);Ledger 层无新方法
- [ ] **INV-12 part 2** explicit check(★ P1.1-amend):`fg.assertions.retract(asrt_id)` where target `pred_id.startswith("__system__.")` raise `SDKStoreError` 含 ADR-SYS-B §4.1.5 reference + revoke-of-revoke forbidden hint
- [ ] write_protocol defense-in-depth INV-12 part 2 check 同样 raise(若 application 漏 catch)
- [ ] `idx_claims_revokes` partial index created
- [ ] `find_revoker` SQL 重写(per §4.5.4)**不含** "exclude revoked revokers" subquery(简化为单条件 `WHERE pred_id='__system__.revokes' AND value=?`)

**Canonical value/value_tag mapping**(★ P1.2-amend):
- [ ] NEW write paths(`fg.fields.set/add`,`append_revocation_claim`)统一走 value+value_tag(per §4.3.2 mapping 表);rest_terms 列写 `[]`
- [ ] LEGACY write path(PyReason adapter)继续走 rest_terms 不动 — Slice 3b dual-coexistence(per §4.2.2)
- [ ] Read path 优先 value+value_tag(per §4.3.2);fallback to rest_terms for legacy claims(value+value_tag NULL 时);Slice 5 后 fallback dead code 清理

**Write dedup semantics**(★ P2-amend):
- [ ] `Idempotency(...)` 参数从 `Ledger.append_assertion` 签名移除
- [ ] `fg.fields.set(F, e_ref, value)` preserve dedup — preflight active-claim match via `_find_active_claim_by_value(pred_id, e_ref, value, value_tag)` SQL(替代 ingest_key lookup)— 命中返回既有 asrt_id
- [ ] `fg.fields.add(F, e_ref, value)` 走 multiset semantics — 每次 append 新 asrt_id;**行为变化** 跟 shipped `add_field` aliased to `set_field` 不同 — docs sync 必须显式说明
- [ ] `_compute_ingest_key` / `_find_active_claim_by_ingest_key` 函数移除(或保留 `_compute_ingest_key` 作 SDK helper per §4.5.3 不从 ledger 调)
- [ ] retract idempotency 走 `find_revoker` 路径 verified(INV-14)

**INV-15 read-path filter**(★ P1.4-amend):
- [ ] `fg.entities.*` / `fg.fields.*` / `fg.assertions.where/active/all/field` default exclude `__system__.*` claims(per §4.6.2)— SQL `AND pred_id NOT LIKE '__system__.%'`
- [ ] `fg.assertions.by_id(asrt_id)` / `by_ids([...])` bypass filter(audit/replay can find system claims by exact id;per §4.6.4 Rule 5)
- [ ] contract test 覆盖:emission `__system__.revokes` Claim 后,`fg.assertions.where(...)` / `.active` / `.all` 默认结果不含 system claim;但 `fg.assertions.by_id(revoker_asrt_id)` 可返回

**Cross-ADR invariant**:
- [ ] all `__system__.*` namespace 仅由 `write_protocol.append_revocation_claim` emit(无其他 emission path;per ADR-SYS-A §4.4.2 SYS-B-owned emission concern)
- [ ] contract test:`fg.assertions.retract(asrt_id)` 后 `find_revoker(asrt_id)` 返回非 None;重复 retract 同 asrt_id 返回**同一** revoker(INV-14 idempotency)
- [ ] contract test:`__system__.revokes` Claim 形态严格(`pred_id` / `e_ref` / `value` / `value_tag` / `rest_terms=[]`);claim_meta 可选附 source / trace_id / note 等 atomic
- [ ] contract test:Identity Claim retract(via `fg.assertions.retract(identity_asrt_id)`)在 application layer reject(per ADR-IC §4.1 INV-7c)**不**到达 `append_revocation_claim`;同理 `:exists` Claim retract 经 existence-claim transitional guard reject
- [ ] contract test:`__system__.revokes` Claim 试图被 retract(`fg.assertions.retract(revoker_asrt_id)`)在 application layer reject(per §4.1.5 INV-12 part 2)
- [ ] ADR-SYS-A G1 / G2 guard 跟 `append_revocation_claim` 互不干扰 verified — `__system__.revokes` 不进 schema_ir;G1 catch 不到(无 user-facing pred_id supply);G2 不适用(非 schema declaration)

**Slice 5 deferred marker**:
- [ ] **Step 2+ Slice 5 deferred** explicit marker:`workflow/blueprints/active/2026-05-29_slice-5-adapter-rewrite.md` 内 §0 Inputs 引用本 ADR §4.7.2 + 标 三项绑定 acceptance(drop rest_terms 列 + adapter rewrite + ADR-INV9 strict enforce)

### 4.8 Migration 时序:**alpha atomic flip;blueprint 期可选 incremental**

**锁定**:per ledger-spec §2.3 + §9.8 alpha 阶段说明:
- **alpha 状态无生产数据兼容性负担**:DDL drop + create 一次性 atomic schema flip;**不**需要 ALTER 数据 backfill 工具 / 跨版本 reader dispatch / view snapshot 兼容层
- **Slice 3b blueprint 可选 incremental landing**(per ledger-spec §9.8 推荐 4 阶段):降低单次 review/test 负担;但**不是必须**:
  1. 精简 1+5(meta_rows + annotation_rows → claim_meta)— schema 基础重构
  2. 精简 3(claims/revokes 统一 + INV-12 + INV-14 + INV-15 同步)— 协调 accept 退场的 dead code
  3. 精简 4(value+value_tag 双列加 + dual-coexistence;**不**加 blanket weak enforce)+ 精简 6(ingest_keys 删除 + set/add dedup 语义)**同 slice** — 二者都触动 write_protocol
  4. 精简 7(claim_meta 复合 PK 列结构最终清理)
- **Step 2+ Slice 5**:精简 4 真正 drop rest_terms 列 + adapter rewrite + ADR-INV9 strict enforce(三项绑定,独立 slice)

### 4.9 Cross-Q decision summary

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

- **Why rejected**:`__system__.revokes` Claim 也要走 write path,跟 Q15.2 value+value_tag 双列一致目标(per §4.3.2 NEW write paths 用 value+value_tag,rest_terms=[]);INV-9 strict / weak enforce 整套是 ADR-INV9 / Q4 scope(per §3 Non-scope 显式列出);Slice 3b 加 blanket weak enforce 会立即 break PyReason adapter(legacy 写 2-position rest_terms),force Q-PR1 dep 进 Slice 3b。

#### Q15.1 alternative — Slice 3b 加 blanket weak enforce `len(rest_terms) <= 1`(★ P1.2-amend 新增)

- **Why rejected**(★ P1.2-amend 显式 reject — 替代原 (b) 选项):**会立即 break PyReason adapter**;adapter 当前写 2-position rest_terms,Slice 3b 加 blanket weak enforce → adapter raise → force Q-PR1 rewrite 进 Slice 3b → 违反 user reviewer §1.3 第 3 项 + meta-ADR §4.4 Step 1 zero-Q-PR1 hard rule。INV-9 strict / weak enforce 决策本身是 ADR-INV9 scope。原 draft (b) "Slice 3b 保留列 + weak enforce" 框架混淆 "schema 列引入" 跟 "INV-9 enforce" 两个独立决策;amend 后选 (c) 仅引入列保留 legacy path,enforce 留 ADR-INV9 + Slice 5。

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

#### Q15.5 alternative — Slice 3b 仅必做 3 项(精简 1+5 / 3 / 6),精简 4 partial 跟精简 7 都延后

- **Why rejected**:精简 7(claim_meta 复合 PK)跟新建 claim_meta 同一 DDL operation(per §4.4.3);分两次做需要 ALTER PRIMARY KEY,SQLite 不支持(需 recreate 表 + 数据搬迁);跟 alpha "atomic schema flip" 原则冲突;精简 4 partial(value+value_tag 双列加)是 Slice 3b `__system__.revokes` 走 INV-11 形态的 schema 前置条件,不可拆。

#### Q5b alternative — `append_revocation_claim` 放在 `core/store/ledger.py` 而非 `evidence/write_protocol.py`(★ P1.3-amend)

- **Why rejected**(★ P1.3-amend):shipped `Ledger.append_assertion`(`ledger.py:363`)接受 typed `Claim` / `ClaimArg` / `MetaRow` rows;raw meta dict 处理 + asrt_id generation 在 `write_protocol.py:128` `set_field` 模式做;若把 `append_revocation_claim(revoked_asrt_id, meta)` 放 Ledger 层,Ledger 要 normalize raw meta + 生成 asrt_id → 违反 typed-rows API contract + 跟 shipped layering 不一致。本 ADR §4.1.4 锁 write_protocol 层是 normalization + hardcoded pred_id 的住所;Ledger 仅 typed append(无新方法)。

#### Q15.4 alternative — set/add 都走 multiset semantics(不 preserve set dedup)(★ P2-amend)

- **Why rejected**(★ P2-amend):shipped `set_field`(`write_protocol.py:128`)用 ingest_keys + Idempotency 做 preflight dedup → 同内容多次 set return 同 asrt_id;user 已 depend on 该 behavior(test fixture 等);Slice 3b 改 set multiset 是不可见 behavior change,违反 "schema migration 不该改 API 语义";本 ADR §4.5.2 锁 set preserve dedup(via `_find_active_claim_by_value` SQL 替代 ingest_keys lookup),add 改 multiset(后者本来 shipped aliased to set 是 bug);docs Slice 4 显式说明 add 行为变化。

#### INV-15 alternative — Slice 3b 不锁 INV-15 read filter,留 Step 2+(★ P1.4-amend)

- **Why rejected**(★ P1.4-amend):本 ADR §4.1 emission path Slice 3b 落地后 `__system__.revokes` Claims **会在 ledger 中存在** → user-facing read API(`fg.entities.where` / `fg.assertions.where` 等)若无 filter,system claims 会污染普通 read 结果;INV-15 filter 是 emission 时序耦合 invariant(per ADR-SYS-A §4.4.2 carve-out wording),必须 Slice 3b 同步落地。

### 5.2 Cross-Q rejected combinations

#### Option `SYS-B-defer-everything`:Slice 3b 仅做 Q5b emission;Q15 全留 Step 2+

- **Why rejected**:Q5b emission 走 `append_revocation_claim` 写 `__system__.revokes` Claim 到 claims 表;若 Q15.3 claim_meta 改造不同步,meta 走 meta_rows / annotation_rows 旧 schema → Slice 3b 后跨 schema 混合不连贯;若 Q15.2 value+value_tag 不同步引入,`__system__.revokes` 必须走 1-elem rest_terms 包装 → 跟 Q15.1 weak enforce 冲突。**Q5b + Q15 是同 cluster cohesive 决策**,违反 meta-ADR §4.2 grouping.

#### Option `SYS-B-include-Q-PR1`:Slice 3b 包含 PyReason adapter rewrite + 精简 4 真正 drop 列

- **Why rejected**:scope explosion — Slice 3b 从 ledger schema migration 扩展到 adapter rewrite(跨模块);违反 meta-ADR §4.4 Step 1 zero-Q-PR1 hard rule + user reviewer §1.3 第 3 项;adapter rewrite 涉及 PyReason 适配器内部 Relationship instance 重设计,跟 ledger migration 是不同 concern。Step 2+ Slice 5 独立 slice 更干净。

#### Option `SYS-B-INV-9-strict`:Slice 3b 加 runtime read-path strict assertion(`assert len(claim.rest_terms) <= 1` 在读路径)

- **Why rejected**:本 ADR §4.2 选 (c) 不加 blanket weak enforce(per §4.2.3);read path strict assertion 是 ADR-INV9 / Q4 scope(per ADR-IC §4.4 / meta-ADR §4.4 "INV-9 strict enforcement 留 Step 2+ adapter rewrite");Slice 3b 强行加 read path strict 会跟 ADR-INV9 决策耦合 + 跟 PyReason 适配器现有 2-position 行为冲突。

#### Option `SYS-B-no-INV-12-defense`:Slice 3b 不在 write_protocol 加 INV-12 part 2 defense in depth(只 application layer check)

- **Why rejected**(★ P1.1-amend cascade):per meta-ADR §4.4 4-layer enforcement 模式 + 跟 ADR-FI §4.4.2 caller contract / ADR-SYS-A §4.2.2 Layer B defense in depth 一致 — application 层是 source of truth,write_protocol 层加 defense in depth catch bypass-application-layer 路径(internal migration tool / test fixture / 其他直接调 write_protocol 的 caller);marginal 5 行 cost。

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
- `src/factgraph/core/store/ledger.py:363-378` `Ledger.append_assertion(claim, claim_args, meta_rows, ...)` typed-rows API(★ P1.3-amend — 本 ADR §4.1.4 write_protocol layer 调用此 API,无需新 Ledger 方法)
- `src/factgraph/core/store/ledger.py:430-451` `_write_session` atomic context manager(本 ADR §4.1 emission 走该 transaction)
- `src/factgraph/core/evidence/write_protocol.py:128-157` shipped `set_field` high-level normalization 模式(★ P1.3-amend — 本 ADR §4.1.4 `append_revocation_claim` 跟此模式一致)
- `src/factgraph/core/evidence/write_protocol.py:137` `_compute_ingest_key` + `Idempotency` preflight dedup(★ P2-amend — 本 ADR §4.5.2 `set` preserve dedup 用 `_find_active_claim_by_value` 替代;`add` 改 multiset)
- `src/factgraph/core/evidence/write_protocol.py:170-208` `retract_by_asrt` 当前写 Revokes 行(将改 rename + 重写 → `append_revocation_claim` 写 `__system__.revokes` Claim;含 INV-12 part 2 reassertion per §4.1.5)
- `src/factgraph/core/evidence/write_protocol.py:179-180` shipped INV-12 part 1 existence check(`get_claim(...) is None → raise`)— 本 ADR §4.1.5 加 part 2(target.pred_id.startswith("__system__.") → raise)
- `src/factgraph/core/protocol/tup_v1.py` 8 tag canonical;`rest_terms` JSON 序列化 path(Slice 3b NEW writes 永远 [];legacy adapter 路径继续用;Slice 5 drop 列后取消)

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
- §4.2 Q15.1 答 + §4.3 Q15.2 答 + §4.4 Q15.3 答 + §4.5 Q15.4 答 + §4.7 Q15.5 答 — 5 项 minimum coverage **全部满足**;**额外**锁 §4.6 INV-15 read-path filter(per meta-ADR §4.3 "不限制 ADR-SYS-B 加额外 sub-decisions"允许)+ §4.1.5 INV-12 part 2(per ledger-spec §4.9 必备 invariant)— 二者闭合 ADR-SYS-A §4.4.2 + ledger-spec §4.9 carve-out

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 3b ledger migration refactor blueprint**(`workflow/blueprints/active/2026-05-29_slice-3b-ledger-migration.md`)可起草 — Q5b + Q15.1-Q15.5 + INV-12 part 2 + INV-15 read filter 全部 locked;§4.7.3 acceptance criteria 是 Stage 4 blueprint outline
- **ADR-INV9**(Q4)起草 — 本 ADR §4.2 选 (c) dual-coexistence + INV-9 strict/weak enforce 整套留 ADR-INV9 — 边界已 carve-out
- **Slice 5(Step 2+)PyReason adapter rewrite slice** 准备 — 本 ADR §4.7.2 显式标 三项绑定(drop rest_terms 列 + adapter rewrite + ADR-INV9 strict enforce)是 Slice 5 acceptance criteria
- **ADR-IE / ADR-DOCS** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 3b blueprint draft(`workflow/blueprints/active/2026-05-29_slice-3b-ledger-migration.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-SYS-B adopt 后 |
| Slice 3b pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `Revokes(` / `meta_rows` / `annotation_rows` / `ingest_keys` / `Idempotency(` / `_compute_ingest_key` / `_find_active_claim_by_ingest_key` / `retract_by_asrt` — 全部 migrate;**额外**扫所有 read query 路径 加 INV-15 filter `pred_id NOT LIKE '__system__.%'` 默认 + by_id bypass | Slice 3b blueprint preflight(Step 4.6.5)| Slice 3b blueprint scoped 后 |
| Slice 3b implementation:DDL 重写(drop 5 表 + create 2 表 + claims 表加 value+value_tag 双列 + 保留 rest_terms 列 + claim_args 表 drop)| Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 3b implementation:`write_protocol.append_revocation_claim` 函数(rename + 重写 from `retract_by_asrt`)+ INV-12 part 2 defense-in-depth + 简化 `find_revoker` SQL(无 dead subquery)| Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 3b implementation:application layer dispatch(INV-7c + INV-12 part 2 + find_revoker idempotency)+ INV-15 read-path filter to user-facing read APIs | Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 3b implementation:`Idempotency` 参数链清理 + `set` preserve dedup via `_find_active_claim_by_value` + `add` 改 multiset semantics + retract idempotency 走 find_revoker(INV-14)| Slice 3b implementation | Slice 3b Step 4.7 |
| Slice 5(Step 2+)blueprint:引用本 ADR §4.7.2 作为三项绑定 acceptance(drop rest_terms 列 + adapter rewrite + ADR-INV9 strict enforce)| Slice 5 blueprint preflight | Step 2+ |
| docs sync(Slice 4)— `ledger-schema-specification` 跟 ADR-SYS-B 对齐;`04_api_surface.en.md` 加 retract idempotency + `_meta` claim_meta path + INV-15 read filter + `add` multiset behavior change 说明;`identity-mechanism-redesign §10` 同步 | Slice 4 docs sync | Slice 3b 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-INV9 起草时 Header `Depends on:` 引用本 ADR(§4.2 选 (c) dual-coexistence + INV-9 enforce 留 ADR-INV9);Slice 5 blueprint preflight 引用本 ADR §4.7.2
- **Blueprint pillar**:Slice 3b blueprint preflight(Step 4.3)必须 re-read 本 ADR §4 Decision;**§4.7.3 acceptance criteria 是 Stage 4 minimum coverage**
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q5b + Q15 行 status 仍是 "待 ADR 决策" — 实际 ADR-SYS-B 已 lock;**不**触发 audit doc post-stage sync(跟其他 Stage 2 ADRs 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3b blueprint 不可单方面 override Q5b / Q15.1-Q15.5 / INV-12 part 2 / INV-15 / write dedup 决策;若需要 override,走 "本 ADR superseded by 新 ADR-SYS-B-v2" 路径
- §4.1 emission path:carry-forward — internal exception 永远走专用 function name(`write_protocol.append_revocation_claim`),不可改为 generic `Ledger.append_claim(pred_id=..., bypass_namespace=True)`(违反 ledger-spec §4.7 "internal API 分离" + 本 ADR §5.1 alt rejected);函数 layering 永远 write_protocol normalize + Ledger typed append
- §4.1.5 INV-12 part 2(no revoke-of-revoke):carry-forward — application + write_protocol 双层 check 不可降级
- §4.2 选 (c) dual-coexistence + Step 2+ drop 列:carry-forward — Slice 3b NEW writes 永远 rest_terms=[];legacy 路径 Slice 5 时统一 rewrite;INV-9 strict/weak enforce 整套留 ADR-INV9
- §4.3 value + value_tag 双列 + `__system__.revokes` 形态 + general canonical mapping:carry-forward — 不可改 Claim 形态(per INV-11);不可去 partial index `idx_claims_revokes`;mapping 表是 Slice 3b NEW writes 的 binding contract
- §4.4 claim_meta 完全替代 + 4 列 drop + 复合 PK:carry-forward — Slice 5+ 不可重新加回 namespace / category / origin / derivation / kind / value_tag / surrogate id 列
- §4.5 ingest_keys 删除 + ledger 不 idempotency + set preserve dedup / add multiset:carry-forward — Slice 5+ 不可重新引入 ledger-side idempotency 机制;`set` 永远应用 layer dedup;`add` 永远 multiset
- §4.6 INV-15 read-path default filter:carry-forward — `fg.entities.*` / `fg.fields.*` / `fg.assertions.where/active/all/field` 永远默认 exclude `__system__.*`;by_id/by_ids bypass 永久 carry-forward(audit/replay 不可阻断)
- §4.7 Slice 3b 完成判定 acceptance:carry-forward — Stage 4 acceptance criteria 任一项缺失则 Slice 3b blueprint 不可 mark `implemented`
- §4.7.2 deferred-to-Slice-5 三项绑定 explicit contract:**Slice 5 acceptance criteria 必须** drop rest_terms 列 + Q-PR1 adapter rewrite + ADR-INV9 strict enforce;Slice 5 不可单独完成其一(三项绑定)

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.8 Q5b + Q15.1-Q15.5 + INV-12 part 2 + INV-15 + 时序 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥13 项含 4 项 P1/P2-amend 新增)+ cross-Q rejected combinations(≥4 项含 1 项 P1.1-amend 新增)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / 4 cross-ADR 兼容性 6 类 evidence
- [x] §6.6.4 显式 confirm meta-ADR Q15.1-Q15.5 minimum coverage 全部满足;额外 §4.6 INV-15 + §4.1.5 INV-12 part 2 在 meta-ADR §4.3 "允许额外 sub-decisions" 范围内
- [x] §6.5 显式 confirm 全文 zero Q-PR1 dependency;Step 2+ Slice 5 三项绑定 carve-out 非 dependency
- [x] §4.1 Q5b internal emission path **不**走 ADR-SYS-A G1/G2 user-facing guard(走专用 `write_protocol.append_revocation_claim` 函数,pred_id hardcoded;Ledger 层无新方法,用 typed `Ledger.append_assertion` API)★ P1.3-amend
- [x] §4.1.5 INV-12 part 2 显式锁(application + write_protocol 双层 check)★ P1.1-amend
- [x] §4.3.2 general canonical value/value_tag mapping 覆盖所有 Claim form(existence / unary value / entity_ref / multi / revoke / legacy adapter)★ P1.2-amend
- [x] §4.5.2 set 保留 preflight dedup(via `_find_active_claim_by_value`)+ add 改 multiset semantics ★ P2-amend
- [x] §4.6 INV-15 read-path default filter sub-decision(close ADR-SYS-A §4.4.2 carve-out)★ P1.4-amend
- [x] §4.7.3 显式 enumerate Slice 3b acceptance criteria(分 schema migration / emission path / canonical mapping / write dedup / INV-15 / cross-ADR 6 类)
- [x] §4.2.4 + §4.7.2 显式 deferred-to-Slice-5 三项绑定 carve-out(drop rest_terms 列 + adapter rewrite + ADR-INV9 strict enforce)
- [x] Header `Depends on:` 引用 meta-ADR + ADR-IC + ADR-API + ADR-SYS-A adopted commits
- [x] §7.4 显式 no-retroactive carry-forward 10 项

Post-adoption verification(implementation 阶段验证):

**Schema migration**:
- [ ] Slice 3b blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR + Stage 4 §10 Outcome acceptance criteria 含 §4.7.3 全部项
- [ ] Slice 3b implementation:`meta_rows` 表 dropped + `annotation_rows` 表 dropped + `claim_meta` created with schema `(asrt_id, key, value)` + PRIMARY KEY (asrt_id, key) + 无 4 dropped 列 + 无 kind/value_tag/surrogate id(per §4.4 + §4.4.3)
- [ ] Slice 3b implementation:`revokes` 表 dropped(per §4.1 + §4.7.1 精简 3)
- [ ] Slice 3b implementation:`claims` 表加 `value` + `value_tag` 双列 + `rest_terms` 列保留;`claim_args` 表 dropped(per §4.3 + §4.2)
- [ ] Slice 3b implementation:`ingest_keys` 表 dropped(per §4.5 精简 6)

**Emission path + function layering**(★ P1.3-amend):
- [ ] Slice 3b implementation:`write_protocol.append_revocation_claim(ledger, revoked_asrt_id, meta) -> str` 函数存在 in `evidence/write_protocol.py`(**不在** `core/store/ledger.py`)
- [ ] Slice 3b implementation:`Ledger.append_assertion(...)` typed-rows API 不动(无新 Ledger 方法);`append_revocation_claim` 内部构造 typed Claim with pred_id hardcoded `"__system__.revokes"` + 调 `Ledger.append_assertion(claim=, claim_args=[], meta_rows=)`
- [ ] Slice 3b implementation:`fg.assertions.retract(asrt_id)` → application layer 4 步 dispatch(per §4.1.1):ADR-IC reject + INV-12 part 2 + find_revoker idempotency + lowering verified

**INV-12 part 2**(★ P1.1-amend):
- [ ] Slice 3b implementation:application layer `fg.assertions.retract(revoker_asrt_id)`(target 是 `__system__.revokes` Claim)raise `SDKStoreError(INV-12 part 2)` 含 §4.1.5 reference + revoke-of-revoke forbidden hint
- [ ] Slice 3b implementation:write_protocol layer `append_revocation_claim` defense-in-depth — 直接 callers 跳过 application layer 同样 raise `WriteProtocolError(INV-12 part 2)`(per §4.1.4 code)
- [ ] Slice 3b implementation:`find_revoker(target_asrt_id)` SQL 简化为单 `WHERE pred_id='__system__.revokes' AND value=?`;**不含** "exclude revoked revokers" dead subquery(per §4.5.4);`idx_claims_revokes` partial index existed

**Canonical value/value_tag mapping**(★ P1.2-amend):
- [ ] Slice 3b implementation:NEW write paths(`fg.fields.set/add`,`append_revocation_claim`)写 value+value_tag per §4.3.2 mapping;rest_terms 列写 `[]`(empty)
- [ ] Slice 3b implementation:Existence Claim(`<EntityType>:exists`)写 value=NULL,value_tag=NULL;rest_terms=[]
- [ ] Slice 3b implementation:Unary field Claim 写 value=canonical text,value_tag=tag;rest_terms=[]
- [ ] Slice 3b implementation:`__system__.revokes` Claim 写 value=revoked_asrt_id,value_tag="string",rest_terms=[];claim_meta optional(source/trace_id/note)atomic 同 transaction
- [ ] Slice 3b implementation:LEGACY PyReason adapter 路径 **不动** — 继续写 rest_terms=[a, b](dual-coexistence per §4.2.2)
- [ ] Slice 3b implementation:Read path 优先 value+value_tag;legacy claims(value+value_tag NULL)fallback to rest_terms;Slice 5 后 fallback dead code 清理

**Write dedup semantics**(★ P2-amend):
- [ ] Slice 3b implementation:`Idempotency(...)` 参数从 `Ledger.append_assertion` 签名移除
- [ ] Slice 3b implementation:`fg.fields.set(F, e_ref, value)` preserve dedup — preflight 走 `_find_active_claim_by_value(pred_id, e_ref, value, value_tag)` SQL(走 `idx_claims_pred_value`);命中 return 既有 asrt_id 不写新 claim
- [ ] Slice 3b implementation:`fg.fields.add(F, e_ref, value)` multiset semantics — 每次 append 新 asrt_id;允许 duplicates;**docs Slice 4 显式说明跟 shipped `add_field` aliased to `set_field` 行为变化**
- [ ] Slice 3b implementation:`_compute_ingest_key` / `_find_active_claim_by_ingest_key` 函数移除(`_compute_ingest_key` 可保留作 SDK helper 不从 ledger 调 per §4.5.3)
- [ ] Slice 3b implementation:retract idempotency 走 `find_revoker` 路径 verified(INV-14)

**INV-15 read-path filter**(★ P1.4-amend):
- [ ] Slice 3b implementation:`fg.entities.get/where/match/exists/ref` underlying SQL 加 `AND pred_id NOT LIKE '__system__.%'` 默认 filter(per §4.6.2)
- [ ] Slice 3b implementation:`fg.assertions.where(...)` / `.active` property / `.all` property underlying SQL 加 INV-15 filter
- [ ] Slice 3b implementation:`fg.assertions.field(F)` / `.at(t)` 终结 RecordSet 继承 filter
- [ ] Slice 3b implementation:`fg.assertions.by_id(asrt_id)` / `by_ids([...])` **bypass** filter — 直接走 `WHERE asrt_id = ?`(per §4.6.4 audit/replay use case)
- [ ] Slice 3b implementation:contract test — emission `__system__.revokes` Claim 后,`fg.assertions.where(...)` 默认结果不含 system claim;但 `fg.assertions.by_id(revoker_asrt_id)` 可返回该 system Claim

**Cross-ADR invariant**:
- [ ] all `__system__.*` namespace 仅由 `write_protocol.append_revocation_claim` emit(无其他 emission path;per ADR-SYS-A §4.4.2 SYS-B-owned emission concern)
- [ ] contract test:`fg.assertions.retract(asrt_id)` 后 `find_revoker(asrt_id)` 非 None;重复 retract 同 asrt_id 返回**同一** revoker_asrt_id(INV-14 idempotency via find_revoker)
- [ ] contract test:`__system__.revokes` Claim 形态严格(`pred_id` / `e_ref` / `value` / `value_tag` / `rest_terms=[]`);claim_meta 可选附 source / trace_id / note 等 atomic
- [ ] contract test:Identity Claim retract(via `fg.assertions.retract(identity_asrt_id)`)在 application layer reject(per ADR-IC §4.1 INV-7c)**不**到达 `append_revocation_claim`;同理 `:exists` Claim retract 经 existence-claim transitional guard reject
- [ ] contract test:`__system__.revokes` Claim 试图被 retract(`fg.assertions.retract(revoker_asrt_id)`)在 application + write_protocol 双层 reject(per §4.1.5 INV-12 part 2)
- [ ] ADR-SYS-A G1 / G2 guard 跟 `append_revocation_claim` 互不干扰 verified — `__system__.revokes` 不进 schema_ir;G1 catch 不到;G2 不适用

**Slice 5 deferred marker + docs sync**:
- [ ] **Step 2+ Slice 5 deferred** explicit marker:`workflow/blueprints/active/2026-05-29_slice-5-adapter-rewrite.md` §0 Inputs 引用本 ADR §4.7.2 + 标三项绑定 acceptance(drop rest_terms 列 + Q-PR1 adapter rewrite + ADR-INV9 strict enforce)
- [ ] Slice 4 docs sync:`ledger-schema-specification §9` 跟 ADR-SYS-B §4 时序对齐;`04_api_surface.en.md` 加 retract idempotency(find_revoker)说明 + `_meta` claim_meta path + INV-15 read filter + `add` multiset behavior change;`identity-mechanism-redesign §10` 跟 ADR-SYS-B 对齐

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-SYS-B drafted | Q5b + Q15.1-Q15.5(meta-ADR §4.3 acceptance boundary 5 项必答 全覆盖)+ 时序。Q5b internal emission 走专用 `append_revocation_claim` function(不走 G1/G2);Q15.1 Slice 3b 保留 rest_terms 列 + weak enforce(Step 2+ Slice 5 真正 drop 同 adapter rewrite);Q15.2 同步引入 value + value_tag 双列;Q15.3 完全替代 claim_meta + drop 4 列;Q15.4 Slice 3b 删除 ingest_keys;Q15.5 option (b) 子集落地 + Step 2+ 转(5 项必做 + 1 项延后)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-IC adopted @ `2d0866ed` + ADR-API adopted @ `66434490` + ADR-SYS-A adopted @ `75f1c8bc` + user reviewer 2026-05-29 ADR-SYS-B 4 项 directional review focus + ledger-spec §2-§9 design-point。Branch: `v0.2.0-q-sys-b-revokes-migration-decision-2026-05-29`。Commit: `40174986` |
| 2026-05-29 | proposed | ADR-SYS-B amended(P1/P2 fixes,still proposed)| User reviewer post-draft review(同日)返回 5 findings:**(P1.1)** INV-12 part 2(no revoke-of-revoke)未在原 draft 落地 + find_revoker SQL 暗示允许 revoke-of-revoke。重构 §4.1 加 §4.1.5 INV-12 part 2 显式锁(application layer + write_protocol layer defense-in-depth);§4.5.4 简化 find_revoker SQL(去 dead "exclude revoked revokers" subquery);加 cross-Q rejected option `SYS-B-no-INV-12-defense`。**(P1.2)** value/value_tag 只定义了 revoke claim,普通 claim 的 canonical 映射缺失。重构 §4.3 加 §4.3.2 general canonical value/value_tag mapping 表(覆盖 existence / unary value / entity_ref / multi / revoke / legacy adapter 全 Claim form)+ §4.3.4 read path 优先级;§4.2 重新选 (c) dual-coexistence(NEW writes 用 value+value_tag rest_terms=[];legacy 路径不动);**移除原 blanket weak enforce**(会 break adapter 违反 zero-Q-PR1)— INV-9 enforce 整套留 ADR-INV9;加 Q15.1 alternative reject `Slice 3b 加 blanket weak enforce`。**(P1.3)** `append_revocation_claim` 层级签名混乱(放 ledger.py 收 raw meta vs §4.8 写 write_protocol)。重构 §4.1.4:函数位置锁 `evidence/write_protocol.py`(跟 shipped `set_field` 模式一致);**Ledger 层无新方法**,使用现有 `Ledger.append_assertion(claim, claim_args=[], meta_rows, ...)` typed-rows API;write_protocol 负责 raw meta normalization + asrt_id generation + 构造 typed Claim with hardcoded pred_id;加 Q5b alternative reject `append_revocation_claim 放 ledger.py`。**(P1.4)** INV-15 read-path default filter 被 SYS-A carve out 给 SYS-B 但 SYS-B 未锁。新增 §4.6 INV-15 read-path default filter sub-decision(default exclude `__system__.*`;asrt_id 直查路径 bypass per Rule 5);§4.6.2 Read API 矩阵(`fg.entities.*` / `fg.fields.*` / `fg.assertions.where/active/all/field` filter;by_id/by_ids bypass);§4.6.3 SQL 实施约定;§4.6.4 by_id bypass rationale;§4.6.5 跟 ADR-API §4.2 AssertionView 类型契约不冲突 confirm;原 §4.6/§4.7/§4.8 renumber → §4.7/§4.8/§4.9。加 INV-15 alternative reject(留 Step 2+)。**(P2)** 删除 ingest_keys 后普通重复写入语义未定。重构 §4.5 加 §4.5.2 普通 set/add write dedup 语义显式锁:`fg.fields.set` preserve preflight dedup via `_find_active_claim_by_value(pred_id, e_ref, value, value_tag)` SQL(替代 ingest_keys lookup);`fg.fields.add` 改 multiset semantics(每次 append 新 asrt_id;**行为变化** 跟 shipped `add_field` aliased to `set_field` 不同 — Slice 4 docs sync 显式说明);加 Q15.4 alternative reject `set/add 都走 multiset`。同步 cascade:§4.7.3 acceptance criteria 重写(分 schema migration / emission path / canonical mapping / write dedup / INV-15 / cross-ADR 6 类);§4.7.2 deferred 改三项绑定(drop rest_terms 列 + Q-PR1 + ADR-INV9 strict enforce);§6.2 shipped citations 加 5 项 P1/P2-amend 锚点;§6.6.4 meta-ADR coverage 加 §4.6/§4.1.5 在"允许额外 sub-decisions"范围内 confirm;§7.2 follow-up + §7.4 no-retroactive boundary 扩 10 项;§8 acceptance 重写(13 项 proposed ✓ + 35 项 post-adoption ☐ 分 7 类:schema/emission/INV-12/canonical/dedup/INV-15/cross-ADR/Slice 5)。 |
