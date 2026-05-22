# Templates(模板库存)

集中的 workflow 文档模板库存。Per Q4 §4.1,这是 workflow 模板的**唯一 canonical 位置**;不存在 per-pillar 的 `templates/` 子目录。

## 库存(9 个模板)

| Pillar | 模板 | 用途 |
|---|---|---|
| `blueprints/` | `task_blueprint.md` | 标准任务蓝图(8 状态生命周期)|
| `blueprints/` | `task_blueprint.audit.md` | 配对 paired audit log |
| `blueprints/` | `legacy_reconstructed_archive.md` | 重建的 legacy 归档 |
| `blueprints/` | `legacy_reconstructed_archive.audit.md` | 重建的 legacy 审计日志 |
| `design/` | `design-point.md` | 概念性设计 essay(迭代,非权威) |
| `design/` | `decision.md` | ADR 风格 decision 记录(4-state)|
| `audit/` | `vs-shipped.md` | Stage 1 漂移审计 |
| `audit/` | `preflight.md` | Step 4.3 preflight 安全检查 |
| `audit/` | `synthesis.md` | Stage 3 post-Q 重分桶 |

## 统一 7-field metadata header(per Q4 §4.3)

每个从模板创建的 workflow 文档,在 H1 标题之后第一个内容段必须包含此 block:

```
- Status: <pillar-specific value>
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: <pillar-specific statement>
- Inputs:
  - <upstream sources 的指针>
- Outputs / Downstream:
  - <consuming documents 的指针>
- Related:
  - <交叉引用>
```

**字段语义**:
- `Status` — 必填;值按 pillar 而异(blueprints 8 状态;decisions 4 ADR 状态;design-points + audits 可选用 `n/a` 或起草标记;paired audit log mirror 其 sibling)
- `Created` / `Last Updated` — `YYYY-MM-DD` 格式
- `Authority` — pillar-specific 角色声明
- `Inputs` / `Outputs / Downstream` / `Related` — 列表;空时用 `- (none)`

**Pillar-specific extensions** 允许加在 7-field 之上(不替代)。例:blueprints 加 `Related Modules` + `Audit Log`;decisions 加 `Branch` + `Depends on`;audits 按 sub-type 加 `Source intent` / `Blueprint` / `Source audit` / `Closed Q decisions`。

**Paired blueprint audit log 约定**:配对 audit log(`<basename>.audit.md`)的 7-field header `Status` 字段 mirror sibling 蓝图,`Authority: paired blueprint audit log`,`Inputs` 指向 sibling 蓝图,`Outputs / Downstream` 通常 `- (none)`。

## Customization 政策(per Q4 §4.5)

**模板是新 workflow 文档的唯一批准起点**。不鼓励手工从空白起草。

- **允许**:在模板结构之外加新 section;在同层级内调整顺序(若 pillar 治理允许);省略明确标 optional 的 section。
- **不允许**:修改 7-field schema、省略 required 字段、替换字段名、空列表时静默省略 `Inputs:` / `Outputs / Downstream:` / `Related:`(改用 `- (none)`)。

理由:模板编码了来之不易的 cadence 教训。自由起草会让这些教训随 drift 流失。

## Per-pillar 指针规则(per Q4 §4.4)

每个 pillar 的 `README.md`(SC-1 合并后承担了原 pillar-AGENTS 的内容)包含一个 "模板" 段,指向该 pillar 消费的模板。Agent 不需要每次全局搜索 — 在本 pillar README 内本地查找即可。
