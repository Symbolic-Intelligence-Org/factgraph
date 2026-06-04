# Evaluation and evidence

This chapter has two halves stitched into one chapter because they share too much vocabulary to live apart: running a rule (`fg.eval.evaluate(...)` and its result) and reading what the evaluator returned (the `Explanation` DTO and its `EvidenceGraph`). It builds on [`engines_and_configs.md`](engines_and_configs.md) (the `engine=` / `config=` parameters) and [`rules.md`](rules.md) (the `Rule` / `RuleExpr` / `head` declaration shape).

## 1. `fg.eval.evaluate` — running a rule

### 1.1 Minimal end-to-end

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity, build_application_rule, vars

class User(Entity):
    user_id: str = Identity()
    region: str = Field()

fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.region, alice, "US")

with vars("u", "r") as (u, r):
    region_rule = build_application_rule(
        id="user_region_lookup",
        version="v1",
        when=[User(u).region == r],
        ports={"user": u, "region": r},
    )

result = fg.eval.evaluate(region_rule, head=region_rule)
```

This is the canonical user-facing form: `build_application_rule(...)` with Entity-DSL atoms (see [`rules.md`](rules.md) §2.2).

> **Current shipped status — known gap.** `build_application_rule(when=[User(u).field == v])` lowering auto-prepends `PredAtom("User:exists", [u])`. `fg.entities.create(...)` does not currently emit `User:exists` claims to the ledger, so the body above does not match anything and `result.count()` returns `0` today. The example shows the form you *should* write. Until the gap closes, demonstrations later in this chapter that need live rows fall back to a direct `Rule(...)` + `PredAtom(...)` construction (see §2.1).

### 1.2 `head=` parameter

`head=` is mandatory and supplies the `Rule` whose `ports` shape the output rows. `head.id` (= `rule.id`) is a free-form label — any non-empty string works; it does not need to match any schema predicate.

```python
fg.eval.evaluate(rule, head=rule)                    # single Rule
fg.eval.evaluate(rule_expr, head=some_rule)          # RuleExpr: head can be in OR out of the expression
```

Input-shape rejections (full messages in §8.2):

- missing `head=`
- `head=` is not an **application-protocol** `Rule` (`factgraph.application.protocol.Rule`). The SDK DSL `Rule` (`factgraph.sdk.Rule`, the ergonomic authoring class — see [`rules.md`](rules.md) §2) is a different class and is rejected here; lower it via `build_application_rule(...)` first. `Inference`, `dict`, `str`, and inspect objects are also rejected.

#### How `head=` connects to a `RuleExpr`

Mental model — `fg.eval.evaluate(rule_expr, head=head_rule)` is equivalent to:

```python
(head_rule & rule_expr).join_by_ports(*head_rule.ports)
```

and projecting result rows onto `head_rule.ports`. The SDK derives the join from `head_rule.ports`; you do not write it. The underlying `.join_by_ports(...)` machinery is in [`rules.md`](rules.md) §3.3.

Port flow — head asks for a *subset*; the join is by name:

```text
                  ┌──────┬──────┬────────┬───────┐
head_rule.ports   │ user │      │ region │       │   ← head asks for a subset
                  └──┬───┴──────┴───┬────┴───────┘
                     │ implicit     │ implicit
                     │ join         │ join
                     │ by name      │ by name
                     ▼              ▼
                  ┌──────┬──────┬────────┬───────┐
rule_expr ports   │ user │ name │ region │ party │   ← extras (name, party)
                  └──────┴──────┴────────┴───────┘     stay internal to expr
                              │
                              ▼
                  result.rows.bindings = {"user": …, "region": …}
```

| Relationship | Accepted? | Error |
|---|---|---|
| `head.ports ⊆ every branch's ports` | ✓ | — |
| `head.ports` has a name not in *some* branches | ✗ | `head port '<name>' is only declared in some RuleExpr branches` |
| `head.ports` has a name not in *any* branch | ✗ | `head port '<name>' is not declared by the RuleExpr` |
| Branches declare more ports than `head.ports` | ✓ | — (extras internal to `rule_expr`) |

Whether `head.id` happens to appear in the expression is incidental — both produce the same evaluation; the difference only surfaces in identity-validation errors:

| Identity flavor | Detected by | Side effect |
|---|---|---|
| **inline** | `head.id == occurrence.rule_id` AND `head.content_digest == occurrence.content_digest` for exactly one occurrence | Different `version` on the same id+digest emits a `UserWarning` |
| **external** | head's `id` does not appear in any occurrence | None |

