"""Tests for ephemeral rule authoring (G4 / llm-integration-surface Milestone B)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kernel.sdk import SDKStore
from service.runtime_v1 import (
    accept_runtime_derivation,
    clear_ephemeral_rules,
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_steps,
    list_ephemeral_rules,
    open_runtime_session,
    register_ephemeral_rule,
    reset_runtime_sessions_for_tests,
    run_runtime_rule,
    write_runtime_fact,
)
from kernel.tests._test_helpers import User, _register_exposed_user_tag_rule, _schema_ir, _seed_users_for_syntax_matrix


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


def _register_user_tag_rule(
    session_id: str,
    *,
    rule_id: str = "q.user_tag_rows",
    version: str = "1.0.0",
    pred_id: str = "user:tag",
) -> dict:
    return register_ephemeral_rule(
        session_id,
        {
            "rule": {
                "rule_id": rule_id,
                "version": version,
                "select": ["$u", "$tag"],
                "where": [["pred", pred_id, ["$u", "$tag"]]],
                "expose": True,
            }
        },
    )


def _parent_rule_dto(*, rule_id: str = "q.user_tag_rows", version: str = "1.0.0") -> dict:
    return {
        "rule": {
            "rule_id": "q.parent_runtime_probe",
            "version": "1.0.0",
            "select": ["$u", "$tag"],
            "where": [
                ["ruleref", rule_id, version, ["$u", "$tag"]],
                ["eq", "$tag", "vip"],
            ],
        }
    }


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


class TestRegisterEphemeralRule(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.session_id = _open_session()

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_register_returns_registered_status(self) -> None:
        resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(resp["ok"], resp)
        result = resp["result"]
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["rule_id"], "q.user_tag_rows")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["total_ephemeral"], 1)

    def test_register_invalid_dto_returns_error(self) -> None:
        resp = register_ephemeral_rule(self.session_id, "not-a-dict")  # type: ignore[arg-type]
        self.assertFalse(resp["ok"])

    def test_register_missing_rule_key_returns_error(self) -> None:
        resp = register_ephemeral_rule(self.session_id, {})
        self.assertFalse(resp["ok"])

    def test_register_unknown_session_returns_error(self) -> None:
        resp = _register_user_tag_rule("rt_missing")
        self.assertFalse(resp["ok"])

    def test_reregister_same_key_returns_replaced_status(self) -> None:
        first = _register_user_tag_rule(self.session_id)
        self.assertTrue(first["ok"], first)
        second = _register_user_tag_rule(self.session_id)
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["result"]["status"], "replaced")

    def test_reregister_same_key_does_not_grow_list(self) -> None:
        first = _register_user_tag_rule(self.session_id)
        self.assertTrue(first["ok"], first)
        second = _register_user_tag_rule(self.session_id)
        self.assertTrue(second["ok"], second)
        listed = list_ephemeral_rules(self.session_id)
        self.assertTrue(listed["ok"], listed)
        self.assertEqual(listed["result"]["total"], 1)


class TestListAndClearEphemeralRules(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.session_id = _open_session()

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_list_empty_on_fresh_session(self) -> None:
        resp = list_ephemeral_rules(self.session_id)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["total"], 0)
        self.assertEqual(resp["result"]["ephemeral_rules"], [])

    def test_list_after_register(self) -> None:
        _register_user_tag_rule(self.session_id)
        resp = list_ephemeral_rules(self.session_id)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["total"], 1)
        self.assertEqual(
            resp["result"]["ephemeral_rules"],
            [{"rule_id": "q.user_tag_rows", "version": "1.0.0"}],
        )

    def test_clear_removes_all(self) -> None:
        _register_user_tag_rule(self.session_id)
        resp = clear_ephemeral_rules(self.session_id)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["cleared"], 1)
        self.assertEqual(list_ephemeral_rules(self.session_id)["result"]["total"], 0)

    def test_clear_empty_session_returns_zero(self) -> None:
        resp = clear_ephemeral_rules(self.session_id)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["cleared"], 0)


class TestEphemeralRuleEvaluation(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.sdk = SDKStore([User])
        self.refs = _seed_users_for_syntax_matrix(self.sdk)
        self.session_id = _open_session()
        _write_runtime_user_rows(self.session_id, self.refs)

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_run_runtime_rule_can_resolve_ephemeral_ruleref_without_registry_root(self) -> None:
        register_resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(register_resp["ok"], register_resp)

        rule_resp = run_runtime_rule(self.session_id, _parent_rule_dto())
        self.assertTrue(rule_resp["ok"], rule_resp)
        self.assertEqual(rule_resp["result"]["rows"], [[self.refs["u1"], "vip"]])

    def test_evaluate_runtime_derivation_native_ruleref_uses_ephemeral_rule_without_registry_root(self) -> None:
        register_resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(register_resp["ok"], register_resp)

        eval_resp = evaluate_runtime_derivation(self.session_id, _native_derivation_dto())
        self.assertTrue(eval_resp["ok"], eval_resp)
        self.assertEqual(eval_resp["meta"]["mode"], "native")
        self.assertEqual(eval_resp["meta"]["candidate_count"], 1)
        payload = eval_resp["evaluation"]["candidates"][0]["payload"]
        self.assertEqual(payload["pred_id"], "user:tag")
        self.assertEqual(payload["terms"][0]["value"], self.refs["u1"])
        self.assertEqual(payload["terms"][1]["value"], "vip")

    def test_reregister_same_key_replaces_runtime_behavior(self) -> None:
        first = _register_user_tag_rule(self.session_id, pred_id="user:name")
        self.assertTrue(first["ok"], first)
        rule_before = run_runtime_rule(self.session_id, _parent_rule_dto())
        self.assertTrue(rule_before["ok"], rule_before)
        self.assertEqual(rule_before["result"]["rows"], [])

        second = _register_user_tag_rule(self.session_id, pred_id="user:tag")
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["result"]["status"], "replaced")

        rule_after = run_runtime_rule(self.session_id, _parent_rule_dto())
        self.assertTrue(rule_after["ok"], rule_after)
        self.assertEqual(rule_after["result"]["rows"], [[self.refs["u1"], "vip"]])

    def test_accept_then_explain_steps_includes_ephemeral_rule_name(self) -> None:
        register_resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(register_resp["ok"], register_resp)

        eval_resp = evaluate_runtime_derivation(self.session_id, _native_derivation_dto())
        self.assertTrue(eval_resp["ok"], eval_resp)
        candidate = eval_resp["evaluation"]["candidates"][0]

        accept_resp = accept_runtime_derivation(self.session_id, {"candidate": candidate})
        self.assertTrue(accept_resp["ok"], accept_resp)

        steps_resp = explain_runtime_steps(
            self.session_id,
            {"kind": "candidate", "id": candidate["candidate_id"]},
        )
        self.assertTrue(steps_resp["ok"], steps_resp)
        rule_apply_steps = [
            step
            for step in steps_resp["steps"]
            if step.get("step_kind") == "rule_apply"
        ]
        self.assertTrue(rule_apply_steps, steps_resp)
        self.assertEqual(
            rule_apply_steps[0]["detail"].get("rule_ref_ids"),
            ["q.user_tag_rows"],
        )
        self.assertIn("Rule q.user_tag_rows", rule_apply_steps[0]["description"])

    def test_clear_ephemeral_rules_removes_runtime_resolution(self) -> None:
        register_resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(register_resp["ok"], register_resp)
        clear_resp = clear_ephemeral_rules(self.session_id)
        self.assertTrue(clear_resp["ok"], clear_resp)

        rule_resp = run_runtime_rule(self.session_id, _parent_rule_dto())
        self.assertFalse(rule_resp["ok"])
        self.assertIn("unknown RuleRef", rule_resp["errors"][0]["details"]["message"])


class TestFsPriorityAndSessionIsolation(unittest.TestCase):
    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_fs_rule_wins_when_same_key_registered_ephemerally(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)
        with TemporaryDirectory() as tmp_dir:
            _register_exposed_user_tag_rule(sdk, tmp_dir, rule_id="q.user_tag_rows")

            session_id = _open_session(registry_root=tmp_dir)
            try:
                _write_runtime_user_rows(session_id, refs)
                register_resp = _register_user_tag_rule(
                    session_id,
                    rule_id="q.user_tag_rows",
                    pred_id="user:name",
                )
                self.assertTrue(register_resp["ok"], register_resp)

                rule_resp = run_runtime_rule(session_id, _parent_rule_dto())
                self.assertTrue(rule_resp["ok"], rule_resp)
                self.assertEqual(rule_resp["result"]["rows"], [[refs["u1"], "vip"]])
            finally:
                _close_session(session_id)

    def test_ephemeral_rules_not_shared_across_sessions(self) -> None:
        sid_a = _open_session()
        sid_b = _open_session()
        try:
            register_resp = _register_user_tag_rule(sid_a)
            self.assertTrue(register_resp["ok"], register_resp)
            resp_b = list_ephemeral_rules(sid_b)
            self.assertTrue(resp_b["ok"], resp_b)
            self.assertEqual(resp_b["result"]["total"], 0)
        finally:
            _close_session(sid_a)
            _close_session(sid_b)

    def test_closed_session_ephemeral_rules_gone(self) -> None:
        sid = _open_session()
        register_resp = _register_user_tag_rule(sid)
        self.assertTrue(register_resp["ok"], register_resp)
        _close_session(sid)
        resp = list_ephemeral_rules(sid)
        self.assertFalse(resp["ok"])

    def test_new_session_has_empty_ephemeral_rules(self) -> None:
        sid = _open_session()
        try:
            resp = list_ephemeral_rules(sid)
            self.assertTrue(resp["ok"], resp)
            self.assertEqual(resp["result"]["total"], 0)
        finally:
            _close_session(sid)


class TestRegisterEphemeralRuleSchemaValidation(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.session_id = _open_session()

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_unknown_pred_fails_at_registration(self) -> None:
        resp = register_ephemeral_rule(
            self.session_id,
            {
                "rule": {
                    "rule_id": "q.eph.bad_pred",
                    "version": "v1",
                    "select_vars": ["$r"],
                    "where": [["pred", "missing:nonexistent_pred", ["$r"]]],
                    "expose": True,
                }
            },
        )
        self.assertFalse(resp["ok"])
        err = resp["errors"][0]
        self.assertEqual(err["kind"], "rule_ast_validate")
        self.assertEqual(err["details"]["error_code"], "unknown_predicate")
        self.assertEqual(err["details"]["missing_pred_id"], "missing:nonexistent_pred")
        self.assertIn("remediation_hint", err["details"])

    def test_unknown_pred_does_not_append_to_session(self) -> None:
        resp = register_ephemeral_rule(
            self.session_id,
            {
                "rule": {
                    "rule_id": "q.eph.bad_pred",
                    "version": "v1",
                    "select_vars": ["$r"],
                    "where": [["pred", "missing:nonexistent_pred", ["$r"]]],
                }
            },
        )
        self.assertFalse(resp["ok"])
        listed = list_ephemeral_rules(self.session_id)
        self.assertTrue(listed["ok"], listed)
        self.assertEqual(listed["result"]["total"], 0)

    def test_valid_pred_still_registers_successfully(self) -> None:
        resp = _register_user_tag_rule(self.session_id)
        self.assertTrue(resp["ok"], resp)


class TestAgentFacingErrorCodes(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.session_id = _open_session()

    def tearDown(self) -> None:
        _close_session(self.session_id)
        reset_runtime_sessions_for_tests()

    def test_unknown_rule_ref_in_evaluate_has_error_code(self) -> None:
        reg = _register_user_tag_rule(self.session_id, rule_id="q.present", version="v1")
        self.assertTrue(reg["ok"], reg)
        resp = evaluate_runtime_derivation(
            self.session_id,
            _native_derivation_dto(rule_id="q.nonexistent_rule", version="v1"),
        )
        self.assertFalse(resp["ok"])
        err = resp["errors"][0]
        self.assertEqual(err["details"]["error_code"], "unknown_rule_ref")
        self.assertIn("missing_rule_ref", err["details"])
        self.assertIn("remediation_hint", err["details"])

    def test_rule_not_expose_in_evaluate_has_error_code(self) -> None:
        reg = register_ephemeral_rule(
            self.session_id,
            {
                "rule": {
                    "rule_id": "q.eph.no_expose",
                    "version": "v1",
                    "select_vars": ["$u", "$tag"],
                    "where": [["pred", "user:tag", ["$u", "$tag"]]],
                }
            },
        )
        self.assertTrue(reg["ok"], reg)
        resp = evaluate_runtime_derivation(
            self.session_id,
            _native_derivation_dto(rule_id="q.eph.no_expose", version="v1"),
        )
        self.assertFalse(resp["ok"])
        err = resp["errors"][0]
        self.assertEqual(err["details"]["error_code"], "rule_not_expose")
        self.assertIn("remediation_hint", err["details"])


if __name__ == "__main__":
    unittest.main()
