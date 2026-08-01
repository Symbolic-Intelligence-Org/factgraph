# Audit Log: Slice 3b — Ledger 7→3 表迁移 + claim_meta 事件化 + Meta 分级

- Blueprint: [2026-08-01_slice-3b-ledger-migration.md](./2026-08-01_slice-3b-ledger-migration.md)

## Adopted Conclusions(引用来源 → 本任务采用)

| 来源 | 采用结论 |
|---|---|
| spec §9(权威) | 七步精简逐条落地;§9.7 复合 PK 被 Q-SAE-8 supersede(事件化 PK 含序) |
| Q-SAE-8 adopted | `(tx_seq, op_ordinal)` 全序、last-wins=max、UNSET、receipt as-of(默认 latest-effective / as-of 归 audit)、meta 历史窄域接口 |
| Q-SAE-9 adopted | 五正交属性入 digest、`premise_eligible` 封闭集 `{provenance_class, origin_binding}`、tx_ref 列、tx-lift + 两层 last-wins、audit 类惰性、chosen→seq(语义变更)、S 禁覆盖 + event_time、三组对照测量 |
| Stage A §7.1 护栏 | Q-SAE-8 只有 tx_seq 地基已交付;Q-SAE-9 只有介质裁定已交付 —— 其余在本 blueprint 兑现,不得当作已有 |
| Stage A known-gaps(3b 归属) | append_meta 链-账本 parity、dbtx_v2 golden fixture、application 调 ledger 私有名转正 |
| Stage A 教训 | 新写通道三侧守卫 checklist;blueprint 引用 ADR 承诺表逐行转录;golden 先于动表 |

## Session Journal

| Date | Event | Notes |
|---|---|---|
| 2026-08-01 | blueprint created at `scoped` | scope 由 adopted ADR + spec §9 锁定;Phase 0 把 golden fixture 与 spec 修订前置为安全网;内联裁定待办:migration CLI 对 3b 前 v0.3 工作区的升级路径(§7 倒数第二条)在 Phase 1 前由协调方裁定 |

## Deviations

(none yet)
