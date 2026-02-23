# 教程 8：团队内 Onboarding 清单（30 分钟版）

本清单面向第一次接触项目的同事。目标是在 **30 分钟内** 完成：

- 环境确认
- Authoring dry-run
- 一次真实 `apply-execute`
- 一次 registry 查看
- 一次 audit 静态页面查看

> 本清单是“执行清单”，不是完整原理文档。详细说明请回看教程 1–7。

## 0. 开始前（你需要知道）

- 当前项目已具备 MVP 闭环能力（Authoring → Apply → Registry → Audit）
- `prevalidate_no_partial_strict_v2` 当前是**最小可执行版**，不是完整严格事务实现
- `apply-execute` 不支持 `--safe`（`--safe` 仅用于 DSL 输入的 `preflight` / `workflow-dry-run`）

## 1. 环境与命令入口（5 分钟）

### 1.1 必做检查

在项目根目录执行：

```bash
cd /Users/zhenzhili/symbolic_agent
python -m factpy_kernel.authoring.cli --help
```

你应能看到至少这些子命令：

- `preflight`
- `workflow-dry-run`
- `apply-execute`
- `registry-list`
- `registry-show`

### 1.2 建立练习目录（建议）

```bash
mkdir -p /Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding/{authoring,registry,audit_pkg,audit_site,scripts}
```

## 2. 放入最小 DSL 文件（5 分钟）

### 2.1 `schema.py`

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding/authoring/schema.py`

```python
class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
```

### 2.2 `rule.py`（可选但推荐）

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding/authoring/rule.py`

```python
country_rows = Rule(
    version="v1",
    select=["E", "C"],
    body=[Pred("person:country", "$E", "$C")],
    public=True
)
```

### 2.3 `derivation.py`（可选但推荐）

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding/authoring/derivation.py`

```python
country_drv = Derivation(
    head=Person.country(person=E, country=country),
    materialize_as="fact",
    body=[Pred("person:country", "$E", "$country")],
    mode="python",
    temporal_view="record"
)
```

成功理解标准（最小）：

- 知道 Derivation 推荐写法是 `head + materialize_as`，不是把实体字段“平铺 select”。
- 知道 `head=Person.country(...)` 在 compile 阶段会 lowering 到目标谓词 `person:country`。
- 知道 lowering 后的 `head_vars` 仍按目标谓词 `arg_specs` 的位置顺序映射，`arg0` 必须对应实体槽位（变量名不要求固定为 `"$E"`）。

## 3. Dry-run 验证（5–8 分钟）

### 3.1 Preflight（应成功）

```bash
python -m factpy_kernel.authoring.cli preflight \
  --schema-dsl .tutorial_work/onboarding/authoring/schema.py \
  --rule-dsl .tutorial_work/onboarding/authoring/rule.py \
  --derivation-dsl .tutorial_work/onboarding/authoring/derivation.py
```

**成功标准（最小）**

- 输出 JSON 中 `authoring_session_dto_version` 存在
- `status` 为 `ok` 或 `warning`
- `sections.schema_preflight.status = "ok"`

### 3.2 Workflow dry-run（不写 registry）

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/onboarding/authoring/schema.py \
  --rule-dsl .tutorial_work/onboarding/authoring/rule.py \
  --derivation-dsl .tutorial_work/onboarding/authoring/derivation.py
```

**成功标准（最小）**

- `kind = "authoring_publish_workflow_bundle"`
- `session` / `publish_plan` / `apply_result` 三段都存在

## 4. 真实执行 apply（5 分钟）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/onboarding/authoring/schema.py \
  --rule-dsl .tutorial_work/onboarding/authoring/rule.py \
  --derivation-dsl .tutorial_work/onboarding/authoring/derivation.py \
  --registry-dir .tutorial_work/onboarding/registry \
  --apply-request-id onboarding-req-001 \
  --transaction-policy best_effort_no_rollback_v1
```

**成功标准（最小）**

- `apply_execute.status = "ok"`
- `apply_execute.idempotency.apply_request_id = "onboarding-req-001"`
- `apply_execute.transaction.prevalidate_before_write = true`
- 文件存在：
  - `/.tutorial_work/onboarding/registry/registry_manifest.json`
  - `/.tutorial_work/onboarding/registry/authoring_apply_events.jsonl`

## 5. 查看 registry（2–3 分钟）

### 5.1 列出 apply runs

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/onboarding/registry \
  --kind apply_run_ids
```

预期包含：

- `onboarding-req-001`

### 5.2 查看 apply run

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/onboarding/registry \
  --kind apply-run \
  --id onboarding-req-001
```

**成功标准（最小）**

- `kind = "authoring_registry_show_result"`
- `show_kind = "apply-run"`
- `item.kind = "authoring_apply_execute_run"`

## 6. 生成 audit 静态页面（5–8 分钟）

创建脚本：`/Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding/scripts/build_audit_site.py`

```python
from pathlib import Path
import shutil
import json

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

root = Path("/Users/zhenzhili/symbolic_agent/.tutorial_work/onboarding")
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

运行：

```bash
python .tutorial_work/onboarding/scripts/build_audit_site.py
```

**成功标准（最小）**

- `/.tutorial_work/onboarding/audit_site/index.html` 存在
- `/.tutorial_work/onboarding/audit_site/authoring_apply_events.html` 存在
- `/.tutorial_work/onboarding/audit_site/authoring_apply_runs/onboarding-req-001.html` 存在

## 7. 常见误区（新人最容易踩）

- **误区 1：** 对 `apply-execute` 使用 `--safe`
  - 结论：不支持。请改用 `workflow-dry-run --safe`
- **误区 2：** 认为 `prevalidate_no_partial_strict_v2` 已实现完整严格事务
  - 结论：当前是最小可执行版，未实现 rollback/compensation
- **误区 3：** 只写入 schema，却在 registry 里查询 rule/derivation
  - 结论：需要在 `apply-execute` 时同时传 `--rule-dsl` / `--derivation-dsl`

## 8. 故障上报模板（建议复制）

当你需要向维护者反馈问题时，建议附上：

```text
[Onboarding Issue]
步骤：第 X 步（命令名）
命令：<完整命令>
期望：<你期望看到的关键字段/文件>
实际：<实际现象>
apply_request_id：<如果有>
registry 路径：<路径>
附加信息：
- apply_execute.status = ...
- transaction.failure_phase = ...
- diagnostics[0].code = ...
- diagnostics[0].path = ...
```

## 9. 下一步建议

完成本清单后，建议根据角色选择后续阅读：

- 使用者：先看教程 6（事务策略与排障）
- 维护者：看 `/Users/zhenzhili/symbolic_agent/docs/Authoring 层契约.md`
- 需要完整样板：看教程 7（完整示例项目模板）
