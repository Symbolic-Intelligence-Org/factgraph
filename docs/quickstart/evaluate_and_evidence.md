# Evaluation and evidence

This chapter has two halves stitched into one chapter because they share too much vocabulary to live apart: running a rule (`fg.eval.evaluate(...)` and its result) and reading what the evaluator returned (the `Explanation` DTO and its `EvidenceGraph`). It builds on [`engines_and_configs.md`](engines_and_configs.md) (the `engine=` / `config=` parameters) and [`rules.md`](rules.md) (the `Rule` / `RuleExpr` / `head` declaration shape).

## 1. `fg.eval.evaluate` — running a rule

### 1.1 Minimal end-to-end

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity
from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import PredAtom, Var


class User(Entity):
    user_id: str = Identity()
    region: str = Field()


fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.region, alice, "US")

u = Var(name="u")
r = Var(name="r")

region_rule = Rule(
    id="user:region",
    version="v1",
    when=(PredAtom(pred_id="user:region", terms=[u, r]),),
    ports={"user": u, "region": r},
)

result = fg.eval.evaluate(region_rule, head=region_rule)

assert result.count() == 1
assert result.first().claim.name == "user:region"
```

A note about this minimal example: it uses direct `Rule(...)` construction (per [`rules.md`](rules.md) §2.6) rather than the `build_application_rule(...)` ergonomic factory. The factory's Entity-DSL form (`User(u)`, `User(u).region == r`) auto-prepends a `User:exists` atom, but `User:exists` claims are not currently emitted by `fg.entities.create(...)` in the shipped ledger — so factory-built rules return 0 rows out of the box. The direct path lets the example actually run; the factory path is the right choice once `User:exists` emission lands.

### 1.2 `head=` parameter

`head=` is mandatory on every `fg.eval.evaluate(...)` call. It supplies the `Rule` whose `ports` shape the output rows:

```python
fg.eval.evaluate(rule, head=rule)                    # single Rule: head=rule
fg.eval.evaluate(rule_expr, head=some_rule)          # RuleExpr: head can be in OR out of the expression
```

The relationship with `Rule.ports` (declaration-time output shape, see [`rules.md`](rules.md) §2.3): `Rule.ports` declares what each rule *exposes*; `head=` says "*this* port shape is the one I want for the answer rows".

Rejected forms:

```
SDKStoreError: evaluate(rule_expr, ...) requires head= Rule
SDKStoreError: evaluate(rule_expr, ...) head= must be Rule       ← SDK DSL Rule / Inference / dict / str / inspect objects all rejected
WhereValidationError: target predicate not found: <id>           ← rule's id is not a known ledger predicate
```

#### How `head=` connects to a `RuleExpr`

The mental model: **`head.ports` is a projection-and-implicit-join spec over the `RuleExpr`.** Whatever the expression's branches compute, the SDK uses the names in `head.ports` to pick out and unify port values across operands — you do not write an explicit `.join_by_ports(...)` for the names that already appear as head ports. Anything you need joined beyond that, you join explicitly in the expression itself.

This is exactly what `Rule.projection(*port_names)` makes literal — a synthetic head that *only* declares port names and nothing else:

```python
proj = Rule.projection("user", "region")
# id="__factgraph_projection__<hash>", body is a placeholder
# Conceptually: "give me rows projected on user, region; figure out the joins"
```

`Rule.projection(...)` is the explicit form of the mental model. It is the natural template for `fg.entities.match(EntityCls, template, ...)` (see [`three_layer_api.md`](three_layer_api.md) §2). It is **not currently usable as an `evaluate` head** in v0.2 — the runtime raises:

```
WhereValidationError: target predicate not found: __factgraph_projection__<hash>
```

(per [`rules-and-inferences.md`](../official/kernel/quickstart/rules-and-inferences.md) §"Rule.projection(*names) is not an evaluate head"). For evaluate, supply a real `Rule` whose ports are the projection you want; the SDK does the same projection-and-join derivation from those ports.

Two minor identity-bookkeeping flavors track whether the head's `id` happens to appear in the expression — both produce the same evaluation; the distinction only surfaces as error guards:

| Identity flavor | Detected by | Why you care |
|---|---|---|
| **inline** | `head.id == occurrence.rule_id` AND `head.content_digest == occurrence.content_digest` for exactly one occurrence | Different `version` on the same id+digest emits a `UserWarning` but evaluation proceeds |
| **external** | head's `id` does not appear in any occurrence | No bookkeeping cost — head just provides the projection spec |

Three `RuleExprError`s come from head ↔ expression validation:

```
head rule '<id>' matches an expression occurrence with a different content digest
   ← head and an occurrence share id but differ in body (you redefined the rule
      but the expression still holds the old reference)

