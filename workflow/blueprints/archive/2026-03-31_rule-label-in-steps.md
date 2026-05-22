# rule-label-in-steps

- Status: implemented
- Created: 2026-03-31
- Parent: llm-integration-surface

## 1. Problem

`rule_apply` 步骤（来自 `support_section` 节点）当前描述为通用文本：

```
Support group satisfied: 3 condition(s) met
```

LLM 消费 explain-steps 时不知道这一步走的是哪条规则。`rule_ref` / `rule_ref_section` 兄弟节点已经携带了规则 ID，但在 steps builder 中被标记为 `_TRANSPARENT_KINDS`，信息被完全丢弃。

## 2. Goal

在 `rule_apply` 步骤的 `detail` 字段中暴露 `rule_ref_ids`，描述改为：

| 规则数 | 描述示例 |
|-------|--------|
| 1 条  | `Rule expert-has-recent-pub@v1: 3 condition(s) met` |
| N 条  | `Rules [rule-a@v1, rule-b@v1]: 3 condition(s) met` |
| 0 条  | `Support group satisfied: 3 condition(s) met`（降级兼容） |

## 3. Non-Goals

- 不在描述中展开规则的 `where` 子句
- 不在 `rule_ref` 节点本身生成新步骤（保持 transparent）
- 不改变 ProbLog / PyReason 路径（它们不产生 `support_section`）
- 不暴露 `rule_ref_version` 以外的字段（如 `child_support_digest`）

## 4. Current Context

**树结构（`_candidate_evidence_tree.py`）**

`candidate_result` 节点的 `children` 包含：
```
[support_section, rule_ref_section]   ← 兄弟节点
```

`support_section` 节点（`_build_support_sections()`，line ~125）：
```python
{
    "node_id": "support:<node_key>",
    "node_kind": "support_section",
    "title": "Support",
    "children": [...]
}
```

`rule_ref_section` 节点（`_build_support_sections()`，line ~134）：
```python
{
    "node_id": "rule_refs:<node_key>",
    "node_kind": "rule_ref_section",
    "children": [<rule_ref>, ...]
}
```

`rule_ref` 节点（legacy path，line ~272）：
```python
{ "node_kind": "rule_ref", "rule_ref_id": str, "rule_ref_version": str?, ... }
```

**透传设置（`_candidate_evidence_tree_steps.py`，line 38–45）**

```python
_TRANSPARENT_KINDS = frozenset({
    "predicate_witness_group",
    "rule_ref",
    "referenced_support",
    "rule_ref_section",   # ← 信息在这里被丢弃
})
```

**信息注入点选择**

不修改 steps traversal 的 look-ahead 逻辑；改为在 **树构建阶段** 把 `rule_ref_ids` 注入到 `support_section` 节点中（类似 `witness_count` 的处理方式）。这样 steps traversal 只需读 `node.get("rule_ref_ids", [])`，零耦合变化。

## 5. Design

### 5.1 _candidate_evidence_tree.py — 注入 rule_ref_ids

在构建 `candidate_result` 节点的函数（`_build_candidate_result_node()` 或等价位置）中：
1. 先收集当前层的所有 rule_ref_id（从 `rule_ref_edges` 或 legacy `rule_refs`）
2. 在 `support_section` dict 上追加 `"rule_ref_ids": rule_ref_ids`

```python
rule_ref_ids = [
    e["rule_ref_id"]
    for e in (sa.rule_ref_edges or [])
    if e.get("rule_ref_id")
] or [r for r in (sa.rule_refs or []) if r]
# 注入到每个 support_section 子节点
for child in support_section_nodes:
    child["rule_ref_ids"] = rule_ref_ids
```

### 5.2 _candidate_evidence_tree_steps.py — 三处修改

**① `_traverse_evidence_tree_node`**：`support_section` 分支读取 `rule_ref_ids`
```python
elif node_kind == "support_section":
    data["witness_count"] = _count_assertion_facts(node)
    data["rule_ref_ids"] = list(node.get("rule_ref_ids", []))
```

**② `_describe_step`**：格式化描述
```python
if kind == "support_section":
    n = d.get("witness_count", 0)
    ids = d.get("rule_ref_ids", [])
    if len(ids) == 1:
        return f"Rule {ids[0]}: {n} condition(s) met"
    if len(ids) > 1:
        joined = ", ".join(ids)
        return f"Rules [{joined}]: {n} condition(s) met"
    return f"Support group satisfied: {n} condition(s) met"
```

**③ `_record_to_step`**：把 `rule_ref_ids` 放进 `detail`
```python
elif record.step_kind_raw == "support_section":
    detail["witness_count"] = record.data.get("witness_count", 0)
    detail["rule_ref_ids"] = record.data.get("rule_ref_ids", [])
```

## 6. Implementation Plan

| Step | 文件 | 内容 | 估计 LOC |
|------|------|------|---------|
| 1 | `_candidate_evidence_tree.py` | `_build_candidate_result_node()` 注入 `rule_ref_ids` | ~15 |
| 2 | `_candidate_evidence_tree_steps.py` | traversal + describe + record_to_step 三处 | ~20 |
| 3 | `test_candidate_evidence_steps.py` | 新增 2 个 test case（单规则/多规则/零规则） | ~20 |

总变更：~55 LOC，3 个文件，不影响 ProbLog/PyReason 路径。

## 7. Acceptance Criteria

- [ ] AC1：native tree（support_kind=native）`rule_apply` 步骤的 `description` 包含规则 ID
- [ ] AC2：`detail.rule_ref_ids` 为列表；单规则时 `len==1`，多规则时 `len>1`，无规则时 `len==0`
- [ ] AC3：无 `rule_ref_edges` 且无 `rule_refs` 时，描述降级为原有通用文本
- [ ] AC4：ProbLog/PyReason 路径对应步骤不产生 `rule_ref_ids` 字段（无 support_section）
- [ ] AC5：所有现有 629+ 测试 green

## 8. Open Questions

- Q1（resolved）：`rule_ref_ids` 按 **per-section** 语义注入。当前 tree builder 每个 support artifact 只生成一个 `support_section`，根节点与 `referenced_support` 递归子树都复用相同构建路径，因此无需引入 per-candidate 共享语义。

## 9. Outcome

- 最终落地结果：`support_section.rule_ref_ids` 已在 tree 构建阶段注入；`candidate_evidence_steps.rule_apply` 现在会输出 `detail.rule_ref_ids`，并在单规则/多规则时使用规则名描述。native/souffle 路径生效，ProbLog/PyReason 路径保持不变。
- 与 blueprint 不同的地方：除 `test_candidate_evidence_steps.py` 外，还补了一条 `test_evidence_tree_explain_contracts.py` 用例，直接锁定 tree builder 已把 `rule_ref_ids` 嵌入 `support_section`。
- 为什么会有这些调整：steps tests 只能覆盖 tree→steps 映射，无法证明 `_candidate_evidence_tree.py` 的注入逻辑本身工作正常，因此补一条 tree contract 测试更稳。
- 归档说明：代码、模块文档、母蓝图状态同步完成后，按工作流成对移动到 `docs/blueprints/archive/`。
