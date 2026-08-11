# Fixture / Golden schema v0(Step 2 冻结件)

**EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT**

每个 cell 两个文件:`fixtures/<CELL>.json`(输入面)与 `golden/<CELL>.json`(oracle 面)。
schema 权威为 scoped 蓝图 §5.4–§5.9;本文件只是其 JSON 化,冲突时以蓝图为准。

## fixtures/<CELL>.json

```json
{
  "cell_id": "Q01",
  "model_scored": false,
  "engine_invocations_pinned": 1,          // oracle-pinned 0 或 1(§6.1)
  "candidate_semantics": null,             // 仅 SC01-A/B:"branch_scoped"|"reject_on_partial"
  "fixture_cutoff": null,                  // 仅 Q05/E03:{"kind":"post_engine_truncate_all"|"raw_result_double","mark":"incomplete"}
  "engine_fault_injection": false,         // 仅 X01
  "profile": {                             // AssignedProfileSnapshotV0(§5.4.1)语义内容;digests 由 manifest 工具计算
    "profile_ref": "qp.q01.v0",
    "task_kind": "query",                  // query | validation;server-owned
    "policy": { "policy_ref": "...", "ast": <PolicyAstV0> },
    "slot_descriptors": [ {"slot":"person_ref","type":"entity_ref","entity_type":"person"} ],
    "bind_templates": [ {"path":"m.person","slot":"person_ref"} ],
    "query_mode": "rows",                  // rows | exists
    "select_templates": [ {"alias":"team","path":"m.team"} ],
    "expectation_template": null,          // validation 恰一;{"kind":"exists"|"contains_row"|<unsupported>,"row_template":{alias:slot},"set_mode":...}
    "field_path_grants": [ "m.person.age" ]
  },
  "world": {
    "entity_types": [ {"name":"person","identity":"name","fields":[{"name":"age","type":"int"}]} ],
    "facts": [ ["member","alice","red"], ["age","alice",30] ],   // 谓词元组;harness 映射到 shipped API
    "rules": [ {"rule_id":"member","ports":["person","team"],"from_facts":"member"} ]
  },
  "invocation": { "slots": {"person_ref": "alice"},
                  "extra_fields": {} }     // 仅 A01-AUTH:注入的 forbidden fields 原样列出
}
```

`PolicyAstV0`(§6.3 v0 算子闭包):
```json
{ "all": [ {"occurrence":{"rule_ref":"member","alias":"m"}},
           {"compare":{"left":{"path":"m.person.age"},"op":">","right":{"value":26}}},
           {"any":[ ... ]},
           {"unify":{"left":{"path":"a.x"},"right":{"path":"b.x"}}} ] }
```

## golden/<CELL>.json — 八工件 oracle(§5.6)

```json
{
  "cell_id": "Q01",
  "ingress":   { "status": "accepted",                  // accepted | rejected_unknown_field | rejected_type | ...
                 "attempted_authority_fields": [] },
  "resolution":{ "status": "resolved",                  // resolved | AMBIGUOUS_IDENTITY | PIN_MISMATCH | ...(typed,engine 前)
                 "diagnostics": [] },
  "binding_path": { "bindings": [{"path":"m.person","term":{"entity":"person","id":"alice"}}],
                    "selections": [{"alias":"team","path":"m.team"}] },
  "lineage":   { "assertions": [                        // 逐条具名(§5.8 不变量子集,per-cell)
                   "every_authored_node_mapped", "every_lowered_node_attributed",
                   "synthetic_head_projection_only", "..." ] },
  "result":    { "kind": "rows",                        // rows | exists_summary | typed_failure
                 "rows": [ {"team":"red"} ], "row_count": 1,
                 "completeness": "complete", "truncated": false,
                 "query_summary": null,                 // {"status":true|false|"underdetermined"}
                 "failure": null },                     // {"code":"EXECUTION_ENGINE_FAULT",...}
  "expectation": null,                                  // {"kind":"contains_row","status":"satisfied","matched_row_count":1} | status=unsupported+diagnostic
  "explain_target": { "anchor": "row",                  // row | query_summary | expectation | none
                      "content_class": "native_evidence_graph" },  // native_evidence_graph | structured_diagnostic | none
  "agent_interpretation": { "applicable": false },      // model cells:{"applicable":true,"success_shape":"...","forbidden":[...]}
  "forbidden_interpretation_oracle": null               // 仅 Q04/Q05/E03/X01:{"name":"...","rejects":[<合成错误候选>...]}
}
```

