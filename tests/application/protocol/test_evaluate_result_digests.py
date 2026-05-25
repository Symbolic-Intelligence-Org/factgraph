from __future__ import annotations

import unittest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluate_result import (
    canonical_bytes_for_evaluate,
    claim_digest_for,
    closed_head_digest_for_parts,
    evidence_ref_id_for,
    expr_digest_for_payload,
    new_run_id,
    result_digest_for,
    result_id_for,
    row_id_for,
    rule_set_digest_for_entries,
    semantics_digest_for,
    view_snapshot_digest_for_parts,
)
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.semantics import SemanticsProfile


class EvaluateResultDigestTests(unittest.TestCase):
    def test_canonical_bytes_are_deterministic_for_mapping_order(self) -> None:
        left = canonical_bytes_for_evaluate({"b": 2, "a": [1, 2]})
        right = canonical_bytes_for_evaluate({"a": [1, 2], "b": 2})

        self.assertEqual(left, right)

    def test_namespaced_ids_and_digest_tokens_are_deterministic(self) -> None:
        run_id = "run_v1:" + "a" * 64
        expr_digest = sha256_token(b"expr")
        rule_set_digest = sha256_token(b"rules")
        view_snapshot_digest = sha256_token(b"view")
        semantics_digest = sha256_token(b"semantics")
        head_content_digest = sha256_hex(b"head")

        result_id = result_id_for(
            run_id=run_id,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            engine="native",
            head_id="head",
            head_content_digest=head_content_digest,
        )
        claim_digest = claim_digest_for("fact_triple", "Person:exists", {"person": "p1"})
        row_id = row_id_for(run_id, {"person": "p1"})
        closed_head_digest = closed_head_digest_for_parts("head", head_content_digest)
        ref_id = evidence_ref_id_for(result_id, row_id, claim_digest, closed_head_digest)

        self.assertRegex(result_id, r"^evalr_v1:[0-9a-f]{64}$")
        self.assertRegex(ref_id, r"^evref_v1:[0-9a-f]{64}$")
        self.assertRegex(claim_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(row_id, row_id_for(run_id, {"person": "p1"}))
        self.assertIn(":", row_id)

    def test_new_run_id_uses_namespaced_hex_token(self) -> None:
        self.assertRegex(new_run_id(), r"^run_v1:[0-9a-f]{64}$")

    def test_result_digest_excludes_evaluated_at_and_ref_id(self) -> None:
        run_id = "run_v1:" + "b" * 64
        result_id = "evalr_v1:" + "c" * 64
        row_digest = sha256_token(b"row")
        kwargs = dict(
            result_id=result_id,
            run_id=run_id,
            row_digests=(row_digest,),
            head_id="head",
            head_content_digest=sha256_hex(b"head"),
            engine="native",
            engine_version=None,
            adapter_version=None,
            expr_digest=sha256_token(b"expr"),
            rule_set_digest=sha256_token(b"rules"),
            view_snapshot_digest=sha256_token(b"view"),
            semantics_digest=None,
        )

        self.assertEqual(result_digest_for(**kwargs), result_digest_for(**kwargs))
        self.assertNotIn("evaluated_at", result_digest_for(**kwargs))
        self.assertNotIn("evref_v1", result_digest_for(**kwargs))

    def test_semantics_digest_uses_normalized_profile_content(self) -> None:
        profile = SemanticsProfile(
            name="default",
            engine="native",
            version="1.0",
            engine_options={"mode": "strict"},
            uncertainty_projection={},
            temporal_projection={"mode": "none"},
            rule_projection={},
            certainty_projection={},
            output_readback={},
            fallback="reject_unconfigured",
        )
        same = SemanticsProfile(
            name="default",
            engine="native",
            version="1.0",
            engine_options={"mode": "strict"},
            uncertainty_projection={},
            temporal_projection={"mode": "none"},
            rule_projection={},
            certainty_projection={},
            output_readback={},
            fallback="reject_unconfigured",
        )

        self.assertIsNone(semantics_digest_for(None))
        self.assertEqual(semantics_digest_for(profile), semantics_digest_for(same))

    def test_view_snapshot_digest_uses_store_substrate_without_placeholder(self) -> None:
        digest = view_snapshot_digest_for_parts(
            db_id="db:test",
            base_tx_id="tx:" + "1" * 64,
            schema_digest=sha256_token(b"schema"),
            asrt_ids=(),
        )

        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        with self.assertRaises(ProtocolShapeError):
            view_snapshot_digest_for_parts(
                db_id="db:test",
                base_tx_id="tx:" + "1" * 64,
                schema_digest="",
                asrt_ids=(),
            )

    def test_expr_and_rule_set_digest_helpers_are_deterministic(self) -> None:
        expr = expr_digest_for_payload("rule_expr", {"branches": [1, 2], "head": "h"})
        rules = rule_set_digest_for_entries((("b", sha256_hex(b"b")), ("a", sha256_hex(b"a"))))
        rules_reordered = rule_set_digest_for_entries((("a", sha256_hex(b"a")), ("b", sha256_hex(b"b"))))

        self.assertRegex(expr, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(rules, rules_reordered)


if __name__ == "__main__":
    unittest.main()
