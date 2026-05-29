# Q-IE Decision: EntityEditor lifecycle + commit/rollback + Identity/Field dispatching + sdk_edit factory contract

- Status: proposed
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: design constraint;locks `EntityEditor` lifecycle 模型(open/committed/rolled-back states + EditorClosedError contract)+ commit/rollback semantics(auto-commit on clean `__exit__`)+ Identity 字段 immutability within editor + cardinality enforcement + `sdk_edit` factory contract(edit-existing-only)+ cross-ADR 衔接(ADR-FI Form I descriptor + ADR-IC INV-7c double check + ADR-API §4.1 `fg.entities.edit` Layer 1 入口)。
- Inputs:
  - `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §5.2.2 A16 row(`audit:379`)— Identity 三层 immutable boundary baseline(Layer 1 EntityEditor 已 shipped;Layer 2+3 跟 INV-7c 同 site)+ §5.4 N4 row shipped EntityEditor 形态 + §3.1 Identity-as-Claim cluster overall
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted `b288ea9e` — §4.1 mutable Field contract(docs-only)+ §4.2 `_DataMember` internal + §4.3 Field signature + §4.3-bis Identity descriptor signature 是 EntityEditor `__getattr__` descriptor 分发的输入 schema
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted `2d0866ed` — §4.1 双路径 reject(Layer 1 IdentityEditor + Layer 2+3 application/write_protocol)是本 ADR §4.4 EntityEditor reject 在 Layer 1 的 entry point;§4.2 emission input contract 决定 `sdk_edit` 接受的输入 shape
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted `66434490` — §4.1 Layer 1 `fg.entities.edit` 是 Layer 1 navigation key 唯一 mutation entry;§4.5 `register/extend/apply` 三分锁 EntityEditor 期 schema 必须已注册
  - Identity-mechanism-redesign design-point §12.2 Layer 1 — `fg.entities.edit(EntityCls, **identity)` 是 Layer 1 entry(`:902-922`);§12.8 Identity 三层 immutable boundary table(`:1289-1320`)
- Outputs / Downstream:
  - Slice 2(Identity-as-Claim)blueprint:本 ADR §4.4 Layer 1 reject 跟 ADR-IC §4.1 application 层 reject 一致;Slice 2 实施时 EntityEditor 的 Identity reject 不重写 — shipped baseline
  - Slice 3a(API namespace)blueprint:`fg.write.edit` → `fg.entities.edit` rename + 维持 EntityEditor 实现(per ADR-API §4.1.2 migration mapping);本 ADR 锁定 EntityEditor 公开 contract
- Related:
  - Peer ADRs(Stage 2 收尾):ADR-DOCS(Q17)
- Branch: `v0.2.0-q-ie-entity-editor-decision-2026-05-29`
- Depends on:
  - `workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md` adopted @ `ebafdb0c`(meta-ADR §4.2 grouping — ADR-IE 独立局部 ADR 锁 EntityEditor 公开 surface 形态)
  - `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md` adopted @ `b288ea9e`(ADR-FI Form I descriptor 是 EntityEditor `__getattr__` 分发的输入)
  - `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md` adopted @ `2d0866ed`(ADR-IC §4.1 application 层 reject;本 ADR §4.4 Layer 1 reject 跟其同步)
  - `workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md` adopted @ `66434490`(ADR-API §4.1 Layer 1 `fg.entities.edit` 入口锁定 EntityEditor 是该 entry 的 transaction handle)

> ADR 4-state lifecycle:`proposed` → `adopted`(current binding constraint,stays in `active/`)→ `superseded` or `withdrawn`(moves to `archive/`)。

## 1. Inputs

### 1.1 Audit-sourced rows

本 ADR 锁定 EntityEditor 公开 contract — 跟 audit 中以下 rows 关联:

| Row | Audit anchor | 锁的内容 |
|---|---|---|
| A16 — Identity 三层 immutable boundary | `audit:379` | Layer 1 EntityEditor.IdentityEditor 已 shipped(`sdk/facade.py:448-479` 拒);Layer 2+3 跟 INV-7c 同 site(per ADR-IC §4.1) |
| N4 — EntityEditor lifecycle baseline | shipped `sdk/facade.py:482-547` | open / preview / commit / rollback / `__enter__` / `__exit__` / `EditorClosedError`(`_ensure_open`)|
| sdk_edit factory | shipped `sdk/facade.py:672-680` | edit-existing-only(`sdk_get` first;raise `EntityNotFoundError` if missing) |
| FieldEditor cardinality enforcement | shipped `sdk/facade.py:389-445` | `set` requires single;`add` requires multi;违反 raise `CardinalityError` |

本 ADR **不**引入新 Q list 入口(EntityEditor 是 ADR-FI / ADR-IC / ADR-API 之上的 Layer 1 接口 lockdown,锁 shipped 公开 contract 防 future drift)。

### 1.2 Meta-ADR locked constraints relevant to EntityEditor

- **§4.2 grouping**:ADR-IE 独立局部 ADR(per meta-ADR §4.2 grouping — EntityEditor lifecycle 是 Layer 1 接口议题,不跨 cluster)
- **§4.4 Step 1 zero-Q-PR1 dependency**:本 ADR 无 Q-PR1 / PyReason adapter 依赖 — confirmed
- **§4.4 4-layer enforcement**:本 ADR §4.4 EntityEditor Layer 1 reject 是 SDK shell strict enforce 的实例;跟 ADR-IC §4.1 application/write_protocol 层 strict 一致(defense in depth)

### 1.3 ADR-FI / ADR-IC / ADR-API 已锁的输入

- **ADR-FI §4.1 Field 不可变性 docs-only contract**:EntityEditor 的 Field 路径(`FieldEditor.set/add/retract`)是 Field mutable behavior 的具体实施;本 ADR §4.5 / §4.6 formalize
- **ADR-FI §4.3 / §4.3-bis Field / Identity descriptor signature**:EntityEditor `__getattr__`(`sdk/facade.py:495-514`)按 descriptor 类型分发 FieldEditor / IdentityEditor;本 ADR §4.4 / §4.5 锁定分发契约
- **ADR-IC §4.1 双路径 reject**:Layer 1 IdentityEditor raise + Layer 2/3 application/write_protocol reject — defense in depth;本 ADR §4.4 lock Layer 1 部分(其他 layer 已 ADR-IC 锁)
- **ADR-IC §4.2 emission input contract**:`sdk_edit` 必须接受 already-materialized e_ref(per `sdk_edit` shipped 走 `sdk_get` 前置 check);本 ADR §4.8 lock factory edit-existing-only
- **ADR-API §4.1 Layer 1 入口**:`fg.entities.edit(EntityCls, **identity)` 是 Layer 1 唯一 mutation entry;本 ADR 锁定 EntityEditor 是 该 entry 的返回类型

### 1.4 Shipped baseline(`sdk/facade.py:389-547` + `:672-680`)

**EntityEditor 类**(`facade.py:482-547`):
- `__init__(sdk, entity_cls, identity_values)`:打开 batch transaction(`sdk.batch()`)+ entity handle(`self._tx.entity(...)`)+ `_closed = False`
- `__getattr__(name)`:按 descriptor 类型分发 FieldEditor / IdentityEditor;读取 identity 值 fallback;未知 raise `AttributeError`
- `_ensure_open()`:若 `_closed` raise `EditorClosedError`("editor is closed")
- `preview()`:`_ensure_open` + return BatchPlan preview
- `commit(meta=None)`:`_ensure_open` + commit tx + `_closed = True`(try/finally)
- `rollback()`:`_ensure_open` + `_closed = True`(无 tx rollback — 改 in-memory tx,丢弃即可)
- `__enter__`:`_ensure_open` + return self
- `__exit__(exc_type, exc_val, exc_tb)`:若 exc → rollback;else commit;若已 closed → no-op

**FieldEditor**(`facade.py:389-445`):
- `set(value, meta=None)`:`_ensure_open` + cardinality must be `single`;违反 raise `CardinalityError(operation="set")`
- `add(value, meta=None)`:`_ensure_open` + cardinality must be `multi`;违反 raise `CardinalityError(operation="add")`
- `retract(asrt_id, meta=None)`:`_ensure_open`;delegate to handle

**IdentityEditor**(`facade.py:448-479`):
- `value` property:read from EntityEditor 的 `_identity_values`
- `set/add/retract`:全部 raise `SDKStoreError("identity field is immutable in editor")`

**sdk_edit factory**(`facade.py:672-680`):
- 先调 `sdk_get(sdk, entity_cls, **identity_kwargs)`
- 若 None → raise `EntityNotFoundError`
- 否则 return `EntityEditor(sdk, entity_cls, identity_kwargs)`

## 2. Scope

本 ADR **锁**以下 sub-decisions:

| Sub-decision | 锁的内容 |
|---|---|
| **§4.1** | EntityEditor lifecycle 状态模型 — 4 状态(`open` → `committed` / `rolled-back` / `aborted` 终态)+ EditorClosedError 触发条件 + 终态不可重用 |
| **§4.2** | `commit()` / `rollback()` 行为 — `_closed = True` after either;commit failure 时 transaction 由 ledger 层 rollback,EntityEditor 仍标 closed;rollback 不会 raise(idempotent until 终态)|
| **§4.3** | `__enter__` / `__exit__` 行为 — clean exit auto-commit;exception exit auto-rollback;已 closed 时 `__exit__` no-op;若 commit/rollback 已显式调用,`__exit__` no-op |
| **§4.4** | Identity 字段 Layer 1 reject — IdentityEditor `set/add/retract` raise `SDKStoreError("identity field is immutable in editor")` — 跟 ADR-IC §4.1 INV-7c application/write_protocol 层 reject 形成 defense in depth |
| **§4.5** | Field 字段 cardinality enforcement at FieldEditor 层 — `set` requires single + `add` requires multi;违反 raise `CardinalityError(operation, field_name, actual_cardinality)`;**不依赖**下游 layer 重 check |
| **§4.6** | `__getattr__` descriptor 分发契约 — Field descriptor → FieldEditor;Identity descriptor → IdentityEditor;identity value lookup fallback;未知 name → `AttributeError`(per Python convention);per ADR-FI §4.3 / §4.3-bis descriptor signature |
| **§4.7** | `EditorClosedError` contract — 任何已 closed editor 的 attribute access / method call(除 `__exit__` no-op)raise EditorClosedError;**不可重用**(no `reopen()` semantics);user 必须开新 editor |
| **§4.8** | `sdk_edit` factory edit-existing-only contract — 先 `sdk_get` check;若 entity 不存在 raise `EntityNotFoundError`(含 entity_type + identity_kwargs);若 entity exists 但 user identity_kwargs 形态错(per ADR-FI §4.3-bis Identity 形态)走 `sdk_get` raise 链 |

## 3. Non-scope

本 ADR **不**锁(per cross-ADR boundaries):

| 不锁 | 留给谁 |
|---|---|
| Field signature(`Field(*, description, pattern)`)+ Identity signature(`Identity(*, description, pattern)`)| **ADR-FI §4.3 / §4.3-bis**(已 adopted)|
| Identity Claim emission layer / `_protected_anchor_pred_ids` cache / INV-7c application 层 reject | **ADR-IC**(已 adopted)|
| `fg.entities.create / get / where / match / exists / ref / delete` 形态(per ADR-API §4.1.2 migration)| **ADR-API**(已 adopted)|
| `fg.fields.set/add/retract/delete` 直接路径 cardinality enforcement(不经过 EntityEditor)| **ADR-API §4.1**(已 adopted)+ Slice 3a implementation |
| Batch transaction internal(`sdk.batch()` / `self._tx` 的实施细节;BatchPlan 形态;commit atomic 保证)| **Step 2+** Batch / Transaction ADR 或 Slice 3a blueprint |
| `EntitySnapshot` 形态(`sdk_get` 返回值;`fg.entities.get` 输出)| **ADR-API §4.1**(已 adopted)+ `EntitySnapshot` shipped baseline |
| Field validation(enum / pattern dual-layer)at FieldEditor write path | **ADR-FI §4.4**(已 adopted)— application 层 validate_field_value 是 EntityEditor commit 下游 layer 责任 |
| `sdk_get` factory 内部 implementation(filter / projection logic)| Slice 3a blueprint |
| `fg.entities.create` 路径 — **不**经 EntityEditor;走 ADR-IC §4.2 emission entry(per design-point §12.2 Layer 1 separation) | ADR-IC + Slice 2 |
| Concurrent editing 行为(同时打开多个 EntityEditor on 同 e_ref;commit 顺序;lock semantics)| **Step 2+** Concurrency ADR(本 ADR alpha-stage 单线程假设)|
| Slice 3a 落地的 blueprint slicing | Slice 3a blueprint |

## 4. Decision

### 4.1 EntityEditor lifecycle 状态模型

**锁定**:EntityEditor 有 4 个状态:

| 状态 | 描述 | `_closed` flag | 可调用 |
|---|---|---|---|
| **open** | 初始;`__init__` 完成后 | `False` | 所有 method(`preview` / `commit` / `rollback` / `__enter__` / `__exit__` / 通过 `__getattr__` 拿 FieldEditor/IdentityEditor)|
| **committed** | `commit(meta)` 调用后;ledger 已 append | `True` | 仅 `__exit__` no-op(若仍在 with-block);其他 method raise `EditorClosedError` |
| **rolled-back** | `rollback()` 调用后;tx 丢弃,无 ledger 写入 | `True` | 仅 `__exit__` no-op;其他 method raise `EditorClosedError` |
| **aborted** | `commit()` 调用但 ledger 写入失败(per §4.2.2)| `True` | 仅 `__exit__` no-op;其他 method raise `EditorClosedError` |

**状态转换**(per §4.2 / §4.3):

```text
[open] ─── commit() success ───→ [committed]
[open] ─── commit() failure ───→ [aborted]
[open] ─── rollback() ─────────→ [rolled-back]
[open] ─── __exit__ clean ─────→ [committed] (auto-commit per §4.3)
[open] ─── __exit__ exception ─→ [rolled-back] (auto-rollback per §4.3)

