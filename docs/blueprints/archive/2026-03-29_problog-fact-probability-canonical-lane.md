# Task Blueprint: ProbLog Fact Probability Canonical Lane

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/adapters/problog/problog_export.py`
  - `src/factpy_kernel/adapters/problog/accept.py`
  - `src/factpy_kernel/core/evidence/write_protocol.py`
  - `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/adapters/docs/02_problog_adapter.md](../../../src/factpy_kernel/adapters/docs/02_problog_adapter.md)
  - [src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md](../../../src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md)
- Audit Log:
  - [2026-03-29_problog-fact-probability-canonical-lane.audit.md](./2026-03-29_problog-fact-probability-canonical-lane.audit.md)

## 1. Problem

ProbLog currently uses `meta.confidence` as the source of fact-level EDB probability during export.

That is a design mismatch:

- `confidence` is a shared framework lane used for display/summary compatibility
- ProbLog probability is engine-native semantic data
- the repository already has a canonical ProbLog semantic lane: `problog/semantic/probability`

As long as export reads only `meta.confidence`, the system still conflates shared confidence summary with ProbLog-specific probability semantics.

## 2. Goals

- Make ProbLog export prefer `problog/semantic/probability` for fact-level probability.
- Keep `meta.confidence` as a legacy compatibility fallback.
- Preserve deterministic default `1.0` when neither canonical annotation nor legacy meta exists.
- Add focused tests that prove canonical annotation wins over legacy meta.

## 3. Non-goals

- Do not add a new `meta.probability` write interface in this slice.
- Do not redesign shared write protocol meta keys.
- Do not change `CandidateSet.confidence` / `confidence_kind` contracts.
- Do not change branch-level ProbLog semantics (`ProbLogRuleExt.branch_probabilities`).

## 4. Current Context

- 当前实现入口：
  - `adapters/problog/problog_export.py::_claim_probability(...)` reads `ledger.find_meta(..., key="confidence")`.
  - accepted ProbLog candidates already persist canonical semantic probability via `persist_problog_annotations(...)`.
  - write protocol shared whitelist currently has `confidence`, but no dedicated `probability` key.
- 当前已知约束：
  - `problog/semantic/probability` is the canonical engine-native semantic lane for accepted facts.
  - `meta.confidence` must remain readable for legacy compatibility.
  - export must stay deterministic and fail clearly on malformed probability data.
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-27_problog-semantic-annotation-parity-l4.md`
  - `docs/blueprints/archive/2026-03-29_problog-rule-ext-branch-probabilities.md`

## 5. Proposed Shape

`_claim_probability(...)` in ProbLog export will read fact probability with this priority:

1. `problog/semantic/probability` annotation
2. `meta.confidence` legacy fallback
3. default `1.0`

Canonical annotation is treated as the source of truth when present. Legacy meta remains only as fallback for pre-annotation or mixed historical data.

## 6. Boundaries And Invariants

- 必须保持的边界：
  - canonical ProbLog semantic data lives in annotations, not shared meta
  - legacy `meta.confidence` remains readable during migration
  - malformed probability values fail fast rather than silently changing semantics
- 明确不做的内容：
  - no new write API for fact probability
  - no shared-core renaming of `confidence`
- 兼容性约束：
  - old data that only has `meta.confidence` must still export correctly

## 7. Acceptance

- [x] ProbLog export prefers `problog/semantic/probability` over `meta.confidence`
- [x] Legacy `meta.confidence` continues to work when canonical annotation is absent
- [x] Facts with neither lane still export as deterministic `1.0`
- [x] Focused tests cover canonical win and legacy fallback
- [x] Affected module docs are updated

## 8. Implementation Plan

1. Update `problog_export.py::_claim_probability(...)` to read canonical annotation first, then legacy meta.
2. Add focused export tests for canonical precedence, legacy fallback, and deterministic default.
3. Update ProbLog / SDK docs to describe the canonical-vs-legacy lane split.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.en.md`

## 10. Outcome / Deviations

- 最终落地结果：
- `problog_export.py::_claim_probability(...)` 现在按 `problog/semantic/probability -> meta.confidence -> 1.0` 的优先级读取 fact-level probability。
- canonical ProbLog semantic annotation 若存在但值非法，会 fail fast；不会静默回退到 legacy meta。
- 新增 `test_problog_export.py`，覆盖 canonical annotation 优先、legacy fallback、deterministic default、以及 invalid canonical annotation error。
- ProbLog adapter 与 SDK read/write 文档已同步为“annotation canonical / meta legacy”口径。
- 与 blueprint 不同的地方：
- blueprint 只要求 canonical precedence 和 fallback；实际实现额外收紧了 malformed canonical annotation 的错误处理，明确选择 fail fast。
- 为什么会有这些调整：
- 如果 canonical annotation 已存在但值坏了，静默回退到 `meta.confidence` 会掩盖真实数据损坏；显式报错更符合当前仓库对语义数据的处理原则。
- 归档说明：
- 本蓝图已于 2026-03-29 实现完成并归档到 `docs/blueprints/archive/`。
