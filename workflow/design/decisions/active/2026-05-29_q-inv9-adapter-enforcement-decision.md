# Q-INV9 Decision: INV-9 unary enforce timing + Q-PR1 PyReason adapter rewrite path

- Status: adopted
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
- **§4.4 4-layer enforcement**:本 ADR §4.3 Slice 5 strict enforce 在 **write_protocol layer ingress**(`set_field` 入口,**before** typed Claim DTO construction;per §4.1.1);Ledger 层走 type-system + SQL schema enforce(DTO drop rest_terms field + 表 drop rest_terms 列);**不**触 protocol delayed 层(per ADR-SYS-B §4.2 / 本 ADR §4.2)

### 1.3 ADR-SYS-B §4.7.2 三项绑定 contract — 本 ADR 必须关闭

ADR-SYS-B adopted `6b0ac349` §4.7.2 Slice 5 三项绑定 carve-out:

> | 项 | 延后内容 | 触发条件(三项绑定)|
> |---|---|---|
> | 精简 4 真正 drop `rest_terms` 列(+ Q-PR1 adapter rewrite + ADR-INV9 strict enforce)| ALTER TABLE drop rest_terms;adapter rewrite 改写 Pyreason 2-position;ADR-INV9 锁的 strict / weak enforce 落地 | **三项绑定:任一项缺失则 Slice 5 不可 mark `implemented`** |

本 ADR **必须**:
- §4.3 锁定第 3 项 — INV-9 strict enforce 形态(write_protocol layer ingress runtime check per §4.1.1 + Slice 5 后 DTO/SQL type-level enforce 主防御 per §4.1.2)
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
- Slice 5(本 ADR 锁定):drop `rest_terms` 列(SQL schema + Claim DTO 同步 drop)+ adapter rewrite(per §4.4)+ write_protocol layer ingress 加 `len(rest_terms) > 1` runtime strict check + DTO/SQL type-level enforce 主防御(per §4.1 + §4.3)— **三项同时落地**

## 2. Scope

本 ADR **锁**以下 sub-decisions(单 Q 但跨 cluster):

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q4-1** | INV-9 strict enforce **形态** — **write_protocol layer ingress runtime check**(`set_field` 入口,before typed Claim DTO construction;per §4.1.1)+ Slice 5 后 Claim DTO drop rest_terms field + SQL schema drop 列 type-level enforce 主防御(per §4.1.2);**不**加 Ledger.append_assertion 层 length check(DTO 无 attribute 可 check;per §4.1.5);**不**加 read-path strict assertion(per §3 Non-scope)|
| **§4.2 Q4-2** | INV-9 enforce **Step 1 / Slice 3b 时机** — Slice 3b 期间 **完全不加** runtime enforce(实施 ADR-SYS-B §4.2 选 (c) dual-coexistence;legacy adapter 继续写 2-position rest_terms);跟 meta-ADR §4.4 zero-Q-PR1 hard rule 一致 |
| **§4.3 Q4-3** | INV-9 enforce **Step 2+ / Slice 5 时机** — Slice 5 strict enforce 落地 + 三项绑定其一(per ADR-SYS-B §4.7.2)|
| **§4.4 Q-PR1** | PyReason adapter rewrite path — 走 identity §11.2 option (A) Relationship Claim lowering;edge facts reify 为 **multiple first-class unary Claims**(anchor Claim source-target + edge value as Relationship Field Claim;per §4.4.2);edge value 是 **semantic payload**(不进 claim_meta);**不**改 ledger schema、**不**为 adapter 开 INV-9 例外、**不**做 (C) synthetic-keyed 拆分 |
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

### 4.1 Q4-1 — INV-9 strict enforce 形态:**write_protocol layer ingress runtime check + Slice 5 后 type-level enforce**

**锁定**:INV-9(Ledger Claim 是 unary fact)的 strict enforce 形态 = **write_protocol layer ingress runtime check**(legacy compatibility path,**before** typed `Claim` DTO construction)+ **Slice 5 后** Claim DTO drop `rest_terms` field 后 type-level enforce 是主防御(runtime check 是 defense-in-depth)。

#### 4.1.1 Check 位置:write_protocol layer ingress(★ P1-amend 关键设计点)

per ADR-SYS-B §4.1.4 Ledger.append_assertion DTO 演化 — Slice 5 时 `Claim` DTO **drop `rest_terms` field**(per §4.3.2 acceptance);Ledger.append_assertion 入口看到的是 typed Claim with `value/value_tag` only,**不可能** check `len(claim.rest_terms)`(该 attribute 不存在)。

**正确位置**:`write_protocol` layer 的 **legacy compatibility ingress** — 在 `rest_terms` list parameter **转换为 `value/value_tag` 之前**:

```python
# core/evidence/write_protocol.py (Slice 5 加):
def set_field(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    rest_terms: list[tuple[str, Any]],     # ← legacy signature kept transient;Slice 5 末尾评估改 (value, value_tag) 直接形态
    meta: dict[str, Any] | None = None,
) -> str:
    # ★ INV-9 strict enforce (per ADR-INV9 §4.1.1) — at ingress, BEFORE Claim DTO construction:
    if len(rest_terms) > 1:
        raise WriteProtocolError(
            f"INV-9 violation: write_protocol.set_field called with "
            f"rest_terms length {len(rest_terms)} > 1 for pred_id={pred_id!r};\n"
            f"  ledger Claim must be unary fact (value+value_tag pair).\n"
            f"  PyReason 2-position rest_terms should reify as Relationship "
            f"Claim per ADR-INV9 §4.4 / identity §11.2 option (A).\n"
            f"  See ADR-INV9 §4.1 for enforce position rationale + §4.3 for timing."
        )
    # 正常路径:rest_terms == [] (0-arity) 或 [(tag, value)] (1-arity)
    if rest_terms:
        value_tag, value = rest_terms[0]
    else:
        value, value_tag = None, None

    # 构造 typed Claim WITHOUT rest_terms field (per Slice 5 DTO drop per §4.3.2):
    claim = Claim(asrt_id=..., pred_id=pred_id, e_ref=e_ref, value=value, value_tag=value_tag)
    # ... rest of normalization + Ledger.append_assertion call
```

**为什么 write_protocol layer 而非 Ledger.append_assertion**:
- Slice 5 后 `Claim` DTO **不含 `rest_terms` field**(per ADR-SYS-B §4.1.4 演化 + 本 ADR §4.3.2);Ledger.append_assertion 入口看到的 typed Claim 已是 unary 形态(value+value_tag)— 没有 attribute 可 check
- write_protocol layer 是 `rest_terms` list 仍 alive 的最后一层(legacy compatibility signature);check 在此处覆盖 **所有调 write_protocol 入口的 caller**(adapter / migration tool / test fixture)
- 跟 meta-ADR §4.4 4-layer enforcement 一致:**write_protocol(application 层 strict)** + **ledger (DTO type-level enforce)** — 两层防御不同 surface

