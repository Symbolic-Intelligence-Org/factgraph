"""Shared parsing helpers for the problog adapter package."""
from __future__ import annotations


def _split_top_level_args(args_text: str) -> list[str]:
    """Split comma-separated args respecting nesting and quotes."""
    args: list[str] = []
    start = 0
    depth = 0
    in_single = False
    in_double = False
    i = 0
    while i < len(args_text):
        ch = args_text[i]
        if in_single:
            if ch == "'" and i + 1 < len(args_text) and args_text[i + 1] == "'":
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            i += 1
            continue
        if ch in "([{":
            depth += 1
            i += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            i += 1
            continue
        if ch == "," and depth == 0:
            args.append(args_text[start:i].strip())
            start = i + 1
        i += 1
    args.append(args_text[start:].strip())
    return args
