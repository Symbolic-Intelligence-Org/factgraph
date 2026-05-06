# Evidence Pipeline Tutorial(临时参考稿)

> 仅供个人参考,不入工作流。完整覆盖 v0.1 evidence 设计链路 6 层 + 端到端示例。

---

## 1. 大局观

FactPy v0.1 的 "evidence pipeline" 是从 **用户写入 fact** 到 **capability 给出答案** 的完整数据流。整体分 6 层,自底向上:

```
Layer 6   Capability Lines              Check / Diagnose / Fact Overlay / Why-not / (Frontier)
            ↑    capability 调
Layer 5   Engine Adapters               souffle / problog / pyreason
            ↑                            → CandidateSet + SupportArtifact / ProvenanceEnvelope
Layer 4   Native Evaluator              evaluate_native_where + body_ir + atom evaluators
            ↑    读
Layer 3   Projection                    project_view_facts / _with_witness
            ↑                            → ProjectedFact(asrt_id, fact_tuple)
Layer 2   Ledger                        set_field → asrt_id;追加日志不可变
            ↑    写
Layer 1   Schema & Entity               Entity / Identity / Field;compile_schema_from_classes
```

v0.1 已 shipped 的 5 条 capability line 统一回答这 5 个问题:

| # | Canonical question | 能力 |
|---|---|---|
| Q1 | Does this binding pass? | Check |
| Q2 | Where does this failing binding fail? | Diagnose |
| Q3 | What if this fact were different? | Fact Overlay Check |
| Q4 | Given a finite candidate universe, who passes / who fails / why? | Why-not Universe Diagnose |
| Q5 | In native evaluation, where does the where-body collapse? | Evaluator Frontier Trace |

Layer 6 后续 shipped 4 个 overlay-driven capability(详见 §16),消费 Q1 输出的 `SupportArtifact` + `EvaluationOverlay` 做 hypothetical evaluation:

| 能力 | Batch | 输入 → 输出 |
|---|---|---|
| ProofFrame Rechecker | 4 | SupportArtifact + fact overlay → per-atom verdicts |
| Rule Disable | 5a | RuleSpec + RuleDisableAction → variant rows + ProofFrame |
| Rule Literal Replace | 5b | RuleSpec + RuleLiteralReplaceAction → variant rows + ProofFrame |
| Rule Add Condition | 5c | RuleSpec + RuleAddConditionAction → variant rows + synthetic ProofFrame |

### 关键术语速查

| 术语 | 含义 | 来源 |
|---|---|---|
| `asrt_id` | 每条 assertion 稳定 ID | `set_field(...)` 返回值 |
| `e_ref` | entity reference 编码 | `resolve_selector(...)` |
| `pred_id` | predicate ID | `entity_info(index, ...)` / `field_predicate(index, ...)` |
| `fact_tuple` | 投影输出元组,形如 `(e_ref, *val_atoms)`,entity 永远在位置 0 | `project_view_facts(...)` |
| `BindingItems` | `tuple[tuple[str, JSONValue], ...]`,变量名 `$` 起头 | capability request/result |
| `ProjectedFact` | `(asrt_id, fact_tuple)` | `project_view_facts_with_witness(...)` |
| `CandidateSet` | engine 输出 candidate(`candidate_key` + `payload` + `support_digest`) | adapter dispatch |
| `SupportArtifact` | souffle witness 形态(`binding_items` + `pred_witnesses`) | engine-side evidence |
| `ProvenanceEnvelope` | problog / pyreason 形态(adapter-local proof trace / event log) | engine-side evidence |

### Application-first hard constraint

每个 application capability 都遵循:

- DTO 在 `kernel.application.protocol/`(intent-only,无 `store` / `registry` / cache 字段)
- Runtime 在 `kernel.application/`(纯函数,`store` / `registry` 走 side-channel kwargs)
- `kernel.sdk` 不背 substrate(SDK 仅 ergonomic shell)

详细治理见 cross-session memory anchor `project_application_first_runtime_authority.md`。

---

## 2. Layer 1 — Schema & Entity

Entity 是 schema 中的一阶数据类型。继承 `Entity` 并用 `Identity(primary_key=True)` 标注身份字段、`Field(cardinality=...)` 标注常规字段,定义实体结构。`compile_schema_from_classes` 将 Python 类编译成 schema_ir(JSON-like 字典),被 Store 和 application 层消费。`build_schema_index(schema_ir)` 建快查 index,支持 `entity_info()` 和 `field_predicate()` 查实体元数据及字段谓词映射。

Cardinality 分两种:`"single"` 表示单值字段(一实体最多保有一个值,旧值被覆盖),`"multi"` 表示多值字段。主键字段(`primary_key=True`)组成实体全局唯一标识,在 ledger 写入时被编码为 `e_ref`。

```python
from kernel.sdk import Entity, Identity, Field, compile_schema_from_classes
from kernel.application import build_schema_index

class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")

schema_ir = compile_schema_from_classes([Person])
index = build_schema_index(schema_ir)
```

关键代码:
- `src/kernel/sdk/schema.py` — `Identity` / `Field` 类定义
- `src/kernel/application/schema_runtime.py` — `build_schema_index` 实现

---

## 3. Layer 2 — Ledger 写入

`Store` 是 ledger + indexes 容器,初始化时接 schema_ir,内部维护 ledger(追加式日志存所有 assertion)+ 多个 index。`set_field` 是核心写接口,接 `(ledger, pred_id, e_ref, rest_terms)` 返回稳定 `asrt_id`。`rest_terms` 形如 `[("string", "alice"), ("int", 25)]` 的 `(type_tag, value)` 对列表。每次调用 `set_field` 生成一条新 assertion,包括 exists predicate(如 `Person:exists`)和字段谓词(如 `Person:name` / `Person:age`)。

`asrt_id` 全局唯一不可变,后续被 Fact Overlay 等高层组件引用以追踪数据源。Ledger 通过 `resolve_selector` 将逻辑选择器(`entity_type` + identity 值)解析为 `e_ref` 编码。

```python
from kernel.core.store import Store
from kernel.core.evidence.write_protocol import set_field
from kernel.application import entity_info, field_predicate, resolve_selector
from kernel.application.protocol import EntitySelector

store = Store(schema_ir)
index = build_schema_index(schema_ir)

ref = resolve_selector(
    EntitySelector(entity_type="Person", identity={"name": "alice"}),
    index=index,
)
e_ref = ref.encoded_ref

info = entity_info(index, "Person")
exists_pred_id = info.exists_predicate_id
name_pred_id = info.identity_predicates["name"].pred_id
age_pred_id = field_predicate(index, "Person", "age").pred_id

asrt_exists = set_field(store.ledger, exists_pred_id, e_ref, [])
asrt_name   = set_field(store.ledger, name_pred_id, e_ref, [("string", "alice")])
asrt_age    = set_field(store.ledger, age_pred_id, e_ref, [("int", 25)])
```

