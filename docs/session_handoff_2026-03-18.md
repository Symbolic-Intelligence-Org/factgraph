# Session Handoff: 2026-03-18

这份文档用于让新的 session 快速恢复当前仓库状态。它是 handoff/reference，不替代 active blueprint、archived blueprint 或模块 docs。

## 1. 当前阶段结论

项目已到达一个明确的 cross-domain validation stable stopping point：

- `runtime + explain + audit` 中游 substrate 已完成多域、多 source-shape、多 evidence-pattern 验证
- 第一条 upstream vertical slice 也已被验证：
  - `structured source -> normalize/extract -> materialize -> rule -> explain`
- 所有当前已命名的 deferred gaps 仍然全部是 deferred
  - 没有一个被具体场景逼成 immediate blocker

这意味着下一次 session 默认不应再继续同层 synthetic walkthrough，也不应在没有 concrete trigger 的情况下直接开启 capability blueprint。

## 2. 已验证 Coverage

### 2.1 Domains

已被 walkthrough 直接压过的 domain：

- ECSS / compliance
- AML / suspicious-account review and trigger
- process safety / shutdown command
- clinical deterioration / weak-signal escalation

### 2.2 Source Shapes

已被 walkthrough 直接压过的上游 source/evidence 形状：

- structured feed
- structured form-like document
- single-note free-text narrative
- correlated multi-note narrative
- conflicting multi-note narrative

### 2.3 Evidence Patterns

已被 walkthrough 直接压过的 evidence pattern：

- deterministic field normalization
- deterministic free-text extraction
- best-effort interpretation with explicit meta
- explicit skip/background retention
- pre-materialized helper outputs
- multi-entity fan-out
- partial combination / weak-signal count-threshold placeholder
- must-act readability
- non-conflicting multi-note aggregation
- conflicting evidence retention without automated resolution

## 3. Explain / Audit Substrate 状态

当前 explain delivery 栈已经稳定：

- raw explain
- summary
- narrative
- NL explain
- audit/static proof-entry

关键实现真相入口仍在模块 docs：

- [01_architecture.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
- [03_runtime_queries_views.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- [01_overview.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/01_overview.md)

当前结论不是“还缺 explain substrate”，而是：

- 现有 substrate 的适用范围比一开始预期更宽
- 继续用同层 walkthrough 压它，边际信息已明显下降

## 4. 已完成的关键蓝图线

### 4.1 Explain / Delivery Closure

已完成并归档：

- `runtime-structured-json-explain-api`
- `runtime-rule-run-explain-summary-api`
- `audit-rule-run-explain-summary-export`
- `rule-run-explain-narrative`
- `rule-run-explain-narrative-parity`
- `rule-run-nl-explain`

这些切片共同收口了：

- raw contract
- summary contract
- narrative contract
- NL explain
- audit/static proof-entry

### 4.2 Scenario / Walkthrough Regressions

当前已归档 walkthrough regressions：

- clinical weak-signal
- AML aggregation materialization
- AML transaction-feed materialization
- process-safety shutdown
- form-document extraction
- single-note narrative extraction
- correlated multi-note review
- conflicting multi-note evidence

### 4.3 Anchoring / Analysis Blueprints

当前已归档的关键分析线包括：

- clinical deterioration uncertainty anchoring
- AML transaction-feed normalization anchoring
- document-evidence extraction anchoring
- free-text narrative evidence anchoring
- multi-note narrative synthesis anchoring
- conflicting narrative evidence anchoring

这些分析线的共同结论是：

- 只有在 walkthrough 真的暴露 blocker 时，才值得打开下一条 capability blueprint

## 5. Deferred Gaps 当前状态

以下 gap 仍全部存在，但都 **没有 concrete trigger**：

### 5.1 `T2 sequence/state semantics`

仍 deferred。只有当场景要求：

- in-rule event aggregation
- state propagation / transition semantics
- retraction / evolving state
- 或 ordering 本身进入 rule semantics

时才值得重新打开。

### 5.2 Judgment / Obligation Contract

仍 deferred。只有当消费者需要：

- lifecycle-differentiated result kinds
- first-class obligation/query surface
- 或系统必须显式解释“为何做出该 judgment”

时才值得重新打开。

### 5.3 `U2` Weak-Signal Uncertainty

仍 deferred。clinical weak-signal walkthrough 已证明：

- count/threshold placeholder 在 first-round 里仍然站得住

只有当场景必须解释：

- individually weak signals 如何以非阈值方式合成
- extraction or signal-combination confidence 本身如何参与结论

时才值得重新打开。

### 5.4 Snippet/Span Provenance

仍 deferred。到 conflicting multi-note 为止：

- note-level provenance 仍足够诚实

只有当 source object 足够长、足够密集，导致：

- `note_id` / `document_id` 已不足以定位原文依据

时才值得重新打开。

### 5.5 Extraction Uncertainty

仍 deferred。到当前为止：

- deterministic mapping
- best-effort mapping + explicit meta
- explicit skip

都还足够。

只有当系统必须表达：

- extraction step 本身的 graded confidence
- 或 conflicting/ambiguous extraction 不能再以 retain-or-skip 诚实表达

时才值得重新打开。

### 5.6 Source-Linkage Contract

仍 deferred。到当前为止：

- source identity in terms
- assertion detail drill-down
- multi-note per-source inspection

都还足够。

只有当 reader 无法从现有 surfaces 手动恢复 source relationships 时，才值得重新打开。

## 6. Reopening Trigger Conditions

下一次 session 只有在出现下面这类输入时，才优先重新打开 deferred gaps：

- 真实或半真实 source package，而不是 synthetic fixture
- 长文档或多页材料，需要比 `document_id` / `note_id` 更细的 provenance
- conflicting evidence 需要系统主动做 resolution，而不是 retention
- extraction 结果本身需要 graded confidence / uncertainty，而不是 deterministic/best-effort/skip
- ordering / progression 本身成为规则语义，而不是仅仅作为 metadata

如果没有这些 trigger，默认不重新打开：

- `T2`
- judgment/obligation
- `U2`
- snippet/span provenance
- extraction uncertainty
- source-linkage

## 7. 下一步默认方向

默认不再继续 synthetic walkthrough。

如果继续，优先级应是：

1. 真实或半真实 source package pressure
   - 例如真实样式 document bundle / note bundle / mixed-source ingest case
2. 若没有新的真实压力源
   - 停在当前阶段位置即可

默认 **不** 直接开启 capability blueprint。因为当前所有 gap 仍无 concrete trigger。

## 8. 不要重新开启的旧争议

新 session 默认不需要重新讨论这些点：

- explain substrate 第一阶段是否还没闭环
- 是否应该继续加更多 explain delivery layer
- 是否应该先开 `T2` / judgment / `U2`
- 是否应该因为“也许将来会需要”而先做 provenance/linkage/uncertainty contract

这些问题当前都已有一致结论：

- substrate 已被足够多的场景压过
- deferred gaps 仍然只是 deferred，不是 blocker
- 没有 trigger 就不开 capability blueprint

## 9. 验证基线

当前最近一次完整回归命令：

```bash
PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1
```

当前结果：

- `74 tests` 全通过

## 10. 入口建议

如果下一次 session 用户意图不明确，优先按以下顺序判断：

1. 若用户要继续扩系统能力：
   - 先问是否有真实/半真实 source pressure
2. 若没有新的真实压力源：
   - 默认停在当前阶段，不再继续 synthetic walkthrough
3. 若用户直接提某个 deferred gap：
   - 先确认是否已有 concrete trigger；若没有，不应直接进入 capability design