#### 4.1.2 Slice 5 后的 type-level enforce(主防御)

- `Claim` DTO drop `rest_terms` field → Python type system 即保证 unary(`claim.rest_terms` AttributeError;任何尝试访问 / 构造 multi-arg Claim DTO 在静态 type check / runtime construct 时 fail)
- `claims` 表 drop `rest_terms` 列 → SQL schema 即保证 unary;任何尝试 INSERT row with rest_terms 字段会 SQL error
- §4.1.1 write_protocol layer runtime check 是 **defense-in-depth**:防 legacy caller(如未 rewrite 的 internal API)在 rest_terms list 转换之前 raise — typed exception with migration hint(比 SQL error / AttributeError 更友好)

#### 4.1.3 Check 触发 atomic 保证

- write_protocol layer runtime check 在 `_write_session` atomic context **之前** 调用(per ADR-SYS-B §6.2 + ledger-spec §4.3 INV-3)— raise 时 不会有 partial transaction 状态
- 跟 INV-3 atomic 原子写一致

#### 4.1.4 Error message contract

- error message 必须含 ADR-INV9 §4.1 reference
- 必须含 migration hint:PyReason 2-position rest_terms 应该 reify 为 **multi-Claim Relationship lowering**(anchor + value Field Claims;指 ADR-INV9 §4.4.2 + identity §11.2 option (A))
- 必须含 enforce position reference(指 ADR-INV9 §4.1 write_protocol ingress)
- 触发场景应该极罕见(adapter rewrite 后);若 fire,通常是 caller bug(忘记 reify 或 reify 路径漏)

#### 4.1.5 不在 Ledger.append_assertion 加 length check

- ADR-SYS-B §4.1.4 演化后,Ledger.append_assertion 接受的 `Claim` typed DTO 已 drop `rest_terms` field — 没有 attribute 可 check
- 若强行在 Ledger 层加某种 "claim is unary" check,只能 check `claim.value` / `claim.value_tag` 一致性(类型 check),跟 INV-9 unary 概念不直接对应
- type system + DTO schema 已是 ledger 层的 enforce 形态;runtime check 在 write_protocol 上游已 fail-fast,Ledger 层不需要重复

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

- Slice 3b implementation `write_protocol.set_field` 入口 + `Ledger.append_assertion` 全程 **不**加 `len(rest_terms) > 1` check;legacy adapter 路径继续 work
- Slice 3b blueprint 起草时 **不需要**包含 PyReason adapter 改动(adapter 继续 work — 因 schema 加 value+value_tag 双列但 rest_terms 列 retained per ADR-SYS-B §4.2 选 (c))
- Slice 3b implementation 仍可在 NEW path 的实施细节中 hardcode `rest_terms=[]`(`append_revocation_claim` / SDK fields.set 等)— **不**是 enforce,是 schema contract per §4.3.2

### 4.3 Q4-3 — Slice 5 时机:**strict enforce 落地 + ADR-SYS-B §4.7.2 三项绑定其一**

**锁定**:Step 2+ Slice 5 PyReason adapter rewrite slice **必须**同时:
1. ALTER TABLE drop `rest_terms` 列(ADR-SYS-B §4.7.2 第 1 项)
2. PyReason adapter rewrite — `_edge_rest_terms` 走 identity §11.2 option (A) multi-Claim Relationship lowering(anchor + value Field Claims;本 ADR §4.4)
3. **`write_protocol` layer ingress 加 §4.1.1 INV-9 strict runtime check + Claim DTO drop rest_terms field + SQL schema drop 列 type-level enforce 主防御**(本 ADR §4.1 + §4.3.2)

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

**Schema + DTO 演化**:
- [ ] `claims` 表 ALTER TABLE drop `rest_terms` 列(per ADR-SYS-B §4.7.2 第 1 项)
- [ ] `Claim` DTO drop `rest_terms` 字段(typed dataclass);所有 `claim_args_from_rest_terms` / `canonical_bytes_tup_v1(rest_terms)` 路径 dead code 清理
- [ ] **`Ledger.append_assertion` entry 无 length check**(per §4.1.5;Claim DTO 已无 rest_terms field,无 attribute 可 check;type-level enforce 是主防御)

**INV-9 strict enforce 位置**(★ P1-amend):
- [ ] write_protocol layer ingress(`write_protocol.set_field` or rewritten equivalent)加 §4.1.1 runtime check — `if len(rest_terms) > 1: raise WriteProtocolError(含 ADR-INV9 §4.1 reference + Relationship migration hint)`
- [ ] check 在 typed `Claim` DTO **construction 之前** 执行(per §4.1.1 — rest_terms list 仍 alive 的最后一层)
- [ ] write_protocol.set_field signature 可选 evolve 为 `(value, value_tag)` 直接形态(Slice 5 末尾 cleanup,non-load-bearing follow-up)— 若 evolve,§4.1.1 runtime check 转 dead code(type-level 取代)

**PyReason adapter rewrite**(★ P2-amend):
- [ ] PyReason adapter `_edge_rest_terms` 改写为 `_edge_to_relationship_claims`(返回 typed Claims list:**anchor Claim + value Field Claim**)走 §4.4.2 lowering
- [ ] **edge value 不进 claim_meta**(per §4.4.1 边界)— contract test verify claim_meta 不含 edge fact value
- [ ] PyReason 用的 relationship types 全部已 register in schema(per ADR-API §4.5.1)— Slice 5 implementation 必须 register 前置;若未注册,先 register
- [ ] anchor Claim + value Field Claim atomic 写入(per INV-3 + ADR-IC §4.2 emission)

