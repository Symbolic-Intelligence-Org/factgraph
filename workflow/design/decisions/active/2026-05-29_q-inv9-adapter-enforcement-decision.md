# Q-INV9 Decision: INV-9 unary enforce timing + Q-PR1 PyReason adapter rewrite path

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Q4(INV-9 unary fact enforcement timing)+ Q-PR1(PyReason adapter rewrite path)— **解耦 Step 1 / Slice 3b 跟 adapter rewrite 的 dep**;**关闭 ADR-SYS-B §4.7.2 三项绑定** 的第 3 项 contract(strict enforce + drop rest_terms 列 + adapter rewrite,三项绑定 in Slice 5)。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q4 row(`audit:517`)+ §6 INV-9 row(`audit:283`)+ §5.4 baseline shipped citations(`_edge_rest_terms` 2-element / `_compute_ingest_key` / `accept_pyreason_session`)
  - `workflow/design/decisions/active/2026-05-29_q-sys-b-revokes-migration-decision.md` adopted `6b0ac349` — §4.2 选 (c) dual-coexistence + §4.7.2 deferred-to-Slice-5 **三项绑定** carve-out;**本 ADR 必须**锁三项绑定的第 3 项(ADR-INV9 strict enforce 形态)
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted `ebafdb0c` — §4.4 Step 1 zero-Q-PR1 dependency hard rule + meta-ADR Q4 carve-out
  - Identity-mechanism-redesign §11 Adapter 边界 (Q-PR1)(`:803-829`)— PyReason `_edge_rest_terms` 2-position 问题 + 3 候选解法 + 推荐 (A) Relationship Claim lowering
  - ledger-spec §4.6 INV-9(`:277-288`)— Ledger Claim 是 unary fact + value+value_tag 双列设计
- Outputs / Downstream:
  - Slice 5(Step 2+)PyReason adapter rewrite slice 起草前置 — 本 ADR §4.3 / §4.4 锁定 acceptance criteria 三项绑定
  - Slice 3b implementation(per ADR-SYS-B):本 ADR §4.2 明确 Slice 3b 不加 blanket runtime weak enforce — Slice 3b blueprint enforce 部分 dead code 可清理
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-inv9-adapter-enforcement-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.4 Step 1 zero-Q-PR1 dependency hard rule + Q4 cluster归属 — System namespace + adapter,Slice 3b + Slice 5)
  - `workflow/design/decisions/active/2026-05-29_q-sys-b-revokes-migration-decision.md` adopted @ `6b0ac349`(ADR-SYS-B §4.2 选 (c) dual-coexistence + §4.7.2 三项绑定 carve-out;本 ADR §4.3 / §4.4 **必须**关闭三项绑定 contract)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q4 — adapter cluster + System namespace cluster 跨界 Q:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q4 | INV-9 enforcement timing vs Q-PR1 adapter rewrite 解耦 | `audit:517` | System namespace + adapter |

audit Q4 question framing:
- option (a) Step 1 INV-9 strict + adapter 同步 rewrite — **会 force Q-PR1 进 Step 1,违反 meta-ADR §4.4 zero-Q-PR1 hard rule**
- option (b) Step 1 不 enforce INV-9,留 Step 2+ adapter rewrite slice 一起 lock — **本 ADR 选定方向**

### 1.2 Meta-ADR locked constraints relevant to Q4

- **§4.2 grouping**:Q4 跨 System namespace + adapter cluster;**单 Q ADR**(per meta-ADR §4.2 — Q4 自身一个 sub-decision)
- **§4.4 Step 1 zero-Q-PR1 dependency hard rule**:Step 1 / Slice 3b implementation **不**得 depend on PyReason adapter rewrite — 本 ADR §4.2 显式实施
- **§4.4 4-layer enforcement**:本 ADR §4.3 Slice 5 strict enforce 在 write path(Ledger.append_assertion entry);**不**触 protocol delayed 层(per ADR-SYS-B §4.2 / 本 ADR §4.2)

### 1.3 ADR-SYS-B §4.7.2 三项绑定 contract — 本 ADR 必须关闭

ADR-SYS-B adopted `6b0ac349` §4.7.2 Slice 5 三项绑定 carve-out:

> | 项 | 延后内容 | 触发条件(三项绑定)|
> |---|---|---|
> | 精简 4 真正 drop `rest_terms` 列(+ Q-PR1 adapter rewrite + ADR-INV9 strict enforce)| ALTER TABLE drop rest_terms;adapter rewrite 改写 Pyreason 2-position;ADR-INV9 锁的 strict / weak enforce 落地 | **三项绑定:任一项缺失则 Slice 5 不可 mark `implemented`** |

本 ADR **必须**:
- §4.3 锁定第 3 项 — INV-9 strict enforce 形态(write-path runtime check on Ledger.append_assertion entry)
- §4.4 锁定第 2 项 contract — PyReason adapter rewrite 走 identity §11.2 option (A) Relationship Claim lowering
- §4.5 显式 confirm 三项绑定 — 任一项缺失则 Slice 5 不可 mark implemented

### 1.4 Shipped baseline(audit §5.4 / §6)

**INV-9 enforcement 状态**(audit INV-9 row `:283`):**(f) target-gap / pending migration**:
- `core/store/ledger.py:82-88` `claims` 表 shipped 为 5 列(`seq, asrt_id, pred_id, e_ref, rest_terms`),`rest_terms TEXT NOT NULL` 是 multi-arg JSON list — pre-migration baseline
- shipped 无 `value` / `value_tag` 双列(target schema per ledger-spec §3.1)
- `Claim` dataclass(`:22-26`)`rest_terms: list[tuple[str, Any]]` n-ary shape
- shipped `set_field` 无 `len(rest_terms) <= 1` runtime check — enforce path 当前不存在

**Q-PR1 baseline**(audit `_edge_rest_terms` row `:231` + identity §11.1):
- `adapters/pyreason/accept.py:187-205` `_edge_rest_terms(fact, pred_spec)` **当前返回 2-element rest_terms**:`[(to_ref_tag, to_ref_value), (value_tag, fact["value"])]`
- `adapters/pyreason/accept.py:94-160` `accept_pyreason_session`:
  - node facts → `set_field(ledger, pred_id, node_e_ref, [(value_tag, value)], meta)` — **unary**(1 个 rest_terms 元素)
  - edge facts → `set_field(ledger, pred_id, from_e_ref, [(to_tag, to_ref), (value_tag, value)], meta)` — **n-ary**(2 个 rest_terms 元素,违反 INV-9)