关键代码:
- `src/kernel/core/store/runtime.py` — `Store` 构造函数
- `src/kernel/core/evidence/write_protocol.py` — `set_field` 实现

---

## 4. Layer 3 — Projection

Ledger 存的是原始 assertion;projection 把 active 状态的 assertion 转成 evaluator 友好格式。`project_view_facts(ledger, schema_ir)` 返 `dict[str, list[tuple[Any, ...]]]`,key 是 `pred_id`,value 是 `fact_tuple` 列表;每条 `fact_tuple = (e_ref, *val_atoms)` —— **entity 在位置 0,后续值在位置 1+**。`project_view_facts_with_witness(...)` 返 `dict[str, list[ProjectedFact]]`,其中 `ProjectedFact(asrt_id, fact_tuple)` 保留 assertion 链式追踪。

Cardinality `"single"` 时 projection 应用 chosen policy 选唯一 active assertion;`"multi"` 则保留所有 active。无论哪种,`fact_tuple` 结构一致:entity reference 在首位。

```python
from kernel.core.view.projector import (
    project_view_facts,
    project_view_facts_with_witness,
)

# 普通投影:返 (e_ref, *val_atoms) 元组
facts = project_view_facts(store.ledger, store.schema_ir)
# facts = {"Person:exists": [("alice",)], "Person:age": [("alice", 25)], ...}

# 带见证投影:保留 asrt_id
facts_witnessed = project_view_facts_with_witness(store.ledger, store.schema_ir)
for pred_id, projected_facts in facts_witnessed.items():
    if projected_facts:
        pf = projected_facts[0]
        # pf.asrt_id 是写 assertion 时返回的 ID
        # pf.fact_tuple 是 (e_ref, *val_atoms)
        break
```

关键代码:
- `src/kernel/core/view/projector.py` — `project_view_facts` / `project_view_facts_with_witness`
- `src/kernel/core/store/_support.py` — `ProjectedFact` 数据类

---

## 5. Layer 4 — Native Evaluator

`body_ir` 是 atom 列表的集合,每个 atom 形如 `("pred", pred_id, [args])` / `("eq", "$x", value)` / `("in", "$x", [...])` / `("not", [inner_body])` / `("gt", "$x", 5)` 等。Evaluator 遍历每个 OR 分支的 AND 链,初始化 `envs = [{}]`,逐 atom pruning:`pred` atom 遍历 fact 并绑定变量,`eq`/`ne`/`in`/`cmp`/`arith` 过滤或推导绑定,`not` 检查否定存在。任意 atom 致 envs 为空,该分支失败;最终 envs 中每个 dict 是一个 surviving binding。

`evaluate_native_where(view_facts, body, *, registry=None, witness_facts=None, remember_support_artifact=None)` 是 public entry。registry=None 时(纯 pred/eq/in/cmp/arith atoms),直接调底层 `evaluate_where`。registry 存在且 body 含 RuleRef 时,evaluator 执行 preflight + rewrite(将 ruleref 展开为对应 internal pred)+ 在 rewritten body 上评估;成功 binding 附 `rule_refs` 和 `rule_ref_resolutions` 元数据。返回值 `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`,其中 `bindings: list[dict[str, Any]]` 是最终绑定列表。

RuleRef 三阶段:**preflight**(rule_id/version 在 registry 存在 + arity 匹配)→ **rewrite**(递归评估 child rule 的 where,把 child output 组织为 overlay pred,并记录 row_supports)→ **evaluate**(用 overlay 扩展 view_facts,在 body(ruleref→pred 已替换)上评估)。

```python
from kernel.core.rules.ruleref_substrate import evaluate_native_where

view_facts = {
    "person": [("alice", 30), ("bob", 25), ("carol", 28)],
    "city":   [("alice", "NYC"), ("bob", "LA"), ("carol", "NYC")],
}

# AND 链:NYC 的人及年龄
where = [
    ("pred", "person", ["$name", "$age"]),
    ("pred", "city",   ["$name", "NYC"]),
]
result = evaluate_native_where(view_facts, where, registry=None)
# result.bindings = [{"$name": "alice", "$age": 30}, {"$name": "carol", "$age": 28}]

# OR 分支(嵌套 list)+ not
where_or_not = [
    [
        ("pred", "person", ["$name", "$age"]),
        ("pred", "city", ["$name", "NYC"]),
        ("gt", "$age", 27),
    ],
    [
        ("pred", "person", ["$name", "$age"]),
        ("not", [("pred", "city", ["$name", "LA"])]),
    ],
]
```

关键代码:
- `src/kernel/core/rules/where_eval.py` — `_eval_body` envs pruning
- `src/kernel/core/rules/ruleref_substrate.py` — `evaluate_native_where` + RuleRef 三阶段

---

## 6. Layer 5 — Engine Adapters & Evidence Artifacts

非 native engine(souffle / problog / pyreason)的评估通过 adapter。Application 层调 `evaluate_derivation_plans(request, *, store, registry)`,其中 request 含 plans + engine specifier;dispatcher 遍历 head,调 `store.evaluate_engine(...)` 转发对应 adapter。Adapter 返 `list[CandidateSet]`。

每个 `CandidateSet` 携带:**identity**(`candidate_key` 内容哈希、`key_tuple_digest`)、**payload**(结果数据)、**support 引用**(`support_digest` + `support_kind`)。真正的"证据"分两类:

1. **`SupportArtifact`**(native + souffle witness)—— `binding_items`(变量绑定 k-v 对)+ `pred_witnesses`(哪些 pred atom 及对应 assertion 满足该候选),记录完整推导路径中的 fact 引用
2. **`ProvenanceEnvelope`**(problog / pyreason)—— adapter-local 概率级联 / event log,attach 到 successful candidate

两种都存在 store 的支撑库中,candidate 仅保留 digest 指针。`EvidenceEnvelope`(Check 协议层)是 capability-level wrapper,把 engine 评估输出 normalize 到 shipped capability 用得上的形态。

不深入 adapter 内部;想看真实行为参考:
- `examples/05_dora_pyreason_propagation.ipynb`(PyReason 概率推导)
- `examples/06_problog_probabilistic.ipynb`(ProbLog 概率程序)

