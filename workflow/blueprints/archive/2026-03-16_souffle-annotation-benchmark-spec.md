# Benchmark Spec: Souffle-backed Annotation Kernel Spike

- 文档类型: 操作性规格文档（非决策文档）
- 关联蓝图: [2026-03-16_souffle-backed-annotation-kernel-spike.md](./2026-03-16_souffle-backed-annotation-kernel-spike.md)
- 创建日期: 2026-03-16
- 用途: 为三基线评估（PyReason / ProbLog / Souffle+prototype）提供完整可执行规格，包括数据生成、规则定义、期望输出、runner contract 和度量 harness。本文档是执行手册，不包含架构决策；架构决策见关联蓝图的第 5.11 节（go/no-go 标准）。

---

## Section 1: Workload A — Multi-hop Transitive Closure + Confidence Propagation

本 workload 在一张带置信度的有向图上计算多跳传递闭包，并按路径置信度代数（主实验：min-max）合并每对可达节点的最优置信度。

这是 Souffle 的强项场景（大规模递归闭包）与概率推理场景（置信度传播）的直接交叉点，用于测量 ProbLog 在递归闭包上的性能代价是否可接受。

### 1.1 Input Spec

**事实格式**

```
edge(source_id: str, target_id: str, confidence: float)
```

- `source_id` / `target_id`：命名规范为 `"e{i:03d}"`，如 `"e000"`, `"e001"`, ..., `"e999"`
- `confidence`：浮点数，范围 `(0.0, 1.0]`，精度保留 4 位小数

**生成参数（标准规模 1x）**

| 参数 | 值 |
| --- | --- |
| `N` 节点数 | `200` |
| `E` 边数（去重前目标） | `800` |
| `seed` | `42`（固定，决策点 D-1） |
| 置信度分布 | `uniform(0.3, 1.0)`，保留 4 位小数 |

**过程化生成方法**

```python
import random

def generate_workload_a(N=200, E=800, seed=42):
    random.seed(seed)
    seen = set()
    facts = []
    attempts = 0
    while len(facts) < E and attempts < E * 10:
        attempts += 1
        s = random.randint(0, N - 1)
        t = random.randint(0, N - 1)
        if s == t:
            continue
        key = (s, t)
        if key in seen:
            continue
        seen.add(key)
        c = round(random.uniform(0.3, 1.0), 4)
        facts.append((f"e{s:03d}", f"e{t:03d}", c))
    return facts
```

**示例事实（seed=42, N=200 时前 5 条）**

```
edge("e000", "e017", 0.8214)
edge("e000", "e045", 0.6503)
edge("e017", "e089", 0.9127)
edge("e045", "e089", 0.7341)
edge("e089", "e132", 0.5512)
```

注：以上为示意值，实际以生成器输出为准。运行前须固定 seed=42 并记录实际生成结果作为 golden input。

### 1.2 Rule Spec

以下规则以 Souffle/Datalog 语法写出，作为三个 baseline 的语义参照标准。

```datalog
// R1: 直接可达（1跳）
// 忽略置信度列，仅判定结构可达性
reachable(X, Y) :- edge(X, Y, _).

// R2: 传递闭包（递归多跳）
reachable(X, Z) :- reachable(X, Y), edge(Y, Z, _).

// R3: 单路径置信度
// 决策点 A-1 主实验：min-max 语义
// 路径置信度 = 路径上所有边的最小置信度（最弱环节语义）
path_confidence(X, Y, C) :- edge(X, Y, C).
path_confidence(X, Z, C) :-
    path_confidence(X, Y, C1),
    edge(Y, Z, C2),
    C = min(C1, C2).

// R4: 最优路径置信度（跨多条路径取最大）
best_confidence(X, Y, max(C)) :-
    path_confidence(X, Y, C).
```

**关于决策点 A-1（min-max vs. 乘法-max）**

主实验使用 min-max 语义，原因：
- 语义简单，三个 baseline 均可直接表达
- Souffle 的 semi-naive evaluation 对浮点 min/max 聚合支持稳定
- 避免乘法在深度递归时置信度趋近 0 导致精度问题

灵敏度分析实验（在主实验完成后单独运行）使用乘法-max 语义，将 R3 替换为：

```datalog
// R3 变体（灵敏度分析用，乘法-max）
path_confidence(X, Y, C) :- edge(X, Y, C).
path_confidence(X, Z, C) :-
    path_confidence(X, Y, C1),
    edge(Y, Z, C2),
    C = C1 * C2.
```

注意：ProbLog 的原生 possible-world 语义更接近乘法-max，灵敏度实验结果将直接反映 ProbLog 的语义优势是否显著。

