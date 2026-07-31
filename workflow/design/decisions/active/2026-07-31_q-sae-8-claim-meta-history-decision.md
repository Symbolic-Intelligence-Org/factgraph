# Q-SAE-8 Decision: claim_meta 事件历史 — 显式 supersede Q-SYS-B + 全局事件序

- Status: **adopted**(2026-07-31 用户批准 rev.2;裁定见 §6)
- Created: 2026-07-31
- Branch: `v0.2.0-design-storage-hardening-2026-07-31`
- **Supersedes(治理声明,rev.2 新增)**:本 ADR 显式修订 adopted 决议 [`2026-05-29_q-sys-b-revokes-migration-decision.md`](2026-05-29_q-sys-b-revokes-migration-decision.md) §4.4 中 Q15.3(claim_meta 3 列)与 Q15.7(复合 PK `(asrt_id,key)`)两条锁定 —— 原锁定在"无同键多行历史"前提下成立,该前提被 premise 重分类语义(`append_meta` 活面)证伪。Q-SYS-B 其余条款(meta_rows/annotation_rows 全删等)不受影响。
- Inputs:
  - `workflow/design/design-points/active/storage-hardening-stage-a-slice-3b.zh.md` §3.4-语义透镜
  - `ledger-schema-specification.zh.md` :101/181/184-185(复合 PK + immutable)、INV-2/§7.2(asrt_id = UUID4)
  - 源码:`premise_filter.py`(last-wins per (asrt_id,key)、reload 依赖插入顺序 —— codex 补充核实 `rows[-1]` 与 `ledger.py` reload 排序)、`sdk/store.py:683`(append_meta 活面)
  - codex 评审(2026-07-31):SQLite AUTOINCREMENT 每表独立、receipt 语义三分、Q-SYS-B 治理阻断 —— 关键修正,已核实采纳
- Scope: claim_meta 的事件化形态、全局事件序分配、receipt 承诺语义框架。
- Non-scope: meta 分级与存储位(Q-SAE-9)、tombstone 事件的具体形态(Q-SAE-9 §2 依赖但形态归其定义)。

## 1. Decision(rev.2 提案)

**claim_meta 事件化:每行是一个不可变 meta event,PK `(asrt_id, key, event_seq)`;last-wins = 组内 `max(event_seq)`。**

**`event_seq` 分配(rev.2 核心补强,codex 指出原"复用 claims 全局 seq"不可实现 —— SQLite 自增序列每表独立)**:

- 采用 **`(tx_seq, op_ordinal)` 二元组**:`tx_seq` = 提交序(Stage A 后一次 commit = 一个事务,天然全序);`op_ordinal` = 本次 commit 内按输入顺序的操作序号(覆盖"一次调用同 key 多次赋值"的次序);
- 全部读取入口(premise filter、AssertionMeta 投影、reload、导出)统一按此二元组字典序解析;
- reload/导出/迁移**保序不变量**:落库即定序,任何重建路径不得重排;
- 失败回滚:事务失败则该 `tx_seq` 下全部事件不存在(原子性由 Stage A 追加项 (a) 保证)—— 无部分序号泄漏。

## 2. 选项(修订后)

| 选项 | 判定 |
|---|---|
| **(a) 事件化 + (tx_seq, op_ordinal) 全局序** | ✅ 提案 |
| (b) 废除 append_meta,重分类走 revoke + 新 claim | ❌ 仍拒绝,但**理由修订**(见 §3) |
| (c) 就地 UPDATE | ❌ 破 INV-1,不变 |

## 3. 对 (b) 的拒绝理由修订 + 由此浮出的真问题

codex 评审正确指出原拒绝理由("新 id 使冻结 witness 悬空")**不成立** —— append 重分类同样使既有 frozen receipt 失效(有测试为证)。修订后的拒绝理由:

1. premise filter 的**文档契约**把重分类定义为"同一断言身份移入/移出排除类" —— (b) 改写该契约本身;
2. (b) 下"同一事实"的历史线被切断(新 UUID4 id),跨时间追踪一个事实的可采性演变需要额外的连续性机制;
3. (b) 对活跃事实的重分类需要 witness 重指向,机器面更大。

**但 codex 揭示的真问题独立于 (a)/(b),必须裁**:✎ **receipt 承诺语义三选一(用户拍板)** —— frozen receipt 承诺的是:

| 语义 | 含义 | 后果 |
|---|---|---|
| (i) 创建时 meta | receipt 冻结签发时刻的 effective meta | 重分类不追溯已签发 receipt;审计需另查历史 |
| (ii) 验证时 latest effective | recheck 永远按当前 meta 判 | receipt 可因后续重分类失效 —— **现行实测行为** |
| (iii) 显式 as-of(event_seq) | receipt 携带 as-of 序号,验证按该时点重放 | 机器最重,审计最强;事件化(本 ADR §1)恰好使其可实现 |

我的倾向:(iii) 为终态、(ii) 为现状 —— receipt 增加 as-of 字段但 v0.3 验证默认仍按 (ii),把 (iii) 留作 explain/audit 面的能力。此点与 Q-SAE-7 ✎2(semantic_state_digest)同场裁定。

## 4. 后果

- spec 修订面:claim_meta 表定义(+event_seq)、§9.7、INV 族("immutable"从表级降为行级);**Q-SYS-B §4.4 对应条款按本 ADR supersede 标注**;
- 与 Q-SAE-9 咬合:J 类 claim 覆盖行与 tombstone 事件(Q-SAE-9 定义)都是本 ADR 的 meta event,共用 `(tx_seq, op_ordinal)` 序;
- meta 历史入 `tx_id` 链、不入 `state_digest`(Q-SAE-7 §4 已裁)。

## 5. 验收 gates

1. 重放等价:含重复键 append_meta 的序列在新表可完整重放,读输出与 6 表现状逐字节等价(含一次调用内多次同键赋值);
2. premise filter 差分测试:重分类全路径 + revoker 对称可采性;
3. reload 保序:落库 → 冷启动 → 导出 → 再导入,event 序不变;
4. 若 (iii) 采纳:as-of 重放正确性(任取历史时点,effective meta 与当时实测一致)。

## 6. 评审整合记录 + 待用户拍板

- codex 评审:Q-SYS-B supersede、全局序分配、receipt 语义三分、(b) 拒绝理由不成立 —— **全部采纳**(拒绝结论保留、理由重写);
- **裁定 1(用户 2026-07-31)**:receipt 承诺语义 = **事件化后 receipt 携带 as-of(event_seq)字段;v0.3 验证默认按 (ii) 最新 effective(现行为);(iii) as-of 重放作为 audit/explain 面能力**;
- **裁定 2(用户 2026-07-31)**:meta 历史读取 = **v0.3 不出通用 SDK API,保留窄域 audit/debug 接口**。
