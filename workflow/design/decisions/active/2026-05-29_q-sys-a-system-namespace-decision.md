# Q-SYS-A Decision: `__system__.*` user-facing namespace reservation

- Status: adopted
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Q5a — `__system__.*` user-facing pred_id namespace reservation。**仅锁 user-facing reservation 拒绝点**;**不**锁 `__system__.revokes` payload shape / internal emission exception / read-path default filter(全留 ADR-SYS-B per meta-ADR §4.2 grouping)。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5a row(`audit:518`)+ §5.3 A19 row + §6 INV-10 row(`audit:284`)+ §5.4 shipped baseline confirmation(zero `__system__` hits in source)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md`(ADR-API)adopted `66434490` — §4.1 三层 namespace + §4.5 schema 三分(register/extend/apply)定义本 ADR enforcement 路径的入口
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`(ADR-IC)adopted `2d0866ed` — §4.3.1 `protected_anchor_pred_ids = identity ∪ exists` cache 跟本 ADR 的 `__system__.*` namespace **概念正交**(本 ADR §4.4 cross-ADR compat 显式 confirm)
  - ledger-schema-specification design-point §4.7 INV-10(`:290-300`)+ §3.1 命名空间边界 + §4.12 INV-15 / §4.8-4.11 INV-11/12/13(后三者**不**在本 ADR scope)
  - User reviewer 2026-05-29 ADR-SYS-A directional 4 项 review focus:仅锁 reservation 不锁 revokes payload / 拒绝点覆盖 `fg.fields.*` + 未来 `fg.assertions.write` + schema register/extend/apply / internal emission exception 留 SYS-B / 不冲突 ADR-API 三层 + ADR-IC protected_anchor cache
- Outputs / Downstream:
  - **ADR-SYS-B**(Q5b/Q15 — `__system__.revokes` emission + ledger migration)— 起草前置;ADR-SYS-B Header `Depends on:` 须引用本 ADR adopt commit
  - Slice 3b implementation:本 ADR §4.2 reject 路径跟 ADR-SYS-B 的 internal emission exception(per Q5b)同 slice 落地
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-INV9(Q4)/ ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-sys-a-system-namespace-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping Q5a 单独 ADR-SYS-A;§4.4 Step 1 zero-Q-PR1 dependency)
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`(ADR-FI Form I descriptor 跟本 ADR namespace 正交,§4.4 cross-ADR compat confirm)
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`(ADR-IC `protected_anchor_pred_ids` cache 跟本 ADR `__system__.*` namespace 概念正交,§4.4 显式 confirm)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted @ `66434490`(ADR-API §4.1 三层入口 + §4.5 schema 三分 是本 ADR reject 路径 enumeration 的入口语义依据)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q5a — System namespace cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q5a | `__system__.*` user-facing pred_id reservation check | `audit:518` | System namespace |

**Q5b 在本 ADR 之外**(audit:519):Internal `__system__.revokes` emission exception path → ADR-SYS-B。

### 1.2 Meta-ADR locked constraints relevant to ADR-SYS-A

- **§4.2 grouping**:Q5a 单独 ADR-SYS-A;Q5b + Q15(ledger migration)合 ADR-SYS-B(per meta-ADR §4.2 splitting rationale — Q5a 只锁 user-facing 边界,跟 emission / migration 解耦)
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / PyReason adapter rewrite — confirmed
- **§4.4 4-layer enforcement**:本 ADR §4.2 reject 路径在 SDK shell + application 层(strict)— 跟 ADR-FI §4.4 / ADR-IC §4.1 模式一致

### 1.3 User reviewer 2026-05-29 directional 4 项 review focus

ADR-SYS-A draft 启动前 user reviewer 给出 4 项 directional guidance:

| 项 | User guidance | 影响本 ADR |
|---|---|---|
| 1 | 只锁 user-facing `pred_id` reservation,不锁 revokes payload | §4.1 Scope 明确 user-facing reservation;§3 Non-scope 显式列出 revokes payload 留 ADR-SYS-B |
| 2 | 拒绝点覆盖 `fg.fields.*`、未来 `fg.assertions.write`、schema/register/extend/apply 中能声明 pred_id 的路径 | §4.2 reject 路径 enumeration 显式覆盖 4 个 layer |
| 3 | Internal/system emission exception 留给 ADR-SYS-B,不在 SYS-A 偷偷定义 | §3 Non-scope 显式 reject "internal emission 在 SYS-A" + §5.1 alt 显式 reject |
| 4 | 与 ADR-API 三层入口、ADR-IC protected anchor cache 不冲突 | §4.4 cross-ADR compat 显式 confirm 两项独立性 |

### 1.4 Shipped baseline(audit §5.4 / §6)

**Greenfield state**:
- **zero hits for `__system__` in shipped source**(per audit §6 INV-10 row `:284` — `sdk/store.py` / `sdk/facade.py` / `authoring/` / `core/` 全部 grep 无命中)
- `set_field`(`evidence/write_protocol.py:231-249`)`_validate_write_inputs` 仅类型检查,无 namespace check
- shipped `revokes` 走独立表(`ledger.py:106-110`)— **不**通过 `__system__.revokes` Claim 路径(per audit INV-11 row)

**5+1 state classification**(per audit §6):
- INV-10 `__system__.*` namespace reservation 是 **(f) target-gap / pending migration** — shipped 当前不存在该概念前提;Step 1 实施时建立 load-bearing boundary

**已 shipped 但本 ADR enforcement 路径必须 wire in 的入口**:
- `authoring/schema_compile.py:79-83` `entity_type` 字符串校验(当前仅 non-empty;将加 G2 prefix reject per §4.2 Layer B.1)
- `authoring/schema_compile.py:142` `f"{entity_type}:exists"` 拼接路径(将加 prefix reject defense in depth per §4.2 Layer B.1)
- `authoring/schema_compile.py:175-182` `_compile_relationship` `relationship_type` 校验(当前仅 non-empty;将加 G2 prefix reject per §4.2 Layer B.2 — P1 amendment new coverage)
- `authoring/schema_compile.py:460-478` `_compile_relationship_pred_id` 产 `f"{relationship_prefix}:{local}"`(G2 上游 reject 后自然安全)
- `sdk/schema.py:248-...` `Relationship` / `RelationshipMeta` descriptor public surface(将集成 §4.2 Layer A.2 G2 reject hook)
- ADR-API §4.5 `register/extend/apply` 三分 hook(将集成 §4.2 Layer A.1 + A.2 G2 reject 双路径)
- `sdk/batch.py:540-...` `_parse_wire_write_op` + `:877-...` `_resolve_wire_field_for_write_op`(§4.2 Layer E transitive G2 covered — 不动)

## 2. Scope

