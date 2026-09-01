# Changelog

All notable changes to FactGraph will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking

- **SDK/application entity materialization no longer persists a second
  `<EntityType>:exists` truth carrier.** `fg.entities.create(...)` and lazy
  field materialization emit the complete Identity Claim bundle only. View
  projection derives one virtual entity-domain row when the complete chosen
  bundle reconstructs the same content-derived `e_ref`; incomplete, revoked,
  mismatched, or legacy-marker-only entities remain outside the domain.
  Existing legacy `:exists` Claims remain retract-guarded compatibility data
  and do not become projection authority.
- **Post-creation system metadata overrides now fail closed.** Append or UNSET
  operations cannot replace `ingested_at`, `ingest_key`, or
  `revoked_asrt_id`; these are the lifecycle-managed S-class keys. Source
  timestamps must use the ordinary `event_time` time-valued key instead of
  backfilling `ingested_at`. Mapping projections that explicitly consume
  `ingested_at` reject duplicate persisted values instead of silently resolving
  them last-wins.
- **Single-cardinality chosen selection now follows durable claim sequence.**
  The latest `claims.seq` wins regardless of sampled `ingested_at` or assertion
  id. This intentionally changes time-inversion, equal-time, and imported
  histories; Souffle packages now carry the matching `claim_seq` EDB relation.
- **Initial assertion and revocation metadata now requires unique keys per
  operation.** Repeating one key inside a single assertion/revocation input is
  rejected fail-closed; successive values for one key must be separate
  `append_meta` operations so `(tx_seq, op_ordinal)` defines an unambiguous
  event order.
- **The v0.3 workspace lifecycle is write-through and single-writer.**
  `FactGraph.create(path=...)` and `FactGraph.load_workspace(...)` now own a
  transactional `Database` and hold its exclusive lock until `close()`.
  Canonical mutations are durable when their call returns;
  `save_workspace()` only touches lifecycle metadata. Omitting save no longer
  discards changes, and save cannot copy or rebind a workspace. Copy a closed
  workspace directory first for dry-run/sandbox workflows. A second durable
  open, including read-only use, fails explicitly; v0.3 has no read-only open
  channel.
- **The durable workspace layout converges on `db/`.** The authoritative
  SQLite file is `db/assertions.db`; existing v0.2 `ledger.db` workspaces require
  explicit `python -m factgraph migrate-workspace <path>` before load. The CLI
  stages and verifies the replacement, writes a genesis import transaction
  using standard assertion/revocation/append-meta operations, and retains the
  complete source workspace by default. Interrupted
  replacement is reported as `workspace_recovery_required` with visible backup
  candidates and manual recovery guidance; torn-create or registry-only input
  is `workspace_incomplete` and must be recreated. The v0.3
  `factgraph_workspace.json` no longer contains a top-level `schema_digest`;
  schema anchoring now comes from the Database head and content-addressed
  schema objects. Unreleased v0.3 development workspaces carrying the
  intermediate seven-table layout have no upgrade path: open and migration
  fail with guidance to rebuild or remigrate from the original v0.2 source.
- **Database-backed ingest no longer falls back to unmanaged raw entity
  references.** `FactGraph.create(...)`, `FactGraph.load_workspace(...)`, and
  writable `FactGraph.attach(...)` fail closed when an ingest target or
  `entity_ref` value cannot be recovered from the graph's managed identity
  cache. Obtain references through `fg.entities.ref/create` before ingest.
  `FactGraph.from_schema_classes(...)` remains the lower-level unmanaged
  Ledger compatibility lifecycle and retains the legacy fallback.
- **Raw schema transitions are not an SDK policy surface.**
  `SchemaTransitionInput` is no longer exported from `factgraph.sdk`; SDK
  callers must use the additive-only `fg.schema.register/extend/apply` paths.
  The core Database DTO remains an internal, policy-free commit mechanism.

### Added

- **Trusted product compilers have a public, schema-bound compilation
  context.** `build_product_compilation_context_v1(...)` projects typed field
  descriptions and positive schema-declared relation premises from a resolved
  Rule without exposing `SchemaIndex`, mutable Store state, or Rule AST to the
  consumer. Entity-reference relationship fields are valid
  `ensure_relation` Scenario targets; scalar fields and derived predicates
  remain rejected.