### 1.3 Expected Output Spec

**Golden output JSON 格式**

```json
{
  "workload": "A",
  "query": "best_confidence",
  "algebra": "min_max",
  "seed": 42,
  "scale": "1x",
  "results": [
    {
      "source": "e000",
      "target": "e089",
      "confidence": 0.8214,
      "min_support_depth": 2
    },
    {
      "source": "e000",
      "target": "e132",
      "confidence": 0.5512,
      "min_support_depth": 3
    }
  ],
  "total_reachable_pairs": 0,
  "provenance_complete": true
}
```

`total_reachable_pairs` 由生成器实际计算后填入。`min_support_depth` 为从 source 到 target 的最短路径长度（跳数）。

**Golden output 生成方法**

使用独立的 Python 参考实现（BFS + 手动 min-max 合并），不依赖任何被测引擎。实现须在 spike 执行前冻结并记录版本，不得在测试过程中修改。

**正确性通过标准**

| 检查项 | 标准 |
| --- | --- |
| 候选集完整性（`(source, target)` 对的集合） | 0 个缺失，0 个多余 |
| 置信度数值精度 | 每个候选绝对误差 `< 0.001`，相对误差 `< 0.5%` |
| Provenance 非空 | 所有候选必须有至少一条支撑路径 |
| `provenance_complete` | 所有 support 链中引用的 edge-id 均在输入事实中存在，且构成合法有向路径 |

### 1.4 Runner Contract

三个 baseline 统一通过 `bench_runner.py` 入口调用：

```
python bench_runner.py \
    --workload A \
    --baseline [problog|pyreason|souffle_proto] \
    --input workload_a_N200_seed42.json \
    --output result_A_{baseline}.json \
    --measure-memory
```

**ProbLog baseline**

- 将每条 `edge(X, Y, C)` 事实转为 ProbLog 带概率事实：`C::edge(X, Y).`
- R1/R2/R3/R4 规则以 ProbLog 子句形式加载
- 查询：`query(best_confidence(X, Y, C))`
- ProbLog 的 `max` 聚合通过 meta-interpreter 或 post-processing 实现（若 ProbLog 不支持原生 max 聚合，须在 `unsupported_features` 中记录并在 Python 层处理；此处理不影响评分，仅须如实记录）

**PyReason baseline**

- 将每条 `edge(X, Y, C)` 转为 PyReason 的图边，置信度映射为退化区间 `[C, C]`（标量退化形式，满足 B-2 类似的公平性要求）
- R1/R2 的传递闭包通过 PyReason rule firing 实现
- R3/R4 的 min-max 置信度合并通过 PyReason annotation merge 函数实现
- 从 PyReason 结果图提取可达节点对及其 annotation 上界作为 `best_confidence`
- 若 PyReason 的 annotation merge 不支持 min-max，须在 `unsupported_features` 中记录具体原因

**Souffle + prototype baseline**

- Souffle 执行 R1/R2（纯结构闭包），输出 `reachable(X, Y)` 关系
- annotation kernel（Python prototype）接收 Souffle 输出的可达对列表 + 原始 `edge` 置信度数据
- Python prototype 枚举所有支撑路径，计算每条路径的 min 置信度，取跨路径的 max，输出 `best_confidence`
- 此流程是单向 pipeline（Souffle -> kernel），无需回写；若发现需要多轮迭代，须在结果中记录并触发 Gate 4 评估

**统一归一化输出 JSON 格式**

所有三个 baseline 均须输出以下格式，供 harness 比较：

```json
{
  "workload": "A",
  "baseline": "<problog|pyreason|souffle_proto>",
  "algebra": "min_max",
  "wall_clock_seconds": 0.0,
  "peak_memory_mb": 0.0,
  "results": [
    {"source": "<str>", "target": "<str>", "confidence": 0.0}
  ],
  "provenance_entries": [
    {
      "candidate": {"source": "<str>", "target": "<str>"},
      "support_path": ["<edge: src->tgt>"]
    }
  ],
  "unsupported_features": [],
  "notes": ""
}
```

### 1.5 Measurement Harness

**Wall-clock 计时定义**

- 计时**开始**：引擎初始化完成、所有输入事实已加载到引擎内存、第一次规则求值触发的时刻
- 计时**结束**：最后一条 `best_confidence` 结果写入 Python 内存的时刻
- **不计入**：磁盘 I/O（读取输入 JSON 文件）、结果序列化（写出输出 JSON 文件）、Python 层 post-processing（如排序、格式转换）

**内存采样**

