# Q-FI Decision: Form I cluster — `_DataMember` exposure + cardinality inference + Layer 4 validation + mutable Field contract

- Status: adopted
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks Slice 1 Form I schema refactor 的 5 个 sub-decisions(Q6/Q7/Q8/Q9 per meta-ADR §4.2 grouping + §4.3-bis Identity descriptor surface alignment per 2026-05-29 reviewer P2)before Slice 1 blueprint 起草。
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
- **§7.1 ADR-IC carve-out**:Identity-as-Claim 的 emission / encoding(idref_v1 typed hash / emission layer / schema-evolution)归 ADR-IC;Identity descriptor 的 **public signature** 归本 ADR §4.3-bis(理由见 §4.3-bis 末段)

### 1.3 User reviewer 2026-05-29 directional guidance

ADR-FI draft 启动前 user reviewer 给出 4 条方向:

| Q | User guidance | 影响本 ADR |
|---|---|---|
| Q6 | "不要引入 `volatile=False` 这类额外 surface,除非它确实有 runtime 行为;否则只作为 Field mutable contract 文档化" | §4.1 Decision = documentation-only |
| Q7 | "`_DataMember` 更适合作为 internal/shared base,不建议变成用户显式导入的 public descriptor" | §4.2 Decision = internal-only |
| Q8 | "alpha 阶段可以 breaking,但 ADR 里要明确迁移提示和旧 `cardinality=` 的处置" | §4.3 Decision = alpha breaking + migration notes |
| Q9 | "pattern/Literal 最好 compile-time + write-time 都覆盖:schema 声明早失败,写入值再校验,避免绕过 SDK 时产生脏 Claim"(最终 scope 经 §4.4.2 caller contract 收窄为 application / SDK write path;protocol / ledger direct path 不覆盖 — 详见 §4.4.3 + 第 2 轮 reviewer 2026-05-29 P1 调整) | §4.4 Decision = dual-layer validation |

### 1.4 Shipped baseline(audit §5.4 N2)

- `authoring/schema_compile.py:152-159` Identity field 已 declared in schema_ir(`is_identity_field: True` flag + pred_id 已生成)
- `sdk/schema.py:50-141` Identity / Field 已物理分两类 descriptor
- `sdk/schema.py:91-122` Field `cardinality: str` 必填 kwarg(将被 §4.3 替换)
- `sdk/__init__.py:62-123` shipped `__all__` 含 `Identity` / `Field` / `Entity` / `Relationship`,**不含 `_DataMember`**(本 ADR §4.2 维持)

## 2. Scope

本 ADR **锁**以下 5 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1 Q6** | Mutable Field contract 形态(documentation-only,无新 kwarg / 无 runtime enforce) |
| **§4.2 Q7** | `_DataMember` 共通基类 exposure level(internal/shared base,not public API) |
| **§4.3 Q8** | Field cardinality 推断 migration strategy(alpha breaking,kwarg 删除,migration hints + error messaging) |
| **§4.3-bis** | Identity descriptor surface alignment(`primary_key` / `default` / `default_factory` 三 kwarg 删除,migration hints;同 §4.3 alpha breaking pattern) |
| **§4.4 Q9** | Layer 4 enum + pattern validation layer 分布(dual-layer:compile-time + write-time;protocol/ledger direct path 不覆盖 — caller contract) |

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

### 4.3-bis Identity descriptor surface alignment(companion to §4.3)

**锁定**:`Identity` public signature 在 Form I 下变成 `Identity(*, description=None, pattern=None)` — 跟 `Field` 共享 `_DataMember` 基类的两个 kwargs;**不再**接受 `primary_key=...` / `default=...` / `default_factory=...`。旧调用 raise `SDKSchemaError` 含 migration hint。

**为什么连带去 `primary_key`**:
- Form I 下 Identity bundle = Entity subclass 中**所有** `Identity()` declared fields(per identity-mechanism-redesign §8.1)— `Identity` descriptor 类本身即是 primary-key 标志;`primary_key=True` kwarg 与 descriptor 类型冗余
- 单字段 Identity 跟 multi-field composite Identity 在 Form I 下用 declaration 数量区分(1 个 `Identity()` field vs N 个),不需要 kwarg