- shipped PyReason adapter 没有 `Relationship` Claim 形态使用 — 全部走 generic `set_field` 路径(rest_terms-based)

**Slice 3b vs Slice 5 enforce 形态**:
- Slice 3b(per ADR-SYS-B §4.2 选 (c)):`claims` 表加 `value` + `value_tag` 双列;NEW write paths 用 value+value_tag;legacy adapter 继续写 rest_terms;**不**加 blanket runtime weak enforce — Slice 3b 后 ledger 仍接受 n-ary writes
- Slice 5(本 ADR 锁定):drop `rest_terms` 列 + adapter rewrite(per §4.4)+ Ledger.append_assertion entry 加 `len(rest_terms) <= 1` runtime strict enforce(per §4.3)— **三项同时落地**

## 2. Scope

本 ADR **锁**以下 sub-decisions(单 Q 但跨 cluster):

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q4-1** | INV-9 strict enforce **形态** — write-path runtime check at Ledger.append_assertion entry;`if len(rest_terms) > 1: raise WriteProtocolError`(per ledger-spec §4.6 + 本 ADR §4.3.2);**不**加 read-path strict assertion(per §3 Non-scope)|
| **§4.2 Q4-2** | INV-9 enforce **Step 1 / Slice 3b 时机** — Slice 3b 期间 **完全不加** runtime enforce(实施 ADR-SYS-B §4.2 选 (c) dual-coexistence;legacy adapter 继续写 2-position rest_terms);跟 meta-ADR §4.4 zero-Q-PR1 hard rule 一致 |
| **§4.3 Q4-3** | INV-9 enforce **Step 2+ / Slice 5 时机** — Slice 5 strict enforce 落地 + 三项绑定其一(per ADR-SYS-B §4.7.2)|
| **§4.4 Q-PR1** | PyReason adapter rewrite path — 走 identity §11.2 option (A) Relationship Claim lowering;edge facts reify 为 ledger 已有的 unary Relationship Claim 形态(`Claim(pred_id=<rel_type>, e_ref=<source>, value=<target_e_ref>, value_tag="entity_ref")`);**不**改 ledger schema、**不**为 adapter 开 INV-9 例外、**不**做 edge 拆 2 Claim |
| **§4.5** | 三项绑定 closure — §4.3 INV-9 strict + §4.4 adapter rewrite + ADR-SYS-B §4.7.2 第 1 项 drop rest_terms 列 = Slice 5 acceptance 必备 3 项;任一项缺失 → Slice 5 不可 mark implemented |

## 3. Non-scope

本 ADR **不**锁(per user reviewer §1.3 第 3 项 zero-Q-PR1 carve-out + meta-ADR §4.2 grouping + cross-ADR boundaries):

| 不锁 | 留给谁 |
|---|---|
| Slice 3b ledger migration(claims/claim_meta schema flip / drop 5 表 / etc.)| **ADR-SYS-B**(已 adopted `6b0ac349`)|
| Slice 3b dual-coexistence 实施(NEW writes value+value_tag / legacy rest_terms 路径)| **ADR-SYS-B §4.2 + §4.3**(已 adopted)|
| `Ledger.find_claim_args` compatibility wrapper / set+add dedup 语义 / INV-15 read filter | **ADR-SYS-B**(已 adopted)|
| **Slice 5 blueprint implementation 具体步骤**(PyReason adapter rewrite 内部模块分解 / migration 顺序 / contract test 形态等)| **Slice 5 blueprint**(per CADENCE — blueprint 起草前置由本 ADR + ADR-SYS-B §4.7.2 锁定 acceptance) |
| **PyReason adapter 内部 Relationship 实例化细节**(`_compile_relationship` 跟 PyReason model 对接细节;edge fact → Relationship Claim 转换的具体函数签名)| **Slice 5 blueprint** + 本 ADR §4.4.4 仅锁 lowering 路径形态 |
| Read-path INV-9 strict assertion(`assert isinstance(claim, UnaryClaim)`) | **不锁**(per §4.1)— 本 ADR 显式选 write-path strict only;read-path strict 是不同议题(per §5.1 alt rejected)|
| 其他 invariant enforcement timing(INV-1 append-only / INV-2 asrt_id 全局唯一 / INV-3 atomic 原子写 / INV-4 tup_v1 协议 / INV-5 source of truth / INV-7c Identity claim ↔ e_ref 一致性 / INV-11/12/13/14/15 revoke 相关)| **已 shipped** 或**已锁 in 其他 ADR**(per audit §6 baseline + ADR-FI/IC/API/SYS-A/SYS-B 各自 adopted)|
| `Ledger.append_assertion` signature 演化具体形态(drop 3 参数 + DTO 演化)| **ADR-SYS-B §4.1.4 演化表**(已 adopted)— 本 ADR §4.3 仅锁 strict enforce check 位置 |
| Slice 3b 落地的 blueprint slicing | Slice 3b blueprint(per ADR-SYS-B)|
| Slice 5 落地的 blueprint slicing | Slice 5 blueprint |

## 4. Decision

### 4.1 Q4-1 — INV-9 strict enforce 形态:**write-path runtime check at Ledger.append_assertion entry**

**锁定**:INV-9(Ledger Claim 是 unary fact)的 strict enforce 形态 = **write-path runtime check**,位置在 `Ledger.append_assertion` entry;`if len(rest_terms) > 1: raise WriteProtocolError`。

#### 4.1.1 Check 形态精确性

```python
# core/store/ledger.py Ledger.append_assertion (Slice 5 加):
def append_assertion(
    self,
    *,
    claim: Claim,
    meta_rows: list[MetaRow],
    asrt_id: str | None = None,
) -> AppendResult:
    # ★ Slice 5 INV-9 strict enforce (per ADR-INV9 §4.1):
    if len(claim.rest_terms) > 1:
        raise WriteProtocolError(
            f"INV-9 violation: claim with pred_id={claim.pred_id!r} has "
            f"rest_terms length {len(claim.rest_terms)} > 1; "
            f"ledger Claim must be unary fact (value+value_tag pair).\n"
            f"  PyReason 2-position rest_terms should reify as Relationship "
            f"Claim per ADR-INV9 §4.4 / identity §11.2 option (A).\n"
            f"  See ADR-INV9 §4.3 for enforce timing rationale."
        )
    # ... rest of append_assertion (existing typed-rows append path)
```