本 ADR **锁**以下 sub-decisions(单 Q):

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q5a-1** | `__system__` prefix 是 ledger reserved namespace;**两个独立命名 guard**:**G1 raw pred_id guard**(精确 `__system__.` 含点)+ **G2 schema owner guard**(精确 `__system__` 不含点,覆盖 entity_type / relationship_type 等 owner_type)|
| **§4.2 Q5a-2** | Reject 路径 enumeration — 覆盖 5 layer:Layer A(`fg.schema.register/extend/apply` × entity+relationship 双路径,G2)+ Layer B(`schema_compile.py:_compile_entity` + `_compile_relationship` defense in depth × 2,G2)+ Layer C(未来 raw pred_id 入口若 Step 2+ 引入,G1)+ Layer D(`fg.fields.*` 自动安全 derive)+ Layer E(`WireBatchPlan` schema-bound replay,G2 transitively covered)|

## 3. Non-scope

本 ADR **不**锁(per user reviewer §1.3 第 1+3 项 + meta-ADR §4.2 grouping):

| 不锁 | 留给谁 |
|---|---|
| `__system__.revokes` Claim payload shape(pred_id / e_ref / value / value_tag / claim_meta encoding)| **ADR-SYS-B**(Q5b/Q15.2)|
| Internal / system emission exception path(internal writer API / `retract_by_asrt` lowering / protocol-layer 绕过 mechanism)| **ADR-SYS-B**(Q5b)|
| INV-11 revoke payload shape | **ADR-SYS-B** + ledger migration |
| INV-12 revoke target 约束(part 2 — revoke target 不可是 system claim)| **ADR-SYS-B**(跟 emission 同步实施)|
| INV-13 active projection 单一公式 + INV-15 read path default filter(`pred_id NOT LIKE '__system__.%'`)| **ADR-SYS-B**(跟 emission 时序耦合 — read filter 仅 after emission 存在才必要)|
| 7 数据精简 ledger migration 切片 | **ADR-SYS-B**(Q15)|
| 其他可能未来 reserved prefix(`__internal__` / `__admin__` / etc.)| Step 2+ |
| `<EntityType>:exists` 是否仍属合法 user-facing pred_id(per ADR-IC §4.4 Step 1 保留)| **ADR-IC**(已 adopted)— 不属本 ADR 范畴 |
| Slice 3b 落地的 blueprint slicing | Slice 3b blueprint |

## 4. Decision

### 4.1 Q5a-1 — `__system__` 命名空间预留:**ledger reserved**;**两个命名清晰的 guard**

**锁定**:`__system__` prefix(注意:**双下划线** + `system` + **双下划线**)在 ledger 中是 **reserved system namespace**。两类 user-facing surface 各自由**独立命名的 guard** 把守 — 它们防的是**不同 attack surface**,不可合并:

#### 4.1.1 G1 — `raw pred_id guard`

> `pred_id.startswith("__system__.")`(**精确**双下划线 + system + 双下划线 + **点**)

**适用面**:user **直接供给 raw pred_id** 的入口。Step 1 内 **不存在** 这类入口(per design-point §12.2 line 974 — "Step 1 不引入 `fg.assertions.write` 这类绕开 schema 的写入路径");forward-looking 规约 covering:
- 未来 `fg.assertions.write(pred_id=...)`(若 Step 2+ 引入)— 详 §4.2 Layer C
- 未来 schema-free wire 接口(若 Step 2+ 引入)— 同 §4.2 Layer C 规约

#### 4.1.2 G2 — `schema owner guard`

> `owner_type.startswith("__system__")`(**精确**双下划线 + system + 双下划线;**不要求**末尾点)

**适用面**:user 通过 **schema declaration** 间接产生 pred_id 的入口。owner_type 是 schema 编译路径上 pred_id 拼接的左半:`<owner_type>:<field_name>`(对 entity)或 `<relationship_type>:<field_name>`(对 relationship)。

这类入口下,user 不直接写 `__system__.X`,而是写 `entity_type = "__system__X"` 或 `relationship_type = "__system__Y"`,schema_compile 会产生:
- `__system__x:exists` predicate(entity)
- `__system__x:field_name` predicate(entity field)
- `__system__y:field_name` predicate(relationship field)

这些 pred_id 是 **冒号 separator** 不是 dot,**不**被 G1 catch — 必须用 G2(`owner_type` prefix check)在 schema declaration 层 reject。

**G2 覆盖的所有 owner_type 源**:
- `EntityClass.entity_type`(per `sdk/schema.py` Entity descriptor;`authoring/schema_compile.py:79-83`)
- `RelationshipClass.relationship_type`(per `sdk/schema.py:248-...` Relationship descriptor;`authoring/schema_compile.py:175-182`)
- 任何**未来**新增的 schema declaration 可产生 owner-prefixed pred_id 的 surface(应继承 G2)

#### 4.1.3 为什么不合并成单 guard

| 角度 | G1 单独 | G2 单独 | G1 + G2 双 guard |
|---|---|---|---|
| `entity_type = "__system__X"` → `__system__x:exists` | ✗ catch 不到(no dot)| ✓ | ✓ |
| `relationship_type = "__system__Y"` → `__system__y:field` | ✗ catch 不到(no dot)| ✓ | ✓ |
| 未来 raw `fg.assertions.write(pred_id="__system__.revokes")` | ✓ | ✗ catch 不到(无 owner)| ✓ |
| Implementation 复杂度 | low | low | low(两 helper funcs)|

→ **必须双 guard**,各管 1 类 attack surface;单 guard 任一选择都漏一类。

#### 4.1.4 Pattern 精确性(两 guard 同适用,per design-point ledger-spec §4.7 INV-10)

- G1 / G2 都是 **精确 prefix match**(`str.startswith`)
- **不**拒绝近似变种(如 `__sys__` / `__system_` 单下划线 / `_system_` 单下划线 / `___system___` 三下划线)— 用户若刻意命名近似形式自行承担歧义;本 ADR 不做 fuzzy match(per §5.1 alt rejected)
- 跟 ledger-spec §4.7 INV-10 statement 一致(reserved namespace 是 `__system__.*`,本 ADR 把它解析为 G1(`__system__.` 严格)+ G2(`__system__` 宽口径覆盖 schema-derived 冒号 predicates))

### 4.2 Q5a-2 — Reject 路径 enumeration:**5 layer × 2 guard enforcement**

**锁定**:5 个 layer 各自的 reject 责任,每个 layer 显式标注 **G1**(raw pred_id guard)或 **G2**(schema owner guard)per §4.1:

#### 4.2.1 Layer A — `fg.schema.register/extend/apply(SchemaClass)` 入口侧 reject(**G2** strict)

**位置**:ADR-API §4.5.1 锁的 `register/extend/apply` 三分 method 入口。

**Schema declaration 双路径**:本 layer 覆盖 **entity + relationship** 两类 schema declaration(per shipped SDK public surface)。**owner_type 必须从 SDK schema spec 提取**,不从假定的 class attr — 跟 shipped pattern 一致。

##### 4.2.1.0 Owner type 提取 contract(critical implementation note)