- 首选：Python `tracemalloc`，在计时开始前 `start()`，计时结束后 `get_traced_memory()` 取峰值
- 备选（进程级）：`/usr/bin/time -v`，记录 `Maximum resident set size`
- 两种方式的结果均须记录

**重复次数与中位数**

- 每个 baseline 每个规模运行 5 次
- 丢弃第一次（引擎/JIT 预热）
- 取后 4 次的中位数作为最终报告值
- 同时记录最大值和最小值用于方差分析

**Provenance 验证方法**

对输出的每条 `provenance_entries`：
1. 验证 `support_path` 中的每一步 `src->tgt` 均对应输入事实中的一条 `edge`
2. 验证路径中相邻步骤首尾相连（构成合法有向路径）
3. 验证路径的起点与 `candidate.source` 一致，终点与 `candidate.target` 一致
4. 若任一验证失败，标记该候选的 `provenance_complete = false`，并记录失败原因

---

## Section 2: Workload B — Bounded Timestep State Propagation

本 workload 在 100 个实体、20 个离散时间步、15 条转移规则下传播实体状态，输出 t=20 时所有实体的最终状态及每次状态变化的 provenance 链。

这是 PyReason 的天然优势场景（原生时间步 API），同时也是测试"时间作为推理语义"与"时间作为数据参数"两种编码策略之间表达成本差异的关键 workload。

### 2.1 Input Spec

**事实格式**

```
// 初始状态（仅 t=0 时刻，t=1..20 的状态由规则推导）
state(entity_id: str, timestep: int, status: str)

// 静态属性（不随时间变化，用于规则条件匹配）
property(entity_id: str, prop_name: str, prop_value: str)
```

- `entity_id`：命名规范为 `"ent{i:03d}"`，如 `"ent000"`, `"ent001"`, ..., `"ent099"`
- `timestep`：整数，范围 `0..20`（输入中仅包含 t=0）
- `status`：枚举，取值集合 `{"active", "inactive", "degraded"}`（决策点 B-3）
- `prop_name`：本 workload 中仅使用 `"class"`
- `prop_value`：`"A"`, `"B"`, `"C"` 之一

**生成参数（标准规模 1x）**

| 参数 | 值 |
| --- | --- |
| `N_entities` | `100` |
| `T_max` | `20` |
| `N_rules` | `15`（从规则模板池采样，见 2.2 节） |
| `seed` | `42`（固定，决策点 D-1） |
| 初始状态分布 | `70% active, 20% inactive, 10% degraded` |
| 属性覆盖率 | 60% 实体分配 `property("class", ...)` |
| class 分布 | 三类均匀 |

**过程化生成方法**

```python
import random

def generate_workload_b(N=100, T_max=20, seed=42):
    random.seed(seed)
    state_dist = ["active"] * 70 + ["inactive"] * 20 + ["degraded"] * 10
    facts_state = []
    facts_property = []
    for i in range(N):
        eid = f"ent{i:03d}"
        status = random.choice(state_dist)
        facts_state.append((eid, 0, status))
        if random.random() < 0.6:
            cls = random.choice(["A", "B", "C"])
            facts_property.append((eid, "class", cls))
    return facts_state, facts_property
```

**示例事实（seed=42, N=100 时前 5 条）**

```
state("ent000", 0, "active")
state("ent001", 0, "inactive")
state("ent002", 0, "active")
state("ent003", 0, "degraded")
state("ent004", 0, "active")

property("ent000", "class", "A")
property("ent002", "class", "B")
property("ent004", "class", "C")
```

注：以上为示意值，实际以生成器输出为准。

### 2.2 Rule Spec

本 workload 共定义 3 种规则模板。生成的 15 条规则从模板 T2 和 T3 中采样（参数随机化），T1 为固定规则、不参与采样。

**决策点 B-1：不使用 NAF**

原始设计中，T1（状态持续规则）使用 `\+transition_fired(E, T)` 的 negation-as-failure（NAF）来表达"只有在没有转移触发时才保持状态"。经确认，本 workload 去除 NAF，原因如下：

- Souffle 支持 stratified negation，但需要额外的辅助谓词
- PyReason 的 open-world 语义与 NAF 的 closed-world 假设存在根本冲突，会导致三个 baseline 的语义不等价，无法公平比较
- 替代方案：所有规则共同触发，多条规则对同一实体同一时间步给出不同 status 时，以最后定义的规则优先（或显式指定优先级顺序）

**T1：状态无条件持续（无 NAF）**

