# Design-Point: Schema 演化 — 状态化著述 + Diff 链 + 最小墓碑(两 Profile 模型)

- Status: working
- Created: 2026-08-01
- Last Updated: 2026-08-01
- Authority: candidate design / non-authoritative reference. **Not current behavior.**
- Inputs:
  - 2026-08-01 用户与 Claude 的 schema 迭代讨论(两 profile 汇流模型为用户提出并确认)
  - codex 可行性评估(2026-08-01,五点,含 IR canonical 性 file:line 核实)
  - TypeDB 机制核实(2026-08-01,官方文档级引证 —— 见 §2 对照表)
  - [`append-only-ledger-evaluation.zh.md`](append-only-ledger-evaluation.zh.md) 维度 7 / G6 缺口(non-additive 演化无 upcaster)
  - Stage A Phase 3 落地的 `schema_change` transition op(old/new digest 链,write-once schema objects)—— 本设计的既有地基
- Outputs / Downstream:(拟)独立 blueprint `schema-evolution-diff-chain`,Stage A 之后、不入 3b
- Related: `identity-mechanism-redesign.zh.md`(identity field 变更 = 硬角,显式排除)

## §1 问题与两 Profile 模型

著述制品(Python 类 / YAML)天然状态导向,历史天然事件导向 —— 强行让著述承载历史得到坟场文件。裁定的结构(2026-08-01 用户确认):

```
Profile A(code-first,SDK 直接用户):
  人改 Python 类 ──→ 编译 IR ──┐
                                ├──→ 与库内 head 的 schema IR 求 diff ──→ checker 政策门 ──→ schema_change 入链
Profile B(asset-first,meander):│
  本体 YAML 变更 ──→ checker ──→ generator 重新生成类(编译产物+运行时句柄,人不碰)──→ 编译 IR ──┘
```

**内核只有一套演化机制**(diff→政策门→入链);两 profile 的差异全部在漏斗前端。checker 规则集共用:additive 允许 / retire 允许(查墓碑防复用)/ **identity 变更拒绝**。

## §2 通用模式与产业对照

四件套:**状态化著述 + 系统求 diff + 追加式变迁链 + 最小墓碑**。

| 系统 | 著述形态 | 历史机制 | 对我们的启示 |
|---|---|---|---|
| Django | models.py 现在时 | makemigrations 自动 diff → append-only 迁移链 | Python 类 + 连续迭代的二十年工业证明;类文件是"现在"的视图,时间住在链上 |
| Terraform/Prisma/Atlas | 声明式状态 | plan diff + 应用日志 | 同型 |
| Avro/Confluent Registry | 当前 schema 文件 | registry 版本链 + 注册时兼容门 | 兼容门 = 我们的 checker 政策 |
| Protobuf | 当前 .proto | `reserved N;` 墓碑 | **最小墓碑防复用**的原型 |
| Datomic | schema 即 facts | append-only 到底,ident 改名不删 | "模型也 append-only"的成熟形态,与状态化著述不冲突 |
| GraphQL | 当前 schema | `@deprecated` 留在文件内 | 弃用期作为接口契约的可见中间态(我们可选二段式 deprecated→retired) |
| **TypeDB**(2026-08-01 核实) | **TypeQL define 语句**(非 Python;3.x 连 2.x 的编程式 API 都已删除) | **无** —— define/undefine/redefine 就地可变,只存当前态;`undefine` 真删且**必须先删光数据实例**;无版本链/迁移框架 | 反面教材两则:①"删 schema 先删 facts"与 audit-first 零相容;②零历史 —— 我们的 transition 链是**超出参照产品的差异化**。可借鉴其 `redefine` 的作者面纪律(每查询一处变更 + no-op 报错 + commit 时全量校验)。补注(2026-08-01,用户二手信息、逻辑自洽未单独核实):社区演化出**子类型派生**绕行模式(不改有数据的类型、旁边派生新子类型),硬变更(约束/基数/改名/删有数据类型)仍靠**迁移脚本 + 数据回填**。评判:子类型派生是记录型系统对 additivity 的模拟 —— claim-first 模型下"加字段=新谓词"天然 additive,**无需借鉴**;迁移+回填模式**已借鉴且升级**(见 §3.6) |

## §3 机制设计要点(codex 可行性评估五点,全部采纳)

