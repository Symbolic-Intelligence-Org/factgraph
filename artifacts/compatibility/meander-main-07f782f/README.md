# Shared Meander compatibility baseline

This immutable backup is the exact FactGraph artifact consumed by Meander main
`07f782fbc3ff6e3515294ce5e32cd7deec7f9ee7`. It is retained independently of new
FactGraph candidate builds so UI work can continue against the existing API.

- Distribution: `factgraph==0.2.0rc3`
- Producer: `2a4f6b8fb1e9204c9782213590c61c5d21c069d8`
- Producer tree: `3dd3c7f049125eac0bf87c14f071abff0841e538`
- Wheel SHA-256: `2255138bd7682bb251ee581a7cce92001e3ec313e7499bc3cbb200e751915486`
- Original manifest: [manifest.json](manifest.json)

Verify before use, from this directory:

```bash
shasum -a 256 -c SHA256SUMS
```

The original filename and bytes must never be replaced. New candidates use new
versions and separate directories. This directory is excluded from distributions.

## Rollback without discarding UI work

The shared consumer remains on this artifact during candidate validation. If a
future promoted candidate needs rollback, restore the original wheel and the
matching artifact pins from Meander commit `07f782f`; review only these paths:

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