**Cross-ADR cleanup follow-up**:
- [ ] `find_claim_args` compatibility wrapper 简化(per ADR-SYS-B §4.3.5 Slice 5 cleanup):LEGACY rest_terms parse 路径 dead code 清理;只保留 NEW path decoder
- [ ] migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`(per ADR-SYS-B §4.3.5 Slice 5 cleanup)

**Contract test 覆盖**:
- [ ] PyReason edge fact roundtrip:edge fact `(source, target, value)` → adapter lowering → ledger 2 个 Claims(anchor + value Field)→ query back → reconstruct edge fact with semantic value
- [ ] `write_protocol.set_field` rejects rest_terms length > 1 with WriteProtocolError(INV-9 strict;含 §4.1 reference);跟 Slice 3b 行为有变化(Slice 3b 不 reject)
- [ ] `Ledger.append_assertion` 接受 typed `Claim` without rest_terms attribute(type-level enforce)
- [ ] claim_meta 不承载 edge value 验证 — 写 edge fact 后 query claim_meta,**不**含 `edge_fact_value` / 类似 key

#### 4.3.3 Read-path 不加 strict assertion(per §3 Non-scope)

- 不加 `assert isinstance(claim, UnaryClaim)` 在 read path
- 不加 `assert claim.rest_terms == []` 在 read path(rest_terms 列 drop 后该 attr 不存在)
- Rationale:write-path strict + drop column + DTO drop field 是 type-level 保证;read-path strict 是 redundant defense
- 若 future 决定加 read-path strict(e.g., for migration audit),走独立 ADR 显式 supersede 本 §4.3.3

### 4.4 Q-PR1 — PyReason adapter rewrite:**走 identity §11.2 option (A) Relationship Claim lowering;edge value 是 first-class semantic 不进 claim_meta**

**锁定**:PyReason adapter `_edge_rest_terms` 路径(`accept.py:187-205`)Slice 5 改写 — edge facts 走 **Relationship Claim lowering**:n-ary edge `(source, target, value)` reify 为 **多个 first-class unary Claims**(source-target 锚定 Claim + edge value 作为 Relationship attribute Field Claim);**edge value 不进 claim_meta**(claim_meta 是 non-truth provenance 专用,**不**作为 semantic payload 影 shadow channel)。

#### 4.4.1 PyReason edge value 的 truth status — semantic,不是 provenance(★ P2-amend 关键设计决策)

PyReason edge facts 形态 `(source, target, value)` 中,`value` 是 **semantic payload**(典型 case:confidence / weight / truth degree / label / etc.)— **是事实本身的一部分**,不是关于事实的 provenance。

**claim_meta 边界**:per ledger-spec §3.2 + §5.3 META_KEY_REGISTRY,claim_meta 承载 **non-truth provenance**(`source` / `trace_id` / `note` / `ingested_at` / `bound` etc.);**不**作为 fact 语义的承载体。把 semantic payload(如 edge value)放入 claim_meta:
- 违反 claim_meta non-truth 边界 → 制造 shadow fact channel
- INV-13 active projection 公式不会处理 claim_meta entries → semantic payload 不在 fact projection 中可见
- INV-15 read filter 默认 filter system claims 但 claim_meta 跟随 claim 的 active 状态 → semantic payload 的 retract 语义不连贯
- 跟 ADR-API §4.4 `_meta` 统一(meta 是过滤入口,不是 truth payload)立场冲突

**结论**:edge value **必须** 作为 first-class unary Claim 写入 ledger,**不**进 claim_meta。

#### 4.4.2 Lowering contract(改写 §4.4.1 — multi-Claim 形态)

per identity §11.2 option (A) + ledger-spec §3.1 Claim 形态枚举 "Entity-ref field" row + ADR-API §4.5 schema Relationship registration:

**前置条件**:PyReason 用到的每个 edge type 在 ledger schema 中**必须** declared as Relationship(per ADR-API §4.5.1 register;含 source/target endpoints + value Field 声明);若 schema 未声明,adapter Slice 5 implementation 必须先 register Relationship type(具体 schema 形态由 Slice 5 blueprint 定)。

**Lowering 形态**(本 ADR 锁 contract,**不**锁具体 addressing model):

```text
shipped (Slice 3b 维持):
  edge fact: (source, target, value)
  → rest_terms=[(to_tag, to_ref), (value_tag, value)]
  写 ledger:
    Claim(pred_id=<edge_pred_id>, e_ref=<source>, rest_terms=[2-element])
  违反 INV-9 (n-ary)

Slice 5 后:
  edge fact: (source, target, value)
  → reify 为 multiple first-class unary Claims:

    [1] Source-target anchor Claim (first-class schema-declared relationship anchor):
        Claim(
          pred_id=<rel_type>,           # 或 <rel_type>:<endpoint_marker> 形态;具体 schema 决定
          e_ref=<source_e_ref>,
          value=<target_e_ref>,
          value_tag="entity_ref",
        )
        # 这条 Claim anchors (source, target) pair;满足 INV-9 (unary)

    [2] Edge value as Relationship Field Claim (semantic payload — first-class):
        Claim(
          pred_id=<rel_type>:<value_field_name>,    # schema-declared Field on Relationship
          e_ref=<relationship_instance_e_ref>,       # 具体 addressing model 由 Slice 5 blueprint 定
          value=<edge_value>,
          value_tag=<value_tag>,                     # per schema-declared type_domain
        )
        # 这条 Claim 承载 edge fact 的 semantic value;满足 INV-9 (unary)

  写入 atomic (per ADR-IC §4.2 emission + INV-3):两条 Claims 同 transaction
