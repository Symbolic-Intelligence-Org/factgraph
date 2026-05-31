# 我该用哪个 Capability?

这是一张 task-style 决策表。它不替代 `evidence-pipeline.cn.md` 的分层说明,只回答"我现在该调用哪条 shipped capability line?"

## 一句话决定树(读路径,Q1-Q5)

| 你的问题 | 选择 |
|---|---|
| 我有一个完整或部分 binding,想知道它通不通 | **Q1 Check** — Does this binding pass? |
| 这个 binding 不通,我想知道卡在哪个 atom | **Q2 Diagnose** — Where does this failing binding fail? |
| 我不想写 ledger,只想假设某个 fact 变了会怎样 | **Q3 Fact Overlay Check** — What if this fact were different? |
| 我有一组有限候选 binding,想知道谁通、谁不通、为什么不通 | **Q4 Why-not Universe Diagnose** — Given a finite candidate universe, who passes / who fails / why? |
| native where-body 没产出 binding,我想看 evaluator 在哪一步坍塌 | **Q5 Evaluator Frontier Trace** — In native evaluation, where does the where-body collapse? |

## Overlay & ProofFrame 路径(假设性评估,Batch 4 + 5a/5b/5c)

| 你的问题 | 选择 |
|---|---|
| Fact overlay 已 flip 了 binding 的 pass/fail,我想 per-atom 解释原 proof path 是否仍 valid | **ProofFrame Rechecker**(Batch 4)—— `recheck_proof_frame` |
| 我想测试"如果这条 rule body atom 被禁用会怎样" | **Rule Disable**(Batch 5a)—— `check_rule_disable_action` |
| 我想测试"如果 rule 内某个 literal 改成 X 会怎样" | **Rule Literal Replace**(Batch 5b)—— `check_rule_literal_replace_action` |
| 我想测试"如果 rule body 加一个 filter atom 会怎样" | **Rule Add Condition**(Batch 5c,filter-only)—— `check_rule_add_condition_action` |

## 边界速记

- **Check** 是 boolean judgment:给定 binding,回答 passed / failed / unsupported / invalid_request。
- **Diagnose** 是失败定位:通常在 Check failed 后使用,回答第一个失败 atom。
- **Fact Overlay Check** 是 fact what-if:不写 ledger,只比较 before / after。
- **Why-not Universe Diagnose** 是有限集合分区:一次性得到 green / red rows。
- **Evaluator Frontier Trace** 是 evaluator-layer 工具:不是 application protocol DTO,直接读 native where-body frontier。
- **ProofFrame Rechecker** 是 fact-overlay 路径的 per-atom 解释器:复用 Q1 Check 输出的 `ProofReceipt`,统一 3-status verdict;`not` step 永远 emit `unknown`(strict deferral)。
- **Rule Disable / Literal Replace / Add Condition** 都是 rule-side overlay 操作:输出 `variant_rows + ProofFrame` dual-output;native only;single-action MVP;`evaluate_native_where` 签名 hard-stable;不复活 `superseded_by_full_eval`。

## 何时不在已 shipped 范围(留作 Batch 6+)

- 想 add condition 引入新变量 binder → real binding planner deferred(Batch 5c 仅 filter-only);
- 想 multi-action ordering(disable + replace + add 组合)→ 各 batch single-action MVP,multi-action 留 future;
- 想 RuleRef-recursive overlay → 全 batch reject/defer;
- 想把一个 round 持久化成 event log + reload → Batch 6 durable round persistence;
- 想跨 run 做 proof diff 或 module aggregation → Batch 7 evidence diff / cross-run;
- 想 SDK ergonomic shell / service routes / public surface → Batch 8 public surface decision。

## 示例入口

- 阅读版本(Q1-Q5):`examples/11_capabilities_e2e_demo.ipynb`
- smoke target:`python examples/11_capabilities_e2e_demo.py`
- 机制背景:`tutorials/evidence-pipeline.cn.md` §1-§15(Q1-Q5 + producer 路径) + §16(Batch 4 + 5a/5b/5c overlay 操作)