Shipped pattern(per `sdk/schema.py`):
- **Entity**:`Entity.sdk_entity_spec()` classmethod(`sdk/schema.py:241-245`)返回 dict;`spec["entity_type"]` 是权威 owner type
- **Relationship**:`Relationship.sdk_relationship_spec()` classmethod(`sdk/schema.py:302-307`)返回 dict;`spec["relationship_type"]` 是权威 owner type;**`RelationshipMeta.__new__`(`sdk/schema.py:286-295`)将 `name`(Python class name)写入 `spec["relationship_type"]`**

**Implementation MUST extract from SDK schema spec, not from class attribute**:
- `getattr(cls, "entity_type", None)` — **错误**;Entity 不保证有 public `entity_type` class attribute
- `getattr(cls, "relationship_type", None)` — **错误**;Relationship 的 relationship_type 存在 `__sdk_relationship_spec__` dict 中,不在 class attr
- `cls.__name__` — **错误**;Python class name 可能跟 schema spec 中的 owner_type 不同(尤其 entity 端有可能 customize)

##### 4.2.1.1 G2 owner guard helper(共用 G2 check)

```python
def _check_user_facing_owner_type(owner_type: str, *, kind: str) -> None:
    """G2 schema owner guard — applied to entity_type and relationship_type.

    Args:
        owner_type: extracted from SDK schema spec (entity_type or relationship_type)
        kind: "entity_type" or "relationship_type" — used in error message
    """
    if owner_type.startswith("__system__"):   # G2 schema owner guard (per §4.1.2)
        raise SDKStoreError(
            f"{kind} {owner_type!r} uses reserved system namespace.\n"
            f"  `__system__` is reserved for ledger internal mechanisms\n"
            f"  (see ADR-SYS-A §4.1 G2 schema owner guard). User-facing schema\n"
            f"  registration cannot declare {kind} starting with '__system__'.\n"
            f"  Choose a different {kind} (e.g., a non-system name)."
        )
```

##### 4.2.1.2 Entity 路径(extract via `sdk_entity_spec()`)

```python
def _register_entity_with_g2(entity_class: type[Entity]) -> None:
    spec = entity_class.sdk_entity_spec()                          # raises SDKSchemaError if not compiled
    _check_user_facing_owner_type(spec["entity_type"], kind="entity_type")
    # ... dispatch to ADR-API §4.5 register implementation
```

##### 4.2.1.3 Relationship 路径(extract via `sdk_relationship_spec()`)

```python
def _register_relationship_with_g2(relationship_class: type[Relationship]) -> None:
    spec = relationship_class.sdk_relationship_spec()              # raises SDKSchemaError if not compiled
    _check_user_facing_owner_type(spec["relationship_type"], kind="relationship_type")
    # ... dispatch to ADR-API §4.5 register implementation
```

**为什么覆盖 relationship 路径**:`sdk/schema.py:248-307` `Relationship` / `RelationshipMeta` descriptor 是 shipped public surface;`RelationshipMeta.__new__`(`:286-295`)把 Python class name 作为 `relationship_type` 写进 `__sdk_relationship_spec__`;`authoring/schema_compile.py:175-182` `_compile_relationship` 接受 `relationship_type` 并 `_owner_prefix(relationship_type)` 产生 relationship predicate prefix(`authoring/schema_compile.py:460-478` `_compile_relationship_pred_id`)。**不**加 reject = user 可 `class __system__MyRel(Relationship): ...` 产 spec["relationship_type"] = "__system__MyRel" → schema_compile 产 `__system__my_rel:field` 落地 ledger,违反 INV-10。

**为什么 strict 在 SDK shell**:fail-fast — 在 schema 声明早期 catch,user 立刻收到 error;不浪费 schema_compile 路径资源。

#### 4.2.2 Layer B — `authoring/schema_compile.py` defense in depth(**G2** strict)

**位置**:两个对称 entry point:
- `authoring/schema_compile.py:79-83` `_compile_entity` `entity_type` 校验
- `authoring/schema_compile.py:175-182` `_compile_relationship` `relationship_type` 校验

**实施**:两个 entry point 都加 G2 prefix check(defense in depth — bypass-SDK-shell path catch):

```python
# _compile_entity:
def _compile_entity(entity_raw, entity_index, ...):
    entity_type = entity_raw.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise _compile_error(...)
    if entity_type.startswith("__system__"):   # G2
        raise _compile_error(
            f"entity_type {entity_type!r} uses reserved system namespace `__system__` "
            f"per ADR-SYS-A §4.1 G2. Should have been rejected at SDK shell layer (Layer A) — "
            f"reaching schema_compile suggests internal API bypass; check caller path.",
            path=f"$.entities[{entity_index}].entity_type",
        )
    # ... rest of _compile_entity

# _compile_relationship (对称 — 同 G2 check):
def _compile_relationship(rel_raw, rel_index, ...):
    relationship_type = rel_raw.get("relationship_type")
    if not isinstance(relationship_type, str) or not relationship_type:
        raise _compile_error(...)
    if relationship_type.startswith("__system__"):   # G2
        raise _compile_error(
            f"relationship_type {relationship_type!r} uses reserved system namespace `__system__` "
            f"per ADR-SYS-A §4.1 G2. Should have been rejected at SDK shell layer (Layer A) — "
            f"reaching schema_compile suggests internal API bypass; check caller path.",
            path=f"$.relationships[{rel_index}].relationship_type",
        )
    # ... rest of _compile_relationship
```

**为什么 defense in depth**:caller 直接调 `compile_schema(spec_dict)` 路径(bypass SDK shell `fg.schema.register/extend/apply`)— 如 internal migration tool / test fixture / Step 2+ programmatic schema construction — 仍然 enforce;两个 schema entry point 对称 covered;跟 ADR-FI §4.4 4-layer enforcement 一致(SDK shell + application 双层 strict)。

#### 4.2.3 Layer C — 未来 raw pred_id 入口 reject(**G1** forward-looking 规约,本 ADR **不**锁该 API 是否引入)

**位置**:per design-point §12.2 line 974,**Step 1 不引入** `fg.assertions.write(pred_id, e_ref, value)` 这类绕开 schema 的写入路径。

**Forward-looking 规约**:若 Step 2+ 引入任何接受 user-supplied raw pred_id 的入口(`fg.assertions.write` / 新增 schema-free wire 接口 / 等),**必须** reject 以 G1 pattern:

```python
# Step 2+ 假设引入时:
def write(self, *, pred_id: str, e_ref: str, value: Any, ...) -> str:
    if pred_id.startswith("__system__."):   # G1 raw pred_id guard
        raise SDKStoreError(
            f"pred_id {pred_id!r} uses reserved system namespace per ADR-SYS-A §4.1 G1. "
            f"User-facing assertions.write cannot supply system pred_ids. "
            f"System claims are emitted by internal mechanisms only (see ADR-SYS-B)."
        )
```

**本 ADR 不锁是否引入该 API**;只锁 **若**引入 **必须**包含 G1 reject。该 forward-looking 规约 carry-forward(per §7.4)。

#### 4.2.4 Layer D — `fg.fields.*` 自动安全 derive(no independent enforcement needed)

