# ECSS 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/ecss`
- 最后更新：2026-03-18
- 目标读者：需要在 `authoring` / `sdk` / `audit` 之间共享 ECSS preset 的开发者

## 1. 模块职责

`ecss` 是 **shared domain-preset layer**。它承载跨层共享的 ECSS helper，避免把 domain preset owner 放进 `audit` 消费层或 `sdk` facade 层。

它当前负责：

- ECSS VCD predicate 常量
- ECSS VCD schema preset 定义
- ECSS temporal predicate 常量
- ECSS temporal schema preset 定义
- ECSS uncertainty predicate 常量
- ECSS uncertainty schema preset 定义
- `schema_ir` 扩展 helper

它不负责：

- audit matrix row 组装
- runtime 写入协议
- registry publish/apply 工作流
- live service endpoint

## 2. 当前公共入口

- `ECSS_REQUIREMENT_PRED_ID`
- `ECSS_VERIFICATION_METHOD_PRED_ID`
- `ECSS_COMPLIANCE_STATUS_PRED_ID`
- `ECSS_REQUIREMENT_RID_PRED_ID`
- `ECSS_REVIEW_MILESTONE_PRED_ID`
- `ECSS_VCD_PRED_IDS`
- `ecss_vcd_predicates(...)`
- `extend_schema_ir_with_ecss_vcd_predicates(...)`
- `ECSS_OBLIGATION_TIMESTAMP_PRED_ID`
- `ECSS_WINDOW_START_PRED_ID`
- `ECSS_WINDOW_END_PRED_ID`
- `ECSS_INTERVAL_START_PRED_ID`
- `ECSS_INTERVAL_END_PRED_ID`
- `ECSS_TEMPORAL_PRED_IDS`
- `ecss_temporal_predicates(...)`
- `extend_schema_ir_with_ecss_temporal_predicates(...)`
- `ECSS_COLLISION_PROBABILITY_PPM_PRED_ID`
- `ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID`
- `ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID`
- `ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID`
- `ECSS_UNCERTAINTY_PRED_IDS`
- `ecss_uncertainty_predicates(...)`
- `extend_schema_ir_with_ecss_uncertainty_predicates(...)`

对应模块：

- `vcd.py`
- `temporal.py`
- `uncertainty.py`

## 3. 典型工作流

### 3.1 扩展 schema

1. 调用方先获得已有 `schema_ir`
2. 调用 `extend_schema_ir_with_ecss_vcd_predicates(schema_ir)`
3. 得到带有 requirement/compliance predicates 的新 schema

### 3.2 被其他层消费

- `audit`
  - 复用同一组 predicate ID 与 schema helper，继续做 compliance matrix query / DTO / static UI
- `sdk`
  - 在 `factpy_kernel.sdk.ecss` 子模块里提供更贴近写侧的 convenience wrapper
- `authoring`
  - 可在 schema preset / registry 工作流中消费 shared helper，但不拥有这组 domain preset

### 3.3 Scenario A 时间语义第一轮

- `temporal.py` 当前只承载 `T1` temporal predicate preset：
  - `obligation_timestamp`
  - `window_start` / `window_end`
  - `interval_start` / `interval_end`
- 这些 predicate 的时间参数统一使用 schema tag `"time"`，即 `int` epoch 纳秒时间戳
- 它们用于让 deadline / window / interval relation 复用已有比较语法表达，不意味着 `ecss` 模块本身拥有 runtime temporal semantics

### 3.4 Scenario A 不确定性第一轮

- `uncertainty.py` 当前只承载 threshold-bearing probability lane：
  - `collision_probability_ppm`
  - `collision_probability_threshold_ppm`
  - `disposal_success_probability_ppm`
  - `disposal_success_threshold_ppm`
- 这些 predicate 的数值参数统一使用 schema tag `"int"`，口径为 `ppm`（parts per million）
- 它们用于让 Scenario A 的概率阈值判断复用已有 `<=` / `>=` 比较语法，不意味着 `ecss` 模块本身拥有通用 uncertainty semantics

## 4. 与其他层的边界

- `audit`
  - `audit` 是 requirement/compliance matrix 的消费层；matrix row 组装逻辑仍留在 `audit.compliance`
- `sdk`
  - `sdk` 提供更友好的 authoring helper，但不应重新声明 canonical preset
- `authoring`
  - `authoring` 仍是 schema compile / registry workflow owner，不承担 ECSS preset 的长期 owner 角色
- `core` / `service`
  - runtime temporal checks 仍依赖既有比较链与 explain contract；`ecss` 不拥有这些通用执行语义
  - runtime uncertainty threshold checks 同样依赖既有比较链与 explain contract；`ecss` 只拥有 shared preset

## 5. 当前限制

- 当前只有 `Scenario B` 所需的最小 VCD/compliance preset，以及 `Scenario A` 第一轮 `T1` temporal preset 与第一轮 uncertainty preset
- 还没有更强的 ESSB debris-mitigation 语义、state propagation 或 uncertainty semantics preset
- 这组 helper 只负责 schema/predicate shape，不核实标准原文