**为什么去 `default` / `default_factory`**:
- Identity 是 immutable anchor(per INV-7a — content-derived `idref_v1` hash 锁 Identity 终身不变)— default value 概念 ill-defined:有 default 的 Identity 应该 → 同一 anchor?不同 anchor 看 default 值?均无意义
- Field 端是否保留 `default` 留给 Step 2+(per §3 Non-scope,本 ADR 不锁)

**Migration error path**:

```python
# Form I error path (sdk/schema.py:Identity.__init__):
class Identity(_DataMember):
    def __init__(self, *, description: str | None = None,
                 pattern: str | None = None, **legacy_kwargs: Any) -> None:
        if legacy_kwargs:
            removed = sorted(legacy_kwargs.keys())
            raise SDKSchemaError(
                f"Form I removed Identity kwargs: {removed}.\n"
                f"  - Identity bundle = all Identity() fields on Entity subclass\n"
                f"    (no primary_key flag needed).\n"
                f"  - Identity fields cannot have defaults (immutable anchor).\n"
                f"Migration:\n"
                f"  Old: id: UUID = Identity(primary_key=True)\n"
                f"  New: id: UUID = Identity()"
            )
        super().__init__(description=description, pattern=pattern)
```

**Slice 1 blueprint 必须做的**(跟 §4.3 同 Slice):
- Pre-impl grep:扫所有 shipped 代码 / tests / docs 用 `Identity(primary_key=` / `Identity(default=` / `Identity(default_factory=` 的位置 — 全部 migrate 到 `Identity()` 形态
- shipped `sdk/schema.py:50-89` Identity `__init__` 改 signature(从当前 `Identity(primary_key, default, default_factory, description, ...)` → `Identity(description, pattern)`)
- shipped `sdk/docs/04_api_surface.en.md` / `docs/official/kernel/quickstart/` 含 `Identity(primary_key=)` 示例的 docs 全 sync(在 Slice 4 docs sync 时一并落)
- migration guide(Stage 4 blueprint §10 Outcome)记录 Identity grep 结果(独立计数,跟 Field cardinality 分别报告)

**为什么放在本 ADR 而不延后到 ADR-IC**:
- Identity descriptor 的 signature 是 Form I schema declaration 表面层 —— 跟 Q7 `_DataMember` 共通基类 + Q8 Field signature breaking 同 codebase area(`sdk/schema.py`),同 Slice 1 落地
- ADR-IC 关注 Identity-as-Claim 的 emission / encoding(Q1 idref_v1 typed hash / Q2 emission layer / Q3 schema-evolution),那些是 Identity 的**运行时行为**,跟 descriptor signature **正交**
- 避免 ADR-IC 起草时 retroactively 改 ADR-FI 的 Identity descriptor 形态(违反 §7.4 no-retroactive boundary)

### 4.4 Q9 — Layer 4 enum + pattern validation:**dual-layer**

**锁定**:`Literal[...]` 枚举约束 + `pattern=r"..."` 正则约束**两层都做**:
- **Compile-time(`schema_compile.py`)**:schema 声明 declares-with-static-validation 阶段
- **Write-time(application write path before ledger append)**:每次 `fg.fields.set` / `fg.fields.add` / `fg.entities.create` / `fg.assertions.write`(后者由 ADR-SYS-A 决策)在 application 层调 `evidence/write_protocol` → `ledger.append_assertion` 之前 validate value

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
        # pattern 仅 allowed on str type_domain(per §4.4.1 schema_compile 校验);
        # write-time 显式 isinstance 守卫 — 避免错类型被 str() 字符串化后误通过 regex。
        # 不依赖前置 type-domain 检查的隐式假设,做显式 isinstance 失败更易诊断。
        if not isinstance(value, str):
            raise SDKValueError(
                f"pattern validation expects str value for {pred_id}; "
                f"got {type(value).__name__}"
            )
        if not re.fullmatch(pattern, value):
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

**caller contract**(明确不保证范围):绕过 application 层直接调 `evidence/write_protocol` 或 `core/store/ledger.append_assertion` 的 caller(adapter / migration tool / internal writer / 测试 fixture)是 **trusted internal path**,必须自行 maintain value 与 schema 约束的一致性 — 本 ADR §4.4.2 **不** validate 这些路径,**不** 保证这些路径写入的 Claim 满足 enum / pattern。详见 §4.4.3。