**为什么 write-path entry**:
- per meta-ADR §4.4 4-layer enforcement table:SDK shell + application + protocol(write 边界)strict;**ledger 层 delayed** 是 Slice 3b 形态(per ADR-SYS-B §4.2 不加 blanket enforce);**Slice 5 时升级** ledger 层 strict
- `Ledger.append_assertion` 是 Slice 3b 后唯一 ledger append 边界(per ADR-SYS-B §4.1.4)— 在此处 enforce 覆盖**所有** caller(write_protocol / adapter / internal migration tool / 等)
- write-path runtime check 比 schema constraint(SQL CHECK)更灵活:可 raise typed exception with migration hint
- write-path runtime check 比 read-path strict assertion 早 fail-fast:写入时 catch,不等到读出来才发现(per §5.1 alt rejected)

#### 4.1.2 Check 触发 atomic 保证

- `Ledger.append_assertion` entry 在 `_write_session` atomic context 之内调用(per ADR-SYS-B §6.2 + ledger-spec §4.3 INV-3)
- enforce raise 时 transaction 回滚 — 不会有 partial state(claims 写了但 claim_meta 没写 等)
- 跟 INV-3 atomic 原子写一致

#### 4.1.3 Error message contract

- error message 必须含 ADR-INV9 §4.1 reference
- 必须含 migration hint:PyReason 2-position rest_terms 应该 reify 为 Relationship Claim(指 ADR-INV9 §4.4 + identity §11.2 option (A))
- 必须含 enforce timing reference(指 ADR-INV9 §4.3 Slice 5 落地)
- 触发场景应该极罕见(adapter rewrite 后);若 fire,通常是 caller bug(忘记 reify 或 reify 路径漏)

### 4.2 Q4-2 — Slice 3b 时机:**完全不加 runtime enforce**

**锁定**:Slice 3b 期间 **完全不加** `len(rest_terms) <= 1` runtime enforce — 实施 ADR-SYS-B §4.2 选 (c) dual-coexistence;legacy PyReason adapter 继续写 2-position rest_terms。

#### 4.2.1 决策选项 + 选择

| 选项 | 描述 | 评价 | 选 |
|---|---|---|---|
| (a) Slice 3b 加 blanket runtime weak enforce(`len > 1` raise)| INV-9 enforce 早落地 | **会立即 break PyReason adapter**(adapter 当前写 2-position rest_terms)— force Q-PR1 rewrite 进 Slice 3b → **违反 meta-ADR §4.4 zero-Q-PR1 hard rule** + user reviewer §1.3 第 3 项;Slice 3b scope 膨胀到 adapter rewrite | ✗ |
| (b) Slice 3b 仅在 NEW emission path 加 weak enforce(`append_revocation_claim` / NEW SDK fields paths)| 部分 enforce | 实施复杂度上升(两条 write path 一加一不加);"NEW 路径不会写 length > 1" 是 trivially 满足(无 caller 会犯);weak enforce 在 NEW 路径无防御价值(纯 dead check)| ✗ |
| **(c)** **Slice 3b 完全不加 runtime enforce**;legacy adapter 继续走 2-position rest_terms;Slice 5 时统一加 strict enforce + adapter rewrite + drop rest_terms 列 | 真正解耦 Q-PR1;Slice 3b implementation 干净(无 enforce-related 代码改动)| **跟 ADR-SYS-B §4.2 选 (c) 一致 + meta-ADR §4.4 zero-Q-PR1 一致 + user reviewer §1.3 第 3 项一致** | ✅ |

**选 (c)**。

#### 4.2.2 实施 implication

- Slice 3b implementation `Ledger.append_assertion` entry **不**加 `len(rest_terms) > 1` check
- Slice 3b blueprint 起草时 **不需要**包含 PyReason adapter 改动(adapter 继续 work — 因 schema 加 value+value_tag 双列但 rest_terms 列 retained per ADR-SYS-B §4.2 选 (c))
- Slice 3b implementation 仍可在 NEW path 的实施细节中 hardcode `rest_terms=[]`(`append_revocation_claim` / SDK fields.set 等)— **不**是 enforce,是 schema contract per §4.3.2

### 4.3 Q4-3 — Slice 5 时机:**strict enforce 落地 + ADR-SYS-B §4.7.2 三项绑定其一**

**锁定**:Step 2+ Slice 5 PyReason adapter rewrite slice **必须**同时:
1. ALTER TABLE drop `rest_terms` 列(ADR-SYS-B §4.7.2 第 1 项)
2. PyReason adapter rewrite — `_edge_rest_terms` 走 identity §11.2 option (A) Relationship Claim lowering(本 ADR §4.4)
3. **`Ledger.append_assertion` entry 加 §4.1.1 INV-9 strict enforce**(本 ADR §4.3)

**三项绑定**:任一项缺失则 Slice 5 不可 mark `implemented`。

#### 4.3.1 为什么三项必须同时落地

| 项 | 单独落地的失败模式 |
|---|---|
| 仅 drop rest_terms 列 | adapter break(adapter 当前依赖 rest_terms 写 2-position)— force adapter rewrite 同步 |
| 仅 adapter rewrite | adapter 改完后 ledger 仍有 rest_terms 列 + 仍接受 n-ary writes — INV-9 enforce 缺,migration tool / 测试 fixture / 第三方 caller 仍可写 length > 1 → 污染 ledger |
| 仅 INV-9 strict enforce | adapter 仍写 2-position → enforce 立即 raise → adapter 全部 break;同 (a) 情形 |

→ 三项独立任一项落地都不连贯;**绑定**是必要的 atomicity 保证。

#### 4.3.2 Slice 5 acceptance criteria(per §4.5)

Slice 5 blueprint Stage 4 acceptance criteria 必须包含:

- [ ] `claims` 表 ALTER TABLE drop `rest_terms` 列(per ADR-SYS-B §4.7.2 第 1 项)
- [ ] `Claim` DTO drop `rest_terms` 字段(typed dataclass);所有 `claim_args_from_rest_terms` / `canonical_bytes_tup_v1(rest_terms)` 路径 dead code 清理
- [ ] PyReason adapter `_edge_rest_terms` 改写为 `_edge_to_relationship_claim` 走 §4.4.1 lowering(本 ADR §4.4 acceptance)
- [ ] `Ledger.append_assertion` entry **无 `rest_terms` 参数**(drop 列 + DTO drop 字段后自然;**不再**需要 §4.1.1 runtime enforce — 因 type system 即保证 unary;**但是**仍保留作为 defense-in-depth — 防止 future regression / 任何重新引入 multi-arg claim 的 attempt)
- [ ] `find_claim_args` compatibility wrapper 简化(per ADR-SYS-B §4.3.5 Slice 5 cleanup):LEGACY rest_terms parse 路径 dead code 清理;只保留 NEW path decoder
- [ ] migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`(per ADR-SYS-B §4.3.5 Slice 5 cleanup)
- [ ] contract test 覆盖:PyReason edge fact → 走 Relationship Claim lowering → ledger 写 unary Claim per §4.4.1 形态
- [ ] contract test 覆盖:`Ledger.append_assertion` 接受 `claim.rest_terms = []` (or length 1 if rest_terms still exists in transitional model);**rejects** length > 1 with WriteProtocolError(INV-9 strict);跟 Slice 3b 行为有变化(Slice 3b 不 reject)

#### 4.3.3 Read-path 不加 strict assertion(per §3 Non-scope)

- 不加 `assert isinstance(claim, UnaryClaim)` 在 read path
- 不加 `assert claim.rest_terms == []` 在 read path(rest_terms 列 drop 后该 attr 不存在)
- Rationale:write-path strict + drop column + DTO drop field 是 type-level 保证;read-path strict 是 redundant defense
- 若 future 决定加 read-path strict(e.g., for migration audit),走独立 ADR 显式 supersede 本 §4.3.3

### 4.4 Q-PR1 — PyReason adapter rewrite:**走 identity §11.2 option (A) Relationship Claim lowering**

**锁定**:PyReason adapter `_edge_rest_terms` 路径(`accept.py:187-205`)Slice 5 改写 — edge facts 走 **Relationship Claim lowering**:n-ary edge `(source, target, value)` reify 为 ledger 已有的 **unary Relationship Claim**:

```text
shipped (Slice 3b 维持):
  edge fact: (source, target, value) → rest_terms=[(to_tag, to_ref), (value_tag, value)]
  写 ledger: Claim(pred_id=<edge_pred_id>, e_ref=<source>, rest_terms=[2-element])
  违反 INV-9 (n-ary)

Slice 5 后:
  edge fact: (source, target, value) → reify 为 Relationship Claim 形态
  写 ledger: Claim(
      pred_id=<rel_type>,
      e_ref=<source_e_ref>,
      value=<target_e_ref>,
      value_tag="entity_ref",
      # rest_terms 列已 drop;DTO 不含此字段
  )
  + 同时附 value/meta 信息走 claim_meta (per ledger-spec §3.2):
      claim_meta: {"edge_fact_value": value, "edge_fact_value_tag": <tag>, ...}
  满足 INV-9 (unary, value+value_tag pair)
```

#### 4.4.1 Lowering contract

per identity §11.2 option (A) + ledger-spec §3.1 Claim 形态枚举 "Entity-ref field" row:

- **pred_id**:relationship type identifier(`<rel_type>` — adapter 内部决定具体命名;跟 ADR-SYS-A §4.1 G2 guard 一致 — 不以 `__system__` 开头)
- **e_ref**:edge source 端点(已 materialized e_ref;走 ADR-IC §4.2 emission 路径)
- **value**:edge target 端点(已 materialized e_ref string)
- **value_tag**:`"entity_ref"`(per tup_v1 协议)
- **rest_terms**:Slice 5 drop 列后该 attr 不存在;**Slice 3b dual-coexistence 期间**adapter 仍写 rest_terms(legacy path)
- **claim_meta**:edge 的额外信息(原 `fact["value"]` / `value_tag` / etc.)走 claim_meta 走;具体 key 列由 Slice 5 blueprint 定

#### 4.4.2 跟 ledger-spec §3.1 + ADR-IC §4.2 兼容性

- per ledger-spec §3.1 "Entity-ref field" row:`pred_id=<EntityType>:<field_name>, value=<ref string>, value_tag="entity_ref"` — Relationship Claim 跟 entity field 都用 `entity_ref` tag;**ledger 不区分**(Relationship 是 schema-level 概念,ledger 层是 unary Claim with entity_ref value)
- per ADR-IC §4.2 emission input contract:emission 路径接受 `EntityRef(entity_type, identity={...complete bundle...})`;Relationship Claim 的 target 是 already-materialized e_ref(不重新 materialize)— 跟 ADR-IC 路径正交
- 跟 ADR-SYS-A G1/G2 guard:adapter 必须 use schema-declared relationship types(per ADR-SYS-A §4.2 Layer A.2);若 PyReason model 中的 edge 跟 schema 中的 Relationship 不对应,adapter 必须先 register 该 Relationship type(per ADR-API §4.5.1)— 这是 Slice 5 blueprint scope,不在本 ADR

#### 4.4.3 为什么不走 options (B) 给 INV-9 开 adapter 特例 / (C) Edge 拆 2 Claim

per identity §11.2 table:
- **(B) INV-9 adapter 特例逃生窗**:破坏 INV-9 统一性 — ledger 形态变成 "大多 unary + 少数 n-ary";代码 path 永远要 conditional handle;`Ledger.append_assertion` strict enforce check 要 carve-out;违反"统一 invariant"原则
- **(C) Edge 拆 2 个 Claim + synthetic 共享 ID**:复杂(2 个 Claim 关联);ledger 多写一倍 storage;synthetic ID 不属于 ledger native concept(违反 INV-5 source of truth — synthetic ID 是 derived state)

#### 4.4.4 Slice 5 implementation surface(本 ADR 不锁细节,留 Slice 5 blueprint)

本 ADR 仅锁 lowering 路径形态(per §4.4.1);具体 adapter 内部模块分解 / migration 顺序 / contract test 形态 等留 Slice 5 blueprint:

- adapter 内部 `_edge_rest_terms` rename / 重写 → `_edge_to_relationship_claim`(or similar);返回 typed `Claim`(value+value_tag)而非 rest_terms list
- `accept_pyreason_session` edge facts 路径:`set_field(...)` 调用改 `application/entities.create(...)` + `application/fields.set(<rel_type>:<...>, e_ref, target_e_ref)` 或 typed Claim 直接 emit
- PyReason model 跟 ledger Relationship 跟 schema 注册的 mapping 协议(若 PyReason 用不同名字,adapter 做 name translation)
- contract test:roundtrip PyReason edge fact → ledger Relationship Claim → query back 还原 PyReason model

### 4.5 Cross-Q decision summary + 三项绑定 closure

| Sub-decision | Decision | Implementation surface | Slice |
|---|---|---|---|
| Q4-1 | INV-9 strict enforce form = write-path runtime check at `Ledger.append_assertion` entry;`len(rest_terms) > 1` raise WriteProtocolError | Slice 5 加 5 行 check;Slice 3b 不动 | Slice 5 |
| Q4-2 | Slice 3b 完全不加 runtime enforce(per ADR-SYS-B §4.2 选 (c) 一致;legacy adapter 继续写 2-position)| 跟 ADR-SYS-B 同 — `Ledger.append_assertion` Slice 3b entry 不加 INV-9 check;legacy adapter 不动 | Slice 3b(零 enforce 改动)|
| Q4-3 | Slice 5 strict enforce 落地 + 三项绑定其一(per ADR-SYS-B §4.7.2)| Slice 5 加 §4.1.1 check + 三项绑定 acceptance criteria 落地 | Slice 5 |
| Q-PR1 | PyReason adapter rewrite 走 identity §11.2 option (A) Relationship Claim lowering | Slice 5 adapter `_edge_rest_terms` → `_edge_to_relationship_claim`;reify n-ary edge → unary Relationship Claim | Slice 5 |

**三项绑定 closure**(per §1.3 ADR-SYS-B §4.7.2 contract requirement):

```text
[Slice 5 acceptance — 三项 atomic 必备]
  ┌─ 项 1:ALTER TABLE drop `rest_terms` 列  ← ADR-SYS-B §4.7.2 第 1 项
  ├─ 项 2:PyReason adapter rewrite (lowering)  ← 本 ADR §4.4
  └─ 项 3:Ledger.append_assertion strict enforce  ← 本 ADR §4.1 + §4.3

  ★ 任一项缺失 → Slice 5 不可 mark `implemented`
  ★ 三项绑定保证 ledger schema(drop 列)+ caller(adapter)+ enforce
    (runtime check)同步达终态
