from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from factpy_kernel.audit import AuditQuery, load_audit_package, render_audit_static_site
from factpy_kernel.evidence.write_protocol import set_field
from factpy_kernel.export.package import ExportOptions, export_package
from factpy_kernel.store.api import Store
from factpy_kernel.store.ledger import MetaRow


class AuditStaticUIV1Tests(unittest.TestCase):
    def test_render_audit_static_site_accept_run(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditui-1",
            rest_terms=[("entity_ref", "idref_v1:Person:c_ui1")],
            meta={
                "source": "derivation.accept",
                "run_id": "run-auditui-1",
                "materialize_id": "mat-auditui-1",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "key_tuple_digest": "sha256:" + ("a" * 64),
                "cand_key_digest": "sha256:" + ("b" * 64),
                "support_digest": "sha256:" + ("c" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 100)

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            site_dir = Path(tmp) / "site"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            site_manifest = render_audit_static_site(pkg_dir, site_dir)

            self.assertEqual(site_manifest["audit_ui_site_version"], "audit_ui_site_v1")
            self.assertEqual(site_manifest["run_count"], 1)
            self.assertGreaterEqual(site_manifest["decision_count"], 1)
            self.assertEqual(site_manifest["assertion_count"], 1)
            self.assertIn("indexes/event_kinds.html", site_manifest["indexes"])
            self.assertIn("indexes/error_classes.html", site_manifest["indexes"])
            self.assertIn("indexes/predicates.html", site_manifest["indexes"])
            self.assertEqual(site_manifest["search"], "search.html")
            self.assertEqual(site_manifest["ui_index"], "ui_index.json")
            self.assertEqual(site_manifest["authoring_apply_events"], "authoring_apply_events.html")
            self.assertEqual(site_manifest["authoring_apply_event_count"], 0)
            index_path = site_dir / "index.html"
            self.assertTrue(index_path.exists())
            index_html = index_path.read_text(encoding="utf-8")
            self.assertIn("run-auditui-1", index_html)
            self.assertIn(f"runs/{quote('run-auditui-1', safe='')}.html", index_html)
            self.assertIn("indexes/event_kinds.html", index_html)
            self.assertIn("indexes/predicates.html", index_html)
            self.assertIn("search.html", index_html)
            self.assertIn("authoring_apply_events.html", index_html)
            search_html = (site_dir / "search.html").read_text(encoding="utf-8")
            self.assertIn("Audit Search", search_html)
            self.assertIn("ui_index.json", search_html)
            self.assertIn("id='q'", search_html)
            self.assertIn("id='type'", search_html)
            self.assertIn("id='results'", search_html)
            self.assertIn('qp.has("type")', search_html)
            self.assertIn("option value='event_kind'", search_html)
            self.assertIn("option value='authoring_apply_request_id'", search_html)
            self.assertIn("option value='authoring_apply_status'", search_html)
            self.assertIn("option value='authoring_apply_section'", search_html)
            ui_index = json.loads((site_dir / "ui_index.json").read_text(encoding="utf-8"))
            self.assertEqual(ui_index["audit_ui_index_version"], "audit_ui_index_v1")
            self.assertEqual(ui_index["counts"]["runs"], 1)
            self.assertEqual(ui_index["counts"]["assertions"], 1)
            self.assertEqual(ui_index["counts"]["authoring_apply_events"], 0)
            self.assertEqual(ui_index["links"]["search"], "search.html")
            self.assertEqual(ui_index["links"]["authoring_apply_events"], "authoring_apply_events.html")
            self.assertTrue(any(item["event_kind"] == "accept_write" for item in ui_index["filters"]["event_kinds"]))
            self.assertTrue(any(item["event_kind"] == "mapping_decision" for item in ui_index["filters"]["event_kinds"]))
            self.assertTrue(any(item["pred_id"] == "er:canon_of" for item in ui_index["filters"]["predicates"]))
            self.assertEqual(ui_index["runs"][0]["path"], f"runs/{quote('run-auditui-1', safe='')}.html")
            self.assertEqual(ui_index["lookup"]["run_pages"]["run-auditui-1"], f"runs/{quote('run-auditui-1', safe='')}.html")
            self.assertEqual(ui_index["lookup"]["assertion_pages"][asrt_id], f"assertions/{quote(asrt_id, safe='')}.html")

            data = load_audit_package(pkg_dir)
            query = AuditQuery(data)
            decision_id = query.list_decisions(event_source="accept")[0]["decision_id"]
            run_page = site_dir / "runs" / f"{quote('run-auditui-1', safe='')}.html"
            decision_page = site_dir / "decisions" / f"{quote(decision_id, safe='')}.html"
            assertion_page = site_dir / "assertions" / f"{quote(asrt_id, safe='')}.html"
            self.assertTrue(run_page.exists())
            self.assertTrue(decision_page.exists())
            self.assertTrue(assertion_page.exists())
            run_html = run_page.read_text(encoding="utf-8")
            decision_html = decision_page.read_text(encoding="utf-8")
            self.assertIn("Timeline", run_html)
            self.assertIn(f"assertions/{quote(asrt_id, safe='')}.html", run_html)
            self.assertIn("Assertion Summaries", run_html)
            self.assertIn("source=derivation.accept", run_html)
            self.assertIn("claim_arg=0:entity_ref=idref_v1:Person:c_ui1", run_html)
            self.assertIn("accept_write", decision_html)
            self.assertIn(f"assertions/{quote(asrt_id, safe='')}.html", decision_html)
            self.assertIn("Assertion Summaries", decision_html)
            self.assertIn("source=derivation.accept", decision_html)
            assertion_html = assertion_page.read_text(encoding="utf-8")
            self.assertIn("Assertion", assertion_html)
            self.assertIn("claim_arg", assertion_html)
            self.assertIn("meta_time", assertion_html)
            self.assertIn("Predicate Index", (site_dir / "indexes" / "predicates.html").read_text(encoding="utf-8"))
            event_kinds_html = (site_dir / "indexes" / "event_kinds.html").read_text(encoding="utf-8")
            self.assertIn("accept_write", event_kinds_html)
            self.assertIn("mapping_decision", event_kinds_html)
            self.assertIn("../search.html?q=accept_write&amp;type=event_kind", event_kinds_html)
            predicates_html = (site_dir / "indexes" / "predicates.html").read_text(encoding="utf-8")
            self.assertIn("er:canon_of", predicates_html)
            self.assertIn("../search.html?q=er%3Acanon_of&amp;type=pred_id", predicates_html)
            self.assertIn(decision_id, ui_index["lookup"]["run_to_decisions"]["run-auditui-1"])
            self.assertIn(asrt_id, ui_index["lookup"]["decision_to_assertions"][decision_id])
            self.assertEqual(ui_index["lookup"]["assertion_to_runs"][asrt_id], ["run-auditui-1"])
            self.assertIn(decision_id, ui_index["lookup"]["assertion_to_decisions"][asrt_id])
            authoring_apply_html = (site_dir / "authoring_apply_events.html").read_text(encoding="utf-8")
            self.assertIn("Authoring Apply Events", authoring_apply_html)
            self.assertIn("event_count=0", authoring_apply_html)

    def test_render_audit_static_site_conflict_failure_page(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break=None))
        asrt_1 = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditui-conflict",
            rest_terms=[("entity_ref", "idref_v1:Person:c1")],
            meta={"source": "hr", "source_loc": "row-1", "run_id": "run-auditui-2"},
        )
        asrt_2 = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditui-conflict",
            rest_terms=[("entity_ref", "idref_v1:Person:c2")],
            meta={"source": "crm", "source_loc": "row-2", "run_id": "run-auditui-2"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            site_dir = Path(tmp) / "site"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            render_audit_static_site(pkg_dir, site_dir)

            query = AuditQuery(load_audit_package(pkg_dir))
            decision_id = query.list_decisions(event_kind="mapping_conflict")[0]["decision_id"]
            decision_page = site_dir / "decisions" / f"{quote(decision_id, safe='')}.html"
            html = decision_page.read_text(encoding="utf-8")
            self.assertIn("mapping_conflict", html)
            self.assertIn("failures=1", html)
            self.assertIn("Assertion Summaries", html)
            self.assertIn("source=hr", html)
            self.assertIn("source=crm", html)
            error_classes_html = (site_dir / "indexes" / "error_classes.html").read_text(encoding="utf-8")
            self.assertIn("mapping_conflict", error_classes_html)
            self.assertIn("../search.html?q=mapping_conflict&amp;type=error_class", error_classes_html)
            site_manifest_payload = json.loads((site_dir / "site_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(site_manifest_payload["package_kind"], "audit")
            self.assertEqual(site_manifest_payload["assertion_count"], 2)
            ui_index = json.loads((site_dir / "ui_index.json").read_text(encoding="utf-8"))
            self.assertEqual(ui_index["counts"]["failures"], 1)
            self.assertTrue(any(item["error_class"] == "mapping_conflict" for item in ui_index["filters"]["error_classes"]))
            self.assertEqual(ui_index["links"]["search"], "search.html")
            self.assertEqual(set(ui_index["lookup"]["run_to_assertions"]["run-auditui-2"]), {asrt_1, asrt_2})
            self.assertIn(decision_id, ui_index["lookup"]["decision_to_runs"])
            self.assertEqual(ui_index["lookup"]["decision_to_runs"][decision_id], ["run-auditui-2"])
            self.assertEqual(set(ui_index["lookup"]["decision_to_assertions"][decision_id]), {asrt_1, asrt_2})

    def test_render_audit_static_site_includes_authoring_apply_events_summary(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            site_dir = Path(tmp) / "site"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            (pkg_dir / "authoring_apply_events.jsonl").write_text(
                "\n".join(
                    [
                        '{"kind":"authoring_apply_execute_action","action_id":"action:0:schema_preflight","section":"schema_preflight","status":"applied"}',
                        '{"kind":"authoring_apply_execute_run","apply_request_id":"req-1","status":"ok","ok":true,"idempotency":{"apply_request_id":"req-1","plan_digest":"sha256:abc","replayed":false},"transaction":{"policy":"best_effort_no_rollback_v1","prevalidate_before_write":true,"partial_apply":false}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            site_manifest = render_audit_static_site(pkg_dir, site_dir)
            self.assertEqual(site_manifest["authoring_apply_event_count"], 2)
            ui_index = json.loads((site_dir / "ui_index.json").read_text(encoding="utf-8"))
            self.assertEqual(ui_index["counts"]["authoring_apply_events"], 2)
            self.assertEqual(ui_index["authoring_apply"]["status_counts"]["applied"], 1)
            self.assertTrue(any(item["status"] == "applied" for item in ui_index["filters"]["authoring_apply_statuses"]))
            self.assertTrue(any(item["apply_request_id"] == "req-1" for item in ui_index["filters"]["authoring_apply_request_ids"]))
            self.assertTrue(any(item["section"] == "schema_preflight" for item in ui_index["filters"]["authoring_apply_sections"]))
            self.assertEqual(
                ui_index["lookup"]["authoring_apply_request_pages"]["req-1"],
                f"authoring_apply_runs/{quote('req-1', safe='')}.html",
            )
            self.assertEqual(
                ui_index["lookup"]["authoring_apply_run_pages"]["req-1"],
                f"authoring_apply_runs/{quote('req-1', safe='')}.html",
            )
            html = (site_dir / "authoring_apply_events.html").read_text(encoding="utf-8")
            self.assertIn("action:0:schema_preflight", html)
            self.assertIn("req-1", html)
            self.assertIn(f"id='req-{quote('req-1', safe='')}'", html)
            self.assertIn(f"authoring_apply_runs/{quote('req-1', safe='')}.html", html)
            detail_html = (
                site_dir / "authoring_apply_runs" / f"{quote('req-1', safe='')}.html"
            ).read_text(encoding="utf-8")
            self.assertIn("Authoring Apply Run req-1", detail_html)
            self.assertIn("authoring_apply_execute_run", detail_html)
            self.assertIn("Idempotency", detail_html)
            self.assertIn("Transaction", detail_html)
            self.assertIn("prevalidate_before_write=True", detail_html)
            self.assertIn("plan_digest=sha256:abc", detail_html)
            self.assertIn("execution_path=success", detail_html)
            self.assertIn("execution_path_label=Success", detail_html)
            self.assertIn("execution_path_counts={&quot;success&quot;: 1}", detail_html)
            self.assertIn("failure_summary.first_failure_action_id=None", detail_html)
            self.assertIn("failure_summary.blocked_action_diagnostic_codes=[]", detail_html)
            self.assertIn("action_stats.diagnostic_code_counts={}", detail_html)


def _mapping_schema(tie_break: object) -> dict:
    predicate: dict[str, object] = {
        "pred_id": "er:canon_of",
        "arg_specs": [
            {"name": "mention", "type_domain": "entity_ref"},
            {"name": "canonical", "type_domain": "entity_ref"},
        ],
        "group_key_indexes": [0],
        "cardinality": "functional",
        "is_mapping": True,
        "mapping_kind": "single_valued",
        "mapping_key_positions": [0],
        "mapping_value_positions": [1],
    }
    if tie_break is not None:
        predicate["tie_break"] = tie_break
    return {
        "schema_ir_version": "v1",
        "entities": [{"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]}],
        "predicates": [predicate],
        "projection": {"entities": [], "predicates": ["er:canon_of"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _set_ingested_at(store: Store, asrt_id: str, epoch_nanos: int) -> None:
    replaced = False
    updated: list[MetaRow] = []
    for row in store.ledger._meta_rows:
        if row.asrt_id == asrt_id and row.key == "ingested_at":
            updated.append(MetaRow(asrt_id=row.asrt_id, key=row.key, kind="time", value=epoch_nanos))
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        raise AssertionError(f"missing ingested_at for asrt_id={asrt_id}")
    store.ledger._meta_rows = updated


if __name__ == "__main__":
    unittest.main()
