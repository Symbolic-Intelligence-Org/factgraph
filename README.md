# factpy-kernel

**Append-only fact substrate and auditable reasoning kernel.**

> Language: **中文** | [English](README.en.md)

`factpy-kernel` 的 v0.1 开源 / PyPI surface 只包含 `kernel` 主体。它提供:

- append-only fact ledger 与 field/assertion 写入语义
- canonical Python runtime authority: `kernel.application`
- Python product surface: `kernel.sdk`
- rule / query / derivation authoring 与 runtime adapter
- audit package reader、query、DTO 与 evidence graph

v0.1 公开源码与 PyPI wheel 都以 kernel-only surface 为准。LLM extraction、HTTP delivery、domain bundles 等 companion surfaces 不属于 `factpy-kernel` v0.1 发布内容。

架构原则见 [docs/architecture_principles.md](docs/architecture_principles.md)。

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

## Quickstart

```python
from kernel.sdk import Entity, Field, Identity, FactGraph


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


fg = FactGraph.from_schema_classes([User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.name, alice, "Alice")

snapshot = fg.read.get(User, user_id="u-1")
print(snapshot.name)  # Alice
```

`FactGraph` 是 v0.1 SDK 的顶层入口,通过 8 个 taxonomy namespace (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`) 教学概念分层。`FactGraph` 是 `SDKStore` 的别名 (literal alias),flat 形式 `fg.ref(...)` / `fg.set(...)` / `fg.get(...)` 与 nested 形式同样受支持,作为 **foundational API**——既不被弃用也不会移除。

`kernel.sdk` 是面向用户的 Python product surface。运行时权威在 `kernel.application`;SDK 负责把 ergonomic API、schema/DSL authoring、snapshot/batch/editor 等 outward objects adapter 到 application runtime contract。

## 选择使用层

| 场景 | 推荐入口 | 原因 |
|---|---|---|
| 人写 Python product code、定义 `Entity` / `Field`、跑 query / derivation | `kernel.sdk` | 提供 descriptors、DSL sugar、snapshot、batch、editor 与用户友好的异常 |
| automation process / HTTP bridge / wire protocol,需要接收 JSON-like request | `kernel.application` protocol + executor | 接收 SDK-independent DTO,不要求调用方持有 SDK `Field` descriptor 或 Python DSL object |
| 需要最低层 ledger / evidence / rule primitive | `kernel.core` | 适合 runtime implementer,不是普通用户入口 |
| 读取已导出的 audit package | `kernel.audit` | 离线 reader/query/DTO/evidence consumer surface |

## v0.1 Public Boundary

| Tier | Surface | Commitment |
|---|---|---|
| Product public | `kernel.sdk` | 面向人写 Python product code 的 ergonomic API 与 outward compatibility surface。 |
| Advanced importable | `kernel.application`, `kernel.audit` | 面向 automation、wire bridge、audit consumer 的 runtime/query authority；可直接 import,但不是 SDK ergonomic facade。 |
| Out of v0.1 package | `service`, `agent`, `domains`, internal workflow docs, tutorial/demo add-back candidates | 不属于 `factpy-kernel` v0.1 kernel-only wheel / public source surface。 |

Batch 3-7 新增的 Check、Diagnose、Fact Overlay、ProofFrame、Why-not、rule-action runtimes、round events 与 ProofFrame diff 当前通过 `kernel.application` / `kernel.audit` 暴露为 advanced importable surfaces。v0.1 不新增对应 SDK shell 或 HTTP route；需要 product-facing wrapper 时应先定义单独的 public API blueprint。

## Kernel Surface

| Area | Entry | Notes |
|---|---|---|
| SDK product API | `kernel.sdk` | Entity / Field / Identity / FactGraph (与别名 SDKStore) / Query / Derivation 等用户入口 |
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

## 测试

kernel-only package guard:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_wheel_kernel_only_packaging.py"
```

kernel 回归:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
```

当前 kernel suite 基线:709 tests, 1 skip。

## 许可证与安全

本项目代码以 Apache License 2.0 发布,见 [LICENSE](LICENSE)。

Secret 处理、API key 轮换见 [docs/SECURITY.md](docs/SECURITY.md)。
