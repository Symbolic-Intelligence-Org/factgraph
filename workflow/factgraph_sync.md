# FactGraph Repository Identity

- Status: current
- Supersedes: the `factgraph ↔ hnsm-backend` dual-repository projection runbook
- Effective: 2026-08-27
- Decision record:
  [FactGraph repository canonicalization](./blueprints/active/2026-08-27_factgraph-repository-canonicalization.md)

## Current Topology

FactGraph is one source project with one product repository:

```text
local factgraph repository
  origin -> https://github.com/Symbolic-Intelligence-Org/factgraph.git
  main   -> origin/main
  feature branches -> origin/<same branch>
```

Normal FactGraph development, review, and publication use ordinary Git branches
directly against `origin`. Do not create a clean clone, projection branch, or
path-filtered commit merely to publish FactGraph changes.

Shared AI workflow and FactGraph–Meander coordination state belong in the
separate `symbolic-workflow` repository. Their former presence in
`hnsm-backend` does not make that legacy repository a FactGraph authority.

## Stable Meander Consumption

Meander consumes an immutable wheel built from one committed FactGraph
revision. FactGraph updates reach Meander through explicit artifact promotion:

1. build a candidate wheel from a clean FactGraph commit;
2. run FactGraph release checks;
3. run Meander compatibility and product tests against the candidate wheel;
4. update the Meander dependency lock, artifact manifest, version and digests;
5. merge the coordinated update only when both projects are green.

An editable sibling checkout may support local exploration, but it is not
delivery evidence. A wheel is a FactGraph build artifact, not a separate source
project or repository.

## Historical Note

The previous runbook treated `hnsm-backend` as a private superset and projected
selected paths into a second `factgraph` remote. That topology existed so shared
workflow material had a home before `symbolic-workflow` was separated. It is
superseded and must not be used for new work. Its full procedure remains
available in Git history and in the archived
`2026-05-14_factgraph-dual-repo-workflow` blueprint for rationale only.