```python
from kernel.application.derivation_runtime import evaluate_derivation_plans
from kernel.application.protocol import DerivationEvaluateRequest

# 构造一个 problog 评估请求(需已编译的 plan)
request = DerivationEvaluateRequest(
    plans=(plan,),  # CompiledDerivationPlan list
    engine="problog",
    run_id="run_20260505_001",
)

# 调用:dispatcher 内部转发至 evaluate_problog(...)
# 注:需安装 problog adapter 才能真跑
candidates = evaluate_derivation_plans(request, store=store, registry=registry)
for cand in candidates:
    print(f"candidate_key={cand.candidate_key}")
    print(f"payload={cand.payload}")
    print(f"support: digest={cand.support_digest} kind={cand.support_kind}")
```

关键代码:
- `src/kernel/core/derivation/candidates.py` — `CandidateSet` 字段 + post_init 校验
- `src/kernel/core/store/_support.py` — `SupportArtifact(kind, root_result_kind, binding_items, pred_witnesses)`
- `src/kernel/application/derivation_runtime.py` — `evaluate_derivation_plans` entry + engine dispatch

---

## 7. Layer 6 — Capability Lines(4 application + 1 evaluator)

### 7.1 Check —— Q1: Does this binding pass?

**何时用:** 给定一组变量值,判断规则 body 是否存在与之匹配的 final binding。

**Request:** `CheckRequest(plan, binding, engine)`
**Result:** `CheckResult(status, matched_count, matched_binding, evidence_envelope, errors, warnings)`
**Status:** `Literal["passed", "failed", "unsupported", "invalid_request"]`

- `passed`:至少一个 final binding 子集匹配请求 binding
- `failed`:无任何 final binding 匹配
- `unsupported`:非 native engine 表达性预检失败(如 ProbLog 不支持 body-only 变量)
- `invalid_request`:语义错误(未知变量、缺 registry 等)

```python
from kernel.application import check_derivation_binding
from kernel.application.protocol import CheckRequest

binding = (("$p", "alice_ref"), ("$age", 25), ("$region", "us"))
result = check_derivation_binding(
    CheckRequest(plan=plan, binding=binding, engine="native"),
    store=store,
)
assert result.status == "passed"
assert result.matched_count >= 1
assert result.matched_binding == binding
```

### 7.2 Diagnose —— Q2: Where does this failing binding fail?

**何时用:** binding 在 Check 失败时,定位第一个无法满足的 atom 及其前驱环境。

**Request:** `DiagnoseRequest(plan, binding, engine)`
**Result:** `DiagnoseResult(status, matched_count, matched_binding, failure_kind, diagnostic_payload, errors, warnings)`
**Status:** 同 Check 4 值
**`failure_kind`:** `Literal["no_candidate", "atom_localized"] | None`(仅 failed 时填)
**`diagnostic_payload`:** `DiagnoseAtomLocator(branch_index, failed_atom_index, attempted_binding) | None`(failed.atom_localized 时填,**仅 native engine 支持**;非 native 返回 `failed.no_candidate`)

```python
from kernel.application import diagnose_derivation_binding
from kernel.application.protocol import DiagnoseRequest

wrong_binding = (("$p", "alice_ref"), ("$age", 99), ("$region", "us"))
result = diagnose_derivation_binding(
    DiagnoseRequest(plan=plan, binding=wrong_binding, engine="native"),
    store=store,
)
assert result.status == "failed"
assert result.failure_kind == "atom_localized"
locator = result.diagnostic_payload
assert locator.failed_atom_index == 1   # age atom
assert locator.branch_index == 0
```

### 7.3 Fact Overlay Check —— Q3: What if this fact were different?

**何时用:** 不修改数据库的前提下,评估某些 fact 值改变后 binding 成立状态是否变化。

**Request:** `FactOverlayCheckRequest(plan, binding, overlay, engine)`,`overlay: tuple[FactValueOverride, ...]`(至少 1 个;空 tuple 在 runtime 返回 `invalid_request` + `EMPTY_OVERLAY_NOT_PERMITTED`)
**`FactValueOverride`:** `(asrt_id, pred_id, e_ref, old_fact_tuple, new_fact_tuple, note=None)`
**Result:** `FactOverlayCheckResult(status, before, after, diff, errors, warnings)`
- `before / after: OverlayCheckPhase | None`(`status` / `matched_count` / `matched_binding`)
- `diff: OverlayCheckDiff | None`(`status_changed` / `matched_count_delta` / `bindings_added` / `bindings_removed`)

**Engine:** MVP 仅 `native`(souffle / problog / pyreason 返 `unsupported` + `ENGINE_OVERLAY_NOT_SUPPORTED`)
**关键 invariant:** ledger byte-identical(无 write)+ no live `Store` cache contamination

```python
from kernel.application import check_fact_overlay_binding
from kernel.application.protocol import FactOverlayCheckRequest, FactValueOverride

binding = (("$p", alice.e_ref), ("$age", 30), ("$region", "us"))
result = check_fact_overlay_binding(
    FactOverlayCheckRequest(
        plan=plan,
        binding=binding,
        overlay=(
            FactValueOverride(
                asrt_id=alice.age_asrt_id,
                pred_id=alice.age_pred_id,
                e_ref=alice.e_ref,
                old_fact_tuple=(alice.e_ref, 25),
                new_fact_tuple=(alice.e_ref, 30),
                note="age change demo",
            ),
        ),
        engine="native",
    ),
    store=store,
)
assert result.before.status == "failed"
assert result.after.status  == "passed"
assert result.diff.status_changed
```

### 7.4 Why-not Universe Diagnose —— Q4: Given a finite candidate universe, who passes / who fails / why?

**何时用:** 对显式有限的候选 binding 集合,一次性算 green/red partition + 失败行的 Diagnose 映射。

**Request:** `WhyNotUniverseRequest(plan, candidate_universe, engine)`,`candidate_universe: tuple[BindingItems, ...]`(必须覆盖所有 head 变量,无重复;**空 tuple 合法**,返 `completed` + 空 green/red)
**Result:** `WhyNotUniverseResult(status, requested_universe, green, red, errors, warnings)`
**Status:** `Literal["completed", "unsupported", "invalid_request"]` —— **注意不是 passed/failed**(set 计算语义,不是 binding 判断)
**`red: tuple[WhyNotRedRow, ...]`,`WhyNotRedRow(binding, diagnostic)`,`diagnostic: WhyNotRowDiagnostic(status, failure_kind, diagnostic_granularity, atom_locator, errors, warnings)`**
- `diagnostic.status`:仅 `failed | unsupported`
- `diagnostic.diagnostic_granularity`:`atom_localized`(native 失败 + 可定位)/ `coarse`(非 native failed)/ `unavailable`(Diagnose 返 unsupported)
- `diagnostic.atom_locator: WhyNotAtomLocator | None`(Why-not 自有类型,**不嵌套 `DiagnoseAtomLocator`**)

