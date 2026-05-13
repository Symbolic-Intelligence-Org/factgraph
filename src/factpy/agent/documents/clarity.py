from __future__ import annotations

import re
from typing import Literal


PatternType = Literal["if_then", "entity_relation", "definition", "narrative"]

_SECTION_PATTERNS = (
    re.compile(r"^#{1,6}\s+(.+)$"),
    re.compile(r"^(Article\s+\d+(?:\.\d+)*)", re.IGNORECASE),
    re.compile(r"^(第\s*[一二三四五六七八九十百零\d]+\s*(?:条|章|节))"),
    re.compile(r"^(Section\s+\d+(?:\.\d+)*)", re.IGNORECASE),
)

_IF_THEN_PATTERNS = (
    re.compile(r"if\s+.+\s+then\s+", re.IGNORECASE | re.DOTALL),
    re.compile(r"当\s*.+\s*时"),
    re.compile(r"若\s*.+\s*则"),
    re.compile(r"shall\s+.+\s+when", re.IGNORECASE | re.DOTALL),
)

_DEFINITION_PATTERNS = (
    re.compile(r"^.+\s+(means|refers to|is defined as)\s+", re.IGNORECASE),
    re.compile(r"^.+\s*(?:是指|定义为)\s*"),
)

_CLEAR_VERB_PATTERN = re.compile(
    r"\b(is|are|has|have|owns?|contains?|requires?|means|refers|supports?)\b|"
    r"(是|有|属于|包含|要求|支持)"
)


def compute_structural_clarity(text: str) -> tuple[float, PatternType]:
    stripped = text.strip()
    if not stripped:
        return (0.0, "narrative")

    if any(pattern.search(stripped) for pattern in _IF_THEN_PATTERNS):
        return (0.9, "if_then")

    if any(pattern.search(stripped) for pattern in _DEFINITION_PATTERNS):
        return (0.7, "definition")

    if len(stripped) < 100 and _has_clear_verb(stripped):
        return (0.5, "entity_relation")

    return (0.2, "narrative")


def detect_section_label(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in _SECTION_PATTERNS:
            match = pattern.search(stripped)
            if match:
                return match.group(1).strip() if match.groups() else stripped
        break
    return None


def _has_clear_verb(text: str) -> bool:
    return bool(_CLEAR_VERB_PATTERN.search(text))
