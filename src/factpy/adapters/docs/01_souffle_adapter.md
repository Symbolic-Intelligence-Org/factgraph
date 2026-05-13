# Souffle Adapter overview (factpy)

- Scope: `src/factpy/adapters/souffle`
- Last updated: 2026-03-23
- Audience: developers who need to understand the Souffle export,
  execution, and query-compile path

## 1. Module responsibilities

`adapters.souffle` is the external-engine adapter layer; it
converts `Store` / where IR into Souffle-executable programs and
their outputs.

It is responsible for:

- Engine evaluation for `Store.evaluate(mode="souffle")`
- Inference / audit package export
  (`manifest + facts + rules + policy + outputs`)
- Package execution (supporting `souffle` and `noop`)
- Compiling where IR into a query relation
- View rule generation and predicate-name normalization

It is not responsible for:

- Core semantic definitions (rule semantics, ledger semantics,
  schema canonicalization)
- Runtime session lifecycle orchestration (a service-layer
  responsibility)
- Deontic semantic execution (not implemented in this adapter
  currently)

## 2. Current module structure

- `__init__.py`
  - On import, calls
    `register_engine_evaluator(evaluate_store_engine, "souffle")`
- `engine_eval.py`
  - `evaluate_store_engine(...)`, the entry point for
    `Store.evaluate(mode="souffle")`
- `package.py`
  - `ExportOptions`, `export_package(...)`
- `runner.py`
  - `run_package(...)`, `find_souffle_binary(...)`
- `provenance.py`
  - `SouffleProofNodeV0`, `SouffleProofTreeV0`
  - `parse_souffle_proof_json(...)`
  - `run_provenance_explain(...)`
- `where_compile.py`
  - `compile_where_to_query_dl(...)`, `query_rel_for_where(...)`
- `souffle_view_gen.py`
  - `generate_view_dl(...)`
- `pred_norm.py`
  - `normalize_pred_id(...)` / `denormalize_engine_pred(...)`
- `tsv_v1.py`
  - TSV / facts read / write encoding

## 3. Boundary with core

`core` invokes the engine via a registration mechanism; it does not
statically depend on a specific adapter:

1. Import `factpy.adapters.souffle`
2. `__init__` registers the `souffle` evaluator
3. `Store.evaluate(mode="souffle")` enters this adapter's
   implementation

This boundary allows:

- core to be tested independently
- multiple engines to coexist (currently `souffle` and `problog`)
- engine implementations to be decoupled and switched by mode

Additional boundaries:

- `Souffle` continues to play only the structural-executor role.
- The prototype annotation factpy under
  `src/factpy/core/annotation/` is not part of the adapter itself.
- During the benchmark / prototype phase, combinations such as
  "Souffle structural results + a core-internal annotation helper"
  are allowed, but this does not change the fact that the formal
  `Store.evaluate(mode="souffle")` remains a single-engine adapter
  contract.

## 4. Typical workflows

### 4.1 Souffle engine evaluation

The main flow of `evaluate_store_engine(...)`:

1. Validate target / variable bindings (entity head or fact head)
2. `export_package(...)` exports a temporary package (containing
   the query where)
3. `run_package(..., engine="souffle")` executes
4. Read `outputs/<query_rel>.out.facts` and parse bindings
5. Convert into `CandidateSet` (entity / fact candidate)

Note: `engine_eval` strictly verifies that
`run_manifest.engine_mode == "souffle"`; if the runner falls back
to `noop` because the binary is missing, it raises rather than
silently succeeding.

Explainability addendum:

- The current Souffle evaluate splits explainability into two
  paths:
  - **partial witness path**
    - When `where` contains top-level `pred` atoms, the adapter
      exports a `_w` witness variant view and lets the query
      output additionally pass through witness columns
    - `engine_eval` aggregates these witness columns by binding,
      builds a restricted subset of `SupportArtifact`, and
      registers it with `Store`
    - Externally, `support_kind="souffle_witness_v1"`
    - Currently committed field scope:
      - `binding`
      - `pred_witnesses`
      - minimal `non_fact_steps`
      - `rule_ref_edges=[]`
    - When the same final binding has witness rows across
      multiple OR branches, the adapter applies a
      `source-order wins` rule
    - This is not the official Souffle provenance proof tree, but
      an adapter-level witness sidecar via Datalog rewriting
  - **degraded path**
    - If the current query cannot take the partial-witness path,
      the candidate is explicitly tagged:
      - `support_kind="engine_no_witness_v1"`
      - `support_digest="sha256:000...0"` (compatibility
        placeholder)
    - Service `explain_ref(kind="candidate")` returns `ok=true` +
      `witness_status="degraded"` for such candidates
