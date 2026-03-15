# FactPy ER 开发者指南

## 1. 何时启用 ER（Mention/Canonical）
满足以下任意条件时，建议启用 ER 分层，而不是直接用内容寻址 identity 合并实体：

- 外部数据没有稳定 ID（只有可变字段，如 name/dob/address）
- 同一实体跨来源出现（HR/CRM/日志），字段冲突不可避免
- 需要保留原始记录并支持后续纠错/重跑对齐
- 不接受“误合并不可逆”风险

核心原则：

- Mention 永不合并
- Canonical 才是业务实体
- `canon_of(Mention, Canonical)` 表达实体对齐

## 2. 标准建模

### 2.1 Mention（原始记录层）

- Identity 必须是外部记录地址（如 `source_system + source_id` 或 `batch_id + row_num`）
- `raw_*` 字段是普通 `Field`，不参与 identity

```python
from factpy import Entity, Identity, Field
from factpy import MentionMixin

class PersonMention(MentionMixin, Entity):
    source_system: str = Identity()
    source_id: str = Identity()

    raw_name: str = Field(cardinality="functional")
    raw_dob: str = Field(cardinality="functional")
```

### 2.2 Canonical（业务实体层）

- 默认推荐 synthetic uuid
- 若有权威外部 ID，也可直接使用

```python
from factpy import Entity, Identity, Field
from factpy import CanonicalMixin

class CanonicalPerson(CanonicalMixin, Entity):
    uid: str = Identity(default_factory="uuid4")
    name: str = Field(cardinality="functional")
```

## 3. `canon_of` 语义

`canon_of(Mention, Canonical)` 在 FactPy 中是单值映射。

默认行为：

- 同一 Mention 存在多个 Canonical 候选时，直接报错
- 不会静默选择

SchemaCompiler 会把 `canon_of` 自动标记为 mapping 规格（`single_valued`），由 policy 阶段执行冲突检查与确定化。

## 4. 外部键桥接

推荐使用 ER bridge 谓词：

- `er:key_to_mention(SourceKey, Mention)`
- `er:key_to_canon(SourceKey, Canonical)`

`SourceKey` 建议用 `typed_tuple_v1` 编码，保持可逆与类型稳定：

```python
from factpy import ERCompiler

er = ERCompiler()
source_key = er.encode_source_key("HR", "row-991")
er.emit_key_to_mention(store=store, source_key=source_key, mention=mention_entity)
```

## 5. `canon_policy` 策略

### 5.1 默认推荐：`error`

```python
from factpy import CanonPolicyConfig, export

code = export(
    store=store,
    target="souffle",
    policy_mode="edb",
    canon_policy=CanonPolicyConfig(mode="error"),
)
```

语义：发现多候选即报错，错误信息包含 key 与候选 meta（source/confidence/time）。

### 5.2 可选确定化策略

- `prefer_source`
- `max_confidence`
- `latest`
- `min_assertion_id`
- `min_canonical_id`

所有策略都带稳定兜底排序，确保同样输入重复运行输出一致。

## 6. `policy_mode` 选择

当前建议：

- 需要确定化（tie-break）时，使用 `policy_mode="edb"`
- `policy_mode="idb"` 在需要 tie-break 时会显式拒绝并提示切换到 `edb`

原因：MVP 不依赖目标方言的聚合/排序能力，优先保证确定性和可审计性。

## 7. 最小端到端示例

```python
from factpy import Store, batch, export, CanonPolicyConfig

store = Store()

with batch(store=store, meta={"trace_id": "t1", "source": "HR_DB"}):
    m = PersonMention(source_system="HR", source_id="row-1")
    m.raw_name.set("Alice")
    m.raw_dob.set("1990-01-01")
    m.save(store=store)

    c = CanonicalPerson(uid="c-1")
    c.name.set("Alice")
    c.save(store=store)

    m.canon_of.set(c, meta={"source": "HR_DB", "confidence": 0.99})
    m.save(store=store)

program = export(
    store=store,
    target="souffle",
    policy_mode="edb",
    canon_policy=CanonPolicyConfig(mode="error"),
)
```

## 8. 常见坑

- 不要用可变字段（name/dob）做 identity
- 不要把 `claim/meta_*` 当业务层默认输入（业务规则默认走 `*_view`）
- 不要在多候选 `canon_of` 时静默选择
- tie-break 必须有稳定兜底，否则重复运行结果会漂移
- `claim_arg(A, idx, val, tag)` 的 `tag` 是 canonical typed tag，不应替换成运行时语言类型名
