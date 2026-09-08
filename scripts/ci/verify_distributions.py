"""Verify complete, reproducible release distributions from the current commit."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory

import tomllib


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(first: Path, second: Path, output: Path) -> None:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip()
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    manifest = json.loads((first / "manifest.json").read_text())
    require(manifest["source_commit"] == source, "manifest source does not match HEAD")
    require(manifest["source_tree"] == tree, "manifest tree does not match HEAD")
    require(manifest["version"] == project["version"], "manifest version mismatch")
    wheels = list(first.glob("*.whl"))
    sdists = list(first.glob("*.tar.gz"))
    require(len(wheels) == 1 and len(sdists) == 1, "expected exactly one wheel and sdist")
    wheel, sdist = wheels[0], sdists[0]
    for name, identity in manifest["artifacts"].items():
        path = first / name
        require(digest(path) == identity["sha256"], f"manifest digest mismatch: {name}")
        require(path.stat().st_size == identity["size_bytes"], f"manifest size mismatch: {name}")
    require(digest(wheel) == digest(second / wheel.name), "independent wheel builds differ")
    paths = subprocess.check_output(["git", "ls-files", "src/factgraph"], text=True).splitlines()
    expected = {name.removeprefix("src/"): (root / name).read_bytes() for name in paths if name.endswith(".py")}
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        require(len(members) == len(set(members)), "duplicate wheel members")
        runtime = {name: archive.read(name) for name in members if name.startswith("factgraph/")}
        require(runtime == expected, "wheel does not contain the complete committed runtime")
        metadata_paths = [name for name in members if name.endswith(".dist-info/METADATA")]
        require(len(metadata_paths) == 1, "ambiguous distribution metadata")
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        require(metadata["Name"] == "factgraph" and metadata["Version"] == project["version"], "wheel identity mismatch")
        require(metadata["License-Expression"] == "Apache-2.0", "missing SPDX license")
        licenses = [name for name in members if name.endswith(".dist-info/licenses/LICENSE")]
        require(len(licenses) == 1 and archive.read(licenses[0]) == (root / "LICENSE").read_bytes(), "license bytes missing or changed")
        record = next(name for name in members if name.endswith(".dist-info/RECORD"))
        rows = list(csv.reader(io.StringIO(archive.read(record).decode())))
        require(len(rows) == len(members) and {row[0] for row in rows} == set(members), "RECORD inventory mismatch")
        for name, encoded, size in rows:
            if name == record:
                require(encoded == "" and size == "", "RECORD self-entry must be unhashed")
                continue
            content = archive.read(name)
            expected_hash = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
            require(encoded == expected_hash and size == str(len(content)), f"RECORD mismatch: {name}")
    with TemporaryDirectory(prefix="factgraph-sdist-verification-") as directory:
        temporary = Path(directory)
        with tarfile.open(sdist) as archive:
            names = [Path(name) for name in archive.getnames()]
            require(all(not ({"artifacts", "dist", "__pycache__"} & set(name.parts)) and name.suffix != ".whl" for name in names), "sdist includes local artifacts or backups")
            archive.extractall(temporary, filter="data")
        sources = [path for path in temporary.iterdir() if path.is_dir()]
        require(len(sources) == 1, "ambiguous sdist root")
        source_root = sources[0]
        rebuilt = temporary / "rebuilt"
        environment = dict(os.environ, SOURCE_DATE_EPOCH=str(manifest["source_date_epoch"]))
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(rebuilt), str(source_root)], check=True, env=environment)
        require(digest(rebuilt / wheel.name) == digest(wheel), "sdist roundtrip changes the wheel")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"source_commit": source, "source_tree": tree, "version": project["version"], "wheel_sha256": digest(wheel), "runtime_files": len(expected), "record_verified": True, "two_builds_identical": True, "sdist_roundtrip_identical": True}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verify(args.first.resolve(), args.second.resolve(), args.output.resolve())