[committed] / [rolled-back] / [aborted] — terminal,无 transition out
```

**`_closed` flag 是 binary**:用一个布尔 flag 表示 "non-open"(committed / rolled-back / aborted 三者无 user-visible 区分;只 `_closed=True` 表示 terminal);user 想知道为什么 closed 走 commit_result(若 commit 成功)或 exception(若 commit 失败 / rollback 显式调用)— EntityEditor 本身不保留 detailed state。

**为什么不暴露 detailed terminal state**:
- 用户场景:commit 成功后拿 `BatchCommitResult`;失败后 catch exception;rollback 后丢弃 editor。无需 query 终态原因
- 暴露 detailed state(如 `editor.state` property)鼓励复杂状态机使用,但 EntityEditor 是单次事务 handle,不是长期 state container
- 终态间 user-visible 区分由 commit 返回值 / raised exception 表达,跟 Pythonic context manager 习惯一致

### 4.2 `commit()` / `rollback()` 行为

#### 4.2.1 `commit(meta=None)` 行为

**锁定**:
- pre-condition:`_ensure_open` — 若已 closed raise `EditorClosedError`
- 行为:调 `self._tx.commit(objects=[self._handle], commit_meta=meta)` — ledger atomic append
- success post-condition:`_closed = True`(state → committed);return `BatchCommitResult`
- failure post-condition:`_closed = True`(state → aborted);exception propagate up(原 exception type)— **不**包装为 `EditorClosedError`
- **failure transactional rollback** 由 ledger 层 / `_tx.commit` 实现保证(per ADR-SYS-B + INV-3 atomic;部分 claim 不会写入)
- `_closed = True` 设置在 `try/finally` 块的 finally(per shipped:`finally: self._closed = True`)— 保证无论 commit 成功 / 失败,editor 都标 closed

**为什么 failure → closed**:
- commit 失败后 user 不应该 retry commit(可能 partial state / unclear ledger 状态);走 "open new editor" 路径更安全
- 跟 Python ` context manager` 失败模式一致(failed `__exit__` 仍 close 资源)
- shipped 行为已是 try/finally close;本 ADR formalize

#### 4.2.2 `rollback()` 行为

**锁定**:
- pre-condition:`_ensure_open` — 若已 closed raise `EditorClosedError`
- 行为:`_closed = True`(state → rolled-back);**不**调 ledger rollback(因 commit 未调,batch tx 仅 in-memory accumulation;丢弃即可)
- **不**返回值;**不** raise exception(except `EditorClosedError` from pre-condition)
- shipped 行为:仅 `_ensure_open()` + `_closed = True`(无 tx rollback)— 本 ADR formalize

**为什么 rollback 不调 tx layer 操作**:
- batch tx 在 commit 前是 in-memory accumulation;无 ledger 副作用
- `_closed = True` 表示 editor 终态;batch tx handle 自然 GC
- 显式 tx.rollback 调用是 redundant work,跟 shipped 一致

#### 4.2.3 双重 commit / rollback 行为

- 第二次 commit / rollback 都 raise `EditorClosedError`(per `_ensure_open` pre-condition)— **不**做 silent no-op
- 跟 Python 资源关闭模式一致(eg., `file.close()` 后再 read raise);user 必须 explicit 处理 lifecycle

### 4.3 `__enter__` / `__exit__` context manager 行为

#### 4.3.1 `__enter__` 行为

**锁定**:
- `_ensure_open` — 若已 closed raise `EditorClosedError`
- return self

#### 4.3.2 `__exit__(exc_type, exc_val, exc_tb)` 行为

**锁定**(per shipped `facade.py:539-546`):

| 状态 | exception path | 行为 | return value(suppress exception?)|
|---|---|---|---|
| `_closed = True`(已 commit/rollback)| any | no-op | `False`(不 suppress)|
| `_closed = False` + exc_type is not None | exception path | call `self.rollback()` | `False`(不 suppress)|
| `_closed = False` + exc_type is None | clean path | call `self.commit()` | `False`(不 suppress)|

**关键 lock**:
- `__exit__` **不** suppress exception(return False 一致;tracebacks 完整 propagate)
- **clean exit auto-commit**:user 不显式 call commit,exit context 时自动 commit;commit 失败的 exception propagate out of `__exit__`
- **若 user explicit commit/rollback before exit**:`__exit__` 看到 `_closed=True` 走 no-op path(避免 double commit / rollback raise)
- 跟 shipped 行为一致

#### 4.3.3 为什么 auto-commit on clean exit(rather than explicit commit-only)

**选 (a) auto-commit on clean exit**(shipped + 本 ADR 锁定):
- Pythonic context manager 习惯(`with open(...) as f: ...` 文件自动 close)
- user code 自然形态:`with fg.entities.edit(User, id="u1") as editor: editor.name.set("Alice")` — 不需要显式 `editor.commit()`
- explicit control 仍可用(user 可在 with-block 内 call `editor.commit()` 或 `editor.rollback()`,然后 `__exit__` no-op)

**选 (b) explicit commit only,no auto-commit**(rejected per §5.1):
- 跟 Pythonic 习惯反直觉;user 容易忘 explicit commit
- 行为更难 reason(`with ... as editor: ...` 出 block 是 no-op?还是 raise?)
- shipped 行为已是 auto-commit;改 (b) 是 breaking change without clear benefit

### 4.4 Identity 字段 Layer 1 reject(EntityEditor `__getattr__` → IdentityEditor.set/add/retract raise)

**锁定**:**Layer 1 reject path**(per ADR-IC §4.1 双路径 reject 的 Layer 1 entry):

```python
# sdk/facade.py:448-479 IdentityEditor.set/add/retract:
def set(self, *args, **kwargs) -> None:
    raise SDKStoreError(
        f"identity field {self._field_name!r} is immutable in editor; "
        f"per INV-7a (Identity is immutable anchor),Identity values cannot "
        f"be modified after entity create. To change identity,delete the "
        f"entity (fg.entities.delete) and create a new one with new identity. "
        f"See ADR-IC §4.1 INV-7c reject paths."
    )
