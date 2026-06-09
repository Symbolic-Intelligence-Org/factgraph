# Audit Log: Cleanup — remove schema description

Paired with [2026-06-09_explain-layer-cleanup-schema-description.md](./2026-06-09_explain-layer-cleanup-schema-description.md).

---

## A. Decision (`<user>` 2026-06-09)

`<user>`:同意 repr 排除出 schema identity;并**建议删除 schema description**(repr 的下位替代,目前无处消费)。planner 验证后采纳删除(比仅排除更干净)。

## B. Preflight 实证(verify before delete,2026-06-09)

| 检查 | 结果 |
|---|---|
| 全 src `.description` 读取/消费点 | **0**(仅 storage/parse/validate) |
| `PredicateInfo.description` 运行时读取 | 0 |
| tests 中 schema `description=` | 0 |
| examples 中 schema `description=` | 0 |
| `sdk/dsl/rule.py` description | **独立**(Rule/Inference,owner=),不在范围 |

→ schema description 是 write-only dead metadata,删除安全。

## C. 排序决定

作为独立 cleanup slice 排在 **S1 之后、S2 之前**:单一关注点(纯减法),且让 S2 的 digest 排除机制只需处理 repr(description 届时已不在 IR)。

## D. digest 说明

description 当前在 identity digest 内;删除使含 description 的 schema digest 变化。但 tests/examples 无 description-bearing schema → 预期 0 digest 测试破坏(acceptance 兜底:无 pinned-digest 测试因此 fail)。

## E. Gate result (Claude 独立验证 2026-06-09)

impl `f4300425`(parent = cleanup 蓝图 `fcd10b16`,线性栈)。**PASS**:
- scope:14 文件(4 schema 逻辑 + 2 测试 + 6 docs + S2 蓝图同步);无 memory/无关混入。
- description 删净:sdk/schema.py、authoring/schema_dsl_parse.py、schema_compile.py、schema_ir.py、schema_runtime.py 残留 **0**;`PredicateInfo.description` 移除。
- 保留:`pattern=`(18)、`repr`(29)、`Rule/Inference.description`(独立)未误删。
- 拒绝测试:`test_schema_description_metadata_is_not_accepted` 两路(sdk + authoring)。
- cohort:55 OK(独立,含 schema runtime / db identity / relationship / three-split digest 敏感区,无破坏);Codex 报 61/133。

裁决:**PASS**。

## F. Deviations(良性)

- Codex 把 S2 蓝图 stale hook 同步并入本 cleanup commit(doc 与 code 同 commit,内容相关,可接受)。