Two identity-validation `RuleExprError`s — stale `content_digest` (same id, different body) and duplicate same-digest occurrences (same Rule appears twice without distinct `.as_()` aliases). Full messages in §8.2.

## 2. `EvaluateResult` navigation and `EvaluateRow`

> **Live-row workaround for the rest of this chapter.** Per §1.1's shipped-status note, `build_application_rule` paths return 0 rows on the unattached default workspace today. To demonstrate `result.first()`, `row.bindings`, `row.explain()` etc. with actual values, the remainder of this chapter uses the direct construction form from [`rules.md`](rules.md) §2.6:
>
> ```python
> result = fg.eval.evaluate(region_rule, head=region_rule)
> # result yields one row per matching (user, region) fact in the ledger
> ```
>
> The `EvaluateResult` / `EvaluateRow` / `Explanation` shapes documented from §2 onward apply identically to both paths; the workaround is only about *producing* rows in shipped today.

### 2.1 `EvaluateResult` — the frozen output of one evaluate call

`EvaluateResult` is everything one `fg.eval.evaluate(...)` call produced: the matched rows plus the identifiers and digests that uniquely fingerprint *this evaluation* (engine, head, config, ledger snapshot). The `fingerprint` sub-object answers "have I already run this exact evaluation?"; the row tuple is what you iterate to read the matches.

```text
EvaluateResult (frozen)
  ├── result_id: str             ← stable identifier ("evalr_v1:...")
  ├── rows: tuple[EvaluateRow, ...]
  ├── head: Rule                 ← the head you passed
  ├── engine: str                ← engine name, e.g. "native" / "souffle" / "problog" / "pyreason"
  ├── evaluated_at: object       ← when this evaluate call ran (SDK constructs UTC datetime; type is loose by design)
  ├── fingerprint: ResultFingerprint
  │   ├── run_id                 ← stable run identifier ("run_v1:...")
  │   ├── expr_digest, rule_set_digest, view_snapshot_digest, config_digest
  │   └── result_digest          ← content-addressed over everything above
  └── engine_meta: Mapping[str, Any]
      ├── engine_version
      └── adapter_version
```

Field order above is the dataclass's constructor signature.

The 6 user-facing methods (all delegating to the `rows` tuple):

| Method | Returns | Use when |
|---|---|---|
| `iter(result)` | `Iterator[EvaluateRow]` | streaming over rows |
| `len(result)` | `int` | known row count |
| `result[i]` | `EvaluateRow` | random access by index |
| `result.first()` | `EvaluateRow \| None` | head row, `None` if empty |
| `result.exists()` | `bool` | "any rows?" shortcut |
| `result.count()` | `int` | row count (same as `len(result)`) |

The remaining fields (`result_id`, `engine`, `fingerprint`, and `engine_meta`) are for cache / audit / equivalence — they answer "is this the same evaluation we already ran?" Each `fingerprint` digest fingerprints one input axis:

| Digest | Hash over | "Same digest" means |
|---|---|---|
| `expr_digest` | The lowered `(rule_or_rule_expr, head)` combination — the canonical lowering plan | Same expression compiled to the same head |
| `rule_set_digest` | Sorted `(rule_id, rule.content_digest)` pairs for every rule referenced by the expression | None of the rules involved changed body |
| `view_snapshot_digest` | `(db_id, base_tx_id, schema_digest, sorted asrt_ids)` of the ledger snapshot used | Same ledger state — same facts, same schema, same head transaction |
| `config_digest` | The full lowered `SemanticsProfile` (engine, all projections, fallback). `None` when no `config=` was passed | Same semantics config (or both ran without one) |

Together they fingerprint every input the evaluator considered. `fingerprint.result_digest` hashes over all four plus head metadata — same `fingerprint.result_digest` ⇒ guaranteed same `rows`.

### 2.2 `EvaluateRow` — one match per row

Each `EvaluateRow` is one match — one `(rule body, ledger fact-set)` binding that satisfied the body. The fields say what the body matched (`bindings`), what the rule's head looked like for this match (`kind` / `digest`), what uncertainty the row carries from the source facts (`raw_kind` / `bound`), and what closed-head replay anchor supports it (`closed_head_digest`):

```text
EvaluateRow (frozen)
  ├── row_id: str
  ├── bindings: Mapping[str, Any]   ← port-name → typed term map (see below)
  ├── kind: ClaimKind               ← row conclusion role
  ├── digest: str                   ← row claim digest
  ├── closed_head_digest: str       ← stable replay input for this row
  ├── raw_kind: "probabilistic" | "possibilistic" | None
  ├── bound: tuple[float, float] | None
  └── _result_resolver              ← internal; powers row.explain()
```

```python
row = result.first()

row.row_id                    # str
row.bindings                  # Mapping — port-name → typed term map
result.head.id                # "user_region_lookup" — the head label
row.kind                      # "fact_triple" — row conclusion role
row.digest                    # "sha256:..." — content digest for this row claim
row.raw_kind                  # None (no uncertainty meta on the source claims)
row.bound                     # None (paired with raw_kind, see engines_and_configs.md §2.1)
row.closed_head_digest        # "sha256:..." — stable replay input for this row
```

#### `row_id` — stable per-row identifier

Computed deterministically from `(run_id, bindings)` via `row_id_for(run_id, bindings)`. Same `run_id` + identical `bindings` → same `row_id`. The cross-process row handle is the pair `(result_id, row_id)`.

#### `bindings` — port-name → typed term map

`row.bindings` is a frozen mapping keyed by `head.ports`. Each row is one *assignment* of all head ports to typed terms — not one matched fact, and not necessarily tied to a single entity.

Each binding value is a typed term dict discriminated by `kind`:

| `kind` | Shape | Source |
|---|---|---|
| `entity_ref` | `{"kind": "entity_ref", "value": "<idref_v1:...>"}` | Port resolved to an entity reference |
| `literal` | `{"kind": "literal", "tag": "<type>", "value": <python_value>}` | Port resolved to a typed literal. `tag` ∈ `{string, int, bool, float64, bytes, time, uuid}` |

Example — native engine over a `PredAtom` head body with `ports = {"user": …, "region": …}`:

```python
dict(row.bindings)
{
  "user":   {"kind": "entity_ref", "value": "idref_v1:User:<digest>"},   # user = "idref_v1:User:<digest>"
  "region": {"kind": "literal", "tag": "string", "value": "US"},         # region = "US"
}
```

Per-row variation lives entirely in `bindings` (the head label `result.head.id` is constant across rows). Two rows over two users would carry alice's idref + `"US"` vs bob's idref + `"DE"`; a head like `order:buyer` whose ports are both entity-typed produces rows with multiple `entity_ref` terms keyed by their declared port names.

Programmatic access: `row.bindings[port_name]["value"]` for both term kinds.

#### `kind` and `digest` — what was concluded

`kind` records the conclusion role; `digest` is the `sha256:` content-addressed digest over the canonical `(kind, head.id, bindings)` form for this row's claim, via `claim_digest_for(kind, head.id, bindings)`.

| `kind` | Meaning |
|---|---|
| `"fact_triple"` | A ledger fact — `(pred_id, e_ref, value)` triple form |
| `"rule_head"` | A derived head from rule evaluation |
| `"aggregate_result"` | An aggregate (`agg_count` / `agg_sum` / ...) result |
| `"projection"` | A `Rule.projection(...)` synthetic projection output |

The on-disk ledger has its own `Claim` record (`factgraph.core.store.ledger.Claim`, see [`data_model.md` §1](data_model.md)) at a lower layer — `EvaluateRow.kind` and `EvaluateRow.digest` are evaluation outputs, not ledger primary keys.

#### `closed_head_digest` and `row.close()` — replay anchor

`row.close()` returns the **closed-head `Rule`** for this row — the original head's `when` plus extra atoms pinning every port to the row's matched values. It is the structural input that `fg.eval.explain(...)` / `fg.rules.inspect(...)` consume (concept depth in §5).

`row.closed_head_digest` is the `sha256:` digest of that closed-head Rule, computed as `closed_head_digest_for_parts(closed_head.id, closed_head.content_digest)`. It is **not** the evidence itself (evidence lives in `EvidenceGraph`, §4.4) — it is the deterministic answer to "is this the same closed head we explained last time?"

Two evaluations over the same `(rule, head, engine, config, ledger snapshot)` produce the same `row.digest` and `row.closed_head_digest`, even if `result_id` / `run_id` change.

#### `raw_kind` + `bound` — uncertainty carry-through

`raw_kind` / `bound` carry through from the source assertion's `meta` (per [`engines_and_configs.md`](engines_and_configs.md) §2.1). They are `None` on rows whose source facts have no uncertainty annotation. Invariant from [`data_model.md`](../official/kernel/quickstart/data_model.md) §2.2: `bound is None iff raw_kind is None`.

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

## 4. Explanation: the layered evidence model

`Explanation` is built around the same three reasoning tiers a human uses to read a derivation: *which rules combine into the conclusion*, *which conditions each rule needs*, and *what backs each condition*. Slices γ, η, and ε reshaped the DTO so those tiers are first-class — the rest of this section is a tour of that shape, from concept to wire fields to rendered text.

### 4.1 The three tiers

```
head & RuleExpr   ─ tier 1: composition layer (single / and / or)
       │
       ▼
     Rule         ─ tier 2: one rule occurrence with a linear body
       │
       ▼
     Atom         ─ tier 3: one body condition + status + reason
       │
       ▼
    [seed]              ledger fact backing the atom (when present)
```

**Concrete example.** Given this rule with three body atoms:

```python
from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import PredAtom, CmpAtom, Var

u, age = Var("u"), Var("age")

adults_in_us = Rule(
    id="adults_in_us",
    version="v1",
    when=(
        PredAtom("user:region", [u, "US"]),   # atom 0 — schema predicate match
        PredAtom("user:age",    [u, age]),    # atom 1 — schema predicate match
        CmpAtom(">", age, 18),                # atom 2 — computed check
    ),
    ports={"user": u},
    desc="Adult user %user lives in the US",  # auto-rendered into Conclusion line
)
```

…and ledger facts `user:region(alice, "US")` + `user:age(alice, 25)`, the matching row's `Explanation.evidence` is this layered graph:

```
NODE_CONCLUSION    adults_in_us(user=alice)  [row-1]
       │
       │ EDGE_DERIVED_BY                                              ← tier 1
       ▼
NODE_RULE_EXPR     engine_meta.ast_form = "single"
       │
       │ EDGE_USES                                                    ← tier 1 → 2
       ▼
NODE_RULE          engine_meta.rule_id = "adults_in_us"
       │
       │ EDGE_HAS_ATOM ×3                                             ← tier 2 → 3
       ├──▶ NODE_ATOM[0]   atom_status="support"
       │       │  EDGE_SUPPORTED_BY
       │       ▼
       │     NODE_SEED     ledger fact: user:region(alice, "US")
       │
       ├──▶ NODE_ATOM[1]   atom_status="support"
       │       │  EDGE_SUPPORTED_BY
       │       ▼
       │     NODE_SEED     ledger fact: user:age(alice, 25)
       │
       └──▶ NODE_ATOM[2]   atom_status="support"
                engine_meta.reason = {"kind": "cmp", "status": "satisfied", …}
                (computed check — no seed)
```

Walking the tiers on this graph:

- **Tier 1 (head & RuleExpr)** — one `NODE_RULE_EXPR` saying "this conclusion came from a rule expression". `ast_form="single"` because exactly one rule produces it. The wiring (`EDGE_USES` from rule_expr to ≥1 rule) is in place for future `and`/`or` composition, but `ast_form` is **currently hardcoded `"single"`** for every passed row; today every rule_expr points to exactly one rule.
- **Tier 2 (Rule, linear)** — one `NODE_RULE` per rule with `engine_meta.rule_id` / `content_digest` / `version`, then `EDGE_HAS_ATOM` enumerating every body atom in declaration order. Tier 2 answers "which rule fired and what conditions did it require?" — here three atoms in the order they appear in `when=`.
- **Tier 3 (Atom)** — one `NODE_ATOM` per body atom, each carrying `atom_status` (**binary today**: `"support"` if the atom held, `"unknown"` if not; no separate `"unsupport"` value). The two `PredAtom`s each link to a `NODE_SEED` (the actual ledger fact) via `EDGE_SUPPORTED_BY`; the `CmpAtom` carries its outcome in `engine_meta.reason = {kind, status, details}` instead because it's a computed check, not a ledger lookup. `reason` is populated for native non-fact steps (`cmp` / `not` / etc.); ProbLog and Souffle atom nodes don't currently carry it.

The walker (§4.5) renders this graph DFS from the conclusion, one indented line per node, with the connector coming from each incoming `edge_kind`. Shipped native engine produces:

```
Conclusion: Adult user idref_v1:User:<digest> lives in the US [row-1]
  is derived by RuleExpr(single)
    which uses Rule "adults_in_us"
      which has atom Atom[0]: satisfied — support
        is supported by ledger fact: ledger assertion
      which has atom Atom[1]: satisfied — support
        is supported by ledger fact: ledger assertion
      which has atom Atom[2]: satisfied — support
```

