# factpy-kernel

**Append-only fact substrate and auditable reasoning kernel.**

> Language: **中文** | [English](README.en.md)

`factpy-kernel` 的 v0.1 开源 / PyPI surface 只包含 `kernel` 主体。它提供:

- append-only fact ledger 与 field/assertion 写入语义
- canonical Python runtime authority: `kernel.application`
- Python product surface: `kernel.sdk`
- rule / query / derivation authoring 与 runtime adapter
- audit package reader、query、DTO 与 evidence graph

当前仓库仍是 monorepo。`agent`、`service`、`domains` 是私有 / companion surface,用于内部开发、HTTP delivery、LLM extraction 与 ECSS domain bundle；它们不属于 v0.1 PyPI wheel,也不应被当作 kernel-only OSS 安装目标。

架构原则见 [docs/architecture_principles.md](docs/architecture_principles.md),文档索引见 [docs/README.md](docs/README.md),贡献者工作流见 [AGENTS.md](AGENTS.md)。

## 安装

发布后:

```bash
pip install factpy-kernel
```

从源码使用 kernel:

```bash
git clone <repo-url>
cd hnsm-backend
pip install -e .
```

开发整个 monorepo,包括私有 companion surfaces 和测试依赖:

```bash
pip install -r requirements/dev.txt
```

`requirements/dev.txt` 会安装 service、agent、documents、extraction、observability 等内部开发依赖。其中 PyMuPDF / PyMuPDF4LLM 属 private agent document parser surface,不出现在 `factpy-kernel` 的 PyPI metadata 中。

## Quickstart

```python
from kernel.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


sdk = SDKStore.from_schema_classes([User])

alice = sdk.ref(User, user_id="u-1")
sdk.set(User.name, alice, "Alice")

snapshot = sdk.get(User, user_id="u-1")
print(snapshot.name)  # Alice
```

`kernel.sdk` 是面向用户的 Python product surface。运行时权威在 `kernel.application`;SDK 负责把 ergonomic API、schema/DSL authoring、snapshot/batch/editor 等 outward objects adapter 到 application runtime contract。

## Kernel Surface

| Area | Entry | Notes |
|---|---|---|
| SDK product API | `kernel.sdk` | Entity / Field / Identity / SDKStore / Query / Derivation 等用户入口 |
| Runtime authority | `kernel.application` | read/write/query/ingest/derivation protocol DTO + executor |
| Core primitives | `kernel.core` | ledger、rules、evidence、candidate support、low-level store semantics |
| Authoring | `kernel.authoring` | rule/schema authoring helpers and validation surfaces |
| Adapters | `kernel.adapters` | optional engine integration surfaces,depending on installed third-party engines |
| Audit | `kernel.audit` | exported audit package reader/query/DTO/evidence graph consumer contract |

更详细的当前实现文档:

- [src/kernel/sdk/docs/README.md](src/kernel/sdk/docs/README.md)
- [src/kernel/application/docs/README.md](src/kernel/application/docs/README.md)
- [src/kernel/core/docs/01_architecture.md](src/kernel/core/docs/01_architecture.md)
- [src/kernel/audit/docs/README.md](src/kernel/audit/docs/README.md)
- [src/kernel/adapters/docs/README.md](src/kernel/adapters/docs/README.md)
- [src/kernel/authoring/docs/README.md](src/kernel/authoring/docs/README.md)

## Audit And Optional Domains

`kernel.audit` 读取已经导出的 audit package,并提供 run / candidate / rule trace / evidence graph 等离线查询。

ECSS compliance matrix row assembly 属于 `domains.ecss.compliance`,不是 kernel-only wheel 的必备能力。为兼容 monorepo caller,`AuditQuery.list_compliance_matrix(...)` 仍保留为 optional-domain convenience;缺少 `domains.ecss` 时会抛出 `AuditOptionalDomainError`,而不是隐式要求 kernel 安装 domain package。

## Monorepo Companion Surfaces

这些目录存在于仓库中,但不属于 v0.1 PyPI wheel:

| Surface | Purpose |
|---|---|
| `agent` | LLM document extraction,workflow/session helpers,agent HTTP app |
| `service` | FastAPI delivery for runtime/rules/registry and audit static UI |
| `domains` | Domain bundles such as ECSS compliance presets and helpers |

使用这些 companion surfaces 时,按 monorepo 开发路径安装:

```bash
pip install -r requirements/dev.txt
```

## 测试

kernel-only package guard:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_wheel_kernel_only_packaging.py"
```

完整 monorepo 回归分 5 段:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/agent/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/service/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/domains/ecss/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s tools/benchmarks/tests -p "test_*.py"
```

当前 branch 基线:1097 tests,3 skips。

## 许可证与安全

本项目代码以 Apache License 2.0 发布,见 [LICENSE](LICENSE)。

Secret 处理、API key 轮换见 [docs/SECURITY.md](docs/SECURITY.md)。
