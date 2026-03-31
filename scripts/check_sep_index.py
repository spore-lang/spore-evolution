#!/usr/bin/env -S uv run

from __future__ import annotations

import argparse
import json
import sys

from sep_common import INDEX_PATH, build_sep_index, load_documents


def expected_index_text() -> tuple[str, list[str]]:
    documents, errors = load_documents()
    if errors:
        return "", errors

    payload = build_sep_index(documents)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n", []


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or update seps-index.json")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Write the expected seps-index.json instead of failing on drift.",
    )
    args = parser.parse_args()

    expected, errors = expected_index_text()
    if errors:
        print("SEP index generation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    current = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else None

    if args.fix:
        INDEX_PATH.write_text(expected, encoding="utf-8")
        if current == expected:
            print("seps-index.json is already up to date.")
        else:
            print("Updated seps-index.json.")
        return 0

    if current != expected:
        print(
            "seps-index.json is out of date. Run `uv run scripts/check_sep_index.py --fix`.",
            file=sys.stderr,
        )
        return 1

    print("seps-index.json is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
