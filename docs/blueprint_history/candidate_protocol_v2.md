# Candidate Protocol v2 (Current Implementation Spec)

状态：已实现（严格 v2）  
范围：`authoring` / `core.derivation` / `core.store` / `sdk`

## 1. 目标与边界

本规范定义 Derivation -> CandidateSet -> Accept -> Ledger 的 v2 协议语义：

- 新语义：`CandidateSet` 显式区分 `candidate_kind`（`fact` / `entity`）
- 新语义：`entity candidate` 与 `fact candidate` 分离，字段写入不再打包在 entity payload 内
- 新语义：`candidate_ref` 支持依赖图与批量 accept 拓扑执行

## 2. 关键硬规则

1. `CandidateSet` 必含：
   - `candidate_id`：per-run 临时句柄（`cand_v2:`）
   - `candidate_key`：跨 run 稳定键（`candk_v2:`）
   - `candidate_kind`：`fact` 或 `entity`
2. `candidate_key` 为 content-addressed，不含 `run_id`。哈希输入包含：
   - `derivation_id` + `derivation_version` + `candidate_kind` + canonical content
3. `fact payload` 使用 `terms`（arg0 为 subject）：
   - `terms[0]` 必须是 `entity_ref` 或 `candidate_ref`
   - `candidate_ref` 解析为目标 entity 的 `entity_ref`
4. `entity payload` 至少包含：
   - `entity_type`
   - `identity_fields`
   - `resolved_identity`
   - `missing_identity_fields`
5. `identity_override` 规则：
   - 仅允许填补 `missing_identity_fields`
   - 传入已解析字段（即使值相同）报冲突
   - 传入 schema 外 identity 字段报错
6. `accept_many`：
   - 默认 `mode="atomic"`
   - 按 `candidate_ref` DAG 拓扑排序
   - `best_effort` 下失败候选会阻断依赖候选（`BLOCKED_DEPENDENCY`）

## 3. CandidateSet v2 结构

### 3.1 公共字段

```json
{
  "candidate_id": "cand_v2:...",
  "candidate_key": "candk_v2:...",
  "candidate_kind": "fact|entity",
  "target": "...",
  "derivation_id": "...",
  "derivation_version": "...",
  "run_id": "...",
  "generated_at": 0,
  "state": "generated",
  "payload": {}
}
```

### 3.2 entity candidate payload

```json
{
  "entity_type": "User",
  "identity_fields": ["source_system", "source_id"],
  "identity_types": {"source_system": "string", "source_id": "string"},
  "resolved_identity": {"source_system": "APP"},
  "missing_identity_fields": ["source_id"],
  "proposed_entity_ref": null
}
```

### 3.3 fact candidate payload

```json
{
  "pred_id": "user:name",
  "terms": [
    {"kind": "candidate_ref", "candidate_key": "candk_v2:..."},
    {"kind": "literal", "tag": "string", "value": "Alice"}
  ]
}
```

## 4. Derivation 编译与 Evaluate

### 4.1 head 推断 candidate kind

- `head.callee_kind == entity_type` -> entity 路径
- `head.callee_kind == pred_ref` -> fact 路径
- 无 head -> 仍按 fact 路径（no-head 兼容）

### 4.2 candidate_key 计算约束

- `candidate_key` 输入包含 `derivation_id + derivation_version + candidate_kind + canonical_content`，不包含 `run_id`
- `fact` 的 canonical content 中，`candidate_ref` 必须使用被依赖候选的 `candidate_key`
- 含依赖候选时，计算顺序必须按 DAG 自底向上：先无依赖 entity，后依赖它的 fact

### 4.3 schema 编译规则

- 编译阶段对所有 Entity 自动生成 `<T>:exists` predicate（`is_entity_exists=true`）

## 5. Accept 协议

### 5.1 单条 `accept_candidate_set`

- `candidate_kind=entity`：
  - identity 合并：`resolved_identity + identity_override`
  - identity 完整后生成 `entity_ref`
  - 写入 `<T>:exists` claim
- `candidate_kind=fact`：
  - 先解析 `terms` -> `(subject_e_ref, rest_terms)`
  - 再写入 `pred_id(subject_e_ref, rest_terms...)`
- `terms[0]` 规则：
  - 固定为 subject 槽位（arg0）
  - 仅允许 `entity_ref` 或 `candidate_ref`（且该 `candidate_ref` 必须指向 entity candidate）
- `candidate_ref` 解析顺序：
  - 先查本批次已接受实体映射
  - 再查 ledger 中历史 `candidate_key -> entity_ref`

### 5.2 `accept_many`

接口（Store 层）：

```python
store.accept_many(
    requests,
    mode="atomic" | "best_effort",
    idempotent_duplicate_ok=True,
)
```

返回每条候选的状态：

- `ACCEPTED`
- `DUPLICATE`
- `BLOCKED_DEPENDENCY`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`

## 6. Provenance / Meta

accept 写入的 meta 统一包含：

- `source=derivation.accept`
- `derivation_id` / `derivation_version`
- `run_id`
- `candidate_id` / `candidate_key` / `candidate_kind`
- `accepted_at`
- `support_digest` / `support_kind`

entity accept 额外包含：

- `materialize_kind=entity`
- `entity_type`
- `entity_ref`
- `identity_override_digest`（有 override 时）

## 7. 严格输入约束

当前实现不再接受 legacy payload：

1. fact candidate 必须使用 `pred_id + terms`
2. entity candidate 必须使用 v2 identity payload
3. 用户 DSL 不再接受 `materialize_as` 与 `id_policy`
