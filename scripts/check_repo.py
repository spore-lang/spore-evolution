#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "check-jsonschema",
# ]
# ///

from __future__ import annotations

import sys
from collections.abc import Callable

from check_contract_schemas import main as check_contract_schemas
from check_sep_index import main as check_sep_index
from check_surface_consistency import main as check_surface_consistency
from check_terminology_consistency import main as check_terminology_consistency
from validate_sep_documents import main as validate_sep_documents

CHECKS: tuple[tuple[str, Callable[[], int]], ...] = (
    ("SEP index", check_sep_index),
    ("Contract schemas", check_contract_schemas),
    ("SEP documents", validate_sep_documents),
    ("Terminology consistency", check_terminology_consistency),
    ("Surface consistency", check_surface_consistency),
)


def main() -> int:
    failed: list[str] = []

    for name, check in CHECKS:
        if check() != 0:
            failed.append(name)

    if failed:
        print("Repository checks failed:\n", file=sys.stderr)
        for name in failed:
            print(f"- {name}", file=sys.stderr)
        return 1

    print(f"All {len(CHECKS)} repository checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
