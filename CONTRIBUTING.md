# Contributing to FactGraph

Thank you for your interest in contributing to FactGraph.

FactGraph is currently in an early release phase. We welcome bug reports, documentation improvements, tests, and focused pull requests that keep the public API stable and well documented.

## Development setup

Clone the repository and install the Pixi workspace:

```bash
git clone https://github.com/Symbolic-Intelligence-Org/factgraph.git
cd factgraph
pixi install
````

Run tests:

```bash
pixi run test
```

Build the package:

```bash
pixi run build
```

## Pull requests

Before opening a pull request, please make sure that:

* the test suite passes,
* public API changes are documented,
* new behavior is covered by tests where reasonable,
* the change is focused and does not mix unrelated refactors.

## Branches

Use descriptive branch names, for example:

```text
fix/schema-validation
docs/quickstart
feature/inference-api
```

Release preparation happens on `release/*` branches.

## Public API

FactGraph treats the documented SDK surface as the public contract. Changes to public imports, method names, or return types should be made deliberately and documented in the changelog.

## Code of Conduct

By participating in this project, you agree to follow our Code of Conduct.

