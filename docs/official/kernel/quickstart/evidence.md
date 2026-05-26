# Evaluation Result And Evidence

Evaluation is read-only. `fg.eval.evaluate(...)` returns an `EvaluateResult`
envelope; rows on the envelope expose claims, evidence references, and the
explanation pipeline.

The canonical workflow is:

```python
result = fg.eval.evaluate(rule, head=rule)   # → EvaluateResult
row = result.first()                         # → EvaluateRow
explanation = row.explain()                  # → Explanation
```

| Surface | Returns | Purpose |
| --- | --- | --- |
| `fg.eval.evaluate(expr, head=rule, ...)` | `EvaluateResult` | Read-only evaluation envelope |
| `result[i]` / `result.first()` / `iter(result)` | `EvaluateRow` | Access one derived fact |
| `row.explain()` | `Explanation` | Live row-bound explanation (主路径) |
| `row.close()` | application `Rule` | Closed head for cross-session replay |
| `fg.eval.explain(expr, head=closed_head, ...)` | `Explanation` | Manual / advanced replay path |
| `fg.eval.inspect_semantics(profile)` | preview | Inspect a semantics profile shape |

The rest of this page walks through each DTO in the chain.

## 1. `EvaluateResult` — the envelope

`EvaluateResult` is a frozen dataclass with 13 fields and 7 row-access forms.
The fields fall into four roles:

| Role | Fields |
| --- | --- |
| Envelope identity | `result_id` (`evalr_v1:...`), `run_id` (`run_v1:...`), `result_digest` (`sha256:...`) |
| Replay anchors | `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest` (or `None`) |
| Engine provenance | `engine` (`"native"` / `"problog"` / `"pyreason"`), `engine_version`, `adapter_version` |
| Evaluation context | `head` (the closed application `Rule`), `evaluated_at` (`datetime` UTC), `rows` (`tuple[EvaluateRow, ...]`) |

Row access:

```python
result = fg.eval.evaluate(rule, head=rule)

len(result)            # row count
bool(result)           # True iff non-empty
result.count()         # explicit row count
result.exists()        # explicit non-empty check
result.first()         # first row or None
result[0]              # row by index → EvaluateRow
for row in result:     # iteration over rows
    ...
```

Identity and replay anchors are content-addressed digests. Two `EvaluateResult`
values with matching `expr_digest`, `rule_set_digest`, `view_snapshot_digest`,
and `semantics_digest` evaluated the same logical query against the same
snapshot under the same semantics — they are replay-equivalent regardless of
when they ran.

## 2. `EvaluateRow` — one derived fact

`EvaluateRow` is frozen with 6 data fields and 2 live methods:

| Kind | Member | Purpose |
| --- | --- | --- |
| data | `row_id` (`run_v1:...`) | Stable id within `run_id` |
| data | `bindings` | Frozen `Mapping[str, Any]` keyed by `pred_id` / `terms` |
| data | `claim` | `Claim` describing what was derived |
| data | `raw_kind` | `"probabilistic"` / `"possibilistic"` / `None` |
| data | `bound` | `(lower, upper)` tuple of floats, or `None` |
| data | `evidence_ref` | `EvidenceRef` linking back to envelope |
| method | `row.explain()` | Build `Explanation` for this row |
| method | `row.close()` | Build closed-head application `Rule` |

Both methods are **live-only**. They need the row to still know its owning
`EvaluateResult`. A row reconstructed from JSON or extracted into a
detached variable raises `DetachedRowError`:

```python
from dataclasses import replace

detached = replace(row, _result_resolver=None)
detached.explain()   # → DetachedRowError
detached.close()     # → DetachedRowError
```

`DetachedRowError` is a **Python programming error**, not a failure
classification. It indicates the row was constructed or transferred in a
way that broke its `_result_resolver` linkage (e.g., reconstructing from
JSON without re-binding to a result). It is **not** a `status="failed"`
outcome, has no `failure_class`, and should not be caught as a business
case. Code that needs cross-session explanation should use
`fg.eval.explain(expr, head=closed_head, ...)` with an explicit closed
head — see §5 below.

`row.bindings` is keyed by `pred_id` + `terms`, not by `ports` directly.
The bound port values live inside the `terms` list at positions matching the
rule's port declaration; see `row.claim` and `row.close()` for richer
projections.

