# meander_qv_vertical_probe — 一次性 P0/A0 纵向探测实验包

**EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT**

本目录是 scoped 蓝图
`workflow/blueprints/active/2026-08-11_meander-agent-query-validation-vertical-probe.md`
(@ `6ce7e2a5`)授权的**一次性、不可续期**实验封套的唯一 tracked 实验根。
它不是产品代码、公共 API、SDK、基准平台或任何 shipped 能力;不得被 `src/**`、
生产路由、导出面或文档引用。实验协议、预算(§6.1 / CAP-FINAL `9eb8b95d`)、
kill 语义(§6.4)与处置推导(§5.15)以蓝图为唯一权威。

- 执行身份与全部 pins:见 [`reports/handoff_record_v0.json`](reports/handoff_record_v0.json)
- 运行边界:仅 `§6.2` allowlist;scratch 只进 gitignored
  `workflow/working/meander-agent-query-validation-vertical-probe/`
- 停止语义:任何 STOP/REVISE kill、cap 触边、scope 偏离即停;
  模型阶段(Step 4)在 `BYOK-01`/`EGRESS-01` 授权前不运行
- fixture manifest 与证据解释:Step 2 冻结后见 `fixtures/manifest.json`
  与 `golden/manifest.json`;终报见 `reports/final_disposition.md`(封存后不可改)

结果无论 PROCEED/REVISE/STOP 都是协议完成;本包在封套终结后按蓝图 §8.14 归档,不再运行。
