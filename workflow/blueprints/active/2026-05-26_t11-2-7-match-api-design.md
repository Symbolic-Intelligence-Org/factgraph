# Task Blueprint: T11.2.7 Match API Design

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M/L (predicted docs-only design synthesis; may narrow after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t11-2-7-match-api-design.audit.md`
- Trigger: T11.2.5 classified `src/factgraph/sdk/facade.py` + companion test as the only release-relevant dirty behavior pair; user identified that the facade assertion namespace overlaps the still-unformalized Query -> match API migration.

## 0. Scope Locks

### In scope

T11.2.7 is a design-only release-path cycle. It formalizes the minimum viable
v0.2 match API shape before deciding whether to land or stash the dirty
`facade.py` assertion ergonomics changes.

Primary decisions to lock:

1. **Namespace placement**: decide between `fg.read.match(...)`,
   `fg.assertions.match(...)`, `fg.query.match(...)`, `fg.read.query(...)`,
   `rules.run(query)`, and `AssertionRecordSet.match(...)`.
2. **Template type**: decide whether v0.2 match accepts application `Rule`,
   `RuleExpr`, legacy SDK `Query`, or a compatibility subset.
3. **Return shape**: decide whether match returns rows, snapshots,
   `AssertionRecordSet`, rows with witness assertion ids, or a new envelope.
4. **Witness / assertion boundary**: decide what v0.2 must promise now and what
   remains deferred to evidence / witness design.
5. **View integration**: align match with T11.1 attach-time view scoping and the
   current method-level `view=` rejection rule.
6. **`fg.eval.run` migration timing**: record whether match design merely
   freezes the replacement path or unlocks deletion in v0.2 / v0.3.
7. **Impact on T11.2.6 facade.py**: state whether the dirty property-style
   assertion accessor change is aligned, obsolete, or undecided after match
   return-shape selection.

Output shape:

- Create a new active design-point, tentatively
  `workflow/design/design-points/active/match-api-design.zh.md`.
- Add a narrow cross-link / stub in
  `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md`
  §6, without trying to complete all match / evaluate / prove task-split work.
- Update roadmap / memory only if needed for handoff.

### Out of scope

- Implementing `fg.read.match(...)`.
- Editing `src/factgraph/sdk/facade.py` or its companion test.
- Rewriting notebooks or release machinery.
- Deleting `fg.eval.run`.
- Adding Query persistence (`fg.queries.save/load/list`).
- Implementing method-level `view=`.
- Implementing RuleExpr x evidence joins (§9).
- Implementing witness / EvidenceGraph construction for match results.
- Service / OpenAPI changes.
- New public DTOs unless the design explicitly escalates.

### Stop / amend triggers

Pause and amend if Step 4.6 shows:

- match return shape requires a new public DTO for v0.2;
- `fg.read.match(...)` cannot be specified without implementation changes to
  Query runtime or RuleExpr lowering;
- T11.1 attach-view invariants conflict with any match design candidate;
- `facade.py` behavior must be landed or reverted before the design can be
  stated;
- the design expands into full parent §6 match/evaluate/prove or §9 evidence
  joins rather than minimum viable match API.

## 1. Problem

Legacy `Query` was never fully migrated into the post-T5 public API model. The
parent rule-expression essay has a §6 placeholder for "match / evaluate / prove"
but no actual design. Historical notes discuss Query/Search, views, inference
handles, and assertion-record selection, but no current document owns the v0.2
match API shape.

This matters now because the dirty `facade.py` change modifies
`AssertionRecordSet` / `AssertionNamespace` ergonomics, and
`AssertionRecordSet` is one candidate return / refinement surface for match.
Landing that behavior before deciding match shape risks namespace churn.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §4.9 / §6 TOC stub | Current active parent source; includes illustrative `fg.read.match(R1)` sample but leaves §6 pending. |
| `workflow/design/design-points/archive/query-view-and-inference-handles.zh.md` §5 / §7 | Most direct prior sketch: Query/Search vs Inference, witness ids, view handoff, and `AssertionRecordSet.match(query)` caution. |
| `workflow/design/design-points/archive/factgraph-lifecycle-and-assets.zh.md` §9.3 | Query asset lifecycle deferred; `fg.queries.*` should not exist until real persistence exists. |
| `workflow/design/design-points/archive/rule-query-inference-head-semantics.zh.md` | Historical Query / Rule / Inference head distinction. |
| `workflow/design/design-points/archive/read-write-snapshot-assertion-selection.zh.md` | Assertion selection / read-side predecessor. |
| `workflow/design/design-points/archive/rule-policy-function-tree-and-syntax.zh.md` | Earlier rule/query/run naming sketch. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` and T11.1 shipped behavior | Attach-time view scoping; method-level `view=` remains rejected. |
| `src/factgraph/sdk/dsl/rule.py`, `query_lower.py`, `query_runtime.py` | Shipped legacy Query authoring/lowering/runtime truth. |
| T11.2.5 verdict record | `facade.py` + companion test must be decided after match return-shape alignment. |

## 3. Preliminary Findings

### 3.1 Not greenfield

The match API is not greenfield. It is substantially discussed in archived
design notes, but the canonical parent §6 is still only a table-of-contents
stub. T11.2.7 should synthesize, not invent from scratch.

### 3.2 Existing active hint

Parent §4.9 uses:

```python
fg.read.match(R1)
fg.read.match(R1 & R2)
fg.read.match(RuleExpr.all(R1, R2))
```

That example is documented as a type-boundary illustration, not a final
signature. Still, it creates a strong default toward `fg.read.match(...)`.

### 3.3 Historical tensions

Open questions inherited from prior notes:

- Query rows currently do not carry witness assertion ids.
- Views are assertion-id universes, not general query projections.
- Query/Search and Inference should remain distinct: matching finds existing
  items; inference proves or proposes conclusions.
- `AssertionRecordSet.match(query)` was explicitly not implemented earlier to
  avoid putting a general query engine into record-set selection.
- Query persistence is separate from match execution.

### 3.4 Shipped legacy Query surface

Current SDK still exports `Query`. It has `head` as return/projection contract
and `where` as matching body. It lowers to a runtime query id
`__query__:<digest>` and returns rows / snapshots / scalar slots, not witness
assertion sets.

## 4. Design Questions to Resolve

| # | Question | Default leaning before Step 4.6 |
|---|---|---|
| D1 | Namespace | `fg.read.match(...)`, because matching is read-side and parent §4.9 already hints it. |
| D2 | Template type | Accept `Rule` + `RuleExpr`; legacy `Query` compatibility either adapter-only or deferred. |
| D3 | Return shape | Must be decided before T11.2.6; `AssertionRecordSet` is a candidate but may be too narrow for snapshot rows. |
| D4 | Witness shape | v0.2 likely records witness support as deferred, not required in first match design. |
| D5 | View | Follow attach-only scope; no method-level `view=` in v0.2 match unless explicitly amended. |
| D6 | `fg.eval.run` | Match design may lock the replacement path, but deletion timing likely remains v0.3 / future hard-cut. |
| D7 | Facade impact | If match returns/refines `AssertionRecordSet`, property-style assertion access may be aligned; otherwise dirty facade change may be obsolete or separate. |

## 5. Proposed Step 4.6 Inventory

The scoped inventory must fill:

1. exact references to match / Query migration in active parent essay;
2. exact references in `query-view-and-inference-handles.zh.md`;
3. exact shipped Query class / lower / runtime behavior;
4. current SDK public exports involving `Query`, `Rule`, `RuleExpr`,
   `AssertionRecordSet`, `FactGraph.read`, and `FactGraph.assertions`;
5. existing docs mentions of `fg.eval.run`, `Query`, and match-like behavior;
6. whether `facade.py` dirty behavior aligns with each candidate return shape;
7. recommended output location: new design-point vs D-doc vs parent essay edit;
8. class decision after inventory: M or L.

## 6. Expected Implementation Shape

Implementation should be docs-only:

1. create `workflow/design/design-points/active/match-api-design.zh.md`;
2. add a short parent §6 cross-link in `rule-expression-and-proof-attempt.zh.md`;
3. optionally update `post-t5-completion-roadmap.zh.md` to mark this design as
   an early T7/T11 bridge;
4. record outcome / decision impact in the blueprint audit.

No runtime implementation is expected in T11.2.7.

## 7. Verification

- `git diff --check` clean.
- No changes to `src/factgraph/sdk/facade.py`,
  `tests/test_sdk_assertion_record_set_view_filters.py`, notebooks, or release
  machinery.
- Dirty baseline remains unchanged.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- T11.2.6 handoff states whether facade property-style assertion access should
  proceed, wait, or be stashed/reverted.

## 8. Acceptance

- [ ] Step 4.6 inventory completed with file/line anchors.
- [ ] Namespace decision recorded.
- [ ] Template type decision recorded.
- [ ] Return shape decision recorded.
- [ ] View integration decision recorded.
- [ ] `fg.eval.run` migration timing recorded.
- [ ] T11.2.6 facade impact recorded.
- [ ] No implementation code changes.
- [ ] Dirty baseline preserved.