def add(self, *args, **kwargs) -> None:
    raise SDKStoreError(...)  # 同上
def retract(self, *args, **kwargs) -> None:
    raise SDKStoreError(...)  # 同上
```

#### 4.4.1 跟 ADR-IC §4.1 双路径 reject defense in depth

per ADR-IC §4.1 reject table:
- **Layer 1 EntityEditor.IdentityEditor**:本 ADR §4.4 锁(SDK shell strict;fail-fast at user-facing entry)
- **Layer 2 application `fg.fields.*`**:per ADR-IC §4.1 锁(application strict;catch SDK shell bypass)
- **Layer 3 application `fg.assertions.retract`**:per ADR-IC §4.1 + ADR-SYS-B §4.1.5 INV-12 锁(application + write_protocol defense in depth)

**结论**:Layer 1(EntityEditor IdentityEditor)+ application/protocol 层 reject 互补 — defense in depth;Layer 1 是 fast path(user-facing entry,Python type system 友好 raise),其他 layer 是 catch path(bypass / programmatic access)。

#### 4.4.2 Error message contract

- 必须含 INV-7a reference(per ADR-IC + identity §5.2)— 解释 Identity 为什么 immutable
- 必须含 migration hint:delete + create-new 路径
- 必须含 ADR-IC §4.1 reference(让 user 了解整套 reject 防御)
- shipped error message wording 跟以上 contract 一致(per `facade.py:448-479` "identity field is immutable in editor");本 ADR formalize

#### 4.4.3 `value` property 仍可读

**锁定**:`IdentityEditor.value` property 返回 identity value(read-only access);不 raise;允许在 editor context 内 read identity(per shipped `facade.py:453-455`)。

- read 不破坏 INV-7a immutability
- 跟 `EntityEditor.__getattr__` 对 identity_values 的 fallback 一致
- repr / str / bool / __eq__ 都 delegate 到 `value`(shipped 行为;本 ADR 沿用)

### 4.5 Field 字段 cardinality enforcement at FieldEditor 层

**锁定**:Field cardinality 检查在 **FieldEditor 层**(not lower layers);违反 raise `CardinalityError(operation, field_name, actual_cardinality)`:

- **`FieldEditor.set(value, meta=None)`** — 要求 descriptor.cardinality == `"single"`;违反 raise `CardinalityError(operation="set", ...)`
- **`FieldEditor.add(value, meta=None)`** — 要求 descriptor.cardinality == `"multi"`;违反 raise `CardinalityError(operation="add", ...)`
- **`FieldEditor.retract(asrt_id, meta=None)`** — 无 cardinality 检查(retract by asrt_id 跟 cardinality 正交)

#### 4.5.1 为什么在 FieldEditor 层 enforce 而不下游

- FieldEditor 是 user-facing entry;fail-fast 比下游 application/protocol layer raise 更友好(stack trace 更短 + error 含 field_name + operation)
- cardinality 信息来自 schema descriptor(per ADR-FI §4.3 cardinality 推断),在 EntityEditor `__getattr__` 时已经可访问
- 跟 ADR-IC §4.4 4-layer enforcement "SDK shell strict + application strict" 模式一致(SDK shell 是 EntityEditor;application 层有 `fg.fields.set/add` 直接路径 — per ADR-API §4.1,其 cardinality check 是 Slice 3a 实施 scope)

#### 4.5.2 跟 ADR-API §4.1 `fg.fields.set/add` 直接路径 cardinality check 互补

- ADR-API §4.1.2 `fg.fields.set(Field, e_ref, value)` 是 Layer 2 直接路径,**不经过 EntityEditor**
- ADR-API 锁的 Layer 2 直接路径必须有自己的 cardinality check(本 ADR 不锁,留 Slice 3a)
- 本 ADR 锁的是 EntityEditor 内部 FieldEditor 的 cardinality check — entry 点不同,各自 strict

#### 4.5.3 跟 ADR-FI §4.3 `Field()` 推断 cardinality 衔接

- ADR-FI §4.3 锁 cardinality 从 type annotation 推断(no `cardinality=` kwarg)
- shipped FieldEditor 通过 `getattr(descriptor, "cardinality", "")` 读 cardinality;Slice 1 完成 ADR-FI 实施后,该 attr 由推断 path 填充
- 本 ADR 不锁 cardinality **来源** — 仅锁 EntityEditor 内 enforce **行为**(set→single / add→multi)

### 4.6 `__getattr__` descriptor 分发契约

**锁定**:`EntityEditor.__getattr__(name)` 按 entity_cls 上 descriptor 类型分发(per shipped `facade.py:495-514`):

```python
def __getattr__(self, name: str) -> Any:
    self._ensure_open()
    descriptor = getattr(self._entity_cls, name, None)
    if isinstance(descriptor, Field):
        return self._field_editors.setdefault(name, FieldEditor(self, name))
    if isinstance(descriptor, Identity):
        return self._identity_editors.setdefault(name, IdentityEditor(self, name))
    if name in self._identity_values:
        return self._identity_values[name]
    raise AttributeError(name)