```datalog
// T1: 若本时间步状态为 S，且没有被 T2/T3 覆盖，则下一步继续为 S
// 实现方式：T1 作为默认规则，T2/T3 的优先级高于 T1
// 在 Souffle 中：T1 先触发，T2/T3 覆盖写入；最终结果取 T2/T3 结果，无 T2/T3 匹配时保留 T1
state(E, T+1, S) :- state(E, T, S), T < 20.
```

注：此规则在 ProbLog 中通过 ground instantiation 实现（每个 `T` 展开一条规则）；在 PyReason 中通过 default persistence 行为实现。

**T2：单实体降级（模板，示例 2 条）**

```datalog
// T2a: class=A 的 active 实体在下一步变为 degraded
state(E, T+1, "degraded") :-
    state(E, T, "active"),
    property(E, "class", "A"),
    T < 20.

// T2b: class=C 的 inactive 实体在下一步变为 active（修复语义）
state(E, T+1, "active") :-
    state(E, T, "inactive"),
    property(E, "class", "C"),
    T < 20.
```

**T3：双实体交互恢复（模板，示例 1 条）**

```datalog
// T3a: class=B 的 active 实体可以"激活"同时间步 degraded 的其他实体
state(E1, T+1, "active") :-
    state(E1, T, "degraded"),
    state(E2, T, "active"),
    property(E2, "class", "B"),
    E1 != E2,
    T < 20.
```

生成 15 条规则时，从 T2/T3 模板中采样，随机化 `class` 条件参数和 `status` 转换目标，同时保证：
- 不产生直接矛盾（同一模板的同一 class 条件不同时触发两种不同的转换）
- 规则集在结构上可被 Souffle stratified evaluation 处理（无递归否定）

### 2.3 Expected Output Spec

**Golden output JSON 格式**

```json
{
  "workload": "B",
  "query": "final_state_at_T20",
  "seed": 42,
  "scale": "1x",
  "T_max": 20,
  "results": [
    {
      "entity": "ent000",
      "final_status": "active",
      "first_transition_at": null,
      "transition_count": 0
    },
    {
      "entity": "ent001",
      "final_status": "degraded",
      "first_transition_at": 3,
      "transition_count": 2
    }
  ],
  "state_history_summary": {
    "ent000": ["active", "active", "active"],
    "ent001": ["inactive", "inactive", "inactive", "degraded", "active", "degraded"]
  },
  "provenance_entries": [
    {
      "entity": "ent001",
      "timestep": 3,
      "new_status": "degraded",
      "trigger_rule": "T2a",
      "trigger_entities": ["ent001"]
    },
    {
      "entity": "ent001",
      "timestep": 4,
      "new_status": "active",
      "trigger_rule": "T3a",
      "trigger_entities": ["ent001", "ent027"]
    }
  ]
}
```

注：`state_history_summary` 对每个实体只记录状态**发生变化**的时间步，连续相同状态用最后一次出现的时间步表示即可；完整历史须由 harness 从 golden output 重建。

**正确性通过标准**

| 检查项 | 标准 |
| --- | --- |
| t=20 时所有实体最终状态 | 与 golden output 完全一致，0 个不匹配 |
| 首次状态变化时刻（`first_transition_at`） | 精确匹配 |
| Provenance 覆盖率 | 每次状态变化事件必须有 `trigger_rule` 和 `trigger_entities`，且 `trigger_entities` 均在输入实体集中 |
| 状态变化总次数 | 各实体 `transition_count` 与 golden output 完全一致 |

Golden output 由 Python 参考实现（逐步模拟，按规则优先级顺序直接应用）生成。

### 2.4 Runner Contract

```
python bench_runner.py \
    --workload B \
    --baseline [problog|pyreason|souffle_proto] \
    --input workload_b_N100_T20_seed42.json \
    --output result_B_{baseline}.json \
    --measure-memory
```

**ProbLog baseline**

- 将时间步展开为 ground facts：将所有规则实例化到每个 `T`（0..19），生成 `T_max * N_rules` 条 ground 规则
- `state("ent001", 0, "active").` 形式加载初始事实，置信度为 `1.0`（确定性）
- 规则转为 ProbLog 子句（无概率标注）
- 查询 `state(E, 20, S)` 获取最终状态
- 在 `unsupported_features` 中记录 `["native_temporal_semantics"]`，说明时间步通过手动展开而非原生时序 API 实现
- 在 measurement harness 中单独记录规则展开时间（展开生成 ground 规则的 Python 时间，不计入引擎 wall-clock）

**PyReason baseline（决策点 B-2）**

