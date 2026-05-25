# D14 Decision: T4 Rule Projection Sugar

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks `Rule.projection(*port_names)` shape for T4.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` Q5, F2, F4, F5, and §6 C56 triage.
  - D11 `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md` §4.1, §4.5, and §4.7.
  - D12 `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md` §4.1-§4.8.
  - D13 `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md` §4.1-§4.9.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.7 and C56.
  - Shipped `src/factgraph/application/protocol/rule.py:35-39`, `:47-108`, `:125-127`, `:226-230`, and `:456-489`.
  - Shipped `src/factgraph/core/rules/where_ast.py:13-64`.
  - T3L.3 archived blueprint `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md` §10.
- Outputs / Downstream:
  - D15 closed-head validation treats projection heads as closed by construction once D12 declared-port validation succeeds.
  - Stage 3 T4 synthesis and per-slice blueprints.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md`
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
- Depends on: D11, D12, and D13 reviewed.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C56 wants:

```python
head = Rule.projection("user", "state")
fg.eval.evaluate(expr, head=head)
```

as pure same-name projection sugar.

The parent example shows an empty `where=[]`, but shipped application `Rule` rejects empty `where` and requires every `ports` variable to appear in `where`. Shipped `Rule.port_types` are inferred from `where`, so a projection helper cannot know whether a requested port is `entity_ref` or `value` without the D12 declared-port map.

D14 decides the concrete projection representation under those shipped invariants.

## 2. Scope

This decision locks:

- public `Rule.projection(*port_names)` arity and argument validation;
- the internal representation returned by the helper;
- how projection heads satisfy shipped `Rule.where` non-empty validation;
- how projection heads interact with D12 declared ports and `PortType`;
- how projection heads interact with D13 external-head body materialization;
- identity, digest, and error-bucket behavior for projection heads;
- v1 rename deferral.

## 3. Non-Scope

This decision does not lock:

- keyword rename syntax such as `Rule.projection(out_user="user")`;
- public `expr.declared_ports`;
- public projection DTOs;
- T5 result/evidence surfaces;
- closed-head literal validation details beyond projection-head closure;
- adapter grammar changes;
- output post-processing helpers.

## 4. Decision

### 4.1 `Rule.projection(*port_names)` is public same-name projection sugar

T4 should add a public classmethod:

```python
Rule.projection(*port_names: str) -> Rule
```

The v1 API accepts only positional string port names. It rejects:

- no port names;
- non-string port names;
- empty port names;
- duplicate port names.

The returned value is an application `Rule`, not a new public DTO.

Rename syntax is deferred. Users who need output renaming must post-process result rows or construct an explicit head `Rule` manually.

### 4.2 Projection heads use a private recognizable Rule shape

`Rule.projection(...)` returns a normal `Rule` object that satisfies shipped `Rule` construction invariants, but T4 lowering recognizes it as a projection head through an exact private shape.

Minimum private shape:

- deterministic private `Rule.id` derived from the ordered port-name tuple;
- `ports` maps each requested output name to a generated private `Var`;
- `where` is non-empty and contains generated placeholder atoms that mention every generated port `Var`;
- placeholder atoms carry implementation-recognizable projection metadata, for example `Origin(source="authoring", path="Rule.projection")` plus exact shape checks.

Exact helper names and generated variable names are private.

This is a representation compatibility device, not user-visible semantics.

### 4.3 Placeholder body atoms are validation-only and not materialized as filters

Projection placeholder atoms exist only to satisfy shipped `Rule.where` and `ports` validation.

When T4 lowering recognizes a projection head, it must not materialize those placeholder atoms as external head body filters. A projection head contributes:

- output port names;
- D12 declared-port validation requirements;
- D13 head-port link equality atoms.

It contributes no additional user body constraints.

Therefore `Rule.projection("user")` is equivalent to "project the expression-declared `user` port", not "filter by a generated tautology".

### 4.4 Projection port types come from D12 declared ports, not placeholder `Rule.port_types`

Because `Rule.projection(...)` has no expression context, its placeholder `where` cannot infer correct `PortType` values for requested ports.

D14 locks a projection-specific validation rule:

- D12 declared-port validation remains authoritative;
- each projection port name must exist in the D12 declared-port map;
- each projected output column inherits the D12 declared `PortType`;
- placeholder `Rule.port_types` are ignored for projection-head alignment.

This is the only T4 exception to ordinary `head.port_types` alignment. It applies only to exact projection-head values created by `Rule.projection(...)`.

Explicit user-authored head Rules still use their own `head.port_types` per D12/D13.

### 4.5 Projection heads bypass D11 existing-head identity matching

Projection heads are not existing expression heads and must not be matched by id + content digest against expression occurrences.

Therefore:

- D11 stale same-id / version warning logic does not apply to projection heads;
- the generated private projection id is not user identity;
- projection heads always use the D12 projection validation path;
- projection heads use D13 head-port link semantics without external head body filters.

This avoids accidental matching if an expression occurrence happens to share an implementation-generated id.

### 4.6 Projection heads are closed by construction after D12 validation

A projection head has no user-authored body constraints.

After D12 validates every projected port name as branch-total and unambiguous, D15 may treat projection heads as closed by construction:

- there are no extra head body variables to close;
- output schema is exactly the requested port-name tuple;
- D13 head-port links bind each output port to a declared expression source.

D15 still owns the general closed-head algorithm for explicit head Rules.

### 4.7 Projection output order preserves argument order

