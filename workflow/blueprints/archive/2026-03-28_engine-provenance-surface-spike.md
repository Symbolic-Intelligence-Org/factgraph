# Task Blueprint: Engine Provenance Surface Spike

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py`
  - `src/factpy_kernel/adapters/pyreason/provenance.py`
  - `src/factpy_kernel/adapters/problog/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/provenance.py`
  - `src/factpy_kernel/adapters/problog/problog_engine.py`
  - `src/factpy_kernel/adapters/souffle/provenance.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-22_architectural-decisions-v2.md](../active/2026-03-22_architectural-decisions-v2.md)
  - [2026-03-27_multi-engine-execution-surface-decision.md](../active/2026-03-27_multi-engine-execution-surface-decision.md)
- Audit Log:
  - [2026-03-28_engine-provenance-surface-spike.audit.md](./2026-03-28_engine-provenance-surface-spike.audit.md)

## 1. Problem

`PyReason` and `ProbLog` now both have formal execution surfaces, runtime options, semantic annotations, and real-engine E2E validation. Their remaining shared gap is provenance delivery:

- both engines still emit candidates with `support_kind="engine_no_witness_v1"`
- runtime candidate explain currently only handles two cases:
  - witness-bearing `SupportArtifact`
  - degraded/no-witness fallback
- the two engines now have real provenance sources, but they are not shaped for the current support/tree path:
  - `PyReason`: event log (`PyReasonTraceV0`)
  - `ProbLog`: CLI `--trace` proof tree / call trace

The current explain surface therefore has a hard mismatch: it is tree-first, while at least one target engine (`PyReason`) is event-log-first.

## 2. Goals

- Freeze the shared target for engine provenance before implementation
- Define the boundary between:
  - run-level raw engine trace artifact
  - candidate-level provenance witness handle
  - degraded fallback when no candidate-specific provenance is available
- Reconcile ADR-13 (`ProvenanceEnvelope`) with current `support_digest/support_kind` plumbing
- Clarify how PyReason and ProbLog should enter runtime explain without forcing them into `SupportArtifact`
- Produce an implementation plan that can be executed in narrow slices

## 3. Non-goals

- Do not implement full engine provenance in this spike
- Do not force all engines into a unified proof-tree node schema
- Do not reopen the current `SupportArtifact` / native evidence-tree contract
- Do not touch `body_confidences` core debt
- Do not add new rule-level extension APIs (`ProbLogRuleExt`, etc.)

## 4. Current Context

- 当前实现入口：
  - candidate explain first hop is `candidate_id -> (support_digest, support_kind)`
  - `Store.explain_support(...)` only replays `SupportArtifact`
  - `Store.explain_rule_trace(...)` is a separate rule-run artifact lane
- 当前已知约束：
  - runtime `explain-tree(kind="candidate")` is tree-oriented and assumes witness-bearing `SupportArtifact` or degraded fallback
  - `engine_no_witness_v1` was an explicit v0 reuse decision for multi-engine execution surface
  - ADR-13 already froze the conceptual direction: engine-specific provenance envelope, not unified proof tree
- 当前相关事实：
  - `PyReasonTraceV0` already exists as adapter-local carrier
  - ProbLog `--trace` is usable locally; `explain` subcommand is blocked by missing `maxsatz`
  - Souffle proof tree is the closest existing implementation reference, but it remains adapter-local

## 5. Proposed Shape

### 5.1 Shared target

Keep the existing first hop:

- `candidate_id -> (support_digest, support_kind)`

But split the second hop by support kind:

- native / Souffle witness kinds:
  - continue to resolve through `Store.explain_support(...)`
- engine provenance kinds:
  - resolve through a new provenance readback lane, not `SupportArtifact`
- degraded kinds:
  - continue to resolve to the existing degraded fallback

### 5.2 Core provenance contract

Adopt ADR-13 as the core boundary:

```python
@dataclass(frozen=True)
class ProvenanceEnvelope:
    candidate_id: str
    engine: str
    payload_type: str
    payload: dict[str, Any]
```

Interpretation for this spike:

- the envelope shape is core-visible
- payload contents remain adapter-local
- `payload_type` is the consumer dispatch key

### 5.3 Runtime explain target

Do **not** force engine provenance into the current candidate evidence tree.

Instead, first implementation target should be:

- `explain(kind="candidate")` can return engine provenance envelope for engine-specific witness kinds
- `explain-tree(kind="candidate")` remains tree-specific:
  - native / Souffle witness: existing tree path
  - engine provenance envelope: either explicit unsupported/deferred response or a future payload-type-specific renderer

