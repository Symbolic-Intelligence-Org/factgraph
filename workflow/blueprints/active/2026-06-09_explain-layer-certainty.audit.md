# Audit Log: Certainty — EvaluateRow certainty migration

Paired with [2026-06-09_explain-layer-certainty.md](./2026-06-09_explain-layer-certainty.md).

---

## A. Preflight (2026-06-09)

- `EvaluateRow`:`raw_kind`(:99)+`bound`(:100);`RawKind`(:51);构造 `_raw_kind_and_bound_from_candidate`(:1491)。
- ★digest 核实:`claim_digest_for`(:418)=`(kind,name,bindings)`;`result_digest_for`(:574)=row_digests+引擎字段;均**不含 raw_kind/bound**;row_digest=claim_digest(不含)。→ **raw_kind/bound 不在任何 digest** → 迁移 digest-neutral(claim+result 双不变)。
- 三路来源:native→(None,None);"probability"→prob point;"certainty"→poss point。
- `core/annotation/_certainty.py` = CertaintySummary 推导原型,与本 Certainty DTO 无关。

## B. Codex 边界评估(2026-06-09,全部采纳)

| Codex 边界 | 裁决 |
|---|---|
| 1 类型放 `protocol/certainty.py`(非 explain) | ✅ **采纳并纠正我原 lean** —— 避免 protocol→explain 反向依赖 + explain 未建;S3 从 protocol import |
| 2 三路映射 + native 显式 boolean(非 None) | ✅ 与 design G5 一致 |
| 3a ClaimKind 不动(Q-A defer) | ✅ kind 在 claim_digest,certainty 不应 churn claim identity |
| 3b result_digest 允许变 | ✅ 但 preflight 证 **更优**:raw_kind/bound 本不在 result_digest → **result_digest 也不变**(无需容忍变更) |

## C. Q-A re-evaluation(design §9,Certainty slice 前重评)

**结论:defer / no-op for Certainty slice。**
- `kind`(ClaimKind)在 `claim_digest_for` 内,是 identity-bearing;query-style 下改 kind(删 fact_triple / 加 query_row)会 churn claim digest。
- certainty slice 与 kind 正交;无消费点强制改 kind。
- query-style kind 语义若将来 load-bearing,再单独 slice 评估。

## D. Locked decisions

- `Certainty(lo,hi,kind)` 新 DTO at `protocol/certainty.py`;`BOOLEAN_CERTAINTY`。
- 三路:native `Certainty(1,1,"boolean")` 显式 / problog `(v,v,"probabilistic")` / pyreason `(v,v,"possibilistic")` point。
- INV-digest-stable:claim_digest + result_digest **双不变**(byte-equal 测试)。
- pyreason 真区间 [lo,hi] = 未来(branch_bounds),本片 point。

## E. Open items for Codex

- `Certainty.__post_init__` 边界:`lo<=hi`;`0<=lo,hi<=1`?(boolean=1,1;prob/poss∈[0,1])—— 确认 bounds 校验范围。
- `Certainty.__str__`(design §3 ✓/✗/0.73/[lo,hi])本片做 or 留 S4 渲染 —— 你定,非阻塞。
- `certainty=None` 是否保留(detached/无 candidate 边界)vs 全行必有 certainty。

## F. Gate result / Deviations

impl + gate 后填写。