1. **Diff 以语义键为准,不以数组序为准**:IR 编译按声明序输出、JCS 只排序对象键不排序数组(schema_compile.py:45 / schema_ir.py:63)—— diff 按 `entity_type`/`pred_id` 键控;集合型列表规范化,**语义有序列表(identity_fields、arg_specs)保序**;`generated_at`/`repr` 已被 schema identity 排除,不产生 transition。
2. **`schema_change` op payload = old/new digest-only(已按此定型,Phase 3)**:diff 算法与展示格式会演进,不冻进 tx 协议;两个 content-addressed schema object 均留存,diff 随时可重算。将来若需保存"当时裁定的 diff",增设独立 content-addressed diff object 由 digest 引用 —— 非单向门。
3. **retired 注册表(墓碑)+ 自引用环陷阱**:IR 顶层加 `retired` 节(pred_id + 退休锚点),live predicates/projection 排除退休项,注册/plan 翻译/wire 入口拒绝 pred_id 复用。**陷阱(codex 发现,裁定采纳)**:墓碑若内嵌本次 schema_change 的 tx_id → `new_schema_digest → tx_id → 墓碑 → new_schema_digest` 自引用环。**裁定:墓碑 identity 只含稳定 transition 序数/parent 锚,审计链接放 schema identity 之外。**
4. **checker 统一为 "diff 生成器 + 政策过滤器"**:现行 additive checker 是 map 比较直接抛错(schema_mutation_runtime.py:49),与 diff 门并存会两套规则漂移 —— 重构为单一 diff 生成器,additive/retire/identity 政策作为过滤器;`fg.schema.extend` 的同名类替换保留为前端语法,底下走 keyed diff。
5. **meander 侧配套**:generator/reflection 已刻意保序(generator.py:47),但 YAML model 无 retired carrier、反射丢失部分 asset-only 语义 —— 需同步扩展 YAML model/parser/checker/generator/reflection,并增加 **asset→class→IR→asset round-trip 门禁**。
6. **迁移配方(migration recipe,2026-08-01 增补 —— 借鉴"迁移脚本+回填"模式并升级为账本公民)**:把"schema transition + 回填批(revoke+重断言)+ retire 标记"包成**一个可审计单元**的 ergonomic 面。地基已全部由 Stage A shipped:回填原语(Phase 2 B1/B2 加固的同批 revoke+重断言 + 幂等重放)、迁移纪律(Phase 3 迁移 CLI 的 staging→verified replacement→归档)、schema transition 链。与外部脚本式迁移(TypeDB/Django)的结构差异:**迁移过程本身入 tx 链,可重放可审计** —— "谁、何时、依据什么迁移了这个字段"是产品能力,不是运维残迹。

## §4 硬角与非目标

- **identity field 的退休/变更**:参与 e_ref 推导,动它 = 动实体身份 —— 归 identity-redesign 线,本设计显式拒绝(checker 政策层),不装作能解;
- 不改变 additive-only 的现行允许集(本设计**新增** retire 一类,不放宽其他);
- 不进存储战役 / 不入 3b(3b 已承担表翻转);retired 标记本身 additive,不抢 v0.3 breaking 窗口。

## §5 归属与量级

独立 blueprint,Stage A 完成后可开。codex 粗估 **14–22 engineer-days**:diff/normalization 3–5、retired enforcement 3–4、SDK/additive 适配 3–4、meander round-trip 3–5、测试与迁移 2–4。依赖:Phase 3 `schema_change` op(已 shipped)。

## §6 Open Items

- [ ] retire 的二段式(deprecated 中间态)是否纳入 v1 —— 倾向不纳入,需求出现再加;
- [ ] 基数变更(multi→single 等)纳入迁移配方适用域:transition + 可选归一化回填(哪条 claim 胜出的政策待定);
- [ ] rename 语义:new-field+retire 模式 vs alias 机制 —— 待实际用例;
- [ ] transition 序数的精确定义(全局 schema transition 计数 vs tx_seq 引用)—— blueprint 时定;
- [ ] meander proposal 流与 retire 操作的治理接线(谁有权退休字段)—— meander 侧设计;
- [ ] **rule-impact gate(2026-08-01 增补)**:retire 一个谓词前,checker 用 `fg.rules.structure`(已 shipped 的引擎中立静态投影)提取规则库中每条规则引用的谓词集,与 diff 的 retired 集求交 —— **受影响规则 = 交集**,非空时拒绝 transition 或要求同 proposal 内修正规则。规则绑定 pred_id 字符串而非类对象(类重生成不失效),求值期对未知谓词 fail-closed —— 内核提供分析原语,规则库与治理门在 asset 层(factgraph 有意不设规则库);
- [ ] **`classes_from_schema_ir()` 反向生成(2026-08-01 增补)**:从工作区存储的 canonical IR(`db/objects/schema/<digest>.json`)运行时生成 Entity 类,使完全自动化的进程无需持有资产/源码即可打开工作区(正向:资产→类 已由 meander generator 证明;反向是无类运维打开的缺口,与"class-less load" deferred 项同题)。
