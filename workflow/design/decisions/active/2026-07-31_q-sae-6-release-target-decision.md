# Q-SAE-6 Decision: Storage Hardening 战役的 Release 落点

- Status: **adopted**(2026-07-31 用户批准 rev.2;codex 评审意见已整合)
- Created: 2026-07-31
- Branch: `v0.2.0-design-storage-hardening-2026-07-31`(多 Q 合并分支,per CADENCE deviations)
- Inputs:
  - `workflow/design/design-points/active/storage-hardening-stage-a-slice-3b.zh.md` §1/§4
  - `workflow/design/design-points/active/factgraph-storage-architecture-evolution.zh.md` §5.2(原始 Q-SAE-6 提出处)
  - `feedback_factgraph_main_no_auto_merge.md` / `project_release_branch_invariants.md`(发布面纪律)
- Scope: 裁定 Stage A + Slice 3b(含 Q-SAE-7/8/9 三项合同变更)落 v0.2.x 还是 v0.3.0;联动 meander 侧发布协调义务。
- Non-scope: 具体发版机器(release.sh 流程)、v0.3.0 的其余内容清单、meander 侧适配的实施细节。

## 1. Decision(提案)

**选 (b) — v0.3.0。** v0.2.x 冻结为维护线,不再接收任何本战役内容。

## 2. 选项

| 选项 | 内容 | 判定 |
|---|---|---|
| (a) v0.2.x patch | Stage A 以兼容姿态挤进 v0.2.x | ❌ 拒绝 |
| (b) v0.3.0 | 战役整体(Stage A + 3b + Q-SAE-7/8/9)作为一个协调发布 | ✅ 提案 |

## 3. 理由

1. 本战役至少携带**四项合同破坏**:lifecycle 语义反转(create/load_workspace 内部改基于 Database)、7→3 表 schema flip、`DBDATA_V1`→新 digest 方案(全部 tx_id 变化)、meta 分级(claim_meta 形态变化)。任何一项都不符合 patch line 语义,四项叠加更不容讨论。
2. 四项变更互相咬合(meta 分级决定 claim_meta 形态 → 形态决定 PK 方案 → tx 具象化给 digest 提供批次锚点),拆开跨版本发布 = 中间态合同要维护兼容,成本远超一次协调发布。
3. alpha 窗口论证(design-point §2.5)要求四项**同窗落地**——v0.3.0 是唯一能承载"一次 breaking、终态合同"的载体。

## 4. 后果

- v0.2.x:维护线,仅接收严格受限的 backport(见 §5);
- **发布时序(2026-07-31 按 codex 评审修订:顺序反转,pin 先行)**:
  1. meander test/build/deploy 全部 checkout 先 **pin 到已知 v0.2 不可变 SHA/tag**(现状 `deploy.yml` 无 ref = 永远 default branch,必须先堵);
  2. factgraph 发布 v0.3.0 RC;
  3. meander 对 RC SHA 完成适配 + 跨仓验证;
  4. factgraph 发布 v0.3.0 final;
  5. meander 改 pin 至 v0.3.0 final SHA/tag。**永不解除 pin** —— 跨仓构建从此只引用不可变版本,漂移类问题(PR#22 教训)从根上消除;
- Q-SAE-7/8/9 的全部 ADR 以"落 v0.3.0"为前提起草,无跨版本兼容负担。

## 5. Backport 政策(2026-07-31 按 codex 评审修订:保留通道,严格受限)

v0.2.x 仅接收:安全漏洞、数据丢失/账本损坏、已发布契约的严重正确性错误。**不 backport** 新能力、存储格式或行为变化。理由:v0.2.0 有真实部署消费者,完全关闭通道会把紧急修复与 v0.3 迁移强绑定。

## 6. 评审整合记录

- codex 评审(2026-07-31):发布顺序反转 + 永久 pin —— **采纳**(消除了原时序中 default-branch 断裂窗口);backport 受限保留 —— **采纳**。
- 遗留给用户拍板:本 ADR 修订后即可 adopted,无未决 ✎。