```

**关键 acceptance criteria**:
- edge value Claim 的 `pred_id` 必须是 schema-declared Field on Relationship type(per ADR-API §4.5 register/extend)
- edge value Claim 的 `e_ref` 是 relationship instance e_ref(具体形态:idref_v1 of (rel_type, source, target, [identity fields]),或其他 schema-declared addressing — Slice 5 blueprint scope)
- edge value Claim 跟 source-target anchor Claim **atomic** 写入(per INV-3)
- claim_meta **不**承载 edge value(per §4.4.1 边界)

#### 4.4.3 Addressing model 留 Slice 5 blueprint(本 ADR 不锁)

Relationship instance e_ref 的具体形态(`relationship_instance_e_ref` 怎么算):
- option (i) `idref_v1(rel_type, identity={"from": source_e_ref, "to": target_e_ref, ...additional_identity_fields...})` — 类比 Entity instance e_ref
- option (ii) synthetic composite key derived from anchor Claim — 不引入新 e_ref 类型
- option (iii) 其他形态(per Slice 5 blueprint design exploration)

**本 ADR 不锁** addressing model 选择 — 留 Slice 5 blueprint。约束:
- 必须跟 ADR-IC `_protected_anchor_pred_ids` cache 正交(Relationship pred_id 不属 `is_identity_field` / `is_entity_exists`)
- 必须跟 ADR-SYS-A G1/G2 guard 一致(rel_type 不以 `__system__` 开头)
- 必须支持 unique addressing per (source, target [+ identity fields]) tuple

#### 4.4.4 跟 ledger-spec §3.1 + ADR-IC §4.2 + ADR-API §4.5 兼容性

- per ledger-spec §3.1 "Entity-ref field" row:`pred_id=<EntityType>:<field_name>, value=<ref string>, value_tag="entity_ref"` — anchor Claim 跟 entity field 都用 `entity_ref` tag;**ledger 不区分**(Relationship 是 schema-level 概念,ledger 层是 unary Claim with entity_ref value)
- per ledger-spec §3.1 "普通 value field" row:edge value Claim 是 normal Field on Relationship,跟 Entity field 同 ledger 形态
- per ADR-IC §4.2 emission input contract:emission 路径接受 `EntityRef(entity_type, identity={...})`;Relationship 的 anchor + value Claims 通过 application layer 经过同样 emission path(具体 entry function 由 Slice 5 blueprint 定 — 可能是 `application/relationships.create(...)` 或扩展现有 `application/entity_write.py:_materialization_ops`)
- per ADR-API §4.5 schema `register/extend/apply`:Slice 5 blueprint 必须 verify PyReason adapter 用的 relationship types 全部已 register;若未注册,adapter rewrite 必须先 register(Slice 5 acceptance criteria)
- per ADR-SYS-A G1/G2 guard:rel_type / value_field_name 都不以 `__system__` 开头(schema 注册时 G2 reject 已 enforce)

#### 4.4.5 为什么不走 options (B) 给 INV-9 开 adapter 特例 / (C) Edge 拆 2 Claim with synthetic shared ID

per identity §11.2 table:
- **(B) INV-9 adapter 特例逃生窗**:破坏 INV-9 统一性 — ledger 形态变成 "大多 unary + 少数 n-ary";代码 path 永远要 conditional handle;`write_protocol.set_field` strict enforce check 要 carve-out;违反"统一 invariant"原则
- **(C) Edge 拆 2 个 Claim + synthetic 共享 ID** with non-schema-derived ID(per identity §11.2 原 reject):synthetic ID 不属于 ledger native concept;但**注意**:本 ADR §4.4.2 锁定的 "multi-Claim Relationship lowering" 是**不同的设计** — 用 **schema-declared addressing**(Relationship type + Field declaration + idref_v1-style instance e_ref)而非 ad-hoc synthetic;两条 Claims 是 anchor + Field(各有 first-class 角色),不是 synthetic-keyed 拆分

#### 4.4.6 Slice 5 implementation surface(本 ADR 不锁细节,留 Slice 5 blueprint)

本 ADR 仅锁:
- §4.4.1 edge value 是 semantic + 不进 claim_meta
- §4.4.2 multi-Claim lowering contract(anchor Claim + value Field Claim)
- §4.4.3 addressing model 留 Slice 5(含约束)
- §4.4.4 兼容性 confirm(4 cross-ADR)
- §4.4.5 reject (B) / (C)

具体 adapter 内部模块分解 / migration 顺序 / contract test 形态 留 Slice 5 blueprint:

- adapter 内部 `_edge_rest_terms` rename / 重写 → `_edge_to_relationship_claims`(返回 list of typed `Claim` — anchor + value Field;not rest_terms list)
- `accept_pyreason_session` edge facts 路径:`set_field(...)` 调用改 application layer 高层 entry,**atomic emit anchor + value Claims**
- PyReason model 跟 ledger Relationship schema 注册的 mapping 协议(若 PyReason 用不同名字,adapter 做 name translation)
- Relationship schema 注册 verification:Slice 5 implementation 必须 verify 所有 used relationship types 已 register(per ADR-API §4.5.1)
- contract test:roundtrip PyReason edge fact → ledger anchor Claim + value Field Claim(atomic)→ query back 还原 PyReason model with confidence/weight/etc.
- contract test:**claim_meta 不含 edge value**(per §4.4.1 边界)

### 4.5 Cross-Q decision summary + 三项绑定 closure

| Sub-decision | Decision | Implementation surface | Slice |
|---|---|---|---|
| Q4-1 | INV-9 strict enforce form = **write_protocol layer ingress runtime check**(`set_field` 入口,before typed Claim DTO construction;per §4.1.1)+ Slice 5 后 DTO/SQL type-level enforce 主防御 | Slice 5 加 5 行 check at write_protocol;Slice 3b 不动 | Slice 5 |
| Q4-2 | Slice 3b 完全不加 runtime enforce(per ADR-SYS-B §4.2 选 (c) 一致;legacy adapter 继续写 2-position)| 跟 ADR-SYS-B 同 — `write_protocol.set_field` + `Ledger.append_assertion` Slice 3b 全程不加 INV-9 check;legacy adapter 不动 | Slice 3b(零 enforce 改动)|
| Q4-3 | Slice 5 strict enforce 落地 + 三项绑定其一(per ADR-SYS-B §4.7.2)| Slice 5 加 §4.1.1 write_protocol ingress check + §4.1.2 DTO/SQL drop rest_terms + 三项绑定 acceptance criteria 落地 | Slice 5 |
| Q-PR1 | PyReason adapter rewrite 走 identity §11.2 option (A) **multi-Claim Relationship lowering**(anchor Claim + value Field Claim)| Slice 5 adapter `_edge_rest_terms` → `_edge_to_relationship_claims`(plural);reify n-ary edge → multiple first-class unary Claims(anchor + value Field;edge value 不进 claim_meta)| Slice 5 |

**三项绑定 closure**(per §1.3 ADR-SYS-B §4.7.2 contract requirement):

```text
[Slice 5 acceptance — 三项 atomic 必备]
  ┌─ 项 1:ALTER TABLE drop `rest_terms` 列  ← ADR-SYS-B §4.7.2 第 1 项
  ├─ 项 2:PyReason adapter rewrite (lowering)  ← 本 ADR §4.4
  └─ 项 3:write_protocol ingress strict check + Claim DTO / SQL schema type-level enforce  ← 本 ADR §4.1 + §4.3

  ★ 任一项缺失 → Slice 5 不可 mark `implemented`
  ★ 三项绑定保证 ledger schema(drop 列)+ caller(adapter)+ enforce
    (runtime check)同步达终态
```

**整体**:Slice 5 实施范围 ≈ 200-400 行代码改动:
- `core/evidence/write_protocol.py` `set_field` 入口加 §4.1.1 INV-9 runtime check(before typed Claim DTO construction)
- `core/store/ledger.py` ALTER TABLE drop rest_terms 列 + `Claim` DTO drop rest_terms 字段(SQL/DTO type-level enforce per §4.1.2)
- `adapters/pyreason/accept.py` `_edge_rest_terms` rewrite 为 `_edge_to_relationship_claims`(plural;返回 anchor + value Field Claims;per §4.4)
- `find_claim_args` wrapper LEGACY path 清理(per ADR-SYS-B §4.3.5 Slice 5 cleanup)
- migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`
- contract test(per §4.3.2 7 项)

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q4-1 alternative — read-path strict assertion(`assert isinstance(claim, UnaryClaim)`)

- **Why rejected**:Slice 5 后 drop rest_terms 列 + DTO drop 字段 — type-level 已保证 unary(`Claim.value` / `Claim.value_tag` 唯一 payload);read-path strict assertion 是 redundant defense;write_protocol layer ingress strict check 在更 fail-fast 的位置(写入时 catch,不等到读出来才发现);跟 meta-ADR §4.4 4-layer enforcement 的 "write-side strict;read-side 依赖 type system" 模式一致