#### 4.4.3 为什么 dual-layer 覆盖"schema 声明错误 + application/SDK write path caller 错误"

- **仅 compile-time 不够**:application / SDK shell write path 的 caller 运行时错误(如 `fg.fields.set(User.status, ref, "invalid_enum")` — schema 声明正确但 caller 传入违反 enum 的 value)在 declare 阶段无法 catch,运行时若无 write-time enforcement 会写入脏 Claim
- **仅 write-time 不够**:schema 作者笔误(`Literal[1, "a"]` 混类型 / `pattern=r"["` 不合法 regex)不在 declare 时被 catch,要等第一次写 Claim 才报错 — 反馈环慢、debug 困难
- **dual-layer**:declare-time catch schema author errors;write-time catch **application / SDK shell write path** caller errors;两层覆盖不同失败模式,不重复

**dual-layer 不覆盖的路径**(per §4.4.2 caller contract):
- `evidence/write_protocol.set_field` direct call(non-application internal path)
- adapter / migration tool / 测试 fixture 直接写 ledger 层
- 这些是 **trusted internal paths**;per meta-ADR §4.4 4-layer enforcement table 锁 protocol / ledger 层 schema-aware enforcement delayed(Step 1 范围外)
- 若 future 需要把 enum / pattern enforcement 下沉到 ledger / protocol 层 强制覆盖所有 caller,需另一个 ADR 显式 supersede 本 §4.4.2 调用边界 — 不在本 ADR 范围内

**性能权衡**:write-time validation 是 O(1) hash lookup(enum) + O(value length) regex match;Form I 范围内可接受。enum_values 适合用 `frozenset[str]` 优化 in-check;pattern 适合 cache `re.compile(pattern)` per pred_id。

### 4.5 Cross-Q decision summary

| Sub-decision | Decision | Implementation surface | Step 1 Slice |
|---|---|---|---|
| Q6 | docs-only | 0 code change(docs only at Slice 4)| Slice 1 + Slice 4 |
| Q7 | internal `_DataMember` | `sdk/schema.py` add `_DataMember` class;NOT in `__all__` | Slice 1 |
| Q8 | alpha breaking + migration hint | `sdk/schema.py` Field signature change;`schema_compile.py` cardinality 推断;error message migration hint | Slice 1 |
| §4.3-bis | alpha breaking + migration hint | `sdk/schema.py` Identity signature change(去 `primary_key` / `default` / `default_factory`);error message migration hint | Slice 1 |
| Q9 | dual-layer compile + write | `schema_ir` extend(enum_values + pattern);`schema_compile.py` static validation;`application/value_validation.py` new helper(含 isinstance str-guard for pattern);SDK shell / application write paths integration;**caller contract**:protocol / ledger direct path 不覆盖 | Slice 1 |

**整体**:Slice 1 Form I 实施范围 ≈ 250-450 行代码改动(`sdk/schema.py` Identity + Field signature 重写 + `_DataMember` 共通基类 + `schema_compile.py` extend + `application/value_validation.py` 新模块 + integration calls)+ Identity 和 Field 各一处 error message + docs(Slice 4)。

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

- **Why rejected**:schema 作者笔误能在 declare 时 catch,但 application / SDK shell write path caller 运行时错误(如 `fg.fields.set(User.status, ref, "invalid_enum")` — schema 声明合法但 caller 传错 value)无 enforcement,会被写入违反 enum / pattern 的 Claim。Layer 2(write-time)是必要的 caller-side guard。**注意**:dual-layer 同样不覆盖 protocol / ledger direct path(per §4.4.2 caller contract);"防绕过 SDK shell 的 internal writer"不是本 ADR 的目标,留 Slice 5+ ADR。

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

#### Option `Defer-identity-surface-to-adr-ic`:`Identity(primary_key=...)` etc. 留 ADR-IC 处理

