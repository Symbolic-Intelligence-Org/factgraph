from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factpy_kernel.adapters.souffle.provenance import run_package_provenance
from factpy_kernel.adapters.souffle.runner import run_package
from factpy_kernel.audit import AuditQuery, load_audit_package, render_audit_static_site
from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.domains.ecss import (
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    extend_schema_ir_with_ecss_uncertainty_predicates,
    extend_schema_ir_with_ecss_vcd_predicates,
)
from factpy_kernel.sdk import Entity, Field, Identity, Pred, Rule, SDKStore, vars as sdk_vars
from factpy_kernel.sdk.dsl.rule import RuleRef
from factpy_kernel.service.runtime_v1 import (
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_summary,
    export_runtime_package,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
    write_runtime_fact,
)


class Mission(Entity):
    mission_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    orbit_type: str = Field(cardinality="single")
    mission_profile: str = Field(cardinality="single")
    passivation_status: str = Field(cardinality="single")
    overall_compliance_status: str = Field(cardinality="single")


@dataclass(frozen=True)
class MissionScenario:
    mission_id: str
    locale: str
    name: str
    orbit_type: str
    mission_profile: str
    passivation_status: str
    disposal_prob_ppm: int
    disposal_threshold_ppm: int
    collision_prob_ppm: int
    collision_threshold_ppm: int
    expected_status: str


SCENARIOS = (
    MissionScenario(
        mission_id="SENTINEL-7",
        locale="en",
        name="Sentinel-7 LEO Observatory",
        orbit_type="LEO",
        mission_profile="single",
        passivation_status="complete",
        disposal_prob_ppm=920000,
        disposal_threshold_ppm=900000,
        collision_prob_ppm=500,
        collision_threshold_ppm=1000,
        expected_status="compliant",
    ),
    MissionScenario(
        mission_id="SWARM-9",
        locale="en",
        name="Swarm-9 Constellation Vehicle",
        orbit_type="LEO",
        mission_profile="constellation",
        passivation_status="incomplete",
        disposal_prob_ppm=920000,
        disposal_threshold_ppm=950000,
        collision_prob_ppm=1200,
        collision_threshold_ppm=1000,
        expected_status="non_compliant",
    ),
)


class Reporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def line(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def write_summary(self, path: Path) -> None:
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def main() -> None:
    args = _parse_args()
    output_root = args.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    audit_dir = output_root / "audit"
    site_dir = output_root / "site"
    provenance_dir = output_root / "provenance"
    _reset_demo_output(output_root)
    provenance_dir.mkdir(parents=True, exist_ok=True)

    reporter = Reporter()
    registry_tmpdir = tempfile.TemporaryDirectory(prefix="esa_demo_registry_")
    registry_dir = Path(registry_tmpdir.name)
    session_id: str | None = None

    try:
        sdk, rules = _build_sdk_and_rules()
        _write_registry(sdk, list(rules.values()), registry_dir)
        mission_refs = _mission_refs(sdk)

        reset_runtime_sessions_for_tests()
        session_id = _open_session(registry_dir)
        _seed_runtime_facts(session_id, mission_refs)

        evaluations = _run_demo_evaluations(session_id, rules, reporter)
        _accept_all_candidates(session_id, evaluations, reporter)

        export_resp = export_runtime_package(
            session_id,
            {
                "out_dir": str(audit_dir),
                "package_kind": "audit",
            },
        )
        _assert_ok(export_resp, "audit export")

        package = load_audit_package(audit_dir)
        audit_query = AuditQuery(package)
        site_manifest = render_audit_static_site(audit_dir, site_dir)
        _brand_esa_demo_site(site_dir)

        provenance_payloads = _write_provenance_artifacts(
            session_id=session_id,
            sdk=sdk,
            rules=rules,
            registry_dir=registry_dir,
            provenance_dir=provenance_dir,
        )

        _emit_summary(
            reporter=reporter,
            output_root=output_root,
            audit_dir=audit_dir,
            site_dir=site_dir,
            site_manifest=site_manifest,
            audit_query=audit_query,
            evaluations=evaluations,
            provenance_payloads=provenance_payloads,
        )
        reporter.write_summary(output_root / "summary.txt")
    finally:
        if session_id is not None:
            close_runtime_session(session_id)
        reset_runtime_sessions_for_tests()
        registry_tmpdir.cleanup()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the ESA ECSS compliance demo bundle.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "esa_demo_output",
        help="Target directory for audit/site/provenance/summary artifacts.",
    )
    return parser.parse_args()


