# T1.4 Alias / Port Contract

Status: scoped
Last Updated: 2026-05-23 (Step 4.6 scoped anchor)
Class: S

## 1. Problem

Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.6 makes `ports` the only public interface between Rules and future RuleExpr joins. It also previews occurrence aliases: the same Rule template can appear multiple times in a RuleExpr, and joins bind to an occurrence alias rather than the template itself.

T1.1 shipped `factgraph.application.protocol.Rule` with explicit `ports`. T1.2 shipped the SDK DSL bridge that constructs application Rules. T1.3 shipped top-level transitional SDK aliases. T1.4 now needs the remaining Rule-side alias and port contract substrate before T3 RuleExpr can build `rule.as_("a")`, occurrence-scoped port references, and join validation.

This slice is deliberately substrate-only. It does not implement RuleExpr composition or join semantics.

## 2. Goals

### 2.1 Parent §3.6 Port Contract

Make the shipped Rule surface document and enforce the port contract needed by later RuleExpr:

- ports are explicit; no auto-join by port name
- non-port free variables remain internal existential witnesses
- port names are the external public interface
- internal `Var.name` values do not participate in cross-Rule alignment

### 2.2 Occurrence Alias Infrastructure

Add a small immutable occurrence wrapper with default alias semantics:

```python
default_occ = rule.as_()
default_occ.alias == rule.id

occ = rule.as_("a")
occ.alias == "a"
occ.rule is rule
occ.user  # occurrence-scoped port reference for port "user"
```

The wrapper is future RuleExpr input. It does not evaluate, join, or compose by itself.

### 2.3 Port Reference Infrastructure

Add an immutable `RulePortRef` / equivalent DTO that captures:

- occurrence alias
- rule id
- port name
- port `Var`
- inferred `PortType`

This gives T3 a stable object for join constraints and inspect output without re-parsing Rule internals.

### 2.4 Alias Validation

Validate occurrence aliases at construction:

- non-empty string
- Python-identifier-like shape: `[A-Za-z_][A-Za-z0-9_]*`
- reserved leading underscore rejected for public user aliases
- omitted alias defaults to `rule.id` and is validated through the same path

Alias uniqueness across a RuleExpr remains T3 scope because T1.4 sees only one occurrence at a time.

### 2.5 Docs

Document the port / alias contract in application Rule docs and SDK-facing docs where application Rules are introduced.

## 3. Non-Goals

- Do not implement RuleExpr `&`, `|`, `.join(...)`, `.join_by_ports(...)`, or `.all` / `.any`.
- Do not implement RuleExpr alias uniqueness validation across an expression.
- Do not implement `Rule.__and__`, `Rule.__or__`, or `Rule.__bool__`.
- Do not make same-name ports auto-join.
- Do not change `Rule.ports` storage shape.
- Do not change `build_application_rule(...)` behavior except tests may assert it returns a Rule that supports `.as_(...)`.
- Do not change legacy SDK `Rule`.
- Do not touch adapters, core AST, aggregate, arithmetic, or SDK top-level naming.
- Do not introduce eval / head semantics.

## 4. Current Context

### 4.1 Parent Port / Alias Semantics

- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:160-184` defines explicit `ports` as Rule's external interface.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:185-196` says Rules interact only through RuleExpr composition + explicit port joins, same-name ports do not auto-join, and occurrence aliases distinguish repeated Rules.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:198-213` defines every-proof-path reachability for later `.join(...)`.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:773-800` states that head/RuleExpr alignment is by external port name, not internal Var name.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:805-815` gives the key example: two Rules expose external port `"user"` while using different internal Var names.

### 4.2 Track Plan

- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:114` classifies T1.4 as S-class with narrowed scope.
- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:138` scopes T1.4 to remaining alias / port contract, `.as_(...)` template-stable alias, occurrence alias validation, and RuleExpr `.as_()` infrastructure.
- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:191` marks T3.2 RuleExpr `.as_()` as dependent on T1.4 alias infrastructure.
- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:196` says T3 depends on T1.4.

### 4.3 Shipped Application Rule Ports

- `src/factgraph/application/protocol/rule.py:43-51` defines `Rule` fields including `ports: Mapping[str, Var]`.
- `src/factgraph/application/protocol/rule.py:61-63` requires non-empty `ports`.
- `src/factgraph/application/protocol/rule.py:76-87` validates port keys and values, freezes the mapping, and computes `_port_types`.
- `src/factgraph/application/protocol/rule.py:94-95` exposes `port_types`.
- `src/factgraph/application/protocol/rule.py:99-104` includes sorted `ports` in `content_digest`.

### 4.4 Shipped Port Type Inference

- `src/factgraph/application/protocol/rule.py:361-369` infers `PortType` for each port.
- `src/factgraph/application/protocol/rule.py:372-388` classifies entity-ref ports from `PredAtom(...:exists, [var])`.

### 4.5 Shipped SDK Bridge

- `src/factgraph/sdk/dsl/application_rule.py:46-82` builds application Rules.
- `src/factgraph/sdk/dsl/application_rule.py:150-168` converts SDK `ports` to core `Var` and rejects anonymous ports.
- `src/factgraph/sdk/dsl/application_rule.py:223-233` already collects variables through aggregate terms for T2.3.

### 4.6 Existing Tests

- `tests/application/protocol/test_rule.py` covers required ports, dangling port rejection, `port_types`, `render_desc`, content digest, and shallow immutability.
- `tests/application/protocol/test_rule_aggregate.py` covers aggregate-local port isolation and aggregate target ports.
- `tests/sdk/dsl/test_application_rule.py` covers bridge ports and desc rendering.

## 5. Proposed Shape

### 5.1 New DTOs

Add to `src/factgraph/application/protocol/rule.py`:

```python
@dataclass(frozen=True)
class RuleOccurrence:
    rule: Rule
    alias: str

    def port(self, name: str) -> RulePortRef: ...
    def __getattr__(self, name: str) -> RulePortRef: ...