```

**整体**:Slice 5 实施范围 ≈ 200-400 行代码改动:
- `core/store/ledger.py` Ledger.append_assertion entry 加 §4.1.1 INV-9 check + ALTER TABLE drop rest_terms 列 + Claim DTO drop rest_terms 字段
- `adapters/pyreason/accept.py` _edge_rest_terms rewrite 为 _edge_to_relationship_claim(per §4.4)
- `find_claim_args` wrapper LEGACY path 清理(per ADR-SYS-B §4.3.5 Slice 5 cleanup)
- migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`
- contract test(per §4.3.2 7 项)

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q4-1 alternative — read-path strict assertion(`assert isinstance(claim, UnaryClaim)`)

- **Why rejected**:Slice 5 后 drop rest_terms 列 + DTO drop 字段 — type-level 已保证 unary(`Claim.value` / `Claim.value_tag` 唯一 payload);read-path strict assertion 是 redundant defense;write-path strict enforce 在 Ledger.append_assertion entry 是更 fail-fast 的位置(写入时 catch,不等到读出来才发现);跟 meta-ADR §4.4 4-layer enforcement 的 "write-side strict;read-side 依赖 type system" 模式一致

#### Q4-1 alternative — SQL CHECK constraint(`CHECK (LENGTH(json(rest_terms)) <= 1)`)

- **Why rejected**:Slice 5 drop rest_terms 列后 SQL CHECK target 不存在(列已 drop);若 Slice 3b 加 CHECK 会立即 break adapter(同 Q4-2 (a) 情形)— 违反 zero-Q-PR1;SQL CHECK 错误 message 不可定制(无 migration hint);跟 §4.1.1 write-path runtime check + typed exception 路径不一致

#### Q4-2 alternative — Slice 3b 加 weak enforce 只在 NEW write paths(`append_revocation_claim` / SDK fields.set 等),legacy adapter 路径绕过

- **Why rejected**:NEW write paths 实施侧已 hardcoded `rest_terms=[]`(per ADR-SYS-B §4.3.2)— weak enforce 在 NEW 路径 trivially 满足,无防御价值(纯 dead check);实施复杂度上升(两条 write path 的 enforce 分支处理);Slice 3b 完全无 enforce 跟 ADR-SYS-B §4.2 选 (c) dual-coexistence 一致

#### Q4-3 alternative — Slice 5 仅 adapter rewrite + drop 列,**不**加 strict enforce(留 Slice 6+)

- **Why rejected**:**违反 ADR-SYS-B §4.7.2 三项绑定 contract**;adapter rewrite + drop 列后 ledger schema 已是终态(unary),但若不加 enforce check,future regression(adapter 错误 reintroduce n-ary / migration tool 漏点 / 第三方 caller bug)无 runtime guard;defense-in-depth 是 marginal 5 行 cost,binding 三项确保 atomicity

#### Q-PR1 alternative — option (B):给 INV-9 开 adapter 特例逃生窗(允许特定 pred_id 保留 n-ary)

- **Why rejected**(per identity §11.2):破坏 INV-9 统一性 — ledger 形态变成 "大多 unary + 少数 n-ary",所有 reader 都需要 conditional handle;`Ledger.append_assertion` strict enforce 需 carve-out("特例 pred_id 不 check")— 复杂化整套 invariant 系统;ledger 终态目标是单一 schema 形态

#### Q-PR1 alternative — option (C):Edge 拆 2 个 Claim + synthetic 共享 ID

- **Why rejected**(per identity §11.2):每条 edge 写 2 个 Claim → ledger 存储多一倍;synthetic 共享 ID 不属于 ledger native concept(违反 INV-5 source of truth — synthetic ID 是 derived state);两条 Claim 关联需要复杂 join 路径;Relationship Claim lowering(option A)用现有 ledger 形态(unary entity_ref Claim)更经济

#### Q-PR1 alternative — Step 1 / Slice 3b 内做 adapter rewrite(替代延后 Slice 5)

- **Why rejected**:**违反 meta-ADR §4.4 Step 1 zero-Q-PR1 dependency hard rule**(meta-ADR adopted constraint;不可单方面 override)+ user reviewer multiple rounds explicitly 不让 Q-PR1 进 Step 1;Slice 3b scope 已被 ADR-SYS-B 锁(6 项必做),加 adapter rewrite 会 scope explosion + force Slice 3b blueprint 跨模块(ledger + adapter)— blueprint 难起草 + review 难收敛

### 5.2 Cross-Q rejected combinations

#### Option `INV9-strict-from-start`:Slice 3b INV-9 strict + adapter rewrite + drop rest_terms 列三合一

- **Why rejected**:综合 Q4-2 alt (a) + Q-PR1 alt "Step 1 内 rewrite" 个别 rejected 理由;违反 meta-ADR §4.4 zero-Q-PR1 hard rule;Slice 3b scope 不可承受;此 option 在 user 第 1 轮 review draft ADR-SYS-B 时已被显式 reject

#### Option `INV9-weak-throughout`:Slice 3b 加 blanket weak enforce(无 strict path)+ Slice 5 仅 drop 列 + adapter rewrite