```

#### 4.6.1 分发优先级

1. **Field descriptor → FieldEditor**(mutable Field;per ADR-FI §4.1 mutable contract)
2. **Identity descriptor → IdentityEditor**(immutable;per §4.4)
3. **identity value fallback**(read access for identity values when no descriptor — e.g., 已设值的 identity attribute name)
4. **未知 name → `AttributeError`**(per Python convention — `hasattr` / `getattr(default)` 友好)

#### 4.6.2 跟 ADR-FI Form I 衔接

- per ADR-FI §4.3 / §4.3-bis,`Field()` 和 `Identity()` 是 user-facing descriptor 形态(`_DataMember` 共通基类 internal)
- `isinstance` check 必须用 `Field` 和 `Identity` 两个 public class(**不**用 `_DataMember`,per ADR-FI §4.2 internal-only)
- ADR-FI Slice 1 完成后,descriptor 形态符合新 signature;本 ADR 分发逻辑不变(继续 isinstance check)

#### 4.6.3 缓存 FieldEditor / IdentityEditor 实例(per `setdefault`)

- shipped 用 `setdefault` 缓存 — 同 EntityEditor 实例下多次 access 同 field 返回同一 editor(身份相等)
- user 可 `editor.name.set("A").name.set("B")` 链式 — set 返回 EntityEditor;但 `editor.name` 始终是同 FieldEditor
- 跟 Python attribute access 习惯一致;本 ADR 沿用

### 4.7 `EditorClosedError` contract

**锁定**:`EditorClosedError`(`facade.py:_ensure_open` 中 raise)是 **`SDKStoreError` 的子类**(per shipped `EditorClosedError` 继承链);任何已 closed 状态(committed / rolled-back / aborted)调用任何 method(except `__exit__`)raise。

#### 4.7.1 触发条件 enumeration

| Method | `_closed=True` 时行为 |
|---|---|
| `commit(meta)` | raise EditorClosedError |
| `rollback()` | raise EditorClosedError |
| `preview()` | raise EditorClosedError |
| `__getattr__(name)` | raise EditorClosedError(_ensure_open before descriptor dispatch)|
| `__enter__()` | raise EditorClosedError |
| `__exit__(...)` | **no-op**(special-case — closed editor exit OK)|

#### 4.7.2 No reopen / reuse semantics

- EntityEditor 终态后**不可重用**:无 `reopen()` method;无 state reset
- user 想再次编辑必须 `fg.entities.edit(EntityCls, **identity)` 开新 editor
- 跟 Python 资源关闭模式一致

#### 4.7.3 Error message + class

- shipped error message:`"editor is closed"`(简洁;无 entity_cls / identity reference 因 closed editor 无意义)
- Slice 3a 实施时 error message 可加 hint:`"editor is closed; open new editor via fg.entities.edit(...)"`(non-load-bearing 改善)

### 4.8 `sdk_edit` factory edit-existing-only contract

**锁定**:`sdk_edit(sdk, entity_cls, **identity_kwargs)` 是 ADR-API §4.1 `fg.entities.edit` 的 implementation factory:

```python
def sdk_edit(sdk, entity_cls, **identity_kwargs) -> EntityEditor:
    snapshot = sdk_get(sdk, entity_cls, **identity_kwargs)
    if snapshot is None:
        raise EntityNotFoundError(...)
    return EntityEditor(sdk, entity_cls, identity_kwargs)
