# Task Blueprint: Product Explanation Canonical Read Contract

- Status: archived
- Created: 2026-08-15
- Last Updated: 2026-08-16
- Related Modules:
  - `src/factgraph/application/product_explanation_data_v2.py`
  - `src/factgraph/application/product_result_views_v2.py`
  - `src/factgraph/sdk/product_evaluation_outcome.py`
  - `tests/application/test_product_views_v2.py`
  - `tests/sdk/test_product_evaluation_outcome_v2.py`
  - `tests/sdk/test_product_function_v2.py`
- Related Docs:
  - adopted Q-R5 CompletedRunRecord/data-first Explain boundary (external
    Meander design input, not shipped by this FactGraph slice)
  - [Q20 Product interface decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
  - [Product Result and Explain Views V2](../../../src/factgraph/application/docs/product_result_explain_v2.md)
- Audit Log:
  - [2026-08-15_product-explanation-canonical-read-contract.audit.md](./2026-08-15_product-explanation-canonical-read-contract.audit.md)

## 1. Problem

FactGraph already exposes data-first Product Explain facades for sealed V1 and
V2 runs, including closed EvidenceGraph availability states and pure
`narrate()` / `render_text()` presentation helpers.  The public facade does not
yet expose a versioned, canonical, JSON-safe serialization contract.  Business
code can therefore consume the frozen Python DTOs, but API/UI/Agent boundaries
still lack one stable wire projection and digest.

The gap must be closed without creating a second generic `ExplanationDataV1`,
without converting an identity-only R3a anchor into a Product V2 run, and
without fabricating evidence for an engine or source protocol that did not
capture it.

## 2. Goals

- Add a versioned JSON-safe `to_dict()` projection to both existing Product
  Explain facade variants.
- Add deterministic canonical bytes and a content digest derived solely from
  that structured projection.
- Preserve `source_protocol` and the distinct sealed V1/V2 payload shapes.
- Preserve explicit EvidenceGraph availability as `state + reason_code +
  optional graph`; never infer availability from `graph is None` alone.
- Keep `narrate()`, `render_text()`, and `repr()` as pure, lossy presentation
  consumers of structured data.
- Add executable documentation showing one captured-graph path and one
  graph-unavailable path, with business code branching on structured state.

## 3. Non-goals

- No new FactGraph `ExplanationDataV1` wrapper.
- No Meander `ExplanationReadModelV1`, `CompletedRunRecordV1`, SourceRecord,
  admission, ACL, retention, or redaction implementation.
- No edits to R3a `EvaluateResult`, run-anchor, Store, Query execution bridge,
  or identity-only anchor semantics.
- No new EvidenceGraph capture, detached evaluator, replay level, negative
  proof, source-authority, action-authorization, or cross-engine proof-parity
  claim.
- No coercion of legacy V0/Captured V0 artifacts into a Product V2 run.
- No parsing of narration as machine data.

## 4. Current Context

- `EvaluationExplanationDataV2` adapts a sealed V1 run and may expose sanitized
  Native detached evidence.
- `EvaluationRunV2ExplanationDataV2` adapts a sealed Product V2 engine
  observation and truthfully reports unavailable EvidenceGraph for currently
  unsupported paths such as ProbLog.
- `EvidenceSupportViewV2` already enforces the closed graph/no-graph state
  invariant.
- Both facade variants already provide `narrate()` and `render_text()` but no
  JSON-safe canonical projection.
- Q-R5 assigns the later business join, source filtering and persistence read
  model to Meander rather than FactGraph.
- R3a is a separate active migration line and is limited to identity-only
  anchors; this slice must not edit its shared core files.

## 5. Proposed Shape

### 5.1 One canonical Product Explain envelope

Both existing facade variants expose:

```python
data.to_dict()             # detached JSON-safe dict/list/scalar values
data.to_canonical_bytes() # UTF-8 canonical JSON
data.content_digest       # sha256 token of those exact bytes
```

The top-level projection contains an explicit schema identifier/version and
the source protocol.  The existing structured sections remain top-level; the
wire does not hide them inside renderer output.

### 5.2 Strict projection

The serializer accepts only the closed Product Explain/result-view DTO graph,
the exact nested `GoalTechnicalAssessmentV1` DTO, JSON scalar values,
tuples/lists, and string-keyed mappings.  It never accepts an arbitrary
dataclass and never calls an arbitrary object's `repr()`, `to_dict()`, callback,
source resolver, Store, or evaluator. Mapping proxies become detached
dictionaries; tuples become JSON arrays; non-finite floats are rejected rather
than emitted as non-standard JSON.

### 5.3 Availability remains first-class

The serialized evidence section always includes:

```json
{
  "state": "not_available",
  "reason_code": "PROBLOG_V2_EVIDENCE_GRAPH_NOT_CAPTURED",
  "graph": null,
  "proof_parity": "not_claimed"
}
```

When a graph is captured, the same section contains its sanitized
`EvidenceGraphViewV2` projection.  No consumer must infer meaning from a null
graph alone.

### 5.4 Presentation remains downstream

`narrate()`, `render_text()`, and `repr()` keep their current roles and do not
become canonical storage.  The implementation may refactor them to read the
same frozen DTO, but their prose is not part of the canonical content digest.

### 5.5 Example

An executable notebook or adjacent example demonstrates:

1. selecting an explicit row;
2. obtaining structured Explain data;
3. serializing with `to_dict()` and validating the digest/bytes relationship;
4. inspecting a captured sanitized EvidenceGraph;
5. inspecting an unavailable graph with its reason code; and
6. rendering narration without parsing it back into business state.

## 6. Boundaries And Invariants

- The schema version describes the Product Explain read projection, not the
  source run protocol version.
- `source_protocol` remains `evaluation_run_v1` or `evaluation_run_v2` and is
  never rewritten.
- Serialization is deterministic, redaction-safe relative to the existing
  sanitized DTO, and has no live dependencies.
- `content_digest` proves equality of the read projection bytes only; it does
  not authenticate the underlying run, source, or user.
- `content_digest` is not embedded in `to_dict()` or the bytes it hashes; it is
  the external digest of exactly `to_canonical_bytes()`.
- Existing sealed run/row/observation pins remain the authority for identity.
- Existing unavailable and unsupported evidence states remain unavailable and
  unsupported after serialization.
- No `None` value is assigned new evidence, replay, source, or policy meaning.
- Existing public constructors and facade return types remain compatible.
- The implementation must not touch the active R3a core file set.

## 7. Acceptance

- [x] Both Product Explain facade variants expose `to_dict()`, canonical bytes,
      and a stable content digest.
- [x] The projection is accepted by strict standard-library JSON encoding with
      `allow_nan=False` and contains no tuple, mapping proxy, dataclass, or
      arbitrary rich object.
- [x] Repeated serialization is byte-identical and digest-identical.
- [x] Changing a structured captured value changes canonical bytes and digest.
- [x] V1 captured-graph serialization preserves its sanitized graph and
      availability state.
- [x] V2 graph-unavailable serialization preserves reason code, null graph,
      probability materialization, Scenario provenance, Function and choice
      captures when present.
- [x] Narration/render output remains presentation-only and is excluded from
      the canonical digest.
- [x] Existing V0/V1/V2 tests remain green and R3a core files remain untouched.
- [x] Module docs and the executable example are synchronized.

## 8. Implementation Plan

1. Add one private strict DTO-to-wire projector and canonical JSON/digest
   helpers in `product_explanation_data_v2.py`.
2. Add the three additive methods/properties to the two existing public
   Product Explain facade classes.
3. Add focused serialization, determinism, redaction, graph-available and
   graph-unavailable tests without changing run execution.
4. Update Product Explain module docs and SDK docstrings to make structured
   serialization the business contract and rendering display-only.
5. Add or extend one executable example and run it with the `factpy` kernel.
6. Run focused Product tests, the relevant application/SDK regression cohort,
   Ruff, mypy, JSON validation and `git diff --check`.

## 9. Docs To Update

- `src/factgraph/application/docs/product_result_explain_v2.md`
- `src/factgraph/sdk/docs/08_product_scenario_execution_v2.en.md`
- `examples/README.md`
- one executable notebook under `examples/`

## 10. Outcome / Deviations

- 最终落地结果：`EvaluationExplanationDataV2` 与
  `EvaluationRunV2ExplanationDataV2` 均新增 detached `to_dict()`、strict
  canonical JSON bytes 与 read-projection `content_digest`。序列化器逐字段
  解析真实类型注解，仅接受 Product read DTO、准确的
  `GoalTechnicalAssessmentV1` 和声明允许的 JSON 值；外来 dataclass 或把
  DTO 槽替换成 dict 均 typed fail-closed。
- EvidenceGraph 语义没有扩大：V1 Native detached 路径保留 sanitized graph；
  V2 Native/ProbLog 未捕获路径保留 `state + reason_code + graph=None +
  proof_parity=not_claimed`。Scenario、概率物化、WeightedChoice 与 Product
  Function capture 均能进入 canonical projection。
- 文档与示例：更新 Product application docs、SDK V2 guide、outcome
  docstring 和 examples index；新增并真实执行
  `examples/10_structured_explanation_contract.ipynb`，6/6 code cells、0
  error outputs，同时展示 graph-present 与 graph-unavailable。
- 验证：`tests/application tests/sdk` 为 **772 passed / 853 subtests**；
  Ruff check/format、两生产模块 mypy、`git diff --check` 全部通过。
- 与 blueprint 不同的地方：为了覆盖已承诺的 Function capture wire，新增
  `tests/sdk/test_product_function_v2.py` 的 focused assertion；属于既定
  acceptance 的测试补强，没有扩大 runtime scope。
- 流程偏差：本 slice 是单模块加法式 public read projection，自愿执行
  preflight；为避免切换共享 worktree 干扰并行 R3a，preflight 未另建物理
  branch，而是在当前非 sacred implementation branch 完成并明确记录。
- R3a 边界：`EvaluateResult`、run anchor、Store、Query execution bridge 与
  identity-only semantics 均未修改。未来 R3a adapter 仍是独立加法式 slice。
- 归档说明：实现、测试、module docs 与 executable example 已闭合；
  blueprint、paired audit 与 standalone preflight 已于 2026-08-15 一并归档。
- Post-archive integration correction (2026-08-16): a clean-target acceptance
  found that the delivered module-name dataclass predicate did not enforce
  PF-1. The target now uses the exact reachable DTO identity closure, rejects
  dynamic dataclasses and hostile/unbounded JSON-like values fail-closed, and
  preserves the three graph-bearing availability states in its state-first
  consumer guidance. The paired audit records this explicit correction; the
  original preflight remains historical evidence.
