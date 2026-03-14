# Tutorials Reliability Review

## Goal

Assess whether `docs/guides/tutorials/` can currently be trusted as runnable guide material, and decide what should be:

- kept as a safe pointer
- rewritten against current code
- treated as placeholder backlog
- moved to history later if it only preserves older semantics

## Current Verdict

Overall reliability is `low`.

The directory should not currently be treated as an authoritative guide set.

Why:

1. most files are skeletal placeholders rather than executable tutorials
2. the only substantial SDK tutorials still contain retired semantics such as `functional` cardinality and `dims`
3. command-oriented files mention real CLI surface area, but they are too incomplete to serve as trustworthy runbooks

## Evidence

### 1. Placeholder density is high

Out of the 17 numbered tutorial files:

- 15 files are 19 lines or fewer
- several are only 3 lines long
- multiple files are just title + keyword stubs, not step-by-step procedures

Representative examples:

- [01-环境与安装.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/01-环境与安装.md)
  - only says `安装说明。`
- [03-Apply-Execute-与-Registry.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/03-Apply-Execute-%E4%B8%8E-Registry.md)
  - only says `apply-execute 与 registry 工作流。`
- [04-Registry-只读查看与运维命令.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/04-Registry-%E5%8F%AA%E8%AF%BB%E6%9F%A5%E7%9C%8B%E4%B8%8E%E8%BF%90%E7%BB%B4%E5%91%BD%E4%BB%A4.md)
  - only says `registry-list / registry-show 运维。`
- [05-导出审计包与静态审计页面.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/05-%E5%AF%BC%E5%87%BA%E5%AE%A1%E8%AE%A1%E5%8C%85%E4%B8%8E%E9%9D%99%E6%80%81%E5%AE%A1%E8%AE%A1%E9%A1%B5%E9%9D%A2.md)
  - only says `render_audit_static_site 与审计页面。`
- [08-团队内-Onboarding-清单.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/08-%E5%9B%A2%E9%98%9F%E5%86%85-Onboarding-%E6%B8%85%E5%8D%95.md)
  - repeats `成功标准（最小）` and then drops into stray fragments

### 2. SDK tutorial content is materially stale

The two substantial files are:

- [16-SDK-Batch-staging（sdk.batch）.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/16-SDK-Batch-staging%EF%BC%88sdk.batch%EF%BC%89.md)
- [17-SDK-Batch-staging（语义与契约-v0）.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/17-SDK-Batch-staging%EF%BC%88%E8%AF%AD%E4%B9%89%E4%B8%8E%E5%A5%91%E7%BA%A6-v0%EF%BC%89.md)

These are not safe as current guides because they still use older SDK semantics, for example:

- `Field(cardinality="functional")`
- `functional` vs `multi`
- `dims={...}`
- `SetOp/AddOp(..., dims, ...)`

Current SDK docs explicitly say:

- `Field.cardinality` is only `single|multi`: [01_alignment_matrix.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/01_alignment_matrix.md)
- old `functional/temporal/dims/fact_key` semantics are removed: [01_alignment_matrix.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/01_alignment_matrix.md)
- current batch/write contract is documented under [02_readwrite_and_ingest.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md)

### 3. Some pointers are safe, but not enough to lift the directory

[15-SDK-快速开始（Python 直接定义）.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/15-SDK-%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B%EF%BC%88Python%20%E7%9B%B4%E6%8E%A5%E5%AE%9A%E4%B9%89%EF%BC%89.md) is only an index redirect and is mostly safe as a pointer, because it tells readers to use:

- [src/factpy_kernel/sdk/docs/README.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/README.md)
- [01_alignment_matrix.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/01_alignment_matrix.md)
- [02_readwrite_and_ingest.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md)
- [03_rules_and_derivations.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)

However, it immediately points readers onward to `16` and `17`, which are not yet safe.

### 4. CLI/tutorial command names partially match reality, but the guides are still incomplete

The command set mentioned in tutorial stubs aligns with the current CLI entrypoint [cli.py](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/authoring/cli.py):

- `preflight`
- `workflow-dry-run`
- `apply-execute`
- `registry-list`
- `registry-show`

But files such as [09-CLI-命令速查.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/09-CLI-%E5%91%BD%E4%BB%A4%E9%80%9F%E6%9F%A5.md) and [14-生产化注意事项（registry并发-事务-v2）.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/14-%E7%94%9F%E4%BA%A7%E5%8C%96%E6%B3%A8%E6%84%8F%E4%BA%8B%E9%A1%B9%EF%BC%88registry%E5%B9%B6%E5%8F%91-%E4%BA%8B%E5%8A%A1-v2%EF%BC%89.md) are still only keyword lists, not validated procedures.

## File Grouping

### Group A: Placeholder backlog

These should be treated as `guide backlog`, not runnable guides:

- `01`
- `02`
- `03`
- `04`
- `05`
- `06`
- `07`
- `08`
- `09`
- `10`
- `11`
- `12`
- `13`
- `14`

### Group B: Safe redirect

- `15`
  - keep as a pointer to current SDK docs, but stop routing readers into stale `16/17` until those are fixed

### Group C: Rewrite required

- `16`
  - rewrite against current SDK docs and code
- `17`
  - either rewrite as current batch contract, or move to `history/` if it is mainly preserving v0 design semantics

## Recommended Next Pass

### P0

- stop treating `docs/guides/tutorials/` as a trusted onboarding path
- keep the warning note in [docs/guides/tutorials/README.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/README.md)
- review `16` and `17` first because they are detailed enough to mislead readers

### P1

- decide whether `17` is a rewrite target or historical artifact
- rewrite `16` using:
  - [src/factpy_kernel/sdk/docs/00_user_guide.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/00_user_guide.md)
  - [src/factpy_kernel/sdk/docs/01_alignment_matrix.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/01_alignment_matrix.md)
  - [src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md)
  - [src/factpy_kernel/sdk/docs/04_api_surface.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/04_api_surface.md)

### P2

- rebuild `01-14` as real tutorials or collapse them into fewer higher-quality guides
- for CLI-focused material, use [cli.py](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/authoring/cli.py) and current authoring/service/audit docs as the source of truth

## Conclusion

`docs/guides/tutorials/` is currently a mixed backlog, not a verified tutorial suite.

The directory is useful as:

- a map of intended tutorial topics
- a place to stage future guide writing

But it is not yet reliable enough to be recommended as the default learning path.
