# SDK 中英一致性检查表

更新时间：2026-02-27  
基线：`src/factpy_kernel/sdk/docs`

本文件用于跟踪中文与英文文档的一致性，避免行为说明漂移。

---

## 1. 检查范围

- 主指南：
  - `00_user_guide.md`
  - `00_user_guide.en.md`
- 专项文档：
  - `01_alignment_matrix(.en).md`
  - `02_readwrite_and_ingest(.en).md`
  - `03_rules_and_derivations(.en).md`
  - `04_api_surface(.en).md`

---

## 2. 主指南章节对齐（00）

| 章节 | 中文 | 英文 | 对齐状态 | 备注 |
|---|---|---|---|---|
| 1 | 安装与初始化 | Setup and Initialization | 已对齐 | 结构一致 |
| 2 | Schema 定义 | Schema Definition | 已对齐 | 参数与边界一致 |
| 3 | 写入：`sdk.batch` | Writing with `sdk.batch` | 已对齐 | 语义一致，英文更精简 |
| 4 | 读取：`get/find` | Reading with `get/find` | 已对齐 | 语义一致，英文更精简 |
| 5 | 编辑：`sdk.edit` | Editing with `sdk.edit` | 已对齐 | 语义一致 |
| 6 | 导入：`sdk.ingest` | External Import with `sdk.ingest` | 已对齐 | 语义一致 |
| 7 | 规则与推导 | Rules and Derivations | 部分对齐 | 英文将 `accept` 参数边界合并在 7.3，中文是独立 7.4 |
| 8 | Provenance 校验 | Provenance Validation | 已对齐 | 扁平 dict 语义一致 |
| 9 | 写入入口选择 | Which Write API | 已对齐 | 决策表一致 |
| 10 | 错误速查 | Error Quick Reference | 已对齐 | 分层与排查顺序一致 |
| 11 | Registry 发布与读取 | Registry Publish and Read | 已对齐 | 构造/注册/读取/API 边界一致 |
| 12 | API Surface 补充（高级） | API Surface Additions (Advanced) | 已对齐 | 低层直写/compiled 直通/package 能力一致 |

结论：
- 主指南“行为语义”已对齐。
- 主要差异在“信息密度”：英文版有意更短、更索引化。

---

## 3. 专项文档对齐（01-04）

| 文档组 | 对齐状态 | 备注 |
|---|---|---|
| `01_alignment_matrix` | 已对齐 | 关键边界与延期项一致 |
| `02_readwrite_and_ingest` | 已对齐 | 英文为压缩版参考 |
| `03_rules_and_derivations` | 已对齐 | 英文已覆盖关键限制与运行路径 |
| `04_api_surface` | 已对齐 | 导出面与方法索引一致 |

---

## 4. 术语一致性

已统一：
- `canonical ref` = canonical `idref_v1` token（字符串）
- `Stable Contract` ↔ `稳定合约`
- `Current Behavior` ↔ `当前行为`
- `Planned` ↔ `规划中`
- `collect-and-stop`（ingest 诊断 error 时整批不写）

---

## 5. 待同步清单（下一轮可做）

1. 英文主指南第 7 章可拆分出独立 `accept(...)` 小节，以 1:1 对齐中文结构。  
2. 英文主指南可补充更多“完整代码片段”版本（当前偏精简）。  
3. README 可补一条“中英同步规则”英文说明（当前使用约定为中文描述）。

---

## 6. 维护规则（建议）

每次 SDK 行为变更时：
1. 先改中文主指南（事实源）。
2. 同 PR 更新英文主指南对应章节。
3. 更新本检查表中的“待同步清单”。
4. 在 PR 描述里标注“CN/EN docs synced”。
