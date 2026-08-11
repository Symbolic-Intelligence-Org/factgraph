# Shipped FactGraph SDK 调用面(Phase 2 harness 参考;已实测)

**EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT**

全部私有 import、零 `src/**` 修改。环境硬要求:`PYTHONPATH=src`(包未 pip-install)。
以下调用均由 Phase 1 探索代理在 `PYTHONPATH=src` 下实跑通过。行号为 hnsm-backend @ 6ce7e2a5。

## workspace(内存)
```python
from factgraph.sdk import Entity, FactGraph, Field, Identity, Rule, compile_schema_from_classes, Database
fg = FactGraph.create(schema_classes=[Member])        # store.py:1831 → Database.create(":memory:")
# 变体 B(caller-owned db,便于生命周期控制/replay reopen):
#   db = Database.create(":memory:", schema_ir=compile_schema_from_classes([Member]))
#   fg = FactGraph.attach(db, schema_classes=[Member]) # store.py:1982;attach 时 fg.close() 不关 db,harness 自己 db.close()
```

## schema + pred_id(写事实必须照抄命名)
- exists 谓词 = `f"{EntityType}:exists"`(原类名,schema_compile.py:160)
- field/identity = `f"{snake(EntityType)}:{field}"`(schema_compile.py:264/566)
- **务必从 `fg.schema_ir["predicates"]` 读 pred_id,不要手拼**(exists 用类名、field 用 snake 前缀,大小写不对称)

## 加事实
```python
alice = fg.entities.create(Member, name="alice")      # store.py:1211
fg.fields.set(Member.color, alice, "red")             # store.py:973 → member:color(alice,"red")
fg.fields.set(Member.age,   alice, 30)
# 宽松任意谓词(绕 schema,但 schema 仍须非空):
#   from factgraph.core.evidence.write_protocol import set_field
#   set_field(fg.ledger, "member:x", alice, [("string","v")])
```

## Rule + RuleExpr
```python
from factgraph.core.rules.where_ast import PredAtom, CmpAtom, Const, Var  # CmpAtom op: eq/ne/gt/ge/lt/le
p,c = Var("$p"), Var("$c")
r = Rule(id="member_color",
         when=(PredAtom("Member:exists",[p]), PredAtom("member:color",[p,c])),  # :exists 决定 port=entity_ref
         ports={"person":p,"color":c})                # rule.py:52;每 port 的 Var 须在 when 出现
expr = (r.as_("m") & r2.as_("g")).join(r.as_("m").person.eq(r2.as_("g").person))  # rule.py:213/196; rule_expr.py:105
# .join_by_ports("person") 等价;| 为 OR;_OrGroup.join* 抛错;bool(rule) 抛 ExplicitBoolError
```

## 静态 DNF(不跑 engine)—— SC12/lineage 用
```python
from factgraph.application.protocol.rule_expr_lowering import (
    _DNF_BRANCH_LIMIT,                       # :42 == 32
    _dnf_branches,                           # :764 逐步构造,超 32 时只拿到"越过 32 的计数",精确计数须自算 _DNFBranch
    _normalize_to_dnf,                       # :757
    _validate_dnf_branch_count,              # :790 >32 → RuleExprError
    _lower_rule_expr,                        # :354 需 head,返回 RuleExprLoweringPlan(不跑 engine)
    _validate_rule_expr_head_foundation,     # :434 head/ports 校验(同名 port 未 join 在此炸,evaluate 前)
)
plan = _lower_rule_expr(expr, head=Rule.projection("person","color"))  # rule.py:184
# plan.branches[i].branch_id = "c0","c1"...;plan.occurrence_map[i].alias(字段名是 alias 不是 occurrence_alias)
# head_binding.kind == "projection";generated alias 形如 a__c0(_rewrite_dnf_aliases :801)
```

## evaluate + explain
```python
head = Rule.projection("person","color","age")        # rule.py:184-200(id=__factgraph_projection__<sha16>)
result = fg.eval.evaluate(expr, head=head, engine="native")   # 恰 1 positional,head= 必填(store.py:3174)
# native 默认不传 config;传 config= 报 "engine='native' does not consume SemanticsProfile"
result.count()/result[0]/result.first()/result.exists()       # evaluate_result.py:259-265
row = result[0]                                       # row.row_id "run_v1:<64>:<16>";row.bindings;row.kind
row.certainty                                         # native = Certainty(1.0,1.0,"boolean")
result.fingerprint.view_snapshot_digest               # completeness/闭世界锚(顶层 digest 属性已 deprecated,用 .fingerprint.*)
ex = row.explain()                                    # → Explanation(:270);status ∈ passed/failed/unsupported/invalid_request
# ex.failure_class ∈ no_matching_row/closed_head_false/stale_row/...;ex.evidence(EvidenceGraph);ex.narrate()
# 无叫 "completeness" 的字段;等价语义在 Explanation.status/failure_class + fingerprint.view_snapshot_digest
```

## engine fault 注入接缝(X01)
```python
from unittest.mock import patch
with patch("factgraph.sdk.store.evaluate_derivation_plans", side_effect=RuntimeError("fault")):  # store.py:3251
    fg.eval.evaluate(expr, head=head, engine="native")   # 抛;shipped 测试同款用法
# return_value=[] 可造 0 行;call_args.args[0] 是 DerivationEvaluateRequest(.engine/.plans)
```

## 关键坑
1. `PYTHONPATH=src` 硬要求;官方跑法 `python -m unittest`(无 conftest/pytest ini);harness 起进程须显式设 env + `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider`。
2. `:exists` 命名是 port 类型推断**唯一**依据(rule.py:576);漏写→port 变 value。
3. 同名 port 未 join → `_validate_rule_expr_head_foundation` 静态炸(evaluate 前,fault patch 不触发)。
4. `head=` 必须 `application.protocol.Rule`(非 sdk.dsl.Rule);两个同名 Rule 类是坑。
5. projection head 不比对 port_type,external/inline head 比对。
6. `row.explain()` 依赖父 result 存活(detached → DetachedRowError,evaluate_result.py:38);别拆出存。
7. `fg.close()` 只关自有 db;attach 路径 harness 自己 `db.close()`。
8. `FACTPY_WHERE_AST_VALIDATE=0` 是 ablation 唯一有意义旋钮(默认 1)。