- The first-round consumer surface still narrows to the runtime:
  - runtime `explain` / `explain-tree` accepts
    `souffle_witness_v1`
  - audit / static still defers `souffle_witness_v1`

### 4.2 Package export

`export_package(...)` produces (`export_version=v2`):

- `schema/schema_ir.json`
- `policy/policy_ir.json` and `policy/policy_rules.dl`
- `facts/*.facts` (claim / claim_arg / meta* / revokes)
- `rules/view.dl` and `rules/idb.dl`
- `manifest.json` (containing `outputs_map`, digests, entrypoints)
- `audit/*` (only when `package_kind="audit"`)

### 4.3 Package execution

`run_package(...)` supports:

- `engine="souffle"`: invokes the Souffle CLI
- `engine="noop"`: produces only empty / placeholder outputs

Souffle binary lookup order:

1. The `SOUFFLE_BIN` environment variable
2. `souffle` on `PATH`

### 4.4 Provenance helper (V0, adapter-local)

`adapters.souffle` also provides an **adapter-local provenance
helper**:

- `run_provenance_explain(...)`
  - Independently invokes Souffle `-t explain`
  - Sends `format json` / `explain ...` over stdin
  - Parses the result into `SouffleProofTreeV0`
- `run_package_provenance(...)`
  - Accepts an already-exported factpy package directory
  - Reuses the `view / idb / policy` assembly logic from the
    package manifest
  - Locates the Souffle binary and calls
    `run_provenance_explain(...)`
  - Works directly on flat query packages; for composed query
    packages containing `ruleref`, the export must provide
    `query.registry_root`
- `parse_souffle_proof_json(...)`
  - Parses the Souffle JSON proof stream
  - Depth-limited `subproof ...` truncation nodes are kept as
    leaves of `node_type="subproof"` rather than raising
- `souffle_proof_tree_to_evidence_graph(...)`
  - Consumes `SouffleProofTreeV0` directly
  - Produces `EvidenceGraph(engine="souffle",
    layout_hint="tree", support_kind="souffle_witness_v1")`
  - Current mapping conventions:
    - root = `conclusion`
    - `axiom` = `seed`
    - `derived` / `negation` / `subproof` = `premise`
    - Child nodes point at parent nodes via
      `edge_kind="supports"`
  - `rule-number` / `rule text` is preserved in `rule_label` +
    `engine_meta`

Boundaries:

- Does not modify the signature or return value of
  `run_package(...)`
- Does not enter the public contract of `core/`
- Does not introduce new service endpoints
- Does not write new audit durable artifacts
- Does not replace the existing `candidate_evidence_tree`

This path is currently used only for:

- Real-world ECSS rule / provenance shape validation
- An adapter-local proof-consumption spike

It is not a generic `ProofNode`, nor a stable contract that has
entered the formal runtime / audit / static consumption chain.

## 5. where compilation and validation conventions

`where_compile.py` supports compiling a subset of where into a
query relation, and runs through the AST gate by default
(`FACTPY_WHERE_AST_VALIDATE`):

- Supported atoms: `pred/eq/in/ne/gt/ge/lt/le/not/add/sub/neg/addc/mulc`
- Supports AND and OR-of-AND structures
- The query relation is named `query__<first-8-of-sha256>`
  (protocol-prescribed)
- Not-body and data-flow constraints are jointly enforced by the
  validator and compile-time checks
- When the query where contains `ruleref`:
  - The exporter can load exposed rules from the registry via
    `query.registry_root`
  - The compiler recursively rewrites `ruleref` into adapter-local
    internal relations and writes those relations into the same
    `rules/idb.dl`
  - The output shape of a flat query is unchanged

## 6. Current limitations

- Depends on the external Souffle CLI; when missing, the runner
  falls back to `noop`
- `engine_eval` does not accept `noop` results as valid evaluation
- The current adaptation target is query / derivation execution,
  not a Deontic-semantics inference engine
- Full native parity is not committed currently; the first-round
  Souffle output is a partial witness, not a complete rule-chain /
  recursive proof
- The Souffle provenance helper is still an adapter-local V0:
  - Only validates recursive chain / negation / rule-number
    capture
  - Already convertible to `audit.EvidenceGraph`; the runtime
    exporter now writes the unified graph into
    `audit/evidence_graphs.jsonl`
  - Does not replace the existing
    `candidate_evidence_tree` / witness pipeline
