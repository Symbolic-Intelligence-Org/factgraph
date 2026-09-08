#!/usr/bin/env bash
# Ubuntu 24.04 / x86_64 release-gate engine, pinned to upstream release bytes.
set -euo pipefail
asset=x86_64-ubuntu-2404-souffle-2.5-Linux.deb
expected=6b86e554f6aa5abf8a8b55d8312ae37c0957c5bd6c9edeea89246db9406f645ec5e600b84fe6636b1c163da556f0da6c3d2dad46c1083413f2fcf4f95b9ac62c
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
curl --fail --location --retry 3 --output "$temporary/$asset" \
  "https://github.com/souffle-lang/souffle/releases/download/2.5/$asset"
(cd "$temporary" && printf '%s  %s\n' "$expected" "$asset" | sha512sum --check -)
sudo apt-get update
sudo apt-get install --yes "$temporary/$asset"
souffle --version