```

#### 4.8.1 Edit-existing-only contract

- **Pre-condition**:entity 必须已 exist(`sdk_get` 返回非 None)
- **不存在 → raise `EntityNotFoundError`**(含 `entity_type` + `identity_kwargs`)
- **存在 → return EntityEditor**

**为什么 edit 不创建**:
- per ADR-IC §4.2 emission input contract:Identity Claim emission 在 `fg.entities.create` 路径(per ADR-IC §4.2.2 公共入口分类);`fg.entities.edit` **不**作为 emission entry
- 跟 design-point §12.2 Layer 1 separation 一致(create vs edit 是不同 entry,各管自己的 lifecycle)
- 若 edit 允许创建,会让 user 不清楚何时 entity 真正存在;create + edit 应是 clean separation

#### 4.8.2 跟 ADR-API §4.5 schema register 衔接

- `sdk_get` 内部要求 entity_cls 已 register(per `_validate_entity_cls` raise SDKStoreError if not in `_entity_spec_by_class`)
- 若 entity_cls 未 register,raise 链 → SDKStoreError("unknown Entity class") 而非 EntityNotFoundError
- 本 ADR 沿用 shipped 行为;两 error 区分清晰(unknown class vs unknown instance)

#### 4.8.3 Identity kwargs validation

- per `_validate_identity_kwargs_for_get`:extra keys → raise SDKStoreError
- 缺少 required identity field → 经 `sdk_get` 的 `allow_identity_defaults` 路径处理(per shipped behavior)
- 本 ADR 不锁 identity kwargs validation 细节(留 ADR-FI §4.4 dual-layer validation + Slice 3a sdk_get 实施)

### 4.9 Cross-Q decision summary

| Sub-decision | Decision | Implementation surface | Slice |
|---|---|---|---|
| §4.1 lifecycle | 4 状态(open / committed / rolled-back / aborted)+ `_closed` binary flag + 终态不可重用 | shipped `facade.py:482-547` formalize;0 行新增 code | Slice 3a(per ADR-API §4.1 rename `fg.write.edit` → `fg.entities.edit`)|
| §4.2 commit/rollback | commit failure → aborted state + closed;rollback → no tx ops + closed;双重调 raise EditorClosedError | shipped formalize;0 行新增 | Slice 3a |
| §4.3 `__enter__`/`__exit__` | clean exit auto-commit;exception exit auto-rollback;已 closed → no-op;`__exit__` 不 suppress exc | shipped formalize;0 行新增 | Slice 3a |
| §4.4 Identity Layer 1 reject | IdentityEditor `set/add/retract` raise SDKStoreError(per INV-7a)— Layer 1 fail-fast;跟 ADR-IC application/protocol 层 defense in depth | shipped formalize;Slice 3a 时 error message hint 可改善(non-load-bearing)| Slice 3a |
| §4.5 cardinality | FieldEditor set→single / add→multi;违反 CardinalityError;FieldEditor 层 strict + 跟 ADR-API §4.1 Layer 2 直接路径 互补 | shipped formalize | Slice 3a |
| §4.6 `__getattr__` 分发 | Field → FieldEditor;Identity → IdentityEditor;identity value fallback;未知 AttributeError;缓存 setdefault | shipped formalize;Slice 1 ADR-FI 完成后 descriptor signature 改变但分发逻辑不变 | Slice 3a |
| §4.7 EditorClosedError | SDKStoreError 子类;5 entry methods raise;`__exit__` no-op;no reopen;Slice 3a hint 改善 | shipped formalize | Slice 3a |
| §4.8 sdk_edit factory | edit-existing-only;不存在 raise EntityNotFoundError;跟 ADR-IC §4.2 emission separation 一致 | shipped formalize | Slice 3a |

**整体**:本 ADR 主要 **formalize shipped baseline + 锁 cross-ADR 衔接**;Slice 3a 实施增量小(~ 30-80 行 — `fg.write.edit` → `fg.entities.edit` rename + error message hint 改善 + cardinality check 跟 ADR-FI Slice 1 后的 descriptor 形态对齐验证)。

## 5. Rejected Alternatives

### 5.1 Per-Q rejected options

#### Lifecycle alternative — 暴露 detailed terminal state(`editor.state` property 区分 committed / rolled-back / aborted)

- **Why rejected**:user 场景:commit 成功 → 拿返回值;失败 → catch exception;rollback → 丢弃 editor。无需 query 终态原因;暴露 detailed state 鼓励复杂状态机使用,EntityEditor 是单次事务 handle,不是长期 state container;`_closed` binary flag + 区分通过 commit 返回值 / exception 表达 — 跟 Pythonic context manager 习惯一致

#### Commit failure alternative — commit 失败后保持 `_closed=False` 允许 retry

- **Why rejected**:partial state 风险 — commit 失败可能 ledger 部分写入(虽然 INV-3 atomic 保证不该发生,但 retry 路径在 unclear ledger state 下不安全);跟 Python 资源关闭模式不一致;shipped try/finally close 行为是更安全设计;若 future 需要 retry transactional pattern,走独立 ADR 显式 supersede §4.2.1

#### Commit/rollback alternative — `__exit__` 不 auto-commit;要求 user 显式 `commit()` 否则 `__exit__` raise

- **Why rejected**:跟 Pythonic 习惯反直觉(`with open(...) as f` 文件自动 close);user 容易忘 explicit commit;行为难 reason;shipped auto-commit 已成 user 依赖;改 (b) 是 breaking change without clear benefit

#### Commit/rollback alternative — `__exit__` 在 exception path 不 auto-rollback(propagate exception 同时 leave editor open)

- **Why rejected**:editor 处于 unclean state 但 exit context — 资源泄漏;不可 reuse 也无 cleanup;违反 Python context manager "do the right thing on success, cleanup on failure" 模式

#### Identity reject alternative — Layer 1 仅 docs-only warning(不 raise)

- **Why rejected**:per ADR-IC §4.1 INV-7c 是结构性 invariant,**必须** runtime enforce(不可 docs-only);Layer 1 fail-fast 是 4-layer enforcement 的 user-facing 第一道防线;shipped raise 已是终态

#### Identity reject alternative — Layer 1 仅 wrapper around `fg.fields.set` 失败(reuse application layer reject)

- **Why rejected**:Layer 1 fail-fast 比下游 application 层 raise 更友好(stack trace 短 + error message 直接含 entity context);跟 ADR-IC §4.1 双路径 reject defense in depth 一致;Layer 1 reject 不依赖 application 层路径就 enforce

#### Cardinality enforcement alternative — 下沉到 application 层(`fg.fields.set/add` 入口)

- **Why rejected**:FieldEditor 层 fail-fast 更友好(user 在 with-block 内立即知道用错 method);application 层路径(per ADR-API §4.1)是 Layer 2 直接路径,跟 EntityEditor 是独立 entry,各自 strict 不互斥;defense in depth 模式

#### `__getattr__` alternative — 不缓存 FieldEditor / IdentityEditor 实例(每次 access 创建新对象)

- **Why rejected**:身份相等性问题(`editor.name is editor.name` 应该 True);缓存是 Python attribute access 习惯;cost negligible(每个 field 一个对象);shipped `setdefault` 缓存已是 stable pattern

#### EditorClosedError alternative — closed editor `__exit__` raise EditorClosedError instead of no-op

- **Why rejected**:`with` block 退出时 raise 会污染 traceback;closed editor `__exit__` no-op 是 Pythonic 安全行为;若 user 已 explicit commit before exit,no-op 自动正确;若 user 已 rollback before exit,no-op 自动正确

#### `sdk_edit` alternative — edit 允许 create-on-missing(若 entity 不存在,自动 create)

- **Why rejected**:违反 ADR-IC §4.2 emission separation(create 是 emission entry,edit 是 mutation entry,不应耦合);user 不清楚何时 entity 真正存在;命名空间污染(`edit` 暗示 "modify existing",自动 create 破坏 verb 意图);跟 design-point §12.2 Layer 1 separation 不一致

### 5.2 Cross-Q rejected combinations

#### Option `IE-eager-validate`:EntityEditor `__getattr__` 时 strict validate field value type / pattern(per ADR-FI §4.4 Layer 4)

- **Why rejected**:per ADR-FI §4.4.2 锁 value validation 在 **application 层 write-path before ledger append**(per ADR-FI §4.4.2 caller contract);EntityEditor `__getattr__` 仅 dispatch,不 validate;validation 在 commit 路径下游 application layer 调用;Layer 1 strict validate 会双重 work + 跟 ADR-FI 4-layer enforcement 模式不一致

#### Option `IE-lazy-batch`:EntityEditor 不开 batch tx in `__init__`;延迟到 commit 时才开 tx

- **Why rejected**:shipped 行为是 eager batch tx;preview 路径需要 tx context;改 lazy 会让 `editor.preview()` 行为复杂(必须先 implicit 开 tx);0 收益 + 改变 shipped 模式;若 future 需要 lazy 走 supersede 路径

#### Option `IE-multi-entity`:EntityEditor 支持同一 batch 编辑多个 entities

- **Why rejected**:scope creep;shipped EntityEditor 是 single-entity handle;multi-entity batch 是不同抽象(batch facade / multi-entity transaction);改 EntityEditor 公开 contract 会 breaking 现有 user 代码;multi-entity batch 走独立 design 在 Step 2+

## 6. Supporting Evidence

### 6.1 Audit row citations

- `workflow/audit/active/2026-05-29_identity-as-claim-vs-shipped.md` §5.2.2 A16 row(`audit:379`)— Identity 三层 immutable boundary baseline + Layer 1 EntityEditor shipped 拒
- audit §3.1 Identity-as-Claim cluster overall — Q1 (Layer 2 reject) + Q2 (emission) + Q3 (cache) + Q16 (`:exists`) 都跟 EntityEditor Layer 1 reject defense in depth 关联

### 6.2 Shipped code citations

- `src/factgraph/sdk/facade.py:389-445` `FieldEditor`(set/add/retract + cardinality check)
- `src/factgraph/sdk/facade.py:448-479` `IdentityEditor`(value property + set/add/retract raise)
- `src/factgraph/sdk/facade.py:482-547` `EntityEditor` 主类(`__init__` / `__getattr__` / `_ensure_open` / `preview` / `commit` / `rollback` / `__enter__` / `__exit__`)
- `src/factgraph/sdk/facade.py:672-680` `sdk_edit` factory(sdk_get 前置 + EntityNotFoundError + EntityEditor 创建)
- `src/factgraph/sdk/facade.py:683-688` `_validate_entity_cls`(unknown Entity class → SDKStoreError)
- `src/factgraph/sdk/facade.py:691-694` `_validate_identity_kwargs_for_get`(extra keys → SDKStoreError)
- shipped `EditorClosedError` 继承链:`SDKStoreError` ←`EditorClosedError`(per `sdk/docs/04_api_surface.en.md:143`)

### 6.3 Meta-ADR cross-references

- meta-ADR §4.2 ADR-IE grouping — 独立局部 ADR(EntityEditor lifecycle 是 Layer 1 接口议题)
- meta-ADR §4.4 Step 1 zero-Q-PR1 dependency — 本 ADR §6.5 显式 confirm

### 6.4 Design-point citations

- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` §12.2 三层分层 — Layer 1 `fg.entities.edit` 入口(`:902-922`);本 ADR §4.8 sdk_edit factory 衔接
- identity §12.5 6 条硬定义 — Rule 6 ledger scope `field(str)` reject(对 EntityEditor 无影响,但 Field descriptor 类型 dispatch 跟此 rule 一致)
- identity §12.8 Identity 三层 immutable boundary table(`:1289-1320`)— Layer 1 EntityEditor IdentityEditor 行 + Layer 2+3 跟 INV-7c 同 site;本 ADR §4.4 锁 Layer 1 部分