@dataclass(frozen=True)
class RulePortRef:
    occurrence_alias: str
    rule_id: str
    port_name: str
    var: Var
    port_type: PortType
```

Export both from `src/factgraph/application/protocol/__init__.py`.

### 5.2 `Rule.as_(alias=None)`

Add:

```python
def as_(self, alias: str | None = None) -> RuleOccurrence:
    effective_alias = self.id if alias is None else alias
    return RuleOccurrence(rule=self, alias=_validate_occurrence_alias(effective_alias))
```

`Rule.as_()` with no argument uses `rule.id`, matching parent §3.6 commitment 6. `Rule.as_(...)` is template-stable: it does not mutate the Rule and repeated calls with the same alias produce equal value objects.

### 5.3 Port Access

`RuleOccurrence.port(name)` and `RuleOccurrence.__getattr__(name)` resolve only declared ports.

Rules:

- undeclared port raises `RuleValidationError`
- private attribute names beginning with `_` are not treated as ports
- normal dataclass fields (`rule`, `alias`) remain normal attributes
- `port_ref.port_type` is copied from `rule.port_types[name]`

### 5.4 Alias Validation

Use a local regex:

```python
_OCCURRENCE_ALIAS_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
```

Validation must use `re.fullmatch(_OCCURRENCE_ALIAS_RE, alias)`. This rejects empty strings, leading digits, leading underscores, punctuation, and hyphenated aliases. The narrower shape keeps public occurrence aliases distinct from future internal synthetic aliases.

### 5.5 Serialization / Digest

No `Rule.content_digest` change. Occurrence aliases are expression-level wrappers and must not affect the Rule template digest.

### 5.6 Bridge Compatibility

`build_application_rule(...)` returns the same application `Rule` class, so no bridge code change should be required. Tests should assert the returned Rule supports `.as_(...)`.

## 6. Boundaries And Invariants

- Port names, not internal `Var.name`, are the public cross-Rule interface.
- Same-name ports across Rules do not auto-join in T1.4.
- `RuleOccurrence` is an occurrence wrapper, not a Rule template replacement.
- `RulePortRef` is a reference descriptor, not a core AST term.
- `Rule.as_()` default alias is exactly `rule.id`.
- If `rule.id` is not identifier-shaped, `Rule.as_()` raises `RuleValidationError`; users must call `.as_(custom_alias)`.
- `Rule.content_digest` remains alias-independent.
- `Rule.ports` remains a frozen `MappingProxyType`.
- Application Rule remains SDK-independent.
- T3 owns expression-level alias uniqueness and join reachability validation.
- No adapter/core/SKD legacy Rule changes.

## 7. Acceptance

- `Rule.as_()` returns immutable `RuleOccurrence(rule=rule, alias=rule.id)`.
- `Rule(id="bad-rule", ...).as_()` raises `RuleValidationError` because the default alias must pass occurrence-alias validation; `.as_("good_alias")` remains valid.
- `Rule.as_("a")` returns immutable `RuleOccurrence(rule=rule, alias="a")`.
- Repeated `rule.as_("a")` calls satisfy `rule.as_("a") == rule.as_("a")`; they are not required to satisfy object identity (`is`) because T1.4 does not promise interning.
- Invalid aliases (`""`, `"1a"`, `"_a"`, `"a-b"`) raise `RuleValidationError`.
- `occ.port("user")` returns a `RulePortRef` with alias, rule id, port name, Var, and PortType.
- `occ.user` returns the same object as `occ.port("user")`.
- `occ.port("missing")` raises `RuleValidationError`; `occ.missing` raises `AttributeError` so normal Python attribute probing still behaves correctly.
- Mutating `RuleOccurrence` or `RulePortRef` fields raises `FrozenInstanceError`; both DTOs are hashable.
- `Rule.content_digest` is unchanged by occurrence alias creation.
- Two Rules exposing `"user"` with different internal Var names produce port refs with the same port name and different Vars.
- A Rule returned by `build_application_rule(...)` supports `.as_(...)`.
- Existing application/protocol and SDK DSL bridge tests pass.
- No diff under `src/factgraph/adapters/`, `src/factgraph/core/`, or legacy `src/factgraph/sdk/dsl/rule.py`.

## 8. Implementation Plan

1. Record G7 precondition:
   - `Rule` currently has no `.as_`
   - no `RuleOccurrence` / `RulePortRef` exports
   - `Rule.ports` and `port_types` shipped lines intact
   - T1.3 SDK aliases intact
2. Add DTOs and alias validation in `application/protocol/rule.py`.
3. Re-export from `application/protocol/__init__.py`.
4. Add tests in `tests/application/protocol/test_rule.py` and bridge-facing assertion in `tests/sdk/dsl/test_application_rule.py` or a focused new test.
5. Update application Rule docs and SDK aggregate/application-rule docs if needed.
6. Run targeted tests and ruff.
7. Fill §10 Outcome.
8. Archive blueprint pair.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` is deferred to T3; user-facing `.as_(...)` docs should ship with RuleExpr `&` / `|` / `.join(...)` context rather than this substrate-only slice.

## 10. Outcome

Pending implementation.