#### Q4-1 alternative — SQL CHECK constraint(`CHECK (LENGTH(json(rest_terms)) <= 1)`)

- **Why rejected**:Slice 5 drop rest_terms 列后 SQL CHECK target 不存在(列已 drop);若 Slice 3b 加 CHECK 会立即 break adapter(同 Q4-2 (a) 情形)— 违反 zero-Q-PR1;SQL CHECK 错误 message 不可定制(无 migration hint);跟 §4.1.1 write_protocol layer runtime check + typed exception 路径不一致

#### Q4-1 alternative — strict enforce at `Ledger.append_assertion` entry(检查 `claim.rest_terms`)(★ P1-amend 新增 reject)

- **Why rejected**(★ P1-amend):per ADR-SYS-B §4.1.4 演化 + 本 ADR §4.3.2,Slice 5 时 `Claim` DTO **drop `rest_terms` field** → Ledger.append_assertion 接收的 typed Claim 已不含该 attribute;`len(claim.rest_terms)` 在 Slice 5 后会 raise `AttributeError` 而非 INV-9 检查。check 必须在 `rest_terms` list 仍 alive 的最后一层 — **write_protocol layer ingress**(per §4.1.1),before typed Claim DTO 构造。Ledger.append_assertion 层走 type-level enforce(Claim DTO schema 即保证 unary)+ SQL schema 强制(claims 表无 rest_terms 列)。

#### Q4-1 alternative — Slice 5 keep transitional `rest_terms` field on Claim DTO + check at Ledger,then drop field in same slice

- **Why rejected**:两阶段 work within Slice 5(先加 check 再 drop field)— 实施复杂度上升;DTO transitional 阶段跟 SQL schema 不对齐(列已 drop 但 DTO 仍有 field 形成 dual-truth);write_protocol layer ingress check(本 ADR §4.1.1 选择)是 single-phase clean design — 同 Slice 5 内 check 加 + DTO drop + SQL schema drop 同步落地,无中间 transitional 状态。

#### Q4-2 alternative — Slice 3b 加 weak enforce 只在 NEW write paths(`append_revocation_claim` / SDK fields.set 等),legacy adapter 路径绕过

- **Why rejected**:NEW write paths 实施侧已 hardcoded `rest_terms=[]`(per ADR-SYS-B §4.3.2)— weak enforce 在 NEW 路径 trivially 满足,无防御价值(纯 dead check);实施复杂度上升(两条 write path 的 enforce 分支处理);Slice 3b 完全无 enforce 跟 ADR-SYS-B §4.2 选 (c) dual-coexistence 一致

#### Q4-3 alternative — Slice 5 仅 adapter rewrite + drop 列,**不**加 strict enforce(留 Slice 6+)

- **Why rejected**:**违反 ADR-SYS-B §4.7.2 三项绑定 contract**;adapter rewrite + drop 列后 ledger schema 已是终态(unary),但若不加 enforce check,future regression(adapter 错误 reintroduce n-ary / migration tool 漏点 / 第三方 caller bug)无 runtime guard;defense-in-depth 是 marginal 5 行 cost,binding 三项确保 atomicity

#### Q-PR1 alternative — option (B):给 INV-9 开 adapter 特例逃生窗(允许特定 pred_id 保留 n-ary)

- **Why rejected**(per identity §11.2):破坏 INV-9 统一性 — ledger 形态变成 "大多 unary + 少数 n-ary",所有 reader 都需要 conditional handle;`Ledger.append_assertion` strict enforce 需 carve-out("特例 pred_id 不 check")— 复杂化整套 invariant 系统;ledger 终态目标是单一 schema 形态

#### Q-PR1 alternative — option (C):Edge 拆 2 个 Claim + synthetic 共享 ID

- **Why rejected**(per identity §11.2):synthetic 共享 ID 不属于 ledger native concept(违反 INV-5 source of truth — synthetic ID 是 derived state);两条 Claim 通过 ad-hoc synthetic key 关联(非 schema-derived addressing);Relationship Claim lowering(option A)用 schema-declared addressing(per §4.4.3)是更 native 形态。**注**:本 ADR §4.4.2 multi-Claim lowering(anchor + value Field Claim)**不**是 (C) 的变种 — 用 schema-declared addressing 而非 synthetic ID;两条 Claim 是 first-class anchor + Field(各有 schema 角色),不是 synthetic-keyed 拆分。

#### Q-PR1 alternative — edge value → claim_meta(shadow fact channel)(★ P2-amend 新增 reject)

- **Why rejected**(★ P2-amend):**违反 claim_meta non-truth 边界**(per ledger-spec §3.2 + §5.3 META_KEY_REGISTRY)— claim_meta 承载 non-truth provenance(source / trace_id / note / etc.),**不**作为 fact 语义 payload。把 PyReason edge value(典型是 confidence / weight / truth degree — semantic payload)放入 claim_meta:
  - 制造 shadow fact channel — semantic truth 偷渡进 metadata layer
  - 违反 INV-13 active projection 公式(claim_meta 不在 fact projection 范围)
  - 违反 INV-15 read filter 边界(filter system claims 但 claim_meta 跟随 claim active 状态)— semantic payload retract 语义不连贯
  - 跟 ADR-API §4.4 `_meta` 统一立场冲突(`_meta` 是过滤入口,不是 truth payload)
- **正确做法**(§4.4.2 锁定):edge value 走 first-class Relationship Field Claim(schema-declared);atomic 跟 anchor Claim 写入;走标准 INV-13 projection / INV-15 filter / retract 语义。

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
- `src/factgraph/core/store/ledger.py:363-378` `Ledger.append_assertion` entry — Slice 5 时 Claim DTO 已 drop rest_terms field(per ADR-SYS-B §4.1.4 signature 演化 + 本 ADR §4.1.2 type-level enforce);**不**在此层加 length check(per §4.1.5)— check 在上游 `write_protocol.set_field` ingress
- `src/factgraph/core/evidence/write_protocol.py:128-157` `set_field` entry(Slice 5 加 §4.1.1 INV-9 runtime check before typed Claim DTO construction)
- `src/factgraph/core/protocol/tup_v1.py:156-168` `canonical_bytes_tup_v1(rest_terms)` 协议 list 包装(Slice 5 drop 列后 dead)
- `src/factgraph/core/protocol/tup_v1.py:196-208` `claim_args_from_rest_terms` 路径(Slice 5 drop 列后 dead — 同步 ADR-SYS-B §4.3.5 wrapper Slice 5 cleanup)

