# factgraph

**Append-only fact substrate and auditable reasoning kernel.**

The FactGraph source and distribution surface is the `factgraph` package. It provides:

- an append-only fact ledger and field/assertion write semantics
- the canonical Python runtime authority: `factgraph.application`
- the Python product surface: `factgraph.sdk`
- rule / inference authoring, evaluation, and runtime adapters
- Product Rule / Policy / Function authoring, typed Query, run-local Scenario,
  target-pinned execution profiles, structured Result/Explain, and replay
- audit package reader, query, DTO, and evidence graph surfaces

The public source and PyPI wheel are scoped to the FactGraph package
surface. LLM extraction, HTTP delivery, domain bundles, and other companion
surfaces are not part of the `factgraph` release.

> **Package rename in v0.2.0-rc.1**
>
> The PyPI package was renamed from `factpy-kernel` to `factgraph`. The Python
> import path is already `factgraph.*`, so user code imports do not change.
> Migrate an existing environment with:
>
> ```bash
> pip uninstall factpy-kernel
> pip install factgraph
> ```

For implementation architecture, see the module documentation links below.

## Install

The latest stable release is `0.3.0`; the current prerelease line is `0.4.0rc1`.
`main` carries current development, and [GitHub Releases](https://github.com/Symbolic-Intelligence-Org/factgraph/releases)
record published artifacts and their source identities. Consumers
using a retained wheel should keep its exact version and hash until their
compatibility checks and coordinated promotion complete. See
[release and compatibility guidance](docs/releases.md) and
[repository history](docs/repository-history.md).

Install the published release:

```bash
pip install factgraph
```

Use the kernel from source:

```bash
git clone https://github.com/Symbolic-Intelligence-Org/factgraph.git
cd factgraph
pip install -e .
```

## Quickstart

```python
from factgraph.sdk import Entity, Field, Identity, FactGraph


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])

alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.name, alice, "Alice")
fg.fields.add(User.tags, alice, "engineer")

snapshot = fg.entities.get(User, user_id="u-1")
print(snapshot.name)  # Alice
```

`FactGraph` is the SDK top-level entrypoint. Its current data namespaces are
`entities`, `fields`, `assertions`, `schema`, `assertion_views`, `eval`,
`audit`, `package`, and `meta`. Product authoring/execution additionally uses
`rule_builder` / `build_rule`, `function_builder` / `build_function`,
`policy_builder` / `build_policy`, `scenario`, `execution`, and `problog`.

`factgraph.sdk` is the user-facing Python product surface. Runtime authority
lives in `factgraph.application`; the SDK adapts ergonomic APIs, schema/DSL
authoring, snapshots, batches, editors, and compatibility errors into the
application runtime contract.

Continue with the [quickstart index](docs/quickstart/README.md) or go directly
to the [complete Product V2 workflow](docs/quickstart/product_workflow_v2.md)
for Rule/Policy/Function authoring, typed Query, Scenario, execution profiles,
structured Result/Explain data, and replay.

## Choose Your Layer

| Scenario | Recommended entry | Why |
|---|---|---|
| Human-authored Python product code defining `Entity` / `Field` and evaluating rules | `factgraph.sdk` | Provides descriptors, DSL sugar, snapshots, batches, editors, and user-facing exceptions |
| Automation process / wire protocol receiving JSON-like requests | `factgraph.application` protocol + executor | Accepts SDK-independent DTOs and does not require SDK `Field` descriptors or Python DSL objects |
| Lowest-level ledger / evidence / rule primitives | `factgraph.core` | Intended for runtime implementers, not as the normal user entrypoint |
| Reading an exported audit package | `factgraph.audit` | Offline reader/query/DTO/evidence consumer surface |

## Public Boundary

| Tier | Surface | Commitment |
|---|---|---|
| Product public | `factgraph.sdk` | Ergonomic API and outward compatibility surface for human-authored Python product code. |
| Advanced importable | `factgraph.application`, `factgraph.audit` | Runtime/query authority for automation, wire bridges, and audit consumers; importable directly, but not an SDK ergonomic facade. |
| Out of package | service, agent, domain bundles, internal workflow state | Not owned by the `factgraph` package or source repository. |

The compatibility surface retains `Rule` / `RuleExpr`, `EvaluateResult`,
legacy engine configs, evidence/explanation envelopes, Database attach,
durable views, and property-style assertion records. The additive Product V2
path adds resolved Product Rules, Product Policies, peer Product Functions,
typed Query/Scenario execution, structured Outcome/Explain and detached
replay. Legacy candidate accept, direct check/diagnose/why-not shells, and
method-level `view=` are not part of the public SDK path.

## Kernel Surface

| Area | Entry | Notes |
|---|---|---|
| SDK product API | `factgraph.sdk` | Entity / Field / Identity / FactGraph / Rule / RuleExpr / Inference / Database user entrypoints |
| Runtime authority | `factgraph.application` | read/write/evaluate protocol DTOs and executors |
| Core primitives | `factgraph.core` | ledger, rules, evidence, store, Database/view identity, low-level semantics |
| Authoring | `factgraph.authoring` | rule/schema authoring helpers and validation surfaces |
| Adapters | `factgraph.adapters` | optional engine integration surfaces, depending on installed third-party engines |
| Audit | `factgraph.audit` | exported audit package reader/query/DTO/evidence graph consumer contract |

Current implementation docs:

- [src/factgraph/sdk/docs/README.md](src/factgraph/sdk/docs/README.md)
- [src/factgraph/application/docs/README.md](src/factgraph/application/docs/README.md)
- [src/factgraph/core/docs/01_architecture.en.md](src/factgraph/core/docs/01_architecture.en.md)
- [src/factgraph/audit/docs/README.md](src/factgraph/audit/docs/README.md)
- [src/factgraph/adapters/docs/README.md](src/factgraph/adapters/docs/README.md)
- [src/factgraph/authoring/docs/README.md](src/factgraph/authoring/docs/README.md)

## Audit

`factgraph.audit` reads exported audit packages and provides offline queries for
runs, candidates, rule traces, evidence graphs, and related DTOs.

## Tests

Release-focused G7 preservation gate:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation
```

Focused assertion-access gate:

```bash
PYTHONPATH=src python -m unittest tests.test_sdk_assertion_record_set_view_filters
```

The current release suite baseline is tracked by CI and blueprint audit records;
local environments may show additional environment-only errors for optional
adapters or cold-start import order.

## License And Security

This project is licensed under the Apache License 2.0; see [LICENSE](LICENSE).

Secret handling and API key rotation: [docs/SECURITY.md](docs/SECURITY.md).