def _build_sdk_and_rules() -> tuple[SDKStore, dict[str, Rule]]:
    sdk = SDKStore([Mission])
    schema_ir = extend_schema_ir_with_ecss_uncertainty_predicates(sdk.schema_ir)
    schema_ir = extend_schema_ir_with_ecss_vcd_predicates(schema_ir)
    sdk = SDKStore([Mission], schema_ir=schema_ir)

    with sdk_vars("m", "prob", "threshold") as (m, prob, threshold):
        disposal_check_rule = Rule(
            id="q.essb_u007_disposal_check",
            version="1.0.0",
            select=[m, prob],
            where=[
                Pred(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, m, prob),
                Pred(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, m, threshold),
                prob >= threshold,
            ],
            expose=True,
            condition_weights={"b0.a0": 0.8, "b0.a1": 0.5},
        )

    with sdk_vars("m", "prob", "threshold") as (m, prob, threshold):
        collision_check_rule = Rule(
            id="q.essb_u007_collision_check",
            version="1.0.0",
            select=[m, prob],
            where=[
                Pred(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, m, prob),
                Pred(ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, m, threshold),
                threshold >= prob,
            ],
            expose=True,
            condition_weights={"b0.a0": 0.9, "b0.a1": 0.4},
        )

    with sdk_vars("m", "status") as (m, status):
        passivation_check_rule = Rule(
            id="q.essb_u007_passivation_check",
            version="1.0.0",
            select=[m, status],
            where=[
                Pred("mission:passivation_status", m, status),
                status == "complete",
            ],
            expose=True,
            condition_weights={"b0.a0": 1.0},
        )

    with sdk_vars("m", "profile", "status", "prob", "collision_prob", "pass_status") as (
        m,
        profile,
        status,
        prob,
        collision_prob,
        pass_status,
    ):
        single_branch_compliance_rule = Rule(
            id="q.essb_u007_single_branch_compliance",
            version="1.0.0",
            select=[m, status],
            where=[
                Pred("mission:mission_profile", m, profile),
                profile == "single",
                RuleRef(disposal_check_rule)(m, prob),
                RuleRef(collision_check_rule)(m, collision_prob),
                RuleRef(passivation_check_rule)(m, pass_status),
                status == "compliant",
            ],
            expose=True,
            condition_weights={"b0.a0": 0.2, "b0.a1": 0.5, "b0.a2": 0.4, "b0.a3": 0.8},
        )

    with sdk_vars("m", "profile", "status", "prob", "collision_prob", "pass_status") as (
        m,
        profile,
        status,
        prob,
        collision_prob,
        pass_status,
    ):
        constellation_branch_compliance_rule = Rule(
            id="q.essb_u007_constellation_branch_compliance",
            version="1.0.0",
            select=[m, status],
            where=[
                Pred("mission:mission_profile", m, profile),
                profile == "constellation",
                RuleRef(disposal_check_rule)(m, prob),
                RuleRef(collision_check_rule)(m, collision_prob),
                RuleRef(passivation_check_rule)(m, pass_status),
                status == "compliant",
            ],
            expose=True,
            condition_weights={"b0.a0": 0.2, "b0.a1": 0.5, "b0.a2": 0.4, "b0.a3": 0.8},
        )

    with sdk_vars("m", "status") as (m, status):
        overall_compliance_rule = Rule(
            id="q.essb_u007_overall_compliance",
            version="1.0.0",
            select=[m, status],
            where=[
                [RuleRef(single_branch_compliance_rule)(m, status)],
                [RuleRef(constellation_branch_compliance_rule)(m, status)],
            ],
            expose=True,
        )

    with sdk_vars("m", "profile", "prob", "threshold", "status") as (m, profile, prob, threshold, status):
        constellation_disposal_noncompliance_rule = Rule(
            id="q.essb_u007_constellation_disposal_noncompliance",
            version="1.0.0",
            select=[m, status],
            where=[
                Pred("mission:mission_profile", m, profile),
                profile == "constellation",
                Pred(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, m, prob),
                Pred(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, m, threshold),
                threshold > prob,
                status == "non_compliant",
            ],
            expose=True,
        )

    with sdk_vars("m", "pass_status", "status") as (m, pass_status, status):
        passivation_noncompliance_rule = Rule(
            id="q.essb_u007_passivation_noncompliance",
            version="1.0.0",
            select=[m, status],
            where=[
                Pred("mission:passivation_status", m, pass_status),
                pass_status == "incomplete",
                status == "non_compliant",
            ],
            expose=True,
        )

    with sdk_vars("m", "status") as (m, status):
        overall_noncompliance_rule = Rule(
            id="q.essb_u007_overall_noncompliance",
            version="1.0.0",
            select=[m, status],
            where=[
                [RuleRef(constellation_disposal_noncompliance_rule)(m, status)],
                [RuleRef(passivation_noncompliance_rule)(m, status)],
            ],
            expose=True,
        )

    return sdk, {
        "disposal_check": disposal_check_rule,
        "collision_check": collision_check_rule,
        "passivation_check": passivation_check_rule,
        "single_branch_compliance": single_branch_compliance_rule,
        "constellation_branch_compliance": constellation_branch_compliance_rule,
        "overall_compliance": overall_compliance_rule,
        "constellation_disposal_noncompliance": constellation_disposal_noncompliance_rule,
        "passivation_noncompliance": passivation_noncompliance_rule,
        "overall_noncompliance": overall_noncompliance_rule,
    }


