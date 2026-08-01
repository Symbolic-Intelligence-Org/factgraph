# Task Blueprint: Schema 演化 — Diff 链 + 墓碑 + 内省渲染面

- Status: draft(**scope-freeze 前提 = Slice 3b 完成 + §5 决策点裁定**;先行起草以锁定交付物清单)
- Created: 2026-08-01
- Last Updated: 2026-08-01
- Branch: (实施时定;设计基线 = [schema-evolution-diff-chain.zh.md](../../design/design-points/active/schema-evolution-diff-chain.zh.md) 全文)
- Related Docs:
  - 设计笔记 §1 两 Profile 汇流 / §2 产业对照 / §3.1-3.8 机制要点(全部经用户与 codex 评审收敛)
  - Stage A Phase 3 `schema_change` transition op(地基,已 shipped)
- Audit Log:
  - [2026-08-01_schema-evolution-diff-chain.audit.md](./2026-08-01_schema-evolution-diff-chain.audit.md)

## 1. Problem

schema 演化今天只有 additive 一类且无诊断:load 失败只报 digest 判决不报差异;删/改字段无机制(G6);checker 与未来 diff 门双规则源风险;自动化进程无法无类打开;规则与 schema 无联动分析。设计笔记已收敛全部机制,本 blueprint 是其实施单元。

## 2. Goals(= 设计笔记 §3 八点的交付物化)

1. **keyed diff 生成器**(entity_type/pred_id 键控;语义有序列表保序;repr/generated_at 不产生 transition)—— 单一权威,checker 重构为 "diff 生成器 + 政策过滤器";
2. **retired 注册表**(IR 顶层墓碑;投影排除/写入拒绝/pred_id 复用拒绝;墓碑 identity 只含 transition 序数/parent 锚 —— 自引用环裁定);
3. **携带 diff 的 mismatch 报错 + 沿链版本定位**("schema 的 git status");
4. **内省与渲染面**:`fg.schema.describe()` + CLI `schema` 子命令 + `classes_from_schema_ir()`(运行时对象)+ `python_source_from_schema_ir()`(源码文本)+ 报错内嵌差异实体的修正代码;
5. **迁移配方**(transition + 回填批 + retire 打包为可审计单元);
6. **rule-impact gate**(`fg.rules.structure` 谓词集 ∩ retired 集,非空拒绝/要求同步修正);
7. meander 侧配套(YAML retired carrier + asset→class→IR→asset round-trip 门)。

## 3. Non-goals

- identity field 退休/变更(identity-redesign 线,checker 显式拒绝);
- deprecated 二段式(v1 不纳入,需求出现再加);
- 存储形态(3b 域)、L2/Stage B。

## 4. Gates(核心)

- **round-trip digest 门**:render→compile→digest 逐字节相等(双渲染器共用);
- 类型反向映射从编译器正向映射派生(禁第二张表);
- diff 生成器与既有 additive checker 的行为等价 differential(重构不改判决);
- retire 全路径:投影排除/写拒绝/复用拒绝/规则交集拒绝,各有负向测试;
- mismatch 报错:过期类命中历史版本 → 版本定位 + 变更枚举的端到端用例。

## 5. 决策点(scope-freeze 前裁定)

- transition 序数精确定义(全局计数 vs tx_seq 引用);
- CLI 子命令名与 describe() 输出 shape;class-less `load_workspace(path)` 是否随反向生成一并转正;
- rename:new-field+retire vs alias;基数变更回填的胜出政策;
- meander 治理接线(谁有权 retire)—— meander 侧。

## 6. 量级

codex 估 14–22 工程日(diff/normalization 3–5、retired 3–4、SDK 适配 3–4、meander round-trip 3–5、测试迁移 2–4)+ 内省渲染面增量(§3.8,估 3–5)。