**Q-PR1 baseline**(Slice 5 adapter rewrite target):
- `src/factgraph/adapters/pyreason/accept.py:187-205` `_edge_rest_terms(fact, pred_spec)` — **当前返回 2-element rest_terms**;Slice 5 rewrite 为 `_edge_to_relationship_claims`(plural;返回 typed `Claim` list — anchor + value Field Claims per §4.4.2)
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
| 3. `write_protocol` ingress strict check + Claim DTO / SQL schema type-level enforce | §4.1.1 + §4.1.2 + §4.3(本 ADR 锁)|

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
- §4.1.4 `Ledger.append_assertion` signature 演化 — 本 ADR §4.1.1 check 位置在上游 `write_protocol` ingress(before typed Claim DTO construction);Ledger 层接收的 Claim DTO 已 drop rest_terms field(per §4.1.5 — type-level enforce 已 sufficient,Ledger 层不重复 check)

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
| Slice 5 implementation:`write_protocol.set_field` 入口加 §4.1.1 INV-9 runtime check(before typed Claim DTO construction)+ ALTER TABLE drop `rest_terms` 列 + `Claim` DTO drop `rest_terms` 字段(per §4.1.2 type-level enforce)| Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:PyReason adapter rewrite — `_edge_rest_terms` → `_edge_to_relationship_claims`(plural;returns typed Claim list — anchor + value Field per §4.4.2)| Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:`find_claim_args` wrapper LEGACY path cleanup + migrate `projector.py:96` + `chosen.py:148` 直读(per ADR-SYS-B §4.3.5 Slice 5 cleanup follow-up)| Slice 5 implementation | Slice 5 Step 4.7 |
| Slice 5 implementation:contract test 覆盖三项绑定 acceptance(per §4.3.2 7 项 + §4.4.4 PyReason roundtrip)| Slice 5 implementation | Slice 5 Step 4.7 |
| docs sync(Slice 4 或 ADR-DOCS)— `ledger-schema-specification §9.4` + `identity-mechanism-redesign §11` 跟 ADR-INV9 对齐;`04_api_surface.en.md` 加 Slice 5 后 Claim DTO 终态说明 | Slice 4 docs sync 或 ADR-DOCS | Slice 5 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-DOCS 起草时 Header `Depends on:` 引用本 ADR(本 ADR 锁定的 Q-PR1 adapter rewrite path 是 docs sync 范围内的 architectural change);Slice 5 blueprint preflight(Step 4.3)必须 re-read 本 ADR §4.3 + §4.4 + §4.5 三项绑定
- **Blueprint pillar**:Slice 5 blueprint Stage 4 acceptance criteria 必须包含 §4.3.2 + §4.5 三项绑定 closure check;Slice 3b blueprint **不需要**引用本 ADR(§4.2 锁 Slice 3b 完全 decoupled)
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q4 行 status 仍是 "待 ADR 决策" — 实际 ADR-INV9 已 lock;**不**触发 audit doc post-stage sync(跟其他 Stage 2 ADRs 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 5 blueprint 不可单方面 override Q4 / Q-PR1 决策;若需要 override,走 "本 ADR superseded by 新 ADR-INV9-v2" 路径
- §4.1 write-path strict enforce 位置:carry-forward — 永远在 `write_protocol` layer ingress(`set_field` 入口,before typed Claim DTO construction;per §4.1.1);**不可**移到 `Ledger.append_assertion` 层(per §4.1.5 — DTO drop rest_terms field 后无 attribute 可 check);**不可**改为 read-path strict 或 SQL CHECK 形态
- §4.2 Slice 3b 完全不加 enforce:carry-forward — 不可后续在 Slice 3b implementation 加 enforce(违反 zero-Q-PR1 + 跟 ADR-SYS-B §4.2 (c) 冲突)
- §4.3 三项绑定 + Slice 5 落地:carry-forward — 三项 atomicity 不可拆;不可在 Slice 5 之前 / 之后 / 单独落地任一项
- §4.4 PyReason adapter rewrite 走 option (A) Relationship Claim lowering:carry-forward — 不可改走 option (B) INV-9 例外 / option (C) Edge 拆 2 Claim;若 future 需要 (B) / (C),走 supersede 本 ADR 路径
- §4.4.4 Slice 5 blueprint scope:carry-forward — 本 ADR 不锁 adapter 内部细节(留 Slice 5 blueprint);Slice 5 blueprint 不可单方面改 §4.4.1 lowering 路径形态

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.5 Q4 + Q-PR1 + 三项绑定 closure 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥10 项含 Q4-1 / Q4-2 / Q4-3 / Q-PR1 alternatives + 2 项 P1-amend 新增 + 1 项 P2-amend 新增)+ cross-Q rejected combinations(≥3)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / ADR-SYS-B 三项绑定 closure / no-Q-PR1-as-dep confirmation / 5 cross-ADR 兼容性 7 类 evidence
- [x] §6.5 显式 closure ADR-SYS-B §4.7.2 三项绑定 contract;§6.6 显式 confirm Q-PR1 在本 ADR 范围内是 sub-decision 不是 dep;跟 zero-Q-PR1 hard rule 不冲突
- [x] §4.1 INV-9 strict enforce 位置在 **write_protocol layer ingress**(not Ledger.append_assertion entry — DTO drop rest_terms field 后无 attribute 可 check;per §4.1.5 显式 reject Ledger 层 check)★ P1-amend
- [x] §4.1.2 Slice 5 后 type-level enforce 是主防御(Claim DTO drop field + SQL schema drop 列);§4.1.1 runtime check 是 defense-in-depth ★ P1-amend
- [x] §4.2 Slice 3b 完全不加 enforce — 跟 ADR-SYS-B §4.2 选 (c) + meta-ADR §4.4 zero-Q-PR1 一致
- [x] §4.4.1 PyReason edge value truth status 显式锁 — **semantic payload 不是 provenance**;不进 claim_meta(claim_meta non-truth 边界 per ledger-spec §3.2)★ P2-amend
- [x] §4.4.2 multi-Claim lowering contract 显式锁 — anchor Claim + value Field Claim(各 first-class unary);atomic 写入 per INV-3 + ADR-IC §4.2 ★ P2-amend
- [x] §4.4.3 Relationship instance addressing model 留 Slice 5 blueprint(显式约束 — 跟 ADR-IC cache / ADR-SYS-A G1/G2 / unique per (source, target) 正交)★ P2-amend
- [x] §4.4 PyReason adapter rewrite 走 identity §11.2 option (A) Relationship Claim lowering — 显式 cite design-point + reject (B) / (C);**额外** reject "edge value → claim_meta shadow channel"(per §5.1 P2-amend)
- [x] §4.5 三项绑定 closure 显式 enumerate(项 1 引用 ADR-SYS-B §4.7.2;项 2 + 项 3 本 ADR §4.3 + §4.4 锁)
- [x] Header `Depends on:` 引用 meta-ADR + ADR-SYS-B adopted commits
- [x] §7.4 显式 no-retroactive carry-forward 6 项

