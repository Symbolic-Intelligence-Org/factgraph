# ProbLog Adapter overview (kernel)

- Scope: `src/kernel/adapters/problog`
- Last updated: 2026-03-29
- Audience: developers who need to understand the ProbLog export,
  execution, and result-readback path

## 1. Module responsibilities

`adapters.problog` is the external-engine adapter layer. It
converts `Store + derivation/query where` into a ProbLog program,
executes it, and reads the results back into `CandidateSet`.

It is responsible for:

- Evaluator registration and implementation for
  `Store.evaluate(mode="problog")`
- Exporting where IR into ProbLog clauses
- Invoking the ProbLog CLI for execution
- Parsing CLI output back into bindings, then constructing
  candidate sets
- Writing probability into `CandidateSet.confidence` and tagging
  `confidence_kind="probability"`
- Persisting accepted ProbLog candidates' probabilities into the
  Annotation Store as `problog/semantic/probability` (via the
  post-accept binder)

It is not responsible for:

- Core rule semantic definitions
- Runtime session / HTTP orchestration
- Deontic specification execution semantics

## 2. Current module structure

- `__init__.py`
  - On import:
    `register_engine_evaluator(evaluate_problog, "problog")`
  - Re-exports public entry points such as
    `persist_problog_annotations(...)`
- `engine_eval.py`
  - `evaluate_problog(...)`
  - `resolve_problog_timeout(...)`: shared `engine_options`
    normalization
  - `_remember_pending_probability_annotations(...)`
- `rule_ext.py`
  - `ProbLogRuleExt`
  - `resolve_problog_engine_ext(...)`
  - branch probability normalization / bridge helpers
- `provenance.py`
  - `ProbLogTraceV0` / `ProbLogTraceEventV0` /
    `parse_problog_trace(...)` /
    `problog_trace_to_evidence_graph(...)`
- `problog_export.py`
  - `export_problog(...)`: exports the `.pl` file
- `problog_engine.py`
  - `run_problog(...)`: invokes the ProbLog CLI (the shared
    evaluate path defaults to passing `--trace`)
- `problog_import.py`
  - `parse_problog_output(...)`: parses output and constructs
    `CandidateSet`

## 3. Boundary with core

Same as the Souffle adapter: ProbLog is registered with `Store`
via mode:

1. Import `kernel.adapters.problog`
2. `__init__` registers the evaluator under the name `problog`
3. Calling `Store.evaluate(mode="problog")` enters
   `evaluate_problog(...)`

## 4. Typical workflow

Main flow of `evaluate_problog(...)`:

1. Validate target and variable bindings (entity head / fact
   head)
2. Normalize the run timeout via
   `resolve_problog_timeout(engine_options)`
3. Normalize adapter-internal rule semantics via
   `resolve_problog_engine_ext(...)`:
   - Accepts an internal
     `ProbLogRuleExt(branch_probabilities=...)`
   - Internal compiled `body_confidences` may still be bridged
     upstream (in `sdk/store.py` and `service/runtime_v1.py`), but
     public authoring / service payloads reject that key
   - If both an internal `engine_ext` and legacy
     `body_confidences` are present and inconsistent, the bridge
     raises `ValueError`
   - Track 3 / B provides core `SemanticsProfile` validation and
     inspection scaffolding only. ProbLog does not consume
     `SemanticsProfile` yet; Track 3 / C owns projection from
     `SemanticsProfile.rule_projection.problog` into adapter internals.
4. Assemble `rule_spec` (containing
   `where/head/head_vars/query_vars/engine_ext`)
5. `export_problog(...)` produces a temporary `query.pl`
6. `run_problog(...)` invokes the ProbLog CLI
7. `parse_problog_output(...)` parses the result and maps it into
   `CandidateSet`
8. `parse_problog_trace(...)` parses the same `--trace` output
   into an adapter-local proof trace
9. The derivation probability is written into
   `candidate.confidence` and tagged
   `candidate.confidence_kind="probability"`
10. If the trace is non-empty, each candidate is upgraded to:
    - `support_kind="problog_provenance_v1"`
    - `support_digest=<ProvenanceEnvelope digest>`
    - Runtime `explain_ref(kind="candidate")` can read back the
      provenance envelope of `payload_type="proof_trace"`
11. `evaluate_problog(...)` caches the
    `problog/semantic/probability` templates pending persistence
    in store pending state
12. After `accept`, the caller invokes
    `persist_problog_annotations(...)` to bind real `asrt_id`s
    into the Annotation Store

Explainability addendum:

- The current ProbLog adapter can wire CLI `--trace` output into
  runtime candidate explain:
  - `support_kind="problog_provenance_v1"`
  - `support_digest=<ProvenanceEnvelope digest>`
  - Runtime `explain_ref(kind="candidate")` returns the
    engine-native provenance envelope
