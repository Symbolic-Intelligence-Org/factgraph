# Heritage(历史归档)

只追加(append-only)的历史归档区,容纳有长期参考价值但无 active 维护角色的内容。

## 内容

- `blueprint_history/` — 历史遗留 blueprints(早于现代 `workflow/blueprints/` active→archive 生命周期)。可作 rationale 引用;**不要在此开新任务**。
- `bundles/` — pre-`workflow/` 时代的已闭合工作 bundles(例如 routemap design inputs、load test artifacts、namespace-test 提议等)。每个 bundle 保留原有内部结构。

## 权威

Heritage 内容是**历史 rationale**,不是当前真相。不要把这里的任何文件当作当前的约束;当前约束位于 `workflow/foundations/`、`workflow/design/decisions/`(`adopted` 状态)或 `src/factgraph/*/docs/`。

Heritage 条目**落地后只读** — 更新需明确的 slice 工作,不允许就地编辑历史材料。
