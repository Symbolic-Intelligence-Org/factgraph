"""Zero-engine self-checks on SYNTHETIC inputs (never the 20 primary cells).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT
Run: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src \
     .../factpy/bin/python -m pytest -p no:cacheprovider -q tests/test_selfcheck.py
"""
from __future__ import annotations

import os
import sys
import unittest

_PROBE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROBE_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts import ProbeError, digest, typed_failure_result  # noqa: E402
import compiler as pc  # noqa: E402
import lineage as pl  # noqa: E402
import resolver as pr  # noqa: E402
from profiles import profile_snapshot  # noqa: E402
from scorer import check_assertions, forbidden_oracle_selftest, interpretation_flags, subset_match  # noqa: E402

W_SYN = {
    "entity_types": [
        {"name": "person", "identity": "name", "fields": []},
        {"name": "team_name", "identity": "value", "fields": []},
    ],
    "facts": [["member", "Ada", "red"], ["member", "ada", "blue"], ["member", "bob", "red"]],
    "rules": [{"rule_id": "member", "ports": ["person", "team"], "from_facts": "member"}],
}


def _fixture(slots, extra=None, matching=None, task_kind="query", expectation=None):
    prof = {
        "profile_ref": "syn.v0", "task_kind": task_kind,
        "policy": {"policy_ref": "syn@0", "ast": {"all": [
            {"occurrence": {"rule_ref": "member", "alias": "m"}}]}},
        "slot_descriptors": [{"slot": "person_ref", "type": "entity_ref", "entity_type": "person"}],
        "bind_templates": [{"path": "m.person", "slot": "person_ref"}],
        "query_mode": "rows",
        "select_templates": [{"alias": "team", "path": "m.team"}],
        "expectation_template": expectation,
        "field_path_grants": [],
    }
    if matching:
        prof["resolver_identity_matching"] = matching
    return {"cell_id": "SYN", "profile": prof, "world": W_SYN,
            "invocation": {"slots": slots, "extra_fields": extra or {}}}


class ResolverChecks(unittest.TestCase):
    def test_authority_fields_rejected_with_enumeration(self):
        fx = _fixture({"person_ref": "bob"}, extra={"policy_ref": "x", "config": {"e": 1}})
        with self.assertRaises(ProbeError) as cm:
            pr.resolve(fx, profile_snapshot(fx))
        self.assertEqual(cm.exception.code, "INGRESS_UNKNOWN_FIELDS")
        # submission order preserved (experiment-v0 convention, not a public contract)
        self.assertEqual(cm.exception.diagnostics, ["policy_ref", "config"])

    def test_case_insensitive_ambiguity(self):
        fx = _fixture({"person_ref": "ADA"},
                      matching="case_insensitive_lookup_case_sensitive_identity")
        with self.assertRaises(ProbeError) as cm:
            pr.resolve(fx, profile_snapshot(fx))
        self.assertEqual(cm.exception.code, "AMBIGUOUS_IDENTITY")
        diag = cm.exception.diagnostics[0]
        self.assertEqual([c["id"] for c in diag["candidates"]], ["Ada", "ada"])

    def test_unknown_identity_fails_lookup_type(self):
        fx = _fixture({"person_ref": "nobody"})
        with self.assertRaises(ProbeError) as cm:
            pr.resolve(fx, profile_snapshot(fx))
        self.assertEqual(cm.exception.code, "UNKNOWN_IDENTITY")

    def test_value_identity_resolves_without_existence(self):
        fx = _fixture({"person_ref": "bob"})
        fx["profile"]["slot_descriptors"].append(
            {"slot": "team_ref", "type": "entity_ref", "entity_type": "team_name"})
        fx["invocation"]["slots"]["team_ref"] = "green"
        res = pr.resolve(fx, profile_snapshot(fx))
        self.assertEqual(res["normalized_slot_values"]["team_ref"], {"entity": "team_name", "id": "green"})

    def test_task_kind_coherence(self):
        fx = _fixture({"person_ref": "bob"}, task_kind="validation", expectation=None)
        with self.assertRaises(ProbeError) as cm:
            pr.resolve(fx, profile_snapshot(fx))
        self.assertEqual(cm.exception.code, "VALIDATION_WITHOUT_EXPECTATION")