- **Branch-aware Product V2 targets can be retained and executed after a
  process restart.** `FrozenEvaluationTargetV2` stores a closed, canonical,
  ABI- and digest-bound deterministic Product Policy target together with its
  normalized schema/address-space material and compiled Input Cases. Decode
  never compiles Policy or reads latest state. Product runs retain neutral
  multi-proof Branch witnesses before row deduplication and may enforce an
  explicit whole-invocation aggregate budget without changing existing
  per-side execution-profile semantics. The internal replay codec includes
  explicit typed `Var`/`Origin` and `PortType` arms required by sealed Query
  Graph targets; it is not a public raw-address or arbitrary-object wire.
- **Application-level published relation queries are shipped.** A
  `PublishedRelationGraphV1` admits only schema-matching stored entity fields,
  stored ternary relations, and endpoint-continuous forward/reverse paths.
  Typed bindings and ordered selections compile into a schema- and
  graph-pinned `SealedRelationQueryInvocationV1`; native execution consumes
  only that sealed compiler product, adds virtual entity-domain guards for
  every path node, rejects schema drift and tampering, and fails closed when
  the published row limit would be exceeded. This read/compile surface operates
  on relation facts already present in an application `Store`; it does not add
  SDK Relationship CRUD or a durable ternary Database writer.
- **Database commits now carry dual state/history commitments.** One logical
  batch is one SQLite transaction with a CAS-protected head, incremental
  `lthash16-v2` state digest binding assertion id plus content digest, and a
  normalized delta tx object carrying `digest_scheme`. Open is fail-closed;
  repair is explicit; durable opens use a lifetime `flock`.
- **`Database.commit_changes(...)` supports metadata and schema history.**
  `append_meta` is history-only and leaves active-state identity unchanged.
  Isolated `schema_change` transactions commit old/new schema digests while
  replay requires both content-addressed schema objects and transition
  continuity. Application `FieldValue` now carries `bytes` additively.
- **Schema compilation supports orthogonal metadata policy declarations.**
  `compile_schema_from_classes(..., meta_keys=...)` and authoring JSON accept
  typed `MetaKeyPolicy` declarations for reader class, premise eligibility,
  load policy, storage scope, and query indexing. Default-valued declarations
  stay out of canonical bytes; premise configuration is closed against the
  schema, and audit/lazy keys stay out of the eager evaluation workset.
- **Database batches can carry chained transaction metadata defaults.**
  `Database.commit_changes(..., meta_defaults=...)` accepts unique ordinary
  keys declared `storage_scope="tx_liftable"` and emits them in canonical key
  order. Defaults are committed in the tx object and inherited by assertions
  and revokers in that transaction; claim metadata overrides them and an
  `UNSET` claim event removes inheritance.
- **Ledger persistence converges from seven tables to three.** `claims`,
  eventized `claim_meta`, and `ledger_meta` are the complete SQLite shape;
  revocations are internal claims, while argument and annotation compatibility
  views are reconstructed projections. Metadata events use immutable
  `(tx_seq, op_ordinal)` order, support internal dual-NULL UNSET tombstones, and
  are checked against the canonical tx chain on open. Narrow audit/debug APIs
  expose event history and as-of replay without adding a general SDK history
  surface or changing factual/state/support digests.
- **The SDK exposes low-level atomic assertion/revocation commits.**
  `fg.commit_changes(assertions, revocations)` and the public
  `RevocationInput` DTO let advanced callers submit one mixed change set as
  one Database transaction.
- **The canonical SDK write surface routes through Database transactions.**
  Entity create/delete, field mutation, ingest, batch, metadata append, and
  additive schema mutation use the same commit chain for created, loaded, and
  writable-attached graphs.
- **`fg.meta.capabilities()` runtime introspection** is shipped: new read-only
  `fg.meta` namespace exposing `capabilities()` which returns a frozen
  `MappingProxyType` of `frozenset[str]` reporting runtime-accepted
  enumerations (`value_kinds`, `scalar_tags`, `cardinalities`) mirrored from
  shipped constants. Application-layer source of truth at
  `factgraph.application.capabilities.compute_capabilities`; SDK shell is a
  thin lazy-import delegator. Documented in
  [`docs/quickstart/capabilities.md`](docs/quickstart/capabilities.md).
