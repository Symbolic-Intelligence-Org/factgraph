from __future__ import annotations

from pathlib import Path


def tsv_cell_v1_encode(x: str) -> str:
    if not isinstance(x, str):
        raise TypeError("tsv_cell_v1_encode expects str")
    return x.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def tsv_cell_v1_decode(s: str) -> str:
    if not isinstance(s, str):
        raise TypeError("tsv_cell_v1_decode expects str")

    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        if i + 1 >= n:
            raise ValueError("invalid tsv escape: trailing backslash")
        nxt = s[i + 1]
        if nxt == "t":
            out.append("\t")
        elif nxt == "n":
            out.append("\n")
        elif nxt == "\\":
            out.append("\\")
        else:
            raise ValueError(f"invalid tsv escape sequence: \\{nxt}")
        i += 2

    return "".join(out)


def write_tsv(path: Path, rows: list[list[str]]) -> None:
    if not isinstance(path, Path):
        path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for row in rows:
        if not isinstance(row, list):
            raise TypeError("each row must be list[str]")
        encoded_row: list[str] = []
        for cell in row:
            if not isinstance(cell, str):
                raise TypeError("tsv rows must contain only str cells")
            encoded_row.append(tsv_cell_v1_encode(cell))
        lines.append("\t".join(encoded_row))

    with path.open("w", encoding="utf-8", newline="") as f:
        for line in lines:
            f.write(line)
            f.write("\n")