def _write_registry(sdk: SDKStore, rules: list[Rule], registry_dir: Path) -> None:
    registry = FileAuthoringRegistry(registry_dir)
    registry.upsert_schema_ir(sdk.schema_ir)
    for rule in rules:
        registry.register_rule_spec(sdk._compile_rule_input(rule))


def _mission_refs(sdk: SDKStore) -> dict[str, str]:
    return {
        scenario.mission_id: sdk.ref(Mission, mission_id=scenario.mission_id, locale=scenario.locale)
        for scenario in SCENARIOS
    }


def _open_session(registry_dir: Path) -> str:
    response = open_runtime_session({"registry_root": str(registry_dir)})
    _assert_ok(response, "open runtime session")
    return str(response["session"]["session_id"])


def _seed_runtime_facts(session_id: str, mission_refs: dict[str, str]) -> None:
    for scenario in SCENARIOS:
        mission_ref = mission_refs[scenario.mission_id]
        _write_fact(
            session_id,
            pred_id="mission:name",
            e_ref=mission_ref,
            rest_terms=[["string", scenario.name]],
        )
        _write_fact(
            session_id,
            pred_id="mission:orbit_type",
            e_ref=mission_ref,
            rest_terms=[["string", scenario.orbit_type]],
        )
        _write_fact(
            session_id,
            pred_id="mission:mission_profile",
            e_ref=mission_ref,
            rest_terms=[["string", scenario.mission_profile]],
        )
        _write_fact(
            session_id,
            pred_id="mission:passivation_status",
            e_ref=mission_ref,
            rest_terms=[["string", scenario.passivation_status]],
            meta={"confidence": 0.99 if scenario.expected_status == "compliant" else 0.95},
        )
        _write_fact(
            session_id,
            pred_id=ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
            e_ref=mission_ref,
            rest_terms=[["int", scenario.disposal_prob_ppm]],
            meta={"confidence": 0.85 if scenario.expected_status == "compliant" else 0.82},
        )
        _write_fact(
            session_id,
            pred_id=ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
            e_ref=mission_ref,
            rest_terms=[["int", scenario.disposal_threshold_ppm]],
        )
        _write_fact(
            session_id,
            pred_id=ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
            e_ref=mission_ref,
            rest_terms=[["int", scenario.collision_prob_ppm]],
            meta={"confidence": 0.70 if scenario.expected_status == "compliant" else 0.72},
        )
        _write_fact(
            session_id,
            pred_id=ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
            e_ref=mission_ref,
            rest_terms=[["int", scenario.collision_threshold_ppm]],
        )


def _write_fact(
    session_id: str,
    *,
    pred_id: str,
    e_ref: str,
    rest_terms: list[list[Any]],
    meta: dict[str, Any] | None = None,
) -> None:
    response = write_runtime_fact(
        session_id,
        {
            "pred_id": pred_id,
            "e_ref": e_ref,
            "rest_terms": rest_terms,
            **({"meta": meta} if meta else {}),
        },
        kind="add",
    )
    _assert_ok(response, f"write fact {pred_id}")


