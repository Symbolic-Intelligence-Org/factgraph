"""Tests for session agent inventory."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.sdk import SDKStore
from factpy_kernel.service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    get_runtime_session_rules,
    list_ephemeral_rules,
    list_runtime_candidates,
    open_runtime_session,
    register_ephemeral_rule,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)
from factpy_kernel.tests._test_helpers import (
    User,
    _register_exposed_user_tag_rule,
    _schema_ir,
    _seed_users_for_syntax_matrix,
)


def _open_session(*, registry_root: str | None = None) -> str:
    dto: dict[str, object]
    if registry_root is not None:
        dto = {"registry_root": registry_root}
    else:
        dto = {"schema_ir": _schema_ir()}
    resp = open_runtime_session(dto)
    assert resp["ok"], resp
    return resp["session"]["session_id"]


def _close_session(session_id: str) -> None:
    close_runtime_session(session_id)


def _register_ephemeral_user_tag_rule(
    session_id: str,
    *,
    rule_id: str = "q.user_tag_rows",
    version: str = "1.0.0",
) -> dict:
    return register_ephemeral_rule(
        session_id,
        {
            "rule": {
                "rule_id": rule_id,
                "version": version,
                "select": ["$u", "$tag"],
                "where": [["pred", "user:tag", ["$u", "$tag"]]],
                "expose": True,
            }
        },
    )


def _native_derivation_dto(*, rule_id: str = "q.user_tag_rows", version: str = "1.0.0") -> dict:
    return {
        "derivation": {
            "derivation_id": "drv.runtime.user_tag_copy",
            "version": "1.0.0",
            "target": "user:tag",
            "head_vars": ["$u", "$tag"],
            "where": [
                ["ruleref", rule_id, version, ["$u", "$tag"]],
                ["eq", "$tag", "vip"],
            ],
            "mode": "native",
        }
    }


def _write_runtime_user_rows(session_id: str, refs: dict[str, str]) -> None:
    for pred_id, e_ref, rest_terms in (
        ("user:tag", refs["u1"], [["string", "vip"]]),
        ("user:tag", refs["u2"], [["string", "staff"]]),
        ("user:name", refs["u1"], [["string", "Alice"]]),
        ("user:name", refs["u2"], [["string", "Bob"]]),
    ):
        resp = write_runtime_fact(
            session_id,
            {
                "pred_id": pred_id,
                "e_ref": e_ref,
                "rest_terms": rest_terms,
            },
            kind="add",
        )
        assert resp["ok"], resp


class TestRuleInventory(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_ri1_no_registry_root_empty_rules(self) -> None:
        session_id = _open_session()
        try:
            resp = get_runtime_session_rules(session_id)
            self.assertTrue(resp["ok"], resp)
            self.assertEqual(resp["result"]["total"], 0)
            self.assertEqual(resp["result"]["fs_count"], 0)
            self.assertEqual(resp["result"]["ephemeral_count"], 0)
        finally:
            _close_session(session_id)

    def test_ri2_fs_rules_listed_with_source_fs(self) -> None:
        sdk = SDKStore([User])
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(sdk.schema_ir)
            _register_exposed_user_tag_rule(sdk, tmp_dir, rule_id="q.fs_rule")

            session_id = _open_session(registry_root=tmp_dir)
            try:
                resp = get_runtime_session_rules(session_id)
                self.assertTrue(resp["ok"], resp)
                rules = resp["result"]["rules"]
                ids = {(r["rule_id"], r["version"]) for r in rules}
                self.assertIn(("q.fs_rule", "1.0.0"), ids)
                fs_rule = next(r for r in rules if r["rule_id"] == "q.fs_rule")
                self.assertEqual(fs_rule["source"], "fs")
            finally:
                _close_session(session_id)

    def test_ri3_duplicate_key_shadowed(self) -> None:
        sdk = SDKStore([User])
        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(sdk.schema_ir)
            _register_exposed_user_tag_rule(sdk, tmp_dir, rule_id="q.shadow_test")

            session_id = _open_session(registry_root=tmp_dir)
            try:
                resp = _register_ephemeral_user_tag_rule(
                    session_id,
                    rule_id="q.shadow_test",
                    version="1.0.0",
                )
                self.assertTrue(resp["ok"], resp)

                inv = get_runtime_session_rules(session_id)
                self.assertTrue(inv["ok"], inv)
                matching = [r for r in inv["result"]["rules"] if r["rule_id"] == "q.shadow_test"]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["source"], "ephemeral_shadowed_by_fs")
            finally:
                _close_session(session_id)

    def test_ri4_include_spec_returns_body(self) -> None:
        session_id = _open_session()
        try:
            reg = _register_ephemeral_user_tag_rule(session_id, rule_id="q.spec_test")
            self.assertTrue(reg["ok"], reg)
            resp = get_runtime_session_rules(session_id, include_spec=True)
            self.assertTrue(resp["ok"], resp)
            eph = next(r for r in resp["result"]["rules"] if r["rule_id"] == "q.spec_test")
            self.assertIn("select_vars", eph)
            self.assertIn("where", eph)
            self.assertIn("expose", eph)
        finally:
            _close_session(session_id)

    def test_ri5_unknown_session_returns_error(self) -> None:
        resp = get_runtime_session_rules("rt_missing")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["errors"][0]["kind"], "runtime_session_not_found")


class TestCandidateInventory(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)
        self.session_id = _open_session()
        _write_runtime_user_rows(self.session_id, self.refs)

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_ci1_empty_on_fresh_session(self) -> None:
        fresh_session = _open_session()
        try:
            resp = list_runtime_candidates(fresh_session)
            self.assertTrue(resp["ok"], resp)
            self.assertEqual(resp["result"]["total"], 0)
            self.assertEqual(resp["result"]["candidates"], [])
        finally:
            _close_session(fresh_session)

    def test_ci2_candidate_ids_appear_after_evaluate(self) -> None:
        reg = _register_ephemeral_user_tag_rule(self.session_id)
        self.assertTrue(reg["ok"], reg)

        eval_resp = evaluate_runtime_derivation(self.session_id, _native_derivation_dto())
        self.assertTrue(eval_resp["ok"], eval_resp)
        candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

        inv = list_runtime_candidates(self.session_id)
        self.assertTrue(inv["ok"], inv)
        ids = [c["candidate_id"] for c in inv["result"]["candidates"]]
        self.assertIn(candidate_id, ids)

    def test_ci3_pred_id_populated(self) -> None:
        reg = _register_ephemeral_user_tag_rule(self.session_id, rule_id="q.pred_id_test")
        self.assertTrue(reg["ok"], reg)

        eval_resp = evaluate_runtime_derivation(
            self.session_id,
            _native_derivation_dto(rule_id="q.pred_id_test"),
        )
        self.assertTrue(eval_resp["ok"], eval_resp)

        inv = list_runtime_candidates(self.session_id)
        self.assertTrue(inv["ok"], inv)
        self.assertTrue(inv["result"]["candidates"])
        self.assertTrue(all(c["pred_id"] == "user:tag" for c in inv["result"]["candidates"]))

    def test_ci4_pred_id_filter(self) -> None:
        reg = _register_ephemeral_user_tag_rule(self.session_id, rule_id="q.filter_test")
        self.assertTrue(reg["ok"], reg)

        eval_resp = evaluate_runtime_derivation(
            self.session_id,
            _native_derivation_dto(rule_id="q.filter_test"),
        )
        self.assertTrue(eval_resp["ok"], eval_resp)

        match_resp = list_runtime_candidates(self.session_id, pred_id_filter="user:tag")
        self.assertTrue(match_resp["ok"], match_resp)
        self.assertEqual(match_resp["result"]["total"], 1)

        miss_resp = list_runtime_candidates(self.session_id, pred_id_filter="user:missing")
        self.assertTrue(miss_resp["ok"], miss_resp)
        self.assertEqual(miss_resp["result"]["total"], 0)

    def test_ci5_unknown_session_returns_error(self) -> None:
        resp = list_runtime_candidates("rt_missing")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["errors"][0]["kind"], "runtime_session_not_found")


class TestInventoryRegression(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_reg1_list_ephemeral_rules_unchanged(self) -> None:
        session_id = _open_session()
        try:
            reg = _register_ephemeral_user_tag_rule(session_id, rule_id="q.reg_test")
            self.assertTrue(reg["ok"], reg)
            resp = list_ephemeral_rules(session_id)
            self.assertTrue(resp["ok"], resp)
            entry = resp["result"]["ephemeral_rules"][0]
            self.assertIn("rule_id", entry)
            self.assertIn("version", entry)
            self.assertNotIn("select_vars", entry)
            self.assertNotIn("where", entry)
            self.assertNotIn("expose", entry)
        finally:
            _close_session(session_id)


if __name__ == "__main__":
    unittest.main()
