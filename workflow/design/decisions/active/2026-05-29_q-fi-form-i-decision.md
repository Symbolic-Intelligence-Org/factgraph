# Q-FI Decision: Form I cluster — `_DataMember` exposure + cardinality inference + Layer 4 validation + mutable Field contract

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Slice 1 Form I schema refactor 的 4 个 sub-decisions(Q6/Q7/Q8/Q9 per meta-ADR §4.2 grouping)before Slice 1 blueprint 起草。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q6/Q7/Q8/Q9 rows + §5.2.1 A5 + §5.2.2 A6-A10 + §5.4 N2(Identity field 已 declared in schema_ir)
  - User reviewer 2026-05-29 ADR-FI directional guidance(Q6 docs-only / Q7 internal `_DataMember` / Q8 alpha breaking + migration notes / Q9 dual-layer compile+write validation)
  - Identity-mechanism-redesign design-point §8 Form I + §8.4 类型推断 + §8.5 `_DataMember` 共通基类
- Outputs / Downstream:
  - Slice 1 Form I refactor blueprint(`workflow/blueprints/active/2026-05-29_slice-1-form-i.md` 起草前置)
  - 后续 ADR-IC(Identity-as-Claim core)依赖本 ADR 的 Identity / Field 二分 + `_DataMember` 稳定 baseline
- Related:
  - Peer ADRs(待启动 Stage 2):ADR-IC / ADR-API / ADR-INV9 / ADR-SYS-A / ADR-SYS-B / ADR-IE / ADR-DOCS