- **Why rejected**:ADR-IC 关注 Identity-as-Claim 的 emission / encoding(运行时行为),Identity descriptor signature 是 schema declaration 表面层 — 跟 §4.3 Field signature breaking 是相同 codebase area(`sdk/schema.py`)+ 相同 Slice 1 + 相同 migration pattern。延后会:(i)迫使 Slice 1 blueprint 在 ADR-IC adopt 之前以 stale Identity surface 形态起草,然后被 ADR-IC retroactively 改;(ii)违反 §7.4 no-retroactive boundary 原则(后续 ADR 不应改前序 ADR 的 decision)。

#### Option `Identity-surface-keep-primary-key-as-alias`:`Identity(primary_key=True)` silently ignored,推断为单 Identity field

- **Why rejected**:跟 §4.3 silent ignore alternative 同问题(silent failure 与 audit-first 哲学冲突)+ 用户读旧代码会以为 `primary_key=True` 还在做什么,但实际 Form I 下"primary"概念已变成 "Identity bundle = all Identity() fields";误导胜于无 alias。

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §7.3 Q6/Q7/Q8/Q9 rows(`audit:519-522`)
- audit §5.2.1 A5 row "(d) genuinely new(documentation gap)" — 支持 Q6 docs-only
- audit §5.2.2 A6 row "(a) shipped covers(二分 part)+ (b) small gap(无共通基类)" — 支持 Q7 internal `_DataMember`
- audit §5.2.2 A7 row "(b)+(d) gap" + audit §5.2.2 A10 row 描述 `description` Field 已有 — 支持 Q8 类型推断 + Q7 共通基类提升
- audit §5.2.2 A8 + A9 rows "(d) genuinely new" — 支持 Q9 Layer 4 validation 需要新 infrastructure
- audit §5.4 N2 row Identity 已 declared in schema_ir — Q9 schema_ir extend 路径已有 baseline

### 6.2 Shipped code citations

- `src/factgraph/sdk/schema.py:50-89` Identity descriptor 当前 signature(含 `primary_key` / `default` / `default_factory` — 将被 §4.3-bis 删除)
- `src/factgraph/sdk/schema.py:91-122` Field descriptor 当前 signature(含 `cardinality` — 将被 §4.3 删除)
- `src/factgraph/sdk/schema.py:20-47` `_DeclaredMember` 协议层基类(已存在 — §4.2 `_DataMember` extends 此基类)
- `src/factgraph/sdk/__init__.py:62-123` 当前 `__all__` list(含 `Identity` / `Field`,**不含 `_DataMember`** — 本 ADR §4.2 维持)
- `src/factgraph/authoring/schema_compile.py:291-363` `_compile_field` 当前路径(将被 Q9 extend)
- `src/factgraph/authoring/schema_compile.py:227-260` `_compile_identity_predicate` 当前路径(Q9 同 extend)
- `src/factgraph/core/evidence/write_protocol.py:128-156` `set_field` 当前 — Q9 write-time validation 在 application 层 wrapper,**不**动 protocol 层(per meta-ADR §4.4 + 本 ADR §4.4.2 caller contract)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-FI grouping(Q6/Q7/Q8/Q9 同 ADR)— justifies 本 ADR 不拆 4 个 sub-ADR
- meta-ADR §4.4 4-layer enforcement(SDK + application strict;ledger/protocol delayed)— justifies §4.4.2 write-time validation 在 application 层而非 protocol 层

### 6.4 Design-point citations

- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §4.1 边界规则(`:185-198`)— Q6 docs guideline source
- identity §8.1 当前形态 baseline(`:409-441`)— §4.3-bis `Identity()` bundle 语义 source
- identity §8.3 Form I 最终设计 + §8.4 类型推断规则(`:442-510`)— Q8 推断规则 source
- identity §8.4 enum 约束的层位(`:505-510`)— Q9 dual-layer source
- identity §8.5 `_DataMember` 共通基类(`:511-571`)— Q7 internal base 设计 source
- identity §5.2 INV-7a Identity Anchor immutable(`:244-260`)— §4.3-bis Identity 不接受 `default` 的依据

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter — confirmed Step 1 zero-blocker 合规。

