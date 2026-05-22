# Application Rule DTO

`factgraph.application.protocol.Rule` is the application-layer Rule DTO
introduced for the rule-expression redesign. It is intentionally below the SDK
surface: SDK authoring remains responsible for ergonomic Python syntax and for
lowering user-facing DSL objects into application protocol objects.

## Shape

The DTO has five fields:

- `id`: stable non-empty rule id.
- `where`: non-empty tuple of core AST atoms from
  `factgraph.core.rules.where_ast`.
- `ports`: explicit mapping from public port names to core `Var` objects.
- `version`: optional non-empty version string.
- `desc`: optional description template using `%port_name` interpolation.

The accepted `where` atoms are `PredAtom`, `CmpAtom`, `InAtom`, `BuiltinAtom`,
and `NotAtom`. `RuleRefAtom` is rejected because the new paradigm composes
Rules through RuleExpr and port joins, not through rule-reference atoms.

## Layer Boundary

This DTO does not accept SDK DSL objects such as `LogicVar`, `ExistsAtom`,
`AttrRef`, or `CompareExpr`. The dependency direction stays:

```text
sdk -> application -> core
```

The SDK will later own ergonomic authoring syntax such as
`User(u).field == value` and lowering into the core AST shape consumed here.
Until that bridge exists, callers construct core AST atoms directly.

## Validation

Construction validates the DTO shape:

- `id`, optional `version`, and optional `desc` are non-empty strings.
- `where` is a non-empty tuple.
- `ports` is a non-empty mapping from string names to core `Var` objects.
- Every port variable appears somewhere in `where`.
- `desc` may only reference declared ports.
- Unsupported atom kinds raise `RuleValidationError`.

The DTO provides positional `atom_ids` using `<rule_id>:atom_<index>`, a
deterministic `content_digest`, shallow container immutability, and
`render_desc(...)` for template rendering.

## Immutability

`Rule` is a frozen dataclass and stores `where` as a tuple and `ports` as a
mapping proxy. This is shallow/container immutability. Core AST atoms currently
contain mutable list fields such as `PredAtom.terms`; this DTO does not
deep-freeze or clone those shipped core types.
