#!/usr/bin/env -S uv run

from __future__ import annotations

import re
import sys

from sep_common import ROOT

TARGETS = (
    ROOT / "README.md",
    ROOT / "VISION.md",
    ROOT / "VISION.zh-CN.md",
    ROOT / "GLOSSARY.md",
    *sorted((ROOT / "seps").glob("SEP-*.md")),
)

FORBIDDEN_PATTERNS = (
    (
        re.compile(r"\b[Cc]apab(?:ility|ilities)\b"),
        "retired non-effect terminology; use `effect`, `effect surface`, or `effect context`",
    ),
    (
        re.compile(r"\bruntime[- ]effects?\b", re.IGNORECASE),
        "retired split term `runtime effect`; use `effect` unless contrasting with runtime behavior generally",
    ),
    (
        re.compile(r"能力表面|能力上下文|运行时效应"),
        "retired zh-CN terminology; use `效应表面`, `效应上下文`, or `效应`",
    ),
    (
        re.compile(r"\bC0xxx\b"),
        "retired effect diagnostic prefix `C0xxx`; use `F0xxx`",
    ),
    (
        re.compile(r"\bNetRead\b"),
        "retired term `NetRead`; use `NetConnect` or `NetListen` depending on intent",
    ),
    (
        re.compile(r"\bNetWrite\b"),
        "retired term `NetWrite`; use `NetConnect` or `NetListen` depending on intent",
    ),
    (
        re.compile(r"\bStateRead\b"),
        "retired term `StateRead`; mutable state is no longer a built-in external effect",
    ),
    (
        re.compile(r"\bStateWrite\b"),
        "retired term `StateWrite`; mutable state is no longer a built-in external effect",
    ),
    (
        re.compile(r"cost\s*<="),
        "retired resource syntax `cost <=`; use `budget { ... }` when realization shape must be constrained",
    ),
    (
        re.compile(r"\bcost\s*\["),
        "retired positional resource syntax; use `budget { ... }`",
    ),
    (
        re.compile(r"\bCostVector\b|\bCostExpr\b|@unbounded|with_cost_limit"),
        "retired resource-cost terminology; use budget and evidence terminology",
    ),
    (
        re.compile(r"\bspec\s*\{|\bexample\s+\"|\blaw\s+\""),
        "retired spec syntax; use `properties { name(params): expr }`",
    ),
    (
        re.compile(r"\bwhere\s+[A-Z][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*:"),
        "retired standalone generic-bound syntax; use inline type parameter bounds",
    ),
    (
        re.compile(r"\bsig hash\b|\bimpl hash\b|\bspec hash\b"),
        "retired hash labels; use named signature provenance hash fields",
    ),
)

ALLOWED_LINE_SNIPPETS = {
    ROOT / "seps" / "SEP-0003-effect-system.md": (
        "No `StateRead`/`StateWrite`.",
        "`NetConnect`/`NetListen` instead of `NetRead`/`NetWrite`.",
    ),
}


def main() -> int:
    violations: list[str] = []

    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        allowed_snippets = ALLOWED_LINE_SNIPPETS.get(path, ())
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(snippet in line for snippet in allowed_snippets):
                continue

            for pattern, message in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}: {message}\n    {line}"
                    )

    if violations:
        print("Terminology consistency check failed:\n", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1

    print("Terminology consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