**澄清**:§4.4.3 / §7.4 出现 "Slice 5+" 标识 — 那是**前向 carve-out**(本 ADR 不锁的范围交给未来哪个 Slice),**不是 dependency**。Slice 1 实施可在 Slice 5+ ADR 起草前完成,不会被 block。

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
| Slice 1 pre-impl grep(per §4.3 + §4.3-bis):分别扫 `Field(cardinality=` / `Identity(primary_key=` / `Identity(default=` / `Identity(default_factory=` 四类用法 — 每类独立计数 + 全部 migrate | Slice 1 blueprint preflight(Step 4.6.5)| Slice 1 blueprint scoped 后 |
| `schema_ir` 文档更新 — 加 `enum_values` / `pattern` 字段(per Q9)| Slice 1 implementation | Slice 1 Step 4.7 |
| `application/value_validation.py` 新模块 + integration calls(含 isinstance str-guard per §4.4.2)| Slice 1 implementation | Slice 1 Step 4.7 |
| docs sync(Slice 4)— `04_api_surface.en.md` 加 Form I overview + Field 和 Identity 两类 migration guide;`identity-mechanism-redesign.zh.md` §8 update如 ADR-FI 改了 wording | Slice 4 docs sync | Slice 1 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-IC 启动时 Header `Depends on:` 引用本 ADR(per meta-ADR §7.2 follow-up #2)
- **Blueprint pillar**:Slice 1 blueprint preflight(Step 4.3)必须 re-read 本 ADR 的 §4 Decision,作为 scoped-blueprint §5 Proposed Shape 的输入
- **Audit pillar**:本 ADR adopt 后,audit doc §7.3 Q list 中 Q6/Q7/Q8/Q9 行 status 仍是"待 ADR 决策" — 实际 ADR-FI 已 lock,但 audit doc 不回头改(Stage 1 历史),后续 reviewer 可通过 ADR cross-link 找到答案;**不**触发 audit doc post-stage sync(跟 Q5 split 不同 — Q5 split 是 Q list structure 变化,Q6-Q9 lock 不变 Q list structure)

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 1 blueprint 不可单方面 override Q6-Q9 / §4.3-bis 决策;若需要 override,走"本 ADR superseded by 新 ADR-FI-v2"路径
- §4.3 Q8 alpha breaking 决策 carry-forward 到任何 future Form I 修订 — 不可重新引入 `cardinality` kwarg 作为 deprecated alias
- §4.3-bis Identity surface alpha breaking 同 carry-forward — 不可重新引入 `primary_key` / `default` / `default_factory` 作为 alias;ADR-IC 起草时只能在 §4.3-bis 之上建,不能改 Identity public signature
- §4.4 Q9 dual-layer validation 是 Form I 内的最低 enforcement floor — 后续 Layer 4 扩展(`validators` / `constraints`)沿用 dual-layer 路径(compile-time syntactic + write-time value);**ledger / protocol direct path enforcement 留 Slice 5+ ADR 显式 supersede §4.4.2 caller contract**

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.4 + §4.3-bis 5 sub-decisions 全部含 Decision + rationale
- [x] §5 含 per-Q rejected alternatives(≥1 per Q)+ §4.3-bis 专项 rejected alternatives(≥2)+ cross-Q rejected combinations(≥2)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation 5 类 evidence
- [x] §7 含 downstream unblocking + follow-up actions + cross-pillar + no-retroactive boundary
- [x] Header `Depends on:` 引用 meta-ADR adopted commit
- [x] §1.4 含 shipped baseline pointer(audit N2)
- [x] §4.4.2 含明确 caller contract(protocol / ledger direct path 不覆盖)
- [x] §4.4.3 不声称 dual-layer 防"绕过 SDK 产生脏 Claim"(framing 限于 schema 声明错误 + application/SDK write path caller 错误)

Post-adoption verification(implementation 阶段验证):

- [ ] Slice 1 blueprint `Status: scoped` 时,blueprint §1 Related Docs 引用本 ADR
- [ ] Slice 1 implementation:`sdk/schema.py` 新增 `_DataMember` class **不**在 `__all__` 中
- [ ] Slice 1 implementation:`Field(cardinality="single")` 类调用 raise `SDKSchemaError` 含 migration hint
- [ ] Slice 1 implementation:`Identity(primary_key=True)` / `Identity(default=...)` / `Identity(default_factory=...)` raise `SDKSchemaError` 含 migration hint(per §4.3-bis)
- [ ] Slice 1 implementation:`Field(): str` 推断 cardinality="single";`Field(): list[str]` 推断 cardinality="multi"
- [ ] Slice 1 implementation:`Literal[...]` 注解写 `enum_values` 到 schema_ir
- [ ] Slice 1 implementation:`Field(pattern=r"invalid[")` raise `SDKSchemaError`(regex syntax invalid)
- [ ] Slice 1 implementation:`Field(pattern=r"^[a-z]+$")` on non-`str` type_domain raise `SDKSchemaError`
- [ ] Slice 1 implementation:`application/value_validation.py` write-time validation:enum miss raise `SDKValueError`;pattern miss raise `SDKValueError`
- [ ] Slice 1 implementation:`application/value_validation.py` pattern path 在 `re.fullmatch` **之前**做 `isinstance(value, str)` guard,non-str value raise `SDKValueError`(per §4.4.2 type-bypass 防御)
- [ ] Slice 1 implementation:`fg.fields.set(User.email, ref, "not-an-email")` with `email: str = Field(pattern=r"...")` raise `SDKValueError`(write-time enforcement)
- [ ] Slice 4 docs sync:`04_api_surface.en.md` 加 Form I overview + Field 和 Identity 两类 migration guide;`identity-mechanism-redesign §8 Form I` 跟 ADR-FI 对齐;`docs/official/kernel/quickstart/` schema 示例改 类型推断 形态

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-FI drafted | 4 Qs(Q6 docs-only / Q7 internal `_DataMember` / Q8 alpha breaking + migration / Q9 dual-layer)。基于 meta-ADR adopted @ `ebafdb0c` + user reviewer 2026-05-29 directional guidance(4 条)。Branch: `v0.2.0-q-fi-form-i-decision-2026-05-29`。Commit: `67d9359d` |
| 2026-05-29 | proposed | ADR-FI amended(P1/P2 fixes,still proposed)| User reviewer post-draft review(同日)返回 3 findings:(P1)Q9 §4.4.3 anti-bypass framing 与 §4.4.2 调用边界冲突 — 改为 dual-layer 仅覆盖 schema 声明错误 + application/SDK write path caller 错误;protocol / ledger direct path 列为 caller contract 外。(P2-1)`Identity(primary_key=...)` 缺正式锁 — 新增 §4.3-bis Identity descriptor surface alignment(alpha breaking 同 §4.3 pattern;`primary_key` / `default` / `default_factory` 全去)。(P2-2)`re.fullmatch(pattern, str(value))` 类型绕过风险 — 改为先 `isinstance(value, str)` guard。同步 cascade: §1.2 grouping note / §2 Scope table(4→5 sub-decisions) / §4.5 cross-Q summary / §5 rejected alternatives(+2 §4.3-bis-specific 项 + Q9 alternative wording 修正) / §6.2 shipped code citations(扩 Identity descriptor 行范围) / §6.4 design-point citations(+§8.1 / §5.2 INV-7a + 修正所有行号) / §7.2 follow-up(grep 4 类 kwarg) / §7.4 no-retroactive boundary(+§4.3-bis + Slice 5+ caller-contract supersede note) / §8 Acceptance Criteria(+§4.3-bis post-adoption check + §4.4.2 type-bypass check + 两条 proposed-stage check)。Commit: `d5033a53` |
| 2026-05-29 | **adopted** | User reviewer 第 2 轮 review 通过 → adopt | 第 2 轮 review 结论:P1 / P2 全部 resolved。可选 polish 已采纳:§1.3 Q9 user-guidance 行加括号 clarification(原措辞"避免绕过 SDK 时产生脏 Claim"经 §4.4.2 caller contract 收窄到 application / SDK write path 范围,protocol / ledger direct path 不覆盖)— 让 input record 与 final decision scope 严格对齐。本 ADR 现 binding constraint;Slice 1 Form I blueprint 可起草;ADR-IC 起草需 Header `Depends on:` 引用本 ADR adopt commit;blueprints / 后续 ADR 不可单方面 override §4.1-§4.4 + §4.3-bis,override 需走"superseded by ADR-FI-v2"路径。Commit: TBD post-stage |