class CompilerChecks(unittest.TestCase):
    def _ast(self, n_any_pairs):
        return {"all": [{"any": [{"occurrence": {"rule_ref": f"r{i}a", "alias": f"x{i}"}},
                                 {"occurrence": {"rule_ref": f"r{i}b", "alias": f"y{i}"}}]}
                        for i in range(n_any_pairs)]}

    def test_branch_algebra(self):
        self.assertEqual(len(pc.ast_branches(self._ast(5))), 32)
        self.assertEqual(len(pc.ast_branches(self._ast(6))), 64)
        sc01 = {"all": [{"occurrence": {"rule_ref": "a", "alias": "a"}},
                        {"any": [{"occurrence": {"rule_ref": "b", "alias": "b"}},
                                 {"occurrence": {"rule_ref": "c", "alias": "c"}}]}]}
        self.assertEqual({frozenset(b) for b in pc.ast_branches(sc01)},
                         {frozenset({"a", "b"}), frozenset({"a", "c"})})

    def test_catalog_namespace_collision(self):
        with self.assertRaises(ProbeError) as cm:
            pc.validate_catalog({"rules": [{"rule_id": "__query__:abc"}]})
        self.assertEqual(cm.exception.code, "SYNTHETIC_QUERY_NAMESPACE_COLLISION")
        pc.validate_catalog({"rules": [{"rule_id": "normal__query__inner"}]})  # no false positive

    def test_reject_on_partial_join(self):
        world = {"entity_types": [], "facts": [["a_fact", 1], ["b_fact", 2], ["c_fact", "c"]],
                 "rules": [{"rule_id": "a", "ports": ["x"], "from_facts": "a_fact"},
                           {"rule_id": "b", "ports": ["x"], "from_facts": "b_fact"},
                           {"rule_id": "c", "ports": ["y"], "from_facts": "c_fact"}]}
        prof = {"profile_ref": "syn.sc01", "task_kind": "query",
                "policy": {"policy_ref": "p@0", "ast": {"all": [
                    {"occurrence": {"rule_ref": "a", "alias": "a"}},
                    {"any": [{"occurrence": {"rule_ref": "b", "alias": "b"}},
                             {"occurrence": {"rule_ref": "c", "alias": "c"}}]},
                    {"unify": {"left": {"path": "a.x"}, "right": {"path": "b.x"}}}]}},
                "slot_descriptors": [], "bind_templates": [], "query_mode": "rows",
                "select_templates": [{"alias": "ax", "path": "a.x"}],
                "expectation_template": None, "field_path_grants": []}
        fixture = {"profile": prof, "world": world, "invocation": {"slots": {}, "extra_fields": {}}}
        resolution = {"normalized_slot_values": {}, "resolved_request_digest": "sha256:x"}
        with self.assertRaises(ProbeError) as cm:
            pc.compile_policy(fixture, resolution, candidate_semantics="reject_on_partial")
        self.assertEqual(cm.exception.code, "JOIN_ENDPOINT_NOT_TOTAL")
        # branch_scoped compiles and records per-branch applicability
        cr = pc.compile_policy(fixture, resolution, candidate_semantics="branch_scoped")
        states = {(tuple(a["branch"]), a["state"])
                  for a in cr["joins"][0]["branch_applicability"]}
        self.assertIn((("a", "b"), "materialized"), states)
        self.assertIn((("a", "c"), "not_applicable_by_candidate_semantics"), states)
        lin = pl.build_lineage(cr, expectation_present=False)
        tot = pl.check_totality(lin)
        self.assertTrue(tot["ok"], tot["failures"])

    def test_navigation_validation_codes(self):
        world = {"entity_types": [{"name": "person", "identity": "name",
                                   "fields": [{"name": "age", "type": "int"}]}],
                 "facts": [["member", "bob", "red"], ["age", "bob", 30]],
                 "rules": [{"rule_id": "member", "ports": ["person", "team"], "from_facts": "member"}]}
        occ_index = {"m": {"occurrence": {"rule_ref": "member", "alias": "m"},
                           "rule_spec": world["rules"][0]}}
        branches = [frozenset({"m"})]
        p = pc._resolve_path("m.person.age", occ_index)
        with self.assertRaises(ProbeError) as cm:
            pc._validate_navigation(p, world, [], branches)
        self.assertEqual(cm.exception.code, "FIELD_NAVIGATION_RESTRICTED")
        p2 = pc._resolve_path("m.person.height", occ_index)
        with self.assertRaises(ProbeError) as cm:
            pc._validate_navigation(p2, world, ["m.person.height"], branches)
        self.assertEqual(cm.exception.code, "FIELD_NAVIGATION_UNKNOWN_FIELD")
        with self.assertRaises(ProbeError) as cm:
            pc._resolve_path("x.person", occ_index)
        self.assertEqual(cm.exception.code, "PATH_UNRESOLVED_ALIAS")
        with self.assertRaises(ProbeError) as cm:
            pc._validate_navigation(p, world, ["m.person.age"], [frozenset({"m"}), frozenset({"o"})])
        self.assertEqual(cm.exception.code, "NAVIGATION_BRANCH_UNBOUND")


class ScorerChecks(unittest.TestCase):
    def test_forbidden_oracles(self):
        for name, rejects in [
            ("empty_not_deny", ["request denied", "policy violation detected"]),
            ("incomplete_not_false", ["exists=false", "team red has no members"]),
            ("underdetermined_not_notsatisfied", ["expectation failed", "false"]),
            ("engine_fault_not_empty", ["no rows found", "unsupported query"]),
        ]:
            fails = forbidden_oracle_selftest({"name": name, "rejects": rejects})
            self.assertEqual(fails, [], f"{name}: {fails}")
        self.assertFalse(interpretation_flags(
            "empty_not_deny", "query completed with an empty result set"))

    def test_unknown_assertion_refused(self):
        fails = check_assertions({"engine_invocations": 0}, ["totally_made_up_assertion"])
        self.assertTrue(any("NO HANDLER" in f for f in fails))

    def test_subset_match(self):
        fails: list = []
        subset_match({"a": 1, "b": {"c": [1, 2]}}, {"a": 1, "b": {"c": [1, 2], "d": 9}, "x": 0},
                     "root", fails)
        self.assertEqual(fails, [])
        subset_match({"a": 2}, {"a": 1}, "root", fails)
        self.assertEqual(len(fails), 1)


if __name__ == "__main__":
    unittest.main()
