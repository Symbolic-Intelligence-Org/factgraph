# Souffle Adapter 总览（factpy_kernel）

- 范围：`src/factpy_kernel/adapters/souffle`
- 最后更新：2026-03-23
- 目标读者：需要理解 Souffle 导出、执行、查询编译链路的开发者

## 1. 模块职责

`adapters.souffle` 是外部引擎适配层，负责把 `Store`/where IR 转换为 Souffle 可执行程序与输出。

它主要负责：

- `Store.evaluate(mode="souffle")` 的引擎评估实现
- inference/audit package 导出（`manifest + facts + rules + policy + outputs`）
- package 执行（支持 `souffle` 与 `noop`）
- where IR 编译为查询关系（query relation）
- view 规则生成与 predicate 名称归一化

它不负责：

- core 语义定义（规则语义、ledger 语义、schema canonical）
- runtime session 生命周期编排（service 层职责）
- Deontic 语义执行（当前未在本适配器内实现）

## 2. 当前模块结构

- `__init__.py`
  - import 时调用 `register_engine_evaluator(evaluate_store_engine, "souffle")`
- `engine_eval.py`
  - `evaluate_store_engine(...)`，`Store.evaluate(mode="souffle")` 的入口
- `package.py`
  - `ExportOptions`、`export_package(...)`
- `runner.py`
  - `run_package(...)`、`find_souffle_binary(...)`
- `provenance.py`
  - `SouffleProofNodeV0`、`SouffleProofTreeV0`
  - `parse_souffle_proof_json(...)`
  - `run_provenance_explain(...)`
- `where_compile.py`
  - `compile_where_to_query_dl(...)`、`query_rel_for_where(...)`
- `souffle_view_gen.py`
  - `generate_view_dl(...)`
- `pred_norm.py`
  - `normalize_pred_id(...)` / `denormalize_engine_pred(...)`
- `tsv_v1.py`
  - TSV/facts 的读写编码

## 3. 与 core 的边界

`core` 通过注册机制调用引擎，不静态依赖具体适配器：

1. 导入 `factpy_kernel.adapters.souffle`
2. `__init__` 注册 `souffle` evaluator
3. `Store.evaluate(mode="souffle")` 进入该适配器实现

这个边界允许：

- core 独立测试
- 多引擎并存（当前已有 `souffle` 与 `problog`）
- 引擎实现按 mode 解耦切换

补充边界：

- `Souffle` 仍然只承担结构执行器职责。
- 当前 `src/factpy_kernel/core/annotation/` 中的 prototype annotation kernel 不属于 adapter 本身的一部分。
- benchmark / prototype 阶段允许出现“`Souffle` 结构结果 + core 内部 annotation helper”这种组合，但这不改变正式 `Store.evaluate(mode="souffle")` 仍是单引擎 adapter 契约这一事实。

## 4. 典型工作流

### 4.1 Souffle 引擎评估

`evaluate_store_engine(...)` 的主流程：

1. 校验目标/变量绑定（entity head 或 fact head）
2. `export_package(...)` 导出临时 package（包含 query where）
3. `run_package(..., engine="souffle")` 执行
4. 读取 `outputs/<query_rel>.out.facts` 解析 bindings
5. 转换为 `CandidateSet`（entity/fact candidate）

注意：`engine_eval` 会强校验 `run_manifest.engine_mode == "souffle"`；如果 runner 因缺少二进制回退到 `noop`，会报错而不是静默成功。

explainability 补充：

- 当前 Souffle evaluate 分两条 explainability 路径：
  - **partial witness path**
    - 当 where 含有 top-level `pred` atoms 时，adapter 会导出 `_w` witness 变体 view，并让 query output 额外穿透 witness 列
    - engine_eval 会按 binding 聚合这些 witness 列，构建 `SupportArtifact` 的受限子集并注册到 `Store`
    - 对外 `support_kind="souffle_witness_v1"`
    - 当前承诺的字段范围：
      - `binding`
      - `pred_witnesses`
      - minimal `non_fact_steps`
      - `rule_ref_edges=[]`
    - 同一 final binding 若跨多个 OR branch 都有 witness row，adapter 侧采用 `source-order wins`
    - 这不是 Soufflé 官方 provenance proof tree，而是 adapter-level witness sidecar via Datalog rewriting
  - **degraded path**
    - 若当前 query 无法走 partial witness，candidate 继续显式标记：
      - `support_kind="engine_no_witness_v1"`
      - `support_digest="sha256:000...0"`（兼容占位符）
    - service `explain_ref(kind="candidate")` 对这类 candidate 返回 `ok=true` + `witness_status="degraded"`
