# Audit Log: Extraction Product API

## 2026-04-13 — draft

### Trigger

Benchmark 完成后两个问题浮出:
1. 模型切换需要改源码(hardcoded `gpt-4o-mini` in `ExtractionConfig`)
2. 一次完整提取需要手动组装 7 个对象(schema compile + staging + agent + extractor + resolver + scope)

### Design rationale

- Layer 1 (env config): 最小改动让模型可配置,不需要改源码
- Layer 2 (extract_document): 一个函数封装全链路,产品化入口

### Status transitions

- 2026-04-13 — **draft v1** (7 API decisions documented)
- 2026-04-13 — **scope check v1**: 3× P1 findings:
  1. `entity_descriptions` 无路径注入 prompt(扩展 scope 到 extractor.py + batch.py)
  2. Import-time env 解析(改为 call-time 在 `extract_document` 内部)
  3. AgentScope 默认值不安全(加 `max_batch_size=1000` + `require_source=True` 产品默认值)
- 2026-04-13 — **draft v2** (8 API decisions, all 3 P1 addressed, awaiting scope check v2)
- 2026-04-13 — **scope check v2**: 2× P1 findings:
  1. Error contract undefined — staging/batch/resolution 返回 data errors,非 exceptions;`extract_document` 应 raise 还是返回 union 未决
  2. `source_doc_name=doc_name` 未锁定 — 可能回退 F1 的 Document title fix
- 2026-04-13 — **draft v3** (10 API decisions, API-09 error contract + API-10 source_doc_name locked, awaiting scope check v3)
- 2026-04-13 — **scope check v3**: 2× P1 findings:
  1. Config 优先级链错误 — env 不应覆盖显式传入的 extraction_config;修正为 scalar > config > env > default
  2. API-04 `:exists` filter 和 response model 不一致 — v1 不过滤,全量 schema 传给 extractor
- 2026-04-13 — **draft v4** (10 API decisions updated, API-02 + API-04 corrected)
- 2026-04-13 — **scope check v4**: no blocking findings. 1 nit (section title version tag) cleaned up.
- 2026-04-13 — **scoped** (10 API decisions frozen, ready for implementation)
- 2026-04-13 — **implementing** (`models.py` default model change, `entity_descriptions` threading in `extractor.py` / `batch.py`, new `api.py`, `__init__.py` export, fake test signatures updated)
- 2026-04-13 — **behavioral verification**: real-LLM `extract_document(...)` run succeeded on `README.md -- Project Alpha`
  - `model='gpt-4.1'`
  - `staging_segments=7`
  - `gleaning_segments_reexamined=2`
  - `facts=16`
  - `entities=6`
  - `merge_events=0`
  - `Document.title='README.md'` (F1 not regressed)
- 2026-04-13 — **implemented with deviations**
  - Implementation landed as scoped, but §3.6 planned dedicated API tests were not added
  - Verification relied on compile check + full regression (`1012 passed, 3 skipped, 0 failed`) + one real-LLM end-to-end run
  - Additional observed boundary: when extraction yields 0 valid specs, `extract_document(...)` currently raises `ExtractionDocumentError(stage=\"resolution\")` because resolver rejects empty input
- 2026-04-13 — **archived**