- **RuleExpr OR matching is shipped** for `fg.read.match(...)`, including
  mixed AND/OR rule expressions, distributed port constraints, cross-branch
  de-duplication, and limit-after-union behavior.
- **Native row Form 1 evidence graphs** are shipped for passed native
  `EvaluateRow.explain()` results: native support context now populates
  `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS` topology.
- **Souffle row Form 1 evidence graphs** are shipped for passed Souffle
  `EvaluateRow.explain()` results through the same row-level Form 1 bridge as
  native rows.
- **Evidence metadata validation foundation** is runtime-enforced: graph
  metadata keeps the v1 14-key bridge, `run_id` remains envelope-only, and
  inconsistent graph metadata fails through `GRAPH_VALIDATION_FAILED`.
- **T8-C engine enrichment inventory is archived** as a planning artifact:
  ProbLog/PyReason enrichment remains deferred, with an adapter-side metadata
  bridge direction and T10 dependency gates recorded.
- **T10 semantics adapter execution inventory is archived** as a planning
  artifact: C76 ProbLog, C74+C78 PyReason, and C77 PyReason temporal work are
  split into planned follow-up implementation cycles.
- **ProbLog uncertainty projection execution is shipped** for C76: public
  `ProbLogSemantics` can carry `uncertainty_projection`, SDK lowering preserves
  it in `SemanticsProfile`, and the ProbLog adapter consumes canonical
  `raw_kind` / `bound` uncertainty annotations with explicit reject or
  point-projection policies instead of silently ignoring them.
- **T8-C-1 ProbLog evidence enrichment inventory is archived** as the planning
  artifact for the now-shipped ProbLog row-result bridge: trace-payload
  projection memory, private provenance row context, exact 14-key graph
  metadata, and namespaced `engine_meta["problog"]`.
- **ProbLog row-level provenance evidence graphs are shipped** for passed
  `EvaluateRow.explain()` results: ProbLog rows now use existing trace topology
  with `EDGE_DERIVES`, exact 14-key row graph metadata, namespaced
  `engine_meta["problog"]`, and export-time uncertainty projection decisions
  preserved from the T10-1 C76 semantics path.
- **T10-2 PyReason canonical migration inventory is archived** as a planning
  artifact: C78 `iteration_count` should ship before C74 canonical
  `derived_bound` / full-atom-id `atom_bounds`, with legacy `fixed_timesteps`,
  `head_bound`, and `branch_bounds` handled through explicit compatibility
  policy.
- **PyReason canonical `iteration_count` execution is shipped** for C78:
  public `PyReasonSemantics(iteration_count=...)` lowers into canonical
  `SemanticsProfile.iteration_count`, the adapter consumes it as PyReason run
  timesteps, and explicit conflicts with legacy temporal timesteps modes are
  rejected instead of silently choosing a winner. The wrapper default is the
  canonical `iteration_count=1`; no-profile adapter execution keeps its existing
  engine default.
- **PyReason canonical C74 rule parameters are shipped**: public
  `PyReasonSemantics(derived_bound=..., atom_bounds=...)` lowers into existing
  `rule_projection["pyreason"]` entries, full application atom ids
  `<rule_id>:atom_<index>` convert to PyReason `body_atom:0:<index>` targets,
  `derived_bound` conflicts explicitly with legacy `head_bound`, and legacy
  `branch_bounds` remains compatible with canonical body-atom thresholds.
- **T10-3 PyReason temporal migration inventory is archived** as a planning
  artifact: canonical C77 should ship as T10-3-A `fact_boundaries`
  alias/compatibility followed by T10-3-B `time_binned`; legacy
  `valid_time_boundaries` and `fixed_timesteps` remain compatibility surfaces
  through the first implementation slice.
