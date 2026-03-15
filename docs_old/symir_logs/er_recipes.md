# FactPy ER 实战配方

## 配方 1：从外部行号导入 Mention

目标：把 CSV/DB 行稳定映射为 Mention，不随字段更新改变实体锚点。

```python
from factpy import Store, batch

store = Store()

with batch(store=store, meta={"source": "HR_DB", "trace_id": "import_2026_02_19"}):
    m = PersonMention(source_system="HR", source_id="row-1001")
    m.raw_name.set("Alice")
    m.raw_dob.set("1990-01-01")
    m.save(store=store)
```

检查：

- 多次更新 `raw_name/raw_dob` 后，`claim` 中 subject 不变

## 配方 2：写入 bridge key

目标：建立外部 key 到 Mention/Canonical 的可逆桥接。

```python
from factpy import ERCompiler

er = ERCompiler()

k = er.encode_source_key("HR", "row-1001")
er.emit_key_to_mention(store=store, source_key=k, mention=m)
```

读取并验证 key 可逆：

```python
from factpy import CanonicalTupleCodec

rows = store.view("er:key_to_mention")
source_key_token, mention_ref = next(iter(rows))
parts = CanonicalTupleCodec.decode(source_key_token)
assert [p.value for p in parts] == ["HR", "row-1001"]
```

## 配方 3：默认安全模式（冲突即报错）

目标：保证不会静默误合并。

```python
from factpy import CanonPolicyConfig, export

code = export(
    store=store,
    target="problog",
    policy_mode="edb",
    canon_policy=CanonPolicyConfig(mode="error"),
)
```

当同一 Mention 命中多个 Canonical 候选时，导出会抛错并带冲突明细。

## 配方 4：来源优先策略（prefer_source）

目标：显式按来源可信度选择 Canonical。

```python
cfg = CanonPolicyConfig(
    mode="prefer_source",
    source_priority=("HR_DB", "CRM", "SCRAPER"),
)

code = export(
    store=store,
    target="souffle",
    policy_mode="edb",
    canon_policy=cfg,
)
```

建议：始终保留稳定兜底排序（默认已启用）。

## 配方 5：置信度与时间策略

### 最大置信度

```python
cfg = CanonPolicyConfig(mode="max_confidence", confidence_key="confidence")
```

### 最新记录

```python
cfg = CanonPolicyConfig(mode="latest", time_key="ingested_at")
```

注意：`ingested_at` 建议统一 ISO8601（含时区）。

## 配方 6：排错清单

### 现象：`policy_mode='idb'` 被拒绝

原因：当前方言路径未提供可证明的聚合/排序 tie-break。

处理：

- 切换 `policy_mode="edb"`
- 显式提供 `canon_policy`

### 现象：同一输入多次导出结果不一致

原因：tie-break 规则不完整或 meta 不稳定。

处理：

- 使用 `CanonPolicyConfig(..., stable_tie_break=("assertion_id",))`
- 确保写入 meta（`source/confidence/ingested_at`）一致

### 现象：bridge key 无法反解

原因：source key 不是 typed_tuple_v1。

处理：

- 统一用 `ERCompiler.encode_source_key(...)`
- 或手动保证 token 以 `tup1:` 开头并可由 `CanonicalTupleCodec.decode` 解析

## 配方 7：与非 mapping 谓词共存

目标：ER 策略不影响普通 functional/multi 字段的 chosen 语义。

做法：

- 只对 `is_mapping=True` 的谓词应用 `canon_policy`
- 普通谓词继续走既有 `active/chosen` 路径

这在当前实现中已默认隔离。
