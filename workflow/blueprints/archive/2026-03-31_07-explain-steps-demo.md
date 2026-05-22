# Blueprint: 07 Explain-Steps & Source Provenance Demo

- Status: implemented
- Created: 2026-03-31
- Parent: 2026-03-31_evidence-explain-depth (archived)
- Related Modules:
  - `examples/07_evidence_graph_multi_engine.ipynb`

---

## 1. 问题

`evidence-explain-depth` blueprint 落地了两条新 surface：

1. **`explain-steps` 端点**（三引擎 flat step list）
2. **`fact_meta.source` → narrative `source_lines` → NL "Fact sources:" 段落**

但目前 `examples/07_evidence_graph_multi_engine.ipynb` 没有任何演示：
- `explain_runtime_steps()` 未被 import，七个 section 里没有一格展示步骤路径
- 所有 `write_runtime_fact()` 调用都没有传 `source` / `approved_by` meta，导致 `source_lines` 在 narrative 里永远是空的

对一个将 07 作为 explain flagship 的项目来说，这条 surface 变成了"代码真相存在但永远不可见"的状态。

---

## 2. 目标

**只更新 `07_evidence_graph_multi_engine.ipynb`**，让用户从一个 notebook 里就能看到：

1. **Native steps** — `fact_check → rule_apply → conclusion` 带 depth 缩进
2. **Source provenance demo** — Alice 的 `publications` 写入含 source meta，narrative 里出现 `source_lines`，NL 出现 "Fact sources:" 段落
3. **ProbLog steps** — `proof_leaf_check → proof_goal_derive → conclusion`
4. **PyReason steps** — `bound_seed → bound_update → convergence` 对照 raw timeline

---

## 3. Non-Goals

- 不新建 notebook
- 不新建测试文件（steps 的单测已在 `test_candidate_evidence_steps.py` 覆盖）
- 不修改任何 `src/` 下的 Python 代码
- 不修改其他 example notebook（01-06, 08+）
- 不实现 render_evidence_steps_html 的 live page 接入
- 不做 i18n / locale 参数演示

---

## 4. 当前状态

### 4.1 imports（`cell id="85642c4e"`）

当前从 `runtime_v1` 导入：
```python
explain_runtime_tree, explain_runtime_summary, explain_runtime_narrative, explain_runtime_nl,
explain_runtime_timeline, explain_runtime_timeline_summary, explain_runtime_timeline_narrative,
```

缺失 `explain_runtime_steps`。

### 4.2 事实写入（`cell id="348dac2a"`，L50-66）

当前对所有研究员统一循环写入 4 个 predicate，`meta` 只传 `confidence`：
```python
write_runtime_fact(session_id, {"pred_id": "researcher:publications", "e_ref": ref,
    "rest_terms": [["string", pubs]], "meta": {"confidence": pub_conf}}, kind="add")
```

没有任何 `source` / `approved_by` 字段。

### 4.3 Native explain section（§2）

当前有 §2.1–§2.5，依次是：
- §2.1 Evaluate + Accept
- §2.2 Evidence Tree
- §2.3 Certainty
- §2.4 Narrative + NL
- §2.5 HTML Rendering

没有 explain-steps cell。

### 4.4 ProbLog section（§3）

当前有 §3.1–§3.3（Proof Tree / Summary+Narrative+NL / HTML），没有 explain-steps cell。

### 4.5 PyReason section（§4）

当前有 §4.1–§4.2（Timeline / HTML），没有 explain-steps cell。

### 4.6 Architecture Summary（末尾 markdown cell）

当前 ASCII diagram 只提到 4-layer explain pipeline（raw tree → summary → narrative → NL），未提 explain-steps。

### 4.7 关键实现依赖（需在实施前验证）

`source_lines` 能否出现取决于整条数据链：

```
write_runtime_fact(meta={"source": "..."})
  → AnnotationRow (kind="str", key="source") 写入 annotation_rows 表
  → _runtime_assertion_detail_for_tree() 读回 flat_meta.source
  → _build_assertion_leaf() → assertion_fact.fact_meta.source
  → narrative tree 扫描 → source_lines
```

其中关键疑问：**`write_runtime_fact` 的 `meta` 参数是否将 `source` / `approved_by` 存入 `AnnotationRow`？**

如果 annotation store 的写入白名单只包含 `confidence` 等预定义键，`source` 可能不会落盘。需要在落 patch 前验证，确认路径闭环。若写入侧不支持，有两条回退路径：
- (a) 通过较低层级 annotation write API 直接创建 AnnotationRow
- (b) 改用 `write_runtime_fact(..., meta={"confidence": ..., "source": ...}, kind="set")` 看是否触发 fallthrough

---

## 5. 设计

### 5.1 Cell 变更清单（按执行顺序）