head rule '<id>' matches multiple expression occurrences with the same content digest
   ← the same Rule appears twice in the expression without distinct .as_() aliases

RuleExpr head validation failed: head port '<name>' is only declared in some RuleExpr branches
   ← port-shape contract violation (next paragraph)
```

#### Port-shape contract — the silent gotcha

The head's ports must be **declared in every branch** of the `RuleExpr`. If a port appears in some branches but not others (e.g. one OR side declares `region`, the other doesn't), the head cannot ask for the union — validation rejects with the "only declared in some RuleExpr branches" message. Either equalize the ports across branches, or pick a head whose ports are a subset present everywhere.

### 1.3 What comes back

`fg.eval.evaluate(...)` returns an `EvaluateResult` — covered in §2.

## 2. `EvaluateResult` navigation and `EvaluateRow`

### 2.1 `EvaluateResult` — 6 navigation methods

```text
EvaluateResult (frozen)
  ├── rows: tuple[EvaluateRow, ...]
  ├── result_id, run_id          ← stable identifiers ("evalr_v1:..." / "run_v1:...")
  ├── head: Rule                 ← the head you passed
  ├── engine, engine_version, adapter_version
  ├── expr_digest, rule_set_digest, view_snapshot_digest, config_digest
  ├── evaluated_at
  └── result_digest              ← content-addressed over everything above
```

The 6 user-facing methods:

| Method | Returns | Use when |
|---|---|---|
| `iter(result)` | `Iterator[EvaluateRow]` | streaming over rows |
| `len(result)` | `int` | known row count |
| `result[i]` | `EvaluateRow` | random access by index |
| `result.first()` | `EvaluateRow \| None` | head row, `None` if empty |
| `result.exists()` | `bool` | "any rows?" shortcut |
| `result.count()` | `int` | row count (same as `len(result)`) |

The other fields (`result_id`, `engine`, the digest fields) are for caching / audit / equivalence checks — they answer "did this evaluation already happen with the same inputs?"

### 2.2 `EvaluateRow` shape

```text
EvaluateRow (frozen)
  ├── row_id: str
  ├── bindings: Mapping[str, Any]   ← engine candidate payload (see below)
  ├── claim: Claim                  ← see §2.4
  ├── raw_kind: "probabilistic" | "possibilistic" | None
  ├── bound: tuple[float, float] | None
  ├── evidence_ref: EvidenceRef     ← see §2.5
  └── _result_resolver              ← internal; powers row.explain()
```

```python
row = result.first()

row.row_id                    # str
row.claim.name                # "user:region" — the head predicate that fired
row.raw_kind                  # None (no uncertainty meta on the source claims)
row.bound                     # None (paired with raw_kind, see engines_and_configs.md §2.1)
row.evidence_ref.ref_id       # "evref_v1:..." — stable handle for this evidence
```

**`row.bindings` is the engine's candidate payload, not a `{port_name: value}` map.** For the native engine over a `PredAtom` body, the payload shape is:

```python
dict(row.bindings)
# {
#   "pred_id": "user:region",
#   "terms": [
#     {"kind": "entity_ref", "value": "idref_v1:User:<digest>"},     # ← position 0 — port "user"
#     {"kind": "literal", "tag": "string", "value": "US"},           # ← position 1 — port "region"
#   ],
# }
```

The `terms` list is **positional** — `terms[i]` corresponds to the i-th `Var` in the head's `PredAtom` terms, which maps to the i-th `port` in `head.ports`. Each term is a typed dict:

| Term shape | When |
|---|---|
| `{"kind": "entity_ref", "value": "<idref_v1:...>"}` | The port resolved to an entity reference |
| `{"kind": "literal", "tag": "<type>", "value": <python_value>}` | The port resolved to a typed literal — `tag` is one of `string` / `int` / `bool` / `float64` / `bytes` / `time` / `uuid` |

To go from port name to value, walk `head.ports` (an ordered `Mapping[str, Var]`) in parallel with `terms`. The application protocol exposes an internal helper `_binding_value_for_head_port(row, head, port_name)` that does this lookup but it is not currently re-exported through the SDK.

`raw_kind` / `bound` carry through from the source assertion's `meta` (per `engines_and_configs.md` §2.1). They are `None` on rows whose source facts have no uncertainty annotation. The invariant from `data_model.md` §2.2 holds: `bound is None iff raw_kind is None`.

### 2.3 `row.close()` — the per-row closed-head `Rule`

```python
closed = row.close()                  # Rule
isinstance(closed, Rule)              # True
closed.id                             # "user:region_closed_<row_id>"
closed.desc                           # carries through from head.desc (per design-point D21)
```

This is the *closed-head* construction — a derived `Rule` whose `when` is the original head's `when` plus extra atoms binding each port to the row's specific values. It is used internally by `fg.eval.explain(...)` and `fg.rules.inspect(...)`. See §6 for the concept's broader role.

### 2.4 `Claim` DTO

```text
Claim (frozen)
  ├── kind: Literal["fact_triple", "rule_head", "aggregate_result", "projection"]
  ├── name: str               ← the predicate id (e.g. "user:region", "User:exists")
  ├── arguments: Mapping[str, Any]    ← keyed positional / by name; contains the claim's terms
  ├── repr: str               ← human-readable rendering (e.g. "user:region(alice, US)")
  └── digest: str             ← "sha256:..." over the canonical claim form
```

The four `kind` values say what role the claim plays:

| Kind | Meaning |
|---|---|
| `"fact_triple"` | A ledger fact — `(pred_id, e_ref, value)` triple form |
| `"rule_head"` | A derived head from rule evaluation |
| `"aggregate_result"` | An aggregate (`agg_count` / `agg_sum` / ...) result |
| `"projection"` | A `Rule.projection(...)` synthetic projection output |

### 2.5 `EvidenceRef` DTO

```text
EvidenceRef (frozen)
  ├── ref_id: str                  ← "evref_v1:..." — stable across re-evaluation
  ├── result_id: str               ← "evalr_v1:..." — the parent result
  ├── row_id: str
  ├── fact_digest: str             ← "sha256:..." over the row's source facts
  └── closed_head_digest: str      ← "sha256:..." over the closed-head Rule (§2.3)