- Branch: `v0.2.0-q-fi-form-i-decision-2026-05-29`
- Depends on: `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping locks Q6-Q9 同 ADR + §4.4 Step 1 zero-Q-PR1 dependency)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced Q list

本 ADR 锁定 audit doc §7.3 Q list 中的 Q6/Q7/Q8/Q9 — 全部 Slice 1 / Form I cluster:

| Q | Title | Audit §7.3 row | Cluster |
|---|---|---|---|
| Q6 | Boundary rule: mutable Field 设计 contract | `audit:519` | Form I |
| Q7 | `_DataMember` 共通基类 public API exposure | `audit:520` | Form I |
| Q8 | Cardinality 推断 backward-compat strategy | `audit:521` | Form I |
| Q9 | Layer 4 enum/pattern validation layer | `audit:522` | Form I |

### 1.2 Meta-ADR locked constraints relevant to Form I

- **§4.2 grouping**:Q6/Q7/Q8/Q9 必须**同一 ADR**(本 ADR);拆分会 force "_DataMember 暴露 + cardinality 推断 + Literal/pattern enforcement layer" 跨 4 个 ADR 反复协调
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR §1 Inputs / §6 Supporting Evidence **不**引用 Q-PR1 / Slice 5+ adapter rewrite — confirmed,本 ADR 与 PyReason adapter 无关

### 1.3 User reviewer 2026-05-29 directional guidance

ADR-FI draft 启动前 user reviewer 给出 4 条方向:

| Q | User guidance | 影响本 ADR |
|---|---|---|
| Q6 | "不要引入 `volatile=False` 这类额外 surface,除非它确实有 runtime 行为;否则只作为 Field mutable contract 文档化" | §4.1 Decision = documentation-only |
| Q7 | "`_DataMember` 更适合作为 internal/shared base,不建议变成用户显式导入的 public descriptor" | §4.2 Decision = internal-only |
| Q8 | "alpha 阶段可以 breaking,但 ADR 里要明确迁移提示和旧 `cardinality=` 的处置" | §4.3 Decision = alpha breaking + migration notes |
| Q9 | "pattern/Literal 最好 compile-time + write-time 都覆盖:schema 声明早失败,写入值再校验,避免绕过 SDK 时产生脏 Claim" | §4.4 Decision = dual-layer validation |

### 1.4 Shipped baseline(audit §5.4 N2)

- `authoring/schema_compile.py:152-159` Identity field 已 declared in schema_ir(`is_identity_field: True` flag + pred_id 已生成)
- `sdk/schema.py:50-141` Identity / Field 已物理分两类 descriptor
- `sdk/schema.py:91-122` Field `cardinality: str` 必填 kwarg(将被 §4.3 替换)
- `sdk/__init__.py:62-123` shipped `__all__` 含 `Identity` / `Field` / `Entity` / `Relationship`,**不含 `_DataMember`**(本 ADR §4.2 维持)

## 2. Scope

本 ADR **锁**以下 4 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q6** | Mutable Field contract 形态(documentation-only,无新 kwarg / 无 runtime enforce) |
| **§4.2 Q7** | `_DataMember` 共通基类 exposure level(internal/shared base,not public API) |
| **§4.3 Q8** | Cardinality 推断 migration strategy(alpha breaking,kwarg 删除,migration hints + error messaging) |
| **§4.4 Q9** | Layer 4 enum + pattern validation layer 分布(dual-layer:compile-time + write-time) |

## 3. Non-scope

本 ADR **不**锁:

| 不锁 | 留给谁 |
|---|---|
| `_DataMember` 扩展位(`validators` / `constraints` / `alias` / `deprecated` / `examples`)的具体实施 | Step 2+ extension ADR / Slice 1+ |
| `InternalIdentity` / `Fingerprint` / `ContentHash` 等 Step 2+ Identity 子类型设计 | Step 2+ Identity extensions ADR |
| Identity 字段值是否产 Claim(emission layer) | ADR-IC(Q2) |
| `fg.schema.register / extend / apply` 三分 + schema evolution 约束 | ADR-API(Q14)+ ADR-IC(Q3 schema-evolution hook) |
| `_meta` 统一 meta 输入 + AssertionView 招纳原则 | ADR-API(Q11/Q12/Q13) |
| Form I 落地的 blueprint slicing(具体 commits / impl 顺序) | Slice 1 blueprint |

## 4. Decision

### 4.1 Q6 — Mutable Field contract:**documentation-only**

**锁定**:Field 的 mutable 语义**仅作为文档约束**,**不**引入 `volatile=False` / `mutable=True` / 等类似显式 kwarg。

Field 的 mutability 已**隐式由 API 形态保证**:
- `fg.fields.set` / `fg.fields.add` / `fg.fields.retract` / `fg.fields.delete` 接受 Field descriptor + e_ref + value(可写)
- `IdentityEditor.set/add/retract` raise SDKStoreError(Identity 不可写;`sdk/facade.py:448-479` 已 shipped)
- Identity vs Field 物理上分 descriptor class,不需要在 Field 上加 `volatile=False` 反向声明

**文档化责任**(Slice 1 / Slice 4 docs sync):
- `identity-mechanism-redesign.zh.md` §4.1 边界规则 / §8 Form I 章节明确"未来可能变的值不要建模为 Identity,建模为 Field"
- `sdk/docs/04_api_surface.en.md` Form I 介绍处加 "Field is mutable;Identity is immutable" 的 schema design guideline 句子
- 不进 descriptor signature

**为什么不加 runtime `volatile=False` enforcement**:
- 若 `Field(volatile=False)` 加 runtime check disallow set/add,该 Field 就跟 Identity 等价 — 但 Identity 已有专门 descriptor,重复
- 若不加 runtime check,kwarg 是纯 documentation noise — 跟纯文档化等价但 surface 多一项

### 4.2 Q7 — `_DataMember` exposure:**internal/shared base**

**锁定**:`_DataMember` 是 **internal/shared base**;**不**列入 `factgraph.sdk.__all__`;**不**在 public docs 中作为可 import descriptor 介绍。

**实现位置**:`src/factgraph/sdk/schema.py` 加 `_DataMember(_DeclaredMember)` 共通基类(`_DeclaredMember` 已 shipped 承载 descriptor 协议)。`_DataMember` 承载共通数据语义参数:

```python
# src/factgraph/sdk/schema.py(Step 1 Slice 1 新增)
class _DataMember(_DeclaredMember):
    """Internal shared base for Identity / Field descriptors.

    Not public API. Users use Identity / Field directly.
    Future descriptor types (InternalIdentity, Fingerprint, etc.) extend
    _DataMember internally — they are introduced as separate public
    descriptors when shipped, not via user-subclassing of _DataMember.
    """

    def __init__(
        self,
        *,
        description: str | None = None,
        pattern: str | None = None,
    ) -> None:
        super().__init__()
        self.description = description
        self.pattern = pattern