| ID | 位置 | 变更类型 | 说明 |
|---|---|---|---|
| C1 | §0 imports cell (`id="85642c4e"`) | edit | 追加 `explain_runtime_steps` 到 runtime_v1 import |
| C2 | §1 seeding cell (`id="348dac2a"`) | edit | Alice 的 `publications` 写入加 source meta |
| C3 | §2 — 新增 markdown cell | insert | 添加 `### 2.5 Explain Steps — Fact-to-Conclusion Path` 标题 |
| C4 | §2 — 新增 code cell | insert | Native steps 调用 + depth 缩进打印 |
| C5 | §2 — 新增 code cell | insert | Source provenance：打印 narrative `source_lines` 和 NL source 段落 |
| C6 | §3 — 新增 markdown cell | insert | 添加 `### 3.4 Explain Steps — ProbLog Proof Path` 标题 |
| C7 | §3 — 新增 code cell | insert | ProbLog steps 调用 + 打印 `proof_leaf_check → proof_goal_derive → conclusion` |
| C8 | §4 — 新增 markdown cell | insert | 添加 `### 4.3 Explain Steps — PyReason Timeline as Steps` 标题 |
| C9 | §4 — 新增 code cell | insert | PyReason steps 调用 + 打印 bound_seed/bound_update/convergence，对照 raw timeline |
| C10 | Architecture Summary (末尾 markdown cell) | edit | 在每个引擎的说明里补一行提及 explain-steps |

### 5.2 C2 详细设计（source meta 写入）

在现有的 `publications` 写入循环里，对 Alice 添加 source meta（其他研究员保持不变）：

```python
for ref, name, exp, h_idx, pubs, exp_conf, h_conf, pub_conf in researchers:
    # ... 现有的 name / expertise / h_index / tag_seed 写入保持不变 ...
    pub_meta: dict = {"confidence": pub_conf}
    if ref == alice_ref:
        pub_meta["source"] = "ORCID public database"
        pub_meta["approved_by"] = "data-pipeline-v2"
    write_runtime_fact(session_id, {"pred_id": "researcher:publications", "e_ref": ref,
        "rest_terms": [["string", pubs]], "meta": pub_meta}, kind="add")
```

### 5.3 C4 详细设计（Native steps）

插入在 `cell id="6de0c943"` HTML 渲染 cell **之前**，或之后作为 §2.5（HTML 变为 §2.6）：

```python
steps_n = explain_runtime_steps(session_id, {"kind": "candidate", "id": cid_native})
print(f"explain-steps: {len(steps_n['steps'])} steps")
for s in steps_n["steps"]:
    indent = "  " * s["detail"]["depth"]
    print(f"  {s['step_num']:2}. {indent}[{s['step_kind']}] {s['description']}")
```

预期输出（基于 two-assertion tree with RuleRef chain）：
```
   1.     [fact_check] Fact researcher:expertise(alice_ref) = NLP ✓
   2.     [fact_check] Fact researcher:h_index(alice_ref) = 42 ✓
   3.     [fact_check] Fact researcher:publications(alice_ref) = 50+ ✓
   ...  (established_check leaf group)
   N.   [rule_apply]  Support group satisfied: 3 condition(s) met
   ...  (grant_qualification leaf group + rule_apply)
   M.   [conclusion]  Candidate c1 established (match)
```

（实际 step_num 取决于 tree shape，不硬编码验收标准数字）

### 5.4 C5 详细设计（Source provenance）

```python
narr_src = explain_runtime_narrative(session_id, {"kind": "candidate", "id": cid_native})
source_lines = narr_src["narrative"].get("source_lines", [])
if source_lines:
    print("Fact provenance (source_lines):")
    for line in source_lines:
        print(f"  {line}")
else:
    print("(no source_lines — verify write_runtime_fact meta write path)")

nl_src = explain_runtime_nl(session_id, {"kind": "candidate", "id": cid_native})
paragraphs = nl_src["explain_nl"]["paragraphs"]
src_para = [p for p in paragraphs if p.startswith("Fact sources:")]
if src_para:
    print(f"\nNL source paragraph: {src_para[0]}")
```

### 5.5 C7 详细设计（ProbLog steps）

插入在 `cell id="6981cd12"` HTML 渲染 cell 之后：

```python
steps_p = explain_runtime_steps(session_id, {"kind": "candidate", "id": cid_prob})
print(f"ProbLog explain-steps: {len(steps_p['steps'])} steps")
for s in steps_p["steps"]:
    print(f"  {s['step_num']:2}. [{s['step_kind']}] {s['description']}")
```

预期顺序：`proof_leaf_check` (×2) → `proof_goal_derive` → `rule_apply` → `conclusion`

### 5.6 C9 详细设计（PyReason steps vs raw timeline）

插入在 `cell id="e89c7f02"` EvidenceGraph HTML 之后：

```python
steps_pr = explain_runtime_steps(session_id, {"kind": "candidate", "id": cid_pr})
print(f"PyReason explain-steps: {len(steps_pr['steps'])} steps")
for s in steps_pr["steps"]:
    print(f"  {s['step_num']:2}. [{s['step_kind']:15}] {s['description']}")

print("\n(对照 raw timeline — 同样的事件，不同格式)")
for chain in tl["timeline"]["chains"]:
    for evt in chain.get("events", []):
        comp = chain["component"].rsplit(":", 1)[-1][:20]
        print(f"       t={evt['time']}: {comp}.{chain['label']} "
              f"{evt['old_bound']} → {evt['new_bound']} by {evt['trigger']}")
```