- 使用 PyReason 原生时间步 API，无需手动展开规则
- 将初始状态加载为 t=0 的图节点 annotation
- 将 T2/T3 规则转为 PyReason rule graph 形式，指定 `T_max=20`
- 执行到 `T_max`，提取 t=20 的节点状态 annotation
- 在归一化输出中标注 `native_temporal_advantage: true`，明确此项结果反映了 PyReason 原生时间步能力，不代表三方均等条件下的公平比较
- 提取每个节点每个时间步的状态变化记录，填写 `provenance_entries`

**Souffle + prototype baseline**

- Souffle 直接执行含时间步参数的 Datalog 规则（T 作为 relation 列）
- annotation kernel 对本 workload 不承担语义处理（时间步传播完全由 Souffle 处理）
- 这是一个重要发现信号：**如果 Souffle 原生 Datalog 已可完整表达有界时间步传播，则 annotation kernel 在此场景下的附加价值为零**，应在结果 `notes` 字段中记录 `"annotation_kernel_noop: true"`
- 从 Souffle 输出的 `state(E, 20, S)` relation 提取最终状态

**统一归一化输出 JSON 格式**

```json
{
  "workload": "B",
  "baseline": "<problog|pyreason|souffle_proto>",
  "T_max": 20,
  "wall_clock_seconds": 0.0,
  "rule_unrolling_seconds": 0.0,
  "peak_memory_mb": 0.0,
  "results": [
    {"entity": "<str>", "final_status": "<str>", "transition_count": 0}
  ],
  "provenance_entries": [
    {
      "entity": "<str>",
      "timestep": 0,
      "new_status": "<str>",
      "trigger_rule": "<str>",
      "trigger_entities": ["<str>"]
    }
  ],
  "unsupported_features": [],
  "native_temporal_advantage": false,
  "annotation_kernel_noop": false,
  "notes": ""
}
```

### 2.5 Measurement Harness

与 Workload A 的 harness 定义相同，额外增加以下记录项：

**ProbLog 专用**

- `rule_unrolling_seconds`：将规则模板实例化到每个时间步的 Python 处理时间，单独计时，不计入引擎 wall-clock
- 须报告：展开后的 ground 规则总条数 = `T_max * N_rules`

**全 baseline 共用附加指标**

- `state_change_event_count`：所有实体在 t=1..20 期间发生状态变化的总事件数（用于验证 provenance 覆盖率）
- Provenance 覆盖率 = `有 trigger_rule 记录的状态变化事件数 / state_change_event_count`（目标：三个 baseline 均 >= 100%；若达不到 100%，记录缺失的时间步和实体）

---

## Section 3: Workload C — Deterministic Rules + Probabilistic Evidence Candidate Ranking

本 workload 从 1000 条确定性结构事实和 200 条带置信度证据事实中推导候选集，annotation kernel 执行置信度聚合（主实验：max），harness 统一执行 Top-K 排名后输出 Top-50 候选及其 provenance。

这是 audit/provenance 一致性测试的核心场景，也是最接近 ESA 场景中"规则推理 + 追溯链"需求的 workload。

### 3.1 Input Spec

**事实格式**

```
// 确定性结构事实（无置信度，语义上 confidence=1.0）
struct_fact(subject_id: str, relation: str, object_id: str)

// 带置信度的证据事实（观测或 LLM 抽取结果）
evidence(claim_id: str, subject_id: str, relation: str, object_id: str, confidence: float, source: str)
```

- `subject_id` / `object_id`：`"ent{i:03d}"`（与 Workload B 共享实体命名池）
- `claim_id`：`"claim{i:04d}"`
- `confidence`：浮点数，范围 `[0.4, 0.99]`，精度 4 位小数
- `source`：枚举，取值集合 `{"sensor", "llm_extraction", "manual"}`
- `relation`：枚举，取值集合（共 8 种）：
  - `"reports_to"`, `"is_component_of"`, `"depends_on"`, `"monitors"`, `"triggers"`, `"overrides"`, `"supports"`, `"conflicts_with"`

**生成参数（标准规模 1x）**

| 参数 | 值 |
| --- | --- |
| `N_struct_facts` | `1000` |
| `N_evidence_facts` | `200` |
| `N_entities` | `100`（与 Workload B 相同实体池） |
| `N_relations` | `8`（见上方列表） |
| `seed` | `42`（固定，决策点 D-1） |
| 置信度分布 | `uniform(0.4, 0.99)`，保留 4 位小数 |
| source 分布 | `sensor: 40%, llm_extraction: 40%, manual: 20%` |

**过程化生成方法**