- This provenance is not forcibly converted into a
  `SupportArtifact`
- However, the runtime now allows projecting an anchorable ProbLog
  trace into a `candidate_evidence_tree`:
  - Builder: `problog_trace_to_candidate_evidence_tree(...)`
  - Tree-family support:
    - `explain-tree`
    - `explain-summary`
    - `explain-narrative`
    - `explain-nl`
    - `GET /evidence/candidate/{candidate_id}`
  - This projection currently requires that the candidate payload
    be traceable from accepted claim / ledger
    - For pre-accept candidates or unrecoverable payloads, the
      tree family returns `explain_not_supported`
- The ProbLog tree contract does not reuse witness-leaf
  semantics:
  - Non-leaf logical frames → `proof_goal`
  - Terminal logical leaves → `proof_leaf`
  - `proof_leaf` does not carry an `asrt_id` and does not link to
    an assertion detail page
- When the trace answer probability is available:
  - The raw tree root writes
    `root.engine_meta.probability`
  - The summary appends `problog_probability`
  - The narrative appends `probability_lines`
  - The NL further derives a probability paragraph
- If a future engine path lacks a trace, the candidate falls back
  to:
  - `support_kind="engine_no_witness_v1"`
  - `support_digest="sha256:000...0"`

EvidenceGraph addendum:

- `problog_trace_to_evidence_graph(...)` currently implements a
  candidate-anchored tree converter:
  - Input: `ProbLogTraceV0 + candidate_id + candidate_payload`
  - Output:
    `EvidenceGraph(engine="problog", layout_hint="tree", support_kind="problog_provenance_v1")`
- Runtime export now materializes the converter result into:
  - `audit/evidence_graphs.jsonl`
  - `AuditQuery.get_candidate_evidence_graph(...)`
  - Candidate static-page unified `EvidenceGraph` section
- The converter normalizes the trace as a **call-frame tree**
  rather than a flat per-event list:
  - Each `call goal(...)` frame becomes one `EvidenceNode`
  - `result / complete / fail` is kept in the node's
    `engine_meta`
  - Child call frames point at the parent frame via
    `edge_kind="derives"`
