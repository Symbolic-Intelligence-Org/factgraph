# 09 CLI

> Stub: 这是命令主题速记，不是已核验的 CLI 速查表。

当前命令入口：

- `preflight`
- `workflow-dry-run`
- `apply-execute`
- `registry-list`
- `registry-show`

当前应优先参考：

- `src/factpy_kernel/authoring/cli.py`
- `src/factpy_kernel/authoring/docs/01_overview.md`

已确认的注意点：

- `--safe` 只适用于 DSL 输入下的 `preflight` / `workflow-dry-run`
- `apply-execute` 不支持 `--safe`
- `apply_run_ids` 是 `registry-list --kind ...` 的取值，不是独立命令
- `head（auto inferred kind）` / `target + head_vars` 属于 derivation 语义，不是 CLI 子命令
