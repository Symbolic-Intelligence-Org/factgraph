from __future__ import annotations

import unittest
from pathlib import Path


class DocsV2ClarityV1Tests(unittest.TestCase):
    def test_authoring_overview_explains_strict_v2_inputs(self) -> None:
        text = _read("src/factpy_kernel/authoring/docs/01_overview.md")
        self.assertIn("`head` 结构决定默认路径", text)
        self.assertIn("不再支持 `materialize_as` / `id_policy`", text)
        self.assertIn("最小输入示例", text)

    def test_service_overview_explains_candidate_v2_payload(self) -> None:
        text = _read("src/factpy_kernel/service/docs/01_overview.md")
        self.assertIn("CandidateSet` v2", text)
        self.assertIn("payload 形态为 `terms`", text)
        self.assertIn("不要裁剪 `terms`/identity 字段", text)
        self.assertIn("最小请求示例（accept）", text)

    def test_adapter_overview_explains_entity_fact_graph_shape(self) -> None:
        text = _read("src/factpy_kernel/adapters/docs/01_souffle_adapter.md")
        self.assertIn("entity + fact 的候选图", text)
        self.assertIn("`candidate_kind`", text)
        self.assertIn("`terms[0]` 可为 `candidate_ref`", text)
        self.assertIn("最小输出形态（示意）", text)

    def test_sdk_docs_include_migration_and_templates(self) -> None:
        rules_text = _read("src/factpy_kernel/sdk/docs/03_rules_and_derivations.md")
        api_text = _read("src/factpy_kernel/sdk/docs/04_api_surface.md")
        self.assertIn("从旧写法迁移到 v2（速查）", rules_text)
        self.assertIn("不要再按 `payload[\"e_ref\"]` / `payload[\"rest_terms\"]` 读取", rules_text)
        self.assertIn("最小闭环示例", rules_text)
        self.assertIn("常用调用模板（v2）", api_text)
        self.assertIn("不再使用 `materialize_as` / `id_policy`", api_text)


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":
    unittest.main()
