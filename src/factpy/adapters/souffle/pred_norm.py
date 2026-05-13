from __future__ import annotations

import re


_ENCODED_HEX_RE = re.compile(r"^_h([0-9a-f]{2})_")


def normalize_pred_id(pred_id: str) -> str:
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError("pred_id must be non-empty string")

    parts: list[str] = ["p_"]
    for ch in pred_id:
        if ch.isascii() and ch.isalnum():
            parts.append(ch)
        elif ch == ":":
            parts.append("_")
        elif ch == "_":
            parts.append("__")
        else:
            parts.append(f"_h{ord(ch):02x}_")
    return "".join(parts)


def denormalize_engine_pred(engine_pred: str) -> str:
    if not isinstance(engine_pred, str) or not engine_pred.startswith("p_"):
        raise ValueError("engine_pred must start with 'p_'")

    encoded = engine_pred[2:]
    out: list[str] = []
    i = 0
    n = len(encoded)

    while i < n:
        ch = encoded[i]
        if ch != "_":
            out.append(ch)
            i += 1
            continue

        if i + 1 < n and encoded[i + 1] == "_":
            out.append("_")
            i += 2
            continue

        match = _ENCODED_HEX_RE.match(encoded[i:])
        if match:
            out.append(chr(int(match.group(1), 16)))
            i += len(match.group(0))
            continue

        out.append(":")
        i += 1

    return "".join(out)