```python
from kernel.application import check_why_not_universe
from kernel.application.protocol import WhyNotUniverseRequest

universe = (
    (("$p", alice.e_ref), ("$age", 30), ("$region", "us")),
    (("$p", bob.e_ref),   ("$age", 30), ("$region", "eu")),
    (("$p", carol.e_ref), ("$age", 30), ("$region", "us")),
)
result = check_why_not_universe(
    WhyNotUniverseRequest(plan=plan, candidate_universe=universe, engine="native"),
    store=store,
)
assert result.status == "completed"
# bob 真有 age=30 region=eu → green;alice/carol 都 fail at age atom → red
for row in result.red:
    assert row.diagnostic.status == "failed"
    assert row.diagnostic.failure_kind == "atom_localized"
    assert row.diagnostic.atom_locator.failed_atom_index == 1
```

### 7.5 Evaluator Frontier Trace —— Q5: In native evaluation, where does the where-body collapse?

**何时用:** evaluator 层追踪 where 子句评估轨迹,识别哪个 atom 把 envs filter 空。

**关键特征:** 这是 `kernel.core.rules.frontier`(evaluator 层,**非 application protocol**),使用方式与前 4 个不同 —— 直接调函数,不构造 Request DTO。

**签名:**
```python
def evaluate_native_where_frontier(
    view_facts: dict[str, list[tuple[Any, ...]]],
    where: list[Any],
    *,
    registry: RuleRegistry | None = None,
    witness_facts: dict[str, list[Any]] | None = None,
    remember_support_artifact: Any | None = None,
) -> NativeWhereFrontierEvaluation
```

**Return:** `NativeWhereFrontierEvaluation(bindings, rule_refs, rule_ref_resolutions, frontier_rows)`
- `bindings`:与 `evaluate_native_where(...)` success-side parity
- `frontier_rows: tuple[NativeWhereFrontierRow, ...]`:per failed branch 至多 1 行

**`NativeWhereFrontierRow(branch_index, failed_atom_index, atoms_satisfied, frontier_count, failure_kind)`**:
- `branch_index`:OR 分支号
- `failed_atom_index`:第一个 filter 空的 atom index;DTO 强制 `atoms_satisfied == failed_atom_index`
- `frontier_count`:**该 atom 之前** 的 envs 数量(input env count,非 filtered 后的 0)
- `failure_kind`:`Literal["empty_input", "atom_filter_empty"]`
  - `empty_input`:branch 入口 envs 已空(防御性,正常算法不可达 —— 算法初始 `envs = [{}]`)
  - `atom_filter_empty`:envs 进 atom 但全被 filter 空

```python
from kernel.core.rules.frontier import evaluate_native_where_frontier

view_facts = {
    "Person:exists": [("alice",), ("bob",), ("carol",)],
    "Person:age":    [("alice", 25), ("bob", 30), ("carol", 28)],
}
where = [
    ("pred", "Person:exists", ["$p"]),
    ("pred", "Person:age",    ["$p", 99]),  # 没人 age=99
]
result = evaluate_native_where_frontier(view_facts, where)
assert result.bindings == []
assert len(result.frontier_rows) == 1
row = result.frontier_rows[0]
assert row.failed_atom_index == 1
assert row.frontier_count == 3            # 3 person 候选进 age atom
assert row.failure_kind == "atom_filter_empty"
```

关键代码:
- `src/kernel/core/rules/frontier.py` — DTO + entry + 算法

---

## 8. 端到端示例

完整 5-capability 端到端示例在 `examples/11_capabilities_e2e_demo.ipynb`(`.py` 是 smoke test target,`.ipynb` 是阅读/编辑版本)。

这个示例用同一个 `Person(name, age, region)` fixture 串起 Q1-Q5。它先展示单个 binding 的判断与诊断,再展示 fact what-if、有限候选宇宙、native frontier 这三种更宽的读法。

```bash
# 确定性 smoke run
python examples/11_capabilities_e2e_demo.py

# 或在 Jupyter 中打开
jupyter notebook examples/11_capabilities_e2e_demo.ipynb
```

5 phase 简明:

1. **Q1 Check — Does this binding pass?** alice 真实 binding `($age=25, $region=us)` → `passed`
2. **Q2 Diagnose — Where does this failing binding fail?** alice 假 binding `($age=99, $region=us)` → `failed.atom_localized` at age atom
3. **Q3 Fact Overlay — What if this fact were different?** alice 假设 age=30 → `before.failed → after.passed`,ledger byte-identical
4. **Q4 Why-not — Given a finite candidate universe, who passes / who fails / why?** universe `[(alice,30,us), (bob,30,eu), (carol,30,us)]` → green=[bob],red=[alice 原子定位, carol 原子定位]
5. **Q5 Frontier — In native evaluation, where does the where-body collapse?** where 含 `age($p, 99)` → 1 frontier row,frontier_count=3,failure_kind=atom_filter_empty

每 phase 内嵌 assertion,跑过表示 5 capability composition 在你环境上正常。

---

## 9. 架构 invariant 速查(future contributor 用)

- **Application-first**:每个新 capability 起步是 DTO + 纯函数,不在 SDK 长 substrate
- **Q1 Sibling 三梯度(application 层)**:
  - Diagnose vs Check:不 call 不 import(strict)
  - Fact Overlay vs Check:不 call,共享 helper via `kernel.application._derivation_match_helpers`
  - Why-not vs Diagnose:可 call runtime + 构造 `DiagnoseRequest`,但不 import Diagnose result types(duck typing)
- **Layer-separation invariant(evaluator 层)**:`kernel.core.rules.frontier` 不 import application/SDK/adapter/candidate/evidence types;`§7-EvaluatorFrontier-10` 静态扫强制 application 不 sneak-import frontier
- **§6.6 working hypothesis**:per-capability local engine gate(几行 paragraph 描述完毕),跨 3 个 application capability + 1 evaluator capability 仍 hold;`§6.7` declarative capability schema 未触发
- **No ledger write from read paths**:Check / Diagnose / Fact Overlay / Why-not / Frontier 都 read-only,assertion 仅由 `set_field` 等显式 write API 写

archived blueprints + cross-session memory anchor 含全部决策溯源:
- `docs/blueprints/archive/2026-05-{03,04,05}_*.md`(5 个 implemented capability 蓝图)
- `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_*_shipped.md`(5 个 shipped anchor)

---

## 10. Derivation Evaluate / Accept —— evidence 产生与落 ledger

5 个 capability 全是 **consumer**(读已存在的 evidence 或在它上跑判断)。Evidence 实际**产生**走 evaluate → accept 双阶段流程,这是 derivation 主路径。

