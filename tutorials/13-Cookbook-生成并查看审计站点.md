# 教程 13：Cookbook｜生成并查看审计站点（Audit Static UI）

本篇按“我已经有 registry / apply events，现在要生成并查看审计站点”的任务路径组织。

## 目标

- 生成 `audit package`
- 注入 `authoring_apply_events.jsonl`
- 生成 `audit_site`
- 打开并查看 `authoring_apply_runs/<req>.html`

## 1) 前置条件

你需要至少完成过一次：

- `apply-execute`（以便得到 `registry/authoring_apply_events.jsonl`）

建议先跑过：

- 教程 3 或 教程 7

## 2) 准备最小脚本（可复制）

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/cookbook_audit_site/build_audit_site.py`

```python
from pathlib import Path
import json
import shutil

from factpy_kernel.authoring.schema_compile import compile_authoring_schema_v1
from factpy_kernel.export.package import ExportOptions, export_package
from factpy_kernel.store.api import Store
from factpy_kernel.audit.static_ui import render_audit_static_site

authoring_schema = {
    "entities": [
        {
            "entity_type": "Person",
            "identity_fields": [{"name": "source_id", "type_domain": "string"}],
            "fields": [{"py_name": "country", "name": "country", "type_domain": "string", "cardinality": "functional"}]
        }
    ]
}

root = Path("/Users/zhenzhili/symbolic_agent/.tutorial_work/cookbook_audit_site")
registry_dir = root / "registry"
pkg_dir = root / "audit_pkg"
site_dir = root / "audit_site"

schema_ir = compile_authoring_schema_v1(authoring_schema)
store = Store(schema_ir=schema_ir)
export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))

events_path = registry_dir / "authoring_apply_events.jsonl"
if events_path.exists():
    shutil.copyfile(events_path, pkg_dir / "authoring_apply_events.jsonl")

print(json.dumps(render_audit_static_site(pkg_dir, site_dir), ensure_ascii=False, indent=2))
```

## 3) 运行前检查

确保存在：

- `/.tutorial_work/cookbook_audit_site/registry/authoring_apply_events.jsonl`

如果不存在，先执行一次 `apply-execute`，或从你的示例目录复制过去。

## 4) 执行生成

```bash
cd /Users/zhenzhili/symbolic_agent
python .tutorial_work/cookbook_audit_site/build_audit_site.py
```

预期输出（示意）：

- `audit_ui_site_version`
- `index`
- `authoring_apply_events`
- `authoring_apply_runs`
- `ui_index`

## 5) 查看页面（推荐顺序）

### 5.1 直接打开文件（最简单）

- `/.tutorial_work/cookbook_audit_site/audit_site/index.html`
- `/.tutorial_work/cookbook_audit_site/audit_site/authoring_apply_events.html`

### 5.2 本地 HTTP 服务（可选）

```bash
cd /Users/zhenzhili/symbolic_agent/.tutorial_work/cookbook_audit_site/audit_site
python -m http.server 8000
```

打开：`http://127.0.0.1:8000/`

## 6) 快速定位某个请求（推荐）

如果你知道 `apply_request_id`（例如 `req-001`）：

1. 打开 `authoring_apply_events.html` 查看是否出现该请求
2. 打开 `authoring_apply_runs/req-001.html`
3. 查看：
   - `execution_path`
   - `execution_path_label`
   - `Idempotency`
   - `Transaction`
   - `failure_summary`

## 7) 常见问题

### Q1：`authoring_apply_runs/` 目录为空

通常是因为：

- 没有把 `registry/authoring_apply_events.jsonl` 复制到 `audit_pkg/`
- `apply-execute` 没有成功写入事件

### Q2：站点里只有 authoring apply 页面，`runs/decisions` 基本为空

这是正常的（如果你导出的 `Store` 是空 store）。本 Cookbook 重点是 authoring apply 的审计可视化。

## 8) 关联教程

- 完整模板：[`07-完整示例项目模板（可复制运行）.md`](./07-完整示例项目模板（可复制运行）.md)
- 排障矩阵：[`10-排障手册（CLI-Registry-Audit）.md`](./10-排障手册（CLI-Registry-Audit）.md)
- 事务与失败路径：[`06-事务策略与排障（v1/v2）.md`](./06-事务策略与排障（v1-v2）.md)