```

`EvidenceRef` is the stable handle by which a row can be re-located in a later run or across processes. Two evaluation runs over the same `(rule, head, engine, config, ledger snapshot)` will produce the same `fact_digest` and `closed_head_digest`, even if `result_id` / `run_id` change.

## 3. `row.explain()` and `fg.eval.explain(...)` — two entries to `Explanation`

Both routes produce the same `Explanation` DTO (§4). Pick by ergonomics:

### 3.1 Row-level: `row.explain()`

```python
row = result.first()
explanation = row.explain()
```

Per-row explanation — you already have the row, you want the `Explanation` for it specifically. `row.explain()` raises `DetachedRowError` if its parent `EvaluateResult` has gone out of scope (the row holds a weak reference to its result).

### 3.2 Graph-level: `fg.eval.explain(rule, head=, engine=, config=)`

```python
explanation = fg.eval.explain(rule, head=region_rule, engine="native")
```

`fg.eval.explain(...)` is **syntactic sugar over `evaluate + first().explain()`** — the same kwargs as `evaluate`, but internally it runs evaluate, picks the first matching row, and returns its `Explanation`. With one extra check: it requires `head=` to be a *closed* `Rule` (every port bound by an atom in `when`); if `head` has unbound ports it raises `RuleExprError: manual explain head must be closed; unbound ports: <names>` synchronously rather than returning a failed Explanation.

### 3.3 The two diverge only on "no row found"

| Route | If 0 matching rows | If ≥ 1 matching rows |
|---|---|---|
| `row.explain()` | n/a — you already have a row | returns Explanation for that row |
| `fg.eval.explain(rule, head=, ...)` | returns `Explanation(status="failed", failure_class="closed_head_false")` | returns Explanation for the first matching row |

Otherwise both produce the same shape — see §4.

## 4. `Explanation` DTO

### 4.1 Complete nested structure

```text
Explanation (frozen)
│
├── status              : Literal["passed", "failed", "unsupported", "invalid_request"]
│                                  ↑
│                                  └─── controls which other fields are required
│                                       (see invariants below)
│
├── evidence            : EvidenceGraph | None             ← passed iff non-None
│   │                                                        (full structure in §5)
│   ├── graph_id, engine, root_node_id
│   ├── nodes           : tuple[EvidenceNode, ...]
│   ├── edges           : tuple[EvidenceEdge, ...]
│   ├── support_kind, layout_hint, metadata
│   └── (see §5 for nested EvidenceNode / EvidenceEdge)
│
├── claim               : Claim | None                     ← required iff status == "passed"
│   └── (see §2.4 for full Claim shape)
│
├── result_id           : str | None      ("evalr_v1:..." ; required iff status == "passed")
├── row_id              : str | None
├── evidence_ref_id     : str | None      ("evref_v1:...")
│
├── raw_kind            : Literal["probabilistic", "possibilistic"] | None
├── bound               : tuple[float, float] | None       ← None iff raw_kind is None
│
├── failure_class       : Literal[                         ← required iff status == "failed"
│                            "no_matching_row",            │  0 rows matched
│                            "closed_head_false",          │  head false on every row
│                            "stale_row",                  │  row evidence superseded
│                            "row_not_in_result",          │  row id not from this result
│                            "insufficient_closed_bindings"│  reserved; not currently emitted (§4.4)
│                         ] | None                         └─ must be None when status != "failed"
│
├── checked_scope       : Mapping[str, Any] | None
├── suggested_next_steps: tuple[str, ...]                  (default ())
│
├── errors              : tuple[ErrorDTO, ...]
│   └── ErrorDTO
│       ├── code        : str             (SCREAMING_SNAKE_CASE)
│       ├── message     : str
│       ├── path        : tuple[str, ...]
│       └── details     : dict[str, JSONValue]             ← non-empty iff status ∈
│                                                            {"unsupported", "invalid_request"}
│
└── warnings            : tuple[WarningDTO, ...]
    └── WarningDTO      (same shape as ErrorDTO)
```

### 4.2 6 invariants enforced in `__post_init__`

| Invariant | Where checked |
|---|---|
| `status == "passed" iff evidence is not None` | line 276 |
| `status == "passed" → claim is not None` | line 291–293 |
| `status == "passed" → result_id is non-empty` | line 294 |
| `failure_class is set iff status == "failed"` | line 295–299 |
| `bound is None iff raw_kind is None` | line 303–309 |
| `status ∈ {unsupported, invalid_request} → errors non-empty` | line 300–301 |

### 4.3 The four `status` values and what each Explanation actually carries

| status | When | `evidence` | `claim` | `failure_class` | `errors` | What you read |
|---|---|---|---|---|---|---|
| `"passed"` | head fires on at least one row | ✓ EvidenceGraph | ✓ Claim | None | () | `evidence` for the path; `claim` for the head; `raw_kind`+`bound` for uncertainty |
| `"failed"` | head doesn't fire / no match | None | None | ✓ one of 5 | () | `failure_class` to know *why*; `checked_scope` to see what was examined; `suggested_next_steps` for fixes |
| `"unsupported"` | engine rejects the rule shape | None | None | None | ✓ non-empty | `errors[*].code` + `message` for what the engine didn't accept |
| `"invalid_request"` | call shape is malformed | None | None | None | ✓ non-empty | Same as unsupported, but the problem is in your input, not the engine |

### 4.4 `failure_class` — the five reasons a `"failed"` Explanation gives

| `failure_class` | Trigger |
|---|---|
| `no_matching_row` | The body matches no facts at all |
| `closed_head_false` | The body matches but the head bindings are not the ones you asked for |
| `stale_row` | The row referenced by an `EvidenceRef` has been retracted / superseded since evaluation |
| `row_not_in_result` | You passed an `EvidenceRef.row_id` that does not belong to this `result_id` |
| `insufficient_closed_bindings` | Reserved literal — declared in the enum but no current code path emits it. The "head not closed" check on `fg.eval.explain(...)` short-circuits as `RuleExprError` (see §3.2) before an Explanation is built, so this value is currently unreachable |

### 4.5 `raw_kind` + `bound` carry-over

When the source row has uncertainty meta (`raw_kind` + `bound`), the `Explanation` mirrors them at the top level. This is the read-side counterpart to the write-side pairing in `engines_and_configs.md` §2.1. The same invariant holds: `bound is None iff raw_kind is None`.

## 5. `EvidenceGraph` DTO

When `Explanation.status == "passed"`, `Explanation.evidence` is an `EvidenceGraph` — a cross-engine common representation of how the head was supported.

### 5.1 Structure

```text
EvidenceGraph (frozen)
  ├── graph_id          : str
  ├── engine            : str             ← "native" / "problog" / "pyreason"
  ├── root_node_id      : str             ← the conclusion node id (must be in nodes)
  ├── nodes             : tuple[EvidenceNode, ...]
  ├── edges             : tuple[EvidenceEdge, ...]
  ├── support_kind      : str             (e.g. "native_binding_v1")
  ├── layout_hint       : Literal["tree", "timeline"]   (default "tree")
  └── metadata          : Mapping[str, Any]

EvidenceNode (frozen)
  ├── node_id           : str
  ├── node_kind         : Literal["conclusion", "premise", "seed"]
  ├── component         : str
  ├── label             : str
  ├── value_summary     : str
  ├── timestamp         : int | None
  └── engine_meta       : Mapping[str, Any]

EvidenceEdge (frozen)
  ├── edge_id           : str
  ├── from_node_id      : str
  ├── to_node_id        : str
  ├── edge_kind         : Literal["supports", "derives", "updates"]
  ├── rule_label        : str | None
  └── engine_meta       : Mapping[str, Any]
```

### 5.2 `node_kind` and `edge_kind` semantics

| `node_kind` | Meaning |
|---|---|
| `"conclusion"` | The derived head (one per graph; matches `root_node_id`) |
| `"premise"` | An intermediate derived fact |
| `"seed"` | An EDB fact directly from the ledger (no further derivation) |

| `edge_kind` | Meaning |
|---|---|
| `"supports"` | from_node is a non-derived premise of to_node |
| `"derives"` | from_node is a derivation step that produces to_node |
| `"updates"` | from_node updates the bound on to_node (PyReason temporal) |

### 5.3 `layout_hint` — `"tree"` vs `"timeline"`

| `layout_hint` | Used for |
|---|---|
| `"tree"` (default) | Static support graphs — Native Form 1, ProbLog Form 1, Souffle witnesses, etc. |
| `"timeline"` | Temporal evidence — PyReason multi-timestep traces (deferred per [D11](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) — not currently produced) |

### 5.4 Per-engine richness today

| Engine | EvidenceGraph fidelity |
|---|---|
| Native (`engine="native"`) | Form 1 binding-level support graph — shipped |
| Souffle | Form 1 witness — shipped via `SOUFFLE_WITNESS_KIND` |
| ProbLog | Form 1 binding-level + provenance graph with `EDGE_DERIVES` — shipped |
| PyReason | Form 1 single-conclusion fallback — shipped. **Form 2 timeline (multi-timestep bound updates) deferred** — see [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.1 (D11) |

## 6. The closed-head concept

"Closed head" appears in several places in this chapter — it's the same idea each time, worth pulling out once.

### 6.1 What a closed head is

A `Rule` whose `when` *closes* every `port`: every port's `Var` is bound either by an existing atom in `when`, or by an additional atom appended at close-time that pins the port to a specific value.

For a single-row context, the per-row closed head is built by appending extra `PredAtom` / `CmpAtom` for the row's port bindings:

```text
# Open head (the rule you authored)
Rule(
    id="user:region",
    when=(PredAtom("user:region", [u, r]),),
    ports={"user": u, "region": r},
)