Each line is `<indent><connector> <render(node)>`. Two things to know about what's informative vs terse:

- **Conclusion line** uses `head.render_desc(row.bindings)` to substitute each `%port` in the desc template with the row's binding value (entity_ref ports show their `idref_v1:` token, literal ports show the public value). If `head.desc is None`, the Conclusion line falls back to `head.id + repr(bindings)` form.
- **Atom and seed lines are terse** — the engine populates `value_summary` with the status token (`"satisfied"`) for atoms and the literal string `"ledger assertion"` for seeds, not the atom expression or the underlying ledger triple. You can recover the original predicate / atom expression from the node's `label` field (e.g. `"Predicate witness user:region"` / `"cmp check"`), or `engine_meta.atom_kind` / `engine_meta.atom_id` / `engine_meta.reason`, but the walker doesn't surface them — atom-level NL render is future work.

### 4.2 `Explanation` DTO

```
Explanation (frozen)
├── status                 Literal["passed", "failed", "unsupported", "invalid_request"]
├── evidence               EvidenceGraph | None             ← non-None iff status == "passed"
├── row                    EvaluateRow | None               ← required iff status == "passed"
├── result_id              str | None                       ← required iff status == "passed";
│                                                            otherwise must start with "evalr_v1:" if set
├── failure_class          ExplanationFailureClass | None = None   ← required iff status == "failed"
├── checked_scope          Mapping[str, Any] | None = None
├── suggested_next_steps   tuple[str, ...] = ()
├── errors                 tuple[ErrorDTO, ...] = ()        ← non-empty iff status ∈ {unsupported, invalid_request}
├── warnings               tuple[WarningDTO, ...] = ()
└── repr  (@property)      tuple[str, ...] | None           ← lazy, cached in private _repr_cache;
                                                              NOT a constructor field
```

Field order above is the constructor's positional order (`status`, `evidence`, `row`, `result_id`, ...).

`ErrorDTO` / `WarningDTO` share one shape: `code: str` (SCREAMING_SNAKE_CASE), `message: str`, `path: tuple[str, ...]`, `details: dict[str, JSONValue]`.

Five invariants enforced in `Explanation.__post_init__`:

1. `status == "passed" iff evidence is not None`
2. `status == "passed" → row is not None`
3. `status == "passed" → result_id is non-empty`
4. `failure_class is set iff status == "failed"`
5. `status ∈ {"unsupported", "invalid_request"} → errors non-empty`

Compose by reference, not by inline duplication. The pre-α flat fields (`claim` / `row_id` / `evidence_ref_id` / `raw_kind` / `bound`) are gone — read `explanation.row.bindings`, `explanation.row.raw_kind`, etc. Cross-process row handle is `(explanation.result_id, explanation.row.row_id)`.

### 4.3 Status outcomes

| status | When | `row` | `evidence` | `failure_class` | `errors` | `repr` |
|---|---|---|---|---|---|---|
| `"passed"` | Head fires on a row | ✓ | ✓ | None | () | Walker-rendered multi-line tree |
| `"failed"` | Head doesn't fire / row stale / row not in this result | None | None | one of 5 | () | Flat deterministic summary |
| `"unsupported"` | Engine rejects the rule shape | None | None | None | ≥1 | None |
| `"invalid_request"` | Call shape malformed | None | None | None | ≥1 | None |

Five `failure_class` literals:

| failure_class | Trigger |
|---|---|
| `no_matching_row` | Body matched 0 facts |
| `closed_head_false` | Body matched but head bindings differ from the one you asked about |
| `stale_row` | Row handle retracted/superseded after evaluation |
| `row_not_in_result` | Row's `row_id` doesn't belong to this `result_id` |
| `insufficient_closed_bindings` | Reserved literal; not emitted today. The "head not closed" check on `fg.eval.explain(...)` short-circuits as `RuleExprError` (§3.2) before an Explanation is built |

### 4.4 `EvidenceGraph` — the substrate for the three tiers

When `status == "passed"`, `Explanation.evidence` is an `EvidenceGraph` carrying the tier-1/2/3 nodes and edges as a frozen graph:

```
EvidenceGraph (frozen)
├── graph_id          str
├── engine            str           ← "native" / "souffle" / "problog" / "pyreason"
├── root_node_id      str           ← must be in nodes
├── nodes             tuple[EvidenceNode, ...]
│       └─ EvidenceNode (frozen):
│              node_id: str, node_kind: str, component: str, label: str,
│              value_summary: str, timestamp: int | None = None,
│              engine_meta: Mapping[str, Any] = {}
├── edges             tuple[EvidenceEdge, ...]
│       └─ EvidenceEdge (frozen):
│              edge_id: str, from_node_id: str, to_node_id: str, edge_kind: str,
│              rule_label: str | None = None,
│              engine_meta: Mapping[str, Any] = {}
├── support_kind      str           ← e.g. "native_binding_v1"
├── layout_hint       str = "tree"  ← "tree" | "timeline" (D11 timeline deferred)
└── metadata          Mapping[str, Any] = {}
```

Graph-level validators (`EvidenceGraph.__post_init__`): node_ids unique, edge_ids unique, every edge endpoint in nodes, `root_node_id` in nodes, no cycles via DFS over the inverted adjacency.

**Node kinds** — which tier each maps to:

| node_kind | Tier | Carries |
|---|---|---|
| `conclusion` | top of tree | The row claim; equals `root_node_id` |
| `rule_expr` | tier 1 | `engine_meta.ast_form` (`"single"` today; reserved for `"and"`/`"or"`) |
| `rule` | tier 2 | `engine_meta.rule_id`, `content_digest`, `version` |
| `atom` | tier 3 | `engine_meta.atom_status` (`"support"` / `"unknown"`), `atom_kind`, `atom_index`, optional `reason` |
| `seed` | beneath tier 3 | A ledger fact directly supporting an atom (no further derivation) |
| `premise` | legacy | Intermediate derived fact (still used inside ProbLog adapter trace beneath the row atom) |

**Edge kinds** — physical direction is `from_node` = supporter, `to_node` = supported:

| edge_kind | Tier connection |
|---|---|
| `derived_by` | rule_expr → conclusion |
| `uses` | rule → rule_expr |
| `has_atom` | atom → rule |
| `supported_by` | seed → atom |
| `supports` / `derives` / `updates` | Legacy adapter-internal flows beneath atoms (ProbLog provenance chain, PyReason temporal bound updates) |

Read edge names semantically (`conclusion is derived by rule_expr`) — the physical arrow points the opposite way. The walker traverses each node's incoming edges from `root_node_id`, which is why reader-side traversal matches the rendered indentation.

### 4.5 `Explanation.repr` — the rendered text

`Explanation.repr` (a `tuple[str, ...] | None`) is a **computed property** added by slice ε. Lazy, cached in a private `_repr_cache` field, never settable via constructor (`Explanation(repr=...)` is rejected). Built by `factgraph.application.protocol.explanation_render.walk_evidence(graph, *, row, status, failure_class)`.

**Passed — DFS walk of the layered graph.** Each line is `<indent><connector> <render(node)>`. The indent is `"  " * depth` (one level per tier). The connector is the natural-language form of each incoming edge's `edge_kind`. The per-node render formula is fixed:

| Node kind | Rendered as | Reads |
|---|---|---|
| `NODE_CONCLUSION` | `Conclusion: <summary> [<row_id>]` (`NOT concluded: ...` when failed) | `value_summary` ← `head.render_desc(row.bindings)` from `_row_conclusion_node`, falls back to `head.id + repr(bindings)` when `head.desc is None` |
| `NODE_RULE_EXPR` | `RuleExpr(<ast_form>)` | `engine_meta.ast_form` (hardcoded `"single"` today) |
| `NODE_RULE` | `Rule "<rule_id>"` | `engine_meta.rule_id` |
| `NODE_ATOM` | `Atom[<atom_index>]: <summary> — <atom_status>` | `engine_meta.atom_index` + `value_summary` (shipped: status token `"satisfied"`) + `engine_meta.atom_status` (`"support"` / `"unknown"`) |
| `NODE_SEED` | `ledger fact: <summary>` | `value_summary` (shipped: `"ledger assertion"`) |

Edge-connector mapping (`explanation_render.py:_EDGE_CONNECTORS`):

| `edge_kind` | Connector |
|---|---|
| `derived_by` | `is derived by` |
| `uses` | `which uses` |
| `has_atom` | `which has atom` |
| `supported_by` / `supports` | `is supported by` |
| `derives` | `derives` |
| `updates` | `updates` |

§4.1 walks the `adults_in_us` rule through this machinery as a worked end-to-end example.

**Failed — deterministic flat summary** (no graph walk; `evidence is None` by invariant):