- **Why rejected**:blanket weak enforce 在 Slice 3b 会 break adapter(同 Q4-2 alt (a));Slice 5 仅 drop 列 + adapter rewrite 不加 strict enforce 会破坏三项绑定(同 Q4-3 alt)

#### Option `INV9-two-step-enforce`:Slice 3b weak enforce(只在新 path)+ Slice 5 strict enforce(全 path)

- **Why rejected**:two-step enforce 实施复杂度(两套 enforce 代码 + 两阶段 contract test);weak enforce 在 NEW path 无防御价值(trivial 满足);单 step Slice 5 strict 是更干净的设计

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q4 row(`audit:517`)
- audit §6 INV-9 row(`audit:283`)— shipped baseline 5 列 claims + rest_terms JSON + Claim dataclass n-ary
- audit §5.4 baseline citations:
  - `_edge_rest_terms` row(`audit:231`)— PyReason adapter shipped 2-element rest_terms
  - `accept_pyreason_session` row(`audit:233`)— node unary path + edge n-ary path
  - `claim_args_from_rest_terms` row(`audit:205`)— Slice 5 后 dead path
  - `canonical_bytes_tup_v1(rest_terms)` row(`audit:206`)— Slice 5 后 list 包装不需要
- audit §6 N1 row — Step 2+ defer adapter rewrite baseline

### 6.2 Shipped code citations

**INV-9 baseline**(Slice 5 enforce target):
- `src/factgraph/core/store/ledger.py:82-88` `claims` 表当前 5 列(`seq, asrt_id, pred_id, e_ref, rest_terms`);`rest_terms TEXT NOT NULL` n-ary
- `src/factgraph/core/store/ledger.py:22-26` `Claim` dataclass `rest_terms: list[tuple[str, Any]]` n-ary
- `src/factgraph/core/store/ledger.py:363-378` `Ledger.append_assertion` entry(Slice 5 加 §4.1.1 INV-9 check;ADR-SYS-B §4.1.4 signature 演化已经 drop 3 参数后,此处加 length check)
- `src/factgraph/core/protocol/tup_v1.py:156-168` `canonical_bytes_tup_v1(rest_terms)` 协议 list 包装(Slice 5 drop 列后 dead)
- `src/factgraph/core/protocol/tup_v1.py:196-208` `claim_args_from_rest_terms` 路径(Slice 5 drop 列后 dead — 同步 ADR-SYS-B §4.3.5 wrapper Slice 5 cleanup)

**Q-PR1 baseline**(Slice 5 adapter rewrite target):
- `src/factgraph/adapters/pyreason/accept.py:187-205` `_edge_rest_terms(fact, pred_spec)` — **当前返回 2-element rest_terms**;Slice 5 rewrite 为 `_edge_to_relationship_claim`
- `src/factgraph/adapters/pyreason/accept.py:94-160` `accept_pyreason_session` — node unary + edge n-ary;Slice 5 edge 路径走 Relationship Claim lowering
- `src/factgraph/adapters/pyreason/accept.py:165-184` `_node_rest_terms`(unary,Slice 5 不动 — node 路径已经 unary)
- `src/factgraph/adapters/pyreason/accept.py:208-213` `_node_e_ref` / `_edge_from_e_ref`(e_ref materialization,Slice 5 不动)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 Q4 grouping(System namespace + adapter cluster,Slice 3b + 5)— justifies 本 ADR 跨 cluster 单 Q 形态
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency hard rule — justifies §4.2 Slice 3b 完全不加 enforce + §4.4 adapter rewrite Slice 5 carve-out
- meta-ADR §4.4 4-layer enforcement(SDK shell + application strict;protocol/ledger delayed)— justifies §4.1 ledger 层 strict 在 Slice 5 落地(Slice 3b ledger 仍 delayed per ADR-SYS-B §4.2)

### 6.4 Design-point citations

- `workflow/design/design-points/active/ledger-schema-specification.zh.md` §4.6 INV-9(`:277-288`)— Ledger Claim 是 unary fact 设计源
- ledger-spec §3.1 claims 表 target schema(`:107-155`)+ §3.1 Claim 形态枚举 "Entity-ref field" row(`:140`)— §4.4.1 Relationship Claim lowering 形态依据
- ledger-spec §9.4 数据精简 4(`:737-741`)— rest_terms 内联到 value+value_tag,Slice 5 drop 列依据
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §11 Adapter 边界 Q-PR1(`:803-829`)— **§4.4 决策核心 design-point 依据**;含 3 候选解法 + 推荐 (A)
- identity §11.1 问题(`:811-815`)— `_edge_rest_terms` 2-position 跟 INV-9 unary 冲突
- identity §11.2 候选解法(`:817-823`)— 3 options table + 推荐 (A) Relationship Claim lowering
- identity §11.3 推荐(`:825-829`)— Step 2+ deferred,与 identity Step 1 增量正交

### 6.5 ADR-SYS-B §4.7.2 三项绑定 contract closure

本 ADR §4.3 + §4.4 + §4.5 **关闭** ADR-SYS-B §4.7.2 carve-out 的 Slice 5 三项绑定 contract:

| ADR-SYS-B §4.7.2 项 | 本 ADR § |
|---|---|
| 1. ALTER TABLE drop `rest_terms` 列 | §4.3.2 acceptance + §4.5 closure(ADR-SYS-B 锁,本 ADR 引用)|
| 2. PyReason adapter rewrite — `_edge_rest_terms` 改 Relationship Claim lowering | §4.4(本 ADR 锁)|
| 3. `Ledger.append_assertion` strict enforce | §4.1.1 + §4.3(本 ADR 锁)|

任一项缺失则 Slice 5 不可 mark `implemented`(per §4.5)。

### 6.6 No-Q-PR1-as-dep confirmation(本 ADR Q-PR1 作为 sub-decision in scope,不是 Q-PR1 作为 dep)

**澄清**:本 ADR §4.4 锁定 Q-PR1 adapter rewrite path(走 Relationship Claim lowering)— 这是 **Step 2+ Slice 5 acceptance criteria 的一部分**,**不是** Step 1 / Slice 3b 的 dependency;不违反 meta-ADR §4.4 zero-Q-PR1 hard rule(后者约束 Step 1 implementation 不 depend on adapter rewrite,本 ADR §4.2 明确 Slice 3b 完全不加 enforce — Slice 3b 实施跟 adapter rewrite 完全 decoupled)。