- Root anchoring follows a best-effort rule:
  - Prefer matching the final answer / query line against the
    exact goal of a call frame
  - The candidate payload's term multiset is allowed as a subset
    of the answer args, to handle cases where query vars include
    body-only vars
  - A synthetic `answer(...)` / `query(...)` goal is preserved in
    `engine_meta`; the root node's renderer-facing `label /
    component` is still derived from the candidate payload
    semantics
- Non-goals at this layer:
  - Does not promote every `result/complete/fail` event into its
    own `EvidenceNode`
  - Does not forcibly translate a synthetic `answer(...)` back
    into a complete rule-level semantic tree
  - Does not recover richer rule labels here; `location` remains
    in `engine_meta`

Semantic-delivery addendum:

- shared compatibility lane:
  - `accept` still writes `candidate.confidence` into
    `meta.confidence`
  - `confidence_kind="probability"` is also still preserved in
    meta
- shared raw uncertainty lane:
  - user-authored uncertainty uses
    `meta={"raw_kind": "probabilistic", "bound": [lower, upper]}`
  - `write_protocol` writes `shared/semantic/raw_kind` and
    `shared/semantic/bound`, with mirrored `meta_rows` values for SDK
    selection / review
  - user-authored `probability`, `bound_lower`, and `bound_upper` meta
    are rejected; those names are reserved for adapter projection / output
    lanes
- engine-native semantic lane:
  - `persist_problog_annotations(...)` writes the probabilities of
    accepted fact candidates as
    `problog/semantic/probability`
  - The L2-completed audit export / reader / static annotation
    panel consume this annotation automatically
  - ProbLog export now also reads this annotation as the
    engine-native fact-level probability source first

## 5. Export conventions (`problog_export.py`)

- EDB source: ledger's currently active claims
- Per-claim probability:
  - Default `1.0`
  - Read first from `problog/semantic/probability` (the canonical
    engine-native lane)
  - If the engine-native annotation is absent, read from
    `shared/semantic/probability` (adapter/internal shared probability
    lane, not the user-facing raw uncertainty write contract)
  - If both semantic lanes are absent, fall back to
    `meta.confidence` (compatibility / display summary lane)
- Branch probabilities for `where` are currently carried internally by
  `ProbLogRuleExt.branch_probabilities`:
  - `branch_probabilities[i]` corresponds to normalized `where`
    OR branch `i`
  - `None` is equivalent to all branches at `1.0`
  - The value range remains `(0, 1]`
- Internal compiled `body_confidences` may still appear as input for
  the SDK / runtime bridge, but public authoring and service payloads
  reject that key. The adapter / export itself consumes only the typed
  `engine_ext`
- The durable public replacement is not active in this adapter yet:
  Track 3 / B only validates / inspects `SemanticsProfile`; Track 3 / C
  will decide how `SemanticsProfile.rule_projection.problog` normalizes
  into branch probabilities.
- The output program contains:
  - `edb_fact(...)` facts
  - `rule_body_i` branch rules
  - `answer(...)` aggregation rules
  - `query(answer(...)).`

The supported atom subset for `where`:

- `pred` (currently only 1- or 2-term forms)
- `eq`
- `gt/ge/lt/le`
- `in`
- `not` (supports OR branches in not-body)

## 6. Execution conventions (`problog_engine.py`)

CLI binary:

- Default command: `problog`
- Overridable via the `PROBLOG_BIN` environment variable
- The shared evaluate surface can override the CLI timeout via
  `engine_options={"timeout": 15}`; default `timeout=30`
- The shared evaluate path appends `--trace` by default to
  generate runtime candidate provenance

Error handling:

- Missing CLI: `ProbLogEngineError`
- Timeout: `ProbLogEngineError`
- Non-zero exit code: `ProbLogEngineError`

### 6A. Shared runtime options

ProbLog currently exposes only one run-time option on the shared
evaluate surface:

- `timeout: int`

Constraints:

- `sdk.evaluate(..., mode="problog", engine_options={"timeout": 15})`
  takes effect
- When omitted, the adapter default `timeout=30` is used
- Unknown keys raise `ValueError`
- Non-positive integers raise `ValueError`
- `engine_options` is call-time only; it does not enter
  `Derivation`, `to_authoring_payload()`, or the Ledger

## 7. Output parsing conventions (`problog_import.py`)

- Supports `tab`-separated or `:`-separated probability result
  lines
- Filters by `query_pred` (default `answer`)
- For the same binding, takes the maximum probability
- Then aggregates probability per candidate key and writes back
  into `CandidateSet.confidence`
- Also tags `CandidateSet.confidence_kind` as `"probability"`
- Final candidate construction reuses `store_builders` (consistent
  with the native / souffle paths)

## 8. Current limitations

- Depends on the external ProbLog CLI
- The `pred` atom currently supports only 1- or 2-arity argument
  mappings
- Targets derivation query execution; does not cover Deontic
  specification execution
- Currently commits only the runtime `explain_ref(kind="candidate")`
  flat provenance envelope; does not auto-generate candidate
  evidence tree / summary / narrative / NL
- No ProbLog session API; the shared runtime options currently
  expose only `timeout`
- The internal ProbLog engine extension currently contains only a
  minimal contract:
  - `ProbLogRuleExt(branch_probabilities=...)`
  - Expresses only OR-branch weighting, not fact probability,
    candidate probability, or annotation persistence
- `problog_trace_to_evidence_graph(...)` currently uses
  best-effort candidate anchoring; when a single candidate maps
  to multiple synthetic answer frames, only the closest call
  subtree is selected

## 9. Known Issues (confirmed during 2026-03-29 walkthrough)

### ~~F-PL-1 All candidates share the same trace_dict (severity: medium)~~ — RESOLVED

Fixed: `_attach_problog_provenance()` now uses
`copy.deepcopy(trace_dict)` for each candidate's
`ProvenanceEnvelope.payload`, so trace data is independent across
candidates.

### ~~F-PL-2 `_split_result_line` rsplit on colon may mis-split inside quotes (severity: low)~~ — RESOLVED

Confirmed safe: the colon-path
`_FLOAT_RE.fullmatch(rhs_trimmed)` guard ensures the rhs must be a
valid float literal, so `rsplit(":", 1)` does not mis-split even
when the goal contains colons. An inline comment was added to
document this safety.

### ~~F-PL-3 `persist_problog_annotations` uses only the first asrt_id (severity: low)~~ — RESOLVED

Fixed: `persist_problog_annotations` now iterates over `written`
to build an index→asrt_id mapping and binds each template to the
correct `asrt_id` by `fact_index` (same pattern as F-PR-5).

### ~~F-PL-4 `_claim_probability` bool-only meta.confidence raises instead of falling back (severity: low)~~ — RESOLVED

Fixed: when all `meta.confidence` values are `bool` (skipped via
`continue`), the function falls back to `return 1.0` rather than
raising `ProbLogExportError`.

### ~~F-PL-5 `_split_top_level_args` duplicated implementation (severity: info)~~ — RESOLVED

Fixed: `_split_top_level_args` was extracted into `_parsing.py`;
both `problog_import.py` and `provenance.py` now import it.