### 10.1 两阶段模型

```
[Evaluate]                              [Accept]
CompiledDerivationPlan                  list[CandidateSet]
    +                                       +
store.ledger 投影(view_facts)          DerivationAcceptRequest(...)
    ↓                                       ↓
evaluate_derivation_plans(...)          accept_derivation_candidate_sets(...)
    ↓                                       ↓
list[CandidateSet]                     ledger append fact assertion
+ SupportArtifact / ProvenanceEnvelope  + 新 asrt_id 列表
  写 store in-memory cache              candidate "升级"为 ledger truth
```

**关键:** Evaluate **不写 ledger**,只产 candidate + 把 evidence 写进 `store._remember_*` 内存 cache;Accept 才真 append ledger。

### 10.2 Evaluate 入口

```python
from kernel.application import evaluate_derivation_plans
from kernel.application.protocol import DerivationEvaluateRequest

candidates: list[CandidateSet] = evaluate_derivation_plans(
    DerivationEvaluateRequest(
        plans=(plan,),                 # tuple[CompiledDerivationPlan, ...]
        run_id="optional-trace-id",
        engine="native",               # native / souffle / problog / pyreason
    ),
    store=store,
    registry=registry,                 # 含 ruleref 时必需
)
```

Native 路径走 `evaluate_native_where(...)` + `_evaluate_where_over_view_with_support`(产 `SupportArtifact`);非 native 经 `Store.evaluate_engine(...)` 走 adapter 产 adapter-specific evidence。两路均末尾调 `_remember_candidate_support_backrefs(...)` 把 candidate→evidence 关联落 cache。

### 10.3 Accept 入口

```python
from kernel.application import accept_derivation_candidate_sets
from kernel.application.protocol import DerivationAcceptRequest

results = accept_derivation_candidate_sets(
    candidate_sets=candidates,
    accept_request=DerivationAcceptRequest(
        accept_mode="atomic",              # "atomic" | "best_effort"
        idempotent_duplicate_ok=True,
        approved_by="rule.audit",
        note="auto-accept",
        dry_run=False,                     # True = 校验不写
    ),
    store=store,
)

for result in results:
    if result.get("state") == "ACCEPTED":
        for written in result.get("written_assertions", []):
            print(f"new asrt_id: {written['asrt_id']}")
```

模式:
- `"atomic"`:任一 candidate 失败,整批回滚已写 assertion
- `"best_effort"`:per-candidate 容错,失败行标 `FAILED_*` / `BLOCKED_DEPENDENCY`,继续后续
- `dry_run=True`:跑校验但不 append

### 10.4 Evidence 生命周期

| 时刻 | Evidence 形态 | 存储位置 |
|---|---|---|
| Evaluate 中 | `SupportArtifact` / `ProvenanceEnvelope` | `store._remember_*` in-memory cache |
| Evaluate 后 | `CandidateSet`(含 `support_digest` 指针) | 调用方持有 |
| Accept 中 | `AcceptRequest`(transient) | 事务边界内 |
| Accept 成功 | Ledger fact assertion | `store.ledger`(append-only,持久) |
| Accept 后查 | `EvidenceTreeDTO` / `EvidenceEnvelope` | §14 audit 接口或直接 cache |

### 10.5 关键文件

- `src/kernel/application/derivation_runtime.py` — `evaluate_derivation_plans` + accept 入口
- `src/kernel/application/protocol/derivation.py` — `DerivationEvaluateRequest` / `DerivationAcceptRequest`
- `src/kernel/core/derivation/accept.py` — `accept_many_candidate_sets` 实际实现
- `src/kernel/core/store/_evaluate.py` — native vs adapter dispatch

---

## 11. Entity Read —— 读 entity snapshot + assertion 历史

Application 层对 raw ledger 读的高层抽象。与 §3 `set_field` 写对偶,负责**读取 entity 当前状态 + assertion 链式历史**。

**核心数据模型:**

`EntityReadRequest`:
- `mode="get"`(精确单 entity,需 `selector`)/ `mode="find"`(模糊多 entities,可 `limit`)
- `entity_type`,`selector: EntitySelector`,`field_filters` 过滤
- `include_assertions: bool`,`include_history: bool`(取 assertion 历史)

`EntityReadResponse`:`items: tuple[EntitySnapshotDTO, ...]`,每 entity 一个 snapshot:
- `ref: EntityRef`
- `fields: dict[str, FieldValueDTO]`(`value_kind="scalar" | "entity_ref"`,`cardinality`)
- `assertions: dict[str, FieldAssertionsDTO]`(per-field `active` + `history` of `AssertionRecordDTO`)

`FieldAssertionsDTO.active / history` 是 assertion 链关键 —— 每条 `AssertionRecordDTO(assertion_id, value, active, meta)` 记录一次写入,迭代 active+history 还原字段完整变更日志。

```python
from kernel.application import execute_read_request
from kernel.application.protocol import EntityReadRequest, EntitySelector

request = EntityReadRequest(
    mode="get",
    entity_type="Person",
    selector=EntitySelector(entity_type="Person", identity={"name": "alice"}),
    include_assertions=True,
    include_history=True,
)
response = execute_read_request(request, store=store, index=index)

for snapshot in response.items:
    print(f"Entity: {snapshot.ref.encoded_ref}")
    for field_name, field_value in snapshot.fields.items():
        print(f"  {field_name}: {field_value.value} ({field_value.cardinality})")
    for field_name, assertions_dto in snapshot.assertions.items():
        for record in assertions_dto.active:
            print(f"  [ACTIVE] {field_name}: {record.assertion_id} → {record.value}")
        for record in assertions_dto.history:
            print(f"  [HISTORY] {field_name}: {record.assertion_id} → {record.value}")
```

---

## 12. Entity Write Plan / Ingest —— 高层写 API

两条并行抽象,适配不同写入场景。

### 12.1 EntityWritePlan(编程式精确写)

`EntityWriteCommand` 描述单 entity 修改意图;`plan_write_command(...)` 产 `EntityWritePlan`(完整 schema/cardinality/identity 校验);`apply_write_plan(...)` 执行返 `EntityWriteResult`。

```python
from kernel.application import plan_write_command, apply_write_plan
from kernel.application.protocol import (
    EntityWriteCommand, FieldMutation, EntitySelector, FieldPath,
)

command = EntityWriteCommand(
    target=EntitySelector(entity_type="Person", identity={"name": "alice"}),
    mutations=(
        FieldMutation(
            op="set",
            field=FieldPath(entity_type="Person", field_name="age"),
            value=26,
        ),
        FieldMutation(
            op="add",
            field=FieldPath(entity_type="Person", field_name="tags"),
            value="vip",
        ),
    ),
    create_if_missing=False,
)

plan = plan_write_command(command, store=store, index=index)
if plan.can_apply:
    result = apply_write_plan(plan, store=store, index=index)
    for op in result.applied:
        if op.status == "applied":
            print(f"  op[{op.op_index}]: asrt_id={op.assertion_id}")
else:
    for err in plan.errors:
        print(f"plan error: {err.code}: {err.message}")
```