```
NOT concluded
failure_class: closed_head_false
result_id: evalr_v1:...                  (when explanation.result_id is set)
row_id: row-1                            (when explanation.row is set)
next_step: ...                           (one line per suggested_next_steps entry)
```

**Unsupported / invalid_request** — `repr` is `None`. Read `errors[*].code` + `errors[*].message`.

### 4.6 Per-engine fidelity today

| Engine | tier 1 rule_expr | tier 2 rule | tier 3 atom | seed | Notes |
|---|---|---|---|---|---|
| Native | ✓ | ✓ | ✓ with `reason` for non-fact steps | ✓ | Full 4-tier walk |
| Souffle | ✓ | ✓ | ✓ | ✓ | Full 4-tier walk via `SOUFFLE_WITNESS_KIND` |
| ProbLog | ✓ | ✓ | ✓ (one synthetic `problog_trace` atom) | ✓ | Adapter `NODE_PREMISE` + `EDGE_DERIVES` chain remains beneath the row-level atom node |
| PyReason | ✓ | ✓ | minimal (`atom_status="unknown"` or omitted) | — | L1/L2 shell only; Form 2 timeline (D11) deferred |

### 4.7 `raw_kind` + `bound` carry-over

When the source row has uncertainty meta (`raw_kind` + `bound`), `Explanation.row` carries those fields — read-side counterpart to the write-side pairing in [`engines_and_configs.md`](engines_and_configs.md) §2.1. Invariant on the row: `bound is None iff raw_kind is None`.

## 5. The closed-head concept

"Closed head" appears in several places in this chapter — it's the same idea each time, worth pulling out once.

### 5.1 What a closed head is

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

### 5.2 Where the closed head appears

| Place | Closed-head role |
|---|---|
| `row.close()` (§2.2) | Produces the closed-head `Rule` for a given row |
| `row.explain()` / `fg.eval.explain(...)` (§3) | Both internally close the head and check it against the row's bindings |
| `row.closed_head_digest` (§2.4) | The stable `sha256:` digest of the closed head — same body & same bindings → same digest |
| `fg.rules.inspect(...)` ([`rules.md`](rules.md) §4) | `RuleExprInspect.is_closed` / `unbound_ports` reports closure status of a non-row Rule |

### 5.3 `desc` carries through

If the open head has a `desc` template (e.g. `"User %user is in %region"`, see [`rules.md`](rules.md) §2.5), the closed head receives the same template — letting downstream renderers walk the closed-head chain and produce per-row descriptions.

**Auto-rendered into `Explanation.repr`.** During layered-graph construction, `_row_conclusion_node` calls `head.render_desc(row.bindings)` and stores the rendered string as the conclusion node's `value_summary`. The walker (§4.5) then surfaces that as the first line of `Explanation.repr`. When `head.desc` is `None`, the conclusion line falls back to `head.id + repr(bindings)` so the field is always populated. The `Rule.desc` is also exposed verbatim on the conclusion node's `engine_meta["desc_template"]` for consumers that want the un-substituted template.

**Manual escape hatches remain available.** `row.close().render_desc({"user": ..., "region": ...})` and the `RuleExprInspect.render(...)` path stay as low-level options when a consumer needs templated text outside the `Explanation.repr` walker output (for example, custom UI rendering that bypasses the layered graph traversal).

## 6. `fg.audit` — post-hoc per-cell inspection

`fg.audit` is a different surface from `fg.eval` — it works **per ledger cell** (the `(pred_id, e_ref, value)` triple) rather than per evaluation row. Three methods:

| Method | What it answers |
|---|---|
| `fg.audit.explain(target)` | "For this assertion's cell, which `asrt_id` is the *chosen* one under the current conflict-resolution policy, and why?" Returns a dict with `chosen` (bool), `chosen_asrt_id`, plus policy diagnostics |
| `fg.audit.conflicts(target)` | "What conflicting active assertions are there at this cell?" Returns conflict diagnostics for the cell |
| `fg.audit.diff_proof_frames(...)` | "Compare two recorded proof-frame outcomes — what changed between them?" Useful after re-evaluation |

`target` for `explain` / `conflicts` can be an `AssertionRecord`, an `(EntityCls, identity_kwargs)` tuple resolving to a single cell, or any other object the SDK can resolve via `_resolve_record_asrt_id`. These are diagnostics — they neither write to the ledger nor trigger evaluation.

## 7. What's deferred