```python
import random

def generate_workload_c(N_struct=1000, N_evidence=200, N_entities=100, seed=42):
    random.seed(seed)
    relations = [
        "reports_to", "is_component_of", "depends_on", "monitors",
        "triggers", "overrides", "supports", "conflicts_with"
    ]
    sources = ["sensor"] * 40 + ["llm_extraction"] * 40 + ["manual"] * 20

    struct_facts = []
    seen_struct = set()
    attempts = 0
    while len(struct_facts) < N_struct and attempts < N_struct * 10:
        attempts += 1
        s = f"ent{random.randint(0, N_entities-1):03d}"
        o = f"ent{random.randint(0, N_entities-1):03d}"
        r = random.choice(relations)
        if s == o:
            continue
        key = (s, r, o)
        if key in seen_struct:
            continue
        seen_struct.add(key)
        struct_facts.append((s, r, o))

    evidence_facts = []
    for i in range(N_evidence):
        s = f"ent{random.randint(0, N_entities-1):03d}"
        o = f"ent{random.randint(0, N_entities-1):03d}"
        if s == o:
            o = f"ent{(random.randint(0, N_entities-1) + 1) % N_entities:03d}"
        r = random.choice(relations)
        c = round(random.uniform(0.4, 0.99), 4)
        src = random.choice(sources)
        evidence_facts.append((f"claim{i:04d}", s, r, o, c, src))

    return struct_facts, evidence_facts
```

**示例事实（seed=42 时前 5 条）**

```
struct_fact("ent012", "depends_on", "ent047")
struct_fact("ent033", "monitors", "ent091")
struct_fact("ent047", "is_component_of", "ent005")
struct_fact("ent005", "depends_on", "ent078")
struct_fact("ent091", "reports_to", "ent033")

evidence("claim0000", "ent042", "depends_on", "ent017", 0.9900, "sensor")
evidence("claim0001", "ent007", "supports", "ent055", 0.8721, "llm_extraction")
evidence("claim0002", "ent042", "depends_on", "ent017", 0.8500, "llm_extraction")
```

注：以上为示意值，实际以生成器输出为准。

### 3.2 Rule Spec

**决策点 C-2：Top-K 排名由 harness 统一执行（公平性原则）**

R5（Top-K 排名）从引擎规则中移除，改由 benchmark harness 统一执行。所有三个 baseline 仅须输出 `candidate(S, R, O, C)` 形式的原始候选集（含置信度），harness 统一执行 max 聚合和 Top-K 排序。

这是一个公平性原则，确保排名逻辑不成为任何单一引擎的优势或劣势来源。

```datalog
// R1: 直接候选（来自证据事实）
candidate(S, R, O, C) :- evidence(_, S, R, O, C, _).

// R2: 结构推导：间接依赖（两跳 depends_on）
derived_relation(S, "indirect_dependency", O) :-
    struct_fact(S, "depends_on", M),
    struct_fact(M, "depends_on", O).

// R3: 结构推导：可达监控（monitors + is_component_of）
derived_relation(S, "reachable_monitor", O) :-
    struct_fact(S, "monitors", M),
    struct_fact(M, "is_component_of", O).

// R4: 结构候选（确定性推导，置信度=1.0）
candidate(S, R, O, 1.0) :- derived_relation(S, R, O).

// R5（已移至 harness）：
// best_candidate(S, R, O, max(C)) :- candidate(S, R, O, C).
// ranked_candidate: 由 harness 统一按 best_confidence 降序排列，取 Top-50
```

**决策点 C-1：max 聚合**

同一 `(S, R, O)` 可能有多条 `candidate` 记录（来自多条证据），harness 执行：
```python
best_confidence = max(C for (S, R, O, C) in candidates if S==s and R==r and O==o)
```

**灵敏度分析**

在主实验（max 聚合）完成后单独运行 Noisy-OR 灵敏度分析：
```python
# Noisy-OR: 1 - product(1 - C_i) for all evidence for (S, R, O)
from functools import reduce
import operator
best_confidence_noisy_or = 1.0 - reduce(operator.mul, [(1.0 - c) for c in evidence_confidences], 1.0)
```

Noisy-OR 实验仅在 harness 层修改聚合函数，引擎规则不变。

### 3.3 Expected Output Spec

**Golden output JSON 格式**

```json
{
  "workload": "C",
  "query": "ranked_candidate",
  "aggregation": "max",
  "top_k": 50,
  "seed": 42,
  "scale": "1x",
  "results": [
    {
      "rank": 1,
      "subject": "ent042",
      "relation": "depends_on",
      "object": "ent017",
      "confidence": 0.9900,
      "source_type": "sensor",
      "provenance": {
        "direct_evidence": ["claim0000"],
        "struct_support": []
      }
    },
    {
      "rank": 2,
      "subject": "ent007",
      "relation": "indirect_dependency",
      "object": "ent055",
      "confidence": 1.0,
      "source_type": "derived",
      "provenance": {
        "direct_evidence": [],
        "struct_support": [
          "ent007 -[depends_on]-> ent023",
          "ent023 -[depends_on]-> ent055"
        ]
      }
    }
  ]
}
```