**位置**:ADR-API §4.1 Layer 2 `fg.fields.set/add/retract/delete(Field, e_ref, value)`。

**Derive 安全**:Layer 2 fields API 输入是 `Field` descriptor(来自 schema-declared)+ encoded e_ref string + value;**不接受** raw pred_id。Field descriptor 的 `pred_id` 在 `_compile_field` / `_compile_relationship_field` 路径产生(per `authoring/schema_compile.py:227-260` + `authoring/schema_compile.py:460-478`)— 已经过 Layer A + Layer B G2 reject。

**结论**:Layer 2 入口**无独立 reject 路径**;reject 责任全部 dispatch 到 Layer A + B。这跟 ADR-API §4.1 排他原则(Layer 2 不接 `asrt_id` 或 raw pred_id)一致。

#### 4.2.5 Layer E — Schema-bound wire-replay paths(**transitive G2** covered;no independent reject)

**位置**:shipped `sdk/batch.py:540-...` `_parse_wire_write_op` 路径 — `WireBatchPlan` 从 JSON 解析 raw `pred_id` 字段(看似 raw pred_id 入口);`sdk/batch.py:877-...` `_resolve_wire_field_for_write_op` 应用时通过 `pred_index: dict[str, dict[str, Any]]`(schema pred index)校验 + reject ambiguous / unknown / mismatch entries。

**分类**:**schema-bound wire-replay path** — 虽然 wire JSON 中 raw `pred_id` 字段看似是 user-supplied,但 apply 路径**强制要求**该 pred_id **必须存在于 schema pred_index**(`pred_index.get(op.pred_id) is None → raise SDKStoreError`),且 owner_type / field_name 跟 schema 严格匹配。

**Transitively covered by G2**:Layer A + B G2 reject 后,schema pred_index **不可能**包含 `__system__:*` predicates;wire-replay path 试图 apply `pred_id="__system__:X"` 会被 `pred_index.get(...) is None` reject(binding validation failure),**不需要**本 ADR 在 wire 解析层独立加 reject。

**为什么不算 G1 raw pred_id 入口**:G1 适用于 "user supply raw pred_id 直接写 ledger"(不绑定 schema);Layer E wire-replay 是 "user supply 已经存在 schema 中的 pred_id 用于 replay"(绑定 schema)。后者 attack surface 由 G2 + schema binding validation 双重覆盖,概念上不同。

**ADR docs sync**(per §7.2 follow-up):classification 写进 `04_api_surface.en.md` 防 reviewer 误以为漏 raw pred_id surface。

#### 4.2.6 Enforcement 层级总结

| Layer | 入口 | Reject 路径 | Guard | Enforcement 模式 |
|---|---|---|---|---|
| **A.1** | `fg.schema.register/extend/apply(EntityClass)` | `EntityClass.entity_type.startswith("__system__")` raise `SDKStoreError` | G2 | SDK shell strict |
| **A.2** | `fg.schema.register/extend/apply(RelationshipClass)` | `RelationshipClass.relationship_type.startswith("__system__")` raise `SDKStoreError` | G2 | SDK shell strict |
| **B.1** | `authoring/schema_compile.py:_compile_entity` | defense in depth `entity_type.startswith("__system__")` raise `_compile_error` | G2 | application strict |
| **B.2** | `authoring/schema_compile.py:_compile_relationship` | defense in depth `relationship_type.startswith("__system__")` raise `_compile_error` | G2 | application strict |
| **C** | 未来 raw pred_id 入口(若 Step 2+ 引入)| `pred_id.startswith("__system__.")` raise `SDKStoreError` | G1 | SDK shell strict(forward-looking)|
| **D** | `fg.fields.*` | **N/A** — derive 安全;Field descriptor 来自 schema(已 Layer A+B G2 reject)| — | 自动安全 |
| **E** | `WireBatchPlan` apply 路径(`sdk/batch.py`)| **transitively** — wire raw pred_id 通过 schema pred_index 校验,Layer A+B G2 reject 后 pred_index 不含 `__system__:*` → binding validation 自然 reject | G2(transitive)| schema-bound;无独立 reject |

**跟 meta-ADR §4.4 4-layer enforcement 一致**:SDK shell + application 层 strict;protocol / ledger 层 delayed(per §3 Non-scope — internal emission path 走 ADR-SYS-B 决策)。

### 4.3 Cross-Q decision summary(单 Q,纯 lock)

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q5a-1 | **G1** raw pred_id guard(精确 `__system__.`)+ **G2** schema owner guard(精确 `__system__`)— 两 guard 独立 named 防不同 attack surface | 文档化 + Layer A/B 各 G2 error messages + Layer C G1 forward-looking 规约 docs | Slice 3a + Slice 4 docs |
| Q5a-2 | 5 layer reject:Layer A(SDK shell × entity+relationship 双路径,G2)+ Layer B(schema_compile × `_compile_entity`+`_compile_relationship` 双 defense,G2)+ Layer C(forward-looking raw pred_id 规约,G1)+ Layer D(自动安全)+ Layer E(WireBatchPlan transitively covered)| `sdk/store.py:_SDKSchemaManager`(ADR-API §4.5 新 manager)+ `authoring/schema_compile.py:_compile_entity` + `_compile_relationship` 对称 G2 check;`sdk/batch.py` 不动(transitive)| Slice 3a |

**整体**:Slice 3a 实施增量 ≈ 50-80 行代码(原 30-60 + relationship 路径):
- Layer A:3 个 method × 2 类 schema declaration = 抽 `_check_user_facing_owner_type` 通用 helper(同 G2 pattern apply 给 entity_type / relationship_type);3 个 method 各调用 helper × 2(entity + relationship)
- Layer B:`_compile_entity` + `_compile_relationship` 各 + 5 行 G2 prefix check(defense in depth)
- error message × 2(entity / relationship)+ docs(Slice 4 含 Layer E classification 防 reviewer 误解)

### 4.4 Cross-ADR 不冲突 confirmation(per user reviewer §1.3 第 4 项)

#### 4.4.1 跟 ADR-API §4.1 三层入口 不冲突

- Layer 1 `fg.entities.create(EntityClass, **identity)`:依赖 `EntityClass` 必须已通过 `fg.schema.register/extend/apply`(per ADR-API §4.5);若 EntityClass.entity_type 以 `__system__` 开头,schema 阶段已 reject — Layer 1 不会看到 system entity
- Layer 2 `fg.fields.*`:输入 Field descriptor 来自 schema-declared,自动安全(per §4.2.4)
- Layer 3 `fg.assertions.retract(asrt_id)`:asrt_id-based,不涉及 pred_id 命名;**read** path filter 是 ADR-SYS-B INV-15 范畴,不在本 ADR
- **结论**:三层入口 + 本 ADR `__system__.*` reject **互不冲突** — 本 ADR 把 reject 责任 dispatch 到 schema 入口(Layer A)与 schema_compile(Layer B),三层运行时入口无需独立 enforce

#### 4.4.2 跟 ADR-IC §4.3.1 `protected_anchor_pred_ids` cache 不冲突

