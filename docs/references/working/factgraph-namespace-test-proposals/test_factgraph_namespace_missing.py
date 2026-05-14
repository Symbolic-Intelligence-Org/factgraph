from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from factgraph.sdk import Branch, Entity, FactGraph, Field, Identity, Inference, Pred
from factgraph.sdk import vars as sdk_vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def _seed_user(fg: FactGraph, *, user_id: str = "u-1") -> str:
    ref = fg.read.ref(User, user_id=user_id)
    fg.write.set(User.name, ref, "Alice", meta={"source": "seed"})
    fg.write.set(User.tag_seed, ref, "vip", meta={"source": "seed"})
    return ref


def _tag_inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.namespace.tag",
            version="v1",
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


class FactGraphSchemaValidateProvenanceNamespaceTests(unittest.TestCase):
    def test_schema_validate_provenance_returns_validation_report(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        report = fg.schema.validate_provenance(
            {
                "derived_rule_id": "rule.namespace",
                "derived_rule_version": "v1",
                "run_id": "run-1",
                "support_kind": "native_where_v1",
                "support_digest": "sha256:" + ("a" * 64),
            },
            standard="derivation_v1",
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.errors, [])


class FactGraphWriteEditNamespaceTests(unittest.TestCase):
    def test_write_edit_context_commits_field_changes(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        fg.write.set(User.name, ref, "Alice", meta={"source": "seed"})

        with fg.write.edit(User, user_id="u-1") as editor:
            editor.name.set("Alicia")

        self.assertEqual(fg.read.get(User, user_id="u-1").name, "Alicia")


class FactGraphEvalAcceptManyNamespaceTests(unittest.TestCase):
    def test_eval_accept_many_accepts_evaluated_candidates(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        _seed_user(fg)

        candidates = fg.eval.evaluate(_tag_inference())
        results = fg.eval.accept_many(candidates)

        self.assertEqual(len(results), 1)
        self.assertEqual(tuple(fg.read.get(User, user_id="u-1").tag), ("vip",))


class FactGraphAuditNamespaceTests(unittest.TestCase):
    def test_audit_explain_fact_returns_active_claims_for_fact(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = _seed_user(fg)

        explanation = fg.audit.explain_fact("user:name", ref, "Alice")

        self.assertEqual(explanation["pred_id"], "user:name")
        self.assertEqual(explanation["e_ref"], ref)
        self.assertEqual(len(explanation["active_claims"]), 1)
        self.assertEqual(tuple(explanation["active_claims"][0]["args"][1:]), ("Alice",))

    def test_audit_conflicts_reports_active_ids_and_chosen_id(self) -> None:
        fg = FactGraph.create(schema_classes=[User])
        ref = fg.read.ref(User, user_id="u-1")
        first = fg.write.set(User.name, ref, "Alice", meta={"source": "a"})
        second = fg.write.set(User.name, ref, "Alicia", meta={"source": "b"})

        result = fg.audit.conflicts("user:name", ref)

        self.assertEqual(set(result["active_asrt_ids"]), {first, second})
        self.assertIn(result["chosen_asrt_id"], {first, second})


class FactGraphPackageRunNamespaceTests(unittest.TestCase):
    def test_package_run_package_delegates_to_flat_method(self) -> None:
        fg = FactGraph.create(schema_classes=[User])

        with patch.object(fg, "run_package", return_value={"ok": True}) as run_package:
            result = fg.package.run_package(
                Path("/tmp/package"),
                entrypoints=["main"],
                engine="souffle",
            )

        run_package.assert_called_once_with(
            Path("/tmp/package"),
            entrypoints=["main"],
            engine="souffle",
        )
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