约束(蓝图原文优先):`task_kind=query` ⇒ `expectation=null`;`validation` ⇒ 恰一 expectation。
complete+zero 才允许 `exists=false`/`not_satisfied`;incomplete/unknown+zero 只能 `underdetermined`。
zero-row Explain 用 summary/expectation anchor,禁 implicit first row。
NAV02/SC12-P/AC21/A01-AMB/A01-AUTH 断言 `engine_invocations_pinned=0`。
数值 digest(profile/policy/tool_schema/result_contract/query)由 manifest 工具在冻结时统一计算写入 manifest,fixture 文件内不手写。

## Step 2 冻结批准的 schema 扩展(裁决记录)

以下扩展在 Step 2 起草期由合同原文(§5.4/§5.6/§5.9)推出、SCHEMA.md 初稿欠列,现予批准。均为文档补全,非 scope/semantic deviation:

1. **`result.kind` 枚举**扩为 `rows | exists_summary | typed_failure | static_validation`。`static_validation` 用于 0-engine 的发布期/编目期校验 cell(NAV02/SC12-32/SC12-P/AC21),其 `result.diagnostics[]` 承载具名 typed diagnostics(NAV02 五条、SC12/AC21 各一);canonical 形状与 `typed_failure` 同:`rows=row_count=completeness=truncated=null`(oracle review MINOR-2 后统一)。
2. **`typed_failure` 形状**:`rows=row_count=completeness=truncated=null`(不是 `[]`/`complete`)——§5.4.2「failure != zero rows」的忠实读法,防止与 complete-zero 混淆。`failure` 承载 `{code,...}`;SC12-P/AC21 额外内嵌 `owner/stage`。
3. **stage-not-reached 状态名** = `not_reached`,用于前置失败使某阶段未运行时的 `ingress`/`resolution.status`(SC12/AC21/A01-AUTH 的 resolution);另批准 `resolution.status="static_validation_only"`(NAV02:静态编目校验 cell 无逐请求解析阶段,oracle review MINOR-3)。
4. **`profile_ref` 前缀**不强制统一:`qp.*`(query profile)与 `vp.*`(validation profile)均合法;身份由 `profile_digest`(按内容算)承载,前缀仅可读性。
5. **result-shape invariant 经 lineage.assertions 通道表达**:golden schema 无 per-row-anchor / 无注释字段,故 `distinct_run_local_row_anchor_per_row`(Q02)与 `self_row_included_correct_v0_semantics_no_inequality_operator`(P01)等**结果层**不变量登记在 `lineage.assertions` 内;harness comparator 按前缀/命名把它们分派到 result 层校验,不当作 compile lineage。**Step 3 harness 义务(oracle review MINOR-4)**:必须在结果层真实校验(anchor 逐行互异、self-row 确实含入),不得把断言字符串当 compile-lineage 盖章通过。
5a. **NAV02 "ambiguous" 探针语义澄清(MINOR-1)**:该探针机制为不可解析的基 alias(`x.person` → `PATH_UNRESOLVED_ALIAS`),即"ambiguous"在此=路径无法唯一落到已声明 occurrence,非身份多候选歧义(后者由 A01-AMB 的 `AMBIGUOUS_IDENTITY` 覆盖);Step 3 按此语义实现,不另造 ambiguous-path code。
5b. **NAV02 子探针 digest(MINOR-5)**:五个子探针的 mini policy 不单独 digest,由 `fixture_digest` 整体覆盖——记录为已知覆盖方式,非缺口。
6. **entity_ref 按值身份的解析**:identity-by-value 的 entity_ref(如 team_name 的 `green`),即使世界中无任何成员事实,resolver 也判为 `resolved`(已知但无成员),空由 `complete + zero rows` 表达(Q04/E02/E04 依赖此裁决)。identity-by-lookup 的实体(person)未命中才是 resolution 失败。
7. **0-engine cell 的 batch 世界扩展**:NAV02 的 any-branch-unbound 探针需 `age_rule` occurrence 可解析方能产出 `NAVIGATION_BRANCH_UNBOUND`(否则更早死于 unknown-rule),故 NAV02 世界在 W1 之上加一条 `age_rule`;member 四元组与 team_name 类型保持 W1 字节一致。SC01/SC12 世界为标量端口世界(`entity_types=[]`),harness fact-mapping 须接受。
8. **profile 扩展键**(如 A01-AMB 的 `resolver_identity_matching`)参与 `profile_digest` 计算(manifest 工具对整个 profile 对象哈希)。