`raw_kind` and `bound` carry quantitative uncertainty propagated from the
ledger and engine adapters. The invariant `raw_kind is None ⇒ bound is None`
holds; the reverse pairing is enforced by the protocol. This is the
read-side projection of the same single-source contract documented at
[Canonical quantitative carrier](assertions.md#canonical-quantitative-carrier)
on the write side — same two fields, never duplicated, never normalized to
a single number.

## 3. `Claim` — what was asserted

`Claim` describes the derived fact in a kind-agnostic shape:

| Field | Purpose |
| --- | --- |
| `kind` | One of four `ClaimKind` values |
| `name` | Predicate / rule / aggregate / projection name |
| `arguments` | Frozen `Mapping[str, Any]` of the claim payload |
| `repr` | Pre-rendered string form |
| `digest` | `sha256:` digest of the claim content |

The four `ClaimKind` values:

- `fact_triple` — a derived `(pred_id, *terms)` ground fact
- `rule_head` — a rule's head shape (post-projection but not a fact)
- `aggregate_result` — a Count / Sum / Min / Max / Mean result
- `projection` — a port-projection over evaluation rows

`claim.digest` is what `evidence_ref.fact_digest` mirrors — they must be
equal on a live row.

## 4. `EvidenceRef` — durable identity

`EvidenceRef` is the durable handle that ties an evidence record to its
envelope. 5 fields:

| Field | Tied to |
| --- | --- |
| `ref_id` (`evref_v1:...`) | This evidence reference |
| `result_id` | Back-pointer to `EvaluateResult.result_id` |
| `row_id` | Back-pointer to `EvaluateRow.row_id` |
| `fact_digest` | Mirror of `EvaluateRow.claim.digest` |
| `closed_head_digest` | Digest of the closed head used for this row |

Invariants on a live row:

```python
assert row.evidence_ref.row_id    == row.row_id
assert row.evidence_ref.fact_digest == row.claim.digest
assert row.evidence_ref.result_id == result.result_id
```

`EvidenceRef` is not the public explanation entry point. Use `row.explain()`
on the live row; the ref is for row-local identity, stale detection, and
durable audit linking only.

## 5. `Explanation` — derivation analysis

`Explanation` is a frozen 13-field envelope describing whether and how a
row's claim is supported. It is **terminal**: an Explanation has data
attributes only, no chainable `.explain()` method of its own. Read it by
branching on `status`.

The 4 `status` values:

| Status | Meaning | `evidence` | `failure_class` |
| --- | --- | --- | --- |
| `passed` | Derivation succeeded | `EvidenceGraph` | `None` |
| `failed` | Business failure: binding does not hold | `None` | one of 5 classes |
| `unsupported` | Engine technically cannot answer (non-business) | `None` | `None` |
| `invalid_request` | Input shape was rejected | `None` | `None` |

The 5 `failure_class` values (only when `status == "failed"`):

| Class | When |
| --- | --- |
| `no_matching_row` | Closed head matches no row in the result |
| `closed_head_false` | Closed head present, but underlying facts changed |
| `stale_row` | Row's view snapshot is no longer current |
| `row_not_in_result` | Row id not present in the linked result |
| `insufficient_closed_bindings` | Closed head is not fully closed for replay |

Protocol-enforced invariants:

- `status == "passed"` ⇔ `evidence is not None`
- `status == "failed"` ⇒ `failure_class` is set
- `status in {"unsupported", "invalid_request"}` ⇒ `errors` is non-empty
- `raw_kind is None` ⇒ `bound is None`

All 13 fields:

| Field | Populated when | Purpose |
| --- | --- | --- |
| `status` | always | One of the 4 values above |
| `evidence` | `status == "passed"` | The `EvidenceGraph` derivation tree |
| `claim` | `passed` (also possible on others) | The asserted `Claim` |
| `result_id` | always (required when passed) | Links to `EvaluateResult` |
| `row_id` | live-row path | Links to source `EvaluateRow` |
| `evidence_ref_id` | live-row path | Links to `EvidenceRef.ref_id` |
| `raw_kind` / `bound` | when row has uncertainty | Propagated quantitative carriers |
| `failure_class` | `status == "failed"` | Diagnostic class |
| `checked_scope` | `failed` / `unsupported` | Replay context that was checked |
| `suggested_next_steps` | typically `failed` / `unsupported` | UX hint strings |
| `errors` | `unsupported` / `invalid_request` (non-empty) | `ErrorDTO` tuple with `.code` / `.message` |
| `warnings` | any status | Non-blocking `WarningDTO` tuple |

Passed example:

```python
result = fg.eval.evaluate(rule, head=rule)
row = result.first()
e = row.explain()

assert e.status == "passed"
assert e.evidence is not None       # an EvidenceGraph
assert e.claim is not None
assert e.failure_class is None
assert e.errors == ()
```

Failed example (state changed between `evaluate` and `explain`):

```python
result = fg.eval.evaluate(rule, head=rule)
row = result.first()
closed_head = row.close()

# Mutate the ledger so the closed head's facts no longer hold
fg.write.set(User.name, alice, "Bob")

e = fg.eval.explain(rule, head=closed_head)

assert e.status == "failed"
assert e.failure_class == "closed_head_false"
assert e.evidence is None
# UX hint for the caller
assert e.suggested_next_steps == (
    "Re-evaluate with a closed head that matches at least one result row.",
)
```

`row.explain()` is the row-bound 主路径; `fg.eval.explain(expr,
head=closed_head, ...)` is the advanced / cross-session manual path that
requires the caller to supply a fully closed head.

## 6. `EvidenceGraph` — intentionally opaque (v0.2)

When `status == "passed"`, `explanation.evidence` is an `EvidenceGraph`
containing the full derivation tree (nodes + edges, with engine-specific
metadata per ProbLog / PyReason / native adapters). This page does not yet
document the graph interior; treat it as an opaque value and pass it to
`render_evidence_graph_html(...)` (audit surface) for visualization, or to
audit ingestion for durable replay.

The graph itself is **already shipped** with stable invariants — only the
user-facing tutorial is deferred:

- **DAG with branch convergence** — the graph is acyclic; the same fact
  reached via multiple paths converges on a single node rather than
  duplicating.
- **Cycle detection** — adapters that could produce cyclic derivation
  paths (e.g., recursive ProbLog clauses) detect and reject the cycle
  rather than producing an `EvidenceGraph` that violates the DAG
  invariant.
- **Engine-meta namespace** — adapter-specific information lives under
  scoped keys (`problog/`, `pyreason/`, `native/`) on `EvidenceNode` and
  `EvidenceEdge`; the namespace prevents cross-engine field collisions.

A dedicated cycle covering full `EvidenceGraph` API (`EvidenceNode`,
`EvidenceEdge`, `layout_hint`, complete engine-meta payloads, rendering
hooks) is pending.

## 7. Stability of `Inference` and `Branch`

Application `Rule` (built via `build_application_rule(...)`) plus
`RuleExpr` composition is the **preferred read-pattern surface for new
code** in v0.2. `Inference` and `Branch` (legacy DSL) remain available as
the **compatibility surface**: they produce the same `EvaluateResult` /
`EvaluateRow` / `Claim` / `Explanation` shapes documented in §§1–5 and
share the same lower evaluation pipeline (`SemanticsProfile`, engine
adapters, evidence runtime).

The design has committed to retiring `Branch` from user-facing layers and
folding `Inference` into a `RuleExpr`-based runtime entry in a later
cycle:

> 在新 user-facing 表达层 (`Rule` / `RuleExpr`),`Branch` 不出现 …
> 与 Inference 关系: 新设计 = **解耦** — Inference 是运行时入口,接受 RuleExpr
> — `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.10

Until that migration spec is locked by a future blueprint:

- No `DeprecationWarning` is raised; no public symbol is removed.
- `Inference(..., where=[Branch([...], id="...")])` remains stable for
  current use and continues to be exercised by tests and adapters.
- `Branch` is not a stand-alone user-facing concept — it is the OR-body
  primitive inside `Inference` only. `build_application_rule(...)`
  rejects `Branch` because application `Rule` bodies are AND-only;
  multi-pattern composition belongs at the `RuleExpr` level (`&` / `|`
  operators on application `Rule` values).
- New quickstart examples and SDK docs introduce application `Rule`
  first; `Inference` is shown for cases that need the legacy
  `Branch`-list OR-body syntax (e.g. for compatibility with engine
  adapters that historically consumed it).

## A note on naming collisions

`result[i].explain()` is the subscript form of `row.explain()` — the dot is
on the row obtained by indexing, not on `result` or on the returned
`Explanation`. `EvaluateResult` itself has no `.explain()` method, and
`Explanation` itself has no `.explain()` method either. Only `EvaluateRow`
and `fg.eval` expose the explanation entry points.

## Cross-references

- For the `fg.eval` namespace surface, see [namespace-map.md](namespace-map.md).
- For Rule and Inference construction, see [rules-and-inferences.md](rules-and-inferences.md).
- For semantics profiles (`raw_kind` / `bound` origination), see [semantics.md](semantics.md).
