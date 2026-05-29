# Slice 1 — Form I Schema Refactor

- Status: draft
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Slice: 1 of identity-as-claim Step 1 ladder (per synthesis `d0036e1f`)
- Class: M/L boundary
- Related Modules:
  - `src/factgraph/sdk/schema.py`
  - `src/factgraph/authoring/schema_dsl_parse.py`
  - `src/factgraph/authoring/schema_compile.py`
  - `src/factgraph/authoring/where_schema_lowering.py`
  - `src/factgraph/authoring/derivation_compile.py`
  - `src/factgraph/application/schema_runtime.py`
  - `src/factgraph/application/protocol/schema_runtime.py` (`EntitySelector`)
  - `src/factgraph/application/value_validation.py` (NEW)
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/application/protocol/rule_expr_inspect.py`
  - `src/factgraph/sdk/facade.py` (FieldEditor / bind path)
  - `src/factgraph/sdk/batch.py` (SDKBatchTx materialize)
  - `src/factgraph/sdk/store.py` (SDKStore.ref + primary_key check at 2807)
  - `src/factgraph/sdk/__init__.py` (`__all__` confirm `_DataMember` absent)
- Related Docs:
  - [workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md](../../design/decisions/active/2026-05-29_q-fi-form-i-decision.md) — ADR-FI adopted @ `b288ea9e`
  - [workflow/design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md](../../design/decisions/active/2026-05-29_qm-meta-grouping-and-slice-boundaries-decision.md) — meta-ADR adopted @ `ebafdb0c` (cross-check `7fc11e81`)
  - [workflow/design/decisions/active/2026-05-29_q-docs-sync-decision.md](../../design/decisions/active/2026-05-29_q-docs-sync-decision.md) — ADR-DOCS adopted @ `bb6a2c90`(§4.2.1 Slice 1 load-bearing docs)
  - [workflow/audit/active/2026-05-29_post-q-identity-as-claim-synthesis.md](../../audit/active/2026-05-29_post-q-identity-as-claim-synthesis.md) — Stage 3 synthesis
  - [workflow/design/design-points/active/identity-mechanism-redesign.zh.md](../../design/design-points/active/identity-mechanism-redesign.zh.md) — §8 Form I (target authoritative)
- Audit Log:
  - [2026-05-29_slice-1-form-i-schema.audit.md](./2026-05-29_slice-1-form-i-schema.audit.md)
- Branch: `v0.2.0-blueprint-slice-1-form-i-schema-2026-05-29`(forks from synthesis `d0036e1f`)

## 1. Problem

ADR-FI(`b288ea9e`)locks Form I descriptor + cardinality inference + Layer 4 dual-layer validation + Identity descriptor signature alignment(§4.3-bis)。Slice 1 must convert these locks into shipped code across **descriptor / parser / schema compile / application schema runtime / rule lowering / derivation compile / store / batch / facade / protocol / value-validation** layers,maintain the Q-PR1 carve-out(no PyReason adapter work),and satisfy ADR-DOCS §4.2.1 load-bearing docs sync at slice completion。

Preflight code audit revealed scope exceeds pure descriptor refactor:`primary_key` is a **rule-lowering and derivation semantic** consumed in `where_schema_lowering.py` + `derivation_compile.py` + 3 other kernel paths;`Identity(default=...)` materialization runs in **two parallel paths**(`schema_runtime.materialize_identity` + `SDKStore.ref` 1909-1912);`EntitySelector.allow_identity_defaults` is a frozen protocol field with cross-package consumers。Removing these consistently without leaving zombie surface requires this slice to be M/L boundary,not pure descriptor M。

## 2. Goals

- G1 Land Form I descriptor surface(`Field()`/`Identity()` Form I signatures + `_DataMember(_DeclaredMember)` internal base)
- G2 Land annotation-driven cardinality inference + enum-from-Literal + collection-from-list/tuple/set + reject Optional/Union/dict
- G3 Land Layer 4 dual-layer validation(compile-time schema_ir extension + write-time `application/value_validation.py` with `isinstance(value, str)` guard per ADR-FI §4.4.2)
- G4 Drop `primary_key` / `default` / `default_factory` end-to-end across all consumers(no zombie surface;no no-op stubs)
- G5 Replace primary_key-driven rule-lowering and derivation-head semantics with Form I anchor-bundle model(per §6 Scope Freeze)
- G6 Land Slice 1 load-bearing docs per ADR-DOCS §4.2.1(`04_api_surface.en.md` Form I overview + Field/Identity migration + `identity §8` alignment + `quickstart/schema.md` 类型推断 + dual-layer)
- G7 Preserve Q-PR1 carve-out(zero PyReason / adapter / ledger / write_protocol changes)
- G8 Preserve sacred-master + dirty-baseline + branch lineage per CADENCE per-commit ritual

## 3. Non-goals

- N1 Identity Claim emission(Slice 2 / ADR-IC scope)
- N2 `_identity_pred_ids` / `_exists_pred_ids` / `_protected_anchor_pred_ids` runtime caches(Slice 2 / ADR-IC §4.3)
- N3 Three-layer manager namespace migration(`fg.entities` / `fg.fields` / `fg.assertions`)— Slice 3a / ADR-API
- N4 `_meta` kwarg unification — Slice 3a / ADR-API §4.4
- N5 EntityEditor lifecycle / closed behavior — Slice 3a / ADR-IE
- N6 Ledger schema migration / value+value_tag dual-coexistence — Slice 3b / ADR-SYS-B
- N7 PyReason adapter rewrite / `claims.rest_terms` drop / INV-9 ingress strict — Slice 5 / ADR-INV9
- N8 Slice 4 consolidated docs polish — Slice 4 Phase 2(only Slice 1 load-bearing docs land here per ADR-DOCS §4.2.1)
- N9 `dict[K, V]` field annotation support — Step 2+
- N10 `InternalIdentity` / `Fingerprint` / `ContentHash` Step 2+ Identity sub-descriptors(per ADR-FI §3)
- N11 `validators` / `constraints` / `alias` / `deprecated` / `examples` `_DataMember` extension slots(Step 2+)
- N12 Historical/reference docs migration(per §6 Scope Freeze #6)

## 4. Current Context

### 4.1 Shipped baseline(preflight audit completed)

- **Descriptor layer**(`sdk/schema.py`)
  - `_DeclaredMember:20-47` shipped(`__set_name__` / `__get__` / `__set__` protocol);**`_DataMember` not present**
  - `Identity:50-88` accepts `default/default_factory/primary_key`
  - `Field:91-122` accepts `cardinality(required)/description`
  - `_annotation_to_type_domain_runtime:431-460` handles only Name/Constant/Attribute(uuid/datetime);**no Subscript / Literal / list / Optional / Union**
  - `EntityMeta.__new__:155-200` reads annotations + descriptors → `__sdk_entity_spec__`
  - `RelationshipMeta.__new__:248-296` parallel path for relationship fields
- **Parser**(`authoring/schema_dsl_parse.py`)
  - `_build_identity_from_kwargs:177-203` allowed = `{default, default_factory, primary_key}`
  - `_build_field_from_kwargs:206-237` allowed = `{cardinality, description}`
  - `_annotation_to_type_domain:274-288` narrow:Name / canonical string / `uuid.UUID` / `datetime.datetime` only
- **Schema compile**(`authoring/schema_compile.py`)
  - `_compile_identity_predicate:227-260` stamps `primary_key`
  - `_compile_identity_field:263-288` stamps `default/default_factory/primary_key`
  - `_compile_field:291-363` validates `cardinality`,stamps `description`;**no enum_values/pattern**
  - `_compile_relationship_field:366-436` same shape as `_compile_field`;**no enum_values/pattern**
- **Schema IR**(`core/schema/schema_ir.py`)
  - `_validate_predicates:144-182` validates structural keys;does **not** reject unknown sub-keys → additive `enum_values/pattern` safe
- **Application schema runtime**(`application/schema_runtime.py`)
  - `IdentityFieldInfo:14-20` carries `primary_key/has_default/default_value/default_factory`
  - `PredicateInfo:24-32` lacks `enum_values/pattern`
  - `materialize_identity:278-352`(~75 LOC)6 branches consuming defaults + `allow_identity_defaults`
  - `_materialize_default_factory:388-411`(~24 LOC)`uuid4` factory
  - `build_schema_index:82-222` reads default fields from compiled schema_ir
- **Protocol**(`application/protocol/schema_runtime.py`)
  - `EntitySelector:18-29` frozen dataclass field `allow_identity_defaults: bool = False`
- **Rule lowering**(`authoring/where_schema_lowering.py`)
  - `primary_keys_by_type:36` accumulator
  - line `46-57` filter loop with `if field.get("primary_key") is not True: continue`
  - line `90` metadata key passed downstream
  - line `247-282` cross-coordinate comparison validation enforces "one primary_key per side"
- **Derivation compile**(`authoring/derivation_compile.py`)
  - `_identity_field_names:555-590+` returns `(primary_keys, non_primary_identity)` tuple
  - line `203, 276, 580` consumers + `632` error message
- **Other primary_key consumers**
  - `sdk/store.py:1868-1918` `SDKStore.ref` has **its own parallel default-materialization**(lines 1909-1912)+ line `2807` primary_key check
  - `application/protocol/evaluate_result.py:793` primary_key check
  - `application/protocol/rule_expr_inspect.py:232` primary_key check
- **Facade**(`sdk/facade.py`)
  - FieldEditor:389-445;_cardinality consults `descriptor.cardinality`(line 394-396)
  - lines `560, 617` `allow_identity_defaults` derivation(bind vs query mode)
- **Batch**(`sdk/batch.py`)
  - `SDKBatchTx:1133`,`_materialize_identity_values:1810`,primary_key bind check `1774`
- **SDK exports**(`sdk/__init__.py:64-123`)
  - `__all__` contains `Field`,`Identity`;does NOT contain `_DataMember`
- **Callsite counts**(tests + load-bearing docs)
  - `Field(cardinality=` tests **202** / docs **65**
  - `Identity(primary_key=` tests **115** / docs **38**
  - `Identity(default=` tests **6** / docs **6**(locale-default pattern)
  - `Identity(default_factory=` tests **0** / docs **0**

### 4.2 Active design constraints

- ADR-FI §4.1-§4.4 + §4.3-bis — 5 sub-decisions binding
- meta-ADR §4.4 — Step 1 INV-9 boundary:NEW user-facing paths structurally unary;protocol/ledger runtime strict delayed to Slice 5;Slice 1 stays at application/SDK layer
- ADR-DOCS §4.2.1 — Slice 1 load-bearing docs:`04_api_surface.en.md` Form I + `identity §8` + `quickstart/schema.md` Form I 类型推断 + dual-layer validation usage
- meta-ADR §4.4 hard rule — Step 1 zero-Q-PR1 dependency

### 4.3 Historical context

- ADR-FI Q9 alternative "compile-time only" / "write-time only" / "protocol layer" all rejected — Slice 1 must implement dual-layer
- ADR-FI §4.4.2 caller contract — protocol / ledger direct path NOT covered by validation;trusted internal paths
- ADR-FI §4.3-bis rationale — Identity defaults ill-defined under INV-7a immutable anchor

## 5. Proposed Shape

### 5.1 Descriptor surface(`sdk/schema.py`)

Add internal `_DataMember(_DeclaredMember)` shared base:

```python
class _DataMember(_DeclaredMember):
    def __init__(self, *, description: str | None = None,
                 pattern: str | None = None) -> None:
        super().__init__()
        self.description = description
        self.pattern = pattern
```

`Identity(_DataMember)`:`(*, description=None, pattern=None)` only;reject `primary_key/default/default_factory` via `**legacy_kwargs` capture with migration-hint `SDKSchemaError`(per ADR-FI §4.3-bis)。

`Field(_DataMember)`:`(*, description=None, pattern=None)` only;reject `cardinality=` via legacy-kwarg capture with migration-hint;cardinality becomes inferred-storage:

```python
class Field(_DataMember):
    def __init__(self, *, description=None, pattern=None, **legacy_kwargs):
        if "cardinality" in legacy_kwargs:
            raise SDKSchemaError("Form I removed Field(cardinality=...) ...")
        super().__init__(description=description, pattern=pattern)
        self._inferred_cardinality: str | None = None  # set by EntityMeta

    @property
    def cardinality(self) -> str:
        if self._inferred_cardinality is None:
            raise SDKSchemaError("Field cardinality not yet inferred ...")
        return self._inferred_cardinality
```

`Field.cardinality` is read-only property → preserves `FieldEditor._cardinality()` runtime contract(facade.py:394-396)。

### 5.2 Annotation inference plan(`sdk/schema.py`)

Internal frozen dataclass:

```python
@dataclass(frozen=True)
class _AnnotationPlan:
    type_domain: str
    cardinality: str   # "single" | "multi"
    enum_values: tuple[Any, ...] | None
```

Extend `_annotation_to_type_domain_runtime` → `_resolve_annotation_plan(annotation) -> _AnnotationPlan`:
- `str/int/bool/bytes/float/UUID/datetime/Entity-subclass` → single + scalar/entity_ref domain
- `list[T] / tuple[T, ...] / set[T] / frozenset[T]` → multi + element domain
- `Literal[v1, v2, ...]` homogeneous → single + enum_values (mixed-type reject)
- `list[Literal[...]]` etc → multi + enum_values
- `Optional[T] / T | None` → reject(SDKSchemaError "Form I rejects Optional;unset = None already expresses absence")
- `Union[A, B]` non-Literal → reject
- `dict[K, V]` → reject(Step 2+)
- String-form annotations(from `__future__.annotations`)→ symmetric parsing

`EntityMeta.__new__` + `RelationshipMeta.__new__` call `_resolve_annotation_plan` per field;**write `plan.cardinality` back to `member._inferred_cardinality`** before invoking `member.to_authoring(plan=plan)`(L1 lock)。

`to_authoring` updated to take `plan` instead of `type_domain`:emits `cardinality / enum_values` only when present;keeps `description / pattern` from descriptor。

### 5.3 Parser symmetric extension(`authoring/schema_dsl_parse.py`)

`_build_identity_from_kwargs` allowed = `{description, pattern}` only;reject legacy set with migration hint(C3 lock — must stay symmetric with descriptor path)。

`_build_field_from_kwargs` allowed = `{description, pattern}` only;reject `cardinality=`。

`_annotation_to_type_domain` extended to handle `ast.Subscript`:
- subscript with `Name("list"|"tuple"|"set"|"frozenset")` → multi + element domain
- subscript with `Name("Literal")` → single + enum_values
- subscript with `Name("Optional")` / `ast.BinOp(BitOr with None)` → reject
- subscript with `Name("Union")` non-Literal → reject
- subscript with `Name("dict")` → reject

`_literal_eval_supported` likely sufficient for `Literal[...]` element values(Constants);verify at implementation。

### 5.4 Schema compile drops + extends(`authoring/schema_compile.py`)

`_compile_identity_predicate`:drop `primary_key` read(line 258-259)。
`_compile_identity_field`:drop `default / default_factory / primary_key` reads(lines 282-287);reject unknown sub-keys。
`_compile_field`:keep cardinality validation(arrives from upstream inference);add enum_values + pattern reads + Literal-mixed-type / invalid-regex(via `re.compile`)/ pattern-on-non-str-domain checks per ADR-FI §4.4.1。
`_compile_relationship_field`:**symmetric extension** mirroring `_compile_field`(D6 lock — same enum + pattern + validation paths)。

### 5.5 Schema IR validation(`core/schema/schema_ir.py`)

No structural change required — `_validate_predicates` does not reject unknown sub-keys;additive `enum_values / pattern` keys flow through。Document additive convention in Slice 1 audit。

### 5.6 Application schema runtime simplification(`application/schema_runtime.py`)

- `IdentityFieldInfo`:drop `primary_key / has_default / default_value / default_factory` fields → keep only `name` + `type_domain`
- `PredicateInfo`:add `enum_values: tuple[Any, ...] | None` + `pattern: str | None`(L4 lock — extend existing,no parallel cache)
- `materialize_identity`:simplify to "all identity fields required;no default fallback;no `allow_identity_defaults` parameter";drop signature kwarg
- `_materialize_default_factory`:**delete entire helper**
- `build_schema_index`:drop default-field reads;construct simplified `IdentityFieldInfo`;populate `PredicateInfo.enum_values / pattern` from compiled schema_ir
- `resolve_selector`:drop `allow_identity_defaults` propagation

### 5.7 Protocol layer cleanup(`application/protocol/schema_runtime.py`)

- `EntitySelector.allow_identity_defaults` frozen field(line 23)+ validation(line 29):**remove**
- All `EntitySelector(...)` construction sites that pass `allow_identity_defaults=True/False` updated to drop kwarg

### 5.8 SDKStore.ref parallel default path(`sdk/store.py:1868-1918`)

The SDK store has its **own** identity-materialization path independent of `schema_runtime.materialize_identity`:
- Lines 1909-1912:`elif "default" in field: raw_value = field["default"]` / `elif field.get("default_factory") == "uuid4": raw_value = _default_uuid4_for_tag(tag)`
- This path also drops to "all identity required;no default fallback"
- `_default_uuid4_for_tag` helper + line ~3266 "default_factory='uuid4' not supported" error path also deleted

Update docstring(lines 1879-1881)to remove `default=` / `default_factory=` mentions。Line `2807` primary_key check replaced per N3 plan(see §5.10)。

### 5.9 Facade + Batch cascade(`sdk/facade.py` + `sdk/batch.py`)

- `facade.py:560` `allow_identity_defaults=any(...)` removed;bind requires full identity;raise if missing
- `facade.py:617` `allow_identity_defaults=False` kwarg removed(disappears with materialize_identity signature change)
- `batch.py:1133, 1160, 1737, 1748, 1810` `SDKBatchTx._materialize_identity_values` simplified — no default fallback
- `batch.py:1774` `bool(row.get("primary_key"))` primary_key bind check removed;use anchor-bundle membership check(N3 / N8 / N9 / N10 cascade)

### 5.10 Other primary_key consumers replacement

Replace each `getattr(field, "primary_key", False)` with anchor-bundle membership check(field name in `EntityTypeInfo.identity_fields`):
- `sdk/store.py:2807`
- `application/protocol/evaluate_result.py:793`
- `application/protocol/rule_expr_inspect.py:232`

### 5.11 Rule lowering rewrite(`authoring/where_schema_lowering.py`)

Per Scope Freeze #3(L7 lock — same-Identity-field-match only):

- `primary_keys_by_type:36` → `identity_fields_by_type: dict[str, list[str]]`(collect all Identity fields)
- `46-57` loop:remove `if field.get("primary_key") is not True: continue` filter — collect all Identity fields
- `90` metadata key renamed to `identity_fields_by_type`
- `247-282` cross-coordinate comparison validation rewritten:
  - Allow `attr_eq(EntityType.identity_field, EntityType.identity_field)` same-field same-type only
  - Reject Identity-to-Field、Field-to-Field-via-identity-path、different Identity field
  - **NO** implicit single-field → full-bundle expansion
  - Reject ambiguity → explicit error message points to future entity-equality primitive(out of Slice 1 scope)

### 5.12 Derivation compile rewrite(`authoring/derivation_compile.py`)

Per Scope Freeze #4(L8 lock — head may not include any Identity field):

- `_identity_field_names:555-590+` rewrite:return single `identity_fields: list[str]` not `(primary_keys, non_primary)` tuple
- `203, 276` consumers updated to single-list shape
- `204-207, 580` head-body validation:"head must not include any Identity field"(Option A)
- `632` error message rewritten to anchor-bundle terms
- **Pre-impl grep**(Step 0):find all shipped derivation rules where head body includes any Identity field;catalog as migration items(if 0 → Option A is free lunch)

### 5.13 Write-time validation(`application/value_validation.py` NEW)

```python
def validate_field_value(value: Any, *, pred_info: PredicateInfo) -> None:
    """Validate value against pred_info schema constraints.

    Called by application layer write path BEFORE ledger.append_assertion.
    Raises SDKValueError on validation failure.

    Per ADR-FI §4.4.2 caller contract:
    - Not called from evidence/write_protocol.set_field direct path
    - Not called from adapter / migration tool / test fixture direct path
    """
    if pred_info.enum_values is not None and value not in pred_info.enum_values:
        raise SDKValueError(
            f"value {value!r} not in enum {pred_info.enum_values} "
            f"for {pred_info.pred_id}"
        )
    if pred_info.pattern is not None:
        if not isinstance(value, str):
            raise SDKValueError(
                f"pattern validation expects str value for {pred_info.pred_id}; "
                f"got {type(value).__name__}"
            )
        if not re.fullmatch(pred_info.pattern, value):
            raise SDKValueError(
                f"value {value!r} does not match pattern {pred_info.pattern!r} "
                f"for {pred_info.pred_id}"
            )
```

Integration:`FieldEditor.set/add`(facade.py:398-435)inserts call **before** `getattr(handle, field).set/add(...)`;reuses `SchemaIndex.field_predicates` for `PredicateInfo` lookup(L4 lock)。

Per ADR-FI §4.4.2 explicit isinstance str-guard before `re.fullmatch` — type-bypass defense lock-in。

## 6. Boundaries And Invariants

### 6.1 Scope Freeze(LOCKED — must remain through implementation)

| # | Lock | Source |
|---|---|---|
| **SF1** | **Form I removes primary/default/default_factory semantics completely** — no zombie surface,no no-op stubs,no alias compatibility | ADR-FI §4.3 + §4.3-bis + reviewer lock 2026-05-29 |
| **SF2** | **All Identity fields are immutable anchor-bundle members** — no primary vs non-primary distinction;identity bundle = all `Identity()` fields on Entity subclass | ADR-FI §4.3-bis + identity §8.1 |
| **SF3** | **Cross-coordinate attribute equality may compare the same Identity field only** — no implicit full-bundle expansion;Field-to-Field / Identity-to-Field / different-Identity-field rejected;full anchor-bundle equivalence is a future separate primitive | L7 reviewer lock 2026-05-29 |
| **SF4** | **Derivation heads may not include any Identity field** — Option A;pre-impl grep produces migration list if any shipped rule violates;rule semantics unchanged otherwise | L8 reviewer lock 2026-05-29 |
| **SF5** | **Identity defaults removed end-to-end** — `EntitySelector.allow_identity_defaults` field + `materialize_identity` kwarg + `SDKStore.ref` default path + `SDKBatchTx` default fallback + facade bind logic + `_materialize_default_factory` helper all deleted | L9 reviewer lock 2026-05-29 |
| **SF6** | **Historical/reference docs excluded from migration grep** — must migrate:`tests/`,`src/factgraph/sdk/docs/`,`docs/official/kernel/`,active design/decision/blueprint load-bearing references。Excluded:`workflow/heritage/`,`workflow/blueprints/archive/`,`docs/references/working/`,`docs/references/bridges/`(if not current implementation truth) | L10 reviewer lock 2026-05-29 |

### 6.2 Compatibility constraints

- Sacred `master` `562c74195df43e933bed92a3ff25de94dd8ce666` 不动
- Sacred `v0.1-oss-prep` 不动
- Dirty baseline(4 M + 1 D + 2 untracked,unrelated to identity-as-claim)preserved through all commits
- Branch lineage:每次 commit verify HEAD ancestor includes ADR-FI adopt `b288ea9e` + ADR-DOCS adopt `bb6a2c90` + synthesis `d0036e1f` + cross-check `7fc11e81`

### 6.3 Q-PR1 / Slice 5 carve-out invariant

- Zero changes to `core/evidence/write_protocol.py`
- Zero changes to `core/store/ledger.py`
- Zero changes to `core/store/_builders.py`(D11 stays Slice 2 — ADR-IC §4.3.1 cache integration)
- Zero changes to `adapters/pyreason/*`
- Zero `claims.rest_terms` column / DTO changes
- Zero `INV-9` runtime strict assertions added
- Slice 5 PyReason adapter rewrite + DTO/SQL ingress strict 留 Slice 5 / ADR-INV9 §4.4 三项绑定

### 6.4 ADR-DOCS §4.2.1 load-bearing docs invariant

Slice 1 may NOT mark `implemented` unless these docs land in the same slice:
- `src/factgraph/sdk/docs/04_api_surface.en.md` Form I overview + `Field()` no-cardinality + `Identity()` no-primary_key/default + migration guide(Old/New examples per ADR-FI §4.3 + §4.3-bis)
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §8 Form I` aligned with ADR-FI §4.3 + §4.3-bis adopted wording
- `docs/official/kernel/quickstart/schema.md` Form I 类型推断 cardinality 形态 + dual-layer enum/pattern usage

Per ADR-DOCS §4.1.2 Dimension B:design-point sync IS load-bearing in this slice。

## 7. Acceptance

### 7.1 Descriptor + annotation surface(G1 + G2)

- [ ] `_DataMember(_DeclaredMember)` exists in `sdk/schema.py`,NOT in `sdk/__init__.py:__all__`
- [ ] `Identity(*, description=None, pattern=None)` accepted
- [ ] `Identity(primary_key=True)` raises `SDKSchemaError` with migration hint
- [ ] `Identity(default="x")` raises `SDKSchemaError` with migration hint(negative L11 check)
- [ ] `Identity(default_factory="uuid4")` raises `SDKSchemaError` with migration hint(negative L11 check)
- [ ] `Field(*, description=None, pattern=None)` accepted
- [ ] `Field(cardinality="single")` raises `SDKSchemaError` with migration hint
- [ ] `name: str = Field()` → `_inferred_cardinality == "single"`;`Field.cardinality` property returns `"single"`
- [ ] `tags: list[str] = Field()` → `_inferred_cardinality == "multi"`
- [ ] `status: Literal["a", "b"] = Field()` → single + `enum_values=("a","b")` in schema_ir
- [ ] `tags: list[Literal["a","b"]] = Field()` → multi + enum_values
- [ ] `name: Optional[str] = Field()` raises `SDKSchemaError`
- [ ] `name: str | None = Field()` raises `SDKSchemaError`
- [ ] `name: Union[str, int] = Field()` raises `SDKSchemaError`
- [ ] `tags: dict[str, str] = Field()` raises `SDKSchemaError`(Step 2+ defer)
- [ ] `Field(pattern=r"invalid[")` raises `SDKSchemaError`(regex syntax)
- [ ] `Field(pattern=r"^[a-z]+$")` on non-str type_domain raises `SDKSchemaError`
- [ ] `Literal[1, "a"]` mixed-type raises `SDKSchemaError`
- [ ] Same behaviors apply to Relationship fields(`_compile_relationship_field` symmetric)

### 7.2 Parser symmetric behavior(C3 lock)

- [ ] Parser path raises identical errors for the same inputs as Python class path
- [ ] `_annotation_to_type_domain` parser handles `Subscript[list/tuple/set/Literal]` + rejects Optional/Union/dict
- [ ] No drift between Python class path and text DSL path(symmetric test fixture covers both)

### 7.3 Schema compile + IR(G3)

- [ ] `_compile_field` + `_compile_relationship_field` emit `enum_values` / `pattern` when present
- [ ] `_compile_identity_field` + `_compile_identity_predicate` no longer emit `primary_key` / `default` / `default_factory`
- [ ] `core/schema/schema_ir.py` validation unchanged but accepts new optional keys

### 7.4 Application schema runtime simplification(G4)

- [ ] `IdentityFieldInfo` fields = `{name, type_domain}` only
- [ ] `PredicateInfo` includes `enum_values` + `pattern`
- [ ] `materialize_identity` signature drops `allow_identity_defaults` kwarg;raises `SchemaResolutionError(IDENTITY_INCOMPLETE)` on any missing field
- [ ] `_materialize_default_factory` helper deleted
- [ ] `resolve_selector` no longer propagates `allow_identity_defaults`

### 7.5 Protocol cleanup(G4)

- [ ] `EntitySelector.allow_identity_defaults` field removed from frozen dataclass
- [ ] All `EntitySelector(...)` construction sites updated(grep verified zero remaining references)

### 7.6 SDKStore.ref second default path(L9 reviewer addition)

- [ ] `sdk/store.py:1909-1912` default / default_factory branches deleted
- [ ] `_default_uuid4_for_tag` helper deleted
- [ ] Line ~3266 "default_factory='uuid4' not supported" error deleted
- [ ] Docstring 1879-1881 updated:no `default=` / `default_factory=` mention
- [ ] `SDKStore.ref(User)` lacking identity raises `SDKStoreError("missing identity field: User.<name>")`(L11 negative check)

### 7.7 Facade + Batch + Other primary_key consumers

- [ ] `facade.py:560` bind path requires full identity
- [ ] `facade.py:617` `allow_identity_defaults` kwarg removed(via materialize_identity signature)
- [ ] `batch.py:1774` primary_key bind check replaced
- [ ] `sdk/store.py:2807` primary_key check replaced with anchor-bundle membership
- [ ] `application/protocol/evaluate_result.py:793` primary_key check replaced
- [ ] `application/protocol/rule_expr_inspect.py:232` primary_key check replaced

### 7.8 Rule lowering + derivation semantics(SF3 + SF4)

- [ ] `where_schema_lowering.py:36` renamed `identity_fields_by_type`
- [ ] `where_schema_lowering.py:46-57` primary_key filter removed;all Identity fields collected
- [ ] `where_schema_lowering.py:247-282` cross-coordinate comparison validation enforces same-field same-type only;rejects all other shapes with explicit error message
- [ ] `derivation_compile.py:_identity_field_names` returns single list
- [ ] `derivation_compile.py` head-body validation rejects any Identity field in head
- [ ] Pre-impl grep migration list for shipped Identity-headed derivation rules(0 expected;flag for review if > 0)

### 7.9 Write-time validation(G3)

- [ ] `application/value_validation.py` module shipped with `validate_field_value(value, *, pred_info)` signature
- [ ] enum miss raises `SDKValueError`
- [ ] pattern path executes `isinstance(value, str)` guard BEFORE `re.fullmatch`(ADR-FI §4.4.2 explicit lock)
- [ ] non-str value with pattern raises `SDKValueError`
- [ ] pattern mismatch raises `SDKValueError`
- [ ] `FieldEditor.set(field, value, ...)` invokes validate BEFORE delegating to handle
- [ ] `FieldEditor.add(field, value, ...)` invokes validate BEFORE delegating to handle
- [ ] `evidence/write_protocol.set_field` direct call path NOT touched(caller contract per ADR-FI §4.4.2)

### 7.10 Load-bearing docs(G6 + ADR-DOCS §4.2.1)

- [ ] `sdk/docs/04_api_surface.en.md` Form I overview + `Field()` no-cardinality + `Identity()` no-primary_key/default + migration guide for both descriptors landed in slice
- [ ] `identity-mechanism-redesign.zh.md §8 Form I` aligned with ADR-FI §4.3 + §4.3-bis adopted wording
- [ ] `docs/official/kernel/quickstart/schema.md` Form I 类型推断 + dual-layer enum/pattern usage section landed
- [ ] §10 Outcome explicitly confirms load-bearing docs landed(ADR-DOCS §4.2 per-slice acceptance enforcement)

### 7.11 Migration callsite cleanup(L10 + L11 + P)

- [ ] `tests/` directory:0 remaining `Field(cardinality=` / `Identity(primary_key=` / `Identity(default=` / `Identity(default_factory=` after migration(grep verified)
- [ ] `src/factgraph/sdk/docs/` + `docs/official/kernel/`:0 remaining stale uses after migration
- [ ] Excluded directories(`workflow/heritage/`,`workflow/blueprints/archive/`,`docs/references/working/`,`docs/references/bridges/`(verified non-load-bearing))NOT migrated
- [ ] `Identity(default=...)` 6+6 = 12 callsites migrated to explicit identity supply
- [ ] §10 Outcome reports grep counts:`Field(cardinality=` before / after,`Identity(primary_key=` before / after,`Identity(default=` before / after

### 7.12 Q-PR1 carve-out preservation(G7)

- [ ] No diff in `core/evidence/write_protocol.py`
- [ ] No diff in `core/store/ledger.py`
- [ ] No diff in `adapters/pyreason/*`
- [ ] No new INV-9 runtime strict assertion landed

### 7.13 Per-commit verification ritual(G8)

- [ ] Every commit:`git rev-parse master` = `562c74195df43e933bed92a3ff25de94dd8ce666`
- [ ] Every commit:dirty baseline(4 M + 1 D + 2 untracked)preserved
- [ ] Every commit:branch lineage ancestor includes ADR-FI `b288ea9e` + ADR-DOCS `bb6a2c90` + synthesis `d0036e1f`

## 8. Implementation Plan

Implementation should land in **smaller batches per `feedback_smaller_batch_design_blueprints`** since this slice touches rule-lowering and derivation semantics(SF3 + SF4 are rule-touching)。Each step below is a separate commit with verification ritual between steps。

### Step 0 — Pre-impl grep + migration catalog(no code change)

- 0.1 Grep all derivation rules where head body includes any Identity field;produce migration list(SF4 / Option A free-lunch verification)
- 0.2 Grep `Identity(default=`,`Identity(primary_key=`,`Field(cardinality=`,`Identity(default_factory=` in migration scope per SF6;produce per-pattern count
- 0.3 Catalog SDK callers of `EntitySelector(allow_identity_defaults=...)` outside core paths(if any)
- 0.4 Record findings in audit log under "Pre-impl preflight findings"

### Step 1 — Descriptor surface + annotation plan(`sdk/schema.py`)

- 1.1 Add `_DataMember(_DeclaredMember)` internal base
- 1.2 Add `_AnnotationPlan` frozen dataclass
- 1.3 Extend `_annotation_to_type_domain_runtime` → `_resolve_annotation_plan` with full Form I rules
- 1.4 Rewrite `Identity.__init__` to `(*, description, pattern, **legacy_kwargs)` with migration-hint error
- 1.5 Rewrite `Field.__init__` to `(*, description, pattern, **legacy_kwargs)` + `_inferred_cardinality` storage + read-only `cardinality` property
- 1.6 Update `Identity.to_authoring` + `Field.to_authoring` to take `_AnnotationPlan`
- 1.7 Update `EntityMeta.__new__` + `RelationshipMeta.__new__` to write back `_inferred_cardinality` before `to_authoring`
- 1.8 Tests for descriptor surface(positive + negative + annotation rejects)— commit boundary

### Step 2 — Parser symmetric extension(`authoring/schema_dsl_parse.py`)

- 2.1 Rewrite `_build_identity_from_kwargs` allowed set + migration-hint error
- 2.2 Rewrite `_build_field_from_kwargs` allowed set + migration-hint error
- 2.3 Extend `_annotation_to_type_domain` to handle Subscript / Literal / list / tuple / set / reject Optional / Union / dict
- 2.4 Symmetric test fixture(C3 lock — same input → same error across parser path and class path)— commit boundary

### Step 3 — Schema compile drops + extends(`authoring/schema_compile.py`)

- 3.1 `_compile_identity_predicate` drop `primary_key` read
- 3.2 `_compile_identity_field` drop `default/default_factory/primary_key` reads
- 3.3 `_compile_field` add `enum_values` + `pattern` + Literal mixed-type / invalid regex / pattern-on-non-str checks
- 3.4 `_compile_relationship_field` symmetric extension(D6 lock)
- 3.5 Tests — commit boundary

### Step 4 — Application schema runtime simplification(`application/schema_runtime.py`)

- 4.1 `IdentityFieldInfo` drop `primary_key/has_default/default_value/default_factory`
- 4.2 `PredicateInfo` add `enum_values` + `pattern`(L4 lock)
- 4.3 `materialize_identity` simplify;drop `allow_identity_defaults` kwarg
- 4.4 Delete `_materialize_default_factory`
- 4.5 `build_schema_index` update to construct simplified `IdentityFieldInfo` + populate `PredicateInfo` enum/pattern
- 4.6 `resolve_selector` drop kwarg propagation
- 4.7 Tests — commit boundary

### Step 5 — Protocol layer cleanup(`application/protocol/schema_runtime.py`)

- 5.1 Remove `EntitySelector.allow_identity_defaults` field + validator
- 5.2 Grep all `EntitySelector(...)` construction sites;drop kwarg
- 5.3 Tests — commit boundary

### Step 6 — SDKStore.ref second default path(`sdk/store.py:1868-1918`)+ primary_key check at 2807

- 6.1 Remove default / default_factory branches at lines 1909-1912
- 6.2 Delete `_default_uuid4_for_tag` helper
- 6.3 Delete "default_factory='uuid4' not supported" error around line 3266
- 6.4 Update docstring(1879-1881)
- 6.5 Replace primary_key check at line 2807 with anchor-bundle membership
- 6.6 Tests(negative L11 check:`SDKStore.ref(User)` lacking identity raises)— commit boundary

### Step 7 — Facade + Batch cascade

- 7.1 `facade.py:560` bind requires full identity;raise on missing
- 7.2 `facade.py:617` kwarg removal cascade(automatic via materialize_identity signature change)
- 7.3 `batch.py:_materialize_identity_values` simplification
- 7.4 `batch.py:1774` primary_key bind check replacement
- 7.5 Tests — commit boundary

### Step 8 — Other primary_key consumers replacement

- 8.1 `application/protocol/evaluate_result.py:793` replace check
- 8.2 `application/protocol/rule_expr_inspect.py:232` replace check
- 8.3 Tests — commit boundary

### Step 9 — Rule lowering rewrite(`authoring/where_schema_lowering.py`)— **SF3 enforced**

- 9.1 Rename `primary_keys_by_type` → `identity_fields_by_type`
- 9.2 Remove primary_key filter at 46-57;collect all Identity fields
- 9.3 Rename metadata key at line 90
- 9.4 Rewrite cross-coordinate comparison validation at 247-282 per SF3:same-Identity-field-match only;reject Identity-to-Field / Field-to-Field / different-Identity-field with explicit error pointing to future entity-equality primitive
- 9.5 Tests covering all reject cases — commit boundary

### Step 10 — Derivation compile rewrite(`authoring/derivation_compile.py`)— **SF4 enforced**

- 10.1 Rewrite `_identity_field_names` to single-list shape
- 10.2 Update consumers at 203, 276 to single-list
- 10.3 Head-body validation rejects any Identity field in head(Option A)
- 10.4 Error message rewritten to anchor-bundle terms at 632
- 10.5 If pre-impl grep(Step 0.1)found migration items,land migrations in same commit
- 10.6 Tests — commit boundary

### Step 11 — Write-time validation module(`application/value_validation.py` NEW)+ integration

- 11.1 New module with `validate_field_value(value, *, pred_info)` per §5.13(ADR-FI §4.4.2 explicit isinstance str-guard)
- 11.2 `FieldEditor.set/add` integration in `facade.py:398-435`
- 11.3 Tests covering enum miss / pattern miss / non-str pattern / isinstance guard / valid-paths-pass-through
- 11.4 Confirm `evidence/write_protocol.set_field` direct path NOT touched(grep zero diff)
- 11.5 — commit boundary

### Step 12 — Migration callsite cleanup(tests + load-bearing docs)

- 12.1 `tests/` migration(per Step 0.2 catalog;mechanical regex-assisted):
  - `Field(cardinality="single")` → `Field()` + annotation
  - `Field(cardinality="multi")` → `Field()` + `: list[T]` annotation
  - `Identity(primary_key=True)` → `Identity()`
  - `Identity(default=...)` → callers supply explicit identity values
- 12.2 `src/factgraph/sdk/docs/04_api_surface.en.md` Form I overview + migration guide
- 12.3 `workflow/design/design-points/active/identity-mechanism-redesign.zh.md §8` alignment
- 12.4 `docs/official/kernel/quickstart/schema.md` Form I 类型推断 + dual-layer validation usage
- 12.5 Confirm SF6 excluded directories untouched(grep diff verified)
- 12.6 Final `tests/` + load-bearing docs grep:zero stale uses
- 12.7 — commit boundary

### Step 13 — Final acceptance + §10 Outcome

- 13.1 Run all §7 acceptance checks
- 13.2 Verify §6.1 Scope Freeze items still locked
- 13.3 Fill §10 Outcome:final landing + deviations + grep counts before/after + Q-PR1 carve-out preservation confirmation
- 13.4 Mark `Status: implemented` + audit log final row
- 13.5 — commit boundary(slice 1 close)

## 9. Docs To Update

### 9.1 Slice 1 load-bearing(per ADR-DOCS §4.2.1 — MUST land in this slice)

- `src/factgraph/sdk/docs/04_api_surface.en.md`:
  - New Form I section with `Field()` and `Identity()` Form I signatures
  - Migration guide(Old / New examples per ADR-FI §4.3 + §4.3-bis)
  - dual-layer validation usage(`pattern=` / `Literal[...]` enum)
  - cardinality inference table
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`:
  - §8 Form I aligned with ADR-FI adopted wording
  - §8.4 类型推断 rules synced with implementation
  - §8.5 `_DataMember` internal base documented as Slice 1 landed
- `docs/official/kernel/quickstart/schema.md`:
  - Form I 类型推断 cardinality 形态 section
  - dual-layer enum / pattern validation usage example

### 9.2 Module docs(per `workflow/foundations/module_docs_convention.md` — inherent to each touched module)

- `src/factgraph/sdk/docs/README.md` — Form I changes summary
- `src/factgraph/authoring/docs/README.md`(if exists)— compile / parse / rule lowering changes
- `src/factgraph/application/docs/README.md`(if exists)— schema_runtime + value_validation changes

### 9.3 Out-of-slice docs(Slice 4 Phase 2)

- Other quickstarts(`read-write.md` / `assertions.md` / etc.)cross-doc terminology consistency,5-pass polish per ADR-DOCS §4.3
- Module-wide migration note placement consolidation

### 9.4 Excluded(per SF6)

- `workflow/heritage/`
- `workflow/blueprints/archive/`
- `docs/references/working/`
- `docs/references/bridges/`(verify non-load-bearing at Step 0)

## 10. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- Pre-impl grep results(Step 0.1 / 0.2 / 0.3):
- Final callsite counts(`Field(cardinality=` / `Identity(primary_key=` / `Identity(default=` / `Identity(default_factory=` before vs after):
- Q-PR1 carve-out preservation confirmation:
- Slice 1 load-bearing docs landed confirmation:
- 归档说明:
