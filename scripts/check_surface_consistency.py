#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from sep_common import (
    GUIDING_QUESTIONS_HEADING,
    GUIDING_QUESTIONS_LINK_FRAGMENT,
    ROOT,
    draft_markdown_files,
    iter_markdown_lines,
    relative_path,
    report_errors,
    sep_markdown_files,
    template_markdown_files,
    vision_files,
)


def add_pattern_errors(
    errors: list[str],
    paths: Iterable[Path],
    pattern: re.Pattern[str],
    message: str,
) -> None:
    for path, line_no, line in iter_markdown_lines(paths):
        if pattern.search(line):
            errors.append(f"{relative_path(path)}:{line_no}: {message}: {line.strip()}")


def self_markdown_files() -> list[Path]:
    return [
        ROOT / "README.md",
        ROOT / "GLOSSARY.md",
        *sep_markdown_files(),
    ]


def user_facing_markdown_files() -> list[Path]:
    return [
        ROOT / "README.md",
        ROOT / "GLOSSARY.md",
        *vision_files(),
        *sep_markdown_files(),
        *draft_markdown_files(),
        *template_markdown_files(),
    ]


def files_outside_sep_0000() -> list[Path]:
    return [
        path
        for path in user_facing_markdown_files()
        if path.name != "SEP-0000-process.md"
    ]


def main() -> int:
    errors: list[str] = []
    own_docs = self_markdown_files()

    forbidden_self_patterns = [
        (
            re.compile(r"spore/docs/DESIGN\.md"),
            "use spore/SPARK.md or spore/docs/decisions/syntax.md instead of the retired design path",
        ),
        (
            re.compile(r"\bwhere\s+[A-Z][A-Za-z0-9_]*(?:\[[^\]]+\])?\s*:"),
            "standalone generic bounds are retired; use inline type parameter bounds",
        ),
        (
            re.compile(r"\bWhereClause\b|\bWhereConstraint\b|\bBoundExpr\b"),
            "standalone generic-bound grammar is retired",
        ),
        (
            re.compile(r"\bcost\s*\["),
            "positional resource syntax is retired; use `budget { ... }`",
        ),
        (
            re.compile(
                r"\bCostVector\b|\bCostExpr\b|four-slot|4D|four-dimensional|@unbounded|with_cost_limit"
            ),
            "old resource-cost terminology is retired",
        ),
        (
            re.compile(
                r"\bspec\s*\{|\bSpecClause\b|\bSpecItem\b|\bExampleItem\b|\bLawItem\b"
            ),
            "the old spec block grammar is retired; use `properties { ... }`",
        ),
        (
            re.compile(r"\bexample\s+\"|\blaw\s+\""),
            "old spec item keywords are retired; use named properties",
        ),
        (
            re.compile(r"\bspec hash\b|\bsig hash\b|\bimpl hash\b"),
            "old hash labels are retired; use signature_hash, intent_hash, property_hash, realization_hash, or evidence_hash",
        ),
        (
            re.compile(r"\bK0xxx\b|\bS0xxx\b|`K[0-9]{4}`|`S[0-9]{4}`"),
            "old cost/spec diagnostic prefixes are retired; use B0xxx and P0xxx",
        ),
        (
            re.compile(r"(?:->|:)\s*`?Unit\b`?"),
            "use `()` as the unit type surface spelling",
        ),
        (
            re.compile(
                r"\b(?:current|Current|currently|Currently|today|Today|implemented|Implemented|"
                r"implementation status|not yet implemented|stable implementation|current stable|"
                r"current implementation|current design|current target|current wave|for the current|status quo)\b"
            ),
            "keep SEPs design-oriented; avoid implementation or present-status wording",
        ),
    ]

    for pattern, message in forbidden_self_patterns:
        add_pattern_errors(errors, own_docs, pattern, message)

    add_pattern_errors(
        errors,
        user_facing_markdown_files(),
        re.compile(
            r"\bSignature\s+v[0-9]+\b|\bV[0-9]+\b|\bv[0-9]+(?:\.[0-9]+)*\b|"
            r"\bver" r"sion[- ]range\b|\bSemantic ver" r"sion\b|\bChinese ver" r"sion\b|"
            r"版本" r"号|小设计" r"版本"
        ),
        "avoid numbered narrative labels in user-facing prose; use stable names instead",
    )

    add_pattern_errors(
        errors,
        user_facing_markdown_files(),
        re.compile(r"\bReviewing\b|\bWithdrawn\b|\bwithdrawn\b"),
        "SEP status prose must use only Draft, Accepted, Rejected, or Superseded",
    )

    add_pattern_errors(
        errors,
        files_outside_sep_0000(),
        re.compile(re.escape(GUIDING_QUESTIONS_HEADING)),
        "guiding questions belong in SEP-0000; link to SEP-0000 instead of duplicating them",
    )
    add_pattern_errors(
        errors,
        vision_files(),
        re.compile(r"^## (?:Recommended syntax shape|推荐语法)"),
        "vision documents should stay principle-level; syntax shape belongs in concrete SEPs",
    )
    add_pattern_errors(
        errors,
        vision_files(),
        re.compile(r"^## (?:Guiding questions\b|.*引导问题)"),
        "vision documents should stay principle-level; guiding questions belong in SEP-0000",
    )

    for template in template_markdown_files():
        if not template.is_file():
            continue
        text = template.read_text(encoding="utf-8")
        if GUIDING_QUESTIONS_LINK_FRAGMENT not in text:
            errors.append(
                f"{relative_path(template)}: must link to `{GUIDING_QUESTIONS_LINK_FRAGMENT}` so authors "
                "find the canonical guiding-question section in SEP-0000"
            )

    return report_errors(
        errors,
        "Surface consistency check failed",
        success_message="Surface consistency check passed.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
