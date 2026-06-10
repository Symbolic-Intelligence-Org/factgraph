# Task Blueprint: Certainty — EvaluateRow.raw_kind/bound → certainty: Certainty

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/protocol/certainty.py`(**新建** `Certainty` 值对象)
  - `src/factgraph/application/protocol/evaluate_result.py`(EvaluateRow 迁移 + 三路映射 + ~9 处 raw_kind/bound 站点)
- Related Docs:
  - Design spec §3.1(certainty 字段)/§9(三路映射,G5): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-certainty.audit.md](./2026-06-09_explain-layer-certainty.audit.md)

---

## 1. Problem

design §3.1:`EvaluateRow` 的 `raw_kind: RawKind|None` + `bound: tuple[float,float]|None` 合并为单一 `certainty: Certainty|None`,与 `EvidenceTree.certainty`(S3)同类型。统一不确定度载体,消除 native 行 raw_kind=None 的消费侧特判。

## 2. Goals

1. **新建 `Certainty` 值对象**于 `protocol/certainty.py`(Codex 边界 1:放 protocol,避免 protocol→explain 反向依赖;S3 `EvidenceTree.certainty` 从此处 import)。
2. `EvaluateRow`:`raw_kind`+`bound` → `certainty: Certainty|None`。
3. **三路映射 + native 显式 boolean**(Codex 边界 2)。
4. 更新 ~9 处 raw_kind/bound 站点(serialization / payload / carrier)为 certainty。
5. **digest 不变**(claim + result 双不变,见 §6)。

## 3. Non-goals

- 改 `ClaimKind`(Q-A)—— re-evaluated,**defer/no-op**(见 §6)。
- pyreason 真区间 `[lo,hi]`(当前 confidence 是 point;区间属 branch_bounds / 未来)。
- 复用 `core.annotation.CertaintySummary`(那是 per-condition 推导原型,无关;新 Certainty 是独立 DTO 值对象)。
- prober / EvidenceTree(S3 从 protocol import Certainty)。

## 4. Current Context(preflight 已完成)

- `EvaluateRow`:`raw_kind: RawKind|None`(:99)+ `bound`(:100);`RawKind=Literal["probabilistic","possibilistic"]`(:51);校验 :110-116;构造 :699/706-707。
- 三路来源 `_raw_kind_and_bound_from_candidate`(:1491):native(confidence/confidence_kind None)→(None,None);`"probability"`→probabilistic point;`"certainty"`→possibilistic point。
- raw_kind/bound 站点(~9)::553/567(row payload 序列化)、:699/706(构造)、:968(evidence metadata)、:1263/1309(payload)、:1329/1335(carrier `{"raw_kind","bound"}`)。
- **digest(已核实)**:`claim_digest_for`(:418)= `(kind,name,bindings)`,**不含** raw_kind/bound;`result_digest_for`(:574)= row_digests + 引擎/digest 字段,**不含** raw_kind/bound;row_digest=claim_digest(不含)。→ **raw_kind/bound 不在任何 digest**。
- 既有 `core/annotation/_certainty.py` = `CertaintySummary` 推导原型,**与本 Certainty 无关**。

## 5. Proposed Shape

### `protocol/certainty.py`

```python
@dataclass(frozen=True)
class Certainty:
    lo: float
    hi: float
    kind: Literal["boolean", "probabilistic", "possibilistic"] = "boolean"
    # __post_init__: 0<=lo<=hi<=1(或按 design 边界);kind 枚举校验
