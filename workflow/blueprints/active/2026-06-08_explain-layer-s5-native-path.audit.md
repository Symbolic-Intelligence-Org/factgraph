# Audit Log: Explain Layer S5 — native 路径接通

- Blueprint: [`2026-06-08_explain-layer-s5-native-path.md`](./2026-06-08_explain-layer-s5-native-path.audit.md)
- Created: 2026-06-08
- Status: draft

---

## Preflight Source Read（2026-06-08）

**文件 / commit 读取清单**

| 文件 | 谱系 / commit | 核心发现 |
|---|---|---|
| `evaluate_result.py` | feature branch `ed054fd0` | `Explanation` class 在此；`_build_passed_row_evidence_graph` 用旧 nodes/edges 构造 |
| `evaluate_result.py` | master `562c7419` | **不存在**（master 无此文件） |
| `audit/evidence_graph.py` | S3 impl `69593d36` | thin re-export；只导出 `EvidenceGraph(paths=...)`；`EvidenceNode/EvidenceEdge` 已删 |
| `sdk/store.py` `_explain` | feature branch | `closed_head_false` 分支有 `evidence=None` — S5 接通目标 |
| `sdk/store.py` `_explain` | master | `Explanation`/`_explain` 不存在 |
| `ProofReceipt` | master `_support.py` | 无 `body_ir`/`branches`；passed 路径不能直接复用 probe_native |
| `application/explain/prober.py` | S4 impl `83be07b9` | `probe_native` 就绪；接受 plan+bindings+view_facts |

**关键约束**：
1. S5 必须以 feature branch 为基（含 `Explanation`）；S3/S4 改动需整合进来
2. Q-S5-A 是用户级决策（stale_row/row_not_in_result 改状态）；其他问题委托 Codex

---

## Events

- **2026-06-08 Q-S5-A 用户决策**：Option A 锁定。`stale_row`/`row_not_in_result` → `status="unsupported"`。理由：`failed` 语义 = 逻辑探查失败；协议层不满足 = `unsupported`。完整不变式：`{passed, failed} ↔ evidence is not None`；`{unsupported, invalid_request} ↔ evidence is None`。
- **2026-06-08 scope-freeze**：Q-S5-B/C 委托 Codex。Status → `scoped`。

---

## Deviations

*(实施阶段填入)*