### 12.2 IngestRequest(bulk)

`IngestItem` 是 union:`IngestSetItem`(覆盖)/ `IngestAddItem`(追加多值)/ `IngestRetractItem`(撤销 assertion)。`apply_ingest_request(...)` 返 `IngestResult` 含 `written_assertion_ids` / `skipped_indices` / `duplicate_indices`。

```python
from kernel.application import apply_ingest_request
from kernel.application.protocol import (
    IngestRequest, IngestSetItem, IngestAddItem,
    EntitySelector, FieldPath,
)

request = IngestRequest(
    items=(
        IngestSetItem(
            target=EntitySelector(entity_type="Person", identity={"name": "dave"}),
            field=FieldPath(entity_type="Person", field_name="age"),
            value=42,
        ),
        IngestAddItem(
            target=EntitySelector(entity_type="Person", identity={"name": "dave"}),
            field=FieldPath(entity_type="Person", field_name="tags"),
            value="new-hire",
        ),
    ),
    collect_mode="collect",   # "stop" | "collect"
)
result = apply_ingest_request(request, store=store, index=index)
print(f"written: {len(result.written_assertion_ids)}, skipped: {len(result.skipped_indices)}")
```

### 12.3 选用建议

- **EntityWritePlan**:精确编程式写,完整校验;交互式应用 / workflow 推荐
- **Ingest**:批量 ETL / 初始化导入;错误模式可配,单条错误不阻全局
- 两者底层都最终到 `set_field`(§3 低层),用法 surface 不同

---

## 13. Query Runtime —— Entity 空间的 WHERE 查询

不同于 `evaluate_native_where(...)`(底层 atom walker)和 `evaluate_derivation_plans(...)`(rule 推导),`Query` 是直接对 entity 空间发 SQL-like SELECT 的 application API。

**核心数据模型:**
- `WhereIR`: `list[Any]`,与 derivation `body_ir` 同 atom 形态
- `QueryReturnSlot(alias, kind="entity"|"scalar", var, field_path?, entity_type?)`:每输出列声明
- `QueryReturnContract(slots=(...))`:全部 slot tuple,alias 唯一非空
- `QueryRuntimeRequest(entity_type, where_ir, return_contract, on_missing, on_type_mismatch)`
- `QueryRuntimeResponse(rows: tuple[dict[str, QueryRowValue], ...], errors)`

**两阶段执行:**`execute_query()` 先调 `evaluate_native_where(...)` 拿满足 where 的 binding 集合;再 per-binding per-slot resolve(`hydrate_entity()` 重构 `EntitySnapshotDTO` 或直接取 scalar `FieldValue`)。容错:`on_missing` / `on_type_mismatch` 取 `"error" | "skip" | "null"`。

```python
from kernel.application import execute_query
from kernel.application.protocol import (
    QueryRuntimeRequest, QueryReturnContract, QueryReturnSlot, FieldPath,
)

contract = QueryReturnContract(
    slots=(
        QueryReturnSlot(alias="person", kind="entity", var="$p"),
        QueryReturnSlot(
            alias="age",
            kind="scalar",
            var="$p",
            field_path=FieldPath(entity_type="Person", field_name="age"),
        ),
    ),
)

request = QueryRuntimeRequest(
    entity_type="Person",
    where_ir=[
        ("pred", "Person:exists", ["$p"]),
        ("pred", "Person:region", ["$p", "us"]),
    ],
    return_contract=contract,
    on_missing="skip",
    on_type_mismatch="error",
)

response = execute_query(request, store=store, index=index)
for row in response.rows:
    person_snapshot = row["person"]   # EntitySnapshotDTO
    age_value = row["age"]            # FieldValue
    print(f"{person_snapshot.ref.encoded_ref}: age={age_value}")
```

**何时用:** 用户视角 SQL-like 查询(非 derivation 推导);onboarding journey 的 "ref → set/add → get → **query** → evaluate" 这一步。

---

## 14. Audit —— 证据查询

`kernel.audit` 是独立 package,专做证据追踪 / assertion 历史 / compliance 查询。**不读 entity 当前 snapshot**(那是 §11 entity_read),而是重构完整决策链路、candidate 生成历史、evidence 树。

**核心组件:**

`AuditPackageData`:audit 输出包内存表示(从磁盘 manifest.json + JSONL 加载)。含 `run_ledger` / `candidate_ledger` / `accept_write_ledger` / `decision_log` / `support_artifacts` / `rule_trace_artifacts` / `evidence_graphs` / `provenance_trees`。安装 `domains.ecss` 还含 compliance 注解。

`AuditQuery`:主入口,`AuditQuery(package)` 构造。主要 method:
- `list_runs()` / `get_run(run_id)`:推导运行
- `list_candidates(run_id=..., state=...)` / `get_candidate_evidence_tree(candidate_id)`:候选与证据树
- `list_decisions()` / `get_decision(decision_id)`:决策日志
- `list_accept_writes(candidate_id=...)` / `list_failures()`:accept 日志与错误
- `summarize_provenance_coverage()`:provenance 覆盖率统计
- `list_rule_traces()` / `get_rule_trace_narrative(rule_run_id)`:规则执行轨迹
- `list_compliance_matrix(req_id=..., status=..., milestone=...)`:**ECSS 合规矩阵**(可选 domain,需 `domains.ecss`,缺则抛 `AuditOptionalDomainError`)

```python
from kernel.audit import AuditQuery, load_audit_package

package = load_audit_package("/path/to/audit_package_dir")
audit = AuditQuery(package)

# 列已 accepted 的 candidate
for cand in audit.list_candidates(state="accepted"):
    print(f"{cand['candidate_id']} → {cand['pred_id']} ({cand['support_kind']})")

# 取证据树 + summary
candidate_id = "cand_v2:..."
evidence_tree = audit.get_candidate_evidence_tree(candidate_id)
summary = audit.get_candidate_evidence_tree_summary(candidate_id)
print(f"premises: {summary.get('premise_count')}")

# 覆盖率
cov = audit.summarize_provenance_coverage()
print(f"provenance: {cov['with_provenance']}/{cov['total_candidates']}")

# 可选:ECSS 合规矩阵(需 domains.ecss)
try:
    for req in audit.list_compliance_matrix(status="compliant"):
        print(f"  {req['req_id']}: {req['status']}")
except Exception as exc:
    print(f"compliance unavailable: {exc}")
```

