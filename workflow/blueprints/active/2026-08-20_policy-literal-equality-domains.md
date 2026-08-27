# Task Blueprint: operator-sensitive Policy literal equality domains

- Status: implemented
- Created: 2026-08-20
- Last Updated: 2026-08-20
- Related Modules:
  - `src/factgraph/application/protocol/policy.py`
  - `src/factgraph/sdk/policy_authoring.py`
  - `src/factgraph/application/policy_runtime.py`
  - `src/factgraph/application/evaluation_run_v1_runtime.py`
  - `src/factgraph/application/evaluation_run_bundle_runtime.py`
  - `src/factgraph/application/product_explanation_data_v2.py`
- Related Docs:
  - [Q22 operator-sensitive literal decision](../../design/decisions/active/2026-08-20_q22-policy-literal-equality-domain-decision.md)
  - [Literal equality-domain audit](../../audit/active/2026-08-20_policy-literal-equality-domain-vs-shipped.md)
  - [Required preflight](../../audit/active/2026-08-20_policy-literal-equality-domains-preflight.md)
  - [Rules quickstart](../../../docs/quickstart/rules.md#policy-topology-capability-matrix)
- Audit Log:
  - [2026-08-20_policy-literal-equality-domains.audit.md](./2026-08-20_policy-literal-equality-domains.audit.md)

## 1. Problem

The public `PolicyLiteral` envelope uses the three engines' shared ordering
domains (`int` and `time`) for every comparison operator. This correctly
bounds ordering but incorrectly rejects string and bool equality even though
port-to-port and Rule-body equality already lower to the same equality family.
Entity-reference literal equality is also absent despite being a legitimate,
bounded comparison with an identity port.

## 2. Goals

- Admit canonical `string`, `bool` and `entity_ref` Policy literals for `eq`
  and `ne`.
- Keep `gt/ge/lt/le` restricted to `int` and `time` at authoring and compiler
  boundaries.
- Recompute entity-reference literals from typed `EntityRef.identity` against
  the trusted schema; never trust caller-supplied `encoded_ref`.
- Preserve existing int/time Policy node IDs, structure digests and compiled
  digests byte-for-byte for identical inputs.
- Preserve literal topology through V1 replay/bundle codecs and Product V2
  presentation.
- Prove Native/Souffle/ProbLog selected-row parity for the new equality domains.

## 3. Non-goals

- Float64, UUID or bytes Policy literals.
- Ordering for string, bool or entity references.
- Entity-port-to-entity-port comparison operators; `same()` remains the only
  public identity-unification form.
- Relationship-field literals, multi-hop navigation, coercion or literal vs
  literal comparison.
- Any change to ordinary Rule-body comparison semantics.
- Branch creation, commits, pushes or unrelated dirty-worktree cleanup.

## 4. Current Context

- `PolicyLiteral` accepts only int/time and seals domain/value into node identity.
- `_PolicyScalarHandle._compare` rejects other literal domains before considering
  the operator.
- `_resolve_compare` already applies `_ORDERING_DOMAINS` only to ordering.
- `EntityIdentityEndpoint` is currently rejected by `PolicyCompare`; supporting
  a literal requires an explicit endpoint path, not scalar relabelling.
- Generic V0 bundle wire encoding already supports strings and bools, while the
  strict V1 program codec reconstructs `PolicyLiteral` through its constructor.
- The worktree contains extensive unrelated user changes; only files enumerated
  by this blueprint may be edited for this slice.

## 5. Proposed Shape

1. Extend `PolicyLiteral.scalar_domain` additively to
   `int|time|string|bool|entity_ref`, with domain-directed canonical validation.
2. Split SDK literal admission by operator. Scalar handles infer string/bool
   literals only for equality; explicit non-orderable literals also reject
   ordering during authoring.
3. Let `PolicyEntityPortHandle ==/!= EntityRef` create a canonical entity-ref
   literal after trusted-schema identity materialization. Other entity compare
   syntax remains rejected.
4. Resolve `EntityIdentityEndpoint` explicitly as comparison domain
   `entity_ref`, allow it only opposite an entity-ref literal, and verify the
   encoded reference's entity type matches the endpoint.
5. Reuse existing `CmpAtom` lowering and wire/presentation codecs; add tests
   where their generic behavior already suffices rather than inventing a new
   DTO shape.

## 6. Boundaries And Invariants

- Existing int/time identity and digest outputs must not change.
- `float64` stays rejected for equality and ordering.
- Entity port-to-port operators do not replace `same()`.
- Caller `EntityRef.encoded_ref` is non-authoritative; identity is normalized
  and re-encoded through the active `SchemaIndex`.
- Raw IR entity-reference literals must be canonical `idref_v1` strings and
  must match the resolved endpoint entity type.
- All unsupported shapes fail before engine execution with typed Policy/SDK
  errors.
- Existing branch-total `PARTIAL_BRANCH_CONSTRAINT` behavior is unchanged.
- Historical wire DTO field names remain unchanged; `scalar_domain` is retained
  for compatibility even for the tagged `entity_ref` value.

## 7. Acceptance

- [x] Natural SDK string/bool `eq` and `ne` literals compile and execute.
- [x] Natural SDK entity-port `eq` and `ne` with `EntityRef` compile and execute.
- [x] String/bool/entity-ref ordering rejects before engine execution.
- [x] Float64/UUID/bytes literals remain rejected.
- [x] Entity port-to-port operators still direct authors to `same()`.
- [x] Entity type mismatch and forged `encoded_ref` inputs fail or normalize
      safely against the trusted schema.
- [x] Existing int/time structure/digest construction remains unchanged.
- [x] V1 replay, bundle round-trip and Product V2 topology expose new literals.
- [x] Native/Souffle/ProbLog Policy-path parity is green for all new domains.
- [x] Affected module and quickstart docs are synchronized.

## 8. Implementation Plan

1. Extend protocol literal domains and canonical value validation.
2. Add operator-sensitive scalar authoring and explicit entity-reference
   authoring.
3. Extend compiler endpoint resolution and entity-type validation while reusing
   existing `CmpAtom` lowering.
4. Add protocol/compiler/SDK negative and digest compatibility tests.
5. Add V1 replay/bundle and Product V2 presentation round-trip coverage.
6. Add real portable three-engine string/bool/entity-ref equality fixtures.
7. Update application/SDK/quickstart docs and run focused regression, Ruff and
   diff checks with the repository-pinned factpy interpreter.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `docs/quickstart/rules.md`
- Q22/audit status language after implementation is verified

## 10. Outcome / Deviations

Implemented the complete Q22 matrix in one bounded slice. String and bool use
the ordinary scalar handle path; entity references use a dedicated identity
endpoint path and are recomputed from typed identity against the trusted
schema. Existing lowering, replay/bundle codecs and Product V2 operand views
needed no new DTO shape; focused tests make their generic support explicit.

Verification completed with 82 focused tests plus 34 subtests, including real
Native/Souffle/ProbLog equality and inequality parity. The broader application
and SDK regression passed 779 tests plus 877 subtests. Ruff and targeted mypy
checks are green. The complete `policy_runtime.py` mypy invocation still
reports ten pre-existing `PolicyFunctionOccurrenceV1.children` union-attribute
errors outside the changed comparison lines; the two other changed source
modules pass mypy directly.

The slice executed in the existing non-sacred working branch because the user
requested the repair in a heavily dirty shared worktree. No branch switch,
commit, push or unrelated-worktree cleanup was performed. Archival remains a
separate lifecycle step after the user chooses how to land the shared changes.
