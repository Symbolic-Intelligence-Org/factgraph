# Q-SAE-7 Decision: 双承诺模型 — state digest 与 history commitment 分职

- Status: **adopted**(2026-07-31 用户批准 rev.2;裁定见 §6)
- Created: 2026-07-31
- Branch: `v0.2.0-design-storage-hardening-2026-07-31`
- Inputs:
  - `workflow/design/design-points/active/storage-hardening-stage-a-slice-3b.zh.md` §3.4-1 / §4
  - 源码链(逐行核实于 factgraph main `b92d6bf5`):`core/store/database.py:408-410` / `:550-556` / `:109-116` / `:618-632`
  - 实测(双方独立复现,量级一致):Claude 30ms@10K / 303ms@100K / 3218ms@1M;codex 28.0 / 265.9 / 2756.8ms
  - `ledger-schema-specification.zh.md` INV-2/§7.2(**asrt_id 目标方案 = 服务端 UUID4 hex** —— 威胁模型的关键前提)、§4.9 INV-12(revoke target 禁 system claim,revoke-of-revoke 被禁)
- Scope: 承诺模型的结构(state vs history)、原语选型的裁定框架、崩溃恢复语义、meta 历史的承诺归属。
- Non-scope: tx object 存储介质、commit 原子性(Stage A 追加项)、head CAS。

## 1. Decision(rev.2 提案):不是二选一,是**双承诺并存**

codex 评审指出原 ADR 把 (a) delta 链与 (b) 多重集哈希列为替代方案是**结构错误** —— 它们回答不同问题。采纳,重构为:

| 承诺 | 定义 | 回答的问题 | 维护成本 |
|---|---|---|---|
| **`state_digest`** | 当前 active factual set 的**纯函数**(增量多重集哈希) | "两个副本的当前事实集是否一致"(快速状态核对;审计方可独立重算) | O(delta)/笔 |
| **`tx_id` 链(history commitment)** | `H(parent_tx_id ‖ 本笔全部有序变更)`,变更含:新增 assertion、revoke、**append_meta 事件**、schema 变更、digest-scheme 版本变更 | "到达此状态的完整有序历史是什么"(不同历史收敛到相同集合时仍可区分) | O(delta)/笔 |

现有 `_tx_id_for` 已具链形态,改造点 = 把 `data_digest`(全集)从链输入中移出、换为本笔 delta 的规范化字节;`state_digest` 独立存 `ledger_meta`、随同一事务更新。

## 2. state_digest 原语选型 —— 前置于选型的是威胁模型裁定

codex 评审正确指出:"≥2048-bit 模数求和足够抗 Wagner"**未经论证不成立**(hash-to-group 展宽方式、multiset 语义、攻击者可控 id 数量、目标安全级别与 generalized-birthday 工作因子,均是安全性的组成部分)。同时 spec INV-2 已裁 asrt_id = 服务端 UUID4:攻击者**不能碾磨 id 内容**,但可积累大量随机 id 后做**子集选择**(恰是 generalized birthday 的设定)—— 随机性削弱而非消除攻击面。

由此,✎ **威胁模型二选一(本 ADR 最高优先待裁项,用户拍板)**:

| 定位 | 原语 | 后果 |
|---|---|---|
| (i) **对抗性完整性机制**(digest 参与防篡改声明) | **LtHash 族**(格基,~2KB 状态,有公开分析与工程实现可援引) | 状态较大;宣传语可含"防篡改" |
| (ii) **损坏检测机制**(只防意外损坏/漂移) | 简单加法 checksum | 实现最轻;**宣传语不得声称抗恶意篡改** |

诚实边界(两种定位共同适用):能同时改写事实表与已存 head/digest 的攻击者总能重算一致状态 —— **真正的防篡改需要签名或外部可信锚点**(超出本 ADR,登记为 future design-point 入口)。我的倾向:(i) —— audit-first 产品的回执可信度值这 2KB;若选 (ii),须同步修订产品措辞。

## 3. 崩溃恢复(按 codex 评审采纳,fail-closed)

- 正常提交:数据、tx head、state_digest 状态**同一 SQLite 事务**;
- open 时只**验证**,digest 与数据不符即拒绝打开(fail closed),**不静默重建**;
- 重建走独立显式 `repair/rebuild` 流程,从数据重算(数据为真相源,INV-5 一致),并落审计记录。

## 4. meta 历史的承诺归属(与 Q-SAE-8 ✎ 共题,按 codex 评审裁定)

- append_meta 事件**不进** `state_digest`(它承诺 factual set,不承诺审计元数据);
- append_meta 事件**必进** `tx_id` 历史链(§1 定义);
- 若 premise receipt 需要承诺"有效语义 meta 状态",另设 ✎ `semantic_state_digest`(只覆盖声明为语义相关的 effective meta)—— 是否需要,随 Q-SAE-8 的 receipt as-of 语义一并裁。

## 5. 验收 gates

1. 差分测试:任意 写入/撤销/**撤销后重断言(新 UUID4 id,per INV-12/INV-14 —— 修正:revoke-of-revoke 被 spec 禁止,原 gate 措辞作废)** 序列后,增量维护的 state_digest == 从 active 集全量重算值;
2. harness "写耗时 vs 账本行数"曲线:平坦;
3. tx 链重放:从创世重放全部 tx 得到的终态 state_digest 与存储值一致;
4. 历史区分性:构造两条"不同历史、相同终集"的序列,tx 链头必须不同、state_digest 相同 —— 双承诺各司其职的直接证明。

## 6. 评审整合记录 + 待用户拍板

- codex 评审(2026-07-31):双承诺结构 / 安全论证不足 / fail-closed / meta 归属 —— **全部采纳**;revoke-of-revoke gate 措辞错误 —— **采纳修正**(INV-12 已核实)。
- **裁定 1(用户 2026-07-31)**:威胁模型选 **(i) 对抗性完整性 → LtHash**;
- **裁定 2**:`semantic_state_digest` v0.3 **不设立** —— Q-SAE-8 裁定的 receipt as-of 重放能力覆盖该需求;将来出现"快速比对语义状态"需求再议;
- 默认执行(未单独呈批,可推翻):外部锚点登记为 future design-point 入口,不排期。
