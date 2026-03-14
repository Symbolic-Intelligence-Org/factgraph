# FactPy Authoring 文档

本目录记录 `src/factpy_kernel/authoring` 的当前实现口径，面向需要理解 authoring 预检、发布与 registry 工作流的开发者。

## 当前文档

- `src/factpy_kernel/authoring/docs/01_overview.md`
  - authoring 模块职责、公共入口、registry 文件布局、与 SDK/service/core 的边界。

## 使用约定

- 本目录文档以当前实现行为为准，不是独立设计草案。
- 新增/调整 authoring 公共入口时，应同步更新本目录文档与相关测试。
- 若 `authoring` 内部继续做第二阶段收口，优先更新 `01_overview.md` 中的“推荐入口”与“兼容层”部分。
- 当前声明元数据 contract 已统一到 `version / description / tags`：
  - schema DSL 走 `Entity.Meta`
  - rule / derivation DSL 走顶层参数
  - 这些字段属于 authoring 资产元数据，不参与 runtime 语义
