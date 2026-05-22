# Working(临时工作区)

短生命周期 artifact 的临时工作区:实验脚本、ad-hoc 测试输出、探索性数据、prototype 代码。

## 生命周期

- 内容**全部 gitignored**(per Step 0.1 的 `.gitignore` `workflow/working/*` 规则)。只有本 README 和 `.gitkeep` 被跟踪。
- 短生命周期:小时-数天;不跨 session 持久。
- 与 `/tmp/` 区别:project-scoped,跨 reboot 持久。
- 与 `workflow/heritage/` 区别:heritage 是永久 legacy 归档;working 是临时易逝。

## 什么进来

- 还没值得打包成 skill 的一次性脚本
- 调试中的测试输入 / 输出
- Notebook scratch
- 调试时的 API response captures
- 还没准备进 `src/` 的 prototype 代码

## 什么不进来

- 持久工作产物(→ 相应模块 / docs)
- 参考材料(→ obsidian / `workflow/heritage/`)
- 模块实现真相(→ `src/factgraph/*/docs/`)

## 约定

如果一个 working artifact 证明有价值,把它包成 Claude skill 或通过正式 slice 提升到持久位置。否则随时可安全删除。

无 `Status` 字段,无 metadata,无 governance — 这是自由格式工作区。
