# Reference Docs

`docs/references/` 用于收口三类不会直接成为当前实现真相、但对 blueprint 和架构讨论有价值的材料：

- `external/`
  - 外部标准、竞品、论文、产品或方案比较。
- `bridges/`
  - 历史内部材料到当前 FactPy 结构的提炼、桥接和迁移说明。
- `working/`
  - 仅供当前讨论使用的工作笔记、启发式材料或未定稿参考文档。
- `templates/`
  - 这类文档的最小起点模板。

## 边界

- 本目录不是当前实现真相；当前实现请看 `src/factpy_kernel/*/docs/`。
- 本目录不是 blueprint 状态机；任务决策、边界和验收仍写在 `docs/blueprints/`。
- 本目录不是历史蓝图归档；历史蓝图和 reconstructed archive 仍按既有规则分别放在 `docs/blueprint_history/` 与 `docs/blueprints/archive/`。

## 工作流规则

1. 新的参考材料应放到本目录，不要继续散落在仓库根目录。
2. 文件名应尽量使用可读的描述性 slug，避免再出现 `temp.md` 这类失去语义的命名。
3. 如果某份 reference 文档影响了 blueprint 的问题边界、设计决策或验收标准，必须把被采纳的结论写回 active blueprint 和 audit。
4. 如果某份 reference 文档中的内容已经成为当前实现语义或稳定系统边界，必须继续回写到模块 docs 或 `docs/architecture_principles.md`。
5. `working/` 下的文档必须显式标明其非权威性质；它们可以在后续被提升到 `external/` / `bridges/`，也可以在失去价值后删除。

## 当前条目

- [external/rainbird-evidence-chain-compare.md](/Users/zhenzhili/hnsm-backend/docs/references/external/rainbird-evidence-chain-compare.md)
  - Rainbird 证据链与 explainability 交付形态的外部比较笔记。
- [bridges/symir-blueprint-extraction.md](/Users/zhenzhili/hnsm-backend/docs/references/bridges/symir-blueprint-extraction.md)
  - 历史 Symir 蓝图到当前 FactPy 结构的提炼和桥接工作文档。
- [working/cross-domain-compliance-framing.md](/Users/zhenzhili/hnsm-backend/docs/references/working/cross-domain-compliance-framing.md)
  - 仅供当前讨论使用的跨域合规与可追溯性 framing 笔记；不是外部事实依据。
