# Task Blueprint Audit: certainty-salience-ranking-v1

- Blueprint: [2026-03-21_certainty-salience-ranking-v1.md](./2026-03-21_certainty-salience-ranking-v1.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | draft→scoped | Blueprint created | Scope: annotation-layer ranking helper + narrative/NL bottleneck delivery. Prerequisite: certainty/weight vocabulary 已就绪（blocker 解除）。前置 decision freeze: candidate-evidence-tree-salience-impact (03-20)。 |
| 2026-03-21 | scoped | P1+P2 fixes | P1: 新增 narrative `certainty_bottleneck` structured key，NL 消费 machine-readable 数据而非 parse presentation string。P2a: 去掉 `RankedCondition.rank` 字段（无 consumer）。P2b: 冻结 3+ bottleneck NL wording（count + Oxford comma 枚举）。 |
| 2026-03-21 | implementing | Steps 1-3 complete | annotation ranking helper + narrative sorted output + NL bottleneck sentence。2 旧断言适配新排序。212 tests green。 |
| 2026-03-21 | implemented | Steps 4-5 complete | 7 ranking unit tests + 3 NL wording tests（222 total）。annotation docs + architecture docs (CN/EN) synced。 |

## Decision Notes

- Owner layer: annotation / value-semantics（继承 03-20 冻结结论）
- Compute-time: query-time / read-time derived（继承 03-20 冻结结论）
- Ranking 只在 narrative/NL 呈现，不改 certainty_summary JSON shape
- audit/static 通过复用 narrative 自然继承，不单独扩 contract
- unweighted conditions 排在末尾（无 impact 值，不参与 bottleneck）
- tie: 同 impact 的 conditions 全部标注 `[bottleneck]`
