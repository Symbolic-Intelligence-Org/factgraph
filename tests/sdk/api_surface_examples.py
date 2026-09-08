"""Execute the actual Namespace Map snippet, with no mocked SDK or engine."""

from __future__ import annotations

import re
import sys
from types import ModuleType
from unittest.mock import patch


def execute_namespace_map(text: str) -> dict[str, object]:
    """Return the example's results; always close its in-memory graph."""
    section = text.split("## 0. Namespace Map\n", 1)[1].split("\n---\n", 1)[0]
    examples = re.findall(r"```python\n(.*?)\n```", section, flags=re.DOTALL)
    if len(examples) != 1:
        raise AssertionError("Namespace Map must contain one complete executable example")
    module = ModuleType("_factgraph_namespace_map_example")
    with patch.dict(sys.modules, {module.__name__: module}):
        try:
            code = compile(examples[0], "04_api_surface.en.md:NamespaceMap", "exec", dont_inherit=True)
            exec(code, module.__dict__)  # noqa: S102 - execute test-owned docs and fixed negative fixtures, never user input.
            return module.__dict__
        finally:
            graph = module.__dict__.get("fg")
            if graph is not None:
                graph.close()