def _run_demo_evaluations(session_id: str, rules: dict[str, Rule], reporter: Reporter) -> dict[str, dict[str, Any]]:
    evaluations: dict[str, dict[str, Any]] = {}
    evaluation_specs = {
        "disposal_check": {
            "derivation_id": "drv.disposal_check",
            "target": ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
            "head_vars": ["$m", "$prob"],
            "where": [["ruleref", "q.essb_u007_disposal_check", "1.0.0", ["$m", "$prob"]]],
        },
        "collision_check": {
            "derivation_id": "drv.collision_check",
            "target": ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
            "head_vars": ["$m", "$prob"],
            "where": [["ruleref", "q.essb_u007_collision_check", "1.0.0", ["$m", "$prob"]]],
        },
        "passivation_check": {
            "derivation_id": "drv.passivation_check",
            "target": "mission:passivation_status",
            "head_vars": ["$m", "$status"],
            "where": [["ruleref", "q.essb_u007_passivation_check", "1.0.0", ["$m", "$status"]]],
        },
        "overall_compliance": {
            "derivation_id": "drv.overall_compliance",
            "target": "mission:overall_compliance_status",
            "head_vars": ["$m", "$status"],
            "where": [["ruleref", "q.essb_u007_overall_compliance", "1.0.0", ["$m", "$status"]]],
        },
        "overall_noncompliance": {
            "derivation_id": "drv.overall_noncompliance",
            "target": "mission:overall_compliance_status",
            "head_vars": ["$m", "$status"],
            "where": [["ruleref", "q.essb_u007_overall_noncompliance", "1.0.0", ["$m", "$status"]]],
        },
    }

    reporter.line("=== ESA DEMO: ECSS Compliance Evaluation ===")
    for label, spec in evaluation_specs.items():
        response = evaluate_runtime_derivation(
            session_id,
            {
                "derivation": {
                    "derivation_id": spec["derivation_id"],
                    "version": "1.0.0",
                    "target": spec["target"],
                    "head_vars": spec["head_vars"],
                    "where": spec["where"],
                    "mode": "native",
                }
            },
        )
        _assert_ok(response, f"evaluate {label}")
        candidates = response["evaluation"]["candidates"]
        if not candidates:
            raise RuntimeError(f"{label}: no candidates returned")
        candidate = candidates[0]
        summary_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
        _assert_ok(summary_resp, f"summary {label}")
        evaluations[label] = {
            "response": response,
            "candidate": candidate,
            "summary": summary_resp,
            "rule": rules[label],
        }
        reporter.line(
            f"- {label}: candidate_id={candidate['candidate_id']} "
            f"confidence_kind={candidate.get('confidence_kind')} "
            f"terms={_compact_terms(candidate.get('payload', {}).get('terms', []))}"
        )
    reporter.line()
    return evaluations


def _accept_all_candidates(session_id: str, evaluations: dict[str, dict[str, Any]], reporter: Reporter) -> None:
    reporter.line("=== ESA DEMO: Candidate Acceptance ===")
    for label, bundle in evaluations.items():
        response = accept_runtime_derivation(session_id, {"candidate": bundle["candidate"]})
        _assert_ok(response, f"accept {label}")
        reporter.line(f"- accepted {label}: terminal={response['meta']['terminal']}")
    reporter.line()


