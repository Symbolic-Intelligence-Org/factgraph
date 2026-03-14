# Tutorials CLI/Registry Review

## Scope

Review the `CLI/registry` tutorial group against the current implementation:

- [03-Apply-Execute-与-Registry.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/03-Apply-Execute-%E4%B8%8E-Registry.md)
- [04-Registry-只读查看与运维命令.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/04-Registry-%E5%8F%AA%E8%AF%BB%E6%9F%A5%E7%9C%8B%E4%B8%8E%E8%BF%90%E7%BB%B4%E5%91%BD%E4%BB%A4.md)
- [09-CLI-命令速查.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/09-CLI-%E5%91%BD%E4%BB%A4%E9%80%9F%E6%9F%A5.md)

Primary implementation baselines:

- [cli.py](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/authoring/cli.py)
- [registry_fs.py](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/authoring/registry_fs.py)
- [01_overview.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/authoring/docs/01_overview.md)

## Verdict

All three files are currently `stub`, not runnable guides.

They should not be used as operational documentation until rewritten.

## Findings

### `03-Apply-Execute-与-Registry.md`

Current content is only one line: `apply-execute 与 registry 工作流。`

What the implementation actually requires:

- `apply-execute` is a real subcommand
- it requires `--registry-dir`
- it also expects at least one payload input
- optional flags include `--apply-request-id` and `--transaction-policy`

Decision:

- classify as `stub`
- keep only as a placeholder topic entry
- future rewrite should include a minimal end-to-end example: `preflight/workflow/apply-execute -> registry-show`

### `04-Registry-只读查看与运维命令.md`

Current content is only one line: `registry-list / registry-show 运维。`

What the implementation actually supports:

- `registry-list --kind` only accepts:
  - `rule_ids`
  - `derivation_ids`
  - `apply_run_ids`
  - `rule_versions`
  - `derivation_versions`
- `registry-show --kind` only accepts:
  - `manifest`
  - `schema`
  - `rule`
  - `derivation`
  - `apply-run`

Decision:

- classify as `stub`
- future rewrite should document required/forbidden combinations of `--id`, `--version`, and `--latest`

### `09-CLI-命令速查.md`

This file contains real command names, but it mixes categories and omits critical constraints.

Confirmed matches:

- `preflight`
- `workflow-dry-run`
- `apply-execute`
- `registry-list`
- `registry-show`
- `--transaction-policy`
- `--safe`

Important corrections:

- `--safe` is only valid with DSL inputs on `preflight` and `workflow-dry-run`
- `apply-execute` explicitly rejects `--safe`
- `apply_run_ids` is a `registry-list --kind` value, not a top-level command
- `head（auto inferred kind）` / `target + head_vars` / `arg_specs` are derivation semantics, not CLI command surface

Decision:

- classify as `stub`
- keep only as a note sheet, not as a trusted cheat sheet

## Immediate Actions Applied

To reduce confusion before full rewrites:

- added `Stub` warning notes to `03`, `04`, and `09`
- pointed each file to the current authoritative sources in `authoring`

## Next Step

When this group is rewritten, the minimal acceptable bar should be:

1. every command example is runnable against the current `cli.py`
2. every flag example reflects current parser constraints
3. registry examples show the real file-backed layout from `FileAuthoringRegistry`
