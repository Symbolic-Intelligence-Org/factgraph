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

Each `EvaluateRow` is one match — one `(rule body, ledger fact-set)` binding that satisfied the body. The fields say what the body matched (`bindings`), what the rule's head looked like for this match (`kind` / `digest`), what certainty the row carries from the engine/source facts (`certainty`), and what closed-head replay anchor supports it (`closed_head_digest`):

```text
EvaluateRow (frozen)
  ├── row_id: str
  ├── bindings: Mapping[str, Any]   ← port-name → typed term map (see below)
  ├── kind: ClaimKind               ← row conclusion role
  ├── digest: str                   ← row claim digest
  ├── closed_head_digest: str       ← stable replay input for this row
  ├── certainty: Certainty | None    ← lo/hi/kind carrier
  └── _result_resolver              ← internal; powers row.explain()
```

```python
row = result.first()

row.row_id                    # str
row.bindings                  # Mapping — port-name → typed term map
result.head.id                # "user_region_lookup" — the head label
row.kind                      # "fact_triple" — row conclusion role
row.digest                    # "sha256:..." — content digest for this row claim
row.certainty                 # Certainty(lo=1.0, hi=1.0, kind="boolean") on native/souffle rows
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

#### `certainty` — uncertainty carry-through

`certainty` normalizes the source/engine certainty carrier into one frozen object: `Certainty(lo, hi, kind)`. Native and Souffle rows use `Certainty(1.0, 1.0, "boolean")`; ProbLog rows use `Certainty(p, p, "probabilistic")`; PyReason rows use `Certainty(lo, hi, "possibilistic")`. This replaces the older `raw_kind` / `bound` pair while preserving the same underlying uncertainty semantics described in [`engines_and_configs.md`](engines_and_configs.md) §2.1.

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

`Explanation` is built around the same three reasoning layers a human uses to read a derivation: *which alternative paths could conclude it*, *which rule + conditions each path needs*, and *what each condition's verdict is*. The paths-model DTO makes those layers first-class — the rest of this section tours that shape, from concept to wire fields to rendered text.

### 4.1 The three layers

```
EvidenceGraph.paths   ─ composition: one EvidenceTree per OR branch (holds ⟺ any path holds)
       │
       ▼
   EvidenceRule        ─ one rule occurrence (role="head" / "body") with a linear body
       │
       ▼
   EvidenceAtom        ─ one body condition + verdict (Holds / Fails / NotReached) + repr_text
```

**Concrete example.** Given this rule with three body atoms:

```python
from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import PredAtom, CmpAtom, Var, Const

u, age = Var("u"), Var("age")

adults_in_us = Rule(
    id="adults_in_us",
    version="v1",
    when=(
        PredAtom("user:region", [u, Const("US")]),   # atom 0 — schema predicate match
        PredAtom("user:age",    [u, age]),            # atom 1 — binds age
        CmpAtom("gt", age, Const(18)),                # atom 2 — computed check (gt = >)
    ),
    ports={"user": u},
    repr="Adult user %user lives in the US",  # rendered into the Conclusion line
)
```

> `Rule.repr` is the conclusion template (the old `Rule.desc` was renamed to `Rule.repr`; `desc=` remains a deprecated alias). Literal values in atoms are wrapped in `Const(...)`, and `CmpAtom` ops use the string codes `eq` / `ne` / `gt` / `ge` / `lt` / `le` (not `==` / `>`). A bare `"US"` or `>` raises at construction / evaluation.

…and ledger facts `user:region(alice, "US")` + `user:age(alice, 25)`, the matching row's `Explanation.evidence` is a paths-model `EvidenceGraph` — one `EvidenceTree` (proof path) holding a **head** `EvidenceRule` plus a **body** `EvidenceRule` whose atoms each carry a three-state `verdict` and a baked `repr_text`:

```
EvidenceGraph(engine="native", layout_hint="tree")
└─ paths[0] = EvidenceTree(status="holds")          ← one path (single rule; OR would give N paths)
     ├─ EvidenceRule(role="head", occurrence_alias="adults_in_us", status="holds")
     └─ EvidenceRule(role="body", occurrence_alias="adults_in_us", status="holds")
          ├─ EvidenceAtom(form=Fact,    verdict=Holds, repr_text="User alice is in region US")   ← atom 0
          ├─ EvidenceAtom(form=Fact,    verdict=Holds, repr_text="User alice is 25 years old")    ← atom 1
          └─ EvidenceAtom(form=Compare, verdict=Holds, repr_text="25 > 18")                       ← atom 2