**正确性通过标准**

| 检查项 | 标准 |
| --- | --- |
| Top-50 候选集（`(subject, relation, object)` 三元组集合） | 与 golden output 完全一致，0 个缺失，0 个多余 |
| 置信度数值精度 | 每个候选绝对误差 `< 0.001` |
| Provenance 非空 | Top-50 中每个候选须至少有一条 `direct_evidence` 或一条 `struct_support` 链 |
| `provenance_complete_rate` | `有完整 provenance 的候选数 / 50 >= 95%`（即最多允许 2 个候选 provenance 不完整） |
| Provenance 合法性 | `direct_evidence` 中的每个 `claim_id` 须在输入 `evidence` 事实中存在；`struct_support` 中的每一步须在输入 `struct_fact` 中存在 |

Golden output 由 Python 参考实现（直接应用 R1-R4 + max 聚合 + Top-50 排序）生成。

**Provenance gap 类型定义**

若某候选的 provenance 不完整，须记录缺失原因的类型：

- `internal_engine_node`：provenance 链包含引擎内部节点（如 ProbLog 的 internal proof node），无法映射回输入事实
- `missing_claim_id`：`direct_evidence` 中引用了不存在于输入的 `claim_id`
- `broken_struct_chain`：`struct_support` 链中存在不连续的 struct_fact 引用

### 3.4 Runner Contract

```
python bench_runner.py \
    --workload C \
    --baseline [problog|pyreason|souffle_proto] \
    --input workload_c_N1200_seed42.json \
    --output result_C_{baseline}.json \
    --measure-memory
```

所有三个 baseline **仅执行 R1-R4**，不执行 Top-K 排名。Harness 统一收集 `candidate(S, R, O, C)` 原始输出，执行 max 聚合后排序取 Top-50。

**ProbLog baseline**

- `struct_fact` 以 `1.0::struct_fact(S, R, O).` 形式加载（确定性，置信度为 1.0）
- `evidence` 以 `C::evidence(ClaimId, S, R, O, Src).` 形式加载
- R1-R4 规则以 ProbLog 子句加载
- 查询 `candidate(S, R, O, C)`，获取所有候选及其置信度
- 注意：ProbLog 可能对同一 `(S, R, O)` 产生多个置信度值（来自 possible-world 展开），须以每个 `(S, R, O)` 的最高概率值报告；具体处理方式须在 `notes` 字段说明

**PyReason baseline**

- `struct_fact` 加载为图边，annotation 为 `[1.0, 1.0]`（确定性退化区间）
- `evidence` 加载为图边，annotation 为 `[C, C]`（标量退化区间）
- R2/R3 的结构推导通过 PyReason rule firing 实现
- R1/R4 的候选生成通过 PyReason annotation 传播实现
- 从 PyReason 结果图提取所有 `candidate` 关系及其 annotation 上界

**Souffle + prototype baseline**

- Souffle 执行 R1-R3（结构推导，生成 `derived_relation` 和 `reachable` 骨架）以及 R4（生成置信度为 1.0 的结构候选）
- annotation kernel（Python prototype）执行 R1 的证据候选生成（从 `evidence` 事实中提取），并与 Souffle 输出的结构候选合并
- annotation kernel 不承担 max 聚合（max 聚合由 harness 执行，符合 C-2 原则）
- 输出所有原始 `candidate(S, R, O, C)` 记录，包含来源标记（`direct_evidence` 或 `derived`）

**统一归一化输出 JSON 格式**

```json
{
  "workload": "C",
  "baseline": "<problog|pyreason|souffle_proto>",
  "aggregation": "max",
  "wall_clock_seconds": 0.0,
  "peak_memory_mb": 0.0,
  "raw_candidates": [
    {
      "subject": "<str>",
      "relation": "<str>",
      "object": "<str>",
      "confidence": 0.0,
      "source_type": "<direct_evidence|derived>",
      "claim_id": "<str|null>"
    }
  ],
  "provenance_entries": [
    {
      "candidate": {"subject": "<str>", "relation": "<str>", "object": "<str>"},
      "direct_evidence": ["<claim_id>"],
      "struct_support": ["<str>"]
    }
  ],
  "unsupported_features": [],
  "notes": ""
}
```