# Per-row closed head (built by row.close())
Rule(
    id="user:region_closed_<row_id>",
    when=(
        PredAtom("user:region", [u, r]),    # original
        # + atoms that pin u to a specific entity_ref
        # + atoms that pin r to a specific value
    ),
    ports={"user": u, "region": r},
    desc=<carried over from open head>,
)
```

### 6.2 Where the closed head appears

| Place | Closed-head role |
|---|---|
| `row.close()` (§2.3) | Produces the closed-head `Rule` for a given row |
| `row.explain()` / `fg.eval.explain(...)` (§3) | Both internally close the head and check it against the row's bindings |
| `EvidenceRef.closed_head_digest` (§2.5) | The stable `sha256:` digest of the closed head — same body & same bindings → same digest |
| `fg.rules.inspect(...)` ([`rules.md`](rules.md) §4) | `RuleExprInspect.is_closed` / `unbound_ports` reports closure status of a non-row Rule |

### 6.3 `desc` carries through

If the open head has a `desc` template (e.g. `"User %user is in %region"`, see [`rules.md`](rules.md) §2.5), the closed head receives the same template — letting downstream renderers walk the closed-head chain and produce per-row descriptions. The evaluation runtime does **not** auto-render this; rendering is the consumer's choice via `row.close().render_desc({"user": ..., "region": ...})` or the `RuleExprInspect.render(...)` path. See [`rule-namespace-rulespec-redesign.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.6 (D21) for the open-design future where this surfaces automatically in `Explanation` payloads.

## 7. `fg.audit` — post-hoc per-cell inspection

`fg.audit` is a different surface from `fg.eval` — it works **per ledger cell** (the `(pred_id, e_ref, value)` triple) rather than per evaluation row. Three methods:

| Method | What it answers |
|---|---|
| `fg.audit.explain(target)` | "For this assertion's cell, which `asrt_id` is the *chosen* one under the current conflict-resolution policy, and why?" Returns a dict with `chosen` (bool), `chosen_asrt_id`, plus policy diagnostics |
| `fg.audit.conflicts(target)` | "What conflicting active assertions are there at this cell?" Returns conflict diagnostics for the cell |
| `fg.audit.diff_proof_frames(...)` | "Compare two recorded proof-frame outcomes — what changed between them?" Useful after re-evaluation |

`target` for `explain` / `conflicts` can be an `AssertionRecord`, an `(EntityCls, identity_kwargs)` tuple resolving to a single cell, or any other object the SDK can resolve via `_resolve_record_asrt_id`. These are diagnostics — they neither write to the ledger nor trigger evaluation.

## 8. What's deferred

This chapter covers the shipped surface. Several user-facing capabilities are *designed* but not yet exposed in the SDK:

| Capability | Status | Where designed |
|---|---|---|
| `fg.diagnose(...)` SDK public surface | Internal application-layer logic shipped; SDK shell deferred | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.2 (D1) |
| Why-not / counterfactual explanation | Deferred — only `failure_class="closed_head_false"` available today | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.2 (D5) |
| PyReason multi-timestep timeline evidence | Deferred — current PyReason `EvidenceGraph` is single-conclusion fallback | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.1 (D11) |
| Attribution / salience decomposition | Deferred (D6 / D7) | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.3 |
| Match witness `as_assertions() / witnesses() / to_view()` | Deferred — `fg.entities.match` returns snapshots only today | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.5 (D20) |
| Desc auto-render in `Explanation` payloads | Deferred — only `row.close().render_desc(...)` / `RuleExprInspect.render(...)` consume `desc` today (see §6.3) | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.6 (D21) |

## 9. Reference

### 9.1 Types