Post-adoption verification(implementation 阶段验证 — Slice 5):

**Slice 5 三项绑定 acceptance**:
- [ ] Slice 5 blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR + Stage 4 §10 Outcome acceptance criteria 含 §4.3.2 + §4.5 三项绑定 closure
- [ ] Slice 5 implementation **项 1**:`claims` 表 ALTER TABLE drop `rest_terms` 列 verified;`Claim` DTO drop `rest_terms` 字段;所有 `claim_args_from_rest_terms` / `canonical_bytes_tup_v1(rest_terms)` 路径 dead code 清理
- [ ] Slice 5 implementation **项 2**:PyReason adapter `_edge_rest_terms` rewrite 为 `_edge_to_relationship_claims`(**plural** — 返回 typed `Claim` list);edge facts → **multi-Claim** Relationship lowering(per §4.4.2):**[1]** anchor Claim(`pred_id=<rel_type>, e_ref=<source>, value=<target>, value_tag="entity_ref"`)+ **[2]** edge value Field Claim(`pred_id=<rel_type>:<value_field_name>, e_ref=<relationship_instance_e_ref>, value=<edge_value>, value_tag=<value_tag>`);两条 atomic 同 transaction
- [ ] Slice 5 implementation **项 3**:`write_protocol.set_field` 入口加 §4.1.1 INV-9 runtime check(before typed Claim DTO construction);**`Ledger.append_assertion` 入口不加 length check**(per §4.1.5 — Claim DTO 已 drop rest_terms field,无 attribute 可 check;type-level enforce 通过 DTO/SQL schema 实现)
- [ ] Slice 5 implementation:contract test — PyReason edge fact roundtrip:edge fact in → adapter lowering → ledger **两条 Claims(anchor + value Field)**→ query back via ledger reader → reconstruct edge fact with semantic value
- [ ] Slice 5 implementation:contract test — `write_protocol.set_field` rejects length > 1 rest_terms with WriteProtocolError(含 ADR-INV9 §4.1 reference + Relationship migration hint);**不同于 Slice 3b 行为**(Slice 3b 接受 n-ary)
- [ ] Slice 5 implementation:contract test — `Ledger.append_assertion` 入口接受 typed `Claim` without rest_terms attribute(type-level enforce + SQL schema 无列);任何尝试 construct multi-arg Claim DTO 在静态 / runtime fail
- [ ] Slice 5 implementation:Slice 3b 期间已 shipped `__system__.revokes` Claim + Identity Claim + Field Claim 路径(per ADR-SYS-B + ADR-IC)在 Slice 5 strict enforce 后 **仍正常工作**(value/value_tag 已是 unary 形态;trivially 满足)

**ADR-SYS-B §4.3.5 follow-up**(per Slice 5 cleanup):
- [ ] Slice 5 implementation:`find_claim_args` wrapper LEGACY path dead code 清理(rest_terms 列已 drop,LEGACY path 不可达)
- [ ] Slice 5 implementation:migrate `projector.py:96` + `chosen.py:148` 直读 `Claim.value/value_tag`(per ADR-SYS-B §4.3.5 Slice 5 cleanup deferred follow-up)
- [ ] Slice 5 implementation:`SDKStore.find_claim_args`(`sdk/store.py:182`)deprecate / 评估 remove(per ADR-SYS-B §4.3.5 Slice 5 cleanup follow-up)

**Cross-ADR contract verification**:
- [ ] Slice 5 implementation:anchor Claim 形态(`value_tag="entity_ref"`)跟 ledger-spec §3.1 "Entity-ref field" row 一致;value Field Claim 走 "普通 value field" row 一致(per §4.4.4)
- [ ] Slice 5 implementation:PyReason adapter 用的 relationship types 全部已通过 `fg.schema.register/extend/apply` 路径注册(per ADR-API §4.5.1)— **若未注册,adapter 必须先 register**;Slice 5 blueprint 加 explicit registration step;value Field 也必须 schema-declared on Relationship type
- [ ] Slice 5 implementation:anchor + value Field Claims 的 pred_id 都不以 `__system__` 开头(per ADR-SYS-A G1/G2);adapter 输出 pred_id 经 schema declared,自然安全
- [ ] Slice 5 implementation:anchor + value Field Claims 写入路径不污染 ADR-IC `_protected_anchor_pred_ids` cache(Relationship pred_id 不属 `is_identity_field` / `is_entity_exists`)
- [ ] Slice 5 implementation:contract test — **edge value 不进 claim_meta**(per §4.4.1 边界);query Relationship anchor Claim 的 claim_meta 返回不含 `edge_fact_value` / 类似 key