**与 §11 entity_read 区别:** entity_read 读"当前 snapshot + 浅层 history";audit 读"完整证据链 + candidate 生成轨迹 + provenance + compliance",时序 + 依赖多维度。

---

## 15. 完整 Onboarding Journey 端到端

`examples/10_v01_onboarding_journey.ipynb` 是 v0.1 canonical user journey 完整 notebook:

```
ref → set/add → get → query → evaluate(native) → accept → export audit package
```

每步对应 tutorial 节:

| Journey 步骤 | Tutorial 节 | 关键 API |
|---|---|---|
| **ref** | §3 | `resolve_selector(EntitySelector(...), index=index)` |
| **set / add** | §3,§12 | 低层 `set_field(...)` 或高层 `apply_write_plan(...)` / `apply_ingest_request(...)` |
| **get** | §11 | `execute_read_request(EntityReadRequest(mode="get", ...))` |
| **query** | §13 | `execute_query(QueryRuntimeRequest(where_ir=..., return_contract=...))` |
| **evaluate** | §10.2 | `evaluate_derivation_plans(...)` → `list[CandidateSet]` |
| **accept** | §10.3 | `accept_derivation_candidate_sets(...)` → ledger append |
| **export audit** | §14 | export audit package → `load_audit_package(path)` 读回 |

```bash
# 完整 v0.1 journey(producer + consumer):
jupyter notebook examples/10_v01_onboarding_journey.ipynb

# 仅 5 capability composition sanity:
jupyter notebook examples/11_capabilities_e2e_demo.ipynb     # 见 §8
```

两者覆盖层次不同:
- `10_*.ipynb`:完整 user journey,含 **evaluate / accept producer 流程**
- `11_*.ipynb`:5 个 consumer capability 在固定 fixture 上的快速 sanity

---

## 16. Layer 6 拓展 —— Overlay & ProofFrame Operations(4 capability)

> 这 4 个 capability 不在 Q1-Q5 canonical questions 内。它们消费已有 `SupportArtifact` + `EvaluationOverlay`,做 hypothetical 评估,统一输出 `variant_rows + ProofFrame`。

### 16.1 ProofFrame Rechecker(Batch 4)

一句话:在 fact-side overlay 下,**逐 atom 解释**原 proof frame 是否仍 valid。

DTO:

```python
ProofFrameStatus = Literal["still_valid", "invalidated", "unknown"]

@dataclass(frozen=True)
class ProofFrameRecheckRequest:
    support_artifact: SupportArtifact
    overlay: EvaluationOverlay  # fact actions only

@dataclass(frozen=True)
class ProofFrameAtomVerdict:
    atom_key: str
    verdict: ProofFrameStatus  # 共享同 enum,无 second status set
    affected_action_indices: tuple[int, ...]

@dataclass(frozen=True)
class ProofFrameRecheckResult:
    status: ProofFrameStatus  # MUST 等于 aggregate(atom_verdicts)
    binding_items: BindingItems
    atom_verdicts: tuple[ProofFrameAtomVerdict, ...]
```

入口:`recheck_proof_frame(request, *, store, registry=None) -> ProofFrameRecheckResult`

要点:
- **Native + fact-overlay only**:`SupportArtifact.kind != "native_binding_v1"` / `rule_ref_edges` 非空 / `rule_actions` 非空 → frame-level `unknown`(空 atom_verdicts)
- **Aggregation 优先级**:`invalidated > unknown > still_valid`(protocol `__post_init__` enforce 不变量)
- **`not` step strict deferral**:任何 `kind == "not"` 永远 emit `unknown`(per Batch 4 §5.5.5 Decision 4)
- **Multi-witness pred_atom 区分** vs Fact Overlay Check:Fact Overlay 给 binding-level pass/fail;ProofFrame 区分"原 witness chain 还在"vs"alternative witness 救场"

何时用:Fact Overlay Check 已通,但想知道 specific 原 proof path 是否仍走得通(per-atom 解释)。

### 16.2 Rule Disable(Batch 5a)

一句话:临时禁用 rule body 的一个 locator(branch + atom),跑 variant evaluation,ProofFrame 解释原 frame。

DTO:

```python
@dataclass(frozen=True)
class RuleDisableAction:
    rule_id: str
    version: str
    branch_index: int
    atom_index: int
    note: str | None = None
```

放入 `EvaluationOverlay.rule_actions`(`fact_actions=()` 时仅 rule action 路径有效)。

入口:`check_rule_disable_action(request, *, store, registry=None) -> RuleDisableResult`

输出:`variant_rows: tuple[BindingItems, ...]` + `proof_frame: ProofFrameRecheckResult | None`(原 frame 解释)

要点:
- **Locator stability**:disable 后旧 `b{branch}.a{atom}:{kind}` 不漂移(`enumerate + skip` 模式)
- **Single-action MVP**:runtime 仅接受 1 个 `RuleDisableAction`(`tuple[..., ...]` container forward-compat)
- **RuleRef reject/defer**:`rule_refs / rule_ref_edges / rule_spec.where 含 ruleref` 全 unsupported
- Core primitive:`evaluate_where(..., disabled_locators=frozenset())` —— `evaluate_native_where` 不动(frontier drift gate 防 hardcoded `062ba88`)

### 16.3 Rule Literal Replace(Batch 5b)

一句话:替换 rule body 内一个 Const leaf,跑 variant evaluation。

DTO:

```python
@dataclass(frozen=True)
class RuleLiteralPath:
    kind: Literal["pred_term", "lhs", "rhs", "in_value", "const_operand"]
    index: int | None  # pred_term / in_value 必需,其他必须 None

@dataclass(frozen=True)
class RuleLiteralReplaceAction:
    rule_id: str
    version: str
    branch_index: int
    atom_index: int
    literal_path: RuleLiteralPath
    old_literal: Any  # stale-target guard
    new_literal: Any
    note: str | None = None
```

入口:`check_rule_literal_replace_action(request, *, store, registry=None) -> RuleLiteralReplaceResult`

要点:
- **Const-to-Const only**:不可 Var↔Const swap(避 binder/filter 角色变化 → 走 binding planner territory = Batch 5c)
- **5 path kinds 覆盖 7 atom kinds**:`pred_term`(pred terms[index]) / `lhs/rhs`(comparison sides) / `in_value`(in values[index]) / `const_operand`(addc/mulc 的 c)
- **atom kind / arity / list length 全 preserved**
- **`old_literal` stale-target guard**(同 `FactValueOverride.old_fact_tuple` 模式)
- Core primitive:`evaluate_where(..., literal_replacements=frozenset())`

