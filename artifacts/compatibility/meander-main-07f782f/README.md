# Shared Meander compatibility baseline

This directory records the exact FactGraph artifact consumed by Meander commit
`07f782fbc3ff6e3515294ce5e32cd7deec7f9ee7`. The original wheel is retained in a
dedicated [compatibility archive](https://github.com/Symbolic-Intelligence-Org/factgraph/releases/tag/archive%2Fmeander-main-07f782f).
The repository keeps provenance and digest pins; new candidate builds have
separate identities and storage locations.

- Distribution: `factgraph==0.2.0rc3`
- Producer: `2a4f6b8fb1e9204c9782213590c61c5d21c069d8`
- Producer tree: `3dd3c7f049125eac0bf87c14f071abff0841e538`
- Wheel SHA-256: `2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`
- Original manifest: [manifest.json](manifest.json)
- Archive location and exact asset identities: [location.json](location.json)
- Frozen source: [`release/0.4-baseline`](https://github.com/Symbolic-Intelligence-Org/factgraph/tree/release/0.4-baseline)

## Retrieve and verify

From this directory in a trusted checkout, download into a new temporary
directory. Verification uses this checkout's original checksum pins:

```bash
checksums_path="$PWD/SHA256SUMS"
archive_dir=$(mktemp -d)
gh release download archive/meander-main-07f782f \
  --repo Symbolic-Intelligence-Org/factgraph \
  --dir "$archive_dir" \
  --pattern factgraph-0.2.0rc3-py3-none-any.whl \
  --pattern manifest.json \
  --pattern SHA256SUMS
cmp "$checksums_path" "$archive_dir/SHA256SUMS"
(cd "$archive_dir" && shasum -a 256 -c "$checksums_path")
```

The archive page also provides direct asset downloads, recorded in location.json.
Retain the original filenames and bytes. The original manifest and SHA256SUMS in
this directory are unchanged. The wheel is no longer tracked in the current
source tree; prior Git history and the frozen source ref remain intact. This
directory is excluded from distributions.

The archive tag `archive/meander-main-07f782f` points to the original producer.
The GitHub archival record is marked prerelease and not latest; it creates no
new package version or compatibility acceptance. Its original
`release_eligible=false` remains unchanged.

## Rollback without discarding UI work

When restoring this historical baseline, retrieve and verify the original wheel
as above, then restore the matching artifact pins from Meander commit `07f782f`;
review only these paths:

- `integration/artifacts/factgraph-c2/`
- `integration/stack.lock`
- `pyproject.toml` and `pixi.lock` (FactGraph dependency entries only)
- `Dockerfile` (FactGraph filename/hash entries only)
- `src/meander/evaluation/factgraph_adapter.py` (artifact identity constants only)
- integration verifier and artifact-test expectations for that exact wheel

Preserve later UI, HTTP/SDK implementation and unrelated dependency edits. Do not
reset the whole Meander checkout or replace a workspace database. Once matching
pins are restored, reinstall these exact bytes in the intended consumer environment
and run its retained-artifact, API/SDK and installed-product checks. Version alone
is insufficient: several historical rc3 wheels have different contents.

For an isolated environment that already has the matching consumer pins:

```bash
/path/to/isolated/venv/bin/python -m pip install --no-deps --force-reinstall \
  /absolute/path/to/factgraph-0.2.0rc3-py3-none-any.whl
```

This backup does not grant authorization to publish an artifact or modify a
shared consumer. The manifest's original `release_eligible=false` is preserved.