### 5.7 C10 Architecture Summary 更新

在当前 ASCII diagram 里每个引擎说明末尾补：
- Native：`explain-steps → [fact_check, rule_apply, conclusion]`
- ProbLog：`explain-steps → [proof_leaf_check, proof_goal_derive, conclusion]`
- PyReason：`explain-steps → [bound_seed, bound_update, convergence]`

并把 §6 标题行中 "Full explain pipeline" 更新为包含 steps：

> 6. **Full explain pipeline** — tree/timeline → summary → narrative → NL → **steps** for each engine

---

## 6. 实施计划

| 步骤 | 操作 | 细节 |
|---|---|---|
| N1 | **验证 source meta 写入路径** | 运行 `python -c "from factpy_kernel.service.runtime_v1 import write_runtime_fact; ..."` 确认写入 `source` key 后，AnnotationRow 落盘；检查 ledger 的 annotation rows |
| N2 | **C1** — import 追加 | `cell id="85642c4e"` 加 `explain_runtime_steps` |
| N3 | **C2** — source meta 写入 | `cell id="348dac2a"` 修改 Alice publications 写入，加 `pub_meta` 分支 |
| N4 | **C3/C4** — Native steps cells | 在 `cell id="6de0c943"` 之前插入 markdown + code cell |
| N5 | **C5** — Source provenance cell | 紧接 C4 之后插入 |
| N6 | **C6/C7** — ProbLog steps cells | 在 `cell id="6981cd12"` 之后插入 |
| N7 | **C8/C9** — PyReason steps cells | 在 `cell id="e89c7f02"` 之后插入 |
| N8 | **C10** — Architecture Summary | 更新末尾 markdown cell |

---

## 7. 验收标准

- [ ] `explain_runtime_steps` 在 §0 imports cell 里正确导入，notebook 可从头 Restart & Run All 无报错
- [ ] Alice 的 `researcher:publications` 写入含 `source` 和 `approved_by` meta（N1 确认路径后）
- [ ] Native steps cell 打印 steps，`fact_check` 步骤出现在 `rule_apply` 之前，`conclusion` 在最后
- [ ] Source provenance cell：若写入链路闭环，`source_lines` 非空，NL 含 "Fact sources:" 段落
- [ ] ProbLog steps cell 打印的 step_kind 序列含 `proof_leaf_check` 且在 `proof_goal_derive` 之前
- [ ] PyReason steps cell 打印 `convergence` 为最后一步，`node_ref` 为 None
- [ ] Architecture Summary 更新后三个引擎的说明包含 explain-steps
- [ ] 所有现有 cell 输出不被破坏（Restart & Run All 全程无 exception）

---

## 8. 开放问题

所有开放问题已在 2026-03-31 scoping 阶段关闭。

| ID | 问题 | 结论 |
|---|---|---|
| Q-N1 | `write_runtime_fact(meta={"source": "..."})` 是否写入 kind="str" AnnotationRow？ | **已关闭 — YES**。`source`/`approved_by` 在 `_CONVENTION_META_KEYS` 和 `_SHARED_ANNOTATION_WHITELIST` 里（`write_protocol.py` L29-104），写入 `meta_rows` (kind="str")；`_runtime_assertion_detail_for_tree()` 通过 `ledger.find_meta(asrt_id, key, kind="str")` 读回，放入 `flat_meta`；无需任何回退路径 |
| Q-N2 | Alice 的 `publications` assertion 在 tree 里 `pred_id` / `e_ref` 是否与预期一致？ | **已关闭 — YES**。notebook §1 seeding 使用 `sdk.ref(Researcher, researcher_id="Alice")` 作为 `e_ref`，`pred_id="researcher:publications"`，与 tree builder 保持原值；source_line 格式 = `"researcher:publications({alice_ref}) - from 'ORCID public database' (approved by data-pipeline-v2)"` |

---

## 9. Outcome

- **最终落地结果**：10 项 cell 变更全部落地，34 → 41 cells，所有代码 cell 语法无误。
  - C0：Demonstrates #6 加 `**steps**`
  - C1：imports 加 `explain_runtime_steps`
  - C2：Alice `publications` 写入加 `pub_meta` 分支（source + approved_by）
  - C3–C5：§2.5 新增（标题 + steps cell + source provenance cell），原 §2.5 HTML 重编号为 §2.6
  - C6–C7：§3.4 新增（标题 + ProbLog steps cell）
  - C8–C9：§4.3 新增（标题 + PyReason steps cell）
  - C10：Architecture Summary 三引擎各补一行 explain-steps + source_lines from fact_meta 注记

- **与 blueprint 不同的地方**：
  - blueprint 中 C5 source provenance cell 初稿有 `else: print("(none — no facts have source meta in this tree)")`，落地时精简为 `print("  (none)")`，符合用户指定的"保持和 07 现有风格一致"原则

- **为什么会有这些调整**：精简打印文案，噪音最小化。

- **归档说明**：scope 全部收敛在 notebook，未触碰任何 `src/` 代码。Phase 1/2 explain surface 现已通过 07 可见。