```

`Identity` 与 `Field` 各自继承 `_DataMember`,共享 `description` + `pattern` 参数。

**为什么不暴露为 public**:
- `_DataMember` 是 implementation seam — 给 Identity / Field 共享参数,不是 user-facing extension point
- 若用户需要 custom descriptor(如 Step 2+ `InternalIdentity` / `Fingerprint`),由 framework 显式提供 public descriptor,而不是让用户 subclass `_DataMember` "自助创造"
- 用户自定义 descriptor 走 subclass 会绕开 schema_compile 路径的 validation(`is_identity_field` / `is_entity_exists` flag 等是 internal contract);保留 internal `_DataMember` 强制 user-facing path 走 Identity / Field

**扩展位**(`validators` / `constraints` / `alias` / `deprecated` / `examples`):
- Step 1 不引入(本 ADR 不锁;Non-scope)
- 引入时**也作为 internal `_DataMember` 字段** + 在 Identity / Field 的 public kwarg 中**逐项暴露**
- 不会变成 "users can pass arbitrary `_DataMember` kwargs" 风格

### 4.3 Q8 — Cardinality 推断 migration:**alpha breaking + migration hints**

**锁定**:Form I 内 `Field()` **完全不接受** `cardinality` kwarg;cardinality **从类型注解推断**。旧 `Field(cardinality="single"|"multi")` 在 Form I 下 raise `SDKSchemaError`,error message 含明确 migration hint。

**类型推断规则**(per identity §8.4 类型推断表 + ADR-FI lock):

| 类型注解 | 推断 cardinality |
|---|---|
| `str` / `int` / `bool` / `bytes` / `float` / `UUID` / `datetime` | `single` |
| Entity subclass | `single`(entity_ref) |
| `list[T]` / `tuple[T, ...]` / `set[T]` / `frozenset[T]` | `multi` |
| `Literal[v1, v2, ...]` | `single` + enum constraint(per Q9) |
| `list[Literal[...]]` | `multi` + enum constraint(per Q9) |
| `Optional[T]` / `T \| None` | **拒绝** — unset = None 已表达 |
| `Union[A, B]` non-Literal | **拒绝** |
| `Literal[1, "a"]` mixed-type | **拒绝** |
| `dict[K, V]` | **Step 1 暂不支持**;延后 Step 2+ |

**Migration hints**(error message + docs):

```python
# Form I error path:
class Field(_DataMember):
    def __init__(self, *, description: str | None = None,
                 pattern: str | None = None, **legacy_kwargs: Any) -> None:
        if "cardinality" in legacy_kwargs:
            raise SDKSchemaError(
                "Form I removed Field(cardinality=...) kwarg. "
                "Cardinality is inferred from the field's type annotation:\n"
                "  - `T` (e.g., `str`, `int`)             → single\n"
                "  - `list[T]`, `tuple[T, ...]`, `set[T]` → multi\n"
                "Migration:\n"
                "  Old: name: str = Field(cardinality='single')\n"
                "  New: name: str = Field()\n"
                "  Old: tags: str = Field(cardinality='multi')\n"
                "  New: tags: list[str] = Field()"
            )
        # ... rest of __init__
        super().__init__(description=description, pattern=pattern)