This chapter covers the shipped surface. Several user-facing capabilities are *designed* but not yet exposed in the SDK:

| Capability | Status | Where designed |
|---|---|---|
| `fg.diagnose(...)` SDK public surface | Internal application-layer logic shipped; SDK shell deferred | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.2 (D1) |
| Why-not / counterfactual explanation | Deferred — only `failure_class="closed_head_false"` available today | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.2 (D5) |
| PyReason multi-timestep timeline evidence | Deferred — current PyReason `EvidenceGraph` is single-conclusion fallback | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.1 (D11) |
| Attribution / salience decomposition | Deferred (D6 / D7) | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.3 |
| Match witness `as_assertions() / witnesses() / to_view()` | Deferred — `fg.entities.match` returns snapshots only today | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.5 (D20) |
| Desc auto-render in `Explanation` payloads | Shipped as `Explanation.repr` multi-line rendering for passed/failed explanations; deeper PyReason timeline rendering remains deferred | [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) §6.6 (D21) |

## 8. Reference

### 8.1 Types

```python
# Runtime entry points
from factgraph.sdk import FactGraph              # fg.eval.evaluate, fg.eval.explain
                                                 # fg.audit.explain, fg.audit.conflicts, fg.audit.diff_proof_frames

# DTOs (frozen)
from factgraph.sdk import (
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
    EDGE_DERIVED_BY, EDGE_USES, EDGE_HAS_ATOM, EDGE_SUPPORTED_BY,
    NODE_CONCLUSION, NODE_PREMISE, NODE_SEED,
    NODE_RULE_EXPR, NODE_RULE, NODE_ATOM,
)
```

### 8.2 Errors

| Error | Raised by |
|---|---|
| `SDKStoreError: evaluate(rule_expr, ...) requires head= Rule` | `fg.eval.evaluate` without `head=` |
| `SDKStoreError: evaluate(rule_expr, ...) head= must be Rule` | `head=` is not an **application-protocol** `Rule` (`factgraph.application.protocol.Rule`). The shipped `EvaluateResult.__post_init__` check raises `ProtocolShapeError("EvaluateResult.head must be application protocol Rule")` at construction; the SDK shell surfaces it as `SDKStoreError`. SDK DSL `Rule`, `Inference`, dict, str, inspect objects all rejected here |
| `SDKStoreError: eval.explain(...) head= must be Rule` | Same constraint on `fg.eval.explain` |
| `RuleExprError: manual explain head must be closed; unbound ports: <names>` | `fg.eval.explain(head=...)` with a head whose `when` does not bind every port |
| `RuleExprError: head rule '<id>' matches an expression occurrence with a different content digest` | RuleExpr with head whose id matches an occurrence but content differs (§1.2 stale binding) |
| `RuleExprError: head rule '<id>' matches multiple expression occurrences with the same content digest` | The same Rule appears more than once in the RuleExpr without distinct `.as_()` aliases (§1.2) |
| `RuleExprError: RuleExpr head validation failed: head port '<name>' is only declared in some RuleExpr branches` | OR expression where the head port is present in some branches but not all (§1.2 port-shape contract) |
| `WhereValidationError: head_vars length must match target arg_specs` | Rare: `rule.id` incidentally collides with a schema predicate id but the rule's port count doesn't match that predicate's arity. Pick a different `rule.id` (`head.id` is a free-form label per §1.2) to avoid this path |
| `DetachedRowError` | `row.explain()` after the parent `EvaluateResult` has been garbage-collected |
| `ProtocolShapeError` (various) | `Explanation` / `EvaluateRow` / `EvidenceGraph` invariant violations at construction (the in-process application-protocol `Claim` / `EvidenceRef` wrappers were removed in Slice γ; the ledger-layer `factgraph.core.store.ledger.Claim` is a separate persistence record covered in [`data_model.md` §1](data_model.md)) |

### 8.3 Method signatures by namespace

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

### 8.4 Related chapters

- [`rules.md`](rules.md) — `Rule` / `RuleExpr` / `head` declaration, and `fg.rules.inspect`
- [`engines_and_configs.md`](engines_and_configs.md) — `engine=` / `config=` parameters consumed by `evaluate`
- [`data_model.md`](data_model.md) §2.2 — the `raw_kind` + `bound` meta keys that surface on `EvaluateRow`
- [`assertions.md`](../official/kernel/quickstart/assertions.md) — assertion-level read APIs that `fg.audit.explain` / `conflicts` resolve against
- [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) — the deferred capabilities listed in §7