本 ADR 内 Q-PR1 锁定的形态:
- §4.2 Slice 3b implementation 跟 Q-PR1 完全 decoupled(零 enforce + legacy adapter 继续走 rest_terms)
- §4.4 Q-PR1 adapter rewrite path 锁在 Slice 5 内;Slice 3b blueprint 不需要引用 Q-PR1
- §4.5 三项绑定保证 Slice 5 内 adapter rewrite + strict enforce + drop 列同步落地

### 6.7 Cross-ADR 兼容性

#### 6.7.1 ADR-SYS-B(`6b0ac349`)
- §4.2 选 (c) dual-coexistence — 本 ADR §4.2 一致(Slice 3b 不加 enforce)
- §4.7.2 三项绑定 contract — 本 ADR §4.3 + §4.4 + §4.5 closure
- §4.1.4 `Ledger.append_assertion` signature 演化 — 本 ADR §4.1.1 加 check 跟 演化 signature 兼容(drop 3 参数后,length check 仍 in claim.rest_terms attribute;Slice 5 drop 列后 attribute 不存在 → check 进一步简化 / 移除 / 改 defense-in-depth)

#### 6.7.2 ADR-SYS-A(`75f1c8bc`)
- §4.4.2 PyReason adapter rewrite 是 SYS-B-owned emission concern 的 carve-out — 本 ADR §4.4 lowering 路径 emit Relationship Claims(pred_id 不以 `__system__` 开头),跟 SYS-A G2 user-facing guard 一致;不污染 SYS-A namespace boundary

#### 6.7.3 ADR-IC(`2d0866ed`)
- §4.2 emission input contract — 本 ADR §4.4 Relationship Claim lowering 输入 `EntityRef(entity_type, identity={...})` 形态对 source / target 两个 e_ref 都成立;不污染 ADR-IC `_protected_anchor_pred_ids` cache(Relationship pred_id 不属 Identity / `:exists` schema 标志)

#### 6.7.4 ADR-API(`66434490`)
- §4.5 schema register/extend/apply 三分 — 本 ADR §4.4 Relationship Claim lowering 依赖 schema 中 Relationship 类型已注册(per ADR-API §4.5.1 register);Slice 5 blueprint 必须 verify PyReason adapter 用的 relationship types 已通过 `fg.schema.register/extend/apply` 路径注册

