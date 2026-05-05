# 我该用哪个 Capability?

这是一张 task-style 决策表。它不替代 `evidence-pipeline.cn.md` 的分层说明,只回答"我现在该调用哪条 shipped capability line?"

## 一句话决定树

| 你的问题 | 选择 |
|---|---|
| 我有一个完整或部分 binding,想知道它通不通 | **Q1 Check** — Does this binding pass? |
| 这个 binding 不通,我想知道卡在哪个 atom | **Q2 Diagnose** — Where does this failing binding fail? |
| 我不想写 ledger,只想假设某个 fact 变了会怎样 | **Q3 Fact Overlay Check** — What if this fact were different? |
| 我有一组有限候选 binding,想知道谁通、谁不通、为什么不通 | **Q4 Why-not Universe Diagnose** — Given a finite candidate universe, who passes / who fails / why? |
| native where-body 没产出 binding,我想看 evaluator 在哪一步坍塌 | **Q5 Evaluator Frontier Trace** — In native evaluation, where does the where-body collapse? |

## 边界速记

- Check 是 boolean judgment:给定 binding,回答 passed / failed / unsupported / invalid_request。
- Diagnose 是失败定位:通常在 Check failed 后使用,回答第一个失败 atom。
- Fact Overlay Check 是 fact what-if:不写 ledger,只比较 before / after。
- Why-not Universe Diagnose 是有限集合分区:一次性得到 green / red rows。
- Evaluator Frontier Trace 是 evaluator-layer 工具:不是 application protocol DTO,直接读 native where-body frontier。

## 何时不在这 5 个里

- 想做 multi-fact scenario container:等 Batch 3 `EvaluationOverlay`。
- 想解释旧 proof path 在 overlay 下是否仍成立:等 Batch 4 `ProofFrame Rechecker`。
- 想 disable / replace / add rule condition:等 Batch 5 rule-side operations。
- 想把一个 round 持久化成 event log:等 Batch 6 durable round persistence。
- 想跨 run 做 proof diff 或 aggregation:等 Batch 7 evidence diff / cross-run。

## 示例入口

- 阅读版本:`examples/11_capabilities_e2e_demo.ipynb`
- smoke target:`python examples/11_capabilities_e2e_demo.py`
- 机制背景:`tutorials/evidence-pipeline.cn.md`
