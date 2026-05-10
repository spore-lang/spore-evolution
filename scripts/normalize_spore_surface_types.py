#!/usr/bin/env -S uv run

"""Rewrite legacy surface names inside ```spore / ```Spore fences only.

Substitutions (whole words):
- String -> Str
- Int -> I64
- Float -> F64

Does not modify other code fences (Rust, text, etc.)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from sep_common import ROOT

# ```spore or ```Spore, consume optional info string after language token.
FENCE_OPEN = re.compile(r"^```[Ss]pore[^\n]*\n", re.MULTILINE)
FENCE_CLOSE = re.compile(r"^```\s*$", re.MULTILINE)

WORD_STRING = re.compile(r"\bString\b")
WORD_INT = re.compile(r"\bInt\b")
WORD_FLOAT = re.compile(r"\bFloat\b")


def transform_spore_block(body: str) -> str:
    body = WORD_STRING.sub("Str", body)
    body = WORD_INT.sub("I64", body)
    body = WORD_FLOAT.sub("F64", body)
    return body


def iter_spore_blocks(text: str) -> list[tuple[int, int, str, int]]:
    """(body_start, body_end, body, next_scan_pos). body_end starts at ``` line."""
    spans: list[tuple[int, int, str, int]] = []
    pos = 0
    while True:
        m_open = FENCE_OPEN.search(text, pos)
        if not m_open:
            break
        body_start = m_open.end()
        m_close = FENCE_CLOSE.search(text[body_start:])
        if not m_close:
            break
        body_end = body_start + m_close.start()
        body = text[body_start:body_end]
        next_pos = body_start + m_close.end()
        spans.append((body_start, body_end, body, next_pos))
        pos = next_pos
    return spans


def process_file(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    spans = iter_spore_blocks(raw)
    if not spans:
        return False

    pieces: list[str] = []
    last = 0
    changed = False
    for body_start, body_end, body, next_pos in spans:
        pieces.append(raw[last:body_start])
        new_body = transform_spore_block(body)
        if new_body != body:
            changed = True
        pieces.append(new_body)
        # Keep original closing fence + prose between fences verbatim.
        pieces.append(raw[body_end:next_pos])
        last = next_pos
    pieces.append(raw[last:])
    if not changed:
        return False
    path.write_text("".join(pieces), encoding="utf-8", newline="\n")
    return True


def main(argv: list[str]) -> int:
    paths = [Path(p) for p in argv[1:]] if len(argv) > 1 else sorted((ROOT / "seps").glob("SEP-*.md"))
    updated = sum(process_file(p) for p in paths)
    print(f"Updated {updated} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
