# Blueprint: Cascaded ER — Fuzzy Identity Alias Merge (P2)

- Status: implemented with deviations
- Created: 2026-04-13
- Kind: **resolver layer enhancement** (not a prompt change, not a contract change)
- Trigger: I1+I2 修复后 P0-off adversarial 实验暴露 `Module(name="Kafka Ingest Pipeline")` / `Module(name="ingest")` fragmentation — 满足三点 P2 证据标准
- Related Modules:
  - `src/factpy_kernel/agent/extraction/resolution.py`
- Audit Log:
  - [2026-04-13_extraction-cascaded-er-fuzzy-identity.audit.md](./2026-04-13_extraction-cascaded-er-fuzzy-identity.audit.md)

---

## 0. Scope

在 `EntityResolver.resolve_batch` 的 dedupe 循环内加 **alias canonicalization**: 当两个 entity key 属于同 entity_type、单字符串 identity field、且 shorter name 的 tokens 是 longer name 的 token subset 时,合并为同一 canonical key。

**做什么**: `resolution.py` 加 alias matching + canonicalization
**不做什么**: 不改 prompts / extractor / batch / models / validation。不做 embedding similarity。不做多 identity field matching。不做跨 entity_type matching。

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| ER-01 | Token subset matching(不是 edit distance / embedding） | v1 最保守;命中 "ingest" ⊂ "Kafka Ingest Pipeline" |
| ER-02 | 只匹配同 entity_type + 单 string identity field | v1 scope;多 identity field 的 entity 不做 alias |
| ER-03 | Canonical key = first seen | 和现有 exact merge 行为一致 |
| ER-04 | `enable_alias_merge: bool = False` opt-in | 默认关;caller 显式开启 |
| ER-05 | `MergeEvent.alias_merge: bool = False` 标记 alias merge | 区分 exact merge 和 alias merge |

## 2. Acceptance Criteria

1. P0-off adversarial: `Kafka Ingest Pipeline` / `ingest` 合并为 1 key
2. `resolve` / `serve` 不被误合并
3. `merge_events` 有 `alias_merge=True` 条目
4. Regression: 1007 + 5 new tests green

## 3. Outcome / Deviations

Implemented with deviations.

- Code landed in scope:
  - `ResolutionConfig.enable_alias_merge: bool = False`
  - `MergeEvent.alias_merge: bool = False`
  - resolver alias canonicalization for same-entity-type, single-string-identity, token-subset aliases
  - canonical identity rewrites to first-seen key
- Regression passed: `1012 passed, 3 skipped, 0 failed`.
- Deterministic resolver tests passed the intended behaviors:
  - `Kafka Ingest Pipeline` / `ingest` collapse under one canonical key when alias merge is enabled
  - `resolve` / `serve` do not get over-merged
  - alias merges emit `alias_merge=True` in resolver-layer tests

Deviations:

1. Notebook behavioral gate did not exercise the alias path in the final real-LLM verification.
   - P0-off adversarial rerun produced only three extraction-layer keys:
     - `Kafka Ingest Pipeline`
     - `resolve`
     - `serve`
   - `ingest` did not survive extraction as a separate key in that run, so resolver alias merging was not exercised and `merge_events` remained empty.
2. The blueprint therefore closes on deterministic evidence plus full regression, not on a stable notebook alias-merge demonstration.

Carry-forward:

- The underlying resolver enhancement is implemented and tested.
- Notebook-level verification for alias merge is currently sample- and model-variance-sensitive; if this line is revisited, use a deterministic resolver fixture or a frozen extraction checkpoint instead of relying on a single real-LLM adversarial run.
