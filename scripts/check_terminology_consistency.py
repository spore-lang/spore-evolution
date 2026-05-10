#!/usr/bin/env -S uv run

from __future__ import annotations

import re
import sys
from pathlib import Path

from sep_common import ROOT

TARGETS = (
    ROOT / "GLOSSARY.md",
    ROOT / "seps" / "SEP-0003-effect-system.md",
    ROOT / "seps" / "SEP-0004-cost-analysis.md",
    ROOT / "seps" / "SEP-0006-compiler-architecture.md",
    ROOT / "seps" / "SEP-0008-module-package-system.md",
)

FORBIDDEN_PATTERNS = (
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
        "retired ASCII syntax `cost <=`; use four-slot `cost [compute, alloc, io, parallel]`",
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
