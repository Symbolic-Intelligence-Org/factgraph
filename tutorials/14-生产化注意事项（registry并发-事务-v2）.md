# 14. 生产化注意事项（registry并发-事务-v2）

本篇不是功能教程，而是面向部署/运维的 **边界说明**。目标是避免把当前 MVP（单机可用）误当成生产级方案。

---

## 1) 当前 registry 能力边界（`FileAuthoringRegistry`）

当前 `registry_fs` 适合：

- 单机 / 单进程开发
- 教程、PoC、CI 验证
- authoring workflow dry-run / apply-execute 验证

当前 **不保证**：

- 多进程并发写入安全
- 原子事务（跨多个 action 的真正 rollback）
- 崩溃后自动恢复/修复

建议：

- 生产环境暂时只允许一个写入进程
- 把 registry 目录放在可靠磁盘，不要放临时目录
- 对 `apply_request_id` 做调用方去重（避免误重试）

---

## 2) 事务策略现状（v1 / v2）

### `best_effort_no_rollback_v1`（当前默认）

- 允许部分成功（`partial_apply=true`）
- 不做 rollback / compensation
- prevalidate 失败时不会开始写入

适合：

- 开发环境
- 调试 authoring payload
- 对失败可人工处理的场景

### `prevalidate_no_partial_strict_v2`（当前最小可执行版）

> 注意：当前是 **最小可执行版**，不是完整严格事务实现。

- 需要显式指定 `transaction_policy`
- 幂等与 replay/conflict 语义与 v1 保持一致
- “strict” 语义仍在持续收口中（请结合 `transaction` 字段与 `execution_path_label` 观察）

建议：

- 在生产环境试用前，先在 staging 跑失败路径回归
- 必须保留 `authoring_apply_events.jsonl` 与审计站点

---

## 3) 并发与原子性（当前未实现）

当前 file registry 未实现：

- 文件锁（process lock）
- CAS（compare-and-set）写入
- 原子 manifest 更新（tmp + fsync + rename）

因此不建议：

- 多个 `apply-execute` 进程同时写同一 registry
- 用共享网络盘同时写入（除非你自己加外层锁）

---

## 4) 生产前检查清单（最小）

在把某个环境作为“共享 authoring registry”之前，至少确认：

- [ ] 只有一个写入进程/服务
- [ ] `apply_request_id` 由调用方稳定生成（可重复重放）
- [ ] 定期执行 `registry-list --kind apply_run_ids`
- [ ] `registry-show --kind apply-run --id <req>` 可读并包含 `transaction` / `idempotency`
- [ ] 已启用 audit package 导出与静态审计页面（用于追踪失败路径）

---

## 5) 推荐运维路径（当前阶段）

1. **Authoring apply**
   - `python -m factpy_kernel.authoring.cli apply-execute ...`
2. **确认 apply run**
   - `registry-list --kind apply_run_ids`
   - `registry-show --kind apply-run --id <req>`
3. **导出并查看 audit site**
   - 生成 audit package
   - `render_audit_static_site(...)`
   - 打开 `authoring_apply_runs/<req>.html`

---

## 6) 后续升级方向（spec-only）

后续如果要进入生产化，可按顺序考虑：

1. `registry_fs` 文件锁 + 原子写
2. `transaction_policy` v2 严格语义继续收口
3. registry 一致性检查命令（verify/doctor）
4. 替换后端（SQLite/LMDB/Postgres）并保留同一 authoring API

---

## 7) 与教程的关系

- 若你是第一次使用，请先看：
  - [教程 08（团队内 Onboarding）](./08-团队内-Onboarding-清单.md)
  - [教程 09（CLI 命令速查）](./09-CLI-命令速查.md)
  - [教程 10（排障手册）](./10-排障手册（CLI-Registry-Audit）.md)
- 若你要 Python 直接定义实体，请看：
  - [教程 15（SDK 快速开始）](./15-SDK-快速开始（Python 直接定义）.md)