### 6.5 No-Q-PR1 dependency confirmation(per meta-ADR §4.4 hard rule)

本 ADR §1-§9 全文 grep 检查:无引用 Q-PR1 / PyReason adapter / Slice 5 — confirmed Step 1 zero-blocker 合规。

EntityEditor 跟 PyReason adapter 完全 decoupled(adapter 走 `accept_pyreason_session` 路径,跟 user-facing EntityEditor 不交叉)。

### 6.6 Cross-ADR 兼容性 confirmation

#### 6.6.1 ADR-FI(`b288ea9e`)
- §4.3 / §4.3-bis descriptor signature → EntityEditor `__getattr__` isinstance check 跟 ADR-FI public class 一致(Field / Identity;**不**用 `_DataMember` per ADR-FI §4.2)
- §4.1 Field mutable contract docs-only → EntityEditor.FieldEditor 是 mutable 实施(`set/add/retract`);跟 ADR-FI docs 一致
- §4.4 enum/pattern dual-layer validation → EntityEditor 不重复 validate(per §5.2 IE-eager-validate reject)— validation 在 commit 路径下游

#### 6.6.2 ADR-IC(`2d0866ed`)
- §4.1 双路径 reject Layer 1 部分 → 本 ADR §4.4 IdentityEditor raise;defense in depth 跟 §4.1 application + write_protocol 层 reject 互补
- §4.2 emission input contract → `sdk_edit` 要求 entity 存在(per §4.8;通过 `sdk_get`)— Identity Claim 是 `fg.entities.create` 路径 emit,**不**经 EntityEditor