- ADR-IC §4.3.1 `_identity_pred_ids` ∪ `_exists_pred_ids` cache 来自 schema_ir 的 `is_identity_field == True` + `is_entity_exists == True` filter
- 本 ADR §4.2 Layer A + B G2 reject 保证 entity_type / relationship_type 不以 `__system__` 开头 → schema_ir 中不会出现 **schema-derived system-owner predicates**(冒号形式如 `__system__x:exists` / `__system__x:<field>` / `__system__y:<rel_field>`)→ ADR-IC cache **自然不含** 任何 schema-derived `__system__:*` entries
- 反向也成立:**future internal `__system__.*` claims**(点形式如 `__system__.revokes`)由 ADR-SYS-B 锁定的 internal emission path 产生(per Q5b),**不**经 schema_ir 的 `is_identity_field` / `is_entity_exists` flag → ADR-IC cache 自然不收;这类 system claims 是 SYS-B-owned emission concern,本 ADR scope 外
- **结论**:两类 namespace **概念正交**;两类形态(G2 防的 schema-derived 冒号形式 + G1 防的 future raw 点形式)cache 跟 reservation 互不依赖、互不污染

#### 4.4.3 跟 ADR-FI Identity / Field descriptor 不冲突

- ADR-FI §4.3 / §4.3-bis Identity / Field descriptor signature(`description` / `pattern`)跟 pred_id 命名空间正交 — descriptor signature 不涉及 pred_id 拼接
- 本 ADR reject 是 entity_type / pred_id 字符串 prefix check,跟 descriptor 内部字段无关
- **结论**:descriptor surface(ADR-FI)+ namespace reservation(本 ADR)正交独立

## 5. Rejected Alternatives

### 5.1 Q5a 单 Q rejected options

#### Q5a alternative — 仅在 protocol 层 `set_field` reject,不在 SDK shell + application 层

- **Why rejected**:跟 meta-ADR §4.4 4-layer enforcement 模式不一致(meta-ADR 锁 SDK shell + application strict;protocol delayed);protocol 层 reject 让 user 等到运行时才看到 error,反馈环慢;此外 protocol 层 schema-agnostic,加 namespace 字符串 check 会让 protocol 层 leak schema 知识

#### Q5a alternative — 仅在 SDK shell(Layer A)reject,不在 schema_compile(Layer B)defense in depth

- **Why rejected**:caller 直接调 `compile_schema(spec_dict)` 路径(bypass SDK shell)— 如 internal migration tool / test fixture / future programmatic schema construction — 仍然需要 enforce;defense in depth 是 marginal 5 行 cost,但防止后续 schema_compile-only call site 产生 `__system__.*` predicates 污染 ledger

#### Q5a alternative — Fuzzy match(reject `__sys__` / `__system_` / `_system_` 等近似变种)

- **Why rejected**:fuzzy match 边界永远画不清(`__sys_v2__`?`system__`?`__sys__system__`?);用户若刻意命名近似形式自行承担歧义责任;**精确 pattern**(G1 `__system__.` exact + G2 `__system__` exact prefix)语义清晰,Layer A error message 给出明确推荐(用 `MyEntity` 代替 `__system__MyEntity`);跟 design-point ledger-spec §4.7 INV-10 一致

#### Q5a alternative — 单 guard(只 G1 raw pred_id guard,不要 G2 schema owner guard)

- **Why rejected**:G1 是 `pred_id.startswith("__system__.")` 精确含点;但 schema-derived predicates 用 **冒号** separator(`__system__x:exists`)— **catch 不到**;user 可 `entity_type = "__system__X"` 走 schema 路径产 `__system__x:*` predicates 污染 ledger,完全绕过 G1。**必须**双 guard,各管 1 类 attack surface(per §4.1.3 表格)。

#### Q5a alternative — 单 guard(只 G2 schema owner guard,不要 G1 raw pred_id guard)

- **Why rejected**:G2 是 `owner_type.startswith("__system__")` schema 路径校验;但未来若引入 `fg.assertions.write(pred_id="__system__.X", ...)` raw pred_id 入口(per §4.2.3 Layer C),pred_id 没有 owner_type 可校验,G2 **覆盖不到** → user 直接写 `__system__.X` 进 ledger。必须双 guard 覆盖两类 surface(per §4.1.3 表格)。

#### Q5a alternative — Skip relationship schema 路径(只 cover entity_type,不 cover relationship_type)

- **Why rejected**:shipped `sdk/schema.py:248-...` `Relationship` descriptor 是 public surface;`authoring/schema_compile.py:175-182` `_compile_relationship` 接受 `relationship_type` 并 `_owner_prefix(...)` 产 relationship-prefixed pred_id;**不**加 reject = user 可 `class MyRel(Relationship): relationship_type = "__system__X"` 产 `__system__x:field` 落地 ledger,违反 INV-10;违反 §1.3 user reviewer 第 2 项("拒绝点覆盖 ... schema/register/extend/apply 中能声明 pred_id 的路径")。entity + relationship 是 schema declaration 的对称双路径,必须对称 covered。

#### Q5a alternative — `WireBatchPlan` raw pred_id 入口加独立 reject 路径

- **Why rejected**:Layer E `WireBatchPlan` 是 **schema-bound wire-replay path**(per §4.2.5)— apply 时 `_resolve_wire_field_for_write_op`(`sdk/batch.py:877-...`)强制要求 raw pred_id 在 `pred_index`(schema pred index)存在 + owner_type/field_name 跟 schema 严格匹配;Layer A + B G2 reject 后 pred_index 不含 `__system__:*` → wire-replay 自然 reject(binding validation failure)。独立加 reject 是 redundant work;**transitive coverage 已充分**;ADR §4.2.5 显式 classify 防 reviewer 误判遗漏。

#### Q5a alternative — 锁 `__system__.revokes` payload shape 在 SYS-A 同 ADR

- **Why rejected**:**违反 user reviewer §1.3 第 1+3 项 directional guidance**("只锁 user-facing pred_id reservation,不锁 revokes payload" + "Internal/system emission exception 留给 ADR-SYS-B");此外 revokes payload + emission exception 涉及 ledger migration(per Q15)+ INV-11/12/13/15 整套 — 跟 user-facing reservation 是不同 concern,cluster 一起 ship 但 ADR 分开锁(per meta-ADR §4.2 grouping)

#### Q5a alternative — 同 ADR 锁 INV-15 read path default filter(`pred_id NOT LIKE '__system__.%'`)

- **Why rejected**:read path filter 时序上 **仅 after system claim emission 存在才必要** — 当前 shipped 无 system claim(per §1.4 baseline)→ INV-15 filter vacuously 满足;emission path 由 ADR-SYS-B 锁,filter 跟 emission 时序耦合;本 ADR 锁 filter 会强行 force ADR-SYS-B 同时 ship,违反 cluster sub-ADR 解耦原则

#### Q5a alternative — 多 reserved prefix 一起锁(`__system__` + `__internal__` + `__admin__` ...)