**docs sync**:
- [ ] Slice 4 docs sync 或 ADR-DOCS:`ledger-schema-specification §9.4` 跟 ADR-INV9 对齐;`identity-mechanism-redesign §11.3` 跟 ADR-INV9 §4.4 对齐(Slice 5 实施完成 mark);`04_api_surface.en.md` 加 Slice 5 后 Claim DTO 终态说明

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-INV9 drafted | Q4 + Q-PR1 + 三项绑定 closure(关闭 ADR-SYS-B §4.7.2 carve-out)。Q4-1 strict enforce form = write-path runtime check at `Ledger.append_assertion` entry;Q4-2 Slice 3b 完全不加 enforce(跟 ADR-SYS-B §4.2 选 (c) + meta-ADR §4.4 zero-Q-PR1 一致);Q4-3 Slice 5 strict enforce + 三项绑定其一(per ADR-SYS-B §4.7.2);Q-PR1 走 identity §11.2 option (A) Relationship Claim lowering(reify n-ary edge → unary `Claim(pred=<rel_type>, e_ref=<source>, value=<target>, value_tag="entity_ref")`)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-SYS-B adopted @ `6b0ac349` + identity §11 design-point + ledger-spec §4.6 INV-9 + 5 cross-ADR(SYS-A/SYS-B/IC/API/FI)兼容性 confirm。Branch: `v0.2.0-q-inv9-adapter-enforcement-decision-2026-05-29`。Commit: `8fd22243` |
| 2026-05-29 | **adopted** | User reviewer 第 3 轮 review 通过 → adopt | 第 3 轮 review 结论:可以推进 adopt,前提是先做 P2/P3 sync cleanup;两项已采纳。**P2** 三项绑定 ASCII diagram 项 3(`Ledger.append_assertion strict enforce`)+ §6.5 ADR-SYS-B closure mapping 项 3 + §6.6.1 ADR-SYS-B cross-ADR compat note + §7.2 follow-up Slice 5 implementation row 全部 sync 改为 "write_protocol ingress strict check + Claim DTO / SQL schema type-level enforce"(per §4.1.1 + §4.1.2 + §4.3)。**P3** §4.1.4 error message contract migration hint "Relationship Claim"(单数)→ "**multi-Claim Relationship lowering**(anchor + value Field Claims;指 ADR-INV9 §4.4.2 + identity §11.2 option (A))"。本 ADR 现 binding constraint;Slice 5(Step 2+)PyReason adapter rewrite slice blueprint 可起草(§4.3.2 Stage 4 acceptance criteria 分 4 类 + §4.5 三项绑定 closure);三项绑定 contract 关闭(项 1 ADR-SYS-B + 项 2 + 项 3 本 ADR);**ADR-DOCS / ADR-IE** 可独立起草;blueprints / 后续 ADR 不可单方面 override §4.1-§4.5(含 INV-9 strict enforce 位置 = write_protocol ingress + multi-Claim Relationship lowering + edge value 不进 claim_meta 边界 + Slice 3b 零 enforce + Slice 5 三项绑定 atomic),override 需走"superseded by ADR-INV9-v2"路径。Commit: TBD post-stage |
| 2026-05-29 | proposed | ADR-INV9 2nd-round amended(P1/P2 sync cleanup,proposed)| User reviewer 第 2 轮 review 返回 3 findings — 2 P1 + 1 P2 都是上轮 amendment 漏 sync 残留;binding sections + acceptance criteria 自相矛盾。**(P1 sync — Ledger.append_assertion entry 残留 9 处)** 上轮 §4.1 重构 check 位置为 write_protocol layer ingress,但 §1.2 / §1.3 / §1.4 / §2 Scope §4.1 Q4-1 row / §4.2.2 Slice 3b note / §4.5 三项绑定 ASCII diagram 项 3 / §4.5 Cross-Q summary Q4-1 row / §4.5 implementation surface estimate / §6.2 shipped citation / §7.2 follow-up / §7.4 no-retroactive 仍写 "Ledger.append_assertion entry 加 strict enforce" — 跟 §4.1 + §4.3.2 自相矛盾(DTO drop field 后 Ledger 入口无 attribute 可 check)。**修复**:全量 sync 11 处 wording 为 "write_protocol layer ingress runtime check + Slice 5 后 DTO/SQL type-level enforce 主防御"(per §4.1.1 + §4.1.2 + §4.1.5)。**(P1 sync — single Relationship Claim 残留 3 处)** 上轮 §4.4 重构 lowering 为 multi-Claim,但 §2 Scope §4.4 Q-PR1 row / §4.5 Cross-Q summary Q-PR1 row / §4.5 implementation surface estimate / §6.2 shipped citation / §7.2 follow-up / §8 post-adoption 项 2 + Cross-ADR contract verify 仍写 "单条 Relationship Claim" + 函数名 `_edge_to_relationship_claim`(单数)。**修复**:全量 sync 7 处 wording 为 "multi-Claim Relationship lowering(anchor + value Field Claims)" + 函数名 `_edge_to_relationship_claims`(plural)+ post-adoption 项 2 改 2 条 Claims atomic 形态。**(P2 sync — INV-7b mirrored 误扩张)** §4.4.2 lowering ASCII diagram 把 source-target anchor Claim 标 "INV-7b mirrored",但 INV-7b 锁的是 Identity-as-Claim mirrored(per identity §5.2),不应扩张到 Relationship anchor 语义。**修复**:改 "first-class schema-declared relationship anchor"(语义清晰 + 跟 identity invariant 解耦)。同步 cascade:§8 post-adoption 项 2 + 项 3 重写 reflect multi-Claim + write_protocol ingress check;Cross-ADR contract verify 加 anchor + value Field Claims 区分 + claim_meta 不含 edge value 验证。 |
| 2026-05-29 | proposed | ADR-INV9 amended(1st-round P1/P2 fixes,proposed)| User reviewer post-draft review(同日)返回 2 findings — 1 P1 + 1 P2 都是 substantive contract issues。**(P1)** §4.1 strict enforce 锁在 `Ledger.append_assertion` entry 的 `len(claim.rest_terms) > 1` check,但 §4.3.2 同时要求 Slice 5 drop `rest_terms` 字段 from Claim DTO + drop 列 from claims 表;两项不能同时是 Slice 5 终态 contract — 若 DTO 无 rest_terms field,runtime check 在 Ledger 入口不可成立。**重构 §4.1**:check 位置改为 **write_protocol layer ingress**(`write_protocol.set_field` 入口,**before** typed Claim DTO construction)— rest_terms list 仍 alive 的最后一层 + 跟 meta-ADR §4.4 4-layer enforcement application/write 层 strict 一致;Ledger.append_assertion 看到的 typed Claim 已是 unary 形态(type-level enforce)+ SQL schema drop 列 strict 实施;runtime check 在 Slice 5 后是 defense-in-depth 防 legacy caller / future regression。新增 §4.1.2 Slice 5 type-level enforce + §4.1.5 显式 reject Ledger 层 check rationale;§4.3.2 acceptance 重写分 4 类(schema/DTO 演化 + strict enforce 位置 + adapter rewrite + cross-ADR cleanup + contract test);§5.1 新增 2 项 reject(Ledger 层 check + transitional DTO field 两阶段)。**(P2)** §4.4.1 lowering contract 把 edge `fact["value"]` 直接放进 `claim_meta` — 这是 shadow fact channel 风险(claim_meta 是 non-truth provenance 边界,不应承载 semantic payload)。**重构 §4.4**:加 §4.4.1 PyReason edge value 的 truth status 显式锁 — semantic payload(典型 confidence / weight / truth degree),**不**是 provenance;§4.4.2 重写 lowering contract 为 **multi-Claim** 形态 — anchor Claim(source-target,INV-7b mirrored)+ edge value Field Claim(schema-declared Relationship attribute);两条 Claims atomic per INV-3 + ADR-IC §4.2 emission;§4.4.3 Relationship instance addressing model 留 Slice 5 blueprint(显式约束 — 跟 ADR-IC cache / ADR-SYS-A G1/G2 / unique per (source, target) 正交);§4.4.4 兼容性 cross-ADR confirm 4 项;§4.4.5 reject (B)/(C) 同前 + 加注 §4.4.2 multi-Claim 不是 (C) 的 synthetic-keyed 变种;§4.4.6 Slice 5 implementation surface 加 schema register verification 前置;§5.1 新增 Q-PR1 alternative reject `edge value → claim_meta shadow channel` 含 4 项 invariant 违反 rationale;§8 acceptance criteria 重写分 4 类含 edge value 不进 claim_meta verification + multi-Claim atomic write verification。同步 cascade:§8 proposed-stage check 加 6 项 P1/P2-amend star check;post-adoption verify 重写 4 类 15+ 项。 |