### 16.4 Rule Add Condition(Batch 5c)

一句话:向 rule body branch 末尾**追加**一个 native filter atom(filter-only,**不引入新变量**)。

DTO:

```python
@dataclass(frozen=True)
class RuleAddedAtom:
    atom: tuple[Any, ...]  # raw native atom tuple

@dataclass(frozen=True)
class RuleAddConditionAction:
    rule_id: str
    version: str
    branch_index: int  # 注:无 atom_index(因为是 append)
    added_atom: RuleAddedAtom
    note: str | None = None
```

入口:`check_rule_add_condition_action(request, *, store, registry=None) -> RuleAddConditionResult`

要点:
- **Filter-only**:7 atom kinds(`ne/gt/ge/lt/le/in/eq with both sides resolved`)—— 真正的"binding planner"(新变量绑定)deferred
- **不引入新变量**:`where_ast_validate.atom_binds_new_variables(atom_ir, *, bound_vars)` 守门
- **Synthetic ProofFrame verdict** —— absent-atom mapping 的 minimal-blast-radius 解决:
  - synthetic key:`b{branch_index}.add{action_index}:{atom_kind}`(命名空间不与现 `b{br}.a{at}:{kind}` 冲突)
  - 现有 atoms 全 `still_valid`(filter 不 add fact,`not` 的 absence-check 不被打破 —— honest under filter-only scope)
  - synthetic verdict:`invalidated` iff 原 `binding_items` 不在 `variant_rows`,否则 `still_valid`
  - **不改 Batch 4 ProofFrame protocol**;3-status enum 不动
- Core primitive:`evaluate_where(..., added_conditions=frozenset())`

### 16.5 共享 invariant(贯穿 16.1-16.4)

| Invariant | 出处 |
|---|---|
| 输出 `variant_rows + ProofFrame` dual-output | Step 0.A 5a/5b/5c |
| **不复活** `superseded_by_full_eval` | Batch 4 §5.5.5 frozen 3-status |
| Native only;RuleRef-bearing input 全 reject | 5a/5b/5c §3 non-goals |
| Single-action MVP;tuple container forward-compat | 5a/5b/5c §5.7.5 |
| Cross-runtime auto-rejection via `isinstance(action, X)` 守卫 | 5b/5c §5.7.7 |
| 3-way ordering(forward-compat,MVP 单 action 不触发):`literal_replacements → added_conditions → disabled_locators` | 5c §5.8.4 |

**10 cross-batch drift gates 锁住 10 个文件**(scope guard tests 静态扫描):
- `src/kernel/sdk/` / `src/kernel/agent/` / `src/kernel/service/`
- `src/kernel/core/rules/frontier.py` / `ruleref_substrate.py`
- `src/kernel/application/protocol/proofframe.py` / `proofframe_runtime.py` / `fact_overlay_runtime.py`
- `src/kernel/application/rule_disable_runtime.py`(Batch 5b/5c implementation 0 改动)
- `src/kernel/application/rule_literal_replace_runtime.py`(Batch 5c implementation 0 改动)

### 16.6 跨 batch 经验 —— Tri-Batch Hardening Pattern

5a/5b/5c 三个 rule-ops runtime 共用 helper 时,bug 同时存在 3 份。

具体案例:`9ab282d` commit 一次同时修 3 处 `_contains_ruleref_atom`:
- 旧实现 shallow-scan top-level branch atoms,**不递归 compound atom**
- `("not", [("ruleref", ...)])` —— nested ruleref 在 `not` body 内 escape 到 native_eval_error
- 正确 contract:返回各自 `RULE_<X>_RULE_REF_UNSUPPORTED`
- Fix:递归 scan compound atom(目前仅 `not` 的 body;future compound kind 必须扩此函数)

教训:
1. 跨 batch copy-paste helper 的 bug 同时存在 N 份;review 时检 1 必检 N
2. Tri-batch hardening commit 比 N 单独 hardening commit 经济 —— 前提是 drift gate 允许 cross-batch fix
3. Cross-batch fix 在 archived audit 各自加 post-archive hardening row 同步标记

---

## 覆盖检查表

| 能力 | tutorial 节 | application 入口 |
|---|---|---|
| Schema & Entity 定义 | §2 | `compile_schema_from_classes` / `build_schema_index` |
| Ledger 低层写 | §3 | `set_field` |
| Projection | §4 | `project_view_facts` / `_with_witness` |
| Native evaluator | §5 | `evaluate_native_where` |
| Engine adapters | §6 | dispatch via `Store.evaluate_engine` |
| Check 能力 | §7.1 | `check_derivation_binding` |
| Diagnose 能力 | §7.2 | `diagnose_derivation_binding` |
| Fact Overlay 能力 | §7.3 | `check_fact_overlay_binding` |
| Why-not 能力 | §7.4 | `check_why_not_universe` |
| Frontier 能力 | §7.5 | `evaluate_native_where_frontier` |
| **ProofFrame Rechecker**(Batch 4)| §16.1 | `recheck_proof_frame` |
| **Rule Disable**(Batch 5a)| §16.2 | `check_rule_disable_action` |
| **Rule Literal Replace**(Batch 5b)| §16.3 | `check_rule_literal_replace_action` |
| **Rule Add Condition**(Batch 5c)| §16.4 | `check_rule_add_condition_action` |
| **Derivation Evaluate**(producer)| §10.2 | `evaluate_derivation_plans` |
| **Derivation Accept**(producer)| §10.3 | `accept_derivation_candidate_sets` |
| **Entity Read** | §11 | `execute_read_request` |
| **Entity Write Plan** | §12.1 | `plan_write_command` / `apply_write_plan` |
| **Ingest** | §12.2 | `apply_ingest_request` |
| **Query Runtime** | §13 | `execute_query` |
| **Audit 证据查询** | §14 | `AuditQuery` / `load_audit_package` |
| **完整 onboarding journey** | §15 | examples/10_v01_onboarding_journey.ipynb |

16 节 + 1 检查表 = 当前 v0.1 evidence 线全功能面(Q1-Q5 5 capability + ProofFrame Rechecker + 3 rule-side ops)。后续若发现 SDK ergonomic facade 细节(如 `SDKStore.set` / `add` / `get` / `query` / `evaluate` / `accept` 装饰器层)需展开,可单独再加一节;那是 SDK 层 thin shell,底层落到本 tutorial 列的 application 入口。

下一阶段(Batch 6 起):persistence layer(L8 capability-event JSONL audit trail)/ evidence diff cross-run / public surface decision —— 不在本 tutorial 已覆盖范围内。