```python
# Runtime entry points
from factgraph.sdk import FactGraph              # fg.eval.evaluate, fg.eval.explain
                                                 # fg.audit.explain, fg.audit.conflicts, fg.audit.diff_proof_frames

# DTOs (frozen)
from factgraph.sdk import (
    Claim,           # row.claim (kind / name / arguments / repr / digest)
    EvidenceRef,     # row.evidence_ref (ref_id / result_id / row_id / fact_digest / closed_head_digest)
    EvaluateResult,  # what fg.eval.evaluate returns
    EvaluateRow,     # in result.rows / result.first() / iter(result)
    Explanation,     # what fg.eval.explain / row.explain() returns
    DetachedRowError,  # raised by row.explain() if parent result GC'd
)

# Application-layer rule construction (for §1.1 minimal example)
from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import PredAtom, CmpAtom, Var, Const, NotAtom

# Audit-layer evidence types (typically reached through Explanation.evidence)
from factgraph.audit.evidence_graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceEdge,
    LAYOUT_TREE, LAYOUT_TIMELINE,
    EDGE_SUPPORTS, EDGE_DERIVES, EDGE_UPDATES,
    NODE_CONCLUSION, NODE_PREMISE, NODE_SEED,
)
```

### 9.2 Errors

| Error | Raised by |
|---|---|
| `SDKStoreError: evaluate(rule_expr, ...) requires head= Rule` | `fg.eval.evaluate` without `head=` |
| `SDKStoreError: evaluate(rule_expr, ...) head= must be Rule` | `head=` is a non-Rule value (SDK DSL Rule, Inference, dict, str, inspect object) |
| `SDKStoreError: eval.explain(...) head= must be Rule` | Same constraint on `fg.eval.explain` |
| `RuleExprError: manual explain head must be closed; unbound ports: <names>` | `fg.eval.explain(head=...)` with a head whose `when` does not bind every port |
| `RuleExprError: head rule '<id>' matches an expression occurrence with a different content digest` | RuleExpr with head whose id matches an occurrence but content differs (§1.2 stale binding) |
| `RuleExprError: head rule '<id>' matches multiple expression occurrences with the same content digest` | The same Rule appears more than once in the RuleExpr without distinct `.as_()` aliases (§1.2) |
| `RuleExprError: RuleExpr head validation failed: head port '<name>' is only declared in some RuleExpr branches` | OR expression where the head port is present in some branches but not all (§1.2 port-shape contract) |
| `WhereValidationError: target predicate not found: <id>` | Rule's `id` is not a known ledger predicate |
| `DetachedRowError` | `row.explain()` after the parent `EvaluateResult` has been garbage-collected |
| `ProtocolShapeError` (various) | `Explanation` / `Claim` / `EvidenceGraph` invariant violations at construction |

### 9.3 Method signatures by namespace

```python
# fg.eval (evaluation surface — see also engines_and_configs.md for engine= / config=)
fg.eval.evaluate(rule_or_expr, *, head, engine=None, config=None) -> EvaluateResult
fg.eval.explain(rule_or_expr, *, head, engine=None, config=None) -> Explanation
fg.eval.preview_config(profile_or_config) -> dict          # (see engines_and_configs.md §6)

# row methods
row.explain() -> Explanation
row.close() -> Rule

# fg.audit (post-hoc per-cell)
fg.audit.explain(target) -> dict       # chosen-policy state for a cell
fg.audit.conflicts(target) -> dict     # conflict diagnostics for a cell
fg.audit.diff_proof_frames(...) -> ... # compare two recorded proof outcomes
```

### 9.4 Related chapters

- [`rules.md`](rules.md) — `Rule` / `RuleExpr` / `head` declaration, and `fg.rules.inspect`
- [`engines_and_configs.md`](engines_and_configs.md) — `engine=` / `config=` parameters consumed by `evaluate`
- [`data_model.md`](data_model.md) §2.2 — the `raw_kind` + `bound` meta keys that surface on `EvaluateRow` and `Explanation`
- [`assertions.md`](../official/kernel/quickstart/assertions.md) — assertion-level read APIs that `fg.audit.explain` / `conflicts` resolve against
- [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) — the deferred capabilities listed in §8