```

**Slice 1 blueprint 必须做的**:
- Pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `Field(cardinality=` 的位置 — 全部 migrate 到类型推断形态
- shipped `sdk/schema.py:104-122` Field `__init__` 改 signature
- shipped `sdk/docs/04_api_surface.en.md` / `docs/official/kernel/quickstart/` 含 `Field(cardinality=)` 示例的 docs 全 sync(在 Slice 4 docs sync 时一并落)
- migration guide(Stage 4 blueprint §10 Outcome)记录 grep 结果 + migrate 数

**为什么不 backward-compat 双支持**:
- alpha 阶段无版本 / API 用户兼容性硬约束
- 双支持需要 if-branch 处理 + 类型推断结果 vs explicit kwarg 一致性 verification — 实施复杂度跟纯 breaking 不成比例
- user §17 lock-in "no alias" 立场

### 4.4 Q9 — Layer 4 enum + pattern validation:**dual-layer**

**锁定**:`Literal[...]` 枚举约束 + `pattern=r"..."` 正则约束**两层都做**:
- **Compile-time(`schema_compile.py`)**:schema 声明 declares-with-static-validation 阶段
- **Write-time(application layer + ledger write path)**:每次 `fg.fields.set` / `fg.fields.add` / `fg.entities.create` / `fg.assertions.write`(后者由 ADR-SYS-A 决策)在写 Claim 前 validate value

#### 4.4.1 Layer 1 — Compile-time validation(`schema_compile.py`)

新增 schema_ir 字段(per identity §8.4 enum 约束的 Layer 位):

```python
# schema_ir predicate dict (新增字段):
{
    "pred_id": "<EntityType>:<field_name>",
    "type_domain": "string",  # 或 int / bool / etc.
    "cardinality": "single" | "multi",
    "enum_values": ["a", "b", "c"] | None,  # 新增:Literal 提取
    "pattern": r"^...$" | None,             # 新增:pattern kwarg 透传
    # ... existing fields (is_identity_field, owner_type, etc.)
}
```

`schema_compile.py:_compile_field` + `_compile_identity_predicate` 处理:
- `Literal[v1, v2, ...]` 类型注解 → enum_values list(同 type 校验,混类型拒绝)
- `_DataMember.pattern` kwarg → regex syntax validation(`re.compile(pattern)` 不抛 error)+ 仅对 `str` type_domain 字段允许;其他 type_domain 上 raise `SDKSchemaError`

**validation 边界**:不验证 caller 还未写入的 value(那是 Layer 2 责任);只验证 schema declaration 本身合法。

#### 4.4.2 Layer 2 — Write-time validation(application layer)

新增 application-layer helper:

```python
# src/factgraph/application/value_validation.py(Step 1 Slice 1 新增)
def validate_field_value(
    pred_id: str,
    value: Any,
    *,
    schema_ir: dict[str, Any],
) -> None:
    """Validate value against pred_id's schema constraints.

    Called by application write path BEFORE ledger.append_assertion.
    Raises SDKValueError on validation failure.
    """
    pred_spec = _lookup_pred_spec(schema_ir, pred_id)

    enum_values = pred_spec.get("enum_values")
    if enum_values is not None and value not in enum_values:
        raise SDKValueError(
            f"value {value!r} not in enum {enum_values} for {pred_id}"
        )

    pattern = pred_spec.get("pattern")
    if pattern is not None:
        if not re.fullmatch(pattern, str(value)):
            raise SDKValueError(
                f"value {value!r} does not match pattern {pattern!r} "
                f"for {pred_id}"
            )
```

**调用点**:
- `fg.entities.create`(per ADR-IC Q2 emission layer 决策后)写 Identity Claim 前
- `fg.fields.set` / `fg.fields.add` 写 Field Claim 前
- `fg.assertions.write`(if introduced per ADR-SYS-A;否则 N/A — meta-ADR §4.4 4-layer enforcement 已锁 SDK shell + application layer 必须 enforce)

**调用边界**:**不**调用于 `evidence/write_protocol.py:set_field` 直接(那是 protocol 层,per meta-ADR §4.4 不加 strict 约束);**只**调用于 application 层 / SDK shell 层 write paths。这样跟 meta-ADR §4.4 INV-9 layered weak enforcement 模式一致。

#### 4.4.3 为什么 dual-layer 防"绕过 SDK 产生脏 Claim"

- 仅 compile-time:adapter / migration tool / 直接调 `evidence/write_protocol.set_field` 的路径绕开 SDK shell — value 不被 validate,可写入违反 enum / pattern 的 Claim
- 仅 write-time:schema 作者笔误(Literal 混类型 / pattern 不合法 regex)不在 declare 时被 catch,要写一次 Claim 后才报错 — 反馈环慢
- dual-layer:declare-time catch schema author errors;write-time catch caller errors;不重复(覆盖不同失败模式)

**性能权衡**:write-time validation 是 O(1) hash lookup(enum) + O(value length) regex match;Form I 范围内可接受。enum_values 适合用 `frozenset[str]` 优化 in-check;pattern 适合 cache `re.compile(pattern)` per pred_id。

### 4.5 Cross-Q decision summary

| Q | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q6 | docs-only | 0 code change(docs only at Slice 4)| Slice 1 + Slice 4 |
| Q7 | internal `_DataMember` | `sdk/schema.py` add `_DataMember` class;NOT in `__all__` | Slice 1 |
| Q8 | alpha breaking + migration hint | `sdk/schema.py` Field signature change;`schema_compile.py` cardinality 推断;error message migration hint | Slice 1 |
| Q9 | dual-layer compile + write | `schema_ir` extend(enum_values + pattern);`schema_compile.py` static validation;`application/value_validation.py` new helper;SDK shell / application write paths integration | Slice 1 |

**整体**:Slice 1 Form I 实施范围 ≈ 200-400 行代码改动(`sdk/schema.py` + `schema_compile.py` + `application/value_validation.py` + integration calls)+ 几处 error message + docs(Slice 4)。

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Q6 alternative — `Field(volatile=True/False)` runtime enforcement

- **Why rejected**:若 `volatile=False` 实际 runtime disallow set/add,Field 等价 Identity — 重复 descriptor 概念;若不 enforce,纯 surface noise。documentation-only 更 economical。

#### Q6 alternative — `Entity.Meta.immutable_fields = ["..."]`

- **Why rejected**:跟 `volatile=False` 同一问题(声明 immutable Field 等价 Identity),且引入新 schema 配置层(Entity.Meta 现仅 version/description/tags)。

#### Q7 alternative — `DataMember` public(no underscore)+ user-subclass example

- **Why rejected**:鼓励用户 subclass 共通基类创造 custom descriptor 会绕开 schema_compile 的 internal flag(`is_identity_field` / `is_entity_exists`)— 这些 flag 决定 downstream rule / inference / lookup 路径的处理;用户 custom descriptor 会跟 internal contract 不一致,产生 latent bug。需要 custom descriptor 时,由 framework 显式提供 public descriptor(如 Step 2+ `InternalIdentity` / `Fingerprint`)。

#### Q7 alternative — Internal `_DataMember` + `factgraph.sdk._internal.DataMember` re-export

- **Why rejected**:暴露 internal namespace 的 "use at your own risk" 路径会变成 de-facto public API(users will import it);跟 internal-only 的目标实质冲突。

#### Q8 alternative — backward-compat 双支持(explicit cardinality + 类型推断同时)

- **Why rejected**:双支持的 corner case 多(如果 user 同时给 `tags: list[str] = Field(cardinality="single")` 应该怎样?报错 / 以 explicit 为准 / 以推断为准 / 静默选 explicit?);实施成本不 worth alpha-stage 兼容性。user §17 lock-in "no alias" 立场支持 clean break。

#### Q8 alternative — DeprecationWarning + 1 release cycle

- **Why rejected**:alpha 阶段无 release cycle commitment(rc.1 → rc.2 之类是 ad-hoc 计数,不是 deprecation window);warning 路径需要 silently 接受 explicit kwarg 同时推断类型,跟双支持等价复杂。

#### Q8 alternative — Silently ignore 旧 kwarg(ignore + 推断)

- **Why rejected**:用户不会知道 kwarg 被 ignore,看到旧代码"还能跑"但实际类型推断结果可能跟 explicit 不一致(如果用户写错 type annotation);silent failure 模式跟 audit-first ledger 哲学冲突。

#### Q9 alternative — Compile-time only validation

- **Why rejected**:adapter / migration tool / 任何直接调 protocol 层 `set_field` 的路径绕开 compile validation,可写入违反 enum / pattern 的 Claim — INV-5(ledger 是 source of truth)被破坏。

#### Q9 alternative — Write-time only validation

- **Why rejected**:schema 声明 syntactic errors(Literal 混类型 / 不合法 regex)不在 declare 时 catch,要等第一次写 Claim 才报错 — 反馈环慢,debugging 困难。

#### Q9 alternative — Validate at `evidence/write_protocol.set_field`(protocol 层)

- **Why rejected**:跟 meta-ADR §4.4 INV-9 4-layer enforcement 模式冲突 — meta-ADR 锁 protocol 层不加 schema-aware strict assertion(留 Slice 5+);Layer 4 validation 走 application 层保持一致 layering。

### 5.2 Cross-Q rejected combinations

#### Option `Form-I-light`:跳过 `_DataMember`,直接在 Identity / Field 各自加 `description` + `pattern`

- **Why rejected**:重复实现;无共通基类导致 Step 2+ 扩展位(`validators` / `constraints` / `alias` / etc.)必须在两类各自加,违反 DRY;`_DataMember` 是 0-marginal-cost 的重构(`_DeclaredMember` 已存在,加中间层简单)。

#### Option `Form-I-aggressive`:`_DataMember` public + user-extensible + Layer 4 validation 全 compile-time

- **Why rejected**:综合 Q7 + Q9 个别 rejected 理由;过度暴露 + validation 漏洞。

#### Option `Form-I-defer-pattern`:Step 1 仅 Literal enum,pattern 留 Step 2+

- **Why rejected**:pattern 是 PDF Change Request 2026-05-28 已 user-accepted 项(详见 identity §15 决策日志);Step 1 同 slice 落地 marginal cost 小(共通基类已设计了 pattern 槽位),没有 deferring 收益。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q6/Q7/Q8/Q9 rows(`audit:519-522`)
- audit §5.2.1 A5 row "(d) genuinely new(documentation gap)" — 支持 Q6 docs-only
- audit §5.2.2 A6 row "(a) shipped covers(二分 part)+ (b) small gap(无共通基类)" — 支持 Q7 internal `_DataMember`
- audit §5.2.2 A7 row "(b)+(d) gap" + audit §5.2.2 A10 row 描述 `description` Field 已有 — 支持 Q8 类型推断 + Q7 共通基类提升
- audit §5.2.2 A8 + A9 rows "(d) genuinely new" — 支持 Q9 Layer 4 validation 需要新 infrastructure
- audit §5.4 N2 row Identity 已 declared in schema_ir — Q9 schema_ir extend 路径已有 baseline

### 6.2 Shipped code citations

- `src/factgraph/sdk/schema.py:50-141` Identity / Field descriptor 当前形态
- `src/factgraph/sdk/schema.py:20-47` `_DeclaredMember` 协议层基类(已存在)
- `src/factgraph/sdk/__init__.py:62-123` 当前 `__all__` list(不含 `_DataMember`,本 ADR 维持)
- `src/factgraph/authoring/schema_compile.py:291-363` `_compile_field` 当前路径(将被 Q9 extend)
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` 当前路径(Q9 同 extend)
- `src/factgraph/core/evidence/write_protocol.py:128-156` `set_field` 当前 — Q9 write-time validation 在 application 层 wrapper,不动 protocol 层(per meta-ADR §4.4)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-FI grouping(Q6/Q7/Q8/Q9 同 ADR)— justifies 本 ADR 不拆 4 个 sub-ADR
- meta-ADR §4.4 4-layer enforcement(SDK + application strict;ledger/protocol delayed)— justifies §4.4.2 write-time validation 在 application 层而非 protocol 层

### 6.4 Design-point citations

- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §4.1 边界规则(`:166-176`)— Q6 docs guideline source
- identity §8.5 `_DataMember` 共通基类(`:467-510`)— Q7 internal base 设计 source
- identity §8.4 类型推断规则(`:451-465`)— Q8 推断规则 source
- identity §8.4 enum 约束的层位(`:464-470`)— Q9 dual-layer source

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / Slice 5+ — confirmed Step 1 zero-blocker 合规。

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 1 Form I refactor blueprint**(`workflow/blueprints/active/2026-05-29_slice-1-form-i.md`)可起草 — Q6-Q9 全部 locked,Slice 1 范围清晰
- **ADR-IC**(Identity-as-Claim core)起草 — ADR-IC 依赖 Form I 二分 + `_DataMember` 稳定 baseline(Q2 emission layer 决策需在 `_DataMember` 已 settled 的 schema 上推理)
- **ADR-API**(API surface 重组)可独立起草 — 跟 ADR-FI 无 Q dependency(API 层 vs schema 层 disjoint)
- **Slice 4 docs sync slice** 部分 prep:Q6 docs guideline + Q8 migration guide + Q9 docs example 可起草(等其他 ADR adopt 后再 finalize)

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 1 blueprint draft(`workflow/blueprints/active/2026-05-29_slice-1-form-i.md`)| TBD(per CADENCE drafter/reviewer role assignment)| ADR-FI adopt 后 |
| Slice 1 pre-impl grep:扫所有 `Field(cardinality=` 用法 + `Identity(primary_key=` 用法(后者跟 §4.3 协同 — Form I Identity 也去 `primary_key`)| Slice 1 blueprint preflight(Step 4.6.5)| Slice 1 blueprint scoped 后 |
| `schema_ir` 文档更新 — 加 `enum_values` / `pattern` 字段(per Q9)| Slice 1 implementation | Slice 1 Step 4.7 |
| `application/value_validation.py` 新模块 + integration calls(per Q9.2)| Slice 1 implementation | Slice 1 Step 4.7 |
| docs sync(Slice 4)— `04_api_surface.en.md` 加 Form I overview + migration guide;`identity-mechanism-redesign.zh.md` §8 update如 ADR-FI 改了 wording | Slice 4 docs sync | Slice 1 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-IC 启动时 Header `Depends on:` 引用本 ADR(per meta-ADR §7.2 follow-up #2)
- **Blueprint pillar**:Slice 1 blueprint preflight(Step 4.3)必须 re-read 本 ADR 的 §4 Decision,作为 scoped-blueprint §5 Proposed Shape 的输入
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q6/Q7/Q8/Q9 行 status 仍是"待 ADR 决策" — 实际 ADR-FI 已 lock,但 audit doc 不回头改(Stage 1 历史),后续 reviewer 可通过 ADR cross-link 找到答案;**不**触发 audit doc post-stage sync(跟 Q5 split 不同 — Q5 split 是 Q list structure 变化,Q6-Q9 lock 不变 Q list structure)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 1 blueprint 不可单方面 override Q6-Q9 决策;若需要 override,走"本 ADR superseded by 新 ADR-FI-v2"路径
- §4.3 Q8 alpha breaking 决策 carry-forward 到任何 future Form I 修订 — 不可重新引入 cardinality kwarg 作为 deprecated alias
- §4.4 Q9 dual-layer validation 是 Form I 内的最低 enforcement floor — 后续 Layer 4 扩展(`validators` / `constraints`)沿用 dual-layer 路径(compile-time syntactic + write-time value)

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.4 4 Qs 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥1 per Q)+ cross-Q rejected combinations(≥2)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation 5 类 evidence
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR adopted commit
- [x] §1.4 含 shipped baseline pointer(audit N2)

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 1 blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 1 implementation:`sdk/schema.py` 新增 `_DataMember` class **不**在 `__all__` 中
- [ ] Slice 1 implementation:`Field(cardinality="single")` 类调用 raise `SDKSchemaError` 含 migration hint
- [ ] Slice 1 implementation:`Field(): str` 推断 cardinality="single";`Field(): list[str]` 推断 cardinality="multi"
- [ ] Slice 1 implementation:`Literal[...]` 注解写 `enum_values` 到 schema_ir
- [ ] Slice 1 implementation:`Field(pattern=r"invalid[")` raise `SDKSchemaError`(regex syntax invalid)
- [ ] Slice 1 implementation:`Field(pattern=r"^[a-z]+$")` on non-`str` type_domain raise `SDKSchemaError`
- [ ] Slice 1 implementation:`application/value_validation.py` write-time validation:enum miss raise `SDKValueError`;pattern miss raise `SDKValueError`
- [ ] Slice 1 implementation:`fg.fields.set(User.email, ref, "not-an-email")` with `email: str = Field(pattern=r"...")` raise `SDKValueError`(write-time enforcement)
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 加 Form I overview;`identity-mechanism-redesign §8 Form I` 跟 ADR-FI 对齐;`docs/official/kernel/quickstart/` schema 示例改 类型推断 形态

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-FI drafted | 4 Qs(Q6 docs-only / Q7 internal `_DataMember` / Q8 alpha breaking + migration / Q9 dual-layer)。基于 meta-ADR adopted @ `ebafdb0c` + user reviewer 2026-05-29 directional guidance(4 条)。Branch: `v0.2.0-q-fi-form-i-decision-2026-05-29`。Commit: TBD post-stage |