```

Reading the layers:

- **Composition (paths)** — `EvidenceGraph.paths` is a tuple of `EvidenceTree` (or `EvidenceTimeline` for PyReason). A single rule gives one path; an `or` expression gives one path per branch (holds ⟺ any path holds). There is no flat node/edge graph and no `root_node_id` — the tree *is* the structure.
- **Rule occurrence (`EvidenceRule`)** — each path carries a `role="head"` rule (the conclusion) and one or more `role="body"` rules (real occurrence aliases from the lowering plan). Joins between occurrences are `EvidenceJoin` entries on the tree. Each rule has an explicit `status` (`holds` / `fails` / `not_reached`).
- **Condition (`EvidenceAtom`)** — one atom per body condition, in declaration order. Each atom has a `verdict` — `Holds`, `Fails`, or `NotReached(blocked_by=...)` — and a `repr_text` baked at probe time from the schema's `repr` templates. The native prober is **exhaustive**: after a condition `Fails`, later conditions whose dependencies are bound are still evaluated to their own `Holds`/`Fails` (not blanket-skipped); `NotReached` is reserved for atoms whose own input variable is genuinely unbound.

`Explanation.repr` (§4.5) walks the paths into an indented tree, one line per rule/atom. Shipped native engine produces:

```
Conclusion: c0 [run_v1:<digest>:<row>]
  Rule "adults_in_us": holds
  Body "adults_in_us": holds
    Atom: User alice is in region US — holds
    Atom: User alice is 25 years old — holds
    Atom: 25 > 18 — holds
```

Two things to know about the rendered text:

- **Atom text is schema-authored.** `repr_text` is rendered from `Field.repr` / `Identity.repr` templates (`%ENT` / `%FLD` / `%CLS`); a bound entity-ref resolves to its `Meta.repr` label ("User alice"), not a raw `idref_v1:` token. Compare / builtin / negation atoms use the renderer's default phrasing (`25 > 18`, `!(a && b)`, …). A truly-unbound value renders as `<unbound>`, never an internal `$var`.
- **Conclusion line** is the path/candidate id (e.g. `c0`) plus the run id. `Rule.repr` (the rule-level conclusion template) is **not** auto-rendered into `Explanation` — it only carries through the per-row closed head as data plumbing (see [`rules.md`](rules.md) §2.5). The schema-authored *atom* text above is the part `repr` drives in the explanation.

### 4.2 `Explanation` DTO

```
Explanation (frozen)
├── status                 Literal["passed", "failed", "unsupported", "invalid_request"]
├── evidence               EvidenceGraph | None             ← non-None iff status ∈ {"passed","failed"}
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