#### 6.6.3 ADR-API(`66434490`)
- §4.1 Layer 1 `fg.entities.edit` → EntityEditor 是该入口的返回 transaction handle
- §4.1.2 migration mapping `fg.write.edit` → `fg.entities.edit` — Slice 3a rename;EntityEditor 类不变
- §4.5 schema register/extend/apply → entity_cls 必须已 register(`_validate_entity_cls` check)

#### 6.6.4 ADR-SYS-A / ADR-SYS-B / ADR-INV9
- ADR-SYS-A(`75f1c8bc`)G1/G2 guard 跟 EntityEditor user-facing entry 一致(entity_cls 走 schema register,自然不会以 `__system__` 开头)
- ADR-SYS-B(`6b0ac349`)`Ledger.append_assertion` typed-rows API 是 EntityEditor commit 的下游;无新交互锁定
- ADR-INV9(`c03e435d`)write_protocol ingress INV-9 check 是 EntityEditor commit 路径下游;EntityEditor 内 set/add 永远写 unary value(单 value per call),自然满足 INV-9

## 7. Consequences

### 7.1 Downstream unblocking

本 ADR adopted 后,以下 unblocked:

- **Slice 3a API surface refactor blueprint**(per ADR-API)— `fg.write.edit` → `fg.entities.edit` rename;EntityEditor 公开 contract 已锁,实施 incremental;`fg.entities.edit` 跟其他 Layer 1 method(`get/where/match/exists/ref/create/delete`)同 Slice
- **ADR-DOCS**(Q17)起草 — EntityEditor 公开 contract(lifecycle / commit/rollback / cardinality / Identity reject / sdk_edit)是 docs sync 内容
- **`sdk/docs/04_api_surface.en.md` EntityEditor section** 跟本 ADR 对齐 — Slice 4 docs sync

### 7.2 Required follow-up actions

| Action | Owner | When |
|---|---|---|
| Slice 3a blueprint 起草:`fg.write.edit` → `fg.entities.edit` rename + 维持 EntityEditor 公开 contract per 本 ADR | Slice 3a blueprint preflight(per ADR-API §7.2)| ADR-IE adopt 后 |
| Slice 3a implementation:`fg.entities.edit(EntityCls, **identity)` 入口指向 sdk_edit;EntityEditor 公开 surface 保持 backward-compat 公开 API | Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 3a implementation(optional non-load-bearing):EditorClosedError error message 加 hint("open new editor via fg.entities.edit(...)") per §4.7.3 | Slice 3a implementation | Slice 3a Step 4.7 |
| Slice 1 implementation verify(per ADR-FI):FieldEditor.cardinality enforcement 跟 ADR-FI §4.3 type-推断 cardinality 后的 descriptor 形态对齐(`getattr(descriptor, "cardinality", "")` 仍 work)| Slice 1 implementation | Slice 1 Step 4.7 |
| docs sync(Slice 4 或 ADR-DOCS)— `04_api_surface.en.md` EntityEditor section + `identity-mechanism-redesign §12.8` 跟 ADR-IE 对齐 | Slice 4 docs sync | Slice 3a 完成后 |

### 7.3 Cross-pillar interaction

- **Design pillar**:ADR-DOCS 起草时 Header `Depends on:` 引用本 ADR(EntityEditor 是 docs sync 范围)
- **Blueprint pillar**:Slice 3a blueprint preflight(Step 4.3)必须 re-read 本 ADR §4(EntityEditor 公开 contract);Slice 1 blueprint implementation Field cardinality 推断后跟本 ADR §4.5 cardinality check 兼容
- **Audit pillar**:本 ADR 不直接对应单一 Q list 行;锁定 A16 / N4 shipped baseline + 拓展 cross-ADR 衔接

### 7.4 No-retroactive boundary

- 本 ADR §4 Decision adopted 后,Slice 3a / Slice 1 blueprint 不可单方面 override §4.1-§4.8 决策;若需要 override,走 "本 ADR superseded by 新 ADR-IE-v2" 路径
- §4.1 lifecycle 4 状态 + `_closed` binary flag:carry-forward — 不可改回 detailed state property / 多 boolean flag
- §4.2 commit failure → aborted closed:carry-forward — 不可改 retry on failure(per §5.1 alt rejected)
- §4.3 `__enter__/__exit__` auto-commit on clean exit:carry-forward — 不可改 explicit-only(per §5.1 alt rejected)
- §4.4 Layer 1 Identity reject:carry-forward — 不可降级为 docs-only / 不可 dispatch to lower layer(per §5.1 alt rejected)
- §4.5 cardinality enforcement at FieldEditor 层:carry-forward — 不可下沉到 application 层 only(per §5.1 alt rejected);Layer 2 直接路径 ADR-API 各自 enforce
- §4.6 `__getattr__` 分发优先级 + 缓存:carry-forward — 不可改优先级 / 不可去缓存(per §5.1 alt rejected)
- §4.7 EditorClosedError no reopen / `__exit__` no-op:carry-forward — 不可加 reopen / 不可让 `__exit__` raise on closed(per §5.1 alt rejected)
- §4.8 sdk_edit edit-existing-only:carry-forward — 不可改 create-on-missing(per §5.1 alt rejected;违反 ADR-IC §4.2 emission separation)