This keeps the current evidence-tree contract stable while letting PyReason event logs and ProbLog traces surface without lossy tree coercion.

### 5.4 Engine mapping

- `PyReason`
  - run-level artifact source: `pr.get_rule_trace(interpretation)`
  - candidate-level first implementation likely remains run-level trace attached to each candidate from the same run
  - payload type: `event_log`
- `ProbLog`
  - run-level artifact source: `problog --trace`
  - requires adapter-local parser and `ProbLogTraceV0`
  - payload type: likely `proof_trace` or equivalent tree/trace label, not `proof_tree` until parser shape is frozen

### 5.5 Likely implementation slices

1. Add core provenance envelope type + Store registry/readback lane
2. Add engine-specific witness support kinds
3. Wire runtime `explain(kind="candidate")` dispatch for provenance envelopes
4. PyReason first: bridge existing `PyReasonTraceV0`
5. ProbLog second: parse `--trace` into adapter-local carrier

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `SupportArtifact` remains the native/Souffle tree-oriented witness carrier
  - engine-native provenance payloads stay adapter-local inside a core envelope
  - `candidate_id -> (support_digest, support_kind)` remains the shared first-hop contract
- 明确不做的内容：
  - do not replace `SupportArtifact` with a generic union in this spike
  - do not force PyReason event logs into tree DTOs
  - do not make audit/static HTML parity a prerequisite for first runtime provenance surface
- 兼容性约束：
  - existing native / Souffle candidate explain must not regress
  - existing degraded explain (`engine_no_witness_v1`) must remain valid until each engine gets a real witness kind

## 7. Acceptance

- [x] Shared target for engine provenance is frozen in blueprint form
- [x] No blueprint decision conflicts with ADR-13 or current candidate explain contract
- [x] The implementation plan is decomposed into narrow slices
- [x] If new durable docs become necessary during implementation, affected module docs were updated

## 8. Implementation Plan

1. Freeze the shared provenance shape and dispatch model in this spike blueprint.
2. Add a first implementation slice for core provenance envelope + Store provenance registry/readback.
3. Land PyReason provenance on runtime candidate explain using existing `PyReasonTraceV0`.
4. Land ProbLog `--trace` parser + adapter-local carrier, then connect it to the same runtime provenance lane.
5. Revisit audit/static delivery only after runtime provenance surfaces exist.

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- adapter docs for `pyreason` and `problog` once implementation starts

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - core 新增 `ProvenanceEnvelope`、digest helpers，以及 `Store` 的 provenance registry / readback lane（`explain_provenance(...)`）。
  - runtime `explain_ref(kind="candidate")` 现在按 `support_kind` 分流：
    - native / `souffle_witness_v1` → `SupportArtifact`
    - `pyreason_provenance_v1` / `problog_provenance_v1` → `ProvenanceEnvelope`
    - degraded → `witness_status="degraded"`
  - `PyReason` shared evaluate path 现在内部强制 `atom_trace=True`，把 `PyReasonTraceV0` 挂到每个 candidate 的 provenance envelope 上。
  - `ProbLog` shared evaluate path 现在默认调用 CLI `--trace`，新增 `ProbLogTraceV0` parser，并把 proof trace 挂到每个 candidate 的 provenance envelope 上。
  - tree / summary / narrative / NL / runtime candidate HTML 对 `pyreason_provenance_v1` / `problog_provenance_v1` 当前显式返回 unsupported，而不是伪装成 `SupportArtifact`。
- 与 blueprint 不同的地方：
  - 实际落地的 support kind 命名使用 `pyreason_provenance_v1` / `problog_provenance_v1`，而不是更宽泛的 `*_witness_v1`。
  - `PyReason` 第一轮没有新增 shared `engine_options.atom_trace`；为了不重开运行时参数 contract，adapter 内部直接强制开启 trace。
- 为什么会有这些调整：
  - `*_provenance_v1` 比 `*_witness_v1` 更能明确区分“可 flat explain 的 engine-native provenance”与“可进入 candidate evidence tree 的 tree-bearing witness”。
  - `atom_trace` 已明确冻结为 adapter-internal；保持 shared evaluate surface 只暴露 `timesteps`，可以避免额外 blast radius。
- 归档说明：
  - 本 spike 已完成并归档。runtime live provenance surface 已落地；audit/static consumer parity 仍按 blueprint 边界 deferred 到后续任务。