1. `status ∈ {"passed","failed"} iff evidence is not None`  — a failed explanation also carries an `EvidenceGraph` (the prober's failure tree, e.g. `closed_head_false`), not `None`
2. `status == "passed" → row is not None`  (a failed/closed_head_false explanation has `row is None`)
3. `status == "passed" → result_id is non-empty`
4. `failure_class is set iff status == "failed"`
5. `status ∈ {"unsupported", "invalid_request"} → errors non-empty`

Compose by reference, not by inline duplication. The pre-α flat fields (`claim` / `row_id` / `evidence_ref_id`) and the pre-Certainty `raw_kind` / `bound` pair are gone — read `explanation.row.bindings`, `explanation.row.certainty`, etc. Cross-process row handle is `(explanation.result_id, explanation.row.row_id)`.

### 4.3 Status outcomes

| status | When | `row` | `evidence` | `failure_class` | `errors` | `repr` |
|---|---|---|---|---|---|---|
| `"passed"` | Head fires on a row | ✓ | ✓ | None | () | Paths-model tree walk |
| `"failed"` | Head doesn't fire / row stale / row not in this result | None | ✓ (prober failure tree) | one of 5 | () | Paths-model tree walk |
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

### 4.4 `EvidenceGraph` — the paths-model substrate

When `status ∈ {"passed","failed"}`, `Explanation.evidence` is an `EvidenceGraph` of proof **paths**. There is no flat node/edge graph and no `root_node_id` — each path *is* an `EvidenceTree` of rules and atoms:

```
EvidenceGraph (frozen)
├── graph_id          str
├── engine            str               ← "native" / "souffle" / "problog" / "pyreason"
├── layout_hint       str = "tree"      ← "tree" (native/souffle/problog) | "timeline" (pyreason)
├── subject_binding   Mapping           ← the row's port bindings this graph explains
├── paths             tuple[EvidenceTree | EvidenceTimeline, ...]   ← one per OR branch; holds ⟺ any path holds
│     EvidenceTree (frozen):
│        tree_id, status: "holds"|"fails"|"not_reached",
│        rules: tuple[EvidenceRule, ...], joins: tuple[EvidenceJoin, ...], certainty: Certainty | None
│     EvidenceRule (frozen):
│        role: "head"|"body", occurrence_alias: str, rule_id: str,
│        status: "holds"|"fails"|"not_reached", ports: Mapping, atoms: tuple[EvidenceAtom, ...]
│     EvidenceAtom (frozen):
│        form: Fact|Compare|Builtin|Aggregate, verdict: Holds|Fails|NotReached,
│        atom_id, repr_text: str|None, negated: bool=False, timestep: int|None=None
├── certainty         Certainty | None  ← engine-level (e.g. ProbLog aggregate probability)
└── metadata          Mapping[str, Any] = {}
```

Status aggregates **bottom-up** (no cycle/DFS validation — the tree is acyclic by construction):

| Level | `holds` | `not_reached` | `fails` |
|---|---|---|---|
| `EvidenceRule.status` | all atoms `Holds` | all atoms `NotReached` | any atom `Fails` |
| `EvidenceTree.status` | all rules `holds` | all rules `not_reached` | any rule `fails` |
| graph | **any** path `holds` | — | no path holds |

**Atom verdicts** (`EvidenceAtom.verdict`):

| verdict | Meaning |
|---|---|
| `Holds(certainty, support)` | Condition satisfied |
| `Fails(certainty)` | Condition evaluated and false |
| `NotReached(blocked_by)` | Condition's own input variable is unbound (an upstream binder did not produce it) — **not** a "previous atom failed" marker; the prober keeps evaluating later dependency-bound atoms exhaustively |

PyReason paths are `EvidenceTimeline` instead of `EvidenceTree` — events organized by `timestep`, reusing `EvidenceAtom` leaves (§4.6).

### 4.5 `Explanation.repr` — the rendered text

`Explanation.repr` (a `tuple[str, ...] | None`) is a **computed property** added by slice ε. Lazy, cached in a private `_repr_cache` field, never settable via constructor (`Explanation(repr=...)` is rejected). Built by `factgraph.application.protocol.explanation_render.walk_evidence(graph, *, row, status, failure_class)`.

**Passed / failed — paths walk.** For each `EvidenceTree` path the walker emits a Conclusion line, then the head/body `EvidenceRule` lines with their status, then one atom line per `EvidenceAtom`. Indentation reflects rule → atom nesting (one path block per `paths` entry). Per-line render:

| Element | Rendered as |
|---|---|
| Conclusion | `Conclusion: <path/candidate id> [<run id>]` (e.g. `Conclusion: c0 [run_v1:…]`) |
| `EvidenceRule` (role="head") | `Rule "<occurrence_alias>": <holds\|fails\|not_reached>` |
| `EvidenceRule` (role="body") | `Body "<occurrence_alias>": <status>` |
| `EvidenceAtom` | `Atom: <repr_text> — <holds\|fails\|not reached>` |

The atom line's `repr_text` is the schema-authored / default-rendered text (§4.1): entity-ref labels resolved, no internal `$var`, negation as `!(...)`, unbound values as `<unbound>`.

**`Explanation.narrate()` — rich narrative (additive sibling).** `narrate()` (a separate computed surface, lazy-cached like `.repr`, `tuple[str, ...] | None`) walks the *same* `EvidenceGraph` into a human-facing form: the head `Rule.repr` rendered as the **conclusion headline** — with `[<head rule_id> · <run id> · <candidate id>]  <status>` as a trailing reference tag — then a `produces:` line of the closed head's bound ports, a `Derivation:  head <= ( rule_id AND … )` DNF composition with `join:` lines, then per-rule `Rule.repr` blocks and per-atom `✓/✗/○` verdicts. Multi-path OR explanations show one global DNF line such as `head <= ( a AND b ) OR ( c AND d )`; each path block keeps its own `join:` lines. Non-boolean certainty is rendered in narrative text as `holds with probability 0.4` or `holds with bound [lo, hi]`, while atom/rule probability details stay local to the relevant rule or atom line. It does **not** change `.repr` (the structured tree above stays as-is): `Rule.repr` is surfaced **only** through `narrate()`, never through `.repr` (whose conclusion line remains the candidate id).

§4.1 walks the `adults_in_us` rule through this machinery as a worked end-to-end example.

**Failed** walks its prober failure tree the same way (a failed `Explanation` carries an `EvidenceGraph`, §4.2 invariant 1): the conditions that failed show `Fails`, dependency-bound siblings still show their own verdict, and `failure_class` + `suggested_next_steps` are read off the `Explanation` (they are not nodes inside the tree).

**Unsupported / invalid_request** — `repr` is `None`. Read `errors[*].code` + `errors[*].message`.

### 4.5.1 Selected rule programs

`fg.eval.evaluate_program(program, goal)` exposes the same two-level contract for
an explicitly selected Horn program:

```python
result = fg.eval.evaluate_program(program, goal)
proof = result.explain()

proof.status
proof.evidence       # canonical EvidenceGraph from this evaluation snapshot
proof.repr           # deterministic walk of proof.evidence
proof.steps          # recursive native RuleRef support receipts
proof.checked_scope  # engine, rule-set, premise-scope and view digests
proof.narrate()      # canonical narrate_evidence(proof.evidence, ...)
```

For an entailed goal, `steps` retains the recursive RuleRef receipts and
`evidence` projects that exact selected proof into the standard
`EvidenceGraph`/`EvidenceTree` model, with original assertion ids in
`EvidenceAtom.verdict.support`. `repr` and `narrate()` are therefore two
renderings of the same structural artifact. For a non-entailed closed goal, the
explanation reports `closed_goal_not_entailed`, preserves the exact checked
scope, and runs the canonical native prober for every selected rule that can
produce the goal. The resulting graph carries condition-level
`Holds`/`Fails`/`NotReached` verdicts and joins from the selected program only.
Pre-materialized conclusions from outside that selected program cannot satisfy
or rewrite this explanation.

Program narration is computed during evaluation and retained on the immutable
result. Calling `result.explain().narrate()` later performs no ledger read and no
re-evaluation, so facts appended after the decision cannot rewrite its account.
Applications that persist decisions should store `evidence`, `steps`,
`checked_scope`, and `narrate()` together as one append-only evaluation receipt.

### 4.6 Per-engine fidelity today

| Engine | layout | paths | Notes |
|---|---|---|---|
| Native | tree | exhaustive prober tree(s) | head + body `EvidenceRule`s; per-atom `Holds`/`Fails`/`NotReached`; schema-authored `repr_text` |
| Souffle | tree | diagnostic projection → tree; witness converter fallback | native-grade head/body/atom shape; boolean certainty |
| ProbLog | tree | diagnostic projection → tree; trace converter fallback | native-grade head/body/atom shape plus probabilistic `Certainty` at row/tree/atom levels |
| PyReason | timeline | `EvidenceTimeline` | events by `timestep`, possibilistic `Certainty`; reuses `EvidenceAtom` leaves |

### 4.7 `certainty` carry-over

When the source row has uncertainty meta, `Explanation.row.certainty` carries the normalized `Certainty(lo, hi, kind)` value — read-side counterpart to the write-side uncertainty metadata in [`engines_and_configs.md`](engines_and_configs.md) §2.1. Native/Souffle rows use boolean certainty; ProbLog uses probabilistic certainty; PyReason uses possibilistic interval certainty.

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
    repr=<carried over from open head>,
)
```

### 5.2 Where the closed head appears

| Place | Closed-head role |
|---|---|
| `row.close()` (§2.2) | Produces the closed-head `Rule` for a given row |
| `row.explain()` / `fg.eval.explain(...)` (§3) | Both internally close the head and check it against the row's bindings |
| `row.closed_head_digest` (§2.4) | The stable `sha256:` digest of the closed head — same body & same bindings → same digest |
| `fg.rules.inspect(...)` ([`rules.md`](rules.md) §4) | `RuleExprInspect.is_closed` / `unbound_ports` reports closure status of a non-row Rule |

### 5.3 `repr` carries through

If the open head has a `repr` template (e.g. `"User %user is in %region"`, see [`rules.md`](rules.md) §2.5), the closed head receives the same template — letting downstream renderers produce per-row descriptions.

**Structured `.repr` vs narrative `narrate()`.** The carry-through is data plumbing for the structured `.repr`: the conclusion line of `Explanation.repr` is a path/candidate id (§4.5), **not** the rendered `Rule.repr`. The richer `Explanation.narrate()` surface does render head/body `Rule.repr` labels. Schema `repr` templates (`Field` / `Identity` / `Meta`, [`schema_definition.md`](schema_definition.md) §1.8) render atom text in both surfaces.

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

# Paths-model evidence types (single-definition source in application.explain;
# also re-exported by factgraph.audit.evidence_graph for backward compatibility)
from factgraph.application.explain import (
    EvidenceGraph, EvidenceTree, EvidenceTimeline,
    EvidenceRule, EvidenceAtom, EvidenceJoin,
    Holds, Fails, NotReached,
    Fact, Compare, Builtin, Aggregate,
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
- [`data_model.md`](data_model.md) §2.2 — write-side uncertainty metadata that surfaces as `EvaluateRow.certainty`
- [`assertions.md`](../official/kernel/quickstart/assertions.md) — assertion-level read APIs that `fg.audit.explain` / `conflicts` resolve against
- [`explanation-completion-roadmap.zh.md`](../../workflow/design/design-points/active/explanation-completion-roadmap.zh.md) — the deferred capabilities listed in §7
