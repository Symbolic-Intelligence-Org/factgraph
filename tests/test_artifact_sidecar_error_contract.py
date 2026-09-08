"""FileArtifactSidecar retains its exact ValueError guards and GC failure-record boundary."""

from __future__ import annotations

import json
import re

import pytest

from factgraph.core.rules._trace import RuleTraceArtifact
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar
from factgraph.core.store._support import ProofReceipt, compute_support_digest

_DIGEST = "sha256:" + "a" * 64


class _Clock:
    def __init__(self, now_ns: int) -> None:
        self.now_ns = now_ns

    def __call__(self) -> int:
        return self.now_ns


def _receipt() -> ProofReceipt:
    return ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="fact",
        binding_items=(("$x", "e1"),),
        pred_witnesses=(),
    )


def _trace(rule_run_id: str = "run-1") -> RuleTraceArtifact:
    return RuleTraceArtifact(
        rule_run_id=rule_run_id,
        root_rule_id="rule",
        root_version="v1",
        select_vars=("$x",),
        invocations=(),
        root_rows=(),
    )


@pytest.mark.parametrize("wrong", [None, {}, "receipt", _trace(), ("native_binding_v1",)])
def test_write_support_rejects_non_receipt_with_exact_value_error(tmp_path, wrong):
    sidecar = FileArtifactSidecar(tmp_path)
    with pytest.raises(ValueError, match=re.escape("artifact must be ProofReceipt")) as caught:
        sidecar.write_support(_DIGEST, wrong)
    assert type(caught.value) is ValueError
    assert list(tmp_path.rglob("*")) == []


def test_write_support_accepts_receipt_and_reads_it_back(tmp_path):
    sidecar = FileArtifactSidecar(tmp_path)
    receipt = _receipt()
    digest = compute_support_digest(receipt)
    sidecar.write_support(digest, receipt)
    assert sidecar.read_support(digest) == receipt


@pytest.mark.parametrize("wrong", [None, {}, "trace", _receipt(), ("run-1",)])
def test_write_rule_trace_rejects_non_trace_with_exact_value_error(tmp_path, wrong):
    sidecar = FileArtifactSidecar(tmp_path)
    with pytest.raises(ValueError, match=re.escape("artifact must be RuleTraceArtifact")) as caught:
        sidecar.write_rule_trace("run-1", wrong)
    assert type(caught.value) is ValueError
    assert list(tmp_path.rglob("*")) == []


def test_write_rule_trace_accepts_trace_and_reads_it_back(tmp_path):
    sidecar = FileArtifactSidecar(tmp_path)
    trace = _trace()
    sidecar.write_rule_trace("run-1", trace)
    assert sidecar.read_rule_trace("run-1") == trace


@pytest.mark.parametrize("raw", ["[]", '"row"', "1", "null"])
def test_read_rule_trace_rejects_non_object_row_with_exact_value_error(tmp_path, raw):
    sidecar = FileArtifactSidecar(tmp_path)
    path = tmp_path / "rule_trace" / "run-1.json"
    path.parent.mkdir(parents=True)
    path.write_text(raw, encoding="utf-8")
    message = f"artifact row must decode to object: {path}"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        sidecar.read_rule_trace("run-1")
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("raw", ["[]", '"row"', "1", "null"])
def test_read_support_rejects_non_object_row_with_exact_value_error(tmp_path, raw):
    sidecar = FileArtifactSidecar(tmp_path)
    path = tmp_path / "support" / "sha256" / (_DIGEST.removeprefix("sha256:") + ".json")
    path.parent.mkdir(parents=True)
    path.write_text(raw, encoding="utf-8")
    message = f"artifact row must decode to object: {path}"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        sidecar.read_support(_DIGEST)
    assert type(caught.value) is ValueError


@pytest.mark.parametrize("captured_at_ns", ["10", 10.0, True, None, [10]])
def test_gc_records_wrong_type_captured_at_ns_as_failed_key_and_keeps_files(tmp_path, captured_at_ns):
    clock = _Clock(10)
    sidecar = FileArtifactSidecar(tmp_path, clock=clock)
    sidecar.write_rule_trace("run-1", _trace())
    payload = tmp_path / "rule_trace" / "run-1.json"
    meta = tmp_path / "rule_trace" / "run-1.meta.json"
    meta.write_text(json.dumps({"captured_at_ns": captured_at_ns}), encoding="utf-8")
    clock.now_ns = 1_000
    result = sidecar.gc_rule_trace(ttl_ns=1)
    assert result.total_scanned == 1
    assert result.deleted_keys == ()
    assert result.failed_keys == (("run-1", str(meta), f"captured_at_ns must be int: {meta}"),)
    assert payload.exists()
    assert meta.exists()


@pytest.mark.parametrize("raw", ["[]", '"row"', "1"])
def test_gc_records_non_object_meta_row_as_failed_key_and_keeps_files(tmp_path, raw):
    clock = _Clock(10)
    sidecar = FileArtifactSidecar(tmp_path, clock=clock)
    sidecar.write_rule_trace("run-1", _trace())
    payload = tmp_path / "rule_trace" / "run-1.json"
    meta = tmp_path / "rule_trace" / "run-1.meta.json"
    meta.write_text(raw, encoding="utf-8")
    clock.now_ns = 1_000
    result = sidecar.gc_rule_trace(ttl_ns=1)
    assert result.deleted_keys == ()
    assert result.failed_keys == (
        ("run-1", str(meta), f"artifact row must decode to object: {meta}"),
    )
    assert payload.exists()
    assert meta.exists()


def test_gc_deletes_expired_trace_with_int_captured_at_ns(tmp_path):
    clock = _Clock(10)
    sidecar = FileArtifactSidecar(tmp_path, clock=clock)
    sidecar.write_rule_trace("run-1", _trace())
    payload = tmp_path / "rule_trace" / "run-1.json"
    meta = tmp_path / "rule_trace" / "run-1.meta.json"
    assert json.loads(meta.read_text(encoding="utf-8")) == {"captured_at_ns": 10}
    clock.now_ns = 1_000
    result = sidecar.gc_rule_trace(ttl_ns=1)
    assert result.total_scanned == 1
    assert result.deleted_keys == ("run-1",)
    assert result.failed_keys == ()
    assert not payload.exists()
    assert not meta.exists()
