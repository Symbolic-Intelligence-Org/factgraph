# Task Blueprint Audit: Slice 2 — Identity-as-Claim Core(Identity Claim emission + INV-7c reject + cache + `:exists` transitional guard)

- Blueprint: [2026-05-29_slice-2-identity-claim-emission.md](./2026-05-29_slice-2-identity-claim-emission.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-29 | draft | Blueprint created | Drafted after Slice 1 Form I close(`9cef674b` pushed to origin)+ ADR-IC(`2d0866ed`)+ ADR-DOCS(`bb6a2c90`)+ preflight code audit covering 5 retract_by_asrt call sites(write_protocol:170/226 protocol — Q-PR1 carve-out NOT touched;sdk/store.py:2125 SDK shell;ingest_runtime.py:169 application ingest;entity_write.py:412 application entity_write;derivation/accept.py:401 internal rollback — SF11 classification NOT touched)。Scope Freeze §6.1 captures 12 binding locks(SF1-SF12)。Implementation Plan §8 split into 11 steps each at commit boundary。Q-PR1 zero-dependency confirmed per §6.3 + §7.11。Branch `v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29` forked from Slice 1 close `9cef674b`. Sacred master `562c7419` and dirty baseline preserved per CADENCE ritual. Commit: TBD post-stage |

## Decision Notes

### 2026-05-29 — Preflight code audit

Located all relevant sites per ADR-IC §6.2 citations + 2 new findings:
- **Section A**(emission)+**Section B**(Layer 2 reject)— ALREADY shipped baseline;Slice 2 mainly formalizes via contract tests + docs + error message updates
- **Section C**(Layer 3 asrt_id reject)— NOT shipped main new work
- **Section D**(cache)— `SchemaIndex` 需要扩展;PredicateInfo flags already extended in Slice 1
- **Section E**(shadow store legacy)— Already shipped fail-fast + lazy paths;Slice 2 documents legacy positioning
- **Section F**(`:exists` co-emission + rule layer)— Already shipped read paths;rule layer NOT modified per N5
- **Section G**(protocol/core direct paths)— Q-PR1 carve-out + internal rollback classification

### 2026-05-29 — Reviewer P1+P2 Scope Freeze verdict

**P1 finding**: `application/ingest_runtime.py:169 _apply_retract` direct `retract_by_asrt` call bypass risk — bulk ingest 可绕过 Identity/exists guard。

**P2 finding**: "Application source-of-truth" wording precision —
- application-layer source-of-truth = **shared retract guard helper**(NEW `application/retract_guard.py`)
- SDK shell fail-fast = `SDKStore.retract`(consumer)
- application ingest path = `ingest_runtime._apply_retract`(consumer)
- application entity_write path = `entity_write._apply_op` retract branch(consumer)
- protocol/core direct path = schema-agnostic,intentionally unguarded per Q-PR1 carve-out + ADR-FI §4.4.2

**N11 classification finding**:`core/derivation/accept.py:401` derivation rollback `retract_by_asrt` direct call — internal rollback path,NOT user-facing;Slice 2 不 guard 但 blueprint **MUST** explicitly classify(防 reviewer 误判为漏)。

**Resolution embedded in SF2 + SF3 + SF11**:
- SF2:三层 enforcement model(helper + SDK shell + intentionally-unguarded protocol/core)
- SF3:application-layer guard MUST cover all 3 application-or-above entry points
- SF11:`core/derivation/accept.py:401` 显式 classified as intentionally-unguarded internal rollback;blueprint §6.3 + §10 Outcome 必须记录

### 2026-05-29 — 6 OQ verdicts embedded

OQ1 ✓ SchemaIndex hosts caches(SF1)
OQ2 ✓ Three-layer enforcement(SF2 + P2 precision)
OQ3 ✓ NO stub for `fg.schema.register/extend/apply`;hook-ready contract documented;wiring deferred to ADR-API Q14(SF4)
OQ4 ✓ Q-PR1 carve-out preserved(SF5)
OQ5 ✓ Slice 2 load-bearing docs scope only(SF6)
OQ6 ✓ Tests directory IN scope for Slice 2;Slice 1 SF6 NOT inherited(SF7)

### 2026-05-29 — Class size estimate M

Initial scope per ADR-IC §4.5 was ~150-300 lines。After P1+P2 verdict expansion(application ingest guard + entity_write guard + shared helper):
- SchemaIndex cache extension(~30-50 lines)
- Application retract guard helper(~100-150 lines incl. tests)
- SDK shell wrap(~30 lines)
- Application ingest wrap(~30 lines)
- Application entity_write wrap(~20 lines)
- Error messages update(~30 lines)
- Shadow store comments(~20 lines)
- Contract tests(~150-250 lines)
- Load-bearing docs(~150-200 lines)

Total ≈ 250-400 lines code + 150-250 lines tests + 150-200 lines docs ≈ **M class**(smaller than Slice 1 M/L boundary — Slice 2 is more contract-formalization than semantic rewrite)。

### 2026-05-29 — Q-PR1 carve-out preservation strategy

Per meta-ADR §4.4 hard rule + ADR-INV9 §4.4 三项绑定 carve-out + ADR-SYS-B §4.7.2:
- §6.3 explicitly lists 6 files/paths that must show zero diff:`core/evidence/write_protocol.py`,`core/store/ledger.py`,`core/store/_builders.py`,`adapters/pyreason/*`,`claims.rest_terms`,INV-9 runtime strict
- **+1 additional path classified as intentionally-unguarded(SF11)**:`core/derivation/accept.py:401` derivation rollback `retract_by_asrt` direct call — NOT user-facing
- §7.11 acceptance criterion enforces zero-diff via grep at slice close

Slice 2 has zero PyReason / adapter / ledger / write_protocol / internal derivation rollback dependency by construction。

### 2026-05-29 — Carry-forward dependencies recorded

- **ADR-API Q14 schema-evolution hook**(SF4):cache hook is "hook-ready contract" documented in blueprint §5.10;ADR-API Q14 implementation slice wires `fg.schema.register/extend/apply` to trigger cache rebuild per ADR-IC §4.3.3
- **Step 2+ `:exists` removal**(per ADR-IC §4.4.4 forward-pointer):`exists_pred_ids` 变 empty frozenset 时,`protected_anchor_pred_ids` 退化为 `identity_pred_ids` only;INV-7c 范围不动;`existence-claim transitional guard` reject 路径 dead code 清理
- **Step 2+ shadow store removal**(per ADR-IC §4.2.4 eager-emission 演化方向):`_identity_values_by_e_ref` 删除 + `fg.fields.set(Field, e_ref_string)` 若 e_ref 未 materialized → raise EntityNotInitializedError(显式 contract)