- **PyReason canonical `fact_boundaries` temporal projection is shipped** as
  the T10-3-A C77 alias slice: `SemanticsProfile.temporal_projection` now accepts
  mode `fact_boundaries`, preserves canonical spelling, reuses the existing
  valid-time-boundary materialization substrate, and keeps legacy
  `valid_time_boundaries` compatibility intact. Explicit conflicts with
  canonical `iteration_count` remain rejected with carrier-specific error
  messages.
- **PyReason canonical `time_binned` temporal projection is shipped** as the
  T10-3-B C77 new-mode slice: `SemanticsProfile.temporal_projection` now accepts
  mode `time_binned` with explicit `universe` and strict `bin_size` validation
  (`P<n>D`, `PT<n>H`, `PT<n>M`, `1d`, `1h`, `15m`, `1m`). The adapter
  materializes fixed-width temporal bins, rejects non-divisible universes and
  ambiguous duration strings, and keeps `iteration_count` conflict behavior
  explicit.

### Changed

- **Souffle exports now materialize effective metadata only.** Historical
  superseded values and UNSET tombstones stay in the audit event history but
  do not enter the adapter's evaluation fact set.
- **v0.2 annotation migration now treats `annotation_rows` as ground truth.**
  A shared-key meta row appended after claim creation remains meta-only when
  the source has no matching annotation; migration no longer synthesizes one.
  Exact initial-meta contract annotations are regenerated, while custom
  namespace/category rows are preserved as replayable companion events.
- **SDK write-lifecycle failures are classified at the SDK boundary.**
  Writes after an SDK-owned graph is closed raise
  `SDKStoreError(code="GRAPH_CLOSED")` with
  reopen guidance. Writes through a durable view attach report its read-only
  status directly instead of being wrapped as a non-additive schema failure.
- **`Explanation.repr` conclusion line now auto-renders `Rule.desc`** when the
  rule head sets `desc=` template. `_row_conclusion_node` calls
  `head.render_desc(row.bindings)` and stores the rendered string as the
  conclusion node's `value_summary`; falls back to `head.id + repr(bindings)`
  when `head.desc is None`. The conclusion node's
  `engine_meta["desc_template"]` now carries `head.desc` instead of being
  hardcoded `None`. Closes the actual D21 §6.6 path C deferred-work item;
  the wire from `_row_conclusion_node` to `Rule.render_desc` was missing
  prior to this release.
- **Adapter module docs are aligned with shipped semantics**: ProbLog adapter
  docs now cover C76 `uncertainty_projection`, raw `raw_kind` / `bound`
  projection, and T8-C-1 row provenance graphs; PyReason adapter docs now cover
  C78 `iteration_count`, C74 `derived_bound` / `atom_bounds`, C77
  `fact_boundaries` / `time_binned`, and the T8-D round 5 deferred row-evidence
  boundary.
- **PyReason evidence deferred-state docs are explicit**: the evidence
  quickstart now states that PyReason inference, bounds, and temporal
  materialization are shipped, while rich row-level temporal evidence remains
  deferred to a future Form 2 design cycle. Current PyReason row evidence is
  described as the safe single-`NODE_CONCLUSION` fallback, not a timeline, with
  `pyreason_trace_to_evidence_graph(...)` named only as an advanced adapter
  helper.
- **Canonical semantics user docs are aligned**: quickstarts now teach ProbLog
  `uncertainty_projection`, PyReason `iteration_count`, `derived_bound`,
  `atom_bounds`, `fact_boundaries`, and `time_binned`; `rules-and-inferences`
  now leads with `Rule` / `RuleExpr` / `fg.read.match(...)` /
  `fg.eval.evaluate(...)`, keeps `Inference` as v0.2 compatibility, and no
  longer teaches `Query` as a user-facing projection path.
- **Evidence docs now reflect shipped behavior**: the quickstart and SDK guide
  document the sessionless three-layer audit model, native and Souffle Form 1
  graph shape, ProbLog row provenance graphs, winning-path-only OR marker,
  renderer guard/large-graph boundary, and current deferred evidence surfaces.
- **Evidence audit/rendering bridge hardened**: the reference renderer rejects
  non-`EvidenceGraph` inputs and warns, without truncating or refusing, when a
  graph exceeds 250 nodes or 500 edges.
