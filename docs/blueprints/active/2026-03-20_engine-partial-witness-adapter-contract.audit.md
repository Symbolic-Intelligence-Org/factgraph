# Task Blueprint Audit: Engine Partial Witness — Adapter Contract

- Blueprint: [2026-03-20_engine-partial-witness-adapter-contract.md](./2026-03-20_engine-partial-witness-adapter-contract.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Opened a narrow adapter-contract scoping draft for engine partial witness. Cuts from adapter/evaluator layer, not tree surface. Continues from archived first-round engine witness parity (2026-03-18). |
| 2026-03-20 | scoped | Freeze confirmed | 5 freeze decisions: (1) Souffle-only via Datalog rule rewriting; (2) native SupportArtifact restricted subset with souffle_witness_v1; (3) EngineEvaluatorFn prefer unchanged; (4) runtime-only consumer surface; (5) ProbLog continues degraded. |

## Decision Notes

- 2026-03-20: 本轮切口是 adapter / evaluator contract，不是 tree / NL surface。信息在 adapter 出口处丢失，下游补不回来。
- 2026-03-20: Souffle 初步判断为 first-round 最 feasible 候选（pure Datalog, TSV 可能可扩展），ProbLog 需要 CLI→library 迁移，成本更高。
- 2026-03-20: 不承诺 full native parity。目标是从 "零 witness" 到 "partial witness"，不是到 "完整同构"。
- 2026-03-20: `EngineEvaluatorFn` 返回类型扩展是核心技术决策之一，需要在 scoping 阶段先冻结方向。
- 2026-03-20: Rainbird 比较只用于确认 engine witness 是真实 gap；不直接采纳 Rainbird 的 engine explain 形式。
- 2026-03-20: **Freeze: approach** — 选定方案 C（Datalog rule rewriting），否决方案 A（`-t explain` REPL）和方案 B（`-t none` 注解）。方案 A 的 interpreted-only 限制、REPL 脆弱性、per-tuple 慢是主要否决原因。
- 2026-03-20: **Freeze: naming** — 这是 adapter-level witness sidecar，不是 Soufflé provenance proof tree。不应混淆 "proof tree provenance" 与 "witness-bearing query rows"。
- 2026-03-20: **Freeze: support_kind** — 必须使用新 kind `souffle_witness_v1`，不伪装成 `native_binding_v1`。runtime/tree 消费侧改为按 witness-bearing kind set 判定。
- 2026-03-20: **Freeze: EngineEvaluatorFn** — prefer unchanged，adapter 内部注册 witness 到 Store。显式承认这是 adapter→Store 内部耦合 tradeoff；若实现时证明不可维护，应回到扩展返回类型方案。
- 2026-03-20: **Freeze: consumer surface** — first-round runtime-only（explain + explain-tree）。audit/static deferred。最大风险在 adapter contract，不在离线消费面。
- 2026-03-20: **Freeze: ProbLog** — 继续 `engine_no_witness_v1` + degraded tree。ProbLog partial witness 需要 CLI→library 迁移，deferred 到后续轮次。
