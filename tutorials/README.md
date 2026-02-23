# FactPy Kernel Tutorials（面向用户）

本目录提供面向用户的分步教程，目标是让你从「第一次运行」快速走到「Authoring → Apply → Registry → Audit UI」的可用闭环。

## 适用对象

- 想先跑通最小链路的使用者（不需要先读完整规范）
- 需要用 CLI / DSL 验证 authoring 流程的开发者
- 需要查看 apply 执行结果、registry 状态与审计页面的使用者

## 教程路线（建议顺序）

1. [`01-环境与安装.md`](./01-环境与安装.md)
   - 安装、命令入口检查、Soufflé 可选检查
2. [`02-第一次-Authoring-Preflight（JSON 与 DSL）.md`](./02-第一次-Authoring-Preflight（JSON 与 DSL）.md)
   - 使用 JSON / Python DSL 做 preflight 与 workflow dry-run
3. [`03-Apply-Execute-与-Registry.md`](./03-Apply-Execute-与-Registry.md)
   - 真实执行 apply、幂等请求、事务策略参数
4. [`04-Registry-只读查看与运维命令.md`](./04-Registry-只读查看与运维命令.md)
   - 使用 CLI 查看 schema/rule/derivation/apply runs
5. [`05-导出审计包与静态审计页面.md`](./05-导出审计包与静态审计页面.md)
   - 生成 audit package 与静态审计页面（概念层 UI）
6. [`06-事务策略与排障（v1/v2）.md`](./06-事务策略与排障（v1-v2）.md)
   - 事务策略差异、失败路径、常见诊断与限制
7. [`07-完整示例项目模板（可复制运行）.md`](./07-完整示例项目模板（可复制运行）.md)
   - 一套从 DSL 到 apply 到 audit site 的可复制样板
8. [`08-团队内-Onboarding-清单.md`](./08-团队内-Onboarding-清单.md)
   - 30 分钟清单：环境 → dry-run → apply → registry → audit site
9. [`09-CLI-命令速查.md`](./09-CLI-命令速查.md)
   - Authoring CLI 的命令/参数/输出字段速查表
10. [`10-排障手册（CLI-Registry-Audit）.md`](./10-排障手册（CLI-Registry-Audit）.md)
   - 按“症状→检查→原因→下一步”的排障矩阵
11. [`11-Cookbook-从-DSL-到-Apply.md`](./11-Cookbook-从-DSL-到-Apply.md)
   - 按任务完成一条 DSL→Apply 的最短路径
12. [`12-Cookbook-排查一次失败的-Apply.md`](./12-Cookbook-排查一次失败的-Apply.md)
   - 按失败症状做快速 triage
13. [`13-Cookbook-生成并查看审计站点.md`](./13-Cookbook-生成并查看审计站点.md)
   - 按任务生成并查看审计静态站点
14. [`14-生产化注意事项（registry并发-事务-v2）.md`](./14-生产化注意事项（registry并发-事务-v2）.md)
   - 生产化边界、registry 并发/原子性、事务 v2 现状与升级路径
15. [`15-SDK-快速开始（Python 直接定义）.md`](./15-SDK-快速开始（Python 直接定义）.md)
   - 运行时 `Entity/Field/Identity` 声明 + `SDKStore` / `SDKRegistry` 使用

## 最短可用路径（15–20 分钟）

如果你只想先快速跑通一遍，建议按下面顺序：

1. 教程 1（环境与 CLI 检查）
2. 教程 2（用 `schema.py` 做 `preflight` + `workflow-dry-run`）
3. 教程 3（`apply-execute` 写入 registry）
4. 教程 4（`registry-show --kind apply-run` 查看执行结果）
5. 教程 5（生成 `audit_site` 并打开 authoring apply detail 页面）

## 约定

- 文中命令默认在项目根目录执行：`/Users/zhenzhili/symbolic_agent`
- CLI 使用 `python -m factpy_kernel.authoring.cli`
- JSON 输出均为“示意最小字段片段”；完整字段请以实际输出为准
- `prevalidate_no_partial_strict_v2` 当前为**最小可执行版**，并非完整 rollback/compensation 实现（详见教程 6）
- 若要在教程 4 中查看 `rule/derivation`，请先在教程 3 的“附加步骤”中一并写入 rule/derivation

## 当前能力边界（重要）

- 已支持：
  - Authoring CLI（JSON/DSL 输入）
  - `workflow-dry-run`
  - `apply-execute`
  - file registry（持久化）
  - audit static UI（静态 HTML/JSON）
- 未提供：
  - 完整前端 UI（React/Vue 等）
  - 真正 rollback/compensation 事务实现

## 维护约定（给后续维护者）

- 新增教程时，按数字前缀编号，保持“从基础到高级”的顺序
- 若教程包含稳定输出片段，优先从已有 `docs/Authoring 层契约 fixtures.md` 摘取或引用同一字段口径
- 若 CLI/DTO 字段变更，请同步检查：
  - `docs/tutorials/*.md`
  - `docs/Authoring 层契约.md`
  - `docs/Authoring 层契约 fixtures.md`