- **Workflow/reference docs were refreshed**: the reference index was rebased
  onto current `workflow/` and `src/factgraph/` paths, and T8 split planning now
  records T8-A/B/C/D implementation dependencies.
- **Evidence and adapter planning docs were refreshed**: T8-C and T10
  inventories now record that ProbLog/PyReason runtime enrichment is not yet
  shipped and remains gated by adapter semantics work.
- **ProbLog semantics fixtures were migrated off removed uncertainty keys**:
  legacy `meta.confidence` remains rejected by the C110 write protocol, and the
  ProbLog migration tests now use canonical non-uncertainty fixture metadata.
- **Evidence planning docs were refined for ProbLog**: C119 multi-path DAG,
  aggregate envelopes, per-node projection enrichment, and user-facing ProbLog
  evidence docs remain deferred to future follow-up cycles.
- **Evidence user docs now include ProbLog row provenance graphs** while keeping
  native/Souffle Form 1, PyReason future boundaries, and audit/user-doc
  separation intact.

### Deferred

- PyReason evidence enrichment, ProbLog multi-path DAG enrichment, aggregate
  contributor envelopes, failed/why-not/counterfactual evidence graphs, match
  witness output, and session/signature/ACL evidence channels remain future
  tracks.

## [0.2.0-rc.1] - 2026-05-26

### Breaking

- **PyPI package renamed**: install `factgraph` instead of `factpy-kernel`.
  Existing environments should run:

  ```bash
  pip uninstall factpy-kernel
  pip install factgraph
  ```

  Python imports do not change for the v0.2 surface:
  `from factgraph.sdk import ...`.

### Added

- **Public result/evidence path**: `EvaluateResult`, `EvaluateRow`, `Claim`,
  `EvidenceRef`, `Explanation`, `row.explain()`, `row.close()`, and
  `fg.eval.explain(...)` are the public SDK explanation surface.
- **Application Rule / RuleExpr evaluation**: public `Rule` and `RuleExpr`
  values are the primary rule authoring and evaluation inputs.
- **Public semantics wrappers**: `ProbLogSemantics` and `PyReasonSemantics`
  lower into canonical semantics profiles for public SDK calls.
- **Database and durable view substrate**: `Database.create(...)`,
  `Database.open(...)`, durable assertion views, and read-only
  `FactGraph.attach(db, view=view, schema_classes=[...])` are shipped.
- **Read-side match runtime**: `fg.read.match(EntityCls, Rule | RuleExpr,
  **port_constraints)` returns distinct entity snapshots selected by
  application-rule patterns, including AND and OR `RuleExpr` combinations.
- **Property-style assertion access**: field-scoped assertion records now
  support `snapshot.field("name").active`, `.history`, `.all`, and
  `snapshot.assertions.name`; legacy `.active()` / `.all()` call forms remain
  accepted.

### Changed

- **Public package namespace**: v0.2 releases the `factgraph` Python package
  surface. The old `kernel` package shape and `factpy-kernel` distribution name
  are not the v0.2 release target.
- **SDK hard-cut**: legacy candidate `accept` workflows, direct
  check/diagnose/why-not shells, and public candidate-set result teaching were
  removed from the v0.2 SDK path.
- **View scoping**: method-level `view=` remains intentionally unsupported;
  attach-time `FactGraph.attach(db, view=view)` is the shipped scope mechanism.

### Deferred

- Witness/assertion-returning match output, method-level `view=`, snapshot
  attach by `as_of(...)`, full EvidenceGraph Phase B, and adapter-consuming
  semantics beyond carrier-only public wrappers remain future tracks.

## [0.1.0-rc.1] - 2026-05-10

First public preview release candidate.

### Added

- **FactPy Kernel SDK** (`kernel.sdk`): ergonomic OpenAI-style namespaced API
  (`schema`, `read`, `write`, `eval`, `what_if`, `audit`, `package`, `views`)
  layered over a flat `SDKStore` foundation. `FactGraph` is a literal alias of
  `SDKStore` — both surfaces are permanently supported.
- **Application layer** (`kernel.application`): explicit DTO contracts and
  pure functions for every runtime capability (Check, Diagnose, Fact Overlay,
  Why-not, Frontier, ProofFrame Recheck, Rule overlays, ProofFrame Diff,
  round events, package).