- **Why rejected**:scope creep — 未来 reserved prefix 是 Step 2+ design 问题(可能涉及多 tenant / multi-environment / capability 分级);Step 1 only `__system__` 已覆盖 INV-10/11/12/13/14/15 整套 invariant 的 namespace 需求;额外 prefix 留 future ADR

### 5.2 Cross-Q rejected combinations(本 ADR 单 Q,无 cross-Q)

N/A — 本 ADR 仅 Q5a 单 Q;cross-Q 组合不适用。**注**:跟 Q5b / Q15(ADR-SYS-B)的 cross-ADR 组合在 ADR-SYS-B 内 reject 与否(如 "把 Q5a + Q5b + Q15 全合并成单 ADR")已在 meta-ADR §4.2 grouping decision 锁。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q5a row(`audit:518`)
- audit §6 INV-10 row(`audit:284`)— `__system__.*` namespace classification (f) target-gap + shipped baseline zero hits
- audit §5.3 A19 row — System namespace cluster source(跟 Q5a/Q5b 同 cluster)
- audit §5.4 N6 row — `_write_session` atomic context(per §4.2 reject 在 transaction 外 fail-fast,不影响 atomic 保证)

### 6.2 Shipped code citations

**Entity 路径**(§4.2 Layer A.1 + Layer B.1):
- `src/factgraph/authoring/schema_compile.py:79-83` `entity_type` 字符串校验当前(将加 §4.2 Layer B.1 G2 prefix check)
- `src/factgraph/authoring/schema_compile.py:142` `f"{entity_type}:exists"` 拼接路径
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` 产 pred_id 路径
- `src/factgraph/sdk/schema.py` Entity descriptor public surface

**Relationship 路径**(§4.2 Layer A.2 + Layer B.2 — P1 amendment new coverage):
- `src/factgraph/authoring/schema_compile.py:175-182` `_compile_relationship` 接受 `relationship_type` 当前(将加 §4.2 Layer B.2 G2 prefix check)
- `src/factgraph/authoring/schema_compile.py:210` `_owner_prefix(relationship_type)` 产生 relationship_prefix
- `src/factgraph/authoring/schema_compile.py:460-478` `_compile_relationship_pred_id` 产 `f"{relationship_prefix}:{local}"` pred_id
- `src/factgraph/sdk/schema.py:248-...` `Relationship` / `RelationshipMeta` descriptor public surface

**Wire-replay 路径**(§4.2 Layer E — transitive G2 coverage):
- `src/factgraph/sdk/batch.py:540-...` `_parse_wire_write_op` 从 JSON 解析 raw pred_id
- `src/factgraph/sdk/batch.py:877-...` `_resolve_wire_field_for_write_op` 通过 `pred_index` schema 校验 + reject ambiguous/unknown/mismatch

**Protocol 层 + manager**(meta-ADR §4.4 delayed;本 ADR 不动):
- `src/factgraph/core/evidence/write_protocol.py:231-249` `_validate_write_inputs` 当前仅类型 check(不含 namespace check — per meta-ADR §4.4 protocol 层 delayed)
- `src/factgraph/sdk/store.py:518` `_SDKSchemaManager.add(*classes)` 当前混杂 register/extend(将被 ADR-API §4.5 拆三 + §4.2 Layer A.1/A.2 hook 集成)

**Greenfield confirmation**:shipped **zero hits** for `__system__` confirmed per audit §6 row 284(`sdk/store.py` / `sdk/facade.py` / `sdk/schema.py` / `sdk/batch.py` / `authoring/` / `core/` 全部 grep 无命中)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-SYS-A grouping(Q5a 单独 ADR;Q5b/Q15 → ADR-SYS-B)— justifies §3 Non-scope 拒绝 emission path
- meta-ADR §4.4 4-layer enforcement(SDK shell + application strict)— justifies §4.2 Layer A + B strict;Layer C forward-looking;Layer D 自动安全
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency — 本 ADR §6.5 显式 confirm

### 6.4 Design-point citations

- `workflow/design/design-points/active/ledger-schema-specification.zh.md` §4.7 INV-10(`:290-300`)— `__system__.*` namespace reservation source
- ledger-spec §3.1 命名空间边界表(`:149-151`)— `__system__.*` 顶级 system namespace + INV-10 reject + INV-15 default filter classification
- ledger-spec §4.7 "适用范围:`fg.write.set` / `fg.write.add` / `fg.schema.ingest` / application 层写入门面"(`:294`)— Layer A / B enforcement positions
- ledger-spec §4.7 "internal API(如 `retract_by_asrt`)走分离路径绕开 namespace check"(`:294`)— 本 ADR §3 Non-scope internal emission exception 留 ADR-SYS-B 的 design-point rationale
- ledger-spec §4.7 / §4.12 `<EntityType>:exists` 跟 `__system__.*` 边界区分(`:296-298` / `:355`)— §4.4.2 cache compat confirm 的 design-point 依据
- identity-mechanism-redesign §12.2 line 974 — "Step 1 不引入 `fg.assertions.write` 这类绕开 schema 的写入路径" — §4.2.3 Layer C 不锁是否引入的 design-point 依据

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / adapter rewrite — confirmed Step 1 zero-blocker 合规。

**澄清**:§4.2.3 Layer C 提到 "Step 2+ 引入" — 那是**前向 carve-out**(本 ADR 不锁是否引入,只锁 **若**引入 必须含 reject),**不是 dependency**。Slice 3a 实施可在 Step 2+ 假设之前完成,不会被 block。

### 6.6 ADR-API + ADR-IC + ADR-FI 兼容性 confirmation(per §4.4)

- **ADR-API**(`66434490`):§4.1 三层入口 + §4.5 schema 三分 不冲突 — 本 ADR §4.4.1 详 confirm
- **ADR-IC**(`2d0866ed`):§4.3.1 `protected_anchor_pred_ids` cache 概念正交 — 本 ADR §4.4.2 详 confirm
- **ADR-FI**(`b288ea9e`):descriptor signature 正交 namespace — 本 ADR §4.4.3 详 confirm

**关键观察**:三个前置 ADR 都跟本 ADR `__system__.*` namespace reservation **正交**(各自管不同的 concern:ADR-API 管 namespace 层级 / ADR-IC 管 Identity Claim 保护 / ADR-FI 管 descriptor signature);本 ADR 是 system namespace 边界的独立 dimension,不污染、不被污染。

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **ADR-SYS-B**(Q5b/Q15 — `__system__.revokes` emission + ledger migration)可起草 — `__system__.*` namespace 在本 ADR 已锁,ADR-SYS-B 可基于此设计 internal emission path(`retract_by_asrt` lowering / internal writer API / 等)without ambiguity
- **Slice 3a implementation** Layer A 集成:`_SDKSchemaManager.register/extend/apply`(per ADR-API §4.5)+ `_check_user_facing_entity_type` helper
- **Slice 3a implementation** Layer B 集成:`schema_compile.py:_compile_entity` defense in depth
- **ADR-INV9 / ADR-IE / ADR-DOCS** 可独立起草 — 跟本 ADR 无 Q dependency

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| ADR-SYS-B draft(`__system__.revokes` emission + ledger migration Q5b/Q15)| TBD | ADR-SYS-A adopt 后 |
| Slice 3a implementation:Layer A.1 + A.2 reject 集成(`_SDKSchemaManager.register/extend/apply` per ADR-API §4.5;`_check_user_facing_owner_type` helper apply 给 entity_type + relationship_type)| Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 3a implementation:Layer B.1 + B.2 reject 集成(`schema_compile.py:_compile_entity` + `_compile_relationship` 对称 G2 defense in depth)| Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 3a pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `__system__` 字符串 — confirm zero hits(per audit §6 baseline)+ 加 contract test 覆盖 entity / relationship 两路径 + Layer E transitive coverage | Slice 3a blueprint preflight(Step 4.6.5)| Slice 3a blueprint scoped 后 |
| docs sync(Slice 4)— `04_api_surface.en.md` 加 G1 + G2 两 guard 说明 + Layer A/B/C 各自 reject 描述 + Layer E `WireBatchPlan` "schema-bound binding-validated" classification(防 reviewer 误以为漏 raw pred_id surface);`identity-mechanism-redesign §10` 跟 ADR-SYS-A 对齐 | Slice 4 docs sync | Slice 3a 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-SYS-B 起草时 Header `Depends on:` 引用本 ADR(emission path 设计基于本 ADR namespace lock)
- **Blueprint pillar**:Slice 3a blueprint preflight(Step 4.3)必须 re-read 本 ADR §4.2 — Layer A 跟 ADR-API §4.5 register/extend/apply 同 codebase area,**两个 ADR 同 Slice 3a 落地**
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q5a 行 status 仍是 "待 ADR 决策" — 实际 ADR-SYS-A 已 lock;**不**触发 audit doc post-stage sync(跟 ADR-FI / ADR-IC / ADR-API 相同处理)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3a blueprint 不可单方面 override Q5a 决策;若需要 override,走"本 ADR superseded by 新 ADR-SYS-A-v2"路径
- §4.1 G1 + G2 双 guard:carry-forward — 两 guard pattern 不可改(G1 `__system__.` 精确含点 / G2 `__system__` 精确不含点);**不可合并成单 guard**(per §5.1 alt rejected 两次,G1-only / G2-only 都漏一类 attack surface);近似变种 reject 不可加(per §5.1 fuzzy match alt rejected)
- §4.2 5 layer reject 路径:carry-forward — Layer A.1+A.2(entity + relationship 对称)/ B.1+B.2(schema_compile entity + relationship 对称 defense)strict 不可降级;Layer C forward-looking 规约 carry-forward 到任何未来引入 raw pred_id 入口的 ADR(必须含 G1 reject);Layer D 自动安全 derive 不可改成 independent enforcement(违反 ADR-API §4.1 排他原则);Layer E `WireBatchPlan` transitive coverage 依赖 schema pred_index 绑定校验,**ADR-SYS-B 或 Step 2+ 不可弱化 wire-replay 路径的 binding validation**(否则 Layer E transitive coverage 失效,需补 wire 层 reject)
- 跟 ADR-SYS-B 的 explicit contract:**本 ADR §3 Non-scope 列出的 emission exception / payload / INV-11/13/15 / migration 全由 ADR-SYS-B 锁**;ADR-SYS-B 不可在本 ADR `__system__` namespace 之外引入新 system prefix(若需要新 prefix,走本 ADR superseded 路径)
- 跟未来 schema declaration 扩展的 explicit contract:任何**未来**新增的 schema declaration surface(若 Step 2+ 引入新 owner-type 概念如 view-type / aggregate-type / etc.)**必须**继承 G2 enforcement,在 Layer A + B 加对称 prefix check

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.2 Q5a 全部含 Decision + rationale
- [x] §4.1 显式拆 G1 raw pred_id guard + G2 schema owner guard 两 named guard + §4.1.3 表格论证不可合并成单 guard
- [x] §5 含 per-Q rejected alternatives(≥8 项 含 G1-only / G2-only / Skip-relationship / Wire-replay 等)+ cross-Q N/A 说明
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / ADR-API+ADR-IC+ADR-FI 兼容性 6 类 evidence
- [x] §6.2 shipped citation 含 entity 路径 + relationship 路径(`_compile_relationship` + `Relationship` descriptor)+ wire-replay 路径(`sdk/batch.py` `_parse_wire_write_op` + `_resolve_wire_field_for_write_op`)
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR + ADR-FI + ADR-IC + ADR-API adopted commits
- [x] §1.4 含 shipped baseline pointer + greenfield(zero `__system__` hits)confirmation
- [x] §3 显式 enumerate 不锁的 7 项(per user reviewer §1.3 第 1+3 项 directional guidance)
- [x] §4.4 显式 confirm 跟 ADR-API 三层入口 / ADR-IC `protected_anchor_pred_ids` cache / ADR-FI descriptor 三项正交不冲突(per user reviewer §1.3 第 4 项)
- [x] §4.2.5 Layer E `WireBatchPlan` 显式 classify 为 schema-bound binding-validated(transitive G2 covered)防 reviewer 误以为漏 raw pred_id surface
- [x] §1.3 含 user reviewer 4 项 directional guidance 每项落点

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 3a blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 3a implementation **entity 路径**:`fg.schema.register/extend/apply(SomeEntityCls with entity_type="__system__X")` 三 method 各 raise `SDKStoreError`(G2)含 migration hint(per §4.2.1.1 Layer A.1)
- [ ] Slice 3a implementation **relationship 路径**:`fg.schema.register/extend/apply(SomeRelCls with relationship_type="__system__Y")` 三 method 各 raise `SDKStoreError`(G2)含 migration hint(per §4.2.1.2 Layer A.2)
- [ ] Slice 3a implementation:bypass SDK shell 直接调 `compile_schema(spec_dict_with_system_entity_type)` raise `_compile_error`(per §4.2.2 Layer B.1 defense in depth)
- [ ] Slice 3a implementation:bypass SDK shell 直接调 `compile_schema(spec_dict_with_system_relationship_type)` raise `_compile_error`(per §4.2.2 Layer B.2 defense in depth)
- [ ] Slice 3a implementation:`entity_type="__system__"` / `relationship_type="__system__"` 自身(无后缀)同样被 G2 reject — Layer A 入口侧 catch
- [ ] Slice 3a implementation:`entity_type="__sys__"` / `"__system_"` / `"_system_"` 等**近似变种** **不**被 reject(per §4.1.4 精确 pattern 不做 fuzzy);user 若使用承担歧义责任
- [ ] Slice 3a implementation:`fg.entities.create(EntityWithSystemName, **id)` 不会执行到 — schema 阶段已 reject(per §4.4.1 cross-ADR 不冲突)
- [ ] Slice 3a implementation:`fg.fields.set/add/retract/delete(Field, e_ref, value)` 无独立 namespace reject 路径(per §4.2.4 Layer D 自动安全)
- [ ] Slice 3a implementation:`WireBatchPlan` 解析阶段 **不**对 raw pred_id 加独立 namespace reject;apply 时 `_resolve_wire_field_for_write_op` 通过 schema pred_index `pred_index.get(...) is None` reject(per §4.2.5 Layer E transitive coverage — schema pred_index 不含 `__system__:*` 后自然 reject)
- [ ] Slice 3a implementation:ADR-IC `_identity_pred_ids` / `_exists_pred_ids` cache 不含 `__system__:*` entries(自然分离 per §4.4.2)
- [ ] Slice 3a implementation:contract test 覆盖 Layer A.1+A.2 + B.1+B.2 reject 路径的 error message 含 ADR-SYS-A §4.1 reference + G1/G2 guard 名 + user-facing recommendation
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 加 G1 + G2 两 guard 说明 + Layer C forward-looking 规约 + Layer E classification;`identity-mechanism-redesign §10 / §13` 跟 ADR-SYS-A 对齐;`ledger-schema-specification §4.7` 不需改(本 ADR 直接 cite design-point 形态)

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-SYS-A drafted | 1 Q(Q5a `__system__.*` user-facing namespace reservation;**仅锁 reservation**,不锁 emission / payload / INV-11/13/15 / migration — 全留 ADR-SYS-B per user reviewer §1.3 directional guidance)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-FI adopted @ `b288ea9e` + ADR-IC adopted @ `2d0866ed` + ADR-API adopted @ `66434490` + user reviewer 2026-05-29 ADR-SYS-A 4 项 directional review focus + ledger-spec §4.7 INV-10 design-point。Branch: `v0.2.0-q-sys-a-system-namespace-decision-2026-05-29`。Commit: `def20c74` |
| 2026-05-29 | proposed | ADR-SYS-A amended(P1/P2 fixes,still proposed)| User reviewer post-draft review(同日)返回 3 findings:**(P1)** Relationship schema path 未覆盖 coverage gap — shipped `_compile_relationship` 接受 `relationship_type` + public `Relationship` descriptor + 产 `f"{relationship_prefix}:{local}"` pred_id;原 §4.2 只 cover `EntityClass.entity_type` → user 可 `class MyRel(Relationship): relationship_type = "__system__X"` 走 schema 路径产 `__system__x:field` 污染 ledger。**(P2)** "exact `__system__.` prefix" 跟 "`entity_type.startswith("__system__")`(无点)" 是两个不同 rule 但 §4.1 混在一起 — 应拆成两条命名清楚的 guard。**(Non-blocking)** `WireBatchPlan` raw pred_id 入口分类。**重构方案**:§4.1 完整重写引入 **G1 raw pred_id guard**(精确 `__system__.` 含点)+ **G2 schema owner guard**(精确 `__system__` 不含点,覆盖 entity_type / relationship_type / 任何未来 owner-type 概念);§4.1.3 加 G1-only / G2-only / G1+G2 对比表论证不可合并;§4.1.4 pattern 精确性 rules。§4.2 layer 从 4 扩到 5:Layer A.1+A.2(entity + relationship 对称 G2)/ B.1+B.2(schema_compile entity + relationship 对称 G2 defense)/ C(forward-looking G1)/ D(自动安全)/ E(新增 — `WireBatchPlan` schema-bound binding-validated transitive G2 covered;`sdk/batch.py` 不动)。同步 cascade:§2 Scope 表 reflect 5 layer / §4.3 cross-Q summary 重写 / §5.1 加 4 项 alternative reject(单 guard × 2 + Skip relationship + Wire-replay 独立 reject)/ §6.2 shipped citation 扩 relationship 路径 + wire-replay 路径 / §7.2 follow-up 加 relationship + Layer E grep 任务 / §7.4 no-retroactive boundary 扩 双 guard + 5 layer + 未来 owner-type 概念 G2 inherit / §8 Acceptance Criteria 重写(11 项 proposed-stage ✓ + 12 项 post-adoption ☐ 含 entity+relationship 对称 verify + Layer E transitive verify)。Commit: `ed36f2ec` |
| 2026-05-29 | proposed | ADR-SYS-A re-amended(P2/P3 second-round fixes,still proposed)| User reviewer 第 2 轮 review 结论:基本闭环但 P2 substantive + P3 wording。**(P2)** §4.2.1 Layer A pseudo-code 用 `getattr(cls, "entity_type", None) or cls.__name__` 误导 — shipped `EntityMeta` / `RelationshipMeta` 把 owner_type 写进 `__sdk_entity_spec__` / `__sdk_relationship_spec__` dict,通过 `sdk_entity_spec()` / `sdk_relationship_spec()` classmethod 暴露(per `sdk/schema.py:241-245` + `:286-307`);class 不保证有 public `entity_type` / `relationship_type` class attribute,也不应用 `__name__` fallback(可能跟 spec 中的 owner_type 不同)。**重构 §4.2.1**:加 §4.2.1.0 "Owner type 提取 contract" — 显式锁 implementation MUST extract from SDK schema spec,not class attr;§4.2.1.1 改为 `_check_user_facing_owner_type(owner_type, kind)` 共用 G2 helper;§4.2.1.2 + §4.2.1.3 改为分别用 `EntityCls.sdk_entity_spec()["entity_type"]` + `RelCls.sdk_relationship_spec()["relationship_type"]` 提取后调 G2 helper。**(P3)** §4.4.2 cache 不冲突 wording — 原 "schema_ir 中不会出现 `__system__.*` pred_id" 措辞不精确;G2 实际防的是 schema-derived 冒号形式(`__system__x:*`);future internal `__system__.*` claims(点形式)由 SYS-B 锁的 emission path 产生,本 ADR scope 外。重写区分 G2 schema-derived 冒号形式 + future raw 点形式 + SYS-B owned emission。 |
| 2026-05-29 | **adopted** | User reviewer 第 2 轮 review 通过 → adopt | 第 2 轮 review 结论:可在修掉 P2 后 adopt;P3 顺手修不阻断。两项已采纳:**§4.2.1 owner-type 提取契约**(extract from SDK schema spec,not class attr)+ **§4.4.2 cache compat wording** 区分 G2 schema-derived 冒号形式 vs future raw 点形式 SYS-B-owned。本 ADR 现 binding constraint;ADR-SYS-B 起草(Q5b/Q15 emission + ledger migration)Header `Depends on:` 须引用本 ADR adopt commit;Slice 3a implementation 实施 Layer A.1/A.2 + B.1/B.2 + Layer E transitive coverage;blueprints / 后续 ADR 不可单方面 override §4.1 双 guard(G1/G2 不可合并)+ §4.2 5 layer reject + §4.2.1 owner-type 提取契约;Slice 5+ / SYS-B 不可弱化 wire-replay binding validation(否则 Layer E transitive 失效)。override 需走"superseded by ADR-SYS-A-v2"路径。Commit: TBD post-stage |