#### 6.7.5 ADR-FI(`b288ea9e`)
- descriptor signature 跟 namespace 正交 — Relationship descriptor public surface(per ADR-FI 不动)是 §4.4 lowering 路径输入 schema 来源

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 5(Step 2+)PyReason adapter rewrite slice blueprint** 可起草 — 三项绑定 acceptance criteria(per §4.3.2 + §4.4 + §4.5)是 Stage 4 blueprint outline
- **Slice 3b implementation**(per ADR-SYS-B):本 ADR §4.2 明确 Slice 3b 完全不加 enforce — Slice 3b blueprint 中跟 INV-9 enforce 相关的 ambiguity 已闭合;blueprint 起草侧 `_insert_claim` / `append_assertion` 不需要写 enforce check
- **ADR-DOCS**(Q17)起草 — 本 ADR 锁定的 INV-9 strict timing + Q-PR1 adapter rewrite path 是 docs sync 范围内必须覆盖的内容(`ledger-schema-specification §9.4` + `identity-mechanism-redesign §11` 跟 ADR-INV9 对齐)
- **ADR-IE** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 5(Step 2+)blueprint draft(`workflow/blueprints/active/2026-05-29_slice-5-adapter-rewrite.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-INV9 adopt 后 |
| Slice 5 pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `_edge_rest_terms` / `rest_terms` 列 / `claim_args_from_rest_terms` / `canonical_bytes_tup_v1(rest_terms)` — 全 migrate 或 dead code 清理 | Slice 5 blueprint preflight(Step 4.6.5)| Slice 5 blueprint scoped 后 |
| Slice 5 implementation:`Ledger.append_assertion` entry 加 §4.1.1 INV-9 check + ALTER TABLE drop `rest_terms` 列 + `Claim` DTO drop `rest_terms` 字段 | Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:PyReason adapter rewrite — `_edge_rest_terms` → `_edge_to_relationship_claim`(per §4.4)| Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:`find_claim_args` wrapper LEGACY path cleanup + migrate `projector.py:96` + `chosen.py:148` 直读(per ADR-SYS-B §4.3.5 Slice 5 cleanup follow-up)| Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:contract test 覆盖三项绑定 acceptance(per §4.3.2 7 项 + §4.4.4 PyReason roundtrip)| Slice 5 implementation | Slice 5 Step 4.7 |
| docs sync(Slice 4 或 ADR-DOCS)— `ledger-schema-specification §9.4` + `identity-mechanism-redesign §11` 跟 ADR-INV9 对齐;`04_api_surface.en.md` 加 Slice 5 后 Claim DTO 终态说明 | Slice 4 docs sync 或 ADR-DOCS | Slice 5 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-DOCS 起草时 Header `Depends on:` 引用本 ADR(本 ADR 锁定的 Q-PR1 adapter rewrite path 是 docs sync 范围内的 architectural change);Slice 5 blueprint preflight(Step 4.3)必须 re-read 本 ADR §4.3 + §4.4 + §4.5 三项绑定
- **Blueprint pillar**:Slice 5 blueprint Stage 4 acceptance criteria 必须包含 §4.3.2 + §4.5 三项绑定 closure check;Slice 3b blueprint **不需要**引用本 ADR(§4.2 锁 Slice 3b 完全 decoupled)
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q4 行 status 仍是 "待 ADR 决策" — 实际 ADR-INV9 已 lock;**不**触发 audit doc post-stage sync(跟其他 Stage 2 ADRs 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 5 blueprint 不可单方面 override Q4 / Q-PR1 决策;若需要 override,走 "本 ADR superseded by 新 ADR-INV9-v2" 路径
- §4.1 write-path strict enforce 位置:carry-forward — 永远在 `Ledger.append_assertion` entry;不可改为 read-path strict 或 SQL CHECK 形态
- §4.2 Slice 3b 完全不加 enforce:carry-forward — 不可后续在 Slice 3b implementation 加 enforce(违反 zero-Q-PR1 + 跟 ADR-SYS-B §4.2 (c) 冲突)
- §4.3 三项绑定 + Slice 5 落地:carry-forward — 三项 atomicity 不可拆;不可在 Slice 5 之前 / 之后 / 单独落地任一项
- §4.4 PyReason adapter rewrite 走 option (A) Relationship Claim lowering:carry-forward — 不可改走 option (B) INV-9 例外 / option (C) Edge 拆 2 Claim;若 future 需要 (B) / (C),走 supersede 本 ADR 路径
- §4.4.4 Slice 5 blueprint scope:carry-forward — 本 ADR 不锁 adapter 内部细节(留 Slice 5 blueprint);Slice 5 blueprint 不可单方面改 §4.4.1 lowering 路径形态

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.5 Q4 + Q-PR1 + 三项绑定 closure 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥7 项含 Q4-1 / Q4-2 / Q4-3 / Q-PR1 alternatives)+ cross-Q rejected combinations(≥3)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / ADR-SYS-B 三项绑定 closure / no-Q-PR1-as-dep confirmation / 5 cross-ADR 兼容性 7 类 evidence
- [x] §6.5 显式 closure ADR-SYS-B §4.7.2 三项绑定 contract;§6.6 显式 confirm Q-PR1 在本 ADR 范围内是 sub-decision 不是 dep;跟 zero-Q-PR1 hard rule 不冲突
- [x] §4.2 Slice 3b 完全不加 enforce — 跟 ADR-SYS-B §4.2 选 (c) + meta-ADR §4.4 zero-Q-PR1 一致
- [x] §4.4 PyReason adapter rewrite 走 identity §11.2 option (A) Relationship Claim lowering — 显式 cite design-point + reject (B) / (C)
- [x] §4.5 三项绑定 closure 显式 enumerate(项 1 引用 ADR-SYS-B §4.7.2;项 2 + 项 3 本 ADR §4.3 + §4.4 锁)
- [x] Header `Depends on:` 引用 meta-ADR + ADR-SYS-B adopted commits
- [x] §7.4 显式 no-retroactive carry-forward 6 项

Post-adoption verification(implementation 阶段验证 — Slice 5):

**Slice 5 三项绑定 acceptance**:
- [ ] Slice 5 blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR + Stage 4 §10 Outcome acceptance criteria 含 §4.3.2 + §4.5 三项绑定 closure
- [ ] Slice 5 implementation **项 1**:`claims` 表 ALTER TABLE drop `rest_terms` 列 verified;`Claim` DTO drop `rest_terms` 字段;所有 `claim_args_from_rest_terms` / `canonical_bytes_tup_v1(rest_terms)` 路径 dead code 清理
- [ ] Slice 5 implementation **项 2**:PyReason adapter `_edge_rest_terms` rewrite 为 `_edge_to_relationship_claim`(or similar);edge facts → Relationship Claim lowering(`pred_id=<rel_type>, e_ref=<source>, value=<target>, value_tag="entity_ref"`;per §4.4.1)
- [ ] Slice 5 implementation **项 3**:`Ledger.append_assertion` entry 加 `len(rest_terms) > 1 → raise WriteProtocolError` strict enforce(per §4.1.1;Slice 5 drop 列后此 check 可能转 defense-in-depth 形态 — `assert claim.rest_terms == []` 或类似)
- [ ] Slice 5 implementation:contract test — PyReason edge fact roundtrip:edge fact in → adapter lowering → ledger Relationship Claim(unary)→ query back via ledger reader → reconstruct edge fact
- [ ] Slice 5 implementation:contract test — `Ledger.append_assertion` rejects length > 1 rest_terms with WriteProtocolError(含 ADR-INV9 §4.1 reference + Relationship migration hint);**不同于 Slice 3b 行为**(Slice 3b 接受 n-ary)
- [ ] Slice 5 implementation:Slice 3b 期间已 shipped `__system__.revokes` Claim + Identity Claim + Field Claim 路径(per ADR-SYS-B + ADR-IC)在 Slice 5 strict enforce 后 **仍正常工作**(rest_terms=[] trivially 满足 `len <= 1`)

**ADR-SYS-B §4.3.5 follow-up**(per Slice 5 cleanup):
- [ ] Slice 5 implementation:`find_claim_args` wrapper LEGACY path dead code 清理(rest_terms 列已 drop,LEGACY path 不可达)
- [ ] Slice 5 implementation:migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`(per ADR-SYS-B §4.3.5 Slice 5 cleanup deferred follow-up)
- [ ] Slice 5 implementation:`SDKStore.find_claim_args`(`sdk/store.py:182`)deprecate / 评估 remove(per ADR-SYS-B §4.3.5 Slice 5 cleanup follow-up)

**Cross-ADR contract verification**:
- [ ] Slice 5 implementation:Relationship Claim 形态(`value_tag="entity_ref"`)跟 ledger-spec §3.1 "Entity-ref field" row 一致
- [ ] Slice 5 implementation:PyReason adapter 用的 relationship types 已通过 `fg.schema.register/extend/apply` 路径注册(per ADR-API §4.5.1)— **若未注册,adapter 必须先 register**;Slice 5 blueprint 加 explicit registration step
- [ ] Slice 5 implementation:Relationship Claim 的 pred_id 不以 `__system__` 开头(per ADR-SYS-A G1/G2);adapter 输出 pred_id 经 schema declared,自然安全
- [ ] Slice 5 implementation:Relationship Claim 写入路径不污染 ADR-IC `_protected_anchor_pred_ids` cache(Relationship pred_id 不属 `is_identity_field` / `is_entity_exists`)

**docs sync**:
- [ ] Slice 4 docs sync 或 ADR-DOCS:`ledger-schema-specification §9.4` 跟 ADR-INV9 对齐;`identity-mechanism-redesign §11.3` 跟 ADR-INV9 §4.4 对齐(Slice 5 实施完成 mark);`04_api_surface.en.md` 加 Slice 5 后 Claim DTO 终态说明

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-INV9 drafted | Q4 + Q-PR1 + 三项绑定 closure(关闭 ADR-SYS-B §4.7.2 carve-out)。Q4-1 strict enforce form = write-path runtime check at `Ledger.append_assertion` entry;Q4-2 Slice 3b 完全不加 enforce(跟 ADR-SYS-B §4.2 选 (c) + meta-ADR §4.4 zero-Q-PR1 一致);Q4-3 Slice 5 strict enforce + 三项绑定其一(per ADR-SYS-B §4.7.2);Q-PR1 走 identity §11.2 option (A) Relationship Claim lowering(reify n-ary edge → unary `Claim(pred=<rel_type>, e_ref=<source>, value=<target>, value_tag="entity_ref")`)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-SYS-B adopted @ `6b0ac349` + identity §11 design-point + ledger-spec §4.6 INV-9 + 5 cross-ADR(SYS-A/SYS-B/IC/API/FI)兼容性 confirm。Branch: `v0.2.0-q-inv9-adapter-enforcement-decision-2026-05-29`。Commit: TBD post-stage |
