from __future__ import annotations

import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import cli as authoring_cli


class TutorialDocsV1Tests(unittest.TestCase):
    def test_all_tutorial_relative_links_exist(self) -> None:
        for path in _tutorial_docs():
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"\]\((\./[^)]+)\)", text):
                rel = match.group(1)
                target = (path.parent / rel[2:]).resolve()
                self.assertTrue(target.exists(), msg=f"broken link in {path.name}: {rel}")

    def test_tutorial_readme_lists_expected_core_tutorials(self) -> None:
        readme = _tutorials_root() / "README.md"
        text = readme.read_text(encoding="utf-8")
        for filename in [
            "01-环境与安装.md",
            "02-第一次-Authoring-Preflight（JSON 与 DSL）.md",
            "03-Apply-Execute-与-Registry.md",
            "04-Registry-只读查看与运维命令.md",
            "05-导出审计包与静态审计页面.md",
            "06-事务策略与排障（v1-v2）.md",
            "07-完整示例项目模板（可复制运行）.md",
            "08-团队内-Onboarding-清单.md",
            "09-CLI-命令速查.md",
            "10-排障手册（CLI-Registry-Audit）.md",
            "11-Cookbook-从-DSL-到-Apply.md",
            "12-Cookbook-排查一次失败的-Apply.md",
            "13-Cookbook-生成并查看审计站点.md",
            "14-生产化注意事项（registry并发-事务-v2）.md",
            "15-SDK-快速开始（Python 直接定义）.md",
        ]:
            self.assertIn(filename, text)

    def test_cli_reference_covers_current_subcommands_and_flags(self) -> None:
        parser = authoring_cli._build_parser()  # noqa: SLF001 - docs smoke-check
        subparsers = next(action for action in parser._actions if action.dest == "command")  # noqa: SLF001
        command_names = set(subparsers.choices.keys())

        text = (_tutorials_root() / "09-CLI-命令速查.md").read_text(encoding="utf-8")
        for command in command_names:
            self.assertIn(f"`{command}`", text)
        self.assertIn("--transaction-policy", text)
        self.assertIn("--safe", text)
        self.assertIn("apply_run_ids", text)

    def test_troubleshooting_covers_core_apply_paths(self) -> None:
        text = (_tutorials_root() / "10-排障手册（CLI-Registry-Audit）.md").read_text(encoding="utf-8")
        for keyword in [
            "prevalidate_blocked",
            "runtime_partial",
            "replay",
            "idempotency_conflict",
            "authoring_apply_runs/<req>.html",
            "registry-show --kind apply-run",
        ]:
            self.assertIn(keyword, text)

    def test_cookbook_docs_cover_target_tasks(self) -> None:
        cookbook_apply = (_tutorials_root() / "11-Cookbook-从-DSL-到-Apply.md").read_text(encoding="utf-8")
        self.assertIn("apply-execute", cookbook_apply)
        self.assertIn("registry-show", cookbook_apply)
        self.assertIn("workflow-dry-run", cookbook_apply)

        cookbook_fail = (_tutorials_root() / "12-Cookbook-排查一次失败的-Apply.md").read_text(encoding="utf-8")
        for keyword in ["prevalidate_blocked", "runtime_partial", "idempotency_conflict"]:
            self.assertIn(keyword, cookbook_fail)

        cookbook_audit = (_tutorials_root() / "13-Cookbook-生成并查看审计站点.md").read_text(encoding="utf-8")
        self.assertIn("render_audit_static_site", cookbook_audit)
        self.assertIn("authoring_apply_runs/", cookbook_audit)

    def test_production_notes_and_sdk_tutorial_cover_key_topics(self) -> None:
        prod_notes = (_tutorials_root() / "14-生产化注意事项（registry并发-事务-v2）.md").read_text(encoding="utf-8")
        for keyword in [
            "FileAuthoringRegistry",
            "best_effort_no_rollback_v1",
            "prevalidate_no_partial_strict_v2",
            "registry-list --kind apply_run_ids",
            "registry-show --kind apply-run",
        ]:
            self.assertIn(keyword, prod_notes)

        sdk_tutorial = (_tutorials_root() / "15-SDK-快速开始（Python 直接定义）.md").read_text(encoding="utf-8")
        for keyword in [
            "class Person(Entity)",
            "SDKStore",
            "SDKRegistry",
            "compile_schema_from_classes",
            "schema_preflight_from_classes",
            "build_authoring_schema_from_classes",
            "apply_schema_classes",
        ]:
            self.assertIn(keyword, sdk_tutorial)

    def test_derivation_examples_use_head_vars_and_explain_arg_specs_mapping(self) -> None:
        for filename in [
            "02-第一次-Authoring-Preflight（JSON 与 DSL）.md",
            "07-完整示例项目模板（可复制运行）.md",
            "08-团队内-Onboarding-清单.md",
            "11-Cookbook-从-DSL-到-Apply.md",
        ]:
            text = (_tutorials_root() / filename).read_text(encoding="utf-8")
            self.assertIn('head=Person.country(person=E, country=country)', text, msg=filename)
            self.assertIn('materialize_as="fact"', text, msg=filename)
            self.assertIn("arg_specs", text, msg=filename)

        cli_ref = (_tutorials_root() / "09-CLI-命令速查.md").read_text(encoding="utf-8")
        self.assertIn("head + materialize_as", cli_ref)
        self.assertIn("target + head_vars", cli_ref)
        self.assertIn("arg_specs", cli_ref)

    def test_onboarding_contains_success_criteria_and_issue_template(self) -> None:
        text = (_tutorials_root() / "08-团队内-Onboarding-清单.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("成功标准（最小）"), 4)
        self.assertIn("故障上报模板（建议复制）", text)
        self.assertIn("[Onboarding Issue]", text)

    def test_full_sdk_tutorial_15_matches_current_sdk_surface(self) -> None:
        text = (_source_tutorials_root() / "15-SDK-快速开始（Python 直接定义）.md").read_text(encoding="utf-8")

        self.assertIn("from factpy_kernel.adapters.souffle.package import ExportOptions", text)
        self.assertNotIn("from factpy_kernel.export.package import ExportOptions", text)
        self.assertNotIn("Rule / Derivation 的 runtime builder 还未实装", text)

        for keyword in [
            "Pred(",
            "Not([",
            "SDKRegistry.apply_schema_classes(...)",
            "SDKDSLError",
            "SDKRegistryError",
            "SDKSchemaError",
            "SDKStoreError",
        ]:
            self.assertIn(keyword, text)


def _tutorials_root() -> Path:
    return _repo_root() / "docs" / "tutorials"


def _source_tutorials_root() -> Path:
    return _repo_root() / "tutorials"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _tutorial_docs() -> list[Path]:
    return sorted(_tutorials_root().glob("*.md"))


if __name__ == "__main__":
    unittest.main()
