# 教程 4：Registry 只读查看与运维命令

本教程演示如何查看 file registry 的当前状态、版本列表，以及 authoring apply runs。

## 1. 列出 rule / derivation / apply runs

假设 registry 位于：

- `/.tutorial_work/registry`

### 列出 rule IDs

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/registry \
  --kind rule_ids
```

### 列出 derivation IDs

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/registry \
  --kind derivation_ids
```

### 列出 apply run IDs（按 `apply_request_id` 排序）

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/registry \
  --kind apply_run_ids
```

## 2. 查看 registry manifest / schema

### 查看 manifest

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind manifest
```

输出是 `authoring_registry_show_result`，通常可看到这些字段（示意）：

- `kind = "authoring_registry_show_result"`
- `show_kind = "manifest"`
- `item.schema`
- `item.rules`
- `item.derivations`

### 查看当前 schema entry

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind schema
```

## 3. 查看 rule / derivation（按 latest 或指定版本，需先写入对应对象）

> 只有当你之前执行过包含 rule / derivation 的 `apply-execute`，下面命令才会返回对应数据。
> 如果你目前只写入了 schema，可以先跳到“查看 apply run 明细”。

### 查看 rule 最新版本

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind rule \
  --id rules.country_rows \
  --latest
```

### 查看 derivation 最新版本

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind derivation \
  --id drv.country \
  --latest
```

如果要按版本查看，使用 `--version <version>`（且不要同时使用 `--latest`）。

## 4. 查看 apply run 明细（registry 视角）

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind apply-run \
  --id tutorial-req-001
```

你会看到一个 `authoring_registry_show_result`，其中 `item` 是 `authoring_apply_execute_run` 事件摘要，包含：

- `apply_request_id`
- `idempotency`
- `transaction`
- `status`

> 这是运维/排障的只读入口，不会修改 registry。

### 4.1 常用排障组合（推荐）

先列出所有 apply runs：

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/registry \
  --kind apply_run_ids
```

再查看某个请求：

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/registry \
  --kind apply-run \
  --id tutorial-req-with-rule-derivation
```

重点关注：

- `item.status`
- `item.idempotency`
- `item.transaction`
- `item.apply_request_id`

下一步：继续看 [`05-导出审计包与静态审计页面.md`](./05-导出审计包与静态审计页面.md)