`Rule.projection("user", "state")` preserves the order supplied by the user for the head `ports` mapping and downstream row payload construction where ordering matters.

Validation still treats names as a set for duplicate detection and D12 membership, but public output should remain stable in argument order.

### 4.8 Projection digest is deterministic but not semantic identity

Projection-head `Rule.content_digest` remains whatever shipped `Rule` computes from the private placeholder shape.

T4 must not use that digest as user semantic identity. Projection semantic identity is the ordered tuple of requested port names plus the D12 declared-port validation context.

This preserves shipped digest behavior without making placeholder implementation details part of public semantics.

### 4.9 Projection failures use existing error buckets

Construction-time projection argument errors use `RuleValidationError`, because `Rule.projection(...)` is an application `Rule` constructor helper.

Evaluation-time projection validation errors use `RuleExprError`:

- requested port not in D12 declared-port map;
- requested port not branch-total;
- requested port ambiguous across unjoined same-name sources;
- D12 `PortType` conflict for the requested name.

Public SDK call-shape errors remain `SDKStoreError` per D11/D6. D14 does not add a new public error subclass.

## 5. Rejected Alternatives

### Option A: Relax `Rule.where` globally to allow empty projection Rules

- **Why rejected**: broadens the application `Rule` DTO beyond projection sugar and risks existing assumptions that `where` is non-empty.

### Option B: Allow empty `where` only when `Rule.id` has a projection prefix

- **Why rejected**: still complicates the core `Rule` invariant and makes id string shape control validation.

### Option C: Add a public `ProjectionHead` DTO

- **Why rejected**: violates T4 narrow-public-api discipline and D11's "head remains application Rule" scope.

### Option D: Infer all projection ports as value ports

- **Why rejected**: entity-ref declared ports would fail D12 `PortType` equality despite being valid projection targets.

### Option E: Infer all projection ports as entity-ref ports

- **Why rejected**: value declared ports would fail D12 `PortType` equality despite being valid projection targets.

### Option F: Materialize placeholder atoms as real head body filters

- **Why rejected**: projection sugar is supposed to be pure projection. Placeholder atoms are a shipped-invariant compatibility device and must not affect evaluation semantics.

### Option G: Require `Rule.projection(expr, *port_names)` with expression context

- **Why rejected**: changes parent C56 ergonomics and couples construction to a specific expression before `evaluate(...)`.

### Option H: Implement rename syntax in v1

- **Why rejected**: parent C56 explicitly defers rename to v2. D12/D13 are already complex enough without public rename semantics.

## 6. Supporting Evidence

- Shipped `Rule.__post_init__` requires non-empty `where`.
- Shipped `Rule.__post_init__` requires non-empty `ports`.
- Shipped `Rule.__post_init__` requires every `ports` `Var` to appear in `where`.
- Shipped `Rule.port_types` are inferred from `where`, so projection sugar lacks enough context for ordinary `PortType` inference.
- D12 provides the correct declared-port names and `PortType`s for projection validation.
- D13 already defines head-port link equality atoms that can bind projection outputs without a user-authored head body.
- Parent C56 restricts v1 projection to same-name positional port names and defers rename.
- T3L.3 public success result remains `list[CandidateSet]`; D14 does not change result shape.

## 7. Consequences

### 7.1 Downstream unblocking

D14 unblocks:

- D15 closed-head validation, because projection heads now have a concrete closed-by-construction model.
- Stage 3 T4 synthesis, because the last non-closed-head C52-C60 representation conflict is resolved.
- T4 implementation blueprints, because `Rule.projection(...)` can be implemented without relaxing `Rule.where`.

### 7.2 Implementation constraints

Future implementation should:

- add `Rule.projection(...)` as a `Rule` classmethod;
- keep the recognizer private;
- avoid exporting projection DTOs;
- never materialize projection placeholder atoms;
- copy projection `PortType` values from D12 declared ports;
- preserve argument order in output;
- reject rename syntax until a later decision.

### 7.3 Stage 3 gating

Stage 3 synthesis must ensure any projection implementation blueprint tests:

- no-argument, duplicate, and non-string projection construction errors;
- projection of all D12-declared ports;
- projection subset of D12-declared ports;
- undeclared projection port rejection;
- entity-ref and value port projection;
- placeholder atoms not appearing in final materialized branch bodies;
- projection output order preservation;
- no public result-shape or DTO changes.

## 8. Acceptance Criteria

- [ ] D15 cites D14 for projection-head closed-by-construction behavior.
- [ ] `Rule.projection(*port_names)` returns an application `Rule`, not a public DTO.
- [ ] Projection construction rejects empty, non-string, empty-string, and duplicate port names.
- [ ] Projection heads satisfy shipped `Rule.where` non-empty validation without relaxing the global invariant.
- [ ] Projection placeholder atoms are not materialized as evaluation filters.
- [ ] Projection validation uses D12 declared-port names and `PortType`s.
- [ ] Projection heads bypass D11 existing-head id/digest matching.
- [ ] Projection output order follows argument order.
- [ ] Rename syntax remains deferred.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T4 Stage 1 audit Q5/F2 and parent C56 mapped to D14. D14 chooses a private recognizable projection-head Rule shape that preserves shipped `Rule.where` invariants while using D12 declared ports for semantic validation. |
| 2026-05-25 | reviewed | Claude Step 4.2 v1 clean | D14 substrate sound; WC1 projection recognizer spoofing detail deferred to implementation blueprint contract; D15 unblocked. |