注：`raw_candidates` 是未经 max 聚合和排名的原始输出，由 harness 处理后生成最终 Top-50 结果。

### 3.5 Measurement Harness

与 Workload A 的 harness 定义相同，额外增加以下记录项：

**Provenance 完整率**

```
provenance_complete_rate = (Top-50 中有完整 provenance 的候选数) / 50
```

目标：三个 baseline 均 >= 95%（即最多 2 个候选 provenance 不完整）。

**Provenance gap 统计**

若存在 provenance 不完整的候选，须按 gap 类型分类统计：
- `internal_engine_node` 数量
- `missing_claim_id` 数量
- `broken_struct_chain` 数量

此统计直接影响 Gate 3（Souffle + prototype 的 provenance completeness 是否严格优于其他两个 baseline）的评估。

---

## Section 4: Sensitivity Analysis Experiments

以下灵敏度分析实验在主实验（三个 workload 的 1x 规模主实验）全部完成后运行。灵敏度分析的目的是检验主实验结论是否对特定 algebra 选择敏感。

### 4.1 Workload A Sensitivity: 乘法-max 置信度代数

**触发条件**：主实验完成且 Workload A 的三基线结果已记录。

**变更内容**：仅修改 R3 规则（路径置信度从 min 改为乘积）：

```datalog
// R3 变体（乘法-max）
path_confidence(X, Z, C) :-
    path_confidence(X, Y, C1),
    edge(Y, Z, C2),
    C = C1 * C2.
```

**输出格式**：与主实验相同，在结果 JSON 中标注 `"algebra": "multiplicative_max"`。

**评估目标**

- 记录三个 baseline 在乘法-max 下的 correctness delta（与 min-max 主实验结果的差异量）
- 记录 ProbLog 在乘法-max 下是否获得 correctness 提升（因为 ProbLog 的 possible-world 语义更接近乘法）
- 若乘法-max 下 ProbLog 正确率显著高于 min-max，说明 ProbLog 的语义优势在 min-max 主实验中被低估，需要在 go/no-go 评估中加权考虑

### 4.2 Workload C Sensitivity: Noisy-OR 聚合

**触发条件**：主实验完成且 Workload C 的三基线结果已记录。

**变更内容**：仅修改 harness 的聚合函数（从 max 改为 Noisy-OR），引擎规则不变：

```python
# Noisy-OR 聚合（在 harness 层）
def noisy_or(confidences):
    result = 1.0
    for c in confidences:
        result *= (1.0 - c)
    return 1.0 - result
```

**输出格式**：在结果 JSON 中标注 `"aggregation": "noisy_or"`。

**评估目标**

- 记录 Top-50 集合的稳定性（与 max 聚合下 Top-50 的重叠率）
- 记录候选排名变化（尤其是多条证据支持的候选是否在 Noisy-OR 下排名上升）
- 若 Noisy-OR 下 Top-50 集合与 max 下差异 < 10%，说明聚合方式对排名结论影响较小；若差异 >= 20%，说明聚合方式选择是一个重要决策点，需要在后续 prototype 中明确

---

## Section 5: Scale Variants

以下规模变体用于在主实验（1x 规模）结果不足以支撑 go/no-go 决策时补充执行。若 1x 规模结果已可清晰判断（满足或不满足 Gate 阈值），则不强制运行 2x 和 5x。

| Workload | 参数 | 1x（标准） | 2x | 5x |
| --- | --- | --- | --- | --- |
| `A` | 节点数 `N` | `200` | `400` | `1000` |
| `A` | 边数 `E` | `~800` | `~1600` | `~4000` |
| `B` | 实体数 `N_entities` | `100` | `200` | `500` |
| `B` | 时间步 `T_max` | `20` | `20`（不变） | `20`（不变） |
| `B` | 规则数 `N_rules` | `15` | `15`（不变） | `15`（不变） |
| `C` | 确定性事实 `N_struct` | `1000` | `2000` | `5000` |
| `C` | 证据事实 `N_evidence` | `200` | `400` | `1000` |
| `C` | Top-K | `50` | `50`（不变） | `50`（不变） |

**关于 Workload B 的规模变体说明**

Workload B 的规模瓶颈主要来自实体数量（影响 T3 类双实体交互规则的 grounding 规模），而不是时间步数量。时间步和规则数在 2x/5x 时保持不变，以确保性能变化主要来自实体数量这一单一变量。

**关于种子复用**

所有规模变体均使用相同的 `seed=42`。生成器须保证不同规模下的数据是"扩展相容"的（即 1x 的事实集是 2x 的事实集的子集），以确保规模扩大时结论具有单调性。