- first-round consumer surface 仍收窄在 runtime：
  - runtime `explain` / `explain-tree` 接受 `souffle_witness_v1`
  - audit/static 对 `souffle_witness_v1` 继续 deferred

### 4.2 Package 导出

`export_package(...)` 会产出（`export_version=v2`）：

- `schema/schema_ir.json`
- `policy/policy_ir.json` 与 `policy/policy_rules.dl`
- `facts/*.facts`（claim/claim_arg/meta*/revokes）
- `rules/view.dl` 与 `rules/idb.dl`
- `manifest.json`（含 `outputs_map`、digests、entrypoints）
- `audit/*`（仅 `package_kind="audit"` 时）

### 4.3 Package 执行

`run_package(...)` 支持：

- `engine="souffle"`：调用 Souffle CLI
- `engine="noop"`：仅生成空/占位输出

Souffle 二进制查找顺序：

1. 环境变量 `SOUFFLE_BIN`
2. `PATH` 中的 `souffle`

### 4.4 Provenance Helper（V0, adapter-local）

当前 `adapters.souffle` 还提供一个 **adapter-local provenance helper**：

- `run_provenance_explain(...)`
  - 独立调用 Souffle `-t explain`
  - 通过 stdin 发送 `format json` / `explain ...`
  - 解析为 `SouffleProofTreeV0`
- `run_package_provenance(...)`
  - 接收已导出的 factpy package 目录
  - 复用 package manifest 中的 `view/idb/policy` 组装逻辑
  - 自动定位 Souffle binary 后调用 `run_provenance_explain(...)`
  - 对 flat query package 直接可用；对含 `ruleref` 的 composed query package，导出时需要提供 `query.registry_root`
- `parse_souffle_proof_json(...)`
  - 解析 Souffle JSON proof stream
  - depth-limited `subproof ...` 截断节点会保留为 `node_type="subproof"` 的叶子，而不是报错
- `souffle_proof_tree_to_evidence_graph(...)`
  - 直接消费 `SouffleProofTreeV0`
  - 产出 `EvidenceGraph(engine="souffle", layout_hint="tree", support_kind="souffle_witness_v1")`
  - 当前映射口径：
    - root = `conclusion`
    - `axiom` = `seed`
    - `derived` / `negation` / `subproof` = `premise`
    - child node 通过 `edge_kind="supports"` 指向 parent node
  - `rule-number` / `rule text` 保留在 `rule_label` + `engine_meta`

边界：

- 不修改 `run_package(...)` 的签名或返回值
- 不进入 `core/` 公共 contract
- 不引入新的 service endpoint
- 不写入新的 audit durable artifact
- 不替换当前 `candidate_evidence_tree`

这条路径当前只用于：

- 真实 ECSS rule / provenance shape 验证
- adapter-local proof consumption spike

它不是通用 `ProofNode`，也不是已经进入 runtime/audit/static 正式消费链的稳定 contract。

## 5. where 编译与校验口径

`where_compile.py` 支持把 where 子集编译为 query relation，并默认走 AST gate（`FACTPY_WHERE_AST_VALIDATE`）：

- 支持原子：`pred/eq/in/ne/gt/ge/lt/le/not/add/sub/neg/addc/mulc`
- 支持 AND 与 OR-of-AND 结构
- query relation 名为 `query__<sha256前8位>`（协议约束）
- not body 与数据流约束由 validator + 编译期检查共同保证
- 当 query where 含 `ruleref` 时：
  - exporter 可通过 `query.registry_root` 加载 registry 中的 exposed rules
  - compiler 会递归重写 `ruleref` 为 adapter-local internal relations，并把这些 relation 一起写入同一个 `rules/idb.dl`
  - flat query 的输出形状保持不变

## 6. 当前限制

- 依赖外部 Souffle CLI；缺失时 runner 会回退 `noop`
- `engine_eval` 不接受 `noop` 结果作为有效求值
- 当前适配目标是 query/derivation 执行，不是 Deontic 规范推理引擎
- 当前不承诺 full native parity；Souffle first-round 只输出 partial witness，而不是完整 rule-chain / recursive proof
- Souffle provenance helper 当前仍是 adapter-local V0：
  - 只验证 recursive chain / negation / rule-number capture
  - 已可转换到 `audit.EvidenceGraph`，但还没有接入 runtime/audit/static 正式交付链
  - 不替代现有 `candidate_evidence_tree` / witness pipeline
