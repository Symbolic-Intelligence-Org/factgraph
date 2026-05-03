# 用户原始 Brainstorm(2026-05-03 chat 提供)

- **Status:** working / preserved verbatim
- **Source:** 用户在 2026-05-03 session 内通过 chat 提供,作为 redesign 的设计灵感来源
- **Authority:** non-authoritative;不是当前 implementation truth,也不是 API contract
- **Relationship to other materials:**
  - 内容与 `10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md` 高度同构(brainstrom 是源头思想,该 doc 是后期工作笔记)
  - 与 `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md`(B'' 工作笔记)是同一思想线的两个时点

---

## 原文(中文 verbatim)

如果到最开始的想法, 我想的一个"直觉"应该是模块化的理念, 试想,当前设计有两层,一层 layer1 是简单定义的语法糖,底层运作的是第二层 layer2 更可靠但写法复杂, 在 layer2 层我们可以把 rule 和 evidence 看作由一种"最小模块"拼装成的"树".

### Rule 层

对于 rule, 每个条件都是同类型的对象,可以看作一个最小模块,包含 id,类型,参数等,其中 id 并不需要像定义事实那样严格定义,可以自动生成,但显示定义 id 的一个功能在于同 id 且完全相同的条件会被看作同一条件,当发起变化时它们总是同时改变。

**问题:**
- rule 的条件可以在外边定义,然后再在定义 rule 时关联对应项吗? 这种情况应该显式定义 id 吗?
- 是否存在无法被这个最小模块表达的条件句? 如果有是应该主动放弃还是增加多种模块类型?
- 我们应该设定的语法边界是什么? 尽可能功能强大, 但又不会给自己挖坑, 出现一些边缘报错场景.

### Evidence 层

evidence 本质和 rule 类似,都是这种最小模块组成,rule 的目标是构建可运行代码,而 evidence 则是从结果(推理引擎对应的 evidence 功能)中复现推理过程,使用包含推理状态的最小模块,和 rule 中的最小模块对应,不过它的集合可能是 rule 模块集合的子集,例如 problog 不会严格遍历所有节点,自然这些节点也不会被评估, 不过这是符合直觉的。

每个这样的模块包含推理中的状态,可能用 true false 来表示是否成立(如果不是判断, 而是包含一些未知项的, 则根据是否存在项来判断),unknown 来表示没有遍历到, 而用户可以针对它们进行一些操作, 例如去除某些条件, 更改某些条件, 增加某些条件, 等操作, 然后进行重新评估, 比对变化前后, 和结论的变化.

基于我对推理引擎的逻辑不够清楚的情况下, 我们似乎做出了错误的判断, 误以为部分重计算机制是可行的, 我认为这是一个误区, 实际上我们不能指望从 evidence 中重新唤起"带有余温的逻辑电路", 因为大多数推理引擎并没有提供支持. 对此我想到一种可能更"不专业"的方法, 它可以称作 **"replay-based evidence analysis 或 counterfactual proof analysis"**, 简单来讲, 就是把这类条件的更改, 禁止, 反例等一系列设想的"evidence tree 可以支持的操作", 迁移到 Rule 层: 在 rule 层, 我们可以针对 rule 本身进行这类"修改"操作, 这些被改变的 rule 在执行(evaluate)后获得的不同 evidence tree 可以进行相互比对, 和对每个模块进行分析.

这表面上看 evidence 重新回到了最初的"花瓶"状态, 仅供展示而不能操作, 但事实由于它仍然保留有这些最小模块的结构并且是可以交互的对象, 我们可以尝试通过这些模块实现一些功能, 例如和原 rule 或者其他的 rule 进行比对, 这些通过被改变的 rule 得到的 evidence tree 就相当于原 rule 的 evidence tree 的 diff, 此外我们还可以给 rule 增加一些例如 **why-not provenance** 的机制, 进一步扩展这种比对的功能.

我在想象这些功能的时候, 实际上在想象一些实际的图形操作界面, 例如一个 evidence tree 是一系例可以交互的 box 组成的树, 通过不同颜色表示每个模块的推理结果(true,false 或有确切的值),

最终我们想要达成的是一个**可以"说话"的 evidence tree**, 它不仅可以告诉用户, 什么地方的条件导致整体不成立/成立, 也可以对比相邻

鉴于 evidence tree 可能会很大, 存放完整 evidence tree 将会是成本巨大的事情,因此可以选择存"**可重放证明的最小 carrier**"(ID,version,…),需要解释时再计算 tree(只需要推理一"条"数据), 即把成本从"存储"转移到"解释时计算".

关于可以操作的 rule, 我想到一些场景下可能需要"**临时替换 head 参数**", 例如我们想测试一些事实是否符合特定规则, 当前没法直接把 head 改成事实的参数进行 true/false 的比对(当前不能优雅地把 rule head/select 直接替换成实际值作为 boolean API), 它的必要性在于, 在我们实装新的 evidence tree 机制后, 对特定的 evidence tree 进行 replay 的功能只计算"一条"数据, 这是一个所有参数已知的 boolean 计算场景.

**问:** 这些最小模块应该表达为在对应分支的队列中吗?

---

## 用户在 chat 中追加的补充(2026-05-03)

- "interactive UI 只是作为设计参考, 为将来有 UI 的情况提前准备, 不是我们要实现的目标"
- 实际明确的用户需求一条:**"结果不合要求可以重新改变条件、facts,重新得到新的合规的结果"**
- 解释作"上述的内容仅作为参考, 在你掌握新的内容后, 我们可以再针对具体的设计理念和方法展开讨论"

---

## Brainstorm 的 5 条核心命题(由我从原文抽取,**非用户原话**,仅为后续对照方便)

1. **Rule + Evidence 都由"最小模块"组成**;evidence 模块集合是 rule 模块集合的子集
2. **不重计算 evidence**(承认引擎不支持"余温电路"),而是把可操作的"什么 if"推到 rule 层
3. **不能存完整 evidence tree**,要存最小 carrier,需要时再 recompute
4. **要支持 boolean check** 一个具体 binding 是否符合规则
5. **要支持 why-not** 之类的反向 provenance 比对

这 5 条对应到 v0.1.x design probe 的实现结果:
- 命题 1:✅ v0.1.2 ConditionModule(rule 模块化);❌ evidence 一侧没等价对象化(只通过 `support_key_to_module_id` 反向定位)
- 命题 2:✅ v0.1.1+v0.1.3 通过 `replay_with_patch` 实现 counterfactual replay
- 命题 3:❌ 完全没做(evidence 仍按"完整存"的成本模型;`audit JSONL replay persistence` deferred)
- 命题 4:❌ 完全没做(没有 Check operation;evaluate 只返 candidate set)
- 命题 5:❌ 完全没做(没有 why-not / lazy carrier / candidate universe)

5 条里 v0.1.x design probe 只完成了 1 个完整 + 1 个部分。**redesign 起点应该把 5 条都纳入考虑,不要重复"只做 rule 侧"的偏置**。