def _write_provenance_artifacts(
    *,
    session_id: str,
    sdk: SDKStore,
    rules: dict[str, Rule],
    registry_dir: Path,
    provenance_dir: Path,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    provenance_specs = {
        "disposal_check": rules["disposal_check"],
        "constellation_disposal_noncompliance": rules["constellation_disposal_noncompliance"],
        "overall_compliance": rules["overall_compliance"],
    }
    for name, rule in provenance_specs.items():
        with tempfile.TemporaryDirectory(prefix=f"esa_demo_{name}_") as work_dir:
            query_rel = f"{name}_query"
            compiled_where = sdk._compile_rule_input(rule)["where"]
            export_resp = export_runtime_package(
                session_id,
                {
                    "out_dir": work_dir,
                    "package_kind": "inference",
                    "query": {
                        "where": compiled_where,
                        "query_rel": query_rel,
                        "registry_root": str(registry_dir),
                    },
                },
            )
            _assert_ok(export_resp, f"export provenance package {name}")
            run_package(Path(work_dir), ["__query__"], engine="souffle")
            out_path = Path(work_dir) / "outputs" / f"{query_rel}.out.facts"
            rows = [line.split("\t") for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not rows:
                raise RuntimeError(f"{name}: no query rows for provenance")
            provenance_query = query_rel + "(" + ", ".join(f'"{cell}"' for cell in rows[0]) + ")"
            trees = run_package_provenance(Path(work_dir), [provenance_query])
            if not trees:
                raise RuntimeError(f"{name}: no proof trees returned")
            tree = trees[0]
            payload = {
                "query": tree.query,
                "rules": tree.rules,
                "root": asdict(tree.root),
            }
            (provenance_dir / f"{name}.json").write_text(
                _json_dumps(payload),
                encoding="utf-8",
            )
            output[name] = payload
    return output


def _emit_summary(
    *,
    reporter: Reporter,
    output_root: Path,
    audit_dir: Path,
    site_dir: Path,
    site_manifest: dict[str, Any],
    audit_query: AuditQuery,
    evaluations: dict[str, dict[str, Any]],
    provenance_payloads: dict[str, dict[str, Any]],
) -> None:
    reporter.line("=== ESA DEMO BUNDLE ===")
    reporter.line(f"output_root: {output_root}")
    reporter.line(f"audit_dir:   {audit_dir}")
    reporter.line(f"site_dir:    {site_dir}")
    reporter.line()
    reporter.line("Scenarios:")
    for scenario in SCENARIOS:
        reporter.line(
            f"- {scenario.mission_id}: {scenario.name} "
            f"profile={scenario.mission_profile} expected={scenario.expected_status}"
        )
    reporter.line()

    reporter.line("Evaluation Summary:")
    for label, bundle in evaluations.items():
        candidate = bundle["candidate"]
        summary = bundle["summary"]
        tree_summary = summary.get("summary", {})
        certainty = summary.get("certainty_summary")
        reporter.line(
            f"- {label}: support_kind={tree_summary.get('support_kind')} "
            f"rule_ref_count={tree_summary.get('rule_ref_count')} "
            f"witness_assertion_count={tree_summary.get('witness_assertion_count')}"
        )
        if certainty is not None:
            reporter.line(
                f"  certainty={certainty.get('aggregate_certainty')} "
                f"aggregation={certainty.get('aggregation')}"
            )
        reporter.line(f"  candidate_id={candidate['candidate_id']}")
    reporter.line()

    reporter.line("Provenance Artifacts:")
    for name, payload in provenance_payloads.items():
        root = payload["root"]
        reporter.line(
            f"- {name}.json: relation={root.get('relation')} "
            f"rule_number={root.get('rule_number')} child_count={len(root.get('children', []))}"
        )
    reporter.line()

    reporter.line("Audit Bundle:")
    reporter.line(f"- accepted_candidates={len(audit_query.list_candidates())}")
    reporter.line(f"- compliance_matrix_rows={len(audit_query.list_compliance_matrix())}")
    reporter.line(f"- site_pages={site_manifest.get('assertion_count', 0) + site_manifest.get('rule_trace_count', 0) + site_manifest.get('candidate_evidence_count', 0)} (see site_manifest.json for full counts)")
    reporter.line(f"- site_index={site_dir / 'index.html'}")
    reporter.line()


def _reset_demo_output(output_root: Path) -> None:
    for child_name in ("audit", "site", "provenance"):
        child = output_root / child_name
        if child.exists():
            shutil.rmtree(child)
    summary_path = output_root / "summary.txt"
    if summary_path.exists():
        summary_path.unlink()


def _brand_esa_demo_site(site_dir: Path) -> None:
    index_path = site_dir / "index.html"
    if not index_path.exists():
        return
    html = index_path.read_text(encoding="utf-8")
    html = html.replace(
        "<title>Compliance Audit Review Site</title>",
        "<title>ESSB-ST-U-007 Space Debris Mitigation Compliance Audit</title>",
        1,
    )
    html = html.replace(
        "<h1>Compliance Audit Review Site</h1>",
        "<h1>ESSB-ST-U-007 Space Debris Mitigation Compliance Audit</h1>",
        1,
    )
    html = html.replace(
        "Review verdicts, inspect evidence trees, understand certainty, and share the exported audit bundle with any reviewer in a browser.",
        "Two missions, nine ECSS rules, deterministic compliance decisions, certainty scoring, and exportable audit evidence for ESA review.",
        1,
    )
    index_path.write_text(html, encoding="utf-8")


def _compact_terms(terms: list[dict[str, Any]]) -> str:
    values = []
    for term in terms:
        if isinstance(term, dict):
            values.append(str(term.get("value")))
    return "[" + ", ".join(values) + "]"


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _assert_ok(response: dict[str, Any], label: str) -> None:
    if response.get("ok"):
        return
    raise RuntimeError(f"{label} failed: {response}")


if __name__ == "__main__":
    main()