BOOLEAN_CERTAINTY = Certainty(1.0, 1.0, "boolean")
```
(S3 `EvidenceTree.certainty` 后续从此 import;design §3 的 `__str__ ✓/✗/0.73/[lo,hi]` 可在此或留 S4 渲染,blueprint 不强制 S 这片做 __str__。)

### EvaluateRow 迁移 + 三路映射

- `EvaluateRow.certainty: Certainty | None`(替换 raw_kind+bound)。
- 新 `_certainty_from_candidate(candidate)`:
  - native/souffle(confidence/kind None)→ `Certainty(1.0,1.0,"boolean")`(**显式,非 None**)。
  - problog(`"probability"`)→ `Certainty(v,v,"probabilistic")`。
  - pyreason(`"certainty"`)→ `Certainty(v,v,"possibilistic")`。
- ~9 站点的 `raw_kind`/`bound` 替换为 `certainty`(非 digest 序列化)。

## 6. Boundaries And Invariants

- **★INV-digest-stable(双不变)**:`claim_digest` **不变**(kind/name/bindings 不受 certainty 影响);`result_digest` **不变**(raw_kind/bound 本就不在 result_digest;certainty 也不进 digest)。—— 经 preflight 核实,raw_kind/bound 在任何 digest 都没有,故迁移 digest-neutral。
- **Q-A(ClaimKind)re-evaluated → defer/no-op**:`kind` 在 claim_digest 内(identity-bearing),certainty 是信度/语义层不应顺手 churn claim identity;无消费点强制改 kind。query-style 下 kind 语义若将来 load-bearing 再单独评估。
- native 行 certainty **显式 boolean**(消除 None 特判);`certainty=None` 仅保留给 detached/无 candidate 边界(若有)。
- 新 Certainty 是 frozen DTO 值对象;不复用 CertaintySummary。
- INV-6;单线性栈(S2 之上)。

## 7. Acceptance

- [ ] `protocol/certainty.py` `Certainty(lo,hi,kind)` + 校验(lo<=hi;kind 枚举);`BOOLEAN_CERTAINTY`
- [ ] `EvaluateRow.certainty` 替换 raw_kind/bound;`RawKind`/`bound`/`_raw_kind_and_bound_from_candidate` 移除或改造
- [ ] **三路映射红/绿**:native→`Certainty(1,1,"boolean")`(显式)、problog→`(v,v,"probabilistic")`、pyreason→`(v,v,"possibilistic")`
- [ ] **★digest 双不变测试**:claim_digest + result_digest 在迁移前后对同输入 byte-equal(raw_kind/bound 本不在 digest)
- [ ] ~9 站点 raw_kind/bound → certainty;残留 grep(EvaluateRow 侧)= 0
- [ ] Q-A 记录为 re-evaluated/defer(audit)
- [ ] 受影响 docs 同步(EvaluateRow 字段)

## 8. Implementation Plan

1. 新建 `protocol/certainty.py`:`Certainty` + `BOOLEAN_CERTAINTY` + 校验。
2. `EvaluateRow`:字段 raw_kind/bound → certainty;`__post_init__` 校验改造。
3. `_certainty_from_candidate` 替换 `_raw_kind_and_bound_from_candidate`(三路 + native 显式 boolean)。
4. ~9 站点迁移(payload/carrier/metadata);移除 RawKind。
5. 测试:三路映射 + digest 双不变(claim+result byte-equal)+ native 显式 boolean;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md`(EvaluateRow.certainty + Certainty 类型)。

## 10. Outcome / Deviations

**落地**:impl `253423fd`(线性栈 `… → 764074fc(Certainty蓝图) → 253423fd(Certainty code)`);master 未动,未 push。

**结果**:
- 新建 `protocol/certainty.py`:`Certainty(lo,hi,kind)`(校验 0≤lo≤hi≤1 + kind 枚举 + 拒 bool)+ `BOOLEAN_CERTAINTY`。
- `EvaluateRow.raw_kind+bound → certainty`;`RawKind`/`_raw_kind_and_bound_from_candidate`/`_validate_bound` 移除。
- 三路映射:native/souffle→`BOOLEAN_CERTAINTY`、problog→`Certainty(v,v,"probabilistic")`、pyreason→`Certainty(v,v,"possibilistic")`。

**★preflight 修正(诚实记录)**:我 preflight 误判"raw_kind/bound 不在任何 digest"——**漏了 `_row_digest_for`(:543)的 `evaluate_row_digest_v2` payload 含 bound/raw_kind**(它产 row_digest → result_digest)。Codex 正确识别并补**反投影** `_legacy_raw_kind_bound_for_certainty`(certainty → 旧 raw_kind/bound;boolean→(None,None) 守卫),payload schema/key 不变 → digest 逐字节兼容。

**Gate(我独立验证)**:
- 反投影逻辑实读正确(boolean→None/None、prob/poss→(v,v));pre/post `_row_digest_for` payload schema 一致 → **digest byte-equal 由构造保证**(claim + result 双不变)。
- 三路映射 + native 显式 boolean;`EvaluateRow` 侧 raw_kind/bound/RawKind 残留 0(内部 digest 兼容层保留旧 shape,by design)。
- cohort 36 OK(独立)/ Codex 73 + 146 OK。

**Deviations / 小建议**:无 pinned-digest 钉值回归测试——byte-equal 由构造正确,建议后续补一条钉值回归防漂移(非阻塞)。`Certainty.__str__`(design §3)Codex 暂未做,留 S4;`certainty=None` 保留给边界。

**归档**:暂留 active/,随里程碑批量归档。
