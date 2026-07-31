# Audit Log: Stage A — Lifecycle 收敛 + 写链加固 + 双承诺指纹

- Blueprint: [2026-07-31_stage-a-lifecycle-convergence.md](./2026-07-31_stage-a-lifecycle-convergence.md)

## Adopted Conclusions(引用来源 → 本任务采用)

| 来源 | 采用结论 |
|---|---|
| Q-SAE-6 adopted | v0.3.0 载体;pin-first 发布时序(meander 侧先 pin v0.2 SHA) |
| Q-SAE-7 adopted | 双承诺(LtHash state_digest + tx delta 链);fail-closed + repair;meta 入链不入 state digest |
| Q-SAE-8 adopted | (tx_seq, op_ordinal) 事件序 —— 本 blueprint 只落 tx_seq 基础(单事务提交序),event 化在 3b |
| Q-SAE-9 adopted | 双粒度提交面(裁定 1);tx object 承载批次 meta(默认执行项);tx_ref 列留 3b |
| 设计文档 §2 | 现状锚点(14 reject、绕链漏洞、O(N) digest、head 覆盖写)全部 2026-07-31 逐行核实 |
| codex 评审 2026-07-31 | 发布顺序反转、单事务原子化、AUTOINCREMENT 每表独立(tx_seq 需显式分配) |

## Session Journal

| Date | Event | Notes |
|---|---|---|
| 2026-07-31 | blueprint created at `scoped` | scope 由 adopted ADR 锁定,无 draft 探索期;内联裁定:Q-SAE-2 = migration CLI(opt-in),异议窗口至 Phase 3 前 |
| 2026-07-31 | **Phase 0 baseline exception 登记**(Claude 裁定,已核实) | codex 完成 39 文件 surgical sync 至 `b92d6bf5`;全套件 **2725 passed / 32 skipped / 1 failed**。唯一失败 = `src/service/static_ui.py:23` 导入已退役符号 `render_evidence_graph_html` —— 经 `git show HEAD` 核实该符号在 **sync 之前的 HEAD 即已缺失**(既存跨层漂移,非 Phase 0 引入),service 层在本 blueprint 模块边界外。裁定:登记为 baseline exception,Phase 0 验收基线 = 上述数字;漂移修复拆为独立任务(task_b3c98818),不扩本 blueprint。附注:时间戳测试单次抖动(复跑通过,记录在案);本机 readline segfault 经外部只读 shim 规避(环境项,不入库,已核实无 shim 文件混入工作树) |

## Deviations

(none yet)