- **Walker view layer** (`kernel.application.walker`): deterministic, frozen,
  audit-friendly views over runtime artifacts for SDK-side consumption.
- **L Direction capability shells**:
  - G1: `SDKStore.check()` / `SDKStore.diagnose()`
  - G2: `SDKStore.check_fact_overlay()` / `SDKStore.recheck_proof_frame()`
  - G3: `SDKStore.check_rule_disable()` / `check_rule_literal_replace()` /
    `check_rule_add_condition()`
  - G4: `SDKStore.why_not()` (Frontier stays advanced importable)
  - G5: `SDKStore.diff_proof_frames()`
- **Engine adapters**: native, Souffle, ProbLog, PyReason — selectable at
  evaluation time.
- **Schema authoring** (`kernel.authoring`) with declarative `Entity`,
  `Identity`, `Field`, `Relationship`, `Rule`, `Pred` primitives.
- **Audit subsystem** (`kernel.audit`) with proof-frame and provenance graph
  queries.
- **Release tooling**: `scripts/release.sh` encapsulates the 3-layer
  (master → milestone → release-branch → tag) projection workflow with
  preflight, dry-run, verify, and cleanup-on-failure.
- **Changelog**: this file, following Keep a Changelog 1.1.0.

### Changed

- `pyproject.toml` version bumped to `0.1.0rc1` (PEP 440) for this release
  candidate.

### Fixed

- `SDKStore.retract()` now wraps the underlying `WriteProtocolError` from
  `kernel.core.evidence.write_protocol` into `SDKStoreError`, with the
  original exception preserved as `__cause__`. Unknown assertion ids
  carry `code="ASSERTION_NOT_FOUND"`. The SDK-boundary error contract is
  now consistent across all write operations.

### Documentation

- **SDK docs cycle**: full audit + rewrite of `src/kernel/sdk/docs/`
  against source-of-truth code across all 8 files (00 user guide
  through 07 walker, plus README and the 03 rules/derivations
  canonical reference). Corrected fictional API claims, DTO field
  names, status vocabularies (`CheckStatus`, `OverlayCheckStatus`,
  `WhyNotStatus`, `ProofFrameStatus`), and helper-function imports
  (`fg.persist_*_annotations()`, `ensure_domain`, ViewSpec dict form).
- **Cross-doc consistency**: aligned `mode='python'` / `mode='engine'`
  rename framing across 00 + 03 + 04; expanded error-code coverage in
  00 from 3 to all 7 exported codes; clarified multi-head support
  semantics (registry + evaluate accept multi-head; constraint lives
  at capability shells `check / diagnose / why_not`).
- **EN-only migration of module docs**: deleted 5 Chinese halves of
  CN/EN pairs (application/01_overview, audit/01_overview,
  core/01_architecture, core/02_quality_assessment,
  core/03_progress_roadmap); translated 15 Chinese-only docs to
  English; fixed cross-link hygiene (absolute filesystem paths →
  relative paths; stale `.md` → `.en.md` references). The kernel now
  ships EN-only documentation across every module.
- **Translation drift audit**: restored temporal hedging in
  spike-status adapter docs (PyReason §5C.1 propagation /
  derived-head boundary observations, §5A.4 accept constraint;
  core/annotation §2 certainty-lane status) so that
  observed-up-to-here behaviors are not promoted to permanent design
  claims.
- **Top-level kernel landing**: added `src/kernel/README.md` as a
  human-facing module navigation page, paralleling the existing
  `AGENTS.md` for AI agent guidance.
- Translated 4 deprecation docstrings in `kernel.core.store.ledger`
  from Chinese to English (preserving deprecation semantics).

## Earlier History

Prior development took place across the v0.1.x application-first capability
sequence (Check, Diagnose, Fact Overlay, Why-not, Frontier Trace), the A+B
public surface (helpers + walker), the L Direction SDK shells (G1-G5), and
the post-L SDK ergonomics redesign. See git history and the milestone branches
on origin (`milestone/pre-v0.1-2026-04-27` through `milestone/post-l-2026-05-09`)
for the full progression.
