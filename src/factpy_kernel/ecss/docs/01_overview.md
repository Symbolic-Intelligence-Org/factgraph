# ECSS 模块总览（factpy_kernel）

- 范围：`src/factpy_kernel/ecss`
- 最后更新：2026-03-18
- 目标读者：需要在 `authoring` / `sdk` / `audit` 之间共享 ECSS preset 的开发者

## 1. 模块职责

`ecss` 是 **shared domain-preset layer**。它承载跨层共享的 ECSS helper，避免把 domain preset owner 放进 `audit` 消费层或 `sdk` facade 层。

它当前负责：

- ECSS VCD predicate 常量
- ECSS VCD schema preset 定义
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

对应模块：

- `vcd.py`

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

## 4. 与其他层的边界

- `audit`
  - `audit` 是 requirement/compliance matrix 的消费层；matrix row 组装逻辑仍留在 `audit.compliance`
- `sdk`
  - `sdk` 提供更友好的 authoring helper，但不应重新声明 canonical preset
- `authoring`
  - `authoring` 仍是 schema compile / registry workflow owner，不承担 ECSS preset 的长期 owner 角色

## 5. 当前限制

- 当前只有 `Scenario B` 所需的最小 VCD/compliance preset
- 还没有 ESSB debris-mitigation、temporal semantics、uncertainty semantics 相关 preset
- 这组 helper 只负责 schema/predicate shape，不核实标准原文
