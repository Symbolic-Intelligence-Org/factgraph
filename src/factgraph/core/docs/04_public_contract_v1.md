# Public Contract v1 (stable external commitments)

- Scope: external behavioral constraints of `core / service / sdk`
  v1
- Status: `v1`
- Last updated: 2026-03-10

This document records only what "current code already implements
and should remain stable" as an external contract; it does not
record removed capabilities.

## 1. String DSL policy (v1)

### 1.1 service / HTTP (rules v1)

Entry points:

- `service.rules_v1.validate_rule(...)`
- `service.rules_v1.compile_rule_preview(...)`
- `/v1/rules/*` routes under `app_v1`

If a request uses string DSL, the response is:

- `ok=false`
- `errors[*].kind="string_dsl_unsupported"`

Currently covered:

- `$.rule` is a string
- `$.rule.where` is a string

### 1.2 SDK (Python)

Entry points:

- `SDKStore.run(...)`
- `SDKStore.evaluate(...)`

> **post-L SDK ergonomics redesign cross-ref (§5.5.6):** since the
> post-L redesign, `FactGraph` enters `factgraph.sdk.__all__` as a
> literal alias of `SDKStore`; the contract entry points above are
> equally reachable via `FactGraph.eval.run(...)` /
> `FactGraph.eval.evaluate(...)`. The flat `SDKStore.<method>` form
> remains the foundational anchor of the v1 contract — neither
> deprecated nor removed. Detailed design is recorded in the post-L
> SDK ergonomics redesign blueprint (an internal design record;
> §5.4 / §5.5).

String DSL is explicitly rejected with `SDKStoreError`; stable
prefixes:

- `string rule DSL is not supported in SDK v1; ...`
- `string derivation DSL is not supported in SDK v1; ...`

## 2. Declarative metadata contract (v1)

### 2.1 Entity / schema

The unified declarative metadata across the SDK and authoring
schema DSL is:

- `version`
- `description`
- `tags`

Stable points:

- `entity_type` is derived from the `Entity` class name; no
  separate `schema_id` is required
- `Entity.Meta` allows only `version / description / tags`
- `description` precedence: `Meta.description > class docstring
  fallback`
- The compiler validates and preserves these fields in the schema
  compile output

### 2.2 Rule / Derivation

Currently allowed declarative metadata for `Rule` / `Derivation`:

- `description: str`
- `tags: list[str]`

Stable points:

- For SDK objects, use top-level constructor parameters of
  `Rule(...)` / `Derivation(...)`
- For authoring payloads, use top-level keys `description` / `tags`
- The compiler validates and preserves these fields
- These fields do not change `where` validation, evaluation,
  candidate generation, or accept semantics

Compatibility note:

- `Derivation.target` remains a compatibility field; high-level
  declarations should prefer `head`

## 3. Store.evaluate mode contract (v1)

Allowed modes:

- `native`
- `souffle`
- `problog`

Removed aliases:

- `mode='python'` -> `ValueError("mode='python' is removed; use mode='native'")`
- `mode='engine'` -> `ValueError("mode='engine' is removed; use mode='souffle'")`

If the corresponding evaluator is not registered:

- raise `WhereValidationError`
- error-message format: `"{mode} evaluator not registered; import factgraph.adapters.{mode} first"`

## 4. AcceptResult diagnostics contract (v1)

Source:

- `factgraph.core.derivation.accept.AcceptResult`
- `factgraph.core.store._accept.accept_store_candidate(...)`

### 3.1 Version field

- `AcceptResult.diagnostics_contract_version == 1`

### 3.2 AcceptResult fields

Stable fields:

- `run_id`
- `accepted_count`
- `skipped_count`
- `written_assertions`
- `skipped_reason_counts`
- `diagnostics`
- `diagnostics_contract_version`
- `entity_ref`
- `candidate_id`
- `candidate_key`

### 3.3 `diagnostics[*]` shape

Each item is an object with fields:

- `code: str`
- `severity: "info" | "warning" | "error"`
- `path: str | None`
- `message: str`
- `data: dict[str, Any]`

### 3.4 Currently stable codes (already used in the store accept path)

- `accept_meta_schema_digest_unavailable`
- `accept_meta_policy_digest_unavailable`

Notes:

- New codes may be added.
- Any breaking field change must bump
  `diagnostics_contract_version`.

## 5. accept_many return contract (v1)

Source:

- `Store.accept_many(...)`
- `accept_many_candidate_sets(...)`

Each returned item has the shape:

- `candidate_id: str`
- `candidate_key: str`
- `state: str`
- `entity_ref: str | None`
- `error: None | {code: str, message: str, diagnostics?: list[dict]}`

The current `state` set (already used by the implementation):

- `ACCEPTED`
- `DUPLICATE`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`
- `BLOCKED_DEPENDENCY`

Typical `error.code` values:

- `ATOMIC_ROLLBACK`
- `ATOMIC_ABORTED`
- `BLOCKED_DEPENDENCY`
- `DUPLICATE_NOT_ALLOWED`
- or a prefix derived from an exception (e.g.
  `IDENTITY_INCOMPLETE`, `INVALID_TERM`)

Pre-failure notes:

- When `mode` is not `atomic|best_effort`, the current
  implementation raises `WriteProtocolError` directly and does not
  return per-item results
- When the candidate dependency graph contains a cycle, the
  current implementation raises
  `WriteProtocolError("CANDIDATE_DEPENDENCY_CYCLE: ...")` directly
  and does not return per-item results

## 6. ProjectorAudit contract (v2)

Source:

- `factgraph.core.view.projector.ProjectorAudit`
- `project_view_facts_with_audit(...)`

Version:

- `ProjectorAudit.contract_version == 2`

Fields:

- `predicate_count: int`
- `active_claim_count: int`
- `selected_claim_count: int`
- `selected_by_pred: dict[str, int]`
- `dropped_by_policy_count: int`

Notes:

- `project_view_facts(...)` does not carry audit fields.
- `project_view_facts_with_audit(...)` returns `(facts, audit)`.
- The current projector does not support a
  `legacy_record_visibility` parameter.

## 7. Compatibility surface and change process

Current compatibility entry points (kept but new dependencies are
discouraged):

- `factgraph.core.store.api`
- `Store.evaluate_dummy(...)` (deprecated)

Change-process constraints:

1. Update the contract description in this document first.
2. Update / add regression tests next.
3. Modify the implementation last.
