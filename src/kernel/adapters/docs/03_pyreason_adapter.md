# PyReason Adapter (kernel)

- Scope: `src/kernel/adapters/pyreason`
- Last updated: 2026-03-29
- Status: execution-surface V1 (engine_options: timesteps) +
  bounded materialization L3b + runtime provenance explain +
  EvidenceGraph audit/static delivery

## 1. Overview

The PyReason adapter is factpy's integration with the
[PyReason](https://github.com/lab-v2/pyreason) graph-reasoning
engine. It is now wired into the shared evaluate surface:
`Store.evaluate(mode="pyreason")` /
`SDKStore.evaluate(Derivation(..., mode="pyreason"))` go through
the adapter's EDB materialization, WhereIR compilation, runner,
and `CandidateSet` output. The adapter-local provenance, session,
rule extension, runner, and accept helper are still kept as
engine-internal implementation and standalone helper layers.

PyReason uses Generalized Annotated Logic Programs (GAPs) to
perform interval-valued temporal reasoning over NetworkX graphs;
it differs essentially from Souffle (deterministic Datalog) and
ProbLog (probabilistic logic).

## 2. Environment requirements

- `pyreason==3.0.0` (or newer; the dependency matrix at 3.4.0 is
  the same)
- Python 3.10
- Manual install: `pip install 'pyreason==3.0.0'` (not in
  `pyproject.toml`; spike-only dependency)
- Verified environment as of 2026-03-27: `numba==0.64.0`,
  `llvmlite==0.46.0`
- **Important**: if `import pyreason` fails with a numba cache
  error (`RuntimeError: cannot cache function ... no locator
  available`), clear the stale cache:
  `rm -rf $(python -c "import pyreason, pathlib; print(pathlib.Path(pyreason.__file__).parent / 'cache')")`
- The first run takes about `~170s` for numba JIT compilation;
  subsequent runs use the cache and take about `~8s`

## 3. Current module contents

| File | Role |
|------|------|
| `provenance.py` | `PyReasonTraceEventV0` / `PyReasonTraceV0` / `parse_pyreason_trace` / `pyreason_trace_to_dict` / `pyreason_trace_to_evidence_graph` |
| `session.py` | `PyReasonSession` — engine-specific write session; validates the shared schema_ir; handles batch API / bound / active_from / active_to / annotation templates |
| `rule_ext.py` | `PyReasonRuleExt` / `PyReasonFactDef` / `compile_pyreason_rule(...)` |
| `where_compile.py` | `compile_where_ir_to_pyreason(...)` — lowered WhereIR → PyReason rule syntax (the execution-surface compiler) |
| `runner.py` | `run_pyreason(...)` / `build_pyreason_graph(...)` / `PyReasonRunConfig` / `PyReasonRunResult`; accepts both legacy tuple form and shared `Rule` / typed `PyReasonFactDef` |
| `engine_eval.py` | `pyreason_engine_eval(...)` / `_materialize_edb_session(...)` — shared evaluate dispatch entry point that emits `CandidateSet` and caches pending annotations |
| `accept.py` | `accept_pyreason_session(...)` + `persist_pyreason_annotations(...)` — adapter-local accept helper and shared-surface post-accept annotation binder |
| `__init__.py` | On import, registers `register_engine_evaluator(pyreason_engine_eval, "pyreason")` |

## 4. PyReason inference model

```text
Input: NetworkX DiGraph + rules + initial facts
Rule syntax: head(x) <-T body(y), edge(x,y)   (T = timestep delay)
Value domain: [lower, upper] interval, not boolean or probability
World assumption: open-world (a missing fact = [0,1] unknown, not false)
Output: Interpretation (per-timestep, per-node predicate intervals) + Rule Trace (event log)
```

## 5. Trace data shape

PyReason's `pr.get_rule_trace(interpretation)` returns two pandas
DataFrames.

**`nodes_trace` columns:**

| Column | Meaning |
|----|------|
| Time | Timestep |
| Fixed-Point-Operation / Fixed-Point-Op | Fixed-point iteration number |
| Node | Graph node identifier |
| Label | Predicate name |
| Old Bound | Pre-change interval `[lo, hi]` |
| New Bound | Post-change interval `[lo, hi]` |
| Occurred Due To | Rule name or `fact` |
| Clause-1, Clause-2, ... | Concrete clause grounding (which nodes / edges matched the rule-body atoms) |

**This is an event log, not a proof tree.**

## 5A. Session write model

The write path is currently not the unified `runtime_v1` write
API; it is the adapter-local `PyReasonSession`:

```python
session = PyReasonSession(schema_ir)
with session.batch() as tx:
    alice = tx.entity(User, user_id="Alice")
    alice.name.set("Alice", bound=[1.0, 1.0], meta={"source": "profile"})
    tx.relationship(Friends, from_entity=alice, to_entity=bob,
                    strength="0.9", bound=[0.9, 0.9])
    tx.commit()
```

### 5A.1 Current session API

| API | Role |
|-----|------|
| `session.batch()` | Entity-level batch transaction entry |
| `tx.entity(EntityCls, **identity)` | Create / reuse an entity handle |
| `handle.field.set(value, *, bound, active_from, active_to, meta)` | Write a node fact |
| `tx.relationship(RelCls, *, from_entity, to_entity, **fields)` | Write an edge fact |
| `session.node_facts` / `session.edge_facts` | Engine consumption buffer |
| `session.annotation_templates` | Assertion annotation templates (waiting for the Ledger consumer to fill in `asrt_id`) |
| `session.all_facts_meta` | Audit-facing shared metadata |

### 5A.2 Annotation templates

Each buffered fact also produces an annotation-ready dict
(`asrt_id=""` placeholder):

| namespace | category | key | Notes |
|-----------|----------|-----|------|
| `pyreason` | `semantic` | `bound_lower` | Interval lower bound |
| `pyreason` | `semantic` | `bound_upper` | Interval upper bound |
| `pyreason` | `semantic` | `active_from` | Written when non-default |
| `pyreason` | `semantic` | `active_to` | Written when non-`None` |
| `shared` | `derived` | `confidence` | Derived summary = lower bound |
| `shared` | `derived` | `confidence_source` | Currently fixed at `pyreason:lower_bound` |
| `shared` | `source` | `source` / `analyst` / `method` | Forwarded from shared meta |

These `pyreason/semantic/bound_lower` and `bound_upper` rows are
engine-native adapter lanes. They are not user-authored SDK meta keys. The
shared user-facing raw uncertainty contract is
`meta={"raw_kind": "probabilistic"|"possibilistic", "bound": [lower, upper]}`,
which persists as `shared/semantic/raw_kind` and `shared/semantic/bound`.

The session also auto-fills shared confidence metadata:

- When `confidence` is not explicitly provided, it defaults to
  `confidence = lower_bound`
- When `confidence_source` is not explicitly provided:
  - The default lower-bound path writes
    `pyreason:lower_bound`
  - If the caller explicitly overrides `confidence`, it writes
    `meta:confidence`

### 5A.3 Accept helper

A minimal adapter-local accept path exists:

```python
from kernel.adapters.pyreason.accept import accept_pyreason_session

result = accept_pyreason_session(ledger, session)
```

It does two things:

1. For each buffered fact, calls shared `set_field()` and gets
   the real `asrt_id`
2. Materializes only the `pyreason/*` entries from
   `session.annotation_templates` into `AnnotationRow` and writes
   them via `ledger.append_annotations()`

`shared/*` annotations are not re-written here, because
`set_field()` already writes them via the shared whitelist. The
accept helper now validates the `origin/derivation` combination
locally to avoid letting illegal templates fail late inside
`Ledger.append_annotations()`.

### 5A.4 Current accept constraints

The graph node ids inside the PyReason session are still raw
strings (e.g. `Alice` / `Dog`), while the shared write path's
ingest-key computation requires `entity_ref` to be a canonical
token.

`accept_pyreason_session(...)` therefore currently performs a
minimal adapter-local materialization before writing into the
Ledger:

- node fact: `Alice` → `idref_v1:User:Alice`
- edge `to_ref`: `Bob` → `idref_v1:User:Bob`

This is not full factpy entity-identity alignment; it merely
allows PyReason's raw graph ids to enter the current shared write
path. A more complete identity / encoding plan is left to a
follow-up blueprint.

## 5B. Runner model

There is still a reusable lower-level execution path; the shared
evaluate surface reuses it inside `engine_eval.py`:

```python
from kernel.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    PyReasonRuleExt,
)
from kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from kernel.sdk.dsl.expr import LogicVar, Pred
from kernel.sdk.dsl.rule import Rule

x = LogicVar("x")
y = LogicVar("y")

result = run_pyreason(
    session,
    rule_defs=[
        Rule(
            id="friend_popularity",
            version="1.0",
            select=[Pred("user:popular", x)],
            where=[
                Pred("user:popular", y),
                Pred("friends:strength", x, y),
            ],
            engine_ext=PyReasonRuleExt(timestep_delay=1),
        )
    ],
    fact_defs=[
        PyReasonFactDef(
            atom="popular(Alice)",
            name="alice_popular",
            start=0,
            end=3,
            bound=[0.8, 0.9],
        )
    ],
    config=PyReasonRunConfig(timesteps=2, atom_trace=True),
)
```

### 5B.1 Runner output

| Field | Meaning |
|------|------|
| `interpretation` | Raw PyReason `Interpretation` object |
| `trace` | `PyReasonTraceV0` |
| `trace_dict` | Serializable trace dict |
| `derived_session` | A `PyReasonSession` containing only the new facts derived by the engine |
| `config` | The configuration used for this run |
| `elapsed_seconds` | Run duration |

### 5B.2 Runner boundaries

- `run_pyreason(...)` accepts both the legacy tuple form
  `rules` / `facts` and the shared `Rule` `rule_defs` / typed
  `fact_defs`
- `PyReasonFactDef.bound` is the explicit-interval entry for
  typed initial facts; the runner encodes it as
  `pred(node) : [lo, hi]` fact text before passing it to
  underlying PyReason. When omitted, it defaults to
  `(1.0, 1.0)`.
- Beyond `timestep_delay`, `PyReasonRuleExt` also supports
  `body_predicate_bounds={pred_id: (lo, hi)}` and
  `head_bound=(lo, hi)`. The former compiles body atoms into
  explicit clause intervals such as `popular(y) : [0.5, 1.0]`;
  the latter compiles the head into a static head annotation
  such as `popular(x) : [0.8, 0.9] <-1 ...`.
- When a rule plus an initial **node** seed using a non-`[1.0, 1.0]`
  bound is present, and the rule body has no explicit clause
  interval, the runner emits a `UserWarning`. The warning points
  at **PyReason's default body-threshold semantics**, not at "a
  bounded seed can never participate in matching".
- `Rule(..., engine_ext=PyReasonRuleExt(...))` is now the only
  rule-definition entry point; `compile_pyreason_rule(...)` and
  `run_pyreason(..., rule_defs=[...])` both consume the shared
  `Rule` directly
- `compile_pyreason_rule(...)` currently supports only
  `PredAtom` + `LogicVar` + literals; `CompareExpr` / `NotExpr` /
  `RuleRefAtom` raise an explicit error
- `run_pyreason(...)` itself remains a low-level helper;
  `Store.evaluate(mode="pyreason")` performs the WHERE → PyReason
  compilation and CandidateSet assembly outside, via
  `engine_eval.py`
- `derived_session` can be passed directly to
  `accept_pyreason_session(...)`

### 5B.3 Thread safety

`run_pyreason(...)` holds a module-level `threading.Lock`
(`_PYREASON_LOCK`) across all PyReason global-state operations
(from `pr.reset()` to the final `pr.reset()`). Because
`import pyreason as pr` is a process-global singleton, the lock
serializes concurrent calls.

Cleanup contract:

- `pr.reset()` runs in a `finally` block, so even if
  `pr.reason()` or any intermediate call raises, state cleanup
  still happens
- `build_pyreason_graph()` (a pure NetworkX operation) runs
  before the lock is taken
- The lock is non-reentrant (`threading.Lock`, not `RLock`); a
  reentrant call indicates a bug

## 5C. Shared execution surface

The current shared execution path is:

```python
import kernel.adapters.pyreason

candidates = sdk.evaluate(
    Derivation(
        id="drv.pyreason_popular",
        version="v1",
        where=[Pred("user:name", u, name)],
        target="user:popular",
        head_vars=[u],
        mode="pyreason",
        engine_ext=PyReasonRuleExt(timestep_delay=2),
    ),
    engine_options={"timesteps": 5},
)
```

Execution sequence:

1. `SDKStore.evaluate(...)` extracts `engine_ext` from the
   `Derivation` separately, while keeping the call-time
   `engine_options` at the evaluate-call layer; neither enters
   `to_authoring_payload()`
2. `evaluate_store(...)` / `Store.evaluate_engine(...)` forwards
   `mode="pyreason"`, `engine_ext`, and `engine_options` to the
   adapter
3. `pyreason_engine_eval(...)`:
   - Materializes Ledger active facts into a `PyReasonSession`
     via `project_view_facts(...)`
   - Compiles lowered WhereIR into PyReason rule strings via
     `compile_where_ir_to_pyreason(...)`
   - Normalizes run config via
     `resolve_pyreason_run_config(engine_options)`
   - Calls `run_pyreason(...)`; the shared evaluate path
     internally forces `atom_trace=True` to produce runtime
     provenance
   - Converts derived session facts into `CandidateSet`
   - When the run carries a `trace_dict`, upgrades each
     candidate to:
     - `support_kind="pyreason_provenance_v1"`
     - `support_digest=<ProvenanceEnvelope digest>`
     - `Store.explain_provenance(...)` can replay the event-log
       envelope by digest
   - Caches annotation templates in
     `store._engine_pending_annotations[run_id]`
4. core `accept()` writes the candidate payload back into the
   Ledger
5. In the post-accept stage the caller invokes
   `persist_pyreason_annotations(ledger, run_id, store, accept_result)`
   to bind the pending `pyreason/*` templates to real
   `asrt_id`s and write them into `annotation_rows`

### 5C.0 Runtime options

PyReason currently exposes only one run-time option on the
shared evaluate surface:

- `timesteps: int`

Constraints:

- `sdk.evaluate(..., mode="pyreason", engine_options={"timesteps": 5})`
  takes effect
- When omitted, the adapter default `timesteps=2` is used
- Unknown keys raise `ValueError`
- `atom_trace` / `convergence_*` remain adapter-internal and are
  not exposed via the shared evaluate surface
- Although `atom_trace` is not exposed on the shared evaluate
  surface, runtime candidate explain forces it on inside the
  adapter to generate `PyReasonTraceV0` / `ProvenanceEnvelope`

### 5C.1 Bounded numeric extension (L3b)

The PyReason adapter currently supports a narrowed value-carrying
path: **bounded numeric predicates**.

The trigger conditions must all hold:

1. The predicate spec explicitly declares
   `pyreason_bounded: true`
2. The value `type_domain` is numeric (currently `int` /
   `float64`)
3. The fact value can be parsed into a number within `[0, 1]`

This is an adapter-local semantic extension, not a shared schema
contract. Predicates without `pyreason_bounded: true` continue to
take v0 existence materialization, even if the value looks like
`0.85`.

Current behaviors:

- **EDB materialization**: `engine_eval.py` parses the Ledger
  value of a bounded predicate into a point interval
  `bound=(v, v)`; non-bounded predicates still use
  `bound=(1.0, 1.0)`
- **Graph build**: `runner.build_pyreason_graph(...)` now
  preserves the graph structure and writes **edge labels** as
  edge attributes; when an edge fact has a non-default bound, it
  currently writes the lower-bound summary; otherwise it writes
  `1`
- **Initial fact registration**: `runner.run_pyreason(...)` only
  lowers **node facts** from `PyReasonSession` into
  `pr.add_fact(...)`; edge facts are no longer registered
  separately. Node facts preserve `[lo, hi]` via the fact-text
  interval; edge facts continue to enter the engine via the
  graph-attribute lower-bound summary
- **Propagation boundary**: currently, real engine behavior shows
  that non-`[1.0, 1.0]` node seeds will not match a body clause
  under the **default rule-body threshold**; if the compiler
  emits an explicit clause interval (e.g.
  `popular(y) : [0.5, 1.0]`), bounded seeds can participate in
  body matching. This is verified up to here; do not extrapolate
  to "the derived head will inherit the input interval"
- **Derived head boundary**: currently, real engine behavior shows
  that when the head interval is not declared, the derived head
  defaults to `[1.0, 1.0]`; if the compiler emits an explicit
  head annotation (e.g. `popular(x) : [0.8, 0.9] <-1 ...`), the
  derived head receives that static interval. The interval here
  comes from the rule-head declaration, not from dynamic
  propagation of body bounds.
- **Derived extraction**: `runner._extract_derived_facts(...)`
  returns `value=str(lower_bound)` for bounded predicates;
  non-bounded nodes are still `"true"/"false"`; non-bounded
  edges are still empty strings
- **Canonical float64**: `float64` values that enter the
  adapter via `project_view_facts(...)` are canonical `0x...`
  bit patterns; the bounded parser explicitly supports this
  form

v0 / v1 constraints:

- The WhereIR compiler supports only lowered
  `("pred", pred_id, terms)` atoms; `eq` / `not` / `ruleref`
  raise immediately
- It uses the attribute-existence model: node predicates
  compile only the entity variable, without a value variable
- Body atoms can carry an explicit interval threshold via
  `PyReasonRuleExt.body_predicate_bounds`, but this is an
  engine-specific compile hint, not new shared-DSL semantics
- Rule heads can carry a static interval annotation via
  `PyReasonRuleExt.head_bound`, but this is also an
  engine-specific compile hint, not the dynamic uncertainty
  propagation semantics of the shared DSL
- Bounded numeric only affects materialization / extraction; it
  does not introduce a value variable into rule syntax
- `engine_ext` is a definition-time-only shared carrier;
  currently used by `Rule.engine_ext` and `Derivation.engine_ext`,
  neither of which enters the persisted payload
- `engine_options` is call-time only; it does not enter
  `Derivation`, `to_authoring_payload()`, or audit artifacts
- `Store.accept()` does not currently auto-materialize / clear
  pending annotations; v0 completes that step via
  `persist_pyreason_annotations(...)`

## 6. Souffle vs PyReason provenance comparison

### 6.1 Shape

| Dimension | Souffle | PyReason |
|------|---------|----------|
| **Data structure** | JSON proof tree (per-conclusion) | pandas DataFrame event log (per-change) |
| **Granularity** | One tree explains one conclusion | A flat log of every change |
| **Time dimension** | None | Built-in timestep, propagation traceable |
| **Value domain** | Boolean (true / false) | Interval `[lower, upper]` |
| **World assumption** | Closed (CWA) | Open (OWA, missing = `[0,1]`) |
| **How it's obtained** | `-t explain` + stdin pipe (subprocess) | `pr.get_rule_trace()` (in-process Python) |
| **Serialization** | JSON (native) | DataFrame → must be converted to JSON |

### 6.2 Unifiable fields

| Field | Souffle | PyReason | Unifiable? |
|------|---------|----------|---------|
| Conclusion identifier | `relation(args)` | `Node + Label` | ✅ map |
| Rule identifier | `rule-number (R1)` | `Occurred Due To` (rule name) | ✅ semantically aligned |
| Leaf facts | `axiom` nodes | `Occurred Due To = "fact"` rows | ✅ semantically aligned |
| Time | None | `Time` column | ❌ Souffle has no such dimension |
| Interval value | None | `Old Bound / New Bound` | ❌ Souffle has no such dimension |
| Negation | `!relation` negation leaf | N/A (no explicit negation under OWA) | ❌ different semantics |
| Sub-proof truncation | `subproof` marker | N/A | ❌ Souffle-specific |
| Clause grounding | None (implicit in tree structure) | Explicit `Clause-1, Clause-2, ...` columns | ⚠️ different shape but semantically bridgeable |

### 6.3 ProofNode v1 update suggestions

Based on the two real samples (Souffle + PyReason):

1. **We cannot assume every engine emits a tree.** Souffle is a
   tree; PyReason is an event log. The unified abstraction
   cannot be `ProofTree`.
2. **Option A: per-candidate payload with engine-specific shape.**
   Each candidate carries a `provenance_payload` whose `engine`
   field indicates the shape (`souffle_proof_tree` /
   `pyreason_event_log`); consumers dispatch rendering by engine.
3. **Option B: unify into an event sequence.** Flatten the
   Souffle proof tree into an event sequence (DFS) and align
   with the PyReason event log. The cost is losing Souffle's
   tree structure.
4. **Current recommendation: choose A.** Preserving the
   engine-native shape is more honest and aligns with the ADR
   principle of "adapter-local before core".
5. **Threshold for opening ProofNode v1**: at least two
   engines' real provenance must have flowed through the
   adapter → audit → static pipeline end-to-end before the
   unified abstraction is frozen. Souffle is complete already;
   PyReason is still a spike, not enough to freeze.

## 6A. Current EvidenceGraph converter (Step 2)

`pyreason_trace_to_evidence_graph(...)` currently implements a
**candidate-anchored timeline converter**:

- Input:
  - `PyReasonTraceV0`
  - `candidate_id`
  - `candidate_payload` (currently consumes `pred_id + terms`)
- Output:
  - `EvidenceGraph(engine="pyreason",
    layout_hint="timeline",
    support_kind="pyreason_provenance_v1")`
- Runtime export now materializes the graph into the audit
  package:
  - `audit/evidence_graphs.jsonl`
  - `AuditQuery.get_candidate_evidence_graph(...)`
  - Candidate static-page unified `EvidenceGraph` section

Current mapping rules:

- The graph root anchors on the candidate payload to the last
  matching event in the trace:
  - node candidate: `component=<entity_ref>` +
    `label=<pred short name>`
  - edge candidate: `component=<from_ref->to_ref>` +
    `label=<pred short name>`
- All trace events become graph nodes
- Only consecutive events on the same
  `(component_type, component, label)` chain produce edges of
  `edge_kind="updates"`
- `occurred_due_to`, `old_bound/new_bound`, and
  `clause_groundings` are kept in `engine_meta`

Deliberate non-goals at this version:

- Does not fabricate cross-fact / cross-component causal edges
- Does not forcibly interpret `clause_groundings` as a unified
  body-atom dependency edge
- Does not pretend a run-scoped event log is a lossless proof
  tree

The reason is that the current v0 carrier provides only
grounding text and lacks stable anchors at the body-atom label /
pred_id level; therefore the v1 converter promises only "an
honest timeline + intra-fact update chain".

## 7. Current limitations

- The shared evaluate surface is implemented, but rule registry
  / rule builder integration is still pending
- Currently commits only the runtime
  `explain_ref(kind="candidate")` provenance envelope of
  `payload_type="event_log"`; does not auto-generate candidate
  evidence tree / summary / narrative / NL
- `session.annotation_templates` can already land in the Ledger
  via `accept_pyreason_session(...)`; however accept still
  relies on adapter-local synthetic `entity_ref` materialization
- Pending `pyreason/*` annotations still need explicit
  bind/persist after accept; core `Store.accept()` does not
  complete that step automatically, but the adapter provides
  `persist_pyreason_annotations(...)`
- Depends on `pyreason==3.0.0` (not a repo-managed dependency)
- The real execution-surface operator path is still constrained
  by the external `pyreason` / `numba` / `llvmlite` environment
  compatibility; the local combination
  `numba==0.64.0` / `llvmlite==0.46.0` has not been validated
- `PyReasonTraceEventV0` field shape is not frozen
- `pyreason_trace_to_evidence_graph(...)` only builds the
  `updates` chain within the same fact / edge; cross-fact causal
  edges are deferred

## 8. Known issues (confirmed during 2026-03-29 walkthrough)

### ~~F-PR-1 PyReason global state has no thread-safety guard (severity: high)~~ — RESOLVED

Fixed: `runner.py` adds
`_PYREASON_LOCK = threading.Lock()` and wraps all `pr.*`
global-state operations with `with _PYREASON_LOCK:` +
`try/finally`. See §5B.3.

### ~~F-PR-2 `_validate_bound` does not reject bool (severity: medium)~~ — RESOLVED

Fixed: `_validate_bound` now adds an
`if any(isinstance(v, bool) for v in bound)` guard before
`float()` conversion; bool values now raise `ValueError`.

### ~~F-PR-3 `_resolve_shared_meta` confidence=0.0 asymmetric (severity: medium)~~ — RESOLVED

Fixed: the explicit confidence validation range was changed
from `(0, 1]` to `[0, 1]`, aligned with the auto-derivation
path.

### ~~F-PR-4 `pred_id.split(":", 1)[1]` assumes pred_id contains a colon (severity: low)~~ — RESOLVED

Fixed: 3 instances of `split(":",1)[1]` were replaced with
`_pred_short_name()` (from `_helpers.py`), which returns the
original value when there is no colon.

### ~~F-PR-5 `persist_pyreason_annotations` uses only the first asrt_id (severity: low)~~ — RESOLVED

Fixed: `persist_pyreason_annotations` now iterates over
`written` to build an index→asrt_id mapping and binds each
template to the correct `asrt_id` by `fact_index`.

### ~~F-PR-6 Three duplicate helper functions (severity: info)~~ — RESOLVED

Fixed: `_pred_short_name` and `_parse_edge_component` were
extracted into `_helpers.py`; `provenance.py`, `runner.py`, and
`where_compile.py` now import them.