## 8. Acceptance Criteria

ADR adoption(本 ADR commit Status: proposed → adopted)前:

- [x] §4.1-§4.8 8 sub-decisions 全部含 Decision + rationale
- [x] §5 含 per-decision rejected alternatives(≥9 项)+ cross-decision rejected combinations(≥3)
- [x] §6 含 audit / shipped code / meta-ADR / design-point / no-Q-PR1 confirmation / 6 cross-ADR 兼容性 7 类 evidence
- [x] §6.6 显式 confirm 4 cross-ADR(FI / IC / API + SYS-A/SYS-B/INV9)兼容性
- [x] Header `Depends on:` 引用 meta-ADR + ADR-FI + ADR-IC + ADR-API adopted commits
- [x] §1.4 含 shipped baseline pointer + 关键 method line ranges
- [x] §4.4 Identity Layer 1 reject 跟 ADR-IC §4.1 defense in depth 显式 confirm
- [x] §4.8 sdk_edit edit-existing-only 跟 ADR-IC §4.2 emission separation 显式 confirm
- [x] §7.4 显式 no-retroactive carry-forward 8 项

Post-adoption verification(implementation 阶段验证 — Slice 1 / Slice 3a):

**Lifecycle 4 states**(§4.1):
- [ ] Slice 3a implementation:`EntityEditor.commit()` success → `_closed=True` + return BatchCommitResult;contract test verify
- [ ] Slice 3a implementation:`EntityEditor.commit()` failure → `_closed=True` + propagate exception(per shipped try/finally);contract test
- [ ] Slice 3a implementation:`EntityEditor.rollback()` → `_closed=True` + no ledger writes;contract test verify ledger 不动
- [ ] Slice 3a implementation:任意 closed editor method(except `__exit__`)raise EditorClosedError

**commit / rollback semantics**(§4.2):
- [ ] Slice 3a implementation:`commit` 之后再调 commit/rollback raise EditorClosedError
- [ ] Slice 3a implementation:`rollback` 之后再调 commit/rollback raise EditorClosedError

**context manager**(§4.3):
- [ ] Slice 3a implementation:`with fg.entities.edit(User, id="u1") as editor: editor.name.set("Alice")` — clean exit auto-commits;contract test verify ledger 含 set
- [ ] Slice 3a implementation:`with ... as editor: raise ValueError()` — exception path auto-rollback;contract test verify ledger 不动 + ValueError propagate
- [ ] Slice 3a implementation:`with ... as editor: editor.commit(); ...` — `__exit__` no-op(已 closed)
- [ ] Slice 3a implementation:`__exit__` 不 suppress exception(return False)

**Identity Layer 1 reject**(§4.4):
- [ ] Slice 3a implementation:`editor.<identity_field>.set(value)` raise SDKStoreError(含 INV-7a reference + migration hint);contract test
- [ ] Slice 3a implementation:`editor.<identity_field>.add(value)` 同 raise
- [ ] Slice 3a implementation:`editor.<identity_field>.retract(asrt_id)` 同 raise
- [ ] Slice 3a implementation:`editor.<identity_field>.value` read 正常返回(per §4.4.3)

**cardinality enforcement**(§4.5):
- [ ] Slice 3a implementation:`editor.<single_field>.add(value)` raise CardinalityError(operation="add", actual_cardinality="single")
- [ ] Slice 3a implementation:`editor.<multi_field>.set(value)` raise CardinalityError(operation="set", actual_cardinality="multi")
- [ ] Slice 3a implementation:`editor.<single_field>.set(value)` work;`editor.<multi_field>.add(value)` work
- [ ] Slice 1 implementation verify:ADR-FI Slice 1 完成后,descriptor cardinality 来自 type 推断;FieldEditor cardinality check 仍 work

**`__getattr__` 分发**(§4.6):
- [ ] Slice 3a implementation:`editor.<field_name>` 返回 FieldEditor 实例(`isinstance(editor.name, FieldEditor)`)
- [ ] Slice 3a implementation:`editor.<identity_name>` 返回 IdentityEditor 实例(`isinstance(editor.id_field, IdentityEditor)`)
- [ ] Slice 3a implementation:`editor.<unknown_name>` raise AttributeError(per Python convention;hasattr() returns False)
- [ ] Slice 3a implementation:`editor.<field_name> is editor.<field_name>` — 缓存身份相等(setdefault 工作)

**EditorClosedError**(§4.7):
- [ ] Slice 3a implementation:EditorClosedError 是 SDKStoreError 子类(`issubclass(EditorClosedError, SDKStoreError) is True`)
- [ ] Slice 3a implementation:closed editor 的所有 method 调用 raise EditorClosedError(except `__exit__` no-op)
- [ ] Slice 3a implementation:无 `reopen()` / `reset()` method(确认 method 不存在)

**sdk_edit factory**(§4.8):
- [ ] Slice 3a implementation:`fg.entities.edit(EntityCls, ...)` 调用 sdk_edit;entity not exists → raise EntityNotFoundError(含 entity_type + identity_kwargs)
- [ ] Slice 3a implementation:entity exists → return EntityEditor(`isinstance(..., EntityEditor) is True`)
- [ ] Slice 3a implementation:entity_cls not registered → raise SDKStoreError("unknown Entity class")
- [ ] Slice 3a implementation:contract test verify `fg.entities.edit(EntityCls, ...)` **不**创建 entity(per edit-existing-only)— 调 edit on missing entity then sdk_get returns None;raise EntityNotFoundError

**docs sync**:
- [ ] Slice 4 docs sync:`04_api_surface.en.md` EntityEditor section 跟本 ADR §4 对齐;`identity-mechanism-redesign §12.8` 跟本 ADR §4.4 对齐

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | proposed | ADR-IE drafted | 8 sub-decisions(lifecycle / commit/rollback / __enter__/__exit__ / Identity Layer 1 reject / cardinality / __getattr__ 分发 / EditorClosedError / sdk_edit factory)。基于 meta-ADR adopted @ `ebafdb0c` + ADR-FI adopted @ `b288ea9e` + ADR-IC adopted @ `2d0866ed` + ADR-API adopted @ `66434490` + shipped `sdk/facade.py:389-547, 672-680` baseline。本 ADR 主要 formalize shipped + 锁 cross-ADR 衔接;Slice 3a 实施增量小。Branch: `v0.2.0-q-ie-entity-editor-decision-2026-05-29`。Commit: TBD post-stage |
